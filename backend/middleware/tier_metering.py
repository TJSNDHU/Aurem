"""
AUREM Tier Metering Middleware — Pure ASGI Implementation
Enforces API rate limits based on tenant subscription tier.
Converted from BaseHTTPMiddleware to pure ASGI to avoid Starlette ExceptionGroup crashes.
"""
import os
import time
import json
import logging
from collections import defaultdict
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Skip paths
SKIP_PATHS = frozenset([
    "/api/health", "/health", "/ready", "/api/platform/health",
    "/api/auth/login", "/api/auth/register",
    "/favicon.ico", "/robots.txt",
])

# Tier limits (requests per minute)
TIER_LIMITS = {
    "free": 60,
    "starter": 300,
    "professional": 1000,
    "enterprise": 5000,
}

DEFAULT_TIER = "professional"


class TierMeteringMiddleware:
    """Pure ASGI middleware for tier-based rate metering."""

    def __init__(self, app: ASGIApp):
        self.app = app
        self._counters = defaultdict(list)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Skip non-metered paths
        if path in SKIP_PATHS or not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        # Extract tenant from headers
        headers = dict(scope.get("headers", []))
        tenant_id = None
        for key, value in headers.items():
            if key == b"x-tenant-id":
                tenant_id = value.decode("utf-8", errors="replace")
                break

        if not tenant_id:
            await self.app(scope, receive, send)
            return

        # Check rate limit
        tier = DEFAULT_TIER
        limit = TIER_LIMITS.get(tier, TIER_LIMITS[DEFAULT_TIER])
        now = time.time()
        window = 60  # 1 minute

        # Clean old entries
        self._counters[tenant_id] = [
            t for t in self._counters[tenant_id] if t > now - window
        ]

        if len(self._counters[tenant_id]) >= limit:
            # Rate limited - return 429
            body = json.dumps({
                "detail": "Rate limit exceeded for your tier",
                "tier": tier,
                "limit": limit,
                "window_seconds": window,
            }).encode("utf-8")
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"retry-after", str(window).encode()],
                ],
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })
            return

        self._counters[tenant_id].append(now)

        # Add metering headers to response
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                remaining = max(0, limit - len(self._counters.get(tenant_id, [])))
                headers.extend([
                    [b"x-ratelimit-limit", str(limit).encode()],
                    [b"x-ratelimit-remaining", str(remaining).encode()],
                    [b"x-ratelimit-reset", str(int(now + window)).encode()],
                ])
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            raise
