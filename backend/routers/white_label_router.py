"""
White-Label Admin Router — iter 322ar
========================================
REST surface for Enterprise tenants to customise branding (logo,
brand name, primary colour, custom CNAME). Reads/writes through
`services.white_label`.

Endpoints:
  GET  /api/admin/branding/{bin_id}        — current branding
  POST /api/admin/branding/{bin_id}        — update branding
  GET  /api/admin/branding/{bin_id}/cname  — DNS instructions
"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request, Body

try:
    import jwt
except Exception:
    jwt = None

from services import white_label

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/branding", tags=["white-label"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database
    white_label.set_db(database)


async def _require_admin(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    if jwt is None:
        raise HTTPException(503, "jwt module unavailable")
    secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""
    try:
        claims = jwt.decode(auth[7:], secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    email = (claims.get("email") or "").lower()
    user_id = claims.get("user_id") or claims.get("sub") or claims.get("id")
    if _db is None:
        raise HTTPException(503, "DB not ready")
    if email:
        user = await _db.users.find_one(
            {"email": email},
            {"_id": 0, "email": 1, "is_admin": 1, "is_super_admin": 1, "role": 1},
        )
    elif user_id:
        user = await _db.users.find_one(
            {"$or": [{"id": user_id}, {"user_id": user_id}]},
            {"_id": 0, "email": 1, "is_admin": 1, "is_super_admin": 1, "role": 1},
        )
    else:
        user = None
    if not user or not (
        user.get("is_admin") or user.get("is_super_admin")
        or user.get("role") in ("admin", "super_admin")
    ):
        raise HTTPException(403, "Admin access required")
    return {"email": email or user.get("email", "")}


@router.get("/{bin_id}")
async def get_branding(bin_id: str, request: Request):
    await _require_admin(request)
    return {"ok": True, "branding": await white_label.get_branding(bin_id)}


@router.post("/{bin_id}")
async def set_branding(bin_id: str, body: Dict[str, Any] = Body(...), request: Request = None):
    await _require_admin(request)
    if not isinstance(body, dict):
        raise HTTPException(400, "JSON object required")
    result = await white_label.set_branding(bin_id, body)
    if isinstance(result, dict) and result.get("error"):
        # Enterprise-tier gate → 402 Payment Required
        if "Enterprise" in str(result.get("error", "")):
            raise HTTPException(402, result["error"])
        raise HTTPException(400, result["error"])
    return {"ok": True, "branding": result}


@router.get("/{bin_id}/cname")
async def get_cname(bin_id: str, request: Request):
    await _require_admin(request)
    return {"ok": True, "cname": await white_label.get_cname_instructions(bin_id)}
