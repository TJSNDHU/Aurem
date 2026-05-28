"""
services/cto_learning.py — iter D-53

Self-learning core for AUREM CTO. The agent records what worked and
what didn't, then surfaces confidence stats for similar future tasks.

Hard rule (founder mandate): a learning row is ONLY persisted when the
outcome is system-verified — never on CTO self-report. We accept
`verified_by` in {"code_green", "github_green", "deploy_green",
"user_thumbs_up"}; anything else is rejected with `403 unverified`.

Storage
-------
collection `cto_learnings`
  {
    _id:          UUID,
    task_type:    str   (e.g. "mobile_css_fix"),
    approach:     str   (short label describing the strategy),
    result:       "success" | "failure",
    verified_by:  str   (which D-52 layer confirmed this),
    metadata:     dict  (commit_sha, iter, error_text, etc.),
    actor:        str   (user email),
    ts:           ISO datetime,
    week_iso:     str   ("2026-W22") — for weekly aggregation,
  }

collection `cto_weekly_reports`
  {
    week_iso:        "2026-W22",
    generated_at:    iso,
    learnings_added: int,
    success_rate:    float,
    top_patterns:    [{task_type, approach, n, success_rate}, ...],
    failed_patterns: [{task_type, approach, n, last_error}, ...],
  }
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

_db = None
_VALID_VERIFIED_BY = {
    "code_green", "github_green", "deploy_green", "user_thumbs_up",
}


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _week_iso(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


async def record_outcome(*, task_type: str, approach: str, result: str,
                          verified_by: str, actor: str,
                          metadata: dict[str, Any] | None = None
                          ) -> dict[str, Any]:
    """Persist a learning row. Returns the saved doc minus _id.

    Raises ValueError when the verified_by tag is not on the allowlist —
    callers must catch and surface a 403 to the chat.
    """
    if verified_by not in _VALID_VERIFIED_BY:
        raise ValueError(
            f"unverified_outcome (verified_by={verified_by!r} not in "
            f"{sorted(_VALID_VERIFIED_BY)})"
        )
    if result not in ("success", "failure"):
        raise ValueError(f"result must be 'success' or 'failure', got {result!r}")
    if _db is None:
        raise RuntimeError("cto_learning db not initialised")

    doc = {
        "_id":         str(uuid.uuid4()),
        "task_type":   (task_type or "").strip().lower()[:80],
        "approach":    (approach or "").strip()[:200],
        "result":      result,
        "verified_by": verified_by,
        "metadata":    metadata or {},
        "actor":       actor or "unknown",
        "ts":          _now(),
        "week_iso":    _week_iso(),
    }
    if not doc["task_type"] or not doc["approach"]:
        raise ValueError("task_type and approach are required")

    await _db.cto_learnings.insert_one(doc)
    out = {k: v for k, v in doc.items() if k != "_id"}
    return out


async def find_similar(task_type: str, limit: int = 5
                        ) -> list[dict[str, Any]]:
    """Return distinct approaches for the same task_type, ranked by
    success_rate then count. Each item:
      {approach, n, success, failure, success_rate, last_used_ts}
    """
    if _db is None:
        return []
    pipe = [
        {"$match": {"task_type": (task_type or "").strip().lower()}},
        {"$group": {
            "_id":           "$approach",
            "n":             {"$sum": 1},
            "success":       {"$sum": {"$cond": [{"$eq": ["$result", "success"]}, 1, 0]}},
            "failure":       {"$sum": {"$cond": [{"$eq": ["$result", "failure"]}, 1, 0]}},
            "last_used_ts":  {"$max": "$ts"},
        }},
        {"$project": {
            "approach":     "$_id",
            "_id":          0,
            "n":            1,
            "success":      1,
            "failure":      1,
            "success_rate": {
                "$cond": [{"$gt": ["$n", 0]},
                           {"$divide": ["$success", "$n"]}, 0],
            },
            "last_used_ts": 1,
        }},
        {"$sort":  {"success_rate": -1, "n": -1}},
        {"$limit": max(1, min(50, limit))},
    ]
    out: list[dict[str, Any]] = []
    async for d in _db.cto_learnings.aggregate(pipe):
        out.append(d)
    return out


async def overall_stats() -> dict[str, Any]:
    """Roll-up across all task types — used by the in-chat confidence
    badge and the /stats endpoint."""
    if _db is None:
        return {"total": 0, "success": 0, "failure": 0, "success_rate": 0.0,
                 "distinct_task_types": 0}
    total   = await _db.cto_learnings.count_documents({})
    success = await _db.cto_learnings.count_documents({"result": "success"})
    failure = await _db.cto_learnings.count_documents({"result": "failure"})
    distinct = await _db.cto_learnings.distinct("task_type")
    return {
        "total":               total,
        "success":             success,
        "failure":             failure,
        "success_rate":        (success / total) if total else 0.0,
        "distinct_task_types": len(distinct),
    }


async def confidence_for(task_type: str) -> dict[str, Any]:
    """Return `{n, success_rate, best_approach}` for a single task
    type — used by the chat to render the confidence badge BEFORE
    replying. Conservative: returns `n=0` if no rows exist."""
    rows = await find_similar(task_type, limit=1)
    if not rows:
        return {"n": 0, "success_rate": 0.0, "best_approach": ""}
    top = rows[0]
    return {
        "n":             top["n"],
        "success_rate":  top["success_rate"],
        "best_approach": top["approach"],
        "last_used_ts":  top.get("last_used_ts", ""),
    }


async def weekly_self_review(*, generate_for_week: str | None = None
                              ) -> dict[str, Any]:
    """Aggregate last 7 days and persist a report row. Idempotent
    per-week (replaces previous report for the same `week_iso`)."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    target_week = generate_for_week or _week_iso()
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    pipe_top = [
        {"$match": {"ts": {"$gte": since}, "result": "success"}},
        {"$group": {
            "_id":  {"task_type": "$task_type", "approach": "$approach"},
            "n":    {"$sum": 1},
        }},
        {"$sort":  {"n": -1}},
        {"$limit": 10},
    ]
    top: list[dict[str, Any]] = []
    async for d in _db.cto_learnings.aggregate(pipe_top):
        top.append({
            "task_type":    d["_id"]["task_type"],
            "approach":     d["_id"]["approach"],
            "n":            d["n"],
            "success_rate": 1.0,    # by definition (matched success)
        })

    pipe_fail = [
        {"$match": {"ts": {"$gte": since}, "result": "failure"}},
        {"$group": {
            "_id":        {"task_type": "$task_type", "approach": "$approach"},
            "n":          {"$sum": 1},
            "last_error": {"$last": "$metadata.error_text"},
        }},
        {"$sort":  {"n": -1}},
        {"$limit": 10},
    ]
    failed: list[dict[str, Any]] = []
    async for d in _db.cto_learnings.aggregate(pipe_fail):
        failed.append({
            "task_type":  d["_id"]["task_type"],
            "approach":   d["_id"]["approach"],
            "n":          d["n"],
            "last_error": d.get("last_error") or "",
        })

    learnings_added = await _db.cto_learnings.count_documents(
        {"ts": {"$gte": since}}
    )
    success_added = await _db.cto_learnings.count_documents(
        {"ts": {"$gte": since}, "result": "success"}
    )
    sr = (success_added / learnings_added) if learnings_added else 0.0

    report = {
        "_id":             f"weekly-{target_week}",
        "week_iso":        target_week,
        "generated_at":    _now(),
        "learnings_added": learnings_added,
        "success_rate":    round(sr, 3),
        "top_patterns":    top,
        "failed_patterns": failed,
    }
    await _db.cto_weekly_reports.update_one(
        {"_id": report["_id"]}, {"$set": report}, upsert=True,
    )
    logger.info(f"[cto-learning] weekly review {target_week}: "
                 f"added={learnings_added} sr={sr:.2f} "
                 f"top={len(top)} failed={len(failed)}")
    return {k: v for k, v in report.items() if k != "_id"}


async def latest_weekly_report() -> dict[str, Any] | None:
    if _db is None:
        return None
    return await _db.cto_weekly_reports.find_one(
        {}, {"_id": 0}, sort=[("generated_at", -1)],
    )
