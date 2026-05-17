"""Production-grade middlewares extracted from the old monolithic server.py.

Each middleware is self-contained and receives the FastAPI app as its sole
dependency at registration time. Register in this order so security headers
wrap every other response (including the usage-metering tail):

    from bootstrap.middlewares import register_security_headers, \
        register_jwt_blocklist, register_usage_metering
    register_security_headers(app)
    register_jwt_blocklist(app)
    register_usage_metering(app, db_getter=lambda: server.db,
                            jwt_secret=JWT_SECRET, jwt_alg=JWT_ALGORITHM)
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from fastapi import Request


# ══════════════════════════════════════════════════════════════════════
# 1. Security headers — ASGI-level (wraps every response)
# ══════════════════════════════════════════════════════════════════════
class SecurityHeadersMiddleware:
    """Adds production-grade security headers to every response.

    Fixes Shannon Runner findings:
      - HSTS missing (CWE-319)
      - X-Frame-Options missing (CWE-1021)
      - X-Content-Type-Options missing (CWE-693)
      - Referrer-Policy missing (CWE-200)
      - Content-Security-Policy missing (CWE-79)
      - Permissions-Policy missing (CWE-693)
      - X-Powered-By / Server banner disclosure (CWE-200)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                # Strip existing copies of headers we're about to set (avoid duplicates)
                existing = [
                    (k, v) for k, v in message.get("headers", [])
                    if k.lower() not in {
                        b"strict-transport-security", b"x-frame-options",
                        b"x-content-type-options", b"x-xss-protection",
                        b"referrer-policy", b"permissions-policy",
                        b"content-security-policy", b"x-powered-by", b"server",
                    }
                ]
                existing.extend([
                    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
                    (b"x-frame-options", b"SAMEORIGIN"),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-xss-protection", b"1; mode=block"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"permissions-policy",
                     b"camera=(), microphone=(), geolocation=(), interest-cohort=()"),
                    # CSP: Report-Only first so we don't break the SPA. Promote to
                    # enforcing CSP once frontend is fully compliant.
                    (b"content-security-policy-report-only",
                     b"default-src 'self'; "
                     b"script-src 'self' 'unsafe-inline' 'unsafe-eval' https://js.stripe.com https://checkout.stripe.com; "
                     b"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                     b"font-src 'self' https://fonts.gstatic.com data:; "
                     b"img-src 'self' data: blob: https:; "
                     b"connect-src 'self' https: wss:; "
                     b"frame-src 'self' https://js.stripe.com https://hooks.stripe.com; "
                     b"frame-ancestors 'self'; "
                     b"base-uri 'self'; "
                     b"form-action 'self';"),
                    # Generic, non-fingerprintable Server banner
                    (b"server", b"aurem"),
                ])
                message = {**message, "headers": existing}
            await send(message)

        await self.app(scope, receive, send_with_headers)


def register_security_headers(app) -> None:
    """Attach SecurityHeadersMiddleware to the FastAPI app."""
    app.add_middleware(SecurityHeadersMiddleware)


# ══════════════════════════════════════════════════════════════════════
# 2. JWT blocklist — reject revoked tokens via MongoDB lookup (iter 322y)
# ══════════════════════════════════════════════════════════════════════
class JWTBlocklistMiddleware(BaseHTTPMiddleware):
    """Check every Bearer token against MongoDB blocklist. Revoked tokens get 401."""

    async def dispatch(self, request, call_next):
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1]
            try:
                import jwt as pyjwt
                payload = pyjwt.decode(token, options={"verify_signature": False})
                jti = payload.get("jti")
                if jti:
                    from services.jwt_blocklist import is_blocked
                    if await is_blocked(jti):
                        return JSONResponse(
                            status_code=401,
                            content={"detail": "Token has been revoked"},
                        )
            except Exception:
                pass
        return await call_next(request)


def register_jwt_blocklist(app) -> None:
    """Attach JWTBlocklistMiddleware to the FastAPI app."""
    app.add_middleware(JWTBlocklistMiddleware)


# ══════════════════════════════════════════════════════════════════════
# 3. Usage metering — increment AI-action counters for subscription tiers
# ══════════════════════════════════════════════════════════════════════
METERED_PREFIXES = [
    "/api/aurem/chat",
    "/api/voice/",
    "/api/ora/",
    "/api/ghost/",
    "/api/geo/",
    "/api/universal/webhooks",
]


def register_usage_metering(app, db_getter, jwt_secret: str, jwt_alg: str = "HS256") -> None:
    """Register the usage-metering HTTP middleware.

    Parameters
    ----------
    app : FastAPI
    db_getter : callable returning the live motor db (or None during boot)
    jwt_secret : secret used to decode Bearer tokens (for tenant_id extraction)
    jwt_alg    : algorithm (default HS256)
    """

    @app.middleware("http")
    async def usage_metering_middleware(request: Request, call_next):  # noqa: F841
        response = await call_next(request)
        # Only meter successful POST/PUT on AI action paths
        if request.method in ("POST", "PUT") and response.status_code < 400:
            path = request.url.path
            if any(path.startswith(p) for p in METERED_PREFIXES):
                try:
                    auth = request.headers.get("Authorization", "")
                    if auth.startswith("Bearer "):
                        import jwt as _jwt
                        payload = _jwt.decode(
                            auth.split(" ")[1], jwt_secret, algorithms=[jwt_alg]
                        )
                        tenant_id = payload.get(
                            "tenant_id", payload.get("user_id", payload.get("id"))
                        )
                        db = db_getter()
                        if tenant_id and db is not None:
                            from shared.commercial.usage_service import (
                                get_usage_meter,
                            )
                            meter = get_usage_meter(db)
                            if "chat" in path or "ora" in path:
                                action = "llm_call"
                            elif "voice" in path:
                                action = "v2v_session"
                            elif "webhook" in path:
                                action = "webhook_processed"
                            elif "ghost" in path:
                                action = "ghost_action"
                            else:
                                action = "geo_check"
                            await meter.increment(tenant_id, action)
                except Exception:
                    # Metering must never block requests
                    pass
        return response


__all__ = [
    "SecurityHeadersMiddleware",
    "JWTBlocklistMiddleware",
    "METERED_PREFIXES",
    "register_security_headers",
    "register_jwt_blocklist",
    "register_usage_metering",
]
