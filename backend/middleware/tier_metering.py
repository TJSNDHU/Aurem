"""
AUREM Tier Metering Middleware — Pure ASGI Implementation
Enforces API rate limits based on tenant subscription tier.
Converted from BaseHTTPMiddleware to pure ASGI to avoid Starlette ExceptionGroup crashes.
"""
import os
import time
import json
import logging
from collections import defaultdict, deque
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

# Bug-fix #23 — pull the real tier from the X-Tier header (set by tenant
# guard / auth middleware) or fall back to looking it up in the tenant
# context. The middleware previously hard-coded "professional" so a
# tenant on the $0 free plan got the $97 starter quota — silently.
# Bug-fix #24 — bound the per-tenant counter dict so a flood of distinct
# tenant_id values (or attackers spoofing headers) can't grow RAM
# without limit. We also bound the per-tenant deque so a single chatty
# tenant never holds more than `limit` timestamps.
_MAX_TRACKED_TENANTS = 50_000


def _resolve_tier_from_scope(scope: Scope, headers: dict) -> str:
    """Resolve tier from headers / scope state. Falls back to free, not
    professional, so an un-tiered request gets the safest cap."""
    # Header set by tenant_guard / auth layer.
    raw_tier = headers.get(b"x-tier")
    if raw_tier:
        t = raw_tier.decode("utf-8", errors="replace").strip().lower()
        if t in TIER_LIMITS:
            return t
    # Fallback: scope state populated by auth middleware
    state = scope.get("state") or {}
    t = (state.get("tier") or "").strip().lower() if isinstance(state, dict) else ""
    if t in TIER_LIMITS:
        return t
    return "free"


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
        # Bug-fix #23 — use the actual tier instead of always 'professional'.
        tier = _resolve_tier_from_scope(scope, headers)
        limit = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
        now = time.time()
        window = 60  # 1 minute

        # Bug-fix #24 — cap the tracked-tenant dict size. Drop the oldest
        # entry when we exceed the cap so memory stays bounded under
        # tenant-id churn / header spoofing attempts.
        if (tenant_id not in self._counters
                and len(self._counters) >= _MAX_TRACKED_TENANTS):
            try:
                self._counters.pop(next(iter(self._counters)))
            except StopIteration:
                pass

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
