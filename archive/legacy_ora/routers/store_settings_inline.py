"""
Store settings + offers/discount codes
Extracted from server.py during modularization.
"""

import os
import logging
import json
import hashlib
import secrets
import time
import uuid
from uuid import uuid4
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
    from models.server_models import StoreSettings
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

# ============= STORE SETTINGS MANAGEMENT =============


@router.get("/store-settings")
async def get_store_settings(request: Request):
    # Check if database is initialized
    if db is None:
        raise HTTPException(status_code=503, detail="Service starting up, please retry")
    
    # Check cache first
    cached = get_cached("store_settings")
    if cached:
        return cached
    
    # Public endpoint returns limited info for live chat
    settings = await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0})
    if not settings:
        default_settings = StoreSettings()
        settings_dict = default_settings.model_dump()
        settings_dict["updated_at"] = settings_dict["updated_at"].isoformat()
        await db.store_settings.insert_one(settings_dict)
        settings = await db.store_settings.find_one(
            {"id": "store_settings"}, {"_id": 0}
        )

    # Return public info (hide secret keys, but include language for localization)
    result = {
        "store_name": settings.get("store_name"),
        "live_chat": settings.get("live_chat"),
        "google_business": settings.get("google_business"),
        "language": settings.get(
            "language",
            {
                "default_language": "en",
                "auto_detect": True,
                "supported_languages": ["en"],
            },
        ),
        "payment": {
            "stripe_enabled": settings.get("payment", {}).get("stripe_enabled", True),
            "paypal_enabled": settings.get("payment", {}).get("paypal_enabled", True),
            "currency": settings.get("payment", {}).get("currency", "CAD"),
            "tax_rate": settings.get("payment", {}).get("tax_rate", 13.0),
            "free_shipping_threshold": settings.get("payment", {}).get(
                "free_shipping_threshold", 75.0
            ),
            # Include payment method availability (not secrets)
            "bambora_enabled": settings.get("payment", {}).get(
                "bambora_enabled", True
            ),
            "bank_transfer_enabled": settings.get("payment", {}).get(
                "bank_transfer_enabled", True
            ),
            "etransfer_enabled": settings.get("payment", {}).get(
                "etransfer_enabled", True
            ),
            "etransfer_email": settings.get("payment", {}).get(
                "etransfer_email", "admin@reroots.ca"
            ),
            "etransfer_instructions": settings.get("payment", {}).get(
                "etransfer_instructions", "Send e-Transfer to our email. Include order number in message."
            ),
            "paypal_manual_enabled": settings.get("payment", {}).get(
                "paypal_manual_enabled", False
            ),
            "paypal_email": settings.get("payment", {}).get(
                "paypal_email", "admin@reroots.ca"
            ),
            "paypal_link_url": settings.get("payment", {}).get(
                "paypal_link_url", ""
            ),
            "paypal_instructions": settings.get("payment", {}).get(
                "paypal_instructions", "Send as Friends & Family to avoid fees. Include order number."
            ),
            "paypal_api_enabled": settings.get("payment", {}).get(
                "paypal_api_enabled", False
            ),
            "paytm_enabled": settings.get("payment", {})
            .get("paytm", {})
            .get("enabled", False),
            "upi_enabled": settings.get("payment", {})
            .get("upi", {})
            .get("enabled", False),
            "paypal_enabled_v2": settings.get("payment", {})
            .get("paypal", {})
            .get("enabled", False),
            "card_payment_enabled": settings.get("payment", {})
            .get("card_payment", {})
            .get("enabled", False),
        },
        # Promo Banner settings (public)
        "promo_banner_enabled": settings.get("promo_banner_enabled", False),
        "promo_banner_title": settings.get("promo_banner_title", "FOUNDER'S"),
        "promo_banner_text": settings.get("promo_banner_text", ""),
        "promo_banner_code": settings.get("promo_banner_code", "FOUNDER50"),
        "promo_banner_discount_percent": settings.get(
            "promo_banner_discount_percent", 50
        ),
        "promo_banner_bg_color": settings.get("promo_banner_bg_color", "#FFD93D"),
        "promo_banner_text_color": settings.get("promo_banner_text_color", "#1a1a1a"),
        "promo_banner_design": settings.get("promo_banner_design", "modern"),
        "promo_banner_position": settings.get("promo_banner_position", "bottom-right"),
        "promo_banner_link": settings.get("promo_banner_link", "/shop"),
        # First purchase discount (public - customers don't see %, just the bonus at checkout)
        "first_purchase_discount_enabled": settings.get(
            "first_purchase_discount_enabled", True
        ),
    }
    
    # Cache the result
    set_cached("store_settings", result)
    return result


@router.get("/admin/store-settings")
async def get_admin_store_settings(request: Request):
    await require_admin(request)
    settings = await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0})
    if not settings:
        default_settings = StoreSettings()
        settings_dict = default_settings.model_dump()
        settings_dict["updated_at"] = settings_dict["updated_at"].isoformat()
        await db.store_settings.insert_one(settings_dict)
        settings = await db.store_settings.find_one(
            {"id": "store_settings"}, {"_id": 0}
        )
    return settings


@router.put("/admin/store-settings")
async def update_store_settings(settings_data: dict, request: Request):
    await require_admin(request)
    settings_data["id"] = "store_settings"
    settings_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.store_settings.update_one(
        {"id": "store_settings"}, {"$set": settings_data}, upsert=True
    )

    # Invalidate cache
    invalidate_cache("store_settings")
    
    updated = await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0})
    return updated


@router.put("/admin/store-settings/payment")
async def update_payment_settings(payment_data: dict, request: Request):
    await require_admin(request)
    await db.store_settings.update_one(
        {"id": "store_settings"},
        {
            "$set": {
                "payment": payment_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )
    return {"message": "Payment settings updated"}


@router.put("/admin/store-settings/banking")
async def update_banking_settings(banking_data: dict, request: Request):
    """Update banking/payment destination details"""
    await require_admin(request)
    await db.store_settings.update_one(
        {"id": "store_settings"},
        {
            "$set": {
                "banking": banking_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )
    return {"message": "Banking settings updated"}


@router.put("/admin/store-settings/digital-delivery")
async def update_digital_delivery_settings(delivery_data: dict, request: Request):
    """Update digital file delivery settings"""
    await require_admin(request)
    await db.store_settings.update_one(
        {"id": "store_settings"},
        {
            "$set": {
                "digital_delivery": delivery_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )
    return {"message": "Digital delivery settings updated"}


@router.put("/admin/store-settings/login-background")
async def update_login_background(background_data: dict, request: Request):
    """Update login page background images"""
    await require_admin(request)

    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if "login_background_image" in background_data:
        update_fields["login_background_image"] = background_data[
            "login_background_image"
        ]
    if "admin_login_background_image" in background_data:
        update_fields["admin_login_background_image"] = background_data[
            "admin_login_background_image"
        ]

    await db.store_settings.update_one(
        {"id": "store_settings"}, {"$set": update_fields}, upsert=True
    )

    return {"message": "Login background updated successfully"}


@router.get("/public/login-backgrounds")
async def get_login_backgrounds():
    """Get login page backgrounds (public endpoint for login pages)"""
    settings = await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0})

    return {
        "login_background_image": (
            settings.get("login_background_image") if settings else None
        ),
        "admin_login_background_image": (
            settings.get("admin_login_background_image") if settings else None
        ),
    }


@router.get("/public/site-background")
async def get_site_background():
    """Get global site background settings (public endpoint for all pages)"""
    settings = await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0})

    return {
        "global_site_background": (
            settings.get("global_site_background") if settings else None
        ),
        "global_background_enabled": (
            settings.get("global_background_enabled", False) if settings else False
        ),
        "global_background_opacity": (
            settings.get("global_background_opacity", 0.15) if settings else 0.15
        ),
        "global_background_overlay_color": (
            settings.get("global_background_overlay_color", "#FFFFFF")
            if settings
            else "#FFFFFF"
        ),
        "login_background_image": (
            settings.get("login_background_image") if settings else None
        ),
        "admin_login_background_image": (
            settings.get("admin_login_background_image") if settings else None
        ),
        # Live background settings
        "live_background_type": (
            settings.get("live_background_type", "none") if settings else "none"
        ),
        "live_background_video_url": (
            settings.get("live_background_video_url") if settings else None
        ),
        "live_gradient_colors": (
            settings.get("live_gradient_colors", ["#F8A5B8", "#C9A86C", "#FDF9F9"])
            if settings
            else ["#F8A5B8", "#C9A86C", "#FDF9F9"]
        ),
        "live_gradient_speed": (
            settings.get("live_gradient_speed", 10) if settings else 10
        ),
        "live_particles_enabled": (
            settings.get("live_particles_enabled", False) if settings else False
        ),
        "live_particles_color": (
            settings.get("live_particles_color", "#F8A5B8") if settings else "#F8A5B8"
        ),
        "live_particles_count": (
            settings.get("live_particles_count", 50) if settings else 50
        ),
    }


@router.put("/admin/store-settings/global-background")
async def update_global_background(background_data: dict, request: Request):
    """Update global site background settings"""
    await require_admin(request)

    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}

    # Static background fields
    if "global_site_background" in background_data:
        update_fields["global_site_background"] = background_data[
            "global_site_background"
        ]
    if "global_background_enabled" in background_data:
        update_fields["global_background_enabled"] = background_data[
            "global_background_enabled"
        ]
    if "global_background_opacity" in background_data:
        update_fields["global_background_opacity"] = background_data[
            "global_background_opacity"
        ]
    if "global_background_overlay_color" in background_data:
        update_fields["global_background_overlay_color"] = background_data[
            "global_background_overlay_color"
        ]

    # Live background fields
    if "live_background_type" in background_data:
        update_fields["live_background_type"] = background_data["live_background_type"]
    if "live_background_video_url" in background_data:
        update_fields["live_background_video_url"] = background_data[
            "live_background_video_url"
        ]
    if "live_gradient_colors" in background_data:
        update_fields["live_gradient_colors"] = background_data["live_gradient_colors"]
    if "live_gradient_speed" in background_data:
        update_fields["live_gradient_speed"] = background_data["live_gradient_speed"]
    if "live_particles_enabled" in background_data:
        update_fields["live_particles_enabled"] = background_data[
            "live_particles_enabled"
        ]
    if "live_particles_color" in background_data:
        update_fields["live_particles_color"] = background_data["live_particles_color"]
    if "live_particles_count" in background_data:
        update_fields["live_particles_count"] = background_data["live_particles_count"]

    await db.store_settings.update_one(
        {"id": "store_settings"}, {"$set": update_fields}, upsert=True
    )

    return {"message": "Global background updated successfully"}


@router.put("/admin/store-settings/thank-you-messages")
async def update_thank_you_messages(messages_data: dict, request: Request):
    """Update customizable thank you messages"""
    await require_admin(request)
    await db.store_settings.update_one(
        {"id": "store_settings"},
        {
            "$set": {
                "thank_you_messages": messages_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )
    return {"message": "Thank you messages updated"}


@router.put("/admin/store-settings/promo-banner")
async def update_promo_banner(banner_data: dict, request: Request):
    """Update site-wide promo banner settings"""
    await require_admin(request)

    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if "promo_banner_enabled" in banner_data:
        update_fields["promo_banner_enabled"] = banner_data["promo_banner_enabled"]
    if "promo_banner_title" in banner_data:
        update_fields["promo_banner_title"] = banner_data["promo_banner_title"]
    if "promo_banner_text" in banner_data:
        update_fields["promo_banner_text"] = banner_data["promo_banner_text"]
    if "promo_banner_code" in banner_data:
        update_fields["promo_banner_code"] = banner_data["promo_banner_code"]
    if "promo_banner_discount_percent" in banner_data:
        update_fields["promo_banner_discount_percent"] = banner_data[
            "promo_banner_discount_percent"
        ]
    if "promo_banner_bg_color" in banner_data:
        update_fields["promo_banner_bg_color"] = banner_data["promo_banner_bg_color"]
    if "promo_banner_text_color" in banner_data:
        update_fields["promo_banner_text_color"] = banner_data[
            "promo_banner_text_color"
        ]
    if "promo_banner_link" in banner_data:
        update_fields["promo_banner_link"] = banner_data["promo_banner_link"]
    if "promo_banner_position" in banner_data:
        update_fields["promo_banner_position"] = banner_data["promo_banner_position"]
    if "promo_banner_design" in banner_data:
        update_fields["promo_banner_design"] = banner_data["promo_banner_design"]
    # Exit Intent Modal control
    if "exit_modal_enabled" in banner_data:
        update_fields["exit_modal_enabled"] = banner_data["exit_modal_enabled"]

    await db.store_settings.update_one(
        {"id": "store_settings"}, {"$set": update_fields}, upsert=True
    )

    return {"message": "Promo banner updated successfully"}


@router.put("/admin/store-settings/first-purchase-discount")
async def update_first_purchase_discount(discount_data: dict, request: Request):
    """Update first purchase auto-discount settings"""
    await require_admin(request)

    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if "first_purchase_discount_enabled" in discount_data:
        update_fields["first_purchase_discount_enabled"] = discount_data[
            "first_purchase_discount_enabled"
        ]
    if "first_purchase_discount_percent" in discount_data:
        update_fields["first_purchase_discount_percent"] = float(
            discount_data["first_purchase_discount_percent"]
        )

    await db.store_settings.update_one(
        {"id": "store_settings"}, {"$set": update_fields}, upsert=True
    )

    return {"message": "First purchase discount updated successfully"}


@router.get("/admin/store-settings/auto-discounts")
async def get_auto_discount_settings(request: Request):
    """Get auto-discount settings for admin panel"""
    await require_admin(request)
    settings = (
        await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0}) or {}
    )

    founder_subsidy = settings.get("founder_subsidy", {})

    return {
        "founder_discount_enabled": settings.get("founder_discount_enabled", True),
        "founder_discount_percent": founder_subsidy.get("discount_percent", 50.0),
        "founder_discount_label": founder_subsidy.get(
            "label", "Founder's Launch Subsidy"
        ),
        "first_purchase_discount_enabled": settings.get(
            "first_purchase_discount_enabled", True
        ),
        "first_purchase_discount_percent": settings.get(
            "first_purchase_discount_percent", 10.0
        ),
        "voucher_gate_enabled": settings.get("influencer_program", {}).get(
            "voucher_gate_enabled", True
        ),
        "voucher_gate_threshold": settings.get("influencer_program", {}).get(
            "voucher_gate_threshold", 10
        ),
    }


@router.put("/admin/store-settings/auto-discounts")
async def update_auto_discount_settings(discount_data: dict, request: Request):
    """Update all auto-discount settings at once"""
    await require_admin(request)

    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}

    # Founder discount settings
    if "founder_discount_enabled" in discount_data:
        update_fields["founder_discount_enabled"] = discount_data[
            "founder_discount_enabled"
        ]

    if (
        "founder_discount_percent" in discount_data
        or "founder_discount_label" in discount_data
    ):
        # Get existing founder subsidy settings first
        settings = (
            await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0}) or {}
        )
        founder_subsidy = settings.get("founder_subsidy", {})

        if "founder_discount_percent" in discount_data:
            founder_subsidy["discount_percent"] = float(
                discount_data["founder_discount_percent"]
            )
        if "founder_discount_label" in discount_data:
            founder_subsidy["label"] = discount_data["founder_discount_label"]

        update_fields["founder_subsidy"] = founder_subsidy

    # First purchase discount settings
    if "first_purchase_discount_enabled" in discount_data:
        update_fields["first_purchase_discount_enabled"] = discount_data[
            "first_purchase_discount_enabled"
        ]
    if "first_purchase_discount_percent" in discount_data:
        update_fields["first_purchase_discount_percent"] = float(
            discount_data["first_purchase_discount_percent"]
        )

    # Voucher gate settings (in influencer_program)
    if (
        "voucher_gate_enabled" in discount_data
        or "voucher_gate_threshold" in discount_data
    ):
        settings = (
            await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0}) or {}
        )
        influencer_program = settings.get("influencer_program", {})

        if "voucher_gate_enabled" in discount_data:
            influencer_program["voucher_gate_enabled"] = discount_data[
                "voucher_gate_enabled"
            ]
        if "voucher_gate_threshold" in discount_data:
            influencer_program["voucher_gate_threshold"] = int(
                discount_data["voucher_gate_threshold"]
            )

        update_fields["influencer_program"] = influencer_program

    await db.store_settings.update_one(
        {"id": "store_settings"}, {"$set": update_fields}, upsert=True
    )

    return {"message": "Auto-discount settings updated successfully"}


@router.put("/admin/store-settings/first-purchase-code")
async def update_first_purchase_code(code_data: dict, request: Request):
    """Update first purchase CODE settings (special code for new customers only)"""
    await require_admin(request)

    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if "first_purchase_code_enabled" in code_data:
        update_fields["first_purchase_code_enabled"] = code_data[
            "first_purchase_code_enabled"
        ]
    if "first_purchase_code" in code_data:
        update_fields["first_purchase_code"] = code_data["first_purchase_code"].upper()
    if "first_purchase_code_percent" in code_data:
        update_fields["first_purchase_code_percent"] = float(
            code_data["first_purchase_code_percent"]
        )

    await db.store_settings.update_one(
        {"id": "store_settings"}, {"$set": update_fields}, upsert=True
    )

    return {"message": "First purchase code updated successfully"}


@router.post("/validate-discount-code")
async def validate_discount_code(data: dict):
    """Validate a discount code and return discount info"""
    code = data.get("code", "").upper()
    customer_email = data.get("email", "").lower()

    if not code:
        return {"valid": False, "message": "No code provided"}

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

    # Check if it's the first purchase code
    if fp_code_enabled and code == fp_code:
        if customer_email:
            # Check if customer has previous orders
            previous_orders = await db.orders.count_documents(
                {
                    "customer_email": customer_email,
                    "status": {"$nin": ["cancelled", "refunded"]},
                }
            )

            if previous_orders > 0:
                return {
                    "valid": False,
                    "message": "This code is only for first-time buyers. You already have previous orders.",
                    "code_type": "first_purchase",
                }

        return {
            "valid": True,
            "code_type": "first_purchase",
            "discount_type": "percentage",
            "discount_value": fp_code_percent,
            "message": f"🎉 First-time buyer discount! {fp_code_percent}% off your order!",
        }

    # Check if it's a partner code
    partner = await db.influencer_applications.find_one(
        {"partner_code": code, "status": "approved"}, {"_id": 0}
    )

    if partner:
        return {
            "valid": True,
            "code_type": "partner",
            "discount_type": "percentage",
            "discount_value": partner.get("custom_discount", 20),
            "partner_name": partner.get("full_name", "Partner"),
            "message": f"Partner discount: {partner.get('custom_discount', 20)}% off!",
        }

    # Check if it's a partner voucher
    voucher = await db.partner_vouchers.find_one(
        {"code": code, "is_active": True}, {"_id": 0}
    )

    if voucher:
        return {
            "valid": True,
            "code_type": "voucher",
            "discount_type": voucher.get("discount_type", "percentage"),
            "discount_value": voucher.get("discount_value", 0),
            "message": f"Voucher applied: {voucher.get('discount_value', 0)}{'%' if voucher.get('discount_type') == 'percentage' else '$'} off!",
        }

    # Check if it's a regular discount code
    regular_code = await db.discount_codes.find_one(
        {"code": code, "is_active": True}, {"_id": 0}
    )

    if regular_code:
        return {
            "valid": True,
            "code_type": "discount",
            "discount_type": regular_code.get("discount_type", "percentage"),
            "discount_value": regular_code.get(
                "discount_percent", regular_code.get("discount_amount", 0)
            ),
            "message": "Discount code applied!",
        }

    return {"valid": False, "message": "Invalid discount code"}


# ============ OFFERS & DISCOUNT CODE MANAGER ENDPOINTS ============


@router.get("/admin/offers")
async def get_all_offers(request: Request):
    """Get all email offers for admin"""
    await require_admin(request)
    offers = (
        await db.email_offers.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    )
    return offers


@router.post("/admin/offers")
async def create_offer(offer_data: dict, request: Request):
    """Create a new email offer"""
    await require_admin(request)

    offer = {
        "id": str(ObjectId()),
        "subject": offer_data.get("subject", "Special Offer!"),
        "title": offer_data.get("title", "Exclusive Discount"),
        "message": offer_data.get("message", ""),
        "discount_code": offer_data.get("discount_code", ""),
        "discount_percent": offer_data.get("discount_percent", 10),
        "is_exclusive": offer_data.get("is_exclusive", True),
        "expires_at": offer_data.get("expires_at"),
        "created_at": datetime.utcnow().isoformat(),
        "sent_count": 0,
    }

    await db.email_offers.insert_one(offer)
    return {"message": "Offer created", "offer_id": offer["id"]}


@router.delete("/admin/offers/{offer_id}")
async def delete_offer(offer_id: str, request: Request):
    """Delete an email offer"""
    await require_admin(request)
    result = await db.email_offers.delete_one({"id": offer_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Offer not found")
    return {"message": "Offer deleted"}


@router.get("/admin/discount-codes")
async def get_all_discount_codes(request: Request):
    """Get all discount codes for admin"""
    await require_admin(request)

    codes = (
        await db.discount_codes.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    )
    return codes


@router.post("/admin/discount-codes")
async def create_discount_code(code_data: dict, request: Request):
    """Create a new discount code"""
    await require_admin(request)

    code = code_data.get("code", "").upper().strip()
    
    # Auto-generate code if empty
    if not code:
        # Generate a random code like "SAVE" + percentage + random chars
        import random
        import string
        discount_val = code_data.get("discount_percent") or code_data.get("discount_value") or 10
        random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        code = f"SAVE{int(discount_val)}{random_suffix}"

    # Check if code already exists
    existing = await db.discount_codes.find_one({"code": code})
    if existing:
        raise HTTPException(status_code=400, detail="This code already exists")

    # Support both old and new field names
    discount_percent = float(code_data.get("discount_percent") or code_data.get("discount_value") or 10)
    min_order = float(code_data.get("min_order") or code_data.get("min_order_amount") or 0)
    max_uses_val = code_data.get("max_uses")
    max_uses = int(max_uses_val) if max_uses_val not in [None, "", "0"] else 0
    expires = code_data.get("expires_at") or code_data.get("end_date")

    new_code = {
        "id": str(uuid.uuid4()),
        "code": code,
        "type": code_data.get("type", "general"),
        "discount_type": "percentage",
        "discount_value": discount_percent,
        "discount_percent": discount_percent,
        "discount_amount": 0,
        "description": code_data.get("description", f"{int(discount_percent)}% discount"),
        "min_products": int(code_data.get("min_products", 1)),
        "min_order_amount": min_order,
        "max_uses": max_uses,
        "uses": 0,
        "uses_count": 0,
        "start_date": code_data.get("start_date"),
        "end_date": expires,
        "expires_at": expires,
        "is_active": code_data.get("is_active", True),
        "placements": code_data.get("placements", []),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.discount_codes.insert_one(new_code)

    # If banner placement selected, update store settings
    if "banner" in new_code["placements"]:
        await db.store_settings.update_one(
            {"id": "store_settings"},
            {
                "$set": {
                    "promo_banner_code": code,
                    "promo_banner_discount_percent": new_code["discount_value"],
                }
            },
            upsert=True,
        )

    return {"message": "Discount code created", "id": new_code["id"], "code": new_code["code"]}


@router.put("/admin/discount-codes/{code_id}")
async def update_discount_code(code_id: str, code_data: dict, request: Request):
    """Update a discount code"""
    await require_admin(request)

    existing = await db.discount_codes.find_one({"id": code_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Code not found")

    # Support both old and new field names
    discount_percent = float(code_data.get("discount_percent") or code_data.get("discount_value") or existing.get("discount_percent", 10))
    min_order = float(code_data.get("min_order") or code_data.get("min_order_amount") or existing.get("min_order_amount", 0))
    max_uses_val = code_data.get("max_uses")
    max_uses = int(max_uses_val) if max_uses_val not in [None, "", "0"] else existing.get("max_uses", 0)
    expires = code_data.get("expires_at") or code_data.get("end_date") or existing.get("expires_at")

    update_fields = {
        "code": code_data.get("code", existing["code"]).upper().strip(),
        "type": code_data.get("type", existing.get("type", "general")),
        "discount_type": "percentage",
        "discount_value": discount_percent,
        "discount_percent": discount_percent,
        "discount_amount": 0,
        "description": code_data.get("description", existing.get("description", f"{int(discount_percent)}% discount")),
        "min_products": int(code_data.get("min_products", existing.get("min_products", 1))),
        "min_order_amount": min_order,
        "max_uses": max_uses,
        "start_date": code_data.get("start_date", existing.get("start_date")),
        "end_date": expires,
        "expires_at": expires,
        "is_active": code_data.get("is_active") if "is_active" in code_data else existing.get("is_active", True),
        "placements": code_data.get("placements", existing.get("placements", [])),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.discount_codes.update_one({"id": code_id}, {"$set": update_fields})

    return {"message": "Discount code updated", "code": update_fields["code"]}


@router.delete("/admin/discount-codes/{code_id}")
async def delete_discount_code(code_id: str, request: Request):
    """Delete a discount code"""
    await require_admin(request)

    result = await db.discount_codes.delete_one({"id": code_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Code not found")

    return {"message": "Discount code deleted"}


@router.get("/promo-banner")
async def get_promo_banner():
    """Get promo banner for public display"""
    settings = await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0})
    if not settings:
        return {"enabled": False}

    return {
        "enabled": settings.get("promo_banner_enabled", False),
        "text": settings.get("promo_banner_text", ""),
        "code": settings.get("promo_banner_code", ""),
        "discount_percent": settings.get("promo_banner_discount_percent", 0),
        "bg_color": settings.get("promo_banner_bg_color", "#F8A5B8"),
        "text_color": settings.get("promo_banner_text_color", "#FFFFFF"),
        "link": settings.get("promo_banner_link", "/shop"),
    }


@router.post("/admin/upload-digital-file")
async def upload_digital_file(
    file: UploadFile, request: Request, file_type: str = "booklet"
):
    """Upload digital files for delivery after purchase"""
    await require_admin(request)

    os.makedirs("uploads/digital", exist_ok=True)
    ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
    filename = f"digital_{file_type}_{uuid4().hex[:8]}.{ext}"
    filepath = f"uploads/digital/{filename}"

    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    file_url = (
        f"{os.environ.get('REACT_APP_BACKEND_URL', '')}/api/uploads/digital/{filename}"
    )

    return {"url": file_url, "filename": filename, "type": file_type}


@router.put("/admin/store-settings/live-chat")
async def update_live_chat_settings(chat_data: dict, request: Request):
    await require_admin(request)
    await db.store_settings.update_one(
        {"id": "store_settings"},
        {
            "$set": {
                "live_chat": chat_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )
    return {"message": "Live chat settings updated"}


@router.put("/admin/store-settings/google-business")
async def update_google_business_settings(google_data: dict, request: Request):
    await require_admin(request)
    await db.store_settings.update_one(
        {"id": "store_settings"},
        {
            "$set": {
                "google_business": google_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )
    return {"message": "Google Business settings updated"}


