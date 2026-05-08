"""
Newsletter, SMS subscribers, subscriptions
Extracted from server.py during modularization.
"""

import os
import asyncio
import logging
import json
import hashlib
import secrets
import time
import uuid
import re
import base64
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Request, Query, Body, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
from utils.stubs import (
    send_newsletter_confirmation_email, send_sms_notification,
    send_oroe_vip_approval_email, cleanup_broken_images,
)
from routers.auth_inline import require_auth
try:
    from models.server_models import User, Category, Product, Review, Role, RoleCreate, SubscriptionPlan, SubscriptionSettings, CustomerSubscription, ChatMessage, ChatRequest, TypographySettings, HomepageSection, TeamMember, TeamMemberCreate, TeamMemberInvite, AboutPageContent, AdCampaign, AdCampaignCreate
except ImportError:
    pass
try:
    from services.email_templates import validate_password_strength
except ImportError:
    pass

logger = logging.getLogger(__name__)
def check_permission(*args, **kwargs): return True  # Stub
async def invalidate_cache(*args, **kwargs): pass  # Stub
async def get_cached(*args, **kwargs): return None  # Stub
try:
    from models.server_models import SUPPORTED_CURRENCIES, COUNTRY_TO_CURRENCY, AD_PLATFORMS, DEFAULT_PERMISSIONS, SUPER_ADMIN_PERMISSIONS
except ImportError:
    SUPPORTED_CURRENCIES = ['USD','CAD','EUR','GBP']
    COUNTRY_TO_CURRENCY = {}
    AD_PLATFORMS = []
    DEFAULT_PERMISSIONS = {}
    SUPER_ADMIN_PERMISSIONS = {}
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

def get_claude_api_key():
    return EMERGENT_LLM_KEY or os.environ.get('CLAUDE_API_KEY', '') or os.environ.get('ANTHROPIC_API_KEY', '')
def hash_password(password):
    import bcrypt
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY', '')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '')
try:
    import cloudinary
    import cloudinary.uploader
except ImportError:
    cloudinary = None
async def require_super_admin(request):
    from routers.auth_inline import require_auth
    user = await require_auth(request)
    if not user.get('is_admin'): from fastapi import HTTPException; raise HTTPException(403, 'Admin required')
    return user

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
JWT_ALGORITHM = "HS256"
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

# ============= NEWSLETTER SUBSCRIBERS =============


@router.post("/newsletter/subscribe")
async def subscribe_newsletter(data: dict):
    email = data.get("email")
    phone = data.get("phone")
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    phone_country_code = data.get("phone_country_code", "+1")
    prefer_email = data.get("prefer_email", True)
    prefer_sms = data.get("prefer_sms", False)

    # At least one contact method required
    if not email and not phone:
        raise HTTPException(status_code=400, detail="Email or phone number required")

    # At least one preference must be enabled
    if not prefer_email and not prefer_sms:
        raise HTTPException(
            status_code=400,
            detail="Please select at least one notification method (Email or SMS)",
        )

    # Check existing by email or phone
    query = {}
    if email:
        query = {"email": email.lower().strip()}
    elif phone:
        query = {"phone": phone.strip()}

    existing = await db.newsletter_subscribers.find_one(query)
    if existing:
        # Update preferences if already subscribed
        await db.newsletter_subscribers.update_one(
            query,
            {
                "$set": {
                    "prefer_email": prefer_email,
                    "prefer_sms": prefer_sms,
                    "phone": phone.strip() if phone else existing.get("phone"),
                    "phone_country_code": phone_country_code,
                    "email": email.lower().strip() if email else existing.get("email"),
                    "first_name": first_name or existing.get("first_name", ""),
                    "last_name": last_name or existing.get("last_name", ""),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
        return {"message": "Preferences updated successfully"}

    # Get thank you message from store settings
    store_settings = await db.store_settings.find_one({}, {"_id": 0})
    thank_you_message = (
        store_settings.get("thank_you_messages", {}).get("subscription")
        if store_settings
        else None
    )

    await db.newsletter_subscribers.insert_one(
        {
            "id": str(uuid.uuid4()),
            "email": email.lower().strip() if email else None,
            "phone": phone.strip() if phone else None,
            "phone_country_code": phone_country_code,
            "first_name": first_name,
            "last_name": last_name,
            "prefer_email": prefer_email,
            "prefer_sms": prefer_sms,
            "subscribed_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True,
        }
    )

    # Send confirmation email if email provided and email preference is enabled
    if email and prefer_email:
        asyncio.create_task(
            send_newsletter_confirmation_email(email.lower().strip(), thank_you_message)
        )

    return {"message": "Subscribed successfully"}


# ============= SMS SUBSCRIBERS (Exit Intent Popup) =============

@router.post("/sms-subscribers")
async def add_sms_subscriber(data: dict):
    """
    Add a phone number to SMS marketing list.
    Used by exit-intent popup on ALL product pages and other site pages.
    Automatically works for new products - no configuration needed.
    """
    phone = data.get("phone", "").strip()
    email = data.get("email", "").strip() if data.get("email") else None
    source = data.get("source", "unknown")  # exit_popup, product_page_popup, cart_page, checkout
    page_url = data.get("page_url", "")
    product_name = data.get("product_name")  # Captured if signup was on a product page
    
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required")
    
    # Normalize phone number - ensure it starts with +
    if not phone.startswith("+"):
        # Assume North American if 10 digits
        digits = re.sub(r'\D', '', phone)
        if len(digits) == 10:
            phone = f"+1{digits}"
        elif len(digits) == 11 and digits.startswith("1"):
            phone = f"+{digits}"
        else:
            phone = f"+{digits}"
    
    # Check if already subscribed
    existing = await db.sms_subscribers.find_one({"phone": phone})
    if existing:
        # Update email if provided and not already set
        update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if email and not existing.get("email"):
            update_data["email"] = email.lower()
        if product_name and product_name not in (existing.get("interested_products") or []):
            # Track products user showed interest in
            update_data["$push"] = {"interested_products": product_name}
        
        if "$push" in update_data:
            push_data = update_data.pop("$push")
            await db.sms_subscribers.update_one(
                {"phone": phone},
                {"$set": update_data, "$push": push_data}
            )
        else:
            await db.sms_subscribers.update_one(
                {"phone": phone},
                {"$set": update_data}
            )
        raise HTTPException(status_code=409, detail="Phone number already subscribed")
    
    # Create new subscriber with product interest tracking
    subscriber = {
        "id": str(uuid.uuid4()),
        "phone": phone,
        "email": email.lower() if email else None,
        "source": source,
        "page_url": page_url,
        "product_name": product_name,  # Product they were viewing when they signed up
        "interested_products": [product_name] if product_name else [],
        "subscribed_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True,
        "sms_consent": True,
        "whatsapp_consent": True,  # Also enable for WhatsApp marketing
        "offers_sent": 0,
        "last_offer_sent": None
    }
    
    await db.sms_subscribers.insert_one(subscriber)
    
    # Try to send welcome SMS with discount code
    try:
        if product_name:
            welcome_message = f"ReRoots: Thanks for your interest in {product_name}! Use code SMS10 for 10% off. Shop: https://reroots.ca/shop"
        else:
            welcome_message = "ReRoots: Welcome! Use code SMS10 for 10% off your first order. Shop: https://reroots.ca/shop"
        await send_sms_notification(phone, welcome_message)
        logging.info(f"[SMS Subscriber] Welcome SMS sent to {phone[:7]}***")
    except Exception as e:
        logging.warning(f"[SMS Subscriber] Failed to send welcome SMS: {e}")
    
    return {"message": "Successfully subscribed to SMS offers", "discount_code": "SMS10"}


@router.get("/admin/sms-subscribers")
async def get_sms_subscribers(request: Request):
    """Admin endpoint to view all SMS subscribers"""
    await require_admin(request)
    
    subscribers = await db.sms_subscribers.find(
        {}, {"_id": 0}
    ).sort("subscribed_at", -1).to_list(5000)
    
    return {"subscribers": subscribers, "total": len(subscribers)}


@router.delete("/admin/sms-subscribers/{subscriber_id}")
async def delete_sms_subscriber(subscriber_id: str, request: Request):
    """Admin endpoint to remove an SMS subscriber"""
    await require_admin(request)
    
    result = await db.sms_subscribers.delete_one({"id": subscriber_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    return {"message": "Subscriber removed"}


@router.post("/waitlist")
async def join_product_waitlist(data: dict):
    """Add user to product waitlist for out-of-stock notifications"""
    email = data.get("email")
    product_id = data.get("product_id")
    product_name = data.get("product_name")

    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    # Check if already on waitlist
    existing = await db.product_waitlist.find_one(
        {"email": email.lower().strip(), "product_id": product_id}
    )

    if existing:
        return {"message": "You're already on the waitlist!"}

    await db.product_waitlist.insert_one(
        {
            "id": str(uuid.uuid4()),
            "email": email.lower().strip(),
            "product_id": product_id,
            "product_name": product_name,
            "joined_at": datetime.now(timezone.utc).isoformat(),
            "notified": False,
        }
    )

    return {"message": "Added to waitlist successfully"}


@router.get("/admin/waitlist")
async def get_waitlist(request: Request):
    """Get all waitlist entries from multiple sources"""
    await require_admin(request)

    # Check multiple waitlist collections
    entries = []

    # product_waitlist
    product_wl = (
        await db.product_waitlist.find({}, {"_id": 0})
        .sort("joined_at", -1)
        .to_list(10000)
    )
    for w in product_wl:
        w["source"] = "product_waitlist"
        entries.append(w)

    # waitlist collection
    waitlist = (
        await db.waitlist.find({}, {"_id": 0}).sort("created_at", -1).to_list(10000)
    )
    for w in waitlist:
        w["source"] = "waitlist"
        entries.append(w)

    # waitlist_entries collection
    wl_entries = (
        await db.waitlist_entries.find({}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(10000)
    )
    for w in wl_entries:
        w["source"] = "waitlist_entries"
        entries.append(w)

    return {"entries": entries, "total": len(entries)}


@router.get("/admin/newsletter-subscribers")
async def get_newsletter_subscribers(request: Request):
    await require_admin(request)
    subscribers = (
        await db.newsletter_subscribers.find({"is_active": True}, {"_id": 0})
        .sort("subscribed_at", -1)
        .to_list(10000)
    )
    return subscribers


@router.get("/admin/all-subscribers")
async def get_all_subscribers(
    request: Request, source: str = None, page: int = 1, limit: int = 50
):
    """
    Get all email subscribers from all sources with source tracking.
    Sources: bio_scan, newsletter, waitlist, checkout, referral, google_auth
    """
    await require_admin(request)

    # Aggregate all email sources
    all_subscribers = []

    # 1. Bio-Scan submissions (include both email and phone-only entries)
    bio_scan_query = (
        {"$or": [{"email": {"$ne": ""}}, {"phone": {"$ne": ""}}]}
        if not source or source == "bio_scan"
        else {
            "$and": [
                {"$or": [{"email": {"$ne": ""}}, {"phone": {"$ne": ""}}]},
                {"_never_match": True},
            ]
        }
    )
    bio_scans = (
        await db.bio_scans.find(
            bio_scan_query,
            {
                "_id": 0,
                "email": 1,
                "phone": 1,
                "referral_code": 1,
                "bio_age_offset": 1,
                "risk_level": 1,
                "created_at": 1,
            },
        ).to_list(10000)
        if not source or source == "bio_scan"
        else []
    )

    for scan in bio_scans:
        all_subscribers.append(
            {
                "email": scan.get("email", ""),
                "phone": scan.get("phone", ""),
                "source": "bio_scan",
                "source_display": "Bio-Age Quiz",
                "referral_code": scan.get("referral_code"),
                "extra_data": {
                    "bio_age_offset": scan.get("bio_age_offset"),
                    "risk_level": scan.get("risk_level"),
                },
                "created_at": scan.get("created_at"),
            }
        )

    # 2. Waitlist / Founding Members
    waitlist = (
        await db.waitlist.find(
            (
                {"email": {"$ne": ""}}
                if not source or source == "waitlist"
                else {"$and": [{"email": {"$ne": ""}}, {"_never_match": True}]}
            ),
            {"_id": 0},
        ).to_list(10000)
        if not source or source == "waitlist"
        else []
    )

    for w in waitlist:
        w_source = w.get("source", "waitlist")
        all_subscribers.append(
            {
                "email": w.get("email", ""),
                "phone": w.get("phone", ""),
                "name": w.get("name", ""),
                "source": w_source,
                "source_display": {
                    "bio_scan": "Bio-Age Quiz",
                    "waitlist": "Founding Members",
                    "reddit": "Reddit Campaign",
                    "referral": "Referral Program",
                    "organic": "Organic Signup",
                }.get(w_source, w_source.replace("_", " ").title()),
                "referral_code": w.get("referral_code"),
                "referred_by": w.get("referred_by"),
                "verified_referrals": w.get("verified_referrals", 0),
                "utm_source": w.get("utm_source"),
                "utm_campaign": w.get("utm_campaign"),
                "created_at": w.get("created_at"),
            }
        )

    # 3. Newsletter subscribers
    newsletter = (
        await db.newsletter_subscribers.find(
            (
                {"is_active": True}
                if not source or source == "newsletter"
                else {"$and": [{"is_active": True}, {"_never_match": True}]}
            ),
            {"_id": 0},
        ).to_list(10000)
        if not source or source == "newsletter"
        else []
    )

    for n in newsletter:
        all_subscribers.append(
            {
                "email": n.get("email", ""),
                "source": "newsletter",
                "source_display": "Newsletter",
                "created_at": n.get("subscribed_at"),
            }
        )

    # 4. Users (from registration/checkout)
    users = (
        await db.users.find(
            (
                {"email": {"$ne": ""}}
                if not source or source in ["checkout", "google_auth"]
                else {"$and": [{"email": {"$ne": ""}}, {"_never_match": True}]}
            ),
            {
                "_id": 0,
                "email": 1,
                "first_name": 1,
                "last_name": 1,
                "phone": 1,
                "created_at": 1,
                "google_id": 1,
                "loyalty_points": 1,
            },
        ).to_list(10000)
        if not source or source in ["checkout", "google_auth", "registered"]
        else []
    )

    for u in users:
        u_source = "google_auth" if u.get("google_id") else "registered"
        all_subscribers.append(
            {
                "email": u.get("email", ""),
                "phone": u.get("phone", ""),
                "name": f"{u.get('first_name', '')} {u.get('last_name', '')}".strip(),
                "source": u_source,
                "source_display": (
                    "Google Sign-in" if u.get("google_id") else "Account Registration"
                ),
                "loyalty_points": u.get("loyalty_points", 0),
                "created_at": u.get("created_at"),
            }
        )

    # 7. Influencer/Partner Applications
    influencers = (
        await db.influencer_applications.find(
            (
                {"email": {"$ne": ""}}
                if not source or source == "influencer"
                else {"$and": [{"email": {"$ne": ""}}, {"_never_match": True}]}
            ),
            {
                "_id": 0,
                "email": 1,
                "full_name": 1,
                "phone": 1,
                "instagram_handle": 1,
                "status": 1,
                "referral_code": 1,
                "total_earnings": 1,
                "created_at": 1,
            },
        ).to_list(10000)
        if not source or source == "influencer"
        else []
    )

    for inf in influencers:
        all_subscribers.append(
            {
                "email": inf.get("email", ""),
                "phone": inf.get("phone", ""),
                "name": inf.get("full_name", ""),
                "source": "influencer",
                "source_display": "Partner/Influencer",
                "extra_data": {
                    "instagram": inf.get("instagram_handle"),
                    "status": inf.get("status"),
                    "referral_code": inf.get("referral_code"),
                    "earnings": inf.get("total_earnings", 0),
                },
                "created_at": inf.get("created_at"),
            }
        )

    # Remove duplicates by email OR phone (keep influencer > most recent)
    # Priority sources that should be preserved even with newer duplicates
    priority_sources = ["influencer", "bio_scan"]
    
    seen = {}  # key: email or phone
    for sub in all_subscribers:
        email = (sub.get("email") or "").lower().strip()
        phone = (sub.get("phone") or "").strip()

        # Use email as key if available, otherwise use phone
        key = email if email else (f"phone:{phone}" if phone else None)

        if not key:
            continue
            
        if key not in seen:
            seen[key] = sub
        else:
            existing_source = seen[key].get("source", "")
            new_source = sub.get("source", "")
            
            # Prioritize influencer/partner entries over other sources
            if new_source in priority_sources and existing_source not in priority_sources:
                seen[key] = sub
            elif new_source not in priority_sources and existing_source in priority_sources:
                pass  # Keep existing priority source
            elif (sub.get("created_at") or "") > (seen[key].get("created_at") or ""):
                seen[key] = sub

    unique_subscribers = list(seen.values())

    # Sort by created_at descending (handle None values)
    unique_subscribers.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    # Apply pagination
    total = len(unique_subscribers)
    start = (page - 1) * limit
    end = start + limit
    paginated = unique_subscribers[start:end]

    # Get source counts
    source_counts = {}
    for sub in unique_subscribers:
        src = sub.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1

    return {
        "subscribers": paginated,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit,
        "source_counts": source_counts,
        "sources": [
            {
                "value": "bio_scan",
                "label": "Bio-Age Quiz",
                "count": source_counts.get("bio_scan", 0),
            },
            {
                "value": "waitlist",
                "label": "Founding Members",
                "count": source_counts.get("waitlist", 0),
            },
            {
                "value": "newsletter",
                "label": "Newsletter",
                "count": source_counts.get("newsletter", 0),
            },
            {
                "value": "registered",
                "label": "Account Registration",
                "count": source_counts.get("registered", 0),
            },
            {
                "value": "google_auth",
                "label": "Google Sign-in",
                "count": source_counts.get("google_auth", 0),
            },
            {
                "value": "reddit",
                "label": "Reddit Campaign",
                "count": source_counts.get("reddit", 0),
            },
            {
                "value": "referral",
                "label": "Referral Program",
                "count": source_counts.get("referral", 0),
            },
            {
                "value": "influencer",
                "label": "Partner/Influencer",
                "count": source_counts.get("influencer", 0),
            },
        ],
    }


@router.post("/admin/send-individual-offer")
async def send_individual_offer(data: dict, request: Request):
    """Send a personalized offer email to a specific subscriber"""
    await require_admin(request)

    email = data.get("email")
    name = data.get("name", "")
    subject = data.get("subject", "🎁 Special Offer Just For You!")
    message = data.get("message", "")
    discount_code = data.get("discount_code", "")
    discount_percent = data.get("discount_percent", 0)

    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    try:
        # Format the email HTML
        html_content = f"""
        <div style="font-family: 'Helvetica Neue', Arial, sans-serif; max-width: 600px; margin: 0 auto; background: #fff;">
            <div style="background: linear-gradient(135deg, #F8A5B8 0%, #D4AF37 100%); padding: 30px; text-align: center;">
                <h1 style="color: #fff; margin: 0; font-size: 28px;">ReRoots Aesthetics</h1>
                <p style="color: #fff; opacity: 0.9; margin-top: 5px;">Canadian Biotech Skincare</p>
            </div>
            
            <div style="padding: 40px 30px;">
                <p style="font-size: 18px; color: #2D2A2E;">Hi {name or 'there'},</p>
                
                <div style="margin: 25px 0; padding: 20px; background: #FDF9F9; border-radius: 12px; white-space: pre-line;">
                    {message}
                </div>
                
                {f'''
                <div style="text-align: center; margin: 30px 0;">
                    <div style="display: inline-block; background: linear-gradient(135deg, #F8A5B8 0%, #D4AF37 100%); padding: 20px 40px; border-radius: 12px;">
                        <p style="margin: 0; color: #fff; font-size: 14px;">Your Exclusive Code</p>
                        <p style="margin: 5px 0 0; color: #fff; font-size: 28px; font-weight: bold; letter-spacing: 3px;">{discount_code}</p>
                        <p style="margin: 5px 0 0; color: #fff; font-size: 14px;">{discount_percent}% OFF</p>
                    </div>
                </div>
                ''' if discount_code else ''}
                
                <div style="text-align: center; margin-top: 30px;">
                    <a href="https://reroots.ca/products" style="display: inline-block; background: #2D2A2E; color: #fff; padding: 15px 40px; border-radius: 30px; text-decoration: none; font-weight: bold;">
                        Shop Now
                    </a>
                </div>
            </div>
            
            <div style="background: #2D2A2E; padding: 25px; text-align: center;">
                <p style="color: #fff; opacity: 0.8; margin: 0; font-size: 12px;">
                    © 2025 ReRoots Aesthetics Inc. | Toronto, Canada 🇨🇦
                </p>
            </div>
        </div>
        """

        # Try to send via Resend
        resend_key = os.environ.get("RESEND_API_KEY")
        if resend_key:
            import resend

            resend.api_key = resend_key

            resend.Emails.send(
                {
                    "from": "ReRoots Aesthetics <offers@reroots.ca>",
                    "to": [email],
                    "subject": subject,
                    "html": html_content,
                }
            )

            # Log the sent offer
            await db.sent_offers.insert_one(
                {
                    "email": email,
                    "name": name,
                    "subject": subject,
                    "discount_code": discount_code,
                    "discount_percent": discount_percent,
                    "sent_at": datetime.now(timezone.utc),
                    "status": "sent",
                }
            )

            return {"success": True, "message": f"Offer sent to {email}"}
        else:
            # Log as pending if no email service
            await db.sent_offers.insert_one(
                {
                    "email": email,
                    "name": name,
                    "subject": subject,
                    "discount_code": discount_code,
                    "discount_percent": discount_percent,
                    "sent_at": datetime.now(timezone.utc),
                    "status": "logged_no_email_service",
                }
            )
            return {
                "success": True,
                "message": f"Offer logged for {email} (email service not configured)",
            }

    except Exception as e:
        logging.error(f"Failed to send individual offer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============= AI CHAT ASSISTANT ROUTES =============


@router.post("/admin/chat")
async def send_chat_message(chat_req: ChatRequest, request: Request):
    await require_admin(request)
    
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    # Store user message
    user_msg = ChatMessage(
        session_id=chat_req.session_id, role="user", content=chat_req.message
    )
    user_msg_dict = user_msg.model_dump()
    user_msg_dict["created_at"] = user_msg_dict["created_at"].isoformat()
    await db.chat_messages.insert_one(user_msg_dict)

    # Get chat history for context
    history = (
        await db.chat_messages.find({"session_id": chat_req.session_id}, {"_id": 0})
        .sort("created_at", 1)
        .to_list(50)
    )

    # Build context from history
    history_text = ""
    for msg in history[-10:]:  # Last 10 messages for context
        role = "User" if msg["role"] == "user" else "Assistant"
        history_text += f"{role}: {msg['content']}\n"

    # Determine provider and model
    provider = "openai"
    model = chat_req.model
    if "claude" in model.lower():
        provider = "anthropic"
    elif "gemini" in model.lower():
        provider = "gemini"

    system_message = """You are a helpful AI assistant for ReRoots Skincare admin panel. You help the store owner with:
- Managing products, orders, and inventory
- Website content and design suggestions
- Marketing and business advice
- Technical support for the e-commerce platform
- Customer service best practices

Be friendly, professional, and concise. If asked about specific store data, explain that you can help guide them to the right section of the admin panel."""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=chat_req.session_id,
            system_message=system_message,
        ).with_model(provider, model)

        # Create message with history context
        full_message = f"Previous conversation:\n{history_text}\n\nCurrent question: {chat_req.message}"
        user_message = UserMessage(text=full_message)

        response = await chat.send_message(user_message)

        # Store assistant message
        assistant_msg = ChatMessage(
            session_id=chat_req.session_id, role="assistant", content=response
        )
        assistant_msg_dict = assistant_msg.model_dump()
        assistant_msg_dict["created_at"] = assistant_msg_dict["created_at"].isoformat()
        await db.chat_messages.insert_one(assistant_msg_dict)

        return {"response": response, "session_id": chat_req.session_id}
    except Exception as e:
        logging.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@router.get("/admin/chat/history/{session_id}")
async def get_chat_history(session_id: str, request: Request):
    await require_admin(request)
    messages = (
        await db.chat_messages.find({"session_id": session_id}, {"_id": 0})
        .sort("created_at", 1)
        .to_list(100)
    )
    return messages


@router.delete("/admin/chat/history/{session_id}")
async def clear_chat_history(session_id: str, request: Request):
    await require_admin(request)
    await db.chat_messages.delete_many({"session_id": session_id})
    return {"message": "Chat history cleared"}


# ============= TYPOGRAPHY SETTINGS ROUTES =============


@router.get("/typography-settings")
async def get_typography_settings():
    settings = await db.typography_settings.find_one(
        {"id": "typography_settings"}, {"_id": 0}
    )
    if not settings:
        default_settings = TypographySettings()
        settings_dict = default_settings.model_dump()
        settings_dict["updated_at"] = settings_dict["updated_at"].isoformat()
        await db.typography_settings.insert_one(settings_dict)
        settings = await db.typography_settings.find_one(
            {"id": "typography_settings"}, {"_id": 0}
        )
    return settings


@router.put("/admin/typography-settings")
async def update_typography_settings(settings_data: dict, request: Request):
    await require_admin(request)
    settings_data["id"] = "typography_settings"
    settings_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.typography_settings.update_one(
        {"id": "typography_settings"}, {"$set": settings_data}, upsert=True
    )

    updated = await db.typography_settings.find_one(
        {"id": "typography_settings"}, {"_id": 0}
    )
    return updated


# ============= HOMEPAGE SECTIONS ROUTES =============


@router.get("/homepage-sections")
async def get_homepage_sections():
    sections = (
        await db.homepage_sections.find({"is_active": True}, {"_id": 0})
        .sort("order", 1)
        .to_list(50)
    )

    # If no sections exist, create default ones
    if not sections:
        default_sections = [
            HomepageSection(
                id="section-our-story",
                title="Our Story",
                subtitle="The ReRoots Journey",
                content="Founded with a passion for clean, effective skincare, ReRoots combines cutting-edge biotechnology with natural ingredients. Our journey began with a simple belief: everyone deserves access to scientifically-backed skincare that delivers real results.",
                image_url="https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=800",
                image_position="right",
                background_color="#FDF9F9",
                section_type="our_story",
                order=1,
            ),
            HomepageSection(
                id="section-our-mission",
                title="Our Mission",
                subtitle="Science Meets Nature",
                content="We're on a mission to revolutionize skincare through innovative formulations that harness the power of PDRN technology. Every product we create is backed by research, tested for efficacy, and designed to deliver visible results.",
                image_url="https://images.unsplash.com/photo-1570194065650-d99fb4b38b17?w=800",
                image_position="left",
                background_color="#FFFFFF",
                section_type="our_mission",
                order=2,
            ),
        ]

        for section in default_sections:
            section_dict = section.model_dump()
            section_dict["created_at"] = section_dict["created_at"].isoformat()
            await db.homepage_sections.insert_one(section_dict)

        sections = (
            await db.homepage_sections.find({"is_active": True}, {"_id": 0})
            .sort("order", 1)
            .to_list(50)
        )

    return sections


@router.get("/admin/homepage-sections")
async def get_admin_homepage_sections(request: Request):
    await require_admin(request)
    sections = (
        await db.homepage_sections.find({}, {"_id": 0}).sort("order", 1).to_list(50)
    )
    return sections


@router.post("/admin/homepage-sections")
async def create_homepage_section(section_data: dict, request: Request):
    await require_admin(request)

    # Get max order
    max_section = await db.homepage_sections.find_one(sort=[("order", -1)])
    max_order = max_section.get("order", 0) if max_section else 0

    section = HomepageSection(
        title=section_data.get("title", "New Section"),
        subtitle=section_data.get("subtitle"),
        content=section_data.get("content", ""),
        image_url=section_data.get("image_url"),
        image_position=section_data.get("image_position", "right"),
        background_color=section_data.get("background_color", "#FFFFFF"),
        text_color=section_data.get("text_color", "#2D2A2E"),
        button_text=section_data.get("button_text"),
        button_link=section_data.get("button_link"),
        order=max_order + 1,
        section_type=section_data.get("section_type", "custom"),
    )

    section_dict = section.model_dump()
    section_dict["created_at"] = section_dict["created_at"].isoformat()
    await db.homepage_sections.insert_one(section_dict)

    # Return the section without MongoDB _id
    created_section = await db.homepage_sections.find_one(
        {"id": section.id}, {"_id": 0}
    )
    return created_section


@router.put("/admin/homepage-sections/{section_id}")
async def update_homepage_section(
    section_id: str, section_data: dict, request: Request
):
    await require_admin(request)
    section_data.pop("id", None)
    section_data.pop("_id", None)

    await db.homepage_sections.update_one({"id": section_id}, {"$set": section_data})

    updated = await db.homepage_sections.find_one({"id": section_id}, {"_id": 0})
    return updated


@router.delete("/admin/homepage-sections/{section_id}")
async def delete_homepage_section(section_id: str, request: Request):
    await require_admin(request)
    await db.homepage_sections.delete_one({"id": section_id})
    return {"message": "Section deleted"}


@router.put("/admin/homepage-sections/reorder")
async def reorder_homepage_sections(order_data: dict, request: Request):
    await require_admin(request)
    sections = order_data.get("sections", [])

    for idx, section_id in enumerate(sections):
        await db.homepage_sections.update_one(
            {"id": section_id}, {"$set": {"order": idx + 1}}
        )

    return {"message": "Sections reordered"}


# ============= ABOUT PAGE MANAGEMENT =============


@router.get("/about-page")
async def get_about_page():
    """Get About page content (public)"""
    content = await db.about_page.find_one({"id": "about_page"}, {"_id": 0})
    if not content:
        # Return defaults
        default = AboutPageContent()
        return default.model_dump()
    return content


@router.get("/admin/about-page")
async def get_admin_about_page(request: Request):
    """Get About page content (admin)"""
    await require_admin(request)
    content = await db.about_page.find_one({"id": "about_page"}, {"_id": 0})
    if not content:
        default = AboutPageContent()
        return default.model_dump()
    return content


@router.put("/admin/about-page")
async def update_about_page(content_data: dict, request: Request):
    """Update About page content"""
    await require_admin(request)
    content_data.pop("_id", None)
    content_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.about_page.update_one(
        {"id": "about_page"}, {"$set": content_data}, upsert=True
    )

    updated = await db.about_page.find_one({"id": "about_page"}, {"_id": 0})
    return updated


# ============= SUBSCRIPTION ROUTES =============


@router.get("/subscription-settings")
async def get_subscription_settings():
    """Get subscription settings (public)"""
    settings = await db.subscription_settings.find_one(
        {"id": "subscription_settings"}, {"_id": 0}
    )
    if not settings:
        default = SubscriptionSettings()
        settings_dict = default.model_dump()
        await db.subscription_settings.insert_one(settings_dict)
        settings = await db.subscription_settings.find_one(
            {"id": "subscription_settings"}, {"_id": 0}
        )
    return settings


@router.put("/admin/subscription-settings")
async def update_subscription_settings(settings_data: dict, request: Request):
    """Update subscription settings (admin only)"""
    await require_admin(request)
    settings_data["id"] = "subscription_settings"
    await db.subscription_settings.update_one(
        {"id": "subscription_settings"}, {"$set": settings_data}, upsert=True
    )
    return {"message": "Subscription settings updated"}


@router.get("/subscription-plans")
async def get_subscription_plans():
    """Get all active subscription plans (public)"""
    plans = await db.subscription_plans.find({"is_active": True}, {"_id": 0}).to_list(
        50
    )
    return plans


@router.get("/admin/subscription-plans")
async def get_admin_subscription_plans(request: Request):
    """Get all subscription plans including inactive (admin only)"""
    await require_admin(request)
    plans = await db.subscription_plans.find({}, {"_id": 0}).to_list(50)
    return plans


@router.post("/admin/subscription-plans")
async def create_subscription_plan(plan_data: dict, request: Request):
    """Create a new subscription plan (admin only)"""
    await require_admin(request)
    plan = SubscriptionPlan(**plan_data)
    plan_dict = plan.model_dump()
    plan_dict["created_at"] = plan_dict["created_at"].isoformat()
    await db.subscription_plans.insert_one(plan_dict)
    return plan_dict


@router.put("/admin/subscription-plans/{plan_id}")
async def update_subscription_plan(plan_id: str, plan_data: dict, request: Request):
    """Update a subscription plan (admin only)"""
    await require_admin(request)
    plan_data.pop("id", None)
    plan_data.pop("_id", None)
    await db.subscription_plans.update_one({"id": plan_id}, {"$set": plan_data})
    updated = await db.subscription_plans.find_one({"id": plan_id}, {"_id": 0})
    return updated


@router.delete("/admin/subscription-plans/{plan_id}")
async def delete_subscription_plan(plan_id: str, request: Request):
    """Delete a subscription plan (admin only)"""
    await require_admin(request)
    await db.subscription_plans.delete_one({"id": plan_id})
    return {"message": "Plan deleted"}


@router.post("/subscriptions/subscribe")
async def create_subscription(sub_data: dict, request: Request):
    """Create a new customer subscription"""
    user = await require_auth(request)

    # Calculate next delivery date based on interval
    from datetime import timedelta

    interval_type = sub_data.get("interval_type", "months")
    interval_value = sub_data.get("interval_value", 1)

    now = datetime.now(timezone.utc)
    if interval_type == "days":
        next_delivery = now + timedelta(days=interval_value)
    elif interval_type == "weeks":
        next_delivery = now + timedelta(weeks=interval_value)
    else:  # months
        next_delivery = now + timedelta(days=interval_value * 30)

    subscription = CustomerSubscription(
        user_id=user["id"],
        user_email=user["email"],
        user_name=f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
        plan_id=sub_data.get("plan_id"),
        product_id=sub_data.get("product_id"),
        product_name=sub_data.get("product_name"),
        quantity=sub_data.get("quantity", 1),
        discount_percent=sub_data.get("discount_percent", 15),
        price=sub_data.get("price", 0),
        interval_type=interval_type,
        interval_value=interval_value,
        next_delivery_date=next_delivery.isoformat(),
        delivery_address=sub_data.get("delivery_address"),
        payment_method=sub_data.get("payment_method", "manual"),
    )

    sub_dict = subscription.model_dump()
    sub_dict["created_at"] = sub_dict["created_at"].isoformat()
    await db.customer_subscriptions.insert_one(sub_dict)

    return {"message": "Subscription created successfully!", "subscription": sub_dict}


@router.get("/subscriptions/my")
async def get_my_subscriptions(request: Request):
    """Get current user's subscriptions"""
    user = await require_auth(request)
    subscriptions = await db.customer_subscriptions.find(
        {"user_id": user["id"], "status": {"$in": ["active", "paused"]}}, {"_id": 0}
    ).to_list(50)
    return subscriptions


@router.put("/subscriptions/{sub_id}/pause")
async def pause_subscription(sub_id: str, request: Request):
    """Pause a subscription"""
    user = await require_auth(request)
    await db.customer_subscriptions.update_one(
        {"id": sub_id, "user_id": user["id"]}, {"$set": {"status": "paused"}}
    )
    return {"message": "Subscription paused"}


@router.put("/subscriptions/{sub_id}/resume")
async def resume_subscription(sub_id: str, request: Request):
    """Resume a paused subscription"""
    user = await require_auth(request)
    await db.customer_subscriptions.update_one(
        {"id": sub_id, "user_id": user["id"]}, {"$set": {"status": "active"}}
    )
    return {"message": "Subscription resumed"}


@router.put("/subscriptions/{sub_id}/cancel")
async def cancel_subscription(sub_id: str, request: Request):
    """Cancel a subscription"""
    user = await require_auth(request)
    await db.customer_subscriptions.update_one(
        {"id": sub_id, "user_id": user["id"]},
        {
            "$set": {
                "status": "cancelled",
                "cancelled_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    return {"message": "Subscription cancelled"}


@router.get("/admin/subscriptions")
async def get_all_subscriptions(request: Request, status: Optional[str] = None):
    """Get all customer subscriptions (admin only)"""
    await require_admin(request)
    query = {}
    if status:
        query["status"] = status
    subscriptions = (
        await db.customer_subscriptions.find(query, {"_id": 0})
        .sort("created_at", -1)
        .to_list(500)
    )
    return subscriptions


@router.put("/admin/subscriptions/{sub_id}")
async def admin_update_subscription(sub_id: str, sub_data: dict, request: Request):
    """Admin update any subscription"""
    await require_admin(request)
    sub_data.pop("id", None)
    sub_data.pop("_id", None)
    await db.customer_subscriptions.update_one({"id": sub_id}, {"$set": sub_data})
    return {"message": "Subscription updated"}


# ============= ROLE-BASED ACCESS CONTROL (RBAC) =============

# --- ROLES MANAGEMENT ---


@router.get("/admin/roles")
async def get_roles(request: Request):
    """Get all roles - requires team view permission or super admin"""
    user = await require_admin(request)
    if not user.get("is_super_admin") and not check_permission(user, "team", "view"):
        raise HTTPException(status_code=403, detail="Permission denied")

    roles = await db.roles.find({}, {"_id": 0}).to_list(100)
    return roles


@router.post("/admin/roles")
async def create_role(role_data: RoleCreate, request: Request):
    """Create a new role - super admin only"""
    user = await require_super_admin(request)

    # Check if role name already exists
    existing = await db.roles.find_one({"name": role_data.name})
    if existing:
        raise HTTPException(
            status_code=400, detail="Role with this name already exists"
        )

    role = Role(
        name=role_data.name,
        description=role_data.description,
        permissions=role_data.permissions,
        created_by=user["id"],
    )
    role_dict = role.model_dump()
    role_dict["created_at"] = role_dict["created_at"].isoformat()

    await db.roles.insert_one(role_dict)
    role_dict.pop("_id", None)

    logging.info(f"Role created: {role.name} by {user['email']}")
    return role_dict


@router.put("/admin/roles/{role_id}")
async def update_role(role_id: str, role_data: dict, request: Request):
    """Update a role - super admin only"""
    await require_super_admin(request)

    # Don't allow changing ID
    role_data.pop("id", None)
    role_data.pop("_id", None)
    role_data.pop("created_at", None)
    role_data.pop("created_by", None)

    # Check if role exists
    existing = await db.roles.find_one({"id": role_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Role not found")

    # Check name uniqueness if changing name
    if "name" in role_data and role_data["name"] != existing["name"]:
        name_exists = await db.roles.find_one(
            {"name": role_data["name"], "id": {"$ne": role_id}}
        )
        if name_exists:
            raise HTTPException(
                status_code=400, detail="Role with this name already exists"
            )

    await db.roles.update_one({"id": role_id}, {"$set": role_data})
    updated = await db.roles.find_one({"id": role_id}, {"_id": 0})

    logging.info(f"Role updated: {role_id}")
    return updated


@router.delete("/admin/roles/{role_id}")
async def delete_role(role_id: str, request: Request):
    """Delete a role - super admin only. Cannot delete if team members are assigned."""
    await require_super_admin(request)

    # Check if role exists
    existing = await db.roles.find_one({"id": role_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Role not found")

    # Check if any team members are using this role
    member_count = await db.team_members.count_documents({"role_id": role_id})
    if member_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete role. {member_count} team member(s) are using this role. Reassign them first.",
        )

    await db.roles.delete_one({"id": role_id})

    logging.info(f"Role deleted: {role_id}")
    return {"message": "Role deleted successfully"}


@router.get("/admin/permissions-list")
async def get_permissions_list(request: Request):
    """Get list of all available permissions - for UI"""
    await require_admin(request)

    return {
        "features": [
            {
                "id": "overview",
                "name": "Dashboard Overview",
                "description": "View main dashboard stats and news",
            },
            {
                "id": "products",
                "name": "Products",
                "description": "Manage product catalog",
            },
            {
                "id": "categories",
                "name": "Categories",
                "description": "Manage product categories",
            },
            {
                "id": "orders",
                "name": "Orders",
                "description": "View and manage customer orders",
            },
            {
                "id": "financials",
                "name": "Financials",
                "description": "View revenue, expenses and reports",
            },
            {
                "id": "payroll",
                "name": "Payroll",
                "description": "Manage employees and payroll",
            },
            {
                "id": "customers",
                "name": "Customers",
                "description": "View and manage customers",
            },
            {
                "id": "offers",
                "name": "Offers & Marketing",
                "description": "Create and send promotional offers",
            },
            {
                "id": "reviews",
                "name": "Reviews",
                "description": "Manage product reviews",
            },
            {
                "id": "sections",
                "name": "Homepage Sections",
                "description": "Edit homepage content",
            },
            {
                "id": "website",
                "name": "Website Settings",
                "description": "Site configuration",
            },
            {
                "id": "ads",
                "name": "Ads Generation",
                "description": "Create AI-powered advertisements",
            },
            {
                "id": "typography",
                "name": "Typography",
                "description": "Font and text settings",
            },
            {
                "id": "subscriptions",
                "name": "Subscriptions",
                "description": "Manage subscription plans",
            },
            {"id": "settings", "name": "Settings", "description": "Store settings"},
            {
                "id": "ai_chat",
                "name": "AI Chat",
                "description": "Customer chat management",
            },
            {
                "id": "team",
                "name": "Team Management",
                "description": "Manage roles and team members",
            },
        ],
        "actions": [
            {"id": "view", "name": "View", "description": "Can view/read data"},
            {"id": "create", "name": "Create", "description": "Can create new items"},
            {"id": "edit", "name": "Edit", "description": "Can modify existing items"},
            {"id": "delete", "name": "Delete", "description": "Can remove items"},
        ],
    }


# --- TEAM MEMBERS MANAGEMENT ---


@router.get("/admin/team")
async def get_team_members(request: Request):
    """Get all team members - requires team view permission or super admin"""
    user = await require_admin(request)
    if not user.get("is_super_admin") and not check_permission(user, "team", "view"):
        raise HTTPException(status_code=403, detail="Permission denied")

    members = await db.team_members.find(
        {}, {"_id": 0, "password_hash": 0, "invite_token": 0}
    ).to_list(100)

    # Add role names
    roles = await db.roles.find({}, {"_id": 0}).to_list(100)
    roles_dict = {r["id"]: r for r in roles}

    for member in members:
        role = roles_dict.get(member.get("role_id"))
        member["role_name"] = role.get("name", "Unknown") if role else "Unknown"

    return members


@router.post("/admin/team")
async def create_team_member(member_data: TeamMemberCreate, request: Request):
    """Create a team member directly with password - super admin only"""
    user = await require_super_admin(request)

    email = member_data.email.lower().strip()

    # Check if email already exists (in users or team_members)
    existing_user = await db.users.find_one({"email": email})
    existing_member = await db.team_members.find_one({"email": email})
    if existing_user or existing_member:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check if role exists
    role = await db.roles.find_one({"id": member_data.role_id})
    if not role:
        raise HTTPException(status_code=400, detail="Invalid role ID")

    # Create team member
    member = TeamMember(
        email=email,
        first_name=sanitize_input(member_data.first_name.strip()),
        last_name=sanitize_input(member_data.last_name.strip()),
        role_id=member_data.role_id,
        invited_by=user["id"],
        status="active" if member_data.password else "pending",
    )

    member_dict = member.model_dump()
    member_dict["created_at"] = member_dict["created_at"].isoformat()

    # Hash password if provided
    if member_data.password:
        member_dict["password_hash"] = hash_password(member_data.password)

    await db.team_members.insert_one(member_dict)

    # Remove sensitive data for response
    member_dict.pop("_id", None)
    member_dict.pop("password_hash", None)
    member_dict.pop("invite_token", None)
    member_dict["role_name"] = role["name"]

    logging.info(f"Team member created: {email} by {user['email']}")
    return member_dict


@router.post("/admin/team/invite")
async def invite_team_member(invite_data: TeamMemberInvite, request: Request):
    """Invite a team member via email - super admin only"""
    user = await require_super_admin(request)

    email = invite_data.email.lower().strip()

    # Check if email already exists
    existing_user = await db.users.find_one({"email": email})
    existing_member = await db.team_members.find_one({"email": email})
    if existing_user or existing_member:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check if role exists
    role = await db.roles.find_one({"id": invite_data.role_id})
    if not role:
        raise HTTPException(status_code=400, detail="Invalid role ID")

    # Generate invite token
    invite_token = str(uuid.uuid4())
    invite_expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    # Create team member with pending status
    member = TeamMember(
        email=email,
        first_name=sanitize_input(invite_data.first_name.strip()),
        last_name=sanitize_input(invite_data.last_name.strip()),
        role_id=invite_data.role_id,
        invited_by=user["id"],
        status="pending",
        invite_token=invite_token,
        invite_expires=invite_expires,
    )

    member_dict = member.model_dump()
    member_dict["created_at"] = member_dict["created_at"].isoformat()

    await db.team_members.insert_one(member_dict)

    # TODO: Send invitation email if send_email is True
    # For now, return the invite token in response (admin can share manually)

    logging.info(f"Team member invited: {email} by {user['email']}")

    return {
        "message": "Invitation created successfully",
        "member_id": member.id,
        "email": email,
        "invite_token": invite_token,
        "invite_expires": invite_expires,
        "invite_link": f"/team/accept-invite?token={invite_token}",
        "role_name": role["name"],
    }


@router.post("/admin/team/accept-invite")
async def accept_team_invite(token: str, password: str):
    """Accept team invitation and set password"""
    member = await db.team_members.find_one({"invite_token": token}, {"_id": 0})

    if not member:
        raise HTTPException(status_code=404, detail="Invalid or expired invitation")

    if member.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Invitation already used")

    # Check if invitation expired
    if member.get("invite_expires"):
        expires = datetime.fromisoformat(member["invite_expires"])
        if datetime.now(timezone.utc) > expires:
            raise HTTPException(
                status_code=400,
                detail="Invitation has expired. Please contact admin for a new invitation.",
            )

    # Validate password strength
    is_valid, message = validate_password_strength(password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    # Update member with password and activate
    await db.team_members.update_one(
        {"id": member["id"]},
        {
            "$set": {
                "password_hash": hash_password(password),
                "status": "active",
                "invite_token": None,
                "invite_expires": None,
            }
        },
    )

    logging.info(f"Team member activated: {member['email']}")
    return {"message": "Account activated successfully. You can now login."}


@router.put("/admin/team/{member_id}")
async def update_team_member(member_id: str, member_data: dict, request: Request):
    """Update a team member - super admin only"""
    await require_super_admin(request)

    # Don't allow changing certain fields
    member_data.pop("id", None)
    member_data.pop("_id", None)
    member_data.pop("created_at", None)
    member_data.pop("invited_by", None)
    member_data.pop("password_hash", None)
    member_data.pop("invite_token", None)

    # Check if member exists
    existing = await db.team_members.find_one({"id": member_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Team member not found")

    # If changing role, verify role exists
    if "role_id" in member_data:
        role = await db.roles.find_one({"id": member_data["role_id"]})
        if not role:
            raise HTTPException(status_code=400, detail="Invalid role ID")

    # If changing email, check uniqueness
    if "email" in member_data:
        email = member_data["email"].lower().strip()
        if email != existing["email"]:
            email_exists = await db.team_members.find_one(
                {"email": email, "id": {"$ne": member_id}}
            )
            user_exists = await db.users.find_one({"email": email})
            if email_exists or user_exists:
                raise HTTPException(status_code=400, detail="Email already registered")
            member_data["email"] = email

    await db.team_members.update_one({"id": member_id}, {"$set": member_data})
    updated = await db.team_members.find_one(
        {"id": member_id}, {"_id": 0, "password_hash": 0, "invite_token": 0}
    )

    # Add role name
    role = await db.roles.find_one({"id": updated.get("role_id")}, {"_id": 0})
    updated["role_name"] = role.get("name", "Unknown") if role else "Unknown"

    logging.info(f"Team member updated: {member_id}")
    return updated


@router.put("/admin/team/{member_id}/toggle")
async def toggle_team_member(member_id: str, request: Request):
    """Enable/disable a team member - super admin only"""
    await require_super_admin(request)

    member = await db.team_members.find_one({"id": member_id})
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    new_status = "disabled" if member.get("status") == "active" else "active"

    await db.team_members.update_one(
        {"id": member_id}, {"$set": {"status": new_status}}
    )

    logging.info(f"Team member {member_id} status changed to: {new_status}")
    return {
        "message": f"Team member {'disabled' if new_status == 'disabled' else 'enabled'}",
        "status": new_status,
    }


@router.put("/admin/team/{member_id}/reset-password")
async def reset_team_member_password(
    member_id: str, new_password: str, request: Request
):
    """Reset team member password - super admin only"""
    await require_super_admin(request)

    member = await db.team_members.find_one({"id": member_id})
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    # Validate password strength
    is_valid, message = validate_password_strength(new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    await db.team_members.update_one(
        {"id": member_id}, {"$set": {"password_hash": hash_password(new_password)}}
    )

    logging.info(f"Team member password reset: {member_id}")
    return {"message": "Password reset successfully"}


@router.delete("/admin/team/{member_id}")
async def delete_team_member(member_id: str, request: Request):
    """Delete a team member - super admin only"""
    await require_super_admin(request)

    member = await db.team_members.find_one({"id": member_id})
    if not member:
        raise HTTPException(status_code=404, detail="Team member not found")

    await db.team_members.delete_one({"id": member_id})

    logging.info(f"Team member deleted: {member_id} ({member['email']})")
    return {"message": "Team member deleted successfully"}


@router.get("/admin/my-permissions")
async def get_my_permissions(request: Request):
    """Get current user's permissions"""
    user = await require_admin(request)

    return {
        "is_super_admin": user.get("is_super_admin", False),
        "is_team_member": user.get("is_team_member", False),
        "role_name": user.get(
            "role_name", "Super Admin" if user.get("is_super_admin") else "Unknown"
        ),
        "permissions": user.get(
            "permissions",
            (
                SUPER_ADMIN_PERMISSIONS
                if user.get("is_super_admin")
                else DEFAULT_PERMISSIONS
            ),
        ),
    }


# ============= AD CAMPAIGN MANAGEMENT =============


@router.get("/admin/ad-platforms")
async def get_ad_platforms(request: Request):
    """Get list of supported ad platforms"""
    await require_admin(request)
    return AD_PLATFORMS


@router.get("/admin/ad-campaigns")
async def get_ad_campaigns(
    request: Request, status: Optional[str] = None, platform: Optional[str] = None
):
    """Get all ad campaigns with optional filtering"""
    await require_admin(request)

    query = {}
    if status:
        query["status"] = status
    if platform:
        query["platform"] = platform

    campaigns = (
        await db.ad_campaigns.find(query, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )
    return campaigns


@router.get("/admin/ad-campaigns/{campaign_id}")
async def get_ad_campaign(campaign_id: str, request: Request):
    """Get a single ad campaign"""
    await require_admin(request)

    campaign = await db.ad_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.post("/admin/ad-campaigns")
async def create_ad_campaign(campaign_data: AdCampaignCreate, request: Request):
    """Create a new ad campaign"""
    user = await require_admin(request)

    campaign = AdCampaign(
        **campaign_data.model_dump(), created_by=user.get("email", "admin")
    )

    campaign_dict = campaign.model_dump()
    campaign_dict["created_at"] = campaign_dict["created_at"].isoformat()

    await db.ad_campaigns.insert_one(campaign_dict)
    campaign_dict.pop("_id", None)

    logging.info(f"Ad campaign created: {campaign.name} on {campaign.platform}")
    return campaign_dict


@router.put("/admin/ad-campaigns/{campaign_id}")
async def update_ad_campaign(campaign_id: str, campaign_data: dict, request: Request):
    """Update an ad campaign"""
    await require_admin(request)

    # Don't allow changing certain fields
    campaign_data.pop("id", None)
    campaign_data.pop("_id", None)
    campaign_data.pop("created_at", None)
    campaign_data.pop("created_by", None)

    # Update last_updated timestamp
    campaign_data["last_updated"] = datetime.now(timezone.utc).isoformat()

    # Calculate metrics if relevant data changed
    if "impressions" in campaign_data or "clicks" in campaign_data:
        impressions = campaign_data.get("impressions", 0)
        clicks = campaign_data.get("clicks", 0)
        if impressions > 0:
            campaign_data["ctr"] = round((clicks / impressions) * 100, 2)

    if "spend" in campaign_data or "clicks" in campaign_data:
        spend = campaign_data.get("spend", 0)
        clicks = campaign_data.get("clicks", 0)
        if clicks > 0:
            campaign_data["cpc"] = round(spend / clicks, 2)

    if "spend" in campaign_data or "conversions" in campaign_data:
        spend = campaign_data.get("spend", 0)
        conversions = campaign_data.get("conversions", 0)
        if conversions > 0:
            campaign_data["cpa"] = round(spend / conversions, 2)

    if "spend" in campaign_data or "revenue" in campaign_data:
        spend = campaign_data.get("spend", 0)
        revenue = campaign_data.get("revenue", 0)
        if spend > 0:
            campaign_data["roas"] = round(revenue / spend, 2)

    result = await db.ad_campaigns.update_one(
        {"id": campaign_id}, {"$set": campaign_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")

    updated = await db.ad_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    return updated


@router.put("/admin/ad-campaigns/{campaign_id}/status")
async def update_campaign_status(campaign_id: str, status: str, request: Request):
    """Update campaign status"""
    await require_admin(request)

    valid_statuses = ["draft", "active", "paused", "completed", "cancelled"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    result = await db.ad_campaigns.update_one(
        {"id": campaign_id},
        {
            "$set": {
                "status": status,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return {"message": f"Campaign status updated to {status}"}


@router.delete("/admin/ad-campaigns/{campaign_id}")
async def delete_ad_campaign(campaign_id: str, request: Request):
    """Delete an ad campaign"""
    await require_admin(request)

    result = await db.ad_campaigns.delete_one({"id": campaign_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return {"message": "Campaign deleted successfully"}


@router.get("/admin/ad-campaigns/stats/summary")
async def get_campaign_stats_summary(request: Request):
    """Get summary statistics for all campaigns"""
    await require_admin(request)

    # Total campaigns by status
    pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    status_counts = await db.ad_campaigns.aggregate(pipeline).to_list(10)

    # Total spend and metrics
    totals_pipeline = [
        {
            "$group": {
                "_id": None,
                "total_spend": {"$sum": "$spend"},
                "total_impressions": {"$sum": "$impressions"},
                "total_clicks": {"$sum": "$clicks"},
                "total_conversions": {"$sum": "$conversions"},
                "total_revenue": {"$sum": "$revenue"},
            }
        }
    ]
    totals = await db.ad_campaigns.aggregate(totals_pipeline).to_list(1)

    # By platform
    platform_pipeline = [
        {
            "$group": {
                "_id": "$platform",
                "count": {"$sum": 1},
                "spend": {"$sum": "$spend"},
                "clicks": {"$sum": "$clicks"},
            }
        }
    ]
    by_platform = await db.ad_campaigns.aggregate(platform_pipeline).to_list(20)

    return {
        "by_status": {item["_id"]: item["count"] for item in status_counts},
        "totals": totals[0] if totals else {},
        "by_platform": by_platform,
    }


# ============= REVIEW GOOGLE BUSINESS MANAGEMENT =============


@router.put("/admin/reviews/{review_id}/google-status")
async def update_review_google_status(
    review_id: str, status: str, notes: Optional[str] = None, request: Request = None
):
    """Update review's Google Business status"""
    user = await require_admin(request)

    valid_statuses = ["not_selected", "approved", "request_sent", "posted"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    update_data = {"google_status": status, "google_notes": notes}

    # Set timestamps based on status
    current_time = datetime.now(timezone.utc).isoformat()
    if status == "approved":
        update_data["google_approved_at"] = current_time
        update_data["google_approved_by"] = user.get("email", "admin")
    elif status == "request_sent":
        update_data["google_request_sent_at"] = current_time
    elif status == "posted":
        update_data["google_posted_at"] = current_time

    result = await db.reviews.update_one({"id": review_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Review not found")

    logging.info(f"Review {review_id} Google status updated to {status}")
    return {"message": f"Review Google status updated to {status}"}


@router.get("/admin/reviews/google-stats")
async def get_google_review_stats(request: Request):
    """Get statistics for Google Business reviews"""
    await require_admin(request)

    pipeline = [{"$group": {"_id": "$google_status", "count": {"$sum": 1}}}]
    stats = await db.reviews.aggregate(pipeline).to_list(10)

    return {item["_id"] or "not_selected": item["count"] for item in stats}


@router.put("/admin/reviews/bulk-google-status")
async def bulk_update_google_status(
    review_ids: List[str], status: str, request: Request
):
    """Bulk update Google Business status for multiple reviews"""
    user = await require_admin(request)

    valid_statuses = ["not_selected", "approved", "request_sent", "posted"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    update_data = {"google_status": status}
    current_time = datetime.now(timezone.utc).isoformat()

    if status == "approved":
        update_data["google_approved_at"] = current_time
        update_data["google_approved_by"] = user.get("email", "admin")
    elif status == "request_sent":
        update_data["google_request_sent_at"] = current_time
    elif status == "posted":
        update_data["google_posted_at"] = current_time

    result = await db.reviews.update_many(
        {"id": {"$in": review_ids}}, {"$set": update_data}
    )

    return {"message": f"Updated {result.modified_count} reviews"}


# ============= AI FORMULATION ASSISTANT =============


class FormulationRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Optional[dict] = (
        None  # Additional context like target skin type, concerns, etc.
    )


class FormulationHistoryItem(BaseModel):
    id: str
    session_id: str
    created_at: str
    title: str
    messages: List[dict]


FORMULATION_SYSTEM_PROMPT = """You are an expert cosmetic chemist and skincare formulation specialist with deep knowledge in:
- Biomedical skincare ingredients and their mechanisms
- INCI nomenclature and cosmetic raw materials
- Active ingredients: peptides, growth factors, PDRN, retinoids, AHAs, BHAs, vitamin C derivatives
- Emulsion technology, delivery systems, and formulation stability
- Regulatory compliance (FDA, Health Canada, EU Cosmetics Regulation)
- pH optimization and ingredient compatibility

Your role is to help formulate advanced skincare products. When asked about formulations:

1. **Provide detailed formulas** with:
   - INCI names and trade names
   - Exact percentages for each phase (water phase, oil phase, cool-down phase)
   - pH range and adjustments needed
   - Manufacturing instructions

2. **Consider safety and efficacy**:
   - Maximum safe concentrations
   - Potential irritation concerns
   - Ingredient interactions to avoid
   - Stability considerations

3. **Include technical details**:
   - HLB values for emulsifiers
   - Penetration enhancers when appropriate
   - Preservative systems
   - Antioxidants for stability

4. **Format formulas clearly** using tables or structured lists

5. **Provide alternatives** when ingredients might be hard to source

Always be scientifically accurate and cite relevant research when applicable. If asked about something outside cosmetic chemistry, politely redirect to formulation topics.

ReRoots brand focuses on biotech skincare with PDRN, peptides, and regenerative ingredients."""


@router.post("/admin/formulation-assistant")
async def formulation_assistant_chat(req: FormulationRequest, request: Request):
    """AI-powered skincare formulation assistant for creating biomedical skincare formulas"""
    await require_admin(request)

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        llm_key = get_claude_api_key()
        if not llm_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        # Generate or use provided session ID
        session_id = req.session_id or f"formulation-{str(uuid.uuid4())}"

        # Get conversation history from database
        history = await db.formulation_sessions.find_one(
            {"session_id": session_id}, {"_id": 0}
        )

        messages_history = []
        if history and history.get("messages"):
            messages_history = history["messages"]

        # Build conversation context
        context_text = ""
        if req.context:
            context_parts = []
            if req.context.get("skin_type"):
                context_parts.append(f"Target skin type: {req.context['skin_type']}")
            if req.context.get("concerns"):
                context_parts.append(
                    f"Skin concerns: {', '.join(req.context['concerns'])}"
                )
            if req.context.get("product_type"):
                context_parts.append(f"Product type: {req.context['product_type']}")
            if context_parts:
                context_text = "\n\nContext: " + "; ".join(context_parts)

        # Build history text for context
        history_text = ""
        for msg in messages_history[-10:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"{role}: {msg['content']}\n\n"

        # Create enhanced system message with history
        enhanced_system = FORMULATION_SYSTEM_PROMPT
        if history_text:
            enhanced_system += f"\n\nConversation history:\n{history_text}"

        # Initialize chat
        chat = LlmChat(
            api_key=llm_key, session_id=session_id, system_message=enhanced_system
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")

        # Send message
        user_msg = UserMessage(text=req.message + context_text)
        response = await chat.send_message(user_msg)

        # Generate title from first message
        title = req.message[:50] + "..." if len(req.message) > 50 else req.message
        if not history:
            title = req.message[:100]

        # Update session in database
        new_messages = messages_history + [
            {
                "role": "user",
                "content": req.message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ]

        await db.formulation_sessions.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "session_id": session_id,
                    "title": title if not history else history.get("title", title),
                    "messages": new_messages,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "context": req.context,
                },
                "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()},
            },
            upsert=True,
        )

        return {
            "response": response,
            "session_id": session_id,
            "message_count": len(new_messages),
        }

    except Exception as e:
        logging.error(f"Formulation assistant error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI assistant error: {str(e)}")


@router.get("/admin/formulation-assistant/sessions")
async def get_formulation_sessions(request: Request):
    """Get all formulation assistant sessions"""
    await require_admin(request)

    sessions = (
        await db.formulation_sessions.find(
            {},
            {
                "_id": 0,
                "session_id": 1,
                "title": 1,
                "created_at": 1,
                "updated_at": 1,
                "context": 1,
            },
        )
        .sort("updated_at", -1)
        .to_list(50)
    )

    return {"sessions": sessions}


@router.get("/admin/formulation-assistant/sessions/{session_id}")
async def get_formulation_session(session_id: str, request: Request):
    """Get a specific formulation session with all messages"""
    await require_admin(request)

    session = await db.formulation_sessions.find_one(
        {"session_id": session_id}, {"_id": 0}
    )

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@router.delete("/admin/formulation-assistant/sessions/{session_id}")
async def delete_formulation_session(session_id: str, request: Request):
    """Delete a formulation session"""
    await require_admin(request)

    result = await db.formulation_sessions.delete_one({"session_id": session_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"message": "Session deleted successfully"}


# ============= FILE UPLOAD =============

# Create uploads directory
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# ImgBB API Key for permanent image hosting (optional)
IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")


@router.post("/upload/file")
async def upload_general_file(file: UploadFile = File(...), request: Request = None):
    """Upload any file to Catbox.moe for permanent hosting - supports all file types"""
    import httpx

    # Read file content
    file_content = await file.read()

    # Check file size (max 200MB for Catbox)
    if len(file_content) > 200 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File must be less than 200MB")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Catbox.moe accepts multipart form uploads for any file type
            files = {
                "fileToUpload": (
                    file.filename,
                    file_content,
                    file.content_type or "application/octet-stream",
                )
            }
            data = {"reqtype": "fileupload"}

            response = await client.post(
                "https://catbox.moe/user/api.php", files=files, data=data
            )

            if response.status_code == 200 and response.text.startswith("https://"):
                file_url = response.text.strip()
                logging.info(f"File uploaded to Catbox permanently: {file_url}")
                return {
                    "url": file_url,
                    "filename": file.filename,
                    "type": file.content_type,
                    "size": len(file_content),
                    "permanent": True,
                    "host": "catbox",
                }
            else:
                logging.error(
                    f"Catbox upload response: {response.status_code} - {response.text}"
                )
                raise HTTPException(status_code=500, detail="File upload failed")
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Upload timed out. Please try again with a smaller file.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"File upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload/image")
async def upload_image(file: UploadFile = File(...), request: Request = None):
    """Upload an image file - automatically uses free permanent hosting (no API key required)"""
    import httpx
    
    logging.info(f"Upload request received: filename={file.filename}, content_type={file.content_type}, size={file.size if hasattr(file, 'size') else 'unknown'}")

    # Validate file type - also accept HEIC from iPhones (will be converted)
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp", "image/heic", "image/heif"]
    # Also accept application/octet-stream for some mobile browsers
    if file.content_type not in allowed_types and file.content_type != "application/octet-stream":
        logging.warning(f"Invalid file type rejected: {file.content_type}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Only JPEG, PNG, GIF, and WebP are allowed.",
        )

    # Read file content
    file_content = await file.read()

    # Method 1: Try Catbox.moe (free, no API key needed)
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Catbox.moe accepts multipart form uploads
            files = {"fileToUpload": (file.filename, file_content, file.content_type)}
            data = {"reqtype": "fileupload"}

            response = await client.post(
                "https://catbox.moe/user/api.php", files=files, data=data
            )

            if response.status_code == 200 and response.text.startswith("https://"):
                image_url = response.text.strip()
                logging.info(f"Image uploaded to Catbox permanently: {image_url}")
                return {
                    "url": image_url,
                    "filename": file.filename,
                    "permanent": True,
                    "host": "catbox",
                }
            else:
                logging.warning(
                    f"Catbox upload response: {response.status_code} - {response.text}"
                )
    except Exception as e:
        logging.warning(f"Catbox upload failed: {e}")

    # Method 2: Try ImgBB if API key is configured
    if IMGBB_API_KEY:
        try:
            base64_image = base64.b64encode(file_content).decode("utf-8")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.imgbb.com/1/upload",
                    data={
                        "key": IMGBB_API_KEY,
                        "image": base64_image,
                        "name": (
                            file.filename.rsplit(".", 1)[0]
                            if "." in file.filename
                            else file.filename
                        ),
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        image_url = result["data"]["url"]
                        logging.info(
                            f"Image uploaded to ImgBB permanently: {image_url}"
                        )
                        return {
                            "url": image_url,
                            "filename": file.filename,
                            "permanent": True,
                            "host": "imgbb",
                        }
        except Exception as e:
            logging.warning(f"ImgBB upload failed: {e}")

    # Method 3: Try 0x0.st as another free option
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"file": (file.filename, file_content, file.content_type)}

            response = await client.post("https://0x0.st", files=files)

            if response.status_code == 200 and response.text.startswith("https://"):
                image_url = response.text.strip()
                logging.info(f"Image uploaded to 0x0.st: {image_url}")
                return {
                    "url": image_url,
                    "filename": file.filename,
                    "permanent": True,
                    "host": "0x0.st",
                }
    except Exception as e:
        logging.warning(f"0x0.st upload failed: {e}")

    # Fallback to local storage if all external services failed
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    unique_filename = f"{uuid.uuid4()}.{file_ext}"
    file_path = UPLOAD_DIR / unique_filename

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    logging.info(f"Image saved locally (temporary): {unique_filename}")
    return {
        "url": f"/api/uploads/{unique_filename}",
        "filename": unique_filename,
        "permanent": False,
        "host": "local",
        "warning": "Image saved locally - may be lost after deployment.",
    }


@router.post("/upload/video")
async def upload_video(file: UploadFile = File(...), request: Request = None):
    """Upload a video file - uses Catbox.moe for permanent hosting"""
    import httpx

    # Validate file type
    allowed_types = [
        "video/mp4",
        "video/webm",
        "video/quicktime",
        "video/x-msvideo",
        "video/mpeg",
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only MP4, WebM, MOV, AVI, and MPEG are allowed.",
        )

    # Read file content
    file_content = await file.read()

    # Check file size (max 200MB for Catbox)
    if len(file_content) > 200 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Video must be less than 200MB")

    # Try Catbox.moe (free, up to 200MB)
    try:
        async with httpx.AsyncClient(
            timeout=300.0
        ) as client:  # 5 minute timeout for large files
            files = {"fileToUpload": (file.filename, file_content, file.content_type)}
            data = {"reqtype": "fileupload"}

            response = await client.post(
                "https://catbox.moe/user/api.php", files=files, data=data
            )

            if response.status_code == 200 and response.text.startswith("https://"):
                video_url = response.text.strip()
                logging.info(f"Video uploaded to Catbox permanently: {video_url}")
                return {
                    "url": video_url,
                    "filename": file.filename,
                    "permanent": True,
                    "host": "catbox",
                }
            else:
                logging.warning(
                    f"Catbox video upload response: {response.status_code} - {response.text}"
                )
    except Exception as e:
        logging.warning(f"Catbox video upload failed: {e}")

    # Fallback: Save locally
    import os
    import uuid

    uploads_dir = Path("/app/backend/uploads")
    uploads_dir.mkdir(exist_ok=True)

    file_ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "mp4"
    unique_filename = f"{uuid.uuid4()}.{file_ext}"
    file_path = uploads_dir / unique_filename

    with open(file_path, "wb") as f:
        f.write(file_content)

    logging.info(f"Video saved locally: {unique_filename}")
    return {
        "url": f"/api/uploads/{unique_filename}",
        "filename": unique_filename,
        "permanent": False,
        "host": "local",
        "warning": "Video saved locally - may be lost after deployment.",
    }


@router.post("/upload/permanent")
async def upload_permanent_image(file: UploadFile = File(...)):
    """Upload image to ImgBB for permanent hosting - returns URL that never expires"""
    import httpx

    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only JPEG, PNG, GIF, and WebP are allowed.",
        )

    # Check if ImgBB API key is configured
    if not IMGBB_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ImgBB API key not configured. Please add IMGBB_API_KEY to enable permanent image hosting.",
        )

    try:
        # Read file content
        file_content = await file.read()

        # Convert to base64
        base64_image = base64.b64encode(file_content).decode("utf-8")

        # Upload to ImgBB
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.imgbb.com/1/upload",
                data={
                    "key": IMGBB_API_KEY,
                    "image": base64_image,
                    "name": (
                        file.filename.rsplit(".", 1)[0]
                        if "." in file.filename
                        else file.filename
                    ),
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                logging.error(f"ImgBB upload failed: {response.text}")
                raise HTTPException(status_code=500, detail="Failed to upload to ImgBB")

            result = response.json()

            if not result.get("success"):
                raise HTTPException(
                    status_code=500,
                    detail=result.get("error", {}).get("message", "Upload failed"),
                )

            # Return the permanent URL
            image_url = result["data"]["url"]
            display_url = result["data"]["display_url"]
            delete_url = result["data"]["delete_url"]

            logging.info(f"Image uploaded to ImgBB: {image_url}")

            return {
                "url": image_url,
                "display_url": display_url,
                "delete_url": delete_url,
                "permanent": True,
                "message": "Image uploaded permanently to ImgBB",
            }

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504, detail="Upload timed out. Please try again."
        )
    except Exception as e:
        logging.error(f"ImgBB upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/upload/imgbb-status")
async def get_imgbb_status():
    """Check if ImgBB permanent hosting is configured"""
    return {
        "configured": bool(IMGBB_API_KEY),
        "service": "ImgBB",
        "message": (
            "Permanent image hosting is active"
            if IMGBB_API_KEY
            else "ImgBB API key not configured"
        ),
    }


@router.get("/uploads/{filename}")
async def get_uploaded_file(filename: str):
    """Serve uploaded files"""
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


# ============= CLOUDINARY CDN INTEGRATION =============


class CloudinarySignatureResponse(BaseModel):
    signature: str
    timestamp: int
    cloud_name: str
    api_key: str
    folder: str
    resource_type: str


class CloudinaryUploadResponse(BaseModel):
    public_id: str
    secure_url: str
    url: str
    format: str
    width: Optional[int] = None
    height: Optional[int] = None
    bytes: Optional[int] = None


@router.get("/cloudinary/signature")
async def get_cloudinary_signature(
    resource_type: str = "image", folder: str = "reroots/products"
):
    """Generate signed upload parameters for Cloudinary"""
    if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
        raise HTTPException(status_code=500, detail="Cloudinary not configured")

    # Validate allowed folders
    ALLOWED_FOLDERS = (
        "reroots/products",
        "reroots/categories",
        "reroots/users",
        "reroots/content",
        "reroots/brands",
    )
    if not any(folder.startswith(f) for f in ALLOWED_FOLDERS):
        raise HTTPException(status_code=400, detail="Invalid folder path")

    # Validate resource type
    if resource_type not in ("image", "video", "raw"):
        raise HTTPException(status_code=400, detail="Invalid resource type")

    timestamp = int(time.time())
    params = {
        "timestamp": timestamp,
        "folder": folder,
    }

    signature = cloudinary.utils.api_sign_request(params, CLOUDINARY_API_SECRET)

    return CloudinarySignatureResponse(
        signature=signature,
        timestamp=timestamp,
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        folder=folder,
        resource_type=resource_type,
    )


@router.post("/cloudinary/upload")
async def upload_to_cloudinary(
    file: UploadFile = File(...), folder: str = "reroots/products"
):
    """Direct backend upload to Cloudinary (for admin use)"""
    if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY or not CLOUDINARY_API_SECRET:
        raise HTTPException(status_code=500, detail="Cloudinary not configured")

    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/gif", "image/avif"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400, detail=f"File type {file.content_type} not allowed"
        )

    # Read file content
    contents = await file.read()

    try:
        # Upload to Cloudinary with automatic optimization
        result = cloudinary.uploader.upload(
            contents,
            folder=folder,
            resource_type="image",
            transformation=[{"quality": "auto", "fetch_format": "auto"}],
            eager=[
                {
                    "width": 400,
                    "height": 400,
                    "crop": "fill",
                    "quality": "auto",
                    "fetch_format": "auto",
                },
                {
                    "width": 800,
                    "height": 800,
                    "crop": "fill",
                    "quality": "auto",
                    "fetch_format": "auto",
                },
            ],
            eager_async=True,
        )

        return CloudinaryUploadResponse(
            public_id=result["public_id"],
            secure_url=result["secure_url"],
            url=result["url"],
            format=result.get("format", ""),
            width=result.get("width"),
            height=result.get("height"),
            bytes=result.get("bytes"),
        )
    except Exception as e:
        logging.error(f"Cloudinary upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.delete("/cloudinary/{public_id:path}")
async def delete_from_cloudinary(public_id: str, request: Request):
    """Delete image from Cloudinary (admin only)"""
    await require_admin(request)

    if not CLOUDINARY_CLOUD_NAME:
        raise HTTPException(status_code=500, detail="Cloudinary not configured")

    try:
        result = cloudinary.uploader.destroy(public_id, invalidate=True)
        return {"result": result.get("result"), "public_id": public_id}
    except Exception as e:
        logging.error(f"Cloudinary delete error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@router.get("/cloudinary/transform")
async def get_cloudinary_url(
    url: str,
    width: int = 800,
    height: Optional[int] = None,
    crop: str = "fill",
    quality: str = "auto",
    format: str = "auto",
):
    """Generate optimized Cloudinary URL from any image URL (fetch mode)"""
    if not CLOUDINARY_CLOUD_NAME:
        raise HTTPException(status_code=500, detail="Cloudinary not configured")

    # Build transformation string
    transformations = [f"w_{width}", f"q_{quality}", f"f_{format}"]
    if height:
        transformations.append(f"h_{height}")
    if crop:
        transformations.append(f"c_{crop}")

    transform_str = ",".join(transformations)

    # Use Cloudinary fetch to optimize external URLs
    # Format: https://res.cloudinary.com/{cloud}/image/fetch/{transforms}/{url}
    import urllib.parse

    encoded_url = urllib.parse.quote(url, safe="")

    optimized_url = f"https://res.cloudinary.com/{CLOUDINARY_CLOUD_NAME}/image/fetch/{transform_str}/{encoded_url}"

    return {
        "original_url": url,
        "optimized_url": optimized_url,
        "transformations": transform_str,
    }


# ============= IMAGE CLEANUP =============


@router.post("/admin/cleanup-images")
async def admin_cleanup_images(request: Request):
    """Admin endpoint to manually clean up broken image URLs"""
    await require_admin(request)
    await cleanup_broken_images()
    return {"message": "Image cleanup completed", "status": "success"}


# ============= SEED DATA =============


@router.post("/seed")
async def seed_database():
    if db is None:
        return {"message": "Database not connected, skipping seed"}
    # Check if already seeded
    existing_products = await db.products.count_documents({})
    if existing_products > 0:
        return {"message": "Database already seeded"}

    # Create categories
    categories = [
        Category(
            id="cat-serums",
            name="Serums",
            slug="serums",
            description="Advanced treatment serums",
            image_url="https://images.unsplash.com/photo-1677735476292-0fc57ab097b2?w=400",
        ),
        Category(
            id="cat-cleansers",
            name="Cleansers",
            slug="cleansers",
            description="Gentle cleansing formulas",
            image_url="https://images.unsplash.com/photo-1556228720-195a672e8a03?w=400",
        ),
        Category(
            id="cat-moisturizers",
            name="Moisturizers",
            slug="moisturizers",
            description="Hydrating moisturizers",
            image_url="https://images.unsplash.com/photo-1570194065650-d99fb4b38b17?w=400",
        ),
        Category(
            id="cat-masks",
            name="Masks",
            slug="masks",
            description="Treatment masks",
            image_url="https://images.unsplash.com/photo-1596755389378-c31d21fd1273?w=400",
        ),
    ]

    for cat in categories:
        await db.categories.insert_one(cat.model_dump())

    # Create products
    products = [
        Product(
            id="prod-aura-gen",
            name="AURA-GEN TXA + PDRN Bio-Regenerator",
            slug="aura-gen-txa-pdrn",
            description="Our flagship biotech serum featuring 2.0% PDRN and 5.0% Tranexamic Acid. This advanced formula combines salmon DNA extract with powerful brightening agents to deliver visible results in skin vitality and tone correction.",
            short_description="2.0% PDRN + 5.0% Tranexamic Acid Bio-Revitalizing Serum",
            price=95.00,
            compare_price=125.00,
            category_id="cat-serums",
            images=[
                "https://images.unsplash.com/photo-1677735476292-0fc57ab097b2?w=800",
                "https://images.unsplash.com/photo-1760860992928-221d73c4c0cc?w=800",
                "https://images.unsplash.com/photo-1640621774431-3b28204a5510?w=800",
            ],
            ingredients="Aqua (Water/Eau), Tranexamic Acid (5.0%), Niacinamide, Glycerin, Sodium DNA (PDRN 2.0%), Propanediol, Sodium Hyaluronate, Panax Ginseng Berry Extract, 1,2-Hexanediol, Ethylhexylglycerin, Phenoxyethanol, Synthetic Fluorphlogopite, Titanium Dioxide, Tin Oxide",
            how_to_use="Apply 2-3 drops to cleansed skin morning and evening. Gently pat into skin until absorbed. Follow with moisturizer and SPF during the day.",
            stock=50,
            is_featured=True,
            average_rating=4.8,
            review_count=24,
        ),
        Product(
            id="prod-copper-peptide",
            name="Copper Peptide Revitalizing Complex",
            slug="copper-peptide-revitalizing",
            description="Advanced anti-aging serum featuring GHK-Cu copper peptides to support collagen production and skin vitality. Targets fine lines, wrinkles, and overall skin firmness.",
            short_description="GHK-Cu Copper Peptide Anti-Aging Serum",
            price=85.00,
            compare_price=110.00,
            category_id="cat-serums",
            images=[
                "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=800"
            ],
            ingredients="Aqua, Copper Tripeptide-1, Hyaluronic Acid, Glycerin, Niacinamide, Arginine, Panthenol, Allantoin",
            how_to_use="Apply to clean skin in the evening. Can be used with PDRN serum for enhanced results.",
            stock=40,
            is_featured=True,
            average_rating=4.6,
            review_count=18,
        ),
        Product(
            id="prod-gentle-cleanser",
            name="Biotech Gentle Cleanser",
            slug="biotech-gentle-cleanser",
            description="A pH-balanced cleansing gel that removes impurities while maintaining skin's natural moisture barrier. Infused with soothing botanical extracts.",
            short_description="pH-Balanced Cleansing Gel",
            price=38.00,
            category_id="cat-cleansers",
            images=["https://images.unsplash.com/photo-1556228720-195a672e8a03?w=800"],
            ingredients="Aqua, Cocamidopropyl Betaine, Glycerin, Sodium Cocoyl Glutamate, Aloe Barbadensis Leaf Juice, Chamomilla Recutita Extract",
            how_to_use="Massage onto damp skin, rinse thoroughly. Use morning and evening.",
            stock=75,
            is_featured=False,
            average_rating=4.5,
            review_count=32,
        ),
        Product(
            id="prod-hydra-barrier",
            name="Hydra-Barrier Moisturizer",
            slug="hydra-barrier-moisturizer",
            description="Rich yet fast-absorbing moisturizer that strengthens the skin barrier while providing deep hydration. Features ceramides and hyaluronic acid.",
            short_description="Ceramide-Rich Barrier Support Cream",
            price=68.00,
            category_id="cat-moisturizers",
            images=[
                "https://images.unsplash.com/photo-1570194065650-d99fb4b38b17?w=800"
            ],
            ingredients="Aqua, Ceramide NP, Ceramide AP, Ceramide EOP, Hyaluronic Acid, Squalane, Shea Butter, Niacinamide",
            how_to_use="Apply generously to face and neck after serums. Use morning and evening.",
            stock=60,
            is_featured=True,
            average_rating=4.7,
            review_count=45,
        ),
        Product(
            id="prod-renewal-mask",
            name="Cell Renewal Treatment Mask",
            slug="cell-renewal-mask",
            description="Weekly treatment mask that accelerates cell turnover and reveals brighter, smoother skin. Contains AHA/BHA complex with soothing botanicals.",
            short_description="AHA/BHA Exfoliating Treatment Mask",
            price=52.00,
            category_id="cat-masks",
            images=[
                "https://images.unsplash.com/photo-1596755389378-c31d21fd1273?w=800"
            ],
            ingredients="Aqua, Glycolic Acid, Salicylic Acid, Lactic Acid, Centella Asiatica Extract, Aloe Vera, Vitamin E",
            how_to_use="Apply thin layer to clean skin, leave for 10-15 minutes, rinse thoroughly. Use 1-2 times per week.",
            stock=45,
            is_featured=False,
            average_rating=4.4,
            review_count=15,
        ),
    ]

    for prod in products:
        prod_dict = prod.model_dump()
        prod_dict["created_at"] = prod_dict["created_at"].isoformat()
        await db.products.insert_one(prod_dict)

    # Create admin user - NOTE: This user should use Google SSO login
    # The password is set to a random secure value (cannot be guessed)
    # Admin must use Google OAuth to log in for security
    import secrets
    admin_user = User(
        id="admin-user",
        email="admin@reroots.ca",
        first_name="Admin",
        last_name="User",
        is_admin=True,
    )
    admin_dict = admin_user.model_dump()
    admin_dict["password"] = hash_password(secrets.token_urlsafe(32))  # Secure random password
    admin_dict["auth_provider"] = "google"  # Indicate Google SSO is required
    admin_dict["created_at"] = admin_dict["created_at"].isoformat()
    await db.users.insert_one(admin_dict)

    return {"message": "Database seeded successfully"}


# ============ MULTI-CURRENCY ENDPOINTS ============

import aiohttp


async def fetch_exchange_rates():
    """Fetch exchange rates from free API (base: CAD)"""
    global exchange_rate_cache

    # Check if cache is fresh (less than 1 hour old)
    if exchange_rate_cache["last_updated"]:
        last_updated = datetime.fromisoformat(exchange_rate_cache["last_updated"])
        if datetime.now(timezone.utc) - last_updated < timedelta(hours=1):
            return exchange_rate_cache["rates"]

    try:
        # Using exchangerate-api.com free tier (1500 requests/month)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.exchangerate-api.com/v4/latest/CAD",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get("rates", {})

                    # Filter to supported currencies only
                    filtered_rates = {
                        currency: rates.get(currency, 1.0)
                        for currency in SUPPORTED_CURRENCIES.keys()
                    }
                    filtered_rates["CAD"] = 1.0  # Base currency

                    # Update cache
                    exchange_rate_cache["rates"] = filtered_rates
                    exchange_rate_cache["last_updated"] = datetime.now(
                        timezone.utc
                    ).isoformat()

                    # Store in database for persistence
                    await db.settings.update_one(
                        {"type": "exchange_rates"},
                        {
                            "$set": {
                                "rates": filtered_rates,
                                "last_updated": exchange_rate_cache["last_updated"],
                            }
                        },
                        upsert=True,
                    )

                    return filtered_rates
    except Exception as e:
        logging.error(f"Failed to fetch exchange rates: {e}")

    # Fallback to cached/stored rates
    stored = await db.settings.find_one({"type": "exchange_rates"}, {"_id": 0})
    if stored:
        exchange_rate_cache["rates"] = stored.get("rates", {})
        exchange_rate_cache["last_updated"] = stored.get("last_updated")
        return exchange_rate_cache["rates"]

    # Ultimate fallback - approximate rates
    return {"CAD": 1.0, "USD": 0.74, "GBP": 0.58, "EUR": 0.68, "AUD": 1.12, "INR": 61.5}


@router.get("/currency/rates")
async def get_currency_rates():
    """Get current exchange rates (base: CAD)"""
    rates = await fetch_exchange_rates()
    return {
        "base": "CAD",
        "rates": rates,
        "currencies": SUPPORTED_CURRENCIES,
        "last_updated": exchange_rate_cache.get("last_updated"),
    }


@router.get("/currency/convert")
async def convert_currency(
    amount: float, from_currency: str = "CAD", to_currency: str = "USD"
):
    """Convert amount between currencies"""
    rates = await fetch_exchange_rates()

    if from_currency not in rates or to_currency not in rates:
        raise HTTPException(status_code=400, detail="Unsupported currency")

    # Convert to CAD first, then to target currency
    cad_amount = amount / rates[from_currency]
    converted = cad_amount * rates[to_currency]

    return {
        "original": {"amount": amount, "currency": from_currency},
        "converted": {"amount": round(converted, 2), "currency": to_currency},
        "rate": round(rates[to_currency] / rates[from_currency], 6),
    }


@router.get("/currency/detect")
async def detect_currency(request: Request):
    """Detect currency based on client IP"""
    # Get client IP
    client_ip = request.client.host if request.client else None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    detected_country = "CA"  # Default to Canada
    detected_currency = "CAD"

    try:
        # Use free IP geolocation API
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ip-api.com/json/{client_ip}?fields=countryCode",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    detected_country = data.get("countryCode", "CA")
                    detected_currency = COUNTRY_TO_CURRENCY.get(detected_country, "CAD")
    except Exception as e:
        logging.warning(f"IP detection failed: {e}")

    return {
        "country": detected_country,
        "currency": detected_currency,
        "details": SUPPORTED_CURRENCIES.get(
            detected_currency, SUPPORTED_CURRENCIES["CAD"]
        ),
    }


# ============ WISHLIST ENDPOINTS ============


@router.get("/wishlist")
async def get_wishlist(current_user: dict = Depends(get_current_user)):
    """Get user's wishlist"""
    wishlist_items = await db.wishlist.find(
        {"user_id": current_user["id"]}, {"_id": 0}
    ).to_list(100)

    # Fetch product details for each item
    product_ids = [item["product_id"] for item in wishlist_items]
    products = await db.products.find({"id": {"$in": product_ids}}, {"_id": 0}).to_list(
        100
    )

    products_map = {p["id"]: p for p in products}

    result = []
    for item in wishlist_items:
        product = products_map.get(item["product_id"])
        if product:
            result.append({**item, "product": product})

    return {"items": result, "count": len(result)}


@router.post("/wishlist/{product_id}")
async def add_to_wishlist(
    product_id: str, current_user: dict = Depends(get_current_user)
):
    """Add product to wishlist"""
    # Check if product exists
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check if already in wishlist
    existing = await db.wishlist.find_one(
        {"user_id": current_user["id"], "product_id": product_id}
    )
    if existing:
        return {"message": "Product already in wishlist", "in_wishlist": True}

    # Add to wishlist
    wishlist_item = {
        "id": str(uuid.uuid4()),
        "user_id": current_user["id"],
        "product_id": product_id,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.wishlist.insert_one(wishlist_item)

    return {"message": "Added to wishlist", "in_wishlist": True, "item": wishlist_item}


@router.delete("/wishlist/{product_id}")
async def remove_from_wishlist(
    product_id: str, current_user: dict = Depends(get_current_user)
):
    """Remove product from wishlist"""
    result = await db.wishlist.delete_one(
        {"user_id": current_user["id"], "product_id": product_id}
    )

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not in wishlist")

    return {"message": "Removed from wishlist", "in_wishlist": False}


@router.get("/wishlist/check/{product_id}")
async def check_wishlist(
    product_id: str, current_user: dict = Depends(get_current_user)
):
    """Check if product is in wishlist"""
    existing = await db.wishlist.find_one(
        {"user_id": current_user["id"], "product_id": product_id}
    )
    return {"in_wishlist": existing is not None}


# ============ BACK-IN-STOCK ALERTS ============


@router.post("/alerts/back-in-stock")
async def create_back_in_stock_alert(product_id: str, email: str):
    """Create back-in-stock alert"""
    # Check if product exists
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check if alert already exists
    existing = await db.stock_alerts.find_one(
        {"product_id": product_id, "email": email, "notified": False}
    )
    if existing:
        return {"message": "Alert already exists", "alert_id": existing["id"]}

    alert = {
        "id": str(uuid.uuid4()),
        "product_id": product_id,
        "email": email,
        "notified": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.stock_alerts.insert_one(alert)

    return {"message": "Alert created", "alert_id": alert["id"]}


@router.get("/admin/alerts/back-in-stock")
async def get_stock_alerts(current_user: dict = Depends(require_admin)):
    """Get all back-in-stock alerts"""
    alerts = await db.stock_alerts.find({}, {"_id": 0}).to_list(500)

    # Group by product
    by_product = {}
    for alert in alerts:
        pid = alert["product_id"]
        if pid not in by_product:
            by_product[pid] = {"product_id": pid, "alerts": [], "count": 0}
        by_product[pid]["alerts"].append(alert)
        by_product[pid]["count"] += 1

    return {"alerts": list(by_product.values()), "total": len(alerts)}


# ============ RECENTLY VIEWED (Session-based) ============


@router.post("/recently-viewed/{product_id}")
async def track_recently_viewed(product_id: str, session_id: str):
    """Track recently viewed product"""
    # Get or create session's recently viewed list
    existing = await db.recently_viewed.find_one({"session_id": session_id}, {"_id": 0})

    if existing:
        # Remove product if already in list, add to front
        viewed = [p for p in existing.get("products", []) if p != product_id]
        viewed.insert(0, product_id)
        viewed = viewed[:20]  # Keep only last 20

        await db.recently_viewed.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "products": viewed,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
    else:
        await db.recently_viewed.insert_one(
            {
                "session_id": session_id,
                "products": [product_id],
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    return {"success": True}


@router.get("/recently-viewed")
async def get_recently_viewed(session_id: str):
    """Get recently viewed products"""
    record = await db.recently_viewed.find_one({"session_id": session_id}, {"_id": 0})

    if not record:
        return {"products": []}

    product_ids = record.get("products", [])[:10]

    # Fetch product details
    products = await db.products.find(
        {"id": {"$in": product_ids}, "is_active": True}, {"_id": 0}
    ).to_list(10)

    # Sort by original order
    products_map = {p["id"]: p for p in products}
    sorted_products = [products_map[pid] for pid in product_ids if pid in products_map]

    return {"products": sorted_products}


# ============ GIFT WRAPPING ============


@router.get("/gift-wrap/options")
async def get_gift_wrap_options():
    """Get gift wrapping options"""
    settings = await db.settings.find_one({"type": "gift_wrap"}, {"_id": 0})

    if not settings:
        # Default options
        return {
            "enabled": True,
            "price": 5.99,
            "options": [
                {
                    "id": "standard",
                    "name": "Standard Gift Wrap",
                    "price": 5.99,
                    "description": "Elegant pink tissue paper with ribbon",
                },
                {
                    "id": "premium",
                    "name": "Premium Gift Box",
                    "price": 12.99,
                    "description": "Luxurious black box with gold foil accent",
                },
                {
                    "id": "eco",
                    "name": "Eco-Friendly Wrap",
                    "price": 4.99,
                    "description": "Recyclable kraft paper with dried flower",
                },
            ],
        }

    return settings


# ============ PAYROLL ENDPOINTS ============


@router.get("/admin/employees")
async def get_employees(current_user: dict = Depends(require_admin)):
    """Get all employees"""
    employees = await db.employees.find({}, {"_id": 0}).to_list(500)
    return employees


@router.post("/admin/employees")
async def create_employee(employee: dict, current_user: dict = Depends(require_admin)):
    """Create a new employee"""
    employee_data = {
        "id": str(uuid.uuid4()),
        "name": employee.get("name"),
        "email": employee.get("email"),
        "phone": employee.get("phone"),
        "role": employee.get("role", "Staff"),
        "hourly_rate": float(employee.get("hourly_rate", 0)),
        "salary": employee.get("salary"),
        "employment_type": employee.get("employment_type", "hourly"),
        "tax_rate": float(employee.get("tax_rate", 15)),
        "start_date": employee.get("start_date"),
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.employees.insert_one(employee_data)
    # Remove _id before returning
    employee_data.pop("_id", None)
    return {"message": "Employee created", "employee": employee_data}


@router.put("/admin/employees/{employee_id}")
async def update_employee(
    employee_id: str, employee: dict, current_user: dict = Depends(require_admin)
):
    """Update an employee"""
    update_data = {k: v for k, v in employee.items() if v is not None and k != "id"}
    if "hourly_rate" in update_data:
        update_data["hourly_rate"] = float(update_data["hourly_rate"])
    if "tax_rate" in update_data:
        update_data["tax_rate"] = float(update_data["tax_rate"])

    result = await db.employees.update_one({"id": employee_id}, {"$set": update_data})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"message": "Employee updated"}


@router.delete("/admin/employees/{employee_id}")
async def delete_employee(
    employee_id: str, current_user: dict = Depends(require_admin)
):
    """Delete an employee"""
    result = await db.employees.delete_one({"id": employee_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"message": "Employee deleted"}


@router.get("/admin/payroll")
async def get_payroll_entries(current_user: dict = Depends(require_admin)):
    """Get all payroll entries"""
    entries = await db.payroll.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return entries


@router.post("/admin/payroll/generate")
async def generate_payroll(data: dict, current_user: dict = Depends(require_admin)):
    """Generate payroll for selected employees"""
    pay_period_start = data.get("pay_period_start")
    pay_period_end = data.get("pay_period_end")
    pay_type = data.get("pay_type", "weekly")
    employee_hours = data.get(
        "employee_hours", []
    )  # List of {employee_id, hours_worked, other_deductions, deduction_notes}

    if not pay_period_start or not pay_period_end:
        raise HTTPException(status_code=400, detail="Pay period dates required")

    payroll_entries = []

    for emp_data in employee_hours:
        employee_id = emp_data.get("employee_id")
        hours_worked = float(emp_data.get("hours_worked", 0))
        other_deductions = float(emp_data.get("other_deductions", 0))
        deduction_notes = emp_data.get("deduction_notes", "")

        # Get employee details
        employee = await db.employees.find_one({"id": employee_id}, {"_id": 0})
        if not employee:
            continue

        hourly_rate = float(employee.get("hourly_rate", 0))
        tax_rate = float(employee.get("tax_rate", 15))

        # Calculate pay
        gross_pay = hours_worked * hourly_rate
        tax_deduction = gross_pay * (tax_rate / 100)
        net_pay = gross_pay - tax_deduction - other_deductions

        entry = {
            "id": str(uuid.uuid4()),
            "employee_id": employee_id,
            "employee_name": employee.get("name"),
            "pay_period_start": pay_period_start,
            "pay_period_end": pay_period_end,
            "hours_worked": hours_worked,
            "hourly_rate": hourly_rate,
            "gross_pay": round(gross_pay, 2),
            "tax_deduction": round(tax_deduction, 2),
            "other_deductions": round(other_deductions, 2),
            "deduction_notes": deduction_notes,
            "net_pay": round(net_pay, 2),
            "pay_type": pay_type,
            "status": "pending",
            "paid_date": None,
            "notes": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": current_user.get("id"),
        }

        await db.payroll.insert_one(entry)
        payroll_entries.append(entry)

    return {
        "message": f"Generated {len(payroll_entries)} payroll entries",
        "entries": payroll_entries,
    }


@router.put("/admin/payroll/{payroll_id}/status")
async def update_payroll_status(
    payroll_id: str, data: dict, current_user: dict = Depends(require_admin)
):
    """Update payroll entry status"""
    status = data.get("status", "paid")
    update = {"status": status}
    if status == "paid":
        update["paid_date"] = datetime.now(timezone.utc).isoformat()

    result = await db.payroll.update_one({"id": payroll_id}, {"$set": update})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Payroll entry not found")
    return {"message": "Payroll status updated"}


@router.delete("/admin/payroll/{payroll_id}")
async def delete_payroll(payroll_id: str, current_user: dict = Depends(require_admin)):
    """Delete a payroll entry"""
    result = await db.payroll.delete_one({"id": payroll_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Payroll entry not found")
    return {"message": "Payroll entry deleted"}


@router.get("/admin/payroll/summary")
async def get_payroll_summary(current_user: dict = Depends(require_admin)):
    """Get payroll summary statistics"""
    all_entries = await db.payroll.find({}, {"_id": 0}).to_list(5000)

    total_gross = sum(e.get("gross_pay", 0) for e in all_entries)
    total_tax = sum(e.get("tax_deduction", 0) for e in all_entries)
    total_net = sum(e.get("net_pay", 0) for e in all_entries)
    total_paid = sum(
        e.get("net_pay", 0) for e in all_entries if e.get("status") == "paid"
    )
    total_pending = sum(
        e.get("net_pay", 0) for e in all_entries if e.get("status") == "pending"
    )

    # Group by pay period
    by_period = {}
    for e in all_entries:
        period_key = f"{e.get('pay_period_start')} to {e.get('pay_period_end')}"
        if period_key not in by_period:
            by_period[period_key] = {"gross": 0, "tax": 0, "net": 0, "count": 0}
        by_period[period_key]["gross"] += e.get("gross_pay", 0)
        by_period[period_key]["tax"] += e.get("tax_deduction", 0)
        by_period[period_key]["net"] += e.get("net_pay", 0)
        by_period[period_key]["count"] += 1

    return {
        "total_gross_pay": round(total_gross, 2),
        "total_tax_deducted": round(total_tax, 2),
        "total_net_pay": round(total_net, 2),
        "total_paid": round(total_paid, 2),
        "total_pending": round(total_pending, 2),
        "total_entries": len(all_entries),
        "by_period": by_period,
    }


@router.get("/admin/payroll/settings")
async def get_payroll_settings(current_user: dict = Depends(require_admin)):
    """Get pay stub customization settings"""
    settings = await db.store_settings.find_one(
        {"type": "payroll_settings"}, {"_id": 0}
    )
    if not settings:
        # Return default settings if none exist
        return {
            "logo_url": "",
            "company_name": "ReRoots Beauty Enhancer",
            "company_address": "",
            "company_phone": "",
            "company_email": "",
            "header_text": "",
            "footer_text": "This is a computer-generated pay stub.",
            "signature_name": "",
            "signature_title": "",
            "show_signature_line": True,
            "accent_color": "#F8A5B8",
        }
    # Remove the type field before returning
    settings.pop("type", None)
    return settings


@router.post("/admin/payroll/settings")
async def save_payroll_settings(
    settings: dict, current_user: dict = Depends(require_admin)
):
    """Save pay stub customization settings"""
    settings_data = {
        "type": "payroll_settings",
        "logo_url": settings.get("logo_url", ""),
        "company_name": settings.get("company_name", "ReRoots Beauty Enhancer"),
        "company_address": settings.get("company_address", ""),
        "company_phone": settings.get("company_phone", ""),
        "company_email": settings.get("company_email", ""),
        "header_text": settings.get("header_text", ""),
        "footer_text": settings.get(
            "footer_text", "This is a computer-generated pay stub."
        ),
        "signature_name": settings.get("signature_name", ""),
        "signature_title": settings.get("signature_title", ""),
        "show_signature_line": settings.get("show_signature_line", True),
        "accent_color": settings.get("accent_color", "#F8A5B8"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Upsert the settings document
    await db.store_settings.update_one(
        {"type": "payroll_settings"}, {"$set": settings_data}, upsert=True
    )

    return {"message": "Payroll settings saved successfully", "settings": settings_data}


# ============ PARTNER APPLICATIONS ============

# ============ OROÉ LUXURY BRAND APIS ============


# --- OROÉ Luxury Products ---
class OroeProductCreate(BaseModel):
    name: str
    price_usd: float
    limited_edition_quantity: int = 500
    inventory_type: str = "serialized"  # serialized or standard
    availability: str = "waitlist"  # waitlist or public
    batch_signature: str = ""  # e.g., "Batch 01 - May 2025"
    qr_destination: str = ""  # URL for post-purchase QR code
    descriptions: dict = {}  # {en: "...", fr: "...", ar: "..."}
    payment_methods: List[str] = ["stripe", "crypto"]
    redirect_to_ritual: bool = True
    hero_image_url: Optional[str] = None  # Primary image (kept for backwards compat)
    image_urls: List[str] = []  # Multiple product images gallery
    video_url: Optional[str] = None  # MP4 video for product page background
    status: str = "active"


# --- Translation Request Model ---
class TranslationRequest(BaseModel):
    text: str
    source_lang: str = "en"
    target_langs: List[str] = ["fr", "ar"]


@router.post("/admin/oroe/products")
async def create_oroe_product(
    product: OroeProductCreate, current_user: dict = Depends(require_admin)
):
    """Create a new OROÉ luxury product"""
    try:
        # Generate product slug
        slug = product.name.lower().replace(" ", "-").replace("(", "").replace(")", "")
        slug = re.sub(r"[^a-z0-9-]", "", slug)

        # Check for existing product with same slug
        existing = await db.oroe_products.find_one({"slug": slug})
        if existing:
            raise HTTPException(
                status_code=400, detail="Product with this name already exists"
            )

        product_data = {
            "name": product.name,
            "slug": slug,
            "price_usd": product.price_usd,
            "limited_edition_quantity": product.limited_edition_quantity,
            "sold_count": 0,
            "inventory_type": product.inventory_type,
            "availability": product.availability,
            "batch_signature": product.batch_signature,
            "qr_destination": product.qr_destination,
            "descriptions": product.descriptions,
            "payment_methods": product.payment_methods,
            "redirect_to_ritual": product.redirect_to_ritual,
            "hero_image_url": product.hero_image_url,
            "image_urls": product.image_urls,  # Multiple images gallery
            "video_url": product.video_url,  # Background video for product page
            "status": product.status,
            "created_by": str(current_user.get("_id", "")),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        result = await db.oroe_products.insert_one(product_data)
        product_data["_id"] = str(result.inserted_id)
        del product_data["created_by"]  # Remove ObjectId reference

        return {
            "success": True,
            "message": f"Luxury product '{product.name}' created successfully",
            "product": product_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/oroe/products")
async def get_oroe_products(current_user: dict = Depends(require_admin)):
    """Get all OROÉ luxury products"""
    try:
        products = (
            await db.oroe_products.find().sort("created_at", -1).to_list(length=100)
        )
        for p in products:
            p["_id"] = str(p["_id"])
            if "created_by" in p:
                del p["created_by"]
        return {"products": products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/oroe/products")
async def get_public_oroe_products():
    """Get active OROÉ products for public display (no auth required)"""
    try:
        # Only return active products
        products = (
            await db.oroe_products.find({"status": "active"})
            .sort("created_at", -1)
            .to_list(length=20)
        )
        for p in products:
            p["_id"] = str(p["_id"])
            # Remove sensitive fields from public response
            p.pop("created_by", None)
            p.pop("sold_count", None)
        return {"products": products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/oroe/products/{slug}")
async def get_oroe_product_by_slug(slug: str):
    """Get a specific OROÉ product by slug for public display"""
    try:
        product = await db.oroe_products.find_one({"slug": slug, "status": "active"})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        product["_id"] = str(product["_id"])
        product.pop("created_by", None)
        return {"product": product}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/oroe/products/{product_id}")
async def update_oroe_product(
    product_id: str,
    updates: dict = Body(...),
    current_user: dict = Depends(require_admin),
):
    """Update an OROÉ luxury product"""
    try:
        from bson import ObjectId

        # Remove protected fields
        updates.pop("_id", None)
        updates.pop("created_at", None)
        updates.pop("created_by", None)
        updates["updated_at"] = datetime.now(timezone.utc)

        result = await db.oroe_products.update_one(
            {"_id": ObjectId(product_id)}, {"$set": updates}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")

        return {"success": True, "message": "Product updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/oroe/products/{product_id}")
async def delete_oroe_product(
    product_id: str, current_user: dict = Depends(require_admin)
):
    """Delete an OROÉ luxury product"""
    try:
        from bson import ObjectId

        result = await db.oroe_products.delete_one({"_id": ObjectId(product_id)})

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")

        return {"success": True, "message": "Product deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/oroe/translate")
async def translate_product_description(
    request: TranslationRequest, current_user: dict = Depends(require_admin)
):
    """Auto-translate product description from English to French and Arabic using LLM"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        if not EMERGENT_LLM_KEY:
            raise HTTPException(
                status_code=500, detail="Translation service not configured"
            )

        if not request.text.strip():
            raise HTTPException(status_code=400, detail="Text to translate is required")

        translations = {}

        # Translate to each target language
        for target_lang in request.target_langs:
            lang_name = {
                "fr": "French",
                "ar": "Arabic",
                "es": "Spanish",
                "de": "German",
            }.get(target_lang, target_lang)

            prompt = f"""Translate the following luxury skincare product description from English to {lang_name}. 
Maintain the premium, sophisticated tone suitable for a high-end brand. 
Keep any technical terms accurate but accessible.
Use terminology appropriate for Canadian regulations (e.g., 'targets the appearance of' rather than medical claims).
Only return the translation, no explanations.

Text to translate:
{request.text}"""

            try:
                chat = LlmChat(
                    api_key=EMERGENT_LLM_KEY,
                    session_id=f"translate_{target_lang}_{str(uuid.uuid4())[:8]}",
                    system_message="You are a professional luxury brand translator specializing in skincare and cosmetics.",
                ).with_model("gemini", "gemini-2.0-flash")

                user_message = UserMessage(text=prompt)
                response = await chat.send_message(user_message)
                translations[target_lang] = response.strip()
            except Exception as e:
                logger.error(f"Translation error for {lang_name}: {e}")
                translations[target_lang] = f"[Translation unavailable: {str(e)[:50]}]"

        return {
            "success": True,
            "translations": translations,
            "source_text": request.text,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Translation endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/oroe/waitlist")
async def submit_oroe_waitlist(application: dict = Body(...)):
    """Submit OROÉ VIP waitlist application with pre-qualification data"""
    try:
        # Calculate pre-qualification score based on answers
        score = 0
        units_requested = application.get("unitsRequested", "1")
        payment_preference = application.get("paymentPreference", "traditional")
        clinical_experience = application.get("clinicalExperience", "first-time")

        # Scoring logic
        if units_requested == "6+":
            score += 3
        elif units_requested == "3":
            score += 2
        else:
            score += 1

        if payment_preference == "crypto":
            score += 1

        if clinical_experience == "professional":
            score += 2
        elif clinical_experience == "experienced":
            score += 1

        # Determine if high-value VIP (6+ units + crypto = gold highlight)
        is_high_value = units_requested == "6+" and payment_preference == "crypto"

        waitlist_entry = {
            "firstName": application.get("firstName", ""),
            "lastName": application.get("lastName", ""),
            "email": application.get("email", ""),
            "country": application.get("country", ""),
            "region": application.get("region", ""),  # For market filtering
            "skinConcern": application.get("skinConcern", ""),
            "whyJoin": application.get("whyJoin", ""),
            "language": application.get("language", "en"),
            "currency": application.get("currency", "USD"),
            "source": application.get("source", "landing_page"),
            # Referral tracking for "inner circle" growth
            "referredBy": application.get("referredBy", ""),  # Who referred them
            "referralCode": application.get("referralCode", ""),  # If they used a code
            # New pre-qualification fields
            "clinicalExperience": clinical_experience,
            "discoverySource": application.get("discoverySource", "direct"),
            "unitsRequested": units_requested,
            "paymentPreference": payment_preference,
            "communicationPreference": application.get(
                "communicationPreference", "email"
            ),
            "qualificationScore": min(score, 5),  # Max 5 stars
            "isHighValue": is_high_value,
            # Sample/Tester CRM fields
            "sampleStatus": "not_sent",  # not_sent, sent, received, tested, feedback_received
            "sampleSentDate": None,
            "feedbackNotes": "",  # Admin notes on tester feedback
            "feedbackRating": None,  # 1-5 rating from tester
            # Status tracking
            "status": "pending",  # pending, approved, blacklisted
            "accessCode": None,  # Generated on approval (OROE-VIP-XXX)
            "bottleReservedUntil": None,  # 48-hour reservation
            "bottle_number": None,
            "waitlist_position": None,
            "created_at": datetime.now(timezone.utc),
            "approved_at": None,
            "brand": "oroe",
        }

        # Check if email already exists
        existing = await db.oroe_waitlist.find_one({"email": waitlist_entry["email"]})
        if existing:
            return {
                "success": True,
                "message": "Already on waitlist",
                "status": existing.get("status"),
                "position": existing.get("waitlist_position"),
            }

        # Get next waitlist number
        count = await db.oroe_waitlist.count_documents({})
        waitlist_entry["waitlist_position"] = count + 1

        result = await db.oroe_waitlist.insert_one(waitlist_entry)

        return {
            "success": True,
            "message": "Application received",
            "position": waitlist_entry["waitlist_position"],
            "id": str(result.inserted_id),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Country to region mapping for market filtering
COUNTRY_REGIONS = {
    # Middle East
    "UAE": "middle_east",
    "Saudi Arabia": "middle_east",
    "Qatar": "middle_east",
    "Kuwait": "middle_east",
    "Bahrain": "middle_east",
    "Oman": "middle_east",
    "Jordan": "middle_east",
    "Lebanon": "middle_east",
    # Canada
    "Canada": "canada",
    # Europe
    "France": "europe",
    "Germany": "europe",
    "UK": "europe",
    "United Kingdom": "europe",
    "Italy": "europe",
    "Spain": "europe",
    "Netherlands": "europe",
    "Belgium": "europe",
    "Switzerland": "europe",
    "Austria": "europe",
    "Sweden": "europe",
    # USA
    "USA": "north_america",
    "United States": "north_america",
    # Asia Pacific
    "Japan": "asia_pacific",
    "South Korea": "asia_pacific",
    "Singapore": "asia_pacific",
    "Hong Kong": "asia_pacific",
    "Australia": "asia_pacific",
}

COUNTRY_FLAGS = {
    "Canada": "🇨🇦",
    "UAE": "🇦🇪",
    "Saudi Arabia": "🇸🇦",
    "Qatar": "🇶🇦",
    "Kuwait": "🇰🇼",
    "France": "🇫🇷",
    "Germany": "🇩🇪",
    "UK": "🇬🇧",
    "United Kingdom": "🇬🇧",
    "Italy": "🇮🇹",
    "Spain": "🇪🇸",
    "USA": "🇺🇸",
    "United States": "🇺🇸",
    "Japan": "🇯🇵",
    "South Korea": "🇰🇷",
    "Singapore": "🇸🇬",
    "Hong Kong": "🇭🇰",
    "Australia": "🇦🇺",
    "Netherlands": "🇳🇱",
    "Belgium": "🇧🇪",
    "Switzerland": "🇨🇭",
    "Sweden": "🇸🇪",
    "Austria": "🇦🇹",
    "Bahrain": "🇧🇭",
    "Oman": "🇴🇲",
    "Jordan": "🇯🇴",
    "Lebanon": "🇱🇧",
}


@router.get("/oroe/waitlist/stats")
async def get_oroe_waitlist_stats():
    """Get OROÉ waitlist statistics for Global Command Center"""
    try:
        total = await db.oroe_waitlist.count_documents({})
        approved = await db.oroe_waitlist.count_documents({"status": "approved"})
        pending = await db.oroe_waitlist.count_documents({"status": "pending"})
        blacklisted = await db.oroe_waitlist.count_documents({"status": "blacklisted"})
        high_value = await db.oroe_waitlist.count_documents({"isHighValue": True})

        # Middle East interest (UAE, Saudi, Qatar, Kuwait, etc.)
        middle_east_countries = [
            "UAE",
            "Saudi Arabia",
            "Qatar",
            "Kuwait",
            "Bahrain",
            "Oman",
            "Jordan",
            "Lebanon",
        ]
        middle_east_count = await db.oroe_waitlist.count_documents(
            {"country": {"$in": middle_east_countries}}
        )

        # Canada interest
        canada_count = await db.oroe_waitlist.count_documents({"country": "Canada"})

        # Europe interest
        europe_countries = [
            "France",
            "Germany",
            "UK",
            "United Kingdom",
            "Italy",
            "Spain",
            "Netherlands",
            "Belgium",
            "Switzerland",
            "Austria",
            "Sweden",
        ]
        europe_count = await db.oroe_waitlist.count_documents(
            {"country": {"$in": europe_countries}}
        )

        # Crypto preference count
        crypto_preference = await db.oroe_waitlist.count_documents(
            {"paymentPreference": "crypto"}
        )

        # Conversion forecast (approved * $155 USD)
        conversion_forecast = approved * 155

        # Potential revenue (all pending + approved who requested units)
        pipeline_revenue = [
            {"$match": {"status": {"$in": ["pending", "approved"]}}},
            {
                "$group": {
                    "_id": None,
                    "potential": {
                        "$sum": {
                            "$switch": {
                                "branches": [
                                    {
                                        "case": {"$eq": ["$unitsRequested", "6+"]},
                                        "then": 930,
                                    },  # 6 * 155
                                    {
                                        "case": {"$eq": ["$unitsRequested", "3"]},
                                        "then": 465,
                                    },  # 3 * 155
                                ],
                                "default": 155,
                            }
                        }
                    },
                }
            },
        ]
        revenue_result = await db.oroe_waitlist.aggregate(pipeline_revenue).to_list(
            length=1
        )
        potential_revenue = revenue_result[0]["potential"] if revenue_result else 0

        # Get country distribution
        pipeline = [
            {"$group": {"_id": "$country", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]
        by_country = await db.oroe_waitlist.aggregate(pipeline).to_list(length=10)

        # Add flags to country data
        for item in by_country:
            item["flag"] = COUNTRY_FLAGS.get(item["_id"], "🌍")

        return {
            "global_demand": total,
            "total": total,
            "approved": approved,
            "pending": pending,
            "blacklisted": blacklisted,
            "high_value_vips": high_value,
            "batch_availability": max(0, 500 - approved),
            "remaining_slots": max(0, 500 - approved),
            "middle_east_interest": middle_east_count,
            "canada_interest": canada_count,
            "europe_interest": europe_count,
            "crypto_preference": crypto_preference,
            "conversion_forecast": conversion_forecast,
            "potential_revenue": potential_revenue,
            "by_country": by_country,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/oroe/waitlist")
async def get_oroe_waitlist(
    market: Optional[str] = None,
    status: Optional[str] = None,
    high_value_only: bool = False,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(require_admin),
):
    """Get OROÉ waitlist applications with market filtering for admin"""
    try:
        # Build filter query
        query = {}

        # Market filter
        if market == "middle_east":
            query["country"] = {
                "$in": [
                    "UAE",
                    "Saudi Arabia",
                    "Qatar",
                    "Kuwait",
                    "Bahrain",
                    "Oman",
                    "Jordan",
                    "Lebanon",
                ]
            }
        elif market == "canada":
            query["country"] = "Canada"
        elif market == "europe":
            query["country"] = {
                "$in": [
                    "France",
                    "Germany",
                    "UK",
                    "United Kingdom",
                    "Italy",
                    "Spain",
                    "Netherlands",
                    "Belgium",
                    "Switzerland",
                    "Austria",
                    "Sweden",
                ]
            }
        elif market == "north_america":
            query["country"] = {"$in": ["USA", "United States", "Canada"]}
        elif market == "asia_pacific":
            query["country"] = {
                "$in": ["Japan", "South Korea", "Singapore", "Hong Kong", "Australia"]
            }

        # Status filter
        if status:
            query["status"] = status

        # High-value filter
        if high_value_only:
            query["isHighValue"] = True

        # Get total count for pagination
        total_count = await db.oroe_waitlist.count_documents(query)

        # Fetch applications with pagination, high-value first
        applications = (
            await db.oroe_waitlist.find(query)
            .sort(
                [
                    ("isHighValue", -1),  # High-value VIPs first
                    ("qualificationScore", -1),  # Then by score
                    ("created_at", -1),  # Then by date
                ]
            )
            .skip(skip)
            .limit(limit)
            .to_list(length=limit)
        )

        for app in applications:
            app["_id"] = str(app["_id"])
            app["flag"] = COUNTRY_FLAGS.get(app.get("country", ""), "🌍")
            app["region"] = COUNTRY_REGIONS.get(app.get("country", ""), "other")
            if "created_at" in app and app["created_at"]:
                app["created_at"] = (
                    app["created_at"].isoformat()
                    if hasattr(app["created_at"], "isoformat")
                    else str(app["created_at"])
                )
            if "approved_at" in app and app["approved_at"]:
                app["approved_at"] = (
                    app["approved_at"].isoformat()
                    if hasattr(app["approved_at"], "isoformat")
                    else str(app["approved_at"])
                )
            if "bottleReservedUntil" in app and app["bottleReservedUntil"]:
                app["bottleReservedUntil"] = (
                    app["bottleReservedUntil"].isoformat()
                    if hasattr(app["bottleReservedUntil"], "isoformat")
                    else str(app["bottleReservedUntil"])
                )

        return {
            "applications": applications,
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "has_more": (skip + limit) < total_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/oroe/waitlist/{application_id}/approve")
async def approve_oroe_application(
    application_id: str, current_user: dict = Depends(require_admin)
):
    """Approve an OROÉ waitlist application with unique access code and bottle reservation"""
    try:
        from bson import ObjectId

        # Get current approved count for bottle numbering
        approved_count = await db.oroe_waitlist.count_documents({"status": "approved"})

        if approved_count >= 500:
            raise HTTPException(
                status_code=400, detail="All 500 bottles have been allocated"
            )

        bottle_number = approved_count + 1

        # Generate unique access code (OROE-VIP-XXX)
        access_code = f"OROE-VIP-{str(bottle_number).zfill(3)}"

        # Calculate 48-hour reservation window
        reservation_expires = datetime.now(timezone.utc) + timedelta(hours=48)

        # Get the application to access email for mocked notification
        application = await db.oroe_waitlist.find_one({"_id": ObjectId(application_id)})
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")

        result = await db.oroe_waitlist.update_one(
            {"_id": ObjectId(application_id)},
            {
                "$set": {
                    "status": "approved",
                    "bottle_number": bottle_number,
                    "accessCode": access_code,
                    "bottleReservedUntil": reservation_expires,
                    "approved_at": datetime.now(timezone.utc),
                    "approved_by": str(current_user.get("_id", "")),
                }
            },
        )

        if result.modified_count == 0:
            raise HTTPException(
                status_code=404, detail="Application not found or already processed"
            )

        # Send real VIP approval email using Resend
        email_sent = await send_oroe_vip_approval_email(
            email=application.get("email"),
            first_name=application.get("firstName", application.get("first_name", "")),
            access_code=access_code,
            bottle_number=bottle_number,
            reservation_expires=reservation_expires.isoformat(),
        )

        # Log the email attempt
        email_status = "SENT" if email_sent else "FAILED"
        email_payload = {
            "to": application.get("email"),
            "subject": "Welcome to Maison OROÉ - Your VIP Access Has Been Approved",
            "access_code": access_code,
            "bottle_number": bottle_number,
            "reservation_expires": reservation_expires.isoformat(),
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "status": email_status,
        }

        # Store email log in database for tracking
        await db.oroe_email_logs.insert_one(
            {
                "type": "vip_approval",
                "application_id": application_id,
                "email_payload": email_payload,
                "email_sent": email_sent,
                "created_at": datetime.now(timezone.utc),
            }
        )

        return {
            "success": True,
            "bottle_number": bottle_number,
            "access_code": access_code,
            "reservation_expires": reservation_expires.isoformat(),
            "message": f"Approved! Bottle #{bottle_number} reserved with code {access_code}. Reservation valid for 48 hours.",
            "email_status": f"Email {'sent successfully' if email_sent else 'failed to send'} to {application.get('email', 'unknown')}",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/oroe/waitlist/{application_id}/blacklist")
async def blacklist_oroe_application(
    application_id: str, reason: str = "", current_user: dict = Depends(require_admin)
):
    """Blacklist an OROÉ waitlist application"""
    try:
        from bson import ObjectId

        result = await db.oroe_waitlist.update_one(
            {"_id": ObjectId(application_id)},
            {
                "$set": {
                    "status": "blacklisted",
                    "blacklist_reason": reason,
                    "blacklisted_at": datetime.now(timezone.utc),
                    "blacklisted_by": str(current_user.get("_id", "")),
                }
            },
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Application not found")

        return {"success": True, "message": "Application blacklisted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/oroe/waitlist/{application_id}/status")
async def update_oroe_status(
    application_id: str,
    status: str = Body(..., embed=True),
    current_user: dict = Depends(require_admin),
):
    """Update OROÉ waitlist application status (pending, approved, blacklisted)"""
    try:
        from bson import ObjectId

        if status not in ["pending", "approved", "blacklisted"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid status. Must be: pending, approved, or blacklisted",
            )

        update_data = {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
            "updated_by": str(current_user.get("_id", "")),
        }

        # If approving, add bottle number and access code
        if status == "approved":
            approved_count = await db.oroe_waitlist.count_documents(
                {"status": "approved"}
            )
            if approved_count >= 500:
                raise HTTPException(
                    status_code=400, detail="All 500 bottles have been allocated"
                )

            bottle_number = approved_count + 1
            update_data["bottle_number"] = bottle_number
            update_data["accessCode"] = f"OROE-VIP-{str(bottle_number).zfill(3)}"
            update_data["bottleReservedUntil"] = datetime.now(timezone.utc) + timedelta(
                hours=48
            )
            update_data["approved_at"] = datetime.now(timezone.utc)

        result = await db.oroe_waitlist.update_one(
            {"_id": ObjectId(application_id)}, {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Application not found")

        return {
            "success": True,
            "message": f"Status updated to {status}",
            "update_data": {
                k: str(v) if isinstance(v, datetime) else v
                for k, v in update_data.items()
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/oroe/waitlist/{application_id}/sample")
async def update_oroe_sample_status(
    application_id: str,
    sample_status: Optional[str] = Body(None),
    feedback_notes: Optional[str] = Body(None),
    feedback_rating: Optional[int] = Body(None),
    current_user: dict = Depends(require_admin),
):
    """Update OROÉ tester sample status and feedback notes for CRM tracking"""
    try:
        from bson import ObjectId

        valid_statuses = ["not_sent", "sent", "received", "tested", "feedback_received"]

        update_data = {
            "updated_at": datetime.now(timezone.utc),
            "updated_by": str(current_user.get("_id", "")),
        }

        if sample_status:
            if sample_status not in valid_statuses:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid sample status. Must be one of: {', '.join(valid_statuses)}",
                )
            update_data["sampleStatus"] = sample_status
            if sample_status == "sent":
                update_data["sampleSentDate"] = datetime.now(timezone.utc)

        if feedback_notes is not None:
            update_data["feedbackNotes"] = feedback_notes

        if feedback_rating is not None:
            if feedback_rating < 1 or feedback_rating > 5:
                raise HTTPException(
                    status_code=400, detail="Feedback rating must be between 1 and 5"
                )
            update_data["feedbackRating"] = feedback_rating

        result = await db.oroe_waitlist.update_one(
            {"_id": ObjectId(application_id)}, {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Application not found")

        return {
            "success": True,
            "message": "Sample tracking updated",
            "update_data": {
                k: str(v) if isinstance(v, datetime) else v
                for k, v in update_data.items()
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# OROÉ CRYPTO PAYMENT ENDPOINTS
# ============================================


class CryptoChargeRequest(BaseModel):
    amount: str
    currency: str = "USD"
    crypto_currency: str  # BTC, ETH, USDC
    description: str
    customer_email: str
    customer_name: str
    product_id: Optional[str] = None


@router.post("/oroe/crypto/create-charge")
async def create_crypto_charge(request: CryptoChargeRequest):
    """Create a crypto payment charge for OROÉ products using Coinbase Commerce"""
    import httpx

    try:
        # Get Coinbase Commerce API key from environment
        coinbase_api_key = os.environ.get("COINBASE_COMMERCE_API_KEY")

        if not coinbase_api_key:
            # For demo/development, create a mock charge
            charge_id = f"mock_{uuid.uuid4().hex[:12]}"

            # Store the charge in database
            charge_data = {
                "charge_id": charge_id,
                "amount": request.amount,
                "currency": request.currency,
                "crypto_currency": request.crypto_currency,
                "customer_email": request.customer_email,
                "customer_name": request.customer_name,
                "description": request.description,
                "product_id": request.product_id,
                "status": "pending",
                "is_mock": True,
                "created_at": datetime.utcnow(),
            }

            await db.oroe_crypto_charges.insert_one(charge_data)

            return {
                "success": True,
                "charge_id": charge_id,
                "hosted_url": f"/oroe/checkout/crypto/{charge_id}",
                "is_mock": True,
                "message": "Demo mode: Coinbase Commerce API key not configured. Set COINBASE_COMMERCE_API_KEY in environment.",
            }

        # Real Coinbase Commerce integration
        frontend_url = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:3000")

        payload = {
            "name": "OROÉ Luminous Elixir",
            "description": request.description,
            "pricing_type": "fixed_price",
            "local_price": {"amount": request.amount, "currency": request.currency},
            "redirect_url": f"{frontend_url}/oroe/payment-success",
            "cancel_url": f"{frontend_url}/oroe/payment-cancel",
            "metadata": {
                "customer_email": request.customer_email,
                "customer_name": request.customer_name,
                "crypto_currency": request.crypto_currency,
                "product_id": request.product_id or "oroe-luminous-elixir",
            },
        }

        headers = {
            "X-CC-Api-Key": coinbase_api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.commerce.coinbase.com/charges",
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        # Store charge in database
        charge_data = {
            "charge_id": data.get("data", {}).get("id"),
            "charge_code": data.get("data", {}).get("code"),
            "amount": request.amount,
            "currency": request.currency,
            "crypto_currency": request.crypto_currency,
            "customer_email": request.customer_email,
            "customer_name": request.customer_name,
            "description": request.description,
            "product_id": request.product_id,
            "hosted_url": data.get("data", {}).get("hosted_url"),
            "status": "pending",
            "is_mock": False,
            "created_at": datetime.utcnow(),
            "coinbase_response": data,
        }

        await db.oroe_crypto_charges.insert_one(charge_data)

        return {
            "success": True,
            "charge_id": data.get("data", {}).get("id"),
            "hosted_url": data.get("data", {}).get("hosted_url"),
            "expires_at": data.get("data", {}).get("expires_at"),
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"Coinbase Commerce API error: {e}")
        raise HTTPException(status_code=500, detail=f"Payment provider error: {str(e)}")
    except Exception as e:
        logger.error(f"Error creating crypto charge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/oroe/crypto/charge/{charge_id}")
async def get_crypto_charge_status(charge_id: str):
    """Get the status of a crypto payment charge"""
    try:
        charge = await db.oroe_crypto_charges.find_one({"charge_id": charge_id})

        if not charge:
            raise HTTPException(status_code=404, detail="Charge not found")

        return {
            "charge_id": charge_id,
            "status": charge.get("status", "pending"),
            "amount": charge.get("amount"),
            "currency": charge.get("currency"),
            "crypto_currency": charge.get("crypto_currency"),
            "customer_email": charge.get("customer_email"),
            "is_mock": charge.get("is_mock", False),
            "created_at": (
                charge.get("created_at").isoformat()
                if charge.get("created_at")
                else None
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/oroe/crypto/charges")
async def list_crypto_charges():
    """List all crypto payment charges for OROÉ"""
    try:
        charges = (
            await db.oroe_crypto_charges.find()
            .sort("created_at", -1)
            .to_list(length=100)
        )
        for charge in charges:
            charge["_id"] = str(charge["_id"])
            if "created_at" in charge and charge["created_at"]:
                charge["created_at"] = (
                    charge["created_at"].isoformat()
                    if hasattr(charge["created_at"], "isoformat")
                    else str(charge["created_at"])
                )
        return charges
    except Exception:
        return []


@router.post("/oroe/crypto/webhook")
async def handle_coinbase_webhook(request: Request):
    """Handle Coinbase Commerce webhook events"""
    import hmac

    try:
        body = await request.body()
        payload_str = body.decode("utf-8")
        signature = request.headers.get("X-CC-Webhook-Signature")

        webhook_secret = os.environ.get("COINBASE_WEBHOOK_SECRET")

        # Verify signature if secret is configured
        if webhook_secret and signature:
            expected_signature = hmac.new(
                webhook_secret.encode(), payload_str.encode(), hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(expected_signature, signature):
                logger.warning("Invalid webhook signature")
                raise HTTPException(status_code=401, detail="Invalid signature")

        import json

        webhook_data = json.loads(payload_str)

        event_type = webhook_data.get("type")
        charge_data = webhook_data.get("data", {})
        charge_id = charge_data.get("id")

        logger.info(f"Received Coinbase webhook: {event_type} for charge {charge_id}")

        if charge_id:
            # Update charge status in database
            status_map = {
                "charge:pending": "pending",
                "charge:confirmed": "confirmed",
                "charge:failed": "failed",
                "charge:expired": "expired",
            }

            new_status = status_map.get(event_type, "unknown")

            await db.oroe_crypto_charges.update_one(
                {"charge_id": charge_id},
                {
                    "$set": {"status": new_status, "updated_at": datetime.utcnow()},
                    "$push": {
                        "webhook_events": {
                            "event_type": event_type,
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": charge_data,
                        }
                    },
                },
            )

            # If payment confirmed, create an order
            if event_type == "charge:confirmed":
                charge = await db.oroe_crypto_charges.find_one({"charge_id": charge_id})
                if charge:
                    order_data = {
                        "order_id": f"OROE-{uuid.uuid4().hex[:8].upper()}",
                        "charge_id": charge_id,
                        "customer_email": charge.get("customer_email"),
                        "customer_name": charge.get("customer_name"),
                        "amount": charge.get("amount"),
                        "currency": charge.get("currency"),
                        "crypto_currency": charge.get("crypto_currency"),
                        "payment_method": "crypto",
                        "status": "paid",
                        "created_at": datetime.utcnow(),
                    }
                    await db.oroe_orders.insert_one(order_data)
                    logger.info(f"Created OROÉ order: {order_data['order_id']}")

        return {"status": "success", "message": "Webhook processed"}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/partner-applications")
async def submit_partner_application_v2(application: dict = Body(...)):
    """Submit a partner/influencer application"""
    try:
        application_data = {
            "full_name": application.get("full_name", ""),
            "first_name": application.get("first_name", ""),
            "last_name": application.get("last_name", ""),
            "email": application.get("email", ""),
            "phone": application.get("phone", ""),
            "phone_country_code": application.get("phone_country_code", "+1"),
            "instagram": application.get("instagram", ""),
            "tiktok": application.get("tiktok", ""),
            "youtube": application.get("youtube", ""),
            "followers": application.get("followers", ""),
            "niche": application.get("niche", ""),
            "message": application.get("message", ""),
            "status": "pending",
            "created_at": datetime.utcnow(),
            "source": "partner_program_page",
        }

        result = db.partner_applications.insert_one(application_data)

        # Also add to subscribers if not exists
        if application_data["email"]:
            existing = db.subscribers.find_one({"email": application_data["email"]})
            if not existing:
                db.subscribers.insert_one(
                    {
                        "email": application_data["email"],
                        "name": application_data["full_name"],
                        "phone": application_data.get("phone"),
                        "source": "partner_application",
                        "created_at": datetime.utcnow(),
                    }
                )

        return {
            "success": True,
            "message": "Application submitted successfully",
            "id": str(result.inserted_id),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/partner-applications")
async def get_partner_applications(current_user: dict = Depends(require_admin)):
    """Get all partner applications for admin review"""
    try:
        applications = list(db.partner_applications.find().sort("created_at", -1))
        for app in applications:
            app["_id"] = str(app["_id"])
            if "created_at" in app:
                app["created_at"] = app["created_at"].isoformat()
        return {"applications": applications}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ LA VELA BIANCA TEEN SKINCARE BRAND APIS ============


# --- LA VELA Customer Auth Models ---
class LaVelaSignup(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    password: str


class LaVelaLogin(BaseModel):
    email: EmailStr
    password: str


# --- LA VELA Customer Auth Endpoints ---
@router.post("/lavela/auth/signup")
async def lavela_signup(data: LaVelaSignup):
    """Sign up a new LA VELA BIANCA customer"""
    try:
        # Check if email already exists
        existing = await db.lavela_customers.find_one({"email": data.email.lower()})
        if existing:
            raise HTTPException(
                status_code=400, detail="Email already registered. Please sign in."
            )

        # Hash password
        hashed_password = bcrypt.hashpw(data.password.encode("utf-8"), bcrypt.gensalt())

        # Generate referral code
        referral_code = f"LV{secrets.token_hex(4).upper()}"

        customer_data = {
            "id": str(uuid.uuid4()),
            "name": data.name,
            "email": data.email.lower(),
            "phone": data.phone,
            "password": hashed_password.decode("utf-8"),
            "referral_code": referral_code,
            "points": 100,  # Welcome bonus
            "tier": "Bronze",
            "total_spent": 0,
            "orders": [],
            "is_glow_club_member": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": datetime.now(timezone.utc).isoformat(),
        }

        await db.lavela_customers.insert_one(customer_data)

        # Generate JWT token
        token_data = {
            "user_id": customer_data["id"],
            "email": customer_data["email"],
            "name": customer_data["name"],
            "brand": "lavela",
            "exp": datetime.now(timezone.utc) + timedelta(days=30),
        }
        token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)

        # Return safe user data (exclude password)
        user_response = {
            "id": customer_data["id"],
            "name": customer_data["name"],
            "email": customer_data["email"],
            "phone": customer_data["phone"],
            "points": customer_data["points"],
            "tier": customer_data["tier"],
            "referral_code": customer_data["referral_code"],
        }

        return {
            "token": token,
            "user": user_response,
            "message": "Welcome to LA VELA BIANCA!",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lavela/auth/login")
async def lavela_login(data: LaVelaLogin):
    """Login a LA VELA BIANCA customer"""
    try:
        customer = await db.lavela_customers.find_one({"email": data.email.lower()})
        if not customer:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Verify password
        if not bcrypt.checkpw(
            data.password.encode("utf-8"), customer["password"].encode("utf-8")
        ):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Update last login
        await db.lavela_customers.update_one(
            {"email": data.email.lower()},
            {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}},
        )

        # Generate JWT token
        token_data = {
            "user_id": customer["id"],
            "email": customer["email"],
            "name": customer["name"],
            "brand": "lavela",
            "exp": datetime.now(timezone.utc) + timedelta(days=30),
        }
        token = jwt.encode(token_data, JWT_SECRET, algorithm=JWT_ALGORITHM)

        # Return safe user data
        user_response = {
            "id": customer["id"],
            "name": customer["name"],
            "email": customer["email"],
            "phone": customer.get("phone"),
            "points": customer.get("points", 0),
            "tier": customer.get("tier", "Bronze"),
            "referral_code": customer.get("referral_code"),
        }

        return {"token": token, "user": user_response}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/lavela/customers")
async def get_lavela_customers(current_user: dict = Depends(require_admin)):
    """Get all LA VELA customers (admin only)"""
    try:
        customers = (
            await db.lavela_customers.find({}, {"password": 0})
            .sort("created_at", -1)
            .to_list(length=500)
        )
        for c in customers:
            c["_id"] = str(c["_id"])
        return {"customers": customers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- LA VELA Products Model ---
class LaVelaProductCreate(BaseModel):
    name: str
    price_cad: float
    description: str = ""
    short_description: str = ""
    ingredients: str = ""
    how_to_use: str = ""
    hero_image_url: Optional[str] = None
    image_urls: List[str] = []
    age_range: str = "8-16"  # Target age range
    skin_concerns: List[str] = []  # e.g., ["acne", "dryness", "sensitivity"]
    is_bestseller: bool = False
    stock: int = 100
    status: str = "active"


@router.post("/admin/lavela/products")
async def create_lavela_product(
    product: LaVelaProductCreate, current_user: dict = Depends(require_admin)
):
    """Create a new LA VELA BIANCA product"""
    try:
        slug = product.name.lower().replace(" ", "-").replace("(", "").replace(")", "")
        slug = re.sub(r"[^a-z0-9-]", "", slug)

        existing = await db.lavela_products.find_one({"slug": slug})
        if existing:
            raise HTTPException(
                status_code=400, detail="Product with this name already exists"
            )

        product_data = {
            "name": product.name,
            "slug": slug,
            "price_cad": product.price_cad,
            "description": product.description,
            "short_description": product.short_description,
            "ingredients": product.ingredients,
            "how_to_use": product.how_to_use,
            "hero_image_url": product.hero_image_url,
            "image_urls": product.image_urls,
            "age_range": product.age_range,
            "skin_concerns": product.skin_concerns,
            "is_bestseller": product.is_bestseller,
            "stock": product.stock,
            "status": product.status,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        result = await db.lavela_products.insert_one(product_data)
        product_data["id"] = str(result.inserted_id)
        if "_id" in product_data:
            del product_data["_id"]

        return {"message": "Product created successfully", "product": product_data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/lavela/products")
async def get_lavela_products(current_user: dict = Depends(require_admin)):
    """Get all LA VELA BIANCA products (admin)"""
    try:
        products = (
            await db.lavela_products.find().sort("created_at", -1).to_list(length=100)
        )
        for p in products:
            p["id"] = str(p["_id"])
            del p["_id"]
        return {"products": products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lavela/products")
async def get_public_lavela_products():
    """Get public LA VELA BIANCA products"""
    try:
        products = (
            await db.lavela_products.find({"status": "active"})
            .sort("created_at", -1)
            .to_list(length=50)
        )
        for p in products:
            p["id"] = str(p["_id"])
            del p["_id"]
        return {"products": products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/lavela/products/{product_id}")
async def update_lavela_product(
    product_id: str,
    updates: dict = Body(...),
    current_user: dict = Depends(require_admin),
):
    """Update a LA VELA BIANCA product"""
    try:
        updates["updated_at"] = datetime.now(timezone.utc)
        if "_id" in updates:
            del updates["_id"]
        if "id" in updates:
            del updates["id"]

        result = await db.lavela_products.update_one(
            {"_id": ObjectId(product_id)}, {"$set": updates}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")

        return {"message": "Product updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/lavela/products/{product_id}")
async def delete_lavela_product(
    product_id: str, current_user: dict = Depends(require_admin)
):
    """Delete a LA VELA BIANCA product"""
    try:
        result = await db.lavela_products.delete_one({"_id": ObjectId(product_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        return {"message": "Product deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Glow Club Membership ---
class GlowClubMember(BaseModel):
    email: str
    name: str
    age: Optional[int] = None
    parent_email: Optional[str] = None  # For minors
    tier: str = "starter"  # starter, pro, queen
    points: int = 0
    referral_code: Optional[str] = None


@router.post("/lavela/glow-club/join")
async def join_glow_club(member: GlowClubMember):
    """Join the Glow Club loyalty program"""
    try:
        existing = await db.lavela_glow_club.find_one({"email": member.email})
        if existing:
            raise HTTPException(status_code=400, detail="Already a Glow Club member")

        # Generate unique referral code
        import random
        import string

        referral_code = "GLOW" + "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )

        member_data = {
            "email": member.email,
            "name": member.name,
            "age": member.age,
            "parent_email": member.parent_email,
            "tier": "starter",
            "points": 100,  # Welcome bonus
            "referral_code": referral_code,
            "referred_by": member.referral_code,
            "total_spent": 0,
            "orders_count": 0,
            "joined_at": datetime.now(timezone.utc),
            "status": "active",
        }

        # Award referral points if referred by someone
        if member.referral_code:
            referrer = await db.lavela_glow_club.find_one(
                {"referral_code": member.referral_code}
            )
            if referrer:
                await db.lavela_glow_club.update_one(
                    {"_id": referrer["_id"]},
                    {"$inc": {"points": 200}},  # Referral bonus
                )

        result = await db.lavela_glow_club.insert_one(member_data)
        member_data["id"] = str(result.inserted_id)

        return {"message": "Welcome to the Glow Club!", "member": member_data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/lavela/glow-club")
async def get_glow_club_members(current_user: dict = Depends(require_admin)):
    """Get all Glow Club members (admin)"""
    try:
        members = (
            await db.lavela_glow_club.find().sort("joined_at", -1).to_list(length=500)
        )
        for m in members:
            m["id"] = str(m["_id"])
            del m["_id"]

        # Calculate stats
        total_members = len(members)
        tier_counts = {"starter": 0, "pro": 0, "queen": 0}
        total_points = 0

        for m in members:
            tier_counts[m.get("tier", "starter")] = (
                tier_counts.get(m.get("tier", "starter"), 0) + 1
            )
            total_points += m.get("points", 0)

        return {
            "members": members,
            "stats": {
                "total_members": total_members,
                "tier_counts": tier_counts,
                "total_points_issued": total_points,
                "avg_points": total_points // total_members if total_members > 0 else 0,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/lavela/glow-club/{member_id}")
async def update_glow_club_member(
    member_id: str,
    updates: dict = Body(...),
    current_user: dict = Depends(require_admin),
):
    """Update a Glow Club member"""
    try:
        if "_id" in updates:
            del updates["_id"]
        if "id" in updates:
            del updates["id"]

        result = await db.lavela_glow_club.update_one(
            {"_id": ObjectId(member_id)}, {"$set": updates}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Member not found")

        return {"message": "Member updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- LA VELA Analytics ---
@router.get("/admin/lavela/stats")
async def get_lavela_stats(current_user: dict = Depends(require_admin)):
    """Get LA VELA BIANCA analytics and statistics"""
    try:
        # Product stats
        products_count = await db.lavela_products.count_documents({"status": "active"})
        total_stock = 0
        products = await db.lavela_products.find({"status": "active"}).to_list(
            length=100
        )
        for p in products:
            total_stock += p.get("stock", 0)

        # Glow Club stats
        glow_club_count = await db.lavela_glow_club.count_documents({})
        glow_club_active = await db.lavela_glow_club.count_documents(
            {"status": "active"}
        )

        # Tier distribution
        starter_count = await db.lavela_glow_club.count_documents({"tier": "starter"})
        pro_count = await db.lavela_glow_club.count_documents({"tier": "pro"})
        queen_count = await db.lavela_glow_club.count_documents({"tier": "queen"})

        # Recent signups (last 7 days)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_signups = await db.lavela_glow_club.count_documents(
            {"joined_at": {"$gte": week_ago}}
        )

        return {
            "products": {"total": products_count, "total_stock": total_stock},
            "glow_club": {
                "total_members": glow_club_count,
                "active_members": glow_club_active,
                "recent_signups": recent_signups,
                "tiers": {
                    "starter": starter_count,
                    "pro": pro_count,
                    "queen": queen_count,
                },
            },
            "growth": {
                "weekly_signups": recent_signups,
                "conversion_rate": round(
                    (queen_count / glow_club_count * 100) if glow_club_count > 0 else 0,
                    1,
                ),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ SKINCARE NEWS FEED ============

import xml.etree.ElementTree as ET
from urllib.parse import quote


@router.get("/admin/skincare-news")
async def get_skincare_news(current_user: dict = Depends(require_admin)):
    """Fetch latest skincare industry news from multiple sources"""

    # Define skincare-related search queries for comprehensive coverage
    search_queries = [
        "skincare industry trends",
        "beauty skincare innovation",
        "cosmetics ingredients research",
        "skincare regulatory news",
        "beauty industry business",
    ]

    all_news = []

    async with aiohttp.ClientSession() as session:
        for query in search_queries:
            try:
                # Use Google News RSS feed
                rss_url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"

                async with session.get(
                    rss_url, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        content = await response.text()
                        root = ET.fromstring(content)

                        # Parse RSS items
                        for item in root.findall(".//item")[:5]:  # Get top 5 per query
                            title = item.find("title")
                            link = item.find("link")
                            pub_date = item.find("pubDate")
                            source = item.find("source")
                            description = item.find("description")

                            news_item = {
                                "id": str(uuid.uuid4()),
                                "title": (
                                    title.text if title is not None else "No title"
                                ),
                                "link": link.text if link is not None else "#",
                                "published": (
                                    pub_date.text if pub_date is not None else ""
                                ),
                                "source": (
                                    source.text if source is not None else "Google News"
                                ),
                                "description": (
                                    description.text[:200]
                                    if description is not None and description.text
                                    else ""
                                ),
                                "category": query.split()[0].capitalize(),
                            }

                            # Avoid duplicates based on title
                            if not any(
                                n["title"] == news_item["title"] for n in all_news
                            ):
                                all_news.append(news_item)

            except Exception as e:
                logging.warning(f"Failed to fetch news for query '{query}': {e}")
                continue

    # Sort by published date (most recent first) and limit
    all_news.sort(key=lambda x: x.get("published", ""), reverse=True)

    return {
        "news": all_news[:25],  # Return top 25 unique articles
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_sources": len(search_queries),
    }


# Root route
@router.get("/")
async def root():
    return {"message": "ReRoots Skincare API", "version": "1.0.0"}


