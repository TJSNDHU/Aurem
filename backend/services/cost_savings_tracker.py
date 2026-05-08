"""
AUREM Cost Savings Tracker
============================

Logs every ORA query with model tier (free/paid) and estimated cost savings.
Provides aggregation endpoints for the Cost Savings Dashboard.

Estimated costs if paid models had been used:
  GPT-4o          = $0.005 per query
  Claude Haiku    = $0.003 per query
  Perplexity Sonar = $0.008 per query

Cost for free models: $0.000
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

_db = None

# Estimated cost per query if paid model had been used
PAID_COST_MAP = {
    "general": 0.005,    # GPT-4o equivalent
    "analysis": 0.003,   # Claude Haiku equivalent
    "search": 0.008,     # Perplexity Sonar equivalent
}


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        from server import db
        return db
    except Exception:
        return None


async def log_query_cost(
    model_used: str,
    query_type: str = "general",
    tenant_id: str = "system",
    response_time_ms: int = 0,
    success: bool = True,
):
    """Log a query for cost tracking. Call this after every ORA brain response."""
    db = _get_db()
    if db is None:
        return

    is_free = ":free" in model_used or model_used == "emergent_gpt4o"
    model_tier = "free" if is_free else "paid"
    estimated_saved = PAID_COST_MAP.get(query_type, 0.005) if is_free else 0.0

    doc = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_used": model_used,
        "model_tier": model_tier,
        "query_type": query_type,
        "estimated_cost_saved": estimated_saved,
        "tenant_id": tenant_id,
        "response_time_ms": response_time_ms,
        "success": success,
    }

    try:
        await db.cost_savings_log.insert_one(doc)
    except Exception as e:
        logger.warning(f"[CostTracker] Failed to log: {e}")


async def get_today_savings() -> dict:
    """Card 1: Today's savings."""
    db = _get_db()
    if db is None:
        return {"free_queries": 0, "paid_queries": 0, "estimated_saved": 0.0}

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        pipeline = [
            {"$match": {"timestamp": {"$gte": today_start.isoformat()}}},
            {"$group": {
                "_id": "$model_tier",
                "count": {"$sum": 1},
                "saved": {"$sum": "$estimated_cost_saved"},
            }},
        ]
        results = {}
        async for doc in db.cost_savings_log.aggregate(pipeline):
            results[doc["_id"]] = {"count": doc["count"], "saved": doc["saved"]}

        free = results.get("free", {"count": 0, "saved": 0.0})
        paid = results.get("paid", {"count": 0, "saved": 0.0})

        return {
            "free_queries": free["count"],
            "paid_queries": paid["count"],
            "total_queries": free["count"] + paid["count"],
            "estimated_saved": round(free["saved"], 4),
        }
    except Exception as e:
        logger.warning(f"[CostTracker] today error: {e}")
        return {"free_queries": 0, "paid_queries": 0, "estimated_saved": 0.0}


async def get_month_savings() -> dict:
    """Card 2: This month's savings."""
    db = _get_db()
    if db is None:
        return {"free_queries": 0, "paid_queries": 0, "free_pct": 0, "estimated_saved": 0.0}

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    try:
        pipeline = [
            {"$match": {"timestamp": {"$gte": month_start.isoformat()}}},
            {"$group": {
                "_id": "$model_tier",
                "count": {"$sum": 1},
                "saved": {"$sum": "$estimated_cost_saved"},
            }},
        ]
        results = {}
        async for doc in db.cost_savings_log.aggregate(pipeline):
            results[doc["_id"]] = {"count": doc["count"], "saved": doc["saved"]}

        free = results.get("free", {"count": 0, "saved": 0.0})
        paid = results.get("paid", {"count": 0, "saved": 0.0})
        total = free["count"] + paid["count"]
        free_pct = round((free["count"] / total * 100), 1) if total > 0 else 100.0

        return {
            "free_queries": free["count"],
            "paid_queries": paid["count"],
            "total_queries": total,
            "free_pct": free_pct,
            "paid_pct": round(100 - free_pct, 1),
            "estimated_saved": round(free["saved"], 4),
        }
    except Exception as e:
        logger.warning(f"[CostTracker] month error: {e}")
        return {"free_queries": 0, "paid_queries": 0, "free_pct": 0, "estimated_saved": 0.0}


async def get_alltime_savings() -> dict:
    """Card 3: All-time savings + model rankings."""
    db = _get_db()
    if db is None:
        return {"total_saved": 0.0, "total_queries": 0, "model_rankings": []}

    try:
        # Total savings
        pipeline = [
            {"$group": {
                "_id": "$model_tier",
                "count": {"$sum": 1},
                "saved": {"$sum": "$estimated_cost_saved"},
            }},
        ]
        results = {}
        async for doc in db.cost_savings_log.aggregate(pipeline):
            results[doc["_id"]] = {"count": doc["count"], "saved": doc["saved"]}

        free = results.get("free", {"count": 0, "saved": 0.0})
        paid = results.get("paid", {"count": 0, "saved": 0.0})

        # Model rankings
        model_pipeline = [
            {"$group": {
                "_id": "$model_used",
                "queries": {"$sum": 1},
                "successes": {"$sum": {"$cond": ["$success", 1, 0]}},
                "avg_response_ms": {"$avg": "$response_time_ms"},
                "total_saved": {"$sum": "$estimated_cost_saved"},
            }},
            {"$sort": {"queries": -1}},
            {"$limit": 10},
        ]
        rankings = []
        async for doc in db.cost_savings_log.aggregate(model_pipeline):
            total = doc["queries"]
            success_rate = round((doc["successes"] / total * 100), 1) if total > 0 else 0
            rankings.append({
                "model": doc["_id"],
                "queries": total,
                "success_rate": success_rate,
                "avg_response_ms": round(doc["avg_response_ms"] or 0),
                "total_saved": round(doc["total_saved"], 4),
            })

        return {
            "total_saved": round(free["saved"], 4),
            "total_queries": free["count"] + paid["count"],
            "free_queries": free["count"],
            "paid_queries": paid["count"],
            "model_rankings": rankings,
        }
    except Exception as e:
        logger.warning(f"[CostTracker] alltime error: {e}")
        return {"total_saved": 0.0, "total_queries": 0, "model_rankings": []}


async def get_daily_chart(days: int = 7) -> list:
    """7-day bar chart data: free vs paid queries per day."""
    db = _get_db()
    if db is None:
        return []

    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        pipeline = [
            {"$match": {"timestamp": {"$gte": start.isoformat()}}},
            {"$addFields": {
                "date": {"$substr": ["$timestamp", 0, 10]},
            }},
            {"$group": {
                "_id": {"date": "$date", "tier": "$model_tier"},
                "count": {"$sum": 1},
                "saved": {"$sum": "$estimated_cost_saved"},
            }},
            {"$sort": {"_id.date": 1}},
        ]

        daily = {}
        async for doc in db.cost_savings_log.aggregate(pipeline):
            date = doc["_id"]["date"]
            tier = doc["_id"]["tier"]
            if date not in daily:
                daily[date] = {"date": date, "free": 0, "paid": 0, "saved": 0.0}
            daily[date][tier] = doc["count"]
            if tier == "free":
                daily[date]["saved"] = round(doc["saved"], 4)

        # Fill missing days
        chart = []
        for i in range(days):
            d = (start + timedelta(days=i + 1)).strftime("%Y-%m-%d")
            if d in daily:
                chart.append(daily[d])
            else:
                chart.append({"date": d, "free": 0, "paid": 0, "saved": 0.0})

        return chart
    except Exception as e:
        logger.warning(f"[CostTracker] chart error: {e}")
        return []


async def check_paid_alert_threshold() -> Optional[str]:
    """Check if paid usage exceeds 10% today. Returns alert message or None."""
    today = await get_today_savings()
    total = today.get("total_queries", 0)
    paid = today.get("paid_queries", 0)

    if total < 5:
        return None

    paid_pct = (paid / total * 100) if total > 0 else 0
    if paid_pct > 10:
        return (
            f"AUREM Cost Alert: {paid_pct:.0f}% paid model usage today "
            f"({paid}/{total} queries). Free models may be rate-limited. Check Sentinel."
        )
    return None


async def get_morning_brief_savings() -> str:
    """Returns savings string for the morning brief."""
    today = await get_today_savings()
    month = await get_month_savings()

    return (
        f"Yesterday: {today['total_queries']} queries, "
        f"${today['estimated_saved']:.2f} saved vs paid models. "
        f"Month to date: ${month['estimated_saved']:.2f} total savings."
    )
