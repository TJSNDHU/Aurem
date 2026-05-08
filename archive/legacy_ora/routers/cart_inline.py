"""
Cart operations + shipping calculator
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
    from models.server_models import (
        CartItem, Cart, ComboCartRequest, ShippingCalculatorRequest, ShippingRate,
        CheckoutRequest, OrderCreate, OrderItem, Order, PaymentTransaction,
        SUPPORTED_CURRENCIES, COUNTRY_TO_CURRENCY
    )
except ImportError:
    pass
try:
    from services.email_templates import (
        get_email_base_styles, generate_order_confirmation_email,
        generate_shipping_update_email, generate_order_cancellation_email
    )
except ImportError:
    pass

logger = logging.getLogger(__name__)

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

# ============= CART ROUTES =============


@router.get("/cart/{session_id}")
async def get_cart(session_id: str):
    cart = await db.carts.find_one({"session_id": session_id}, {"_id": 0})
    if not cart:
        new_cart = Cart(session_id=session_id)
        cart_dict = new_cart.model_dump()
        cart_dict["updated_at"] = cart_dict["updated_at"].isoformat()
        await db.carts.insert_one(cart_dict)
        # Return the cart without _id
        cart = await db.carts.find_one({"session_id": session_id}, {"_id": 0})

    # Populate product details - batch fetch to avoid N+1 queries
    # Support both UUID and slug lookups
    items = cart.get("items", [])
    if items:
        product_ids = [item["product_id"] for item in items]
        
        # Query from main products collection
        products_list = await db.products.find(
            {"$or": [{"id": {"$in": product_ids}}, {"slug": {"$in": product_ids}}]},
            {"_id": 0},
        ).to_list(len(product_ids) * 2)
        
        # Also query from lavela_products collection (supports both id field and _id ObjectId)
        from bson import ObjectId
        lavela_query = {"$or": [{"id": {"$in": product_ids}}, {"slug": {"$in": product_ids}}]}
        # Add ObjectId queries for product IDs that look like ObjectIds
        oid_list = []
        for pid in product_ids:
            try:
                oid_list.append(ObjectId(pid))
            except:
                pass
        if oid_list:
            lavela_query["$or"].append({"_id": {"$in": oid_list}})
        
        lavela_products_raw = await db.lavela_products.find(lavela_query).to_list(len(product_ids) * 2)
        
        # Convert lavela products to have consistent id field
        lavela_products_list = []
        for p in lavela_products_raw:
            product_dict = {k: v for k, v in p.items() if k != "_id"}
            product_dict["id"] = str(p.get("_id")) if not p.get("id") else p.get("id")
            # Map price fields for consistency
            if "price_cad" in product_dict and "price" not in product_dict:
                product_dict["price"] = product_dict["price_cad"]
            lavela_products_list.append(product_dict)
        
        # Combine both lists
        all_products = products_list + lavela_products_list

        # Build dict mapping both id and slug to product
        products_dict = {}
        for p in all_products:
            products_dict[p.get("id", "")] = p
            if p.get("slug"):
                products_dict[p["slug"]] = p

        items_with_details = []
        for item in items:
            # Handle combo items differently - they already have products array
            if item.get("item_type") == "combo":
                # Combo items already have products embedded, just pass through
                items_with_details.append(item)
            else:
                # Regular product item - lookup product details
                product = products_dict.get(item["product_id"])
                if product:
                    items_with_details.append({**item, "product": product})
        cart["items"] = items_with_details
    return cart


@router.post("/cart/{session_id}/add")
async def add_to_cart(session_id: str, item: CartItem):
    # Resolve product_id - support both UUID and slug
    # First check main products collection
    product = await db.products.find_one(
        {"$or": [{"id": item.product_id}, {"slug": item.product_id}]},
        {"_id": 0, "id": 1},
    )
    
    # If not found in products, check lavela_products collection
    # Note: lavela_products may use _id as ObjectId instead of id field
    if not product:
        from bson import ObjectId
        lavela_query = {"$or": [{"id": item.product_id}, {"slug": item.product_id}]}
        # Also try to match by _id if the product_id looks like an ObjectId
        try:
            lavela_query["$or"].append({"_id": ObjectId(item.product_id)})
        except:
            pass
        
        lavela_product = await db.lavela_products.find_one(lavela_query)
        if lavela_product:
            # Convert _id to id for consistency
            product = {"id": str(lavela_product.get("_id", lavela_product.get("id", item.product_id)))}
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    actual_product_id = product["id"]

    cart = await db.carts.find_one({"session_id": session_id})

    if not cart:
        cart = Cart(session_id=session_id).model_dump()
        cart["updated_at"] = cart["updated_at"].isoformat()
        await db.carts.insert_one(cart)

    items = cart.get("items", [])
    existing_item = next(
        (i for i in items if i["product_id"] == actual_product_id), None
    )

    if existing_item:
        existing_item["quantity"] += item.quantity
    else:
        items.append({"product_id": actual_product_id, "quantity": item.quantity})

    await db.carts.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "items": items,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return await get_cart(session_id)


@router.post("/cart/{session_id}/add-combo")
async def add_combo_to_cart(session_id: str, request: ComboCartRequest):
    """Add a combo to cart with its discounted price"""
    
    # Fetch the combo details - the frontend passes the _id converted to string as "id"
    combo = None
    try:
        # First try as ObjectId (this is the most common case since API returns _id as id)
        combo = await db.combo_offers.find_one({"_id": ObjectId(request.combo_id)})
    except Exception:
        logging.info(f"Not a valid ObjectId: {request.combo_id}, trying as string id")
    
    if not combo:
        # Try with the "id" field as fallback
        combo = await db.combo_offers.find_one({"id": request.combo_id})
    
    if not combo:
        raise HTTPException(status_code=404, detail=f"Combo not found: {request.combo_id}")
    
    # Get combo price - recalculate dynamically based on products
    product_ids = combo.get("product_ids", [])
    
    if not product_ids:
        raise HTTPException(status_code=400, detail="Combo has no products")
    
    # Calculate per-product price (proportional to original prices)
    products = []
    total_original = 0
    for pid in product_ids:
        # Try both id formats for products
        product = await db.products.find_one({"id": pid}, {"_id": 0})
        if not product:
            try:
                product = await db.products.find_one({"_id": ObjectId(pid)}, {"_id": 0})
                if product:
                    product["id"] = pid
            except:
                pass
        if product:
            products.append(product)
            total_original += product.get("compare_price") or product.get("price", 0)
    
    # Use the exact combo_price from database - DO NOT recalculate!
    combo_price = combo.get("combo_price") or combo.get("fixed_price")
    if combo_price:
        combo_price = round(float(combo_price), 2)
    else:
        # Fallback only if no stored price in database
        discount_percent = combo.get("discount_percent", 15) / 100
        combo_price = round(total_original * (1 - discount_percent), 2)
    
    combo_name = combo.get("name", "Combo Deal")
    combo_id_str = str(combo.get("_id", request.combo_id))
    discount_percent = combo.get("discount_percent", 0)
    
    # Ensure cart exists
    cart = await db.carts.find_one({"session_id": session_id})
    if not cart:
        cart = Cart(session_id=session_id).model_dump()
        cart["updated_at"] = cart["updated_at"].isoformat()
        await db.carts.insert_one(cart)
    
    items = cart.get("items", [])
    
    # CORRECT LOGIC: Add combo as ONE line item, not separate products
    # Check if this combo already exists in cart
    existing_combo = None
    for i in items:
        if i.get("item_type") == "combo" and i.get("combo_id") == combo_id_str:
            existing_combo = i
            break
    
    if existing_combo:
        # Increment quantity of existing combo
        existing_combo["quantity"] += request.quantity
    else:
        # Add combo as single line item
        combo_item = {
            "item_type": "combo",
            "combo_id": combo_id_str,
            "combo_name": combo_name,
            "product_ids": [p.get("id") for p in products],
            "products": products,  # Full product details for display
            "price": combo_price,  # Total combo price
            "original_price": round(total_original, 2),  # Sum of individual prices
            "discount_percent": discount_percent,
            "quantity": request.quantity,
            "product_id": f"combo-{combo_id_str}"  # Unique ID for cart operations
        }
        items.append(combo_item)
    
    await db.carts.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "items": items,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    
    return await get_cart(session_id)


@router.put("/cart/{session_id}/update")
async def update_cart_item(session_id: str, item: CartItem):
    cart = await db.carts.find_one({"session_id": session_id})
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    items = cart.get("items", [])
    for i in items:
        if i["product_id"] == item.product_id:
            if item.quantity <= 0:
                items.remove(i)
            else:
                i["quantity"] = item.quantity
            break

    await db.carts.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "items": items,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return await get_cart(session_id)


@router.delete("/cart/{session_id}/item/{product_id}")
async def remove_from_cart(session_id: str, product_id: str):
    await db.carts.update_one(
        {"session_id": session_id},
        {
            "$pull": {"items": {"product_id": product_id}},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
        },
    )
    return await get_cart(session_id)


@router.delete("/cart/{session_id}")
async def clear_cart(session_id: str):
    await db.carts.update_one(
        {"session_id": session_id},
        {"$set": {"items": [], "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"message": "Cart cleared"}


# ============= SHIPPING CALCULATOR =============


def calculate_shipping_rates(
    weight_grams: int, province: str, subtotal: float = 0
) -> List[dict]:
    """Calculate shipping rates based on weight and destination"""
    rates = []

    # Free shipping threshold
    free_threshold = 75.0

    # Base rates (in CAD)
    if province in ["ON", "QC"]:
        base_standard = 8.0
        base_express = 15.0
        base_priority = 25.0
    elif province in ["BC", "AB", "MB", "SK"]:
        base_standard = 12.0
        base_express = 20.0
        base_priority = 35.0
    else:  # Atlantic provinces, territories
        base_standard = 15.0
        base_express = 25.0
        base_priority = 40.0

    # Weight surcharge (per 500g over 500g)
    weight_surcharge = max(0, (weight_grams - 500) // 500) * 2

    standard_price = base_standard + weight_surcharge
    express_price = base_express + weight_surcharge
    priority_price = base_priority + weight_surcharge

    # Apply free shipping if threshold met
    if subtotal >= free_threshold:
        standard_price = 0

    rates.append(
        {
            "method": "standard",
            "name": "Standard Shipping",
            "description": "Canada Post Regular Parcel",
            "price": round(standard_price, 2),
            "estimated_days": "5-8 business days",
            "is_free": subtotal >= free_threshold,
        }
    )

    rates.append(
        {
            "method": "express",
            "name": "Express Shipping",
            "description": "Canada Post Xpresspost",
            "price": round(express_price, 2),
            "estimated_days": "2-3 business days",
            "is_free": False,
        }
    )

    rates.append(
        {
            "method": "priority",
            "name": "Priority Shipping",
            "description": "Canada Post Priority - Next Day",
            "price": round(priority_price, 2),
            "estimated_days": "1-2 business days",
            "is_free": False,
        }
    )

    return rates


# ============= INTERNATIONAL TAX & DUTY CALCULATOR (LANDED COST) =============

# Comprehensive international tax rates and duty rates for skincare (HS Code 3304.99)
INTERNATIONAL_TAX_RATES = {
    # North America
    "CA": {
        "vat": 0.0,
        "gst": 0.05,
        "duty": 0.0,
        "name": "Canada",
        "currency": "CAD",
        "de_minimis": 20,
    },
    "US": {
        "vat": 0.0,
        "sales_tax": 0.07,
        "duty": 0.0,
        "name": "United States",
        "currency": "USD",
        "de_minimis": 800,
    },
    "MX": {
        "vat": 0.16,
        "duty": 0.10,
        "name": "Mexico",
        "currency": "MXN",
        "de_minimis": 50,
    },
    # Europe (EU)
    "GB": {
        "vat": 0.20,
        "duty": 0.065,
        "name": "United Kingdom",
        "currency": "GBP",
        "de_minimis": 135,
    },
    "DE": {
        "vat": 0.19,
        "duty": 0.065,
        "name": "Germany",
        "currency": "EUR",
        "de_minimis": 150,
    },
    "FR": {
        "vat": 0.20,
        "duty": 0.065,
        "name": "France",
        "currency": "EUR",
        "de_minimis": 150,
    },
    "IT": {
        "vat": 0.22,
        "duty": 0.065,
        "name": "Italy",
        "currency": "EUR",
        "de_minimis": 150,
    },
    "ES": {
        "vat": 0.21,
        "duty": 0.065,
        "name": "Spain",
        "currency": "EUR",
        "de_minimis": 150,
    },
    "NL": {
        "vat": 0.21,
        "duty": 0.065,
        "name": "Netherlands",
        "currency": "EUR",
        "de_minimis": 150,
    },
    "BE": {
        "vat": 0.21,
        "duty": 0.065,
        "name": "Belgium",
        "currency": "EUR",
        "de_minimis": 150,
    },
    "AT": {
        "vat": 0.20,
        "duty": 0.065,
        "name": "Austria",
        "currency": "EUR",
        "de_minimis": 150,
    },
    "PT": {
        "vat": 0.23,
        "duty": 0.065,
        "name": "Portugal",
        "currency": "EUR",
        "de_minimis": 150,
    },
    "IE": {
        "vat": 0.23,
        "duty": 0.065,
        "name": "Ireland",
        "currency": "EUR",
        "de_minimis": 150,
    },
    "SE": {
        "vat": 0.25,
        "duty": 0.065,
        "name": "Sweden",
        "currency": "SEK",
        "de_minimis": 150,
    },
    "DK": {
        "vat": 0.25,
        "duty": 0.065,
        "name": "Denmark",
        "currency": "DKK",
        "de_minimis": 150,
    },
    "FI": {
        "vat": 0.24,
        "duty": 0.065,
        "name": "Finland",
        "currency": "EUR",
        "de_minimis": 150,
    },
    "NO": {
        "vat": 0.25,
        "duty": 0.08,
        "name": "Norway",
        "currency": "NOK",
        "de_minimis": 350,
    },
    "CH": {
        "vat": 0.077,
        "duty": 0.0,
        "name": "Switzerland",
        "currency": "CHF",
        "de_minimis": 65,
    },
    "PL": {
        "vat": 0.23,
        "duty": 0.065,
        "name": "Poland",
        "currency": "PLN",
        "de_minimis": 150,
    },
    # Asia Pacific
    "AU": {
        "vat": 0.10,
        "duty": 0.05,
        "name": "Australia",
        "currency": "AUD",
        "de_minimis": 1000,
    },
    "NZ": {
        "vat": 0.15,
        "duty": 0.05,
        "name": "New Zealand",
        "currency": "NZD",
        "de_minimis": 1000,
    },
    "JP": {
        "vat": 0.10,
        "duty": 0.0,
        "name": "Japan",
        "currency": "JPY",
        "de_minimis": 10000,
    },
    "KR": {
        "vat": 0.10,
        "duty": 0.08,
        "name": "South Korea",
        "currency": "KRW",
        "de_minimis": 150,
    },
    "CN": {
        "vat": 0.13,
        "duty": 0.085,
        "name": "China",
        "currency": "CNY",
        "de_minimis": 50,
    },
    "HK": {
        "vat": 0.0,
        "duty": 0.0,
        "name": "Hong Kong",
        "currency": "HKD",
        "de_minimis": 0,
    },
    "SG": {
        "vat": 0.08,
        "duty": 0.0,
        "name": "Singapore",
        "currency": "SGD",
        "de_minimis": 400,
    },
    "MY": {
        "vat": 0.06,
        "duty": 0.05,
        "name": "Malaysia",
        "currency": "MYR",
        "de_minimis": 500,
    },
    "TH": {
        "vat": 0.07,
        "duty": 0.20,
        "name": "Thailand",
        "currency": "THB",
        "de_minimis": 1500,
    },
    "IN": {
        "vat": 0.18,
        "duty": 0.28,
        "name": "India",
        "currency": "INR",
        "de_minimis": 0,
    },
    "PH": {
        "vat": 0.12,
        "duty": 0.10,
        "name": "Philippines",
        "currency": "PHP",
        "de_minimis": 10000,
    },
    "ID": {
        "vat": 0.11,
        "duty": 0.15,
        "name": "Indonesia",
        "currency": "IDR",
        "de_minimis": 75,
    },
    "VN": {
        "vat": 0.10,
        "duty": 0.20,
        "name": "Vietnam",
        "currency": "VND",
        "de_minimis": 1000000,
    },
    "TW": {
        "vat": 0.05,
        "duty": 0.05,
        "name": "Taiwan",
        "currency": "TWD",
        "de_minimis": 3000,
    },
    # Middle East
    "AE": {
        "vat": 0.05,
        "duty": 0.05,
        "name": "United Arab Emirates",
        "currency": "AED",
        "de_minimis": 1000,
    },
    "SA": {
        "vat": 0.15,
        "duty": 0.05,
        "name": "Saudi Arabia",
        "currency": "SAR",
        "de_minimis": 1000,
    },
    "IL": {
        "vat": 0.17,
        "duty": 0.12,
        "name": "Israel",
        "currency": "ILS",
        "de_minimis": 75,
    },
    "QA": {
        "vat": 0.0,
        "duty": 0.05,
        "name": "Qatar",
        "currency": "QAR",
        "de_minimis": 3000,
    },
    # South America
    "BR": {
        "vat": 0.17,
        "duty": 0.18,
        "name": "Brazil",
        "currency": "BRL",
        "de_minimis": 50,
    },
    "AR": {
        "vat": 0.21,
        "duty": 0.35,
        "name": "Argentina",
        "currency": "ARS",
        "de_minimis": 50,
    },
    "CL": {
        "vat": 0.19,
        "duty": 0.06,
        "name": "Chile",
        "currency": "CLP",
        "de_minimis": 30,
    },
    "CO": {
        "vat": 0.19,
        "duty": 0.15,
        "name": "Colombia",
        "currency": "COP",
        "de_minimis": 200,
    },
    "PE": {
        "vat": 0.18,
        "duty": 0.06,
        "name": "Peru",
        "currency": "PEN",
        "de_minimis": 200,
    },
    # Africa
    "ZA": {
        "vat": 0.15,
        "duty": 0.20,
        "name": "South Africa",
        "currency": "ZAR",
        "de_minimis": 500,
    },
    "NG": {
        "vat": 0.075,
        "duty": 0.20,
        "name": "Nigeria",
        "currency": "NGN",
        "de_minimis": 50000,
    },
    "EG": {
        "vat": 0.14,
        "duty": 0.30,
        "name": "Egypt",
        "currency": "EGP",
        "de_minimis": 100,
    },
    "KE": {
        "vat": 0.16,
        "duty": 0.25,
        "name": "Kenya",
        "currency": "KES",
        "de_minimis": 500,
    },
}

# Canadian provincial tax rates
CANADIAN_TAX_RATES = {
    "ON": {"gst": 0.05, "pst": 0.08, "hst": 0.13, "name": "Ontario"},
    "BC": {"gst": 0.05, "pst": 0.07, "hst": 0.0, "name": "British Columbia"},
    "AB": {"gst": 0.05, "pst": 0.0, "hst": 0.0, "name": "Alberta"},
    "QC": {"gst": 0.05, "pst": 0.09975, "hst": 0.0, "name": "Quebec"},
    "MB": {"gst": 0.05, "pst": 0.07, "hst": 0.0, "name": "Manitoba"},
    "SK": {"gst": 0.05, "pst": 0.06, "hst": 0.0, "name": "Saskatchewan"},
    "NS": {"gst": 0.0, "pst": 0.0, "hst": 0.15, "name": "Nova Scotia"},
    "NB": {"gst": 0.0, "pst": 0.0, "hst": 0.15, "name": "New Brunswick"},
    "PE": {"gst": 0.0, "pst": 0.0, "hst": 0.15, "name": "Prince Edward Island"},
    "NL": {"gst": 0.0, "pst": 0.0, "hst": 0.15, "name": "Newfoundland"},
    "NT": {"gst": 0.05, "pst": 0.0, "hst": 0.0, "name": "Northwest Territories"},
    "YT": {"gst": 0.05, "pst": 0.0, "hst": 0.0, "name": "Yukon"},
    "NU": {"gst": 0.05, "pst": 0.0, "hst": 0.0, "name": "Nunavut"},
}

# International shipping rates from Canada
INTERNATIONAL_SHIPPING_RATES = {
    "US": {
        "standard": 15.0,
        "express": 35.0,
        "priority": 55.0,
        "days_standard": "5-10",
        "days_express": "3-5",
        "days_priority": "2-3",
    },
    "GB": {
        "standard": 25.0,
        "express": 55.0,
        "priority": 85.0,
        "days_standard": "10-15",
        "days_express": "5-7",
        "days_priority": "3-5",
    },
    "EU": {
        "standard": 25.0,
        "express": 55.0,
        "priority": 85.0,
        "days_standard": "10-15",
        "days_express": "5-7",
        "days_priority": "3-5",
    },
    "AU": {
        "standard": 30.0,
        "express": 65.0,
        "priority": 95.0,
        "days_standard": "12-18",
        "days_express": "6-8",
        "days_priority": "4-6",
    },
    "ASIA": {
        "standard": 28.0,
        "express": 60.0,
        "priority": 90.0,
        "days_standard": "12-20",
        "days_express": "5-8",
        "days_priority": "3-5",
    },
    "LATAM": {
        "standard": 35.0,
        "express": 70.0,
        "priority": 110.0,
        "days_standard": "15-25",
        "days_express": "7-10",
        "days_priority": "4-6",
    },
    "OTHER": {
        "standard": 40.0,
        "express": 80.0,
        "priority": 120.0,
        "days_standard": "15-30",
        "days_express": "7-12",
        "days_priority": "5-7",
    },
}


def get_shipping_region(country_code: str) -> str:
    """Get shipping region for a country"""
    eu_countries = [
        "DE",
        "FR",
        "IT",
        "ES",
        "NL",
        "BE",
        "AT",
        "PT",
        "IE",
        "SE",
        "DK",
        "FI",
        "PL",
        "CZ",
        "GR",
        "HU",
        "RO",
        "BG",
    ]
    asia_countries = [
        "JP",
        "KR",
        "CN",
        "HK",
        "SG",
        "MY",
        "TH",
        "IN",
        "PH",
        "ID",
        "VN",
        "TW",
    ]
    latam_countries = ["MX", "BR", "AR", "CL", "CO", "PE"]

    if country_code == "US":
        return "US"
    elif country_code == "GB":
        return "GB"
    elif country_code in eu_countries:
        return "EU"
    elif country_code in ["AU", "NZ"]:
        return "AU"
    elif country_code in asia_countries:
        return "ASIA"
    elif country_code in latam_countries:
        return "LATAM"
    else:
        return "OTHER"


def calculate_landed_cost(
    subtotal: float,
    country_code: str,
    province: Optional[str] = None,
    weight_grams: int = 200,
    shipping_method: str = "standard",
    currency: str = "CAD",
) -> dict:
    """
    Calculate landed cost including tax, duty, and shipping for international orders.
    Returns all costs in CAD.
    """
    is_canada = country_code == "CA"
    is_international = not is_canada

    # Get tax/duty rates
    if is_canada:
        # Canadian order - use provincial rates
        prov_rates = CANADIAN_TAX_RATES.get(province, CANADIAN_TAX_RATES["ON"])
        if prov_rates["hst"] > 0:
            tax_rate = prov_rates["hst"]
        else:
            tax_rate = prov_rates["gst"] + prov_rates["pst"]
        duty_rate = 0.0
        tax_name = "HST" if prov_rates["hst"] > 0 else "GST/PST"
    else:
        # International order
        country_rates = INTERNATIONAL_TAX_RATES.get(
            country_code,
            {"vat": 0.15, "duty": 0.10, "name": "International", "de_minimis": 0},
        )
        tax_rate = (
            country_rates.get("vat", 0)
            or country_rates.get("sales_tax", 0)
            or country_rates.get("gst", 0)
        )
        duty_rate = country_rates.get("duty", 0.10)
        tax_name = "VAT/GST"

        # Check de minimis threshold (duty-free below threshold)
        de_minimis = country_rates.get("de_minimis", 0)
        if subtotal < de_minimis:
            duty_rate = 0.0

    # Calculate tax and duty
    tax = round(subtotal * tax_rate, 2)
    duty = round(subtotal * duty_rate, 2) if is_international else 0.0

    # Calculate shipping
    if is_canada:
        # Use domestic shipping calculator
        shipping_rates = calculate_shipping_rates(
            weight_grams, province or "ON", subtotal
        )
        selected_rate = next(
            (r for r in shipping_rates if r["method"] == shipping_method),
            shipping_rates[0],
        )
        shipping = selected_rate["price"]
        shipping_days = selected_rate["estimated_days"]
    else:
        # International shipping
        region = get_shipping_region(country_code)
        intl_rates = INTERNATIONAL_SHIPPING_RATES.get(
            region, INTERNATIONAL_SHIPPING_RATES["OTHER"]
        )

        # Weight surcharge for international (per 500g over 500g)
        weight_surcharge = max(0, (weight_grams - 500) // 500) * 5

        if shipping_method == "express":
            shipping = intl_rates["express"] + weight_surcharge
            shipping_days = intl_rates["days_express"]
        elif shipping_method == "priority":
            shipping = intl_rates["priority"] + weight_surcharge
            shipping_days = intl_rates["days_priority"]
        else:
            shipping = intl_rates["standard"] + weight_surcharge
            shipping_days = intl_rates["days_standard"]

    # Calculate landed cost (total)
    landed_cost = round(subtotal + tax + duty + shipping, 2)

    return {
        "subtotal": subtotal,
        "tax": tax,
        "tax_rate": round(tax_rate * 100, 2),
        "tax_name": tax_name,
        "duty": duty,
        "duty_rate": round(duty_rate * 100, 2),
        "shipping": round(shipping, 2),
        "shipping_days": shipping_days,
        "landed_cost": landed_cost,
        "is_international": is_international,
        "country_code": country_code,
        "country_name": INTERNATIONAL_TAX_RATES.get(country_code, {}).get(
            "name", country_code
        ),
        "currency": currency,
        "duty_free": duty == 0 and is_international,
        "breakdown": {
            "product_total": subtotal,
            "estimated_tax": tax,
            "estimated_duty": duty,
            "shipping_cost": round(shipping, 2),
            "total_to_pay": landed_cost,
        },
    }


@router.post("/calculate-landed-cost")
async def api_calculate_landed_cost(data: dict):
    """Calculate landed cost for an order including tax, duty, and shipping"""
    subtotal = data.get("subtotal", 0)
    country_code = data.get("country_code", "CA")
    province = data.get("province", "ON")
    weight_grams = data.get("weight_grams", 200)
    shipping_method = data.get("shipping_method", "standard")

    result = calculate_landed_cost(
        subtotal=subtotal,
        country_code=country_code,
        province=province,
        weight_grams=weight_grams,
        shipping_method=shipping_method,
    )

    return result


@router.get("/international-shipping-info")
async def get_international_shipping_info():
    """Get international shipping information for all supported countries"""
    countries = []
    for code, rates in INTERNATIONAL_TAX_RATES.items():
        region = get_shipping_region(code)
        shipping = INTERNATIONAL_SHIPPING_RATES.get(
            region, INTERNATIONAL_SHIPPING_RATES["OTHER"]
        )
        countries.append(
            {
                "code": code,
                "name": rates["name"],
                "currency": rates.get("currency", "USD"),
                "vat_rate": rates.get("vat", 0) * 100,
                "duty_rate": rates.get("duty", 0) * 100,
                "de_minimis": rates.get("de_minimis", 0),
                "shipping_standard": shipping["standard"],
                "shipping_express": shipping["express"],
                "delivery_days": shipping["days_standard"],
            }
        )

    return {
        "countries": sorted(countries, key=lambda x: x["name"]),
        "shipping_regions": INTERNATIONAL_SHIPPING_RATES,
        "base_currency": "CAD",
    }


@router.post("/shipping/calculate")
async def calculate_shipping(data: ShippingCalculatorRequest):
    rates = calculate_shipping_rates(data.weight_grams, data.province)
    return {"rates": rates, "weight_grams": data.weight_grams}


@router.get("/shipping/calculate-cart/{session_id}")
async def calculate_cart_shipping(session_id: str, province: str = "ON"):
    cart = await db.carts.find_one({"session_id": session_id})
    if not cart or not cart.get("items"):
        return {"rates": [], "total_weight": 0, "subtotal": 0}

    # Batch fetch products to avoid N+1 queries
    items = cart.get("items", [])
    product_ids = [item["product_id"] for item in items]
    products_list = await db.products.find(
        {"id": {"$in": product_ids}}, {"_id": 0}
    ).to_list(len(product_ids))
    products_dict = {p["id"]: p for p in products_list}

    total_weight = 0
    subtotal = 0

    for item in items:
        product = products_dict.get(item["product_id"])
        if product:
            weight = product.get("weight_grams", 200)
            total_weight += weight * item["quantity"]
            subtotal += product["price"] * item["quantity"]

    rates = calculate_shipping_rates(total_weight, province, subtotal)
    return {"rates": rates, "total_weight": total_weight, "subtotal": subtotal}


