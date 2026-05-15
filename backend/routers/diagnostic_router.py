"""
AUREM Full Diagnostic Endpoint
GET /api/admin/full-diagnostic
Admin JWT required.
Returns complete system snapshot for external AI analysis.
"""

import os
import time
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin Diagnostics"])

_db = None

def set_db(db):
    global _db
    _db = db


async def _require_admin(request: Request):
    """Bug-fix #172 (R21): use canonical admin guard.
    Eliminates: (a) email-bypass, (b) third hardcoded JWT default
    `"aurem-secret-key"` which let forged tokens pass even without the
    real JWT_SECRET.
    """
    from utils.admin_guard import verify_admin
    return verify_admin(request.headers.get("Authorization", ""))


async def _get_database_info() -> Dict[str, Any]:
    """Collect MongoDB diagnostics."""
    if _db is None:
        return {"status": "not_connected"}

    try:
        collections = await _db.list_collection_names()
        doc_counts = {}
        for coll in sorted(collections):
            try:
                count = await _db[coll].estimated_document_count()
                doc_counts[coll] = count
            except Exception:
                doc_counts[coll] = "error"

        # Check indexes
        missing_indexes = []
        critical_collections = ["users", "api_keys", "scan_history", "api_audit_log", "conversations"]
        for coll in critical_collections:
            if coll in collections:
                try:
                    indexes = await _db[coll].index_information()
                    if len(indexes) <= 1:  # Only _id index
                        missing_indexes.append(f"{coll}: only _id index")
                except Exception:
                    pass

        return {
            "status": "connected",
            "collections_count": len(collections),
            "collections": sorted(collections),
            "document_counts": doc_counts,
            "total_documents": sum(v for v in doc_counts.values() if isinstance(v, int)),
            "missing_indexes": missing_indexes,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _get_route_info(app) -> Dict[str, Any]:
    """Collect all registered routes."""
    routes = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            for method in route.methods:
                routes.append({"method": method, "path": route.path})
    return {
        "total": len(routes),
        "routes": sorted(routes, key=lambda r: r["path"]),
    }


def _get_env_info() -> Dict[str, Any]:
    """Check which env vars are set vs missing."""
    expected = [
        "MONGO_URL", "DB_NAME", "JWT_SECRET", "SECRET_KEY",
        "EMERGENT_API_KEY", "OPENROUTER_API_KEY", "DEEPGRAM_API_KEY",
        "GOOGLE_PAGESPEED_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY",
        "STRIPE_WEBHOOK_SECRET", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN",
        "SENDGRID_API_KEY", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
        "WHAPI_API_TOKEN", "REDIS_URL", "HF_TOKEN",
    ]
    env_set = [k for k in expected if os.environ.get(k)]
    env_missing = [k for k in expected if not os.environ.get(k)]
    return {"set": env_set, "missing": env_missing}


async def _get_error_logs() -> list:
    """Get recent errors from DB audit log."""
    if _db is None:
        return []
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        errors = await _db.api_audit_log.find(
            {"status_code": {"$gte": 500}, "timestamp": {"$gte": cutoff}},
            {"_id": 0, "path": 1, "status_code": 1, "timestamp": 1, "error": 1}
        ).sort("timestamp", -1).limit(50).to_list(50)
        return errors
    except Exception:
        return []


async def _get_scheduler_status() -> Dict[str, Any]:
    """Check running asyncio tasks for scheduler health."""
    tasks = asyncio.all_tasks()
    task_names = [t.get_name() for t in tasks if not t.done()]

    expected = [
        "daily_digest_scheduler", "abandoned_cart_scheduler",
        "operational_alerts_scheduler", "day21_review_scheduler",
        "whatsapp_crm_scheduler", "birthday_bonus_scheduler",
        "auto_heal_scheduler", "auto_repair_scheduler",
        "self_repair_loop",
    ]
    running = [s for s in expected if any(s in tn for tn in task_names)]
    missing = [s for s in expected if s not in running]

    return {
        "total_asyncio_tasks": len(task_names),
        "expected_schedulers": expected,
        "running": running,
        "missing": missing,
    }


def _get_performance_score(db_info, env_info, scheduler_info, errors, route_count=0) -> int:
    """Calculate overall health score 0-100."""
    score = 100

    # DB penalties
    if db_info.get("status") != "connected":
        score -= 40
    if db_info.get("missing_indexes"):
        score -= 2 * len(db_info["missing_indexes"])

    # Env penalties — only critical ones matter heavily
    missing_critical = [k for k in env_info.get("missing", [])
                        if k in ("MONGO_URL", "JWT_SECRET", "SECRET_KEY")]
    score -= 15 * len(missing_critical)
    # Optional env vars are minor penalties
    optional_missing = len(env_info.get("missing", [])) - len(missing_critical)
    score -= min(10, optional_missing)  # cap at -10

    # Scheduler penalties
    missing_schedulers = len(scheduler_info.get("missing", []))
    score -= 2 * missing_schedulers

    # Error penalties
    if len(errors) > 20:
        score -= 10
    elif len(errors) > 5:
        score -= 5

    # Route bloat penalty
    if route_count > 1000:
        score -= 10
    elif route_count > 500:
        score -= 5

    return max(0, min(100, score))


def _generate_suggestions(db_info, env_info, scheduler_info, errors) -> list:
    """Generate actionable suggestions based on diagnostics."""
    suggestions = []

    if db_info.get("missing_indexes"):
        suggestions.append({
            "priority": "HIGH",
            "area": "database",
            "suggestion": f"Add indexes to: {', '.join(db_info['missing_indexes'])}",
        })

    critical_missing = [k for k in env_info.get("missing", [])
                        if k in ("STRIPE_SECRET_KEY", "GOOGLE_PAGESPEED_API_KEY")]
    for key in critical_missing:
        suggestions.append({
            "priority": "HIGH",
            "area": "env",
            "suggestion": f"Set {key} to enable revenue/scanning features",
        })

    optional_missing = [k for k in env_info.get("missing", [])
                        if k not in ("STRIPE_SECRET_KEY", "GOOGLE_PAGESPEED_API_KEY",
                                     "MONGO_URL", "DB_NAME", "JWT_SECRET", "SECRET_KEY")]
    if optional_missing:
        suggestions.append({
            "priority": "LOW",
            "area": "env",
            "suggestion": f"Optional services disabled (missing keys): {', '.join(optional_missing)}",
        })

    if scheduler_info.get("missing"):
        suggestions.append({
            "priority": "MEDIUM",
            "area": "schedulers",
            "suggestion": f"Missing schedulers: {', '.join(scheduler_info['missing'])}. May need restart.",
        })

    if len(errors) > 10:
        suggestions.append({
            "priority": "HIGH",
            "area": "errors",
            "suggestion": f"{len(errors)} server errors in last 24h — investigate top failing endpoints.",
        })

    return suggestions


@router.get("/full-diagnostic")
async def full_diagnostic(request: Request, admin=Depends(_require_admin)):
    """Complete system snapshot for AI analysis tools."""
    start = time.time()

    db_info, scheduler_info, errors = await asyncio.gather(
        _get_database_info(),
        _get_scheduler_status(),
        _get_error_logs(),
    )

    env_info = _get_env_info()
    route_info = _get_route_info(request.app)
    perf_score = _get_performance_score(db_info, env_info, scheduler_info, errors, route_info["total"])
    suggestions = _generate_suggestions(db_info, env_info, scheduler_info, errors)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "diagnostic_duration_ms": round((time.time() - start) * 1000, 1),
        "database": db_info,
        "routes": route_info,
        "env_vars": env_info,
        "schedulers": scheduler_info,
        "errors_last_24h": errors,
        "performance_score": perf_score,
        "suggestions": suggestions,
    }
