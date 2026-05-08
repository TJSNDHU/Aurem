"""
Analytics Service - Sales Dashboard & Acquisition Tracking
Provides business intelligence and conversion funnel metrics.
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

# MongoDB will be injected from server.py
db = None

def set_db(database):
    """Set the database reference."""
    global db
    db = database


async def get_sales_dashboard(period: str = "daily") -> dict:
    """
    GET /api/admin/analytics/sales?period=daily|weekly|monthly
    Returns revenue data, summary stats, and top products.
    """
    now = datetime.now(timezone.utc)
    
    # Determine date range based on period
    if period == "daily":
        start_date = now - timedelta(days=30)
        group_format = "%Y-%m-%d"
    elif period == "weekly":
        start_date = now - timedelta(weeks=12)
        group_format = "%Y-W%W"
    else:  # monthly
        start_date = now - timedelta(days=365)
        group_format = "%Y-%m"
    
    start_date_str = start_date.isoformat()
    
    # Get all orders in range (excluding refunded/cancelled)
    orders_cursor = db.orders.find({
        "created_at": {"$gte": start_date_str},
        "order_status": {"$nin": ["refunded", "cancelled"]},
        "payment_status": {"$in": ["paid", "completed", "success"]}
    }, {"_id": 0})
    
    orders = await orders_cursor.to_list(1000)
    
    # Group by period
    revenue_by_period = {}
    for order in orders:
        try:
            order_date_str = order.get("created_at", "")
            if isinstance(order_date_str, str):
                order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
            else:
                order_date = order_date_str or now
            
            period_key = order_date.strftime(group_format)
            
            if period_key not in revenue_by_period:
                revenue_by_period[period_key] = {
                    "period": period_key,
                    "order_count": 0,
                    "revenue": 0.0,
                    "totals": []
                }
            
            revenue_by_period[period_key]["order_count"] += 1
            revenue_by_period[period_key]["revenue"] += float(order.get("total", 0))
            revenue_by_period[period_key]["totals"].append(float(order.get("total", 0)))
        except Exception as e:
            logging.warning(f"[Analytics] Date parsing error: {e}")
            continue
    
    # Calculate averages and format chart data
    chart_data = []
    for key in sorted(revenue_by_period.keys()):
        data = revenue_by_period[key]
        avg_order_value = sum(data["totals"]) / len(data["totals"]) if data["totals"] else 0
        chart_data.append({
            "period": data["period"],
            "order_count": data["order_count"],
            "revenue": round(data["revenue"], 2),
            "avg_order_value": round(avg_order_value, 2)
        })
    
    # Summary stats (last 30 days)
    thirty_days_ago = (now - timedelta(days=30)).isoformat()
    recent_orders = [o for o in orders if o.get("created_at", "") >= thirty_days_ago]
    
    unique_customers = set()
    total_revenue = 0.0
    order_totals = []
    
    for order in recent_orders:
        total_revenue += float(order.get("total", 0))
        order_totals.append(float(order.get("total", 0)))
        email = order.get("customer_email") or order.get("shipping_address", {}).get("email")
        if email:
            unique_customers.add(email.lower())
    
    avg_order_value = sum(order_totals) / len(order_totals) if order_totals else 0
    
    summary = {
        "total_orders": len(recent_orders),
        "total_revenue": round(total_revenue, 2),
        "avg_order_value": round(avg_order_value, 2),
        "unique_customers": len(unique_customers)
    }
    
    # Top products (last 30 days)
    product_sales = {}
    for order in recent_orders:
        for item in order.get("items", []):
            product_name = item.get("product_name") or item.get("name", "Unknown")
            quantity = int(item.get("quantity", 1))
            price = float(item.get("price", 0))
            
            if product_name not in product_sales:
                product_sales[product_name] = {"units_sold": 0, "revenue": 0.0}
            
            product_sales[product_name]["units_sold"] += quantity
            product_sales[product_name]["revenue"] += price * quantity
    
    top_products = sorted(
        [{"product": k, **v} for k, v in product_sales.items()],
        key=lambda x: x["revenue"],
        reverse=True
    )[:5]
    
    for p in top_products:
        p["revenue"] = round(p["revenue"], 2)
    
    return {
        "period": period,
        "summary": summary,
        "chart_data": chart_data,
        "top_products": top_products
    }


async def get_acquisition_sources() -> dict:
    """
    GET /api/admin/analytics/acquisition
    Tracks where customers came from and conversion funnel.
    """
    # Get all customers
    customers_cursor = db.customers.find({}, {"_id": 0})
    customers = await customers_cursor.to_list(1000)
    
    # Group by acquisition source
    sources = {}
    funnel = {
        "visitors": 0,
        "quiz_completions": 0,
        "first_purchase": 0,
        "repeat_purchase": 0,
        "vip": 0
    }
    
    for customer in customers:
        source = customer.get("acquisition_source", "direct") or "direct"
        
        if source not in sources:
            sources[source] = {
                "acquisition_source": source,
                "customers": 0,
                "total_revenue": 0.0,
                "total_ltv": 0.0,
                "vip_count": 0
            }
        
        sources[source]["customers"] += 1
        sources[source]["total_revenue"] += float(customer.get("ltv", 0))
        sources[source]["total_ltv"] += float(customer.get("ltv", 0))
        
        if customer.get("vip_status"):
            sources[source]["vip_count"] += 1
        
        # Funnel metrics
        funnel["visitors"] += 1
        
        if customer.get("quiz_completed"):
            funnel["quiz_completions"] += 1
        
        total_orders = customer.get("total_orders", 0)
        if total_orders >= 1:
            funnel["first_purchase"] += 1
        if total_orders >= 2:
            funnel["repeat_purchase"] += 1
        if customer.get("vip_status"):
            funnel["vip"] += 1
    
    # Calculate averages and format
    by_source = []
    for source_data in sources.values():
        count = source_data["customers"]
        by_source.append({
            "acquisition_source": source_data["acquisition_source"],
            "customers": count,
            "total_revenue": round(source_data["total_revenue"], 2),
            "avg_ltv": round(source_data["total_ltv"] / count, 2) if count > 0 else 0,
            "vip_count": source_data["vip_count"]
        })
    
    # Sort by revenue
    by_source = sorted(by_source, key=lambda x: x["total_revenue"], reverse=True)
    
    return {
        "by_source": by_source,
        "funnel": funnel
    }


async def get_revenue_metrics() -> dict:
    """
    Get key revenue metrics for dashboard cards.
    """
    now = datetime.now(timezone.utc)
    
    # This month
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Last month
    last_month_end = month_start - timedelta(seconds=1)
    last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Count orders and revenue
    async def get_period_stats(start_date, end_date=None):
        query = {
            "created_at": {"$gte": start_date.isoformat()},
            "payment_status": {"$in": ["paid", "completed", "success"]}
        }
        if end_date:
            query["created_at"]["$lt"] = end_date.isoformat()
        
        cursor = db.orders.find(query, {"_id": 0, "total": 1})
        orders = await cursor.to_list(1000)
        
        return {
            "count": len(orders),
            "revenue": sum(float(o.get("total", 0)) for o in orders)
        }
    
    this_month = await get_period_stats(month_start)
    last_month = await get_period_stats(last_month_start, month_start)
    today = await get_period_stats(today_start)
    
    # Calculate growth
    revenue_growth = 0
    if last_month["revenue"] > 0:
        revenue_growth = ((this_month["revenue"] - last_month["revenue"]) / last_month["revenue"]) * 100
    
    return {
        "today": {
            "orders": today["count"],
            "revenue": round(today["revenue"], 2)
        },
        "this_month": {
            "orders": this_month["count"],
            "revenue": round(this_month["revenue"], 2)
        },
        "last_month": {
            "orders": last_month["count"],
            "revenue": round(last_month["revenue"], 2)
        },
        "revenue_growth_percent": round(revenue_growth, 1)
    }


def capture_utm_params(order_data: dict, utm_params: dict) -> dict:
    """
    Capture UTM parameters at checkout.
    Call this before creating an order.
    """
    source_map = {
        "instagram": "instagram",
        "tiktok": "tiktok",
        "google": "google",
        "email": "email",
        "whatsapp": "whatsapp",
        "facebook": "facebook",
        "twitter": "twitter",
        "referral": "referral"
    }
    
    source = utm_params.get("utm_source", "direct") or "direct"
    acquisition_source = source_map.get(source.lower(), source.lower() if source else "direct")
    
    order_data["acquisition_source"] = acquisition_source
    order_data["utm_campaign"] = utm_params.get("utm_campaign")
    order_data["utm_medium"] = utm_params.get("utm_medium")
    order_data["utm_content"] = utm_params.get("utm_content")
    
    return order_data
