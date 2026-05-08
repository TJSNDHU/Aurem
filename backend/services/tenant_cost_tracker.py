"""
Per-Tenant Cost Breakdown — Track tokens, model usage, and savings per tenant.
Monthly cost report with free vs paid model breakdown.
"""

import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import os
        mongo_url = os.environ.get("MONGO_URL", "").strip().strip('"').strip("'")
        if not mongo_url:
            return None
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(mongo_url)
        _db = client[os.environ.get("DB_NAME", "aurem_db")]
        return _db
    except Exception:
        return None


# Cost per 1M tokens (approximate GPT-4o rates)
PAID_RATES = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-3.5-sonnet": {"input": 3.00, "output": 15.00},
    "default": {"input": 2.00, "output": 8.00},
}


async def record_usage(tenant_id: str, model: str, input_tokens: int,
                       output_tokens: int, is_free: bool = True):
    """Record token usage for a tenant."""
    db = _get_db()
    if db is None:
        return

    now = datetime.now(timezone.utc)
    month_key = now.strftime("%Y-%m")

    rates = PAID_RATES.get(model, PAID_RATES["default"])
    estimated_cost = (input_tokens / 1_000_000 * rates["input"]) + (output_tokens / 1_000_000 * rates["output"])

    await db.tenant_usage.update_one(
        {"tenant_id": tenant_id, "month": month_key},
        {
            "$inc": {
                "total_input_tokens": input_tokens,
                "total_output_tokens": output_tokens,
                "total_requests": 1,
                "free_requests": 1 if is_free else 0,
                "paid_requests": 0 if is_free else 1,
                "estimated_cost_usd": round(estimated_cost, 4),
                "actual_cost_usd": 0 if is_free else round(estimated_cost, 4),
            },
            "$set": {
                "tenant_id": tenant_id,
                "month": month_key,
                "last_updated": now.isoformat(),
            },
        },
        upsert=True,
    )


async def get_tenant_cost(tenant_id: str, month: str = None) -> dict:
    """Get cost breakdown for a tenant for a specific month."""
    db = _get_db()
    if db is None:
        return {}

    if not month:
        month = datetime.now(timezone.utc).strftime("%Y-%m")

    doc = await db.tenant_usage.find_one(
        {"tenant_id": tenant_id, "month": month}, {"_id": 0}
    )
    if not doc:
        return {
            "tenant_id": tenant_id, "month": month,
            "total_requests": 0, "total_input_tokens": 0, "total_output_tokens": 0,
            "estimated_cost_usd": 0, "actual_cost_usd": 0, "savings_usd": 0,
            "free_pct": 100, "paid_pct": 0,
        }

    total = doc.get("total_requests", 0) or 1
    free = doc.get("free_requests", 0)
    estimated = doc.get("estimated_cost_usd", 0)
    actual = doc.get("actual_cost_usd", 0)

    return {
        **doc,
        "free_pct": round(free / total * 100, 1) if total > 0 else 100,
        "paid_pct": round((total - free) / total * 100, 1) if total > 0 else 0,
        "savings_usd": round(estimated - actual, 2),
    }


async def get_all_costs(month: str = None) -> list:
    """Get cost breakdown for all tenants."""
    db = _get_db()
    if db is None:
        return []

    if not month:
        month = datetime.now(timezone.utc).strftime("%Y-%m")

    cursor = db.tenant_usage.find(
        {"month": month}, {"_id": 0}
    ).sort("estimated_cost_usd", -1)
    docs = await cursor.to_list(length=100)

    results = []
    for doc in docs:
        total = doc.get("total_requests", 0) or 1
        free = doc.get("free_requests", 0)
        estimated = doc.get("estimated_cost_usd", 0)
        actual = doc.get("actual_cost_usd", 0)
        results.append({
            **doc,
            "free_pct": round(free / total * 100, 1) if total > 0 else 100,
            "paid_pct": round((total - free) / total * 100, 1) if total > 0 else 0,
            "savings_usd": round(estimated - actual, 2),
        })

    return results


async def generate_monthly_report(tenant_id: str, month: str = None) -> dict:
    """Generate monthly cost report for email delivery."""
    cost = await get_tenant_cost(tenant_id, month)
    if not month:
        month = datetime.now(timezone.utc).strftime("%Y-%m")

    report = {
        "tenant_id": tenant_id,
        "month": month,
        "subject": f"Your AUREM AI Cost Report — {month}",
        "body": (
            f"AI actions completed: {cost.get('total_requests', 0)}\n"
            f"Estimated cost at GPT-4o rates: ${cost.get('estimated_cost_usd', 0):.2f}\n"
            f"Your actual cost: ${cost.get('actual_cost_usd', 0):.2f}"
            f" ({'free tier' if cost.get('actual_cost_usd', 0) == 0 else 'paid'})\n"
            f"You saved: ${cost.get('savings_usd', 0):.2f} this month\n"
            f"\nFree model usage: {cost.get('free_pct', 0)}%\n"
            f"Paid model fallback: {cost.get('paid_pct', 0)}%"
        ),
        "data": cost,
    }
    return report
