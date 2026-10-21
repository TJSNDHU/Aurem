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