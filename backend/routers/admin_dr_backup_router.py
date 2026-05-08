"""
admin_dr_backup_router.py — Admin-only endpoints for Disaster Recovery backups.

Endpoints:
  POST /api/admin/backup/trigger  — start a manual mirror run (background)
  GET  /api/admin/backup/status   — last 20 backup runs + secondary cluster health
"""
import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorClient

from services.db_backup_service import run_backup

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/backup", tags=["admin", "backup"])

# Lazy DB accessor — avoids creating an AsyncIOMotorClient at module-import
# time (which can crash startup on K8s deploy when MONGO_URL is missing
# or uses Atlas DNS that's slow to resolve before the event loop is up).
_db_client = None
_db_handle = None


def _get_db():
    global _db_client, _db_handle
    if _db_handle is None:
        url = os.environ.get("MONGO_URL")
        if not url:
            return None
        _db_client = AsyncIOMotorClient(url)
        _db_handle = _db_client[os.environ.get("DB_NAME", "aurem_db")]
    return _db_handle


async def _require_super_admin(authorization: str = None) -> Dict[str, Any]:
    """Reuse the platform admin dependency from existing auth router."""
    from routers.ai_platform_router import get_current_platform_user
    user = await get_current_platform_user(authorization=authorization)
    is_admin = (
        user.get("is_admin")
        or user.get("role") in ("super_admin", "admin")
        or user.get("_id") == "admin"
    )
    if not is_admin:
        raise HTTPException(403, "super_admin required")
    return user


def _run_in_thread() -> Dict[str, Any]:
    """Synchronous wrapper called from BackgroundTasks (runs in threadpool)."""
    return run_backup(triggered_by="manual_admin")


@router.post("/trigger")
async def trigger_backup(
    background_tasks: BackgroundTasks,
    authorization: str = None,
):
    """Kick off a primary→secondary mirror in the background.
    Returns immediately with the new run_id. Poll /status for progress."""
    await _require_super_admin(authorization=authorization)
    if not os.environ.get("SECONDARY_MONGO_URL"):
        raise HTTPException(
            400,
            "SECONDARY_MONGO_URL not configured — set this env var first",
        )
    run_id = f"dr-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    background_tasks.add_task(_run_in_thread)
    logger.info(f"[DR-BACKUP] manual trigger queued — {run_id}")
    return {
        "ok": True,
        "queued": True,
        "run_id_prefix": run_id,
        "message": "Backup started in background. Poll /api/admin/backup/status",
    }


@router.get("/status")
async def backup_status(authorization: str = None) -> Dict[str, Any]:
    """Return last 20 runs + secondary cluster reachability."""
    await _require_super_admin(authorization=authorization)

    runs: List[Dict[str, Any]] = []
    db = _get_db()
    if db is None:
        return {
            "ok": True,
            "runs": [],
            "secondary": {"configured": False, "reachable": False},
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "warning": "MONGO_URL not configured",
        }
    cursor = (
        db["db_backup_runs"]
        .find({}, {"_id": 0, "collections": 0})
        .sort("started_at", -1)
        .limit(20)
    )
    async for r in cursor:
        runs.append(r)

    # Probe secondary cluster (do not block more than 4s)
    secondary_health: Dict[str, Any] = {"configured": False, "reachable": False}
    sec_url = os.environ.get("SECONDARY_MONGO_URL")
    if sec_url:
        secondary_health["configured"] = True
        try:
            from pymongo import MongoClient
            def _probe():
                c = MongoClient(sec_url, serverSelectionTimeoutMS=4000)
                try:
                    c.admin.command("ping")
                    return True
                finally:
                    c.close()
            secondary_health["reachable"] = await asyncio.to_thread(_probe)
        except Exception as e:
            secondary_health["error"] = f"{type(e).__name__}: {str(e)[:140]}"

    last_ok = next((r for r in runs if r.get("status") == "ok"), None)
    return {
        "ok": True,
        "runs": runs,
        "last_successful": last_ok,
        "secondary": secondary_health,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
