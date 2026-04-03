"""
AUREM Circuit Breaker Service
Centralized circuit breaker management for all external services

Circuit Breaker States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service failing, requests rejected immediately
- HALF_OPEN: Testing recovery, limited requests allowed

Breakers Implemented:
1. Database (MongoDB)
2. Email (Resend/SendGrid)
3. WhatsApp (Twilio)
4. Voice (Vapi/OmniDim)
5. LLM (OpenRouter)
6. Redis Cache
7. FlagShip Courier
8. OmniDimension Webhook

Trip threshold: 3 consecutive failures
Reset timeout: 60 seconds
"""

import logging
import time
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
import os

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""
    name: str
    failure_threshold: int = 3
    reset_timeout_seconds: int = 60
    half_open_max_calls: int = 1


@dataclass
class CircuitBreaker:
    """
    Circuit breaker implementation.
    
    Protects external service calls from cascading failures.
    """
    config: CircuitBreakerConfig
    state: CircuitState = CircuitState.CLOSED
    failures: int = 0
    last_failure_time: float = 0
    half_open_calls: int = 0
    last_success_time: float = 0
    total_failures: int = 0
    total_successes: int = 0
    
    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        return {
            "name": self.config.name,
            "state": self.state.value,
            "failures": self.failures,
            "failure_threshold": self.config.failure_threshold,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "reset_timeout": self.config.reset_timeout_seconds
        }
    
    def can_execute(self) -> bool:
        """Check if a request can be executed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if reset timeout has elapsed
            if time.time() - self.last_failure_time >= self.config.reset_timeout_seconds:
                self._transition_to_half_open()
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            # Allow limited calls in half-open state
            return self.half_open_calls < self.config.half_open_max_calls
        
        return False
    
    def record_success(self):
        """Record a successful call."""
        self.total_successes += 1
        self.last_success_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # Successful call in half-open state - close the circuit
            self._transition_to_closed()
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failures = 0
    
    def record_failure(self, error: Optional[str] = None):
        """Record a failed call."""
        self.failures += 1
        self.total_failures += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # Failure in half-open state - reopen the circuit
            self._transition_to_open()
        elif self.state == CircuitState.CLOSED:
            if self.failures >= self.config.failure_threshold:
                self._transition_to_open()
                logger.warning(
                    f"[CircuitBreaker] {self.config.name} TRIPPED after {self.failures} failures"
                )
                # Trigger alert
                asyncio.create_task(self._send_alert(error))
    
    def reset(self):
        """Manually reset the circuit breaker."""
        self._transition_to_closed()
        logger.info(f"[CircuitBreaker] {self.config.name} manually reset")
    
    def _transition_to_open(self):
        """Transition to OPEN state."""
        self.state = CircuitState.OPEN
        logger.warning(f"[CircuitBreaker] {self.config.name} -> OPEN")
    
    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        self.state = CircuitState.HALF_OPEN
        self.half_open_calls = 0
        logger.info(f"[CircuitBreaker] {self.config.name} -> HALF_OPEN (testing recovery)")
    
    def _transition_to_closed(self):
        """Transition to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.half_open_calls = 0
        logger.info(f"[CircuitBreaker] {self.config.name} -> CLOSED")
    
    async def _send_alert(self, error: Optional[str] = None):
        """Send WhatsApp alert when circuit trips."""
        try:
            # Use existing Twilio WhatsApp integration
            twilio_number = os.environ.get("TWILIO_WHATSAPP_NUMBER")
            tj_number = os.environ.get("TJ_WHATSAPP_NUMBER") or os.environ.get("TWILIO_PHONE_NUMBER")
            
            if not twilio_number or not tj_number:
                logger.warning("[CircuitBreaker] No WhatsApp numbers configured for alerting")
                return
            
            account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
            auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
            
            if not account_sid or not auth_token:
                return
            
            from twilio.rest import Client
            client = Client(account_sid, auth_token)
            
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            message_body = (
                f"🚨 AUREM ALERT: Circuit Breaker Tripped\n\n"
                f"Service: {self.config.name}\n"
                f"Time: {timestamp}\n"
                f"Failures: {self.failures}/{self.config.failure_threshold}\n"
                f"Error: {error[:200] if error else 'Unknown'}\n\n"
                f"Auto-recovery in {self.config.reset_timeout_seconds}s"
            )
            
            client.messages.create(
                from_=f"whatsapp:{twilio_number}",
                to=f"whatsapp:{tj_number}",
                body=message_body
            )
            
            logger.info(f"[CircuitBreaker] Alert sent for {self.config.name}")
            
        except Exception as e:
            logger.error(f"[CircuitBreaker] Failed to send alert: {e}")


class CircuitBreakerRegistry:
    """
    Central registry for all circuit breakers.
    
    Provides unified access to all service circuit breakers.
    """
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._initialize_breakers()
    
    def _initialize_breakers(self):
        """Initialize all 8 circuit breakers."""
        breaker_configs = [
            # Original 5 breakers
            CircuitBreakerConfig(name="database", failure_threshold=3, reset_timeout_seconds=60),
            CircuitBreakerConfig(name="email", failure_threshold=3, reset_timeout_seconds=60),
            CircuitBreakerConfig(name="whatsapp", failure_threshold=3, reset_timeout_seconds=60),
            CircuitBreakerConfig(name="voice", failure_threshold=3, reset_timeout_seconds=60),
            CircuitBreakerConfig(name="llm", failure_threshold=3, reset_timeout_seconds=60),
            # 3 NEW breakers
            CircuitBreakerConfig(name="redis", failure_threshold=3, reset_timeout_seconds=60),
            CircuitBreakerConfig(name="flagship", failure_threshold=3, reset_timeout_seconds=60),
            CircuitBreakerConfig(name="omnidim", failure_threshold=3, reset_timeout_seconds=60),
        ]
        
        for config in breaker_configs:
            self._breakers[config.name] = CircuitBreaker(config=config)
            logger.info(f"[CircuitBreaker] Initialized: {config.name}")
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker by name."""
        return self._breakers.get(name)
    
    def get_all_status(self) -> Dict[str, Dict]:
        """Get status of all circuit breakers."""
        return {
            name: breaker.get_status()
            for name, breaker in self._breakers.items()
        }
    
    def get_open_breakers(self) -> list:
        """Get list of currently open (tripped) breakers."""
        return [
            name for name, breaker in self._breakers.items()
            if breaker.state == CircuitState.OPEN
        ]
    
    def reset_all(self):
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()
    
    def reset(self, name: str) -> bool:
        """Reset a specific circuit breaker."""
        breaker = self._breakers.get(name)
        if breaker:
            breaker.reset()
            return True
        return False


# Global registry instance
circuit_registry = CircuitBreakerRegistry()


# Convenience accessors for each breaker
def get_db_breaker() -> CircuitBreaker:
    return circuit_registry.get("database")

def get_email_breaker() -> CircuitBreaker:
    return circuit_registry.get("email")

def get_whatsapp_breaker() -> CircuitBreaker:
    return circuit_registry.get("whatsapp")

def get_voice_breaker() -> CircuitBreaker:
    return circuit_registry.get("voice")

def get_llm_breaker() -> CircuitBreaker:
    return circuit_registry.get("llm")

def get_redis_breaker() -> CircuitBreaker:
    return circuit_registry.get("redis")

def get_flagship_breaker() -> CircuitBreaker:
    return circuit_registry.get("flagship")

def get_omnidim_breaker() -> CircuitBreaker:
    return circuit_registry.get("omnidim")


# Decorator for circuit breaker protection
def with_circuit_breaker(breaker_name: str):
    """
    Decorator to protect a function with a circuit breaker.
    
    Usage:
        @with_circuit_breaker("redis")
        async def get_cached_data(key):
            ...
    """
    def decorator(func: Callable[..., Awaitable]):
        async def wrapper(*args, **kwargs):
            breaker = circuit_registry.get(breaker_name)
            if not breaker:
                return await func(*args, **kwargs)
            
            if not breaker.can_execute():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{breaker_name}' is OPEN"
                )
            
            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure(str(e))
                raise
        
        return wrapper
    return decorator


class CircuitBreakerOpenError(Exception):
    """Raised when attempting to call a service with an open circuit breaker."""
    pass


# Legacy compatibility - for existing code that imports db_circuit_breaker
db_circuit_breaker = get_db_breaker()
