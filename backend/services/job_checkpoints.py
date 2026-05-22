"""
services/job_checkpoints.py — iter 326z (Phase 2 P1.2).

Generic checkpoint store for long-running jobs (multi-hour campaign blasts,
nightly DR sweeps, scout replenish cycles). Any job that crashes mid-flight
can resume from its last saved checkpoint instead of starting over.

Public API
──────────
    await save_checkpoint(job_id, step_idx, state, *, ttl_hours=72)
        — atomic upsert. Idempotent. Overwrites previous state for the
          same job_id. `state` is any JSON-serialisable dict.

    await load_checkpoint(job_id)
        → dict with {step_idx, state, updated_at} or None if no checkpoint.

    await clear_checkpoint(job_id)
        — call on successful completion so the row is gone immediately.
          Otherwise the TTL index reaps it after `ttl_hours`.

    await list_checkpoints(prefix="", limit=50)
        — admin view of in-flight long jobs (debug surface).

Storage
───────
    Mongo collection `ora_job_checkpoints` with a TTL index on `expires_at`
    so abandoned jobs don't pile up.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

_COLLECTION = "ora_job_checkpoints"
_DEFAULT_TTL_HOURS = 72
_db = None
_indexes_ensured = False


def set_db(database) -> None:
    global _db, _indexes_ensured
    _db = database
    _indexes_ensured = False


async def _ensure_indexes() -> None:
    global _indexes_ensured
    if _indexes_ensured or _db is None:
        return
    try:
        await _db[_COLLECTION].create_index("expires_at", expireAfterSeconds=0)
        _indexes_ensured = True
    except Exception as e:
        logger.warning(f"[checkpoints] index ensure failed: {e}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def save_checkpoint(
    job_id: str,
    step_idx: int,
    state: dict,
    *,
    ttl_hours: int = _DEFAULT_TTL_HOURS,
) -> dict:
    """Atomically upsert a checkpoint for `job_id`. Last write wins."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    if not isinstance(job_id, str) or not job_id:
        return {"ok": False, "error": "job_id required"}
    if not isinstance(state, dict):
        return {"ok": False, "error": "state must be dict"}
    await _ensure_indexes()
    now = _now()
    try:
        await _db[_COLLECTION].update_one(
            {"_id": job_id},
            {"$set": {
                "step_idx":   int(step_idx),
                "state":      state,
                "updated_at": now,
                "expires_at": now + timedelta(hours=max(1, int(ttl_hours))),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"[checkpoints] save failed for {job_id}: {e}")
        return {"ok": False, "error": str(e)[:200]}
    return {"ok": True, "job_id": job_id, "step_idx": int(step_idx)}


async def load_checkpoint(job_id: str) -> Optional[dict]:
    """Return the last saved checkpoint or None."""
    if _db is None or not job_id:
        return None
    doc = await _db[_COLLECTION].find_one(
        {"_id": job_id},
        {"_id": 0, "step_idx": 1, "state": 1, "updated_at": 1},
    )
    if not doc:
        return None
    ua = doc.get("updated_at")
    if isinstance(ua, datetime):
        doc["updated_at"] = ua.isoformat()
    return doc


async def clear_checkpoint(job_id: str) -> dict:
    """Delete the checkpoint — call on successful job completion."""
    if _db is None or not job_id:
        return {"ok": False, "error": "db_not_ready"}
    try:
        res = await _db[_COLLECTION].delete_one({"_id": job_id})
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
    return {"ok": True, "deleted": res.deleted_count}


async def list_checkpoints(prefix: str = "", limit: int = 50) -> list:
    """Admin view — most-recent in-flight checkpoints first."""
    if _db is None:
        return []
    q: dict[str, Any] = {}
    if prefix:
        q["_id"] = {"$regex": f"^{prefix}"}
    rows: list = []
    cur = (
        _db[_COLLECTION]
        .find(q, {"_id": 1, "step_idx": 1, "updated_at": 1})
        .sort("updated_at", -1)
        .limit(int(limit))
    )
    async for d in cur:
        ua = d.get("updated_at")
        rows.append({
            "job_id":     d.get("_id"),
            "step_idx":   d.get("step_idx"),
            "updated_at": ua.isoformat() if isinstance(ua, datetime) else ua,
        })
    return rows
