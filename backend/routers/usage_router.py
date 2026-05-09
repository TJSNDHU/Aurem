"""
usage_router.py — Per-BIN usage breakdown for the customer billing UI.
═══════════════════════════════════════════════════════════════════════════
  GET /api/billing/usage
       Returns per-service usage for the current billing period (this month).
       Used by /my/billing UI to render the per-service usage bars.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from aurem_config.plans import PLANS, SERVICE_TO_LIMIT_KEY
from middleware.bin_context import get_bin_ctx

logger = logging.getLogger(__name__)
router = APIRouter()
_db = None


def set_db(db):
    global _db
    _db = db


def _month_start_iso() -> str:
    return datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    ).isoformat()


@router.get("/api/billing/usage")
async def billing_usage(request: Request):
    ctx = get_bin_ctx(request, required=True)
    if _db is None:
        raise HTTPException(503, "db not ready")

    plan = PLANS.get(ctx.plan or "trial") or PLANS["trial"]
    limits = plan["limits"]

    pipeline = [
        {"$match": {"business_id": ctx.business_id, "ts": {"$gte": _month_start_iso()}}},
        {"$group": {"_id": "$service", "used": {"$sum": "$count"}}},
    ]
    used_by_service: Dict[str, int] = {}
    async for r in _db.service_usage_log.aggregate(pipeline):
        used_by_service[r["_id"]] = r["used"]

    bars = []
    for svc in sorted(set(list(used_by_service.keys()) + list(SERVICE_TO_LIMIT_KEY.keys()))):
        limit_key = SERVICE_TO_LIMIT_KEY.get(svc)
        cap = limits.get(limit_key, 0) if limit_key else 0
        used = used_by_service.get(svc, 0)
        if cap and cap < 1_000_000:
            pct = round(min(100, (used / cap) * 100)) if cap else 0
        else:
            pct = 0
        bars.append({
            "service": svc,
            "used": used,
            "limit": cap if cap < 1_000_000 else None,
            "limit_key": limit_key,
            "pct": pct,
        })

    return {
        "ok": True,
        "business_id": ctx.business_id,
        "plan": ctx.plan,
        "period_start": _month_start_iso(),
        "bars": bars,
    }
