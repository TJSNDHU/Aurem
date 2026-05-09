"""
bin_context.py — Middleware that resolves the calling tenant's BIN context
once per request and attaches it to `request.state.bin_ctx`.
═══════════════════════════════════════════════════════════════════════════
Routes use:
    from middleware.bin_context import get_bin_ctx
    ctx = get_bin_ctx(request)        # raises 401 if missing
    ctx.business_id, ctx.plan, ctx.services_unlocked, ctx.user_id, ctx.email

Lookup is purely from JWT — no DB hit per request. plan/services_unlocked
were baked into the JWT at login (or refreshed by a webhook). For routes
that need fresh state, call `services.plan_resolver.get_plan_state` directly.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import List, Optional

import jwt
from fastapi import HTTPException, Request
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


@dataclass
class BinCtx:
    user_id: str
    email: str
    business_id: str
    plan: str
    services_unlocked: List[str]
    is_admin: bool = False
    raw_claims: Optional[dict] = None


SKIP_PATHS = (
    "/api/health", "/api/sentinel/heartbeat", "/api/platform/health",
    "/api/auth/login", "/api/auth/register",
    "/api/platform/auth/login", "/api/platform/auth/register",
    "/api/platform/auth/forgot-password", "/api/platform/auth/reset-password",
    "/api/public/", "/api/catalog/services", "/api/website-builder/no-website",
    "/api/sentinel/client-error", "/api/pixel/",
)


class BinContextMiddleware:
    """Pure ASGI middleware — decodes JWT once, attaches BinCtx if present.
    Does NOT enforce — service_gate decorator does that. Missing/invalid
    token simply leaves bin_ctx = None.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "") or ""
        if not path.startswith("/api/") or path.startswith(SKIP_PATHS):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        auth = headers.get(b"authorization", b"").decode("latin-1")
        if not auth.startswith("Bearer "):
            await self.app(scope, receive, send)
            return
        token = auth[7:]
        secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""
        if not secret:
            await self.app(scope, receive, send)
            return
        try:
            claims = jwt.decode(token, secret, algorithms=["HS256"], options={"verify_exp": True})
        except Exception:
            await self.app(scope, receive, send)
            return

        ctx = BinCtx(
            user_id=claims.get("user_id") or claims.get("id") or claims.get("sub") or "",
            email=(claims.get("email") or "").lower(),
            business_id=claims.get("business_id") or "",
            plan=claims.get("plan") or "",
            services_unlocked=claims.get("services_unlocked") or [],
            is_admin=bool(claims.get("is_admin") or claims.get("is_super_admin")),
            raw_claims=claims,
        )
        # Stash on scope for routes to retrieve via request.state
        scope.setdefault("state", {})
        scope["state"]["bin_ctx"] = ctx
        await self.app(scope, receive, send)


def get_bin_ctx(request: Request, *, required: bool = True) -> Optional[BinCtx]:
    """Helper used by routes."""
    ctx: Optional[BinCtx] = getattr(request.state, "bin_ctx", None)
    if ctx is None and required:
        raise HTTPException(401, "auth required")
    return ctx
