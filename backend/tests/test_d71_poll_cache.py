"""
D-71 perf — verify the in-memory poll cache wraps the hot polling endpoints
and that concurrent calls coalesce (single DB hit, multiple receivers).
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest


# ─── 1. The cache module itself ───────────────────────────────────────

@pytest.mark.asyncio
async def test_cached_returns_same_value_within_ttl():
    from services.poll_cache import cached, invalidate

    invalidate("test:basic")
    calls = []

    async def loader():
        calls.append(1)
        return {"n": len(calls)}

    a = await cached("test:basic", ttl_sec=5, loader=loader)
    b = await cached("test:basic", ttl_sec=5, loader=loader)
    assert a == b == {"n": 1}
    assert len(calls) == 1  # second call hit the cache


@pytest.mark.asyncio
async def test_cached_recomputes_after_ttl():
    from services.poll_cache import cached, invalidate

    invalidate("test:ttl")
    calls = []

    async def loader():
        calls.append(1)
        return len(calls)

    v1 = await cached("test:ttl", ttl_sec=0.1, loader=loader)
    await asyncio.sleep(0.2)
    v2 = await cached("test:ttl", ttl_sec=0.1, loader=loader)
    assert v1 == 1
    assert v2 == 2


@pytest.mark.asyncio
async def test_concurrent_misses_coalesce_to_single_loader_call():
    """The whole point of the cache: 5 concurrent miss-callers must NOT
    fire 5 Mongo queries. Only ONE loader runs, the rest await it."""
    from services.poll_cache import cached, invalidate

    invalidate("test:race")
    call_count = 0

    async def slow_loader():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)  # simulate DB latency
        return call_count

    results = await asyncio.gather(*(
        cached("test:race", ttl_sec=5, loader=slow_loader) for _ in range(5)
    ))
    assert call_count == 1, f"Expected coalesce → 1 call, got {call_count}"
    assert results == [1, 1, 1, 1, 1]


@pytest.mark.asyncio
async def test_invalidate_prefix_clears_namespace():
    from services.poll_cache import cached, invalidate_prefix

    async def loader():
        return "x"

    await cached("ns:a", ttl_sec=60, loader=loader)
    await cached("ns:b", ttl_sec=60, loader=loader)
    await cached("other:c", ttl_sec=60, loader=loader)

    removed = invalidate_prefix("ns:")
    assert removed == 2


# ─── 2. Endpoint wiring — static source assertions ────────────────────

def _src(p):
    return Path(p).read_text()


def test_mission_control_dashboard_is_cached():
    s = _src("/app/backend/routers/admin_mission_control_router.py")
    assert "_poll_cached" in s
    assert 'key="mc:dashboard"' in s


def test_mission_control_overview_is_cached():
    s = _src("/app/backend/routers/admin_mission_control_router.py")
    assert 'key="mc:overview"' in s


def test_mission_control_services_and_api_keys_are_cached():
    s = _src("/app/backend/routers/admin_mission_control_router.py")
    assert 'key="mc:services"' in s
    assert 'key="mc:api-keys"' in s


def test_agents_status_is_cached():
    s = _src("/app/backend/routers/aurem_routes.py")
    assert 'key="aurem:agents:status"' in s


def test_codebase_health_latest_is_cached():
    s = _src("/app/backend/routers/codebase_health_router.py")
    assert 'key="codebase:health:latest"' in s


def test_autonomous_overview_is_cached():
    s = _src("/app/backend/routers/autonomous_stack_router.py")
    assert 'key="autonomous:overview"' in s


def test_sentinel_overview_is_cached():
    s = _src("/app/backend/routers/sentinel_client_router.py")
    assert 'key="sentinel:overview"' in s


def test_dogfood_pulse_is_cached():
    s = _src("/app/backend/routers/dogfood_pulse_router.py")
    assert 'key="dogfood:pulse"' in s


def test_poll_cache_stats_router_registered():
    s = _src("/app/backend/routers/registry.py")
    assert "poll_cache_stats_router" in s
