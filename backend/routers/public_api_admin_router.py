"""
routers/public_api_admin_router.py — iter D-59 Part B

Admin-only endpoints for managing AUREM public API keys.

  GET  /api/admin/public-api/keys              → list
  POST /api/admin/public-api/keys              → issue new (returns secret ONCE)
  POST /api/admin/public-api/keys/{id}/revoke
  GET  /api/admin/public-api/keys/{id}/usage   → 7-day usage stats
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/admin/public-api",
                    tags=["aurem-public-api-admin"])


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
    name:         str = Field(..., min_length=2, max_length=80)
    owner_email:  str = Field(..., min_length=4, max_length=120)
    scopes:       list[str] = Field(default_factory=lambda:
                                       ["ora_chat", "cto_chat", "leads_read"])
    rate_per_min: int = Field(30,   ge=1, le=600)
    rate_per_day: int = Field(5000, ge=10, le=100000)


@router.get("/keys")
async def list_keys(authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.aurem_public_api import list_keys as _list
    items = await _list()
    return {"ok": True, "items": items, "count": len(items)}


@router.post("/keys")
async def issue_key(body: IssueBody,
                     authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.aurem_public_api import issue_key as _issue
    return await _issue(
        name=body.name, owner_email=body.owner_email,
        scopes=body.scopes,
        rate_per_min=body.rate_per_min,
        rate_per_day=body.rate_per_day,
    )


@router.post("/keys/{key_id}/revoke")
async def revoke_key(key_id: str = Path(..., min_length=8, max_length=80),
                      authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.aurem_public_api import revoke as _revoke
    return await _revoke(key_id)


@router.get("/keys/{key_id}/usage")
async def key_usage(key_id: str = Path(..., min_length=8, max_length=80),
                     days: int = Query(7, ge=1, le=90),
                     authorization: str = Header(None)) -> dict[str, Any]:
    await _require_admin(authorization)
    from services.aurem_public_api import usage_for
    return {"ok": True, "key_id": key_id,
             "usage": await usage_for(key_id, days=days)}
