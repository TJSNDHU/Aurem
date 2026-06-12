"""
Conviction Router — admin visibility for Adaptive ORA (P1 Shadow Mode).

Endpoints:
  GET  /api/conviction/top             — top hot leads by score
  GET  /api/conviction/lead/{lead_id}  — full history for one lead
  POST /api/conviction/signal          — manual signal injection (admin / webhooks)
  POST /api/conviction/backfill        — seed scores on existing leads (one-shot)
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Request

from services.adaptive_ora import (
    record_signal,
    top_leads,
    backfill_missing_scores,
    get_mode,
    set_mode,
    MODE_SHADOW,
    MODE_AUTOMATION,
    SIGNAL_WEIGHTS,
    BUCKETS,
)

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conviction", tags=["conviction"])

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    if _db is None:
        raise HTTPException(500, "DB not initialized")
    return _db


def _require_admin(request: Request):
    """Reuse same bearer-JWT check as the rest of the admin surface.
    Accepts both token schemas:
      • platform_auth_router: {role: 'admin'|'super_admin', email, ...}
      • aurem_routes:         {is_admin: true, is_super_admin?: true, user_id, email, ...}
    """
    from jose import jwt, JWTError
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    token = auth.replace("Bearer ", "", 1)
    secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(401, "Invalid token")
    role = (payload.get("role") or "").lower()
    is_admin = bool(payload.get("is_admin") or payload.get("is_super_admin"))
    if role not in ("admin", "super_admin") and not is_admin:
        raise HTTPException(403, "Admin role required")
    return payload


@router.get("/top")
async def get_top_leads(request: Request, limit: int = 20):
    _require_admin(request)
    db = _get_db()
    leads = await top_leads(db, limit=limit)
    mode = await get_mode(db)
    return {
        "count": len(leads),
        "leads": leads,
        "buckets": [
            {"floor": floor, "name": name, "next_agent": agent}
            for floor, name, agent, _ in BUCKETS
        ],
        "mode": mode,
        "note": (
            "AUTOMATION MODE — hot leads auto-handed to Closer, cold leads auto-halted."
            if mode == MODE_AUTOMATION
            else "SHADOW MODE — scores computed but no agents auto-fire."
        ),
    }


@router.get("/config")
async def get_config(request: Request):
    """Return current Adaptive ORA mode + counts by bucket."""
    _require_admin(request)
    db = _get_db()
    mode = await get_mode(db)
    bucket_counts = {}
    try:
        pipeline = [
            {"$match": {"conviction_bucket": {"$exists": True},
                        "business_id": FOUNDER_BIN}},
            {"$group": {"_id": "$conviction_bucket", "count": {"$sum": 1}}},
        ]
        async for doc in db.campaign_leads.aggregate(pipeline):
            bucket_counts[doc["_id"]] = doc["count"]
    except Exception:
        pass
    cfg = await db.adaptive_ora_config.find_one({"_id": "singleton"}, {"_id": 0})
    return {
        "mode": mode,
        "modes_available": [MODE_SHADOW, MODE_AUTOMATION],
        "bucket_counts": bucket_counts,
        "updated_at": (cfg or {}).get("updated_at"),
        "updated_by": (cfg or {}).get("updated_by"),
    }


@router.get("/activity")
async def get_automation_activity(request: Request, limit: int = 30, hours: int = 72):
    """Return recent automation side-effects: closer hand-offs + auto-halts.
    Used by the Campaign Dashboard monitoring drawer so the admin can watch
    Adaptive ORA's decisions in real time.
    """
    from datetime import datetime, timezone, timedelta
    _require_admin(request)
    db = _get_db()

    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    # Build a unified activity list from both event types
    events = []

    # Closer hand-offs
    async for lead in db.campaign_leads.find(
        {"handed_to_closer_at": {"$gte": since}, "business_id": FOUNDER_BIN},
        {"_id": 0, "lead_id": 1, "business_name": 1, "handed_to_closer_at": 1,
         "handed_to_closer_reason": 1, "conviction_score": 1, "conviction_bucket": 1, "stage": 1},
    ).sort("handed_to_closer_at", -1).limit(limit):
        events.append({
            "type": "closer_handoff",
            "lead_id": lead.get("lead_id"),
            "business_name": lead.get("business_name"),
            "timestamp": lead.get("handed_to_closer_at"),
            "reason": lead.get("handed_to_closer_reason"),
            "score": lead.get("conviction_score"),
            "bucket": lead.get("conviction_bucket"),
            "stage": lead.get("stage"),
        })

    # Auto-halts
    async for lead in db.campaign_leads.find(
        {"halted_at": {"$gte": since}, "business_id": FOUNDER_BIN},
        {"_id": 0, "lead_id": 1, "business_name": 1, "halted_at": 1,
         "halted_reason": 1, "conviction_score": 1, "conviction_bucket": 1, "stage": 1},
    ).sort("halted_at", -1).limit(limit):
        events.append({
            "type": "halted",
            "lead_id": lead.get("lead_id"),
            "business_name": lead.get("business_name"),
            "timestamp": lead.get("halted_at"),
            "reason": lead.get("halted_reason"),
            "score": lead.get("conviction_score"),
            "bucket": lead.get("conviction_bucket"),
            "stage": lead.get("stage"),
        })

    # Sort merged by timestamp desc, trim to limit
    events.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
    events = events[:limit]

    # 24h totals for the summary pills
    since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    handoffs_24h = await db.campaign_leads.count_documents(
        {"handed_to_closer_at": {"$gte": since_24h}, "business_id": FOUNDER_BIN})
    halts_24h = await db.campaign_leads.count_documents(
        {"halted_at": {"$gte": since_24h}, "business_id": FOUNDER_BIN})

    mode = await get_mode(db)

    return {
        "mode": mode,
        "window_hours": hours,
        "summary": {
            "handoffs_24h": handoffs_24h,
            "halts_24h": halts_24h,
            "total_events": len(events),
        },
        "events": events,
    }


@router.post("/config")
async def update_config(request: Request):
    """Admin toggle between shadow and automation modes.
    Body: {"mode": "shadow" | "automation"}"""
    payload = _require_admin(request)
    body = await request.json()
    mode = ((body or {}).get("mode") or "").strip().lower()
    if mode not in (MODE_SHADOW, MODE_AUTOMATION):
        raise HTTPException(400, f"mode must be one of: {MODE_SHADOW}, {MODE_AUTOMATION}")
    db = _get_db()
    actor = payload.get("email") or payload.get("sub") or "admin"
    saved = await set_mode(db, mode, actor=actor)
    return {"ok": True, "mode": saved, "actor": actor}


@router.get("/lead/{lead_id}")
async def get_lead_conviction(lead_id: str, request: Request):
    _require_admin(request)
    db = _get_db()
    lead = await db.campaign_leads.find_one(
        {"lead_id": lead_id, "business_id": FOUNDER_BIN},
        {"_id": 0, "lead_id": 1, "business_name": 1, "conviction_score": 1,
         "conviction_bucket": 1, "conviction_history": 1, "next_agent": 1,
         "next_run_at": 1, "last_signal": 1, "last_signal_at": 1},
    )
    if not lead:
        raise HTTPException(404, f"Lead not found: {lead_id}")
    # Ensure history is ordered newest-first for UI
    hist = lead.get("conviction_history") or []
    lead["conviction_history"] = list(reversed(hist))
    return lead


@router.post("/signal")
async def inject_signal(request: Request):
    """
    Manually record a signal. Primary use: webhook landing pad + manual admin ops.
    Body: {"lead_id": "...", "signal": "site_visit", "meta": {...}}
    """
    _require_admin(request)
    body = await request.json()
    lead_id = (body or {}).get("lead_id")
    signal = (body or {}).get("signal")
    meta = (body or {}).get("meta")
    if not lead_id or not signal:
        raise HTTPException(400, "lead_id and signal required")
    if signal not in SIGNAL_WEIGHTS:
        raise HTTPException(
            400,
            f"Unknown signal '{signal}'. Known: {list(SIGNAL_WEIGHTS.keys())}",
        )
    db = _get_db()
    result = await record_signal(db, lead_id, signal, meta)
    if not result:
        raise HTTPException(404, f"Lead not found or update failed: {lead_id}")
    return result


@router.post("/backfill")
async def backfill(request: Request):
    _require_admin(request)
    db = _get_db()
    updated = await backfill_missing_scores(db)
    return {"ok": True, "seeded": updated}


@router.get("/catalog")
async def get_catalog(request: Request):
    """Return available signal names + weights + bucket thresholds for UI."""
    _require_admin(request)
    return {
        "signals": SIGNAL_WEIGHTS,
        "buckets": [
            {"floor": floor, "name": name, "next_agent": agent}
            for floor, name, agent, _ in BUCKETS
        ],
    }
