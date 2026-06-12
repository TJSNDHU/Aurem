"""
routers/system_health_full_router.py — composite admin dashboard
data source. Iter 325f Phase 6.

Single GET /api/admin/system-health-full call that returns:

  - qa_bot.last_pulse
  - error_ledger.recent (10)
  - incident_bus.open + last 5
  - shannon.score + severity_counts
  - autonomous_repair.pending + last 5
  - anomaly_detector.active
  - campaign.zero_sent_streak + eligible_leads
  - react_doctor.last_score
  - ora_cto.proposals_pending

Replaces 9 parallel admin dashboard fetches with 1. Admin JWT required.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, Header, HTTPException

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["System Health"])

_db = None


def set_db(database):
    global _db
    _db = database


def _require_admin(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing_bearer")
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(500, "jwt_not_configured")
    try:
        claims = jwt.decode(authorization.split(" ", 1)[1].strip(),
                             secret, algorithms=["HS256"])
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, f"invalid_token: {e}")
    if not (claims.get("is_admin") or claims.get("is_super_admin") or
            claims.get("role") in ("admin", "super_admin")):
        raise HTTPException(403, "admin_only")
    return claims


# ─── Section fetchers ────────────────────────────────────────────────
# Each fetcher is wrapped so an individual failure does NOT collapse
# the whole composite — degraded data is better than no data.
async def _safe(coro):
    try:
        return await coro
    except Exception as e:
        return {"error": str(e)[:160]}


async def _qa_bot(db) -> Dict[str, Any]:
    last = await db.qa_bot_runs.find_one({}, {"_id": 0}, sort=[("ts", -1)])
    return {"last_pulse": last}


async def _error_ledger(db) -> Dict[str, Any]:
    recent: List[Dict[str, Any]] = []
    async for row in db.error_ledger.find(
            {}, {"_id": 0}).sort("last_seen", -1).limit(10):
        recent.append(row)
    open_n = await db.error_ledger.count_documents({"status": "open"})
    return {"open": open_n, "recent": recent}


async def _incident_bus(db) -> Dict[str, Any]:
    open_n = await db.incident_ledger.count_documents(
        {"status": {"$in": ["open", "triaged", "fixing"]}}
    )
    recent: List[Dict[str, Any]] = []
    async for row in db.incident_ledger.find(
            {}, {"_id": 0}).sort("created_at", -1).limit(5):
        recent.append(row)
    return {"open": open_n, "recent": recent}


async def _shannon(db) -> Dict[str, Any]:
    latest = await db.shannon_reports.find_one({}, {"_id": 0},
                                                sort=[("created_at", -1)])
    if not latest:
        return {"score": None, "severity_counts": {}}
    return {
        "score": latest.get("security_score"),
        "severity_counts": latest.get("severity_counts", {}),
        "total": latest.get("total_vulnerabilities"),
        "target": latest.get("target"),
        "ts": latest.get("created_at"),
    }


async def _approvals(db) -> Dict[str, Any]:
    pending = await db.pending_approvals.count_documents(
        {"status": "pending_approval", "business_id": FOUNDER_BIN}
    )
    recent: List[Dict[str, Any]] = []
    async for row in db.pending_approvals.find(
            {"status": "pending_approval", "business_id": FOUNDER_BIN},
            {"_id": 0}
    ).sort("created_at", -1).limit(5):
        recent.append(row)
    return {"pending": pending, "recent": recent}


async def _anomaly(db) -> Dict[str, Any]:
    try:
        cutoff = datetime.now(timezone.utc).timestamp() - 3600
        active = await db.sentinel_alerts.count_documents(
            {"created_at": {"$gte": cutoff}}
        )
    except Exception:
        active = 0
    return {"active": active}


async def _campaign(db) -> Dict[str, Any]:
    state = await db.campaign_watchdog_state.find_one(
        {}, {"_id": 0}, sort=[("ts", -1)]
    )
    eligible = await db.campaign_leads.count_documents(
        {"status": {"$in": ["queued", "ready"]}, "business_id": FOUNDER_BIN}
    )
    return {
        "zero_sent_streak": (state or {}).get("zero_streak", 0),
        "last_sent": (state or {}).get("last_sent_at"),
        "eligible_leads": eligible,
    }


async def _react_doctor(db) -> Dict[str, Any]:
    latest = await db.react_doctor_runs.find_one({}, {"_id": 0},
                                                  sort=[("ts", -1)])
    return {"last_score": (latest or {}).get("score"),
            "ts": (latest or {}).get("ts")}


async def _ora_cto(db) -> Dict[str, Any]:
    pending = await db.ora_cto_proposals.count_documents(
        {"status": {"$in": ["awaiting_founder", "pending_apply"]},
         "business_id": FOUNDER_BIN}
    )
    return {"proposals_pending": pending}


# ─── Endpoint ────────────────────────────────────────────────────────
@router.get("/system-health-full")
async def system_health_full(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Single-call composite of every monitoring source. Admin JWT only."""
    _require_admin(authorization)
    if _db is None:
        raise HTTPException(503, "db_unavailable")

    (qa, err, inc, sh, ap, an, cmp_, rd, ct) = await asyncio.gather(
        _safe(_qa_bot(_db)),
        _safe(_error_ledger(_db)),
        _safe(_incident_bus(_db)),
        _safe(_shannon(_db)),
        _safe(_approvals(_db)),
        _safe(_anomaly(_db)),
        _safe(_campaign(_db)),
        _safe(_react_doctor(_db)),
        _safe(_ora_cto(_db)),
    )
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        "qa_bot": qa,
        "error_ledger": err,
        "incident_bus": inc,
        "shannon": sh,
        "autonomous_repair": ap,
        "anomaly_detector": an,
        "campaign": cmp_,
        "react_doctor": rd,
        "ora_cto": ct,
    }
