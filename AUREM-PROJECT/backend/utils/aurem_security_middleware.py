"""
AUREM Security - ASGI Security Middleware
Company: Polaris Built Inc.

Pure ASGI middleware (not BaseHTTPMiddleware) for maximum performance.

Features:
- Blocks suspicious paths (/.env, /wp-admin, /.git, etc.)
- Adds security headers to all responses
- Blocks path traversal attempts
- Logs all blocked attempts
"""

import logging
from datetime import datetime, timezone
from typing import Callable, Set

logger = logging.getLogger(__name__)

# Paths to block with 404
BLOCKED_PATHS: Set[str] = {
    "/.env",
    "/.git",
    "/wp-admin",
    "/wp-login.php",
    "/phpMyAdmin",
    "/phpmyadmin",
    "/config.json",
    "/secrets.json",
    "/.aws",
    "/.ssh",
    "/admin.php",
    "/xmlrpc.php",
    "/.htaccess",
    "/web.config",
    "/.DS_Store",
    "/package-lock.json",
    "/yarn.lock",
    "/.npmrc",
    "/docker-compose.yml",
    "/Dockerfile",
}

# Blocked path prefixes
BLOCKED_PREFIXES = [
    "/.git/",
    "/.svn/",
    "/.hg/",
    "/wp-",
    "/admin/config",
    "/api/.env",
]

# Security headers to add
SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"x-xss-protection", b"1; mode=block"),
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
]

# MongoDB reference
_db = None

def set_db(database):
    global _db
    _db = database


def is_blocked_path(path: str) -> bool:
    """Check if path should be blocked"""
    # Exact match
    if path in BLOCKED_PATHS:
        return True
    
    # Prefix match
    for prefix in BLOCKED_PREFIXES:
        if path.startswith(prefix):
            return True
    
    # Path traversal detection
    if ".." in path:
        return True
    
    # Null byte injection
    if "\x00" in path or "%00" in path:
        return True
    
    return False


class AuremSecurityMiddleware:
    """
    Pure ASGI security middleware for AUREM.
    
    Usage:
        app = FastAPI()
        app = AuremSecurityMiddleware(app)
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        path = scope.get("path", "")
        client = scope.get("client", ("unknown", 0))
        client_ip = client[0] if client else "unknown"
        
        # Check for blocked paths
        if is_blocked_path(path):
            logger.warning(f"[SECURITY] Blocked path access: {path} from {client_ip}")
            
            # Log to database
            if _db is not None:
                try:
                    # Use sync insert for middleware
                    import asyncio
                    asyncio.create_task(self._log_blocked(client_ip, path))
                except:
                    pass
            
            # Return 404
            await self._send_404(scope, receive, send)
            return
        
        # Wrap send to add security headers
        async def send_with_security(message):
            if message["type"] == "http.response.start":
                # Add security headers
                headers = list(message.get("headers", []))
                headers.extend(SECURITY_HEADERS)
                message = {**message, "headers": headers}
            await send(message)
        
        await self.app(scope, receive, send_with_security)
    
    async def _send_404(self, scope, receive, send):
        """Send 404 Not Found response"""
        await send({
            "type": "http.response.start",
            "status": 404,
            "headers": [
                (b"content-type", b"application/json"),
                *SECURITY_HEADERS
            ]
        })
        await send({
            "type": "http.response.body",
            "body": b'{"detail": "Not Found"}'
        })
    
    async def _log_blocked(self, ip: str, path: str):
        """Log blocked attempt to database"""
        if _db is not None:
            await _db.security_block_log.insert_one({
                "ip": ip,
                "path": path,
                "reason": "blocked_path",
                "timestamp": datetime.now(timezone.utc)
            })


class AuremRateLimitMiddleware:
    """
    Pure ASGI rate limiting middleware.
    
    Usage:
        app = FastAPI()
        app = AuremRateLimitMiddleware(app)
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        from .aurem_rate_limiter import check_rate_limit, _hash_request
        
        path = scope.get("path", "")
        
        # Only rate limit /api/aurem/* endpoints
        if not path.startswith("/api/aurem"):
            await self.app(scope, receive, send)
            return
        
        # Extract user_id from authorization header
        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"").decode()
        user_id = None
        
        if auth.startswith("Bearer "):
            # In production, decode JWT to get user_id
            # For now, use token as user_id
            user_id = auth[7:30] if len(auth) > 7 else None
        
        # Create simple request mock for rate limiter
        class RequestMock:
            def __init__(self, client, headers):
                self.client = client
                self.headers = headers
        
        client = scope.get("client", ("unknown", 0))
        request = RequestMock(
            type("Client", (), {"host": client[0] if client else "unknown"})(),
            {k.decode(): v.decode() for k, v in scope.get("headers", [])}
        )
        
        # Check rate limit
        request_hash = _hash_request(path)
        allowed, error = await check_rate_limit(request, user_id, request_hash)
        
        if not allowed:
            await self._send_429(send, error)
            return
        
        await self.app(scope, receive, send)
    
    async def _send_429(self, send, message: str):
        """Send 429 Too Many Requests response"""
        import json
        body = json.dumps({"detail": message}).encode()
        
        await send({
            "type": "http.response.start",
            "status": 429,
            "headers": [
                (b"content-type", b"application/json"),
                (b"retry-after", b"3600"),
                *SECURITY_HEADERS
            ]
        })
        await send({
            "type": "http.response.body",
            "body": body
        })
