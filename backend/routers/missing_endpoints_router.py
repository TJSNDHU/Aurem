"""
Missing Endpoints Router — closes the 6 real wiring gaps found in the
backlog deep-dive (see backlog_fix_report.md).

Place at: backend/routers/missing_endpoints_router.py
Register in registry.py Section 5:
    from routers.missing_endpoints_router import router as missing_endpoints_router, set_db as _me_set_db
    _me_set_db(db); app.include_router(missing_endpoints_router)

Zero-mocks policy: every handler reads/writes the real collections already
used elsewhere in the codebase (sentinel_runs, sentinel_heartbeats,
repair_suggestions, autonomous_repair_events, tenant_settings) or delegates
to an existing service (evolver_client.get_status). If a dependency is
missing the handler raises 503 with the exact missing piece — never fake
numbers.

Auth follows the house pattern (JWT HS256 via config.JWT_SECRET):
  - admin endpoints  → role/admin claims (same check as wiring_audit_router)
  - customer endpoints → bin_id / business_id claim from the customer token
    (aurem_customer_token). ⚠ Confirm claim names against bin_auth issuance;
    adjust _customer_bin() if your customer JWT uses a different key.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import JWT_SECRET

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Wiring Gap Fixes (D-83)"])

_db = None


def set_db(db) -> None:
    global _db
    _db = db


# ── auth helpers (house pattern) ────────────────────────────────────────────

def _decode(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    try:
        return jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


def _require_admin(request: Request) -> Dict[str, Any]:
    p = _decode(request)
    if p.get("role") not in ("admin", "super_admin") and not p.get("is_admin") and not p.get("is_super_admin"):
        raise HTTPException(403, "Admin only")
    return p


def _customer_bin(request: Request) -> str:
    p = _decode(request)
    # Match v2_customer_actions_router derivation EXACTLY so scan-schedule /
    # site reads hit the same tenant_settings doc: business_id → bin → email-prefix.
    bin_id = p.get("business_id") or p.get("bin") or p.get("bin_id")
    if not bin_id:
        email = p.get("email") or ""
        if "@" in email:
            bin_id = email.split("@")[0]
    if not bin_id:
        raise HTTPException(403, "Customer token required")
    return str(bin_id)


def _need_db():
    if _db is None:
        raise HTTPException(503, "DB not initialised (set_db not called)")


# ════════════════════════════════════════════════════════════════════════════
# 1) GET /api/admin/evolver/status
#    Caller: AdminEvolver.jsx, AdminControlCenter.jsx (routed /admin/evolver)
#    Source: services/evolver_client.get_status(db) — already implemented.
# ════════════════════════════════════════════════════════════════════════════
@router.get("/api/admin/evolver/status")
async def evolver_status(request: Request):
    _require_admin(request)
    _need_db()
    try:
        from services.evolver_client import get_status
    except ImportError as e:
        raise HTTPException(503, f"evolver_client unavailable: {e}")
    return await get_status(_db)


# ════════════════════════════════════════════════════════════════════════════
# 2) GET /api/admin/system-pulse-live
#    Caller: lib/sentinel.js → SystemPulseLive page (routed)
#    Source: real sentinel collections (no synthetic numbers).
# ════════════════════════════════════════════════════════════════════════════
@router.get("/api/admin/system-pulse-live")
async def system_pulse_live(request: Request):
    _require_admin(request)
    _need_db()
    now = datetime.now(timezone.utc)

    heartbeat = await _db.sentinel_heartbeats.find_one(
        {}, {"_id": 0}, sort=[("ts", -1)]
    )
    runs = [r async for r in _db.sentinel_runs.find(
        {}, {"_id": 0}, sort=[("started_at", -1)], limit=10
    )]
    recent_repairs = [r async for r in _db.autonomous_repair_events.find(
        {}, {"_id": 0}, sort=[("ts", -1)], limit=10
    )]

    return {
        "generated_at": now.isoformat(),
        "heartbeat": heartbeat,            # None if sentinel never beat — honest
        "recent_runs": runs,
        "recent_repairs": recent_repairs,
        "counts": {
            "runs_total": await _db.sentinel_runs.count_documents({}),
            "repairs_total": await _db.autonomous_repair_events.count_documents({}),
            "open_suggestions": await _db.repair_suggestions.count_documents(
                {"status": {"$nin": ["applied", "dismissed", "fixed"]}}
            ),
        },
    }


# ════════════════════════════════════════════════════════════════════════════
# 3) GET + POST /api/customer/scan-schedule
#    Caller: LuxePages.jsx (live customer portal)
#    Source: tenant_settings.scan_schedule — the SAME field
#    v2_customer_actions_router already returns inside another payload.
# ════════════════════════════════════════════════════════════════════════════
_ALLOWED_SCHEDULES = ("daily", "weekly", "biweekly", "monthly", "off")


class ScanScheduleBody(BaseModel):
    schedule: str


@router.get("/api/customer/scan-schedule")
async def get_scan_schedule(request: Request):
    bin_id = _customer_bin(request)
    _need_db()
    doc = await _db.tenant_settings.find_one(
        {"bin_id": bin_id}, {"_id": 0, "scan_schedule": 1}
    ) or {}
    return {"bin_id": bin_id, "schedule": doc.get("scan_schedule") or "weekly"}


@router.post("/api/customer/scan-schedule")
async def set_scan_schedule(body: ScanScheduleBody, request: Request):
    bin_id = _customer_bin(request)
    _need_db()
    sched = body.schedule.strip().lower()
    if sched not in _ALLOWED_SCHEDULES:
        raise HTTPException(422, f"schedule must be one of {_ALLOWED_SCHEDULES}")
    await _db.tenant_settings.update_one(
        {"bin_id": bin_id},
        {"$set": {"scan_schedule": sched,
                  "scan_schedule_updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"ok": True, "bin_id": bin_id, "schedule": sched}


# ════════════════════════════════════════════════════════════════════════════
# 4) GET /api/sentinel/fixes-log     (customer-visible auto-fix history)
#    Caller: LuxePages.jsx / LuxeV2Pages.jsx (live)
#    Source: repair_suggestions (applied) + autonomous_repair_events,
#    scoped to the caller's bin where the documents carry one.
# ════════════════════════════════════════════════════════════════════════════
@router.get("/api/sentinel/fixes-log")
async def sentinel_fixes_log(request: Request, limit: int = 25):
    bin_id = _customer_bin(request)
    _need_db()
    limit = max(1, min(limit, 100))

    scope = {"$or": [{"bin_id": bin_id}, {"tenant_id": bin_id},
                     {"bin_id": {"$exists": False}, "tenant_id": {"$exists": False}}]}

    applied = [d async for d in _db.repair_suggestions.find(
        {**scope, "status": {"$in": ["applied", "fixed"]}},
        {"_id": 0}, sort=[("updated_at", -1)], limit=limit
    )]
    events = [d async for d in _db.autonomous_repair_events.find(
        scope, {"_id": 0}, sort=[("ts", -1)], limit=limit
    )]
    return {"bin_id": bin_id, "applied_suggestions": applied, "repair_events": events}


# ════════════════════════════════════════════════════════════════════════════
# 5) GET /api/sentinel/pulse-history
#    Caller: LuxePages.jsx / LuxeV2Pages.jsx (live)
#    Source: sentinel_runs — last 50 real runs.
# ════════════════════════════════════════════════════════════════════════════
@router.get("/api/sentinel/pulse-history")
async def sentinel_pulse_history(request: Request, limit: int = 50):
    _customer_bin(request)  # any authed customer may view platform pulse
    _need_db()
    limit = max(1, min(limit, 200))
    runs = [r async for r in _db.sentinel_runs.find(
        {}, {"_id": 0}, sort=[("started_at", -1)], limit=limit
    )]
    return {"runs": runs, "count": len(runs)}


# ════════════════════════════════════════════════════════════════════════════
# 6) GET /api/site-monitor/me/sites
#    Caller: LuxeV2Pages.jsx (live)
#    Source: tenant_settings.website_url — the tenant's real monitored site.
#    TODO(D-83b): when a multi-site `monitored_sites` collection ships,
#    extend this to list it; until then one real site, never fabricated.
# ════════════════════════════════════════════════════════════════════════════
@router.get("/api/site-monitor/me/sites")
async def my_monitored_sites(request: Request):
    bin_id = _customer_bin(request)
    _need_db()
    doc = await _db.tenant_settings.find_one(
        {"bin_id": bin_id}, {"_id": 0, "website_url": 1, "scan_schedule": 1}
    ) or {}
    sites = []
    if doc.get("website_url"):
        sites.append({
            "url": doc["website_url"],
            "schedule": doc.get("scan_schedule") or "weekly",
            "source": "tenant_settings",
        })
    return {"bin_id": bin_id, "sites": sites, "count": len(sites)}
