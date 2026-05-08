"""
AUREM TTL Cache — In-memory with optional Redis backend.
Used for Scout search results, API response caching, etc.
"""

import time
import hashlib
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_cache: dict = {}
_redis_client = None


def _init_redis():
    """Return the shared sync Redis client from the global pool."""
    global _redis_client
    if _redis_client is not None and _redis_client is not False:
        return _redis_client
    if _redis_client is False:
        return None
    try:
        from utils.redis_pool import get_sync_redis
        client = get_sync_redis()
        if client is not None:
            _redis_client = client
            logger.info("[TTL Cache] Using shared Redis pool")
            return client
        _redis_client = False
        return None
    except Exception as e:
        logger.warning(f"[TTL Cache] Shared pool unavailable, using in-memory: {e}")
        _redis_client = False
        return None


def _make_key(prefix: str, data: Any) -> str:
    """Create a deterministic cache key from arbitrary data"""
    raw = json.dumps(data, sort_keys=True, default=str)
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"aurem:{prefix}:{h}"


async def cache_get(prefix: str, key_data: Any) -> Optional[Any]:
    """Get from cache (Redis first, then in-memory)"""
    key = _make_key(prefix, key_data)

    # Try Redis
    r = _init_redis()
    if r and r is not False:
        try:
            val = r.get(key)
            if val:
                return json.loads(val)
        except Exception:
            pass

    # In-memory fallback
    entry = _cache.get(key)
    if entry and entry["expires"] > time.time():
        return entry["data"]
    elif entry:
        del _cache[key]  # Expired — clean up

    return None


async def cache_set(prefix: str, key_data: Any, value: Any, ttl: int = 3600):
    """Set in cache with TTL (Redis + in-memory)"""
    key = _make_key(prefix, key_data)
    serialized = json.dumps(value, default=str)

    # Redis
    r = _init_redis()
    if r and r is not False:
        try:
            r.setex(key, ttl, serialized)
        except Exception:
            pass

    # In-memory (always, as backup)
    _cache[key] = {
        "data": value,
        "expires": time.time() + ttl,
    }

    # Evict old entries if cache grows too large (max 500 entries)
    if len(_cache) > 500:
        now = time.time()
        expired_keys = [k for k, v in _cache.items() if v["expires"] < now]
        for k in expired_keys:
            del _cache[k]


async def cache_invalidate(prefix: str, key_data: Any):
    """Remove a specific cache entry"""
    key = _make_key(prefix, key_data)

    r = _init_redis()
    if r and r is not False:
        try:
            r.delete(key)
        except Exception:
            pass

    _cache.pop(key, None)


def cache_invalidate_by_domain(domain: str) -> int:
    """Bulk-invalidate all cache entries whose key contains the domain string.
    Clears both in-memory and Redis (via SCAN pattern match).
    Returns the number of keys removed."""
    removed = 0

    # In-memory
    keys_to_remove = [k for k in _cache if domain in k]
    for k in keys_to_remove:
        del _cache[k]
    removed += len(keys_to_remove)

    # Redis
    r = _init_redis()
    if r and r is not False:
        try:
            cursor = 0
            while True:
                cursor, keys = r.scan(cursor, match=f"aurem:*{domain}*", count=100)
                if keys:
                    r.delete(*keys)
                    removed += len(keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.warning(f"[TTL Cache] Redis domain invalidation failed: {e}")

    if removed:
        logger.info(f"[TTL Cache] Cleared {removed} entries for domain '{domain}'")
    return removed


def cache_stats() -> dict:
    """Return cache statistics"""
    now = time.time()
    valid = sum(1 for v in _cache.values() if v["expires"] > now)
    r = _init_redis()
    return {
        "in_memory_entries": len(_cache),
        "in_memory_valid": valid,
        "redis_connected": bool(r and r is not False),
    }
