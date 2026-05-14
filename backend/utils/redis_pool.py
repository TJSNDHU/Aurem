"""
AUREM Shared Redis Pool
=======================
Single source of truth for Redis connections across the backend.

Architecture:
  ONE async ConnectionPool (max_connections=25) — every service calls
  `get_async_redis()` and gets a `Redis` client bound to the same underlying
  pool. No service should ever call `aioredis.from_url()` directly.

  Redis Cloud free tier caps at 30 clients. With 25 pooled + 1 pubsub + buffer,
  we stay comfortably under the ceiling regardless of concurrency.

Sync path:
  Same idea with `redis.ConnectionPool` shared across the single sync client.

Usage:
  from utils.redis_pool import get_async_redis, get_sync_redis, get_async_pool

  r = await get_async_redis()           # returns a Redis client (pool-bound)
  pool = get_async_pool()               # ConnectionPool for advanced uses (PubSub)

DO NOT call `.close()` / `.aclose()` on the returned clients —
the pool is shared and will be disconnected at app shutdown.
"""
import os
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════
# Async shared ConnectionPool
# ═══════════════════════════════════════

_async_pool = None
_async_client = None
# Bug-fix: previously `_async_lock = asyncio.Lock()` at module import.
# Python 3.10+ keeps loop-binding deferred for asyncio.Lock now, but the
# safer pattern (and the one that survives Windows + test event-loop
# swaps) is lazy: create on first use inside the running loop.
_async_lock: "asyncio.Lock | None" = None


def _get_async_lock() -> asyncio.Lock:
    global _async_lock
    if _async_lock is None:
        _async_lock = asyncio.Lock()
    return _async_lock


_async_init_failed = False
_async_init_failed_at = 0.0
_ASYNC_RETRY_AFTER_SEC = 60.0  # circuit-breaker window

MAX_CONNECTIONS = int(os.environ.get("REDIS_MAX_CONNECTIONS", "12"))
SYNC_MAX_CONNECTIONS = int(os.environ.get("REDIS_SYNC_MAX_CONNECTIONS", "3"))


def _build_async_pool():
    """Create the single async ConnectionPool. Caller must handle None.

    iter 281.2 hardening (Redis Cloud free tier — 30-client global cap):
      - max_connections lowered 25 → 12 (room for sync 3 + pubsub 1 + buffer)
      - socket_keepalive + retry_on_timeout for prompt stale-conn cleanup
      - timeout property so evicted pool members don't hang callers
    """
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        return None
    try:
        import redis.asyncio as aioredis
        pool = aioredis.ConnectionPool.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=MAX_CONNECTIONS,
            socket_timeout=1.5,
            socket_connect_timeout=1.5,
            socket_keepalive=True,
            health_check_interval=30,
            retry_on_timeout=True,
        )
        return pool
    except Exception as e:
        logger.warning(f"[redis_pool] Async pool build failed: {e}")
        return None


def get_async_pool():
    """
    Return the shared async ConnectionPool (or None).
    Synchronous accessor — safe to call from any context. Does NOT ping.
    Used by PubSub consumers that need the raw pool reference.
    """
    global _async_pool, _async_init_failed
    if _async_pool is not None:
        return _async_pool
    if _async_init_failed:
        return None
    pool = _build_async_pool()
    if pool is None:
        _async_init_failed = True
        return None
    _async_pool = pool
    return _async_pool


async def get_async_redis():
    """
    Return a shared async Redis client backed by the single ConnectionPool.
    First call pings to verify connectivity; subsequent calls return cached client.
    Returns None if REDIS_URL not configured or connection failed.

    iter 282al-28 — Circuit breaker: after a failed init we DO NOT retry
    for 60 s. Prevents a dead/rate-limited Redis from burning 1.5 s of
    event-loop per caller and starving the K8s health probe.
    """
    global _async_client, _async_init_failed, _async_init_failed_at

    if _async_client is not None:
        return _async_client
    if _async_init_failed:
        # Re-try once the breaker window expires
        import time as _t
        if (_t.time() - _async_init_failed_at) < _ASYNC_RETRY_AFTER_SEC:
            return None
        # Breaker window expired — reset and try again
        _async_init_failed = False

    async with _get_async_lock():
        if _async_client is not None:
            return _async_client
        if _async_init_failed:
            return None

        pool = get_async_pool()
        if pool is None:
            _async_init_failed = True
            import time as _t
            _async_init_failed_at = _t.time()
            return None

        try:
            import redis.asyncio as aioredis
            client = aioredis.Redis(connection_pool=pool)
            # Tighter ping timeout than socket default so a stuck Redis
            # cannot stall cold-boot → starve K8s liveness.
            await asyncio.wait_for(client.ping(), timeout=0.8)
            _async_client = client
            logger.info(
                f"[redis_pool] Async client bound to shared ConnectionPool "
                f"(max_connections={MAX_CONNECTIONS})"
            )
            return _async_client
        except Exception as e:
            logger.warning(f"[redis_pool] Async client init failed: {e} — "
                           f"breaker open for {_ASYNC_RETRY_AFTER_SEC}s")
            _async_init_failed = True
            import time as _t
            _async_init_failed_at = _t.time()
            return None


# ═══════════════════════════════════════
# Sync shared ConnectionPool
# ═══════════════════════════════════════

_sync_pool = None
_sync_client = None
_sync_init_failed = False


def get_sync_redis():
    """
    Return a shared sync Redis client backed by one sync ConnectionPool.
    Returns None if REDIS_URL not configured or connection failed.
    """
    global _sync_pool, _sync_client, _sync_init_failed

    if _sync_client is not None:
        return _sync_client
    if _sync_init_failed:
        return None

    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        return None

    try:
        import redis as redis_sync
        if _sync_pool is None:
            _sync_pool = redis_sync.ConnectionPool.from_url(
                redis_url,
                decode_responses=True,
                max_connections=SYNC_MAX_CONNECTIONS,
                socket_timeout=5,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30,
                retry_on_timeout=True,
            )
        client = redis_sync.Redis(connection_pool=_sync_pool)
        client.ping()
        _sync_client = client
        logger.info(f"[redis_pool] Sync client bound to shared ConnectionPool (max_connections={SYNC_MAX_CONNECTIONS})")
        return _sync_client
    except Exception as e:
        logger.warning(f"[redis_pool] Sync pool init failed: {e}")
        _sync_init_failed = True
        return None


# ═══════════════════════════════════════
# Shutdown / hot-reload
# ═══════════════════════════════════════

async def close_pools():
    """Disconnect shared Redis pools cleanly on application shutdown."""
    global _async_pool, _async_client, _sync_pool, _sync_client
    if _async_pool is not None:
        try:
            await _async_pool.disconnect()
            logger.info("[redis_pool] Async ConnectionPool disconnected")
        except Exception as e:
            logger.debug(f"[redis_pool] Async disconnect error: {e}")
        _async_pool = None
        _async_client = None

    if _sync_pool is not None:
        try:
            _sync_pool.disconnect()
            logger.info("[redis_pool] Sync ConnectionPool disconnected")
        except Exception as e:
            logger.debug(f"[redis_pool] Sync disconnect error: {e}")
        _sync_pool = None
        _sync_client = None


def reset_for_hot_reload():
    """Reset cached clients so a new REDIS_URL takes effect (admin infra hot-reload)."""
    global _async_pool, _async_client, _sync_pool, _sync_client
    global _async_init_failed, _sync_init_failed, _async_init_failed_at
    _async_pool = None
    _async_client = None
    _sync_pool = None
    _sync_client = None
    _async_init_failed = False
    _async_init_failed_at = 0.0
    _sync_init_failed = False


async def pool_stats() -> dict:
    """Return live pool stats for the /api/admin/redis-pool-stats endpoint."""
    stats = {
        "async": {"configured": False},
        "sync": {"configured": False},
        "max_connections": MAX_CONNECTIONS,
    }
    if _async_pool is not None:
        try:
            stats["async"] = {
                "configured": True,
                "in_use": getattr(_async_pool, "_in_use_connections", None),
                "available": len(getattr(_async_pool, "_available_connections", []) or []),
                "max_connections": _async_pool.max_connections,
            }
            # _in_use_connections is a set, not list
            in_use = getattr(_async_pool, "_in_use_connections", None)
            if in_use is not None:
                stats["async"]["in_use"] = len(in_use)
        except Exception as e:
            stats["async"]["error"] = str(e)
    if _sync_pool is not None:
        try:
            stats["sync"] = {
                "configured": True,
                "in_use": len(getattr(_sync_pool, "_in_use_connections", []) or []),
                "available": len(getattr(_sync_pool, "_available_connections", []) or []),
                "max_connections": _sync_pool.max_connections,
            }
        except Exception as e:
            stats["sync"]["error"] = str(e)
    return stats
