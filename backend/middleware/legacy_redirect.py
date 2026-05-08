"""
Legacy URL Redirect Middleware — SEO-safe URL migration
"""
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

logger = logging.getLogger(__name__)

class LegacyRedirectMiddleware:
    """Handle 301 redirects for old Wix URLs - Pure ASGI middleware"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        path = scope.get("path", "")
        
        # Skip health check endpoints - critical for Kubernetes probes
        if path in ["/health", "/ready", "/", "/api/health"]:
            await self.app(scope, receive, send)
            return
        
        # Skip API routes - don't redirect them
        if path.startswith("/api/"):
            await self.app(scope, receive, send)
            return
        
        # Check exact match redirects
        LEGACY_REDIRECTS = {}  # Define empty if no redirects configured
        LEGACY_PREFIX_REDIRECTS = []
        if path in LEGACY_REDIRECTS:
            response = RedirectResponse(url=LEGACY_REDIRECTS[path], status_code=301)
            await response(scope, receive, send)
            return
        
        # Check prefix redirects
        for prefix in LEGACY_PREFIX_REDIRECTS:
            if path.startswith(prefix):
                response = RedirectResponse(url="/", status_code=301)
                await response(scope, receive, send)
                return
        
        await self.app(scope, receive, send)

