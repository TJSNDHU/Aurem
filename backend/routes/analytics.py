"""
ReRoots Admin Analytics Routes
Extracted from server.py to reduce main file size
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

analytics_router = APIRouter(prefix="/admin/analytics", tags=["Admin Analytics"])


def get_db():
    """Get database instance"""
    from server import db
    return db


def get_current_user():
    """Get current user dependency"""
    from server import get_current_user as _get_current_user
    return _get_current_user


@analytics_router.get("")
async def get_admin_analytics(
    days: int = 30,
    current_user: dict = Depends(get_current_user())
):
    """Get admin analytics data (server-side computed)"""
    db = get_db()
    
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        start_date_str = start_date.isoformat()

        # Total orders in period
        orders = await db.orders.find(
            {
                "$or": [
                    {"created_at": {"$gte": start_date_str}},
                    {"created_at": {"$gte": start_date.strftime("%Y-%m-%dT%H:%M:%S")}},
                ]
            },
            {"_id": 0, "total": 1, "status": 1},
        ).to_list(10000)

        total_orders = len(orders)
        completed_orders = [
            o for o in orders
            if o.get("status") in ["completed", "shipped", "delivered"]
        ]
        total_revenue = sum(float(o.get("total", 0)) for o in completed_orders)

        # Sessions (unique carts)
        total_sessions = await db.carts.count_documents(
            {
                "$or": [
                    {"updated_at": {"$gte": start_date_str}},
                    {"updated_at": {"$gte": start_date.strftime("%Y-%m-%dT%H:%M:%S")}},
                ]
            }
        )

        # Calculate metrics
        conversion_rate = (total_orders / total_sessions * 100) if total_sessions > 0 else 0
        aov = (total_revenue / len(completed_orders)) if completed_orders else 0

        return {
            "total_revenue": round(total_revenue, 2),
            "total_orders": total_orders,
            "conversion_rate": round(conversion_rate, 2),
            "average_order_value": round(aov, 2),
            "total_sessions": total_sessions,
            "period_days": days,
        }
    except Exception as e:
        logger.error(f"Analytics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
