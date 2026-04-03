"""
AUREM Circuit Breaker System
Protects against cascading failures from external APIs
Based on battle-tested Reroots patterns
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Callable
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing - block calls
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker for external API calls
    
    - CLOSED: Normal operation, all calls go through
    - OPEN: Too many failures, block all calls
    - HALF_OPEN: Testing recovery, allow one call
    
    Pattern from Reroots production system
    """
    
    def __init__(
        self,
        name: str,
        threshold: int = 3,
        timeout: int = 60,
        reset_timeout: int = 300
    ):
        self.name = name
        self.threshold = threshold  # Failures before opening
        self.timeout = timeout  # Seconds to wait before half-open
        self.reset_timeout = reset_timeout  # Seconds before full reset
        
        self.failures = 0
        self.successes = 0
        self.last_failure = None
        self.last_success = None
        self.state = CircuitState.CLOSED
        
        self.total_calls = 0
        self.total_failures = 0
        self.total_blocks = 0
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker
        
        Raises:
            Exception: If circuit is OPEN or call fails
        """
        self.total_calls += 1
        
        # Check if circuit is open
        if self.state == CircuitState.OPEN:
            # Check if timeout expired
            if self.last_failure and (datetime.now(timezone.utc) - self.last_failure).seconds > self.timeout:
                logger.info(f"[CIRCUIT] {self.name} -> HALF_OPEN (testing recovery)")
                self.state = CircuitState.HALF_OPEN
            else:
                self.total_blocks += 1
                raise Exception(f"Circuit breaker {self.name} is OPEN - calls blocked (last failure: {self.last_failure})")
        
        # Execute call
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success
            self._on_success()
            return result
            
        except Exception as e:
            # Failure
            self._on_failure(e)
            raise
    
    def _on_success(self):
        """Handle successful call"""
        self.successes += 1
        self.last_success = datetime.now(timezone.utc)
        
        if self.state == CircuitState.HALF_OPEN:
            # Recovery successful - close circuit
            logger.info(f"[CIRCUIT] {self.name} -> CLOSED (recovery confirmed)")
            self.state = CircuitState.CLOSED
            self.failures = 0
        
        # Reset failures if enough successes
        if self.successes >= 10:
            self.failures = 0
            self.successes = 0
    
    def _on_failure(self, error: Exception):
        """Handle failed call"""
        self.failures += 1
        self.total_failures += 1
        self.last_failure = datetime.now(timezone.utc)
        self.successes = 0
        
        logger.warning(f"[CIRCUIT] {self.name} failure {self.failures}/{self.threshold}: {str(error)[:100]}")
        
        if self.failures >= self.threshold:
            # Open circuit
            logger.error(f"[CIRCUIT] {self.name} -> OPEN (threshold {self.threshold} reached)")
            self.state = CircuitState.OPEN
            
            # Notify orchestrator
            self._notify_orchestrator(error)
        
        elif self.state == CircuitState.HALF_OPEN:
            # Recovery failed - back to open
            logger.warning(f"[CIRCUIT] {self.name} -> OPEN (recovery failed)")
            self.state = CircuitState.OPEN
    
    def _notify_orchestrator(self, error: Exception):
        """Notify orchestrator of circuit opening"""
        try:
            # TODO: Integrate with AUREM orchestrator when available
            logger.error(f"[CIRCUIT] {self.name} circuit opened - service degraded")
        except Exception as e:
            logger.error(f"Failed to notify orchestrator: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current circuit status"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self.failures,
            "threshold": self.threshold,
            "last_failure": self.last_failure.isoformat() if self.last_failure else None,
            "last_success": self.last_success.isoformat() if self.last_success else None,
            "stats": {
                "total_calls": self.total_calls,
                "total_failures": self.total_failures,
                "total_blocks": self.total_blocks,
                "failure_rate": round(self.total_failures / self.total_calls * 100, 2) if self.total_calls > 0 else 0
            }
        }
    
    def reset(self):
        """Manually reset circuit"""
        logger.info(f"[CIRCUIT] {self.name} manually reset")
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.successes = 0


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL CIRCUIT BREAKERS FOR AUREM SERVICES
# ═══════════════════════════════════════════════════════════════════════════════

breakers = {
    # AI Services
    "anthropic": CircuitBreaker("anthropic", threshold=3, timeout=120),
    "openai": CircuitBreaker("openai", threshold=3, timeout=120),
    "emergent_llm": CircuitBreaker("emergent_llm", threshold=5, timeout=60),
    
    # Voice Services
    "vapi": CircuitBreaker("vapi", threshold=5, timeout=300),
    "elevenlabs": CircuitBreaker("elevenlabs", threshold=3, timeout=180),
    
    # Messaging Services
    "twilio": CircuitBreaker("twilio", threshold=5, timeout=300),
    "whatsapp": CircuitBreaker("whatsapp", threshold=5, timeout=300),
    "sendgrid": CircuitBreaker("sendgrid", threshold=5, timeout=300),
    
    # Database
    "mongodb": CircuitBreaker("mongodb", threshold=2, timeout=30),
    "redis": CircuitBreaker("redis", threshold=3, timeout=60),
    
    # External APIs
    "stripe": CircuitBreaker("stripe", threshold=3, timeout=120),
    "omnidimension": CircuitBreaker("omnidimension", threshold=3, timeout=180),
    "weather": CircuitBreaker("weather", threshold=5, timeout=3600),
}


def get_breaker(service: str) -> CircuitBreaker:
    """Get circuit breaker for a service"""
    if service not in breakers:
        # Create on-demand breaker
        breakers[service] = CircuitBreaker(service, threshold=3, timeout=120)
    return breakers[service]


def get_all_status() -> Dict[str, Any]:
    """Get status of all circuit breakers"""
    return {
        "breakers": {name: breaker.get_status() for name, breaker in breakers.items()},
        "total_breakers": len(breakers),
        "open_breakers": sum(1 for b in breakers.values() if b.state == CircuitState.OPEN),
        "degraded_services": [name for name, b in breakers.items() if b.state == CircuitState.OPEN]
    }


def reset_all():
    """Reset all circuit breakers"""
    for breaker in breakers.values():
        breaker.reset()
    logger.info("[CIRCUIT] All circuit breakers reset")


async def protected_call(service: str, func: Callable, *args, **kwargs) -> Any:
    """
    Convenience wrapper for protected API calls
    
    Usage:
        result = await protected_call("openai", api.chat, messages=[...])
    """
    breaker = get_breaker(service)
    return await breaker.call(func, *args, **kwargs)
