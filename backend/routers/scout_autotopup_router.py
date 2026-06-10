"""
scout_autotopup_router.py — iter D-71e

Admin endpoints for the Scout Auto-Topup background job:

  GET  /api/admin/scout-autotopup/status    → eligibility, last run, config
  POST /api/admin/scout-autotopup/trigger   → fire one Apollo batch NOW
                                              (respects cooldown unless force=true)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from services import scout_autotopup
from utils.admin_guard import verify_admin

router = APIRouter(prefix="/api/admin/scout-autotopup", tags=["Scout Auto-Topup"])

_db = None


def set_db(database):
    global _db
    _db = database


def _require_db():
    if _db is None:
        raise HTTPException(503, "db not wired")
    return _db


@router.get("/status")
async def get_status(authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    db = _require_db()
    return {"ok": True, **await scout_autotopup.status(db)}


class TriggerBody(BaseModel):
    force: bool = False
    reason: str = "manual_admin_trigger"


@router.post("/trigger")
async def trigger_topup(body: TriggerBody, authorization: Optional[str] = Header(None)):
    """Manually fire one Apollo Canada-wide batch.

    By default this honours the cooldown + daily ceiling like the
    background scheduler. Pass `force=true` to override the cooldown
    (still capped by the daily ceiling — abuse protection).
    """
    verify_admin(authorization)
    db = _require_db()
    if body.force:
        # Skip cooldown check, but daily ceiling still applies.
        if await scout_autotopup._hit_daily_ceiling(db):
            raise HTTPException(429, "Daily ceiling hit — try tomorrow")
        result = await scout_autotopup.trigger_topup(db, reason=body.reason + "_forced")
    else:
        result = await scout_autotopup.check_and_topup(db)
    return {"ok": True, **result}
