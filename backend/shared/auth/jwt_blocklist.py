"""
JWT Blocklist — Redis-backed token revocation for stateless security.
On logout, the token's JTI (JWT ID) is added to Redis with the same TTL as the token.
On every verify_token call, the blocklist is checked first.
"""
import os
import logging

logger = logging.getLogger(__name__)

_redis = None
_KEY_PREFIX = "aurem:jwt:blocked:"


async def _get_redis():
    """Return shared Redis client from the global pool."""
    try:
        from utils.redis_pool import get_async_redis
        return await get_async_redis()
    except Exception as e:
        logger.debug(f"[JWT Blocklist] Redis unavailable: {e}")
        return None


async def block_token(token: str, jti: str, ttl_seconds: int = 86400):
    """Add a token to the blocklist. TTL matches token expiry (default 24h)."""
    r = await _get_redis()
    if not r:
        return False
    try:
        await r.setex(f"{_KEY_PREFIX}{jti}", ttl_seconds, "1")
        return True
    except Exception as e:
        logger.debug(f"[JWT Blocklist] Block failed: {e}")
        return False


async def is_blocked(jti: str) -> bool:
    """Check if a token JTI is in the blocklist."""
    r = await _get_redis()
    if not r:
        return False
    try:
        return await r.exists(f"{_KEY_PREFIX}{jti}") > 0
    except Exception:
        return False
