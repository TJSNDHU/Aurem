"""
Yelp Fusion Scout — primary lead source (iter 282z)
====================================================

Wraps the Yelp Fusion v3 API to fetch real local-business leads with
phone + address + rating + review count. Replaces noise scrapes outright.

Why Yelp first?
  • 5,000 free calls/day on the Fusion plan
  • Phone numbers are pre-formatted (E.164-ready)
  • Quality signal built-in (rating × review_count)
  • Categories are normalized — no need for fuzzy matching
  • Already-vetted SMB pool — no Reddit/Wikipedia residue

Limitation: Yelp does NOT expose the business's own website (the `url`
field returns the yelp.com listing page). We persist that as
`yelp_url` and rely on phone as the primary outreach channel for
Yelp-sourced leads. The Architect step can later harvest the website
by visiting the Yelp page if needed.

Endpoints used:
  GET https://api.yelp.com/v3/businesses/search
  GET https://api.yelp.com/v3/businesses/{id}    (optional — extra detail)

Auth: `Authorization: Bearer {YELP_API_KEY}` header.

Note on filtering: a lead must clear `is_valid_lead()` (≥1 of phone /
email / website) AND not match any `BLOCKED_DOMAINS` from
google_places_scout.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

YELP_API_KEY = os.environ.get("YELP_API_KEY", "").strip()

SEARCH_URL = "https://api.yelp.com/v3/businesses/search"

# Map our scout categories → Yelp Fusion category aliases.
# https://docs.developer.yelp.com/docs/resources-categories
_YELP_CATEGORY_MAP = {
    "roofing": "roofing",
    "roofing contractor": "roofing",
    "plumber": "plumbing",
    "plumbing": "plumbing",
    "electrician": "electricians",
    "hvac": "hvac",
    "lawyer": "lawyers",
    "accountant": "accountants",
    "dentist": "dentists",
    "doctor": "physicians",
    "restaurant": "restaurants",
    "cafe": "cafes",
    "bar": "bars",
    "salon": "hair",
    "barber": "barbers",
    "auto repair": "autorepair",
    "auto dealer": "autodealer",
    "car wash": "carwash",
    "real estate": "realestateagents",
    "gym": "gyms",
    "fitness": "gyms",
    "cleaning": "homecleaning",
    "landscaping": "landscaping",
    "store": "shopping",
    "shop": "shopping",
}


def _strip_phone(p: str) -> str:
    if not p:
        return ""
    return re.sub(r"[^\d+]", "", p).strip()


def _yelp_alias(query: str) -> str:
    q = query.lower().strip()
    if q in _YELP_CATEGORY_MAP:
        return _YELP_CATEGORY_MAP[q]
    for k, v in _YELP_CATEGORY_MAP.items():
        if k in q:
            return v
    return ""  # fall back to free-text term search


async def yelp_leads(
    query: str,
    location: str,
    limit: int = 20,
    radius_m: int = 16000,
) -> dict:
    """Public entrypoint — returns {success, leads:[...]} ready for the scout
    pipeline. Each lead has business_name, phone, address, rating, types,
    yelp_id, yelp_url, source='yelp_fusion'.
    """
    if not YELP_API_KEY:
        logger.warning("[yelp-scout] YELP_API_KEY not set")
        return {"success": False, "leads": [], "total": 0, "source": "yelp_fusion", "error": "no_key"}

    headers = {"Authorization": f"Bearer {YELP_API_KEY}", "Accept": "application/json"}
    params: dict = {
        "location": location,
        "limit": min(max(int(limit), 1), 50),
        "radius": min(max(int(radius_m), 1000), 40000),
        "sort_by": "best_match",
    }
    alias = _yelp_alias(query)
    if alias:
        params["categories"] = alias
    else:
        params["term"] = query

    raw: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(SEARCH_URL, headers=headers, params=params)
            if r.status_code == 401:
                logger.warning("[yelp-scout] 401 — invalid YELP_API_KEY")
                return {"success": False, "leads": [], "total": 0, "source": "yelp_fusion", "error": "unauthorized"}
            if r.status_code != 200:
                logger.warning(f"[yelp-scout] HTTP {r.status_code}: {r.text[:200]}")
                return {"success": False, "leads": [], "total": 0, "source": "yelp_fusion", "error": f"http_{r.status_code}"}
            data = r.json()
            raw = data.get("businesses", []) or []
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[yelp-scout] request failed: {e}")
        return {"success": False, "leads": [], "total": 0, "source": "yelp_fusion", "error": str(e)[:120]}

    # Reuse the canonical noise filter + validation gate from google_places_scout
    try:
        from services.google_places_scout import _is_blocked_url, is_valid_lead
    except Exception:
        _is_blocked_url = lambda _u: False  # noqa: E731
        is_valid_lead = lambda _l: bool(_l.get("phone"))  # noqa: E731

    leads: list[dict] = []
    for b in raw:
        name = (b.get("name") or "").strip()
        if not name:
            continue
        phone = _strip_phone(b.get("phone") or b.get("display_phone") or "")
        loc = b.get("location") or {}
        address_parts = loc.get("display_address") or []
        address = ", ".join(p for p in address_parts if p).strip()

        yelp_url = (b.get("url") or "").strip()
        # Yelp's `url` is the yelp.com listing — never our outreach website.
        if yelp_url and _is_blocked_url(yelp_url):
            yelp_url = ""  # informational only; not a contact channel

        cats = [c.get("title") for c in (b.get("categories") or []) if c.get("title")]
        lead = {
            "business_name": name,
            "phone": phone,
            "website": "",          # Yelp Fusion does NOT expose business website
            "email": "",            # Yelp Fusion does NOT expose email
            "address": address,
            "city": loc.get("city") or "",
            "rating": b.get("rating"),
            "review_count": b.get("review_count"),
            "types": cats,
            "yelp_id": b.get("id"),
            "yelp_url": yelp_url,
            "place_id": None,
            "source": "yelp_fusion",
        }
        if not is_valid_lead(lead):
            continue
        leads.append(lead)

    logger.info(
        f"[yelp-scout] {query!r} @ {location!r} → {len(leads)} valid leads "
        f"(raw={len(raw)})"
    )
    return {
        "success": True,
        "leads": leads,
        "total": len(leads),
        "query": query,
        "location": location,
        "source": "yelp_fusion",
    }
