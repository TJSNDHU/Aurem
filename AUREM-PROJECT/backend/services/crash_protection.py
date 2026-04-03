"""
Crash Protection System for reroots.ca
Implements:
1. Circuit breaker for MongoDB
2. Graceful degradation with Redis cache fallback
3. Request timeout protection
4. Global exception handler
"""

import asyncio
import time
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)

# ============= CIRCUIT BREAKER FOR MONGODB =============

class CircuitBreaker:
    """
    Circuit breaker pattern for database calls.
    Prevents cascading failures when MongoDB is down.
    
    States:
    - CLOSED: Normal operation, requests go through
    - OPEN: Too many failures, requests fail fast
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def _should_allow_request(self) -> bool:
        """Check if request should be allowed based on circuit state"""
        if self.state == "CLOSED":
            return True
        
        if self.state == "OPEN":
            # Check if we should transition to half-open
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("[CIRCUIT_BREAKER] Transitioning to HALF_OPEN state")
                return True
            return False
        
        # HALF_OPEN - allow one request to test
        return True
    
    def _record_success(self):
        """Record successful request"""
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            self.failures = 0
            logger.info("[CIRCUIT_BREAKER] Service recovered, transitioning to CLOSED state")
        elif self.state == "CLOSED":
            # Reset failure count on success
            self.failures = max(0, self.failures - 1)
    
    def _record_failure(self):
        """Record failed request"""
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.state == "HALF_OPEN":
            # Failed during recovery test - go back to open
            self.state = "OPEN"
            logger.warning("[CIRCUIT_BREAKER] Recovery test failed, transitioning back to OPEN state")
        elif self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.error(f"[CIRCUIT_BREAKER] Threshold reached ({self.failures} failures), transitioning to OPEN state")
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.
        
        Args:
            func: Async function to execute
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit is open or function fails
        """
        if not self._should_allow_request():
            raise CircuitBreakerOpenError(
                f"MongoDB circuit breaker OPEN - service unavailable (last failure: {int(time.time() - self.last_failure_time)}s ago)"
            )
        
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            self._record_success()
            return result
        except Exception:
            self._record_failure()
            raise
    
    def get_status(self) -> dict:
        """Get current circuit breaker status"""
        return {
            "state": self.state,
            "failures": self.failures,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_seconds": self.recovery_timeout,
            "last_failure_ago_seconds": int(time.time() - self.last_failure_time) if self.last_failure_time > 0 else None
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


# Global circuit breaker instance for MongoDB
db_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)


# ============= GRACEFUL DEGRADATION WITH REDIS CACHE =============

class GracefulDegradation:
    """
    Provides fallback mechanisms when primary services fail.
    Uses Redis as cache layer for degraded mode.
    """
    
    def __init__(self):
        self._redis_client = None
        self._cache_prefix = "reroots_fallback:"
        self._default_ttl = 3600  # 1 hour
    
    async def set_redis(self, redis_client):
        """Set Redis client for fallback cache"""
        self._redis_client = redis_client
    
    async def cache_data(self, key: str, data: Any, ttl: int = None) -> bool:
        """
        Cache data in Redis for fallback.
        
        Args:
            key: Cache key
            data: Data to cache (will be JSON serialized)
            ttl: Time to live in seconds
            
        Returns:
            True if cached successfully
        """
        if self._redis_client is None:
            return False
        
        try:
            cache_key = f"{self._cache_prefix}{key}"
            serialized = json.dumps(data, default=str)
            await self._redis_client.setex(cache_key, ttl or self._default_ttl, serialized)
            return True
        except Exception as e:
            logger.warning(f"[GRACEFUL_DEGRADATION] Failed to cache {key}: {e}")
            return False
    
    async def get_cached(self, key: str) -> Optional[Any]:
        """
        Get cached data from Redis.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data or None if not found
        """
        if self._redis_client is None:
            return None
        
        try:
            cache_key = f"{self._cache_prefix}{key}"
            data = await self._redis_client.get(cache_key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.warning(f"[GRACEFUL_DEGRADATION] Failed to get cached {key}: {e}")
            return None
    
    async def safe_db_call(
        self, 
        db_func: Callable, 
        cache_key: str,
        fallback_value: Any = None,
        cache_ttl: int = None
    ) -> Any:
        """
        Execute database call with circuit breaker and cache fallback.
        
        Args:
            db_func: Async function that calls the database
            cache_key: Key for caching the result
            fallback_value: Value to return if all else fails
            cache_ttl: Cache TTL in seconds
            
        Returns:
            Database result, cached result, or fallback value
        """
        try:
            # Try database call through circuit breaker
            result = await db_circuit_breaker.call(db_func)
            
            # Cache successful result for future fallback
            await self.cache_data(cache_key, result, cache_ttl)
            
            return result
            
        except CircuitBreakerOpenError:
            logger.warning(f"[GRACEFUL_DEGRADATION] Circuit breaker open for {cache_key}, trying cache")
            
            # Try cached result
            cached = await self.get_cached(cache_key)
            if cached is not None:
                logger.info(f"[GRACEFUL_DEGRADATION] Serving cached data for {cache_key}")
                return cached
            
            # Return fallback
            logger.warning(f"[GRACEFUL_DEGRADATION] No cached data for {cache_key}, returning fallback")
            return fallback_value
            
        except Exception as e:
            logger.error(f"[GRACEFUL_DEGRADATION] Database call failed for {cache_key}: {e}")
            
            # Try cached result
            cached = await self.get_cached(cache_key)
            if cached is not None:
                logger.info(f"[GRACEFUL_DEGRADATION] Serving cached data for {cache_key} after error")
                return cached
            
            return fallback_value


# Global graceful degradation instance
graceful_degradation = GracefulDegradation()


# ============= CRASH LOG UTILITY =============

_crash_log_db = None

def set_crash_log_db(database):
    """Set database for crash logging"""
    global _crash_log_db
    _crash_log_db = database


async def log_crash(request_url: str, error: Exception, error_type: str) -> None:
    """
    Log crash/error to MongoDB for debugging.
    
    Args:
        request_url: URL that caused the error
        error: The exception that occurred
        error_type: Type name of the exception
    """
    if _crash_log_db is None:
        logger.warning("[CRASH_LOG] Database not available for crash logging")
        return
    
    try:
        crash_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "url": str(request_url),
            "error": str(error),
            "type": error_type,
            "traceback": getattr(error, '__traceback__', None) and str(error.__traceback__) or None
        }
        await _crash_log_db.crash_log.insert_one(crash_entry)
        logger.info(f"[CRASH_LOG] Logged crash: {error_type} at {request_url}")
    except Exception as e:
        # Don't let crash logging cause more crashes
        logger.error(f"[CRASH_LOG] Failed to log crash: {e}")


async def get_recent_crashes(limit: int = 50) -> list:
    """Get recent crash logs from MongoDB"""
    if _crash_log_db is None:
        return []
    
    try:
        crashes = await _crash_log_db.crash_log.find(
            {},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        return crashes
    except Exception as e:
        logger.error(f"[CRASH_LOG] Failed to get crash logs: {e}")
        return []
