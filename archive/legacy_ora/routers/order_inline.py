"""
Order creation, management, loyalty, milestones
Extracted from server.py during modularization.
"""

import os
try:
    import resend
except ImportError:
    resend = None
import random
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
from utils.stubs import (
    calculate_shipping_rates, calculate_landed_cost,
    mark_restock_conversion, verify_referral_for_milestone,
)
try:
    from models.server_models import (
        ACCOUNTANT_PERMISSIONS, EXPENSE_CATEGORIES, Expense, ExpenseCreate,
        LOGIN_MILESTONE, Order, OrderCreate, OrderItem, POINTS_PER_REFERRAL,
        REFERRAL_MILESTONE,
    )
except ImportError:
    pass

logger = logging.getLogger(__name__)
async def validate_whatsapp_number(*args, **kwargs): return True  # Stub
ws_manager = None  # WebSocket manager stub
async def process_payment_webhook_internally(*args, **kwargs): pass  # Stub
async def send_discord_notification(*args, **kwargs): pass  # Stub
def calculate_order_tax(*args, **kwargs): return 0  # Stub
async def unlock_milestone_discount(*args, **kwargs): return {}  # Stub
async def set_cached(*args, **kwargs): pass  # Cache stub
async def send_whatsapp_message(*args, **kwargs): pass  # Stub: WhatsApp not configured

# Loyalty program constants
POINT_VALUE = float(os.environ.get('POINT_VALUE', '0.01'))
POINTS_PER_PRODUCT = int(os.environ.get('POINTS_PER_PRODUCT', '10'))
MILESTONE_REFERRAL_THRESHOLD = int(os.environ.get('MILESTONE_REFERRAL_THRESHOLD', '5'))
MILESTONE_EMAIL_TRIGGER = int(os.environ.get('MILESTONE_EMAIL_TRIGGER', '3'))
MILESTONE_DISCOUNT_PERCENT = float(os.environ.get('MILESTONE_DISCOUNT_PERCENT', '10'))
def get_claude_api_key():
    return os.environ.get('EMERGENT_LLM_KEY', '')
try:
    from services.twilio_service import normalize_phone_number
except ImportError:
    def normalize_phone_number(phone, country_code='1'): return phone
try:
    from middleware.websocket_manager import broadcast_admin_event
except ImportError:
    async def broadcast_admin_event(*args, **kwargs): pass
try:
    from utils.auth_utils import require_auth
except ImportError:
    try:
        from utils.auth import require_auth
    except ImportError:
        require_auth = None

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
twilio_client = None
try:
    from twilio.rest import Client as TwilioClient
    _sid = os.environ.get('TWILIO_ACCOUNT_SID', '')
    _tok = os.environ.get('TWILIO_AUTH_TOKEN', '')
    if _sid and _tok:
        twilio_client = TwilioClient(_sid, _tok)
except ImportError:
    pass


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

# ============= ORDER ROUTES =============


@router.post("/orders")
@limiter.limit("10/minute")
async def create_order(order_data: OrderCreate, request: Request):
    user = await get_current_user(request)
    cart = await db.carts.find_one({"session_id": order_data.session_id})

    if not cart or not cart.get("items"):
        raise HTTPException(status_code=400, detail="Cart is empty")

    # Batch fetch products to avoid N+1 queries
    items = cart["items"]
    product_ids = [item["product_id"] for item in items]
    products_list = await db.products.find(
        {"id": {"$in": product_ids}}, {"_id": 0}
    ).to_list(len(product_ids))
    products_dict = {p["id"]: p for p in products_list}

    # Build order items
    order_items = []
    subtotal = 0.0
    total_weight = 0
    has_preorder = False
    cost_of_goods = 0.0  # Track total cost price

    for item in items:
        product = products_dict.get(item["product_id"])
        if product:
            # Check if pre-order
            is_preorder = product.get("stock", 0) <= 0 and product.get(
                "allow_preorder", False
            )
            if is_preorder:
                has_preorder = True

            # Use ORIGINAL price for calculations (tax, shipping threshold)
            original_price = product["price"]
            item_total = original_price * item["quantity"]
            subtotal += item_total
            total_weight += product.get("weight_grams", 200) * item["quantity"]

            # Calculate cost of goods (your actual cost)
            product_cost = product.get("cost_price", 0) or 0
            cost_of_goods += product_cost * item["quantity"]

            # Calculate effective price for the order item (after product discount)
            product_discount = product.get("discount_percent", 0) or 0
            effective_price = (
                original_price * (1 - product_discount / 100)
                if product_discount > 0
                else original_price
            )

            order_items.append(
                OrderItem(
                    product_id=product["id"],
                    product_name=product["name"],
                    product_image=product["images"][0] if product["images"] else "",
                    quantity=item["quantity"],
                    price=effective_price,  # Store the effective (discounted) price
                    is_preorder=is_preorder,
                )
            )

    # Calculate total product discount (from product.discount_percent)
    product_discount_total = 0.0
    discounted_subtotal_before_coupon = subtotal  # Start with original
    for item in items:
        product = products_dict.get(item["product_id"])
        if product:
            product_discount_pct = product.get("discount_percent", 0) or 0
            if product_discount_pct > 0:
                discount_for_item = (
                    product["price"] * product_discount_pct / 100
                ) * item["quantity"]
                product_discount_total += discount_for_item
                discounted_subtotal_before_coupon -= discount_for_item

    # Apply coupon/offer discount on ALREADY DISCOUNTED subtotal (STACKING)
    # Supports multiple codes: Partner code + Admin extra voucher
    # IMPORTANT: Partner codes ALWAYS apply FIRST regardless of input order
    discount_code = getattr(order_data, "discount_code", None)
    discount_codes = getattr(order_data, "discount_codes", None) or []

    # Combine single code with multiple codes list
    all_codes = []
    if discount_code:
        all_codes.append(discount_code.upper())
    if discount_codes:
        all_codes.extend([c.upper() for c in discount_codes if c])
    # Remove duplicates while preserving order
    all_codes = list(dict.fromkeys(all_codes))

    # SMART SORTING: Identify partner codes and process them FIRST
    partner_codes = []
    other_codes = []

    for code in all_codes:
        # Check if it's a partner code
        is_partner = await db.influencer_applications.find_one(
            {"partner_code": code, "status": "approved"}, {"_id": 0}
        )
        if is_partner:
            partner_codes.append(code)
        else:
            other_codes.append(code)

    # Reorder: Partner codes FIRST, then other codes
    sorted_codes = partner_codes + other_codes
    logger.info(f"Discount codes sorted: Partner={partner_codes}, Other={other_codes}")

    coupon_discount_percent = getattr(order_data, "discount_percent", 0) or 0
    total_coupon_discount_amount = 0.0
    partner_code_used = None
    extra_codes_used = []
    running_subtotal = discounted_subtotal_before_coupon
    first_purchase_code_applied = False

    # Get store settings for first purchase code
    store_settings = await db.store_settings.find_one(
        {"id": "store_settings"}, {"_id": 0}
    )
    fp_code_enabled = (
        store_settings.get("first_purchase_code_enabled", True)
        if store_settings
        else True
    )
    fp_code = (
        store_settings.get("first_purchase_code", "SIGNUP25").upper()
        if store_settings
        else "SIGNUP25"
    )
    fp_code_percent = (
        store_settings.get("first_purchase_code_percent", 25.0)
        if store_settings
        else 25.0
    )

    # Process each discount code (stacking) - Partner codes first!
    for code in sorted_codes:
        # Check if it's the FIRST PURCHASE CODE (only for new customers)
        if fp_code_enabled and code == fp_code:
            # Check if customer has previous orders
            customer_email = getattr(order_data, "customer_email", None)
            if customer_email:
                previous_orders = await db.orders.count_documents(
                    {
                        "customer_email": customer_email.lower(),
                        "status": {"$nin": ["cancelled", "refunded"]},
                    }
                )

                if previous_orders == 0:
                    # First time buyer - apply the discount!
                    discount_amount = round(
                        running_subtotal * (fp_code_percent / 100), 2
                    )
                    total_coupon_discount_amount += discount_amount
                    running_subtotal -= discount_amount
                    extra_codes_used.append(code)
                    first_purchase_code_applied = True
                    logger.info(
                        f"First purchase code {code} applied: {fp_code_percent}% = ${discount_amount} off"
                    )
                    continue
                else:
                    logger.info(
                        f"First purchase code {code} rejected: Customer has {previous_orders} previous orders"
                    )
                    continue
            continue

        # Check if it's a partner code
        partner = await db.influencer_applications.find_one(
            {"partner_code": code, "status": "approved"}, {"_id": 0}
        )

        if partner:
            # Partner referral code - ALWAYS APPLIED FIRST
            # Get the CUSTOMER discount from store settings (not partner commission)
            store_settings = await db.store_settings.find_one(
                {"id": "store_settings"}, {"_id": 0}
            )
            influencer_program = (
                store_settings.get("influencer_program", {}) if store_settings else {}
            )

            # Customer gets the influencer program's customer_discount_value (default 50%)
            # NOT the partner's custom_discount (which is their commission rate)
            customer_discount = influencer_program.get("customer_discount_value", 50.0)

            discount_amount = round(running_subtotal * (customer_discount / 100), 2)
            total_coupon_discount_amount += discount_amount
            running_subtotal -= discount_amount
            partner_code_used = code
            logger.info(
                f"Partner code {code} applied FIRST: {customer_discount}% customer discount = ${discount_amount} off"
            )
        else:
            # Check if it's a partner voucher
            voucher = await db.partner_vouchers.find_one(
                {"code": code, "is_active": True}, {"_id": 0}
            )

            if voucher:
                if voucher.get("discount_type") == "percentage":
                    discount_amount = round(
                        running_subtotal * (voucher.get("discount_value", 0) / 100), 2
                    )
                else:
                    discount_amount = min(
                        voucher.get("discount_value", 0), running_subtotal
                    )
                total_coupon_discount_amount += discount_amount
                running_subtotal -= discount_amount
                extra_codes_used.append(code)
                logger.info(f"Partner voucher {code} applied: ${discount_amount} off")
            else:
                # Check if it's a regular discount code
                regular_code = await db.discount_codes.find_one(
                    {"code": code, "is_active": True}, {"_id": 0}
                )

                if regular_code:
                    if regular_code.get("discount_type") == "percentage":
                        discount_amount = round(
                            running_subtotal
                            * (regular_code.get("discount_percent", 0) / 100),
                            2,
                        )
                    else:
                        discount_amount = min(
                            regular_code.get("discount_amount", 0), running_subtotal
                        )
                    total_coupon_discount_amount += discount_amount
                    running_subtotal -= discount_amount
                    extra_codes_used.append(code)
                    logger.info(f"Discount code {code} applied: ${discount_amount} off")
                else:
                    # Check exclusive_discounts collection
                    exclusive_code = await db.exclusive_discounts.find_one(
                        {"code": code, "is_active": {"$ne": False}}, {"_id": 0}
                    )
                    
                    if exclusive_code:
                        discount_pct = exclusive_code.get("discount_percent", 0)
                        discount_amount = round(
                            running_subtotal * (discount_pct / 100), 2
                        )
                        total_coupon_discount_amount += discount_amount
                        running_subtotal -= discount_amount
                        extra_codes_used.append(code)
                        logger.info(f"Exclusive discount {code} applied: {discount_pct}% = ${discount_amount} off")
                    else:
                        # Check offers collection (SMS/Email offer codes)
                        offer_code_doc = await db.offers.find_one(
                            {"code": code, "is_active": True}, {"_id": 0}
                        )
                        
                        if offer_code_doc:
                            discount_pct = offer_code_doc.get("discount_percent") or offer_code_doc.get("discount_value", 0)
                            discount_amount = round(
                                running_subtotal * (discount_pct / 100), 2
                            )
                            total_coupon_discount_amount += discount_amount
                            running_subtotal -= discount_amount
                            extra_codes_used.append(code)
                            logger.info(f"Offer code {code} applied: {discount_pct}% = ${discount_amount} off")
                        else:
                            # Check coupons collection
                            coupon_doc = await db.coupons.find_one(
                                {"code": code, "is_active": True}, {"_id": 0}
                            )
                            
                            if coupon_doc:
                                discount_pct = coupon_doc.get("discount_percent") or coupon_doc.get("discount_value", 0)
                                discount_amount = round(
                                    running_subtotal * (discount_pct / 100), 2
                                )
                                total_coupon_discount_amount += discount_amount
                                running_subtotal -= discount_amount
                                extra_codes_used.append(code)
                                logger.info(f"Coupon {code} applied: {discount_pct}% = ${discount_amount} off")

    # Apply any additional discount percent passed directly (e.g., from pre-validated codes)
    # This ensures the discount is applied even if the code doesn't exist in this database
    # (frontend may have validated it against a different source or it's a special code)
    if coupon_discount_percent > 0 and total_coupon_discount_amount == 0:
        additional_discount = round(
            running_subtotal * (coupon_discount_percent / 100), 2
        )
        total_coupon_discount_amount += additional_discount
        running_subtotal -= additional_discount
        logger.info(f"Frontend-validated discount applied: {coupon_discount_percent}% = ${additional_discount} off")

    coupon_discount_amount = total_coupon_discount_amount

    # Total discount = product discounts + all coupon discounts
    total_discount_amount = round(product_discount_total + coupon_discount_amount, 2)

    # Final discounted subtotal (after all discounts stacked)
    discounted_subtotal = round(running_subtotal, 2)

    # ========== FIRST PURCHASE AUTO-DISCOUNT ==========
    # Check if this is customer's first order and apply bonus
    first_purchase_bonus = 0.0
    first_purchase_applied = False

    # Get store settings for first purchase discount
    store_settings = await db.store_settings.find_one(
        {"id": "store_settings"}, {"_id": 0}
    )
    first_purchase_enabled = (
        store_settings.get("first_purchase_discount_enabled", True)
        if store_settings
        else True
    )
    first_purchase_percent = (
        store_settings.get("first_purchase_discount_percent", 10.0)
        if store_settings
        else 10.0
    )

    if first_purchase_enabled and first_purchase_percent > 0:
        # Check if customer has previous orders
        customer_email = (
            order_data.shipping_address.email
            if hasattr(order_data.shipping_address, "email")
            else None
        )
        user_id = user["id"] if user else None

        has_previous_orders = False
        if user_id:
            prev_order = await db.orders.find_one(
                {"user_id": user_id}, {"_id": 0, "id": 1}
            )
            has_previous_orders = prev_order is not None
        elif customer_email:
            prev_order = await db.orders.find_one(
                {"shipping_address.email": customer_email}, {"_id": 0, "id": 1}
            )
            has_previous_orders = prev_order is not None

        if not has_previous_orders:
            # Apply first purchase bonus on top of everything!
            first_purchase_bonus = round(
                discounted_subtotal * (first_purchase_percent / 100), 2
            )
            discounted_subtotal = round(discounted_subtotal - first_purchase_bonus, 2)
            total_discount_amount += first_purchase_bonus
            first_purchase_applied = True
            logger.info(
                f"First purchase bonus applied: {first_purchase_percent}% = ${first_purchase_bonus} off"
            )

    # Store all codes used
    all_discount_codes = ",".join(sorted_codes) if sorted_codes else discount_code

    # Calculate shipping based on method and weight (on ORIGINAL subtotal for free shipping threshold)
    province = order_data.shipping_address.province
    shipping_method = order_data.shipping_method or "standard"
    shipping_rates = calculate_shipping_rates(
        total_weight, province, subtotal
    )  # Use original subtotal

    selected_rate = next(
        (r for r in shipping_rates if r["method"] == shipping_method), shipping_rates[0]
    )
    shipping = selected_rate["price"]

    # Determine if this is an international order
    country = order_data.shipping_address.country
    country_code = "CA"  # Default to Canada
    is_international = False

    # Map common country names to codes
    country_mapping = {
        "canada": "CA",
        "united states": "US",
        "usa": "US",
        "united kingdom": "GB",
        "uk": "GB",
        "germany": "DE",
        "france": "FR",
        "italy": "IT",
        "spain": "ES",
        "australia": "AU",
        "japan": "JP",
        "china": "CN",
        "india": "IN",
        "brazil": "BR",
        "mexico": "MX",
        "netherlands": "NL",
        "belgium": "BE",
        "switzerland": "CH",
        "sweden": "SE",
        "norway": "NO",
        "denmark": "DK",
        "finland": "FI",
        "ireland": "IE",
        "portugal": "PT",
        "austria": "AT",
        "poland": "PL",
        "south korea": "KR",
        "singapore": "SG",
        "malaysia": "MY",
        "thailand": "TH",
        "philippines": "PH",
        "indonesia": "ID",
        "vietnam": "VN",
        "taiwan": "TW",
        "hong kong": "HK",
        "new zealand": "NZ",
        "united arab emirates": "AE",
        "uae": "AE",
        "saudi arabia": "SA",
        "israel": "IL",
        "south africa": "ZA",
        "nigeria": "NG",
        "egypt": "EG",
        "argentina": "AR",
        "chile": "CL",
        "colombia": "CO",
        "peru": "PE",
        "qatar": "QA",
        "kenya": "KE",
    }

    country_lower = country.lower().strip()
    if country_lower in country_mapping:
        country_code = country_mapping[country_lower]
    elif len(country) == 2:
        country_code = country.upper()

    is_international = country_code != "CA"

    # Calculate tax and duty using landed cost calculator
    landed_cost_result = calculate_landed_cost(
        subtotal=subtotal,
        country_code=country_code,
        province=province,
        weight_grams=total_weight,
        shipping_method=shipping_method,
    )

    tax = landed_cost_result["tax"]
    duty = landed_cost_result["duty"]

    # For international orders, use international shipping rates
    if is_international:
        shipping = landed_cost_result["shipping"]

    # ========== LOYALTY POINTS REDEMPTION ==========
    # Apply points discount AFTER all other discounts, tax on original price
    points_discount = 0.0
    points_redeemed = 0

    if order_data.redemption_token and user:
        # Validate and get the redemption
        redemption = await db.points_redemptions.find_one(
            {
                "id": order_data.redemption_token,
                "user_id": user["id"],
                "status": "pending",
            },
            {"_id": 0},
        )

        if redemption:
            points_redeemed = redemption.get("points", 0)
            points_discount = redemption.get("value", 0)

            # Points discount reduces the discounted_subtotal (not tax)
            discounted_subtotal = max(
                0, round(discounted_subtotal - points_discount, 2)
            )
            total_discount_amount += points_discount

            logger.info(
                f"Points redemption applied: {points_redeemed} points = ${points_discount} off"
            )

    # Total = Final discounted price + Tax (on ORIGINAL $99) + Duty + Shipping
    # Tax is ALWAYS calculated on original subtotal, not after discounts
    total = round(discounted_subtotal + tax + duty + shipping, 2)
    landed_total = round(subtotal + tax + duty + shipping, 2)

    # Generate order number
    order_count = await db.orders.count_documents({})
    order_number = f"RR-{str(order_count + 1).zfill(6)}"

    order = Order(
        order_number=order_number,
        user_id=user["id"] if user else None,
        items=[item.model_dump() for item in order_items],
        shipping_address=order_data.shipping_address.model_dump(),
        subtotal=subtotal,  # Original subtotal before any discounts
        discount_code=all_discount_codes,  # All codes used (comma-separated)
        discount_percent=coupon_discount_percent,  # Coupon discount percentage
        discount_amount=total_discount_amount,  # Total discount (product + coupon + points)
        points_discount=points_discount,  # Points discount amount separately
        points_redeemed=points_redeemed,  # Number of points used
        shipping=shipping,
        shipping_cost_paid=0.0,  # To be updated when shipped
        tax=tax,  # Tax on ORIGINAL price ($99)
        duty=duty,
        landed_cost=landed_total,
        total=total,
        cost_of_goods=round(cost_of_goods, 2),  # Your actual cost for products
        payment_method=order_data.payment_method,
        is_international=is_international,
        destination_country=country_code,
        storefront=order_data.storefront or "reroots",  # Track which storefront
    )

    order_dict = order.model_dump()
    order_dict["created_at"] = order_dict["created_at"].isoformat()

    # Add first purchase bonus info
    if first_purchase_applied:
        order_dict["first_purchase_bonus"] = first_purchase_bonus
        order_dict["first_purchase_percent"] = first_purchase_percent

    # Add WhatsApp opt-in flag
    order_dict["whatsapp_opted_in"] = order_data.whatsapp_opted_in or False

    await db.orders.insert_one(order_dict)
    
    # Update customer record with WhatsApp opt-in
    if order_data.whatsapp_opted_in and order.shipping_address.email:
        await db.customers.update_one(
            {"email": order.shipping_address.email.lower()},
            {"$set": {
                "whatsapp_opted_in": True,
                "whatsapp_phone": order.shipping_address.phone,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }},
            upsert=False  # Only update if exists
        )
    
    # Broadcast new order event to admin WebSocket connections
    await broadcast_admin_event("new_order", {
        "order_id": order.id,
        "order_number": order.order_number,
        "total": total,
        "customer_email": order.shipping_address.email,
        "items_count": len(order.items)
    })

    # Update partner stats if partner code was used
    if partner_code_used:
        # Check if it's a partner's code
        partner = await db.influencer_applications.find_one(
            {"partner_code": partner_code_used, "status": "approved"}, {"_id": 0}
        )

        if partner:
            # Calculate commission
            commission_rate = partner.get("custom_commission", 10) / 100
            commission_earned = round(discounted_subtotal * commission_rate, 2)

            # Update partner stats
            await db.influencer_applications.update_one(
                {"id": partner["id"]},
                {
                    "$inc": {
                        "total_orders": 1,
                        "total_revenue": discounted_subtotal,
                        "total_commission": commission_earned,
                        "pending_payout": commission_earned,
                    }
                },
            )
            logger.info(
                f"Partner {partner.get('full_name')} credited: Order ${discounted_subtotal}, Commission ${commission_earned}"
            )

            # Store partner info in order for reference
            await db.orders.update_one(
                {"id": order.id},
                {
                    "$set": {
                        "partner_id": partner["id"],
                        "partner_name": partner.get("full_name"),
                        "partner_commission": commission_earned,
                    }
                },
            )
            
            # Create commission record for easy tracking
            await db.partner_commissions.insert_one({
                "id": str(uuid.uuid4()),
                "partner_id": partner["id"],
                "partner_name": partner.get("full_name"),
                "order_id": order.id,
                "order_total": discounted_subtotal,
                "commission": commission_earned,
                "commission_rate": commission_rate,
                "code": partner_code_used,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            # WhatsApp alert to admin about referral
            try:
                tj_number = os.environ.get("TJ_WHATSAPP_NUMBER")
                if tj_number:
                    from services.twilio_service import send_whatsapp_message
                    await send_whatsapp_message(
                        tj_number,
                        f"🤝 Partner referral: {partner.get('full_name')} earned ${commission_earned} CAD commission on order #{order.id[:8]}"
                    )
            except Exception as e:
                logging.warning(f"Failed to send partner commission WhatsApp: {e}")
        else:
            # Check if it's a partner voucher
            voucher = await db.partner_vouchers.find_one(
                {"code": discount_code.upper(), "is_active": True}, {"_id": 0}
            )

            if voucher:
                voucher_partner = await db.influencer_applications.find_one(
                    {"id": voucher["partner_id"]}, {"_id": 0}
                )

                if voucher_partner:
                    commission_rate = voucher.get("partner_commission", 10) / 100
                    commission_earned = round(discounted_subtotal * commission_rate, 2)

                    # Update partner stats
                    await db.influencer_applications.update_one(
                        {"id": voucher_partner["id"]},
                        {
                            "$inc": {
                                "total_orders": 1,
                                "total_revenue": discounted_subtotal,
                                "total_commission": commission_earned,
                                "pending_payout": commission_earned,
                            }
                        },
                    )

                    # Update voucher usage count
                    await db.partner_vouchers.update_one(
                        {"id": voucher["id"]}, {"$inc": {"current_uses": 1}}
                    )

                    logger.info(
                        f"Partner {voucher_partner.get('full_name')} credited via voucher: Order ${discounted_subtotal}, Commission ${commission_earned}"
                    )

                    # Store partner info in order
                    await db.orders.update_one(
                        {"id": order.id},
                        {
                            "$set": {
                                "partner_id": voucher_partner["id"],
                                "partner_name": voucher_partner.get("full_name"),
                                "partner_commission": commission_earned,
                                "voucher_id": voucher["id"],
                            }
                        },
                    )
                    
                    # Create commission record for voucher-based referral
                    await db.partner_commissions.insert_one({
                        "id": str(uuid.uuid4()),
                        "partner_id": voucher_partner["id"],
                        "partner_name": voucher_partner.get("full_name"),
                        "order_id": order.id,
                        "order_total": discounted_subtotal,
                        "commission": commission_earned,
                        "commission_rate": commission_rate,
                        "code": discount_code.upper(),
                        "voucher_id": voucher["id"],
                        "status": "pending",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    })
                    
                    # WhatsApp alert to admin about referral
                    try:
                        tj_number = os.environ.get("TJ_WHATSAPP_NUMBER")
                        if tj_number:
                            from services.twilio_service import send_whatsapp_message
                            await send_whatsapp_message(
                                tj_number,
                                f"🤝 Partner referral: {voucher_partner.get('full_name')} earned ${commission_earned} CAD commission on order #{order.id[:8]}"
                            )
                    except Exception as e:
                        logging.warning(f"Failed to send partner commission WhatsApp: {e}")

    # P0 Fix: Award loyalty points, track partner referrals, send notifications
    # This is the on_order_placed handler - Steps 1-5 of order completion
    try:
        from routes.reroots_p0_fixes import (
            award_loyalty_points, track_partner_referral, sendgrid_send_email,
            send_whatsapp_order_confirmation
        )
        from routes.reroots_email_templates import order_confirmation
        
        customer_email = order.shipping_address.email
        customer_phone = order.shipping_address.phone if hasattr(order.shipping_address, 'phone') else None
        # Combine first_name and last_name for customer name
        customer_name = f"{order.shipping_address.first_name} {order.shipping_address.last_name}".strip()
        
        # Step 1: Update CRM record (already built - handled elsewhere)
        
        # Step 2: Award loyalty points FIRST (so we have balance for email)
        loyalty_result = None
        points_earned = 250
        new_balance = 0
        if customer_email:
            loyalty_result = await award_loyalty_points(
                db=db,
                customer_email=customer_email,
                order_total=total,
                order_id=order.id,
                customer_phone=customer_phone,
                customer_name=customer_name
            )
            points_earned = loyalty_result.get("points_earned", 250)
            new_balance = loyalty_result.get("new_balance", 0)
            is_first = loyalty_result.get("is_first_order", False)
            logger.info(f"Awarded {points_earned} Roots to {customer_email} (first_order={is_first})")
            
            # Task 6: Create WhatsApp notification for points earned
            try:
                from routes.whatsapp_templates import notify_points_earned
                customer_data = {
                    'email': customer_email,
                    'first_name': customer_name.split()[0] if customer_name else '',
                    'last_name': ' '.join(customer_name.split()[1:]) if customer_name and len(customer_name.split()) > 1 else '',
                    'phone': customer_phone
                }
                await notify_points_earned(db, customer_data, points_earned, new_balance, is_first)
            except Exception as e:
                logger.error(f"Failed to create points earned WhatsApp action: {e}")
        
        # Step 3: Send confirmation email WITH Roots balance (Task 8)
        if customer_email:
            order_for_email = {
                "_id": order.id,
                "id": order.id,
                "customerName": customer_name,
                "name": customer_name,
                "total": total,
                "items": [{"name": item.product_name, "quantity": item.quantity, "price": item.price} for item in order_items]
            }
            tmpl = order_confirmation(order_for_email, loyalty_balance=new_balance, points_earned=points_earned)
            await sendgrid_send_email(to=customer_email, subject=tmpl["subject"], html_body=tmpl["html"])
            logger.info(f"Order confirmation email sent to {customer_email}")
        
        # Step 4: Create revenue transaction (already built - handled elsewhere)
        
        # Step 5: Send WhatsApp order confirmation
        if customer_phone:
            # Build product name for WhatsApp message
            product_names = [item.product_name for item in order_items[:3]]
            product_name = ", ".join(product_names)
            if len(order_items) > 3:
                product_name += f" + {len(order_items) - 3} more"
            
            whatsapp_order_data = {
                "email": customer_email,
                "phone": customer_phone,
                "name": customer_name,
                "order_id": order.order_number,
                "total": total,
                "product_name": product_name,
                "is_first_order": loyalty_result.get("is_first_order", False) if loyalty_result else False
            }
            whatsapp_result = await send_whatsapp_order_confirmation(db, whatsapp_order_data)
            if whatsapp_result.get("success"):
                logger.info(f"WhatsApp order confirmation sent to {customer_phone}")
            else:
                logger.warning(f"WhatsApp order confirmation failed: {whatsapp_result.get('error')}")
        
        # Track partner referral using the P0 tracking system
        if discount_code:
            await track_partner_referral(db, order.id, total, discount_code)
        
        # RESTOCK CONVERSION TRACKING: Mark waitlist conversions for analytics
        if customer_email and order_items:
            for item in order_items:
                try:
                    await mark_restock_conversion(db, customer_email, item.product_id)
                except Exception as conv_err:
                    logger.debug(f"Restock conversion tracking skipped: {conv_err}")
        
        # Task 7: Check if this is a referred customer's first order
        if customer_email and is_first:
            try:
                from routes.loyalty_bonuses import get_referrer_id, on_referral_first_purchase, set_db as set_bonus_db
                set_bonus_db(db)
                
                referrer_id = await get_referrer_id(customer_email)
                if referrer_id:
                    await on_referral_first_purchase(
                        referrer_id=referrer_id,
                        referred_email=customer_email
                    )
                    logger.info(f"Referral bonus triggered for referrer of {customer_email}")
            except Exception as ref_err:
                logger.debug(f"Referral bonus check skipped: {ref_err}")
            
    except Exception as e:
        logger.error(f"P0 post-order processing error: {e}")

    # Send order confirmation email
    try:
        from routers.email_service import send_order_confirmation
        email_items = [{"name": i.get("name"), "quantity": i.get("quantity"), "price": i.get("price")} for i in order_items]
        customer_name = order_data.shipping_address.get("first_name", "Customer") if order_data.shipping_address else "Customer"
        send_order_confirmation(customer_email, customer_name, order.order_number, email_items, total)
    except Exception as e:
        logger.warning(f"Order confirmation email failed: {e}")

    return {"order_id": order.id, "order_number": order.order_number, "total": total}


# ============================================
# LOYALTY POINTS SYSTEM (Default values - configurable via admin)
# Default: 250 points per product purchased
# Default: 1 point = $0.05 (20 points = $1)
# ============================================
DEFAULT_POINTS_PER_PRODUCT = 250
DEFAULT_POINT_VALUE = 0.05  # $0.05 per point (20 points = $1)
DEFAULT_POINTS_FOR_30_DISCOUNT = 600  # 600 points = 30% off (one-time)
DEFAULT_THIRTY_PERCENT_DISCOUNT = 30  # The discount percentage for 600 points

# Aliases for backward compatibility
POINTS_FOR_30_DISCOUNT = DEFAULT_POINTS_FOR_30_DISCOUNT
THIRTY_PERCENT_DISCOUNT = DEFAULT_THIRTY_PERCENT_DISCOUNT


async def get_loyalty_config():
    """Get loyalty points configuration from store settings"""
    store_settings = await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0})
    loyalty_config = store_settings.get("loyalty_config", {}) if store_settings else {}
    
    return {
        "points_per_product": loyalty_config.get("points_per_product", DEFAULT_POINTS_PER_PRODUCT),
        "point_value": loyalty_config.get("point_value", DEFAULT_POINT_VALUE),
        "points_for_30_discount": loyalty_config.get("points_for_30_discount", DEFAULT_POINTS_FOR_30_DISCOUNT),
        "thirty_percent_discount": loyalty_config.get("thirty_percent_discount", DEFAULT_THIRTY_PERCENT_DISCOUNT),
        "points_per_dollar": loyalty_config.get("points_per_dollar", 20),  # 20 points = $1 by default
        "max_redemption_percent": loyalty_config.get("max_redemption_percent", 30),  # 30% cap on redemption
        "enabled": loyalty_config.get("enabled", True),
        "allow_gift_points": loyalty_config.get("allow_gift_points", True),
        "allow_buy_points": loyalty_config.get("allow_buy_points", True),
    }


@router.get("/loyalty/config")
async def get_loyalty_config_endpoint():
    """Get loyalty points configuration (public endpoint)"""
    config = await get_loyalty_config()
    return config


@router.put("/admin/loyalty/config")
async def update_loyalty_config(data: dict, request: Request):
    """Update loyalty points configuration (admin only)"""
    user = await get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Validate data
    loyalty_config = {
        "points_per_product": int(data.get("points_per_product", DEFAULT_POINTS_PER_PRODUCT)),
        "point_value": float(data.get("point_value", DEFAULT_POINT_VALUE)),
        "points_for_30_discount": int(data.get("points_for_30_discount", DEFAULT_POINTS_FOR_30_DISCOUNT)),
        "thirty_percent_discount": int(data.get("thirty_percent_discount", DEFAULT_THIRTY_PERCENT_DISCOUNT)),
        "points_per_dollar": int(data.get("points_per_dollar", 20)),
        "max_redemption_percent": int(data.get("max_redemption_percent", 30)),  # 30% cap
        "enabled": data.get("enabled", True),
        "allow_gift_points": data.get("allow_gift_points", True),
        "allow_buy_points": data.get("allow_buy_points", True),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.store_settings.update_one(
        {"id": "store_settings"},
        {"$set": {"loyalty_config": loyalty_config}},
        upsert=True
    )
    
    logging.info(f"Loyalty config updated by admin: {user.get('email')}")
    
    return {"success": True, "config": loyalty_config}


@router.post("/admin/loyalty/adjust-points")
async def admin_adjust_user_points(data: dict, request: Request):
    """Adjust a user's points balance (admin only)"""
    user = await get_current_user(request)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    target_user_email = data.get("user_email")
    adjustment = int(data.get("adjustment", 0))
    reason = data.get("reason", "Admin adjustment")
    
    if not target_user_email:
        raise HTTPException(status_code=400, detail="User email required")
    
    # Find target user
    target_user = await db.users.find_one({"email": target_user_email.lower()}, {"_id": 0})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    target_user_id = target_user["id"]
    
    # Get or create points record
    points_record = await db.loyalty_points.find_one({"user_id": target_user_id})
    
    current_balance = points_record.get("balance", 0) if points_record else 0
    new_balance = max(0, current_balance + adjustment)  # Can't go negative
    
    # Create transaction record
    transaction = {
        "type": "admin_adjustment",
        "amount": adjustment,
        "reason": reason,
        "admin_email": user.get("email"),
        "balance_before": current_balance,
        "balance_after": new_balance,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    if points_record:
        await db.loyalty_points.update_one(
            {"user_id": target_user_id},
            {
                "$set": {"balance": new_balance},
                "$push": {"history": transaction},
                "$inc": {
                    "lifetime_earned": max(0, adjustment),  # Only add positive adjustments
                    "admin_adjustments_count": 1
                }
            }
        )
    else:
        await db.loyalty_points.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": target_user_id,
            "balance": new_balance,
            "lifetime_earned": max(0, adjustment),
            "lifetime_redeemed": 0,
            "history": [transaction],
            "admin_adjustments_count": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    
    logging.info(f"Admin {user.get('email')} adjusted points for {target_user_email}: {adjustment} ({reason})")
    
    # Check for tier upgrade in background
    try:
        async def do_tier_upgrade():
            from routers.cron_jobs import check_tier_upgrade
            await check_tier_upgrade(target_user_id, new_balance)
        asyncio.create_task(do_tier_upgrade())
    except Exception as e:
        logging.warning(f"Tier upgrade check failed: {e}")
    
    return {
        "success": True,
        "user_email": target_user_email,
        "previous_balance": current_balance,
        "new_balance": new_balance,
        "adjustment": adjustment
    }


@router.get("/admin/loyalty/users")
async def get_users_with_points(request: Request, skip: int = 0, limit: int = 50):
    """Get all users with their points balance (admin only)"""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = []
    
    # First, check the legacy loyalty_points collection
    points_records = await db.loyalty_points.find(
        {},
        {"_id": 0}
    ).sort("balance", -1).skip(skip).limit(limit).to_list(limit)
    
    # Enrich with user info
    for record in points_records:
        user_info = await db.users.find_one({"id": record["user_id"]}, {"_id": 0, "id": 1, "email": 1, "first_name": 1, "last_name": 1})
        if user_info:
            result.append({
                "user_id": record["user_id"],
                "email": user_info.get("email"),
                "name": f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip(),
                "balance": record.get("balance", 0),
                "lifetime_earned": record.get("lifetime_earned", 0),
                "lifetime_redeemed": record.get("lifetime_redeemed", 0),
            })
    
    # Also check the loyalty_members collection (used by new award_loyalty_points)
    seen_emails = {r["email"] for r in result if r.get("email")}
    loyalty_members = await db.loyalty_members.find(
        {},
        {"_id": 0}
    ).sort("points", -1).to_list(100)
    
    for member in loyalty_members:
        if member.get("email") not in seen_emails:
            joined = member.get("joinedAt")
            result.append({
                "user_id": member.get("email"),  # Use email as ID for loyalty_members
                "email": member.get("email"),
                "name": member.get("email", "").split("@")[0],  # Use email prefix as name
                "balance": member.get("points", 0),
                "lifetime_earned": member.get("lifetimeEarned", member.get("points", 0)),
                "lifetime_redeemed": 0,
                "tier": member.get("tier", "Standard"),
                "total_orders": member.get("totalOrders", 0),
                "joined_at": joined.isoformat() if joined else None,
            })
            seen_emails.add(member.get("email"))
    
    # Sort combined results by balance
    result.sort(key=lambda x: x.get("balance", 0), reverse=True)
    
    # Apply pagination
    total = len(result)
    result = result[skip:skip + limit]
    
    return {"users": result, "total": total}


@router.get("/loyalty/points")
async def get_loyalty_points(request: Request):
    """Get user's loyalty points balance"""
    user = await get_current_user(request)
    if not user:
        return {"points": 0, "value": 0, "history": []}

    # Get config for point value
    config = await get_loyalty_config()
    point_value = config.get("point_value", DEFAULT_POINT_VALUE)

    # Get or create points record
    points_record = await db.loyalty_points.find_one(
        {"user_id": user["id"]}, {"_id": 0}
    )

    if not points_record:
        return {"points": 0, "value": 0, "history": [], "config": config}

    return {
        "points": points_record.get("balance", 0),
        "points_balance": points_record.get("balance", 0),  # Alias for frontend
        "value": round(points_record.get("balance", 0) * point_value, 2),
        "lifetime_earned": points_record.get("lifetime_earned", 0),
        "lifetime_redeemed": points_record.get("lifetime_redeemed", 0),
        "history": points_record.get("history", [])[-10:],  # Last 10 transactions
        "config": config
    }


@router.post("/loyalty/points/earn")
async def earn_loyalty_points(data: dict, request: Request):
    """Award points for a completed order (called after successful payment)"""
    order_id = data.get("order_id")

    if not order_id:
        raise HTTPException(status_code=400, detail="Order ID required")

    # Get loyalty config
    config = await get_loyalty_config()
    if not config.get("enabled", True):
        return {"message": "Loyalty points system is disabled", "points": 0}
    
    points_per_product = config.get("points_per_product", DEFAULT_POINTS_PER_PRODUCT)

    # Get order
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Check if points already awarded for this order
    if order.get("points_awarded"):
        return {
            "message": "Points already awarded",
            "points": order.get("points_awarded"),
        }

    # Calculate points using config
    total_quantity = sum(item.get("quantity", 1) for item in order.get("items", []))
    points_earned = total_quantity * points_per_product

    # Get user (if logged in) or use customer email
    user_id = order.get("user_id")
    customer_email = order.get("customer_email", "").lower()

    if not user_id and customer_email:
        # Try to find user by email
        user = await db.users.find_one({"email": customer_email}, {"_id": 0})
        if user:
            user_id = user["id"]

    if not user_id:
        # Store points as pending for guest checkout
        await db.pending_points.insert_one(
            {
                "id": str(uuid.uuid4()),
                "email": customer_email,
                "order_id": order_id,
                "points": points_earned,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # Mark order as points awarded
        await db.orders.update_one(
            {"id": order_id},
            {"$set": {"points_awarded": points_earned, "points_pending": True}},
        )

        return {
            "message": "Points pending - will be credited when customer creates account",
            "points": points_earned,
            "pending": True,
        }

    # Award points to user
    history_entry = {
        "id": str(uuid.uuid4()),
        "type": "earned",
        "points": points_earned,
        "description": f"Purchase - Order #{order.get('order_number', order_id[:8])}",
        "order_id": order_id,
        "date": datetime.now(timezone.utc).isoformat(),
    }

    # Update or create points record
    await db.loyalty_points.update_one(
        {"user_id": user_id},
        {
            "$inc": {"balance": points_earned, "lifetime_earned": points_earned},
            "$push": {"history": history_entry},
            "$setOnInsert": {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        upsert=True,
    )

    # Mark order as points awarded
    await db.orders.update_one(
        {"id": order_id},
        {"$set": {"points_awarded": points_earned, "points_pending": False}},
    )

    logger.info(
        f"Awarded {points_earned} points to user {user_id} for order {order_id}"
    )

    return {
        "message": f"Earned {points_earned} ReRoots Points!",
        "points": points_earned,
        "value": round(points_earned * POINT_VALUE, 2),
    }


@router.post("/loyalty/points/redeem")
async def redeem_loyalty_points(data: dict, request: Request):
    """Redeem points for discount at checkout - capped at 30% of subtotal"""
    user = await require_auth(request)
    points_to_redeem = data.get("points", 0)
    subtotal = data.get("subtotal", 0)  # Order subtotal for cap calculation

    if points_to_redeem < 1:
        raise HTTPException(status_code=400, detail="Minimum 1 point to redeem")

    # Get loyalty config
    config = await get_loyalty_config()
    point_value = config.get("point_value", DEFAULT_POINT_VALUE)
    max_discount_percent = config.get("max_redemption_percent", 30)  # 30% cap

    # Get user's points balance - check both collections
    balance = 0
    balance_source = None
    
    # Check legacy loyalty_points collection
    points_record = await db.loyalty_points.find_one(
        {"user_id": user["id"]}, {"_id": 0}
    )
    if points_record:
        balance = points_record.get("balance", 0)
        balance_source = "loyalty_points"
    
    # Also check new loyalty_members collection
    if balance == 0:
        member_record = await db.loyalty_members.find_one(
            {"email": user.get("email")}, {"_id": 0}
        )
        if member_record:
            balance = member_record.get("points", 0)
            balance_source = "loyalty_members"

    if balance < points_to_redeem:
        raise HTTPException(status_code=400, detail="Insufficient points")

    # Calculate discount value
    discount_value = round(points_to_redeem * point_value, 2)
    
    # Apply 30% cap on discount if subtotal provided
    max_discount = None
    capped = False
    if subtotal > 0:
        max_discount = round(subtotal * (max_discount_percent / 100), 2)
        if discount_value > max_discount:
            discount_value = max_discount
            # Recalculate points needed for capped discount
            points_to_redeem = int(max_discount / point_value)
            capped = True

    # Generate a redemption token (valid for 30 minutes)
    redemption_token = str(uuid.uuid4())

    await db.points_redemptions.insert_one(
        {
            "id": redemption_token,
            "user_id": user["id"],
            "user_email": user.get("email"),
            "points": points_to_redeem,
            "value": discount_value,
            "status": "pending",
            "balance_source": balance_source,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=30)
            ).isoformat(),
        }
    )

    return {
        "redemption_token": redemption_token,
        "points": points_to_redeem,
        "discount_value": discount_value,
        "message": f"Redeem {points_to_redeem} points for ${discount_value} off",
        "capped": capped,
        "max_discount": max_discount,
        "max_discount_percent": max_discount_percent,
    }


@router.post("/loyalty/points/redeem-30-percent")
async def redeem_30_percent_discount(data: dict, request: Request):
    """
    Redeem 600 points for 30% off - ONE TIME ONLY per user.
    This is a special redemption that gives 30% off the order total (instead of a fixed dollar amount).
    """
    user = await require_auth(request)
    order_subtotal = data.get("order_subtotal", 0)  # Needed to calculate 30% value

    if order_subtotal <= 0:
        raise HTTPException(status_code=400, detail="Order subtotal required")

    # Check if user has already used this one-time offer
    points_record = await db.loyalty_points.find_one(
        {"user_id": user["id"]}, {"_id": 0}
    )

    if not points_record:
        raise HTTPException(status_code=400, detail="No points balance found")

    # Check if user has already used the 30% discount
    if points_record.get("used_30_percent_discount", False):
        raise HTTPException(
            status_code=400,
            detail="You have already used your one-time 30% discount offer"
        )

    # Check if user has enough points (600 required)
    current_balance = points_record.get("balance", 0)
    if current_balance < POINTS_FOR_30_DISCOUNT:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient points. You have {current_balance} points, but need {POINTS_FOR_30_DISCOUNT} for 30% off"
        )

    # Calculate the 30% discount value based on order subtotal
    discount_value = round(order_subtotal * (THIRTY_PERCENT_DISCOUNT / 100), 2)

    # Generate a redemption token (valid for 30 minutes)
    redemption_token = str(uuid.uuid4())

    await db.points_redemptions.insert_one(
        {
            "id": redemption_token,
            "user_id": user["id"],
            "points": POINTS_FOR_30_DISCOUNT,
            "value": discount_value,
            "discount_type": "percentage",
            "discount_percent": THIRTY_PERCENT_DISCOUNT,
            "is_30_percent_offer": True,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=30)
            ).isoformat(),
        }
    )

    logger.info(
        f"User {user['id']} initiated 30% discount redemption for ${discount_value} (subtotal: ${order_subtotal})"
    )

    return {
        "redemption_token": redemption_token,
        "points": POINTS_FOR_30_DISCOUNT,
        "discount_value": discount_value,
        "discount_percent": THIRTY_PERCENT_DISCOUNT,
        "is_30_percent_offer": True,
        "message": f"🎉 Redeem {POINTS_FOR_30_DISCOUNT} points for {THIRTY_PERCENT_DISCOUNT}% off (${discount_value})!",
    }


@router.get("/loyalty/points/check-30-percent-eligibility")
async def check_30_percent_eligibility(request: Request):
    """
    Check if user is eligible for the one-time 30% discount offer.
    Returns eligibility status, points balance, and whether it's already been used.
    """
    user = await get_current_user(request)
    if not user:
        return {
            "eligible": False,
            "has_enough_points": False,
            "already_used": False,
            "points_balance": 0,
            "points_needed": POINTS_FOR_30_DISCOUNT,
            "message": "Please log in to check eligibility"
        }

    points_record = await db.loyalty_points.find_one(
        {"user_id": user["id"]}, {"_id": 0}
    )

    if not points_record:
        return {
            "eligible": False,
            "has_enough_points": False,
            "already_used": False,
            "points_balance": 0,
            "points_needed": POINTS_FOR_30_DISCOUNT,
            "message": f"Earn {POINTS_FOR_30_DISCOUNT} points to unlock 30% off!"
        }

    current_balance = points_record.get("balance", 0)
    already_used = points_record.get("used_30_percent_discount", False)
    has_enough_points = current_balance >= POINTS_FOR_30_DISCOUNT

    if already_used:
        return {
            "eligible": False,
            "has_enough_points": has_enough_points,
            "already_used": True,
            "points_balance": current_balance,
            "points_needed": POINTS_FOR_30_DISCOUNT,
            "message": "You've already used your one-time 30% discount"
        }

    if not has_enough_points:
        points_remaining = POINTS_FOR_30_DISCOUNT - current_balance
        return {
            "eligible": False,
            "has_enough_points": False,
            "already_used": False,
            "points_balance": current_balance,
            "points_needed": POINTS_FOR_30_DISCOUNT,
            "points_remaining": points_remaining,
            "message": f"Earn {points_remaining} more points to unlock 30% off!"
        }

    return {
        "eligible": True,
        "has_enough_points": True,
        "already_used": False,
        "points_balance": current_balance,
        "points_needed": POINTS_FOR_30_DISCOUNT,
        "discount_percent": THIRTY_PERCENT_DISCOUNT,
        "message": f"🎉 You can redeem {POINTS_FOR_30_DISCOUNT} points for {THIRTY_PERCENT_DISCOUNT}% off (one-time offer)!"
    }


@router.post("/loyalty/points/apply")
async def apply_points_redemption(data: dict, request: Request):
    """Apply a points redemption to an order (deduct points)"""
    user = await require_auth(request)
    redemption_token = data.get("redemption_token")
    order_id = data.get("order_id")

    if not redemption_token:
        raise HTTPException(status_code=400, detail="Redemption token required")

    # Find and validate redemption
    redemption = await db.points_redemptions.find_one(
        {"id": redemption_token, "user_id": user["id"], "status": "pending"}, {"_id": 0}
    )

    if not redemption:
        raise HTTPException(status_code=404, detail="Invalid or expired redemption")

    # Check expiration
    expires_at = datetime.fromisoformat(redemption["expires_at"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) > expires_at:
        await db.points_redemptions.update_one(
            {"id": redemption_token}, {"$set": {"status": "expired"}}
        )
        raise HTTPException(status_code=400, detail="Redemption expired")

    points_to_deduct = redemption["points"]
    discount_value = redemption["value"]
    balance_source = redemption.get("balance_source", "loyalty_points")

    # Deduct points from the appropriate collection
    if balance_source == "loyalty_members":
        # Deduct from loyalty_members collection
        await db.loyalty_members.update_one(
            {"email": user.get("email")},
            {"$inc": {"points": -points_to_deduct}}
        )
        # Log transaction
        await db.loyalty_transactions.insert_one({
            "email": user.get("email"),
            "type": "redeem",
            "points": -points_to_deduct,
            "reason": f"Redeemed for ${discount_value} discount",
            "orderId": order_id,
            "createdAt": datetime.now(timezone.utc),
        })
        logger.info(f"Deducted {points_to_deduct} points from loyalty_members for {user.get('email')}")
    else:
        # Deduct from legacy loyalty_points collection
        history_entry = {
            "id": str(uuid.uuid4()),
            "type": "redeemed",
            "points": -points_to_deduct,
            "description": f"Redeemed for ${discount_value} discount",
            "order_id": order_id,
            "date": datetime.now(timezone.utc).isoformat(),
        }

        # Build update operation
        update_ops = {
            "$inc": {
                "balance": -points_to_deduct,
                "lifetime_redeemed": points_to_deduct,
            },
            "$push": {"history": history_entry},
        }

        # If this is the 30% one-time offer, mark it as used
        is_30_percent_offer = redemption.get("is_30_percent_offer", False)
        if is_30_percent_offer:
            update_ops["$set"] = {"used_30_percent_discount": True}
            logger.info(f"User {user['id']} used their one-time 30% discount offer")

        await db.loyalty_points.update_one(
            {"user_id": user["id"]},
            update_ops,
        )

    # Mark redemption as used
    await db.points_redemptions.update_one(
        {"id": redemption_token}, {"$set": {"status": "used", "order_id": order_id}}
    )

    # Send WhatsApp confirmation if phone available
    try:
        from routes.reroots_p0_fixes import send_redemption_confirmation_whatsapp, send_redemption_confirmation_email
        
        # Get user's phone and remaining balance
        if balance_source == "loyalty_members":
            member = await db.loyalty_members.find_one({"email": user.get("email")}, {"_id": 0})
            remaining = member.get("points", 0) if member else 0
        else:
            record = await db.loyalty_points.find_one({"user_id": user["id"]}, {"_id": 0})
            remaining = record.get("balance", 0) if record else 0
        
        # Get phone from user profile
        phone = user.get("phone")
        name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or user.get("email", "").split("@")[0]
        
        # Send email notification
        await send_redemption_confirmation_email(
            customer_email=user.get("email"),
            customer_name=name,
            points_redeemed=points_to_deduct,
            discount_applied=discount_value,
            remaining_balance=remaining
        )
        
        # Send WhatsApp if phone available - creates wa.me link for admin to send
        if phone:
            # Legacy direct send (if WHAPI configured)
            await send_redemption_confirmation_whatsapp(
                phone=phone,
                name=name,
                points_redeemed=points_to_deduct,
                discount_applied=discount_value,
                remaining_balance=remaining
            )
            
            # Task 6: Also create wa.me CRM action for admin panel
            try:
                from routes.whatsapp_templates import notify_redemption_confirmed
                customer_data = {
                    'email': user.get("email"),
                    'first_name': user.get("first_name", ""),
                    'last_name': user.get("last_name", ""),
                    'phone': phone
                }
                await notify_redemption_confirmed(db, customer_data, points_to_deduct, discount_value, remaining)
            except Exception as wa_err:
                logger.debug(f"wa.me action creation skipped: {wa_err}")
    except Exception as e:
        logger.warning(f"Failed to send redemption notifications: {e}")

    logger.info(
        f"User {user['id']} redeemed {points_to_deduct} points for ${discount_value}"
    )

    return {
        "success": True,
        "points_deducted": points_to_deduct,
        "discount_applied": discount_value,
    }


@router.get("/checkout/loyalty-context")
async def get_checkout_loyalty_context(request: Request, subtotal: float = 0):
    """
    Get loyalty balance and redemption info for checkout.
    Returns: balance, balance_value, max_redeemable_amount, points_to_redeem
    
    Per Task 2 specs:
    - Point value: $0.05 per point (20 points = $1)
    - Max discount: 30% of order subtotal
    """
    user = await get_current_user(request)
    
    if not user:
        return {
            "loyalty_balance": 0,
            "balance_value": 0,
            "redeemable_amount": 0,
            "points_to_redeem": 0,
            "max_discount_pct": 30,
            "logged_in": False,
            "message": "Log in to use your Roots balance"
        }
    
    # Get config
    config = await get_loyalty_config()
    point_value = config.get("point_value", 0.05)  # $0.05 per point
    max_discount_pct = config.get("max_redemption_percent", 30)  # 30% cap
    
    # Check loyalty_points collection (legacy)
    balance = 0
    points_record = await db.loyalty_points.find_one({"user_id": user["id"]}, {"_id": 0})
    if points_record:
        balance = points_record.get("balance", 0)
    
    # Also check loyalty_members collection (new system)
    if balance == 0:
        member = await db.loyalty_members.find_one({"email": user.get("email")}, {"_id": 0})
        if member:
            balance = member.get("points", 0)
    
    # Calculate redemption values
    balance_dollar_value = round(balance * point_value, 2)
    
    # Calculate max discount based on subtotal
    max_discount_amount = 0
    redeemable_amount = 0
    points_to_redeem = 0
    
    if subtotal > 0:
        max_discount_amount = round(subtotal * (max_discount_pct / 100), 2)
        # Can only redeem up to max discount or balance value, whichever is smaller
        redeemable_amount = min(balance_dollar_value, max_discount_amount)
        # Calculate how many points needed for this amount
        points_to_redeem = int(redeemable_amount / point_value) if point_value > 0 else 0
    else:
        redeemable_amount = balance_dollar_value
        points_to_redeem = balance
    
    return {
        "loyalty_balance": balance,
        "balance_value": balance_dollar_value,
        "redeemable_amount": redeemable_amount,
        "points_to_redeem": points_to_redeem,
        "max_discount_pct": max_discount_pct,
        "max_discount_amount": max_discount_amount if subtotal > 0 else None,
        "point_value": point_value,
        "logged_in": True,
        "message": f"You have {balance} Roots (${balance_dollar_value:.2f} value)"
    }


@router.post("/account/gift-points")
async def gift_roots_to_friend(data: dict, request: Request):
    """
    Gift Roots (loyalty points) to a friend.
    Per Task 3 spec:
    - Minimum 50 Roots
    - Cannot gift to yourself
    - Creates pending account for new recipients
    - Awards 50 bonus Roots if recipient is new customer
    - Sends WhatsApp + Email notifications
    """
    user = await require_auth(request)
    
    recipient_email = data.get("recipient_email", "").lower().strip()
    points_to_gift = data.get("points", 0)
    personal_message = data.get("message", "").strip()[:200]
    
    # --- Validation ---
    
    # 1. Email required
    if not recipient_email or "@" not in recipient_email:
        raise HTTPException(status_code=400, detail="Valid recipient email is required")
    
    # 2. Minimum 50 Roots
    if points_to_gift < 50:
        raise HTTPException(status_code=400, detail="Minimum gift is 50 Roots")
    
    # 3. Cannot gift to yourself
    sender_email = user.get("email", "").lower()
    if sender_email == recipient_email:
        raise HTTPException(status_code=400, detail="You cannot gift Roots to yourself")
    
    # 4. Check sender balance from both collections
    sender_balance = 0
    balance_source = None
    
    # Check legacy loyalty_points
    points_record = await db.loyalty_points.find_one({"user_id": user["id"]}, {"_id": 0})
    if points_record:
        sender_balance = points_record.get("balance", 0)
        balance_source = "loyalty_points"
    
    # Check new loyalty_members
    if sender_balance == 0:
        member = await db.loyalty_members.find_one({"email": sender_email}, {"_id": 0})
        if member:
            sender_balance = member.get("points", 0)
            balance_source = "loyalty_members"
    
    if sender_balance < points_to_gift:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient balance. You have {sender_balance} Roots."
        )
    
    # --- Find or Create Recipient ---
    
    is_new_customer = False
    recipient_user = await db.users.find_one({"email": recipient_email}, {"_id": 0, "id": 1, "email": 1, "first_name": 1, "phone": 1})
    
    if not recipient_user:
        # Create pending account for new recipient
        is_new_customer = True
        recipient_user = {
            "id": str(uuid.uuid4()),
            "email": recipient_email,
            "account_status": "pending",
            "signup_source": "gift_received",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one({**recipient_user, "_id": None})
        logger.info(f"Created pending account for gift recipient: {recipient_email}")
    else:
        # Check if recipient has placed any orders
        order_count = await db.orders.count_documents({"user_id": recipient_user.get("id")})
        is_new_customer = order_count == 0
    
    # --- Execute Transfer ---
    
    point_value = 0.05  # $0.05 per point
    gift_value = round(points_to_gift * point_value, 2)
    
    # Deduct from sender
    if balance_source == "loyalty_members":
        await db.loyalty_members.update_one(
            {"email": sender_email},
            {"$inc": {"points": -points_to_gift}}
        )
    else:
        await db.loyalty_points.update_one(
            {"user_id": user["id"]},
            {"$inc": {"balance": -points_to_gift}}
        )
    
    # Add to recipient's loyalty_members (using new system)
    await db.loyalty_members.update_one(
        {"email": recipient_email},
        {
            "$inc": {"points": points_to_gift},
            "$setOnInsert": {
                "email": recipient_email,
                "tier": "Standard",
                "totalOrders": 0,
                "lifetimeEarned": 0,
                "joinedAt": datetime.now(timezone.utc)
            }
        },
        upsert=True
    )
    
    # Award bonus for gifting to new customer
    bonus_points = 0
    if is_new_customer:
        bonus_points = 50
        if balance_source == "loyalty_members":
            await db.loyalty_members.update_one(
                {"email": sender_email},
                {"$inc": {"points": bonus_points, "lifetimeEarned": bonus_points}}
            )
        else:
            await db.loyalty_points.update_one(
                {"user_id": user["id"]},
                {"$inc": {"balance": bonus_points, "lifetime_earned": bonus_points}}
            )
    
    # Calculate new sender balance
    new_sender_balance = sender_balance - points_to_gift + bonus_points
    
    # --- Log Transactions ---
    
    sender_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or sender_email.split("@")[0]
    
    # Log sender gift transaction
    await db.loyalty_transactions.insert_one({
        "email": sender_email,
        "type": "gift",
        "points": -points_to_gift,
        "reason": f"Gifted {points_to_gift} Roots to {recipient_email}",
        "recipientEmail": recipient_email,
        "createdAt": datetime.now(timezone.utc),
    })
    
    # Log bonus transaction if applicable
    if bonus_points > 0:
        await db.loyalty_transactions.insert_one({
            "email": sender_email,
            "type": "bonus",
            "points": bonus_points,
            "reason": f"New customer referral bonus — gifted to {recipient_email}",
            "recipientEmail": recipient_email,
            "createdAt": datetime.now(timezone.utc),
        })
    
    # Log recipient transaction
    await db.loyalty_transactions.insert_one({
        "email": recipient_email,
        "type": "gift_received",
        "points": points_to_gift,
        "reason": f"Received {points_to_gift} Roots gift from {sender_name}",
        "senderEmail": sender_email,
        "createdAt": datetime.now(timezone.utc),
    })
    
    # --- Send Notifications ---
    
    try:
        from routes.reroots_p0_fixes import sendgrid_send_email
        from services.twilio_service import send_whatsapp_message
        
        # Get recipient's new balance
        recipient_member = await db.loyalty_members.find_one({"email": recipient_email}, {"_id": 0, "points": 1})
        recipient_balance = recipient_member.get("points", points_to_gift) if recipient_member else points_to_gift
        
        # Sender WhatsApp notification
        sender_phone = user.get("phone")
        if sender_phone:
            bonus_msg = f"\n\n🌟 Bonus! You earned {bonus_points} Roots for\nintroducing a new ReRoots member!\n\nUpdated balance: *{new_sender_balance} Roots* 🎉" if bonus_points > 0 else ""
            
            sender_msg = f"""🎁 Roots Gift Sent, {sender_name.split()[0]}!

You gifted *{points_to_gift} Roots* (${gift_value:.2f})
to {recipient_email} 🌿

Your new balance: *{new_sender_balance} Roots*
(${new_sender_balance * point_value:.2f} value){bonus_msg}"""
            
            await send_whatsapp_message(sender_phone, sender_msg)
        
        # Recipient Email (always send - they may not have WhatsApp)
        recipient_first_name = recipient_user.get("first_name", recipient_email.split("@")[0])
        claim_url = f"https://reroots.ca/signup?gift=true&email={recipient_email}"
        
        recipient_email_html = f"""
        <div style="font-family: 'Cormorant Garamond', Georgia, serif; max-width: 480px; margin: 0 auto; padding: 40px 20px; background: #FDF9F9;">
          <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="font-size: 28px; letter-spacing: 0.3em; color: #2D2A2E; font-weight: 300;">RE<span style="color: #F8A5B8;">ROOTS</span></h1>
            <p style="font-size: 11px; letter-spacing: 0.2em; color: #C4BAC0; text-transform: uppercase;">You Received a Gift!</p>
          </div>
          <div style="background: #fff; border: 1px solid #F0E8E8; border-radius: 12px; padding: 32px; text-align: center;">
            <div style="font-size: 48px; margin-bottom: 16px;">🎁</div>
            <h2 style="font-size: 22px; color: #2D2A2E; font-weight: 300; margin-bottom: 8px;">{sender_name} sent you a gift!</h2>
            <p style="font-size: 14px; color: #8A8490; line-height: 1.7; margin-bottom: 20px;">
              {personal_message if personal_message else f"You received {points_to_gift} Roots from {sender_name}!"}
            </p>
            <div style="background: #FDF9F9; border: 1px solid #F8A5B8; border-radius: 10px; padding: 20px; margin-bottom: 24px;">
              <p style="font-size: 11px; letter-spacing: 0.15em; color: #C4BAC0; text-transform: uppercase; margin-bottom: 8px;">Your Gift</p>
              <p style="font-size: 36px; color: #F8A5B8; font-weight: 600; margin-bottom: 4px;">{points_to_gift} Roots</p>
              <p style="font-size: 16px; color: #2D2A2E; font-weight: 500;">${gift_value:.2f} to use at checkout</p>
            </div>
            <a href="{claim_url}" style="display: inline-block; background: #F8A5B8; color: #fff; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-family: Inter, sans-serif; font-size: 13px; font-weight: 600; letter-spacing: 0.05em;">Claim Your Roots →</a>
            <p style="font-size: 12px; color: #8A8490; margin-top: 20px;">
              Roots expire after 12 months of inactivity.
            </p>
          </div>
          <p style="text-align: center; font-size: 11px; color: #C4BAC0; margin-top: 24px;">
            REROOTS AESTHETICS INC. · TORONTO, CANADA
          </p>
        </div>
        """
        
        await sendgrid_send_email(
            to=recipient_email,
            subject=f"🎁 {sender_name} sent you {points_to_gift} Roots!",
            html_body=recipient_email_html
        )
        
        # Recipient WhatsApp (if phone on file)
        recipient_phone = recipient_user.get("phone")
        if recipient_phone:
            recipient_msg = f"""🎁 You just received a gift!

{sender_name.split()[0]} sent you *{points_to_gift} Roots*
= ${gift_value:.2f} to use at reroots.ca

Your balance: *{recipient_balance} Roots* 🌿

Use them at checkout for up to 30% off!
reroots.ca"""
            
            await send_whatsapp_message(recipient_phone, recipient_msg)
        
        logger.info(f"Gift notifications sent for {points_to_gift} Roots from {sender_email} to {recipient_email}")
        
        # Task 6: Create wa.me CRM actions for admin panel
        try:
            from routes.whatsapp_templates import notify_gift_sent, notify_gift_received
            
            # Sender notification
            if sender_phone:
                sender_data = {
                    'email': sender_email,
                    'first_name': user.get('first_name', ''),
                    'last_name': user.get('last_name', ''),
                    'phone': sender_phone
                }
                await notify_gift_sent(db, sender_data, points_to_gift, recipient_email, new_sender_balance, is_new_customer)
            
            # Recipient notification
            if recipient_phone:
                recipient_data = {
                    'email': recipient_email,
                    'first_name': recipient_user.get('first_name', ''),
                    'last_name': recipient_user.get('last_name', ''),
                    'phone': recipient_phone
                }
                await notify_gift_received(db, recipient_data, points_to_gift, recipient_balance)
        except Exception as wa_err:
            logger.debug(f"wa.me gift action creation skipped: {wa_err}")
        
    except Exception as e:
        logger.warning(f"Gift notification error: {e}")
    
    return {
        "success": True,
        "points_gifted": points_to_gift,
        "gift_value": gift_value,
        "new_sender_balance": new_sender_balance,
        "bonus_earned": bonus_points,
        "recipient_is_new": is_new_customer,
        "message": f"Successfully gifted {points_to_gift} Roots to {recipient_email}!"
    }


# ============================================================
# TASK 4: Reviews Module Endpoints
# ============================================================

@router.get("/review/{token}")
async def get_review_form_data(token: str):
    """Get review request data for the review form page."""
    from routes.reviews_module import get_review_request_by_token, GOOGLE_REVIEW_LINK
    
    request_record = await get_review_request_by_token(db, token)
    
    if not request_record:
        raise HTTPException(status_code=404, detail="This review link has expired or already been used.")
    
    return {
        "valid": True,
        "customer_name": request_record.get("customer_name", ""),
        "product_name": "AURA-GEN PDRN+TXA Serum",
        "token": token,
        "google_review_link": GOOGLE_REVIEW_LINK
    }


@router.post("/reviews/submit")
async def submit_review_endpoint(data: dict):
    """Submit a review and earn 100 Roots."""
    from routes.reviews_module import submit_review
    
    token = data.get("token", "")
    rating = int(data.get("rating", 0))
    headline = data.get("headline", "")
    body = data.get("body", "")
    
    result = await submit_review(db, token, rating, headline, body)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Submission failed"))
    
    return result


@router.get("/admin/reviews")
async def admin_get_reviews(request: Request, status: str = "pending", skip: int = 0, limit: int = 50):
    """Get all reviews for admin panel."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from routes.reviews_module import get_admin_reviews
    return await get_admin_reviews(db, status, skip, limit)


@router.post("/admin/reviews/{token}/approve")
async def admin_approve_review(token: str, request: Request):
    """Approve a review for display on site."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from routes.reviews_module import approve_review
    result = await approve_review(db, token)
    
    if not result.get("success"):
        raise HTTPException(status_code=404, detail="Review not found")
    
    return result


@router.post("/admin/reviews/{token}/reject")
async def admin_reject_review(token: str, request: Request):
    """Reject a review."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from routes.reviews_module import reject_review
    result = await reject_review(db, token)
    
    if not result.get("success"):
        raise HTTPException(status_code=404, detail="Review not found")
    
    return result


@router.post("/admin/reviews/trigger-day21")
async def admin_trigger_day21_reviews(request: Request):
    """Manually trigger Day 21 review requests (for testing)."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from routes.reviews_module import check_day21_review_requests
    count = await check_day21_review_requests(db)
    
    return {"success": True, "review_requests_created": count}


# ============================================================
# TASK 5: WhatsApp Templates Endpoints
# ============================================================

@router.get("/admin/whatsapp-templates")
async def get_whatsapp_templates(request: Request):
    """Get all WhatsApp templates for admin panel."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from routes.whatsapp_templates import get_all_whatsapp_templates, initialize_whatsapp_templates
    
    # Initialize templates if they don't exist
    await initialize_whatsapp_templates(db)
    
    templates = await get_all_whatsapp_templates(db)
    return {"templates": templates, "total": len(templates)}


@router.put("/admin/whatsapp-templates/{key}")
async def update_whatsapp_template_endpoint(key: str, data: dict, request: Request):
    """Update a WhatsApp template."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from routes.whatsapp_templates import update_whatsapp_template
    
    # Only allow updating specific fields
    allowed_fields = {"whatsapp", "email_subject", "active", "name"}
    updates = {k: v for k, v in data.items() if k in allowed_fields}
    
    success = await update_whatsapp_template(db, key, updates)
    
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {"success": True}


@router.post("/admin/whatsapp-templates/send-test")
async def send_test_whatsapp_template(data: dict, request: Request):
    """Send a test WhatsApp message with a template."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from routes.whatsapp_templates import render_template, get_whatsapp_template
    from services.twilio_service import send_whatsapp_message
    
    template_key = data.get("template_key")
    phone = data.get("phone")
    
    if not template_key or not phone:
        raise HTTPException(status_code=400, detail="template_key and phone required")
    
    template = await get_whatsapp_template(db, template_key)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Render with test data
    test_data = {
        "name": user.get("first_name", "Test User"),
        "loyalty_balance": 250,
        "review_url": "https://reroots.ca/review/test-token",
        "discount_code": "TEST20",
        "discount_pct": 20
    }
    
    message = render_template(template["whatsapp"], test_data)
    result = await send_whatsapp_message(phone, message)
    
    return {"success": True, "message_preview": message[:200] + "..."}


@router.post("/admin/whatsapp-templates/trigger-day/{day}")
async def trigger_day_messages(day: int, request: Request):
    """Manually trigger messages for a specific day (for testing)."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if day not in [0, 7, 14, 21, 25, 28, 35]:
        raise HTTPException(status_code=400, detail="Invalid day. Must be 0, 7, 14, 21, 25, 28, or 35")
    
    from routes.whatsapp_templates import check_day_messages
    count = await check_day_messages(db, day)
    
    return {"success": True, "messages_sent": count}


@router.post("/whatsapp/send-alert")
async def send_low_stock_whatsapp_alert(request: Request, data: dict = Body(...)):
    """Send low stock alert to admin via WhatsApp."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    message = data.get("message", "")
    alert_type = data.get("alert_type", "low_stock")
    product_id = data.get("product_id", "")
    
    if not message:
        raise HTTPException(status_code=400, detail="Message required")
    
    # Get admin phone from environment
    admin_phone = os.environ.get("ADMIN_PHONE_NUMBER")
    if not admin_phone:
        # Log but don't fail - return success so frontend continues
        print(f"[LOW_STOCK_ALERT] No ADMIN_PHONE_NUMBER configured. Alert: {message[:100]}")
        return {"success": True, "sent": False, "reason": "No admin phone configured"}
    
    try:
        result = await send_whatsapp_message(admin_phone, message)
        
        # Log the alert
        await db.admin_alerts.insert_one({
            "type": alert_type,
            "product_id": product_id,
            "message": message,
            "sent_to": admin_phone,
            "success": result.get("success", False),
            "created_at": datetime.now(timezone.utc)
        })
        
        return {"success": True, "sent": result.get("success", False)}
    except Exception as e:
        print(f"[LOW_STOCK_ALERT] Error sending: {e}")
        return {"success": True, "sent": False, "error": str(e)}


# ============================================================
# TASK 5: CRM Actions (WhatsApp wa.me Links) Endpoints
# ============================================================

@router.get("/admin/crm-actions")
async def get_crm_actions(request: Request, status: str = "pending", limit: int = 50):
    """Get pending WhatsApp CRM actions for admin to send via wa.me links."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from routes.whatsapp_templates import get_pending_whatsapp_actions, get_whatsapp_stats
    
    if status == "pending":
        actions = await get_pending_whatsapp_actions(db, limit)
    else:
        # Get all actions or specific status
        query = {'type': 'whatsapp'}
        if status != 'all':
            query['status'] = status
        actions = await db.crm_actions.find(query, {'_id': 0}).sort('created_at', -1).limit(limit).to_list(limit)
    
    # Get stats
    stats = await get_whatsapp_stats(db)
    
    return {
        "actions": actions,
        "total": len(actions),
        "stats": stats
    }


@router.post("/admin/crm-actions/{order_id}/day/{day}/sent")
async def mark_crm_action_sent(order_id: str, day: int, request: Request):
    """Mark a WhatsApp CRM action as sent (admin clicked the wa.me link)."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from routes.whatsapp_templates import mark_whatsapp_sent
    success = await mark_whatsapp_sent(db, order_id, day)
    
    if not success:
        raise HTTPException(status_code=404, detail="Action not found")
    
    return {"success": True, "message": f"Day {day} message marked as sent"}


@router.post("/admin/crm-actions/run-scheduler")
async def run_crm_scheduler(request: Request, day: int = None):
    """Manually run the CRM actions scheduler for all days or a specific day."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from routes.whatsapp_templates import check_day_messages
    
    days_to_check = [day] if day else [0, 7, 14, 21, 25, 28, 35]
    results = {}
    
    for d in days_to_check:
        count = await check_day_messages(db, d)
        results[f"day_{d}"] = count
    
    return {
        "success": True,
        "results": results,
        "total_actions_created": sum(results.values())
    }


@router.delete("/admin/crm-actions/{order_id}/day/{day}")
async def delete_crm_action(order_id: str, day: int, request: Request):
    """Delete a CRM action (admin decided not to send)."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.crm_actions.delete_one({
        'order_id': order_id,
        'day': day,
        'type': 'whatsapp'
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Action not found")
    
    return {"success": True, "message": "Action deleted"}


# Task 6: Endpoints for loyalty notification actions (by action_id)
@router.post("/admin/crm-actions/action/{action_id}/sent")
async def mark_action_sent_by_id(action_id: str, request: Request):
    """Mark a CRM action as sent by its action_id (for loyalty notifications)."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.crm_actions.update_one(
        {'action_id': action_id, 'status': 'pending'},
        {'$set': {'status': 'sent', 'sent_at': datetime.now(timezone.utc)}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Action not found or already sent")
    
    return {"success": True, "message": "Action marked as sent"}


@router.delete("/admin/crm-actions/action/{action_id}")
async def delete_action_by_id(action_id: str, request: Request):
    """Delete a CRM action by its action_id (for loyalty notifications)."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.crm_actions.delete_one({'action_id': action_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Action not found")
    
    return {"success": True, "message": "Action deleted"}


# ============================================================
# AUTO-HEAL MONITOR API ENDPOINTS
# ============================================================

from services.auto_heal import run_all_health_checks, get_auto_heal_logs

@router.get("/admin/auto-heal/status")
async def get_auto_heal_status(request: Request):
    """Get current auto-heal status and last run info."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get last 10 logs
    logs = await get_auto_heal_logs(limit=10)
    
    return {
        "success": True,
        "status": "running",
        "check_interval_minutes": 10,
        "recent_logs": logs
    }


@router.post("/admin/auto-heal/run")
async def trigger_auto_heal(request: Request):
    """Manually trigger all auto-heal health checks."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    results = await run_all_health_checks()
    return {
        "success": True,
        "results": results
    }


@router.get("/admin/auto-heal/logs")
async def get_auto_heal_logs_endpoint(request: Request, limit: int = 50):
    """Get auto-heal action logs."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    logs = await get_auto_heal_logs(limit=limit)
    return {
        "success": True,
        "logs": logs,
        "count": len(logs)
    }


# ============================================================
# TASK 7: BIRTHDAY + REFERRAL BONUS API ENDPOINTS
# ============================================================

@router.post("/admin/loyalty/trigger-birthday-check")
async def trigger_birthday_check(request: Request):
    """Manual trigger for birthday bonus check (for developer testing)."""
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    from routes.loyalty_bonuses import check_birthday_bonuses, set_db as set_bonus_db
    set_bonus_db(db)
    
    result = await check_birthday_bonuses()
    return result


@router.post("/admin/loyalty/trigger-referral-bonus")
async def trigger_referral_bonus(data: dict, request: Request):
    """
    Manual referral bonus trigger (for edge cases).
    Body: { referrer_id, referred_email }
    """
    user = await get_current_user(request)
    if not user or not (user.get("role") == "admin" or user.get("is_admin") == True):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    referrer_id = data.get("referrer_id")
    referred_email = data.get("referred_email")
    
    if not referrer_id or not referred_email:
        raise HTTPException(status_code=400, detail="referrer_id and referred_email are required")
    
    from routes.loyalty_bonuses import on_referral_first_purchase, set_db as set_bonus_db
    set_bonus_db(db)
    
    result = await on_referral_first_purchase(referrer_id, referred_email)
    return result


@router.post("/loyalty/points/claim-pending")
async def claim_pending_points(request: Request):
    """Claim any pending points when user creates account or logs in"""
    user = await require_auth(request)

    # Find pending points for this email
    pending = await db.pending_points.find(
        {"email": user["email"].lower()}, {"_id": 0}
    ).to_list(100)

    if not pending:
        return {"message": "No pending points", "points_claimed": 0}

    total_points = 0
    for record in pending:
        points = record.get("points", 0)
        total_points += points

        # Add to user's balance
        history_entry = {
            "id": str(uuid.uuid4()),
            "type": "earned",
            "points": points,
            "description": f"Claimed from order #{record.get('order_id', 'unknown')[:8]}",
            "order_id": record.get("order_id"),
            "date": datetime.now(timezone.utc).isoformat(),
        }

        await db.loyalty_points.update_one(
            {"user_id": user["id"]},
            {
                "$inc": {"balance": points, "lifetime_earned": points},
                "$push": {"history": history_entry},
                "$setOnInsert": {
                    "id": str(uuid.uuid4()),
                    "user_id": user["id"],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            },
            upsert=True,
        )

    # Delete pending records
    await db.pending_points.delete_many({"email": user["email"].lower()})

    logger.info(f"User {user['id']} claimed {total_points} pending points")

    return {
        "message": f"Claimed {total_points} ReRoots Points!",
        "points_claimed": total_points,
        "value": round(total_points * POINT_VALUE, 2),
    }


@router.get("/admin/loyalty/stats")
async def get_loyalty_stats(request: Request):
    """Admin: Get loyalty program statistics"""
    await require_admin(request)

    # Total points in circulation
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_balance": {"$sum": "$balance"},
                "total_earned": {"$sum": "$lifetime_earned"},
                "total_redeemed": {"$sum": "$lifetime_redeemed"},
                "users_with_points": {"$sum": 1},
            }
        }
    ]

    stats = await db.loyalty_points.aggregate(pipeline).to_list(1)

    if stats:
        s = stats[0]
        return {
            "total_points_in_circulation": s.get("total_balance", 0),
            "total_points_earned": s.get("total_earned", 0),
            "total_points_redeemed": s.get("total_redeemed", 0),
            "users_with_points": s.get("users_with_points", 0),
            "liability": round(s.get("total_balance", 0) * POINT_VALUE, 2),
            "points_per_product": POINTS_PER_PRODUCT,
            "point_value": POINT_VALUE,
        }

    return {
        "total_points_in_circulation": 0,
        "total_points_earned": 0,
        "total_points_redeemed": 0,
        "users_with_points": 0,
        "liability": 0,
        "points_per_product": POINTS_PER_PRODUCT,
        "point_value": POINT_VALUE,
    }


# ============================================
# ENHANCED REWARDS & REFERRAL SYSTEM
# Daily Login + Referral Points
# ============================================


@router.get("/rewards/profile")
async def get_rewards_profile(request: Request):
    """Get user's complete rewards profile including daily login and referral stats"""
    user = await get_current_user(request)
    if not user:
        return {
            "points_balance": 0,
            "login_streak": 0,
            "referral_code": None,
            "total_referrals": 0,
            "successful_referrals": 0,
            "milestones_achieved": [],
            "next_milestone": {
                "type": "login",
                "current": 0,
                "target": 10,
                "reward": "$5 discount",
            },
        }

    # Get loyalty points (check both collections)
    loyalty_record = await db.loyalty_points.find_one({"user_id": user["id"]}, {"_id": 0})
    loyalty_balance = loyalty_record.get("balance", 0) if loyalty_record else 0
    
    # Also check loyalty_members collection (new system)
    if loyalty_balance == 0:
        member_record = await db.loyalty_members.find_one({"email": user.get("email")}, {"_id": 0})
        if member_record:
            loyalty_balance = member_record.get("points", 0)

    # Get or create rewards profile
    profile = await db.rewards_profiles.find_one({"user_id": user["id"]}, {"_id": 0})

    if not profile:
        # Create new profile with referral code
        referral_code = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=8))
        profile = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "email": user["email"],
            "points_balance": 0,
            "lifetime_points_earned": 0,
            "lifetime_points_redeemed": 0,
            "login_streak": 0,
            "last_login_date": None,
            "total_logins": 0,
            "referral_code": referral_code,
            "total_referrals": 0,
            "successful_referrals": 0,
            "milestones_achieved": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.rewards_profiles.insert_one(profile)

    # Calculate next milestone
    login_count = profile.get("total_logins", 0)
    referral_count = profile.get("successful_referrals", 0)

    next_milestone = None
    if login_count < LOGIN_MILESTONE:
        next_milestone = {
            "type": "login",
            "current": login_count,
            "target": LOGIN_MILESTONE,
            "reward": "$5 discount",
            "description": f"Log in {LOGIN_MILESTONE - login_count} more days to unlock $5 off!",
        }
    elif referral_count < REFERRAL_MILESTONE:
        next_milestone = {
            "type": "referral",
            "current": referral_count,
            "target": REFERRAL_MILESTONE,
            "reward": "30% discount",
            "description": f"Refer {REFERRAL_MILESTONE - referral_count} more friends for 30% off!",
        }
    else:
        next_milestone = {
            "type": "complete",
            "current": 0,
            "target": 0,
            "reward": "VIP Status",
            "description": "You've achieved all milestones! Enjoy VIP benefits.",
        }

    # Get recent points transactions
    transactions = (
        await db.points_transactions.find({"user_id": user["id"]})
        .sort("created_at", -1)
        .limit(10)
        .to_list(10)
    )

    for t in transactions:
        if "_id" in t:
            del t["_id"]

    return {
        "points_balance": loyalty_balance or profile.get("points_balance", 0),  # Use loyalty_points first
        "points_value": round((loyalty_balance or profile.get("points_balance", 0)) * 0.05, 2),
        "login_streak": profile.get("login_streak", 0),
        "total_logins": profile.get("total_logins", 0),
        "last_login_date": profile.get("last_login_date"),
        "referral_code": profile.get("referral_code"),
        "total_referrals": profile.get("total_referrals", 0),
        "successful_referrals": profile.get("successful_referrals", 0),
        "milestones_achieved": profile.get("milestones_achieved", []),
        "lifetime_points_earned": profile.get("lifetime_points_earned", 0),
        "lifetime_points_redeemed": profile.get("lifetime_points_redeemed", 0),
        "next_milestone": next_milestone,
        "recent_transactions": transactions,
    }


@router.post("/rewards/daily-login")
async def record_daily_login(request: Request):
    """Daily login points feature - DISABLED"""
    return {
        "message": "Daily login points feature is disabled",
        "points_awarded": 0,
        "already_claimed": True,
        "feature_disabled": True
    }


@router.post("/rewards/track-referral-click")
async def track_referral_click(data: dict, request: Request):
    """Track when a referral link is clicked"""
    referral_code = data.get("referral_code", "").upper().strip()
    program_type = data.get("program_type", "general")

    if not referral_code:
        raise HTTPException(status_code=400, detail="Referral code required")

    # Find the referrer
    referrer = await db.rewards_profiles.find_one(
        {"referral_code": referral_code}, {"_id": 0}
    )

    if not referrer:
        # Try influencer codes
        influencer = await db.influencer_applications.find_one(
            {"partner_code": referral_code}, {"_id": 0}
        )
        if influencer:
            referrer = {"user_id": influencer.get("id"), "referral_code": referral_code}

    if not referrer:
        raise HTTPException(status_code=404, detail="Invalid referral code")

    # Hash IP for deduplication (don't store raw IPs)
    client_ip = request.client.host if request.client else "unknown"
    ip_hash = hashlib.sha256(
        f"{client_ip}{referral_code}{datetime.now(timezone.utc).strftime('%Y-%m-%d')}".encode()
    ).hexdigest()

    # Check for duplicate click today
    existing = await db.referral_clicks.find_one({"ip_hash": ip_hash}, {"_id": 0})
    if existing:
        return {"message": "Click already recorded", "duplicate": True}

    # Record the click
    click_record = {
        "id": str(uuid.uuid4()),
        "referral_code": referral_code,
        "referrer_user_id": referrer.get("user_id"),
        "program_type": program_type,
        "clicked_at": datetime.now(timezone.utc).isoformat(),
        "ip_hash": ip_hash,
        "user_agent": request.headers.get("user-agent", "")[:200],
        "converted": False,
        "conversion_order_id": None,
    }

    await db.referral_clicks.insert_one(click_record)

    # Increment click counter on profile
    await db.rewards_profiles.update_one(
        {"referral_code": referral_code}, {"$inc": {"total_referrals": 1}}
    )

    return {"message": "Click tracked", "click_id": click_record["id"]}


@router.post("/rewards/record-referral-conversion")
async def record_referral_conversion(data: dict, request: Request):
    """Record a referral conversion (purchase made via referral)"""
    referral_code = data.get("referral_code", "").upper().strip()
    order_id = data.get("order_id")
    order_total = data.get("order_total", 0)
    referee_email = data.get("referee_email", "")

    if not referral_code or not order_id:
        raise HTTPException(
            status_code=400, detail="Referral code and order ID required"
        )

    # Find the referrer
    referrer = await db.rewards_profiles.find_one(
        {"referral_code": referral_code}, {"_id": 0}
    )

    if not referrer:
        return {"message": "Referrer not found", "points_awarded": 0}

    # Check if already converted
    existing = await db.referral_conversions.find_one(
        {"order_id": order_id}, {"_id": 0}
    )
    if existing:
        return {"message": "Conversion already recorded", "duplicate": True}

    # Record conversion
    conversion_record = {
        "id": str(uuid.uuid4()),
        "referral_code": referral_code,
        "referrer_user_id": referrer.get("user_id"),
        "referee_email": referee_email,
        "order_id": order_id,
        "order_total": order_total,
        "points_awarded": POINTS_PER_REFERRAL,
        "commission_earned": 0.0,
        "program_type": "general",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.referral_conversions.insert_one(conversion_record)

    # Award points to referrer
    new_points = referrer.get("points_balance", 0) + POINTS_PER_REFERRAL
    new_successful = referrer.get("successful_referrals", 0) + 1
    new_lifetime = referrer.get("lifetime_points_earned", 0) + POINTS_PER_REFERRAL

    # Check for milestone
    milestones = referrer.get("milestones_achieved", [])
    milestone_achieved = None

    if new_successful == REFERRAL_MILESTONE and "10_referrals" not in milestones:
        milestones.append("10_referrals")
        milestone_achieved = {
            "type": "10_referrals",
            "name": "Referral Champion",
            "reward": "30% discount",
            "discount_code": "REFER30VIP",
        }
        # Create 30% discount code
        await db.user_rewards.insert_one(
            {
                "id": str(uuid.uuid4()),
                "user_id": referrer.get("user_id"),
                "type": "discount",
                "code": "REFER30VIP",
                "value": 30.0,
                "value_type": "percentage",
                "reason": "10 Referrals Milestone",
                "used": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    await db.rewards_profiles.update_one(
        {"referral_code": referral_code},
        {
            "$set": {
                "points_balance": new_points,
                "successful_referrals": new_successful,
                "lifetime_points_earned": new_lifetime,
                "milestones_achieved": milestones,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    # Record transaction
    await db.points_transactions.insert_one(
        {
            "id": str(uuid.uuid4()),
            "user_id": referrer.get("user_id"),
            "action": "referral_conversion",
            "points": POINTS_PER_REFERRAL,
            "description": f"Referral conversion - Order ${order_total:.2f}",
            "reference_id": order_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    return {
        "message": f"Conversion recorded! Referrer earned {POINTS_PER_REFERRAL} points",
        "points_awarded": POINTS_PER_REFERRAL,
        "milestone_achieved": milestone_achieved,
    }


@router.get("/rewards/referral-link/{program_type}")
async def get_referral_link(program_type: str, request: Request):
    """Get personalized referral link for a specific program"""
    user = await get_current_user(request)

    base_url = os.environ.get("FRONTEND_URL")

    program_paths = {
        "general": "/shop",
        "influencer": "/partner",
        "founder": "/founding-member",
        "quiz": "/skin-quiz",
        "bioAgeScan": "/bio-scan",
        "comparison": "/compare",
    }

    path = program_paths.get(program_type, "/shop")

    if not user:
        # Return generic link for non-logged-in users
        return {
            "link": f"{base_url}{path}",
            "referral_code": None,
            "program_type": program_type,
        }

    # Get user's referral code
    profile = await db.rewards_profiles.find_one({"user_id": user["id"]}, {"_id": 0})

    if not profile:
        # Create profile with referral code
        referral_code = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=8))
        profile = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "email": user["email"],
            "points_balance": 0,
            "referral_code": referral_code,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.rewards_profiles.insert_one(profile)
    else:
        referral_code = profile.get("referral_code")

    return {
        "link": f"{base_url}{path}?ref={referral_code}",
        "referral_code": referral_code,
        "program_type": program_type,
    }


@router.get("/admin/program-analytics")
async def get_program_analytics(request: Request):
    """Get analytics for all programs (admin only)"""
    await require_admin(request)

    # Influencer stats
    influencer_clicks = await db.referral_clicks.count_documents(
        {"program_type": "influencer"}
    )
    influencer_conversions = await db.referral_conversions.count_documents(
        {"program_type": "influencer"}
    )
    influencer_pipeline = [
        {"$match": {"program_type": "influencer"}},
        {"$group": {"_id": None, "total": {"$sum": "$order_total"}}},
    ]
    influencer_revenue = await db.referral_conversions.aggregate(
        influencer_pipeline
    ).to_list(1)
    active_influencers = await db.influencer_applications.count_documents(
        {"status": "approved"}
    )

    # Founder stats
    founder_count = await db.rewards_profiles.count_documents(
        {"milestones_achieved": "10_referrals"}
    )
    founder_points_pipeline = [
        {
            "$group": {
                "_id": None,
                "issued": {"$sum": "$lifetime_points_earned"},
                "redeemed": {"$sum": "$lifetime_points_redeemed"},
            }
        }
    ]
    founder_points = await db.rewards_profiles.aggregate(
        founder_points_pipeline
    ).to_list(1)

    # Quiz stats
    quiz_completions = await db.bio_scans.count_documents({})
    quiz_emails = await db.bio_scans.count_documents({"email": {"$ne": ""}})

    # Bio scan stats
    bio_scans = await db.bio_scans.count_documents({})
    bio_emails = await db.bio_scans.count_documents({"email": {"$ne": ""}})

    # Comparison stats (using referral clicks with comparison type)
    comparison_uses = await db.referral_clicks.count_documents(
        {"program_type": "comparison"}
    )

    return {
        "influencer": {
            "totalReferrals": influencer_clicks,
            "conversions": influencer_conversions,
            "clicks": influencer_clicks,
            "earnings": (
                influencer_revenue[0].get("total", 0) if influencer_revenue else 0
            ),
            "activeUsers": active_influencers,
        },
        "founder": {
            "totalMembers": founder_count,
            "redemptions": 0,
            "pointsIssued": founder_points[0].get("issued", 0) if founder_points else 0,
            "pointsRedeemed": (
                founder_points[0].get("redeemed", 0) if founder_points else 0
            ),
        },
        "quiz": {
            "completions": quiz_completions,
            "emailsCaptured": quiz_emails,
            "discountsUsed": 0,
            "conversionRate": round((quiz_emails / max(quiz_completions, 1)) * 100, 1),
        },
        "bioAgeScan": {
            "scansCompleted": bio_scans,
            "emailsCaptured": bio_emails,
            "discountsUsed": 0,
            "avgBioAge": 32,
        },
        "comparison": {
            "comparisons": comparison_uses,
            "productsCompared": comparison_uses * 3,
            "addToCartRate": 23,
        },
    }


@router.get("/admin/referral-tracking")
async def get_referral_tracking(request: Request):
    """Get detailed referral tracking data for admin"""
    await require_admin(request)

    # Get top referrers
    pipeline = [
        {
            "$group": {
                "_id": "$referral_code",
                "clicks": {"$sum": 1},
                "conversions": {"$sum": {"$cond": ["$converted", 1, 0]}},
            }
        },
        {"$sort": {"clicks": -1}},
        {"$limit": 20},
    ]

    referral_stats = await db.referral_clicks.aggregate(pipeline).to_list(20)

    # Get profiles for these codes
    referrals = []
    for stat in referral_stats:
        code = stat.get("_id")
        profile = await db.rewards_profiles.find_one(
            {"referral_code": code}, {"_id": 0}
        )

        if profile:
            # Calculate earnings from conversions
            earnings_pipeline = [
                {"$match": {"referral_code": code}},
                {"$group": {"_id": None, "total": {"$sum": "$order_total"}}},
            ]
            earnings = await db.referral_conversions.aggregate(
                earnings_pipeline
            ).to_list(1)

            referrals.append(
                {
                    "id": profile.get("id"),
                    "name": profile.get("email", "Unknown").split("@")[0].title(),
                    "code": code,
                    "clicks": stat.get("clicks", 0),
                    "conversions": stat.get("conversions", 0),
                    "earnings": round(
                        (earnings[0].get("total", 0) if earnings else 0) * 0.1, 2
                    ),  # 10% commission
                    "status": "active",
                }
            )

    return {"referrals": referrals}


@router.get("/admin/points-history")
async def get_points_history(request: Request):
    """Get recent points transactions for admin"""
    await require_admin(request)

    transactions = (
        await db.points_transactions.find({})
        .sort("created_at", -1)
        .limit(50)
        .to_list(50)
    )

    history = []
    for t in transactions:
        # Get user email
        profile = await db.rewards_profiles.find_one(
            {"user_id": t.get("user_id")}, {"_id": 0}
        )

        history.append(
            {
                "id": t.get("id"),
                "user": profile.get("email", "Unknown") if profile else "Unknown",
                "action": t.get("action", "").replace("_", " ").title(),
                "points": t.get("points", 0),
                "date": t.get("created_at", "")[:10],
            }
        )

    return {"history": history}


@router.get("/rewards/user-rewards")
async def get_user_rewards(request: Request):
    """Get user's available reward codes and discounts"""
    user = await require_auth(request)

    rewards = await db.user_rewards.find(
        {"user_id": user["id"], "used": False}
    ).to_list(20)

    for r in rewards:
        if "_id" in r:
            del r["_id"]

    return {"rewards": rewards}


# ============================================
# GIFT POINTS SYSTEM
# Send & Receive Points Between Users
# ============================================

# Points pricing: $1 = 20 points
POINTS_PER_DOLLAR = 20

@router.post("/rewards/buy-points")
async def buy_points(data: dict, request: Request):
    """Purchase points with Bambora payment - $1 = 20 points"""
    import httpx
    
    user = await require_auth(request)
    
    dollar_amount = data.get("amount", 0)
    card_number = data.get("card_number", "").replace(" ", "").replace("-", "")
    expiry_month = data.get("expiry_month", "")
    expiry_year = data.get("expiry_year", "")
    cvv = data.get("cvv", "")
    cardholder_name = data.get("cardholder_name", "")
    
    if dollar_amount < 1:
        raise HTTPException(status_code=400, detail="Minimum purchase is $1")
    
    if dollar_amount > 1000:
        raise HTTPException(status_code=400, detail="Maximum purchase is $1000")
    
    # Validate card details
    if not all([card_number, expiry_month, expiry_year, cvv, cardholder_name]):
        raise HTTPException(status_code=400, detail="All card details are required")
    
    points_to_add = int(dollar_amount * POINTS_PER_DOLLAR)
    
    # Check if Bambora is configured
    if not BAMBORA_MERCHANT_ID or not BAMBORA_API_PASSCODE:
        raise HTTPException(status_code=500, detail="Payment processing not configured")
    
    try:
        # Prepare Bambora API authentication
        credentials = f"{BAMBORA_MERCHANT_ID}:{BAMBORA_API_PASSCODE}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Passcode {encoded_credentials}",
            "Content-Type": "application/json",
        }
        
        # Prepare payment payload
        order_number = f"PTS-{str(uuid.uuid4())[:8].upper()}"
        payload = {
            "payment_method": "card",
            "order_number": order_number,
            "amount": float(dollar_amount),
            "card": {
                "name": cardholder_name,
                "number": card_number,
                "expiry_month": str(expiry_month).zfill(2),
                "expiry_year": str(expiry_year)[-2:],
                "cvd": cvv,
                "complete": True,
            },
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BAMBORA_API_URL}/payments",
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            
            response_data = response.json()
            logging.info(f"Bambora points purchase response: {response.status_code} - {response_data}")
            
            if response.status_code == 200 and response_data.get("approved") == 1:
                # Payment successful - add points
                transaction_id = response_data.get("id", "")
                
                # Get or create rewards profile
                profile = await db.rewards_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
                
                if not profile:
                    referral_code = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=8))
                    profile = {
                        "id": str(uuid.uuid4()),
                        "user_id": user["id"],
                        "email": user["email"],
                        "points_balance": 0,
                        "lifetime_points_earned": 0,
                        "lifetime_points_redeemed": 0,
                        "referral_code": referral_code,
                        "total_referrals": 0,
                        "successful_referrals": 0,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                    await db.rewards_profiles.insert_one(profile)
                
                # Update points balance
                new_balance = profile.get("points_balance", 0) + points_to_add
                new_lifetime = profile.get("lifetime_points_earned", 0) + points_to_add
                
                await db.rewards_profiles.update_one(
                    {"user_id": user["id"]},
                    {
                        "$set": {
                            "points_balance": new_balance,
                            "lifetime_points_earned": new_lifetime,
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                )
                
                # Record transaction
                purchase_id = str(uuid.uuid4())
                await db.points_transactions.insert_one({
                    "id": purchase_id,
                    "user_id": user["id"],
                    "action": "points_purchase",
                    "points": points_to_add,
                    "amount_paid": dollar_amount,
                    "bambora_transaction_id": transaction_id,
                    "description": f"Purchased {points_to_add} points for ${dollar_amount}",
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                
                # Record in purchases collection
                await db.points_purchases.insert_one({
                    "id": purchase_id,
                    "user_id": user["id"],
                    "email": user["email"],
                    "dollar_amount": dollar_amount,
                    "points_purchased": points_to_add,
                    "rate": POINTS_PER_DOLLAR,
                    "bambora_transaction_id": transaction_id,
                    "order_number": order_number,
                    "status": "completed",
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                
                return {
                    "success": True,
                    "points_purchased": points_to_add,
                    "amount_paid": dollar_amount,
                    "new_balance": new_balance,
                    "transaction_id": transaction_id,
                    "message": f"Successfully purchased {points_to_add} points!"
                }
            else:
                # Payment failed
                error_message = response_data.get("message", "Payment declined")
                logging.error(f"Points purchase failed: {error_message}")
                raise HTTPException(status_code=400, detail=f"Payment failed: {error_message}")
                
    except httpx.RequestError as e:
        logging.error(f"Bambora request error: {str(e)}")
        raise HTTPException(status_code=500, detail="Payment service unavailable")


@router.get("/rewards/points-pricing")
async def get_points_pricing():
    """Get current points pricing"""
    return {
        "rate": POINTS_PER_DOLLAR,
        "currency": "USD",
        "packages": [
            {"dollars": 5, "points": 5 * POINTS_PER_DOLLAR, "label": "Starter"},
            {"dollars": 10, "points": 10 * POINTS_PER_DOLLAR, "label": "Popular"},
            {"dollars": 25, "points": 25 * POINTS_PER_DOLLAR, "label": "Value"},
            {"dollars": 50, "points": 50 * POINTS_PER_DOLLAR, "label": "Best Deal"}
        ]
    }


@router.post("/rewards/gift-points")
async def gift_points(data: dict, request: Request):
    """Send points as a gift to another user by email"""
    user = await require_auth(request)
    
    recipient_email = data.get("recipient_email", "").lower().strip()
    points_amount = data.get("points", 0)
    message = data.get("message", "").strip()[:200]  # Limit message length
    
    if not recipient_email:
        raise HTTPException(status_code=400, detail="Recipient email is required")
    
    if points_amount < 60:
        raise HTTPException(status_code=400, detail="Minimum gift is 60 points")
    
    if recipient_email == user["email"].lower():
        raise HTTPException(status_code=400, detail="Cannot gift points to yourself")
    
    # Get sender's rewards profile
    sender_profile = await db.rewards_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
    if not sender_profile:
        raise HTTPException(status_code=400, detail="No rewards profile found")
    
    if sender_profile.get("points_balance", 0) < points_amount:
        raise HTTPException(status_code=400, detail="Insufficient points balance")
    
    # Check if recipient exists
    recipient_user = await db.users.find_one({"email": recipient_email}, {"_id": 0, "id": 1, "email": 1, "first_name": 1})
    
    # Create gift record (stores valuable data about who gifts to whom)
    gift_id = str(uuid.uuid4())
    gift_record = {
        "id": gift_id,
        "sender_id": user["id"],
        "sender_email": user["email"],
        "sender_name": user.get("first_name", "A friend"),
        "recipient_email": recipient_email,
        "recipient_id": recipient_user["id"] if recipient_user else None,
        "points": points_amount,
        "message": message,
        "status": "completed" if recipient_user else "pending",  # Pending if recipient not registered yet
        "created_at": datetime.now(timezone.utc).isoformat(),
        "claimed_at": datetime.now(timezone.utc).isoformat() if recipient_user else None
    }
    await db.points_gifts.insert_one(gift_record)
    
    # Deduct from sender
    await db.rewards_profiles.update_one(
        {"user_id": user["id"]},
        {
            "$inc": {"points_balance": -points_amount},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
        }
    )
    
    # Record sender transaction
    await db.points_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "action": "gift_sent",
        "points": -points_amount,
        "description": f"Gifted {points_amount} points to {recipient_email}",
        "reference_id": gift_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # If recipient has account, credit immediately
    if recipient_user:
        recipient_profile = await db.rewards_profiles.find_one({"user_id": recipient_user["id"]})
        if recipient_profile:
            await db.rewards_profiles.update_one(
                {"user_id": recipient_user["id"]},
                {
                    "$inc": {"points_balance": points_amount, "lifetime_points_earned": points_amount},
                    "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                }
            )
        else:
            # Create new rewards profile for recipient
            referral_code = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=8))
            await db.rewards_profiles.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": recipient_user["id"],
                "email": recipient_email,
                "points_balance": points_amount,
                "lifetime_points_earned": points_amount,
                "lifetime_points_redeemed": 0,
                "referral_code": referral_code,
                "total_referrals": 0,
                "successful_referrals": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
        
        # Record recipient transaction
        await db.points_transactions.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": recipient_user["id"],
            "action": "gift_received",
            "points": points_amount,
            "description": f"Received {points_amount} points from {user.get('first_name', 'A friend')}",
            "reference_id": gift_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    return {
        "success": True,
        "gift_id": gift_id,
        "points_sent": points_amount,
        "recipient": recipient_email,
        "status": "completed" if recipient_user else "pending",
        "message": f"Successfully sent {points_amount} points!" if recipient_user else f"Gift of {points_amount} points will be available when {recipient_email} creates an account"
    }


@router.get("/rewards/gift-history")
async def get_gift_history(request: Request):
    """Get user's gift history (sent and received)"""
    user = await require_auth(request)
    
    # Get gifts sent
    sent_gifts = await db.points_gifts.find(
        {"sender_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    # Get gifts received
    received_gifts = await db.points_gifts.find(
        {"recipient_email": user["email"].lower()},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    return {
        "sent": sent_gifts,
        "received": received_gifts,
        "total_sent": sum(g.get("points", 0) for g in sent_gifts),
        "total_received": sum(g.get("points", 0) for g in received_gifts if g.get("status") == "completed")
    }


@router.post("/rewards/claim-pending-gifts")
async def claim_pending_gifts(request: Request):
    """Claim any pending gifts for a newly registered user"""
    user = await require_auth(request)
    
    # Find pending gifts for this email
    pending_gifts = await db.points_gifts.find({
        "recipient_email": user["email"].lower(),
        "status": "pending"
    }).to_list(100)
    
    if not pending_gifts:
        return {"claimed": 0, "message": "No pending gifts"}
    
    total_points = 0
    claimed_count = 0
    
    for gift in pending_gifts:
        points = gift.get("points", 0)
        total_points += points
        claimed_count += 1
        
        # Update gift status
        await db.points_gifts.update_one(
            {"id": gift["id"]},
            {
                "$set": {
                    "status": "completed",
                    "recipient_id": user["id"],
                    "claimed_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # Record transaction
        await db.points_transactions.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "action": "gift_received",
            "points": points,
            "description": f"Claimed gift of {points} points from {gift.get('sender_name', 'A friend')}",
            "reference_id": gift["id"],
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Update rewards profile
    profile = await db.rewards_profiles.find_one({"user_id": user["id"]})
    if profile:
        await db.rewards_profiles.update_one(
            {"user_id": user["id"]},
            {
                "$inc": {"points_balance": total_points, "lifetime_points_earned": total_points},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )
    else:
        referral_code = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=8))
        await db.rewards_profiles.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "email": user["email"],
            "points_balance": total_points,
            "lifetime_points_earned": total_points,
            "lifetime_points_redeemed": 0,
            "referral_code": referral_code,
            "total_referrals": 0,
            "successful_referrals": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    
    return {
        "claimed": claimed_count,
        "total_points": total_points,
        "message": f"Claimed {total_points} points from {claimed_count} gift(s)!"
    }


@router.get("/admin/gift-analytics")
async def get_gift_analytics(request: Request):
    """Admin endpoint to view all gift data - THE GOLD MINE"""
    await require_admin(request)
    
    # Get all gifts
    all_gifts = await db.points_gifts.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    
    # Calculate stats
    total_gifts = len(all_gifts)
    total_points_gifted = sum(g.get("points", 0) for g in all_gifts)
    completed_gifts = [g for g in all_gifts if g.get("status") == "completed"]
    pending_gifts = [g for g in all_gifts if g.get("status") == "pending"]
    
    # Get top gifters
    gifter_stats = {}
    for gift in all_gifts:
        sender = gift.get("sender_email", "unknown")
        if sender not in gifter_stats:
            gifter_stats[sender] = {"email": sender, "gifts_sent": 0, "points_sent": 0, "recipients": set()}
        gifter_stats[sender]["gifts_sent"] += 1
        gifter_stats[sender]["points_sent"] += gift.get("points", 0)
        gifter_stats[sender]["recipients"].add(gift.get("recipient_email", ""))
    
    top_gifters = sorted(gifter_stats.values(), key=lambda x: x["points_sent"], reverse=True)[:20]
    for g in top_gifters:
        g["unique_recipients"] = len(g["recipients"])
        del g["recipients"]
    
    # Get most popular recipients
    recipient_stats = {}
    for gift in all_gifts:
        recipient = gift.get("recipient_email", "unknown")
        if recipient not in recipient_stats:
            recipient_stats[recipient] = {"email": recipient, "gifts_received": 0, "points_received": 0, "senders": set()}
        recipient_stats[recipient]["gifts_received"] += 1
        recipient_stats[recipient]["points_received"] += gift.get("points", 0)
        recipient_stats[recipient]["senders"].add(gift.get("sender_email", ""))
    
    top_recipients = sorted(recipient_stats.values(), key=lambda x: x["points_received"], reverse=True)[:20]
    for r in top_recipients:
        r["unique_senders"] = len(r["senders"])
        del r["senders"]
    
    # Get relationship network (who gifts to whom)
    relationships = []
    relationship_map = {}
    for gift in all_gifts:
        key = f"{gift.get('sender_email')} -> {gift.get('recipient_email')}"
        if key not in relationship_map:
            relationship_map[key] = {
                "sender": gift.get("sender_email"),
                "sender_name": gift.get("sender_name"),
                "recipient": gift.get("recipient_email"),
                "gift_count": 0,
                "total_points": 0
            }
        relationship_map[key]["gift_count"] += 1
        relationship_map[key]["total_points"] += gift.get("points", 0)
    
    relationships = sorted(relationship_map.values(), key=lambda x: x["total_points"], reverse=True)[:50]
    
    return {
        "summary": {
            "total_gifts": total_gifts,
            "total_points_gifted": total_points_gifted,
            "completed_gifts": len(completed_gifts),
            "pending_gifts": len(pending_gifts),
            "unique_gifters": len(gifter_stats),
            "unique_recipients": len(recipient_stats),
            "avg_gift_size": round(total_points_gifted / total_gifts, 1) if total_gifts > 0 else 0
        },
        "top_gifters": top_gifters,
        "top_recipients": top_recipients,
        "relationships": relationships,
        "recent_gifts": all_gifts[:50]
    }


# ============================================
# GIFT POINTS + SHOP SYSTEM
# Enhanced gifting with claim links & tracking
# ============================================
GIFT_EXPIRY_DAYS = 30
GIFT_MIN_POINTS = 99
GIFT_WARNING_DAYS = 3  # Send reminder X days before expiry


@router.post("/rewards/gift-points-with-link")
async def gift_points_with_shop_link(data: dict, request: Request):
    """
    Send points as a gift with a claimable shop link.
    Sends notifications via Email + SMS + WhatsApp.
    """
    user = await require_auth(request)
    
    recipient_name = data.get("recipient_name", "").strip()
    recipient_email = data.get("recipient_email", "").lower().strip()
    recipient_phone = data.get("recipient_phone", "").strip()
    points_amount = data.get("points", 0)
    personal_note = data.get("personal_note", "").strip()[:300]
    
    # Validations
    if not recipient_email and not recipient_phone:
        raise HTTPException(status_code=400, detail="Recipient email or phone is required")
    
    if points_amount < GIFT_MIN_POINTS:
        raise HTTPException(status_code=400, detail=f"Minimum gift is {GIFT_MIN_POINTS} points")
    
    if recipient_email and recipient_email == user["email"].lower():
        raise HTTPException(status_code=400, detail="Cannot gift points to yourself")
    
    # Check sender's points balance
    sender_points = await db.loyalty_points.find_one({"user_id": user["id"]}, {"_id": 0})
    if not sender_points or sender_points.get("balance", 0) < points_amount:
        raise HTTPException(status_code=400, detail="Insufficient points balance")
    
    # Calculate points value
    config = await get_loyalty_config()
    point_value = config.get("point_value", 0.05)
    points_dollar_value = round(points_amount * point_value, 2)
    
    # Generate unique claim token
    claim_token = secrets.token_urlsafe(32)
    
    # Get frontend URL for claim link
    frontend_url = os.environ.get("FRONTEND_URL")
    claim_link = f"{frontend_url}/claim-gift/{claim_token}"
    
    # Create gift record
    gift_id = str(uuid.uuid4())
    expiry_date = datetime.now(timezone.utc) + timedelta(days=GIFT_EXPIRY_DAYS)
    warning_date = expiry_date - timedelta(days=GIFT_WARNING_DAYS)
    
    gift_record = {
        "id": gift_id,
        "claim_token": claim_token,
        
        # Sender info
        "sender_id": user["id"],
        "sender_email": user["email"],
        "sender_name": user.get("first_name", "A friend"),
        
        # Recipient info
        "recipient_name": recipient_name or "Friend",
        "recipient_email": recipient_email,
        "recipient_phone": recipient_phone,
        
        # Gift details
        "points_amount": points_amount,
        "points_value": points_dollar_value,
        "personal_note": personal_note,
        
        # Status tracking
        "status": "pending",  # pending -> in_progress -> claimed -> converted -> expired
        "claim_lock_at": None,  # Ghost claim prevention
        
        # Notification tracking
        "notifications_sent": {
            "email": False,
            "sms": False,
            "whatsapp": False
        },
        
        # Claim tracking
        "claimed_at": None,
        "claimed_by_user_id": None,
        
        # Conversion tracking
        "converted_to_order_id": None,
        "order_value": None,
        
        # Timestamps
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expiry_date.isoformat(),
        "warning_sent_at": None,
        "warning_due_at": warning_date.isoformat()
    }
    
    await db.gift_points_links.insert_one(gift_record)
    
    # Deduct points from sender
    await db.loyalty_points.update_one(
        {"user_id": user["id"]},
        {
            "$inc": {"balance": -points_amount},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
        }
    )
    
    # Record sender transaction
    await db.points_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "type": "gift_sent",
        "points": -points_amount,
        "description": f"Gifted {points_amount} points to {recipient_name or recipient_email or recipient_phone}",
        "reference_id": gift_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Get gift message templates from admin settings
    templates = await get_gift_message_templates()
    
    # Prepare template variables
    template_vars = {
        "sender_name": user.get("first_name", "A friend"),
        "recipient_name": recipient_name or "Friend",
        "points_amount": str(points_amount),
        "points_value": f"${points_dollar_value:.2f}",
        "personal_note": personal_note,
        "claim_link": claim_link,
        "expiry_days": str(GIFT_EXPIRY_DAYS)
    }
    
    notifications_sent = {"email": False, "sms": False, "whatsapp": False}
    
    # Send Email notification
    if recipient_email and RESEND_API_KEY:
        try:
            email_html = await generate_gift_email_html(template_vars, templates.get("email", {}))
            email_subject = templates.get("email", {}).get("subject", "🎁 You received a gift!")
            email_subject = replace_template_vars(email_subject, template_vars)
            
            params = {
                "from": SENDER_EMAIL,
                "to": [recipient_email],
                "subject": email_subject,
                "html": email_html
            }
            await asyncio.to_thread(resend.Emails.send, params)
            notifications_sent["email"] = True
            logging.info(f"Gift email sent to {recipient_email}")
        except Exception as e:
            logging.error(f"Failed to send gift email: {e}")
    
    # Send SMS notification
    if recipient_phone and twilio_client and TWILIO_ACCOUNT_SID:
        try:
            sms_template = templates.get("sms", {}).get("message", 
                "🎁 {sender_name} sent you {points_amount} points (${points_value})! Claim & shop: {claim_link}")
            sms_message = replace_template_vars(sms_template, template_vars)
            
            # Normalize phone number
            phone_normalized = normalize_phone_number(recipient_phone)
            
            twilio_client.messages.create(
                body=sms_message[:160],  # SMS character limit
                from_=os.environ.get("TWILIO_PHONE_NUMBER"),
                to=phone_normalized
            )
            notifications_sent["sms"] = True
            logging.info(f"Gift SMS sent to {recipient_phone}")
        except Exception as e:
            logging.error(f"Failed to send gift SMS: {e}")
    
    # Send WhatsApp notification
    if recipient_phone:
        try:
            wa_template = templates.get("whatsapp", {}).get("message",
                "🎁 *You received a gift!*\n\n{sender_name} sent you *{points_amount} points* (worth {points_value})!\n\n{personal_note}\n\n👉 Claim your points & shop: {claim_link}\n\n⏰ Expires in {expiry_days} days")
            wa_message = replace_template_vars(wa_template, template_vars)
            
            phone_normalized = normalize_phone_number(recipient_phone)
            await send_whatsapp_message(phone_normalized, wa_message)
            notifications_sent["whatsapp"] = True
            logging.info(f"Gift WhatsApp sent to {recipient_phone}")
        except Exception as e:
            logging.error(f"Failed to send gift WhatsApp: {e}")
    
    # Update notification status
    await db.gift_points_links.update_one(
        {"id": gift_id},
        {"$set": {"notifications_sent": notifications_sent}}
    )
    
    return {
        "success": True,
        "gift_id": gift_id,
        "claim_link": claim_link,
        "points_sent": points_amount,
        "points_value": points_dollar_value,
        "recipient_name": recipient_name,
        "notifications_sent": notifications_sent,
        "expires_at": expiry_date.isoformat(),
        "message": f"Successfully sent {points_amount} points! Recipient will receive notifications to claim."
    }


def replace_template_vars(template: str, vars: dict) -> str:
    """Replace {var_name} placeholders with actual values"""
    result = template
    for key, value in vars.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result


async def get_gift_message_templates() -> dict:
    """Get admin-configured gift message templates"""
    settings = await db.store_settings.find_one({}, {"_id": 0})
    if not settings:
        return {}
    return settings.get("gift_message_templates", {})


async def generate_gift_email_html(vars: dict, email_config: dict) -> str:
    """Generate branded HTML email for gift notification"""
    cta_text = email_config.get("cta_text", "🛍️ Claim Points & Shop Now")
    cta_color = email_config.get("cta_color", "#F8A5B8")
    
    personal_note_html = ""
    if vars.get("personal_note"):
        personal_note_html = f'''
        <div style="background: #FFF5F7; border-radius: 12px; padding: 20px; margin: 20px 0; border-left: 4px solid #F8A5B8;">
            <p style="font-style: italic; color: #666; margin: 0;">"{vars["personal_note"]}"</p>
            <p style="color: #888; font-size: 12px; margin: 10px 0 0 0;">— {vars["sender_name"]}</p>
        </div>
        '''
    
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>You Received a Gift!</title>
    </head>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #2D2A2E; margin: 0; padding: 0; background-color: #f5f5f5;">
        <table cellpadding="0" cellspacing="0" width="100%" style="background-color: #f5f5f5;">
            <tr>
                <td align="center" style="padding: 20px;">
                    <table cellpadding="0" cellspacing="0" width="600" style="background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #2D2A2E 0%, #3d393d 100%); padding: 30px 20px; text-align: center;">
                                <div style="font-size: 32px; font-weight: bold; color: #F8A5B8; letter-spacing: 2px;">REROOTS</div>
                                <div style="color: #D4AF37; font-size: 12px; letter-spacing: 3px; margin-top: 5px;">BEAUTY ENHANCER</div>
                            </td>
                        </tr>
                        
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px 30px;">
                                <!-- Gift Icon -->
                                <div style="text-align: center; margin-bottom: 30px;">
                                    <div style="font-size: 60px;">🎁</div>
                                </div>
                                
                                <h1 style="text-align: center; color: #2D2A2E; margin: 0 0 10px 0; font-size: 28px;">
                                    You Received a Gift!
                                </h1>
                                <p style="text-align: center; color: #666; margin: 0 0 30px 0; font-size: 18px;">
                                    {vars["sender_name"]} sent you something special ✨
                                </p>
                                
                                <!-- Points Box -->
                                <div style="background: linear-gradient(135deg, #FFF5F7 0%, #FFF8E7 100%); border-radius: 16px; padding: 30px; margin: 20px 0; text-align: center; border: 2px solid #F8A5B8;">
                                    <div style="font-size: 48px; font-weight: bold; color: #D4AF37; margin-bottom: 5px;">
                                        {vars["points_amount"]} <span style="font-size: 24px;">points</span>
                                    </div>
                                    <div style="font-size: 20px; color: #2D2A2E;">
                                        Worth <strong>{vars["points_value"]}</strong> off your next order!
                                    </div>
                                </div>
                                
                                {personal_note_html}
                                
                                <!-- CTA Button -->
                                <div style="text-align: center; margin: 30px 0;">
                                    <a href="{vars["claim_link"]}" style="display: inline-block; background: linear-gradient(135deg, {cta_color} 0%, #FFB6C1 100%); color: #2D2A2E; padding: 18px 45px; text-decoration: none; border-radius: 30px; font-weight: bold; font-size: 18px; box-shadow: 0 4px 15px rgba(248, 165, 184, 0.4);">
                                        {cta_text}
                                    </a>
                                </div>
                                
                                <!-- Expiry Notice -->
                                <div style="text-align: center; background: #FFF3E0; border-radius: 8px; padding: 15px; margin-top: 20px;">
                                    <p style="margin: 0; color: #E65100; font-size: 14px;">
                                        ⏰ <strong>Don't wait!</strong> This gift expires in {vars["expiry_days"]} days
                                    </p>
                                </div>
                                
                                <p style="text-align: center; color: #888; font-size: 14px; margin-top: 30px;">
                                    Use your points at checkout to get instant savings on premium skincare!
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background: #2D2A2E; color: #ffffff; padding: 30px; text-align: center;">
                                <p style="margin: 0 0 10px 0; font-size: 14px;">
                                    Questions? Contact us at <a href="mailto:support@reroots.ca" style="color: #F8A5B8; text-decoration: none;">support@reroots.ca</a>
                                </p>
                                <p style="margin: 0; font-size: 12px; color: #888;">© 2026 ReRoots. All rights reserved.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    '''
    return html


@router.get("/gifts/claim/{token}")
async def validate_gift_claim_token(token: str):
    """
    Validate a gift claim token (public endpoint).
    Returns gift info without claiming it.
    """
    gift = await db.gift_points_links.find_one({"claim_token": token}, {"_id": 0})
    
    if not gift:
        raise HTTPException(status_code=404, detail="Gift not found or invalid link")
    
    # Check if expired
    expires_at = datetime.fromisoformat(gift["expires_at"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) > expires_at:
        await db.gift_points_links.update_one(
            {"claim_token": token},
            {"$set": {"status": "expired"}}
        )
        raise HTTPException(status_code=410, detail="This gift has expired")
    
    # Check if already claimed
    if gift["status"] in ["claimed", "converted"]:
        raise HTTPException(status_code=409, detail="This gift has already been claimed")
    
    return {
        "valid": True,
        "sender_name": gift["sender_name"],
        "recipient_name": gift["recipient_name"],
        "points_amount": gift["points_amount"],
        "points_value": gift["points_value"],
        "personal_note": gift.get("personal_note", ""),
        "expires_at": gift["expires_at"],
        "status": gift["status"]
    }


@router.post("/gifts/claim/{token}")
async def claim_gift_points(token: str, request: Request):
    """
    Claim gift points after user is authenticated.
    Implements "claim lock" to prevent ghost claims.
    """
    user = await require_auth(request)
    
    gift = await db.gift_points_links.find_one({"claim_token": token}, {"_id": 0})
    
    if not gift:
        raise HTTPException(status_code=404, detail="Gift not found or invalid link")
    
    # Check if expired
    expires_at = datetime.fromisoformat(gift["expires_at"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) > expires_at:
        await db.gift_points_links.update_one(
            {"claim_token": token},
            {"$set": {"status": "expired"}}
        )
        raise HTTPException(status_code=410, detail="This gift has expired")
    
    # Check if already claimed
    if gift["status"] in ["claimed", "converted"]:
        raise HTTPException(status_code=409, detail="This gift has already been claimed")
    
    # Ghost Claim Prevention: Check if another user has a claim lock
    if gift.get("claim_lock_at"):
        lock_time = datetime.fromisoformat(gift["claim_lock_at"].replace("Z", "+00:00"))
        lock_user = gift.get("claim_lock_user_id")
        # Lock expires after 5 minutes or if same user
        if datetime.now(timezone.utc) - lock_time < timedelta(minutes=5) and lock_user != user["id"]:
            raise HTTPException(status_code=423, detail="This gift is being claimed by another user. Please try again.")
    
    # Set claim lock (ghost claim prevention)
    await db.gift_points_links.update_one(
        {"claim_token": token},
        {
            "$set": {
                "status": "in_progress",
                "claim_lock_at": datetime.now(timezone.utc).isoformat(),
                "claim_lock_user_id": user["id"]
            }
        }
    )
    
    points_amount = gift["points_amount"]
    
    # Get or create user's loyalty points record
    user_points = await db.loyalty_points.find_one({"user_id": user["id"]})
    
    if user_points:
        await db.loyalty_points.update_one(
            {"user_id": user["id"]},
            {
                "$inc": {"balance": points_amount, "lifetime_earned": points_amount},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )
    else:
        await db.loyalty_points.insert_one({
            "user_id": user["id"],
            "email": user["email"],
            "balance": points_amount,
            "lifetime_earned": points_amount,
            "lifetime_redeemed": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Record transaction
    await db.points_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "type": "gift_claimed",
        "points": points_amount,
        "description": f"Claimed gift of {points_amount} points from {gift['sender_name']}",
        "reference_id": gift["id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Update gift status to claimed
    await db.gift_points_links.update_one(
        {"claim_token": token},
        {
            "$set": {
                "status": "claimed",
                "claimed_at": datetime.now(timezone.utc).isoformat(),
                "claimed_by_user_id": user["id"],
                "claimed_by_email": user["email"]
            }
        }
    )
    
    logging.info(f"Gift {gift['id']} claimed by {user['email']} - {points_amount} points")
    
    return {
        "success": True,
        "points_claimed": points_amount,
        "points_value": gift["points_value"],
        "sender_name": gift["sender_name"],
        "message": f"🎉 {points_amount} points added to your account!"
    }


@router.get("/admin/gift-tracking")
async def get_gift_tracking_dashboard(request: Request):
    """Admin dashboard for tracking gift conversions"""
    await require_admin(request)
    
    # Get all gift links
    all_gifts = await db.gift_points_links.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    # Calculate stats
    total_gifts = len(all_gifts)
    total_points = sum(g.get("points_amount", 0) for g in all_gifts)
    total_value = sum(g.get("points_value", 0) for g in all_gifts)
    
    # Status breakdown
    pending = [g for g in all_gifts if g.get("status") == "pending"]
    claimed = [g for g in all_gifts if g.get("status") == "claimed"]
    converted = [g for g in all_gifts if g.get("status") == "converted"]
    expired = [g for g in all_gifts if g.get("status") == "expired"]
    
    # Conversion revenue
    total_revenue = sum(g.get("order_value", 0) or 0 for g in converted)
    
    # Claim rate and conversion rate
    claim_rate = (len(claimed) + len(converted)) / total_gifts * 100 if total_gifts > 0 else 0
    conversion_rate = len(converted) / (len(claimed) + len(converted)) * 100 if (len(claimed) + len(converted)) > 0 else 0
    
    # Recent gifts for table
    recent_gifts = []
    for g in all_gifts[:100]:
        recent_gifts.append({
            "id": g["id"],
            "sender_name": g.get("sender_name", ""),
            "sender_email": g.get("sender_email", ""),
            "recipient_name": g.get("recipient_name", ""),
            "recipient_email": g.get("recipient_email", ""),
            "recipient_phone": g.get("recipient_phone", ""),
            "points_amount": g.get("points_amount", 0),
            "points_value": g.get("points_value", 0),
            "status": g.get("status", "pending"),
            "notifications_sent": g.get("notifications_sent", {}),
            "claimed_at": g.get("claimed_at"),
            "order_value": g.get("order_value"),
            "created_at": g.get("created_at"),
            "expires_at": g.get("expires_at")
        })
    
    return {
        "stats": {
            "total_gifts": total_gifts,
            "total_points_gifted": total_points,
            "total_value_gifted": total_value,
            "pending_count": len(pending),
            "claimed_count": len(claimed),
            "converted_count": len(converted),
            "expired_count": len(expired),
            "claim_rate": round(claim_rate, 1),
            "conversion_rate": round(conversion_rate, 1),
            "total_revenue": total_revenue
        },
        "recent_gifts": recent_gifts
    }


@router.get("/admin/gift-templates")
async def get_gift_message_templates_admin(request: Request):
    """Get gift message templates for admin editing"""
    await require_admin(request)
    
    settings = await db.store_settings.find_one({}, {"_id": 0})
    templates = settings.get("gift_message_templates", {}) if settings else {}
    
    # Return with defaults if not set
    return {
        "email": templates.get("email", {
            "subject": "🎁 {sender_name} sent you a gift!",
            "cta_text": "🛍️ Claim Points & Shop Now",
            "cta_color": "#F8A5B8"
        }),
        "sms": templates.get("sms", {
            "message": "🎁 {sender_name} sent you {points_amount} points ({points_value})! Claim & shop: {claim_link}"
        }),
        "whatsapp": templates.get("whatsapp", {
            "message": "🎁 *You received a gift!*\n\n{sender_name} sent you *{points_amount} points* (worth {points_value})!\n\n{personal_note}\n\n👉 Claim your points & shop: {claim_link}\n\n⏰ Expires in {expiry_days} days"
        })
    }


@router.put("/admin/gift-templates")
async def update_gift_message_templates(data: dict, request: Request):
    """Update gift message templates"""
    await require_admin(request)
    
    templates = {
        "email": data.get("email", {}),
        "sms": data.get("sms", {}),
        "whatsapp": data.get("whatsapp", {})
    }
    
    await db.store_settings.update_one(
        {},
        {"$set": {"gift_message_templates": templates}},
        upsert=True
    )
    
    return {"success": True, "templates": templates}


@router.post("/admin/gift-tracking/mark-converted")
async def mark_gift_converted(data: dict, request: Request):
    """Manually mark a gift as converted (or called automatically after order)"""
    await require_admin(request)
    
    gift_id = data.get("gift_id")
    order_id = data.get("order_id")
    order_value = data.get("order_value", 0)
    
    if not gift_id:
        raise HTTPException(status_code=400, detail="Gift ID required")
    
    result = await db.gift_points_links.update_one(
        {"id": gift_id, "status": "claimed"},
        {
            "$set": {
                "status": "converted",
                "converted_to_order_id": order_id,
                "order_value": order_value,
                "converted_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Gift not found or not in claimed status")
    
    return {"success": True, "message": "Gift marked as converted"}


async def check_and_link_gift_to_order(user_id: str, order_id: str, order_total: float):
    """
    Called after order is placed to link any recently claimed gifts.
    This tracks conversion from gift → sale.
    """
    try:
        # Find gifts claimed by this user in the last 30 days that haven't been converted
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        
        gift = await db.gift_points_links.find_one({
            "claimed_by_user_id": user_id,
            "status": "claimed",
            "claimed_at": {"$gte": thirty_days_ago}
        })
        
        if gift:
            await db.gift_points_links.update_one(
                {"id": gift["id"]},
                {
                    "$set": {
                        "status": "converted",
                        "converted_to_order_id": order_id,
                        "order_value": order_total,
                        "converted_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            logging.info(f"Gift {gift['id']} converted to order {order_id} (${order_total})")
            return True
    except Exception as e:
        logging.error(f"Error linking gift to order: {e}")
    return False


# ============================================
# BIO-AGE SCAN SYSTEM
# Viral Quiz with Referral Points
# ============================================
BIO_SCAN_REFERRAL_POINTS = 100  # Points per friend who completes scan = $5


@router.post("/bio-scan/submit")
async def submit_bio_scan(data: dict, request: Request):
    """Submit Bio-Age Scan results and handle referral tracking"""
    email = data.get("email", "").lower().strip()
    phone = data.get("phone", "").strip()
    answers = data.get("answers", {})
    bio_age_offset = data.get("bio_age_offset", 0)
    risk_level = data.get("risk_level", "Low")
    referrer_code = data.get("referrer_code", "").upper().strip()

    if not email and not phone:
        raise HTTPException(status_code=400, detail="Email or phone required")

    # Extract customer tags from answers for remarketing
    customer_tags = []

    # Age group tag
    age_group = answers.get("age_group", "")
    if age_group:
        customer_tags.append(f"age:{age_group}")

    # Primary concern tag
    primary_concern = answers.get("primary_concern", "")
    if primary_concern:
        customer_tags.append(f"concern:{primary_concern}")

    # Eye concern tag
    eye_concern = answers.get("eye_concern", "")
    if eye_concern and eye_concern != "none":
        customer_tags.append(f"eye:{eye_concern}")

    # Determine recommended product based on answers
    recommended_product = "AURA-GEN"  # default
    if age_group == "teen":
        recommended_product = "ORO-ROSA"
    elif primary_concern == "dark_circles":
        recommended_product = "ROSE-GEN"
    elif eye_concern in ["severe", "moderate"] and age_group == "mature":
        recommended_product = "ROSE-GEN"
    elif age_group == "mature" and primary_concern == "aging":
        recommended_product = "OROE"

    customer_tags.append(f"recommended:{recommended_product}")

    # Risk level tag
    if risk_level:
        customer_tags.append(f"risk:{risk_level.lower()}")

    # Add "High Intent" tag since they completed the full diagnostic scan
    customer_tags.append("intent:high")
    customer_tags.append("source:bio_scan")

    # Check if this person already completed the scan
    # Build query conditions only for non-empty values
    or_conditions = []
    if email:
        or_conditions.append({"email": email})
    if phone:
        or_conditions.append({"phone": phone})

    existing = None
    if or_conditions:
        existing = await db.bio_scans.find_one({"$or": or_conditions}, {"_id": 0})

    if existing:
        # Update tags for returning user
        await db.bio_scans.update_one(
            {"$or": or_conditions},
            {
                "$set": {
                    "customer_tags": customer_tags,
                    "recommended_product": recommended_product,
                }
            },
        )

        # Return existing data with full info for returning user
        return {
            "message": "Welcome back! Here's your referral dashboard.",
            "referral_code": existing.get("referral_code", ""),
            "referral_count": existing.get("referral_count", 0),
            "referrals_started": existing.get("referrals_started", 0),
            "total_points": existing.get("total_points", 0),
            "bio_age_offset": existing.get("bio_age_offset", 0),
            "risk_level": existing.get("risk_level", "Low"),
            "is_new_user": False,
            "recommended_product": recommended_product,
        }

    # Generate unique referral code for this scan participant
    scan_referral_code = f"SCAN-{str(uuid.uuid4())[:6].upper()}"

    # Normalize and validate WhatsApp number if provided
    whatsapp_number = None
    whatsapp_verified = False
    if phone:
        normalized_phone = normalize_phone_number(phone)
        if normalized_phone:
            # Validate WhatsApp registration (anti-fraud gate)
            validation = await validate_whatsapp_number(normalized_phone)
            if validation.get("valid"):
                whatsapp_number = normalized_phone
                whatsapp_verified = True
                logger.info(
                    f"WhatsApp validated for bio-scan: {normalized_phone[:5]}***"
                )

    # Create scan record
    scan_id = str(uuid.uuid4())
    scan_record = {
        "id": scan_id,
        "email": email,
        "phone": phone,
        "whatsapp": whatsapp_number,  # Normalized WhatsApp number for Marketing Lab
        "whatsapp_verified": whatsapp_verified,
        "answers": answers,
        "bio_age_offset": bio_age_offset,
        "risk_level": risk_level,
        "referral_code": scan_referral_code,
        "referred_by": referrer_code if referrer_code else None,
        "referral_count": 0,
        "total_points": 0,
        "customer_tags": customer_tags,
        "recommended_product": recommended_product,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ip_address": request.client.host if request.client else None,
    }

    await db.bio_scans.insert_one(scan_record)
    
    # Broadcast new bio-age scan submission event to admin WebSocket connections
    await broadcast_admin_event("new_bio_scan", {
        "id": scan_record["id"],
        "email": email,
        "name": email.split("@")[0] if email else phone,  # Use email prefix or phone as name
        "referral_code": scan_record["referral_code"],
        "concerns": customer_tags  # Use customer_tags as concerns
    })

    # If referred by someone, award them points
    if referrer_code:
        # Find the referrer's scan record
        referrer = await db.bio_scans.find_one(
            {"referral_code": referrer_code}, {"_id": 0}
        )

        if referrer:
            # Award points to referrer
            new_referral_count = referrer.get("referral_count", 0) + 1
            new_total_points = (
                referrer.get("total_points", 0) + BIO_SCAN_REFERRAL_POINTS
            )

            await db.bio_scans.update_one(
                {"referral_code": referrer_code},
                {
                    "$inc": {
                        "referral_count": 1,
                        "total_points": BIO_SCAN_REFERRAL_POINTS,
                    }
                },
            )

            # Also add to loyalty points if referrer has an account
            if referrer.get("email"):
                referrer_user = await db.users.find_one(
                    {"email": referrer["email"].lower()}, {"_id": 0}
                )
                if referrer_user:
                    history_entry = {
                        "id": str(uuid.uuid4()),
                        "type": "earned",
                        "points": BIO_SCAN_REFERRAL_POINTS,
                        "description": "Bio-Scan Referral",
                        "date": datetime.now(timezone.utc).isoformat(),
                    }

                    await db.loyalty_points.update_one(
                        {"user_id": referrer_user["id"]},
                        {
                            "$inc": {
                                "balance": BIO_SCAN_REFERRAL_POINTS,
                                "lifetime_earned": BIO_SCAN_REFERRAL_POINTS,
                            },
                            "$push": {"history": history_entry},
                            "$setOnInsert": {
                                "id": str(uuid.uuid4()),
                                "user_id": referrer_user["id"],
                                "created_at": datetime.now(timezone.utc).isoformat(),
                            },
                        },
                        upsert=True,
                    )

            logger.info(
                f"Awarded {BIO_SCAN_REFERRAL_POINTS} points to {referrer_code} for bio-scan referral"
            )

            # ===== MILESTONE UNLOCK SYSTEM: Verify this referral =====
            # This bio-scan completion counts toward the referrer's milestone progress
            try:
                # Get client IP for fraud detection
                ip_address = (
                    request.client.host if hasattr(request, "client") else "unknown"
                )
                forwarded = (
                    request.headers.get("x-forwarded-for")
                    if hasattr(request, "headers")
                    else None
                )
                if forwarded:
                    ip_address = forwarded.split(",")[0].strip()

                device_fp = data.get("device_fingerprint", "")

                # Verify this referral for milestone
                await verify_referral_for_milestone(
                    referrer_code,
                    email,
                    ip_address,
                    device_fp,
                )
                logger.info(f"Milestone referral verified: {referrer_code} <- {email}")
            except Exception as e:
                logger.error(f"Milestone verification error: {e}")
            # ===== END MILESTONE =====

    # Also add to waitlist if not already there
    existing_waitlist = await db.waitlist.find_one({"email": email}, {"_id": 0})
    if not existing_waitlist and email:
        waitlist_code = f"FM-{str(uuid.uuid4())[:6].upper()}"
        await db.waitlist.insert_one(
            {
                "id": str(uuid.uuid4()),
                "email": email,
                "name": "",
                "referral_code": waitlist_code,
                "referred_by": referrer_code if referrer_code else None,
                "referral_count": 0,
                "verified_referrals": 0,
                "source": "bio_scan",
                "voucher_unlocked": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    return {
        "message": "Bio-Scan completed successfully!",
        "referral_code": scan_referral_code,
        "referral_count": 0,
        "total_points": 0,
        "points_earned": 0,
        "is_new_user": True,
    }


@router.get("/bio-scan/stats/{referral_code}")
async def get_bio_scan_stats(referral_code: str):
    """Get referral stats for a bio-scan participant"""
    scan = await db.bio_scans.find_one(
        {"referral_code": referral_code.upper()}, {"_id": 0}
    )

    if not scan:
        raise HTTPException(status_code=404, detail="Scan record not found")

    return {
        "referral_code": scan.get("referral_code"),
        "referrals_started": scan.get("referrals_started", 0),
        "referral_count": scan.get("referral_count", 0),
        "total_points": scan.get("total_points", 0),
        "total_value": round(scan.get("total_points", 0) * POINT_VALUE, 2),
        "goal_progress": min(100, (scan.get("referral_count", 0) / 10) * 100),
    }


@router.post("/bio-scan/track-start")
async def track_bio_scan_start(data: dict):
    """Track when someone starts a quiz via a referral link"""
    referrer_code = data.get("referrer_code", "").upper().strip()

    if not referrer_code:
        return {"success": False, "message": "No referrer code provided"}

    # Increment the "started" count for the referrer
    result = await db.bio_scans.update_one(
        {"referral_code": referrer_code}, {"$inc": {"referrals_started": 1}}
    )

    if result.modified_count > 0:
        logger.info(f"Tracked quiz start for referrer: {referrer_code}")
        return {"success": True, "message": "Start tracked"}

    return {"success": False, "message": "Referrer not found"}


@router.post("/bio-scan/analyze-face")
async def analyze_face_for_bio_scan(data: dict):
    """Analyze uploaded face photo for skin concerns using AI"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

    image_base64 = data.get("image_base64", "")
    bio_age_offset = data.get("bio_age_offset", 0)
    risk_level = data.get("risk_level", "Moderate")
    quiz_answers = data.get("answers", {})

    if not image_base64:
        raise HTTPException(status_code=400, detail="No image provided")

    # Clean base64 if it has data URL prefix
    if "base64," in image_base64:
        image_base64 = image_base64.split("base64,")[1]

    try:
        llm_key = get_claude_api_key()

        # Create skin analysis prompt based on quiz answers
        concerns = []
        if quiz_answers.get("climate", 0) >= 2:
            concerns.append("thermal stress damage")
        if quiz_answers.get("repair", 0) >= 2:
            concerns.append("slow cellular recovery")
        if quiz_answers.get("barrier", 0) >= 2:
            concerns.append("compromised moisture barrier")
        if quiz_answers.get("dna", 0) >= 2:
            concerns.append("UV/DNA vulnerability")
        if quiz_answers.get("receptivity", 0) >= 2:
            concerns.append("product absorption plateau")

        system_prompt = """You are a clinical skincare AI analyst for ReRoots, a premium PDRN skincare brand. 
Analyze the uploaded face photo and identify visible skin concerns. Be professional, clinical, and encouraging.
Focus on concerns that PDRN (Polydeoxyribonucleotide) therapy can address:
- Fine lines and wrinkles
- Uneven skin tone
- Dehydration signs
- Texture irregularities
- Signs of environmental stress
- Barrier damage indicators

Respond in JSON format only:
{
  "detected_concerns": ["concern1", "concern2", "concern3"],
  "primary_zone": "forehead/cheeks/around_eyes/chin/overall",
  "skin_type_estimate": "dry/oily/combination/normal",
  "bio_age_visual_match": true/false,
  "clinical_summary": "Brief 1-2 sentence clinical observation",
  "pdrn_recommendation": "How PDRN can help this specific skin"
}"""

        chat = LlmChat(
            api_key=llm_key,
            session_id=f"bio-scan-face-{datetime.now().timestamp()}",
            system_message=system_prompt,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")

        image_content = ImageContent(image_base64=image_base64)

        user_message = UserMessage(
            text=f"""Analyze this face photo. The user's quiz indicates:
- Bio-Age Offset: +{bio_age_offset} years (skin acting older than actual age)
- Risk Level: {risk_level}
- Quiz-identified concerns: {', '.join(concerns) if concerns else 'minimal concerns'}

Provide your clinical skin analysis in JSON format.""",
            file_contents=[image_content],
        )

        response = await chat.send_message(user_message)

        # Parse JSON from response
        import json

        try:
            # Extract JSON from response (might be wrapped in markdown)
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            analysis = json.loads(json_str.strip())
        except:
            # Fallback if JSON parsing fails
            analysis = {
                "detected_concerns": concerns if concerns else ["general aging signs"],
                "primary_zone": "overall",
                "skin_type_estimate": "combination",
                "bio_age_visual_match": True,
                "clinical_summary": f"Analysis indicates skin showing signs consistent with +{bio_age_offset} year bio-age offset.",
                "pdrn_recommendation": "PDRN therapy can help regenerate cellular function and restore skin vitality.",
            }

        logger.info(f"Face analysis completed: {analysis.get('detected_concerns', [])}")

        return {
            "success": True,
            "analysis": analysis,
            "bio_age_offset": bio_age_offset,
            "risk_level": risk_level,
        }

    except Exception as e:
        logger.error(f"Face analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/bio-scan/generate-shareable")
async def generate_shareable_image(data: dict):
    """Generate a futuristic branded shareable image for social media"""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    import httpx

    bio_age_offset = data.get("bio_age_offset", 5)
    detected_concerns = data.get("detected_concerns", ["aging signs"])
    referral_code = data.get("referral_code", "")
    user_name = data.get("user_name", "")

    try:
        llm_key = get_claude_api_key()

        # Generate futuristic scan result image using DALL-E
        prompt = f"""Create a futuristic, high-tech medical scan result display image for a premium skincare brand called "ReRoots".

Style: Dark background (#0a0a0a), cyan and purple neon accents, holographic UI elements, clinical yet luxury aesthetic.

Must include these elements:
1. Large circular bio-scanner display in center showing "+{bio_age_offset}" prominently
2. Glowing cyan scan lines and data visualization around the circle
3. Small holographic icons representing skin concerns: {', '.join(detected_concerns[:3])}
4. "ReRoots" brand text in elegant gold (#C9A86C) at bottom
5. Futuristic grid lines in background
6. Text "BIO-AGE SCAN RESULT" at top in cyan
7. Small QR code placeholder area
8. Overall look: like a high-end medical diagnostic display from a sci-fi movie

Do NOT include any human faces or realistic people. Focus on the data visualization and branding elements.
The image should look shareable on Instagram/TikTok - modern, sleek, and impressive."""

        # Use OpenAI image generation
        import openai

        client = openai.OpenAI(api_key=llm_key)

        response = client.images.generate(
            model="gpt-image-1", prompt=prompt, size="1024x1024", quality="high", n=1
        )

        # Get the image URL or base64
        image_url = response.data[0].url if hasattr(response.data[0], "url") else None
        image_b64 = (
            response.data[0].b64_json if hasattr(response.data[0], "b64_json") else None
        )

        if image_url:
            # Download and convert to base64
            async with httpx.AsyncClient() as client_http:
                img_response = await client_http.get(image_url)
                image_b64 = base64.b64encode(img_response.content).decode("utf-8")

        logger.info(f"Generated shareable image for bio-age: +{bio_age_offset}")

        return {
            "success": True,
            "image_base64": image_b64,
            "share_text": f"🧬 My Skin Bio-Age is +{bio_age_offset} years! Discovered my skin's real age with this clinical scan. Take yours at ReRoots! 💫",
            "hashtags": "#BioAgeScan #SkinHealth #ReRoots #PDRN #SkincareScience #SkinAge",
        }

    except Exception as e:
        logger.error(f"Shareable image generation error: {str(e)}")
        # Return a fallback template-based response
        return {
            "success": False,
            "error": str(e),
            "share_text": f"🧬 My Skin Bio-Age is +{bio_age_offset} years! Discovered my skin's real age with the ReRoots Bio-Scan. Take yours at reroots.ca/bio-scan 💫",
            "hashtags": "#BioAgeScan #SkinHealth #ReRoots #PDRN",
        }


@router.post("/bio-scan/update-tags")
async def update_bio_scan_tags(data: dict):
    """Update user profile with quiz-derived tags for email marketing"""
    email = data.get("email", "").lower().strip()
    answers = data.get("answers", {})
    bio_age_offset = data.get("bio_age_offset", 0)
    risk_level = data.get("risk_level", "Low")
    face_analysis = data.get("face_analysis", {})

    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    # Generate tags from quiz answers
    tags = []

    # Climate/Environmental tags
    climate_score = answers.get("climate", 0)
    if climate_score >= 2:
        tags.append("Concern: High Climate Exposure")
        tags.append("Need: Thermal Protection")
    else:
        tags.append("Concern: Low Climate Exposure")

    # Recovery tags
    repair_score = answers.get("repair", 0)
    if repair_score >= 2:
        tags.append("Concern: Slow Recovery")
        tags.append("Need: Cellular Energy Boost")
    else:
        tags.append("Concern: Normal Recovery")

    # Barrier tags
    barrier_score = answers.get("barrier", 0)
    if barrier_score >= 2:
        tags.append("Concern: Compromised Barrier")
        tags.append("Need: Barrier Repair")
    else:
        tags.append("Concern: Healthy Barrier")

    # DNA Protection tags
    dna_score = answers.get("dna", 0)
    if dna_score >= 2:
        tags.append("Concern: Low DNA Protection")
        tags.append("Need: DNA Repair")
        tags.append("Goal: UV Protection")
    else:
        tags.append("Concern: Active DNA Protection")

    # Product efficacy tags
    receptivity_score = answers.get("receptivity", 0)
    if receptivity_score >= 2:
        tags.append("Concern: Product Plateau")
        tags.append("Need: Cell Reactivation")
    else:
        tags.append("Concern: Good Product Response")

    # Risk level tags
    tags.append(f"Risk: {risk_level}")
    tags.append(f"Bio-Age: +{bio_age_offset} Years")

    # Face analysis tags
    if face_analysis:
        detected = face_analysis.get("detected_concerns", [])
        for concern in detected[:3]:
            tags.append(f"Visual: {concern.title()}")

        skin_type = face_analysis.get("skin_type_estimate", "")
        if skin_type:
            tags.append(f"Skin Type: {skin_type.title()}")

    # Update bio_scans collection
    await db.bio_scans.update_one(
        {"email": email},
        {"$set": {"tags": tags, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    # Also update waitlist if exists
    await db.waitlist.update_one(
        {"email": email},
        {
            "$set": {
                "quiz_tags": tags,
                "bio_age_offset": bio_age_offset,
                "risk_level": risk_level,
            }
        },
        upsert=False,
    )

    logger.info(f"Updated tags for {email}: {len(tags)} tags")

    return {"success": True, "email": email, "tags": tags, "tag_count": len(tags)}


@router.get("/admin/bio-scan/stats")
async def get_admin_bio_scan_stats(request: Request):
    """Admin: Get comprehensive Bio-Scan analytics"""
    await require_admin(request)

    total_scans = await db.bio_scans.count_documents({})

    # Risk level distribution
    risk_pipeline = [{"$group": {"_id": "$risk_level", "count": {"$sum": 1}}}]
    risk_stats = await db.bio_scans.aggregate(risk_pipeline).to_list(10)

    # Bio-Age distribution
    bio_age_pipeline = [
        {"$group": {"_id": "$bio_age_offset", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    bio_age_stats = await db.bio_scans.aggregate(bio_age_pipeline).to_list(20)

    # Top referrers
    top_referrers = (
        await db.bio_scans.find(
            {"referral_count": {"$gt": 0}},
            {
                "_id": 0,
                "email": 1,
                "phone": 1,
                "referral_code": 1,
                "referral_count": 1,
                "referrals_started": 1,
                "total_points": 1,
            },
        )
        .sort("referral_count", -1)
        .limit(10)
        .to_list(10)
    )

    # Total points issued through bio-scan
    points_pipeline = [{"$group": {"_id": None, "total": {"$sum": "$total_points"}}}]
    points_stats = await db.bio_scans.aggregate(points_pipeline).to_list(1)
    total_points = points_stats[0]["total"] if points_stats else 0

    # Emails and phones collected
    emails_collected = await db.bio_scans.count_documents({"email": {"$ne": ""}})
    phones_collected = await db.bio_scans.count_documents({"phone": {"$ne": ""}})
    email_only = await db.bio_scans.count_documents(
        {"email": {"$ne": ""}, "$or": [{"phone": ""}, {"phone": None}]}
    )
    phone_only = await db.bio_scans.count_documents(
        {"$or": [{"email": ""}, {"email": None}], "phone": {"$ne": ""}}
    )
    both = await db.bio_scans.count_documents(
        {"email": {"$ne": ""}, "phone": {"$ne": ""}}
    )

    # Daily submissions (last 14 days)
    from datetime import datetime, timedelta

    fourteen_days_ago = datetime.utcnow() - timedelta(days=14)
    daily_pipeline = [
        {"$match": {"created_at": {"$gte": fourteen_days_ago.isoformat()}}},
        {"$addFields": {"date": {"$substr": ["$created_at", 0, 10]}}},
        {"$group": {"_id": "$date", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    daily_stats = await db.bio_scans.aggregate(daily_pipeline).to_list(14)

    # Referral conversion rate
    total_referrals_started = 0
    total_referrals_completed = 0
    async for scan in db.bio_scans.find(
        {}, {"referrals_started": 1, "referral_count": 1}
    ):
        total_referrals_started += scan.get("referrals_started", 0)
        total_referrals_completed += scan.get("referral_count", 0)

    conversion_rate = (
        (total_referrals_completed / total_referrals_started * 100)
        if total_referrals_started > 0
        else 0
    )

    # Recent submissions
    recent_scans = (
        await db.bio_scans.find(
            {},
            {
                "_id": 0,
                "email": 1,
                "phone": 1,
                "bio_age_offset": 1,
                "risk_level": 1,
                "referral_code": 1,
                "referral_count": 1,
                "created_at": 1,
            },
        )
        .sort("created_at", -1)
        .limit(20)
        .to_list(20)
    )

    return {
        "total_scans": total_scans,
        "contacts": {
            "emails": emails_collected,
            "phones": phones_collected,
            "email_only": email_only,
            "phone_only": phone_only,
            "both": both,
        },
        "risk_distribution": {
            str(r["_id"] or "Unknown"): r["count"] for r in risk_stats
        },
        "bio_age_distribution": {str(b["_id"] or 0): b["count"] for b in bio_age_stats},
        "referrals": {
            "total_started": total_referrals_started,
            "total_completed": total_referrals_completed,
            "conversion_rate": round(conversion_rate, 1),
            "total_points_issued": total_points,
            "total_value": round(total_points * POINT_VALUE, 2),
        },
        "daily_submissions": {d["_id"]: d["count"] for d in daily_stats},
        "top_referrers": top_referrers,
        "recent_submissions": recent_scans,
    }


@router.get("/orders")
async def get_orders(request: Request):
    user = await require_auth(request)
    orders = (
        await db.orders.find({"user_id": user["id"]}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )
    return orders


@router.get("/orders/{order_id}")
async def get_order(order_id: str):
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


# Update order shipping cost paid
@router.put("/admin/orders/{order_id}/shipping-cost")
async def update_order_shipping_cost(order_id: str, request: Request):
    await require_admin(request)
    data = await request.json()
    shipping_cost_paid = data.get("shipping_cost_paid", 0)

    result = await db.orders.update_one(
        {"id": order_id}, {"$set": {"shipping_cost_paid": float(shipping_cost_paid)}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")

    return {"success": True, "message": "Shipping cost updated"}


# ============= FINANCIALS API =============


@router.get("/admin/financials")
async def get_financials(request: Request, period: str = "all"):
    """Get financial summary - Balance Sheet / P&L"""
    await require_admin(request)

    # Build date filter
    date_filter = {}
    now = datetime.now(timezone.utc)

    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        date_filter = {"created_at": {"$gte": start.isoformat()}}
    elif period == "week":
        start = now - timedelta(days=7)
        date_filter = {"created_at": {"$gte": start.isoformat()}}
    elif period == "month":
        start = now - timedelta(days=30)
        date_filter = {"created_at": {"$gte": start.isoformat()}}
    elif period == "year":
        start = now - timedelta(days=365)
        date_filter = {"created_at": {"$gte": start.isoformat()}}

    # Only include paid orders
    query = {"payment_status": "paid", **date_filter}
    orders = await db.orders.find(query, {"_id": 0}).to_list(10000)

    # Calculate totals
    total_revenue = 0.0  # Total customer payments (total field)
    total_subtotal = 0.0  # Product sales before discounts
    total_discounts = 0.0  # Total discounts given
    total_tax_collected = 0.0  # Tax charged to customers (on original price)
    total_shipping_collected = 0.0  # Shipping charged to customers
    total_shipping_paid = 0.0  # Actual shipping cost you paid
    total_cost_of_goods = 0.0  # Your product costs (COGS)
    total_final_selling_price = (
        0.0  # What products actually sold for (after all discounts)
    )

    for order in orders:
        total_revenue += order.get("total", 0)
        total_subtotal += order.get("subtotal", 0)
        total_discounts += order.get("discount_amount", 0)
        total_tax_collected += order.get("tax", 0)
        total_shipping_collected += order.get("shipping", 0)
        total_shipping_paid += order.get("shipping_cost_paid", 0)
        total_cost_of_goods += order.get("cost_of_goods", 0)
        # Calculate actual selling price (subtotal - discount)
        actual_selling = order.get("subtotal", 0) - order.get("discount_amount", 0)
        total_final_selling_price += actual_selling

    # TAX CALCULATION FOR ACCOUNTANT (on final selling price, not original)
    # This is what you actually owe to the government
    tax_rate = 0.13  # 13% HST
    tax_liability = round(total_final_selling_price * tax_rate, 2)  # Tax you OWE
    tax_profit = round(total_tax_collected - tax_liability, 2)  # Extra tax you keep

    # Get business expenses for the same period
    expense_query = {**date_filter} if date_filter else {}
    expenses = await db.expenses.find(expense_query, {"_id": 0}).to_list(10000)
    total_expenses = sum(e.get("amount", 0) for e in expenses)
    expenses_by_category = {}
    for exp in expenses:
        cat = exp.get("category", "Other")
        expenses_by_category[cat] = expenses_by_category.get(cat, 0) + exp.get(
            "amount", 0
        )

    # Calculate profits
    gross_revenue = total_subtotal - total_discounts  # Revenue after discounts
    shipping_profit = total_shipping_collected - total_shipping_paid
    gross_profit = gross_revenue - total_cost_of_goods  # Before shipping costs
    operating_profit = gross_profit + shipping_profit  # Before business expenses
    net_profit = operating_profit - total_expenses  # After ALL expenses

    # Profit margin
    profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0

    # Get order count
    order_count = len(orders)
    avg_order_value = total_revenue / order_count if order_count > 0 else 0

    return {
        "period": period,
        "order_count": order_count,
        "avg_order_value": round(avg_order_value, 2),
        # Revenue breakdown
        "total_revenue": round(total_revenue, 2),  # What customers paid
        "total_subtotal": round(total_subtotal, 2),  # Before discounts
        "total_discounts": round(total_discounts, 2),
        "gross_revenue": round(
            gross_revenue, 2
        ),  # After discounts (actual selling price)
        # Tax - TWO calculations
        "total_tax_collected": round(
            total_tax_collected, 2
        ),  # What you charged customers
        "tax_liability": tax_liability,  # What you OWE to government (on final selling price)
        "tax_profit": tax_profit,  # Extra tax you keep (collected - liability)
        # Shipping
        "total_shipping_collected": round(total_shipping_collected, 2),
        "total_shipping_paid": round(total_shipping_paid, 2),
        "shipping_profit": round(shipping_profit, 2),
        # Costs & Profit
        "total_cost_of_goods": round(total_cost_of_goods, 2),
        "gross_profit": round(gross_profit, 2),
        "operating_profit": round(operating_profit, 2),
        # Business Expenses
        "total_expenses": round(total_expenses, 2),
        "expenses_by_category": {
            k: round(v, 2) for k, v in expenses_by_category.items()
        },
        "expense_count": len(expenses),
        # Final Profit
        "net_profit": round(net_profit, 2),
        "profit_margin": round(profit_margin, 2),
        # Recent orders for detail view
        "recent_orders": orders[:20],
    }


@router.get("/admin/financials/orders")
async def get_financial_orders(request: Request, page: int = 1, limit: int = 50):
    """Get detailed order financials"""
    await require_admin(request)

    skip = (page - 1) * limit
    orders = (
        await db.orders.find({"payment_status": "paid"}, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )

    total = await db.orders.count_documents({"payment_status": "paid"})

    # Add profit calculation to each order
    for order in orders:
        revenue = order.get("total", 0) - order.get("tax", 0) - order.get("shipping", 0)
        cogs = order.get("cost_of_goods", 0)
        shipping_profit = order.get("shipping", 0) - order.get("shipping_cost_paid", 0)
        order["profit"] = round(revenue - cogs + shipping_profit, 2)

    return {
        "orders": orders,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/admin/financials/export")
async def export_financials(
    request: Request, period: str = "month", format: str = "csv"
):
    """Export financial report as CSV"""
    await require_admin(request)

    # Get financial data
    date_filter = {}
    now = datetime.now(timezone.utc)

    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        date_filter = {"created_at": {"$gte": start.isoformat()}}
    elif period == "week":
        start = now - timedelta(days=7)
        date_filter = {"created_at": {"$gte": start.isoformat()}}
    elif period == "month":
        start = now - timedelta(days=30)
        date_filter = {"created_at": {"$gte": start.isoformat()}}
    elif period == "year":
        start = now - timedelta(days=365)
        date_filter = {"created_at": {"$gte": start.isoformat()}}

    query = {"payment_status": "paid", **date_filter}
    orders = await db.orders.find(query, {"_id": 0}).to_list(10000)

    # Create CSV content
    csv_lines = []
    csv_lines.append("PROFIT & LOSS STATEMENT")
    csv_lines.append(f"Period: {period.upper()}")
    csv_lines.append(f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    csv_lines.append("")
    csv_lines.append("ORDER DETAILS")
    csv_lines.append(
        "Order #,Date,Subtotal,Discount,Tax Collected,Shipping Collected,Shipping Paid,COGS,Total Revenue,Net Profit"
    )

    total_subtotal = 0
    total_discounts = 0
    total_tax = 0
    total_shipping_collected = 0
    total_shipping_paid = 0
    total_cogs = 0
    total_revenue = 0
    total_profit = 0

    for order in orders:
        subtotal = order.get("subtotal", 0)
        discount = order.get("discount_amount", 0)
        tax = order.get("tax", 0)
        ship_collected = order.get("shipping", 0)
        ship_paid = order.get("shipping_cost_paid", 0)
        cogs = order.get("cost_of_goods", 0)
        revenue = order.get("total", 0)
        profit = (subtotal - discount - cogs) + (ship_collected - ship_paid)

        total_subtotal += subtotal
        total_discounts += discount
        total_tax += tax
        total_shipping_collected += ship_collected
        total_shipping_paid += ship_paid
        total_cogs += cogs
        total_revenue += revenue
        total_profit += profit

        date_str = order.get("created_at", "")[:10]
        csv_lines.append(
            f"{order.get('order_number','')},{date_str},{subtotal:.2f},{discount:.2f},{tax:.2f},{ship_collected:.2f},{ship_paid:.2f},{cogs:.2f},{revenue:.2f},{profit:.2f}"
        )

    csv_lines.append("")
    csv_lines.append("SUMMARY")
    csv_lines.append(f"Total Orders,{len(orders)}")
    csv_lines.append(f"Gross Sales (before discounts),${total_subtotal:.2f}")
    csv_lines.append(f"Total Discounts,${total_discounts:.2f}")
    csv_lines.append(f"Net Sales,${total_subtotal - total_discounts:.2f}")
    csv_lines.append(f"Tax Collected (HST),${total_tax:.2f}")
    csv_lines.append(f"Shipping Collected,${total_shipping_collected:.2f}")
    csv_lines.append(f"Shipping Paid,${total_shipping_paid:.2f}")
    csv_lines.append(f"Cost of Goods Sold,${total_cogs:.2f}")
    csv_lines.append(f"TOTAL REVENUE,${total_revenue:.2f}")
    csv_lines.append(f"NET PROFIT,${total_profit:.2f}")

    csv_content = "\n".join(csv_lines)


    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=pnl_report_{period}_{now.strftime('%Y%m%d')}.csv"
        },
    )


class SendReportRequest(BaseModel):
    email: str
    period: str = "month"
    message: Optional[str] = ""


@router.post("/admin/financials/send-report")
async def send_financial_report(data: SendReportRequest, request: Request):
    """Send financial report to accountant via email"""
    await require_admin(request)

    # Get financial data
    date_filter = {}
    now = datetime.now(timezone.utc)

    if data.period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        date_filter = {"created_at": {"$gte": start.isoformat()}}
    elif data.period == "week":
        start = now - timedelta(days=7)
        date_filter = {"created_at": {"$gte": start.isoformat()}}
    elif data.period == "month":
        start = now - timedelta(days=30)
        date_filter = {"created_at": {"$gte": start.isoformat()}}
    elif data.period == "year":
        start = now - timedelta(days=365)
        date_filter = {"created_at": {"$gte": start.isoformat()}}

    query = {"payment_status": "paid", **date_filter}
    orders = await db.orders.find(query, {"_id": 0}).to_list(10000)

    # Calculate totals
    total_revenue = sum(o.get("total", 0) for o in orders)
    total_subtotal = sum(o.get("subtotal", 0) for o in orders)
    total_discounts = sum(o.get("discount_amount", 0) for o in orders)
    total_tax = sum(o.get("tax", 0) for o in orders)
    total_shipping_collected = sum(o.get("shipping", 0) for o in orders)
    total_shipping_paid = sum(o.get("shipping_cost_paid", 0) for o in orders)
    total_cogs = sum(o.get("cost_of_goods", 0) for o in orders)
    net_profit = (total_subtotal - total_discounts - total_cogs) + (
        total_shipping_collected - total_shipping_paid
    )

    # Get store settings for branding
    store_settings = await db.store_settings.find_one({}, {"_id": 0}) or {}
    store_name = store_settings.get("store_name", "ReRoots")

    # Build HTML email
    html_content = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; }}
            .header {{ background: #2D2A2E; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 30px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
            th {{ background: #f8f8f8; font-weight: 600; }}
            .total-row {{ background: #f0fdf4; font-weight: bold; }}
            .profit-row {{ background: #10b981; color: white; font-weight: bold; font-size: 18px; }}
            .section-title {{ color: #2D2A2E; font-size: 16px; font-weight: 600; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1 style="margin: 0;">💰 {store_name}</h1>
                <p style="margin: 5px 0 0; opacity: 0.8;">Profit & Loss Statement</p>
            </div>
            <div class="content">
                <p><strong>Period:</strong> {data.period.upper()}</p>
                <p><strong>Generated:</strong> {now.strftime('%B %d, %Y at %H:%M UTC')}</p>
                <p><strong>Total Orders:</strong> {len(orders)}</p>
                
                {f'<p style="background: #fef3c7; padding: 10px; border-radius: 4px;"><strong>Note:</strong> {data.message}</p>' if data.message else ''}
                
                <h3 class="section-title">📊 Revenue</h3>
                <table>
                    <tr><td>Gross Sales (before discounts)</td><td style="text-align: right;">${total_subtotal:.2f}</td></tr>
                    <tr><td>Discounts Given</td><td style="text-align: right; color: #dc2626;">-${total_discounts:.2f}</td></tr>
                    <tr class="total-row"><td>Net Sales</td><td style="text-align: right;">${total_subtotal - total_discounts:.2f}</td></tr>
                </table>
                
                <h3 class="section-title">💵 Tax & Shipping</h3>
                <table>
                    <tr><td>Tax Collected (HST 13%)</td><td style="text-align: right;">${total_tax:.2f}</td></tr>
                    <tr><td>Shipping Collected from Customers</td><td style="text-align: right;">${total_shipping_collected:.2f}</td></tr>
                    <tr><td>Shipping Paid to Couriers</td><td style="text-align: right; color: #dc2626;">-${total_shipping_paid:.2f}</td></tr>
                </table>
                
                <h3 class="section-title">📦 Costs</h3>
                <table>
                    <tr><td>Cost of Goods Sold (COGS)</td><td style="text-align: right; color: #dc2626;">-${total_cogs:.2f}</td></tr>
                </table>
                
                <h3 class="section-title">💰 Summary</h3>
                <table>
                    <tr class="total-row"><td>Total Revenue Collected</td><td style="text-align: right;">${total_revenue:.2f}</td></tr>
                    <tr class="profit-row"><td>NET PROFIT</td><td style="text-align: right;">${net_profit:.2f}</td></tr>
                </table>
                
                <p style="color: #666; font-size: 12px; margin-top: 30px;">
                    This report was automatically generated by {store_name}'s financial system.<br>
                    For questions, please contact the store administrator.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    # Send email using Resend
    if RESEND_API_KEY:
        try:
            resend.api_key = RESEND_API_KEY
            sender_email = os.environ.get("SENDER_EMAIL", "noreply@reroots.ca")

            resend.Emails.send(
                {
                    "from": f"{store_name} Financials <{sender_email}>",
                    "to": [data.email],
                    "subject": f"📊 {store_name} P&L Report - {data.period.upper()} ({now.strftime('%B %Y')})",
                    "html": html_content,
                }
            )

            logging.info(f"Financial report sent to {data.email}")
            return {"success": True, "message": f"Report sent to {data.email}"}
        except Exception as e:
            logging.error(f"Failed to send financial report: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to send email: {str(e)}"
            )
    else:
        raise HTTPException(status_code=500, detail="Email service not configured")


@router.post("/admin/roles/accountant")
async def create_accountant_role(request: Request):
    """Create a pre-configured Accountant role"""
    await require_admin(request)

    # Check if role already exists
    existing = await db.roles.find_one({"name": "Accountant"}, {"_id": 0})
    if existing:
        return {
            "success": True,
            "role": existing,
            "message": "Accountant role already exists",
        }

    user = await get_current_user(request)
    role = {
        "id": str(uuid.uuid4()),
        "name": "Accountant",
        "description": "Read-only access to financial reports and orders for tax filing",
        "permissions": ACCOUNTANT_PERMISSIONS,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user["id"] if user else "",
        "is_active": True,
    }

    await db.roles.insert_one(role)
    role_copy = {k: v for k, v in role.items() if k != "_id"}

    return {"success": True, "role": role_copy, "message": "Accountant role created"}


# ============= BUSINESS EXPENSES =============


@router.get("/admin/expenses/categories")
async def get_expense_categories(request: Request):
    """Get list of expense categories"""
    await require_admin(request)
    return {"categories": EXPENSE_CATEGORIES}


@router.get("/admin/expenses")
async def get_expenses(request: Request, period: str = "month", category: str = None):
    """Get all business expenses"""
    await require_admin(request)

    # Build date filter
    date_filter = {}
    now = datetime.now(timezone.utc)

    if period == "today":
        start = now.strftime("%Y-%m-%d")
        date_filter = {"date": start}
    elif period == "week":
        start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        date_filter = {"date": {"$gte": start}}
    elif period == "month":
        start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        date_filter = {"date": {"$gte": start}}
    elif period == "year":
        start = (now - timedelta(days=365)).strftime("%Y-%m-%d")
        date_filter = {"date": {"$gte": start}}

    query = {**date_filter}
    if category:
        query["category"] = category

    expenses = await db.expenses.find(query, {"_id": 0}).sort("date", -1).to_list(1000)

    # Calculate totals by category
    totals_by_category = {}
    total_amount = 0
    for expense in expenses:
        cat = expense.get("category", "Other")
        totals_by_category[cat] = totals_by_category.get(cat, 0) + expense.get(
            "amount", 0
        )
        total_amount += expense.get("amount", 0)

    return {
        "expenses": expenses,
        "totals_by_category": totals_by_category,
        "total_amount": round(total_amount, 2),
        "count": len(expenses),
    }


@router.post("/admin/expenses")
async def create_expense(expense_data: ExpenseCreate, request: Request):
    """Create a new business expense"""
    await require_admin(request)
    user = await get_current_user(request)

    expense = Expense(
        **expense_data.model_dump(), created_by=user["id"] if user else ""
    )

    await db.expenses.insert_one(expense.model_dump())
    expense_dict = {k: v for k, v in expense.model_dump().items() if k != "_id"}

    return {"success": True, "expense": expense_dict}


@router.put("/admin/expenses/{expense_id}")
async def update_expense(expense_id: str, request: Request):
    """Update an expense"""
    await require_admin(request)
    data = await request.json()

    # Remove id and created_at from update
    update_data = {
        k: v for k, v in data.items() if k not in ["id", "created_at", "created_by"]
    }

    result = await db.expenses.update_one({"id": expense_id}, {"$set": update_data})

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Expense not found")

    expense = await db.expenses.find_one({"id": expense_id}, {"_id": 0})
    return {"success": True, "expense": expense}


@router.delete("/admin/expenses/{expense_id}")
async def delete_expense(expense_id: str, request: Request):
    """Delete an expense"""
    await require_admin(request)

    result = await db.expenses.delete_one({"id": expense_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Expense not found")

    return {"success": True, "message": "Expense deleted"}


@router.post("/admin/expenses/upload-receipt")
async def upload_expense_receipt(request: Request):
    """Upload a receipt image and return the URL"""
    await require_admin(request)

    form = await request.form()
    file = form.get("file")

    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    # Read file content
    content = await file.read()

    # Convert to base64 for storage (simple approach)

    file_ext = file.filename.split(".")[-1].lower() if file.filename else "png"
    content_type = (
        f"image/{file_ext}"
        if file_ext in ["png", "jpg", "jpeg", "gif", "webp"]
        else "application/pdf"
    )
    base64_content = base64.b64encode(content).decode("utf-8")
    data_url = f"data:{content_type};base64,{base64_content}"

    return {"success": True, "url": data_url}


