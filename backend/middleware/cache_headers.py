"""
Cache Headers Middleware — Smart caching for API responses
Extracted from server.py during modularization.
"""
import logging
from starlette.responses import Response as StarletteResponse

logger = logging.getLogger(__name__)


class CacheHeadersMiddleware:
    """Add appropriate cache headers for different response types - Pure ASGI middleware"""

    LONG_CACHE_PATHS = [
        "/api/store-settings",
        "/api/referral-program",
        "/api/skincare-dictionary",
        "/api/ingredients",
        "/api/site-content",
        "/api/public/",
    ]

    PRODUCT_CACHE_PATHS = [
        "/api/products",
        "/api/featured-products",
    ]

    SHORT_CACHE_PATHS = [
        "/api/exchange-rates",
        "/api/currency/rates",
    ]

    NO_CACHE_PATHS = [
        "/api/auth",
        "/api/cart",
        "/api/checkout",
        "/api/admin",
        "/api/user",
        "/api/orders",
        "/api/payments",
        "/api/chat",
    ]

    BLOCKED_PATHS = [
        "/app/memory/",
        "/.env",
        "/backend/.env",
        "/frontend/.env",
        "/AUDIT_REPORT",
        "/PRD.md",
        "/SECRETS_POLICY",
        "/.secrets/",
    ]

    IMMUTABLE_EXTENSIONS = [
        ".woff", ".woff2", ".ttf", ".otf", ".eot",
        ".avif", ".webp", ".png", ".jpg", ".jpeg", ".svg", ".ico",
        ".js", ".css", ".map",
    ]

    IMMUTABLE_PATHS = ["/static/", "/icons/"]

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        if any(blocked in path for blocked in self.BLOCKED_PATHS):
            response = StarletteResponse(
                content='{"error": "Forbidden", "message": "Access to this resource is not allowed"}',
                status_code=403,
                media_type="application/json"
            )
            await response(scope, receive, send)
            return

        if path in ["/health", "/ready", "/", "/api/health", "/api/platform/health"]:
            await self.app(scope, receive, send)
            return

        cache_header = None

        if method == "GET":
            if any(path.startswith(p) for p in self.IMMUTABLE_PATHS):
                cache_header = b"public, max-age=31536000, immutable"
            elif any(path.endswith(ext) for ext in self.IMMUTABLE_EXTENSIONS):
                cache_header = b"public, max-age=31536000, immutable"
            elif any(path.startswith(p) for p in self.NO_CACHE_PATHS):
                cache_header = b"no-store, no-cache, must-revalidate, private"
            elif any(path.startswith(p) for p in self.LONG_CACHE_PATHS):
                cache_header = b"public, max-age=300, stale-while-revalidate=3600"
            elif any(path.startswith(p) for p in self.PRODUCT_CACHE_PATHS):
                cache_header = b"public, max-age=30, must-revalidate"
            elif any(path.startswith(p) for p in self.SHORT_CACHE_PATHS):
                cache_header = b"public, max-age=60, stale-while-revalidate=300"
            elif path in ["/api/health", "/health", "/api/platform/health"]:
                cache_header = b"public, max-age=10"
            else:
                cache_header = b"private, max-age=30"
        else:
            cache_header = b"no-store"

        async def send_with_cache(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                status = message.get("status", 200)
                if status >= 400:
                    headers.append((b"cache-control", b"no-store"))
                else:
                    headers.append((b"cache-control", cache_header))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_cache)