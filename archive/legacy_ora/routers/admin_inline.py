"""
Admin panel, order mgmt, email, shipping
Extracted from server.py during modularization.
"""

import os
try:
    import resend
except ImportError:
    resend = None
try:
    import httpx
except ImportError:
    httpx = None
import asyncio
import logging
import json
import hashlib
import secrets
import time
import uuid
import re
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Request, Query, Body, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, Response, StreamingResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId

async def auto_create_shipment(order: dict):
    logging.warning(f"auto_create_shipment not implemented — skipping (order={order.get('id', 'unknown')})")
    return None
try:
    from models.server_models import Order, Review
except ImportError:
    pass
try:
    from services.email_templates import (
        send_daily_review_digest, send_order_cancellation_email,
        send_order_confirmation_email, send_review_thank_you_email,
        send_shipping_notifications, send_shipping_update_email
    )
except ImportError:
    pass

logger = logging.getLogger(__name__)
import base64
_paypal_token_cache = {'token': None, 'expires_at': 0}
async def get_paypal_access_token():
    import time
    if _paypal_token_cache['token'] and _paypal_token_cache['expires_at'] > time.time() + 60:
        return _paypal_token_cache['token']
    pid = os.environ.get('PAYPAL_CLIENT_ID', '')
    psecret = os.environ.get('PAYPAL_SECRET', '')
    if not pid or not psecret: raise Exception('PayPal not configured')
    creds = base64.b64encode(f'{pid}:{psecret}'.encode()).decode()
    pbase = 'https://api-m.sandbox.paypal.com' if os.environ.get('PAYPAL_MODE','sandbox')=='sandbox' else 'https://api-m.paypal.com'
    async with httpx.AsyncClient() as client:
        resp = await client.post(f'{pbase}/v1/oauth2/token', headers={'Authorization': f'Basic {creds}', 'Content-Type': 'application/x-www-form-urlencoded'}, data='grant_type=client_credentials')
        if resp.status_code == 200:
            data = resp.json()
            _paypal_token_cache['token'] = data['access_token']
            _paypal_token_cache['expires_at'] = time.time() + data.get('expires_in', 3600)
            return data['access_token']
        raise Exception(f'PayPal auth failed: {resp.status_code}')
async def trigger_restock_notifications(*args, **kwargs): pass  # Stub: notifications not configured

# Environment variables
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'noreply@aurem.live')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')

# Payment & messaging env vars
BAMBORA_MERCHANT_ID = os.environ.get('BAMBORA_MERCHANT_ID', '')
BAMBORA_API_PASSCODE = os.environ.get('BAMBORA_API_PASSCODE', '')
BAMBORA_API_URL = os.environ.get('BAMBORA_API_URL', 'https://api.na.bambora.com')
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID', '')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET', '')
PAYPAL_MODE = os.environ.get('PAYPAL_MODE', 'sandbox')
PAYPAL_API_BASE = 'https://api-m.sandbox.paypal.com' if os.environ.get('PAYPAL_MODE', 'sandbox') == 'sandbox' else 'https://api-m.paypal.com'
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')


# Common imports from server.py scope
import bcrypt
import jwt
try:
    import stripe
except ImportError:
    stripe = None

try:
    from performance_patch import limiter
except ImportError:
    limiter = type('obj', (object,), {'limit': lambda self, *a, **kw: lambda f: f})()

from middleware.security import sanitize_input, validate_email

try:
    from middleware.websocket_manager import WebSocketConnectionManager
    manager = WebSocketConnectionManager()
except ImportError:
    manager = None

from config import JWT_SECRET
FRONTEND_URL = os.environ.get("FRONTEND_URL", "")
SITE_URL = os.environ.get("SITE_URL", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
if stripe and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

# MongoDB client reference (set at startup)
client = None

def set_client(c):
    global client
    client = c

# Helpers from server.py scope
ROOT_DIR = __import__("pathlib").Path(os.path.dirname(os.path.abspath(__file__)))

async def get_current_user(request: Request):
    """Extract user from JWT token in request."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        token = auth.replace("Bearer ", "")
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except Exception:
        return None

async def require_admin(request: Request):
    """Verify admin role from JWT."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user.get("role") not in ("admin", "founder", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def generate_jwt_token(user_data: dict, expires_hours: int = 24):
    """Generate JWT token."""
    import time as _time
    payload = {
        **user_data,
        "exp": int(_time.time()) + (expires_hours * 3600),
        "iat": int(_time.time()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")



# Shared state — set by server.py at startup
db = None
api_router = None

def set_db(database):
    global db
    db = database

def set_router(router):
    global api_router
    api_router = router

def get_db():
    return db

router = APIRouter()

# ============= ADMIN ROUTES =============


@router.get("/admin/stats")
async def get_admin_stats(request: Request, period: str = "30d", brand: Optional[str] = None):
    await require_admin(request)

    # Calculate date range based on period
    now = datetime.now(timezone.utc)
    if period == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        prev_start = start_date - timedelta(days=1)
        prev_end = start_date
    elif period == "7d":
        start_date = now - timedelta(days=7)
        prev_start = start_date - timedelta(days=7)
        prev_end = start_date
    elif period == "90d":
        start_date = now - timedelta(days=90)
        prev_start = start_date - timedelta(days=90)
        prev_end = start_date
    else:  # default 30d
        start_date = now - timedelta(days=30)
        prev_start = start_date - timedelta(days=30)
        prev_end = start_date

    start_date_str = start_date.isoformat()
    prev_start_str = prev_start.isoformat()
    prev_end_str = prev_end.isoformat()

    # Build brand filter
    active_brand = brand or getattr(request.state, 'brand', 'reroots')
    brand_filter = {}
    if active_brand == "lavela":
        brand_filter = {"$or": [{"brand": "lavela"}, {"items.brand": "lavela"}, {"tags": {"$in": ["lavela", "teen"]}}]}
    elif active_brand == "reroots":
        brand_filter = {"brand": {"$ne": "lavela"}}

    # Current period - ONLY paid orders (excludes canceled, refunded, test) with brand filter
    paid_query = {"payment_status": "paid", "created_at": {"$gte": start_date_str}, **brand_filter}

    # Previous period for comparison
    prev_paid_query = {
        "payment_status": "paid",
        "created_at": {"$gte": prev_start_str, "$lt": prev_end_str},
        **brand_filter
    }

    # Current period stats
    current_orders = await db.orders.find(paid_query, {"_id": 0}).to_list(1000)
    current_revenue = sum(o.get("total", 0) for o in current_orders)
    current_order_count = len(current_orders)

    # Previous period stats for comparison
    prev_orders = await db.orders.find(prev_paid_query, {"_id": 0}).to_list(1000)
    prev_revenue = sum(o.get("total", 0) for o in prev_orders)
    prev_order_count = len(prev_orders)

    # Calculate percentage changes
    def calc_change(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100, 1)

    revenue_change = calc_change(current_revenue, prev_revenue)
    orders_change = calc_change(current_order_count, prev_order_count)

    # Total counts (with brand filter)
    all_time_filter = {"payment_status": "paid", **brand_filter}
    total_orders = await db.orders.count_documents(all_time_filter)
    
    # Products filter by brand
    product_brand_filter = {}
    if active_brand == "lavela":
        product_brand_filter = {"$or": [{"brand": "lavela"}, {"tags": {"$in": ["lavela", "teen"]}}]}
    elif active_brand == "reroots":
        product_brand_filter = {"brand": {"$ne": "lavela"}}
    total_products = await db.products.count_documents(product_brand_filter)
    
    # Customers - filter by brand preference if available
    customer_brand_filter = {}
    if active_brand == "lavela":
        customer_brand_filter = {"$or": [{"brand": "lavela"}, {"preferences.brand": "lavela"}]}
    total_customers = await db.users.count_documents({"is_admin": False, **customer_brand_filter})

    # All-time revenue (only paid orders with brand filter)
    pipeline = [
        {"$match": all_time_filter},
        {"$group": {"_id": None, "total": {"$sum": "$total"}}},
    ]
    revenue_result = await db.orders.aggregate(pipeline).to_list(1)
    total_revenue = revenue_result[0]["total"] if revenue_result else 0

    # AOV - Average Order Value (only paid orders)
    avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

    # Previous period AOV
    prev_aov = (
        sum(o.get("total", 0) for o in prev_orders) / len(prev_orders)
        if prev_orders
        else 0
    )
    current_aov = (
        current_revenue / current_order_count if current_order_count > 0 else 0
    )
    aov_change = calc_change(current_aov, prev_aov)

    # Top products by actual sales (from paid orders)
    product_sales = {}
    for order in current_orders:
        for item in order.get("items", []):
            pid = item.get("product_id") or item.get("id")
            if pid:
                if pid not in product_sales:
                    product_sales[pid] = {
                        "name": item.get("product_name", "Unknown"),
                        "sales": 0,
                        "revenue": 0,
                    }
                product_sales[pid]["sales"] += item.get("quantity", 1)
                product_sales[pid]["revenue"] += item.get("price", 0) * item.get(
                    "quantity", 1
                )

    top_products = sorted(
        product_sales.values(), key=lambda x: x["revenue"], reverse=True
    )[:5]

    # Visitor tracking - get from analytics collection if exists
    visitors_current = (
        await db.analytics_visits.count_documents(
            {"timestamp": {"$gte": start_date_str}}
        )
        or 0
    )
    visitors_prev = (
        await db.analytics_visits.count_documents(
            {"timestamp": {"$gte": prev_start_str, "$lt": prev_end_str}}
        )
        or 0
    )

    # Conversion rate (orders / visitors * 100)
    # If no visitor tracking, estimate based on industry average or use 0
    if visitors_current > 0:
        conversion_rate = round((current_order_count / visitors_current) * 100, 2)
        prev_conversion = (
            round((prev_order_count / visitors_prev) * 100, 2)
            if visitors_prev > 0
            else 0
        )
        conversion_change = calc_change(conversion_rate, prev_conversion)
    else:
        # No visitor tracking - show as "N/A" indicator
        conversion_rate = 0
        conversion_change = 0

    # Recent orders (most recent 5 paid orders)
    recent_orders = (
        await db.orders.find({"payment_status": "paid"}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(5)
    )

    # Customer stats
    new_customers_current = await db.users.count_documents(
        {"is_admin": False, "created_at": {"$gte": start_date_str}}
    )
    new_customers_prev = await db.users.count_documents(
        {"is_admin": False, "created_at": {"$gte": prev_start_str, "$lt": prev_end_str}}
    )
    customers_change = calc_change(new_customers_current, new_customers_prev)

    return {
        "total_orders": total_orders,
        "total_products": total_products,
        "total_customers": total_customers,
        "total_revenue": round(total_revenue, 2),
        "avg_order_value": round(avg_order_value, 2),
        "conversion_rate": conversion_rate,
        "top_products": top_products,
        "recent_orders": recent_orders,
        # Period-specific stats
        "period_revenue": round(current_revenue, 2),
        "period_orders": current_order_count,
        # Percentage changes vs previous period
        "revenue_change": revenue_change,
        "orders_change": orders_change,
        "customers_change": customers_change,
        "aov_change": aov_change,
        "conversion_change": conversion_change,
        # Tracking status
        "visitor_tracking_enabled": visitors_current > 0,
    }


@router.get("/admin/waitlist-stats")
async def get_waitlist_stats(request: Request):
    """Get waitlist/referral army statistics for admin dashboard"""
    await require_admin(request)

    # Total Emails Collected (size of your army)
    total_emails = await db.waitlist.count_documents({})

    # Active Referrers (people with 1+ referrals)
    active_referrers = await db.waitlist.count_documents(
        {"verified_referrals": {"$gte": 1}}
    )

    # VIP Members (people who hit 10+ referrals)
    vip_members = await db.waitlist.count_documents({"voucher_unlocked": True})

    # Total referrals sent (all referral records)
    total_referrals_sent = await db.founding_member_referrals.count_documents({})

    # Verified referrals (converted)
    verified_referrals = await db.founding_member_referrals.count_documents(
        {"verified": True}
    )

    # Conversion Rate: % of referred friends who signed up and verified
    conversion_rate = (
        (verified_referrals / total_referrals_sent * 100)
        if total_referrals_sent > 0
        else 0
    )

    # Top referrers leaderboard
    top_referrers = (
        await db.waitlist.find(
            {"verified_referrals": {"$gte": 1}},
            {
                "_id": 0,
                "name": 1,
                "email": 1,
                "verified_referrals": 1,
                "voucher_unlocked": 1,
            },
        )
        .sort("verified_referrals", -1)
        .limit(10)
        .to_list(10)
    )

    # Recent signups (last 24 hours)
    from datetime import timedelta

    yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_signups = await db.waitlist.count_documents(
        {"created_at": {"$gte": yesterday.isoformat()}}
    )

    # Signups by source
    source_pipeline = [
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    sources = await db.waitlist.aggregate(source_pipeline).to_list(5)
    signup_sources = {s["_id"] or "direct": s["count"] for s in sources}

    return {
        "total_emails": total_emails,
        "active_referrers": active_referrers,
        "vip_members": vip_members,
        "total_referrals_sent": total_referrals_sent,
        "verified_referrals": verified_referrals,
        "conversion_rate": round(conversion_rate, 1),
        "top_referrers": top_referrers,
        "recent_signups_24h": recent_signups,
        "signup_sources": signup_sources,
    }


@router.post("/admin/inventory/trigger-restock")
async def manual_restock_trigger(data: dict, request: Request):
    """Manually trigger restock notifications for a product"""
    await require_admin(request)
    product_id = data.get("productId") or data.get("product_id")
    new_stock = int(data.get("newStock") or data.get("stock") or 1)
    if not product_id:
        raise HTTPException(status_code=400, detail="productId required")
    return await trigger_restock_notifications(db, product_id, new_stock, 0)


@router.get("/admin/restock-notifications/stats")
async def restock_stats(request: Request):
    """Get restock notification statistics"""
    await require_admin(request)
    total_sent = await db.restock_notifications.count_documents({})
    total_converted = await db.restock_notifications.count_documents({"converted": True})
    wl_a = await db.waitlist_subscribers.count_documents({"notified": {"$ne": True}})
    wl_b = await db.subscribers.count_documents({"type": "waitlist", "notified": {"$ne": True}})
    return {
        "waitlist_pending": wl_a + wl_b,
        "notifications_sent": total_sent,
        "conversions": total_converted,
        "cvr_pct": round(total_converted / total_sent * 100, 1) if total_sent else 0,
    }


@router.get("/admin/analytics/reddit")
async def get_reddit_analytics(request: Request):
    """Get Reddit-specific signup analytics"""
    await require_admin(request)

    # Get all Reddit signups
    reddit_pipeline = [
        {"$match": {"source": {"$regex": "^reddit", "$options": "i"}}},
        {"$group": {"_id": "$source", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    reddit_sources = await db.waitlist.aggregate(reddit_pipeline).to_list(20)

    # Get signups with UTM data
    utm_pipeline = [
        {"$match": {"utm_data.source": "reddit"}},
        {
            "$group": {
                "_id": "$utm_data.medium",
                "count": {"$sum": 1},
                "referrals": {"$sum": "$referral_count"},
            }
        },
        {"$sort": {"count": -1}},
    ]
    subreddit_stats = await db.waitlist.aggregate(utm_pipeline).to_list(20)

    # Total Reddit signups
    total_reddit = await db.waitlist.count_documents(
        {
            "$or": [
                {"source": {"$regex": "^reddit", "$options": "i"}},
                {"utm_data.source": "reddit"},
            ]
        }
    )

    # Reddit signups in last 7 days
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent_reddit = await db.waitlist.count_documents(
        {
            "$or": [
                {"source": {"$regex": "^reddit", "$options": "i"}},
                {"utm_data.source": "reddit"},
            ],
            "created_at": {"$gte": week_ago.isoformat()},
        }
    )

    # VIP conversions from Reddit
    reddit_vip = await db.waitlist.count_documents(
        {
            "$or": [
                {"source": {"$regex": "^reddit", "$options": "i"}},
                {"utm_data.source": "reddit"},
            ],
            "voucher_unlocked": True,
        }
    )

    return {
        "total_reddit_signups": total_reddit,
        "recent_7_days": recent_reddit,
        "reddit_vip_conversions": reddit_vip,
        "by_source": {s["_id"]: s["count"] for s in reddit_sources},
        "by_subreddit": [
            {
                "subreddit": s["_id"] or "unknown",
                "signups": s["count"],
                "total_referrals": s.get("referrals", 0),
            }
            for s in subreddit_stats
        ],
    }


@router.get("/admin/orders")
async def get_all_orders(
    request: Request, 
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    brand: Optional[str] = None
):
    """
    Get orders with server-side pagination, search, and filtering.
    - page: Page number (1-indexed)
    - limit: Items per page (default 20, max 100)
    - search: Search in order_number, customer name, email
    - status: Filter by order status
    - sort_by: Field to sort by
    - sort_order: 'asc' or 'desc'
    - brand: Filter by brand ('reroots' or 'lavela')
    """
    await require_admin(request)
    
    # Ensure limit is reasonable
    limit = min(max(1, limit), 100)
    skip = (page - 1) * limit
    
    # Build query
    query = {}
    if status and status != "all":
        query["order_status"] = status
    
    # Brand filtering
    if brand and brand != "all":
        if brand == "lavela":
            # La Vela orders: products with lavela tag or category
            query["$or"] = [
                {"brand": "lavela"},
                {"items.brand": "lavela"},
                {"items.tags": {"$in": ["lavela", "teen"]}},
            ]
        elif brand == "reroots":
            # ReRoots orders: exclude La Vela
            query["brand"] = {"$ne": "lavela"}
            query["items.brand"] = {"$ne": "lavela"}
    
    # Search functionality
    if search:
        search_regex = {"$regex": search, "$options": "i"}
        search_conditions = [
            {"order_number": search_regex},
            {"shipping_address.first_name": search_regex},
            {"shipping_address.last_name": search_regex},
            {"shipping_address.email": search_regex},
            {"user_email": search_regex},
            {"id": search_regex}
        ]
        if "$or" in query:
            # Combine existing $or with search $or
            query = {"$and": [{"$or": query["$or"]}, {"$or": search_conditions}]}
        else:
            query["$or"] = search_conditions
    
    # Sort direction
    sort_direction = -1 if sort_order == "desc" else 1
    
    # Get total count for pagination info
    total_count = await db.orders.count_documents(query)
    
    # Fetch paginated orders
    orders = await db.orders.find(query, {"_id": 0}).sort(sort_by, sort_direction).skip(skip).limit(limit).to_list(limit)
    
    # Calculate pagination metadata
    total_pages = (total_count + limit - 1) // limit  # Ceiling division
    
    return {
        "orders": orders,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        }
    }


@router.put("/admin/orders/{order_id}/status")
async def update_order_status(order_id: str, status_data: dict, request: Request):
    await require_admin(request)
    await db.orders.update_one(
        {"id": order_id}, {"$set": {"order_status": status_data.get("status")}}
    )
    return {"message": "Order status updated"}


# ============= FLAGSHIP SHIPPING - TRACKING =============
# Manual courier tracking removed - Now using FlagShip API only


@router.get("/orders/{order_id}/tracking")
async def get_order_tracking(order_id: str, request: Request):
    """Get tracking information for an order (customer accessible via FlagShip)"""
    user = await get_current_user(request)
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Check if user is admin or owns the order
    if user and (user.get("is_admin") or order.get("user_id") == user.get("id")):
        tracking_number = order.get("tracking_number")

        # If we have a tracking number, try to get live tracking from FlagShip
        tracking_info = None
        if tracking_number:
            try:
                from services.flagship_shipping import flagship_client

                tracking_info = await flagship_client.track_shipment(tracking_number)
            except Exception as e:
                logging.error(f"FlagShip tracking error: {e}")

        return {
            "order_id": order_id,
            "order_number": order.get("order_number"),
            "tracking_number": tracking_number,
            "shipping_carrier": order.get("shipping_carrier"),
            "shipping_label_url": order.get("shipping_label_url"),
            "shipment_id": order.get("shipment_id"),
            "tracking_status": order.get("tracking_status", "pending"),
            "shipped_at": order.get("shipped_at"),
            "delivered_at": order.get("delivered_at"),
            "order_status": order.get("order_status"),
            "live_tracking": tracking_info,
        }

    raise HTTPException(status_code=403, detail="Access denied")


# ============= ORDER CANCELLATION & REFUND =============


def generate_cancellation_email(
    order: dict, refund_amount: float, store_settings: dict = None
) -> str:
    """Generate HTML email for order cancellation confirmation"""
    store_name = (
        store_settings.get("store_name", "ReRoots") if store_settings else "ReRoots"
    )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Order Cancelled - {store_name}</title>
    </head>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #2D2A2E; margin: 0; padding: 0; background-color: #f5f5f5;">
        <table cellpadding="0" cellspacing="0" width="100%" style="background-color: #f5f5f5;">
            <tr>
                <td align="center" style="padding: 20px;">
                    <table cellpadding="0" cellspacing="0" width="600" style="background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                        <tr>
                            <td style="background: linear-gradient(135deg, #2D2A2E 0%, #3d393d 100%); padding: 30px 20px; text-align: center;">
                                <div style="font-size: 32px; font-weight: bold; color: #F8A5B8; letter-spacing: 2px;">REROOTS</div>
                                <div style="color: #D4AF37; font-size: 12px; letter-spacing: 3px; margin-top: 5px;">BEAUTY ENHANCER</div>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 40px 30px;">
                                <div style="text-align: center; margin-bottom: 30px;">
                                    <div style="font-size: 50px;">📦❌</div>
                                </div>
                                
                                <h1 style="text-align: center; color: #2D2A2E; margin: 0 0 10px 0; font-size: 24px;">Order Cancelled</h1>
                                <p style="text-align: center; color: #666; margin: 0 0 30px 0;">Your order has been successfully cancelled.</p>
                                
                                <div style="background: #FEF3F3; border-radius: 12px; padding: 25px; margin: 20px 0; border-left: 4px solid #EF4444;">
                                    <div style="font-size: 14px; color: #666;">Order Number</div>
                                    <div style="font-size: 24px; font-weight: bold; color: #2D2A2E; margin: 5px 0;">{order.get('order_number', 'N/A')}</div>
                                    <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #FCA5A5;">
                                        <span style="display: inline-block; padding: 8px 16px; border-radius: 20px; font-weight: bold; font-size: 14px; background: #FEE2E2; color: #DC2626;">Cancelled</span>
                                    </div>
                                </div>
                                
                                <div style="background: #ECFDF5; border-radius: 12px; padding: 25px; margin: 20px 0; text-align: center;">
                                    <div style="font-size: 14px; color: #666;">💰 Refund Amount</div>
                                    <div style="font-size: 32px; font-weight: bold; color: #059669; margin: 10px 0;">${refund_amount:.2f} CAD</div>
                                    <p style="color: #666; font-size: 14px; margin: 0;">Refund will be processed to your original payment method within 5-10 business days.</p>
                                </div>
                                
                                <div style="background: #f9f9f9; border-radius: 8px; padding: 20px; margin: 20px 0;">
                                    <h3 style="margin: 0 0 10px 0; color: #2D2A2E;">What happens next?</h3>
                                    <ul style="margin: 0; padding-left: 20px; color: #666;">
                                        <li>Your refund has been initiated</li>
                                        <li>You'll receive the funds in 5-10 business days</li>
                                        <li>Check your email for refund confirmation from your bank</li>
                                    </ul>
                                </div>
                                
                                <p style="text-align: center; color: #666; margin-top: 30px; font-size: 14px;">
                                    Questions? Contact us at <a href="mailto:support@reroots.ca" style="color: #F8A5B8;">support@reroots.ca</a>
                                </p>
                            </td>
                        </tr>
                        <tr>
                            <td style="background: #2D2A2E; color: #ffffff; padding: 20px; text-align: center;">
                                <p style="margin: 0; font-size: 12px; color: #888;">© 2025 {store_name}. All rights reserved.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    return html


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, data: dict, request: Request):
    """Cancel an order and process refund"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Verify user owns this order
    if order.get("user_id") != user.get("id") and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if order can be cancelled
    non_cancellable = [
        "shipped",
        "in_transit",
        "out_for_delivery",
        "delivered",
        "cancelled",
    ]
    if order.get("order_status") in non_cancellable:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel order with status: {order.get('order_status')}",
        )

    if order.get("payment_status") != "paid":
        raise HTTPException(status_code=400, detail="Cannot cancel unpaid order")

    refund_amount = order.get("total", 0)
    refund_status = "pending"
    stripe_refund_id = None

    # Process Stripe refund if session_id exists
    if order.get("stripe_session_id") and STRIPE_API_KEY:
        try:
            import stripe

            stripe.api_key = STRIPE_API_KEY

            # Get the payment intent from the session
            session = stripe.checkout.Session.retrieve(order["stripe_session_id"])
            if session.payment_intent:
                refund = stripe.Refund.create(
                    payment_intent=session.payment_intent,
                    amount=int(refund_amount * 100),  # Stripe uses cents
                    reason="requested_by_customer",
                )
                stripe_refund_id = refund.id
                refund_status = (
                    "refunded" if refund.status == "succeeded" else "pending"
                )
                logging.info(f"Stripe refund created: {refund.id} for order {order_id}")
        except Exception as e:
            logging.error(f"Stripe refund failed: {e}")
            # Continue with cancellation even if refund fails - admin can handle manually
            refund_status = "failed"

    # Update order status
    cancellation_reason = data.get("reason", "customer_requested")
    await db.orders.update_one(
        {"id": order_id},
        {
            "$set": {
                "order_status": "cancelled",
                "cancelled_at": datetime.now(timezone.utc).isoformat(),
                "cancellation_reason": cancellation_reason,
                "refund_status": refund_status,
                "refund_amount": refund_amount,
                "stripe_refund_id": stripe_refund_id,
                "refunded_at": (
                    datetime.now(timezone.utc).isoformat()
                    if refund_status == "refunded"
                    else None
                ),
            }
        },
    )

    # Send cancellation email to customer
    customer_email = order.get("shipping_address", {}).get("email")
    if not customer_email and order.get("user_id"):
        user_data = await db.users.find_one({"id": order["user_id"]}, {"_id": 0})
        customer_email = user_data.get("email") if user_data else None

    if customer_email and RESEND_API_KEY:
        try:
            store_settings = await db.store_settings.find_one({}, {"_id": 0})
            html_content = generate_cancellation_email(
                order, refund_amount, store_settings
            )

            params = {
                "from": SENDER_EMAIL,
                "to": [customer_email],
                "subject": f"Order Cancelled - #{order.get('order_number', '')} - Refund Processing",
                "html": html_content,
            }
            await asyncio.to_thread(resend.Emails.send, params)
            logging.info(f"Cancellation email sent to: {customer_email}")
        except Exception as e:
            logging.error(f"Failed to send cancellation email: {e}")

    return {
        "message": "Order cancelled successfully. Refund is being processed.",
        "refund_amount": refund_amount,
        "refund_status": refund_status,
    }


@router.post("/admin/orders/{order_id}/refund")
async def admin_refund_order(order_id: str, data: dict, request: Request):
    """Admin endpoint to manually process refund"""
    await require_admin(request)

    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    refund_amount = data.get("amount", order.get("total", 0))

    # Update order with refund info
    await db.orders.update_one(
        {"id": order_id},
        {
            "$set": {
                "refund_status": "refunded",
                "refund_amount": refund_amount,
                "refunded_at": datetime.now(timezone.utc).isoformat(),
                "refund_notes": data.get("notes", "Manual refund by admin"),
            }
        },
    )

    return {"message": f"Refund of ${refund_amount:.2f} recorded successfully"}


@router.post("/admin/orders/{order_id}/approve")
async def approve_order(order_id: str, request: Request):
    """Admin endpoint to approve a pending order"""
    await require_admin(request)
    
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Update order status to approved/processing
    await db.orders.update_one(
        {"id": order_id},
        {
            "$set": {
                "order_status": "processing",
                "approved_at": datetime.now(timezone.utc).isoformat(),
            }
        }
    )
    
    return {"message": "Order approved successfully", "status": "processing"}


@router.post("/admin/orders/{order_id}/cancel")
async def admin_cancel_order(order_id: str, data: dict, request: Request):
    """Admin endpoint to cancel an order and process refund automatically"""
    await require_admin(request)
    
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check if order is already cancelled
    if order.get("order_status") == "cancelled":
        raise HTTPException(status_code=400, detail="Order is already cancelled")
    
    refund_amount = 0
    refund_status = "not_required"
    refund_id = None
    refund_provider = None
    
    # Process refund if order was paid
    if order.get("payment_status") == "paid":
        refund_amount = order.get("total", 0)
        refund_status = "pending"
        
        payment_method = order.get("payment_method", "")
        
        # PayPal Refund
        if payment_method == "paypal_api" and order.get("paypal_order_id"):
            try:
                # Get PayPal access token
                access_token = await get_paypal_access_token()
                
                # First, get the capture ID from the PayPal order
                async with httpx.AsyncClient() as client:
                    # Get order details to find capture ID
                    order_resp = await client.get(
                        f"{PAYPAL_API_BASE}/v2/checkout/orders/{order['paypal_order_id']}",
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    
                    if order_resp.status_code == 200:
                        paypal_order = order_resp.json()
                        # Find capture ID from purchase units
                        capture_id = None
                        for pu in paypal_order.get("purchase_units", []):
                            for capture in pu.get("payments", {}).get("captures", []):
                                capture_id = capture.get("id")
                                break
                        
                        if capture_id:
                            # Process refund
                            refund_resp = await client.post(
                                f"{PAYPAL_API_BASE}/v2/payments/captures/{capture_id}/refund",
                                headers={
                                    "Authorization": f"Bearer {access_token}",
                                    "Content-Type": "application/json"
                                },
                                json={
                                    "amount": {
                                        "value": str(round(refund_amount, 2)),
                                        "currency_code": "CAD"
                                    },
                                    "note_to_payer": "Order cancelled. Refund processed."
                                }
                            )
                            
                            if refund_resp.status_code in [200, 201]:
                                refund_data = refund_resp.json()
                                refund_id = refund_data.get("id")
                                refund_status = "refunded" if refund_data.get("status") == "COMPLETED" else "pending"
                                refund_provider = "paypal"
                                logging.info(f"PayPal refund created: {refund_id} for order {order_id}")
                            else:
                                logging.error(f"PayPal refund failed: {refund_resp.text}")
                                refund_status = "failed"
                        else:
                            logging.error(f"No capture ID found for PayPal order {order['paypal_order_id']}")
                            refund_status = "manual_required"
                    else:
                        logging.error(f"Failed to get PayPal order: {order_resp.text}")
                        refund_status = "manual_required"
                        
            except Exception as e:
                logging.error(f"PayPal refund error: {e}")
                refund_status = "failed"
        
        # Stripe Refund
        elif order.get("stripe_session_id") and STRIPE_API_KEY:
            try:
                import stripe
                stripe.api_key = STRIPE_API_KEY
                
                session = stripe.checkout.Session.retrieve(order["stripe_session_id"])
                if session.payment_intent:
                    refund = stripe.Refund.create(
                        payment_intent=session.payment_intent,
                        amount=int(refund_amount * 100),
                        reason="requested_by_customer",
                    )
                    refund_id = refund.id
                    refund_status = "refunded" if refund.status == "succeeded" else "pending"
                    refund_provider = "stripe"
                    logging.info(f"Stripe refund created: {refund.id} for order {order_id}")
            except Exception as e:
                logging.error(f"Stripe refund failed: {e}")
                refund_status = "failed"
        
        # Other payment methods - mark for manual refund
        else:
            refund_status = "manual_required"
            logging.info(f"Manual refund required for order {order_id} (payment method: {payment_method})")
    
    # Update order
    cancellation_reason = data.get("reason", "admin_cancelled")
    await db.orders.update_one(
        {"id": order_id},
        {
            "$set": {
                "order_status": "cancelled",
                "payment_status": "refunded" if refund_status == "refunded" else order.get("payment_status"),
                "cancelled_at": datetime.now(timezone.utc).isoformat(),
                "cancellation_reason": cancellation_reason,
                "refund_status": refund_status,
                "refund_amount": refund_amount,
                "refund_id": refund_id,
                "refund_provider": refund_provider,
                "cancelled_by": "admin",
            }
        }
    )
    
    # Send cancellation notification email to customer
    customer_email = order.get("customer_email") or order.get("shipping_address", {}).get("email")
    if customer_email:
        # Update order with new status for email
        updated_order = {**order, "order_status": "cancelled"}
        asyncio.create_task(send_order_cancellation_email(updated_order, customer_email, refund_amount))
        logging.info(f"Order cancellation email queued for: {customer_email}")
    
    refund_message = ""
    if refund_status == "refunded":
        refund_message = f"Refund of ${refund_amount:.2f} processed via {refund_provider}"
    elif refund_status == "pending":
        refund_message = f"Refund of ${refund_amount:.2f} is pending via {refund_provider}"
    elif refund_status == "manual_required":
        refund_message = f"Manual refund of ${refund_amount:.2f} required"
    elif refund_status == "failed":
        refund_message = f"Automatic refund failed. Manual refund of ${refund_amount:.2f} required"
    
    return {
        "message": "Order cancelled successfully",
        "refund_amount": refund_amount,
        "refund_status": refund_status,
        "refund_provider": refund_provider,
        "refund_id": refund_id,
        "refund_message": refund_message,
        "notification_sent": bool(customer_email),
    }


@router.delete("/admin/orders/{order_id}")
async def delete_order(order_id: str, request: Request):
    """Admin endpoint to permanently remove an order from the database"""
    await require_admin(request)
    
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Delete the order
    result = await db.orders.delete_one({"id": order_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=500, detail="Failed to delete order")
    
    return {"message": "Order removed successfully"}


@router.post("/admin/courier/message")
async def send_courier_message(message_data: dict, request: Request):
    """Store courier communication for an order"""
    await require_admin(request)

    courier_message = {
        "id": str(uuid.uuid4()),
        "order_id": message_data.get("order_id"),
        "courier": message_data.get("courier"),
        "subject": message_data.get("subject"),
        "message": message_data.get("message"),
        "tracking_number": message_data.get("tracking_number"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.courier_messages.insert_one(courier_message)

    return {"message": "Courier communication logged", "id": courier_message["id"]}


@router.get("/admin/courier/messages")
async def get_courier_messages(request: Request, order_id: Optional[str] = None):
    """Get courier communication history"""
    await require_admin(request)
    query = {}
    if order_id:
        query["order_id"] = order_id
    messages = (
        await db.courier_messages.find(query, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )
    return messages


# ============= ADMIN EMAIL MANAGEMENT =============


@router.post("/admin/orders/{order_id}/send-confirmation")
async def admin_send_order_confirmation(order_id: str, request: Request):
    """Admin endpoint to send/resend order confirmation email"""
    await require_admin(request)

    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Get customer email
    customer_email = order.get("shipping_address", {}).get("email")
    if not customer_email and order.get("user_id"):
        user = await db.users.find_one({"id": order["user_id"]}, {"_id": 0})
        customer_email = user.get("email") if user else None

    if not customer_email:
        raise HTTPException(
            status_code=400, detail="No customer email found for this order"
        )

    success = await send_order_confirmation_email(order, customer_email)

    if success:
        return {"message": f"Order confirmation email sent to {customer_email}"}
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to send email. Check if Resend API key is configured.",
        )


@router.post("/admin/orders/{order_id}/send-shipping-update")
async def admin_send_shipping_update(order_id: str, request: Request):
    """Admin endpoint to send/resend shipping update email"""
    await require_admin(request)

    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    tracking_status = order.get("tracking_status", "pending")
    if tracking_status == "pending":
        raise HTTPException(
            status_code=400,
            detail="Order has no tracking status set. Update tracking first.",
        )

    # Get customer email
    customer_email = order.get("shipping_address", {}).get("email")
    if not customer_email and order.get("user_id"):
        user = await db.users.find_one({"id": order["user_id"]}, {"_id": 0})
        customer_email = user.get("email") if user else None

    if not customer_email:
        raise HTTPException(
            status_code=400, detail="No customer email found for this order"
        )

    success = await send_shipping_update_email(order, customer_email, tracking_status)

    if success:
        return {
            "message": f"Shipping update email ({tracking_status}) sent to {customer_email}"
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to send email. Check if Resend API key is configured.",
        )


@router.post("/admin/orders/{order_id}/create-shipment")
async def admin_create_shipment(order_id: str, request: Request):
    """Admin endpoint to manually create shipping label via FlagShip"""
    await require_admin(request)
    
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check if already shipped
    if order.get("tracking_number"):
        return {
            "success": True,
            "message": "Order already has tracking number",
            "tracking_number": order.get("tracking_number"),
            "shipping_label_url": order.get("shipping_label_url")
        }
    
    # Validate shipping address before creating label
    shipping_addr = order.get("shipping_address", {})
    missing_fields = []
    if not shipping_addr.get('first_name'):
        missing_fields.append('first_name')
    if not (shipping_addr.get('address_line1') or shipping_addr.get('address')):
        missing_fields.append('address')
    if not shipping_addr.get('city'):
        missing_fields.append('city')
    if not shipping_addr.get('postal_code'):
        missing_fields.append('postal_code')
    if not (shipping_addr.get('province') or shipping_addr.get('state')):
        missing_fields.append('province')
    
    if missing_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot create shipping label - missing address fields: {', '.join(missing_fields)}"
        )
    
    # Create shipment via FlagShip
    logging.info(f"[Admin] Creating shipment for order {order_id}")
    
    try:
        shipment_result = await auto_create_shipment(order)
        
        if not shipment_result:
            raise HTTPException(
                status_code=500, 
                detail="Failed to create shipping label. Check FlagShip credentials and order details."
            )
        
        # Update order with shipping info
        await db.orders.update_one(
            {"id": order_id},
            {"$set": {
                "tracking_number": shipment_result["tracking_number"],
                "tracking_url": shipment_result.get("tracking_url", ""),
                "shipment_id": shipment_result["shipment_id"],
                "shipping_carrier": shipment_result["courier_name"],
                "shipping_label_url": shipment_result["label_url"],
                "shipping_cost_actual": shipment_result["total_cost"],
                "order_status": "shipped",
                "shipped_at": datetime.now(timezone.utc).isoformat(),
                "shipping_note": None  # Clear any previous error note
            }}
        )
        
        logging.info(f"[Admin] Shipment created for order {order_id}: {shipment_result['tracking_number']}")
        
        # Send shipping notifications via Email, SMS, and WhatsApp
        tracking_url = shipment_result.get("tracking_url") or f"https://www.google.com/search?q={shipment_result['tracking_number']}+tracking"
        notification_results = await send_shipping_notifications(
            order=order,
            tracking_number=shipment_result["tracking_number"],
            courier=shipment_result["courier_name"],
            tracking_url=tracking_url
        )
        
        return {
            "success": True,
            "tracking_number": shipment_result["tracking_number"],
            "shipping_label_url": shipment_result["label_url"],
            "courier": shipment_result["courier_name"],
            "message": f"Shipping label created! Tracking: {shipment_result['tracking_number']}",
            "notifications": notification_results
        }
        
    except Exception as e:
        logging.error(f"[Admin] Failed to create shipment for order {order_id}: {e}")
        
        # Update order with error note
        await db.orders.update_one(
            {"id": order_id},
            {"$set": {"shipping_note": f"Manual shipping failed: {str(e)}"}}
        )
        
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/email-settings")
async def get_email_settings(request: Request):
    """Get email notification settings"""
    await require_admin(request)

    settings = await db.email_settings.find_one({}, {"_id": 0})
    if not settings:
        settings = {
            "order_confirmation_enabled": True,
            "shipping_updates_enabled": True,
            "delivery_confirmation_enabled": True,
            "sender_email": SENDER_EMAIL,
            "api_key_configured": bool(RESEND_API_KEY),
        }

    settings["api_key_configured"] = bool(RESEND_API_KEY)
    return settings


@router.put("/admin/email-settings")
async def update_email_settings(settings_data: dict, request: Request):
    """Update email notification settings"""
    await require_admin(request)

    update_fields = {
        "order_confirmation_enabled": settings_data.get(
            "order_confirmation_enabled", True
        ),
        "shipping_updates_enabled": settings_data.get("shipping_updates_enabled", True),
        "delivery_confirmation_enabled": settings_data.get(
            "delivery_confirmation_enabled", True
        ),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.email_settings.update_one({}, {"$set": update_fields}, upsert=True)

    return {"message": "Email settings updated"}


@router.get("/admin/reviews")
async def get_all_reviews(request: Request, approved: Optional[bool] = None):
    await require_admin(request)
    query = {}
    if approved is not None:
        query["is_approved"] = approved
    reviews = (
        await db.reviews.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    )
    return reviews


@router.post("/admin/reviews/send-digest")
async def trigger_review_digest(request: Request):
    """Manually trigger the daily review digest email"""
    await require_admin(request)

    # Check pending count
    pending_count = await db.review_digest_queue.count_documents({"sent": False})

    if pending_count == 0:
        return {"message": "No pending reviews in digest queue", "count": 0}

    success = await send_daily_review_digest()

    if success:
        return {
            "message": f"Digest sent successfully with {pending_count} reviews",
            "count": pending_count,
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to send digest")


@router.get("/admin/reviews/digest-queue")
async def get_digest_queue(request: Request):
    """Get pending reviews in the digest queue"""
    await require_admin(request)

    pending = await db.review_digest_queue.find({"sent": False}, {"_id": 0}).to_list(
        100
    )
    sent = await db.review_digest_queue.count_documents({"sent": True})

    return {
        "pending_count": len(pending),
        "sent_count": sent,
        "pending_reviews": pending,
    }


@router.put("/admin/reviews/{review_id}/approve")
async def approve_review(review_id: str, request: Request):
    await require_admin(request)

    # Get the review first (before updating)
    review = await db.reviews.find_one({"id": review_id}, {"_id": 0})
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Check if already approved (to avoid duplicate emails)
    was_already_approved = review.get("is_approved", False)

    # Approve the review
    await db.reviews.update_one({"id": review_id}, {"$set": {"is_approved": True}})

    # Update product rating
    pipeline = [
        {"$match": {"product_id": review["product_id"], "is_approved": True}},
        {
            "$group": {
                "_id": None,
                "avg_rating": {"$avg": "$rating"},
                "count": {"$sum": 1},
            }
        },
    ]
    result = await db.reviews.aggregate(pipeline).to_list(1)
    if result:
        await db.products.update_one(
            {"id": review["product_id"]},
            {
                "$set": {
                    "average_rating": round(result[0]["avg_rating"], 1),
                    "review_count": result[0]["count"],
                }
            },
        )

    # Send thank you email if not already approved
    if not was_already_approved:
        try:
            # Get customer info from user_id
            user = await db.users.find_one({"id": review.get("user_id")}, {"_id": 0})
            if user and user.get("email"):
                # Get product name
                product = await db.products.find_one(
                    {"id": review.get("product_id")}, {"_id": 0, "name": 1}
                )
                product_name = (
                    product.get("name", "your product") if product else "your product"
                )
                customer_name = (
                    f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                    or review.get("user_name", "")
                )

                # Fire and forget - don't wait for email
                asyncio.create_task(
                    send_review_thank_you_email(
                        review, product_name, user.get("email"), customer_name
                    )
                )
        except Exception as e:
            logging.error(f"Failed to queue thank you email: {e}")

    return {"message": "Review approved"}


@router.delete("/admin/reviews/{review_id}")
async def delete_review(review_id: str, request: Request):
    await require_admin(request)
    await db.reviews.delete_one({"id": review_id})
    return {"message": "Review deleted"}


