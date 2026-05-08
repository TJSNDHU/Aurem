"""
AUREM Lead Enrichment Helpers (Phase 4)
========================================
Given a phone + IP, enrich a lead with:
  - NumVerify: phone validity, carrier, country, line type
  - IPStack: geolocation, ISP, timezone

CASL-safe: these helpers DO NOT send any SMS. They enrich only.
The caller must verify `consent_sms` before firing Twilio.
"""
from __future__ import annotations

import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

NUMVERIFY_KEY = os.environ.get("NUMVERIFY_API_KEY", "")
IPSTACK_KEY = os.environ.get("IPSTACK_API_KEY", "")


async def enrich_phone(phone: str) -> dict:
    """NumVerify: validate a phone. Returns dict or {} on failure."""
    if not (NUMVERIFY_KEY and phone):
        return {}
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                "http://apilayer.net/api/validate",
                params={"access_key": NUMVERIFY_KEY, "number": phone, "format": 1},
            )
            d = r.json()
            return {
                "phone_valid": bool(d.get("valid")),
                "phone_country": d.get("country_code"),
                "phone_carrier": d.get("carrier"),
                "phone_line_type": d.get("line_type"),
                "phone_location": d.get("location"),
                "phone_international": d.get("international_format"),
            }
    except Exception as e:
        logger.warning(f"[enrich] numverify: {e}")
        return {}


async def enrich_ip(ip: str) -> dict:
    """IPStack: geolocate a lead's IP. Returns dict or {} on failure."""
    if not (IPSTACK_KEY and ip and ip not in ("127.0.0.1", "localhost")):
        return {}
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(
                f"http://api.ipstack.com/{ip}",
                params={"access_key": IPSTACK_KEY, "fields": "main,location"},
            )
            d = r.json()
            return {
                "ip_country": d.get("country_code"),
                "ip_region": d.get("region_name"),
                "ip_city": d.get("city"),
                "ip_zip": d.get("zip"),
                "ip_lat": d.get("latitude"),
                "ip_lon": d.get("longitude"),
                "ip_timezone": (d.get("time_zone") or {}).get("id"),
            }
    except Exception as e:
        logger.warning(f"[enrich] ipstack: {e}")
        return {}


async def enrich_lead(phone: Optional[str], ip: Optional[str]) -> dict:
    """Run both enrichments. Safe for missing inputs."""
    out: dict = {}
    if phone:
        out.update(await enrich_phone(phone))
    if ip:
        out.update(await enrich_ip(ip))
    return out


def is_local_lead(enriched: dict, target_region: Optional[str] = None) -> bool:
    """
    Determine if a lead is 'local' relative to a target region.
    Example: target_region='Ontario' → matches ip_region containing 'Ontario'
    Default rule: if both phone and IP country match each other.
    """
    phone_c = (enriched.get("phone_country") or "").upper()
    ip_c = (enriched.get("ip_country") or "").upper()
    if target_region:
        region = (enriched.get("ip_region") or "").lower()
        return target_region.lower() in region
    return bool(phone_c and ip_c and phone_c == ip_c)


def casl_compliant(consent_sms: bool, consent_email: bool, channel: str) -> tuple[bool, str]:
    """
    Check CASL compliance before firing a channel.
    Returns (allowed: bool, reason: str)
    """
    channel = channel.lower()
    if channel in ("sms", "voice"):
        if not consent_sms:
            return False, "SMS/voice consent not given (CASL violation)"
    if channel == "email":
        if not consent_email:
            return False, "Email consent not given (CASL violation)"
    return True, "ok"
