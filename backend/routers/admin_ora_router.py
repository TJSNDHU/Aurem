"""
admin_ora_router.py — Admin ORA Q&A across the BIN learning pool.
═══════════════════════════════════════════════════════════════════════════
Admin ORA learns from anonymized telemetry (db.admin_ora_brain) collected by
the service_gate decorator on EVERY paid action across EVERY BIN. Founders
can ask questions and get aggregated insights without seeing per-BIN PII.

  GET  /api/admin/ora/summary            → service usage rollups across all BINs
  POST /api/admin/ora/ask {question}     → Claude-backed Q&A grounded on the
                                           anonymized telemetry pool

Data scope:
  • db.admin_ora_brain rows have bin_hash (irreversible), service, plan, ts
  • NO emails, NO BIN strings, NO user identifiers leave the aggregation
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from middleware.bin_context import get_bin_ctx

logger = logging.getLogger(__name__)
router = APIRouter()
_db = None


def set_db(db):
    global _db
    _db = db


def _ensure_admin(request: Request):
    ctx = get_bin_ctx(request, required=True)
    if not ctx.is_admin:
        raise HTTPException(403, "admin only")
    return ctx


@router.get("/api/admin/ora/summary")
async def admin_ora_summary(request: Request, hours: int = 168):
    """Aggregate service usage across all BINs over a time window. Default
    168h (7 days). Hash-anonymized — never reveals a specific BIN."""
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    pipeline = [
        {"$match": {"ts": {"$gte": cutoff}, "type": "service_usage"}},
        {"$group": {
            "_id": {"service": "$service", "plan": "$plan"},
            "events": {"$sum": 1},
            "unique_bins": {"$addToSet": "$bin_hash"},
        }},
        {"$project": {
            "_id": 0,
            "service": "$_id.service",
            "plan": "$_id.plan",
            "events": 1,
            "unique_bins": {"$size": "$unique_bins"},
        }},
        {"$sort": {"events": -1}},
    ]
    rows: List[Dict[str, Any]] = []
    async for r in _db.admin_ora_brain.aggregate(pipeline):
        rows.append(r)
    total_events = sum(r["events"] for r in rows)
    total_bins = await _db.admin_ora_brain.distinct("bin_hash", {"ts": {"$gte": cutoff}})
    return {
        "ok": True,
        "window_hours": hours,
        "total_events": total_events,
        "active_unique_bins": len(total_bins),
        "by_service_plan": rows,
    }


class AskReq(BaseModel):
    question: str


@router.post("/api/admin/ora/ask")
async def admin_ora_ask(body: AskReq, request: Request):
    """Claude-backed Q&A grounded on the admin telemetry pool. Useful for:
       • "Which services hit quota most?"
       • "What's our trial-to-paid conversion across plans?"
       • "Which features are under-used and may need a UX nudge?"
    """
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    q = (body.question or "").strip()
    if not q:
        raise HTTPException(400, "question required")

    # Build a small grounding snapshot
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    by_service: Dict[str, int] = {}
    by_plan: Dict[str, int] = {}
    async for r in _db.admin_ora_brain.aggregate([
        {"$match": {"ts": {"$gte": cutoff}, "type": "service_usage"}},
        {"$group": {"_id": {"s": "$service", "p": "$plan"}, "n": {"$sum": 1}}},
    ]):
        s = r["_id"].get("s") or "unknown"
        p = r["_id"].get("p") or "unknown"
        by_service[s] = by_service.get(s, 0) + r["n"]
        by_plan[p] = by_plan.get(p, 0) + r["n"]

    # Total tenants snapshot
    tenants = await _db.platform_users.count_documents({})
    paying = await _db.platform_users.count_documents({"plan": {"$in": ["starter", "growth", "pro", "enterprise"]}})

    # Trial conversion (anonymous count of trial vs converted)
    trialing = await _db.aurem_billing.count_documents({"status": "trialing"})
    expired = await _db.aurem_billing.count_documents({"status": "trial_expired"})
    converted = await _db.aurem_billing.count_documents({"plan": {"$in": ["starter", "growth", "pro", "enterprise"]}})

    grounding = {
        "window_days": 30,
        "service_usage_counts": dict(sorted(by_service.items(), key=lambda x: -x[1])[:25]),
        "plan_usage_counts": by_plan,
        "tenant_totals": {"total": tenants, "paying": paying},
        "trial_funnel": {"trialing": trialing, "expired": expired, "converted": converted},
    }

    # Claude diagnose using shared service
    try:
        from services.sentinel_ai_diagnose import diagnose_error
        # Reuse the LLM helper with a tailored grounding doc
        import json as _json
        synthetic = {
            "type": "admin_ora_question",
            "classification": "admin_query",
            "message": f"Founder question: {q}\n\nAggregated grounding (30d):\n{_json.dumps(grounding, indent=2)}",
            "status_code": 0,
            "url": "/api/admin/ora/ask",
            "method": "POST",
            "stack": "",
            "page_url": "",
            "hostname": "aurem-admin-ora",
        }
        parsed = await diagnose_error(synthetic)
        # Persist the Q&A so it becomes part of the brain
        await _db.admin_ora_qa.insert_one({
            "ts": datetime.now(timezone.utc).isoformat(),
            "question": q,
            "answer": parsed,
            "grounding_snapshot": grounding,
        })
        return {"ok": True, "answer": parsed, "grounding": grounding}
    except Exception as e:
        logger.exception(f"[admin_ora_ask] LLM failed: {e}")
        raise HTTPException(500, f"admin ORA failed: {e}")


@router.get("/api/admin/ora/recent")
async def admin_ora_recent(request: Request, limit: int = 25):
    """Recent admin ORA Q&A history."""
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    rows: List[Dict[str, Any]] = []
    async for d in _db.admin_ora_qa.find({}, {"_id": 0}).sort("ts", -1).limit(limit):
        rows.append(d)
    return {"ok": True, "count": len(rows), "history": rows}
