"""
AUREM Security - Rate Limiting
Company: Polaris Built Inc.

Tight rate limiting for commercial API protection:
- Unauthenticated: 20 requests/hour per IP
- Authenticated: 200 requests/hour per user
- Suspicious pattern detection: 10+ identical requests → 24h IP block
"""

import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)

# Rate limit configuration
RATE_LIMITS = {
    "unauthenticated": {
        "requests": 20,
        "window_seconds": 3600,  # 1 hour
    },
    "authenticated": {
        "requests": 200,
        "window_seconds": 3600,
    },
    "suspicious_threshold": 10,  # Identical requests in 1 hour
    "block_duration_hours": 24,
}

# In-memory storage (replace with Redis for production scaling)
_request_counts: Dict[str, list] = defaultdict(list)  # IP -> list of timestamps
_request_hashes: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))  # IP -> {hash: count}
_blocked_ips: Dict[str, datetime] = {}  # IP -> block_until
_user_request_counts: Dict[str, list] = defaultdict(list)  # user_id -> list of timestamps

# MongoDB reference for persistent logging
_db = None

def set_db(database):
    global _db
    _db = database


def get_client_ip(request) -> str:
    """Extract client IP from request"""
    # Check X-Forwarded-For for proxied requests
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _hash_request(path: str, body: bytes = None) -> str:
    """Create hash of request for duplicate detection"""
    content = f"{path}:{body.decode() if body else ''}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def _cleanup_old_entries(entries: list, window_seconds: int) -> list:
    """Remove entries older than the window"""
    cutoff = time.time() - window_seconds
    return [ts for ts in entries if ts > cutoff]


async def check_rate_limit(
    request,
    user_id: Optional[str] = None,
    request_hash: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Check if request should be rate limited.
    
    Returns:
        (allowed: bool, error_message: Optional[str])
    """
    ip = get_client_ip(request)
    now = time.time()
    
    # Check if IP is blocked
    if ip in _blocked_ips:
        block_until = _blocked_ips[ip]
        if datetime.now(timezone.utc) < block_until:
            remaining = (block_until - datetime.now(timezone.utc)).seconds // 60
            logger.warning(f"[RATE LIMIT] Blocked IP {ip} attempted access")
            return False, f"Access suspended for security reasons. Try again in {remaining} minutes."
        else:
            # Block expired
            del _blocked_ips[ip]
    
    # Determine rate limit based on authentication
    if user_id:
        # Authenticated user
        limits = RATE_LIMITS["authenticated"]
        _user_request_counts[user_id] = _cleanup_old_entries(
            _user_request_counts[user_id], 
            limits["window_seconds"]
        )
        
        if len(_user_request_counts[user_id]) >= limits["requests"]:
            logger.warning(f"[RATE LIMIT] User {user_id} exceeded limit")
            return False, "Rate limit exceeded. Please wait before making more requests."
        
        _user_request_counts[user_id].append(now)
    else:
        # Unauthenticated IP
        limits = RATE_LIMITS["unauthenticated"]
        _request_counts[ip] = _cleanup_old_entries(
            _request_counts[ip],
            limits["window_seconds"]
        )
        
        if len(_request_counts[ip]) >= limits["requests"]:
            logger.warning(f"[RATE LIMIT] IP {ip} exceeded unauthenticated limit")
            return False, "Rate limit exceeded. Please authenticate or wait."
        
        _request_counts[ip].append(now)
    
    # Check for suspicious patterns (duplicate requests)
    if request_hash:
        _request_hashes[ip][request_hash] += 1
        
        if _request_hashes[ip][request_hash] >= RATE_LIMITS["suspicious_threshold"]:
            # Block the IP
            block_until = datetime.now(timezone.utc) + timedelta(
                hours=RATE_LIMITS["block_duration_hours"]
            )
            _blocked_ips[ip] = block_until
            
            # Log to database
            if _db is not None:
                await _db.suspicious_activity_log.insert_one({
                    "ip": ip,
                    "pattern": "duplicate_requests",
                    "request_hash": request_hash,
                    "count": _request_hashes[ip][request_hash],
                    "blocked_until": block_until,
                    "timestamp": datetime.now(timezone.utc)
                })
            
            logger.critical(f"[RATE LIMIT] IP {ip} blocked for suspicious activity")
            return False, "Access suspended for security reasons."
    
    return True, None


def get_rate_limit_stats() -> Dict:
    """Get current rate limiting statistics"""
    return {
        "active_ips": len(_request_counts),
        "active_users": len(_user_request_counts),
        "blocked_ips": len(_blocked_ips),
        "blocked_ip_list": list(_blocked_ips.keys())
    }


def unblock_ip(ip: str) -> bool:
    """Manually unblock an IP address"""
    if ip in _blocked_ips:
        del _blocked_ips[ip]
        logger.info(f"[RATE LIMIT] IP {ip} manually unblocked")
        return True
    return False


def clear_rate_limits():
    """Clear all rate limit data (admin only)"""
    global _request_counts, _request_hashes, _blocked_ips, _user_request_counts
    _request_counts = defaultdict(list)
    _request_hashes = defaultdict(lambda: defaultdict(int))
    _blocked_ips = {}
    _user_request_counts = defaultdict(list)
    logger.info("[RATE LIMIT] All rate limit data cleared")
