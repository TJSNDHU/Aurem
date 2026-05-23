"""
services/consent_data_network.py — iter 331c Sprint 6.1

Consent-Based Data Network — PIPEDA / GDPR compliant.

Flow:
  1. Tenant sets `data_sharing_consent = true` via PATCH on their
     profile (default = false).
  2. Post-campaign hook fires every time `outreach_history` gets a new
     record. If the lead's tenant has consent=true, the hook extracts
     STRICTLY non-PII metadata (industry, city, region, country,
     channel, outcome) and writes it to `aurem_network_leads`.
  3. The aggregated network powers a future predictive lead scorer —
     but at this stage the deliverable is the *legal moat*: a fully
     consented, anonymized lead-quality network.
  4. When a tenant opts OUT (true → false), a background task deletes
     all their previously contributed records within 30 days (the
     hard-delete is wired to run on the daily scheduler tick).

What we NEVER copy into `aurem_network_leads`:
  - business_name, email, phone, website, address, owner_name, notes
  - lead_id, tenant_id (raw) — we hash tenant_id to a stable but
    non-reversible token so we can still apply 30-day deletion.
  - free-text fields of any kind.

Public API:
    set_db(database)
    set_consent(tenant_id, consent: bool, actor_email) -> dict
    get_consent(tenant_id) -> dict
    extract_anonymized_record(lead_doc, outreach_doc) -> dict | None
    record_network_event_if_consented(lead_id, outreach_doc) -> dict
    purge_revoked_tenant(tenant_id) -> dict
    purge_scheduler_tick() -> dict

Portability: zero Emergent imports. All env-overridable.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────
_NETWORK_COLLECTION = os.environ.get(
    "ORA_NETWORK_COLLECTION", "aurem_network_leads"
)
_PROFILES_COLLECTION = os.environ.get(
    "ORA_TENANT_PROFILES", "user_profiles"
)
_LEADS_COLLECTION = os.environ.get(
    "ORA_LEADS_COLLECTION", "leads"
)
_OUTREACH_COLLECTION = os.environ.get(
    "ORA_OUTREACH_COLLECTION", "outreach_history"
)

# Tenant-id hash salt — stable so we can still target a tenant for
# deletion, but irreversible.
_TENANT_HASH_SALT = os.environ.get("ORA_NETWORK_TENANT_SALT", "aurem-network-v1")

# Hard-delete grace period after revocation.
_GRACE_DAYS = int(os.environ.get("ORA_NETWORK_GRACE_DAYS", "30"))

_db = None


def set_db(database) -> None:
    global _db
    _db = database


# ── Consent state management ────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_tenant(tenant_id: str) -> str:
    """One-way hash. Stable across calls, never reversible to the
    original tenant_id without the salt — and the salt never leaves
    the server."""
    if not tenant_id:
        return ""
    raw = f"{_TENANT_HASH_SALT}|{tenant_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


async def set_consent(tenant_id: str, consent: bool, actor_email: str = "") -> dict:
    """Toggle a tenant's data_sharing_consent.

    On false→true: just records the consent + timestamp.
    On true→false: records revocation and schedules a 30-day delete.

    Returns the new consent state + the next purge timestamp if revoked.
    """
    if _db is None:
        return {"ok": False, "error": "DB not wired"}
    if not tenant_id or not isinstance(tenant_id, str):
        return {"ok": False, "error": "tenant_id is required"}

    profile = await _db[_PROFILES_COLLECTION].find_one(
        {"tenant_id": tenant_id}, {"_id": 0, "data_sharing_consent": 1}
    )
    prev = bool((profile or {}).get("data_sharing_consent"))
    consent = bool(consent)

    now = _now_iso()
    update: dict[str, Any] = {
        "data_sharing_consent": consent,
        "consent_updated_at":   now,
        "consent_actor":        actor_email,
    }
    if not consent and prev:
        # opted out — schedule purge
        purge_at = (
            datetime.now(timezone.utc) + timedelta(days=_GRACE_DAYS)
        ).isoformat()
        update["consent_revoked_at"]   = now
        update["network_purge_due_at"] = purge_at
    elif consent and not prev:
        update["consent_granted_at"]   = now
        update.pop("consent_revoked_at", None)
        update["network_purge_due_at"] = None

    await _db[_PROFILES_COLLECTION].update_one(
        {"tenant_id": tenant_id},
        {"$set": update, "$setOnInsert": {"tenant_id": tenant_id,
                                           "created_at": now}},
        upsert=True,
    )
    return {
        "ok":               True,
        "tenant_id":        tenant_id,
        "previous_consent": prev,
        "current_consent":  consent,
        "purge_due_at":     update.get("network_purge_due_at"),
    }


async def get_consent(tenant_id: str) -> dict:
    """Return the current consent state + 20%-discount flag."""
    if _db is None:
        return {"ok": False, "error": "DB not wired"}
    profile = await _db[_PROFILES_COLLECTION].find_one(
        {"tenant_id": tenant_id},
        {"_id": 0, "data_sharing_consent": 1, "consent_granted_at": 1,
         "consent_revoked_at": 1, "network_purge_due_at": 1},
    )
    consent = bool((profile or {}).get("data_sharing_consent"))
    # Count anonymized contributions this calendar month (for the
    # cockpit tile "Data shared: N anonymized leads this month").
    contributed_this_month = 0
    try:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0,
                                    microsecond=0).isoformat()
        contributed_this_month = await _db[_NETWORK_COLLECTION].count_documents({
            "tenant_token": _hash_tenant(tenant_id),
            "ts":           {"$gte": month_start},
        })
    except Exception:
        pass
    return {
        "ok":                       True,
        "tenant_id":                tenant_id,
        "data_sharing_consent":     consent,
        "discount_active":          consent,
        "discount_pct":             20 if consent else 0,
        "consent_granted_at":       (profile or {}).get("consent_granted_at"),
        "consent_revoked_at":       (profile or {}).get("consent_revoked_at"),
        "network_purge_due_at":     (profile or {}).get("network_purge_due_at"),
        "contributed_this_month":   contributed_this_month,
    }


# ── Anonymization (the core compliance check) ──────────────────────

# Allowed non-PII fields. Anything outside this set is DROPPED.
_NON_PII_LEAD_FIELDS = {
    "industry", "category", "city", "region", "province", "state",
    "country", "company_size", "employees",
}
_NON_PII_OUTREACH_FIELDS = {
    "type", "result", "outcome", "status",
}

# Patterns that, if matched, force-reject the value (defense in depth).
_PII_PATTERNS = [
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),  # email
    re.compile(r"\b\+?\d[\d\s().-]{7,}\b"),                          # phone
    re.compile(r"https?://"),                                        # any URL
    re.compile(r"\b\d{1,5}\s+[A-Za-z]+\s+(Street|St|Avenue|Ave|Road|Rd|Blvd)\b",
                re.IGNORECASE),                                      # street
]


def _is_pii_safe(value: Any) -> bool:
    """True if `value` contains no PII patterns."""
    if value is None:
        return True
    if isinstance(value, (int, float, bool)):
        return True
    s = str(value)
    for pat in _PII_PATTERNS:
        if pat.search(s):
            return False
    return True


def extract_anonymized_record(
    lead_doc: dict,
    outreach_doc: dict,
    tenant_token: str = "",
) -> dict | None:
    """Build the strictly non-PII record we persist to aurem_network_leads.

    Returns None if there's not enough non-PII data to be useful
    (e.g. lead has no industry AND no city) — we don't want empty rows.
    """
    if not isinstance(lead_doc, dict) or not isinstance(outreach_doc, dict):
        return None

    out: dict[str, Any] = {
        "tenant_token": tenant_token,
        "ts":           _now_iso(),
    }

    for f in _NON_PII_LEAD_FIELDS:
        v = lead_doc.get(f)
        if v is None or v == "":
            continue
        if not _is_pii_safe(v):
            continue
        out[f] = str(v).strip()[:60]

    for f in _NON_PII_OUTREACH_FIELDS:
        v = outreach_doc.get(f)
        if v is None or v == "":
            continue
        if not _is_pii_safe(v):
            continue
        out[f"outreach_{f}"] = str(v).strip()[:30]

    # Channel — derive from channels_attempted list if present
    channels = outreach_doc.get("channels_attempted") or []
    if isinstance(channels, list) and channels:
        # Normalise to a single canonical channel name
        out["channel"] = str(channels[0]).strip().lower()[:20]

    # Conversion outcome — boolean flag derived from result
    res = (outreach_doc.get("result") or "").lower()
    out["converted"] = res in ("converted", "won", "booked", "scheduled", "replied_positive")

    # Drop the row if we extracted nothing useful (industry/city/category all missing).
    if not any(out.get(k) for k in ("industry", "category", "city", "region")):
        return None

    return out


async def record_network_event_if_consented(
    lead_id: str,
    outreach_doc: dict,
) -> dict:
    """Hook called from the outreach pipeline AFTER each attempt.

    Looks up the lead → finds tenant → checks consent → if yes, writes
    an anonymized row to aurem_network_leads. ALWAYS best-effort,
    never blocks the outreach flow.

    Returns a status dict.
    """
    if _db is None:
        return {"ok": False, "reason": "db_not_wired"}
    try:
        lead = await _db[_LEADS_COLLECTION].find_one(
            {"lead_id": lead_id},
            {"_id": 0, "tenant_id": 1, "industry": 1, "category": 1,
             "city": 1, "region": 1, "country": 1, "company_size": 1},
        )
        if not lead:
            return {"ok": False, "reason": "lead_not_found"}
        tenant_id = lead.get("tenant_id") or ""
        if not tenant_id:
            return {"ok": False, "reason": "lead_has_no_tenant"}

        # CRITICAL: check consent BEFORE writing anything.
        profile = await _db[_PROFILES_COLLECTION].find_one(
            {"tenant_id": tenant_id}, {"_id": 0, "data_sharing_consent": 1}
        )
        if not profile or not profile.get("data_sharing_consent"):
            return {"ok": True, "wrote": False, "reason": "consent_false"}

        anon = extract_anonymized_record(
            lead_doc=lead,
            outreach_doc=outreach_doc or {},
            tenant_token=_hash_tenant(tenant_id),
        )
        if not anon:
            return {"ok": True, "wrote": False, "reason": "no_useful_non_pii_fields"}

        await _db[_NETWORK_COLLECTION].insert_one(anon)
        return {"ok": True, "wrote": True, "tenant_token": anon["tenant_token"]}
    except Exception as e:
        logger.warning(f"[consent_network] record failed: {e}")
        return {"ok": False, "reason": str(e)[:200]}


# ── Revocation purge (runs nightly) ─────────────────────────────────

async def purge_revoked_tenant(tenant_id: str) -> dict:
    """Hard-delete every aurem_network_leads row tied to this tenant."""
    if _db is None:
        return {"ok": False, "error": "DB not wired"}
    token = _hash_tenant(tenant_id)
    r = await _db[_NETWORK_COLLECTION].delete_many({"tenant_token": token})
    # Clear the purge_due_at on the profile so we don't re-run.
    await _db[_PROFILES_COLLECTION].update_one(
        {"tenant_id": tenant_id},
        {"$set": {"network_purge_completed_at": _now_iso(),
                   "network_purge_due_at": None}},
    )
    return {"ok": True, "tenant_id": tenant_id, "deleted_count": r.deleted_count}


async def purge_scheduler_tick() -> dict:
    """Run on the daily scheduler. Purges every tenant whose
    `network_purge_due_at` is in the past."""
    if _db is None:
        return {"ok": False, "error": "DB not wired"}
    now = _now_iso()
    due = _db[_PROFILES_COLLECTION].find(
        {"network_purge_due_at": {"$ne": None, "$lte": now}},
        {"_id": 0, "tenant_id": 1, "network_purge_due_at": 1},
    )
    purged: list[dict] = []
    async for doc in due:
        tid = doc.get("tenant_id")
        if not tid:
            continue
        result = await purge_revoked_tenant(tid)
        purged.append({"tenant_id": tid, **result})
    return {"ok": True, "purged_count": len(purged), "purged": purged}


__all__ = [
    "set_db",
    "set_consent", "get_consent",
    "extract_anonymized_record",
    "record_network_event_if_consented",
    "purge_revoked_tenant", "purge_scheduler_tick",
]
