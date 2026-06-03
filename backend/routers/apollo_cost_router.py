"""
Apollo cost dashboard — admin endpoint.

Surfaces Apollo API spend from the `apollo_call_log` Mongo collection
written by services.proximity_blast on every successful call.

Endpoints:
    GET /api/admin/apollo-cost/summary       last 30 days
    GET /api/admin/apollo-cost/forecast      30-day projection
"""

import logging
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/api/admin/apollo-cost", tags=["apollo-cost"])
logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET")
COST_PER_CALL_USD = 0.03


_db = None


def set_db(database):
    global _db
    _db = database


async def _require_admin(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing_bearer_token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if (payload.get("is_admin") or payload.get("is_super_admin") or
                payload.get("role") in ("admin", "super_admin", "founder")):
            return payload.get("email") or payload.get("sub") or "admin"
    except Exception:
        pass
    raise HTTPException(403, "admin_required")


@router.get("/summary")
async def summary(authorization: str = Header(None)):
    """Last 30 days of Apollo spend, broken down by day."""
    await _require_admin(authorization)
    if _db is None:
        raise HTTPException(503, "Database unavailable")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)) \
        .strftime("%Y-%m-%d")

    # Aggregate by day
    pipeline = [
        {"$match": {"day": {"$gte": cutoff}}},
        {"$group": {
            "_id":   "$day",
            "calls": {"$sum": 1},
            "usd":   {"$sum": "$estimated_usd"},
        }},
        {"$sort": {"_id": 1}},
    ]
    daily: list[dict] = []
    async for row in _db.apollo_call_log.aggregate(pipeline):
        daily.append({
            "day":   row["_id"],
            "calls": row["calls"],
            "usd":   round(float(row.get("usd", 0)), 2),
        })

    total_calls = sum(d["calls"] for d in daily)
    total_usd = round(sum(d["usd"] for d in daily), 2)
    return {
        "ok":          True,
        "period_days": 30,
        "total_calls": total_calls,
        "total_usd":   total_usd,
        "per_call_usd": COST_PER_CALL_USD,
        "daily":       daily,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/forecast")
async def forecast(authorization: str = Header(None)):
    """Project monthly spend from the trailing-7-day average."""
    await _require_admin(authorization)
    if _db is None:
        raise HTTPException(503, "Database unavailable")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)) \
        .strftime("%Y-%m-%d")
    pipeline = [
        {"$match": {"day": {"$gte": cutoff}}},
        {"$group": {"_id": None,
                      "calls": {"$sum": 1},
                      "usd":   {"$sum": "$estimated_usd"}}},
    ]
    calls_7d = 0
    usd_7d = 0.0
    async for row in _db.apollo_call_log.aggregate(pipeline):
        calls_7d = int(row.get("calls", 0))
        usd_7d = float(row.get("usd", 0))
    avg_per_day = usd_7d / 7
    return {
        "ok":                 True,
        "trailing_7d_calls":  calls_7d,
        "trailing_7d_usd":    round(usd_7d, 2),
        "avg_daily_usd":      round(avg_per_day, 2),
        "projected_30d_usd":  round(avg_per_day * 30, 2),
        "per_call_usd":       COST_PER_CALL_USD,
        "rate_limit_per_hour": 100,
    }
