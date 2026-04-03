"""
AUREM Commercial Platform - Multi-Tenant Rate Limiter
Redis-based rate limiting with per-business quotas

Key Pattern: aurem:ratelimit:biz_{id}:{channel}:{window}
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import os
import time

logger = logging.getLogger(__name__)

# Default limits per plan (messages per minute)
PLAN_LIMITS = {
    "trial": {"messages": 10, "emails": 5, "whatsapp": 5},
    "starter": {"messages": 50, "emails": 25, "whatsapp": 25},
    "pro": {"messages": 200, "emails": 100, "whatsapp": 100},
    "enterprise": {"messages": 1000, "emails": 500, "whatsapp": 500}
}

WINDOW_SECONDS = 60  # 1 minute window


class AuremRateLimiter:
    """
    Multi-tenant rate limiter using Redis.
    Protects against spam and bot attacks.
    """
    
    PREFIX = "aurem:ratelimit"
    
    def __init__(self):
        self._redis = None
        self._connected = False
    
    async def connect(self):
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            return
        
        try:
            import redis.asyncio as aioredis
            self._redis = await aioredis.from_url(
                redis_url, encoding="utf-8", decode_responses=True,
                socket_timeout=5, socket_connect_timeout=5
            )
            await self._redis.ping()
            self._connected = True
            logger.info("[RateLimiter] Connected to Redis")
        except Exception as e:
            logger.warning(f"[RateLimiter] Redis connection failed: {e}")
    
    @property
    def available(self) -> bool:
        return self._connected and self._redis is not None
    
    def _key(self, business_id: str, channel: str) -> str:
        window = int(time.time()) // WINDOW_SECONDS
        return f"{self.PREFIX}:biz_{business_id}:{channel}:{window}"
    
    async def check_limit(
        self,
        business_id: str,
        channel: str,
        plan: str = "trial"
    ) -> Dict[str, Any]:
        """
        Check if business is within rate limits.
        Returns {allowed: bool, remaining: int, limit: int, reset_in: int}
        """
        if not self.available:
            return {"allowed": True, "remaining": 999, "limit": 999, "reset_in": 0}
        
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["trial"])
        limit = limits.get(channel, limits.get("messages", 10))
        
        key = self._key(business_id, channel)
        
        try:
            current = await self._redis.incr(key)
            if current == 1:
                await self._redis.expire(key, WINDOW_SECONDS)
            
            ttl = await self._redis.ttl(key)
            remaining = max(0, limit - current)
            allowed = current <= limit
            
            if not allowed:
                logger.warning(f"[RateLimiter] Limit exceeded: {business_id}/{channel} ({current}/{limit})")
            
            return {
                "allowed": allowed,
                "remaining": remaining,
                "limit": limit,
                "current": current,
                "reset_in": max(0, ttl)
            }
        except Exception as e:
            logger.error(f"[RateLimiter] check_limit failed: {e}")
            return {"allowed": True, "remaining": limit, "limit": limit, "reset_in": 60}
    
    async def get_usage(self, business_id: str) -> Dict[str, Any]:
        """Get current usage for all channels"""
        if not self.available:
            return {"status": "unavailable"}
        
        usage = {}
        for channel in ["messages", "emails", "whatsapp"]:
            key = self._key(business_id, channel)
            try:
                count = await self._redis.get(key)
                usage[channel] = int(count) if count else 0
            except Exception:
                usage[channel] = 0
        
        return {"status": "connected", "usage": usage, "window_seconds": WINDOW_SECONDS}
    
    async def reset_limit(self, business_id: str, channel: str = None):
        """Reset rate limit (admin function)"""
        if not self.available:
            return
        
        try:
            if channel:
                key = self._key(business_id, channel)
                await self._redis.delete(key)
            else:
                pattern = f"{self.PREFIX}:biz_{business_id}:*"
                keys = await self._redis.keys(pattern)
                if keys:
                    await self._redis.delete(*keys)
        except Exception as e:
            logger.error(f"[RateLimiter] reset failed: {e}")


_rate_limiter: Optional[AuremRateLimiter] = None

async def get_rate_limiter() -> AuremRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = AuremRateLimiter()
        await _rate_limiter.connect()
    return _rate_limiter
