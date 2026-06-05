"""
codebase_health_router.py — iter D-70
=======================================
Admin-only endpoints for the live codebase-health dashboard.

  GET  /api/admin/codebase-health/latest  → most recent snapshot
  GET  /api/admin/codebase-health/trend   → score over time
  POST /api/admin/codebase-health/refresh → force-run (founder click)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from services import codebase_health as ch
from utils.admin_guard import verify_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/codebase-health", tags=["Codebase Health"])


def set_db(database):
    ch.set_db(database)


@router.get("/latest")
async def latest(authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    snap = await ch.latest_snapshot()
    if not snap:
        # First load: run synchronously so the UI gets data immediately.
        snap = await ch.run_snapshot()
    return {"ok": True, "snapshot": snap}


@router.get("/trend")
async def trend(days: int = 7, authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    days = max(1, min(int(days), 30))
    return {"ok": True, "items": await ch.trend(days)}


@router.post("/refresh")
async def refresh(authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    return {"ok": True, "snapshot": await ch.run_snapshot()}
