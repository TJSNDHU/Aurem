"""
AUREM Security Router
Administrative endpoints for security monitoring

Endpoints:
- GET /api/security/rate-limits - Check rate limit status
- GET /api/security/lockouts - Check auth lockouts
- GET /api/security/audit-log - Get secrets access audit
- POST /api/security/unlock - Manually unlock an IP/user
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, Query, Request

from services.security_service import (
    rate_limiter,
    auth_tracker,
    secrets_audit,
    set_security_db
)

router = APIRouter(prefix="/api/security", tags=["Security"])

logger = logging.getLogger(__name__)

_db = None


def set_db(db):
    """Set database dependency."""
    global _db
    _db = db
    set_security_db(db)


async def verify_admin_key(x_admin_key: str = Header(None, alias="X-Admin-Key")):
    """Verify admin key for security endpoints."""
    import os
    expected_key = os.environ.get("ADMIN_API_KEY") or os.environ.get("JWT_SECRET", "")[:32]
    
    if not x_admin_key or x_admin_key != expected_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing admin key"
        )


@router.get("/rate-limits")
async def get_rate_limit_status(
    request: Request,
    ip: Optional[str] = Query(None, description="Specific IP to check")
):
    """
    Get rate limit status.
    
    If no IP specified, returns stats for the requesting IP.
    """
    check_ip = ip or (request.client.host if request.client else "unknown")
    stats = rate_limiter.get_stats(check_ip)
    
    return {
        "status": "ok",
        "rate_limits": stats,
        "config": {
            "requests_per_minute": rate_limiter.requests_per_minute,
            "block_duration_seconds": rate_limiter.block_duration
        }
    }


@router.get("/lockouts")
async def get_lockout_status(
    request: Request,
    ip: Optional[str] = Query(None),
    username: Optional[str] = Query(None)
):
    """Check if an IP/username is locked out."""
    check_ip = ip or (request.client.host if request.client else "unknown")
    
    is_locked, remaining = await auth_tracker.is_locked(check_ip, username or "")
    
    return {
        "ip": check_ip,
        "username": username or "(any)",
        "is_locked": is_locked,
        "remaining_seconds": remaining,
        "config": {
            "max_attempts": auth_tracker.MAX_ATTEMPTS,
            "lockout_duration_minutes": auth_tracker.LOCKOUT_DURATION // 60
        }
    }


@router.post("/unlock")
async def unlock_ip_user(
    ip: str = Query(..., description="IP address to unlock"),
    username: Optional[str] = Query(None),
    x_admin_key: str = Header(None, alias="X-Admin-Key")
):
    """
    Manually unlock an IP/username.
    
    Requires admin key.
    """
    await verify_admin_key(x_admin_key)
    
    key = auth_tracker._get_key(ip, username or "")
    
    if key in auth_tracker._lockouts:
        del auth_tracker._lockouts[key]
        auth_tracker._attempts[key] = []
        
        logger.info(f"[Security] Manual unlock: IP={ip}, username={username}")
        
        return {
            "success": True,
            "message": f"Unlocked IP {ip}" + (f" for user {username}" if username else "")
        }
    
    return {
        "success": True,
        "message": "IP/user was not locked"
    }


@router.get("/audit-log")
async def get_secrets_audit_log(
    limit: int = Query(100, ge=1, le=500),
    x_admin_key: str = Header(None, alias="X-Admin-Key")
):
    """
    Get secrets access audit log.
    
    Requires admin key.
    """
    await verify_admin_key(x_admin_key)
    
    logs = await secrets_audit.get_recent_access(limit)
    
    return {
        "count": len(logs),
        "logs": logs,
        "retrieved_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/status")
async def get_security_status():
    """Get overall security status summary."""
    return {
        "status": "ok",
        "services": {
            "rate_limiter": "active",
            "auth_tracker": "active",
            "secrets_audit": "active",
            "path_protection": "active"
        },
        "config": {
            "rate_limit": f"{rate_limiter.requests_per_minute} req/min",
            "auth_lockout": f"{auth_tracker.MAX_ATTEMPTS} attempts / {auth_tracker.LOCKOUT_DURATION // 60} min",
            "protected_paths": [
                "/memory/",
                "/.env",
                "/AUDIT_REPORT",
                "/PRD.md",
                "/SECRETS_POLICY"
            ]
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/health")
async def security_health_check():
    """Simple health check for security service."""
    return {"status": "healthy"}
