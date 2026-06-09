"""
poll_cache — in-memory TTL cache for frontend-polled endpoints.

Why this exists
---------------
The Admin Mission Control screen polls 7 endpoints every 20s and the
Sentinel / Agent / Codebase-Health panels poll another 5 endpoints
every 15-30s. Each tab = ~1,500 Mongo reads/hour, and a single founder
session with two open tabs (mission-control + dashboard) hit ~3k/hour.
The same payload is served to every admin viewer so there is no reason
to re-aggregate per request.

This module gives a tiny dict + timestamp + TTL cache — exactly the
pattern used in `routers/pillars_health_router.py:36`. Single SSOT so
new endpoints don't reinvent the wheel.

Design notes
------------
* In-memory ONLY — the cache is wiped on every pod restart. That is by
  design: we never want a cached value to outlive a hot-fix deploy.
* Per-key (`scope`) bucketing so user-scoped data (`scope="tenant:abc"`)
  doesn't pollute the global bucket.
* `async` aware — if two requests race for the same key and the cache
  has just expired, only ONE recomputation runs; the other awaiters get
  the fresh value via an asyncio.Event.

Usage
-----
    from services.poll_cache import cached

    @router.get("/dashboard")
    async def dashboard():
        return await cached(
            key="mc:dashboard",
            ttl_sec=15,
            loader=_compute_dashboard,   # async no-arg callable
        )

For per-tenant data:
    return await cached(
        key=f"mc:dashboard:{tenant_id}",
        ttl_sec=15,
        loader=lambda: _compute_for(tenant_id),
    )
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict


# Each bucket: {"value": Any, "expires_at": float, "lock": asyncio.Lock}
_CACHE: Dict[str, Dict[str, Any]] = {}
_GLOBAL_LOCK = asyncio.Lock()


async def cached(
    key: str,
    ttl_sec: float,
    loader: Callable[[], Awaitable[Any]],
) -> Any:
    """Return a cached value for `key`, recomputing via `loader` after TTL.

    Concurrent calls during a miss are coalesced — only the first caller
    runs `loader`, the rest await the same future.
    """
    now = time.time()
    bucket = _CACHE.get(key)
    if bucket and bucket["expires_at"] > now:
        return bucket["value"]

    # Get or create per-key lock under a global lock (cheap, only on miss).
    if bucket is None:
        async with _GLOBAL_LOCK:
            bucket = _CACHE.get(key)
            if bucket is None:
                bucket = {"value": None, "expires_at": 0.0, "lock": asyncio.Lock()}
                _CACHE[key] = bucket

    async with bucket["lock"]:
        # Re-check: another coro may have refreshed while we waited.
        now = time.time()
        if bucket["expires_at"] > now:
            return bucket["value"]
        value = await loader()
        bucket["value"] = value
        bucket["expires_at"] = now + ttl_sec
        return value


def invalidate(key: str) -> None:
    """Force-evict a single key (e.g. after a write)."""
    _CACHE.pop(key, None)


def invalidate_prefix(prefix: str) -> int:
    """Force-evict all keys starting with `prefix`. Returns count cleared."""
    keys = [k for k in _CACHE if k.startswith(prefix)]
    for k in keys:
        _CACHE.pop(k, None)
    return len(keys)


def stats() -> Dict[str, Any]:
    """Diagnostics — exposed via /api/admin/poll-cache/stats for ops."""
    now = time.time()
    live = sum(1 for b in _CACHE.values() if b["expires_at"] > now)
    return {
        "total_keys": len(_CACHE),
        "live_keys": live,
        "expired_keys": len(_CACHE) - live,
        "keys": [
            {
                "key": k,
                "ttl_remaining_sec": max(0, round(b["expires_at"] - now, 1)),
            }
            for k, b in _CACHE.items()
        ][:50],
    }
