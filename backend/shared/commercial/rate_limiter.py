"""
AUREM Commercial Platform - Multi-Tenant Rate Limiter
Redis-based rate limiting with per-business quotas.

THE SHIELD: When Redis is unavailable, enforces hard in-memory limits
to prevent API cost spikes during public launch.

Key Pattern: aurem:ratelimit:biz_{id}:{channel}:{window}
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import os
import time
import threading

logger = logging.getLogger(__name__)

# Default limits per plan (messages per minute)
PLAN_LIMITS = {
    "free": {"messages": 5, "emails": 2, "whatsapp": 2},
    "trial": {"messages": 10, "emails": 5, "whatsapp": 5},
    "starter": {"messages": 50, "emails": 25, "whatsapp": 25},
    "pro": {"messages": 200, "emails": 100, "whatsapp": 100},
    "enterprise": {"messages": 1000, "emails": 500, "whatsapp": 500},
}

WINDOW_SECONDS = 60  # 1 minute window

# Global hard cap (absolute maximum across ALL plans when Redis is down)
# Prevents runaway API costs even if plan detection fails
EMERGENCY_HARD_CAP = 30  # max msgs/min per business when Redis unavailable


class InMemoryRateLimiter:
    """
    THE SHIELD: Hard in-memory rate limiter for when Redis is unavailable.
    Uses a sliding window counter with automatic cleanup.
    Thread-safe via Lock.
    """

    def __init__(self):
        self._counters: Dict[str, list] = {}  # key -> [timestamp, timestamp, ...]
        self._lock = threading.Lock()

    def _cleanup_window(self, key: str, now: float):
        """Remove timestamps older than the window."""
        if key in self._counters:
            cutoff = now - WINDOW_SECONDS
            self._counters[key] = [t for t in self._counters[key] if t > cutoff]
            if not self._counters[key]:
                del self._counters[key]

    def check_and_increment(self, business_id: str, channel: str, plan: str = "trial") -> Dict[str, Any]:
        """Check rate limit and increment counter. Returns same format as Redis version."""
        now = time.time()
        key = f"{business_id}:{channel}"

        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["trial"])
        limit = min(limits.get(channel, limits.get("messages", 10)), EMERGENCY_HARD_CAP)

        with self._lock:
            self._cleanup_window(key, now)

            current_count = len(self._counters.get(key, []))

            if current_count >= limit:
                logger.warning(f"[Shield] HARD LIMIT: {business_id}/{channel} ({current_count}/{limit})")
                return {
                    "allowed": False,
                    "remaining": 0,
                    "limit": limit,
                    "current": current_count,
                    "reset_in": WINDOW_SECONDS,
                    "engine": "in_memory_shield",
                }

            if key not in self._counters:
                self._counters[key] = []
            self._counters[key].append(now)

            remaining = max(0, limit - current_count - 1)
            return {
                "allowed": True,
                "remaining": remaining,
                "limit": limit,
                "current": current_count + 1,
                "reset_in": WINDOW_SECONDS,
                "engine": "in_memory_shield",
            }

    def get_usage(self, business_id: str) -> Dict[str, int]:
        now = time.time()
        usage = {}
        with self._lock:
            for channel in ["messages", "emails", "whatsapp"]:
                key = f"{business_id}:{channel}"
                self._cleanup_window(key, now)
                usage[channel] = len(self._counters.get(key, []))
        return usage

    def cleanup_all(self):
        """Periodic cleanup of stale entries."""
        now = time.time()
        with self._lock:
            stale = [k for k, v in self._counters.items() if all(t < now - WINDOW_SECONDS * 2 for t in v)]
            for k in stale:
                del self._counters[k]


# Singleton in-memory fallback
_memory_limiter = InMemoryRateLimiter()


class AuremRateLimiter:
    """
    Multi-tenant rate limiter.
    Uses Redis when available, falls back to in-memory HARD LIMITS (not "allow all").
    """

    PREFIX = "aurem:ratelimit"

    def __init__(self):
        self._redis = None
        self._connected = False

    async def connect(self):
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            logger.warning("[RateLimiter] REDIS_URL not set - using in-memory Shield (hard limits enforced)")
            return

        try:
            from utils.redis_pool import get_async_redis
            client = await get_async_redis()
            if client is not None:
                self._redis = client
                self._connected = True
                logger.info("[RateLimiter] Using shared Redis pool")
        except Exception as e:
            logger.warning(f"[RateLimiter] Redis failed, using in-memory Shield: {e}")

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
        THE SHIELD: When Redis unavailable, enforces hard in-memory limits.
        """
        # FALLBACK: In-memory hard limits (THE SHIELD)
        if not self.available:
            return _memory_limiter.check_and_increment(business_id, channel, plan)

        # Redis-based rate limiting
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
                "reset_in": max(0, ttl),
                "engine": "redis",
            }
        except Exception as e:
            logger.error(f"[RateLimiter] Redis check_limit failed, falling back to Shield: {e}")
            return _memory_limiter.check_and_increment(business_id, channel, plan)

    async def get_usage(self, business_id: str) -> Dict[str, Any]:
        """Get current usage for all channels."""
        if not self.available:
            usage = _memory_limiter.get_usage(business_id)
            return {"status": "shield_active", "usage": usage, "window_seconds": WINDOW_SECONDS}

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
        """Reset rate limit (admin function)."""
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
