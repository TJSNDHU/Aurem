"""
Step 2 of P0 mock purge — proximity_blast.py must:
  • Have NO fake-name lists (FIRST_NAMES, BUSINESS_TYPES, etc.)
  • Call Apollo for real lead discovery
  • Reverse-geocode lat/lng → city
  • Enforce a 100/hour Apollo rate limit
  • Return [] (not fake data) on Apollo failure
  • Default `data_source: "apollo"` (not `"simulated"`)
"""
from __future__ import annotations

import asyncio
import importlib
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _reload():
    for m in ("services.proximity_blast", "services.apollo_discovery"):
        if m in sys.modules:
            del sys.modules[m]
    return importlib.import_module("services.proximity_blast")


# ── Source invariants ─────────────────────────────────────────────

def test_no_fake_name_lists():
    src = _read(os.path.join(ROOT, "services", "proximity_blast.py"))
    for token in ("FIRST_NAMES", "LAST_NAMES", "BUSINESS_TYPES",
                    "STREET_NAMES", "_random_point_in_radius"):
        assert token not in src, f"forbidden fake-data token: {token}"


def test_imports_apollo_discovery():
    src = _read(os.path.join(ROOT, "services", "proximity_blast.py"))
    assert "from services.apollo_discovery import discover_organizations" in src


def test_default_data_source_is_apollo():
    src = _read(os.path.join(ROOT, "services", "proximity_blast.py"))
    assert '"data_source":          "apollo"' in src
    assert '"data_source": "simulated"' not in src


def test_rate_limit_constant_present():
    src = _read(os.path.join(ROOT, "services", "proximity_blast.py"))
    assert "_APOLLO_RATE_LIMIT_PER_HOUR = 100" in src
    assert "apollo_rate_limit_pause" in src


# ── Runtime behaviour ─────────────────────────────────────────────

def test_returns_empty_when_apollo_key_missing(monkeypatch):
    monkeypatch.delenv("APOLLO_API_KEY", raising=False)
    pb = _reload()
    out = asyncio.run(pb.discover_real_leads_via_apollo(
        43.6532, -79.3832, 10, count=5,
    ))
    assert out == []


def test_returns_empty_when_geocode_fails(monkeypatch):
    monkeypatch.setenv("APOLLO_API_KEY", "fake_for_test")
    pb = _reload()
    async def _no_city(lat, lng): return "", ""
    monkeypatch.setattr(pb, "_city_from_latlng", _no_city)
    out = asyncio.run(pb.discover_real_leads_via_apollo(
        43.6532, -79.3832, 10, count=5,
    ))
    assert out == []


def test_returns_real_leads_when_apollo_succeeds(monkeypatch):
    monkeypatch.setenv("APOLLO_API_KEY", "fake_for_test")
    pb = _reload()
    async def _fake_city(lat, lng): return "Mississauga", "CA"
    monkeypatch.setattr(pb, "_city_from_latlng", _fake_city)
    # Replace the real Apollo call with a stub returning 3 fake orgs
    async def _fake_apollo(*, industry_keyword, city, country, per_page):
        assert city == "Mississauga"
        assert country == "Canada"
        return [
            {"business_name": f"Real Biz {i}",
              "phone": f"+1416555010{i}",
              "city": "Mississauga",
              "province": "Ontario",
              "website": f"https://biz{i}.ca",
              "industry": "dental",
              "employees": 12 + i,
              "domain": f"biz{i}.ca",
              "linkedin_url": ""}
            for i in range(3)
        ]
    import services.apollo_discovery
    monkeypatch.setattr(
        services.apollo_discovery, "discover_organizations", _fake_apollo,
    )
    out = asyncio.run(pb.discover_real_leads_via_apollo(
        43.6532, -79.3832, 10, count=3, industry_hint="dental",
    ))
    assert len(out) == 3
    assert out[0]["business_name"] == "Real Biz 0"
    assert out[0]["phone"] == "+14165550100"
    assert out[0]["source"] == "apollo_discovery"
    assert out[0]["address"] == "Mississauga, Ontario"
    # Never simulate decimals
    assert out[0]["distance_km"] is None
    assert out[0]["rating"] is None


def test_rate_limit_blocks_after_100_calls(monkeypatch):
    monkeypatch.setenv("APOLLO_API_KEY", "fake_for_test")
    pb = _reload()
    # Pre-populate the call log with 100 fresh timestamps
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).timestamp()
    for _ in range(100):
        pb._apollo_call_log.append(now - 1)
    with pytest.raises(RuntimeError, match="apollo_rate_limit_pause"):
        pb._check_apollo_rate_limit()


def test_rate_limit_resets_after_one_hour(monkeypatch):
    monkeypatch.setenv("APOLLO_API_KEY", "fake_for_test")
    pb = _reload()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).timestamp()
    # Old (>1h) timestamps don't count
    for _ in range(150):
        pb._apollo_call_log.append(now - 4000)
    # Should not raise — the old entries get pruned
    pb._check_apollo_rate_limit()
    assert len(pb._apollo_call_log) == 1


def test_run_blast_uses_apollo_path(monkeypatch):
    monkeypatch.setenv("APOLLO_API_KEY", "fake_for_test")
    pb = _reload()
    async def _fake_disc(*a, **kw):
        return [{"business_name": "X", "lead_id": "X1"}]
    monkeypatch.setattr(pb, "discover_real_leads_via_apollo", _fake_disc)
    monkeypatch.setattr(pb, "_get_db", lambda: None)
    out = asyncio.run(pb.run_blast(
        "tenant_x", 43.6532, -79.3832, 10, count=1,
    ))
    assert out["source"] == "apollo"
    assert out["leads"] == [{"business_name": "X", "lead_id": "X1"}]


def test_legacy_alias_removed():
    """After Step 3, the temporary alias must be deleted — callers
    must use `discover_real_leads_via_apollo` directly."""
    src = _read(os.path.join(ROOT, "services", "proximity_blast.py"))
    assert "async def generate_simulated_leads" not in src
    assert "DEPRECATED" not in src
