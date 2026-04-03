"""
AI Rate Limiter for Reroots
Enhanced rate limiting specifically for AI chat endpoints.

Features:
- Per-IP rate limiting (10/hr unauthenticated, 50/hr authenticated)
- Duplicate message detection (5+ identical = 24hr block)
- IP fingerprinting
- Suspicious activity logging

Usage:
    from services.ai_rate_limiter import AIRateLimiter
    
    limiter = AIRateLimiter(db)
    allowed, info = await limiter.check_rate_limit(ip, is_authenticated, message)
"""

import os
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Rate limits
UNAUTHENTICATED_LIMIT_PER_HOUR = 10
AUTHENTICATED_LIMIT_PER_HOUR = 50
DUPLICATE_MESSAGE_THRESHOLD = 5  # Block after 5 identical messages
BLOCK_DURATION_HOURS = 24

# Admin WhatsApp for alerts
ADMIN_WHATSAPP = os.environ.get("ADMIN_WHATSAPP", "+14168869408")


class AIRateLimiter:
    """
    Enhanced rate limiter for AI chat endpoints.
    Implements IP-based rate limiting with duplicate detection.
    """
    
    def __init__(self, db):
        self.db = db
        self.collection = db.ai_rate_limits if db is not None else None
        self.suspicious_log = db.suspicious_activity_log if db is not None else None
    
    def _hash_message(self, message: str) -> str:
        """Create hash of message for duplicate detection."""
        return hashlib.sha256(message.lower().strip().encode()).hexdigest()[:32]
    
    def _hash_ip(self, ip: str) -> str:
        """Create hash of IP for storage."""
        return hashlib.sha256(ip.encode()).hexdigest()[:32]
    
    async def _is_ip_blocked(self, ip_hash: str) -> Tuple[bool, Optional[datetime]]:
        """Check if IP is currently blocked."""
        if self.collection is None:
            return False, None
        
        block_record = await self.collection.find_one({
            "ip_hash": ip_hash,
            "blocked": True,
            "blocked_until": {"$gt": datetime.now(timezone.utc).isoformat()}
        })
        
        if block_record:
            return True, block_record.get("blocked_until")
        
        return False, None
    
    async def _count_recent_requests(
        self, 
        ip_hash: str, 
        hours: int = 1
    ) -> int:
        """Count requests from IP in the last N hours."""
        if self.collection is None:
            return 0
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        count = await self.collection.count_documents({
            "ip_hash": ip_hash,
            "timestamp": {"$gte": cutoff.isoformat()},
            "type": "request"
        })
        
        return count
    
    async def _count_duplicate_messages(
        self,
        ip_hash: str,
        message_hash: str,
        hours: int = 1
    ) -> int:
        """Count identical messages from IP in the last N hours."""
        if self.collection is None:
            return 0
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        count = await self.collection.count_documents({
            "ip_hash": ip_hash,
            "message_hash": message_hash,
            "timestamp": {"$gte": cutoff.isoformat()},
            "type": "request"
        })
        
        return count
    
    async def _block_ip(self, ip_hash: str, reason: str, duration_hours: int = 24):
        """Block an IP address."""
        if self.collection is None:
            return
        
        blocked_until = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
        
        await self.collection.update_one(
            {"ip_hash": ip_hash, "type": "block"},
            {
                "$set": {
                    "ip_hash": ip_hash,
                    "type": "block",
                    "blocked": True,
                    "blocked_until": blocked_until.isoformat(),
                    "reason": reason,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
        
        logger.warning(f"[AI_RATE_LIMITER] Blocked IP hash {ip_hash[:8]}... for {duration_hours}h: {reason}")
    
    async def _log_suspicious_activity(
        self,
        ip_hash: str,
        activity_type: str,
        details: Dict[str, Any]
    ):
        """Log suspicious activity for review."""
        if not self.suspicious_log:
            return
        
        try:
            await self.suspicious_log.insert_one({
                "ip_hash": ip_hash,
                "activity_type": activity_type,
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            # Send WhatsApp alert for serious issues
            if activity_type in ["duplicate_spam", "rate_limit_exceeded"]:
                try:
                    from services.twilio_service import send_whatsapp_message
                    await send_whatsapp_message(
                        ADMIN_WHATSAPP,
                        f"Security Alert: {activity_type} detected from IP {ip_hash[:8]}..."
                    )
                except Exception as e:
                    logger.warning(f"[AI_RATE_LIMITER] WhatsApp alert failed: {e}")
                    
        except Exception as e:
            logger.error(f"[AI_RATE_LIMITER] Failed to log suspicious activity: {e}")
    
    async def _record_request(
        self,
        ip_hash: str,
        message_hash: str,
        is_authenticated: bool
    ):
        """Record a request for rate limiting."""
        if self.collection is None:
            return
        
        try:
            await self.collection.insert_one({
                "ip_hash": ip_hash,
                "message_hash": message_hash,
                "is_authenticated": is_authenticated,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "request"
            })
        except Exception as e:
            logger.error(f"[AI_RATE_LIMITER] Failed to record request: {e}")
    
    async def check_rate_limit(
        self,
        ip_address: str,
        is_authenticated: bool = False,
        message: str = ""
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request should be allowed.
        
        Args:
            ip_address: Client IP address
            is_authenticated: Whether user is logged in
            message: The message being sent
            
        Returns:
            Tuple of (allowed: bool, info: dict)
        """
        ip_hash = self._hash_ip(ip_address)
        message_hash = self._hash_message(message) if message else ""
        
        # Check if IP is blocked
        is_blocked, blocked_until = await self._is_ip_blocked(ip_hash)
        if is_blocked:
            return False, {
                "error": "rate_limit_exceeded",
                "message": "Rate limit exceeded. For urgent help WhatsApp us at +14168869408",
                "blocked_until": blocked_until,
                "retry_after_seconds": 86400  # 24 hours
            }
        
        # Check duplicate message spam
        if message_hash:
            duplicate_count = await self._count_duplicate_messages(ip_hash, message_hash)
            
            if duplicate_count >= DUPLICATE_MESSAGE_THRESHOLD:
                # Block for 24 hours
                await self._block_ip(
                    ip_hash,
                    f"Duplicate message spam: {duplicate_count}+ identical messages in 1 hour",
                    BLOCK_DURATION_HOURS
                )
                
                await self._log_suspicious_activity(
                    ip_hash,
                    "duplicate_spam",
                    {
                        "duplicate_count": duplicate_count,
                        "message_hash": message_hash
                    }
                )
                
                return False, {
                    "error": "spam_detected",
                    "message": "Too many identical messages. For urgent help WhatsApp us at +14168869408",
                    "blocked_for_hours": BLOCK_DURATION_HOURS
                }
        
        # Check hourly rate limit
        request_count = await self._count_recent_requests(ip_hash, hours=1)
        limit = AUTHENTICATED_LIMIT_PER_HOUR if is_authenticated else UNAUTHENTICATED_LIMIT_PER_HOUR
        
        if request_count >= limit:
            # Log suspicious activity
            await self._log_suspicious_activity(
                ip_hash,
                "rate_limit_exceeded",
                {
                    "request_count": request_count,
                    "limit": limit,
                    "is_authenticated": is_authenticated
                }
            )
            
            return False, {
                "error": "rate_limit_exceeded",
                "message": f"Rate limit exceeded ({limit} requests per hour). For urgent help WhatsApp us at +14168869408",
                "limit": limit,
                "used": request_count,
                "remaining": 0,
                "reset_in_minutes": 60
            }
        
        # Record this request
        await self._record_request(ip_hash, message_hash, is_authenticated)
        
        return True, {
            "allowed": True,
            "limit": limit,
            "used": request_count + 1,
            "remaining": limit - request_count - 1
        }
    
    async def get_ip_status(self, ip_address: str) -> Dict[str, Any]:
        """Get current rate limit status for an IP."""
        ip_hash = self._hash_ip(ip_address)
        
        is_blocked, blocked_until = await self._is_ip_blocked(ip_hash)
        request_count = await self._count_recent_requests(ip_hash, hours=1)
        
        return {
            "ip_hash": ip_hash[:8] + "...",
            "is_blocked": is_blocked,
            "blocked_until": blocked_until,
            "requests_last_hour": request_count,
            "unauthenticated_limit": UNAUTHENTICATED_LIMIT_PER_HOUR,
            "authenticated_limit": AUTHENTICATED_LIMIT_PER_HOUR
        }


# Global instance (initialized with db from server.py)
_rate_limiter = None


def get_ai_rate_limiter(db) -> AIRateLimiter:
    """Get or create the rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None or _rate_limiter.db != db:
        _rate_limiter = AIRateLimiter(db)
    return _rate_limiter
