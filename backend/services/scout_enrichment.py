"""
AUREM Scout Enrichment — Section 3 of growth-engine upgrade
=============================================================
Per spec: applied to every Total-Scout result BEFORE persistence.

Adds 4 capabilities to the Total-Scout discover pipeline:

  1. **DB Dedup**   — drop leads already in `campaign_leads` matched by
     E.164 phone OR (business_name + postal_code) tuple.

  2. **Dead Check** — drop "permanently_closed" / "closed" / "out of
     business" leads from any source.

  3. **Lead Score (1–10)**:
        +3  no website
        +2  reviews 10–100
        +2  valid mobile CA number
        +2  business <2 years old
        +1  email found
        -2  reviews >500
        -3  in DNC list
     Final score clamped to [1, 10].

  4. **Industry Priority** — boosts ordering for the 10 trade verticals
     AUREM is built for (HVAC, Plumbing, Electrical, …). Non-trades
     stay in the queue but rank lower.

The enrichment is a *pure* annotation step — it never mutates the
caller's underlying lead dicts before dedup; it operates on the
already-deduplicated final list and adds:

    lead["score"]              ← int 1..10
    lead["industry"]           ← canonical lowercased trade name or ""
    lead["industry_priority"]  ← int 1..10 (10 = highest priority)
    lead["dnc"]                ← bool
    lead["dead"]               ← bool   (True → excluded by enrich())
    lead["dedup_skipped"]      ← bool   (True → excluded by enrich())
    lead["scored_at"]          ← ISO timestamp

`enrich_and_filter_leads(leads, db)` returns the **filtered** list with
scored survivors, sorted by (industry_priority DESC, score DESC).
"""
from __future__ import annotations

import re
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ─── Industry vocabulary (matches spec order = priority 10..1) ────────
# Higher = better fit for AUREM's blast templates + Retell scripts.
TRADE_PRIORITY: Dict[str, int] = {
    "hvac":          10,
    "plumbing":       9,
    "electrical":     8,
    "roofing":        7,
    "landscaping":    6,
    "cleaning":       5,
    "painting":       4,
    "flooring":       3,
    "renovation":     2,
    "pest control":   1,
}
# Common synonyms / tokens we see in Yelp/OSM categories
_TRADE_TOKENS: List[Tuple[List[str], str]] = [
    (["hvac", "heating", "cooling", "air conditioning", "furnace", "ac repair"], "hvac"),
    (["plumb", "plumber", "drain", "sewer"], "plumbing"),
    (["electric", "electrician", "wiring"], "electrical"),
    (["roof", "shingle", "eavestrough"], "roofing"),
    (["landscap", "lawn", "garden", "tree care"], "landscaping"),
    (["clean", "janitor", "maid", "carpet clean"], "cleaning"),
    (["paint"], "painting"),
    (["floor", "tile", "hardwood", "laminate"], "flooring"),
    (["renov", "remodel", "contractor", "kitchen", "bathroom"], "renovation"),
    (["pest", "exterminator", "rodent", "wildlife"], "pest control"),
]

_DEAD_TOKENS = {
    "permanently_closed", "permanently closed", "closed permanently",
    "out of business", "ceased operations", "closed",
}

E164_RE = re.compile(r"^\+?1?[\s\-\(]*([2-9]\d{2})[\s\-\)]*([2-9]\d{2})[\s\-]*(\d{4})$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
# Canadian non-toll-free area codes that are mostly mobile-eligible.
# (Actual mobile/landline split is opaque without Twilio Lookup; this
# heuristic only filters out known-toll-free which spec rules out.)
_TOLL_FREE_AC = {"800", "833", "844", "855", "866", "877", "888"}


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

async def enrich_and_filter_leads(
    leads: List[Dict[str, Any]],
    db=None,
) -> List[Dict[str, Any]]:
    """Apply dead-check → DB dedup → score → industry priority → sort.

    Returns the filtered & sorted list of survivors. Excluded leads are
    not returned, but a count is logged.

    Safe for `db is None` (returns enriched leads without DB dedup).
    """
    if not leads:
        return []

    # 1. Dead check (cheap, no I/O)
    alive: List[Dict[str, Any]] = []
    n_dead = 0
    for L in leads:
        if _is_dead(L):
            n_dead += 1
            continue
        alive.append(L)

    # 2. DB dedup — single round-trip across ALL alive leads
    n_dup = 0
    if db is not None and alive:
        existing = await _existing_lead_keys(db, alive)
        survivors: List[Dict[str, Any]] = []
        for L in alive:
            if _matches_existing(L, existing):
                n_dup += 1
                continue
            survivors.append(L)
        alive = survivors

    # 3. DNC (cheap — single round-trip too)
    dnc_phones: Set[str] = await _dnc_phone_set(db, alive) if db is not None else set()

    # 4. Score + industry priority (in-place annotation)
    out: List[Dict[str, Any]] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    for L in alive:
        industry = _classify_industry(L)
        L["industry"] = industry
        L["industry_priority"] = TRADE_PRIORITY.get(industry, 0)
        phone_e164 = _to_e164(L.get("phone"))
        is_dnc = bool(phone_e164 and phone_e164 in dnc_phones)
        L["dnc"] = is_dnc
        L["score"] = _score_lead(L, is_dnc=is_dnc, phone_e164=phone_e164)
        L["scored_at"] = now_iso
        out.append(L)

    # 5. Sort: trade priority desc, then score desc, then review_count desc
    out.sort(
        key=lambda x: (
            -(x.get("industry_priority") or 0),
            -(x.get("score") or 0),
            -(int(x.get("review_count") or 0)),
        )
    )

    if n_dead or n_dup:
        logger.info(
            f"[scout-enrich] in={len(leads)} alive={len(alive)} "
            f"dead={n_dead} dup={n_dup} scored={len(out)}"
        )
    return out


# ─────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────

def _is_dead(lead: Dict[str, Any]) -> bool:
    blob = " ".join(
        str(lead.get(k, "")).lower()
        for k in ("status", "business_status", "operational_status", "closed_reason", "name")
    )
    return any(t in blob for t in _DEAD_TOKENS)


def _to_e164(raw: Optional[str]) -> str:
    """Best-effort E.164 normaliser for North-American numbers."""
    if not raw:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    if not digits:
        return ""
    if digits.startswith("1") and len(digits) == 11:
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    if raw.strip().startswith("+"):
        return f"+{digits}"
    return ""


def _is_valid_mobile_ca(phone_e164: str) -> bool:
    """Reject toll-free + non-NA. Anything else assumed mobile-eligible."""
    if not phone_e164 or not phone_e164.startswith("+1") or len(phone_e164) != 12:
        return False
    area = phone_e164[2:5]
    return area not in _TOLL_FREE_AC


def _classify_industry(lead: Dict[str, Any]) -> str:
    """Map free-text categories/name → canonical TRADE_PRIORITY key.

    Returns "" when the lead is outside our 10 trade verticals.
    """
    blob_parts = []
    for k in ("category", "categories", "industry", "type", "types", "name", "description"):
        v = lead.get(k)
        if isinstance(v, list):
            blob_parts.extend(str(x) for x in v if x)
        elif v:
            blob_parts.append(str(v))
    blob = " ".join(blob_parts).lower()
    if not blob:
        return ""
    for tokens, canonical in _TRADE_TOKENS:
        for t in tokens:
            if t in blob:
                return canonical
    return ""


def _score_lead(
    lead: Dict[str, Any], *, is_dnc: bool, phone_e164: str,
) -> int:
    """Compute lead score per spec, clamped to [1, 10]."""
    score = 5  # baseline

    # +3 no website
    web = (lead.get("website") or "").strip()
    if not web or web.lower() in ("none", "n/a", "null"):
        score += 3

    # ±reviews
    rc_raw = lead.get("review_count")
    try:
        rc = int(rc_raw) if rc_raw is not None else 0
    except (TypeError, ValueError):
        rc = 0
    if 10 <= rc <= 100:
        score += 2
    elif rc > 500:
        score -= 2

    # +2 valid mobile CA number
    if _is_valid_mobile_ca(phone_e164):
        score += 2

    # +2 business < 2 years old (best-effort — fields differ per source)
    age_years = _years_in_business(lead)
    if age_years is not None and age_years < 2:
        score += 2

    # +1 email found
    email = (lead.get("email") or "").strip()
    if email and EMAIL_RE.match(email):
        score += 1

    # -3 in DNC
    if is_dnc:
        score -= 3

    return max(1, min(10, score))


def _years_in_business(lead: Dict[str, Any]) -> Optional[float]:
    """Try several common fields. Returns None when unknown."""
    now = datetime.now(timezone.utc)
    for k in ("founded_year", "established", "year_founded", "established_year"):
        v = lead.get(k)
        if not v:
            continue
        try:
            yr = int(str(v)[:4])
            if 1800 < yr < now.year + 1:
                return now.year - yr
        except Exception:
            continue
    for k in ("founded_at", "established_at", "registered_at"):
        v = lead.get(k)
        if not v:
            continue
        try:
            dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            return (now - dt).days / 365.25
        except Exception:
            continue
    return None


# ─────────────────────────────────────────────────────────────────────
# DB lookups (single round-trip each)
# ─────────────────────────────────────────────────────────────────────

async def _existing_lead_keys(
    db, leads: List[Dict[str, Any]],
) -> Dict[str, Set[str]]:
    """Pull all existing dedup keys for the given candidate leads.

    Returns:
        {
          "phones": {<e164>, ...},
          "name_postal": {"name|postal", ...},
        }
    """
    phones: Set[str] = set()
    name_postals: Set[str] = set()
    for L in leads:
        e = _to_e164(L.get("phone"))
        if e:
            phones.add(e)
        np = _name_postal_key(L)
        if np:
            name_postals.add(np)

    found_phones: Set[str] = set()
    found_np: Set[str] = set()

    if phones:
        try:
            cursor = db.campaign_leads.find(
                {"phone_e164": {"$in": list(phones)}},
                {"_id": 0, "phone_e164": 1},
            )
            async for doc in cursor:
                v = doc.get("phone_e164")
                if v:
                    found_phones.add(v)
        except Exception as e:
            logger.debug(f"[scout-enrich] phone dedup lookup failed: {e}")

    if name_postals:
        try:
            cursor = db.campaign_leads.find(
                {"dedup_name_postal": {"$in": list(name_postals)}},
                {"_id": 0, "dedup_name_postal": 1},
            )
            async for doc in cursor:
                v = doc.get("dedup_name_postal")
                if v:
                    found_np.add(v)
        except Exception as e:
            logger.debug(f"[scout-enrich] name+postal dedup lookup failed: {e}")

    return {"phones": found_phones, "name_postal": found_np}


async def _dnc_phone_set(db, leads: List[Dict[str, Any]]) -> Set[str]:
    """Pull DNC matches for our candidate phone numbers."""
    phones = set()
    for L in leads:
        e = _to_e164(L.get("phone"))
        if e:
            phones.add(e)
    if not phones:
        return set()
    found: Set[str] = set()
    try:
        cursor = db.dnc_list.find(
            {"phone_e164": {"$in": list(phones)}},
            {"_id": 0, "phone_e164": 1},
        )
        async for doc in cursor:
            v = doc.get("phone_e164")
            if v:
                found.add(v)
    except Exception as e:
        logger.debug(f"[scout-enrich] DNC lookup failed: {e}")
    return found


def _matches_existing(lead: Dict[str, Any], existing: Dict[str, Set[str]]) -> bool:
    e = _to_e164(lead.get("phone"))
    if e and e in existing.get("phones", set()):
        return True
    np = _name_postal_key(lead)
    if np and np in existing.get("name_postal", set()):
        return True
    return False


def _name_postal_key(lead: Dict[str, Any]) -> str:
    name = (lead.get("name") or lead.get("business_name") or "").strip().lower()
    postal = (lead.get("postal_code") or lead.get("postal") or lead.get("zip") or "").strip().upper().replace(" ", "")
    if not name or not postal:
        return ""
    name = re.sub(r"[^a-z0-9]", "", name)
    return f"{name}|{postal[:6]}"


def annotate_dedup_fields(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Public helper: stamp dedup keys onto a lead dict before insert.

    Callers (auto_blast / hunter) MUST persist these keys so future
    Scout runs can dedup against them.
    """
    e = _to_e164(lead.get("phone"))
    if e:
        lead["phone_e164"] = e
    np = _name_postal_key(lead)
    if np:
        lead["dedup_name_postal"] = np
    return lead


async def ensure_indexes(db) -> None:
    """Idempotent index creation — call once at startup."""
    if db is None:
        return
    try:
        await db.campaign_leads.create_index("phone_e164")
        await db.campaign_leads.create_index("dedup_name_postal")
        await db.dnc_list.create_index("phone_e164", unique=False, sparse=True)
    except Exception as e:
        logger.debug(f"[scout-enrich] index ensure skipped: {e}")
