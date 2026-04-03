"""
Performance Patch Module for AUREM Platform
Rate limiting and caching utilities
"""

import os
import time
import logging
import hashlib
from typing import Dict, Any, Optional, Callable
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# RATE LIMITER (SlowAPI-compatible)
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    
    limiter = Limiter(key_func=get_remote_address)
except ImportError:
    # Fallback if slowapi not installed
    class DummyLimiter:
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
        
        def shared_limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    
    limiter = DummyLimiter()
    logger.warning("slowapi not installed - rate limiting disabled")


def setup_rate_limiter(app):
    """Setup rate limiter on FastAPI app"""
    try:
        from slowapi import _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        logger.info("✓ Rate limiter configured")
    except ImportError:
        logger.warning("slowapi not available - skipping rate limiter setup")
    except Exception as e:
        logger.warning(f"Rate limiter setup failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# CACHE MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class CacheManager:
    """
    In-memory cache with TTL support.
    Optionally backed by Redis for multi-instance deployments.
    """
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._redis = None
        self._redis_connected = False
        
        # Default TTLs
        self.TTL_SHORT = 60       # 1 minute
        self.TTL_MEDIUM = 300     # 5 minutes
        self.TTL_LONG = 3600      # 1 hour
        self.TTL_DAY = 86400      # 24 hours
    
    async def connect_redis(self):
        """Connect to Redis if available"""
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            logger.info("REDIS_URL not set - using in-memory cache only")
            return False
        
        try:
            import redis.asyncio as aioredis
            self._redis = await aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=2,
                socket_connect_timeout=2,
            )
            await self._redis.ping()
            self._redis_connected = True
            logger.info("✓ CacheManager connected to Redis")
            return True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e} - using in-memory cache")
            self._redis_connected = False
            return False
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from prefix and arguments"""
        key_data = f"{prefix}:{':'.join(str(a) for a in args)}"
        if kwargs:
            key_data += f":{hashlib.md5(str(sorted(kwargs.items())).encode()).hexdigest()[:8]}"
        return key_data
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        # Try Redis first
        if self._redis_connected:
            try:
                import json
                value = await self._redis.get(f"cache:{key}")
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.debug(f"Redis get failed: {e}")
        
        # Fall back to memory
        if key in self._cache:
            item = self._cache[key]
            if item["expires_at"] > time.time():
                return item["value"]
            else:
                del self._cache[key]
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = None):
        """Set value in cache with TTL"""
        ttl = ttl or self.TTL_MEDIUM
        
        # Try Redis first
        if self._redis_connected:
            try:
                import json
                await self._redis.setex(f"cache:{key}", ttl, json.dumps(value, default=str))
            except Exception as e:
                logger.debug(f"Redis set failed: {e}")
        
        # Always store in memory as fallback
        self._cache[key] = {
            "value": value,
            "expires_at": time.time() + ttl
        }
    
    async def delete(self, key: str):
        """Delete from cache"""
        if self._redis_connected:
            try:
                await self._redis.delete(f"cache:{key}")
            except Exception:
                pass
        
        self._cache.pop(key, None)
    
    async def clear_prefix(self, prefix: str):
        """Clear all cache keys with a prefix"""
        # Clear from Redis
        if self._redis_connected:
            try:
                keys = await self._redis.keys(f"cache:{prefix}:*")
                if keys:
                    await self._redis.delete(*keys)
            except Exception:
                pass
        
        # Clear from memory
        keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._cache[k]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        # Clean expired entries
        current_time = time.time()
        expired = [k for k, v in self._cache.items() if v["expires_at"] <= current_time]
        for k in expired:
            del self._cache[k]
        
        return {
            "backend": "redis" if self._redis_connected else "memory",
            "memory_entries": len(self._cache),
            "redis_connected": self._redis_connected
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CACHE WARMING
# ═══════════════════════════════════════════════════════════════════════════════

async def warm_cache_on_startup(cache_manager: CacheManager, db):
    """
    Pre-populate cache with frequently accessed data on startup.
    This reduces cold-start latency for common queries.
    """
    try:
        logger.info("[Cache Warm] Starting cache warm-up...")
        
        # Try to connect to Redis
        await cache_manager.connect_redis()
        
        # Cache store settings
        try:
            store_settings = await db.store_settings.find_one({}, {"_id": 0})
            if store_settings:
                await cache_manager.set("store_settings", store_settings, cache_manager.TTL_LONG)
                logger.info("[Cache Warm] ✓ Store settings cached")
        except Exception as e:
            logger.debug(f"[Cache Warm] Store settings: {e}")
        
        # Cache product count
        try:
            product_count = await db.products.count_documents({"is_active": True})
            await cache_manager.set("product_count", product_count, cache_manager.TTL_MEDIUM)
            logger.info(f"[Cache Warm] ✓ Product count cached: {product_count}")
        except Exception as e:
            logger.debug(f"[Cache Warm] Product count: {e}")
        
        # Cache featured products
        try:
            featured = await db.products.find(
                {"is_active": True, "is_featured": True},
                {"_id": 0}
            ).to_list(10)
            if featured:
                await cache_manager.set("featured_products", featured, cache_manager.TTL_MEDIUM)
                logger.info(f"[Cache Warm] ✓ Featured products cached: {len(featured)}")
        except Exception as e:
            logger.debug(f"[Cache Warm] Featured products: {e}")
        
        # Cache collections
        try:
            collections = await db.collections.find(
                {"is_active": True},
                {"_id": 0}
            ).to_list(50)
            if collections:
                await cache_manager.set("collections", collections, cache_manager.TTL_MEDIUM)
                logger.info(f"[Cache Warm] ✓ Collections cached: {len(collections)}")
        except Exception as e:
            logger.debug(f"[Cache Warm] Collections: {e}")
        
        logger.info("[Cache Warm] Cache warm-up complete!")
        return True
        
    except Exception as e:
        logger.error(f"[Cache Warm] Failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# DECORATOR FOR CACHED FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def cached(cache_manager: CacheManager, prefix: str, ttl: int = 300):
    """
    Decorator to cache function results.
    
    Usage:
        @cached(cache_manager, "products", ttl=300)
        async def get_products():
            return await db.products.find().to_list(100)
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{prefix}:{hashlib.md5(str(args).encode() + str(kwargs).encode()).hexdigest()[:12]}"
            
            # Try to get from cache
            cached_value = await cache_manager.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Store in cache
            await cache_manager.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator
