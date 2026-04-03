"""
cache_routes.py
═══════════════════════════════════════════════════════════════════
Admin endpoints for Redis cache monitoring and management.

Endpoints:
  GET  /api/admin/cache/status       - Get cache stats and key inventory
  POST /api/admin/cache/flush        - Flush all cache keys
  POST /api/admin/cache/flush/{key}  - Flush a specific key
  POST /api/admin/cache/warm         - Trigger cache warming

Register in server.py:
  from routes.cache_routes import cache_router
  app.include_router(cache_router)
═══════════════════════════════════════════════════════════════════
"""

import os
import time
import logging
from fastapi import APIRouter, Request
from typing import Optional

logger = logging.getLogger("reroots.cache")

cache_router = APIRouter(prefix="/api/admin/cache", tags=["cache"])

# These will be injected from server.py
_cache_manager = None
_db = None
_warm_cache_func = None


def init_cache_routes(cache_manager, db, warm_cache_on_startup):
    """Initialize cache routes with dependencies from server.py"""
    global _cache_manager, _db, _warm_cache_func
    _cache_manager = cache_manager
    _db = db
    _warm_cache_func = warm_cache_on_startup
    logger.info("Cache routes initialized")


@cache_router.get("/status")
async def cache_status(request: Request):
    """Get comprehensive Redis cache statistics."""
    if not _cache_manager or not _cache_manager.available:
        return {
            "connected": False,
            "message": "Redis not connected - check REDIS_URL in .env"
        }
    
    try:
        r = _cache_manager._redis
        
        # Get Redis server info
        info = await r.info()
        
        # Get all keys with TTL and size
        keys_raw = await r.keys("*")
        key_data = []
        
        for k in keys_raw[:100]:  # Cap at 100 keys for performance
            try:
                ttl = await r.ttl(k)
                typ = await r.type(k)
                
                # Get memory usage (may not be available on all Redis versions)
                try:
                    size = await r.memory_usage(k) or 0
                except:
                    size = 0
                
                key_data.append({
                    "key": k,
                    "ttl": ttl,
                    "size_bytes": size,
                    "type": typ,
                })
            except Exception as e:
                logger.warning(f"Error getting key info for {k}: {e}")
        
        # Sort by key name
        key_data.sort(key=lambda x: x["key"])
        
        # Get last warm metadata
        last_warmed = await r.get("_meta:last_warmed") or ""
        warming_ms = await r.get("_meta:warming_ms") or "0"
        
        # Parse Redis host from URL (safe, no password)
        redis_url = os.getenv("REDIS_URL", "")
        redis_host = redis_url.split("@")[-1] if "@" in redis_url else "localhost:6379"
        
        return {
            "connected": True,
            "redis_host": redis_host,
            "uptime_seconds": info.get("uptime_in_seconds", 0),
            "memory_used_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2),
            "memory_peak_mb": round(info.get("used_memory_peak", 0) / 1024 / 1024, 2),
            "memory_max_mb": 30,  # Redis Cloud free tier limit
            "hit_count": info.get("keyspace_hits", 0),
            "miss_count": info.get("keyspace_misses", 0),
            "total_commands": info.get("total_commands_processed", 0),
            "keys": key_data,
            "last_warmed": last_warmed or time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "warming_ms": int(warming_ms) if warming_ms else 0,
        }
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        return {
            "connected": True,
            "error": str(e),
            "keys": []
        }


@cache_router.post("/flush")
async def flush_all(request: Request):
    """Flush all cache keys (dangerous - use with caution)."""
    if not _cache_manager or not _cache_manager.available:
        return {"success": False, "message": "Redis not connected"}
    
    try:
        r = _cache_manager._redis
        
        # Get count before flush
        keys = await r.keys("*")
        count = len(keys)
        
        # Flush the database
        await r.flushdb()
        
        logger.info(f"Flushed all {count} cache keys")
        return {
            "success": True,
            "message": f"Flushed {count} keys",
            "flushed_count": count
        }
    except Exception as e:
        logger.error(f"Error flushing cache: {e}")
        return {"success": False, "message": str(e)}


@cache_router.post("/flush/{key:path}")
async def flush_key(key: str, request: Request):
    """Flush a specific cache key."""
    if not _cache_manager or not _cache_manager.available:
        return {"success": False, "message": "Redis not connected"}
    
    try:
        r = _cache_manager._redis
        deleted = await r.delete(key)
        
        logger.info(f"Flushed cache key: {key} (deleted={deleted})")
        return {
            "success": True,
            "deleted": deleted,
            "key": key
        }
    except Exception as e:
        logger.error(f"Error flushing key {key}: {e}")
        return {"success": False, "message": str(e)}


@cache_router.post("/warm")
async def warm_now(request: Request):
    """Trigger immediate cache warming."""
    if not _cache_manager or not _cache_manager.available:
        return {"success": False, "message": "Redis not connected"}
    
    if _warm_cache_func is None or _db is None:
        return {"success": False, "message": "Warm function not initialized"}
    
    try:
        t0 = time.time()
        await _warm_cache_func(_cache_manager, _db)
        ms = int((time.time() - t0) * 1000)
        
        # Store meta for status panel
        r = _cache_manager._redis
        await r.set("_meta:last_warmed", time.strftime("%Y-%m-%dT%H:%M:%SZ"), ex=86400)
        await r.set("_meta:warming_ms", str(ms), ex=86400)
        
        logger.info(f"Cache warmed successfully in {ms}ms")
        return {
            "success": True,
            "warming_ms": ms,
            "message": f"Cache warmed in {ms}ms"
        }
    except Exception as e:
        logger.error(f"Error warming cache: {e}")
        return {"success": False, "message": str(e)}
