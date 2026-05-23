"""
ora_github_lock_router.py — iter 327d

Three tiny admin endpoints around the iter-327d GitHub read-only lock:

  GET  /api/admin/ora/github-lock          → current status (UI uses this)
  POST /api/admin/ora/github-unlock        → flip locked=False (audited)
  POST /api/admin/ora/github-relock        → flip locked=True  (audited)

Auth: admin JWT via the same `get_admin_user` dep ORA's other admin
routes use. The unlock endpoint requires a `reason` ≥ 10 chars so the
audit row in `ora_governance_audit` is meaningful.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/ora", tags=["ora-github-lock"])

_db = None


def set_db(database):
    global _db
    _db = database
    # Wire the lockdown service to the same DB so reads share the row
    try:
        from services import github_lockdown
        github_lockdown.set_db(database)
    except Exception as e:
        logger.warning(f"[github-lock-router] failed to wire lockdown db: {e}")


def _get_admin_dep():
    from routers.ora_agent_router import get_admin_user
    return get_admin_user


class UnlockBody(BaseModel):
    reason: str = Field(min_length=10, max_length=600)
    # iter 327f — TTL-bounded unlock. Default 15 min, hard cap 60 min.
    # Founder's verbatim request: "One click unlock → auto-relocks
    # after 15 min. Audit row on relock."
    ttl_minutes: int = Field(default=15, ge=1, le=60)


# ───────────────────────────────────────────────────────────────────

@router.get("/github-lock")
async def github_lock_status(user: dict = Depends(_get_admin_dep())):
    from services.github_lockdown import get_lock_status
    status = await get_lock_status()
    # Add a small "recent attempts" tail so the UI can show how
    # often ORA has been bouncing off the lock.
    recent = []
    if _db is not None:
        try:
            cursor = _db.ora_github_block_log.find({}, {"_id": 0}).sort(
                "ts", -1
            ).limit(5)
            recent = await cursor.to_list(length=5)
        except Exception:
            pass
    status["recent_attempts"] = recent
    return {"ok": True, **status}


@router.post("/github-unlock")
async def github_unlock(body: UnlockBody, user: dict = Depends(_get_admin_dep())):
    if _db is None:
        raise HTTPException(503, "db not ready")
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=body.ttl_minutes)
    await _db.ora_governance.update_one(
        {"_id": "github_lock_state"},
        {"$set": {
            "locked":             False,
            "unlocked_at":        now.isoformat(),
            "unlocked_by":        user.get("email") or user.get("user_id"),
            "unlocked_reason":    body.reason,
            "unlock_ttl_minutes": body.ttl_minutes,
            "unlock_expires_at":  expires_at.isoformat(),
        },
         "$unset": {"auto_relocked_at": "", "auto_relock_reason": ""}},
        upsert=True,
    )
    await _db.ora_governance_audit.insert_one({
        "action":       "github_unlock",
        "actor":        user.get("email") or user.get("user_id"),
        "reason":       body.reason,
        "ttl_minutes":  body.ttl_minutes,
        "expires_at":   expires_at.isoformat(),
        "ts":           now.isoformat(),
    })
    logger.warning(
        f"[github-lock] UNLOCKED by {user.get('email')} for "
        f"{body.ttl_minutes}m — reason: {body.reason!r} — "
        f"auto-relock at {expires_at.isoformat()}"
    )
    return {
        "ok":                  True,
        "locked":              False,
        "mode":                "write_unlocked",
        "unlock_expires_at":   expires_at.isoformat(),
        "ttl_minutes":         body.ttl_minutes,
        "seconds_until_relock": body.ttl_minutes * 60,
    }


@router.post("/github-relock")
async def github_relock(user: dict = Depends(_get_admin_dep())):
    if _db is None:
        raise HTTPException(503, "db not ready")
    await _db.ora_governance.update_one(
        {"_id": "github_lock_state"},
        {"$set": {
            "locked":      True,
            "relocked_at": datetime.now(timezone.utc).isoformat(),
            "relocked_by": user.get("email") or user.get("user_id"),
        },
         "$unset": {"unlock_expires_at": ""}},
        upsert=True,
    )
    await _db.ora_governance_audit.insert_one({
        "action": "github_relock",
        "actor":  user.get("email") or user.get("user_id"),
        "ts":     datetime.now(timezone.utc).isoformat(),
    })
    logger.info(f"[github-lock] RELOCKED by {user.get('email')}")
    return {"ok": True, "locked": True, "mode": "read_only"}
