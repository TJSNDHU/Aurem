"""
nightly_selfcheck_router.py — iter 322av
=========================================
Admin endpoint to run the AUREM Nightly System Check on demand and read
the latest reports.
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/selfcheck", tags=["Nightly Self-Check"])

_db = None


def set_db(database):
    global _db
    _db = database


async def _require_super_admin():
    try:
        from utils.auth import require_super_admin   # type: ignore
        return await require_super_admin()
    except Exception:
        return None


@router.post("/run")
async def trigger_selfcheck(_=Depends(_require_super_admin)):
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    from services.aurem_nightly_selfcheck import run_selfcheck
    return await run_selfcheck(_db, slot="manual")


@router.post("/watchdog-tick")
async def trigger_watchdog(_=Depends(_require_super_admin)):
    """Run ORA Watchdog now (otherwise auto-runs every 15 min)."""
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    from services.ora_autonomous_driver import ora_watchdog
    return await ora_watchdog(_db)


@router.post("/daily-hunt")
async def trigger_daily_hunt(_=Depends(_require_super_admin)):
    """Run the autonomous daily hunt now (otherwise auto-runs at 06:00 UTC)."""
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    from services.ora_autonomous_driver import daily_hunt_for_all_tenants
    return await daily_hunt_for_all_tenants(_db)


@router.get("/watchdog-log")
async def watchdog_log(limit: int = 50, _=Depends(_require_super_admin)):
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    limit = max(1, min(200, limit))
    cur = _db.ora_watchdog_log.find({}, {"_id": 0}).sort("ts", -1).limit(limit)
    items = await cur.to_list(length=limit)
    return {"ok": True, "items": items, "count": len(items)}


@router.get("/latest")
async def latest_selfcheck(_=Depends(_require_super_admin)):
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    try:
        doc = await _db.nightly_selfcheck.find_one({}, {"_id": 0}, sort=[("ts", -1)])
        return {"ok": True, "report": doc}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/history")
async def selfcheck_history(limit: int = 30, _=Depends(_require_super_admin)):
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    limit = max(1, min(100, limit))
    try:
        cur = _db.nightly_selfcheck.find({}, {"_id": 0, "pillars": 0}).sort("ts", -1).limit(limit)
        items = await cur.to_list(length=limit)
        return {"ok": True, "items": items, "count": len(items)}
    except Exception as e:
        raise HTTPException(500, str(e))
