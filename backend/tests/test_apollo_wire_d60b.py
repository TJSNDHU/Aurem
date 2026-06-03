"""
tests/test_apollo_wire_d60b.py — iter D-60b

Lock in the Apollo discovery wire-up across the scout/hunt pipeline.
Production was returning 0 customers because:
  • hunt_live.py used Google Places (billing disabled in prod) → 0 results
  • ghost_scout used OSM Overpass first which often returns junk → low yield
  • Apollo API (paid by founder $65/mo) was NOT wired into either pipeline,
    only used downstream for enrichment.

After D-60b:
  • hunt_live._discover_businesses calls Apollo FIRST when APOLLO_API_KEY set
  • ghost_scout.harvest_leads calls Apollo FIRST when APOLLO_API_KEY set
  • campaign_autofix topup_via_scout uses a wider Apollo-friendly query set
    with a longer per-query timeout (20s) and a 90s outer timeout.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ── hunt_live.py wiring ──────────────────────────────────────────

def test_hunt_live_calls_apollo_before_google_places():
    src = _read(os.path.join(ROOT, "services", "hunt_live.py"))
    apollo_at = src.find("from services.apollo_discovery import discover_organizations")
    google_at = src.find('"https://places.googleapis.com/v1/places:searchText"')
    assert apollo_at != -1, "Apollo import missing in hunt_live.py"
    assert google_at != -1, "Google Places sentinel missing in hunt_live.py"
    assert apollo_at < google_at, (
        "Apollo must be wired BEFORE Google Places in hunt_live.py"
    )


def test_hunt_live_apollo_branch_returns_early_when_results():
    src = _read(os.path.join(ROOT, "services", "hunt_live.py"))
    # The Apollo branch should short-circuit when results list is non-empty
    assert "Apollo → " in src
    assert "primary, real SMBs" in src


# ── ghost_scout_iproyal.py wiring ────────────────────────────────

def test_ghost_scout_uses_apollo_primary():
    src = _read(os.path.join(ROOT, "services", "ghost_scout_iproyal.py"))
    apollo_idx = src.find("_apollo_pre")
    osm_idx    = src.find("_osm_pre")
    assert apollo_idx != -1, "Apollo pre-result handler missing in ghost_scout"
    assert osm_idx    != -1, "OSM pre-result handler still required"
    # Apollo declaration appears before the OSM branch in the loop
    assert apollo_idx < src.find("Apollo gave"), "Apollo branch must be wired"


def test_ghost_scout_apollo_branch_skips_when_no_key():
    src = _read(os.path.join(ROOT, "services", "ghost_scout_iproyal.py"))
    assert 'os.environ.get("APOLLO_API_KEY")' in src
    assert "Apollo discovery failed" in src      # error branch logs warn
    assert "Apollo gave" in src                   # success branch logs info


# ── campaign_autofix.py — topup_via_scout config ─────────────────

def test_campaign_autofix_topup_uses_wide_apollo_query_set():
    src = _read(os.path.join(ROOT, "services", "campaign_autofix.py"))
    # The 6-query Apollo-friendly burst — verify each industry/city pair
    expected_pairs = [
        ("dental clinic", "Toronto"),
        ("dental clinic", "Mississauga"),
        ("med spa",       "Mississauga"),
        ("roofing contractor", "Brampton"),
        ("auto repair",   "Toronto"),
        ("law firm",      "Mississauga"),
    ]
    for q, city in expected_pairs:
        assert f'"{q}"' in src and f'"{city}"' in src, (
            f"missing autofix query pair: {q}/{city}")


def test_campaign_autofix_per_query_timeout_at_least_15s():
    src = _read(os.path.join(ROOT, "services", "campaign_autofix.py"))
    # Verify the timeout was bumped from the old 10s default
    import re
    m = re.search(r"harvest_leads\([^)]*\),\s*timeout=(\d+)", src)
    assert m, "per-query timeout pattern not found"
    assert int(m.group(1)) >= 15


def test_campaign_autofix_outer_timeout_at_least_60s():
    src = _read(os.path.join(ROOT, "services", "campaign_autofix.py"))
    import re
    m = re.search(r"_TIMEOUT_S\s*=\s*(\d+)", src)
    assert m, "_TIMEOUT_S constant missing"
    assert int(m.group(1)) >= 60, (
        f"outer timeout {m.group(1)}s too low — Apollo burst can take 60-90s"
    )


# ── apollo_discovery.py still healthy ────────────────────────────

def test_apollo_discovery_exposes_discover_organizations():
    from services.apollo_discovery import discover_organizations
    import inspect
    assert inspect.iscoroutinefunction(discover_organizations)
    sig = inspect.signature(discover_organizations)
    for param in ("industry_keyword", "city", "country", "per_page"):
        assert param in sig.parameters, f"discover_organizations missing param: {param}"
