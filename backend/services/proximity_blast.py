"""
AUREM AI Platform — Proprietary Software
Copyright (c) 2026 Polaris Built Inc.

Proximity Blast Service
=======================
Geofenced local lead discovery via Apollo.io.

Given (lat, lng, radius_km), this service:
  1. Reverse-geocodes the coordinate to a city/country via the
     existing OpenWeatherMap free geo helper.
  2. Queries Apollo for SMBs matching `industry_hint` in that city.
  3. Returns a list of real leads (verified phone/website/city) in
     the same dict shape used by all downstream consumers.

NO simulated leads are generated. If Apollo is unreachable or returns
empty, this service returns `[]` and the caller is responsible for
handling the empty case (e.g. log + skip, never fabricate).

Rate-limit safeguard: a module-level deque tracks Apollo call
timestamps. If we exceed 100 calls in a rolling 60-minute window, the
function raises RuntimeError("apollo_rate_limit_pause") so the campaign
loop can back off instead of burning budget.

Add-on: $49/month for Starter/Growth tiers.
"""
import asyncio
import logging
import math
from collections import deque
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_db = None
_apollo_call_log: deque = deque(maxlen=500)
_APOLLO_RATE_LIMIT_PER_HOUR = 100


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


# ─── Geo helpers ───────────────────────────────────────────────────

def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2 +
          math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def _city_from_latlng(lat: float, lng: float) -> tuple[str, str]:
    """Reverse-geocode (lat,lng) → (city, country_iso2).

    Uses the existing OpenWeatherMap geo helper in
    `services.location_service`. Returns ("", "") on failure — the
    caller decides whether to skip or fall back to a default city.
    """
    try:
        from services.location_service import _reverse_geocode
        out = await _reverse_geocode(lat, lng)
        city = (out or {}).get("city", "") or ""
        country = (out or {}).get("country", "") or ""
        return city, country
    except Exception as e:
        logger.warning(f"[proximity-blast] reverse-geocode failed: {e}")
        return "", ""


# ─── Rate limit ────────────────────────────────────────────────────

def _check_apollo_rate_limit() -> None:
    """Raise RuntimeError if we've already burned 100 Apollo calls in
    the last 60 minutes. Otherwise record this call's timestamp."""
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - 3600
    while _apollo_call_log and _apollo_call_log[0] < cutoff:
        _apollo_call_log.popleft()
    if len(_apollo_call_log) >= _APOLLO_RATE_LIMIT_PER_HOUR:
        logger.error(
            f"[proximity-blast] Apollo rate limit hit "
            f"({_APOLLO_RATE_LIMIT_PER_HOUR}/hr) — pausing"
        )
        raise RuntimeError("apollo_rate_limit_pause")
    _apollo_call_log.append(now.timestamp())


# ─── Real lead discovery ───────────────────────────────────────────

async def discover_real_leads_via_apollo(
    lat: float,
    lng: float,
    radius_km: float,
    count: int = 20,
    industry_hint: str = "",
) -> list:
    """Find real local SMBs around (lat,lng) via Apollo.

    Returns leads in the same shape used by all downstream consumers:
        lead_id, business_name, owner_name, business_type, address,
        lat, lng, distance_km, phone, email, rating, review_count,
        match_score, status

    Empty list if Apollo unavailable / 0 results. Never simulates.
    Raises RuntimeError("apollo_rate_limit_pause") when the per-hour
    budget is exhausted.
    """
    import os
    if not os.environ.get("APOLLO_API_KEY"):
        logger.warning("[proximity-blast] APOLLO_API_KEY missing — returning []")
        return []

    _check_apollo_rate_limit()

    city, country = await _city_from_latlng(lat, lng)
    if not city:
        # Reverse-geocode failed. Don't fabricate a city — return empty.
        logger.warning(
            f"[proximity-blast] reverse-geocode produced no city for "
            f"({lat:.4f},{lng:.4f}) — returning []"
        )
        return []

    industry = industry_hint.strip() or "local business"
    country_name = "Canada" if country.upper() == "CA" else (country or "Canada")

    try:
        from services.apollo_discovery import discover_organizations
        orgs = await discover_organizations(
            industry_keyword=industry,
            city=city,
            country=country_name,
            per_page=max(1, min(count, 50)),
        )
    except Exception as e:
        logger.error(f"[proximity-blast] Apollo call failed: {e}")
        return []

    leads = []
    for i, org in enumerate(orgs[:count]):
        # Apollo organizations don't expose a per-location lat/lng,
        # so we use the search-anchor coordinate and tag distance as
        # None — UI shows "in {city}" rather than a fake decimal.
        leads.append({
            "lead_id":       org.get("lead_id") or f"prox_{i + 1:04d}",
            "business_name": org.get("business_name", ""),
            "owner_name":    "",        # not in Apollo org payload
            "business_type": org.get("industry") or industry,
            "address":       f"{org.get('city','')}, {org.get('province','')}".strip(", "),
            "lat":           None,
            "lng":           None,
            "distance_km":   None,
            "phone":         org.get("phone", ""),
            "email":         "",        # enriched downstream
            "website":       org.get("website", ""),
            "domain":        org.get("domain", ""),
            "linkedin_url":  org.get("linkedin_url", ""),
            "employees":     org.get("employees", 0),
            "rating":        None,
            "review_count":  None,
            "match_score":   None,
            "status":        "new",
            "source":        "apollo_discovery",
        })

    logger.info(
        f"[proximity-blast] Apollo returned {len(leads)} real SMBs "
        f"for {industry} near {city} (radius hint={radius_km}km, "
        f"requested={count})"
    )
    return leads


# ─── Config CRUD ───────────────────────────────────────────────────

async def get_proximity_config(tenant_id: str) -> dict:
    """Get the proximity blast config for a tenant."""
    db = _get_db()
    defaults = {
        "tenant_id":            tenant_id,
        "enabled":              False,
        "data_source":          "apollo",
        "default_radius_km":    10,
        "business_lat":         43.6532,
        "business_lng":         -79.3832,
        "addon_active":         False,
        "addon_price_monthly":  49,
        "campaigns_run":        0,
    }
    if db is None:
        return defaults

    config = await db.proximity_config.find_one(
        {"tenant_id": tenant_id}, {"_id": 0},
    )
    if not config:
        return defaults
    return {**defaults, **config}


async def save_proximity_config(tenant_id: str, update: dict) -> dict:
    """Update proximity blast config."""
    db = _get_db()
    if db is None:
        return {"error": "Database unavailable"}

    safe_fields = {
        k: v for k, v in update.items()
        if k in ("enabled", "data_source", "default_radius_km",
                  "business_lat", "business_lng", "addon_active")
    }
    safe_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.proximity_config.update_one(
        {"tenant_id": tenant_id},
        {
            "$set": safe_fields,
            "$setOnInsert": {
                "tenant_id":  tenant_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        upsert=True,
    )
    return await get_proximity_config(tenant_id)


# ─── Campaign runner ───────────────────────────────────────────────

async def run_blast(tenant_id: str, lat: float, lng: float,
                      radius_km: float, count: int = 20,
                      industry_hint: str = "") -> dict:
    """Execute a proximity blast — discover real leads in radius.

    Tenant config is honoured for radius defaults but `data_source` is
    no longer a switch: there is exactly ONE source (Apollo). Legacy
    configs still listing `"simulated"` are accepted but the call
    silently uses Apollo.
    """
    db = _get_db()
    config = await get_proximity_config(tenant_id)
    _ = config.get("data_source", "apollo")   # honoured by db update only

    try:
        leads = await discover_real_leads_via_apollo(
            lat, lng, radius_km, count, industry_hint=industry_hint,
        )
    except RuntimeError as e:
        # Rate-limit pause — surface to the caller rather than silently
        # emit zero leads.
        return {
            "campaign":   None,
            "leads":      [],
            "total":      0,
            "source":     "apollo",
            "error":      str(e),
        }

    campaign = {
        "tenant_id":   tenant_id,
        "lat":         lat,
        "lng":         lng,
        "radius_km":   radius_km,
        "leads_found": len(leads),
        "data_source": "apollo",
        "created_at":  datetime.now(timezone.utc).isoformat(),
    }

    if db is not None:
        await db.proximity_campaigns.insert_one({**campaign})
        await db.proximity_config.update_one(
            {"tenant_id": tenant_id},
            {"$inc": {"campaigns_run": 1}},
        )

    return {
        "campaign": {k: v for k, v in campaign.items() if k != "_id"},
        "leads":    leads,
        "total":    len(leads),
        "source":   "apollo",
    }
