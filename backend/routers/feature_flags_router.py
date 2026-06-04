"""
feature_flags_router.py — iter D-63
====================================
Admin-only CRUD over Mongo-backed feature flags.

Endpoints:
    GET    /api/admin/feature-flags             list all flags
    GET    /api/admin/feature-flags/{flag}      get one (with current is_enabled
                                                computed for the founder tenant)
    POST   /api/admin/feature-flags             upsert
    DELETE /api/admin/feature-flags/{flag}      remove
    POST   /api/admin/feature-flags/{flag}/check?tenant=...
                                                debug — see what is_enabled
                                                returns for a specific tenant
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from services import feature_flags as ff
from utils.admin_guard import verify_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/feature-flags", tags=["Feature Flags"])


def set_db(db):
    ff.set_db(db)


class _FlagBody(BaseModel):
    flag: str = Field(..., min_length=1, max_length=64)
    enabled: bool = True
    rollout_pct: int = Field(100, ge=0, le=100)
    tenants: List[str] = Field(default_factory=list)
    description: str = ""


@router.get("")
async def list_all(authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    return {"ok": True, "flags": await ff.list_flags()}


@router.get("/{flag}")
async def get_one(flag: str, authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    flags = [f for f in await ff.list_flags() if f.get("flag") == flag]
    if not flags:
        raise HTTPException(404, f"flag {flag!r} not found")
    return {"ok": True, "flag": flags[0]}


@router.post("")
async def upsert(body: _FlagBody, authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    try:
        doc = await ff.set_flag(
            body.flag,
            enabled=body.enabled,
            rollout_pct=body.rollout_pct,
            tenants=body.tenants,
            description=body.description,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    return {"ok": True, "flag": doc}


@router.delete("/{flag}")
async def delete(flag: str, authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    deleted = await ff.delete_flag(flag)
    if not deleted:
        raise HTTPException(404, f"flag {flag!r} not found")
    return {"ok": True, "deleted": flag}


@router.get("/{flag}/check")
async def check(
    flag: str,
    tenant: str = Query(""),
    authorization: Optional[str] = Header(None),
):
    """Debug helper — show what is_enabled() returns for a given tenant."""
    verify_admin(authorization)
    enabled = await ff.is_enabled(flag, tenant)
    return {"ok": True, "flag": flag, "tenant": tenant or "(none)", "enabled": enabled}
