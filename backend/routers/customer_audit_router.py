"""
Customer Site Audit Router — $49/mo upsell endpoints.

All endpoints require a customer JWT (Bearer token). Customer can:
  - POST /api/customer/audit/run    — fire a fresh audit for their site
  - GET  /api/customer/audit/latest — get the most-recent completed audit
  - GET  /api/customer/audit/history?limit=10
  - GET  /api/customer/audit/{audit_id}

Auto-trigger on signup is handled separately by `services.customer_audit_service`
via `asyncio.create_task(run_audit(...))` called from the signup flow.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from services.customer_audit_service import (
    run_audit, get_latest_audit, list_audits, ensure_indexes,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/customer/audit", tags=["customer-audit"])

_db = None
_jwt_secret: str = ""
_jwt_algo: str = "HS256"


def set_db(database):
    global _db
    _db = database
    if database is not None:
        asyncio.create_task(ensure_indexes(database))


def set_jwt(secret: str, algo: str = "HS256"):
    global _jwt_secret, _jwt_algo
    _jwt_secret = secret
    _jwt_algo = algo


# ─── Auth ─────────────────────────────────────────────────────────────
async def _current_customer(authorization: Optional[str] = Header(None)) -> dict:
    if _db is None:
        raise HTTPException(503, "DB not initialised")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, _jwt_secret, algorithms=[_jwt_algo])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(401, f"Invalid token: {str(e)[:120]}")
    cid = (
        payload.get("sub")
        or payload.get("email")
        or payload.get("customer_id")
        or payload.get("user_id")
    )
    if not cid:
        raise HTTPException(401, "Token has no subject")
    return {"customer_id": cid, "bin": payload.get("bin"), "claims": payload}


# ─── Models ───────────────────────────────────────────────────────────
class RunAuditRequest(BaseModel):
    url: HttpUrl
    strategy: str = Field("mobile", pattern="^(mobile|desktop)$")


# ─── Routes ───────────────────────────────────────────────────────────
@router.post("/run")
async def run(req: RunAuditRequest, user: dict = Depends(_current_customer)):
    """Trigger a fresh audit. Runs synchronously up to PageSpeed timeout (~60s)."""
    a = await run_audit(
        str(req.url), customer_id=user["customer_id"],
        bin=user.get("bin"), strategy=req.strategy, db=_db,
    )
    return a.model_dump()


@router.get("/latest")
async def latest(user: dict = Depends(_current_customer)):
    doc = await get_latest_audit(_db, user["customer_id"])
    return doc or {"audit": None, "message": "No audit yet — run /api/customer/audit/run"}


@router.get("/history")
async def history(limit: int = 20, user: dict = Depends(_current_customer)):
    if limit < 1 or limit > 100:
        limit = 20
    return {"items": await list_audits(_db, user["customer_id"], limit=limit)}


# ─── Admin live dashboard (iter 322ed) ────────────────────────────────
# IMPORTANT — declared BEFORE `/{audit_id}` so FastAPI doesn't match
# "admin" as a customer audit_id and 404. Order matters in FastAPI.
_ADMIN_LIVE_LIMIT = 10


async def _require_admin_claims(authorization: Optional[str]) -> dict:
    """Reject if the JWT subject isn't an admin in db.users."""
    if _db is None:
        raise HTTPException(503, "DB not initialised")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    try:
        payload = jwt.decode(authorization.split(" ", 1)[1].strip(),
                              _jwt_secret, algorithms=[_jwt_algo])
    except Exception:
        raise HTTPException(401, "Invalid token")
    email = (payload.get("email") or payload.get("sub") or "").lower()
    if not email:
        raise HTTPException(403, "no email on token")
    user = await _db.users.find_one({"email": email},
        {"_id": 0, "is_admin": 1, "is_super_admin": 1, "role": 1})
    if not user or not (user.get("is_admin") or user.get("is_super_admin")
                          or user.get("role") in ("admin", "super_admin")):
        raise HTTPException(403, "Admin access required")
    return {"email": email}


@router.get("/admin/live")
async def admin_live(authorization: Optional[str] = Header(None)):
    """Live aggregate metrics across all customer audits — for admin widget.
    Aggregates audit + intelligence so the operator can see in real time:
      • how many audits ran today
      • total $/mo waste detected across the customer base
      • most-common issues (surfaces patterns to fix in the product itself)
      • intelligence coverage (which BINs have pixel firing, etc.)
    """
    await _require_admin_claims(authorization)
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    today_iso = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    week_ago_iso = (now - timedelta(days=7)).isoformat()

    total = await _db.customer_audits.count_documents({})
    today = await _db.customer_audits.count_documents({"started_at": {"$gte": today_iso}})
    week = await _db.customer_audits.count_documents({"started_at": {"$gte": week_ago_iso}})
    failed_today = await _db.customer_audits.count_documents(
        {"started_at": {"$gte": today_iso}, "status": "failed"})

    pipe_waste = [
        {"$match": {"started_at": {"$gte": week_ago_iso}, "status": "completed"}},
        {"$group": {"_id": None,
                     "total_waste": {"$sum": "$ads.estimated_monthly_waste_usd"},
                     "avg_perf":     {"$avg": "$scores.performance"},
                     "avg_seo":      {"$avg": "$scores.seo"}}},
    ]
    waste_agg = await _db.customer_audits.aggregate(pipe_waste).to_list(1)
    waste_doc = (waste_agg[0] if waste_agg else {}) or {}

    pipe_issues = [
        {"$match": {"started_at": {"$gte": week_ago_iso}, "status": "completed"}},
        {"$unwind": "$top_issues"},
        {"$group": {"_id": "$top_issues", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": _ADMIN_LIVE_LIMIT},
    ]
    top_issues = await _db.customer_audits.aggregate(pipe_issues).to_list(_ADMIN_LIVE_LIMIT)

    bins_with_pixel = await _db.pixel_events.distinct("bin_id")
    bins_with_intel = await _db.bin_intelligence.distinct("bin_id")
    merged_profiles = await _db.bin_unified_profiles.estimated_document_count()
    raw_signals = await _db.bin_intelligence.estimated_document_count()

    latest_cur = _db.customer_audits.find(
        {}, {"_id": 0, "id": 1, "customer_id": 1, "url": 1, "status": 1,
              "started_at": 1, "scores.performance": 1, "scores.seo": 1,
              "ads.estimated_monthly_waste_usd": 1,
              "intelligence.pixel_visitors_today": 1,
              "intelligence.pixel_matched_contacts": 1,
              "intelligence.available": 1},
    ).sort("started_at", -1).limit(_ADMIN_LIVE_LIMIT)
    latest = await latest_cur.to_list(_ADMIN_LIVE_LIMIT)

    return {
        "ok": True,
        "generated_at": now.isoformat(),
        "counts": {
            "total": total, "today": today, "week": week,
            "failed_today": failed_today,
        },
        "rollup_7d": {
            "total_waste_usd": int(waste_doc.get("total_waste") or 0),
            "avg_performance": round(float(waste_doc.get("avg_perf") or 0), 1),
            "avg_seo":         round(float(waste_doc.get("avg_seo") or 0), 1),
        },
        "top_issues": [{"issue": x["_id"], "count": x["count"]} for x in top_issues],
        "intelligence": {
            "bins_with_pixel":   len(bins_with_pixel),
            "bins_with_signals": len(bins_with_intel),
            "merged_profiles":   merged_profiles,
            "raw_signals":       raw_signals,
        },
        "latest_audits": latest,
    }


@router.get("/{audit_id}")
async def get_one(audit_id: str, user: dict = Depends(_current_customer)):
    doc = await _db.customer_audits.find_one(
        {"id": audit_id, "customer_id": user["customer_id"]}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(404, "Audit not found")
    return doc


# ─── Public health (so Pillars Map can grid-check us) ────────────────
@router.get("/_/health", include_in_schema=False)
async def health():
    has_key = bool((
        os.environ.get("GOOGLE_PSI_API_KEY")
        or os.environ.get("GOOGLE_PAGESPEED_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or ""
    ).strip())
    return {
        "ok": True,
        "service": "customer-audit",
        "psi_key_configured": has_key,
    }
