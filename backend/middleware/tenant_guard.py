"""
AUREM Tenant Guard — Async-safe Global Tenant Scoping

Uses Python contextvars for async-safe per-request tenant isolation.
Every authenticated request automatically carries a tenant_id that
the ScopedDB layer reads to filter all database operations.
"""

import os
import logging
from contextvars import ContextVar
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import jwt

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"

# ─── Async-safe context variables ───────────────────────────────
_tenant_id_var: ContextVar[str | None] = ContextVar("tenant_id", default=None)
_is_admin_var: ContextVar[bool] = ContextVar("is_admin", default=False)
_user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


class TenantGuard:
    """Static accessor for the current request's tenant context."""

    @staticmethod
    def set(tenant_id: str, is_admin: bool = False, user_id: str | None = None):
        _tenant_id_var.set(tenant_id)
        _is_admin_var.set(is_admin)
        _user_id_var.set(user_id or tenant_id)

    @staticmethod
    def get() -> str | None:
        return _tenant_id_var.get()

    @staticmethod
    def is_admin() -> bool:
        return _is_admin_var.get()

    @staticmethod
    def user_id() -> str | None:
        return _user_id_var.get()

    @staticmethod
    def require() -> str:
        tid = _tenant_id_var.get()
        if not tid:
            raise HTTPException(403, "Tenant context required")
        return tid

    @staticmethod
    def clear():
        _tenant_id_var.set(None)
        _is_admin_var.set(False)
        _user_id_var.set(None)


# ─── Paths exempt from tenant scoping ──────────────────────────
EXEMPT_PATHS = {
    "/api/health",
    "/api/auth/login",
    "/api/auth/register",
    "/api/push/vapid-key",
    "/api/admin/pulse",
    "/api/admin/pulse/snapshot",
    "/api/admin/pulse/status",
}

EXEMPT_PREFIXES = (
    "/api/public/",
    "/api/pwa/",
    "/api/repair/webhook/",
    "/api/intelligence/webhook/",
    "/api/webhook/shopify/",
    "/api/shopify/callback",
    "/api/shopify-app/",
    "/api/attribution/click/",
    "/api/attribution/pixel",
    "/docs",
    "/openapi",
)


class TenantGuardMiddleware(BaseHTTPMiddleware):
    """
    Extracts tenant_id from JWT on every request and stores it
    in async-safe contextvars. The ScopedDB proxy reads this
    automatically to scope all database queries.
    """

    async def dispatch(self, request: Request, call_next):
        TenantGuard.clear()

        path = request.url.path

        # Skip public / exempt routes
        if path in EXEMPT_PATHS or path.startswith(EXEMPT_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            try:
                # Bug-fix: previous code passed options={"verify_exp": False}
                # which made TenantGuard happily honour months-old expired
                # tokens. Any route trusting request.state.tenant_id was
                # therefore reachable with a dead token. Enforce expiry
                # like the rest of the auth layer does.
                payload = jwt.decode(
                    token,
                    JWT_SECRET,
                    algorithms=[JWT_ALGORITHM],
                )
                user_id = payload.get("user_id")
                is_admin = payload.get("is_admin", False)
                # tenant_id: explicit in JWT → fall back to user_id
                tenant_id = payload.get("tenant_id") or user_id

                if tenant_id:
                    TenantGuard.set(
                        tenant_id=tenant_id,
                        is_admin=is_admin,
                        user_id=user_id,
                    )
                    # Also store on request.state for route-level access
                    request.state.tenant_id = tenant_id
                    request.state.is_admin = is_admin

            except jwt.ExpiredSignatureError:
                # Expired token: leave TenantGuard cleared and let the
                # downstream auth dependency surface the proper 401.
                logger.debug("[TenantGuard] Expired token rejected")
            except jwt.InvalidTokenError:
                pass
            except Exception as e:
                logger.debug(f"[TenantGuard] JWT decode error: {e}")

        response = await call_next(request)
        TenantGuard.clear()
        return response
