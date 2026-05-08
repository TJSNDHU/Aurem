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
        settings = InfluencerLandingSettings().model_dump()
    
    return settings


@router.get("/partner-program")
async def get_partner_program_info():
    """Public endpoint - get partner program info for application page"""
    settings = await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0})
    if not settings:
        settings = StoreSettings().model_dump()

    influencer = settings.get("influencer_program", {})
    referral = settings.get("referral_program", {})
    leaderboard = settings.get("leaderboard_settings", {})
    thank_you = settings.get("thank_you_messages", {})

    return {
        "influencer_program": {
            "enabled": influencer.get("enabled", True),
            "program_name": influencer.get("program_name", "ReRoots Partner Program"),
            "commission_rate": influencer.get("commission_rate", 10.0),
            "customer_discount_value": influencer.get("customer_discount_value", 50.0),
            "customer_discount_type": influencer.get(
                "customer_discount_type", "percentage"
            ),
            "min_followers": influencer.get("min_followers", 1000),
            "accepted_platforms": influencer.get(
                "accepted_platforms", ["instagram", "tiktok", "youtube"]
            ),
        },
        "referral_program": {
            "enabled": referral.get("enabled", True),
            "program_name": referral.get("program_name", "Share the Glow"),
            "referrer_reward_label": referral.get(
                "referrer_reward_label", "$10 Store Credit"
            ),
            "referee_reward_label": referral.get(
                "referee_reward_label", "$10 Off Your First Order"
            ),
            "milestones": referral.get("milestones", []),
        },
        "leaderboard_settings": {
            "reset_period": leaderboard.get("reset_period", "monthly"),
            "first_prize": leaderboard.get("first_prize", 500),
            "second_prize": leaderboard.get("second_prize", 250),
            "third_prize": leaderboard.get("third_prize", 100),
            "prize_type": leaderboard.get("prize_type", "cash"),
        },
        "thank_you_messages": {
            "partner_application": thank_you.get(
                "partner_application",
                "Thank you for applying to become a ReRoots Partner! 🌟 We're excited to review your application. Our team will get back to you within 48-72 hours with the next steps.",
            )
        },
    }


# ============================================
# PAGE CONTENT ENDPOINTS FOR PROGRAMS
# Quiz, Bio-Age Scan, Comparison Tool
# ============================================


@router.get("/quiz-page")
async def get_quiz_page_content():
    """Public endpoint - get skin quiz landing page content"""
    content = await db.quiz_page.find_one({"id": "quiz_page"}, {"_id": 0})

    if not content:
        # Default content
        content = {
            "id": "quiz_page",
            "hero": {
                "title": "Discover Your Perfect Skincare",
                "subtitle": "Take Our AI-Powered Skin Quiz",
                "description": "Answer a few questions about your skin and lifestyle, and we'll create a personalized routine just for you.",
                "image": "",
                "badge_text": "FREE SKIN ANALYSIS",
            },
            "about": {
                "title": "How It Works",
                "description": "Our advanced quiz analyzes your skin type, concerns, and goals to recommend the perfect products for your unique needs. Get personalized recommendations in under 2 minutes.",
            },
            "benefits": {
                "title": "Why Take The Quiz?",
                "items": [
                    {
                        "title": "Personalized Results",
                        "description": "Get product recommendations tailored to your skin",
                        "icon": "sparkles",
                    },
                    {
                        "title": "Expert-Backed",
                        "description": "Developed with dermatologist input",
                        "icon": "shield",
                    },
                    {
                        "title": "Save Time",
                        "description": "No more guessing which products are right for you",
                        "icon": "clock",
                    },
                    {
                        "title": "Exclusive Offers",
                        "description": "Unlock special discounts after completing the quiz",
                        "icon": "gift",
                    },
                ],
            },
            "cta": {
                "title": "Ready to Start?",
                "description": "Take our free skin quiz and discover your personalized skincare routine",
                "button_text": "Start Quiz",
            },
        }

    return content


@router.put("/admin/quiz-page")
async def update_quiz_page_content(data: dict, request: Request):
    """Admin - update skin quiz landing page content"""
    await require_admin(request)

    data["id"] = "quiz_page"
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.quiz_page.update_one({"id": "quiz_page"}, {"$set": data}, upsert=True)

    return {"success": True, "message": "Quiz page content updated"}


@router.get("/bio-scan-page")
async def get_bio_scan_page_content():
    """Public endpoint - get bio-age scan landing page content"""
    content = await db.bio_scan_page.find_one({"id": "bio_scan_page"}, {"_id": 0})

    if not content:
        # Default content
        content = {
            "id": "bio_scan_page",
            "hero": {
                "title": "Discover Your Skin's True Age",
                "subtitle": "AI-Powered Bio-Age Analysis",
                "description": "Upload a selfie and our advanced AI will analyze your skin to reveal your biological skin age and personalized recommendations.",
                "image": "",
                "badge_text": "FREE BIO-AGE SCAN",
            },
            "about": {
                "title": "What is Bio-Age?",
                "description": "Your biological age (bio-age) can differ from your chronological age based on lifestyle, skincare habits, and environmental factors. Our AI analyzes key facial features to determine your skin's true age.",
            },
            "benefits": {
                "title": "What You'll Learn",
                "items": [
                    {
                        "title": "Your Skin Age",
                        "description": "See how your skin compares to your actual age",
                        "icon": "calendar",
                    },
                    {
                        "title": "Key Concerns",
                        "description": "Identify wrinkles, texture, and tone issues",
                        "icon": "search",
                    },
                    {
                        "title": "Custom Routine",
                        "description": "Get product recommendations for your results",
                        "icon": "sparkles",
                    },
                    {
                        "title": "Track Progress",
                        "description": "Scan again later to see improvement",
                        "icon": "trending-up",
                    },
                ],
            },
            "cta": {
                "title": "Ready to See Your Results?",
                "description": "Take a quick selfie and discover your skin's biological age",
                "button_text": "Start Bio-Scan",
            },
        }

    return content


@router.put("/admin/bio-scan-page")
async def update_bio_scan_page_content(data: dict, request: Request):
    """Admin - update bio-age scan landing page content"""
    await require_admin(request)

    data["id"] = "bio_scan_page"
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.bio_scan_page.update_one(
        {"id": "bio_scan_page"}, {"$set": data}, upsert=True
    )

    return {"success": True, "message": "Bio-Age Scan page content updated"}


@router.get("/comparison-page")
async def get_comparison_page_content():
    """Public endpoint - get product comparison page content"""
    content = await db.comparison_page.find_one({"id": "comparison_page"}, {"_id": 0})

    if not content:
        # Default content
        content = {
            "id": "comparison_page",
            "hero": {
                "title": "Compare Products Side by Side",
                "subtitle": "Make Informed Skincare Decisions",
                "description": "Select up to 4 products and compare ingredients, benefits, and reviews to find the perfect match for your skin.",
                "image": "",
                "badge_text": "PRODUCT COMPARISON",
            },
            "about": {
                "title": "Why Compare?",
                "description": "With so many skincare options, it's hard to know which products are right for you. Our comparison tool makes it easy to see the differences and similarities between products.",
            },
            "features": {
                "title": "What You Can Compare",
                "items": [
                    {
                        "title": "Ingredients",
                        "description": "See key active ingredients side by side",
                        "icon": "beaker",
                    },
                    {
                        "title": "Benefits",
                        "description": "Compare what each product does for your skin",
                        "icon": "check-circle",
                    },
                    {
                        "title": "Reviews",
                        "description": "See ratings and customer feedback",
                        "icon": "star",
                    },
                    {
                        "title": "Price",
                        "description": "Compare value and price per ml",
                        "icon": "dollar-sign",
                    },
                ],
            },
            "cta": {
                "title": "Start Comparing",
                "description": "Select products from our collection to begin your comparison",
                "button_text": "Compare Now",
            },
        }

    return content


@router.put("/admin/comparison-page")
async def update_comparison_page_content(data: dict, request: Request):
    """Admin - update comparison tool page content"""
    await require_admin(request)

    data["id"] = "comparison_page"
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.comparison_page.update_one(
        {"id": "comparison_page"}, {"$set": data}, upsert=True
    )

    return {"success": True, "message": "Comparison page content updated"}


# ============= BIOMARKER BENCHMARKS API =============

@router.get("/admin/biomarker-benchmarks")
async def get_biomarker_benchmarks(request: Request):
    """Admin - get all biomarker benchmarks for comparison tool"""
    await require_admin(request)
    
    benchmarks = await db.biomarker_benchmarks.find({}, {"_id": 0}).sort("display_order", 1).to_list(100)
    return {"benchmarks": benchmarks, "count": len(benchmarks)}


@router.get("/biomarker-benchmarks")
async def get_public_biomarker_benchmarks():
    """Public endpoint - get active biomarker benchmarks"""
    benchmarks = await db.biomarker_benchmarks.find(
        {"is_active": True}, 
        {"_id": 0}
    ).sort("display_order", 1).to_list(100)
    return {"benchmarks": benchmarks}


@router.get("/admin/biomarker-benchmarks/categories")
async def get_biomarker_categories(request: Request):
    """Admin - get list of biomarker categories"""
    await require_admin(request)
    
    # Get distinct categories
    categories = await db.biomarker_benchmarks.distinct("category")
    
    # Default categories with descriptions
    default_categories = [
        {"value": "skin_age", "label": "Skin Age", "description": "Age-related markers"},
        {"value": "hydration", "label": "Hydration", "description": "Moisture levels"},
        {"value": "elasticity", "label": "Elasticity", "description": "Skin firmness"},
        {"value": "pigmentation", "label": "Pigmentation", "description": "Skin tone evenness"},
        {"value": "texture", "label": "Texture", "description": "Skin smoothness"},
        {"value": "inflammation", "label": "Inflammation", "description": "Redness and irritation"},
        {"value": "general", "label": "General", "description": "General health markers"},
    ]
    
    return {"categories": default_categories, "used_categories": categories}


@router.get("/admin/biomarker-benchmarks/{benchmark_id}")
async def get_biomarker_benchmark(benchmark_id: str, request: Request):
    """Admin - get a single biomarker benchmark"""
    await require_admin(request)
    
    benchmark = await db.biomarker_benchmarks.find_one({"id": benchmark_id}, {"_id": 0})
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return benchmark


@router.post("/admin/biomarker-benchmarks")
async def create_biomarker_benchmark(data: dict, request: Request):
    """Admin - create a new biomarker benchmark"""
    await require_admin(request)
    
    # Get current max display_order
    max_order_doc = await db.biomarker_benchmarks.find_one(
        {}, 
        {"display_order": 1}, 
        sort=[("display_order", -1)]
    )
    next_order = (max_order_doc.get("display_order", 0) + 1) if max_order_doc else 0
    
    benchmark = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", "New Biomarker"),
        "category": data.get("category", "general"),
        "unit": data.get("unit", ""),
        "low_threshold": float(data.get("low_threshold", 0)),
        "optimal_min": float(data.get("optimal_min", 30)),
        "optimal_max": float(data.get("optimal_max", 70)),
        "high_threshold": float(data.get("high_threshold", 100)),
        "low_label": data.get("low_label", "Low"),
        "optimal_label": data.get("optimal_label", "Optimal"),
        "high_label": data.get("high_label", "High"),
        "low_advice": data.get("low_advice", ""),
        "optimal_advice": data.get("optimal_advice", ""),
        "high_advice": data.get("high_advice", ""),
        "low_recommendations": data.get("low_recommendations", []),
        "high_recommendations": data.get("high_recommendations", []),
        "color_low": data.get("color_low", "#EF4444"),
        "color_optimal": data.get("color_optimal", "#22C55E"),
        "color_high": data.get("color_high", "#F59E0B"),
        "is_active": data.get("is_active", True),
        "display_order": data.get("display_order", next_order),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": None
    }
    
    await db.biomarker_benchmarks.insert_one(benchmark)
    
    # Broadcast event to admin WebSocket connections
    await broadcast_admin_event("biomarker_created", {
        "id": benchmark["id"],
        "name": benchmark["name"],
        "category": benchmark["category"]
    })
    
    # Remove _id before returning
    return {"success": True, "benchmark": {k: v for k, v in benchmark.items() if k != "_id"}}


@router.put("/admin/biomarker-benchmarks/reorder")
async def reorder_biomarker_benchmarks(data: dict, request: Request):
    """Admin - reorder biomarker benchmarks"""
    await require_admin(request)
    
    order = data.get("order", [])  # List of {id, display_order}
    
    for item in order:
        await db.biomarker_benchmarks.update_one(
            {"id": item["id"]},
            {"$set": {"display_order": item["display_order"]}}
        )
    
    return {"success": True, "message": "Order updated"}


@router.put("/admin/biomarker-benchmarks/{benchmark_id}")
async def update_biomarker_benchmark(benchmark_id: str, data: dict, request: Request):
    """Admin - update a biomarker benchmark"""
    await require_admin(request)
    
    existing = await db.biomarker_benchmarks.find_one({"id": benchmark_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    
    # Build update data
    update_data = {
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Allowed fields to update
    allowed_fields = [
        "name", "category", "unit",
        "low_threshold", "optimal_min", "optimal_max", "high_threshold",
        "low_label", "optimal_label", "high_label",
        "low_advice", "optimal_advice", "high_advice",
        "low_recommendations", "high_recommendations",
        "color_low", "color_optimal", "color_high",
        "is_active", "display_order"
    ]
    
    for field in allowed_fields:
        if field in data:
            # Convert numeric fields
            if field in ["low_threshold", "optimal_min", "optimal_max", "high_threshold", "display_order"]:
                update_data[field] = float(data[field]) if field != "display_order" else int(data[field])
            else:
                update_data[field] = data[field]
    
    await db.biomarker_benchmarks.update_one(
        {"id": benchmark_id},
        {"$set": update_data}
    )
    
    # Get updated document
    updated = await db.biomarker_benchmarks.find_one({"id": benchmark_id}, {"_id": 0})
    
    # Broadcast event
    await broadcast_admin_event("biomarker_updated", {
        "id": benchmark_id,
        "name": updated.get("name"),
        "category": updated.get("category")
    })
    
    return {"success": True, "benchmark": updated}


@router.delete("/admin/biomarker-benchmarks/{benchmark_id}")
async def delete_biomarker_benchmark(benchmark_id: str, request: Request):
    """Admin - delete a biomarker benchmark"""
    await require_admin(request)
    
    existing = await db.biomarker_benchmarks.find_one({"id": benchmark_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    
    await db.biomarker_benchmarks.delete_one({"id": benchmark_id})
    
    # Broadcast event
    await broadcast_admin_event("biomarker_deleted", {
        "id": benchmark_id,
        "name": existing.get("name")
    })
    
    return {"success": True, "message": "Benchmark deleted"}


@router.get("/shop-page")
async def get_shop_page_content():
    """Public endpoint - get shop/collections page content"""
    content = await db.shop_page.find_one({"id": "shop_page"}, {"_id": 0})

    if not content:
        # Default content
        content = {
            "id": "shop_page",
            "hero": {
                "title": "Shop Our Collections",
                "subtitle": "Science-Backed Skincare for Every Age",
                "description": "Discover our curated collections designed for different skin needs and ages. From teen-safe formulas to luxury anti-aging solutions.",
                "image": "",
                "badge_text": "EXCLUSIVE COLLECTIONS",
            },
            "about": {
                "title": "Our Philosophy",
                "description": "At ReRoots, we believe in skincare that's backed by science and tailored to your unique needs. Each collection is crafted with precision for specific age groups and skin concerns.",
            },
            "collections": {
                "title": "Explore Our Collections",
                "items": [
                    {
                        "name": "OROÉ",
                        "description": "Luxury cellular rejuvenation for 35+ skin",
                        "age_range": "35+",
                    },
                    {
                        "name": "ReRoots",
                        "description": "Clinical-grade bio-active skincare",
                        "age_range": "18-35",
                    },
                    {
                        "name": "La Vela Bianca",
                        "description": "Pediatric-safe luxury skincare",
                        "age_range": "8-18",
                    },
                ],
            },
            "cta": {
                "title": "Find Your Perfect Match",
                "description": "Not sure which collection is right for you? Take our skin quiz for personalized recommendations.",
                "button_text": "Take Skin Quiz",
            },
        }

    return content


@router.put("/admin/shop-page")
async def update_shop_page_content(data: dict, request: Request):
    """Admin - update shop page content"""
    await require_admin(request)

    data["id"] = "shop_page"
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.shop_page.update_one({"id": "shop_page"}, {"$set": data}, upsert=True)

    return {"success": True, "message": "Shop page content updated"}


@router.get("/waitlist-page")
async def get_waitlist_page_content():
    """Public endpoint - get waitlist page content"""
    content = await db.waitlist_page.find_one({"id": "waitlist_page"}, {"_id": 0})

    if not content:
        # Default content
        content = {
            "id": "waitlist_page",
            "hero": {
                "title": "Join the ReRoots Waitlist",
                "subtitle": "Be First to Experience the Future of Skincare",
                "description": "Sign up to get early access to new products, exclusive discounts, and insider skincare tips from our team.",
                "image": "",
                "badge_text": "EXCLUSIVE ACCESS",
            },
            "about": {
                "title": "Why Join?",
                "description": "Waitlist members get first access to limited-edition products, exclusive founding member discounts, and early bird pricing on new launches.",
            },
            "benefits": {
                "title": "Member Benefits",
                "items": [
                    {
                        "title": "Early Access",
                        "description": "Be first to shop new releases",
                        "icon": "clock",
                    },
                    {
                        "title": "Exclusive Discounts",
                        "description": "Members-only pricing and offers",
                        "icon": "gift",
                    },
                    {
                        "title": "Insider Tips",
                        "description": "Expert skincare advice delivered weekly",
                        "icon": "sparkles",
                    },
                    {
                        "title": "Refer & Earn",
                        "description": "Earn points by sharing with friends",
                        "icon": "users",
                    },
                ],
            },
            "cta": {
                "title": "Ready to Join?",
                "description": "Enter your email below to secure your spot",
                "button_text": "Join Waitlist",
            },
        }

    return content


@router.put("/admin/waitlist-page")
async def update_waitlist_page_content(data: dict, request: Request):
    """Admin - update waitlist page content"""
    await require_admin(request)

    data["id"] = "waitlist_page"
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.waitlist_page.update_one(
        {"id": "waitlist_page"}, {"$set": data}, upsert=True
    )

    return {"success": True, "message": "Waitlist page content updated"}


@router.get("/partner-leaderboard")
async def get_partner_leaderboard():
    """Public endpoint - get top 3 partners for the Founder's Leaderboard"""
    try:
        # Get approved partners with their referral counts
        partners = (
            await db.influencer_applications.find(
                {"status": "approved"},
                {
                    "_id": 0,
                    "full_name": 1,
                    "social_handle": 1,
                    "referral_count": 1,
                    "total_sales": 1,
                },
            )
            .sort("referral_count", -1)
            .limit(3)
            .to_list(3)
        )

        leaderboard = []
        avatars = ["👑", "⭐", "💫"]
        for i, partner in enumerate(partners):
            leaderboard.append(
                {
                    "name": partner.get("full_name", "Partner"),
                    "handle": partner.get("social_handle", "").replace("@", ""),
                    "referrals": partner.get("referral_count", 0),
                    "avatar": avatars[i] if i < len(avatars) else "🌟",
                }
            )

        return {"leaderboard": leaderboard}
    except Exception as e:
        logging.error(f"Error fetching leaderboard: {e}")
        return {"leaderboard": []}


@router.post("/partner-application")
async def submit_partner_application(application: dict):
    """
    Public endpoint - submit elite partner application.
    Creates an application that goes to admin review queue.
    """
    # Support both first_name/last_name and full_name
    first_name = application.get("first_name", "").strip()
    last_name = application.get("last_name", "").strip()
    full_name = application.get("full_name", "").strip()
    
    # Build full_name if not provided but first/last name are
    if not full_name and (first_name or last_name):
        full_name = f"{first_name} {last_name}".strip()
    
    # Update application with computed full_name
    application["full_name"] = full_name
    
    required_fields = [
        "full_name",
        "email",
        "primary_platform",
        "social_handle",
        "follower_count",
        "why_partner",
    ]
    for field in required_fields:
        if not application.get(field):
            raise HTTPException(
                status_code=400, detail=f"Missing required field: {field}"
            )

    # Check if already applied
    existing = await db.influencer_applications.find_one(
        {"email": application["email"].lower()}
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="An application with this email already exists"
        )

    # Build secondary platforms array from application data
    secondary_platforms = []
    if application.get("instagram_handle"):
        secondary_platforms.append(
            {
                "platform": "instagram",
                "handle": application["instagram_handle"],
                "followers": int(application.get("instagram_followers") or 0),
            }
        )
    if application.get("tiktok_handle"):
        secondary_platforms.append(
            {
                "platform": "tiktok",
                "handle": application["tiktok_handle"],
                "followers": int(application.get("tiktok_followers") or 0),
            }
        )
    if application.get("youtube_handle"):
        secondary_platforms.append(
            {
                "platform": "youtube",
                "handle": application["youtube_handle"],
                "followers": int(application.get("youtube_followers") or 0),
            }
        )

    # Auto-generate profile URL if not provided
    primary_platform = application["primary_platform"].lower()
    social_handle = application["social_handle"].replace("@", "")
    profile_url = application.get("profile_url", "")
    if not profile_url:
        if primary_platform == "instagram":
            profile_url = f"https://instagram.com/{social_handle}"
        elif primary_platform == "tiktok":
            profile_url = f"https://tiktok.com/@{social_handle}"
        elif primary_platform == "youtube":
            profile_url = f"https://youtube.com/@{social_handle}"

    # Create application
    app_data = {
        "id": str(uuid.uuid4()),
        "full_name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "email": application["email"].lower(),
        "phone": application.get("phone", ""),
        "phone_country_code": application.get("phone_country_code", "+1"),
        "whatsapp": application.get("whatsapp", application.get("phone", "")),
        "country": application.get("country", "Canada"),
        "primary_platform": primary_platform,
        "social_handle": application["social_handle"],
        "follower_count": (
            int(application["follower_count"])
            if application.get("follower_count")
            else 0
        ),
        "engagement_rate": float(application.get("engagement_rate") or 0),
        "content_niche": application.get("content_niche", "skincare"),
        "profile_url": profile_url,
        "secondary_platforms": secondary_platforms
        or application.get("secondary_platforms", []),
        "why_partner": application["why_partner"],
        "content_ideas": application.get("content_ideas", ""),
        "previous_brands": application.get("previous_brands", ""),
        "status": "pending",
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "total_clicks": 0,
        "total_orders": 0,
        "total_revenue": 0.0,
        "total_commission": 0.0,
        "pending_payout": 0.0,
    }

    await db.influencer_applications.insert_one(app_data)
    
    # Broadcast new partner application event to admin WebSocket connections
    await broadcast_admin_event("new_partner_application", {
        "application_id": app_data["id"],
        "name": full_name,
        "email": application["email"].lower(),
        "platform": primary_platform,
        "followers": app_data["follower_count"]
    })

    return {
        "message": "Application submitted successfully! We'll review and get back to you within 48 hours.",
        "application_id": app_data["id"],
    }


@router.get("/admin/influencers")
async def get_all_influencers(request: Request, status: str = None):
    """Admin - get all influencer applications"""
    await require_admin(request)

    query = {}
    if status:
        query["status"] = status

    applications = (
        await db.influencer_applications.find(query, {"_id": 0})
        .sort("applied_at", -1)
        .to_list(1000)
    )

    # Get stats
    total = await db.influencer_applications.count_documents({})
    pending = await db.influencer_applications.count_documents({"status": "pending"})
    approved = await db.influencer_applications.count_documents({"status": "approved"})
    active = await db.influencer_applications.count_documents({"status": "active"})

    return {
        "applications": applications,
        "stats": {
            "total": total,
            "pending": pending,
            "approved": approved,
            "active": active,
        },
    }


@router.get("/admin/influencers/{influencer_id}")
async def get_influencer_details(influencer_id: str, request: Request):
    """Admin - get single influencer details"""
    await require_admin(request)

    influencer = await db.influencer_applications.find_one(
        {"id": influencer_id}, {"_id": 0}
    )
    if not influencer:
        raise HTTPException(status_code=404, detail="Influencer not found")

    # Get their orders if active
    orders = []
    if influencer.get("partner_code"):
        orders = (
            await db.orders.find(
                {"discount_code": influencer["partner_code"]}, {"_id": 0}
            )
            .sort("created_at", -1)
            .to_list(100)
        )

    return {"influencer": influencer, "orders": orders}


@router.put("/admin/influencers/{influencer_id}/approve")
async def approve_influencer(influencer_id: str, request: Request, data: dict = None):
    """Admin - approve influencer and generate their unique code/link"""
    user = await require_admin(request)

    influencer = await db.influencer_applications.find_one({"id": influencer_id})
    if not influencer:
        raise HTTPException(status_code=404, detail="Influencer not found")

    # Generate unique partner code (e.g., REROOTS-SARAH20)
    name_part = influencer["social_handle"].upper().replace("@", "")[:10]
    partner_code = f"REROOTS-{name_part}"

    # Make sure code is unique
    existing_code = await db.influencer_applications.find_one(
        {"partner_code": partner_code}
    )
    if existing_code:
        partner_code = f"{partner_code}{random.randint(10, 99)}"

    # Get settings for default values
    settings = await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0})
    inf_settings = settings.get("influencer_program", {}) if settings else {}

    custom_discount = data.get("custom_discount") if data else None
    custom_commission = data.get("custom_commission") if data else None

    # Calculate partnership dates (1 year validity)
    partnership_start = datetime.now(timezone.utc)
    partnership_expires = partnership_start + timedelta(days=365)

    update_data = {
        "status": "approved",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_by": user["id"],
        "partner_code": partner_code,
        "partner_link": f"/partner/{partner_code.lower()}",
        "custom_discount": custom_discount
        or inf_settings.get("customer_discount_value", 50.0),
        "custom_commission": custom_commission
        or inf_settings.get("commission_rate", 10.0),
        "partnership_start_date": partnership_start.isoformat(),
        "partnership_expires_at": partnership_expires.isoformat(),
        "partnership_active": True,
        "renewal_requested": False,
        "renewal_requested_at": None,
    }

    await db.influencer_applications.update_one(
        {"id": influencer_id}, {"$set": update_data}
    )

    # Also create a coupon for their code
    coupon_data = {
        "id": str(uuid.uuid4()),
        "code": partner_code,
        "discount_type": "percentage",
        "discount_value": update_data["custom_discount"],
        "min_purchase": 0,
        "max_uses": 0,  # Unlimited
        "used_count": 0,
        "is_active": True,
        "expires_at": None,
        "is_influencer_code": True,
        "influencer_id": influencer_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Check if coupon already exists
    existing_coupon = await db.coupons.find_one({"code": partner_code})
    if not existing_coupon:
        await db.coupons.insert_one(coupon_data)

    # ===== SEND WHAPI APPROVAL NOTIFICATION =====
    whapi_sent = False
    phone = influencer.get("phone") or influencer.get("whatsapp")
    if phone:
        referral_link = f"https://reroots.ca/Bio-Age-Repair-Scan?ref={partner_code}"
        whapi_result = await send_partner_approved_whatsapp(
            phone=phone,
            name=influencer.get("full_name", ""),
            partner_code=partner_code,
            referral_link=referral_link,
        )
        whapi_sent = whapi_result.get("success", False)
        if whapi_sent:
            logger.info(f"Partner approval WhatsApp sent to {influencer_id}")
        else:
            logger.warning(
                f"Partner approval WhatsApp failed for {influencer_id}: {whapi_result.get('error')}"
            )
    
    # Broadcast partner approval event to admin WebSocket connections
    await broadcast_admin_event("partner_approved", {
        "partner_id": influencer_id,
        "name": influencer.get("full_name", ""),
        "partner_code": partner_code,
        "commission_rate": update_data["custom_commission"],
        "customer_discount": update_data["custom_discount"]
    })

    return {
        "message": "Influencer approved successfully!",
        "partner_code": partner_code,
        "partner_link": update_data["partner_link"],
        "commission_rate": update_data["custom_commission"],
        "customer_discount": update_data["custom_discount"],
        "whatsapp_notification_sent": whapi_sent,
    }


@router.put("/admin/influencers/{influencer_id}/reject")
async def reject_influencer(influencer_id: str, request: Request, data: dict):
    """Admin - reject influencer application"""
    user = await require_admin(request)

    # Get influencer data for notification
    influencer = await db.influencer_applications.find_one({"id": influencer_id})
    if not influencer:
        raise HTTPException(status_code=404, detail="Application not found")

    reason = data.get(
        "reason", "Application does not meet our requirements at this time."
    )

    await db.influencer_applications.update_one(
        {"id": influencer_id},
        {
            "$set": {
                "status": "rejected",
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "reviewed_by": user["id"],
                "rejection_reason": reason,
            }
        },
    )
    
    # Broadcast partner rejection event to admin WebSocket connections
    await broadcast_admin_event("partner_rejected", {
        "partner_id": influencer_id,
        "name": influencer.get("full_name", ""),
        "reason": reason
    })

    # ===== SEND WHAPI DENIAL NOTIFICATION =====
    whapi_sent = False
    phone = influencer.get("phone") or influencer.get("whatsapp")
    if phone:
        whapi_result = await send_partner_denied_whatsapp(
            phone=phone, name=influencer.get("full_name", "")
        )
        whapi_sent = whapi_result.get("success", False)
        if whapi_sent:
            logger.info(f"Partner denial WhatsApp sent to {influencer_id}")

    return {"message": "Application rejected", "whatsapp_notification_sent": whapi_sent}


@router.put("/admin/influencers/{influencer_id}")
async def update_influencer(influencer_id: str, request: Request, data: dict):
    """Admin - update influencer settings (commission, discount, status)"""
    await require_admin(request)

    allowed_fields = ["custom_discount", "custom_commission", "status", "partner_code"]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    if update_data:
        await db.influencer_applications.update_one(
            {"id": influencer_id}, {"$set": update_data}
        )

        # Update coupon if discount changed
        if "custom_discount" in update_data:
            influencer = await db.influencer_applications.find_one(
                {"id": influencer_id}
            )
            if influencer and influencer.get("partner_code"):
                await db.coupons.update_one(
                    {"code": influencer["partner_code"]},
                    {"$set": {"discount_value": update_data["custom_discount"]}},
                )

    return {"message": "Influencer updated"}


@router.get("/partner/{partner_code}")
async def get_partner_landing_page(partner_code: str):
    """Public - get influencer landing page data"""
    # Find influencer by code (case insensitive)
    influencer = await db.influencer_applications.find_one(
        {"partner_code": {"$regex": f"^{partner_code}$", "$options": "i"}},
        {"_id": 0, "email": 0, "phone": 0},  # Hide personal info
    )

    if not influencer or influencer.get("status") not in ["approved", "active"]:
        raise HTTPException(status_code=404, detail="Partner not found")

    # Increment clicks
    await db.influencer_applications.update_one(
        {"id": influencer["id"]}, {"$inc": {"total_clicks": 1}}
    )

    # Get program settings
    settings = await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0})
    inf_settings = settings.get("influencer_program", {}) if settings else {}

    # Get featured products
    products = (
        await db.products.find({"is_active": True, "is_featured": True}, {"_id": 0})
        .limit(4)
        .to_list(4)
    )

    return {
        "influencer": {
            "name": influencer["full_name"],
            "social_handle": influencer["social_handle"],
            "platform": influencer["primary_platform"],
            "profile_url": influencer["profile_url"],
            "partner_code": influencer["partner_code"],
            "discount": influencer.get(
                "custom_discount", inf_settings.get("customer_discount_value", 20)
            ),
        },
        "landing_page": {
            "headline": inf_settings.get(
                "landing_page_headline", "Exclusive Partner Access"
            ),
            "subheadline": inf_settings.get(
                "landing_page_subheadline",
                "Get {discount}% off with {influencer_name}'s special link",
            ),
            "cta": inf_settings.get("landing_page_cta", "Shop Now & Save"),
            "show_photo": inf_settings.get("show_influencer_photo", True),
            "show_banner": inf_settings.get("show_discount_banner", True),
        },
        "products": products,
        "anti_stacking": not inf_settings.get("allow_coupon_stacking", False),
    }


# ============= PARTNER VOUCHERS/REFERRAL OFFERS SYSTEM =============


@router.post("/admin/partner-vouchers")
async def create_partner_voucher(request: Request, data: dict):
    """Admin - create a special voucher/offer for a specific partner to share with their audience"""
    user = await require_admin(request)

    partner_id = data.get("partner_id")
    voucher_code = data.get("code", "").upper().strip()
    discount_type = data.get("discount_type", "percentage")  # percentage, fixed
    discount_value = float(data.get("discount_value", 10))
    partner_commission = float(
        data.get("partner_commission", 10)
    )  # % commission partner earns (10% of founder's price)
    min_order = float(data.get("min_order", 0))
    max_uses = int(data.get("max_uses", 0))  # 0 = unlimited
    valid_from = data.get("valid_from")
    valid_until = data.get("valid_until")
    description = data.get("description", "")
    applicable_products = data.get("applicable_products", [])  # Empty = all products
    is_active = data.get("is_active", True)

    if not partner_id or not voucher_code:
        raise HTTPException(
            status_code=400, detail="Partner ID and voucher code are required"
        )

    # Check partner exists
    partner = await db.influencer_applications.find_one({"id": partner_id}, {"_id": 0})
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    # Check code uniqueness
    existing = await db.partner_vouchers.find_one({"code": voucher_code})
    if existing:
        raise HTTPException(status_code=400, detail="Voucher code already exists")

    voucher_data = {
        "id": str(uuid.uuid4()),
        "partner_id": partner_id,
        "partner_name": partner.get("full_name", ""),
        "partner_code": partner.get("partner_code", ""),
        "code": voucher_code,
        "discount_type": discount_type,
        "discount_value": discount_value,
        "partner_commission": partner_commission,
        "min_order": min_order,
        "max_uses": max_uses,
        "current_uses": 0,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "description": description,
        "applicable_products": applicable_products,
        "is_active": is_active,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user["id"],
        "total_revenue": 0.0,
        "total_commission_earned": 0.0,
    }

    await db.partner_vouchers.insert_one(voucher_data)

    # Also create in coupons collection for checkout compatibility
    coupon_data = {
        "id": str(uuid.uuid4()),
        "code": voucher_code,
        "discount_type": discount_type,
        "discount_value": discount_value,
        "min_order": min_order,
        "max_uses": max_uses,
        "current_uses": 0,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "is_active": is_active,
        "partner_voucher_id": voucher_data["id"],
        "partner_id": partner_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.coupons.insert_one(coupon_data)

    # Return voucher without MongoDB _id
    voucher_data.pop("_id", None)
    return {"message": "Partner voucher created successfully", "voucher": voucher_data}


@router.get("/admin/partner-vouchers/{partner_id}")
async def get_partner_vouchers(partner_id: str, request: Request):
    """Admin - get all vouchers for a specific partner"""
    await require_admin(request)

    vouchers = (
        await db.partner_vouchers.find({"partner_id": partner_id}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )

    return {"vouchers": vouchers}


@router.get("/admin/partner-vouchers")
async def get_all_partner_vouchers(request: Request):
    """Admin - get all partner vouchers"""
    await require_admin(request)

    vouchers = (
        await db.partner_vouchers.find({}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(500)
    )
    return {"vouchers": vouchers}


@router.put("/admin/partner-vouchers/{voucher_id}")
async def update_partner_voucher(voucher_id: str, request: Request, data: dict):
    """Admin - update a partner voucher"""
    await require_admin(request)

    allowed_fields = [
        "discount_value",
        "partner_commission",
        "min_order",
        "max_uses",
        "valid_from",
        "valid_until",
        "description",
        "is_active",
        "applicable_products",
    ]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    if update_data:
        await db.partner_vouchers.update_one({"id": voucher_id}, {"$set": update_data})

        # Also update the coupon
        voucher = await db.partner_vouchers.find_one({"id": voucher_id})
        if voucher:
            coupon_update = {}
            if "discount_value" in update_data:
                coupon_update["discount_value"] = update_data["discount_value"]
            if "is_active" in update_data:
                coupon_update["is_active"] = update_data["is_active"]
            if "max_uses" in update_data:
                coupon_update["max_uses"] = update_data["max_uses"]
            if coupon_update:
                await db.coupons.update_one(
                    {"code": voucher["code"]}, {"$set": coupon_update}
                )

    return {"message": "Voucher updated"}


@router.delete("/admin/partner-vouchers/{voucher_id}")
async def delete_partner_voucher(voucher_id: str, request: Request):
    """Admin - delete a partner voucher"""
    await require_admin(request)

    voucher = await db.partner_vouchers.find_one({"id": voucher_id})
    if voucher:
        await db.coupons.delete_one({"code": voucher["code"]})
    await db.partner_vouchers.delete_one({"id": voucher_id})

    return {"message": "Voucher deleted"}


@router.get("/partner-vouchers/{partner_code}")
async def get_my_vouchers(partner_code: str, request: Request):
    """Partner - get their own vouchers (requires auth)"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_email = payload.get("email", "").lower()
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Find partner and verify
    partner = await db.influencer_applications.find_one(
        {"partner_code": {"$regex": f"^{partner_code}$", "$options": "i"}}, {"_id": 0}
    )

    if not partner or partner.get("email", "").lower() != user_email:
        raise HTTPException(status_code=403, detail="Access denied")

    vouchers = (
        await db.partner_vouchers.find(
            {"partner_id": partner["id"], "is_active": True}, {"_id": 0}
        )
        .sort("created_at", -1)
        .to_list(100)
    )

    return {"vouchers": vouchers, "partner": partner}


# ============= PARTNER MESSAGING SYSTEM =============


@router.post("/admin/partner-messages")
async def send_partner_message(request: Request, data: dict):
    """Admin - send message/task to partner with optional file attachment and notification"""
    user = await require_admin(request)

    partner_id = data.get("partner_id")
    message_type = data.get("type", "message")  # message, task, announcement
    subject = data.get("subject", "")
    content = data.get("content", "")
    files = data.get("files", [])  # Array of {name, url, type}
    priority = data.get("priority", "normal")  # low, normal, high, urgent
    send_email = data.get("send_email", True)
    send_sms = data.get("send_sms", False)

    if not partner_id or not content:
        raise HTTPException(
            status_code=400, detail="Partner ID and content are required"
        )

    # Get partner info
    partner = await db.influencer_applications.find_one({"id": partner_id}, {"_id": 0})
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    # Create message
    message_data = {
        "id": str(uuid.uuid4()),
        "partner_id": partner_id,
        "type": message_type,
        "subject": subject,
        "content": content,
        "files": files,
        "priority": priority,
        "sent_by": user["id"],
        "sent_by_name": user.get("name", "Admin"),
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "read": False,
        "read_at": None,
        "email_sent": False,
        "sms_sent": False,
    }

    await db.partner_messages.insert_one(message_data)

    # Get store settings for branding (used by both email and SMS)
    settings = await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0})
    store_name = settings.get("store_name", "ReRoots") if settings else "ReRoots"

    # Send email notification
    if send_email and partner.get("email"):
        try:

            email_subject = (
                f"[{store_name}] {subject or 'New Message from Partner Program'}"
            )

            # Build file links HTML
            files_html = ""
            if files:
                files_html = "<br><br><strong>Attached Files:</strong><ul>"
                for f in files:
                    files_html += f'<li><a href="{f.get("url", "#")}">{f.get("name", "File")}</a></li>'
                files_html += "</ul>"

            email_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #D4AF37, #F4D03F); padding: 20px; text-align: center;">
                    <h1 style="color: #2D2A2E; margin: 0;">✨ {store_name} Partner Program</h1>
                </div>
                <div style="padding: 30px; background: #FDF9F9;">
                    <p>Hi <strong>{partner.get('full_name', 'Partner')}</strong>,</p>
                    <p>You have a new {message_type} from the {store_name} team:</p>
                    <div style="background: white; border-left: 4px solid #D4AF37; padding: 20px; margin: 20px 0; border-radius: 0 8px 8px 0;">
                        {f'<h3 style="margin-top: 0; color: #2D2A2E;">{subject}</h3>' if subject else ''}
                        <p style="color: #5A5A5A; white-space: pre-wrap;">{content}</p>
                        {files_html}
                    </div>
                    <p>Log in to your partner dashboard to respond or view more details.</p>
                    <p style="color: #888; font-size: 12px;">- The {store_name} Team</p>
                </div>
            </div>
            """

            # Try to send via Resend
            resend_key = os.environ.get("RESEND_API_KEY")
            if resend_key:
                import httpx

                sender_domain = os.environ.get("RESEND_DOMAIN", "resend.dev")
                sender_email = (
                    f"{store_name} <onboarding@resend.dev>"  # Use Resend's test domain
                )

                # Check if domain is verified - if not, we're in test mode
                is_test_mode = sender_domain == "resend.dev" or not sender_domain

                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    # In test mode, try sending to admin email as CC/notification
                    admin_email = os.environ.get("ADMIN_EMAIL", "admin@reroots.ca")

                    # First try to send to partner
                    response = await http_client.post(
                        "https://api.resend.com/emails",
                        headers={"Authorization": f"Bearer {resend_key}"},
                        json={
                            "from": sender_email,
                            "to": [partner["email"]],
                            "subject": email_subject,
                            "html": email_html,
                        },
                    )

                    if response.status_code == 200:
                        message_data["email_sent"] = True
                        await db.partner_messages.update_one(
                            {"id": message_data["id"]}, {"$set": {"email_sent": True}}
                        )
                        logger.info(f"Email sent successfully to {partner['email']}")
                    elif response.status_code == 403 and is_test_mode:
                        # Domain not verified - send notification to admin instead and log for partner
                        logger.warning(
                            "Resend domain not verified. Sending notification to admin instead."
                        )

                        # Send to admin as notification
                        admin_response = await http_client.post(
                            "https://api.resend.com/emails",
                            headers={"Authorization": f"Bearer {resend_key}"},
                            json={
                                "from": sender_email,
                                "to": [admin_email],
                                "subject": f"[COPY] Partner Message to {partner.get('full_name', partner['email'])}",
                                "html": f"<p><strong>Note:</strong> This is a copy. Original recipient: {partner['email']}</p><hr/>{email_html}",
                            },
                        )

                        if admin_response.status_code == 200:
                            message_data["email_sent"] = True
                            message_data["email_to_admin"] = True
                            await db.partner_messages.update_one(
                                {"id": message_data["id"]},
                                {"$set": {"email_sent": True, "email_to_admin": True}},
                            )
                            logger.info(
                                f"Email copy sent to admin ({admin_email}) - Domain verification pending for partner emails"
                            )
                        else:
                            message_data["email_error"] = (
                                "Domain not verified - verify at resend.com/domains"
                            )
                    else:
                        logger.error(
                            f"Resend API error: {response.status_code} - {response.text}"
                        )
                        message_data["email_error"] = (
                            f"API error: {response.status_code}"
                        )
            else:
                logger.warning("RESEND_API_KEY not configured - email not sent")
                message_data["email_error"] = "Email service not configured"
        except Exception as e:
            logger.error(
                f"Failed to send email notification to {partner.get('email')}: {e}"
            )
            message_data["email_error"] = str(e)

    # Send SMS notification (mock mode - logs for now)
    if send_sms and partner.get("phone"):
        try:
            phone = partner.get("phone", "")
            sms_content = f"[{store_name}] New message: {subject or 'Partner Program Update'}. Check your partner dashboard for details."

            # Log SMS attempt (mock mode)
            logger.info(
                f"SMS NOTIFICATION (Mock): To: {phone}, Message: {sms_content[:100]}..."
            )

            # Mark as sent (mock mode - in production, integrate with Twilio/SMS provider)
            message_data["sms_sent"] = True
            message_data["sms_mock"] = True  # Flag indicating this was mocked
            await db.partner_messages.update_one(
                {"id": message_data["id"]},
                {"$set": {"sms_sent": True, "sms_mock": True}},
            )

            logger.info(f"SMS logged for partner {partner.get('full_name')} at {phone}")
        except Exception as e:
            logger.error(f"Failed to process SMS notification: {e}")
            message_data["sms_error"] = str(e)

    return {
        "message": "Message sent successfully",
        "message_id": message_data["id"],
        "email_sent": message_data.get("email_sent", False),
        "sms_sent": message_data.get("sms_sent", False),
        "email_error": message_data.get("email_error"),
        "sms_error": message_data.get("sms_error"),
    }


@router.get("/admin/partner-messages/{partner_id}")
async def get_partner_messages_admin(partner_id: str, request: Request):
    """Admin - get all messages for a specific partner"""
    await require_admin(request)

    messages = (
        await db.partner_messages.find({"partner_id": partner_id}, {"_id": 0})
        .sort("sent_at", -1)
        .to_list(100)
    )

    return {"messages": messages}


@router.get("/partner-messages/{partner_code}")
async def get_partner_messages(partner_code: str, request: Request):
    """Partner - get their messages (requires auth)"""
    # Verify the logged-in user is this partner
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_email = payload.get("email", "").lower()
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Find partner by code and verify email matches
    partner = await db.influencer_applications.find_one(
        {"partner_code": {"$regex": f"^{partner_code}$", "$options": "i"}}, {"_id": 0}
    )

    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    if partner.get("email", "").lower() != user_email:
        raise HTTPException(status_code=403, detail="Access denied")

    messages = (
        await db.partner_messages.find({"partner_id": partner["id"]}, {"_id": 0})
        .sort("sent_at", -1)
        .to_list(100)
    )

    # Mark unread messages as read and notify admin
    unread_ids = [m["id"] for m in messages if not m.get("read")]
    if unread_ids:
        read_time = datetime.now(timezone.utc).isoformat()
        await db.partner_messages.update_many(
            {"id": {"$in": unread_ids}}, {"$set": {"read": True, "read_at": read_time}}
        )

        # Create admin notification for each read message
        for msg in messages:
            if msg["id"] in unread_ids:
                notification = {
                    "id": str(uuid.uuid4()),
                    "type": "message_read",
                    "title": f"Message Read by {partner.get('full_name', 'Partner')}",
                    "message": f"{partner.get('full_name', partner.get('email', 'Partner'))} has viewed your message: \"{msg.get('subject', 'No subject')[:50]}\"",
                    "partner_id": partner["id"],
                    "partner_name": partner.get("full_name", partner.get("email", "")),
                    "message_id": msg["id"],
                    "created_at": read_time,
                    "read": False,
                }
                await db.admin_notifications.insert_one(notification)

    return {"messages": messages, "partner": partner}



@router.post("/admin/maintenance-mode")
async def toggle_maintenance_mode(data: dict, request: Request):
    """Toggle maintenance mode for the store"""
    await require_admin(request)
    
    enabled = data.get("enabled", False)
    
    # Update store settings with maintenance mode
    await db.store_settings.update_one(
        {},
        {"$set": {"maintenance_mode": enabled, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    
    return {"maintenance_mode": enabled, "message": f"Maintenance mode {'enabled' if enabled else 'disabled'}"}



@router.get("/admin/notifications")
async def get_admin_notifications(request: Request):
    """Get admin notifications including message read receipts"""
    await require_admin(request)

    notifications = (
        await db.admin_notifications.find({}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(100)
    )

    unread_count = await db.admin_notifications.count_documents({"read": False})

    return {"notifications": notifications, "unread_count": unread_count}


@router.put("/admin/notifications/mark-read")
async def mark_notifications_read(request: Request, data: dict = None):
    """Mark notifications as read"""
    await require_admin(request)

    if data and data.get("notification_ids"):
        # Mark specific notifications as read
        await db.admin_notifications.update_many(
            {"id": {"$in": data["notification_ids"]}},
            {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}},
        )
    else:
        # Mark all as read
        await db.admin_notifications.update_many(
            {"read": False},
            {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}},
        )

    return {"message": "Notifications marked as read"}


@router.delete("/admin/notifications/{notification_id}")
async def delete_notification(notification_id: str, request: Request):
    """Delete a notification"""
    await require_admin(request)
    await db.admin_notifications.delete_one({"id": notification_id})
    return {"message": "Notification deleted"}


@router.get("/partner-messages-count/{partner_id}")
async def get_unread_count(partner_id: str):
    """Get unread message count for partner"""
    count = await db.partner_messages.count_documents(
        {"partner_id": partner_id, "read": False}
    )
    return {"unread_count": count}


# ============= INFLUENCER LIVE CHAT TO ADMIN =============


@router.post("/partner-chat/send")
async def partner_send_chat_message(data: dict, request: Request):
    """Partner/Influencer sends a chat message to admin"""
    partner_code = data.get("partner_code")
    message = data.get("message", "").strip()

    if not partner_code or not message:
        raise HTTPException(
            status_code=400, detail="partner_code and message are required"
        )

    # Get partner info
    partner = await db.influencer_applications.find_one(
        {"partner_code": partner_code, "status": "approved"},
        {"_id": 0, "id": 1, "full_name": 1, "email": 1, "partner_code": 1},
    )
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found or not approved")

    # Create chat message
    chat_message = {
        "id": str(uuid.uuid4()),
        "conversation_id": f"partner_{partner['id']}",
        "partner_id": partner["id"],
        "partner_code": partner_code,
        "partner_name": partner.get("full_name", "Partner"),
        "sender": "partner",
        "message": message,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "read_by_admin": False,
    }

    await db.partner_chats.insert_one(chat_message)

    # Increment admin notification count
    await db.admin_notifications.update_one(
        {"type": "partner_chat"},
        {
            "$inc": {"unread_count": 1},
            "$set": {"last_message_at": datetime.now(timezone.utc).isoformat()},
        },
        upsert=True,
    )

    return {"success": True, "message_id": chat_message["id"]}


@router.get("/partner-chat/{partner_code}")
async def get_partner_chat_history(partner_code: str, limit: int = 50):
    """Get chat history for a partner"""
    partner = await db.influencer_applications.find_one(
        {"partner_code": partner_code}, {"_id": 0, "id": 1}
    )
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    messages = (
        await db.partner_chats.find({"partner_id": partner["id"]}, {"_id": 0})
        .sort("sent_at", -1)
        .limit(limit)
        .to_list(length=limit)
    )

    return {"messages": list(reversed(messages))}


@router.get("/admin/partner-chats")
async def get_all_partner_chats(request: Request):
    """Admin - Get all active partner chat conversations with unread counts"""
    await require_admin(request)

    # Aggregate to get conversations with last message and unread count
    pipeline = [
        {"$sort": {"sent_at": -1}},
        {
            "$group": {
                "_id": "$partner_id",
                "partner_code": {"$first": "$partner_code"},
                "partner_name": {"$first": "$partner_name"},
                "last_message": {"$first": "$message"},
                "last_message_at": {"$first": "$sent_at"},
                "last_sender": {"$first": "$sender"},
                "unread_count": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$eq": ["$read_by_admin", False]},
                                    {"$eq": ["$sender", "partner"]},
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },
            }
        },
        {"$sort": {"last_message_at": -1}},
    ]

    conversations = await db.partner_chats.aggregate(pipeline).to_list(length=100)

    # Format response
    result = []
    for conv in conversations:
        result.append(
            {
                "partner_id": conv["_id"],
                "partner_code": conv.get("partner_code", ""),
                "partner_name": conv.get("partner_name", "Unknown"),
                "last_message": conv.get("last_message", "")[:100],
                "last_message_at": conv.get("last_message_at"),
                "last_sender": conv.get("last_sender", "partner"),
                "unread_count": conv.get("unread_count", 0),
            }
        )

    return {"conversations": result}


@router.get("/admin/partner-chat/{partner_id}")
async def get_admin_partner_chat(partner_id: str, request: Request, limit: int = 50):
    """Admin - Get chat history with specific partner"""
    await require_admin(request)

    messages = (
        await db.partner_chats.find({"partner_id": partner_id}, {"_id": 0})
        .sort("sent_at", -1)
        .limit(limit)
        .to_list(length=limit)
    )

    # Mark messages as read
    await db.partner_chats.update_many(
        {"partner_id": partner_id, "sender": "partner", "read_by_admin": False},
        {
            "$set": {
                "read_by_admin": True,
                "read_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    # Update notification count
    unread_total = await db.partner_chats.count_documents(
        {"sender": "partner", "read_by_admin": False}
    )
    await db.admin_notifications.update_one(
        {"type": "partner_chat"}, {"$set": {"unread_count": unread_total}}, upsert=True
    )

    # Get partner info
    partner = await db.influencer_applications.find_one(
        {"id": partner_id}, {"_id": 0, "full_name": 1, "email": 1, "partner_code": 1}
    )

    return {"messages": list(reversed(messages)), "partner": partner}


@router.post("/admin/partner-chat/send")
async def admin_send_chat_message(data: dict, request: Request):
    """Admin sends a chat message to partner"""
    user = await require_admin(request)

    partner_id = data.get("partner_id")
    message = data.get("message", "").strip()

    if not partner_id or not message:
        raise HTTPException(
            status_code=400, detail="partner_id and message are required"
        )

    # Get partner info
    partner = await db.influencer_applications.find_one({"id": partner_id}, {"_id": 0})
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    # Create chat message
    chat_message = {
        "id": str(uuid.uuid4()),
        "conversation_id": f"partner_{partner_id}",
        "partner_id": partner_id,
        "partner_code": partner.get("partner_code", ""),
        "partner_name": partner.get("full_name", "Partner"),
        "sender": "admin",
        "admin_name": user.get("name", "Admin"),
        "message": message,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "read_by_partner": False,
    }

    await db.partner_chats.insert_one(chat_message)

    return {"success": True, "message_id": chat_message["id"]}


@router.get("/admin/notifications/count")
async def get_admin_notification_count(request: Request):
    """Admin - Get total unread notification count"""
    await require_admin(request)

    # Count unread partner chat messages
    chat_count = await db.partner_chats.count_documents(
        {"sender": "partner", "read_by_admin": False}
    )

    # Count pending partner applications
    pending_partners = await db.influencer_applications.count_documents(
        {"status": "pending"}
    )

    # Count unread customer messages (if exists)
    customer_chat_count = (
        await db.customer_chats.count_documents({"read_by_admin": False})
        if await db.list_collection_names()
        and "customer_chats" in await db.list_collection_names()
        else 0
    )

    return {
        "total": chat_count + pending_partners,
        "partner_chats": chat_count,
        "pending_partners": pending_partners,
        "customer_chats": customer_chat_count,
    }


@router.post("/partner-chat/mark-read")
async def mark_partner_messages_read(data: dict):
    """Partner marks admin messages as read"""
    partner_code = data.get("partner_code")

    if not partner_code:
        raise HTTPException(status_code=400, detail="partner_code is required")

    partner = await db.influencer_applications.find_one(
        {"partner_code": partner_code}, {"_id": 0, "id": 1}
    )
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    await db.partner_chats.update_many(
        {"partner_id": partner["id"], "sender": "admin", "read_by_partner": False},
        {"$set": {"read_by_partner": True}},
    )

    return {"success": True}


@router.get("/partner-chat/unread-count/{partner_code}")
async def get_partner_unread_chat_count(partner_code: str):
    """Get unread message count for partner from admin"""
    partner = await db.influencer_applications.find_one(
        {"partner_code": partner_code}, {"_id": 0, "id": 1}
    )
    if not partner:
        return {"unread_count": 0}

    count = await db.partner_chats.count_documents(
        {"partner_id": partner["id"], "sender": "admin", "read_by_partner": False}
    )

    return {"unread_count": count}


@router.delete("/admin/partner-messages/{message_id}")
async def delete_partner_message(message_id: str, request: Request):
    """Admin - delete a message"""
    await require_admin(request)
    await db.partner_messages.delete_one({"id": message_id})
    return {"message": "Message deleted"}


# ============= PRESENCE / ONLINE STATUS TRACKING =============


@router.post("/presence/heartbeat")
async def update_presence(data: dict, request: Request):
    """Update user's online presence - called every 30 seconds"""
    user = await get_current_user(request)
    user_type = data.get("user_type", "user")  # "admin" or "partner"
    partner_code = data.get("partner_code")

    presence_data = {
        "last_active": datetime.now(timezone.utc).isoformat(),
        "is_online": True,
    }

    if user_type == "admin" and user and user.get("role") == "admin":
        await db.presence.update_one(
            {"type": "admin"}, {"$set": presence_data}, upsert=True
        )
    elif user_type == "partner" and partner_code:
        await db.presence.update_one(
            {"type": "partner", "partner_code": partner_code},
            {"$set": {**presence_data, "partner_code": partner_code}},
            upsert=True,
        )

    return {"success": True}


@router.get("/presence/status")
async def get_presence_status(partner_code: str = None):
    """Get online status - returns who is online"""
    # Consider someone offline if no heartbeat in last 60 seconds
    cutoff_time = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()

    # Get admin status
    admin_presence = await db.presence.find_one({"type": "admin"}, {"_id": 0})
    admin_online = False
    if admin_presence and admin_presence.get("last_active", "") > cutoff_time:
        admin_online = True

    # Get specific partner status if requested
    partner_online = False
    if partner_code:
        partner_presence = await db.presence.find_one(
            {"type": "partner", "partner_code": partner_code}, {"_id": 0}
        )
        if partner_presence and partner_presence.get("last_active", "") > cutoff_time:
            partner_online = True

    return {"admin_online": admin_online, "partner_online": partner_online}


@router.get("/admin/partners/online-status")
async def get_all_partners_online_status(request: Request):
    """Admin - Get online status of all partners"""
    await require_admin(request)

    cutoff_time = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()

    # Get all partner presence records
    partner_presences = await db.presence.find({"type": "partner"}, {"_id": 0}).to_list(
        1000
    )

    online_partners = {}
    for p in partner_presences:
        partner_code = p.get("partner_code")
        if partner_code:
            online_partners[partner_code] = p.get("last_active", "") > cutoff_time

    return {"online_partners": online_partners}


# ============= PARTNER REFERRAL PROGRAM ENDPOINTS =============


@router.post("/admin/partner-referrals")
async def create_partner_referral(data: dict, request: Request):
    """Admin - Create a referral program for a specific partner"""
    await require_admin(request)

    partner_id = data.get("partner_id")
    if not partner_id:
        raise HTTPException(status_code=400, detail="partner_id is required")

    # Check partner exists
    partner = await db.influencer_applications.find_one({"id": partner_id}, {"_id": 0})
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    # Generate unique referral code based on partner code
    base_code = partner.get("partner_code", f"PARTNER-{partner_id[:8]}")
    referral_code = f"REF-{base_code}"

    referral = {
        "id": str(uuid.uuid4()),
        "partner_id": partner_id,
        "partner_name": partner.get("full_name", "Partner"),
        "name": data.get("name", "Partner Referral Program"),
        "reward_discount_percent": data.get("reward_discount_percent", 15),
        "required_referrals": data.get("required_referrals", 3),
        "referral_action": data.get("referral_action", "signup"),  # signup or purchase
        "referral_code": referral_code,
        "referral_link": f"/shop?partner_ref={referral_code}",
        "is_active": True,
        "total_referrals": 0,
        "successful_referrals": 0,
        "rewards_earned": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.partner_referrals.insert_one(referral)

    return {
        "message": "Partner referral program created",
        "referral": {k: v for k, v in referral.items() if k != "_id"},
    }


@router.get("/admin/partner-referrals/{partner_id}")
async def get_partner_referrals(partner_id: str, request: Request):
    """Admin - Get all referral programs for a specific partner"""
    await require_admin(request)
    referrals = await db.partner_referrals.find(
        {"partner_id": partner_id}, {"_id": 0}
    ).to_list(100)
    return {"referrals": referrals}


@router.get("/admin/partner-referrals")
async def get_all_partner_referrals(request: Request):
    """Admin - Get all partner referral programs"""
    await require_admin(request)
    referrals = await db.partner_referrals.find({}, {"_id": 0}).to_list(1000)
    return {"referrals": referrals}


@router.put("/admin/partner-referrals/{referral_id}")
async def update_partner_referral(referral_id: str, data: dict, request: Request):
    """Admin - Update a partner referral program"""
    await require_admin(request)

    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}

    # Only update allowed fields
    for field in [
        "name",
        "reward_discount_percent",
        "required_referrals",
        "referral_action",
        "is_active",
    ]:
        if field in data:
            update_data[field] = data[field]

    await db.partner_referrals.update_one({"id": referral_id}, {"$set": update_data})

    return {"message": "Partner referral updated"}


@router.delete("/admin/partner-referrals/{referral_id}")
async def delete_partner_referral(referral_id: str, request: Request):
    """Admin - Delete a partner referral program"""
    await require_admin(request)
    result = await db.partner_referrals.delete_one({"id": referral_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Referral program not found")
    return {"message": "Partner referral program deleted"}


@router.get("/partner-referrals/{partner_code}")
async def get_partner_referrals_public(partner_code: str):
    """Public - Get active referral programs for a partner by their partner code"""
    # Find partner by code
    partner = await db.influencer_applications.find_one(
        {"partner_code": {"$regex": f"^{partner_code}$", "$options": "i"}},
        {"_id": 0, "id": 1},
    )
    if not partner:
        return {"referrals": []}

    referrals = await db.partner_referrals.find(
        {"partner_id": partner["id"], "is_active": True}, {"_id": 0}
    ).to_list(100)
    return {"referrals": referrals}


@router.post("/partner-referral/track")
async def track_partner_referral(data: dict, request: Request):
    """Track a referral action (signup or purchase) from a partner's referral link"""
    referral_code = data.get("referral_code")
    action = data.get("action", "signup")  # signup or purchase
    referred_user_id = data.get("user_id")

    if not referral_code:
        raise HTTPException(status_code=400, detail="referral_code is required")

    # Find the referral program
    referral = await db.partner_referrals.find_one(
        {"referral_code": referral_code, "is_active": True}
    )
    if not referral:
        return {"message": "Referral program not found or inactive"}

    # Check if action matches the required action
    if action != referral.get("referral_action", "signup"):
        return {"message": "Action type doesn't match referral requirements"}

    # Update referral stats
    update_fields = {
        "total_referrals": referral.get("total_referrals", 0) + 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Check if successful (met requirements)
    new_total = update_fields["total_referrals"]
    required = referral.get("required_referrals", 3)

    if new_total >= required:
        successful_batches = new_total // required
        update_fields["successful_referrals"] = successful_batches
        update_fields["rewards_earned"] = successful_batches

    await db.partner_referrals.update_one(
        {"id": referral["id"]}, {"$set": update_fields}
    )

    # Log the referral
    referral_log = {
        "id": str(uuid.uuid4()),
        "referral_program_id": referral["id"],
        "partner_id": referral["partner_id"],
        "referred_user_id": referred_user_id,
        "action": action,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.partner_referral_logs.insert_one(referral_log)

    return {
        "message": "Referral tracked successfully",
        "total_referrals": update_fields["total_referrals"],
    }


# ============= PARTNER COMMISSIONS TRACKING =============

@router.get("/admin/partners/commissions")
async def get_partner_commissions(request: Request, status: str = None, limit: int = 50):
    """Admin - View all partner commissions with totals"""
    await require_admin(request)
    
    # Build query filter
    query = {}
    if status and status != "all":
        query["status"] = status
    
    # Get commissions from partner_commissions collection
    commissions = await db.partner_commissions.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Calculate totals
    all_commissions = await db.partner_commissions.find({}, {"commission": 1, "status": 1}).to_list(None)
    total_pending = sum(c.get("commission", 0) for c in all_commissions if c.get("status") == "pending")
    total_paid = sum(c.get("commission", 0) for c in all_commissions if c.get("status") == "paid")
    total_all = sum(c.get("commission", 0) for c in all_commissions)
    
    return {
        "commissions": commissions,
        "total_pending": round(total_pending, 2),
        "total_paid": round(total_paid, 2),
        "total_all": round(total_all, 2),
        "count": len(commissions)
    }


@router.put("/admin/partners/commissions/{commission_id}/pay")
async def mark_commission_paid(commission_id: str, request: Request):
    """Admin - Mark a commission as paid"""
    await require_admin(request)
    
    result = await db.partner_commissions.update_one(
        {"id": commission_id},
        {"$set": {
            "status": "paid",
            "paid_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Commission not found")
    
    return {"message": "Commission marked as paid"}


# ============= EMAIL AUTOMATION TEST ENDPOINT =============

@router.post("/admin/automations/test-email")
async def test_automation_email(request: Request):
    """Admin - Test email sending via SendGrid"""
    await require_admin(request)
    
    body = await request.json()
    to_email = body.get("to")
    template = body.get("template", "order_confirmation")
    
    if not to_email:
        raise HTTPException(status_code=400, detail="'to' email address is required")
    
    try:
        from routes.reroots_p0_fixes import sendgrid_send_email
        
        # Get test HTML based on template
        test_htmls = {
            "order_confirmation": """
                <div style="font-family: Georgia, serif; max-width: 480px; margin: 0 auto; padding: 40px 20px;">
                    <h1 style="text-align: center; color: #2D2A2E;">ReRoots Test Email</h1>
                    <p style="text-align: center; color: #666;">This is a test email from the automation system.</p>
                    <p style="text-align: center; color: #F8A5B8; font-weight: bold;">If you received this, SendGrid is working! ✓</p>
                </div>
            """,
            "shipping": """
                <div style="font-family: Georgia, serif; max-width: 480px; margin: 0 auto; padding: 40px 20px;">
                    <h1 style="text-align: center; color: #2D2A2E;">Shipping Test</h1>
                    <p style="text-align: center; color: #666;">Your test order has shipped!</p>
                    <p style="text-align: center;">Tracking: TEST-123456</p>
                </div>
            """,
            "welcome": """
                <div style="font-family: Georgia, serif; max-width: 480px; margin: 0 auto; padding: 40px 20px;">
                    <h1 style="text-align: center; color: #2D2A2E;">Welcome to ReRoots</h1>
                    <p style="text-align: center; color: #666;">Thank you for joining our community!</p>
                </div>
            """
        }
        
        html_body = test_htmls.get(template, test_htmls["order_confirmation"])
        subject = f"ReRoots Test: {template.replace('_', ' ').title()}"
        
        result = await sendgrid_send_email(
            to=to_email,
            subject=subject,
            html_body=html_body
        )
        
        return {
            "sent": result,
            "to": to_email,
            "template": template,
            "message": "Email sent successfully" if result else "Email sending failed"
        }
        
    except Exception as e:
        logging.error(f"Test email failed: {e}")
        return {
            "sent": False,
            "error": str(e),
            "message": "Check SENDGRID_API_KEY is set correctly"
        }


@router.get("/partner/my-status")
async def get_my_partner_status(request: Request):
    """Partner - Get their partnership status including expiry"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")

    # Find partner by email
    partner = await db.influencer_applications.find_one(
        {
            "email": user.get("email", "").lower(),
            "status": {"$in": ["approved", "active"]},
        },
        {"_id": 0},
    )

    if not partner:
        return {"is_partner": False}

    # Check if partnership has expired
    expires_at = partner.get("partnership_expires_at")
    is_expired = False
    days_until_expiry = None

    if expires_at:
        expiry_date = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        is_expired = now > expiry_date
        days_until_expiry = (expiry_date - now).days if not is_expired else 0

    return {
        "is_partner": True,
        "partner_id": partner.get("id"),
        "partner_code": partner.get("partner_code"),
        "full_name": partner.get("full_name"),
        "status": partner.get("status"),
        "partnership_start_date": partner.get("partnership_start_date"),
        "partnership_expires_at": expires_at,
        "is_expired": is_expired,
        "days_until_expiry": days_until_expiry,
        "partnership_active": partner.get("partnership_active", True)
        and not is_expired,
        "renewal_requested": partner.get("renewal_requested", False),
        "renewal_requested_at": partner.get("renewal_requested_at"),
        "custom_discount": partner.get("custom_discount"),
        "custom_commission": partner.get("custom_commission"),
        "total_clicks": partner.get("total_clicks", 0),
        "total_orders": partner.get("total_orders", 0),
        "total_revenue": partner.get("total_revenue", 0),
        "total_commission": partner.get("total_commission", 0),
    }


@router.post("/partner/request-renewal")
async def request_partnership_renewal(request: Request):
    """Partner - Request renewal of their partnership"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")

    # Find partner by email
    partner = await db.influencer_applications.find_one(
        {
            "email": user.get("email", "").lower(),
            "status": {"$in": ["approved", "active"]},
        },
        {"_id": 0},
    )

    if not partner:
        raise HTTPException(status_code=404, detail="Partner account not found")

    # Check if already requested
    if partner.get("renewal_requested"):
        return {
            "message": "Renewal already requested. Please wait for admin approval.",
            "already_requested": True,
        }

    # Update to request renewal
    await db.influencer_applications.update_one(
        {"id": partner["id"]},
        {
            "$set": {
                "renewal_requested": True,
                "renewal_requested_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    return {
        "message": "Renewal request submitted successfully! Admin will review your request.",
        "success": True,
    }


@router.put("/admin/partner/{partner_id}/renew")
async def admin_renew_partnership(partner_id: str, data: dict, request: Request):
    """Admin - Renew a partner's partnership for another year"""
    await require_admin(request)

    partner = await db.influencer_applications.find_one({"id": partner_id})
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    # Calculate new expiry (1 year from now or from current expiry if not expired)
    current_expiry = partner.get("partnership_expires_at")
    now = datetime.now(timezone.utc)

    if current_expiry:
        expiry_date = datetime.fromisoformat(current_expiry.replace("Z", "+00:00"))
        # If not expired yet, extend from current expiry; if expired, extend from now
        if expiry_date > now:
            new_expiry = expiry_date + timedelta(days=365)
        else:
            new_expiry = now + timedelta(days=365)
    else:
        new_expiry = now + timedelta(days=365)

    # Renew partnership
    await db.influencer_applications.update_one(
        {"id": partner_id},
        {
            "$set": {
                "partnership_expires_at": new_expiry.isoformat(),
                "partnership_active": True,
                "renewal_requested": False,
                "renewal_requested_at": None,
                "last_renewed_at": now.isoformat(),
                "renewed_by": (await get_current_user(request))["id"],
            }
        },
    )

    return {
        "message": f"Partnership renewed until {new_expiry.strftime('%B %d, %Y')}",
        "new_expiry": new_expiry.isoformat(),
    }


@router.get("/admin/partners/renewal-requests")
async def get_renewal_requests(request: Request):
    """Admin - Get all partners who have requested renewal"""
    await require_admin(request)

    partners = await db.influencer_applications.find(
        {"renewal_requested": True}, {"_id": 0}
    ).to_list(100)

    return {"partners": partners}


@router.get("/admin/partners/expired")
async def get_expired_partners(request: Request):
    """Admin - Get all partners with expired partnerships"""
    await require_admin(request)

    now = datetime.now(timezone.utc).isoformat()
    partners = await db.influencer_applications.find(
        {
            "status": {"$in": ["approved", "active"]},
            "partnership_expires_at": {"$lt": now},
        },
        {"_id": 0},
    ).to_list(100)

    return {"partners": partners}


# ============= REFERRAL PROGRAM ENDPOINTS =============


@router.get("/referral-program")
async def get_referral_program():
    """Public - get referral program settings for widget"""
    settings = await db.store_settings.find_one({"id": "store_settings"}, {"_id": 0})
    if not settings:
        settings = StoreSettings().model_dump()

    referral = settings.get("referral_program", {})

    return {
        "enabled": referral.get("enabled", True),
        "widget": {
            "enabled": referral.get("widget_enabled", True),
            "position": referral.get("widget_position", "bottom-right"),
            "button_text": referral.get("widget_button_text", "Get ReRoots FREE"),
            "button_color": referral.get("widget_button_color", "#D4AF37"),
            "popup_title": referral.get("widget_popup_title", "Share the Glow ✨"),
            "popup_subtitle": referral.get(
                "widget_popup_subtitle", "Invite friends & earn rewards"
            ),
            "share_message": referral.get(
                "widget_share_message",
                "I love ReRoots skincare! Use my link for $10 off:",
            ),
        },
        "rewards": {
            "referrer": referral.get("referrer_reward_label", "$10 Store Credit"),
            "referee": referral.get("referee_reward_label", "$10 Off Your First Order"),
            "milestones": referral.get("milestones", []),
        },
    }


@router.post("/referral/create")
async def create_referral(data: dict, request: Request):
    """Create a referral - user shares their link"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required to refer friends")

    # Generate unique referral code for user if they don't have one
    existing = await db.referral_codes.find_one({"user_id": user["id"]})
    if existing:
        return {
            "referral_code": existing["code"],
            "referral_link": f"/ref/{existing['code']}",
        }

    # Generate code
    name_part = user.get("name", "FRIEND").upper()[:6]
    code = f"REF-{name_part}-{random.randint(1000, 9999)}"

    await db.referral_codes.insert_one(
        {
            "user_id": user["id"],
            "user_email": user["email"],
            "code": code,
            "total_referrals": 0,
            "successful_referrals": 0,
            "total_earned": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    return {"referral_code": code, "referral_link": f"/ref/{code}"}


# ============= FOUNDING MEMBER REFERRAL SYSTEM (with Anti-Cheat) =============


@router.post("/waitlist")
async def join_waitlist(data: dict, request: Request):
    """Join the Founding Member waitlist with anti-cheat protection"""
    email = data.get("email", "").lower().strip()
    name = data.get("name", "").strip()
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    phone = data.get("phone", "").strip()
    phone_country_code = data.get("phone_country_code", "+1")
    referrer_code = data.get("referrer_code", data.get("ref", "")).upper().strip()
    source = data.get("source", "direct")

    # Enhanced UTM tracking for Reddit and other platforms
    utm_source = data.get("utm_source", "")
    utm_medium = data.get("utm_medium", "")  # e.g., "SkincareAddiction", "CanSkincare"
    utm_campaign = data.get("utm_campaign", "")
    utm_content = data.get("utm_content", "")

    # Auto-detect Reddit source
    if utm_source.lower() == "reddit" or "reddit" in source.lower():
        source = f"reddit:{utm_medium}" if utm_medium else "reddit"

    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    # Basic email validation
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(
            status_code=400, detail="Please enter a valid email address"
        )

    # ANTI-CHEAT: Get client IP
    client_ip = request.client.host
    forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if forwarded_for:
        client_ip = forwarded_for

    # ANTI-CHEAT: Check for recent signups from same IP (rate limiting)
    recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    recent_signups_from_ip = await db.waitlist.count_documents(
        {"ip_address": client_ip, "created_at": {"$gte": recent_cutoff.isoformat()}}
    )

    if recent_signups_from_ip >= 3:
        raise HTTPException(
            status_code=429,
            detail="Too many signups from this location. Please try again later.",
        )

    # Check if email already exists
    existing = await db.waitlist.find_one({"email": email})
    if existing:
        # Calculate their position (count of entries created before them)
        existing_position = await db.waitlist.count_documents(
            {
                "created_at": {
                    "$lte": existing.get(
                        "created_at", datetime.now(timezone.utc).isoformat()
                    )
                }
            }
        )
        # Return existing user's referral code
        return {
            "success": True,
            "message": "You're already on the waitlist!",
            "referral_code": existing.get("referral_code"),
            "position": existing_position,
            "already_registered": True,
        }

    # Generate unique referral code for the new user
    code_base = name.upper()[:4] if name else "USER"
    referral_code = f"FM-{code_base}-{random.randint(10000, 99999)}"

    # Create verification token
    verification_token = secrets.token_urlsafe(32)

    # Create waitlist entry
    waitlist_entry = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": name,
        "first_name": first_name,
        "last_name": last_name,
        "phone": phone if phone else None,
        "phone_country_code": phone_country_code,
        "referral_code": referral_code,
        "referred_by": referrer_code if referrer_code else None,
        "referral_count": 0,
        "verified_referrals": 0,
        "email_verified": False,
        "verification_token": verification_token,
        "ip_address": client_ip,
        "user_agent": request.headers.get("User-Agent", "")[:200],
        "source": source,
        "utm_data": (
            {
                "source": utm_source,
                "medium": utm_medium,
                "campaign": utm_campaign,
                "content": utm_content,
            }
            if utm_source
            else None
        ),
        "voucher_unlocked": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.waitlist.insert_one(waitlist_entry)
    
    # Broadcast new waitlist signup event to admin WebSocket connections
    await broadcast_admin_event("new_waitlist_signup", {
        "id": waitlist_entry["id"],
        "email": email,
        "name": name or f"{first_name} {last_name}".strip(),
        "referred_by": referrer_code or None,
        "source": source
    })

    # Calculate position in line (total entries before this one + 1)
    position_in_line = await db.waitlist.count_documents({})

    # If referred by someone, create referral record (pending verification)
    if referrer_code:
        referrer = await db.waitlist.find_one({"referral_code": referrer_code})
        if referrer:
            await db.founding_member_referrals.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "referrer_email": referrer["email"],
                    "referrer_code": referrer_code,
                    "referee_email": email,
                    "referee_name": name,
                    "verified": False,
                    "verification_token": verification_token,
                    "ip_address": client_ip,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

    # Store referral code in response for redirect
    logger.info(
        f"New waitlist signup: {email} (referred by {referrer_code or 'direct'})"
    )

    return {
        "success": True,
        "message": "Welcome to the Founding Member program!",
        "referral_code": referral_code,
        "position": position_in_line,
        "verification_required": True,
        "redirect_to": f"/mission-control?code={referral_code}",
    }


@router.get("/waitlist/verify/{token}")
async def verify_waitlist_email(token: str):
    """Verify waitlist email - referral only counts after verification"""
    # Find the waitlist entry with this verification token
    user = await db.waitlist.find_one({"verification_token": token})
    if not user:
        raise HTTPException(status_code=404, detail="Invalid verification link")

    if user.get("email_verified"):
        return {
            "success": True,
            "message": "Email already verified",
            "referral_code": user["referral_code"],
        }

    # Mark as verified
    await db.waitlist.update_one(
        {"verification_token": token},
        {
            "$set": {
                "email_verified": True,
                "verified_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )

    # If this user was referred, mark the referral as verified
    if user.get("referred_by"):
        await db.founding_member_referrals.update_one(
            {"referee_email": user["email"], "verified": False},
            {
                "$set": {
                    "verified": True,
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )

        # Update referrer's count
        await db.waitlist.update_one(
            {"referral_code": user["referred_by"]}, {"$inc": {"verified_referrals": 1}}
        )

        # Check if referrer just hit 10 referrals
        referrer = await db.waitlist.find_one({"referral_code": user["referred_by"]})
        if referrer and referrer.get("verified_referrals", 0) >= 10:
            # Check if voucher wasn't already unlocked (first time hitting 10)
            was_already_unlocked = referrer.get("voucher_unlocked", False)

            await db.waitlist.update_one(
                {"referral_code": user["referred_by"]},
                {
                    "$set": {
                        "voucher_unlocked": True,
                        "voucher_unlocked_at": datetime.now(timezone.utc).isoformat(),
                    }
                },
            )

            # Send congratulations email only if this is the first time unlocking
            if not was_already_unlocked:
                referrer_email = referrer.get("email")
                referrer_name = referrer.get("name", "Founding Member")
                if referrer_email:
                    # Fire and forget - don't block the response
                    asyncio.create_task(
                        send_goal_achieved_email(referrer_email, referrer_name)
                    )
                    logger.info(
                        f"🏆 Goal achieved! Voucher unlocked for {referrer_email} - sending congratulations email"
                    )

    return {
        "success": True,
        "message": "Email verified! Your referral has been counted.",
        "referral_code": user["referral_code"],
        "redirect_to": f"/mission-control?code={user['referral_code']}",
    }


@router.get("/referral/status/{code}")
async def get_referral_status(code: str):
    """Get referral status for Mission Control page"""
    # Look up in waitlist first
    user = await db.waitlist.find_one({"referral_code": code.upper()}, {"_id": 0})

    if not user:
        # Try old referral_codes collection
        old_user = await db.referral_codes.find_one({"code": code.upper()}, {"_id": 0})
        if not old_user:
            raise HTTPException(status_code=404, detail="Referral code not found")
        user = old_user

    # Get all referrals for this user
    referrals = await db.founding_member_referrals.find(
        {"referrer_code": code.upper()},
        {"_id": 0, "referee_email": 1, "verified": 1, "created_at": 1},
    ).to_list(100)

    verified_count = len([r for r in referrals if r.get("verified")])

    # Get spots remaining (could be from settings or calculated)
    store_settings = await db.store_settings.find_one(
        {"id": "store_settings"}, {"_id": 0}
    )
    total_kits = (
        store_settings.get("founding_member_total_kits", 1000)
        if store_settings
        else 1000
    )
    claimed_kits = await db.waitlist.count_documents({"voucher_unlocked": True})
    spots_remaining = max(0, total_kits - claimed_kits)

    return {
        "email": user.get("email", ""),
        "name": user.get("name", ""),
        "referral_code": code.upper(),
        "referral_count": verified_count,
        "total_signups": len(referrals),
        "verified_referrals": verified_count,
        "voucher_unlocked": verified_count >= 10 or user.get("voucher_unlocked", False),
        "email_verified": user.get("email_verified", False),
        "referrals": referrals,
        "spots_remaining": spots_remaining,
        "voucher_gate_threshold": 10,
        "pricing": {
            "retail": 100.0,
            "base_price": 100.0,
            "unlocked_price": 70.00,  # FIXED: $70 Founding Member price (30% off)
            "current_price": 70.00 if verified_count >= 10 else 100.0,
        },
    }


@router.get("/referral/leaderboard")
async def get_referral_leaderboard():
    """Get top referrers for leaderboard display"""
    try:
        # Aggregate referral counts from founding_member_referrals
        pipeline = [
            {"$match": {"verified": True}},
            {"$group": {"_id": "$referrer_code", "referral_count": {"$sum": 1}}},
            {"$sort": {"referral_count": -1}},
            {"$limit": 20},
        ]

        top_referrers = await db.founding_member_referrals.aggregate(pipeline).to_list(
            20
        )

        # Enrich with user names from waitlist
        leaderboard = []
        for entry in top_referrers:
            user = await db.waitlist.find_one(
                {"referral_code": entry["_id"]},
                {"_id": 0, "name": 1, "email": 1, "voucher_unlocked": 1},
            )

            # Mask name for privacy (show first name + last initial)
            name = "Member"
            if user and user.get("name"):
                name_parts = user["name"].split()
                if len(name_parts) >= 2:
                    name = f"{name_parts[0]} {name_parts[-1][0]}."
                else:
                    name = name_parts[0]

            leaderboard.append(
                {
                    "name": name,
                    "referral_code": entry["_id"],
                    "referral_count": entry["referral_count"],
                    "voucher_unlocked": (
                        user.get("voucher_unlocked", False)
                        if user
                        else entry["referral_count"] >= 10
                    ),
                }
            )

        # Get total unique referrers
        total_referrers = await db.founding_member_referrals.distinct("referrer_code")

        return {
            "leaderboard": leaderboard,
            "total_referrers": len(total_referrers),
            "updated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        print(f"Leaderboard error: {e}")
        return {"leaderboard": [], "total_referrers": 0, "error": str(e)}


@router.post("/referral/invite")
async def send_referral_invite(data: dict, request: Request):
    """Send referral invites via email"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")

    emails = data.get("emails", [])
    if not emails:
        raise HTTPException(status_code=400, detail="No emails provided")

    # Get user's referral code
    ref_data = await db.referral_codes.find_one({"user_id": user["id"]})
    if not ref_data:
        raise HTTPException(
            status_code=400, detail="Please generate your referral code first"
        )

    # Create referral records
    for email in emails[:10]:  # Max 10 at a time
        existing = await db.referrals.find_one(
            {"referrer_id": user["id"], "referee_email": email.lower()}
        )
        if not existing:
            await db.referrals.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "referrer_id": user["id"],
                    "referrer_email": user["email"],
                    "referee_email": email.lower(),
                    "referral_code": ref_data["code"],
                    "status": "pending",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

    return {"message": f"Invitations sent to {len(emails)} friends!"}


@router.get("/referral/stats")
async def get_referral_stats(request: Request):
    """Get user's referral stats"""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")

    ref_data = await db.referral_codes.find_one({"user_id": user["id"]}, {"_id": 0})
    referrals = await db.referrals.find(
        {"referrer_id": user["id"]}, {"_id": 0}
    ).to_list(100)

    return {
        "code": ref_data.get("code") if ref_data else None,
        "total_referrals": ref_data.get("total_referrals", 0) if ref_data else 0,
        "successful": ref_data.get("successful_referrals", 0) if ref_data else 0,
        "total_earned": ref_data.get("total_earned", 0.0) if ref_data else 0.0,
        "referrals": referrals,
    }


