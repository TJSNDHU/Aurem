"""
Revenue Forecasting — P1
==========================
90-day forecast for Revenue Dashboard:
  pipeline_value x win_probability_avg
  + recurring x avg_invoice
  + pending x historical_payment_rate
Show: projected revenue + revenue at risk.
One line in Morning Brief.
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
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


async def compute_90day_forecast(tenant_id: str) -> dict:
    """Compute 90-day revenue forecast from pipeline, recurring, and pending data."""
    db = _get_db()
    if db is None:
        return {"forecast_available": False, "reason": "no_db"}

    now = datetime.now(timezone.utc)
    cutoff_90d = (now - timedelta(days=90)).isoformat()

    # 1. Pipeline value x win_probability_avg
    pipeline_value = 0
    win_prob_sum = 0
    lead_count = 0
    async for lead in db.leads.find(
        {"tenant_id": tenant_id, "status": {"$in": ["new", "contacted", "qualified", "unprocessed"]}},
        {"_id": 0, "win_probability": 1, "deal_value": 1, "estimated_value": 1}
    ).limit(500):
        val = float(lead.get("deal_value") or lead.get("estimated_value") or 0)
        prob = float(lead.get("win_probability") or 0.3)
        pipeline_value += val
        win_prob_sum += prob
        lead_count += 1
    avg_win_prob = round(win_prob_sum / lead_count, 2) if lead_count > 0 else 0.3
    pipeline_weighted = round(pipeline_value * avg_win_prob, 2)

    # 2. Recurring revenue (completed orders in last 90d)
    completed_amounts = []
    async for order in db.orders.find(
        {"tenant_id": tenant_id, "status": {"$in": ["completed", "paid"]},
         "created_at": {"$gte": cutoff_90d}},
        {"_id": 0, "total": 1, "amount": 1}
    ).limit(500):
        amt = float(order.get("total") or order.get("amount") or 0)
        if amt > 0:
            completed_amounts.append(amt)

    avg_invoice = round(sum(completed_amounts) / len(completed_amounts), 2) if completed_amounts else 0
    monthly_recurring = round(len(completed_amounts) / 3 * avg_invoice, 2)  # 3 months
    recurring_90d = round(monthly_recurring * 3, 2)

    # 3. Pending x historical_payment_rate
    pending_count = await db.orders.count_documents({
        "tenant_id": tenant_id, "status": "pending"
    })
    total_orders = await db.orders.count_documents({"tenant_id": tenant_id})
    completed_count = len(completed_amounts)
    historical_rate = round(completed_count / total_orders, 2) if total_orders > 0 else 0.5

    pending_amounts = []
    async for order in db.orders.find(
        {"tenant_id": tenant_id, "status": "pending"},
        {"_id": 0, "total": 1, "amount": 1}
    ).limit(200):
        amt = float(order.get("total") or order.get("amount") or 0)
        if amt > 0:
            pending_amounts.append(amt)
    pending_total = sum(pending_amounts)
    pending_expected = round(pending_total * historical_rate, 2)

    # Totals
    projected_revenue = round(pipeline_weighted + recurring_90d + pending_expected, 2)
    revenue_at_risk = round(
        pipeline_value * (1 - avg_win_prob) + pending_total * (1 - historical_rate), 2
    )

    forecast = {
        "tenant_id": tenant_id,
        "forecast_available": True,
        "period_days": 90,
        "pipeline": {
            "total_value": pipeline_value,
            "active_leads": lead_count,
            "avg_win_probability": avg_win_prob,
            "weighted_value": pipeline_weighted,
        },
        "recurring": {
            "completed_orders_90d": len(completed_amounts),
            "avg_invoice": avg_invoice,
            "monthly_recurring": monthly_recurring,
            "projected_90d": recurring_90d,
        },
        "pending": {
            "pending_orders": pending_count,
            "pending_total": pending_total,
            "historical_payment_rate": historical_rate,
            "expected_recovery": pending_expected,
        },
        "summary": {
            "projected_revenue": projected_revenue,
            "revenue_at_risk": revenue_at_risk,
            "confidence": "high" if lead_count > 10 else "medium" if lead_count > 3 else "low",
        },
        "computed_at": now.isoformat(),
    }

    # Store forecast
    if db is not None:
        await db.revenue_forecasts.insert_one({
            **{k: v for k, v in forecast.items() if k != "forecast_available"},
            "timestamp": now.isoformat(),
        })

    return forecast


async def get_morning_brief_line(tenant_id: str) -> str:
    """One-line revenue forecast for the Morning Brief."""
    forecast = await compute_90day_forecast(tenant_id)
    if not forecast.get("forecast_available"):
        return "Revenue forecast: insufficient data."

    s = forecast["summary"]
    p = forecast["pipeline"]
    return (
        f"90-Day Forecast: ${s['projected_revenue']:,.0f} projected "
        f"(${p['weighted_value']:,.0f} pipeline + "
        f"${forecast['recurring']['projected_90d']:,.0f} recurring + "
        f"${forecast['pending']['expected_recovery']:,.0f} pending). "
        f"Revenue at risk: ${s['revenue_at_risk']:,.0f}. "
        f"Confidence: {s['confidence']}."
    )


async def get_forecast_history(tenant_id: str, limit: int = 10) -> list:
    """Get recent forecast snapshots."""
    db = _get_db()
    if db is None:
        return []
    cursor = db.revenue_forecasts.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("timestamp", -1).limit(limit)
    return await cursor.to_list(length=limit)
