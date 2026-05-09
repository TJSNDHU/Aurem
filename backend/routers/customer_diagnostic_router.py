"""
Customer Diagnostic Router — Admin endpoints
=============================================
GET  /api/admin/diagnostics/all              → list all tenants health
GET  /api/admin/diagnostics/customer/{bid}   → full detail
POST /api/admin/diagnostics/run/{bid}        → run check synchronously
POST /api/admin/diagnostics/fix/{bid}        → trigger repair pipeline
POST /api/admin/diagnostics/fix-action/{bid} → manual single-fix button
GET  /api/admin/diagnostics/repair-log/{bid} → recent repair history
GET  /api/admin/diagnostics/summary          → roll-up counts (for dashboard)

Admin-only (Bearer JWT with role=admin / super_admin).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
import jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/diagnostics", tags=["Customer Diagnostics"])

JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET:
    raise RuntimeError("CRITICAL: JWT_SECRET not set.")

_db = None


def set_db(database) -> None:
    global _db
    _db = database
    try:
        from services.customer_health_monitor import set_db as _set_hm_db
        _set_hm_db(database)
    except Exception:
        pass


def _get_db():
    if _db is None:
        raise HTTPException(503, "DB not available")
    return _db


async def _require_admin(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(
            auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"]
        )
    except Exception:
        raise HTTPException(401, "Invalid token")
    role = payload.get("role", "")
    if (role in ("admin", "super_admin")
            or payload.get("is_admin")
            or payload.get("is_super_admin")):
        return payload
    raise HTTPException(403, "Admin only")


# ─────────────────────────────────────────────────────────────

@router.get("/summary")
async def get_summary(request: Request) -> Dict[str, Any]:
    await _require_admin(request)
    db = _get_db()
    summary = await db.customer_health_summary.find_one(
        {"_id": "latest"}, {"_id": 0}
    )
    return summary or {"scanned": 0, "counts": {}, "checked_at": None}


@router.get("/all")
async def list_all(request: Request, status: Optional[str] = None,
                    limit: int = 200) -> Dict[str, Any]:
    await _require_admin(request)
    db = _get_db()
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    rows = await db.customer_health_log.find(
        q, {"_id": 0}
    ).sort("checked_at", -1).limit(min(limit, 500)).to_list(min(limit, 500))
    return {"count": len(rows), "tenants": rows}


@router.get("/customer/{business_id}")
async def get_customer(business_id: str, request: Request) -> Dict[str, Any]:
    await _require_admin(request)
    db = _get_db()
    doc = await db.customer_health_log.find_one(
        {"business_id": business_id}, {"_id": 0}
    )
    history = await db.customer_health_history.find(
        {"business_id": business_id}, {"_id": 0}
    ).sort("checked_at", -1).limit(20).to_list(20)
    repairs = await db.customer_repair_log.find(
        {"business_id": business_id}, {"_id": 0}
    ).sort("ts", -1).limit(20).to_list(20)
    return {
        "business_id": business_id,
        "current": doc,
        "history": history,
        "repairs": repairs,
    }


@router.post("/run/{business_id}")
async def run_now(business_id: str, request: Request) -> Dict[str, Any]:
    await _require_admin(request)
    from services.customer_health_monitor import check_tenant
    return await check_tenant(business_id)


@router.post("/run-all")
async def run_all_now(request: Request) -> Dict[str, Any]:
    await _require_admin(request)
    from services.customer_health_monitor import check_all_tenants
    return await check_all_tenants()


@router.post("/fix/{business_id}")
async def trigger_repair(business_id: str, request: Request) -> Dict[str, Any]:
    await _require_admin(request)
    from services.customer_health_monitor import check_tenant
    from services.customer_repair_pipeline import trigger_repair_pipeline
    summary = await check_tenant(business_id)
    if summary.get("status") == "healthy":
        return {"business_id": business_id, "outcome": "already_healthy"}
    return await trigger_repair_pipeline(
        business_id, summary.get("checks", {}), summary.get("status", "degraded")
    )


@router.post("/fix-action/{business_id}/{action}")
async def manual_fix(business_id: str, action: str,
                      request: Request) -> Dict[str, Any]:
    """Single-fix button from the admin panel — bypasses council for known
    safe actions, queues council for unsafe ones."""
    await _require_admin(request)
    from services.customer_fix_executors import apply_customer_fix, EXECUTORS
    if action not in EXECUTORS:
        raise HTTPException(400, f"Unknown action: {action}")
    ok = await apply_customer_fix(business_id, action)

    # Log the manual click
    try:
        from services.customer_repair_pipeline import _log_repair
        await _log_repair(
            business_id,
            {"fix": action, "description": f"manual:{action}",
             "confidence": 1.0, "safe": True},
            "manual_applied" if ok else "manual_failed",
        )
    except Exception:
        pass

    # Re-verify after manual fix
    try:
        from services.customer_health_monitor import check_tenant
        post = await check_tenant(business_id)
    except Exception:
        post = None

    return {"business_id": business_id, "action": action, "applied": ok,
            "post": post}


@router.get("/repair-log/{business_id}")
async def repair_log(business_id: str, request: Request,
                      limit: int = 50) -> Dict[str, Any]:
    await _require_admin(request)
    db = _get_db()
    rows = await db.customer_repair_log.find(
        {"business_id": business_id}, {"_id": 0}
    ).sort("ts", -1).limit(min(limit, 200)).to_list(min(limit, 200))
    return {"count": len(rows), "log": rows}


# ─────────────────────────────────────────────────────────────
# UNIFIED DIAGNOSTIC ENDPOINT (legacy spec compatibility)
# ─────────────────────────────────────────────────────────────

@router.get("/customer-detail/{business_id}")
async def customer_detail(business_id: str, request: Request) -> Dict[str, Any]:
    """Returns latest health + raw DB shapes that an admin would want to see
    when triaging a stuck tenant. Combines customer_360 lite data with
    the diagnostic checks."""
    await _require_admin(request)
    db = _get_db()
    user = await db.platform_users.find_one(
        {"business_id": business_id}, {"_id": 0, "password_hash": 0}
    )
    billing = await db.aurem_billing.find_one(
        {"business_id": business_id}, {"_id": 0}
    )
    workspace = await db.aurem_workspaces.find_one(
        {"business_id": business_id}, {"_id": 0}
    )
    onboarding = await db.aurem_onboarding.find_one(
        {"business_id": business_id}, {"_id": 0}
    )
    tenant = await db.tenant_customers.find_one(
        {"business_id": business_id}, {"_id": 0}
    )
    health = await db.customer_health_log.find_one(
        {"business_id": business_id}, {"_id": 0}
    )
    return {
        "business_id": business_id,
        "user": user,
        "billing": billing,
        "workspace": workspace,
        "onboarding": onboarding,
        "tenant": tenant,
        "health": health,
    }



# ─────────────────────────────────────────────────────────────
# /db-counts — raw collection counts for ground-truth verification
# ─────────────────────────────────────────────────────────────
# Founder reality-check endpoint. Returns the live document count for
# the canonical observability collections so we can prove from outside
# the pod (curl https://aurem.live/...) that the autonomous stack is
# actually running and accumulating data — not mocked/seeded.
@router.get("/db-counts")
async def get_db_counts(request: Request) -> Dict[str, Any]:
    await _require_admin(request)
    db = _get_db()
    from datetime import datetime, timezone

    collections = [
        "council_decisions",
        "council_decisions_detailed",
        "ora_brain_thoughts",
        "llm_costs",
        "llm_response_cache",
        "agent_actions",
        "repair_suggestions",
        "client_errors",
        "ora_dev_actions",
        "platform_users",
        "campaign_leads",
        "scheduled_followups",
        "auto_call_log",
    ]
    counts: Dict[str, int] = {}
    errors: Dict[str, str] = {}
    for name in collections:
        try:
            counts[name] = await db[name].count_documents({})
        except Exception as e:
            errors[name] = f"{type(e).__name__}: {e}"
    # 24h rollups for the most-active autonomous-stack tables.
    cutoff_24h = (datetime.now(timezone.utc).timestamp() - 86400)
    last24h: Dict[str, int] = {}
    try:
        last24h["council_decisions"] = await db.council_decisions.count_documents(
            {"ts": {"$gte": datetime.fromtimestamp(cutoff_24h, tz=timezone.utc)}}
        )
    except Exception:
        last24h["council_decisions"] = -1
    try:
        last24h["llm_costs"] = await db.llm_costs.count_documents(
            {"ts": {"$gte": datetime.fromtimestamp(cutoff_24h, tz=timezone.utc)}}
        )
    except Exception:
        last24h["llm_costs"] = -1
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "last_24h": last24h,
        "errors": errors,
    }
