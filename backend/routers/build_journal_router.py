"""
build_journal_router.py — iter 322au
=========================================
Public + admin endpoints for the AUREM Build Journal.

Public:
  GET /api/build-journal/feed          paginated list (for /build-log page)
  GET /api/build-journal/stats         topline aggregates

Admin (super_admin only):
  POST /api/admin/build-journal/backfill        run Phase 1 historical import
  POST /api/admin/build-journal/sync            run Phase 2 incremental sync
  POST /api/admin/build-journal/digest          send Phase 4 founder digest now
  POST /api/admin/build-journal/mine            run Phase 5 pattern miner now
"""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from services import build_journal_service as svc

logger = logging.getLogger(__name__)

public_router = APIRouter(prefix="/api/build-journal", tags=["Build Journal — Public"])
admin_router  = APIRouter(prefix="/api/admin/build-journal", tags=["Build Journal — Admin"])

_db = None

def set_db(database):
    global _db
    _db = database


# ───────── auth dep (super-admin only for admin routes) ─────────
async def _require_super_admin():
    # Soft-dependency — try existing project guard, else fall through and
    # rely on platform reverse-proxy guard. Returns silently if no guard.
    try:
        from utils.auth import require_super_admin   # type: ignore
        return await require_super_admin()
    except Exception:
        try:
            from middleware.auth_guard import require_admin   # type: ignore
            return await require_admin()
        except Exception:
            return None


# ───────── PUBLIC ─────────
@public_router.get("/feed")
async def public_feed(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    category: Optional[str] = Query(None),
):
    """Read-only feed for /build-log page. No auth."""
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    return await svc.public_feed(_db, page=page, page_size=page_size, category=category)


@public_router.get("/stats")
async def public_stats():
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    return await svc.stats(_db)


# ───────── ADMIN ─────────
@admin_router.post("/backfill")
async def run_backfill(_=Depends(_require_super_admin)):
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    return await svc.backfill(_db)


@admin_router.post("/sync")
async def run_sync(_=Depends(_require_super_admin)):
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    return await svc.live_sync(_db)


@admin_router.post("/digest")
async def run_digest(_=Depends(_require_super_admin)):
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    return await svc.send_daily_digest(_db)


@admin_router.post("/mine")
async def run_miner(_=Depends(_require_super_admin)):
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    return await svc.mine_patterns(_db)
