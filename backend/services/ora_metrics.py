"""
services/ora_metrics.py — iter 331c Sprint 6

Per-session metrics collection. Tracks ORA's autonomy quality over
time so the founder can see if she's getting better or worse week-over-week.

Persists to Mongo collection `ora_session_metrics` (one doc per session).
Read-only summary endpoint at `/api/admin/ora/health` returns a
green/yellow/red status over the last 7 days.

Public API:
    set_db(database)
    record_tool_call(session_id, tool, ok, elapsed_ms, blocked_by=None)
    record_prose_scrub(session_id, n_redacted)
    record_session_end(session_id, task_success, usd_cost=None)
    health_snapshot(days=7) -> dict   # for the cockpit tile

Portability: zero Emergent imports. All env-overridable.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

_COLLECTION = os.environ.get("ORA_METRICS_COLLECTION", "ora_session_metrics")

_db = None


def set_db(database) -> None:
    global _db
    _db = database


# ── Per-session in-memory accumulators ──────────────────────────────
# Persist to Mongo on each call (idempotent upsert) so a crash before
# `record_session_end` still leaves a useful record.

def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _upsert(session_id: str, updates: dict) -> None:
    if _db is None or not session_id:
        return
    try:
        await _db[_COLLECTION].update_one(
            {"_id": session_id},
            {
                "$set":           {"updated_at": _iso(), **updates.get("$set", {})},
                "$setOnInsert":   {"started_at": _iso(), **updates.get("$setOnInsert", {})},
                "$inc":           updates.get("$inc", {}),
            },
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[ora-metrics] upsert skipped: {e}")


async def record_tool_call(
    session_id: str,
    tool: str,
    ok: bool,
    elapsed_ms: int,
    blocked_by: str | None = None,
) -> None:
    """Increment counters for a single tool invocation."""
    inc = {
        "tool_calls_total": 1,
        "elapsed_ms_total": int(elapsed_ms or 0),
    }
    if not ok:
        inc["tools_failed"] = 1
    if blocked_by:
        inc[f"blocked_by.{blocked_by}"] = 1
    await _upsert(session_id, {"$inc": inc,
                                  "$setOnInsert": {"session_id": session_id}})


async def record_prose_scrub(session_id: str, n_redacted: int) -> None:
    if n_redacted <= 0:
        return
    await _upsert(session_id, {"$inc": {"prose_filter_scrubs": int(n_redacted)}})


async def record_loop_halt(session_id: str, reason: str) -> None:
    await _upsert(session_id, {"$inc": {f"loops_detected.{reason}": 1}})


async def record_session_end(
    session_id: str,
    task_success: bool,
    usd_cost: float | None = None,
    tier2_rejected: int = 0,
    tier2_total: int = 0,
    coverage_percent: float | None = None,
) -> dict:
    """Mark the session as ended + record final metrics."""
    upd_set: dict[str, Any] = {
        "ended_at":          _iso(),
        "task_success":      bool(task_success),
        "tier2_rejected":    int(tier2_rejected),
        "tier2_total":       int(tier2_total),
    }
    if usd_cost is not None:
        upd_set["usd_cost"] = float(usd_cost)
    if coverage_percent is not None:
        upd_set["coverage_percent"] = float(coverage_percent)
    await _upsert(session_id, {"$set": upd_set,
                                  "$setOnInsert": {"session_id": session_id}})
    return {"ok": True, "session_id": session_id}


# ── Health snapshot for the cockpit tile ────────────────────────────

async def health_snapshot(days: int = 7) -> dict:
    """Return rolling-window health stats for the Cockpit tile.

    Returns:
      ok                   : True
      window_days          : echo
      sessions_count       : int
      sessions_succeeded   : int
      success_rate         : 0..1
      tool_calls_total     : int
      tools_failed         : int
      failure_rate         : 0..1
      prose_filter_scrubs  : int   (Rule Zero hygiene trend)
      loops_detected       : int
      avg_usd_per_session  : float | None
      status               : "green"|"yellow"|"red"
      reasons              : list[str] — why the status is what it is
    """
    if _db is None:
        return {"ok": False, "error": "DB not wired"}

    since_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        cursor = _db[_COLLECTION].find(
            {"updated_at": {"$gte": since_iso}},
            {"_id": 0},
        )
        docs = await cursor.to_list(length=2000)
    except Exception as e:
        return {"ok": False, "error": f"query failed: {e}"}

    sessions = len(docs)
    succeeded = sum(1 for d in docs if d.get("task_success"))
    tool_total = sum(int(d.get("tool_calls_total") or 0) for d in docs)
    tool_failed = sum(int(d.get("tools_failed") or 0) for d in docs)
    scrubs = sum(int(d.get("prose_filter_scrubs") or 0) for d in docs)
    loops = sum(
        sum(v for v in (d.get("loops_detected") or {}).values())
        for d in docs
    )
    costs = [float(d["usd_cost"]) for d in docs if isinstance(d.get("usd_cost"), (int, float))]
    avg_cost = round(sum(costs) / len(costs), 4) if costs else None

    success_rate = (succeeded / sessions) if sessions else 1.0
    failure_rate = (tool_failed / tool_total) if tool_total else 0.0

    # Status calculation
    reasons: list[str] = []
    status = "green"
    if sessions == 0:
        status = "green"
        reasons.append("no_sessions_in_window")
    else:
        if success_rate < 0.5:
            status = "red"
            reasons.append(f"session_success_rate {success_rate:.0%} < 50%")
        elif success_rate < 0.8:
            status = "yellow"
            reasons.append(f"session_success_rate {success_rate:.0%} < 80%")
        if failure_rate > 0.20:
            status = "red"
            reasons.append(f"tool_failure_rate {failure_rate:.0%} > 20%")
        elif failure_rate > 0.10:
            status = "yellow" if status == "green" else status
            reasons.append(f"tool_failure_rate {failure_rate:.0%} > 10%")
        if loops > 3:
            status = "yellow" if status == "green" else status
            reasons.append(f"{loops} loop-halts in {days}d")

    return {
        "ok":                  True,
        "window_days":         days,
        "sessions_count":      sessions,
        "sessions_succeeded":  succeeded,
        "success_rate":        round(success_rate, 3),
        "tool_calls_total":    tool_total,
        "tools_failed":        tool_failed,
        "failure_rate":        round(failure_rate, 3),
        "prose_filter_scrubs": scrubs,
        "loops_detected":      loops,
        "avg_usd_per_session": avg_cost,
        "status":              status,
        "reasons":             reasons,
    }


__all__ = [
    "set_db",
    "record_tool_call", "record_prose_scrub", "record_loop_halt",
    "record_session_end", "health_snapshot",
]
