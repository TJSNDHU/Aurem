"""
Blog CMS, content management
Extracted from server.py during modularization.
"""

import os
try:
    import resend
except ImportError:
    resend = None
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
try:
    from models.server_models import (
        BlogPostCreate, BlogPostUpdate, UserBase, UserCreate, UserLogin,
        CartItem, Cart, ComboCartRequest, ShippingCalculatorRequest,
        SUPPORTED_CURRENCIES, COUNTRY_TO_CURRENCY
    )
except ImportError:
    pass
try:
    from services.email_templates import (
        get_email_base_styles, generate_email_action_token, verify_email_action_token
    )
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Environment variables
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', 'noreply@aurem.live')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')


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

# ============ BLOG / CONTENT MANAGEMENT SYSTEM ============


class BlogPostCreate(BaseModel):
    """Schema for creating a blog post"""

    title: str
    slug: Optional[str] = None
    content: str
    excerpt: Optional[str] = None
    featured_image: Optional[str] = None
    category: Optional[str] = "General"
    tags: List[str] = Field(default_factory=list)
    status: str = "draft"  # draft, published, scheduled
    published_at: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    author_name: Optional[str] = "ReRoots Team"
    # Enhanced SEO fields
    focus_keyword: Optional[str] = None
    schema_type: Optional[str] = "Article"
    # Shoppable content
    featured_products: List[dict] = Field(default_factory=list)
    # Scientific citations
    references: List[dict] = Field(default_factory=list)


class BlogPostUpdate(BaseModel):
    """Schema for updating a blog post"""

    title: Optional[str] = None
    slug: Optional[str] = None
    content: Optional[str] = None
    excerpt: Optional[str] = None
    featured_image: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    published_at: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    author_name: Optional[str] = None
    # Enhanced SEO fields
    focus_keyword: Optional[str] = None
    schema_type: Optional[str] = None
    # Shoppable content
    featured_products: Optional[List[dict]] = None
    # Scientific citations
    references: Optional[List[dict]] = None


def generate_blog_slug(title: str) -> str:
    """Generate URL-friendly slug from title"""
    slug = title.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug


@router.get("/blog/posts")
async def get_blog_posts(
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 20,
    skip: int = 0,
):
    """Get all blog posts (public endpoint for published, admin for all)"""
    query = {}

    # If status filter provided
    if status:
        query["status"] = status
    else:
        # Default: only show published posts for public
        query["status"] = "published"

    posts = (
        await db.blog_posts.find(query, {"_id": 0})
        .sort("published_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )

    total = await db.blog_posts.count_documents(query)

    return {"posts": posts, "total": total, "has_more": skip + limit < total}


@router.get("/blog/posts/{slug}")
async def get_blog_post_by_slug(slug: str):
    """Get a single blog post by slug (public)"""
    post = await db.blog_posts.find_one(
        {"slug": slug, "status": "published"}, {"_id": 0}
    )

    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")

    # Increment view count
    await db.blog_posts.update_one({"slug": slug}, {"$inc": {"views": 1}})

    return post


@router.get("/admin/blog/posts")
async def admin_get_all_blog_posts(
    status: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    current_user: dict = Depends(get_current_user),
):
    """Admin endpoint to get all blog posts including drafts"""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    query = {}
    if status and status != "all":
        query["status"] = status

    posts = (
        await db.blog_posts.find(query, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )
    total = await db.blog_posts.count_documents(query)

    # Get category counts
    pipeline = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}]
    category_counts = await db.blog_posts.aggregate(pipeline).to_list(100)

    return {
        "posts": posts,
        "total": total,
        "categories": {
            item["_id"]: item["count"] for item in category_counts if item["_id"]
        },
    }


@router.post("/admin/blog/posts")
async def create_blog_post(
    post_data: BlogPostCreate, current_user: dict = Depends(get_current_user)
):
    """Create a new blog post"""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Generate slug if not provided
    slug = post_data.slug or generate_blog_slug(post_data.title)

    # Check for existing slug
    existing = await db.blog_posts.find_one({"slug": slug})
    if existing:
        # Add unique suffix
        slug = f"{slug}-{str(uuid.uuid4())[:8]}"

    # Generate excerpt if not provided
    excerpt = post_data.excerpt
    if not excerpt and post_data.content:
        # Strip HTML and take first 160 chars
        plain_text = re.sub(r"<[^>]+>", "", post_data.content)
        excerpt = plain_text[:160] + "..." if len(plain_text) > 160 else plain_text

    now = datetime.now(timezone.utc).isoformat()

    post = {
        "id": str(uuid.uuid4()),
        "title": post_data.title,
        "slug": slug,
        "content": post_data.content,
        "excerpt": excerpt,
        "featured_image": post_data.featured_image,
        "category": post_data.category or "General",
        "tags": post_data.tags or [],
        "status": post_data.status,
        "published_at": (
            post_data.published_at if post_data.status == "published" else None
        ),
        "meta_title": post_data.meta_title or post_data.title,
        "meta_description": post_data.meta_description or excerpt,
        "author_name": post_data.author_name
        or current_user.get("name", "ReRoots Team"),
        "author_id": current_user.get("id"),
        "views": 0,
        # Enhanced SEO
        "focus_keyword": post_data.focus_keyword,
        "schema_type": post_data.schema_type or "Article",
        # Shoppable content
        "featured_products": post_data.featured_products or [],
        # Scientific citations
        "references": post_data.references or [],
        "created_at": now,
        "updated_at": now,
    }

    # If publishing, set published_at
    if post_data.status == "published" and not post["published_at"]:
        post["published_at"] = now

    await db.blog_posts.insert_one(post)

    # Return without _id
    post.pop("_id", None)

    return {"success": True, "post": post}


@router.put("/admin/blog/posts/{post_id}")
async def update_blog_post(
    post_id: str,
    post_data: BlogPostUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update an existing blog post"""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    existing = await db.blog_posts.find_one({"id": post_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Blog post not found")

    update_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}

    if post_data.title is not None:
        update_fields["title"] = post_data.title
        # Update slug if title changed and no custom slug provided
        if post_data.slug is None:
            update_fields["slug"] = generate_blog_slug(post_data.title)

    if post_data.slug is not None:
        update_fields["slug"] = post_data.slug

    if post_data.content is not None:
        update_fields["content"] = post_data.content
        # Update excerpt if content changed and no custom excerpt
        if post_data.excerpt is None:
            plain_text = re.sub(r"<[^>]+>", "", post_data.content)
            update_fields["excerpt"] = (
                plain_text[:160] + "..." if len(plain_text) > 160 else plain_text
            )

    if post_data.excerpt is not None:
        update_fields["excerpt"] = post_data.excerpt

    if post_data.featured_image is not None:
        update_fields["featured_image"] = post_data.featured_image

    if post_data.category is not None:
        update_fields["category"] = post_data.category

    if post_data.tags is not None:
        update_fields["tags"] = post_data.tags

    if post_data.status is not None:
        update_fields["status"] = post_data.status
        # Set published_at when publishing
        if post_data.status == "published" and not existing.get("published_at"):
            update_fields["published_at"] = datetime.now(timezone.utc).isoformat()

    if post_data.published_at is not None:
        update_fields["published_at"] = post_data.published_at

    if post_data.meta_title is not None:
        update_fields["meta_title"] = post_data.meta_title

    if post_data.meta_description is not None:
        update_fields["meta_description"] = post_data.meta_description

    if post_data.author_name is not None:
        update_fields["author_name"] = post_data.author_name

    # Enhanced SEO fields
    if post_data.focus_keyword is not None:
        update_fields["focus_keyword"] = post_data.focus_keyword

    if post_data.schema_type is not None:
        update_fields["schema_type"] = post_data.schema_type

    # Shoppable content
    if post_data.featured_products is not None:
        update_fields["featured_products"] = post_data.featured_products

    # Scientific citations
    if post_data.references is not None:
        update_fields["references"] = post_data.references

    await db.blog_posts.update_one({"id": post_id}, {"$set": update_fields})

    updated = await db.blog_posts.find_one({"id": post_id}, {"_id": 0})

    return {"success": True, "post": updated}


@router.delete("/admin/blog/posts/{post_id}")
async def delete_blog_post(
    post_id: str, current_user: dict = Depends(get_current_user)
):
    """Delete a blog post"""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await db.blog_posts.delete_one({"id": post_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Blog post not found")

    return {"success": True, "message": "Blog post deleted"}


@router.get("/blog/categories")
async def get_blog_categories():
    """Get all blog categories with post counts"""
    pipeline = [
        {"$match": {"status": "published"}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]

    results = await db.blog_posts.aggregate(pipeline).to_list(50)

    categories = [
        {"name": item["_id"], "count": item["count"]} for item in results if item["_id"]
    ]

    return {"categories": categories}


@router.get("/blog/tags")
async def get_blog_tags():
    """Get all unique tags from published posts"""
    pipeline = [
        {"$match": {"status": "published"}},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 30},
    ]

    results = await db.blog_posts.aggregate(pipeline).to_list(30)

    tags = [{"name": item["_id"], "count": item["count"]} for item in results]

    return {"tags": tags}


# ============ END BLOG SYSTEM ============


# ============ PARTNER DASHBOARD API ============


@router.post("/partner/verify")
async def verify_partner(data: dict):
    """Verify partner credentials and return dashboard data"""
    email = data.get("email", "").lower().strip()
    code = data.get("code", "").upper().strip()

    if not email or not code:
        raise HTTPException(status_code=400, detail="Email and partner code required")

    # Look for partner in multiple collections
    # First check influencer applications
    partner = await db.influencer_applications.find_one(
        {"email": email, "status": "approved"}, {"_id": 0}
    )

    if not partner:
        # Check partner applications
        partner = await db.partner_applications.find_one(
            {"email": email, "status": "approved"}, {"_id": 0}
        )

    if not partner:
        # Check waitlist founding members
        partner = await db.waitlist.find_one(
            {"email": email, "referral_code": code}, {"_id": 0}
        )

    if not partner:
        return {"valid": False, "message": "Invalid credentials"}

    # Verify code matches
    partner_code = (
        partner.get("referral_code")
        or partner.get("partner_code")
        or partner.get("code")
    )
    if partner_code and partner_code.upper() != code:
        return {"valid": False, "message": "Invalid partner code"}

    # Get partner stats
    referral_code = partner_code or code

    # Count clicks (from referral_tracks)
    clicks = await db.referral_tracks.count_documents({"referrer_code": referral_code})

    # Count signups (from bio_scans or waitlist)
    signups = await db.bio_scans.count_documents({"referred_by": referral_code})
    signups += await db.waitlist.count_documents({"referrer_code": referral_code})

    # Count founding member signups from this partner
    founding_signups = await db.founding_members.count_documents(
        {"referred_by": referral_code}
    )
    signups += founding_signups

    # Count sales (from orders)
    sales_cursor = db.orders.find(
        {"referral_code": referral_code}, {"total": 1, "_id": 0}
    )
    sales_list = await sales_cursor.to_list(100)
    total_sales = len(sales_list)
    total_revenue = sum(o.get("total", 0) for o in sales_list)

    # Add founding member revenue ($70 per signup)
    total_sales += founding_signups
    total_revenue += founding_signups * 70

    # Calculate commission (default 15%)
    commission_rate = partner.get("commission_rate", 15)
    commission = total_revenue * (commission_rate / 100)

    # Also get direct partner earnings from the partners collection
    partner_record = await db.partners.find_one(
        {"referral_code": referral_code}, {"_id": 0}
    )
    if partner_record:
        # Use the actual tracked earnings if available
        commission = partner_record.get("earnings", commission)

    stats = {
        "clicks": clicks,
        "signups": signups,
        "sales": total_sales,
        "commission": round(commission, 2),
        "conversionRate": round((total_sales / clicks * 100) if clicks > 0 else 0, 1),
    }

    return {
        "valid": True,
        "partner": {
            "name": partner.get("name") or partner.get("full_name"),
            "email": email,
            "code": referral_code,
            "discount_code": partner.get("discount_code") or referral_code,
            "tier": partner.get("tier", "Partner"),
            "commission_rate": commission_rate,
            "joined": partner.get("created_at") or partner.get("applied_at"),
        },
        "stats": stats,
    }


@router.get("/partner/stats/{code}")
async def get_partner_stats(code: str):
    """Get stats for a specific partner code"""
    referral_code = code.upper()

    # Count clicks
    clicks = await db.referral_tracks.count_documents({"referrer_code": referral_code})

    # Count signups
    signups = await db.bio_scans.count_documents({"referred_by": referral_code})
    signups += await db.waitlist.count_documents({"referrer_code": referral_code})

    # Count sales
    sales = await db.orders.count_documents({"referral_code": referral_code})

    return {"clicks": clicks, "signups": signups, "sales": sales}


@router.get("/referrer-info/{code}")
async def get_referrer_info(code: str):
    """Get referrer name and discount info for sticky bar display"""
    referral_code = code.upper()

    # Track the click
    await db.referral_tracks.insert_one(
        {
            "referrer_code": referral_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "page_view",
        }
    )

    # Try to find the referrer in multiple collections
    referrer = await db.waitlist.find_one({"referral_code": referral_code}, {"_id": 0})
    if not referrer:
        referrer = await db.influencer_applications.find_one(
            {
                "$or": [
                    {"referral_code": referral_code},
                    {"partner_code": referral_code},
                ]
            },
            {"_id": 0},
        )
    if not referrer:
        referrer = await db.partner_applications.find_one(
            {
                "$or": [
                    {"referral_code": referral_code},
                    {"partner_code": referral_code},
                ]
            },
            {"_id": 0},
        )
    if not referrer:
        referrer = await db.bio_scans.find_one(
            {"referral_code": referral_code}, {"_id": 0}
        )

    if referrer:
        name = (
            referrer.get("name")
            or referrer.get("full_name")
            or referrer.get("instagram_handle")
        )
        if not name and referrer.get("email"):
            # Use first part of email
            name = referrer.get("email").split("@")[0].title()

        return {
            "name": name or "a ReRoots Partner",
            "discount_code": referral_code,
            "discount_percent": 15,
        }

    # Return generic if not found
    return {
        "name": "a ReRoots Partner",
        "discount_code": referral_code,
        "discount_percent": 15,
    }


# ============ END PARTNER DASHBOARD ============


# ============ QUIZ RESULTS EMAIL API ============


@router.post("/send-quiz-results-email")
async def send_quiz_results_email(data: dict):
    """Send personalized quiz results email via Resend"""
    email = data.get("email", "").lower().strip()
    name = data.get("name", "").strip() or "Friend"
    concern = data.get("concern", "skin health")
    recommended_product = data.get("recommended_product", "AURA-GEN")
    secondary_product = data.get("secondary_product")
    referral_code = data.get("referral_code", "")

    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured - skipping email")
        return {"success": False, "message": "Email service not configured"}

    # Map concern tags to human-readable text
    concern_map = {
        "dark_circles": "dark circles and under-eye concerns",
        "aging": "fine lines and loss of firmness",
        "dullness": "dullness and uneven skin tone",
        "acne": "breakouts and congestion",
        "sensitivity": "redness and sensitivity",
        "hydration": "dryness and dehydration",
    }
    concern_text = concern_map.get(concern, concern.replace("_", " "))

    # Map product to link
    product_links = {
        "AURA-GEN": "/products/prod-aura-gen",
        "ROSE-GEN": "/products/prod-rose-gen",
        "OROE": "/oroe",
        "ORO-ROSA": "/lavela",
    }
    product_link = product_links.get(recommended_product, "/shop")

    # Build email HTML
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #FAF8F5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
            <!-- Header -->
            <div style="text-align: center; margin-bottom: 40px;">
                <img src="https://reroots.ca/reroots-logo.png" alt="ReRoots" style="height: 40px; margin-bottom: 20px;">
                <h1 style="color: #2D2A2E; font-size: 28px; margin: 0; font-family: Georgia, serif;">
                    Your Bio-Age Scan Results
                </h1>
                <p style="color: #5A5A5A; font-size: 14px; margin-top: 10px;">
                    Personalized skincare protocol based on your unique profile
                </p>
            </div>
            
            <!-- Greeting -->
            <div style="background: white; border-radius: 16px; padding: 30px; margin-bottom: 20px; border: 1px solid rgba(45,42,46,0.05);">
                <p style="color: #2D2A2E; font-size: 16px; margin: 0 0 15px 0;">
                    Hello {name},
                </p>
                <p style="color: #5A5A5A; font-size: 14px; line-height: 1.6; margin: 0;">
                    Thank you for completing your Bio-Age Repair Scan. Our algorithm has analyzed your primary concerns regarding <strong style="color: #2D2A2E;">{concern_text}</strong>.
                </p>
            </div>
            
            <!-- The Verdict -->
            <div style="background: linear-gradient(135deg, #2D2A2E 0%, #3D3A3E 100%); border-radius: 16px; padding: 30px; margin-bottom: 20px; text-align: center;">
                <p style="color: #D4AF37; font-size: 12px; text-transform: uppercase; letter-spacing: 2px; margin: 0 0 10px 0;">
                    The Verdict
                </p>
                <h2 style="color: white; font-size: 24px; margin: 0 0 15px 0; font-family: Georgia, serif;">
                    {recommended_product}
                </h2>
                <p style="color: rgba(255,255,255,0.7); font-size: 14px; line-height: 1.6; margin: 0;">
                    Based on your profile, your skin is a prime candidate for Biotech Recovery. Our 17% Active Recovery Complex uses high-purity PDRN to support the very fibroblasts your skin needs for a firm, luminous appearance.
                </p>
            </div>
            
            <!-- Your Protocol -->
            <div style="background: white; border-radius: 16px; padding: 30px; margin-bottom: 20px; border: 1px solid rgba(45,42,46,0.05);">
                <h3 style="color: #2D2A2E; font-size: 18px; margin: 0 0 20px 0; font-family: Georgia, serif;">
                    Your Custom Protocol
                </h3>
                <div style="background: #FAF8F5; border-radius: 12px; padding: 20px; margin-bottom: 15px; border-left: 4px solid #D4AF37;">
                    <p style="color: #D4AF37; font-size: 12px; font-weight: bold; margin: 0 0 5px 0;">STEP 1</p>
                    <p style="color: #2D2A2E; font-size: 14px; margin: 0;">
                        <strong>{recommended_product}</strong> — Morning & Night
                    </p>
                </div>
                {"<div style='background: #FAF8F5; border-radius: 12px; padding: 20px; border-left: 4px solid #F8A5B8;'><p style='color: #F8A5B8; font-size: 12px; font-weight: bold; margin: 0 0 5px 0;'>STEP 2</p><p style='color: #2D2A2E; font-size: 14px; margin: 0;'><strong>" + secondary_product + "</strong> — Eye Area, Morning & Night</p></div>" if secondary_product else ""}
            </div>
            
            <!-- CTA -->
            <div style="text-align: center; margin-bottom: 30px;">
                <p style="color: #5A5A5A; font-size: 14px; margin: 0 0 15px 0;">
                    Use code <strong style="color: #D4AF37;">SCAN10</strong> for 10% off your protocol
                </p>
                <a href="https://reroots.ca{product_link}" style="display: inline-block; background: linear-gradient(135deg, #D4AF37 0%, #B8960F 100%); color: #0a0a0a; text-decoration: none; padding: 16px 40px; border-radius: 50px; font-weight: bold; font-size: 14px;">
                    Shop My Results
                </a>
            </div>
            
            <!-- Footer -->
            <div style="text-align: center; border-top: 1px solid rgba(45,42,46,0.1); padding-top: 30px;">
                <p style="color: #5A5A5A; font-size: 12px; margin: 0;">
                    Stay Radiant,<br>
                    <strong>The ReRoots Team</strong>
                </p>
                <p style="color: #9A9A9A; font-size: 11px; margin-top: 20px;">
                    ReRoots Aesthetics Inc. | Canadian Biotech Skincare
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    try:
        params = {
            "from": SENDER_EMAIL,
            "to": email,
            "subject": "Your ReRoots Bio-Age Scan Results are In 🧬",
            "html": html_content,
        }
        await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Quiz results email sent to {email}")
        return {"success": True, "message": "Email sent successfully"}
    except Exception as e:
        logger.error(f"Failed to send quiz results email: {e}")
        return {"success": False, "message": str(e)}


@router.post("/send-quiz-results-batch")
async def send_quiz_results_batch():
    """Send quiz results emails to all pending users"""
    if not RESEND_API_KEY:
        raise HTTPException(status_code=400, detail="Email service not configured")

    # Find bio_scans that haven't received results email
    pending_scans = await db.bio_scans.find(
        {"results_email_sent": {"$ne": True}}, {"_id": 0}
    ).to_list(50)

    sent_count = 0
    for scan in pending_scans:
        email = scan.get("email")
        if not email:
            continue

        # Get recommendation from tags
        tags = scan.get("customer_tags", [])
        recommended = "AURA-GEN"
        concern = "skin health"

        for tag in tags:
            if tag.startswith("recommended:"):
                recommended = tag.split(":")[1]
            elif tag.startswith("concern:"):
                concern = tag.split(":")[1]

        # Send email
        try:
            await send_quiz_results_email(
                {
                    "email": email,
                    "name": scan.get("name", ""),
                    "concern": concern,
                    "recommended_product": recommended,
                }
            )

            # Mark as sent
            await db.bio_scans.update_one(
                {"email": email}, {"$set": {"results_email_sent": True}}
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send to {email}: {e}")

    return {"success": True, "sent": sent_count, "total_pending": len(pending_scans)}


# ============ END QUIZ RESULTS EMAIL ============


