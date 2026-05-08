"""Scheduler introspection — admin only."""
from fastapi import APIRouter, Header, HTTPException
from typing import Optional
import os
import jwt

router = APIRouter()


def _verify_admin(authorization: Optional[str]) -> None:
    if not authorization:
        raise HTTPException(401, "missing token")
    try:
        token = authorization.replace("Bearer ", "").strip()
        decoded = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
        if not decoded.get("is_admin"):
            raise HTTPException(403, "admin only")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "invalid token")


@router.get("/api/admin/scheduler/jobs")
async def scheduler_jobs(authorization: Optional[str] = Header(None)) -> dict:
    _verify_admin(authorization)
    try:
        from routers import registry as _r
        sched = getattr(_r, "aurem_scheduler", None)
        if sched is None:
            return {"ok": False, "reason": "scheduler not initialised"}
        jobs = []
        for j in sched.get_jobs():
            jobs.append({
                "id": j.id,
                "name": j.name,
                "trigger": str(j.trigger),
                "next_run": j.next_run_time.isoformat() if j.next_run_time else None,
            })
        return {"ok": True, "running": sched.running, "count": len(jobs),
                "jobs": jobs}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


# Public count-only + filtered ids (used by Pillars chip / status banner)
@router.get("/api/admin/scheduler/count")
async def scheduler_count() -> dict:
    try:
        from routers import registry as _r
        sched = getattr(_r, "aurem_scheduler", None)
        if sched is None:
            return {"ok": False, "count": 0, "running": False}
        ids = [j.id for j in sched.get_jobs()]
        return {"ok": True, "running": sched.running,
                "count": len(ids), "ids": sorted(ids)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
