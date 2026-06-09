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


# Each bucket: {"value": Any, "expires_at": float, "lock": asyncio.Lock,
#               "hits": int, "misses": int, "last_load_ms": float,
#               "default_ttl_sec": float, "tuned": bool}
_CACHE: Dict[str, Dict[str, Any]] = {}
# Per-key TTL overrides (admin-tuned). Survives across cache evictions
# so a re-populated key remembers its bumped TTL.
_TTL_OVERRIDES: Dict[str, float] = {}
_GLOBAL_LOCK = asyncio.Lock()


async def cached(
    key: str,
    ttl_sec: float,
    loader: Callable[[], Awaitable[Any]],
) -> Any:
    """Return a cached value for `key`, recomputing via `loader` after TTL.

    Concurrent calls during a miss are coalesced — only the first caller
    runs `loader`, the rest await the same future.

    iter D-71b — `_TTL_OVERRIDES` lets the admin sidebar's "auto-tune"
    button double a key's effective TTL without code changes. The
    override is honoured only if it's *bigger* than the caller-passed
    `ttl_sec` (so we never make caching worse than the developer asked
    for, only better).
    """
    effective_ttl = max(ttl_sec, _TTL_OVERRIDES.get(key, 0.0))
    now = time.time()
    bucket = _CACHE.get(key)
    if bucket and bucket["expires_at"] > now:
        bucket["hits"] = bucket.get("hits", 0) + 1
        return bucket["value"]

    # Get or create per-key lock under a global lock (cheap, only on miss).
    if bucket is None:
        async with _GLOBAL_LOCK:
            bucket = _CACHE.get(key)
            if bucket is None:
                bucket = {
                    "value": None, "expires_at": 0.0, "lock": asyncio.Lock(),
                    "hits": 0, "misses": 0, "last_load_ms": 0.0,
                    "default_ttl_sec": ttl_sec,
                    "tuned": key in _TTL_OVERRIDES,
                }
                _CACHE[key] = bucket
    # Remember the developer-declared TTL so the widget can show
    # "default 15s → tuned 30s" badges.
    bucket["default_ttl_sec"] = ttl_sec
    bucket["tuned"] = key in _TTL_OVERRIDES

    async with bucket["lock"]:
        # Re-check: another coro may have refreshed while we waited.
        now = time.time()
        if bucket["expires_at"] > now:
            bucket["hits"] = bucket.get("hits", 0) + 1
            return bucket["value"]
        t0 = time.time()
        value = await loader()
        bucket["last_load_ms"] = round((time.time() - t0) * 1000, 1)
        bucket["value"] = value
        bucket["expires_at"] = now + effective_ttl
        bucket["misses"] = bucket.get("misses", 0) + 1
        return value


def tune(key: str, multiplier: float = 2.0) -> Dict[str, Any]:
    """Bump a key's effective TTL by `multiplier` (default 2x).

    Used by the admin sidebar's auto-tune button when a key's hit-rate
    drops below 40% — usually means the poll interval >= the original
    TTL so the cache misses on every poll. Doubling solves it without
    a code change or redeploy.

    Returns the new effective TTL so the UI can confirm visually.
    """
    bucket = _CACHE.get(key)
    base = (bucket or {}).get("default_ttl_sec") if bucket else None
    # Anchor on the larger of (developer-declared TTL, current override).
    current = max(base or 0.0, _TTL_OVERRIDES.get(key, 0.0))
    if current <= 0:
        # Unknown key — refuse rather than guess.
        return {"ok": False, "reason": "unknown_key", "key": key}
    new_ttl = round(current * multiplier, 1)
    # Hard ceiling at 30 min — prevents accidental "1 day TTL on live data".
    new_ttl = min(new_ttl, 1800.0)
    _TTL_OVERRIDES[key] = new_ttl
    if bucket:
        bucket["tuned"] = True
        # Force-evict so the next poll picks up the new TTL immediately
        # rather than waiting for the (old) TTL to expire.
        bucket["expires_at"] = 0.0
    return {
        "ok": True,
        "key": key,
        "previous_ttl_sec": current,
        "new_ttl_sec": new_ttl,
        "multiplier": multiplier,
    }


def reset_tune(key: str) -> Dict[str, Any]:
    """Drop a tuned override, falling back to the developer-declared TTL."""
    had = _TTL_OVERRIDES.pop(key, None)
    bucket = _CACHE.get(key)
    if bucket:
        bucket["tuned"] = False
        bucket["expires_at"] = 0.0
    return {"ok": True, "key": key, "removed": had is not None, "previous_override": had}


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
    """Diagnostics — exposed via /api/admin/poll-cache/stats for ops.

    Each key reports hits / misses / hit-rate / last loader latency so the
    admin sidebar widget can highlight any endpoint with a poor hit rate
    (likely poll interval >= TTL → bump the TTL).
    """
    now = time.time()
    live = sum(1 for b in _CACHE.values() if b["expires_at"] > now)
    total_hits = sum(b.get("hits", 0) for b in _CACHE.values())
    total_misses = sum(b.get("misses", 0) for b in _CACHE.values())
    total_calls = total_hits + total_misses
    overall_hit_rate = round(total_hits / total_calls * 100, 1) if total_calls else 0.0
    keys: list = []
    for k, b in _CACHE.items():
        hits = b.get("hits", 0)
        misses = b.get("misses", 0)
        calls = hits + misses
        hit_rate = round(hits / calls * 100, 1) if calls else 0.0
        default_ttl = b.get("default_ttl_sec", 0.0)
        override = _TTL_OVERRIDES.get(k)
        effective_ttl = max(default_ttl, override or 0.0)
        keys.append({
            "key": k,
            "ttl_remaining_sec": max(0, round(b["expires_at"] - now, 1)),
            "hits": hits,
            "misses": misses,
            "calls": calls,
            "hit_rate_pct": hit_rate,
            "last_load_ms": b.get("last_load_ms", 0.0),
            "default_ttl_sec": default_ttl,
            "effective_ttl_sec": effective_ttl,
            "tuned": bool(override),
            # The widget shows the auto-tune button only when this is True.
            "tunable": calls >= 5 and hit_rate < 40.0,
        })
    # Sort by call volume desc so the heaviest endpoints float to the top
    keys.sort(key=lambda x: x["calls"], reverse=True)
    return {
        "total_keys": len(_CACHE),
        "live_keys": live,
        "expired_keys": len(_CACHE) - live,
        "total_hits": total_hits,
        "total_misses": total_misses,
        "overall_hit_rate_pct": overall_hit_rate,
        "db_ops_saved_estimate": total_hits,  # each hit = 1 avoided loader run
        "tuned_keys_count": len(_TTL_OVERRIDES),
        "keys": keys[:50],
    }
