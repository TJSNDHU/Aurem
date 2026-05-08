"""
AUREM Free API Arsenal — Zero-Cost Intelligence Layer
======================================================
Curated from public-apis repo. Each API: $0 cost, no/free auth.
Replaces paid dependencies and adds missing capabilities.

Integrated APIs:
  1. Open-Meteo        — Weather (replaces OpenWeatherMap, NO key needed)
  2. URLhaus           — Malware URL detection (Shannon security, NO key)
  3. LibreTranslate    — 17-language translation (NO key)
  4. Tomba.io          — B2B email finder (Forensic Miner, free 50/mo)
  5. Numverify         — Phone validation (lead enrichment)
  6. Domainsdb.info    — Domain search (Forensic Miner, NO key)
  7. Open-Meteo AQI    — Air quality index (NO key)
  8. ExchangeRate.host — Currency exchange CAD/USD (NO key)
  9. IPapi.co          — IP geolocation (NO key, 1000/day)
  10. Mailboxlayer     — Email validation (free tier)
"""
import os
import re
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, List

import httpx

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


# ═══════════════════════════════════════════════════════════════
# 1. OPEN-METEO — Weather (replaces OpenWeatherMap, $0, NO KEY)
# ═══════════════════════════════════════════════════════════════

async def get_weather(lat: float = 43.59, lon: float = -79.65, city: str = "Mississauga") -> Dict:
    """Free weather via Open-Meteo. No API key needed. Replaces OpenWeatherMap."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code,apparent_temperature",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
                "timezone": "America/Toronto", "forecast_days": 3,
            })
            if r.status_code == 200:
                d = r.json()
                cur = d.get("current", {})
                WMO = {0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                       45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle",
                       55: "Dense drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
                       71: "Light snow", 73: "Snow", 75: "Heavy snow", 80: "Rain showers",
                       95: "Thunderstorm", 96: "Thunderstorm + hail"}
                return {
                    "city": city, "source": "open-meteo", "cost": "$0",
                    "temp_c": cur.get("temperature_2m"),
                    "feels_like_c": cur.get("apparent_temperature"),
                    "humidity": cur.get("relative_humidity_2m"),
                    "wind_kph": cur.get("wind_speed_10m"),
                    "condition": WMO.get(cur.get("weather_code", 0), "Unknown"),
                    "forecast_3d": [{"date": d["daily"]["time"][i], "high": d["daily"]["temperature_2m_max"][i], "low": d["daily"]["temperature_2m_min"][i], "rain_mm": d["daily"]["precipitation_sum"][i]} for i in range(min(3, len(d.get("daily", {}).get("time", []))))],
                }
    except Exception as e:
        logger.debug(f"[FreeAPI] Open-Meteo: {e}")
    return {"city": city, "source": "open-meteo", "error": "unavailable"}


# ═══════════════════════════════════════════════════════════════
# 2. URLHAUS — Malware URL Detection (Shannon, $0, NO KEY)
# ═══════════════════════════════════════════════════════════════

async def check_url_malware(url: str) -> Dict:
    """Check if a URL is known malware/phishing via URLhaus (abuse.ch). Free, no key."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.post("https://urlhaus-api.abuse.ch/v1/url/", data={"url": url})
            if r.status_code == 200:
                d = r.json()
                return {
                    "url": url, "source": "urlhaus", "cost": "$0",
                    "threat": d.get("query_status") == "listed",
                    "status": d.get("query_status", "unknown"),
                    "threat_type": d.get("threat", ""),
                    "tags": d.get("tags", []),
                    "date_added": d.get("date_added", ""),
                }
    except Exception as e:
        logger.debug(f"[FreeAPI] URLhaus: {e}")
    return {"url": url, "source": "urlhaus", "threat": False, "status": "check_failed"}


async def check_url_batch(urls: List[str]) -> List[Dict]:
    """Batch check multiple URLs for malware."""
    tasks = [check_url_malware(u) for u in urls[:20]]
    return await asyncio.gather(*tasks, return_exceptions=False)


# ═══════════════════════════════════════════════════════════════
# 3. LIBRETRANSLATE — 17-Language Translation ($0, NO KEY)
# ═══════════════════════════════════════════════════════════════

LIBRE_URL = "https://libretranslate.com"

async def translate_text(text: str, source: str = "auto", target: str = "en") -> Dict:
    """Free translation via LibreTranslate. No API key. 17 languages."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(f"{LIBRE_URL}/translate", json={
                "q": text[:5000], "source": source, "target": target, "format": "text",
            })
            if r.status_code == 200:
                d = r.json()
                return {"translated": d.get("translatedText", ""), "source_lang": source, "target_lang": target, "source_api": "libretranslate", "cost": "$0"}
    except Exception as e:
        logger.debug(f"[FreeAPI] LibreTranslate: {e}")
    return {"translated": "", "error": "translation_unavailable", "source_api": "libretranslate"}


async def detect_language(text: str) -> Dict:
    """Detect language of text via LibreTranslate."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.post(f"{LIBRE_URL}/detect", json={"q": text[:1000]})
            if r.status_code == 200:
                langs = r.json()
                if langs and isinstance(langs, list):
                    return {"language": langs[0].get("language"), "confidence": langs[0].get("confidence"), "source_api": "libretranslate"}
    except Exception as e:
        logger.debug(f"[FreeAPI] Language detect: {e}")
    return {"language": "en", "confidence": 0, "source_api": "fallback"}


# ═══════════════════════════════════════════════════════════════
# 4. DOMAINSDB — Domain Search (Forensic Miner, $0, NO KEY)
# ═══════════════════════════════════════════════════════════════

async def search_domains(keyword: str, zone: str = "com", limit: int = 20) -> Dict:
    """Search registered domains by keyword. Free, no key. For Forensic Miner competitor discovery."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get("https://api.domainsdb.info/v1/domains/search", params={"domain": keyword, "zone": zone, "limit": limit})
            if r.status_code == 200:
                d = r.json()
                domains = d.get("domains", [])
                return {
                    "keyword": keyword, "zone": zone, "source": "domainsdb", "cost": "$0",
                    "total": d.get("total", len(domains)),
                    "domains": [{"domain": dom.get("domain"), "create_date": dom.get("create_date"), "update_date": dom.get("update_date"), "country": dom.get("country")} for dom in domains[:limit]],
                }
    except Exception as e:
        logger.debug(f"[FreeAPI] DomainsDB: {e}")
    return {"keyword": keyword, "domains": [], "source": "domainsdb", "error": "unavailable"}


# ═══════════════════════════════════════════════════════════════
# 5. EXCHANGERATE — Currency Rates ($0, NO KEY)
# ═══════════════════════════════════════════════════════════════

async def get_exchange_rates(base: str = "CAD") -> Dict:
    """Free currency exchange rates. No key needed."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(f"https://open.er-api.com/v6/latest/{base}")
            if r.status_code == 200:
                d = r.json()
                rates = d.get("rates", {})
                return {
                    "base": base, "source": "open-er-api", "cost": "$0",
                    "usd": rates.get("USD"), "eur": rates.get("EUR"), "gbp": rates.get("GBP"),
                    "inr": rates.get("INR"), "cny": rates.get("CNY"), "jpy": rates.get("JPY"),
                    "updated": d.get("time_last_update_utc", ""),
                }
    except Exception as e:
        logger.debug(f"[FreeAPI] ExchangeRate: {e}")
    return {"base": base, "source": "open-er-api", "error": "unavailable"}


# ═══════════════════════════════════════════════════════════════
# 6. IP-API — IP Geolocation ($0, NO KEY, 45/min)
# ═══════════════════════════════════════════════════════════════

async def geolocate_ip(ip: str) -> Dict:
    """Free IP geolocation via ip-api.com. No key, 45 req/min."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"http://ip-api.com/json/{ip}", params={"fields": "status,country,regionName,city,zip,lat,lon,timezone,isp,org,query"})
            if r.status_code == 200:
                d = r.json()
                if d.get("status") == "success":
                    return {
                        "ip": ip, "source": "ip-api", "cost": "$0",
                        "country": d.get("country"), "region": d.get("regionName"),
                        "city": d.get("city"), "zip": d.get("zip"),
                        "lat": d.get("lat"), "lon": d.get("lon"),
                        "timezone": d.get("timezone"), "isp": d.get("isp"), "org": d.get("org"),
                    }
    except Exception as e:
        logger.debug(f"[FreeAPI] IP-API: {e}")
    return {"ip": ip, "source": "ip-api", "error": "unavailable"}


# ═══════════════════════════════════════════════════════════════
# 7. EMAIL VALIDATION — Regex + DNS MX Check ($0, NO KEY)
# ═══════════════════════════════════════════════════════════════

async def validate_email(email: str) -> Dict:
    """Validate email format + DNS MX check. Zero cost, no external API."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return {"email": email, "valid": False, "reason": "invalid_format", "cost": "$0"}
    domain = email.split("@")[1]
    # DNS MX check
    try:
        import subprocess
        result = subprocess.run(["nslookup", "-type=mx", domain], capture_output=True, text=True, timeout=5)
        has_mx = "mail exchanger" in result.stdout.lower() or "mx" in result.stdout.lower()
        disposable_domains = {"tempmail.com", "guerrillamail.com", "mailinator.com", "throwaway.email", "yopmail.com", "trashmail.com", "sharklasers.com"}
        return {
            "email": email, "valid": has_mx, "domain": domain,
            "has_mx": has_mx, "disposable": domain in disposable_domains,
            "source": "dns_mx_check", "cost": "$0",
        }
    except Exception:
        return {"email": email, "valid": True, "domain": domain, "has_mx": None, "source": "regex_only", "cost": "$0"}


# ═══════════════════════════════════════════════════════════════
# 8. US WEATHER SERVICE — Alerts ($0, NO KEY)
# ═══════════════════════════════════════════════════════════════

async def get_weather_alerts(lat: float = 43.59, lon: float = -79.65) -> Dict:
    """Free severe weather alerts via Open-Meteo. No key."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": lat, "longitude": lon,
                "daily": "uv_index_max,precipitation_probability_max",
                "timezone": "auto", "forecast_days": 3,
            })
            if r.status_code == 200:
                d = r.json()
                daily = d.get("daily", {})
                alerts = []
                for i, date in enumerate(daily.get("time", [])):
                    uv = daily.get("uv_index_max", [0])[i] if i < len(daily.get("uv_index_max", [])) else 0
                    precip = daily.get("precipitation_probability_max", [0])[i] if i < len(daily.get("precipitation_probability_max", [])) else 0
                    if uv and uv > 8:
                        alerts.append({"date": date, "type": "uv_extreme", "value": uv, "message": f"Extreme UV index: {uv}"})
                    if precip and precip > 80:
                        alerts.append({"date": date, "type": "heavy_rain", "value": precip, "message": f"Heavy precipitation likely: {precip}%"})
                return {"alerts": alerts, "count": len(alerts), "source": "open-meteo", "cost": "$0"}
    except Exception as e:
        logger.debug(f"[FreeAPI] Weather alerts: {e}")
    return {"alerts": [], "count": 0, "source": "open-meteo"}


# ═══════════════════════════════════════════════════════════════
# 9. TOMBA.IO — B2B Email Finder (Forensic Miner, free 50/mo)
# ═══════════════════════════════════════════════════════════════

TOMBA_KEY = os.environ.get("TOMBA_API_KEY", "")
TOMBA_SECRET = os.environ.get("TOMBA_SECRET", "")


async def find_emails_by_domain(domain: str, limit: int = 10) -> Dict:
    """Find email addresses for a company domain.

    iter 282f — Defaults to the sovereign `tomba_local` miner (Playwright +
    regex + MX verify, zero cost). Falls back to the paid Tomba.io API
    only if `TOMBA_API_KEY` is set AND `TOMBA_LOCAL_DISABLED=1` (opt-in).
    """
    if not TOMBA_KEY or os.environ.get("TOMBA_LOCAL_DISABLED") != "1":
        try:
            from services.tomba_local import find_emails_by_domain as _local_find
            return await _local_find(domain, limit=limit)
        except Exception as e:
            logger.warning(f"[FreeAPI] tomba_local failed, falling back: {e}")
            if not TOMBA_KEY:
                return {"domain": domain, "emails": [], "source": "tomba_local",
                        "error": str(e)[:120], "cost": "$0"}
    # Paid Tomba.io path (kept for users who already have a key)
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get("https://api.tomba.io/v1/domain-search", params={"domain": domain, "limit": limit},
                            headers={"X-Tomba-Key": TOMBA_KEY, "X-Tomba-Secret": TOMBA_SECRET})
            if r.status_code == 200:
                d = r.json().get("data", {})
                emails = d.get("emails", [])
                return {
                    "domain": domain, "source": "tomba", "cost": "$0 (free tier)",
                    "organization": d.get("organization", ""),
                    "total_found": len(emails),
                    "emails": [{"email": e.get("email"), "type": e.get("type", ""), "confidence": e.get("confidence", 0), "first_name": e.get("first_name", ""), "last_name": e.get("last_name", ""), "department": e.get("department", "")} for e in emails[:limit]],
                }
            return {"domain": domain, "emails": [], "source": "tomba", "error": f"HTTP {r.status_code}", "cost": "$0"}
    except Exception as e:
        logger.debug(f"[FreeAPI] Tomba: {e}")
    return {"domain": domain, "emails": [], "source": "tomba", "error": "unavailable"}


async def verify_email_tomba(email: str) -> Dict:
    """Verify an email address.

    iter 282f — Defaults to sovereign MX-based `tomba_local.verify_email`
    when paid Tomba key isn't set (or TOMBA_LOCAL_DISABLED is unset).
    """
    if not TOMBA_KEY or os.environ.get("TOMBA_LOCAL_DISABLED") != "1":
        try:
            from services.tomba_local import verify_email as _local_verify
            return await _local_verify(email)
        except Exception as e:
            logger.warning(f"[FreeAPI] tomba_local verify failed: {e}")
            if not TOMBA_KEY:
                return {"email": email, "source": "tomba_local",
                        "error": str(e)[:120], "cost": "$0"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get("https://api.tomba.io/v1/email-verifier", params={"email": email},
                            headers={"X-Tomba-Key": TOMBA_KEY, "X-Tomba-Secret": TOMBA_SECRET})
            if r.status_code == 200:
                d = r.json().get("data", {})
                return {
                    "email": email, "source": "tomba", "cost": "$0 (free tier)",
                    "deliverable": d.get("result") == "deliverable",
                    "result": d.get("result", "unknown"),
                    "mx_found": d.get("mx_found", False),
                    "disposable": d.get("disposable", False),
                    "free_provider": d.get("free", False),
                    "score": d.get("score", 0),
                }
    except Exception as e:
        logger.debug(f"[FreeAPI] Tomba verify: {e}")
    return {"email": email, "source": "tomba", "error": "unavailable"}


# ═══════════════════════════════════════════════════════════════
# 10. NUMVERIFY — Phone Number Validation (WhatsApp leads)
# ═══════════════════════════════════════════════════════════════

NUMVERIFY_KEY = os.environ.get("NUMVERIFY_API_KEY", "")


async def validate_phone(phone: str) -> Dict:
    """Validate phone number via Numverify. Free: 100 lookups/month."""
    if not NUMVERIFY_KEY:
        # DIY fallback: basic format validation
        import re
        cleaned = re.sub(r'[^\d+]', '', phone)
        is_valid = len(cleaned) >= 10 and (cleaned.startswith('+') or cleaned[0].isdigit())
        return {
            "phone": phone, "valid": is_valid, "source": "regex_fallback",
            "note": "Set NUMVERIFY_API_KEY for full validation (free at numverify.com)", "cost": "$0",
        }
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get("http://apilayer.net/api/validate", params={"access_key": NUMVERIFY_KEY, "number": phone})
            if r.status_code == 200:
                d = r.json()
                return {
                    "phone": phone, "source": "numverify", "cost": "$0 (free tier)",
                    "valid": d.get("valid", False),
                    "country": d.get("country_name", ""),
                    "country_code": d.get("country_code", ""),
                    "carrier": d.get("carrier", ""),
                    "line_type": d.get("line_type", ""),
                    "international_format": d.get("international_format", ""),
                    "local_format": d.get("local_format", ""),
                }
    except Exception as e:
        logger.debug(f"[FreeAPI] Numverify: {e}")
    return {"phone": phone, "source": "numverify", "error": "unavailable"}


# ═══════════════════════════════════════════════════════════════
# 11. IPSTACK — Rich IP Geolocation (AURA welcome screen)
# ═══════════════════════════════════════════════════════════════

IPSTACK_KEY = os.environ.get("IPSTACK_API_KEY", "")


async def geolocate_ip_rich(ip: str) -> Dict:
    """Rich IP geolocation via IPstack. Free: 100 lookups/month. Falls back to ip-api.com."""
    if IPSTACK_KEY:
        try:
            async with httpx.AsyncClient(timeout=8.0) as c:
                r = await c.get(f"http://api.ipstack.com/{ip}", params={"access_key": IPSTACK_KEY})
                if r.status_code == 200:
                    d = r.json()
                    if d.get("country_name"):
                        return {
                            "ip": ip, "source": "ipstack", "cost": "$0 (free tier)",
                            "country": d.get("country_name"), "country_code": d.get("country_code"),
                            "region": d.get("region_name"), "city": d.get("city"),
                            "zip": d.get("zip"), "lat": d.get("latitude"), "lon": d.get("longitude"),
                            "timezone": d.get("time_zone", {}).get("id", "") if isinstance(d.get("time_zone"), dict) else "",
                            "currency": d.get("currency", {}).get("code", "") if isinstance(d.get("currency"), dict) else "",
                            "flag": d.get("location", {}).get("country_flag", "") if isinstance(d.get("location"), dict) else "",
                            "languages": [lang.get("name") for lang in d.get("location", {}).get("languages", [])] if isinstance(d.get("location"), dict) else [],
                        }
        except Exception as e:
            logger.debug(f"[FreeAPI] IPstack: {e}")

    # Fallback to ip-api.com (no key needed)
    return await geolocate_ip(ip)


# ═══════════════════════════════════════════════════════════════
# 12. DEEPAI — Image Analysis/Vision ($0 free tier, replaces MMX vision)
# ═══════════════════════════════════════════════════════════════

DEEPAI_KEY = os.environ.get("DEEPAI_API_KEY", "")


async def analyze_image_vision(image_url: str, question: str = "Describe this image") -> Dict:
    """Free image analysis via DeepAI. Replaces mmx vision. Free tier available."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            headers = {}
            if DEEPAI_KEY:
                headers["api-key"] = DEEPAI_KEY
            r = await c.post("https://api.deepai.org/api/image-recognition", data={"image": image_url}, headers=headers)
            if r.status_code == 200:
                d = r.json()
                return {
                    "image_url": image_url, "source": "deepai", "cost": "$0 (free tier)",
                    "description": d.get("output", {}).get("description", d.get("output", "")),
                    "tags": d.get("output", {}).get("tags", []) if isinstance(d.get("output"), dict) else [],
                }
            return {"image_url": image_url, "source": "deepai", "error": f"HTTP {r.status_code}"}
    except Exception as e:
        logger.debug(f"[FreeAPI] DeepAI: {e}")

    # Fallback: return text description request
    return {"image_url": image_url, "source": "fallback", "description": f"Image at {image_url} — visual analysis unavailable", "note": "Set DEEPAI_API_KEY for free image analysis (deepai.org)"}


# ═══════════════════════════════════════════════════════════════
# 13. JAMENDO — Royalty-Free Music ($0, NO KEY, replaces MMX music)
# ═══════════════════════════════════════════════════════════════

JAMENDO_CLIENT_ID = os.environ.get("JAMENDO_CLIENT_ID", "")


async def search_music(query: str = "corporate background", limit: int = 5, mood: str = "") -> Dict:
    """Search royalty-free music via Jamendo. Free, CC licensed. For video content engine."""
    params = {"client_id": JAMENDO_CLIENT_ID or "demo", "format": "json", "limit": limit, "namesearch": query, "include": "musicinfo"}
    if mood:
        params["tags"] = mood
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get("https://api.jamendo.com/v3.0/tracks/", params=params)
            if r.status_code == 200:
                d = r.json()
                tracks = d.get("results", [])
                return {
                    "query": query, "source": "jamendo", "cost": "$0 (CC licensed)", "license": "Creative Commons",
                    "tracks": [{
                        "name": t.get("name", ""),
                        "artist": t.get("artist_name", ""),
                        "duration": t.get("duration", 0),
                        "audio_url": t.get("audio", ""),
                        "download_url": t.get("audiodownload", ""),
                        "license": t.get("license_ccurl", ""),
                        "tags": t.get("musicinfo", {}).get("tags", {}).get("genres", []) if isinstance(t.get("musicinfo"), dict) else [],
                    } for t in tracks[:limit]],
                    "total": len(tracks),
                }
    except Exception as e:
        logger.debug(f"[FreeAPI] Jamendo: {e}")
    return {"query": query, "source": "jamendo", "tracks": [], "error": "unavailable", "note": "Set JAMENDO_CLIENT_ID at developer.jamendo.com (free)"}


# ═══════════════════════════════════════════════════════════════
# MASTER REGISTRY — All free APIs
# ═══════════════════════════════════════════════════════════════

FREE_API_REGISTRY = {
    "open_meteo": {"name": "Open-Meteo", "replaces": "OpenWeatherMap ($0 vs apiKey)", "auth": "None", "module": "AURA/Scout"},
    "urlhaus": {"name": "URLhaus", "replaces": "NEW — malware URL detection", "auth": "None", "module": "Shannon Security"},
    "libretranslate": {"name": "LibreTranslate", "replaces": "NEW — 17-language translation", "auth": "None", "module": "AURA/WhatsApp"},
    "domainsdb": {"name": "DomainsDB", "replaces": "NEW — competitor domain discovery", "auth": "None", "module": "Forensic Miner"},
    "exchange_rate": {"name": "Open ExchangeRate", "replaces": "NEW — CAD/USD/EUR live rates", "auth": "None", "module": "Scout/Billing"},
    "ip_api": {"name": "IP-API", "replaces": "ip-api.com (already partial)", "auth": "None", "module": "AURA/Security"},
    "email_validation": {"name": "DNS MX Check", "replaces": "Mailboxlayer (paid)", "auth": "None (DIY)", "module": "Forensic Miner/Email"},
    "weather_alerts": {"name": "Open-Meteo Alerts", "replaces": "NEW — severe weather alerts", "auth": "None", "module": "Scout/AURA"},
    "tomba": {"name": "Tomba.io", "replaces": "Hunter.io ($49/mo → $0)", "auth": "apiKey (free 50/mo)", "module": "Forensic Miner"},
    "numverify": {"name": "Numverify", "replaces": "NEW — phone validation for WhatsApp leads", "auth": "apiKey (free 100/mo)", "module": "WhatsApp/SMS"},
    "ipstack": {"name": "IPstack", "replaces": "IP-API (richer data: currency, flag, languages)", "auth": "apiKey (free 100/mo)", "module": "AURA Welcome Screen"},
    "deepai": {"name": "DeepAI Vision", "replaces": "MMX vision ($0 free tier)", "auth": "apiKey (free)", "module": "V2V/ORA Vision"},
    "jamendo": {"name": "Jamendo Music", "replaces": "MMX music ($0, CC licensed)", "auth": "client_id (free)", "module": "Content Engine Video"},
}

TOOL_HANDLERS = {
    "free_weather": lambda args: get_weather(float(args.get("lat", 43.59)), float(args.get("lon", -79.65)), args.get("city", "Mississauga")),
    "free_url_check": lambda args: check_url_malware(args.get("url", "")),
    "free_url_batch": lambda args: check_url_batch(args.get("urls", [])),
    "free_translate": lambda args: translate_text(args.get("text", ""), args.get("source", "auto"), args.get("target", "en")),
    "free_detect_lang": lambda args: detect_language(args.get("text", "")),
    "free_domain_search": lambda args: search_domains(args.get("keyword", ""), args.get("zone", "com"), int(args.get("limit", 20))),
    "free_exchange_rates": lambda args: get_exchange_rates(args.get("base", "CAD")),
    "free_geolocate_ip": lambda args: geolocate_ip(args.get("ip", "")),
    "free_validate_email": lambda args: validate_email(args.get("email", "")),
    "free_weather_alerts": lambda args: get_weather_alerts(float(args.get("lat", 43.59)), float(args.get("lon", -79.65))),
    "free_find_emails": lambda args: find_emails_by_domain(args.get("domain", ""), int(args.get("limit", 10))),
    "free_verify_email_tomba": lambda args: verify_email_tomba(args.get("email", "")),
    "free_validate_phone": lambda args: validate_phone(args.get("phone", "")),
    "free_geolocate_ip_rich": lambda args: geolocate_ip_rich(args.get("ip", "")),
    "free_vision": lambda args: analyze_image_vision(args.get("image_url", ""), args.get("question", "Describe this image")),
    "free_music": lambda args: search_music(args.get("query", "corporate background"), int(args.get("limit", 5)), args.get("mood", "")),
}

TOOL_DEFS = [
    {"name": "free_weather", "description": "Free weather via Open-Meteo (no API key). Replaces OpenWeatherMap.", "parameters": {"lat": "Latitude", "lon": "Longitude", "city": "City name"}},
    {"name": "free_url_check", "description": "Check if URL is known malware/phishing via URLhaus (free, no key).", "parameters": {"url": "URL to check"}},
    {"name": "free_url_batch", "description": "Batch check multiple URLs for malware.", "parameters": {"urls": "List of URLs"}},
    {"name": "free_translate", "description": "Translate text between 17 languages via LibreTranslate (free, no key).", "parameters": {"text": "Text to translate", "source": "Source language (auto)", "target": "Target language (en)"}},
    {"name": "free_detect_lang", "description": "Detect language of text.", "parameters": {"text": "Text to detect"}},
    {"name": "free_domain_search", "description": "Search registered domains by keyword for competitor discovery.", "parameters": {"keyword": "Domain keyword", "zone": "TLD (com)", "limit": "Max results"}},
    {"name": "free_exchange_rates", "description": "Live currency exchange rates (CAD/USD/EUR). No key needed.", "parameters": {"base": "Base currency (CAD)"}},
    {"name": "free_geolocate_ip", "description": "IP geolocation — country, city, ISP, coordinates. No key.", "parameters": {"ip": "IP address"}},
    {"name": "free_validate_email", "description": "Validate email format + DNS MX check. Zero cost DIY.", "parameters": {"email": "Email to validate"}},
    {"name": "free_weather_alerts", "description": "Severe weather alerts (UV, precipitation). No key.", "parameters": {"lat": "Latitude", "lon": "Longitude"}},
    {"name": "free_find_emails", "description": "Find emails for a company domain via Tomba.io. Replaces Hunter.io. Free 50/month.", "parameters": {"domain": "Company domain (e.g. reroots.ca)", "limit": "Max results (default: 10)"}},
    {"name": "free_verify_email_tomba", "description": "Verify email deliverability via Tomba.io. Checks MX, disposable, score.", "parameters": {"email": "Email to verify"}},
    {"name": "free_validate_phone", "description": "Validate phone number via Numverify. Country, carrier, line type. Free 100/month.", "parameters": {"phone": "Phone number (E.164 or local format)"}},
    {"name": "free_geolocate_ip_rich", "description": "Rich IP geolocation via IPstack — country, currency, flag, languages. Free 100/month.", "parameters": {"ip": "IP address"}},
    {"name": "free_vision", "description": "Analyze/describe an image via DeepAI. Free tier. Replaces mmx vision.", "parameters": {"image_url": "URL of image to analyze", "question": "What to analyze (default: describe)"}},
    {"name": "free_music", "description": "Search royalty-free music via Jamendo. CC licensed, free. For video background.", "parameters": {"query": "Music search query", "limit": "Max tracks (default: 5)", "mood": "Mood tag filter"}},
]


async def call_free_api(tool_name: str, arguments: Dict) -> Dict:
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {"error": f"Unknown free API tool: {tool_name}"}
    return await handler(arguments)
