"""
Google Places Scout — REAL businesses, not noise (iter 282u)
=============================================================

Replaces the Camofox/scrape-Google-Maps approach (which returned Reddit
threads & forum posts as "leads") with the official Google Places API.

Pipeline:
  1) Text Search — `query + location` → place_id list
  2) Place Details — phone, website, address, rating, types
  3) Validate — must have at least ONE of (phone | website | email)
  4) Block known noise domains as defense-in-depth

Requires `GOOGLE_PLACES_API_KEY` (already set in /app/backend/.env).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

# Defense-in-depth: even if a URL slips through, we never send outreach to these.
BLOCKED_DOMAINS = (
    "reddit.com", "quora.com", "linkedin.com",
    "stackexchange.com", "stackoverflow.com",
    "yelp.com/biz_photos", "yelp.com/search", "yelp.com",
    "yellowpages.com/search", "yellowpages.com", "yellowpages.ca",
    "facebook.com/search", "twitter.com/search", "x.com/search",
    "youtube.com/results", "youtube.com", "tiktok.com",
    "instagram.com/explore", "pinterest.com/search",
    "google.com", "google.ca",
    "wikipedia.org", "en.wikipedia.org",
    # Business-for-sale / directory / listing aggregators — not prospect businesses
    "findbusinesses4sale.com", "bizbuysell.com", "bizsold.com",
    "fslocal.com", "canpages.ca", "411.ca",
    "bbb.org/search", "superpages.com",
    "angi.com", "angieslist.com", "houzz.com",
    # National chains — not SMB prospects
    "autozone.com", "walmart.com", "amazon.com", "amazon.ca",
    "homedepot.com", "lowes.com", "costco.com", "target.com",
    "shopify.com/search",
)
BLOCKED_PATH_FRAGMENTS = (
    "/r/",                 # subreddit
    "/forum/", "/forums/",
    "/discussions/",
    "/search?",
    "/threads/",
)


def _is_blocked_url(url: str) -> bool:
    if not url:
        return False
    low = url.lower()
    if any(d in low for d in BLOCKED_DOMAINS):
        return True
    if any(fr in low for fr in BLOCKED_PATH_FRAGMENTS):
        return True
    return False


def is_valid_lead(lead: dict) -> bool:
    """Lead enters pipeline only if it has at least one contact channel
    AND its website (if any) isn't blacklisted."""
    has_contact = bool(
        (lead.get("phone") or "").strip()
        or (lead.get("email") or "").strip()
        or (lead.get("website") or "").strip()
    )
    if not has_contact:
        return False
    site = (lead.get("website") or "").strip()
    if site and _is_blocked_url(site):
        return False
    return True


async def _text_search(query: str, location: str, max_results: int = 20) -> list[dict]:
    if not PLACES_API_KEY:
        logger.warning("[places-scout] GOOGLE_PLACES_API_KEY not set")
        return []
    params = {
        "query": f"{query} in {location}",
        "key": PLACES_API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(TEXT_SEARCH_URL, params=params)
            if r.status_code != 200:
                logger.warning(f"[places-scout] text search HTTP {r.status_code}")
                return []
            data = r.json()
        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            logger.warning(f"[places-scout] API status={data.get('status')} err={data.get('error_message')}")
            return []
        return (data.get("results") or [])[:max_results]
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[places-scout] text search failed: {e}")
        return []


# ─── OSM Overpass fallback (free, no key) ───────────────────────────────
# Used when Google Places returns REQUEST_DENIED / billing-disabled / no key.
# Queries OpenStreetMap for businesses with a phone OR website tag in the
# given bbox derived from the location string.
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Map common scout categories → OSM tag filters
_OSM_CATEGORY_MAP = {
    "roofing": '["craft"="roofer"]',
    "roofing contractor": '["craft"="roofer"]',
    "plumber": '["craft"="plumber"]',
    "plumbing": '["craft"="plumber"]',
    "electrician": '["craft"="electrician"]',
    "hvac": '["craft"="hvac"]',
    "lawyer": '["office"="lawyer"]',
    "accountant": '["office"="accountant"]',
    "dentist": '["amenity"="dentist"]',
    "doctor": '["amenity"="doctors"]',
    "restaurant": '["amenity"="restaurant"]',
    "cafe": '["amenity"="cafe"]',
    "bar": '["amenity"="bar"]',
    "salon": '["shop"="hairdresser"]',
    "barber": '["shop"="hairdresser"]',
    "auto repair": '["shop"="car_repair"]',
    "auto dealer": '["shop"="car"]',
    "car wash": '["amenity"="car_wash"]',
    "real estate": '["office"="estate_agent"]',
    "gym": '["leisure"="fitness_centre"]',
    "fitness": '["leisure"="fitness_centre"]',
    "store": '["shop"]',
    "shop": '["shop"]',
}


async def _geocode(location: str) -> Optional[tuple[float, float, float, float]]:
    """Return (south, west, north, east) bbox for the given location."""
    try:
        async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "AUREM-Scout/1.0"}) as c:
            r = await c.get(NOMINATIM_URL, params={"q": location, "format": "json", "limit": 1})
            data = r.json()
            if not data:
                return None
            bb = data[0].get("boundingbox")
            if not bb or len(bb) != 4:
                return None
            return (float(bb[0]), float(bb[2]), float(bb[1]), float(bb[3]))
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[osm-scout] geocode failed: {e}")
        return None


def _osm_tag_for(query: str) -> str:
    q = query.lower().strip()
    for k, v in _OSM_CATEGORY_MAP.items():
        if k in q:
            return v
    # Fallback — any tagged "shop" with a name
    return '["shop"]'


async def _overpass_search(query: str, location: str, max_results: int = 20) -> list[dict]:
    bbox = await _geocode(location)
    if not bbox:
        logger.warning(f"[osm-scout] could not geocode '{location}'")
        return []
    south, west, north, east = bbox
    tag = _osm_tag_for(query)
    overpass_q = f"""[out:json][timeout:25];
(
  node{tag}["name"]({south},{west},{north},{east});
  way{tag}["name"]({south},{west},{north},{east});
);
out tags center {max_results * 3};"""
    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "AUREM-Scout/1.0", "Accept": "application/json"},
        ) as c:
            r = await c.post(
                OVERPASS_URL,
                content=f"data={httpx.QueryParams({'q': overpass_q})['q']}",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if r.status_code != 200:
                # Retry with simple GET form which most Overpass mirrors accept
                r = await c.get(OVERPASS_URL, params={"data": overpass_q})
            if r.status_code != 200:
                logger.warning(f"[osm-scout] overpass HTTP {r.status_code} body={r.text[:200]}")
                return []
            data = r.json()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[osm-scout] overpass error: {e}")
        return []
    leads: list[dict] = []
    for el in (data.get("elements") or []):
        tags = el.get("tags") or {}
        name = (tags.get("name") or "").strip()
        if not name:
            continue
        phone = (
            tags.get("contact:phone")
            or tags.get("phone")
            or ""
        ).strip()
        website = (
            tags.get("contact:website")
            or tags.get("website")
            or ""
        ).strip()
        email = (tags.get("contact:email") or tags.get("email") or "").strip()
        if not (phone or website or email):
            continue
        addr_parts = [
            tags.get("addr:housenumber"),
            tags.get("addr:street"),
            tags.get("addr:city"),
            tags.get("addr:postcode"),
        ]
        addr = " ".join(p for p in addr_parts if p).strip()
        leads.append({
            "name": name,
            "phone": phone,
            "website": website,
            "email": email,
            "address": addr,
            "source": "osm_overpass",
            "osm_id": f"{el.get('type')}/{el.get('id')}",
        })
        if len(leads) >= max_results:
            break
    return leads


async def _place_details(place_id: str) -> Optional[dict]:
    if not PLACES_API_KEY or not place_id:
        return None
    params = {
        "place_id": place_id,
        # Single billable session per call. Field mask reduces cost.
        "fields": "name,formatted_phone_number,international_phone_number,"
                  "website,formatted_address,rating,user_ratings_total,types,url",
        "key": PLACES_API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(PLACE_DETAILS_URL, params=params)
            if r.status_code != 200:
                return None
            data = r.json()
        if data.get("status") != "OK":
            return None
        return data.get("result")
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[places-scout] details fetch failed for {place_id}: {e}")
        return None


def _strip_phone(p: str) -> str:
    if not p:
        return ""
    return re.sub(r"[^\d+]", "", p).strip()


async def google_places_leads(query: str, location: str, limit: int = 20) -> dict:
    """Public entrypoint — multi-source dispatcher (iter 282z).

    Order:
      1) Yelp Fusion (primary — real SMBs with phone+rating)
      2) Google Places (rich detail incl. website — when billing enabled)
      3) OSM Overpass (free fallback — no key required)

    Returns {success, leads:[...]} with each lead bearing business_name,
    phone, optional website/email, address, source, plus place_id/yelp_id.
    """
    leads: list[dict] = []
    used_source = "none"

    # ── 1) Yelp Fusion (primary) ──
    try:
        from services.yelp_scout import yelp_leads
        y = await yelp_leads(query, location, limit=limit)
        if y.get("success") and y.get("leads"):
            leads.extend(y["leads"])
            used_source = "yelp_fusion"
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[scout] yelp dispatch failed: {e}")

    # ── 2) Google Places (top-up) ──
    if len(leads) < limit:
        raw = await _text_search(query, location, max_results=limit - len(leads))
        seen_names = {(L.get("business_name") or "").lower() for L in leads}
        for r in raw:
            place_id = r.get("place_id")
            if not place_id:
                continue
            details = await _place_details(place_id) or {}
            name = (details.get("name") or r.get("name") or "").strip()
            if not name or name.lower() in seen_names:
                continue
            website = (details.get("website") or "").strip()
            if website and _is_blocked_url(website):
                continue
            phone = _strip_phone(
                details.get("formatted_phone_number")
                or details.get("international_phone_number")
                or ""
            )
            lead = {
                "business_name": name,
                "phone": phone,
                "website": website,
                "address": details.get("formatted_address") or r.get("formatted_address") or "",
                "rating": details.get("rating"),
                "review_count": details.get("user_ratings_total"),
                "types": details.get("types") or r.get("types") or [],
                "place_id": place_id,
                "source": "google_places",
                "google_url": details.get("url"),
            }
            if not is_valid_lead(lead):
                continue
            leads.append(lead)
            seen_names.add(name.lower())
            if len(leads) >= limit:
                break
        if any(L.get("source") == "google_places" for L in leads):
            used_source = used_source if used_source != "none" else "google_places"

    # ── 3) OSM Overpass (final fallback) ──
    if not leads:
        used_source = "osm_overpass"
        osm_raw = await _overpass_search(query, location, max_results=limit)
        for o in osm_raw:
            phone = _strip_phone(o.get("phone") or "")
            website = (o.get("website") or "").strip()
            if website and _is_blocked_url(website):
                continue
            lead = {
                "business_name": o["name"],
                "phone": phone,
                "website": website,
                "email": (o.get("email") or "").strip(),
                "address": o.get("address", ""),
                "rating": None,
                "review_count": None,
                "types": [],
                "place_id": None,
                "osm_id": o.get("osm_id"),
                "source": "osm_overpass",
            }
            if not is_valid_lead(lead):
                continue
            leads.append(lead)

    logger.info(
        f"[scout] {query!r} @ {location!r} → {len(leads)} valid leads "
        f"(primary_source={used_source})"
    )
    return {
        "success": True,
        "leads": leads,
        "total": len(leads),
        "query": query,
        "location": location,
        "source": used_source,
    }
