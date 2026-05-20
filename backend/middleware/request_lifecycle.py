"""
Request Lifecycle Middleware — DB Readiness, Brand Detection, Tenant Guard, Security Headers
Extracted from server.py during modularization.
"""
import os
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi import Request

logger = logging.getLogger(__name__)

# ============= DATABASE READINESS MIDDLEWARE =============
# Returns 503 for API requests if database isn't ready yet

class DatabaseReadinessMiddleware:
    """Check database readiness - Pure ASGI middleware"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        path = scope.get("path", "")
        
        # Skip health check endpoints
        if path in ["/health", "/api/health", "/ready", "/"]:
            await self.app(scope, receive, send)
            return
        
        # Bug-fix #22: `db` was referenced here without ever being
        # imported, so this ENTIRE guard raised NameError on the first
        # non-health API request — which the ASGI stack catches as a
        # 500 OR (depending on uvicorn config) lets through. Either way
        # the readiness gate was dead code. Pull `db` from `server`
        # lazily so we don't introduce an import cycle.
        if path.startswith("/api"):
            try:
                from server import db as _db
            except Exception:
                _db = None
            if _db is None:
                response = JSONResponse(
                    status_code=503,
                    content={"detail": "Service is starting up, please retry in a few seconds"}
                )
                await response(scope, receive, send)
                return
        
        await self.app(scope, receive, send)


# ============= BRAND DETECTION MIDDLEWARE =============
# Multi-tenant: Detects brand from host header for lavelabianca.com vs aurem.live
class BrandDetectionMiddleware:
    """Multi-tenant brand detection - Pure ASGI middleware"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        path = scope.get("path", "")
        
        # Skip health check endpoints immediately - critical for Kubernetes probes
        if path in ["/health", "/ready", "/", "/api/health"]:
            await self.app(scope, receive, send)
            return
        
        # Detect brand from headers
        host = ""
        origin = ""
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"host":
                host = header_value.decode().lower()
            elif header_name == b"origin":
                origin = header_value.decode().lower()
        
        # Set brand in scope state
        if "lavelabianca" in host or "lavelabianca" in origin:
            brand = "lavela"
        else:
            brand = "reroots"
        
        # Store brand in scope for route handlers
        scope["state"] = scope.get("state", {})
        scope["state"]["brand"] = brand
        
        # Wrap send to add brand header to response
        async def send_with_brand(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-brand", brand.encode()))
                message = {**message, "headers": headers}
            await send(message)
        
        await self.app(scope, receive, send_with_brand)


# ============= TENANT GUARD MIDDLEWARE (Global Scoping) =============
# Uses contextvars for async-safe per-request tenant isolation.
# ScopedDB reads TenantGuard context to auto-filter every query.
try:
    from middleware.tenant_guard import TenantGuardMiddleware
    logging.info("[STARTUP] ✓ TenantGuard Middleware registered — fortress-grade tenant isolation")
except Exception as e:
    logging.warning(f"[STARTUP] TenantGuard Middleware not registered: {e}")

# ============= SECURITY HEADER MIDDLEWARE =============
