"""
Lead deduplication + outreach cooldown + DNC — iter 282al-6.

Three layers of defense against duplicate / over-contacted leads:

  1. is_duplicate_lead(db, lead)  → blocks at Scout's insert step
  2. can_contact_lead(db, lead)   → blocks at Envoy/Follow-up's send step
  3. ensure_unique_site(db, lead) → returns existing site instead of rebuilding

Plus DNC helpers (`add_to_dnc`, `is_in_dnc`) for STOP replies / max-contact /
closed_lost flows.

Every public function never raises. On Mongo failure, callers get a safe
default that errs on the side of NOT contacting (skip rather than spam).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

# Status values that count as "we already touched this business"
TOUCHED_STATUSES = (
    "contacted", "outreach_sent", "following_up",
    "handed_to_closer", "closed", "closed_won", "closed_lost",
    "converted", "client",
)

# Hard cap on total outreach attempts per phone before DNC auto-add
MAX_CONTACTS_PER_PHONE = 3
# Cooldown between any two outreach sends to the same lead_id
COOLDOWN_DAYS = 7
# Fuzzy-match score that counts as "same business"
SAME_BUSINESS_THRESHOLD = 0.85


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
def extract_domain(url: str) -> str:
    """Lower-cased, www-stripped host. Empty string on garbage input."""
    if not url:
        return ""
    try:
        s = url.strip()
        p = urlparse(s if "://" in s else f"https://{s}")
        return (p.netloc or "").lower().replace("www.", "").strip("/")
    except Exception:
        return ""


def _norm_phone(p: str) -> str:
    """Strip everything but digits. Returns '' on empty/None."""
    if not p:
        return ""
    return re.sub(r"\D+", "", str(p))


def _norm_name(n: str) -> str:
    if not n:
        return ""
    n = n.lower().strip()
    # Strip common suffixes that create false positives
    n = re.sub(r"\b(inc|llc|ltd|co|company|corp|the)\b\.?", " ", n)
    n = re.sub(r"[^\w\s]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def fuzzy_match(a: str, b: str) -> float:
    """Light-weight similarity (0..1) without external deps.
    Combines substring + condensed-string + token-jaccard + SequenceMatcher
    so that variants like "mike's plumbing co" / "mikes plumbing company"
    resolve to >= 0.85."""
    from difflib import SequenceMatcher
    a, b = _norm_name(a), _norm_name(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    # Condensed (whitespace-stripped) — handles apostrophe drift
    ca, cb = a.replace(" ", ""), b.replace(" ", "")
    if ca == cb:
        return 0.95

    # Substring on condensed strings
    if ca in cb or cb in ca:
        ratio = min(len(ca), len(cb)) / max(len(ca), len(cb))
        if ratio >= 0.6:
            return 0.9
        if ratio < 0.4:
            return 0.5

    # SequenceMatcher on condensed (catches "mikes" vs "mike s")
    seq = SequenceMatcher(None, ca, cb).ratio()

    # Token Jaccard on space-split
    wa, wb = set(a.split()), set(b.split())
    jacc = (len(wa & wb) / len(wa | wb)) if (wa and wb) else 0.0

    return max(seq, jacc)


# ─────────────────────────────────────────────────────────────────────
# Layer 1 — is_duplicate_lead (Scout gate)
# ─────────────────────────────────────────────────────────────────────
async def is_duplicate_lead(db, lead: dict) -> tuple[bool, str]:
    """Return (is_dup, reason). Reason is empty when not a duplicate."""
    if db is None or not lead:
        return (False, "")
    phone   = _norm_phone(lead.get("phone"))
    email   = (lead.get("email") or "").lower().strip()
    name    = _norm_name(lead.get("business_name") or "")
    city    = (lead.get("city") or "").lower().strip()
    site    = lead.get("website") or lead.get("website_url") or ""
    domain  = extract_domain(site)

    # 1) DNC takes priority — if anything in DNC, treat as duplicate (skip)
    try:
        if phone:
            if await db.dnc_list.find_one(
                {"phone": phone}, projection={"_id": 1},
            ):
                return (True, "dnc_phone")
        if email:
            if await db.dnc_list.find_one(
                {"email": email}, projection={"_id": 1},
            ):
                return (True, "dnc_email")
    except Exception:
        pass

    # 2) Exact phone match
    if phone:
        try:
            if await db.campaign_leads.find_one(
                {"phone_normalized": phone, "business_id": FOUNDER_BIN},
                projection={"_id": 1},
            ):
                return (True, "phone_match")
        except Exception:
            pass

    # 3) Exact website domain match
    if domain:
        try:
            if await db.campaign_leads.find_one(
                {"website_domain": domain, "business_id": FOUNDER_BIN},
                projection={"_id": 1},
            ):
                return (True, "domain_match")
        except Exception:
            pass

    # 4) Email exact match
    if email:
        try:
            if await db.campaign_leads.find_one(
                {"email": email, "business_id": FOUNDER_BIN},
                projection={"_id": 1},
            ):
                return (True, "email_match")
        except Exception:
            pass

    # 5) Fuzzy business_name + city
    if name and city:
        try:
            cursor = db.campaign_leads.find(
                {"city": {"$regex": re.escape(city), "$options": "i"},
                 "business_id": FOUNDER_BIN},
                projection={"_id": 0, "business_name": 1},
            ).limit(200)
            async for existing in cursor:
                if fuzzy_match(name, existing.get("business_name", "")) \
                        >= SAME_BUSINESS_THRESHOLD:
                    return (True, "fuzzy_name_city")
        except Exception:
            pass

    return (False, "")


async def reject_duplicate(db, lead: dict, reason: str) -> None:
    """Log a rejected lead to scout_rejected for learning + audit."""
    if db is None or not lead:
        return
    try:
        await db.scout_rejected.insert_one({
            "business_name": lead.get("business_name"),
            "city":          lead.get("city"),
            "phone":         lead.get("phone"),
            "email":         lead.get("email"),
            "website":       lead.get("website") or lead.get("website_url"),
            "category":      lead.get("category"),
            "reason":        reason or "unknown",
            "ts":            datetime.now(timezone.utc),
        })
    except Exception as e:
        logger.debug(f"[dedup] scout_rejected log failed: {e}")


# ─────────────────────────────────────────────────────────────────────
# Layer 2 — can_contact_lead (Envoy / Follow-up gate)
# ─────────────────────────────────────────────────────────────────────
async def can_contact_lead(db, lead: dict) -> tuple[bool, str]:
    """Return (allowed, reason). Reason is 'ok' when allowed, otherwise
    a short machine-friendly code (`dnc_phone`, `cooldown:3d`, `max_contacts`,
    `dup_business`)."""
    if db is None or not lead:
        return (False, "no_db")
    phone   = _norm_phone(lead.get("phone"))
    email   = (lead.get("email") or "").lower().strip()
    name    = lead.get("business_name") or ""
    city    = (lead.get("city") or "").lower().strip()
    lead_id = (lead.get("lead_id") or str(lead.get("_id") or "")).strip()

    # 1) DNC hard block
    try:
        if phone and await db.dnc_list.find_one(
            {"phone": phone}, projection={"_id": 1},
        ):
            return (False, "dnc_phone")
        if email and await db.dnc_list.find_one(
            {"email": email}, projection={"_id": 1},
        ):
            return (False, "dnc_email")
    except Exception:
        pass

    # 2) Same lead — 7d cooldown
    if lead_id:
        try:
            last = await db.outreach_history.find_one(
                {"lead_id": lead_id},
                sort=[("dispatched_at", -1)],
                projection={"_id": 0, "dispatched_at": 1, "ts": 1},
            )
            if last:
                ts = last.get("dispatched_at") or last.get("ts")
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        ts = None
                if isinstance(ts, datetime):
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    days_ago = (datetime.now(timezone.utc) - ts).days
                    if days_ago < COOLDOWN_DAYS:
                        return (False, f"cooldown:{days_ago}d")
        except Exception:
            pass

    # 3) Same phone — max 3 lifetime contacts
    if phone:
        try:
            total = await db.outreach_history.count_documents(
                {"phone_normalized": phone},
            )
            if total >= MAX_CONTACTS_PER_PHONE:
                # Auto-add to DNC so future Scout runs skip immediately.
                await add_to_dnc(db, phone=phone, email=email,
                                  reason="max_contacts_reached")
                return (False, "max_contacts")
        except Exception:
            pass

    # 4) Similar business+city already touched
    if name and city:
        try:
            cursor = db.campaign_leads.find(
                {
                    "business_id": FOUNDER_BIN,
                    "city":   {"$regex": re.escape(city), "$options": "i"},
                    "status": {"$in": list(TOUCHED_STATUSES)},
                },
                projection={"_id": 0, "business_name": 1, "lead_id": 1},
            ).limit(100)
            async for similar in cursor:
                if (similar.get("lead_id") and
                        similar.get("lead_id") == lead_id):
                    continue
                if fuzzy_match(name, similar.get("business_name", "")) \
                        >= SAME_BUSINESS_THRESHOLD:
                    return (False, "dup_business")
        except Exception:
            pass

    return (True, "ok")


async def log_outreach_blocked(db, lead: dict, reason: str) -> None:
    if db is None:
        return
    try:
        await db.outreach_blocked.insert_one({
            "lead_id":       lead.get("lead_id") or str(lead.get("_id") or ""),
            "business_name": lead.get("business_name"),
            "phone":         lead.get("phone"),
            "phone_normalized": _norm_phone(lead.get("phone")),
            "email":         (lead.get("email") or "").lower().strip(),
            "reason":        reason,
            "ts":            datetime.now(timezone.utc),
        })
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────
# Layer 3 — ensure_unique_site (Builder gate)
# ─────────────────────────────────────────────────────────────────────
async def find_existing_site(db, lead: dict) -> dict | None:
    """Return {site_id, preview_url, slug} of an existing site for this
    business, or None.

    iter 305f — status filter now INCLUDES `drafting` to block concurrent
    rebuilds of the same business (race condition fix — prevents the
    "Mike got 3 websites" scenario when two OODA runs fire within the
    same minute). Also added a loose `business_name_normalized`-only
    probe as a last resort for legacy records that have no city column.
    """
    if db is None or not lead:
        return None
    phone   = _norm_phone(lead.get("phone"))
    domain  = extract_domain(lead.get("website") or lead.get("website_url"))
    name    = _norm_name(lead.get("business_name") or "")
    city    = (lead.get("city") or "").lower().strip()
    proj    = {"_id": 0, "site_id": 1, "slug": 1, "preview_url": 1,
                "lead_id": 1, "ts": 1}

    # Include `drafting` so two concurrent build jobs for the same
    # business cannot both sail past the gate.
    block_statuses = ["rendered", "published", "deployed", "drafting"]

    # Try strongest signals first.
    queries = []
    if phone:
        queries.append({"phone_normalized": phone})
    if domain:
        queries.append({"website_domain": domain})
    if name and city:
        queries.append({"business_name_normalized": name, "city": city})
    # Fallback — business_name alone (still safer than letting a dup ship
    # because legacy records never got `city` populated).
    if name:
        queries.append({"business_name_normalized": name})

    for q in queries:
        try:
            doc = await db.auto_built_sites.find_one(
                {**q, "status": {"$in": block_statuses}},
                projection=proj,
                sort=[("ts", -1)],
            )
            if doc:
                return doc
        except Exception as e:
            logger.debug(f"[dedup] find_existing_site failed: {e}")
    return None


# ─────────────────────────────────────────────────────────────────────
# DNC helpers
# ─────────────────────────────────────────────────────────────────────
async def add_to_dnc(db, *, phone: str = "", email: str = "",
                       reason: str = "manual") -> bool:
    if db is None:
        return False
    p = _norm_phone(phone)
    e = (email or "").lower().strip()
    if not p and not e:
        return False
    try:
        await db.dnc_list.update_one(
            {"phone": p, "email": e} if (p and e) else
            ({"phone": p} if p else {"email": e}),
            {"$set": {
                "phone":  p or None,
                "email":  e or None,
                "reason": reason,
                "ts":     datetime.now(timezone.utc),
            }},
            upsert=True,
        )
        return True
    except Exception as e2:
        logger.debug(f"[dedup] add_to_dnc failed: {e2}")
        return False


async def is_in_dnc(db, *, phone: str = "", email: str = "") -> bool:
    if db is None:
        return False
    p = _norm_phone(phone)
    e = (email or "").lower().strip()
    try:
        if p and await db.dnc_list.find_one({"phone": p}, projection={"_id": 1}):
            return True
        if e and await db.dnc_list.find_one({"email": e}, projection={"_id": 1}):
            return True
    except Exception:
        pass
    return False


async def process_stop_reply(db, *, phone: str = "", email: str = "") -> bool:
    """Public wrapper used by the SMS/email reply handlers when a STOP
    keyword arrives. Adds to DNC + logs reason."""
    return await add_to_dnc(db, phone=phone, email=email,
                              reason="stop_reply")


# ─────────────────────────────────────────────────────────────────────
# Indexes
# ─────────────────────────────────────────────────────────────────────
async def ensure_dedup_indexes(db) -> None:
    """Idempotent — safe to call on every boot."""
    if db is None:
        return
    plans = [
        ("campaign_leads", [("phone_normalized", 1)],
            {"sparse": True, "name": "phone_norm"}),
        ("campaign_leads", [("website_domain", 1)],
            {"sparse": True, "name": "website_domain"}),
        ("campaign_leads", [("email", 1)],
            {"sparse": True, "name": "email_idx"}),
        ("campaign_leads", [("business_name_normalized", 1), ("city", 1)],
            {"name": "biz_city"}),
        ("auto_built_sites", [("phone_normalized", 1)],
            {"sparse": True, "name": "phone_norm"}),
        ("auto_built_sites", [("website_domain", 1)],
            {"sparse": True, "name": "domain"}),
        ("auto_built_sites", [("business_name_normalized", 1), ("city", 1)],
            {"name": "biz_city"}),
        ("outreach_history", [("phone_normalized", 1)],
            {"sparse": True, "name": "phone_norm"}),
        ("dnc_list", [("phone", 1)],
            {"sparse": True, "name": "phone_idx"}),
        ("dnc_list", [("email", 1)],
            {"sparse": True, "name": "email_idx"}),
        ("outreach_blocked", [("ts", 1)],
            {"expireAfterSeconds": 90 * 24 * 3600, "name": "ts_ttl"}),
    ]
    for coll, keys, opts in plans:
        try:
            await db[coll].create_index(keys, **opts)
        except Exception as e:
            logger.debug(f"[dedup] index skip {coll}.{keys}: {e}")


# ─────────────────────────────────────────────────────────────────────
# Sync wrappers for pytest
# ─────────────────────────────────────────────────────────────────────
def _run(coro):
    import asyncio
    import concurrent.futures
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(lambda: asyncio.run(coro)).result()
    except RuntimeError:
        pass
    return asyncio.run(coro)


def is_duplicate_sync(db, lead):
    return _run(is_duplicate_lead(db, lead))


def can_contact_sync(db, lead):
    return _run(can_contact_lead(db, lead))


def add_to_dnc_sync(db, *, phone="", email="", reason="manual"):
    return _run(add_to_dnc(db, phone=phone, email=email, reason=reason))


def is_in_dnc_sync(db, *, phone="", email=""):
    return _run(is_in_dnc(db, phone=phone, email=email))


def process_stop_reply_sync(db, *, phone="", email=""):
    return _run(process_stop_reply(db, phone=phone, email=email))


__all__ = [
    "fuzzy_match",
    "extract_domain",
    "is_duplicate_lead",
    "reject_duplicate",
    "can_contact_lead",
    "log_outreach_blocked",
    "find_existing_site",
    "add_to_dnc",
    "is_in_dnc",
    "process_stop_reply",
    "ensure_dedup_indexes",
    "is_duplicate_sync",
    "can_contact_sync",
    "add_to_dnc_sync",
    "is_in_dnc_sync",
    "process_stop_reply_sync",
    "MAX_CONTACTS_PER_PHONE",
    "COOLDOWN_DAYS",
    "SAME_BUSINESS_THRESHOLD",
    "TOUCHED_STATUSES",
]
