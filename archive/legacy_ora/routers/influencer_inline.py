"""
Influencer, referral, vouchers, partner, founding member referral
Extracted from server.py during modularization.
"""

import os
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
    send_partner_approved_whatsapp, send_partner_denied_whatsapp,
    send_goal_achieved_email,
)
try:
    from models.server_models import StoreSettings
except ImportError:
    pass

logger = logging.getLogger(__name__)
try:
    from middleware.websocket_manager import broadcast_admin_event
except ImportError:
    async def broadcast_admin_event(*args, **kwargs): pass

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

# ============= INFLUENCER & REFERRAL PROGRAM =============


@router.get("/influencer-page")
async def get_influencer_page_content():
    """Public endpoint - get influencer landing page content"""
    content = await db.influencer_page.find_one({"id": "influencer_page"}, {"_id": 0})

    if not content:
        # Default content
        content = {
            "id": "influencer_page",
            "hero": {
                "title": "Join the ReRoots Family",
                "subtitle": "Partner with Canada's Premier Professional-Strength Skincare Brand",
                "description": "Become an influencer partner and earn while sharing science-backed skincare with your audience.",
                "image": "https://files.catbox.moe/jdjokm.jpg",
                "badge_text": "GOLD PARTNER PROGRAM",
            },
            "about": {
                "title": "About ReRoots",
                "description": "ReRoots is a Canadian skincare brand specializing in professional-strength formulations powered by PDRN technology. Our products are developed with dermatologist input and backed by scientific research to deliver real results.",
                "highlights": [
                    {"icon": "beaker", "text": "PDRN Science Technology"},
                    {"icon": "maple-leaf", "text": "Formulated in Canada"},
                    {"icon": "shield", "text": "Professional-Strength Quality"},
                    {"icon": "heart", "text": "Cruelty-Free & Vegan"},
                ],
            },
            "benefits": {
                "title": "Partner Benefits",
                "items": [
                    {
                        "title": "High Commission",
                        "description": "Earn up to 15% commission on every sale",
                        "icon": "dollar-sign",
                    },
                    {
                        "title": "Exclusive Discounts",
                        "description": "Give your audience 20% off with your unique code",
                        "icon": "gift",
                    },
                    {
                        "title": "Free Products",
                        "description": "Receive complimentary products to try and review",
                        "icon": "package",
                    },
                    {
                        "title": "Monthly Bonuses",
                        "description": "Top performers earn up to $500 monthly bonus",
                        "icon": "trophy",
                    },
                ],
            },
            "products": {"title": "Our Featured Products", "show_featured": True},
            "cta": {
                "title": "Ready to Join?",
                "description": "Apply now and start your journey as a ReRoots Gold Partner",
                "button_text": "Apply Now",
            },
        }

    # Get featured products
    products = (
        await db.products.find({"is_active": True}, {"_id": 0}).limit(4).to_list(4)
    )
    content["featured_products"] = products

    # Get program info
    settings = await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0})
    if settings:
        inf = settings.get("influencer_program", {})
        content["program_info"] = {
            "commission_rate": inf.get("commission_rate", 10),
            "customer_discount": inf.get("customer_discount_value", 50),
        }

    return content


@router.put("/admin/influencer-page")
async def update_influencer_page_content(data: dict, request: Request):
    """Admin - update influencer landing page content"""
    await require_admin(request)

    data["id"] = "influencer_page"
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.influencer_page.update_one(
        {"id": "influencer_page"}, {"$set": data}, upsert=True
    )

    return {"message": "Influencer page updated successfully"}


class InfluencerLandingSettings(BaseModel):
    banner_enabled: bool = True
    banner_text: str = "50% OFF"
    banner_color: str = "#FFD700"
    hero_image_url: str = ""
    hero_product_image_url: str = ""
    show_oroe_tier: bool = True
    show_reroots_tier: bool = True
    show_lavela_tier: bool = True
    oroe_commission: int = 25
    oroe_discount: int = 15
    oroe_bonus: int = 1000
    reroots_commission: int = 15
    reroots_discount: int = 20
    reroots_bonus: int = 500
    lavela_commission: int = 12
    lavela_discount: int = 25
    lavela_bonus: int = 250


@router.get("/admin/influencer-landing-settings")
async def get_influencer_landing_settings(request: Request):
    """Admin - get influencer landing page settings"""
    await require_admin(request)
    
    settings = await db.influencer_landing_settings.find_one(
        {"id": "landing_settings"}, {"_id": 0}
    )
    
    if not settings:
        settings = InfluencerLandingSettings().model_dump()
    
    return settings


@router.post("/admin/influencer-landing-settings")
async def update_influencer_landing_settings(data: InfluencerLandingSettings, request: Request):
    """Admin - update influencer landing page settings"""
    await require_admin(request)
    
    settings_dict = data.model_dump()
    settings_dict["id"] = "landing_settings"
    settings_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.influencer_landing_settings.update_one(
        {"id": "landing_settings"},
        {"$set": settings_dict},
        upsert=True
    )
    
    return {"message": "Landing page settings saved successfully"}


@router.get("/influencer-landing-settings")
async def get_public_influencer_landing_settings():
    """Public - get influencer landing page settings for display"""
    settings = await db.influencer_landing_settings.find_one(
        {"id": "landing_settings"}, {"_id": 0}
    )
    
    if not settings:
        settings =