"""
routers/dashboard_bootstrap_router.py — iter 326l
═══════════════════════════════════════════════════════════════════════════
Admin endpoints to bootstrap a tenant's dashboard from all-zero to
real-data state. Pairs with services/dashboard_bootstrap.py.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services import dashboard_bootstrap as svc

logger = logging.getLogger(__name__)

router = APIRouter()
_db = None


def set_db(database) -> None:
    global _db
    _db = database


class BootstrapRequest(BaseModel):
    tenant_id:     str             = Field(..., min_length=3, max_length=64)
    domain:        str             = Field(..., min_length=4, max_length=200)
    email:         Optional[str]   = None
    business_name: Optional[str]   = None
    force_scan:    bool            = True


@router.post("/api/admin/tenant/bootstrap-dashboard")
async def bootstrap_tenant(body: BootstrapRequest):
    """Bootstrap a single tenant. Idempotent."""
    if _db is None:
        raise HTTPException(503, "db not ready")
    res = await svc.bootstrap_tenant_dashboard(
        _db,
        tenant_id=body.tenant_id,
        domain=body.domain,
        email=body.email,
        business_name=body.business_name,
        force_scan=body.force_scan,
    )
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "bootstrap failed"))
    return res


@router.post("/api/admin/tenant/bootstrap-all-pending")
async def bootstrap_all():
    """Find every tenant with a business_id but no pixel and bootstrap
    them all. One-shot backfill — safe to call repeatedly (idempotent)."""
    if _db is None:
        raise HTTPException(503, "db not ready")
    res = await svc.bootstrap_all_pending_tenants(_db)
    if not res.get("ok"):
        raise HTTPException(500, res.get("error", "bulk bootstrap failed"))
    return res
