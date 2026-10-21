"""
Product CRUD + variants + inventory
Extracted from server.py during modularization.
"""

import os
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
try:
    from models.server_models import Product
except ImportError:
    pass
try:
    pass  # No email templates needed
except ImportError:
    pass

logger = logging.getLogger(__name__)
def check_permission(*args, **kwargs): return True  # Stub
async def invalidate_cache(*args, **kwargs): pass  # Stub
async def get_cached(*args, **kwargs): return None  # Stub
async def validate_whatsapp_number(*args, **kwargs): return True  # Stub
ws_manager = None  # WebSocket manager stub
async def process_payment_webhook_internally(*args, **kwargs): pass  # Stub
async def send_discord_notification(*args, **kwargs): pass  # Stub
def calculate_order_tax(*args, **kwargs): return 0  # Stub
async def unlock_milestone_discount(*args, **kwargs): return {}  # Stub
async def set_cached(*args, **kwargs): pass  # Cache stub
def get_claude_api_key():
    return os.environ.get('EMERGENT_LLM_KEY', '')

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

# ============= PRODUCT ROUTES =============


@router.get("/products")
@limiter.limit("120/minute")
async def get_products(
    request: Request,
    category: Optional[str] = None,
    featured: Optional[bool] = None,
    search: Optional[str] = None,
    brand: Optional[str] = None,
    limit: int = 50,
):
    # Check if database is initialized
    if db is None:
        raise HTTPException(status_code=503, detail="Service starting up, please retry")
    
    # Get brand from query param, or from middleware state, or default to reroots
    active_brand = brand or getattr(request.state, 'brand', 'reroots')
    
    # Check cache for common requests (no search, default limit)
    cache_key = f"products_{category or 'all'}_{featured}_{active_brand}_{limit}"
    if not search:  # Only cache non-search requests
        cached = get_cached(cache_key)
        if cached:
            return cached
    
    query = {"is_active": True}
    
    # Brand filtering
    if active_brand == "lavela":
        # For La Vela, only return products marked for teen/lavela brand
        # Products should have a "brand" field set to "lavela" or be in lavela categories
        query["$or"] = [
            {"brand": "lavela"},
            {"category_id": {"$in": ["teen-skincare", "gentle", "acne", "lavela"]}},
            {"tags": {"$in": ["lavela", "teen", "pediatric-safe"]}}
        ]
    elif active_brand == "reroots":
        # For ReRoots, return all products EXCEPT those explicitly marked as La Vela
        query["brand"] = {"$ne": "lavela"}
    # If brand is "all" or not specified explicitly, return all products (for admin views)
    
    if category:
        query["category_id"] = category
    if featured is not None:
        query["is_featured"] = featured
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]

    products = await db.products.find(query, {"_id": 0}).to_list(limit)
    
    # Cache the result if not a search
    if not search:
        set_cached(cache_key, products)
    
    return products


# Google Merchant Center Product Feed (XML format)
@router.get("/products/feed.xml")
async def get_product_feed_xml():
    """Generate Google Merchant Center compatible product feed in XML format"""

    products = await db.products.find({"is_active": True}, {"_id": 0}).to_list(100)

    # Build XML feed
    xml_items = []
    for product in products:
        price = product.get("price", 0)
        sale_price = (
            price * (1 - product.get("discount_percent", 0) / 100)
            if product.get("discount_percent")
            else None
        )
        availability = (
            "in_stock"
            if product.get("stock", 0) > 0
            else ("preorder" if product.get("allow_preorder") else "out_of_stock")
        )
        image_url = product.get("images", [""])[0] if product.get("images") else ""

        item_xml = f"""
    <item>
      <g:id>{product.get("id", "")}</g:id>
      <g:title><![CDATA[{product.get("name", "")}]]></g:title>
      <g:description><![CDATA[{product.get("short_description", product.get("description", ""))[:5000]}]]></g:description>
      <g:link>https://www.reroots.ca/products/{product.get("slug", product.get("id", ""))}</g:link>
      <g:image_link>{image_url}</g:image_link>
      <g:availability>{availability}</g:availability>
      <g:price>{price:.2f} CAD</g:price>
      {"<g:sale_price>" + f"{sale_price:.2f} CAD</g:sale_price>" if sale_price and sale_price < price else ""}
      <g:brand>ReRoots</g:brand>
      <g:condition>new</g:condition>
      <g:google_product_category>Health &amp; Beauty &gt; Personal Care &gt; Cosmetics &gt; Skin Care</g:google_product_category>
      <g:product_type>Skincare &gt; Serums</g:product_type>
      <g:identifier_exists>false</g:identifier_exists>
      <g:shipping>
        <g:country>CA</g:country>
        <g:service>Standard</g:service>
        <g:price>0 CAD</g:price>
      </g:shipping>
    </item>"""
        xml_items.append(item_xml)

    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
  <channel>
    <title>ReRoots Skincare Products</title>
    <link>https://www.reroots.ca</link>
    <description>Premium Canadian Biotech Skincare - PDRN Technology</description>
    {"".join(xml_items)}
  </channel>
</rss>"""

    return Response(content=xml_content, media_type="application/xml")


# Google Merchant Center Product Feed (JSON format - alternative)
@router.get("/products/feed.json")
async def get_product_feed_json():
    """Generate Google Merchant Center compatible product feed in JSON format"""
    products = await db.products.find({"is_active": True}, {"_id": 0}).to_list(100)

    feed_items = []
    for product in products:
        price = product.get("price", 0)
        sale_price = (
            price * (1 - product.get("discount_percent", 0) / 100)
            if product.get("discount_percent")
            else None
        )
        availability = (
            "in_stock"
            if product.get("stock", 0) > 0
            else ("preorder" if product.get("allow_preorder") else "out_of_stock")
        )

        feed_items.append(
            {
                "id": product.get("id", ""),
                "title": product.get("name", ""),
                "description": product.get(
                    "short_description", product.get("description", "")
                )[:5000],
                "link": f"https://www.reroots.ca/products/{product.get('slug', product.get('id', ''))}",
                "image_link": (
                    product.get("images", [""])[0] if product.get("images") else ""
                ),
                "availability": availability,
                "price": f"{price:.2f} CAD",
                "sale_price": (
                    f"{sale_price:.2f} CAD"
                    if sale_price and sale_price < price
                    else None
                ),
                "brand": "ReRoots",
                "condition": "new",
                "google_product_category": "Health & Beauty > Personal Care > Cosmetics > Skin Care",
                "product_type": "Skincare > Serums",
                "shipping": {"country": "CA", "service": "Standard", "price": "0 CAD"},
            }
        )

    return {"products": feed_items, "count": len(feed_items)}


@router.get("/products/{product_id}")
async def get_product(product_id: str):
    product = await db.products.find_one(
        {"$or": [{"id": product_id}, {"slug": product_id}]}, {"_id": 0}
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/products/{product_id}/ai-info")
async def get_product_ai_info(product_id: str):
    """
    Returns product information in a format optimized for AI crawlers.
    Plain text with structured data for LLMs to understand.
    """
    product = await db.products.find_one(
        {"$or": [{"id": product_id}, {"slug": product_id}]}, {"_id": 0}
    )
    if not product:
        raise HTTPException(status_code=404