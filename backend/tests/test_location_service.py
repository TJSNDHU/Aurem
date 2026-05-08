"""Tests for services.location_service — Section 1 of growth-engine upgrade."""
import asyncio
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services import location_service as ls


def test_postal_to_city_toronto():
    assert ls._postal_to_city("M5V 2T6") == "Toronto"
    assert ls._postal_to_city("m5v") == "Toronto"
    assert ls._postal_to_city("V6B") == "Vancouver"
    assert ls._postal_to_city("H3A") == "Montreal"
    assert ls._postal_to_city("") is None
    assert ls._postal_to_city(None) is None


def test_haversine_toronto_to_vancouver():
    # Real-world distance ~3360 km
    d = ls._haversine_km(43.6532, -79.3832, 49.2827, -123.1207)
    assert 3300 < d < 3450


def test_weather_fallback_seasonal():
    out = ls._weather_fallback("Toronto")
    assert "temp_c" in out
    assert "emoji" in out
    assert out["city"] == "Toronto"


def test_resolve_location_gps_wins(monkeypatch):
    async def fake_reverse(lat, lon):
        return {"city": "Toronto", "country": "CA"}
    monkeypatch.setattr(ls, "_reverse_geocode", fake_reverse)
    out = asyncio.run(ls.resolve_location(gps_lat=43.65, gps_lon=-79.38))
    assert out["source"] == "gps"
    assert out["city"] == "Toronto"
    assert out["international"] is False


def test_resolve_location_postal_only():
    out = asyncio.run(ls.resolve_location(postal_code="M5V 2T6"))
    assert out["source"] == "postal"
    assert out["city"] == "Toronto"
    assert out["country"] == "CA"


def test_resolve_location_fallback_when_no_data():
    out = asyncio.run(ls.resolve_location())
    assert out["source"] == "fallback"
    assert out["city"] == "Canada"


def test_resolve_location_travel_flag(monkeypatch):
    async def fake_ip_lookup(ip):
        return {"city": "Calgary", "country_code": "CA",
                "latitude": 51.0447, "longitude": -114.0719}
    monkeypatch.setattr(ls, "_lookup_ip", fake_ip_lookup)
    # Toronto user, IP says Calgary (~3000km away → VPN)
    out = asyncio.run(ls.resolve_location(ip="1.2.3.4", postal_code="M5V"))
    assert out["vpn_suspected"] is True
    assert out["source"] == "postal"


def test_resolve_location_short_travel(monkeypatch):
    async def fake_ip_lookup(ip):
        # Hamilton is ~70km from Toronto → travelling
        return {"city": "Hamilton", "country_code": "CA",
                "latitude": 43.2557, "longitude": -79.8711}
    monkeypatch.setattr(ls, "_lookup_ip", fake_ip_lookup)
    out = asyncio.run(ls.resolve_location(ip="1.2.3.4", postal_code="M5V"))
    # Per spec: short travel (>50km, <500km) → use IP city, set travel_flag
    assert out["source"] == "ip"
    assert out["city"] == "Hamilton"
    assert out["travel_flag"] is True


def test_get_weather_returns_shape(monkeypatch):
    # No DB cache, no API key → must hit fallback
    monkeypatch.setattr(ls, "OWM_KEY", "")
    out = asyncio.run(ls.get_weather("Toronto"))
    assert "city" in out and "temp_c" in out and "emoji" in out
