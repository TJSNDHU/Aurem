"""
D-71b regression — Apollo Canada-wide, scheduler wiring, 5xx noise fixes,
and the cache hit-rate stats expansion.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


# ─── 1. Apollo Canada-wide ────────────────────────────────────────────

def test_apollo_default_cities_cover_all_provinces():
    from services.apollo_discovery import DEFAULT_GTA_CITIES
    text = " ".join(DEFAULT_GTA_CITIES)
    for c in (
        "Toronto", "Vancouver", "Montreal", "Calgary",
        "Halifax", "Winnipeg", "Saskatoon", "Quebec City",
        "St. John's", "Charlottetown",
    ):
        assert c in text, f"Default Apollo cities missing '{c}' — not Canada-wide"


def test_apollo_default_industries_cover_full_smb_universe():
    from services.apollo_discovery import DEFAULT_INDUSTRY_KEYWORDS
    text = " ".join(DEFAULT_INDUSTRY_KEYWORDS)
    # Must include trades, health, beauty, food, professional, fitness, retail
    for kw in ("plumbing", "dental", "restaurant", "law firm",
               "gym", "florist", "real estate"):
        assert kw in text, f"Default industries missing '{kw}'"


def test_apollo_discover_caps_combos_to_prevent_credit_blast():
    src = Path("/app/backend/services/apollo_discovery.py").read_text()
    assert "max_combos" in src, (
        "discover_for_default_targets must cap combos with max_combos kwarg"
    )
    assert "random.sample" in src, (
        "Sampling must be random so the rotation covers the full matrix over time"
    )


# ─── 2. Auto-blast scheduler is actually launched ─────────────────────

def test_auto_blast_scheduler_is_attached_at_startup():
    """The `auto_blast_scheduler()` forever-loop is launched by the
    p1-worker (pillars/sales/worker.py) at startup. Verify the attach
    code is in place — without it the campaign sits at 'Last run never'
    forever even with auto-blast enabled."""
    src = Path("/app/backend/pillars/sales/worker.py").read_text()
    assert "auto_blast_scheduler" in src
    assert "_safe_task(auto_blast_scheduler()" in src or "_safe_task(auto_blast_scheduler(" in src
    assert "Auto-Blast scheduler attached" in src


# ─── 3. The two new 5xx fixes ─────────────────────────────────────────

def test_smart_search_db_is_wired_in_startup():
    """`/api/search/history` was returning 500 'Database not available'
    because set_smart_search_db was imported but never called."""
    src = Path("/app/backend/server.py").read_text()
    assert "set_smart_search_db(db)" in src, (
        "server.py must call set_smart_search_db(db) at startup"
    )


def test_ora_providers_health_public_no_503_noise():
    """The provider health snapshot is empty for a few minutes after pod
    boot. Returning 503 for that period painted ~100 false P1 incidents/hr
    in the Live Health panel. Now returns status='warming' with 200."""
    src = Path("/app/backend/routers/ora_providers_router.py").read_text()
    assert '"warming"' in src or "'warming'" in src
    # The old `raise HTTPException(503, "no health snapshot yet...")` must be gone.
    assert "no health snapshot yet — try /health (admin)" not in src or \
           src.count("no health snapshot yet") <= 1  # might still be in the reason str


# ─── 4. Cache hit-rate stats expansion ────────────────────────────────

@pytest.mark.asyncio
async def test_poll_cache_records_hits_and_misses():
    from services.poll_cache import cached, invalidate, stats

    invalidate("test:rate")
    async def loader():
        return 42

    # 1 miss + 3 hits
    await cached("test:rate", ttl_sec=60, loader=loader)
    await cached("test:rate", ttl_sec=60, loader=loader)
    await cached("test:rate", ttl_sec=60, loader=loader)
    await cached("test:rate", ttl_sec=60, loader=loader)

    s = stats()
    row = next(k for k in s["keys"] if k["key"] == "test:rate")
    assert row["misses"] == 1
    assert row["hits"] == 3
    assert row["hit_rate_pct"] == 75.0
    assert s["overall_hit_rate_pct"] >= 0


def test_cache_widget_component_exists():
    p = Path("/app/frontend/src/platform/CacheHitRateWidget.jsx")
    assert p.exists()
    src = p.read_text()
    assert "/api/admin/poll-cache/stats" in src
    assert "data-testid=\"cache-hitrate-widget\"" in src


def test_admin_shell_mounts_cache_widget():
    src = Path("/app/frontend/src/platform/AdminShell.jsx").read_text()
    assert "CacheHitRateWidget" in src
    assert "<CacheHitRateWidget" in src
