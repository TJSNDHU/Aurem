"""
Autonomous Repair Router — iter 281
═══════════════════════════════════════════════════════════════════════

Admin-only visibility + control surface for the autonomous repair loop.

Endpoints:
  GET  /api/admin/autonomous-repair/status
  GET  /api/admin/autonomous-repair/events
  POST /api/admin/autonomous-repair/trigger      (manual fire)
  POST /api/admin/autonomous-repair/pause
  POST /api/admin/autonomous-repair/resume
  GET  /api/admin/autonomous-repair/health       (public probe)
"""
from __future__ import annotations

import os
from typing import Optional

import jwt
from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/api/admin/autonomous-repair", tags=["Autonomous Repair"])

_db = None
_jwt_secret: Optional[str] = None
_jwt_alg: str = "HS256"


def set_db(db) -> None:
    global _db
    _db = db
    # Propagate into engine
    try:
        from services.autonomous_repair_engine import set_db as _eng_set_db
        _eng_set_db(db)
    except Exception:
        pass


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


@router.get("/status")
async def status(authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.autonomous_repair_engine import status_snapshot
    return await status_snapshot()


@router.get("/events")
async def events(
    limit: int = 30,
    authorization: Optional[str] = Header(None),
):
    _verify_admin(authorization)
    if _db is None:
        return {"events": [], "count": 0}
    limit = max(1, min(int(limit or 30), 200))
    docs = []
    async for d in _db.autonomous_repair_events.find(
        {}, {"_id": 0, "ts": 0}
    ).sort("ts_iso", -1).limit(limit):
        docs.append(d)
    return {"events": docs, "count": len(docs)}


@router.post("/trigger")
async def trigger(authorization: Optional[str] = Header(None)):
    admin = _verify_admin(authorization)
    from services.autonomous_repair_engine import run_cycle_once
    result = await run_cycle_once()
    return {"triggered_by": admin.get("email") or admin.get("sub"), "result": result}


@router.post("/pause")
async def pause(authorization: Optional[str] = Header(None)):
    admin = _verify_admin(authorization)
    from services.autonomous_repair_engine import set_enabled
    return await set_enabled(False, actor=admin.get("email") or "admin")


@router.post("/resume")
async def resume(authorization: Optional[str] = Header(None)):
    admin = _verify_admin(authorization)
    from services.autonomous_repair_engine import set_enabled
    return await set_enabled(True, actor=admin.get("email") or "admin")


@router.get("/health")
async def health():
    return {"status": "ok", "component": "autonomous_repair", "db_ready": _db is not None}


# ═══════════════════════════════════════════════════════════════════════
# iter 285 — Auto-Heal Bridge: pending-fix approval flow
# ═══════════════════════════════════════════════════════════════════════
# Tier 3 fixes stage to `pending_code_fixes` with a pre-generated
# [auto-heal] commit message. Operator reviews → approves → the commit
# message surfaces in the UI for one-click copy. When the operator uses
# Emergent "Save to GitHub", the [auto-heal] prefix triggers the GitHub
# workflow which fires the Emergent deploy webhook (if configured).
# Honest limit: we do NOT git commit from the pod directly — that needs
# the operator's GitHub creds on Emergent. We prep the message.

@router.get("/pending-fixes")
async def pending_fixes(
    status_filter: Optional[str] = None,
    limit: int = 50,
    authorization: Optional[str] = Header(None),
):
    """List staged code fixes from the autonomous repair engine."""
    _verify_admin(authorization)
    if _db is None:
        return {"fixes": [], "count": 0}
    limit = max(1, min(int(limit or 50), 200))
    q: dict = {}
    if status_filter:
        q["status"] = status_filter
    docs = []
    async for d in _db.pending_code_fixes.find(q, {"_id": 0}).sort(
        "staged_at", -1
    ).limit(limit):
        docs.append(d)
    return {"fixes": docs, "count": len(docs)}


@router.post("/pending-fixes/{fix_id}/approve")
async def approve_fix(fix_id: str, authorization: Optional[str] = Header(None)):
    """Mark a staged fix as approved_for_deploy. Returns the [auto-heal]
    commit message the operator can paste into Emergent's Save-to-GitHub."""
    admin = _verify_admin(authorization)
    if _db is None:
        raise HTTPException(500, "db_unset")
    from datetime import datetime, timezone
    res = await _db.pending_code_fixes.find_one_and_update(
        {"id": fix_id, "status": {"$in": ["needs_human_review", "rejected"]}},
        {"$set": {
            "status": "approved_for_deploy",
            "approved_by": admin.get("email") or admin.get("sub") or "admin",
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }},
        return_document=True,
        projection={"_id": 0},
    )
    if not res:
        raise HTTPException(404, f"fix {fix_id} not found or already deployed")
    # Record to truth_ledger
    try:
        from services import truth_ledger
        await truth_ledger.record_success(
            actor="autonomous_repair_bridge",
            description=f"Code fix approved for deploy: {fix_id}",
            evidence={"fix_id": fix_id, "commit_message": res.get("commit_message"),
                      "approver": res.get("approved_by")},
        )
    except Exception:
        pass
    return {
        "ok": True,
        "fix": res,
        "commit_message": res.get("commit_message"),
        "next_step": "Paste commit_message into Emergent Save-to-GitHub to fire [auto-heal] workflow",
    }


@router.post("/pending-fixes/{fix_id}/reject")
async def reject_fix(
    fix_id: str,
    authorization: Optional[str] = Header(None),
):
    """Mark a staged fix as rejected — will not be deployed."""
    admin = _verify_admin(authorization)
    if _db is None:
        raise HTTPException(500, "db_unset")
    from datetime import datetime, timezone
    res = await _db.pending_code_fixes.find_one_and_update(
        {"id": fix_id},
        {"$set": {
            "status": "rejected",
            "rejected_by": admin.get("email") or admin.get("sub") or "admin",
            "rejected_at": datetime.now(timezone.utc).isoformat(),
        }},
        return_document=True,
        projection={"_id": 0},
    )
    if not res:
        raise HTTPException(404, f"fix {fix_id} not found")
    return {"ok": True, "fix": res}


@router.get("/pending-fixes/stats")
async def pending_fix_stats(authorization: Optional[str] = Header(None)):
    """Count by status — powers the AutonomousRepairPanel badge."""
    _verify_admin(authorization)
    if _db is None:
        return {"needs_human_review": 0, "approved_for_deploy": 0, "rejected": 0}
    pipeline = [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]
    out = {"needs_human_review": 0, "approved_for_deploy": 0, "rejected": 0, "total": 0}
    async for row in _db.pending_code_fixes.aggregate(pipeline):
        key = row.get("_id") or "unknown"
        out[key] = row["n"]
        out["total"] += row["n"]
    return out


# iter 285.7 — sentinel noise purge (abort/cancel fetch events are not real failures)
@router.post("/purge-user-abort-noise")
async def purge_user_abort_noise(authorization: Optional[str] = Header(None)):
    """Remove 'signal is aborted' / AbortError entries from sentinel_alerts +
    client_errors. These are component-unmount artifacts, not real failures.
    Called manually once after the sentinel.js fix, or can be re-run anytime."""
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(500, "db_unset")
    abort_filter = {
        "$or": [
            {"message": {"$regex": "signal is aborted", "$options": "i"}},
            {"message": {"$regex": "AbortError", "$options": "i"}},
            {"sample": {"$regex": "signal is aborted", "$options": "i"}},
        ]
    }
    ce_deleted = (await _db.client_errors.delete_many(abort_filter)).deleted_count
    sa_deleted = (await _db.sentinel_alerts.delete_many(abort_filter)).deleted_count
    # Also close any resolved sentinel_clusters
    try:
        from services import truth_ledger
        await truth_ledger.record_success(
            actor="autonomous_repair",
            description=f"Purged abort-noise: {ce_deleted} client_errors + {sa_deleted} sentinel_alerts",
            evidence={"ce_deleted": ce_deleted, "sa_deleted": sa_deleted},
        )
    except Exception:
        pass
    return {"ok": True, "client_errors_deleted": ce_deleted,
            "sentinel_alerts_deleted": sa_deleted}


# iter 320.3 — purge polling-endpoint network-failure noise. Same idea as
# the abort purge above: these events fire on transient blips when a tab is
# polling every 30s. They are NEVER actionable — they're a tax on the
# Sentinel review queue and dilute real signals.
_POLLING_PATTERNS = [
    "/api/public/aurem-stats", "/api/public/config", "/api/health",
    "/api/admin/sentinel/overview", "/api/admin/pillars-map",
    "/api/pillars/health", "/api/agents/board/",
    "/api/admin/system-pulse-live", "/api/admin/truth-ledger",
    "/api/admin/transparency/wall", "/api/admin/autopilot",
    "/api/admin/autonomous-repair", "/api/admin/deploy-drift",
    "/api/admin/cache/", "/api/admin/builder/", "/api/admin/evolver/",
    "/api/admin/legion/", "/api/admin/wiring-audit",
    "/api/admin/system-audit", "/api/admin/db-indexes/",
    "/api/admin/breakers/status", "/api/admin/mission-control/",
    "/api/empire-hud/nodes", "/api/customer/pixel/status",
]


@router.post("/purge-polling-network-noise")
async def purge_polling_network_noise(authorization: Optional[str] = Header(None)):
    """Remove network_failure entries on known polling endpoints — they're
    transient blips, not bugs."""
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(500, "db_unset")
    or_clauses = [{"url": {"$regex": p, "$options": "i"}} for p in _POLLING_PATTERNS]
    ce_filter = {"type": "network_failure", "$or": or_clauses}
    deleted = (await _db.client_errors.delete_many(ce_filter)).deleted_count
    return {"ok": True, "client_errors_deleted": deleted,
            "patterns_used": len(_POLLING_PATTERNS)}
