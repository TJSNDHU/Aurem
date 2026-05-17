"""
Round 11-15 Security Sprint — Unified Auth Dependencies
========================================================
Single source of truth for FastAPI auth guards used to retrofit
zero-auth endpoints across the AUREM platform.

Why this exists:
  Rounds 7-15 of the security audit found 130+ endpoints that ship
  with no JWT verification. Adding ad-hoc auth in every router
  produces divergent implementations and breaks audit trails. This
  module centralises the four patterns we actually need:

    require_auth         → any verified JWT (returns payload dict)
    require_admin        → must be admin (via admin_guard.verify_admin)
    require_tenant_match → JWT tenant_id must match path/body tenant_id
                           (admin bypass automatic)
    constant_time_admin_key → constant-time AUREM_ADMIN_KEY compare

All helpers raise HTTPException(401/403) on failure. Plug into any
FastAPI route as either `Depends(require_auth)` or `await require_auth(authorization)`.
"""
from __future__ import annotations

import hmac
import os
from typing import Optional

import jwt
from fastapi import Header, HTTPException

from utils.admin_guard import is_admin_email, verify_admin as _verify_admin


def _decode(token: str) -> dict:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(500, "JWT secret not configured")
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, f"Invalid token: {e}")


async def require_auth(authorization: Optional[str] = Header(None)) -> dict:
    """Any verified JWT — returns decoded payload."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or malformed Authorization header")
    payload = _decode(authorization.split(" ", 1)[1].strip())
    if is_admin_email(payload.get("email")) or payload.get("role") in ("admin", "super_admin"):
        payload["is_admin"] = True
    return payload


async def require_admin(authorization: Optional[str] = Header(None)) -> dict:
    """Must be admin (JWT with admin claim/role/whitelist email)."""
    return _verify_admin(authorization)


async def require_admin_or_key(
    authorization: Optional[str] = Header(None),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
) -> dict:
    """Admin via JWT OR constant-time match against AUREM_ADMIN_KEY env var."""
    if x_admin_key:
        expected = (os.environ.get("AUREM_ADMIN_KEY") or "").strip()
        if expected and hmac.compare_digest(x_admin_key, expected):
            return {"admin_key": "valid", "is_admin": True}
    return _verify_admin(authorization)


def enforce_tenant_match(payload: dict, tenant_id: str) -> None:
    """Caller must own tenant or be admin. Raises 403 otherwise."""
    if payload.get("is_admin") or payload.get("is_super_admin"):
        return
    caller = payload.get("tenant_id") or payload.get("business_id")
    if not caller or caller != tenant_id:
        raise HTTPException(403, "Tenant mismatch")
