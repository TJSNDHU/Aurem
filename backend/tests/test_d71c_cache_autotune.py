"""
D-71c — Auto-tune TTL button regression.

Verifies:
 1. poll_cache.tune() doubles the TTL of a registered key
 2. Effective TTL is clamped at 30min and floored at the developer default
 3. Stats output exposes `tunable`, `tuned`, `effective_ttl_sec` for the UI
 4. POST /api/admin/poll-cache/tune endpoint is wired
 5. The frontend widget renders the ⚡2× button only when `tunable=true`
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


# ─── 1. Cache module tune/reset_tune behaviour ──────────────────────

@pytest.mark.asyncio
async def test_tune_doubles_ttl_on_known_key():
    from services.poll_cache import cached, tune, invalidate, _TTL_OVERRIDES

    invalidate("test:tune:a")
    _TTL_OVERRIDES.pop("test:tune:a", None)

    async def loader():
        return 1

    # Prime the bucket with default_ttl_sec = 15.
    await cached("test:tune:a", ttl_sec=15, loader=loader)
    result = tune("test:tune:a", multiplier=2.0)
    assert result["ok"] is True
    assert result["new_ttl_sec"] == 30.0
    assert result["previous_ttl_sec"] == 15.0


@pytest.mark.asyncio
async def test_tune_refuses_unknown_keys():
    from services.poll_cache import tune
    r = tune("never:populated", multiplier=2.0)
    assert r["ok"] is False
    assert r["reason"] == "unknown_key"


@pytest.mark.asyncio
async def test_tune_is_clamped_at_30min():
    from services.poll_cache import cached, tune, invalidate, _TTL_OVERRIDES

    invalidate("test:tune:huge")
    _TTL_OVERRIDES.pop("test:tune:huge", None)
    async def loader():
        return 1
    await cached("test:tune:huge", ttl_sec=1000, loader=loader)
    # 1000 × 10 = 10,000 should be clamped to 1800 (30 min).
    r = tune("test:tune:huge", multiplier=10.0)
    assert r["new_ttl_sec"] == 1800.0


@pytest.mark.asyncio
async def test_tune_take_effect_on_next_call():
    from services.poll_cache import cached, tune, invalidate, _TTL_OVERRIDES

    invalidate("test:tune:effect")
    _TTL_OVERRIDES.pop("test:tune:effect", None)
    calls = []
    async def loader():
        calls.append(1)
        return len(calls)

    # TTL=0.05 → expires immediately, every call would miss.
    await cached("test:tune:effect", ttl_sec=0.05, loader=loader)
    # Without tune: 0.05s TTL, so a 0.2s sleep wipes it.
    await asyncio.sleep(0.2)
    await cached("test:tune:effect", ttl_sec=0.05, loader=loader)
    misses_without_tune = len(calls)
    assert misses_without_tune == 2

    # Now tune 100× → 5s TTL. Two quick subsequent calls = 1 miss + 1 hit.
    tune("test:tune:effect", multiplier=100.0)
    await cached("test:tune:effect", ttl_sec=0.05, loader=loader)  # miss
    await cached("test:tune:effect", ttl_sec=0.05, loader=loader)  # hit (cache survives)
    assert len(calls) == 3  # only ONE additional miss after tune


@pytest.mark.asyncio
async def test_stats_exposes_tunable_and_tuned_flags():
    from services.poll_cache import cached, invalidate, stats, _TTL_OVERRIDES

    invalidate("test:flags")
    _TTL_OVERRIDES.pop("test:flags", None)

    async def loader():
        return 1
    # Force a 0% hit-rate to satisfy the tunable condition (calls >= 5, hit_rate < 40).
    for _ in range(6):
        await cached("test:flags", ttl_sec=0.001, loader=loader)
        await asyncio.sleep(0.01)

    s = stats()
    row = next(k for k in s["keys"] if k["key"] == "test:flags")
    assert row["tunable"] is True, f"hit_rate={row['hit_rate_pct']}, calls={row['calls']}"
    assert row["tuned"] is False
    assert row["default_ttl_sec"] == 0.001
    assert row["effective_ttl_sec"] == 0.001


@pytest.mark.asyncio
async def test_reset_tune_clears_override():
    from services.poll_cache import cached, tune, reset_tune, _TTL_OVERRIDES

    async def loader():
        return 1
    await cached("test:reset", ttl_sec=10, loader=loader)
    tune("test:reset", multiplier=2.0)
    assert "test:reset" in _TTL_OVERRIDES
    r = reset_tune("test:reset")
    assert r["ok"] is True
    assert r["removed"] is True
    assert "test:reset" not in _TTL_OVERRIDES


# ─── 2. Endpoint wiring ─────────────────────────────────────────────

def test_tune_endpoint_is_registered():
    src = Path("/app/backend/routers/poll_cache_stats_router.py").read_text()
    assert '@router.post("/tune")' in src
    assert "TuneBody" in src
    assert "multiplier" in src


def test_tune_endpoint_clamps_multiplier_input():
    src = Path("/app/backend/routers/poll_cache_stats_router.py").read_text()
    # The 1.1 floor + 10 ceiling guards against fat-finger / abuse.
    assert "max(1.1" in src and "min(10.0" in src


# ─── 3. Frontend widget — ⚡2× button only when tunable ────────────

def test_widget_has_autotune_button_for_tunable_rows_only():
    src = Path("/app/frontend/src/platform/CacheHitRateWidget.jsx").read_text()
    assert "autoTune" in src, "autoTune handler missing"
    assert "k.tunable" in src, "Widget must read backend `tunable` flag"
    assert "⚡2" in src or "2×" in src or "2x" in src, "Visible auto-tune affordance missing"
    assert "/api/admin/poll-cache/tune" in src
    # Confirmation message after tune lands
    assert "TTL" in src and "→" in src


def test_widget_skips_tune_button_when_already_tuned():
    src = Path("/app/frontend/src/platform/CacheHitRateWidget.jsx").read_text()
    # The button must hide when `tuned=true` to prevent infinite doubling
    assert "!k.tuned" in src
