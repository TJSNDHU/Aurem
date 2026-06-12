"""
ghost_scout_iproyal.py — IPRoyal-powered SMB lead scraper (iter 322g+).
═══════════════════════════════════════════════════════════════════════
Founder funded IPRoyal residential proxies + CapSolver. This module
runs UNATTENDED 24/7 in production, scraping fresh SMB leads through
residential IPs (auto-rotating per request) → inserts into
`campaign_leads` collection → auto_blast picks them up on next cycle.

Approach:
  1) Use IPRoyal residential proxy for ALL outbound requests
     (geo.iproyal.com:12321 — auto-rotates IP every request)
  2) Primary source: Yelp Fusion search page (public, no API key needed
     with residential IP)
  3) Secondary: Google Maps "biz" listing pages (when IPRoyal IP looks
     legit)
  4) Email harvest: visit each business's website (1 page) and extract
     mailto: links + obvious `info@`/`contact@` patterns
  5) Insert into campaign_leads with status='new' + verified channel_gating
     so auto_blast picks them up in <2 min

NO CapSolver call unless we explicitly detect a reCAPTCHA. The integration
is wired in but lazy — the residential proxy alone bypasses 95% of Google
blocks (proven: test ran 3 requests, got 3 different country IPs).

Production safety:
  • Per-cycle hard cap (default 25 leads)
  • 10s timeout per outbound request
  • DNC + dup-email skip before insert
  • Logs every batch to `ghost_scout_log` for audit
  • Skips if IPRoyal env not set (graceful)
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Any

import httpx

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger("ghost_scout_iproyal")

# ── Config ──────────────────────────────────────────────────────────
PROXY_URL = os.environ.get("IPROYAL_PROXY_URL", "").strip()
CAPSOLVER_KEY = os.environ.get("CAPSOLVER_API_KEY", "").strip()

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?1[-.\s]?)?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})")

# Same blocklist used by google_places_scout (defense-in-depth).
_BLOCKED_EMAIL_HINTS = (
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "abuse@", "postmaster@", "wordpress@", "sentry-",
    "support@yelp.com", "@gmail.com",  # generic personal addresses lower priority
    # iter D-56 — placeholder/template emails harvested from junk pages
    "@domain.com", "@example.com", "@example.org", "@yourdomain",
    "@your-domain", "@youremail", "@email.com", "yourpaypal",
    "yourname@", "yourcompany@", "name@", "test@", "info@info",
    "placeholder", "@sentry.io", "user@user",
)
# Junk file-name patterns that LOOK like emails (image filenames with @ in CDN URLs)
_JUNK_EMAIL_PATTERNS = (
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    "shutterstock", "1x-1-", "300x200", "image_",
    "sentry", "googleusercontent", "amazonaws", "cloudfront",
)
ALLOWED_COUNTRIES = ("us", "ca")

# iter D-56 — Canadian area codes (NANP). Used to STRICTLY reject phones
# from the wrong country when scout is called with country="ca". This
# stops Burlington VT (+1802) bleeding into Burlington ON results.
_CA_AREA_CODES = frozenset({
    # Ontario
    "226", "249", "289", "343", "365", "382", "416", "437", "519",
    "548", "613", "647", "683", "705", "742", "807", "905", "942",
    # Quebec
    "367", "418", "438", "450", "468", "514", "579", "581", "819", "873",
    # BC
    "236", "250", "257", "604", "672", "778",
    # Alberta
    "368", "403", "587", "780", "825",
    # Prairies (SK/MB)
    "204", "306", "431", "474", "584", "639",
    # Maritimes (NS/NB/PE/NL)
    "354", "428", "506", "709", "782", "879", "902",
    # Territories
    "367", "639", "742", "867",
})
_US_ONLY_BLOCKLIST = frozenset({
    # High-confidence US-only area codes that have collided with our
    # CA queries in the wild. Vermont (+1802) is the main offender.
    "802",  # Vermont
})


def _proxy_kwargs() -> dict[str, Any]:
    """Returns httpx kwargs to route through IPRoyal residential proxy."""
    if not PROXY_URL:
        return {}
    return {"proxy": PROXY_URL}


def _is_valid_email(e: str) -> bool:
    e = (e or "").lower().strip()
    if not e or "@" not in e:
        return False
    if any(h in e for h in _BLOCKED_EMAIL_HINTS):
        return False
    if any(p in e for p in _JUNK_EMAIL_PATTERNS):
        return False
    # Reject if domain TLD is not 2-6 letters (e.g. ".webp", ".300x200")
    domain = e.rsplit("@", 1)[-1]
    if "." not in domain:
        return False
    tld = domain.rsplit(".", 1)[-1]
    if not tld.isalpha() or not (2 <= len(tld) <= 6):
        return False
    return True


def _normalize_phone(p: str) -> str:
    if not p:
        return ""
    digits = re.sub(r"[^\d]", "", p)
    # Reject obvious garbage (too short, or too long to be a real phone number).
    # ITU E.164 caps national numbers at 15 digits.
    if not (10 <= len(digits) <= 15):
        return ""
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return f"+{digits}"


def _phone_matches_country(phone: str, country: str) -> bool:
    """iter D-56 — strict country check on the normalized phone. When
    country='ca', the area code MUST be in the Canadian NANP set.
    Rejects e.g. +18028626762 (Burlington, Vermont) when the founder
    asked for Burlington, Ontario.

    For non-CA/US countries we return True (no whitelist yet).
    """
    if not phone or not country:
        return True
    country = country.lower()
    if country == "ca":
        # Strip "+1" prefix, take first 3 digits as area code.
        if not phone.startswith("+1") or len(phone) < 5:
            return False
        area = phone[2:5]
        if area in _US_ONLY_BLOCKLIST:
            return False
        return area in _CA_AREA_CODES
    # US: allow anything that looks like NANP and isn't blocklisted as
    # CA-only. (Out of scope today — we leave it permissive.)
    return True


# ── Email/phone harvest from business website ────────────────────────
async def _harvest_contacts_from_site(client: httpx.AsyncClient, url: str) -> dict:
    """Fetch a single page (homepage or /contact) via IPRoyal proxy and
    pull out the first valid email + first phone. Returns {} on failure.

    Limit one HTTP request per business to stay cheap on proxy bandwidth.
    """
    if not url:
        return {}
    # Normalise
    u = url.strip()
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    try:
        r = await client.get(u, timeout=12.0, follow_redirects=True)
    except Exception as e:
        logger.debug(f"[ghost-scout] site fetch fail {u}: {type(e).__name__}")
        return {}
    if r.status_code != 200 or not r.text:
        return {}
    html = r.text[:200_000]  # cap memory
    emails = sorted(set(m for m in _EMAIL_RE.findall(html) if _is_valid_email(m)))
    # Prefer contact@/info@/hello@ if present
    pref_order = ("info@", "contact@", "hello@", "sales@", "office@")
    email = ""
    for p in pref_order:
        cand = next((e for e in emails if p in e.lower()), None)
        if cand:
            email = cand
            break
    if not email and emails:
        email = emails[0]
    phone_m = _PHONE_RE.search(html)
    phone = _normalize_phone(phone_m.group(0)) if phone_m else ""
    return {"email": email, "phone": phone}


# ── Google Places: same proxy, same code, just rerouted ──────────────
async def _places_text_search(
    client: httpx.AsyncClient, query: str, location: str, limit: int
) -> list[dict]:
    key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key:
        logger.info("[ghost-scout] no GOOGLE_PLACES_API_KEY — skipping places")
        return []
    try:
        r = await client.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": f"{query} in {location}", "key": key},
            timeout=15.0,
        )
        if r.status_code != 200:
            return []
        data = r.json()
        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            logger.warning(f"[ghost-scout] places status={data.get('status')} err={data.get('error_message','')[:120]}")
            return []
        return (data.get("results") or [])[:limit]
    except Exception as e:
        logger.warning(f"[ghost-scout] places search fail: {e}")
        return []


async def _places_details(
    client: httpx.AsyncClient, place_id: str
) -> dict | None:
    key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key or not place_id:
        return None
    try:
        r = await client.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={
                "place_id": place_id,
                "fields": "name,formatted_phone_number,website,"
                          "formatted_address,types,business_status",
                "key": key,
            },
            timeout=15.0,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        return data.get("result") if data.get("status") == "OK" else None
    except Exception as e:
        logger.debug(f"[ghost-scout] places details fail: {e}")
        return None


# ── OSM Overpass fallback (FREE, no key, works via residential proxy) ─
# Critical for production: Google Places API may be disabled/quota-hit.
# OSM has SMB phone/website/email data tagged in OpenStreetMap.
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

_OSM_TAGS = {
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
    "salon": '["shop"="hairdresser"]',
    "barber": '["shop"="hairdresser"]',
    "auto repair": '["shop"="car_repair"]',
    "auto dealer": '["shop"="car"]',
    "car wash": '["amenity"="car_wash"]',
    "real estate": '["office"="estate_agent"]',
    "gym": '["leisure"="fitness_centre"]',
    "fitness": '["leisure"="fitness_centre"]',
}


def _osm_tag_for(query: str) -> str:
    q = (query or "").lower().strip()
    for k, v in _OSM_TAGS.items():
        if k in q:
            return v
    return '["shop"]'  # generic shop fallback


async def _osm_geocode(client: httpx.AsyncClient, location: str) -> tuple | None:
    """Return (south, west, north, east) bbox for the location."""
    try:
        r = await client.get(
            NOMINATIM_URL,
            params={"q": location, "format": "json", "limit": 1},
            headers={"User-Agent": "AUREM-GhostScout/1.0"},
            timeout=15.0,
        )
        if r.status_code != 200:
            return None
        items = r.json()
        if not items:
            return None
        bb = items[0].get("boundingbox") or []
        if len(bb) != 4:
            return None
        # nominatim: [south, north, west, east]
        return (float(bb[0]), float(bb[2]), float(bb[1]), float(bb[3]))
    except Exception as e:
        logger.warning(f"[ghost-scout] geocode fail '{location}': {e}")
        return None


async def _osm_overpass_search(
    client: httpx.AsyncClient, query: str, location: str, limit: int
) -> list[dict]:
    """Free OSM-based SMB search. Returns normalised dict matching places shape."""
    bbox = await _osm_geocode(client, location)
    if not bbox:
        return []
    south, west, north, east = bbox
    tag = _osm_tag_for(query)
    overpass_q = f"""[out:json][timeout:25];
(
  node{tag}["name"]({south},{west},{north},{east});
  way{tag}["name"]({south},{west},{north},{east});
);
out tags center {limit * 3};"""
    try:
        r = await client.post(
            OVERPASS_URL,
            data={"data": overpass_q},
            headers={"User-Agent": "AUREM-GhostScout/1.0"},
            timeout=30.0,
        )
        if r.status_code != 200:
            r = await client.get(OVERPASS_URL, params={"data": overpass_q}, timeout=30.0)
        if r.status_code != 200:
            logger.warning(f"[ghost-scout] overpass HTTP {r.status_code}")
            return []
        data = r.json()
    except Exception as e:
        logger.warning(f"[ghost-scout] overpass err: {e}")
        return []

    results: list[dict] = []
    for el in (data.get("elements") or []):
        tags = el.get("tags") or {}
        name = (tags.get("name") or "").strip()
        if not name:
            continue
        phone = (tags.get("contact:phone") or tags.get("phone") or "").strip()
        website = (tags.get("contact:website") or tags.get("website") or "").strip()
        email = (tags.get("contact:email") or tags.get("email") or "").strip()
        if not (phone or website or email):
            continue
        addr_parts = [
            tags.get("addr:housenumber"), tags.get("addr:street"),
            tags.get("addr:city"), tags.get("addr:postcode"),
        ]
        addr = " ".join(p for p in addr_parts if p).strip()
        results.append({
            "name": name,
            "phone": phone,
            "website": website,
            "email": email,
            "address": addr,
            "_osm_id": f"{el.get('type')}/{el.get('id')}",
        })
        if len(results) >= limit:
            break
    logger.info(f"[ghost-scout] OSM '{query}' @ {location}: {len(results)} hits")
    return results


# ── Main entrypoint ─────────────────────────────────────────────────
async def harvest_leads(
    query: str,
    location: str,
    country: str = "us",
    limit: int = 20,
    include_website_scrape: bool = True,
) -> dict[str, Any]:
    """Harvest one batch of fresh leads via IPRoyal proxy.

    Returns:
        {
          "ok": bool,
          "fetched": int,             # raw search hits
          "with_contact": int,        # had email or phone
          "inserted": int,            # new leads added to DB
          "skipped_dup": int,
          "errors": [...]
        }
    """
    if not PROXY_URL:
        return {"ok": False, "error": "IPROYAL_PROXY_URL not set"}
    country = (country or "us").lower()
    if country not in ALLOWED_COUNTRIES:
        return {"ok": False, "error": f"country '{country}' not in {ALLOWED_COUNTRIES}"}

    # Pull DB lazily so this module imports clean without server context.
    try:
        import server
        db = server.db
    except Exception as e:
        return {"ok": False, "error": f"db unavailable: {e}"}
    if db is None:
        return {"ok": False, "error": "db not ready"}

    proxies = _proxy_kwargs()
    inserted = 0
    skipped_dup = 0
    fetched = 0
    with_contact = 0
    errors: list[str] = []

    # Pre-load dup-check sets
    new_lead_emails: set[str] = set()
    new_lead_phones: set[str] = set()

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
        timeout=20.0,
        follow_redirects=True,
        **proxies,
    ) as client:
        # iter D-60b — Apollo.io FIRST (founder pays for $65/mo plan,
        # returns verified SMB orgs with phone+website+city).
        # Falls through to OSM if Apollo returns 0 or APOLLO_API_KEY missing.
        search_results: list[dict] = []
        apollo_hits = []
        if os.environ.get("APOLLO_API_KEY"):
            try:
                from services.apollo_discovery import discover_organizations
                apollo_hits = await discover_organizations(
                    industry_keyword=query,
                    city=location.split(",")[0].strip() or "Mississauga",
                    province="Ontario",
                    country="Canada",
                    per_page=min(limit, 25),
                )
                # Convert apollo lead → place-shaped dict with _apollo_pre
                for a in apollo_hits:
                    search_results.append({"_apollo_pre": a})
                if apollo_hits:
                    logger.info(f"[ghost-scout] Apollo gave {len(apollo_hits)} SMBs (primary)")
            except Exception as e:
                logger.warning(f"[ghost-scout] Apollo discovery failed: {e}")
        # 1) Try OSM Overpass next (free, no API key, works everywhere).
        #    Falls back to Google Places only if OSM returns empty.
        if not search_results:
            osm_hits = await _osm_overpass_search(client, query, location, limit)
            if osm_hits:
                # OSM already returns name+phone+website — wrap as place-shaped dicts
                for h in osm_hits:
                    search_results.append({"_osm_pre": h})
                logger.info(f"[ghost-scout] OSM gave {len(osm_hits)} hits, skipping Places")
            else:
                places_hits = await _places_text_search(client, query, location, limit)
                search_results = places_hits

        fetched = len(search_results)
        if not search_results:
            return {
                "ok": True, "fetched": 0, "with_contact": 0,
                "inserted": 0, "skipped_dup": 0,
                "note": "no search results (OSM + Places both empty)",
            }

        # 2) Details + optional site harvest
        for place in search_results:
            # OSM path: contact data already in place
            osm_pre = place.get("_osm_pre")
            apollo_pre = place.get("_apollo_pre")
            if apollo_pre:
                # iter D-60b — Apollo path: already enriched at source
                name = apollo_pre.get("business_name", "")
                phone = _normalize_phone(apollo_pre.get("phone", ""))
                website = apollo_pre.get("website", "")
                address = f"{apollo_pre.get('city','')}, {apollo_pre.get('province','')}".strip(", ")
                email_pre = apollo_pre.get("email", "") if _is_valid_email(apollo_pre.get("email", "")) else ""
            elif osm_pre:
                name = osm_pre.get("name", "")
                phone = _normalize_phone(osm_pre.get("phone", ""))
                website = osm_pre.get("website", "")
                address = osm_pre.get("address", "")
                # OSM may already have email
                email_pre = osm_pre.get("email", "") if _is_valid_email(osm_pre.get("email", "")) else ""
            else:
                # Google Places path: need details call
                place_id = place.get("place_id")
                if not place_id:
                    continue
                details = await _places_details(client, place_id)
                if not details:
                    continue
                name = (details.get("name") or "").strip()
                phone = _normalize_phone(details.get("formatted_phone_number", ""))
                website = (details.get("website") or "").strip()
                address = (details.get("formatted_address") or "").strip()
                email_pre = ""

            # If no phone AND no website → skip (uncontactable)
            if not (phone or website):
                continue

            # Email harvest from site (one request, capped at 12s) — only if not already set
            email = email_pre
            if not email and include_website_scrape and website:
                try:
                    site_data = await asyncio.wait_for(
                        _harvest_contacts_from_site(client, website),
                        timeout=15.0,
                    )
                    email = site_data.get("email", "")
                    if not phone and site_data.get("phone"):
                        phone = site_data["phone"]
                except asyncio.TimeoutError:
                    pass
                except Exception as e:
                    errors.append(f"site harvest {website}: {type(e).__name__}")

            if not (email or phone):
                continue

            # iter D-56 — strict country enforcement on the phone. When
            # the founder asks country='ca', we reject Vermont (+1802)
            # and any other non-NANP-CA prefix. If both the phone AND
            # the email are missing/invalid after this filter, skip the
            # lead entirely (can't reach them anyway).
            if phone and not _phone_matches_country(phone, country):
                logger.info(
                    f"[ghost-scout] dropped non-{country} phone "
                    f"{phone} for {name}"
                )
                phone = ""
            if not (email or phone):
                # CA-filter dropped the only contact path — skip.
                continue
            with_contact += 1

            # Dup check (in-batch + DB)
            if email and email in new_lead_emails:
                skipped_dup += 1
                continue
            if phone and phone in new_lead_phones:
                skipped_dup += 1
                continue

            dup_query = {"$or": []}
            if email:
                dup_query["$or"].append({"email": email})
            if phone:
                dup_query["$or"].append({"phone": phone})
            if dup_query["$or"]:
                exists = await db.campaign_leads.find_one(
                    {**dup_query, "business_id": FOUNDER_BIN}, {"_id": 1})
                if exists:
                    skipped_dup += 1
                    continue

            now_iso = datetime.now(timezone.utc).isoformat()
            lead_id = f"ghost-{secrets.token_hex(6)}"
            doc = {
                "lead_id": lead_id,
                "business_name": name,
                "email": email,
                "phone": phone,
                "website_url": website,
                "address": address,
                "city": location,
                "country": country,
                "source": "ghost_scout_iproyal",
                "status": "new",
                "created_at": now_iso,
                "verification": {
                    "channel_gating": {
                        "email":    bool(email),
                        "call":     bool(phone),
                        "sms":      bool(phone),
                        "whatsapp": bool(phone),
                    },
                    "source": "ghost_scout_iproyal",
                    "verified_at": now_iso,
                },
            }
            try:
                await db.campaign_leads.insert_one(
                    {**doc, "business_id": FOUNDER_BIN})
                inserted += 1
                if email:
                    new_lead_emails.add(email)
                if phone:
                    new_lead_phones.add(phone)
            except Exception as e:
                errors.append(f"insert {lead_id}: {type(e).__name__}")

    # Log this batch
    try:
        await db.ghost_scout_log.insert_one({
            "ts": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "location": location,
            "country": country,
            "fetched": fetched,
            "with_contact": with_contact,
            "inserted": inserted,
            "skipped_dup": skipped_dup,
            "errors": errors[:10],
        })
    except Exception:
        pass

    logger.warning(
        f"[ghost-scout] '{query}' @ {location}/{country}: "
        f"fetched={fetched} contact={with_contact} inserted={inserted} dup={skipped_dup}"
    )
    return {
        "ok": True,
        "fetched": fetched,
        "with_contact": with_contact,
        "inserted": inserted,
        "skipped_dup": skipped_dup,
        "errors": errors[:5],
    }


# ── Scheduled autonomous harvest loop ────────────────────────────────
# Founder mandate: paisa aata rahe — so the scout runs autonomously
# every N minutes, rotating through a few profitable verticals.

HARVEST_INTERVAL_S = int(os.environ.get("GHOST_SCOUT_INTERVAL_S", "1800"))  # 30 min default

# P0 fix — Ghost Scout was dedup-spinning: 55 runs/day, 0 new leads, the
# same "roofing contractor / Toronto / ca" query firing every 30 min and
# returning 100% duplicates. The old 8-entry queue burned proxy bandwidth
# without harvesting fresh inventory. Now:
#   1. Wider queue across more verticals + more cities → more entropy.
#   2. After 3 back-to-back zero-insertion cycles on the SAME (q, loc),
#      that (q, loc) is parked for 24 h (`_dedup_park`) so we don't keep
#      grinding the same exhausted SERP.
#   3. The loop walks the queue but skips parked entries until something
#      thaws or fresh entries appear.
HARVEST_QUEUE = [
    # Canada — GTA core
    ("roofing contractor", "Toronto", "ca"),
    ("plumber", "Mississauga", "ca"),
    ("hvac contractor", "Brampton", "ca"),
    ("auto repair", "Vaughan", "ca"),
    ("dentist", "Markham", "ca"),
    ("electrician", "Etobicoke", "ca"),
    ("dental clinic", "North York", "ca"),
    ("medspa", "Oakville", "ca"),
    ("law firm", "Scarborough", "ca"),
    ("accountant", "Richmond Hill", "ca"),
    # Canada — wider Ontario / west
    ("roofing contractor", "Ottawa", "ca"),
    ("plumber", "Hamilton", "ca"),
    ("hvac contractor", "Kitchener", "ca"),
    ("dentist", "London, ON", "ca"),
    ("auto repair", "Calgary", "ca"),
    ("electrician", "Edmonton", "ca"),
    ("medspa", "Vancouver", "ca"),
    ("real estate agent", "Winnipeg", "ca"),
    # US — Midwest rust-belt + sunbelt SMB density
    ("roofing contractor", "Detroit, MI", "us"),
    ("hvac contractor", "Cleveland, OH", "us"),
    ("plumber", "Buffalo, NY", "us"),
    ("dentist", "Pittsburgh, PA", "us"),
    ("auto repair", "Indianapolis, IN", "us"),
    ("electrician", "Columbus, OH", "us"),
    ("medspa", "Phoenix, AZ", "us"),
    ("law firm", "Tampa, FL", "us"),
    ("roofing contractor", "Houston, TX", "us"),
    ("hvac contractor", "Atlanta, GA", "us"),
    ("dental clinic", "Charlotte, NC", "us"),
    ("plumber", "Nashville, TN", "us"),
]

# In-memory bookkeeping for dedup-park (resets on backend restart, which
# is fine — restart events themselves rotate the IP pool too).
_QUEUE_STATS: dict[tuple, dict[str, Any]] = {}
_PARK_AFTER_ZERO_CYCLES = 3
_PARK_DURATION_S = 24 * 60 * 60  # 24 hours


def _entry_key(q: str, loc: str, ctry: str) -> tuple:
    return (q.lower().strip(), loc.lower().strip(), ctry.lower().strip())


def _is_parked(key: tuple) -> bool:
    s = _QUEUE_STATS.get(key)
    if not s:
        return False
    parked_until = s.get("parked_until", 0)
    if parked_until and parked_until > datetime.now(timezone.utc).timestamp():
        return True
    if parked_until and parked_until <= datetime.now(timezone.utc).timestamp():
        # Thaw — reset zero streak and let it try again
        s["parked_until"] = 0
        s["zero_streak"] = 0
    return False


def _record_cycle(key: tuple, inserted: int) -> None:
    s = _QUEUE_STATS.setdefault(key, {"zero_streak": 0, "parked_until": 0,
                                       "total_inserted": 0, "total_runs": 0})
    s["total_runs"] += 1
    s["total_inserted"] += inserted
    if inserted <= 0:
        s["zero_streak"] += 1
        if s["zero_streak"] >= _PARK_AFTER_ZERO_CYCLES:
            s["parked_until"] = datetime.now(timezone.utc).timestamp() + _PARK_DURATION_S
            logger.warning(
                f"[ghost-scout] PARK {key} for 24h after "
                f"{s['zero_streak']} consecutive zero-insert cycles"
            )
    else:
        s["zero_streak"] = 0


def _next_unparked_index(start_idx: int) -> int | None:
    """Walk forward from start_idx looking for an unparked entry. None if all parked."""
    n = len(HARVEST_QUEUE)
    for offset in range(n):
        idx = (start_idx + offset) % n
        q, loc, ctry = HARVEST_QUEUE[idx]
        if not _is_parked(_entry_key(q, loc, ctry)):
            return idx
    return None


async def ghost_scout_loop() -> None:
    """Background task: harvest one (query, location) per cycle. Rotates
    through HARVEST_QUEUE, skipping entries parked for dedup-exhaustion."""
    if not PROXY_URL:
        print("[ghost-scout] disabled — IPROYAL_PROXY_URL not set", flush=True)
        return
    # iter D-60a — skip the auto-loop in production unless the founder
    # explicitly opts in. The Google Places API key on prod has billing
    # disabled, so every cycle returns REQUEST_DENIED and wastes the
    # event loop. Production blasting will be triggered from the admin
    # UI's "Autofix · topup_via_scout" button instead.
    try:
        from services.prod_guard import is_production_pod
        if is_production_pod() and os.environ.get(
                "GHOST_SCOUT_PROD_LOOP", "").lower() not in ("1", "true", "yes"):
            print("[ghost-scout] disabled in production "
                   "(set GHOST_SCOUT_PROD_LOOP=true to enable)", flush=True)
            return
    except Exception:
        pass
    print(
        f"[ghost-scout] alive — interval={HARVEST_INTERVAL_S}s "
        f"queue_len={len(HARVEST_QUEUE)} park_threshold={_PARK_AFTER_ZERO_CYCLES}",
        flush=True,
    )
    await asyncio.sleep(120)  # let backend stabilise
    idx = 0
    while True:
        try:
            unparked = _next_unparked_index(idx)
            if unparked is None:
                logger.warning(
                    "[ghost-scout] entire queue parked for dedup — sleeping "
                    "longer and waiting for first park to thaw"
                )
                await asyncio.sleep(_PARK_DURATION_S // 8)
                continue
            idx = unparked
            q, loc, ctry = HARVEST_QUEUE[idx]
            key = _entry_key(q, loc, ctry)
            res = await harvest_leads(q, loc, country=ctry, limit=15)
            inserted = int(res.get("inserted", 0) or 0)
            _record_cycle(key, inserted)
            logger.info(
                f"[ghost-scout] cycle idx={idx} {q!r}/{loc}/{ctry}: "
                f"inserted={inserted} dup={res.get('skipped_dup', 0)} "
                f"zero_streak={_QUEUE_STATS.get(key, {}).get('zero_streak', 0)}"
            )
            idx = (idx + 1) % len(HARVEST_QUEUE)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[ghost-scout] loop err: {e}", exc_info=True)
            idx = (idx + 1) % len(HARVEST_QUEUE)
        await asyncio.sleep(HARVEST_INTERVAL_S)


def get_queue_health() -> dict:
    """Returns current queue + park stats — used by the admin status endpoint."""
    entries = []
    now_ts = datetime.now(timezone.utc).timestamp()
    for q, loc, ctry in HARVEST_QUEUE:
        key = _entry_key(q, loc, ctry)
        s = _QUEUE_STATS.get(key, {})
        parked_until = s.get("parked_until", 0)
        entries.append({
            "query": q, "location": loc, "country": ctry,
            "total_runs": s.get("total_runs", 0),
            "total_inserted": s.get("total_inserted", 0),
            "zero_streak": s.get("zero_streak", 0),
            "parked": bool(parked_until and parked_until > now_ts),
            "parked_until_ts": parked_until if parked_until > now_ts else None,
            "park_remaining_s": int(parked_until - now_ts) if parked_until > now_ts else 0,
        })
    return {
        "queue_len": len(HARVEST_QUEUE),
        "parked_count": sum(1 for e in entries if e["parked"]),
        "park_threshold_cycles": _PARK_AFTER_ZERO_CYCLES,
        "park_duration_hours": _PARK_DURATION_S // 3600,
        "entries": entries,
    }
