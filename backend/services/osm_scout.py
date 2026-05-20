"""
OpenStreetMap Overpass Scout — iter 322av (May 11, 2026)
========================================================
100% FREE lead source, no API key, no quota cap, no billing.

Uses OpenStreetMap's Overpass API to find local businesses matching an
industry + city. Returns real names, phone numbers, addresses, websites.

Why we use it:
  • Google Places API key is quota-exhausted (P2 user issue)
  • Yelp Fusion API revoked the user's key in 2025
  • OSM is community-maintained, no auth required, no rate limit per IP
  • Coverage in Canadian metros is excellent (especially for trades:
    plumbers, electricians, auto shops, dental clinics, salons, etc.)

Architecture:
  Industry name → OSM tag matrix
  ("plumber"   → craft=plumber OR office=plumber OR shop=plumber)
  ("electrician" → craft=electrician OR office=electrician)
  ("auto shop" → shop=car_repair OR shop=tyres)
  ("dental"    → healthcare=dentist OR amenity=dentist)
  ...

Returns shape mirrors yelp_scout.yelp_leads() so it drops into the same
pipeline.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple
import httpx

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# iter 324k — Mirror fallbacks. Overpass main server has frequent
# transient outages (504 / ConnectError). When the primary is dead the
# OSM scout retries the same query on these community mirrors before
# giving up. Order matters — keep most-reliable first.
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.openstreetmap.ru/cgi/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]

# ── Industry name → list of OSM tag pairs to OR together
# Format: [(key, value), ...] — each pair becomes one Overpass query line.
INDUSTRY_TO_OSM_TAGS: Dict[str, List[Tuple[str, str]]] = {
    "plumber":          [("craft", "plumber"), ("office", "plumber"), ("shop", "plumber")],
    "plumbers":         [("craft", "plumber"), ("office", "plumber"), ("shop", "plumber")],
    "plumbing":         [("craft", "plumber"), ("office", "plumber")],
    "electrician":      [("craft", "electrician"), ("office", "electrician")],
    "electricians":     [("craft", "electrician"), ("office", "electrician")],
    "auto_shop":        [("shop", "car_repair"), ("shop", "tyres"), ("shop", "car_parts")],
    "auto_shops":       [("shop", "car_repair"), ("shop", "tyres"), ("shop", "car_parts")],
    "automotive":       [("shop", "car_repair"), ("shop", "tyres"), ("shop", "car_parts")],
    "dental_clinic":    [("healthcare", "dentist"), ("amenity", "dentist")],
    "dental_clinics":   [("healthcare", "dentist"), ("amenity", "dentist")],
    "dentist":          [("healthcare", "dentist"), ("amenity", "dentist")],
    "salon":            [("shop", "hairdresser"), ("shop", "beauty")],
    "salons":           [("shop", "hairdresser"), ("shop", "beauty")],
    "salons_spas":      [("shop", "hairdresser"), ("shop", "beauty"), ("shop", "massage")],
    "spa":              [("shop", "beauty"), ("shop", "massage"), ("leisure", "spa")],
    "spas":             [("shop", "beauty"), ("shop", "massage"), ("leisure", "spa")],
    "real_estate":      [("office", "estate_agent")],
    "landscaper":       [("craft", "gardener"), ("office", "landscape_architect")],
    "landscapers":      [("craft", "gardener"), ("office", "landscape_architect")],
    "landscaping":      [("craft", "gardener"), ("office", "landscape_architect")],
    "restaurant":       [("amenity", "restaurant")],
    "restaurants":      [("amenity", "restaurant")],
    "cafe":             [("amenity", "cafe")],
    "cafes":            [("amenity", "cafe")],
    "contractor":       [("craft", "carpenter"), ("craft", "builder"), ("office", "construction_company")],
    "contractors":      [("craft", "carpenter"), ("craft", "builder"), ("office", "construction_company")],
    "roofer":           [("craft", "roofer")],
    "roofers":          [("craft", "roofer")],
    "roofing":          [("craft", "roofer")],
    "hvac":             [("craft", "hvac"), ("trade", "hvac")],
    "cleaner":          [("shop", "dry_cleaning"), ("craft", "cleaner")],
    "cleaners":         [("shop", "dry_cleaning"), ("craft", "cleaner")],
    "fitness":          [("leisure", "fitness_centre"), ("leisure", "sports_centre")],
    "gym":              [("leisure", "fitness_centre"), ("leisure", "sports_centre")],
    "veterinarian":     [("amenity", "veterinary")],
    "vet":              [("amenity", "veterinary")],
    "pet_services":     [("amenity", "veterinary"), ("shop", "pet")],
    "pet":              [("shop", "pet"), ("amenity", "veterinary")],
    # ── iter 324j — expanded SMB taxonomy so ORA hunt commands no longer fall
    # through to the (disabled) Tavily/DDG branches when Google Places/Yelp
    # keys are dead. Each row picks the OSM tag(s) that best match the
    # business category Aurem actually targets in cold outreach.
    "cleaning":             [("craft", "cleaner"), ("shop", "dry_cleaning"), ("office", "company")],
    "cleaning_service":     [("craft", "cleaner"), ("shop", "dry_cleaning")],
    "cleaning_services":    [("craft", "cleaner"), ("shop", "dry_cleaning")],
    "house_cleaning":       [("craft", "cleaner")],
    "maid_service":         [("craft", "cleaner")],
    "maid_services":        [("craft", "cleaner")],
    "janitorial":           [("craft", "cleaner")],
    "dental":               [("healthcare", "dentist"), ("amenity", "dentist")],
    "dentists":             [("healthcare", "dentist"), ("amenity", "dentist")],
    "doctor":               [("amenity", "doctors"), ("healthcare", "doctor")],
    "doctors":              [("amenity", "doctors"), ("healthcare", "doctor")],
    "clinic":               [("amenity", "clinic"), ("healthcare", "clinic")],
    "physiotherapy":        [("healthcare", "physiotherapist")],
    "physiotherapist":      [("healthcare", "physiotherapist")],
    "physio":               [("healthcare", "physiotherapist")],
    "chiropractor":         [("healthcare", "chiropractor")],
    "chiropractors":        [("healthcare", "chiropractor")],
    "optometrist":          [("healthcare", "optometrist"), ("shop", "optician")],
    "optician":             [("shop", "optician")],
    "pharmacy":             [("amenity", "pharmacy")],
    "lawyer":               [("office", "lawyer")],
    "lawyers":              [("office", "lawyer")],
    "law_firm":             [("office", "lawyer")],
    "attorney":             [("office", "lawyer")],
    "accountant":           [("office", "accountant")],
    "accountants":          [("office", "accountant")],
    "accounting":           [("office", "accountant")],
    "bookkeeper":           [("office", "accountant")],
    "financial_advisor":    [("office", "financial"), ("office", "financial_advisor")],
    "insurance":            [("office", "insurance")],
    "notary":               [("office", "notary")],
    "consultant":           [("office", "consulting")],
    "marketing_agency":     [("office", "advertising_agency"), ("office", "marketing")],
    "advertising":          [("office", "advertising_agency")],
    "web_design":           [("office", "it"), ("office", "company")],
    "it_service":           [("office", "it")],
    "barber":               [("shop", "hairdresser")],
    "barbershop":           [("shop", "hairdresser")],
    "hair_salon":           [("shop", "hairdresser"), ("shop", "beauty")],
    "hair_salons":          [("shop", "hairdresser"), ("shop", "beauty")],
    "hairdresser":          [("shop", "hairdresser")],
    "beauty_salon":         [("shop", "beauty"), ("shop", "hairdresser")],
    "nail_salon":           [("shop", "beauty")],
    "nails":                [("shop", "beauty")],
    "massage":              [("shop", "massage")],
    "tattoo":               [("shop", "tattoo")],
    "florist":              [("shop", "florist")],
    "bakery":               [("shop", "bakery")],
    "butcher":              [("shop", "butcher")],
    "coffee_shop":          [("amenity", "cafe")],
    "coffee":               [("amenity", "cafe")],
    "bar":                  [("amenity", "bar"), ("amenity", "pub")],
    "pub":                  [("amenity", "pub")],
    "pizzeria":             [("amenity", "fast_food"), ("amenity", "restaurant")],
    "fast_food":            [("amenity", "fast_food")],
    "auto_body":            [("shop", "car_repair")],
    "auto_repair":          [("shop", "car_repair")],
    "mechanic":             [("shop", "car_repair")],
    "mechanics":            [("shop", "car_repair")],
    "car_wash":             [("amenity", "car_wash")],
    "car_dealership":       [("shop", "car")],
    "tire_shop":            [("shop", "tyres")],
    "tires":                [("shop", "tyres")],
    "real_estate_agent":    [("office", "estate_agent")],
    "realtor":              [("office", "estate_agent")],
    "realtors":             [("office", "estate_agent")],
    "property_management":  [("office", "estate_agent"), ("office", "property_management")],
    "moving_company":       [("office", "moving_company"), ("shop", "moving_company")],
    "movers":               [("office", "moving_company"), ("shop", "moving_company")],
    "storage":              [("shop", "storage_rental")],
    "self_storage":         [("shop", "storage_rental")],
    "construction":         [("office", "construction_company"), ("craft", "builder")],
    "general_contractor":   [("office", "construction_company"), ("craft", "builder")],
    "painter":              [("craft", "painter")],
    "painters":             [("craft", "painter")],
    "painting":             [("craft", "painter")],
    "carpenter":            [("craft", "carpenter")],
    "carpentry":            [("craft", "carpenter")],
    "flooring":             [("craft", "carpenter"), ("shop", "flooring")],
    "tiling":               [("craft", "tiler")],
    "tile":                 [("craft", "tiler")],
    "drywall":              [("craft", "plasterer")],
    "plasterer":            [("craft", "plasterer")],
    "mason":                [("craft", "stonemason")],
    "stonemason":           [("craft", "stonemason")],
    "concrete":             [("craft", "stonemason"), ("craft", "builder")],
    "landscape":            [("craft", "gardener")],
    "lawn_care":            [("craft", "gardener")],
    "snow_removal":         [("craft", "gardener")],
    "pool_service":         [("leisure", "swimming_pool"), ("craft", "pool")],
    "pest_control":         [("craft", "pest_control")],
    "locksmith":            [("shop", "locksmith")],
    "appliance_repair":     [("craft", "electronics_repair"), ("shop", "electronics_repair")],
    "computer_repair":      [("shop", "electronics_repair")],
    "phone_repair":         [("shop", "mobile_phone")],
    "personal_trainer":     [("leisure", "fitness_centre")],
    "yoga":                 [("leisure", "fitness_centre"), ("shop", "yoga")],
    "yoga_studio":          [("leisure", "fitness_centre")],
    "daycare":              [("amenity", "childcare"), ("amenity", "kindergarten")],
    "childcare":            [("amenity", "childcare")],
    "tutoring":             [("amenity", "school"), ("amenity", "training")],
    "driving_school":       [("amenity", "driving_school")],
    "music_school":         [("amenity", "music_school")],
    "boutique":             [("shop", "clothes"), ("shop", "boutique")],
    "clothing_store":       [("shop", "clothes")],
    "jewelry":              [("shop", "jewelry")],
    "jeweller":             [("shop", "jewelry")],
    "shoe_store":           [("shop", "shoes")],
    "furniture_store":      [("shop", "furniture")],
    "convenience_store":    [("shop", "convenience")],
    "grocery":              [("shop", "supermarket"), ("shop", "convenience")],
    "supermarket":          [("shop", "supermarket")],
    "liquor_store":         [("shop", "alcohol")],
    "garden_centre":        [("shop", "garden_centre")],
    "hardware_store":       [("shop", "hardware"), ("shop", "doityourself")],
    "photographer":         [("craft", "photographer"), ("office", "photographer")],
    "videographer":         [("craft", "photographer")],
    "event_planner":        [("office", "event_management")],
    "wedding_planner":      [("office", "event_management")],
    "caterer":              [("shop", "deli"), ("craft", "caterer")],
    "catering":             [("craft", "caterer")],
    "funeral_home":         [("amenity", "funeral_hall"), ("shop", "funeral_directors")],
    "travel_agency":        [("shop", "travel_agency"), ("office", "travel_agent")],
    "printer":              [("craft", "printer"), ("shop", "copyshop")],
    "print_shop":           [("shop", "copyshop")],
    "sign_shop":            [("craft", "signmaker")],
    "tailor":               [("craft", "tailor"), ("shop", "tailor")],
    "alterations":          [("craft", "tailor")],
    "shoe_repair":          [("shop", "shoes"), ("craft", "shoemaker")],
}

# Major Canadian cities → centroid lat/lon (used when geocoding is unavailable)
CITY_CENTROIDS: Dict[str, Tuple[float, float]] = {
    "mississauga": (43.5890, -79.6441),
    "toronto":     (43.6532, -79.3832),
    "brampton":    (43.7315, -79.7624),
    "oakville":    (43.4675, -79.6877),
    "hamilton":    (43.2557, -79.8711),
    "burlington":  (43.3255, -79.7990),
    "vaughan":     (43.8361, -79.4983),
    "markham":     (43.8561, -79.3370),
    "ottawa":      (45.4215, -75.6972),
    "calgary":     (51.0447, -114.0719),
    "edmonton":    (53.5461, -113.4938),
    "vancouver":   (49.2827, -123.1207),
    "winnipeg":    (49.8951, -97.1384),
    "halifax":     (44.6488, -63.5752),
    "victoria":    (48.4284, -123.3656),
    "regina":      (50.4452, -104.6189),
    "saskatoon":   (52.1332, -106.6700),
    "windsor":     (42.3149, -83.0364),
    "london":      (42.9849, -81.2453),
    "kingston":    (44.2312, -76.4860),
}


def _normalise_industry(raw: str) -> str:
    s = (raw or "").lower().strip()
    # collapse spaces/hyphens to underscore
    s = s.replace("&", "and").replace(" ", "_").replace("-", "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s


def _resolve_city(city: str) -> Tuple[float, float] | None:
    if not city:
        return None
    # Strip ", ON" / ", Canada" etc.
    name = city.split(",")[0].strip().lower()
    return CITY_CENTROIDS.get(name)


def _build_overpass_query(industry: str, lat: float, lon: float, radius_m: int) -> str:
    tag_pairs = INDUSTRY_TO_OSM_TAGS.get(industry) or []
    if not tag_pairs:
        # Generic fallback — search by name keyword
        keyword = industry.replace("_", " ")
        return (
            f'[out:json][timeout:25];'
            f'nwr["name"~"{keyword}",i](around:{radius_m},{lat},{lon});'
            f'out tags 50;'
        )
    lines = "".join(f'nwr["{k}"="{v}"](around:{radius_m},{lat},{lon});' for k, v in tag_pairs)
    return f'[out:json][timeout:25];({lines});out tags 50;'


async def osm_leads(
    *,
    query: str,
    location: str,
    limit: int = 20,
    radius_m: int = 15000,
) -> Dict[str, Any]:
    """Find businesses via OSM Overpass. Mirrors yelp_scout.yelp_leads()."""
    industry = _normalise_industry(query)
    centroid = _resolve_city(location)
    if not centroid:
        logger.warning(f"[osm-scout] city '{location}' not in centroid map; aborting")
        return {"success": False, "leads": [], "total": 0, "source": "osm_overpass", "error": "unknown_city"}

    lat, lon = centroid
    overpass = _build_overpass_query(industry, lat, lon, radius_m)

    # iter 324k — Try each Overpass mirror in turn. Bail out on the
    # first 200. Surface a single combined error if all fail so the
    # caller knows it's an infra outage, not a query bug.
    last_err: str = ""
    data: Dict[str, Any] | None = None
    for mirror in OVERPASS_MIRRORS:
        try:
            async with httpx.AsyncClient(
                timeout=8.0,
                headers={
                    "User-Agent": "AUREM-AutomationPlatform/324k (https://aurem.live; ops@aurem.live)",
                    "Accept": "application/json",
                },
            ) as client:
                r = await client.post(
                    mirror,
                    content=f"data={overpass}",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                if r.status_code != 200:
                    last_err = f"{mirror} → http_{r.status_code}"
                    logger.debug(f"[osm-scout] {last_err}")
                    continue
                data = r.json()
                logger.info(f"[osm-scout] mirror hit: {mirror}")
                break
        except Exception as e:
            last_err = f"{mirror} → {type(e).__name__}"
            logger.debug(f"[osm-scout] {last_err}: {str(e)[:120]}")
            continue

    if data is None:
        logger.warning(f"[osm-scout] all mirrors failed: {last_err}")
        return {"success": False, "leads": [], "total": 0,
                "source": "osm_overpass",
                "error": f"all_mirrors_failed:{last_err[:120]}"}

    raw = data.get("elements", []) or []
    leads: List[Dict[str, Any]] = []
    for el in raw:
        tags = el.get("tags") or {}
        name = (tags.get("name") or "").strip()
        if not name:
            continue
        phone = (tags.get("contact:phone") or tags.get("phone") or "").strip()
        website = (tags.get("contact:website") or tags.get("website") or "").strip()
        email = (tags.get("contact:email") or tags.get("email") or "").strip()
        # Build address from address tags
        addr_parts = [
            tags.get("addr:housenumber"),
            tags.get("addr:street"),
            tags.get("addr:city"),
            tags.get("addr:province") or tags.get("addr:state"),
        ]
        address = " ".join(p for p in addr_parts if p).strip()
        if not address:
            address = tags.get("addr:full", "")

        # At least one contact channel (phone OR website OR email) is required.
        if not (phone or website or email):
            continue

        leads.append({
            "business_name": name,
            "phone": phone,
            "website": website,
            "email": email,
            "address": address,
            "city": tags.get("addr:city") or location,
            "rating": None,             # OSM has no rating
            "review_count": 0,
            "types": [tags.get(k) for k in ("amenity", "shop", "craft", "office", "leisure", "healthcare") if tags.get(k)],
            "osm_id": el.get("id"),
            "osm_type": el.get("type"),
            "source": "osm_overpass",
        })
        if len(leads) >= limit:
            break

    logger.info(
        f"[osm-scout] {query!r} @ {location!r} → {len(leads)} valid leads "
        f"(raw={len(raw)})"
    )
    return {
        "success": True,
        "leads": leads,
        "total": len(leads),
        "query": query,
        "location": location,
        "source": "osm_overpass",
    }
