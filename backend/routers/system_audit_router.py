"""
System Audit Router — Iteration 202
====================================
Admin-only Living Audit Dashboard.

GET  /api/admin/system-audit        — Live checklist of honest system state
GET  /api/admin/system-audit/health — Public service health

Surfaces:
  • Nightly onboarding health check last result
  • 4-agent status (paused, today_stats)
  • Scheduler jobs registered
  • Integration secrets present/missing
  • Recent critical errors from audit_chain
  • Pixel connectivity summary
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
import jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["System Audit"])

from config import JWT_SECRET  # safe 3-tier resolver (env -> file -> ephemeral)
_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    if _db is None:
        raise HTTPException(503, "DB not available")
    return _db


async def _require_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")

    # Accept admin, super_admin roles, or is_admin/is_super_admin flags
    role = payload.get("role", "")
    is_admin = payload.get("is_admin", False)
    is_super_admin = payload.get("is_super_admin", False)
    
    if role in ("admin", "super_admin") or is_admin or is_super_admin:
        return payload
    
    # Fallback: Verify from DB
    email = (payload.get("email") or payload.get("sub") or "").lower()
    if email:
        db = _get_db()
        u = await db.platform_users.find_one({"email": email}, {"_id": 0, "role": 1}) or \
            await db.users.find_one({"email": email}, {"_id": 0, "role": 1})
        if u and u.get("role") in ("admin", "super_admin"):
            return payload
    
    raise HTTPException(403, "Admin only")


# ═══════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════

REQUIRED_INTEGRATIONS = [
    ("stripe",           "STRIPE_SECRET_KEY"),
    ("stripe_pub",       "STRIPE_PUBLISHABLE_KEY"),
    ("resend_email",     "RESEND_API_KEY"),
    ("twilio",           "TWILIO_ACCOUNT_SID"),
    ("whapi",            "WHAPI_API_TOKEN"),
    ("openai_llm_key",   "EMERGENT_LLM_KEY"),
    ("google_places",    "GOOGLE_PLACES_API_KEY"),
    ("jwt",              "JWT_SECRET"),
    ("mongo",            "MONGO_URL"),
]

OPTIONAL_INTEGRATIONS = [
    ("postiz",           "POSTIZ_API_KEY"),
    ("stripe_referral",  "STRIPE_REFERRAL_COUPON_ID"),
    ("sendgrid",         "SENDGRID_API_KEY"),
    ("github",           "GITHUB_PAT"),
]


def _env_status(keys) -> List[Dict[str, Any]]:
    out = []
    for name, env in keys:
        present = bool((os.environ.get(env) or "").strip())
        out.append({"name": name, "env": env, "present": present})
    return out


async def _agent_snapshot(db) -> List[Dict[str, Any]]:
    try:
        from services.agents import all_agents
        return [a.snapshot() for a in all_agents()]
    except Exception as e:
        logger.debug(f"[SystemAudit] agents not available: {e}")
        return []


async def _last_health_check(db) -> Dict[str, Any]:
    try:
        doc = await db.aurem_health_checks.find_one({}, {"_id": 0}, sort=[("created_at", -1)])
        return doc or {"overall": "not_run_yet"}
    except Exception:
        return {"overall": "not_run_yet"}


async def _pixel_summary(db) -> Dict[str, Any]:
    try:
        total_keys = await db.api_keys.count_documents({"active": True})
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        active_24h = await db.patch_reports.count_documents({"reported_at": {"$gte": cutoff}})
        return {"active_keys": total_keys, "reports_24h": active_24h}
    except Exception:
        return {"active_keys": 0, "reports_24h": 0}


async def _recent_errors(db, limit: int = 5) -> List[Dict[str, Any]]:
    try:
        cursor = db.audit_chain.find(
            {"event_type": {"$regex": "error|failed|critical", "$options": "i"}},
            {"_id": 0, "event_type": 1, "timestamp": 1, "message": 1, "email": 1},
        ).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(limit)
    except Exception:
        return []


async def _scheduler_status() -> Dict[str, Any]:
    """Best-effort introspection of the APScheduler registered jobs."""
    try:
        # Try both common scheduler names in this codebase
        import routers.registry as _reg
        sched = getattr(_reg, "aurem_scheduler", None)
        if sched is None:
            return {"available": False}
        jobs = [{"id": j.id, "next_run": (j.next_run_time.isoformat() if j.next_run_time else None)} for j in sched.get_jobs()]
        return {"available": True, "running": sched.running, "jobs": jobs}
    except Exception as e:
        return {"available": False, "error": str(e)}


# ═══════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════

@router.get("/system-audit/health")
async def audit_health():
    return {"status": "ok", "service": "system-audit"}


@router.get("/system-audit")
async def system_audit(request: Request):
    """Return honest real-time state of all subsystems."""
    await _require_admin(request)
    db = _get_db()

    agents = await _agent_snapshot(db)
    last_hc = await _last_health_check(db)
    pixel = await _pixel_summary(db)
    scheduler = await _scheduler_status()
    errors = await _recent_errors(db)

    required = _env_status(REQUIRED_INTEGRATIONS)
    optional = _env_status(OPTIONAL_INTEGRATIONS)

    missing_required = [r["name"] for r in required if not r["present"]]

    # Overall verdict
    red_flags = []
    if missing_required:
        red_flags.append(f"Missing required secrets: {', '.join(missing_required)}")
    if last_hc.get("overall") == "FAIL":
        red_flags.append("Last nightly health check FAILED")
    if not scheduler.get("running"):
        red_flags.append("Scheduler not running")

    verdict = "healthy" if not red_flags else "degraded" if len(red_flags) < 3 else "critical"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "red_flags": red_flags,
        "health_check": last_hc,
        "agents": agents,
        "scheduler": scheduler,
        "integrations": {
            "required": required,
            "optional": optional,
        },
        "pixel": pixel,
        "recent_errors": errors,
    }


@router.post("/system-audit/run-health-check")
async def run_health_check_now(request: Request):
    """Trigger the nightly health-check dry run immediately."""
    await _require_admin(request)
    from services.nightly_health_check import nightly_health_check, set_db as set_hc_db
    set_hc_db(_get_db())
    result = await nightly_health_check()
    return result


@router.get("/db-indexes/status")
async def db_indexes_status(request: Request):
    """Return the result of the startup DB index build (safe-mode, add-only)."""
    await _require_admin(request)
    try:
        from server import app as _app    # import lazily to avoid circular
    except Exception:
        _app = None
    result = getattr(getattr(_app, "state", None), "db_index_result", None) if _app else None
    return result or {"status": "unknown", "note": "Index builder has not reported yet. Check backend logs."}


@router.post("/db-indexes/rebuild")
async def db_indexes_rebuild(request: Request):
    """Re-run the index builder immediately — idempotent, safe."""
    await _require_admin(request)
    db = _get_db()
    from services.db_index_builder import build_all_indexes
    return await build_all_indexes(db)


@router.get("/cache/stats")
async def cache_stats(request: Request):
    """Redis cache hit/miss stats. Returns zero-state if cache never used."""
    await _require_admin(request)
    from services.aurem_cache import get_stats
    return get_stats()


@router.get("/pixel-buffer/stats")
async def pixel_buffer_stats(request: Request):
    """Pixel event buffer stats — in-memory batching efficiency."""
    await _require_admin(request)
    from services.pixel_event_buffer import get_stats
    return get_stats()


@router.post("/pixel-buffer/flush")
async def pixel_buffer_flush(request: Request):
    """Manually flush the pixel event buffer now."""
    await _require_admin(request)
    from services.pixel_event_buffer import flush
    return await flush()


@router.get("/anomaly/status")
async def anomaly_status(request: Request):
    """Return last baseline + last alert timestamps."""
    await _require_admin(request)
    db = _get_db()
    state = await db.aurem_anomaly_state.find_one({"_key": "aurem_anomaly_state"}, {"_id": 0}) or {}
    # Last 10 alerts
    try:
        hist = await db.aurem_anomaly_log.find({}, {"_id": 0}).sort("fired_at", -1).limit(10).to_list(10)
    except Exception:
        hist = []
    return {"state": state, "recent_alerts": hist}


@router.post("/anomaly/run-now")
async def anomaly_run_now(request: Request):
    """Trigger the anomaly detector immediately."""
    await _require_admin(request)
    from services.anomaly_detector import detect_anomalies, set_db as set_ad_db
    set_ad_db(_get_db())
    return await detect_anomalies()
