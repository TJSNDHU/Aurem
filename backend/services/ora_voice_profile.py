"""
services/ora_voice_profile.py — iter 326ff (Phase 3 P3.1).

Per-tenant ORA voice tuning. Same agent code, different personality
depending on the customer's industry / preference.

  Roofing contractor   → tone: direct,       formality: casual
  Dental clinic        → tone: warm,         formality: professional
  Restaurant           → tone: friendly,     formality: casual
  Tax accountant       → tone: precise,      formality: formal
  Default              → tone: balanced,     formality: professional

The voice profile is a small dict stored in `db.tenant_ora_voice` keyed
by tenant_id. ORA's system prompt is prepended with a 4-6 line voice
preamble at runtime so the LLM adopts the right register.

Founder can override any field via PUT /api/admin/ora/voice-profile/<tenant_id>.

Public API
──────────
    set_db(database)
    await get_profile(tenant_id) -> dict
    await save_profile(tenant_id, *, tone, formality, signature, industry) -> dict
    await build_voice_preamble(tenant_id) -> str     # what ora_agent prepends
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

_COLLECTION = "tenant_ora_voice"
_db = None
_indexes_ensured = False


def set_db(database) -> None:
    global _db, _indexes_ensured
    _db = database
    _indexes_ensured = False


# Industry → sensible default tone/formality. Sourced from how each
# vertical's customers actually talk. Roofers don't want "kindly note";
# dentists don't want bro-energy.
INDUSTRY_DEFAULTS: dict[str, dict[str, str]] = {
    "roofing":      {"tone": "direct",   "formality": "casual"},
    "construction": {"tone": "direct",   "formality": "casual"},
    "plumbing":     {"tone": "direct",   "formality": "casual"},
    "hvac":         {"tone": "direct",   "formality": "casual"},
    "landscaping":  {"tone": "friendly", "formality": "casual"},
    "dental":       {"tone": "warm",     "formality": "professional"},
    "medical":      {"tone": "warm",     "formality": "professional"},
    "clinic":       {"tone": "warm",     "formality": "professional"},
    "restaurant":   {"tone": "friendly", "formality": "casual"},
    "cafe":         {"tone": "friendly", "formality": "casual"},
    "salon":        {"tone": "friendly", "formality": "casual"},
    "spa":          {"tone": "warm",     "formality": "professional"},
    "accounting":   {"tone": "precise",  "formality": "formal"},
    "tax":          {"tone": "precise",  "formality": "formal"},
    "legal":        {"tone": "precise",  "formality": "formal"},
    "law":          {"tone": "precise",  "formality": "formal"},
    "real_estate":  {"tone": "direct",   "formality": "professional"},
    "fitness":      {"tone": "friendly", "formality": "casual"},
    "retail":       {"tone": "friendly", "formality": "professional"},
    "default":      {"tone": "balanced", "formality": "professional"},
}

VALID_TONES = frozenset(
    {"direct", "warm", "friendly", "precise", "balanced", "playful"}
)
VALID_FORMALITY = frozenset({"casual", "professional", "formal"})


def _normalise_industry(industry: Optional[str]) -> str:
    """Map a free-form industry string to a known key, or 'default'."""
    if not industry:
        return "default"
    lo = industry.lower().strip()
    for key in INDUSTRY_DEFAULTS:
        if key == "default":
            continue
        if key in lo or lo in key:
            return key
    return "default"


async def _ensure_indexes() -> None:
    global _indexes_ensured
    if _indexes_ensured or _db is None:
        return
    try:
        await _db[_COLLECTION].create_index("tenant_id", unique=True)
        _indexes_ensured = True
    except Exception as e:
        logger.warning(f"[voice-profile] index ensure failed: {e}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def get_profile(tenant_id: str) -> dict:
    """Return the saved profile or industry-defaulted fallback."""
    if _db is None or not tenant_id:
        return {"tenant_id": tenant_id, **INDUSTRY_DEFAULTS["default"],
                "industry": "default", "signature": "", "source": "fallback"}
    await _ensure_indexes()
    doc = await _db[_COLLECTION].find_one(
        {"tenant_id": tenant_id},
        {"_id": 0, "tenant_id": 1, "tone": 1, "formality": 1,
         "industry": 1, "signature": 1, "updated_at": 1},
    )
    if doc:
        doc["source"] = "saved"
        ua = doc.get("updated_at")
        if isinstance(ua, datetime):
            doc["updated_at"] = ua.isoformat()
        return doc
    # Synthesize defaults from industry registered on the tenant doc, if any.
    industry_key = "default"
    try:
        t = await _db.tenants.find_one(
            {"tenant_id": tenant_id},
            {"_id": 0, "industry": 1, "category": 1},
        ) or {}
        industry_key = _normalise_industry(t.get("industry") or t.get("category"))
    except Exception:
        pass
    return {
        "tenant_id": tenant_id,
        "industry":  industry_key,
        "signature": "",
        "source":    "industry_default",
        **INDUSTRY_DEFAULTS.get(industry_key, INDUSTRY_DEFAULTS["default"]),
    }


async def save_profile(
    tenant_id: str,
    *,
    tone:      Optional[str] = None,
    formality: Optional[str] = None,
    signature: Optional[str] = None,
    industry:  Optional[str] = None,
) -> dict:
    """Upsert a tenant's voice profile. Validates enums, normalises industry."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    if not tenant_id:
        return {"ok": False, "error": "tenant_id required"}
    if tone is not None and tone not in VALID_TONES:
        return {"ok": False, "error": f"invalid tone (allowed: {sorted(VALID_TONES)})"}
    if formality is not None and formality not in VALID_FORMALITY:
        return {"ok": False, "error": f"invalid formality (allowed: {sorted(VALID_FORMALITY)})"}
    await _ensure_indexes()
    industry_key = _normalise_industry(industry) if industry else None
    cur = await get_profile(tenant_id)
    patch: dict[str, Any] = {
        "tone":      tone      if tone      is not None else cur.get("tone"),
        "formality": formality if formality is not None else cur.get("formality"),
        "signature": (signature if signature is not None else cur.get("signature") or "")[:200],
        "industry":  industry_key if industry_key       is not None else cur.get("industry"),
        "updated_at": _now(),
    }
    await _db[_COLLECTION].update_one(
        {"tenant_id": tenant_id},
        {"$set": patch, "$setOnInsert": {"tenant_id": tenant_id, "created_at": _now()}},
        upsert=True,
    )
    return {"ok": True, "tenant_id": tenant_id, **patch,
            "updated_at": patch["updated_at"].isoformat()}


async def build_voice_preamble(tenant_id: Optional[str]) -> str:
    """Return the ~5-line system-prompt prefix that conditions ORA's
    tone for this tenant. Empty string for unknown / unset tenants
    (ORA's default voice applies)."""
    if not tenant_id:
        return ""
    profile = await get_profile(tenant_id)
    tone = profile.get("tone") or "balanced"
    form = profile.get("formality") or "professional"
    sig  = profile.get("signature") or ""
    ind  = profile.get("industry") or "default"
    lines = [
        "## Tenant voice profile",
        f"- Industry: {ind}",
        f"- Tone: {tone}",
        f"- Formality: {form}",
        ("- Address the founder in plain English. "
         "Match the tone above. Skip filler. "
         "Use trade-specific vocabulary the founder's industry uses daily."),
    ]
    if sig:
        lines.append(f"- Sign replies with: {sig[:120]}")
    return "\n".join(lines) + "\n\n"
