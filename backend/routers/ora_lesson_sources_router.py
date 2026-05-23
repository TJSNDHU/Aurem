"""
routers/ora_lesson_sources_router.py — iter 327p (backend half)

Surfaces the ORA lesson-injection state so the founder can see at a
glance which files are wired into the brain's prompt today.

Endpoints (all super-admin gated)
  GET  /api/admin/ora/lesson-sources
      → {tier1: [...], tier2: [...], total_chars, journal_count}
  GET  /api/admin/ora/lesson-journal?limit=N
      → recent snapshots from ora_learning_journal (iter 327o)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/ora", tags=["ora-admin"])

_db = None


def set_db(database):
    global _db
    _db = database


def _admin_dep():
    """iter 327p — reuse the same admin guard the github-lock router uses."""
    from routers.ora_agent_router import get_admin_user
    return get_admin_user


@router.get("/lesson-sources")
async def lesson_sources(user: dict = Depends(_admin_dep())):
    """What's in ORA's prompt today? Tier-1 (always) + Tier-2 (gated)."""
    from services.ora_lessons_loader import (
        last_injection_manifest,
        tier1_total_chars,
        tier2_rule_table,
        _TIER1_CAP_TOTAL,
        _TIER1_CAP_PER_FILE,
    )
    journal_count = 0
    if _db is not None:
        try:
            journal_count = await _db.ora_learning_journal.count_documents({})
        except Exception:
            pass
    return {
        "ok":              True,
        "tier1": {
            "files":            last_injection_manifest(),
            "total_chars":      tier1_total_chars(),
            "cap_total":        _TIER1_CAP_TOTAL,
            "cap_per_file":     _TIER1_CAP_PER_FILE,
        },
        "tier2": {
            "rules":            tier2_rule_table(),
        },
        "journal_count":   journal_count,
    }


@router.get("/lesson-journal")
async def lesson_journal(limit: int = 20,
                            user: dict = Depends(_admin_dep())):
    """Recent tier-1 snapshots — used to roll back a bad lesson edit."""
    if _db is None:
        raise HTTPException(503, "db not ready")
    limit = max(1, min(int(limit or 20), 100))
    try:
        cur = _db.ora_learning_journal.find(
            {}, {"_id": 0}
        ).sort("ts", -1).limit(limit)
        entries = await cur.to_list(length=limit)
    except Exception as e:
        logger.warning(f"[lesson-journal] read failed: {e}")
        entries = []
    return {"ok": True, "entries": entries, "count": len(entries)}


@router.post("/lesson-snapshot")
async def lesson_snapshot_now(user: dict = Depends(_admin_dep())):
    """iter 327q — Force a tier-1 snapshot right now (founder-triggered).

    Re-reads disk via `build_lessons_block`, compares sha256s, writes a
    new `ora_learning_journal` row when anything changed. Idempotent
    when no files changed (returns `changed: false`).
    """
    if _db is None:
        raise HTTPException(503, "db not ready")
    from services.ora_lessons_loader import (
        build_lessons_block, record_journal_entry_if_changed,
    )
    # Rebuild so the in-memory manifest reflects what's on disk RIGHT NOW.
    build_lessons_block()
    result = await record_journal_entry_if_changed(_db)
    return {"ok": bool(result.get("ok")), **result}


@router.get("/nightly-self-tests")
async def nightly_self_tests(limit: int = 14,
                                 user: dict = Depends(_admin_dep())):
    """iter 327q — Last N nightly self-test rows for the admin UI."""
    if _db is None:
        raise HTTPException(503, "db not ready")
    limit = max(1, min(int(limit or 14), 60))
    try:
        cur = _db.ora_nightly_self_tests.find(
            {}, {"_id": 0}
        ).sort("ts", -1).limit(limit)
        entries = await cur.to_list(length=limit)
    except Exception as e:
        logger.warning(f"[nightly-self-tests] read failed: {e}")
        entries = []
    return {"ok": True, "entries": entries, "count": len(entries)}
