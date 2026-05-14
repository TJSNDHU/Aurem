"""
AUREM QA Bot Router
─────────────────────────────────────────────────
Admin-only endpoints to view QA Bot (10-min pulse) + Deep QA Agent (weekly) results.

Routes:
  GET  /api/qa/pulse/latest       — summary of last pulse run
  GET  /api/qa/pulse/history      — last N pulse runs (lightweight)
  GET  /api/qa/pulse/endpoints    — per-endpoint stats over window
  POST /api/qa/pulse/run-now      — admin trigger immediate pulse

  GET  /api/qa/deep/latest        — last deep journey run
  GET  /api/qa/deep/history       — last N deep runs
  POST /api/qa/deep/run-now       — admin trigger immediate deep run
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, HTTPException, Request, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/qa", tags=["QA Bot"])

_db = None


def set_db(database):
    global _db
    _db = database
    # Propagate to services
    try:
        from services.qa_bot import set_db as set_qa_db
        set_qa_db(database)
    except Exception:
        pass
    try:
        from services.qa_agent_deep import set_db as set_deep_db
        set_deep_db(database)
    except Exception:
        pass


def _require_admin(request: Request):
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    token = auth.split(" ", 1)[1] if auth.startswith("Bearer ") else request.query_params.get("token")
    if not token:
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(token, (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured"))), algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    role = (payload.get("role") or "").lower()
    is_admin = bool(payload.get("is_admin") or payload.get("is_super_admin"))
    if role not in ("admin", "super_admin") and not is_admin:
        raise HTTPException(403, "Admin role required")
    return payload


# ══════════════════════════════════════════════════════════════
# Pulse endpoints (fast — 10-min sweep data)
# ══════════════════════════════════════════════════════════════
@router.get("/pulse/latest")
async def pulse_latest(request: Request):
    _require_admin(request)
    from services.qa_bot import get_latest_run
    doc = await get_latest_run()
    return {"ok": True, "run": doc}


@router.get("/pulse/history")
async def pulse_history(request: Request, limit: int = Query(50, ge=1, le=500)):
    _require_admin(request)
    from services.qa_bot import get_run_history
    runs = await get_run_history(limit)
    return {"ok": True, "count": len(runs), "runs": runs}


@router.get("/pulse/endpoints")
async def pulse_endpoints(request: Request, window_hours: int = Query(24, ge=1, le=720)):
    _require_admin(request)
    from services.qa_bot import get_endpoint_stats, CRITICAL_ENDPOINTS
    stats = await get_endpoint_stats(window_hours)
    return {
        "ok": True,
        "window_hours": window_hours,
        "total_endpoints": len(CRITICAL_ENDPOINTS),
        "endpoints": stats,
    }


@router.post("/pulse/run-now")
async def pulse_run_now(request: Request):
    _require_admin(request)
    from services.qa_bot import run_pulse_once
    result = await run_pulse_once()
    return {"ok": True, "run": result}


# ══════════════════════════════════════════════════════════════
# Deep QA endpoints (weekly — full journey simulation)
# ══════════════════════════════════════════════════════════════
@router.get("/deep/latest")
async def deep_latest(request: Request):
    _require_admin(request)
    from services.qa_agent_deep import get_latest_deep_run
    doc = await get_latest_deep_run()
    return {"ok": True, "run": doc}


@router.get("/deep/history")
async def deep_history(request: Request, limit: int = Query(20, ge=1, le=100)):
    _require_admin(request)
    from services.qa_agent_deep import get_deep_run_history
    runs = await get_deep_run_history(limit)
    return {"ok": True, "count": len(runs), "runs": runs}


@router.post("/deep/run-now")
async def deep_run_now(request: Request, journey_id: Optional[str] = None, analyze: bool = True):
    _require_admin(request)
    from services.qa_agent_deep import run_deep_qa, JOURNEYS
    if journey_id and journey_id not in JOURNEYS:
        raise HTTPException(400, f"Unknown journey. Options: {list(JOURNEYS.keys())}")
    result = await run_deep_qa([journey_id] if journey_id else None, analyze=analyze)
    return {"ok": True, "run": result}


@router.get("/deep/journeys")
async def deep_journeys(request: Request):
    _require_admin(request)
    from services.qa_agent_deep import JOURNEYS
    return {"ok": True, "journeys": [{"id": k, "label": v["label"]} for k, v in JOURNEYS.items()]}


# ─── Auto-Latency Guardian (iter 322f) ─────────────────────────────────
@router.get("/guardian/status")
async def guardian_status(request: Request):
    """Live state pill for the System Pulse dashboard."""
    _require_admin(request)
    from services.latency_guardian import get_guardian_status
    return await get_guardian_status(_db)


@router.get("/guardian/actions")
async def guardian_actions(request: Request, limit: int = Query(20, ge=1, le=100)):
    """Recent auto-fix actions (cache_flush, index_refresh, alert_admin, etc.)."""
    _require_admin(request)
    from services.latency_guardian import get_recent_actions
    return {"ok": True, "actions": await get_recent_actions(_db, limit)}


@router.post("/guardian/run-now")
async def guardian_run_now(request: Request):
    """Admin trigger — run a pulse + guardian pass immediately."""
    _require_admin(request)
    from services.qa_bot import run_pulse_once
    run = await run_pulse_once()
    return {"ok": True, "run": run}


@router.post("/guardian/clear-legacy-alerts")
async def guardian_clear_legacy_alerts(request: Request):
    """Admin trigger — purge legacy `alert_admin` rows (pre iter-322i Council
    Mode) so the dashboard pill turns green immediately. Autonomous flow
    no longer produces these; this is a one-time cleanup utility."""
    _require_admin(request)
    if _db is None:
        return {"ok": False, "error": "db_unavailable"}
    try:
        res = await _db.system_pulse_actions.delete_many(
            {"action_taken": "alert_admin"},
        )
        ack = await _db.admin_alerts.update_many(
            {"source": "latency_guardian", "ack": False},
            {"$set": {"ack": True, "auto_acked_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {
            "ok": True,
            "alerts_purged": res.deleted_count,
            "admin_alerts_acked": ack.modified_count,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# ─── Sovereign Watchdog (iter 322j) ────────────────────────────────────
@router.get("/watchdog/status")
async def watchdog_status(request: Request):
    """Live state pill — green/yellow/red — for the System Pulse dashboard."""
    _require_admin(request)
    from services.sovereign_watchdog import get_watchdog_status
    return await get_watchdog_status(_db)


@router.get("/watchdog/findings")
async def watchdog_findings(request: Request, limit: int = Query(20, ge=1, le=100)):
    """Recent watchdog findings + auto-fix outcomes."""
    _require_admin(request)
    from services.sovereign_watchdog import get_recent_findings
    return {"ok": True, "findings": await get_recent_findings(_db, limit)}


@router.post("/watchdog/run-now")
async def watchdog_run_now(request: Request):
    """Admin trigger — run a single Sovereign Watchdog scan immediately."""
    _require_admin(request)
    from services.sovereign_watchdog import scan_once
    return {"ok": True, "summary": await scan_once(_db)}

