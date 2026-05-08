"""
AUREM Location Service — IP/GPS-aware geolocation + weather cache
==================================================================
Single source of truth for "where is this user/customer right now?"
Used by:
  • Saturday warm-message generator (city + weather + cultural events)
  • Sunday morning brief (timezone-aware send-time)
  • Customer onboarding (auto-fill city)
  • ORA Widget (location-aware support)

Resolution order (most → least authoritative):
  1. GPS coords (PWA navigator.geolocation push) → exact
  2. Stored postal_code (Canadian FSA → city)
  3. IP geolocation (ipapi.co)
  4. Generic Canadian seasonal fallback

Travel detection:
  - postal city ≠ IP city + IP city >50km away → travel_flag=True
  - IP city >500km from postal city in <24h → likely VPN, prefer postal

Cache: weather cached 1h in MongoDB `location_weather_cache` collection
       (TTL index, never grows beyond hot region count).

External APIs (cheap, no auth budget):
  • ipapi.co/json/{ip}      — free 1k/day, no key, good Canadian coverage
  • api.openweathermap.org  — free 1k/day, key in OPENWEATHERMAP_API_KEY env
"""
from __future__ import annotations

import os
import math
import asyncio
import logging
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

_db = None
OWM_KEY = os.environ.get("OPENWEATHERMAP_API_KEY", "")
OWM_TIMEOUT_S = 4.0
IP_TIMEOUT_S = 4.0
WEATHER_CACHE_HOURS = 1

# ── Canadian postal code FSA prefix → primary city map (top 50 covers ~90% lead volume) ──
# Source: Canada Post FSA reference. Lowercase first letter for case-insensitive lookup.
_FSA_TO_CITY = {
    # Toronto / GTA
    "M": "Toronto", "L": "GTA",
    # Ottawa / E-Ontario
    "K": "Ottawa",
    # Niagara / SW-Ontario
    "N": "London",
    # Quebec
    "H": "Montreal", "J": "Laval", "G": "Quebec City",
    # Atlantic
    "E": "Moncton", "B": "Halifax", "C": "Charlottetown", "A": "St. John's",
    # Prairies
    "R": "Winnipeg", "S": "Saskatoon", "T": "Calgary",
    # BC / Yukon / North
    "V": "Vancouver", "X": "Yellowknife", "Y": "Whitehorse",
    "P": "Sudbury",  # NW Ontario
}

WEATHER_EMOJI = {
    "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️", "Drizzle": "🌦️",
    "Thunderstorm": "⛈️", "Snow": "❄️", "Mist": "🌫️", "Fog": "🌫️",
    "Haze": "🌫️", "Smoke": "🌫️",
}


def set_db(database):
    global _db
    _db = database


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

async def resolve_location(
    *,
    ip: Optional[str] = None,
    postal_code: Optional[str] = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve the authoritative location for a single user/session.

    Returns a dict with at minimum:
      {
        "source": "gps" | "postal" | "ip" | "fallback",
        "city": str,
        "country": "CA" | "US" | <ISO> | "??",
        "lat": float | None,
        "lon": float | None,
        "travel_flag": bool,
        "vpn_suspected": bool,
        "international": bool,    # outside CA
      }
    """
    # 1. GPS wins outright when present and plausible
    if gps_lat is not None and gps_lon is not None and -90 <= gps_lat <= 90 and -180 <= gps_lon <= 180:
        rev = await _reverse_geocode(gps_lat, gps_lon)
        return {
            "source": "gps",
            "city": rev.get("city") or "Unknown",
            "country": rev.get("country") or "CA",
            "lat": gps_lat, "lon": gps_lon,
            "travel_flag": False,
            "vpn_suspected": False,
            "international": (rev.get("country") or "CA") != "CA",
        }

    # 2. IP lookup (parallel to postal map for speed)
    ip_data = await _lookup_ip(ip) if ip else {}
    postal_city = _postal_to_city(postal_code) if postal_code else None

    ip_city = (ip_data.get("city") or "").strip()
    ip_country = (ip_data.get("country_code") or "").upper()
    ip_lat = ip_data.get("latitude")
    ip_lon = ip_data.get("longitude")

    # 3. Decide source
    travel_flag = False
    vpn_suspected = False
    if postal_city and ip_city and postal_city.lower() != ip_city.lower():
        # Same city naming variation? (e.g. "Toronto" vs "Etobicoke")
        # Use distance heuristic if we have ip_lat/lon and postal coords (approx).
        dist_km = await _city_distance_km(postal_city, ip_city, ip_lat, ip_lon)
        if dist_km is not None and dist_km > 500:
            vpn_suspected = True
        elif dist_km is not None and dist_km > 50:
            travel_flag = True

    # 4. Pick winning source
    if postal_city and not travel_flag and not vpn_suspected:
        # Postal code is the most reliable for repeat customers
        return {
            "source": "postal",
            "city": postal_city,
            "country": "CA",
            "lat": ip_lat, "lon": ip_lon,
            "travel_flag": False,
            "vpn_suspected": vpn_suspected,
            "international": False,
        }
    if ip_city and not vpn_suspected:
        return {
            "source": "ip",
            "city": ip_city,
            "country": ip_country or "CA",
            "lat": ip_lat, "lon": ip_lon,
            "travel_flag": travel_flag,
            "vpn_suspected": False,
            "international": ip_country and ip_country != "CA",
        }
    if vpn_suspected and postal_city:
        return {
            "source": "postal",
            "city": postal_city, "country": "CA",
            "lat": None, "lon": None,
            "travel_flag": False, "vpn_suspected": True,
            "international": False,
        }

    # 5. Generic Canadian fallback
    return {
        "source": "fallback",
        "city": "Canada",
        "country": "CA",
        "lat": None, "lon": None,
        "travel_flag": False,
        "vpn_suspected": False,
        "international": False,
    }


async def get_weather(city: str, lat: Optional[float] = None, lon: Optional[float] = None) -> Dict[str, Any]:
    """Return current weather for a city. Cached 1h in MongoDB.

    {"city": str, "temp_c": float, "condition": str, "emoji": str}
    """
    if not city:
        return _weather_fallback(city or "Canada")

    cache_key = f"{(city or '').lower()}|{round(lat or 0, 2)}|{round(lon or 0, 2)}"
    cached = await _read_weather_cache(cache_key)
    if cached:
        return cached

    if not OWM_KEY:
        out = _weather_fallback(city)
        await _write_weather_cache(cache_key, out)
        return out

    try:
        params = {"appid": OWM_KEY, "units": "metric"}
        if lat is not None and lon is not None:
            params["lat"] = lat
            params["lon"] = lon
        else:
            params["q"] = f"{city},CA"
        async with httpx.AsyncClient(timeout=OWM_TIMEOUT_S) as client:
            r = await client.get("https://api.openweathermap.org/data/2.5/weather", params=params)
            if r.status_code != 200:
                out = _weather_fallback(city)
                await _write_weather_cache(cache_key, out)
                return out
            data = r.json()
            cond = (data.get("weather") or [{}])[0].get("main", "Clear")
            out = {
                "city": data.get("name") or city,
                "temp_c": round(float(data.get("main", {}).get("temp", 0.0)), 1),
                "condition": cond,
                "emoji": WEATHER_EMOJI.get(cond, "🌤️"),
            }
            await _write_weather_cache(cache_key, out)
            return out
    except Exception as e:
        logger.debug(f"[location] OWM failed for {city}: {e}")
        out = _weather_fallback(city)
        await _write_weather_cache(cache_key, out)
        return out


# ─────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────

async def _lookup_ip(ip: str) -> Dict[str, Any]:
    """ipapi.co lookup with hard timeout. Fails silent → empty dict."""
    if not ip or ip in ("127.0.0.1", "::1") or ip.startswith("10.") or ip.startswith("192.168.") or ip.startswith("172."):
        return {}
    try:
        async with httpx.AsyncClient(timeout=IP_TIMEOUT_S) as client:
            r = await client.get(f"https://ipapi.co/{ip}/json/", headers={"User-Agent": "AUREM/1.0"})
            if r.status_code == 200:
                d = r.json()
                # Filter known stubs
                if d.get("error"):
                    return {}
                return d
    except Exception as e:
        logger.debug(f"[location] ipapi failed for {ip}: {e}")
    return {}


def _postal_to_city(postal: str) -> Optional[str]:
    if not postal:
        return None
    p = postal.strip().upper().replace(" ", "")
    if not p:
        return None
    return _FSA_TO_CITY.get(p[0])


async def _reverse_geocode(lat: float, lon: float) -> Dict[str, Any]:
    """Use OWM reverse-geo endpoint (free, no extra key)."""
    if not OWM_KEY:
        return {}
    try:
        async with httpx.AsyncClient(timeout=OWM_TIMEOUT_S) as client:
            r = await client.get(
                "https://api.openweathermap.org/geo/1.0/reverse",
                params={"lat": lat, "lon": lon, "limit": 1, "appid": OWM_KEY},
            )
            if r.status_code != 200:
                return {}
            arr = r.json() or []
            if not arr:
                return {}
            d = arr[0]
            return {"city": d.get("name"), "country": d.get("country")}
    except Exception:
        return {}


async def _city_distance_km(city_a: str, city_b: str, lat: Optional[float], lon: Optional[float]) -> Optional[float]:
    """Best-effort distance between postal-mapped city and IP-detected location.

    We don't geocode city_a (postal map → city) — instead we accept lat/lon
    of the IP location and compare against a tiny lookup table for Canadian
    cities. Good enough for VPN detection (>500km threshold).
    """
    if lat is None or lon is None:
        return None
    canon = _CITY_COORDS.get(city_a.title())
    if not canon:
        return None
    return _haversine_km(canon[0], canon[1], lat, lon)


# Tiny lookup of major Canadian city centroids (covers ~95% lead volume).
_CITY_COORDS = {
    "Toronto": (43.6532, -79.3832), "Gta": (43.6532, -79.3832),
    "Ottawa": (45.4215, -75.6972), "London": (42.9849, -81.2453),
    "Montreal": (45.5017, -73.5673), "Laval": (45.6066, -73.7124),
    "Quebec City": (46.8139, -71.2080),
    "Moncton": (46.0878, -64.7782), "Halifax": (44.6488, -63.5752),
    "Charlottetown": (46.2382, -63.1311), "St. John's": (47.5615, -52.7126),
    "Winnipeg": (49.8951, -97.1384), "Saskatoon": (52.1332, -106.6700),
    "Calgary": (51.0447, -114.0719), "Vancouver": (49.2827, -123.1207),
    "Yellowknife": (62.4540, -114.3718), "Whitehorse": (60.7212, -135.0568),
    "Sudbury": (46.4917, -80.9930),
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _weather_fallback(city: str) -> Dict[str, Any]:
    """Generic seasonal fallback when OWM is down or no key."""
    month = datetime.now(timezone.utc).month
    if month in (12, 1, 2):
        return {"city": city, "temp_c": -5.0, "condition": "Snow", "emoji": "❄️"}
    if month in (3, 4, 5):
        return {"city": city, "temp_c": 10.0, "condition": "Clouds", "emoji": "🌤️"}
    if month in (6, 7, 8):
        return {"city": city, "temp_c": 24.0, "condition": "Clear", "emoji": "☀️"}
    return {"city": city, "temp_c": 8.0, "condition": "Clouds", "emoji": "🍂"}


# ─────────────────────────────────────────────────────────────────────
# Cache (MongoDB, TTL 1h)
# ─────────────────────────────────────────────────────────────────────

async def _read_weather_cache(key: str) -> Optional[Dict[str, Any]]:
    if _db is None:
        return None
    try:
        doc = await asyncio.wait_for(
            _db.location_weather_cache.find_one({"_id": key}, {"_id": 0, "data": 1, "ts": 1}),
            timeout=1.5,
        )
        if not doc:
            return None
        ts = doc.get("ts")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                return None
        if ts and (datetime.now(timezone.utc) - ts) < timedelta(hours=WEATHER_CACHE_HOURS):
            return doc.get("data")
    except Exception:
        return None
    return None


async def _write_weather_cache(key: str, data: Dict[str, Any]) -> None:
    if _db is None:
        return
    try:
        await asyncio.wait_for(
            _db.location_weather_cache.update_one(
                {"_id": key},
                {"$set": {"data": data, "ts": datetime.now(timezone.utc)}},
                upsert=True,
            ),
            timeout=1.5,
        )
    except Exception:
        pass


async def ensure_indexes() -> None:
    if _db is None:
        return
    try:
        await _db.location_weather_cache.create_index(
            "ts", expireAfterSeconds=WEATHER_CACHE_HOURS * 3600 + 300,
        )
    except Exception as e:
        logger.debug(f"[location] index ensure skipped: {e}")
