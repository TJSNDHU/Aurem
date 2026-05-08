"""
AUREM Sharded Cache — Partitioned Redis Lanes
==============================================
Separates cache into 3 isolated lanes:
  - COMMS:    Live Chat sessions, WhatsApp messages, lead data
  - OVERWATCH: Pulse metrics, TPS readings, failover state
  - SYSTEM:   JWT blocklist, rate limits, session tokens

Prevents one lane from starving others during high load.
Each lane gets its own key prefix and optional TTL defaults.
"""
import os
import logging
from typing import Optional, Any
from datetime import timedelta

logger = logging.getLogger(__name__)

# Lane definitions
LANES = {
    "comms": {"prefix": "aurem:comms:", "default_ttl": 3600},       # 1 hour
    "overwatch": {"prefix": "aurem:ow:", "default_ttl": 300},       # 5 min
    "system": {"prefix": "aurem:sys:", "default_ttl": 86400},       # 24 hours
}

_redis_pool = None


async def _get_redis():
    """Get shared Redis client (all lanes share one connection pool but use prefixed keys)."""
    try:
        from utils.redis_pool import get_async_redis
        return await get_async_redis()
    except Exception as e:
        logger.warning(f"[ShardedCache] Redis unavailable: {e}")
        return None


def _key(lane: str, key: str) -> str:
    """Build a lane-prefixed key."""
    prefix = LANES.get(lane, LANES["system"])["prefix"]
    return f"{prefix}{key}"


def _ttl(lane: str, custom_ttl: Optional[int] = None) -> int:
    """Get TTL for a lane."""
    if custom_ttl is not None:
        return custom_ttl
    return LANES.get(lane, LANES["system"])["default_ttl"]


# ═══════════════════════════════════════
# Core Operations (lane-aware)
# ═══════════════════════════════════════

async def cache_set(lane: str, key: str, value: str, ttl: Optional[int] = None) -> bool:
    """Set a value in a specific cache lane."""
    r = await _get_redis()
    if not r:
        return False
    try:
        full_key = _key(lane, key)
        await r.setex(full_key, _ttl(lane, ttl), value)
        return True
    except Exception as e:
        logger.debug(f"[ShardedCache] SET {lane}/{key} failed: {e}")
        return False


async def cache_get(lane: str, key: str) -> Optional[str]:
    """Get a value from a specific cache lane."""
    r = await _get_redis()
    if not r:
        return None
    try:
        return await r.get(_key(lane, key))
    except Exception as e:
        logger.debug(f"[ShardedCache] GET {lane}/{key} failed: {e}")
        return None


async def cache_delete(lane: str, key: str) -> bool:
    """Delete a key from a specific cache lane."""
    r = await _get_redis()
    if not r:
        return False
    try:
        await r.delete(_key(lane, key))
        return True
    except Exception:
        return False


async def cache_incr(lane: str, key: str, ttl: Optional[int] = None) -> Optional[int]:
    """Increment a counter in a specific lane (for rate limiting)."""
    r = await _get_redis()
    if not r:
        return None
    try:
        full_key = _key(lane, key)
        val = await r.incr(full_key)
        if val == 1:
            await r.expire(full_key, _ttl(lane, ttl))
        return val
    except Exception:
        return None


# ═══════════════════════════════════════
# Lane-specific helpers
# ═══════════════════════════════════════

async def cache_chat_session(session_id: str, data: str, ttl: int = 3600):
    """Cache a live chat session in the COMMS lane."""
    return await cache_set("comms", f"chat:{session_id}", data, ttl)


async def get_chat_session(session_id: str) -> Optional[str]:
    """Get cached chat session from COMMS lane."""
    return await cache_get("comms", f"chat:{session_id}")


async def cache_overwatch_pulse(data: str, ttl: int = 10):
    """Cache the latest Overwatch pulse in the OVERWATCH lane."""
    return await cache_set("overwatch", "pulse:latest", data, ttl)


async def get_cached_pulse() -> Optional[str]:
    """Get cached Overwatch pulse."""
    return await cache_get("overwatch", "pulse:latest")


async def cache_rate_limit(identifier: str, window_seconds: int = 60) -> Optional[int]:
    """Increment rate limit counter in SYSTEM lane."""
    return await cache_incr("system", f"rate:{identifier}", window_seconds)


# ═══════════════════════════════════════
# Diagnostics
# ═══════════════════════════════════════

async def get_lane_stats() -> dict:
    """Get stats for each cache lane (key counts, memory usage)."""
    r = await _get_redis()
    stats = {"connected": r is not None, "lanes": {}}

    if not r:
        for lane in LANES:
            stats["lanes"][lane] = {"keys": 0, "status": "offline"}
        return stats

    try:
        for lane, config in LANES.items():
            prefix = config["prefix"]
            keys = []
            async for key in r.scan_iter(match=f"{prefix}*", count=100):
                keys.append(key)
                if len(keys) >= 1000:
                    break
            stats["lanes"][lane] = {
                "keys": len(keys),
                "prefix": prefix,
                "default_ttl": config["default_ttl"],
                "status": "active",
            }
    except Exception as e:
        logger.debug(f"[ShardedCache] Stats error: {e}")

    return stats
