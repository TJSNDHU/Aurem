"""
Unified Admin Guard — single source of truth for admin authentication.

Why this exists:
  The codebase historically had two divergent auth flows:
    1. /api/auth/login + /api/auth/google-oauth (routes/auth.py) — minted
       JWTs WITH `is_admin` / `is_super_admin` claims for whitelisted emails.
    2. /api/platform/auth/login (routers/platform_auth_router.py) — minted
       JWTs with ONLY `email` + `role`, never an `is_admin` claim.

  Result: a real admin (e.g. admin@reroots.ca) who authenticated via the
  platform endpoint received a token that admin routes rejected with 403,
  producing a Sentinel "403 Forbidden storm" on
  /api/admin/deploy-drift and /api/admin/pillars-map/overview.

This guard fixes that by accepting any of:
  * an explicit admin claim in the token, OR
  * a token whose `email` claim matches ADMIN_EMAIL_WHITELIST, OR
  * a token whose `role` claim is "admin" or "super_admin".

Usage in routers:
    from utils.admin_guard import verify_admin
    @router.get("")
    async def my_admin_route(authorization: Optional[str] = Header(None)):
        verify_admin(authorization)
        ...
"""
from __future__ import annotations

import os
from typing import Optional

import jwt
from fastapi import HTTPException


# Single canonical whitelist — kept in sync with routes/auth.py.
# Importing from routes/auth.py would create a circular dep at startup,
# so we duplicate the literal list here.
ADMIN_EMAIL_WHITELIST = [
    "admin@reroots.ca",
    "teji.ss1986@gmail.com",
]


def _normalize_whitelist() -> set[str]:
    return {e.strip().lower() for e in ADMIN_EMAIL_WHITELIST if e}


def is_admin_email(email: Optional[str]) -> bool:
    if not email:
        return False
    return email.strip().lower() in _normalize_whitelist()


def decode_token(token: str, secret: Optional[str] = None, algorithm: str = "HS256") -> dict:
    """Decode a JWT, raising 401 on any failure."""
    key = secret or os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""
    if not key:
        raise HTTPException(status_code=500, detail="JWT secret not configured")
    try:
        return jwt.decode(token, key, algorithms=[algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def verify_admin(
    authorization: Optional[str],
    *,
    secret: Optional[str] = None,
    algorithm: str = "HS256",
) -> dict:
    """Validate an Authorization header and require admin privileges.

    Accepts admins via four paths (any one passes):
      1. `is_admin` claim is True
      2. `is_super_admin` claim is True
      3. `role` claim is "admin" or "super_admin"
      4. `email` claim is in ADMIN_EMAIL_WHITELIST

    Returns the decoded JWT payload, with `is_admin: True` synthesized
    when path #3/#4 is used so downstream code can rely on it.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization.split(" ", 1)[1].strip()
    payload = decode_token(token, secret=secret, algorithm=algorithm)

    if payload.get("is_admin") or payload.get("is_super_admin"):
        return payload

    role = (payload.get("role") or "").lower()
    if role in ("admin", "super_admin"):
        payload["is_admin"] = True
        payload["_admin_via"] = "role"
        return payload

    if is_admin_email(payload.get("email")):
        payload["is_admin"] = True
        payload["_admin_via"] = "whitelist"
        return payload

    raise HTTPException(status_code=403, detail="Admin access required")
