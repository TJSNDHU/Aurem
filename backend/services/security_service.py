"""
AUREM Security Module
Centralized security controls for the platform

Features:
- Rate limiting with IP-based blocking
- Auth attempt tracking with lockout
- Secrets access audit logging
- Memory directory protection
"""

import logging
import time
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from collections import defaultdict
import asyncio

from fastapi import Request, HTTPException, Depends
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ==================== RATE LIMITING ====================

class RateLimiter:
    """
    IP-based rate limiter with configurable limits.
    
    Default: 20 requests/minute per IP on public endpoints.
    """
    
    def __init__(
        self,
        requests_per_minute: int = 20,
        block_duration_seconds: int = 60
    ):
        self.requests_per_minute = requests_per_minute
        self.block_duration = block_duration_seconds
        self._requests: Dict[str, list] = defaultdict(list)
        self._blocked: Dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, ip: str) -> Tuple[bool, Optional[str]]:
        """
        Check if request from IP is allowed.
        
        Returns:
            Tuple of (allowed, reason if blocked)
        """
        async with self._lock:
            now = time.time()
            
            # Check if IP is blocked
            if ip in self._blocked:
                if now < self._blocked[ip]:
                    remaining = int(self._blocked[ip] - now)
                    return False, f"Rate limited. Retry in {remaining}s"
                else:
                    del self._blocked[ip]
            
            # Clean old requests
            minute_ago = now - 60
            self._requests[ip] = [t for t in self._requests[ip] if t > minute_ago]
            
            # Check rate
            if len(self._requests[ip]) >= self.requests_per_minute:
                self._blocked[ip] = now + self.block_duration
                logger.warning(f"[RateLimiter] IP {ip} blocked for {self.block_duration}s")
                return False, f"Rate limit exceeded ({self.requests_per_minute}/min). Blocked for {self.block_duration}s"
            
            # Record request
            self._requests[ip].append(now)
            return True, None
    
    def get_stats(self, ip: str) -> Dict[str, Any]:
        """Get rate limit stats for an IP."""
        now = time.time()
        minute_ago = now - 60
        
        recent_requests = [t for t in self._requests.get(ip, []) if t > minute_ago]
        is_blocked = ip in self._blocked and now < self._blocked[ip]
        
        return {
            "ip": ip,
            "requests_last_minute": len(recent_requests),
            "limit": self.requests_per_minute,
            "is_blocked": is_blocked,
            "remaining": self.requests_per_minute - len(recent_requests)
        }


# ==================== AUTH ATTEMPT TRACKING ====================

class AuthAttemptTracker:
    """
    Tracks failed auth attempts and implements lockout.
    
    - 5 failed attempts = 15 minute lockout
    - Tracks by IP and username combination
    """
    
    MAX_ATTEMPTS = 5
    LOCKOUT_DURATION = 15 * 60  # 15 minutes
    
    def __init__(self):
        self._attempts: Dict[str, list] = defaultdict(list)
        self._lockouts: Dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    def _get_key(self, ip: str, username: str = "") -> str:
        """Generate tracking key from IP and optional username."""
        combined = f"{ip}:{username}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    async def record_attempt(
        self,
        ip: str,
        username: str = "",
        success: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Record an auth attempt.
        
        Returns:
            Tuple of (allowed_to_continue, lockout_message)
        """
        async with self._lock:
            key = self._get_key(ip, username)
            now = time.time()
            
            # Check existing lockout
            if key in self._lockouts:
                if now < self._lockouts[key]:
                    remaining = int((self._lockouts[key] - now) / 60)
                    return False, f"Account locked. Try again in {remaining} minutes."
                else:
                    del self._lockouts[key]
                    self._attempts[key] = []
            
            if success:
                # Clear attempts on success
                self._attempts[key] = []
                return True, None
            
            # Record failed attempt
            # Keep only recent attempts (within lockout window)
            cutoff = now - self.LOCKOUT_DURATION
            self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]
            self._attempts[key].append(now)
            
            # Check if lockout triggered
            if len(self._attempts[key]) >= self.MAX_ATTEMPTS:
                self._lockouts[key] = now + self.LOCKOUT_DURATION
                logger.warning(
                    f"[AuthTracker] Lockout triggered for key {key[:8]}... "
                    f"({self.MAX_ATTEMPTS} failed attempts)"
                )
                return False, f"Too many failed attempts. Locked for {self.LOCKOUT_DURATION // 60} minutes."
            
            remaining_attempts = self.MAX_ATTEMPTS - len(self._attempts[key])
            return True, f"{remaining_attempts} attempts remaining"
    
    async def is_locked(self, ip: str, username: str = "") -> Tuple[bool, Optional[int]]:
        """
        Check if IP/username is currently locked.
        
        Returns:
            Tuple of (is_locked, remaining_seconds)
        """
        key = self._get_key(ip, username)
        now = time.time()
        
        if key in self._lockouts:
            if now < self._lockouts[key]:
                return True, int(self._lockouts[key] - now)
            else:
                async with self._lock:
                    del self._lockouts[key]
        
        return False, None


# ==================== SECRETS AUDIT ====================

class SecretsAuditLog:
    """
    Logs access to sensitive configuration and secrets.
    
    Does NOT log the actual secret values - only access events.
    """
    
    def __init__(self, db=None):
        self.db = db
        self._memory_log: list = []
    
    async def log_access(
        self,
        secret_name: str,
        accessor: str,
        action: str = "read",
        ip: Optional[str] = None,
        success: bool = True
    ):
        """Log a secret access event."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "secret_name": secret_name,
            "accessor": accessor,
            "action": action,
            "ip": ip,
            "success": success
        }
        
        # Log to memory (for immediate queries)
        self._memory_log.append(entry)
        if len(self._memory_log) > 1000:
            self._memory_log = self._memory_log[-500:]
        
        # Log to database if available
        if self.db is not None:
            try:
                await self.db["secrets_audit_log"].insert_one(entry.copy())
            except Exception as e:
                logger.error(f"[SecretsAudit] Failed to log: {e}")
        
        # Always log to application log
        logger.info(
            f"[SecretsAudit] {action.upper()} {secret_name} by {accessor} "
            f"from {ip or 'unknown'} - {'SUCCESS' if success else 'FAILED'}"
        )
    
    async def get_recent_access(self, limit: int = 100) -> list:
        """Get recent access log entries."""
        if self.db is not None:
            try:
                cursor = self.db["secrets_audit_log"].find(
                    {},
                    {"_id": 0}
                ).sort("timestamp", -1).limit(limit)
                return await cursor.to_list(limit)
            except Exception:
                pass
        
        return self._memory_log[-limit:][::-1]


# ==================== PROTECTED PATHS ====================

PROTECTED_PATHS = [
    "/app/memory/",
    "/app/backend/.env",
    "/app/frontend/.env",
    "AUDIT_REPORT.md",
    "PRD.md",
    "secrets/",
]


def is_protected_path(path: str) -> bool:
    """Check if a path should be protected from web access."""
    return any(protected in path for protected in PROTECTED_PATHS)


# ==================== GLOBAL INSTANCES ====================

rate_limiter = RateLimiter(requests_per_minute=20, block_duration_seconds=60)
auth_tracker = AuthAttemptTracker()
secrets_audit = SecretsAuditLog()


def set_security_db(db):
    """Set database for security services."""
    global secrets_audit
    secrets_audit.db = db


# ==================== FASTAPI DEPENDENCIES ====================

async def rate_limit_check(request: Request):
    """
    FastAPI dependency for rate limiting.
    
    Usage:
        @app.get("/public", dependencies=[Depends(rate_limit_check)])
        async def public_endpoint():
            ...
    """
    ip = request.client.host if request.client else "unknown"
    
    allowed, reason = await rate_limiter.is_allowed(ip)
    
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Too Many Requests",
                "message": reason,
                "retry_after": 60
            }
        )


async def auth_lockout_check(request: Request, username: str = ""):
    """
    FastAPI dependency for auth lockout checking.
    
    Call this BEFORE processing login attempts.
    """
    ip = request.client.host if request.client else "unknown"
    
    is_locked, remaining = await auth_tracker.is_locked(ip, username)
    
    if is_locked:
        raise HTTPException(
            status_code=423,
            detail={
                "error": "Account Locked",
                "message": f"Too many failed attempts. Retry in {remaining // 60} minutes.",
                "retry_after": remaining
            }
        )
