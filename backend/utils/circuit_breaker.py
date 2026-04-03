"""
Circuit Breaker Pattern for External API Calls
═══════════════════════════════════════════════════════════════════
Protects Reroots from cascading failures when external services fail.
When a service fails repeatedly, the circuit opens and skips calls
until the service has time to recover.

States:
- CLOSED: Normal operation, calls go through
- OPEN: Service is broken, calls are skipped
- HALF-OPEN: Testing if service recovered
═══════════════════════════════════════════════════════════════════
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    Circuit breaker for a single external service.
    Tracks failures and opens the circuit when threshold is exceeded.
    """
    
    def __init__(self, name: str, threshold: int = 3, timeout: int = 60):
        """
        Args:
            name: Service name (e.g., 'anthropic', 'mongodb', 'twilio')
            threshold: Number of failures before opening circuit
            timeout: Seconds to wait before testing recovery
        """
        self.name = name
        self.threshold = threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure: Optional[datetime] = None
        self.state = 'closed'  # closed=ok, open=broken, half=testing
        self.last_success: Optional[datetime] = None
    
    def _should_attempt(self) -> bool:
        """Check if we should attempt a call based on circuit state."""
        if self.state == 'closed':
            return True
        
        if self.state == 'open':
            # Check if timeout has passed
            if self.last_failure:
                elapsed = (datetime.now(timezone.utc) - self.last_failure).total_seconds()
                if elapsed > self.timeout:
                    self.state = 'half'
                    logger.info(f"[CircuitBreaker] {self.name}: HALF-OPEN (testing recovery)")
                    return True
            return False
        
        if self.state == 'half':
            return True
        
        return False
    
    def _record_success(self):
        """Record a successful call."""
        if self.state == 'half':
            logger.info(f"[CircuitBreaker] {self.name}: CLOSED (recovered)")
        self.state = 'closed'
        self.failures = 0
        self.last_success = datetime.now(timezone.utc)
    
    def _record_failure(self, error: Exception):
        """Record a failed call."""
        self.failures += 1
        self.last_failure = datetime.now(timezone.utc)
        
        if self.failures >= self.threshold:
            if self.state != 'open':
                logger.warning(f"[CircuitBreaker] {self.name}: OPEN (too many failures: {self.failures})")
            self.state = 'open'
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        Args:
            func: Async function to call
            *args, **kwargs: Arguments to pass to func
            
        Returns:
            Result of func
            
        Raises:
            CircuitOpenError: If circuit is open
            Original exception: If call fails
        """
        if not self._should_attempt():
            raise CircuitOpenError(f"Circuit {self.name} is OPEN — skipping call")
        
        try:
            result = await func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure(e)
            
            # Notify orchestrator if circuit just opened
            if self.state == 'open' and self.failures == self.threshold:
                await self._notify_orchestrator(e)
            
            raise
    
    async def _notify_orchestrator(self, error: Exception):
        """Notify orchestrator when circuit opens."""
        try:
            from services.orchestrator import orchestrator
            await orchestrator.receive('crash', {
                'service': self.name,
                'error': str(error),
                'key': f'circuit_{self.name}'
            }, 'circuit_breaker')
        except Exception as e:
            logger.error(f"[CircuitBreaker] Failed to notify orchestrator: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            'name': self.name,
            'state': self.state,
            'failures': self.failures,
            'threshold': self.threshold,
            'timeout_seconds': self.timeout,
            'last_failure': self.last_failure.isoformat() if self.last_failure else None,
            'last_success': self.last_success.isoformat() if self.last_success else None,
        }


class CircuitOpenError(Exception):
    """Raised when a call is attempted while circuit is open."""
    pass


# ═══════════════════════════════════════════════════════════════════
# GLOBAL CIRCUIT BREAKERS FOR REROOTS SERVICES
# ═══════════════════════════════════════════════════════════════════

breakers: Dict[str, CircuitBreaker] = {
    'anthropic': CircuitBreaker('anthropic', threshold=3, timeout=120),
    'openai': CircuitBreaker('openai', threshold=3, timeout=120),
    'mongodb': CircuitBreaker('mongodb', threshold=2, timeout=30),
    'redis': CircuitBreaker('redis', threshold=3, timeout=60),
    'twilio': CircuitBreaker('twilio', threshold=5, timeout=300),
    'sendgrid': CircuitBreaker('sendgrid', threshold=3, timeout=300),
    'stripe': CircuitBreaker('stripe', threshold=3, timeout=120),
    'cloudinary': CircuitBreaker('cloudinary', threshold=3, timeout=300),
}


def get_breaker(name: str) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    if name not in breakers:
        breakers[name] = CircuitBreaker(name)
    return breakers[name]


def get_all_statuses() -> Dict[str, Dict[str, Any]]:
    """Get status of all circuit breakers."""
    return {name: breaker.get_status() for name, breaker in breakers.items()}


# ═══════════════════════════════════════════════════════════════════
# STARTUP VALIDATION
# ═══════════════════════════════════════════════════════════════════

async def startup_validation(db) -> tuple[bool, list]:
    """
    Validate all critical services are available on startup.
    Returns (success, list_of_errors).
    """
    errors = []
    
    # 1. Check MongoDB
    try:
        await db.command('ping')
        logger.info("[STARTUP] ✓ MongoDB connected")
    except Exception as e:
        errors.append(f'MongoDB connection failed: {str(e)[:50]}')
    
    # 2. Check required environment variables
    import os
    required_vars = {
        'MONGO_URL': 'Database connection',
        'EMERGENT_LLM_KEY': 'AI services',
    }
    
    optional_but_important = {
        'TWILIO_ACCOUNT_SID': 'WhatsApp/SMS',
        'SENDGRID_API_KEY': 'Email automation',
        'TJ_WHATSAPP_NUMBER': 'Admin alerts',
    }
    
    for var, purpose in required_vars.items():
        if not os.environ.get(var):
            errors.append(f'Missing required env var: {var} ({purpose})')
    
    for var, purpose in optional_but_important.items():
        if not os.environ.get(var):
            logger.warning(f"[STARTUP] Optional env var not set: {var} ({purpose})")
    
    # 3. Log startup result
    if errors:
        logger.error(f"[STARTUP] ❌ Validation failed: {errors}")
        
        # Try to send WhatsApp alert
        try:
            tj_number = os.environ.get('TJ_WHATSAPP_NUMBER')
            if tj_number:
                from services.twilio_service import send_whatsapp_message
                await send_whatsapp_message(
                    tj_number,
                    f"🚨 reroots.ca startup validation failed:\n\n" + 
                    "\n".join(f"• {e}" for e in errors)
                )
        except Exception as e:
            logger.error(f"[STARTUP] Could not send WhatsApp alert: {e}")
    else:
        logger.info("[STARTUP] ✓ All validation checks passed")
    
    return len(errors) == 0, errors
