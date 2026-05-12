"""
Security Middleware — Rate Limiting, CORS, Input Sanitization
Extracted from server.py during modularization.
"""
import os
import re
import html
import time
import json
import hashlib
import logging
import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi import Request

logger = logging.getLogger(__name__)

# Rate limiting defaults
RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))
LOGIN_RATE_LIMIT = int(os.environ.get("LOGIN_RATE_LIMIT", "10"))
LOGIN_RATE_WINDOW = int(os.environ.get("LOGIN_RATE_WINDOW", "300"))
STRICT_RATE_LIMIT = int(os.environ.get("STRICT_RATE_LIMIT", "30"))
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
REDIS_URL = os.environ.get("REDIS_URL", "")

BLOCKED_PATHS = [
    "/.env", "/wp-admin", "/wp-login", "/.git",
    "/phpmyadmin", "/admin.php", "/.well-known/security.txt",
]

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store, no-cache, must-revalidate",
}


class RedisRateLimiter:
    """
    Redis-backed rate limiter with in-memory fallback.
    Works across multiple server instances in production.
    """
    def __init__(self):
        self._redis = None
        self._connected = False
        self._memory_storage = defaultdict(list)  # Fallback only
    
    async def connect(self):
        """Connect to Redis via shared ConnectionPool."""
        try:
            redis_url = os.environ.get("REDIS_URL")
            if redis_url:
                from utils.redis_pool import get_async_redis
                client = await get_async_redis()
                if client is not None:
                    self._redis = client
                    self._connected = True
                    logging.info("✓ Rate limiter using shared Redis pool")
                else:
                    self._connected = False
            else:
                logging.warning("REDIS_URL not set - rate limiter using in-memory storage (not suitable for multi-instance)")
        except Exception as e:
            logging.warning(f"Rate limiter Redis connection failed, using in-memory fallback: {e}")
            self._connected = False
    
    async def is_rate_limited(self, key: str, limit: int, window: int) -> bool:
        """Check if request should be rate limited. Returns True if over limit."""
        current_time = time.time()
        
        if self._connected and self._redis:
            try:
                # Use Redis sorted set for sliding window rate limiting
                redis_key = f"ratelimit:{key}"

                # All Redis ops capped at 0.5s — in deployed k8s env the cloud
                # Redis may be unreachable; we'd rather fall back to memory fast
                # than block every request for 4s.
                await asyncio.wait_for(
                    self._redis.zremrangebyscore(redis_key, 0, current_time - window),
                    timeout=0.5,
                )

                count = await asyncio.wait_for(
                    self._redis.zcard(redis_key),
                    timeout=0.5,
                )

                if count >= limit:
                    return True

                await asyncio.wait_for(
                    self._redis.zadd(redis_key, {str(current_time): current_time}),
                    timeout=0.5,
                )
                await asyncio.wait_for(
                    self._redis.expire(redis_key, window + 1),
                    timeout=0.5,
                )

                return False
            except (asyncio.TimeoutError, Exception) as e:
                # Redis is best-effort — we always have an in-memory fallback.
                # Log once on the *transition* to disconnected so prod logs
                # aren't spammed with the same warning every request.
                if self._connected:
                    logging.warning(
                        f"Redis unavailable, switching to in-memory rate "
                        f"limiter (sovereign fallback): {e}"
                    )
                self._connected = False  # Stop trying Redis until reconnect
        
        # Fallback to in-memory
        self._memory_storage[key] = [
            t for t in self._memory_storage[key] if current_time - t < window
        ]
        
        if len(self._memory_storage[key]) >= limit:
            return True
        
        self._memory_storage[key].append(current_time)
        return False
    
    async def get_stats(self) -> dict:
        """Get rate limiter statistics for admin dashboard."""
        if self._connected and self._redis:
            try:
                keys = await self._redis.keys("ratelimit:*")
                return {
                    "backend": "redis",
                    "active_keys": len(keys),
                    "status": "connected"
                }
            except:
                pass
        
        return {
            "backend": "memory",
            "active_keys": len(self._memory_storage),
            "status": "fallback"
        }

# Global rate limiter instance
rate_limiter = RedisRateLimiter()


class SecurityMiddleware:
    """Comprehensive security middleware - Pure ASGI implementation"""
    
    # Block common vulnerability scan paths - return 404 immediately
    BLOCKED_PATHS = [
        "/wp-admin", "/wp-login.php", "/wp-includes", "/wp-content",
        "/phpMyAdmin", "/phpmyadmin", "/pma",
        "/admin.php", "/administrator",
        "/.env", "/.git", "/.htaccess",
        "/config.php", "/configuration.php",
        "/xmlrpc.php",
        "/cgi-bin", "/scripts",
        "/backup", "/db", "/database",
        "/shell", "/cmd", "/command",
    ]
    
    SECURITY_HEADERS = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"x-xss-protection", b"1; mode=block"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
        (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
        (b"x-dns-prefetch-control", b"off"),
        (b"x-download-options", b"noopen"),
        (b"x-permitted-cross-domain-policies", b"none"),
        (b"content-security-policy", b"default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; style-src 'self' 'unsafe-inline'; img-src 'self' data: https: blob:; font-src 'self' data: https:; connect-src 'self' https: wss:; worker-src 'self' blob:; child-src 'self' blob:; frame-src 'self' https:; base-uri 'self'; form-action 'self';"),
    ]

    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        path = scope.get("path", "").lower()
        
        # Block vulnerability scan paths immediately - return 404
        if any(path.startswith(blocked) for blocked in self.BLOCKED_PATHS):
            response = JSONResponse(status_code=404, content={"detail": "Not found"})
            await response(scope, receive, send)
            return
        
        # Skip heavy processing for health check endpoints - critical for Kubernetes probes
        if path in ["/health", "/ready", "/", "/api/health"]:
            await self.app(scope, receive, send)
            return
        
        # Get client IP for rate limiting
        client_ip = "unknown"
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"x-forwarded-for":
                client_ip = header_value.decode().split(",")[0].strip()
                break
        if client_ip == "unknown":
            client = scope.get("client")
            if client:
                client_ip = client[0]
        
        # Skip rate limiting for OPTIONS (CORS preflight) — must NEVER be blocked
        if scope.get("method", "GET") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # iter 285.5 — bypass rate limit for internal-audit self-probes
        # The /api/admin/a2a/audit/widgets endpoint fires 60+ requests back
        # to other widget endpoints inside the pod. Each carries this header.
        # iter 322db — also bypass for X-Synthetic-Probe header used by the
        # endpoint heartbeat scheduler that pings every safe GET every 4 h.
        try:
            hdrs = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            if hdrs.get("x-internal-audit") == "true" and client_ip in ("127.0.0.1", "localhost", "::1"):
                await self.app(scope, receive, send)
                return
            if hdrs.get("x-synthetic-probe") == "heartbeat" and client_ip in ("127.0.0.1", "localhost", "::1"):
                await self.app(scope, receive, send)
                return
        except Exception:
            pass
        
        # Rate limiting - Use Redis-backed rate limiter
        # Skip rate limiting for health, system, and static endpoints
        skip_rate_limit = ["/translate", "/sitemap", "/robots", "/health", "/static", "/oroe",
                           "/api/health", "/api/platform/health", "/api/system/status",
                           "/api/aurem/agents", "/api/aurem/system", "/api/aurem/metrics",
                           "/api/aurem/activity", "/api/aurem/voice/config",
                           "/api/voice/", "/api/voice-analytics", "/api/push/vapid-key", "/ready",
                           # iter 284 — internal widget audit self-probes; admin-auth-gated
                           "/api/admin/a2a/audit/",
                           # iter 285.5 — admin-only observability endpoints should not be
                           # rate-limited during live polling (sidebar refreshes every 20-30s)
                           "/api/admin/a2a/sidebar/",
                           "/api/admin/a2a/widget-signal",
                           "/api/admin/transparency/",
                           "/api/admin/mtth/",
                           # iter 315f — QA pulse page polls latest summary on
                           # mount; admin-gated and read-only, safe to exempt.
                           "/api/qa/pulse/",
                           "/api/sentinel-anomaly/"]
        if not any(skip in path for skip in skip_rate_limit):
            # Determine rate limit based on endpoint
            if "/auth/login" in path or "/admin/login" in path:
                rate_key = f"login:{client_ip}"
                limit = LOGIN_RATE_LIMIT
                window = LOGIN_RATE_WINDOW
            else:
                rate_key = f"api:{client_ip}"
                limit = RATE_LIMIT_REQUESTS
                window = RATE_LIMIT_WINDOW
            
            # P0 FIX: Use Redis-backed rate limiter
            try:
                is_limited = await rate_limiter.is_rate_limited(rate_key, limit, window)
                if is_limited:
                    response = JSONResponse(
                        status_code=429,
                        content={"detail": "Too many requests. Please try again later."}
                    )
                    await response(scope, receive, send)
                    return
            except Exception as e:
                # Log but don't block request if rate limiter fails
                logging.warning(f"Rate limiter error: {e}")
        
        # Wrap send to inject security headers
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(self.SECURITY_HEADERS)
                message = {**message, "headers": headers}
            await send(message)
        
        await self.app(scope, receive, send_with_headers)


from starlette.responses import JSONResponse


# Input sanitization functions
def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent XSS and injection attacks"""
    if not text:
        return text
    if not isinstance(text, str):
        return str(text)
    # HTML escape
    text = html.escape(text)
    # Remove potential script tags
    text = re.sub(
        r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL
    )
    # Remove javascript: URLs
    text = re.sub(r"javascript:", "", text, flags=re.IGNORECASE)
    # Remove on* event handlers
    text = re.sub(r"\bon\w+\s*=", "", text, flags=re.IGNORECASE)
    return text


def sanitize_mongo_query(value):
    """
    Strip MongoDB query operators ($gt, $ne, $regex, etc.) from user-supplied values.
    Prevents NoSQL injection when values are used in find()/update() queries.
    Accepts str, dict, or list. Returns sanitized version.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return {k: sanitize_mongo_query(v) for k, v in value.items() if not k.startswith("$")}
    if isinstance(value, list):
        return [sanitize_mongo_query(item) for item in value]
    return value


_OBJECT_ID_RE = re.compile(r"^[a-fA-F0-9]{24}$")

def validate_object_id(oid: str) -> bool:
    """Validate that a string looks like a MongoDB ObjectId (24 hex chars)."""
    return bool(oid and isinstance(oid, str) and _OBJECT_ID_RE.match(oid))


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))

