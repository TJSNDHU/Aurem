"""
Root Command Router — Unified Error Intelligence Hub (iter 266).
═══════════════════════════════════════════════════════════════

Single aggregation endpoint that powers /admin/root-command. Fans out in
parallel to the 5 dashboards that previously lived in separate UIs
(AutoFixer, DevConsole, SelfRepair, SystemAudit, Shannon) and returns one
JSON blob ready to render.

The goal is *Root Cause*, not *Patch Cosmetics*. Every aggregated row
exposes the file + line that originated the failure, so the next step —
"Stem-Fix" — can refactor the source module rather than patch the symptom.

Endpoints:
  GET  /api/admin/root-command/overview  — aggregate every error-finder source

Collections read (never written by this router):
  • db.repair_fixes         — Pillar 3 Auto-Repair pending patches
  • db.client_errors        — Sentinel-captured browser/API errors
  • db.repair_suggestions   — AI-generated repair suggestions awaiting human OK
  • db.shannon_reports      — Defensive security posture history
  • db.system_audit         — Monthly heartbeat audit
  • db.migrations           — DB migration audit trail
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt
from fastapi import APIRouter, Header, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/root-command", tags=["Root Command"])

_db = None
_jwt_secret: Optional[str] = None
_jwt_alg: str = "HS256"


def set_db(db):
    global _db
    _db = db


def set_jwt(secret: str, algorithm: str = "HS256") -> None:
    global _jwt_secret, _jwt_alg
    _jwt_secret = secret
    _jwt_alg = algorithm


def _verify_admin(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1],
            _jwt_secret or (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured"))),
            algorithms=[_jwt_alg],
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    if not (payload.get("is_admin") or payload.get("is_super_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


# ══════════════════════════════════════════════════════════════════════
# Individual gather functions — run in parallel via asyncio.gather
# Each returns a small dict; a failure in one source MUST NOT fail the
# whole aggregation (always wrap in try/except → {"status": "error"}).
# ══════════════════════════════════════════════════════════════════════

async def _gather_auto_fixer():
    """Pillar 3 — pending repair patches grouped by status."""
    try:
        pipeline = [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]
        buckets = {}
        async for row in _db.repair_fixes.aggregate(pipeline):
            buckets[row["_id"] or "unknown"] = row["n"]
        total = sum(buckets.values())

        # Latest 3 pending — shows root file:line so Stem-Fix has a target
        latest = await _db.repair_fixes.find(
            {"status": {"$in": ["pending", "approved"]}},
            {"_id": 0, "id": 1, "category": 1, "severity": 1, "title": 1,
             "file": 1, "line": 1, "status": 1, "created_at": 1},
            sort=[("created_at", -1)],
            limit=3,
        ).to_list(3)

        return {
            "status": "ok",
            "total": total,
            "by_status": buckets,
            "latest_pending": latest,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:100]}


async def _gather_sentinel_errors():
    """Browser/API errors captured by Sentinel Client."""
    try:
        now = datetime.now(timezone.utc)
        one_hour = now - timedelta(hours=1)
        one_day = now - timedelta(days=1)

        errors_1h = await _db.client_errors.count_documents(
            {"created_at": {"$gte": one_hour.isoformat()}}
        )
        errors_24h = await _db.client_errors.count_documents(
            {"created_at": {"$gte": one_day.isoformat()}}
        )
        suggestions_pending = await _db.repair_suggestions.count_documents(
            {"status": "pending"}
        )

        # Latest 3 unresolved (highest frequency wins)
        top_errors = await _db.client_errors.find(
            {"resolved": {"$ne": True}},
            {"_id": 0, "id": 1, "error_type": 1, "message": 1, "source_file": 1,
             "source_line": 1, "count": 1, "last_seen": 1},
            sort=[("count", -1)],
            limit=3,
        ).to_list(3)

        return {
            "status": "ok",
            "errors_1h": errors_1h,
            "errors_24h": errors_24h,
            "suggestions_pending": suggestions_pending,
            "top_errors": top_errors,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)[:100]}


async def _gather_shannon():
    """Defensive security posture."""
    try:
        latest = await _db.shannon_reports.find_one(
            {},
            {"_id": 0, "score": 1, "critical_count": 1, "high_count": 1,
             "medium_count": 1, "low_count": 1, "audited_at": 1},
            sort=[("audited_at", -1)],
        )
        if not latest:
            return {"status": "ok", "score": None, "note": "no audit yet"}
        return {"status": "ok", **latest}
    except Exception as e:
        return {"status": "error", "error": str(e)[:100]}


async def _gather_system_audit():
    """Monthly heartbeat audit verdict + red flags."""
    try:
        latest = await _db.system_audit.find_one(
            {},
            {"_id": 0, "verdict": 1, "red_flags": 1, "generated_at": 1,
             "summary": 1},
            sort=[("generated_at", -1)],
        )
        if not latest:
            return {"status": "ok", "verdict": None, "note": "no audit yet"}
        return {"status": "ok", **latest}
    except Exception as e:
        return {"status": "error", "error": str(e)[:100]}


async def _gather_infra_health():
    """Live infra health — MongoDB, Redis, 4 pillar workers."""
    checks = {}

    # MongoDB
    try:
        await asyncio.wait_for(_db.command("ping"), timeout=1.0)
        checks["mongodb"] = "ok"
    except Exception:
        checks["mongodb"] = "error"

    # Redis
    try:
        from utils.redis_pool import get_async_redis
        r = await asyncio.wait_for(get_async_redis(), timeout=0.5)
        if r is not None:
            await asyncio.wait_for(r.ping(), timeout=0.3)
            checks["redis"] = "ok"
        else:
            checks["redis"] = "fallback_memory"
    except Exception:
        checks["redis"] = "fallback_memory"

    # Pillar workers — count tasks prefixed p1:/p2:/p3:/p4:
    try:
        tasks = asyncio.all_tasks()
        task_names = [t.get_name() for t in tasks if not t.done()]
        pillars = {
            "p1_sales":       sum(1 for n in task_names if n.startswith("p1:")),
            "p2_billing":     sum(1 for n in task_names if n.startswith("p2:")),
            "p3_monitor":     sum(1 for n in task_names if n.startswith("p3:")),
            "p4_command_hub": sum(1 for n in task_names if n.startswith("p4:")),
        }
        checks["pillars"] = pillars
        checks["total_schedulers"] = sum(pillars.values())
    except Exception:
        checks["pillars"] = "unknown"

    return {"status": "ok", **checks}


async def _gather_migrations():
    """DB migration audit trail — shows if stem-fix migrations have run."""
    try:
        recent = await _db.migrations.find(
            {},
            {"_id": 1, "ran_at": 1, "report": 1, "total_leads": 1},
            sort=[("ran_at", -1)],
            limit=3,
        ).to_list(3)
        return {"status": "ok", "count": len(recent), "recent": recent}
    except Exception as e:
        return {"status": "error", "error": str(e)[:100]}


# ══════════════════════════════════════════════════════════════════════
# Primary endpoint — parallel fan-out
# ══════════════════════════════════════════════════════════════════════
@router.get("/overview")
async def overview(authorization: Optional[str] = Header(None)):
    """Aggregate everything the error-finder dashboards need, in parallel.

    The response is one flat dict so the frontend can mount the whole page
    from a single network round-trip instead of 6 concurrent XHRs.
    """
    _verify_admin(authorization)

    if _db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    # Parallel fan-out — every gather is independent and must not block
    # siblings. Exceptions per-source are caught inside each function.
    (
        auto_fixer,
        sentinel_errors,
        shannon,
        system_audit,
        infra,
        migrations,
    ) = await asyncio.gather(
        _gather_auto_fixer(),
        _gather_sentinel_errors(),
        _gather_shannon(),
        _gather_system_audit(),
        _gather_infra_health(),
        _gather_migrations(),
    )

    # Verdict heuristic — if ANY source says "error", page shows yellow banner
    sources = [auto_fixer, sentinel_errors, shannon, system_audit, migrations]
    degraded = [s for s in sources if s.get("status") == "error"]
    verdict = "healthy" if not degraded else "degraded"

    # Aggregate counters — a single number operators look at first
    total_action_items = (
        (auto_fixer.get("by_status", {}).get("pending", 0))
        + (sentinel_errors.get("suggestions_pending", 0))
        + (len(system_audit.get("red_flags", []) or []))
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "total_action_items": total_action_items,
        "sources": {
            "auto_fixer":       auto_fixer,
            "sentinel_errors":  sentinel_errors,
            "shannon":          shannon,
            "system_audit":     system_audit,
            "infra":            infra,
            "migrations":       migrations,
        },
        "degraded_sources": [s for s in degraded],
    }


@router.get("/health")
async def root_command_health():
    """Unauthenticated mini-probe — does the router itself work?"""
    return {"status": "ok", "component": "root-command", "db_ready": _db is not None}


@router.get("/workers")
async def workers(authorization: Optional[str] = Header(None)):
    """Detailed introspection of every live pillar worker task.

    Returns name, done/cancelled state, and exception (if any) so you can
    pinpoint which scheduler exited vs which is still running.
    """
    _verify_admin(authorization)
    tasks = asyncio.all_tasks()
    rows = []
    for t in tasks:
        name = t.get_name()
        if not name.startswith(("p1:", "p2:", "p3:", "p4:")):
            continue
        entry = {
            "name": name,
            "done": t.done(),
            "cancelled": t.cancelled() if t.done() else False,
        }
        if t.done() and not t.cancelled():
            exc = t.exception()
            entry["exception"] = str(exc)[:300] if exc else None
        rows.append(entry)

    # Split by pillar + by state
    by_pillar = {"p1": [], "p2": [], "p3": [], "p4": []}
    for r in rows:
        prefix = r["name"].split(":", 1)[0]
        by_pillar.setdefault(prefix, []).append(r)

    # Also list the "expected" set the worker startup logs recorded, so
    # operator can see which ones vanished between attach + now.
    return {
        "ok": True,
        "live_count": sum(1 for r in rows if not r["done"]),
        "done_count": sum(1 for r in rows if r["done"]),
        "by_pillar": by_pillar,
        "rows": rows,
    }
