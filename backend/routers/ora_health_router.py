"""
ORA Self-Heal — read-only status endpoint for Mission Control widget.

GET /api/admin/ora-health/status
  Returns latest snapshot of all 5 watched services + last 10 incidents.

POST /api/admin/ora-health/run-now
  Force-runs a tick (admin-only). Useful for manual debugging.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header

from utils.admin_guard import verify_admin
from services.ora_self_heal import run_health_tick

router = APIRouter(prefix="/api/admin/ora-health", tags=["ORA Self-Heal"])

_db = None


def set_db(db):
    global _db
    _db = db


@router.get("/status")
async def status(authorization: Optional[str] = Header(None)):
    """Latest health snapshot across the 5 watched services + recent
    incidents. Same loopback-friendly auth pattern as payments_health
    (body contains no sensitive data — mode flags + counts + timestamps)."""
    if authorization:
        try:
            verify_admin(authorization)
        except Exception:
            pass  # body is non-sensitive, allow read

    if _db is None:
        return {"services": {}, "incidents": [], "error": "db not ready"}

    services_list = []
    cursor = _db.ora_health_checks.find({}, {"_id": 0})
    async for s in cursor:
        services_list.append(s)

    incidents = []
    cursor = _db.ora_health_incidents.find({}, {"_id": 0}).sort("ts", -1).limit(10)
    async for inc in cursor:
        incidents.append(inc)

    # Roll up a top-level color: any red → red, else any yellow → yellow, else green
    rollup = "green"
    for s in services_list:
        if s.get("status") == "red":
            rollup = "red"
            break
        if s.get("status") == "yellow":
            rollup = "yellow"
    if not services_list:
        rollup = "unknown"

    return {
        "rollup_status": rollup,
        "services": {s["service"]: s for s in services_list},
        "incidents": incidents,
    }


@router.post("/run-now")
async def run_now(authorization: Optional[str] = Header(None)):
    """Force-run a watchdog tick. Admin-gated."""
    verify_admin(authorization)
    if _db is None:
        return {"ok": False, "error": "db not ready"}
    snapshot = await run_health_tick(_db)
    return {"ok": True, "snapshot": snapshot}


@router.get("/scheduler-info")
async def scheduler_info(authorization: Optional[str] = Header(None)):
    """List scheduler jobs (debug aid). Confirms the 5-min watchdog is
    actually registered. iter 281.1"""
    verify_admin(authorization)
    try:
        from routers import registry as _reg
        sched = getattr(_reg, "aurem_scheduler", None)
        if sched is None:
            return {"ok": False, "reason": "aurem_scheduler not exposed yet"}
        jobs = []
        for j in sched.get_jobs():
            jobs.append({
                "id": j.id,
                "name": j.name,
                "next_run": str(j.next_run_time) if j.next_run_time else None,
                "trigger": str(j.trigger),
            })
        return {
            "ok": True,
            "running": sched.running,
            "job_count": len(jobs),
            "jobs": jobs,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
