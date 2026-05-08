"""
ClawChief OS API
================

REST endpoints for the autonomous operations layer.
Exposes heartbeat, sweeps, workspace files, and manual triggers.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import os
import jwt
import logging

router = APIRouter(prefix="/api/clawchief", tags=["clawchief"])
logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database
    from services.clawchief_service import set_db as set_chief_db
    set_chief_db(database)


def _get_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = auth.split(" ", 1)[1]
    secret = os.environ.get("JWT_SECRET", "")
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


# ═══════════════════════════════════════════════════
# HEARTBEAT
# ═══════════════════════════════════════════════════

@router.get("/heartbeat")
async def get_heartbeat(request: Request):
    """Get the latest heartbeat status."""
    _get_user(request)
    if _db is None:
        raise HTTPException(500, "Database not initialized")

    latest = await _db.heartbeats.find_one(
        sort=[("stored_at", -1)], projection={"_id": 0}
    )
    if not latest:
        return {"alert_level": "INITIALIZING", "message": "No heartbeat recorded yet. Trigger manually or wait for first scheduled check."}
    return latest


@router.post("/heartbeat/trigger")
async def trigger_heartbeat(request: Request):
    """Manually trigger a heartbeat check."""
    _get_user(request)

    from services.clawchief_service import run_heartbeat
    result = await run_heartbeat()
    return {"triggered": True, "heartbeat": result}


# ═══════════════════════════════════════════════════
# SWEEPS
# ═══════════════════════════════════════════════════

@router.post("/sweep/daily")
async def trigger_daily_sweep(request: Request):
    """Manually trigger the daily sweep (runs Scout, Oracle, Closer)."""
    _get_user(request)

    from services.clawchief_service import run_daily_sweep
    result = await run_daily_sweep()
    return {"triggered": True, "sweep": result}


@router.post("/sweep/pipeline")
async def trigger_pipeline_audit(request: Request):
    """Manually trigger a pipeline audit."""
    _get_user(request)

    from services.clawchief_service import run_pipeline_audit
    result = await run_pipeline_audit()
    return {"triggered": True, "audit": result}


@router.get("/sweeps")
async def list_sweeps(request: Request, limit: int = 20):
    """List recent sweep records."""
    _get_user(request)
    if _db is None:
        return {"sweeps": []}

    sweeps = await _db.sweeps.find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    return {"sweeps": sweeps, "total": len(sweeps)}


# ═══════════════════════════════════════════════════
# WORKSPACE FILES
# ═══════════════════════════════════════════════════

@router.get("/workspace/{filename}")
async def read_workspace_file(request: Request, filename: str):
    """Read a workspace file (SOUL.md, IDENTITY.md, AGENTS.md, MEMORY.md, HEARTBEAT.md)."""
    _get_user(request)

    from services.clawchief_service import WORKSPACE_ROOT, read_workspace_file as read_file

    allowed_files = ["SOUL.md", "IDENTITY.md", "AGENTS.md", "MEMORY.md", "HEARTBEAT.md"]
    if filename not in allowed_files:
        raise HTTPException(400, f"File not accessible. Allowed: {', '.join(allowed_files)}")

    content = read_file(WORKSPACE_ROOT / filename)
    if not content:
        raise HTTPException(404, f"{filename} not found in workspace")

    return {"filename": filename, "content": content}


@router.get("/tasks")
async def read_current_tasks(request: Request):
    """Read the current task log (tasks/current.md)."""
    _get_user(request)

    from services.clawchief_service import TASKS_FILE, read_workspace_file as read_file

    content = read_file(TASKS_FILE)
    return {"filename": "tasks/current.md", "content": content}


# ═══════════════════════════════════════════════════
# STATUS
# ═══════════════════════════════════════════════════

@router.get("/status")
async def clawchief_status(request: Request):
    """Overall ClawChief OS status."""
    _get_user(request)

    from services.clawchief_service import WORKSPACE_ROOT

    workspace_files = []
    for f in WORKSPACE_ROOT.glob("*.md"):
        workspace_files.append(f.name)

    heartbeat_count = 0
    sweep_count = 0
    if _db is not None:
        heartbeat_count = await _db.heartbeats.count_documents({})
        sweep_count = await _db.sweeps.count_documents({})

    return {
        "status": "OPERATIONAL",
        "workspace_root": str(WORKSPACE_ROOT),
        "workspace_files": sorted(workspace_files),
        "heartbeats_recorded": heartbeat_count,
        "sweeps_recorded": sweep_count,
        "schedulers": {
            "heartbeat": "every 15 minutes",
            "daily_sweep": "08:00 America/Toronto",
            "pipeline_audit": "every 4 hours",
        },
    }
