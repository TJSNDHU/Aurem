"""
Deploy Monitor — Phase 4 (Code Layer)
======================================
Tracks the running version (from `/api/health` v field) and emits
DEPLOY_DETECTED on the A2A bus when it changes.

Also writes a row in `ora_deploy_log` for every transition. The ORA
Brain Observer already subscribes to DEPLOY_DETECTED and persists it.

State is held in-memory + persisted to `system_state` collection so a
backend restart still detects the next true deploy (not its own restart).
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _utc() -> datetime:
    return datetime.now(timezone.utc)


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


async def _read_running_version() -> Optional[str]:
    """Read backend version from bootstrap/health_routes._APP_VERSION."""
    try:
        from bootstrap.health_routes import _APP_VERSION
        if _APP_VERSION:
            return str(_APP_VERSION)
    except Exception:
        pass
    return (
        os.environ.get("APP_VERSION")
        or os.environ.get("AUREM_BUILD_SHA")
        or os.environ.get("GIT_SHA")
    )


async def check_once() -> Dict[str, Any]:
    """One-shot deploy detection. Returns {changed: bool, old, new}."""
    db = _get_db()
    if db is None:
        return {"changed": False, "reason": "db_unavailable"}

    current = await _read_running_version()
    if not current:
        return {"changed": False, "reason": "no_version"}

    state = await db.system_state.find_one(
        {"key": "deploy_version"}, {"_id": 0},
    )
    old = (state or {}).get("value")

    if old == current:
        return {"changed": False, "version": current}

    await db.system_state.update_one(
        {"key": "deploy_version"},
        {"$set": {
            "key": "deploy_version", "value": current, "ts": _utc(),
            "previous": old,
        }},
        upsert=True,
    )

    if old is None:
        # First time we record; not a true deploy event
        return {"changed": False, "first_seen": current}

    # Emit DEPLOY_DETECTED + verify after 60s
    payload = {"old": old, "new": current, "ts": _utc().isoformat()}
    try:
        from services.a2a_bus import bus
        asyncio.create_task(bus.emit(
            "deploy_monitor", "DEPLOY_DETECTED", payload,
        ))
    except Exception:
        pass

    logger.info(f"[deploy_monitor] DEPLOY_DETECTED {old} -> {current}")
    asyncio.create_task(_post_deploy_verify(payload))
    return {"changed": True, **payload}


async def _post_deploy_verify(payload: Dict[str, Any]) -> None:
    """60-second post-deploy stability check.
    If error_ledger gains > 5 new open errors after the deploy, alert founder."""
    await asyncio.sleep(60)
    db = _get_db()
    if db is None:
        return
    try:
        from datetime import timedelta
        cutoff = _utc() - timedelta(seconds=70)
        new_errors = await db.error_ledger.count_documents({
            "status": "open",
            "first_seen": {"$gte": cutoff},
        })
        await db.ora_deploy_verifications.insert_one({
            "old": payload.get("old"),
            "new": payload.get("new"),
            "post_deploy_errors_60s": new_errors,
            "ts": _utc(),
            "status": "unstable" if new_errors > 5 else "stable",
        })
        if new_errors > 5:
            try:
                from services.a2a_bus import bus
                await bus.emit("deploy_monitor", "DEPLOY_UNSTABLE", {
                    "old": payload.get("old"),
                    "new": payload.get("new"),
                    "post_deploy_errors_60s": new_errors,
                })
            except Exception:
                pass
            logger.warning(
                f"[deploy_monitor] UNSTABLE deploy: {new_errors} new errors in 60s",
            )
    except Exception as e:
        logger.debug(f"[deploy_monitor] verify err: {e}")


def deploy_monitor_scheduler():
    """5-minute polling loop. Cheap — single doc lookup + version read."""
    async def _loop():
        await asyncio.sleep(45)
        while True:
            try:
                await check_once()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.debug(f"[deploy_monitor] err: {e}")
            await asyncio.sleep(300)
    return _loop
