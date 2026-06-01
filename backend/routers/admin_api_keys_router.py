"""
routers/admin_api_keys_router.py — iter D-59 Part B

Admin-only management of Public AUREM API keys.

All endpoints require admin Bearer JWT:
  GET  /api/admin/public-api-keys                       list every key (no secret)
  POST /api/admin/public-api-keys/issue                 mint a new key (secret returned ONCE)
  POST /api/admin/public-api-keys/{key_id}/revoke       revoke
  GET  /api/admin/public-api-keys/{key_id}/usage?days=7 endpoint breakdown + total
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/public-api-keys", tags=["public-api-keys"])


def set_db(database) -> None:
    from services import aurem_public_api as _svc
    _svc.set_db(database)


async def _require_admin(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing_bearer_token")
    token = authorization.split(" ", 1)[1]
    try:
        import jwt as _jwt
        from config import JWT_SECRET, JWT_ALGORITHM
        payload = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if (payload.get("is_admin") or payload.get("is_super_admin") or
                payload.get("role") in ("admin", "super_admin", "founder")):
            return payload.get("email") or payload.get("sub") or "admin"
    except Exception:
        pass
    raise HTTPException(403, "admin_required")


class IssueBody(BaseModel):
    name:           str       = Field("founder primary", max_length=80)
    owner_email:    str       = Field(..., min_length=3, max_length=120)
    scopes:         list[str] = Field(default_factory=lambda: [
        "ora_chat", "cto_chat", "leads_read",
    ])
    rate_per_min:   int       = Field(30, ge=1, le=600)
    rate_per_day:   int       = Field(5000, ge=1, le=1_000_000)


@router.get("")
async def list_all(authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.aurem_public_api import list_keys
    return {"ok": True, "items": await list_keys()}


@router.post("/issue")
async def issue(body: IssueBody,
                  authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.aurem_public_api import issue_key, DEFAULT_SCOPES
    bad = [s for s in body.scopes if s not in DEFAULT_SCOPES]
    if bad:
        raise HTTPException(400, f"invalid_scopes: {bad}")
    res = await issue_key(
        name=body.name, owner_email=body.owner_email,
        scopes=body.scopes,
        rate_per_min=body.rate_per_min,
        rate_per_day=body.rate_per_day,
    )
    return res    # contains {ok, secret, key}


@router.post("/{key_id}/revoke")
async def revoke(key_id: str = Path(..., min_length=8, max_length=40),
                   authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.aurem_public_api import revoke as _rev
    return await _rev(key_id)


@router.get("/{key_id}/usage")
async def usage(key_id: str = Path(..., min_length=8, max_length=40),
                  days: int = Query(7, ge=1, le=90),
                  authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.aurem_public_api import usage_for
    return {"ok": True, **(await usage_for(key_id, days=days))}
