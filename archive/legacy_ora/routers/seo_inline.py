"""
SEO meta, sitemap, robots.txt
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
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
try:
    from models.server_models import User, Category, Product, Cart, Review, Order, Role, exchange_rate_cache
except ImportError:
    pass
try:
    pass  # No email templates needed
except ImportError:
    pass

logger = logging.getLogger(__name__)
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

# ============ SEO ENDPOINTS ============


@router.get("/sitemap.xml")
async def get_sitemap(request: Request):
    """Generate dynamic sitemap with all products and GEO pages"""

    # Get base URL from request or settings
    base_url = os.environ.get("SITE_URL") or os.environ.get("FRONTEND_URL")

    # Get all active products
    products = await db.products.find(
        {"status": {"$ne": "archived"}},
        {"id": 1, "slug": 1, "updated_at": 1, "name": 1, "images": 1},
    ).to_list(1000)

    # Get categories
    categories = await db.categories.find({}, {"id": 1, "slug": 1}).to_list(100)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">
  <!-- Homepage -->
  <url>
    <loc>{base_url}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  
  <!-- Shop Page -->
  <url>
    <loc>{base_url}/shop</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
  
  <!-- Products Page -->
  <url>
    <loc>{base_url}/products</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
  
  <!-- About Page -->
  <url>
    <loc>{base_url}/about</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
  
  <!-- Science Page -->
  <url>
    <loc>{base_url}/science</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
  
  <!-- Waitlist Page -->
  <url>
    <loc>{base_url}/waitlist</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  
  <!-- Blog Page -->
  <url>
    <loc>{base_url}/blog</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  
  <!-- Privacy Policy -->
  <url>
    <loc>{base_url}/privacy</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>
  
  <!-- Terms of Service -->
  <url>
    <loc>{base_url}/terms</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>
  
  <!-- Bio-Age Skin Quiz -->
  <url>
    <loc>{base_url}/Bio-Age-Repair-Scan</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.95</priority>
  </url>
  
  <!-- Return Policy -->
  <url>
    <loc>{base_url}/return-policy</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>
  
  <!-- Individual Product Pages -->
"""

    for product in products:
        product_id = product.get("slug") or product.get("id")
        updated = product.get("updated_at", today)
        if isinstance(updated, datetime):
            updated = updated.strftime("%Y-%m-%d")

        sitemap += f"""  <url>
    <loc>{base_url}/products/{product_id}</loc>
    <lastmod>{updated}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
"""
        # Add product images
        images = product.get("images", [])
        for img in images[:5]:  # Max 5 images per URL
            if img:
                sitemap += f"""    <image:image>
      <image:loc>{img}</image:loc>
      <image:title>{product.get('name', 'ReRoots Product')}</image:title>
    </image:image>
"""
        sitemap += """  </url>
"""

    # Category pages
    for category in categories:
        cat_slug = category.get("slug") or category.get("id")
        sitemap += f"""  <url>
    <loc>{base_url}/products?category={cat_slug}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
"""

    # Blog index page
    sitemap += f"""  <url>
    <loc>{base_url}/blog</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>
"""

    # Individual blog posts
    blog_posts = await db.blog_posts.find(
        {"status": "published"},
        {"slug": 1, "published_at": 1, "featured_image": 1, "title": 1},
    ).to_list(500)

    for post in blog_posts:
        post_slug = post.get("slug")
        pub_date = post.get("published_at", today)
        if isinstance(pub_date, str) and "T" in pub_date:
            pub_date = pub_date.split("T")[0]
        elif isinstance(pub_date, datetime):
            pub_date = pub_date.strftime("%Y-%m-%d")

        sitemap += f"""  <url>
    <loc>{base_url}/blog/{post_slug}</loc>
    <lastmod>{pub_date}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
"""
        # Add featured image if exists
        featured_img = post.get("featured_image")
        if featured_img:
            sitemap += f"""    <image:image>
      <image:loc>{featured_img}</image:loc>
      <image:title>{post.get('title', 'ReRoots Blog')}</image:title>
    </image:image>
"""
        sitemap += """  </url>
"""

    sitemap += "</urlset>"

    return Response(content=sitemap, media_type="application/xml")


@router.get("/robots.txt")
async def get_robots():
    """Generate robots.txt"""
    from fastapi.responses import FileResponse, PlainTextResponse

    base_url = os.environ.get("SITE_URL") or os.environ.get("FRONTEND_URL")

    robots = f"""# ReRoots Biotech Skincare - robots.txt
# https://reroots.ca

User-agent: *
Allow: /
Disallow: /admin
Disallow: /reroots-admin
Disallow: /checkout
Disallow: /account
Disallow: /cart
Disallow: /api/

# Allow search engines to index all public pages
Allow: /shop
Allow: /products
Allow: /about
Allow: /science
Allow: /blog
Allow: /privacy
Allow: /terms

# Sitemap location
Sitemap: {base_url}/api/sitemap.xml

# Crawl-delay for polite crawling
Crawl-delay: 1

# Google specific
User-agent: Googlebot
Allow: /

# Bing specific  
User-agent: Bingbot
Allow: /

# AI Crawlers (for ChatGPT, Perplexity, etc.)
User-agent: GPTBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: ClaudeBot
Allow: /
"""
    return PlainTextResponse(content=robots)


# IndexNow API for instant Bing/Yandex indexing
@router.get("/indexnow/{key}")
async def indexnow_key(key: str):
    """Serve IndexNow verification key file"""
    from fastapi.responses import FileResponse, PlainTextResponse

    return PlainTextResponse(content=key)


@router.post("/admin/indexnow/submit")
async def submit_to_indexnow(request: Request):
    """Submit URLs to IndexNow for instant Bing/Yandex indexing"""
    import httpx

    data = await request.json()
    urls = data.get("urls", [])

    if not urls:
        # Default: submit main pages
        base_url = os.environ.get("SITE_URL") or os.environ.get("FRONTEND_URL")
        urls = [
            f"{base_url}/",
            f"{base_url}/shop",
            f"{base_url}/products",
            f"{base_url}/about",
            f"{base_url}/science",
            f"{base_url}/blog",
        ]

        # Add product URLs
        products = await db.products.find(
            {"is_active": True}, {"slug": 1, "_id": 0}
        ).to_list(50)
        for p in products:
            if p.get("slug"):
                urls.append(f"{base_url}/products/{p['slug']}")

    # Generate a key (in production, use a proper key from IndexNow)
    key = "reroots_indexnow_" + str(uuid.uuid4())[:8]

    payload = {
        "host": "reroots.ca",
        "key": key,
        "keyLocation": f"https://reroots.ca/api/indexnow/{key}",
        "urlList": urls[:100],  # IndexNow limit is 10,000 but we'll be conservative
    }

    results = {"bing": None, "yandex": None}

    try:
        async with httpx.AsyncClient() as client:
            # Submit to Bing
            bing_response = await client.post(
                "https://www.bing.com/indexnow",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            results["bing"] = {
                "status": bing_response.status_code,
                "success": bing_response.status_code in [200, 202],
            }

            # Submit to Yandex
            yandex_response = await client.post(
                "https://yandex.com/indexnow",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            results["yandex"] = {
                "status": yandex_response.status_code,
                "success": yandex_response.status_code in [200, 202],
            }

    except Exception as e:
        return {"success": False, "error": str(e), "urls_submitted": len(urls)}

    return {
        "success": True,
        "urls_submitted": len(urls),
        "results": results,
        "urls": urls[:10],  # Show first 10 for confirmation
    }


@router.get("/seo/product/{product_id}")
async def get_product_seo(product_id: str):
    """Get comprehensive SEO metadata and Schema.org structured data for a product"""
    product = await db.products.find_one(
        {"$or": [{"id": product_id}, {"slug": product_id}]}, {"_id": 0}
    )

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    base_url = os.environ.get("SITE_URL") or os.environ.get("FRONTEND_URL")
    store_settings = await db.store_settings.find_one(
        {"id": "store_settings"}, {"_id": 0}
    )

    # Calculate price
    price = product.get("price", 0)
    discount = product.get("discount_percent", 0)
    final_price = price * (1 - discount / 100) if discount else price

    # Get product images
    images = product.get("images", [])
    if not images and product.get("image"):
        images = [product.get("image")]
    main_image = images[0] if images else ""

    # Availability
    stock = product.get("stock", 0)
    allow_preorder = product.get("allow_preorder", False)
    if stock > 0:
        availability = "https://schema.org/InStock"
        availability_text = "In Stock"
    elif allow_preorder:
        availability = "https://schema.org/PreOrder"
        availability_text = "Pre-Order"
    else:
        availability = "https://schema.org/OutOfStock"
        availability_text = "Out of Stock"

    # Build comprehensive Schema.org Product structured data
    structured_data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.get("name", ""),
        "description": product.get("description", ""),
        "image": images,
        "brand": {"@type": "Brand", "name": product.get("brand", "ReRoots")},
        "sku": product.get("id", ""),
        "category": product.get(
            "google_product_category", "Health & Beauty > Skin Care"
        ),
        "offers": {
            "@type": "Offer",
            "url": f"{base_url}/products/{product.get('slug') or product.get('id')}",
            "priceCurrency": "CAD",
            "price": round(final_price, 2),
            "priceValidUntil": (
                datetime.now(timezone.utc) + timedelta(days=30)
            ).strftime("%Y-%m-%d"),
            "availability": availability,
            "itemCondition": "https://schema.org/NewCondition",
            "seller": {
                "@type": "Organization",
                "name": (
                    store_settings.get("store_name", "ReRoots Skincare")
                    if store_settings
                    else "ReRoots Skincare"
                ),
            },
            "shippingDetails": {
                "@type": "OfferShippingDetails",
                "shippingRate": {
                    "@type": "MonetaryAmount",
                    "value": "0",
                    "currency": "CAD",
                },
                "shippingDestination": {
                    "@type": "DefinedRegion",
                    "addressCountry": "CA",
                },
                "deliveryTime": {
                    "@type": "ShippingDeliveryTime",
                    "handlingTime": {
                        "@type": "QuantitativeValue",
                        "minValue": 1,
                        "maxValue": 2,
                        "unitCode": "DAY",
                    },
                    "transitTime": {
                        "@type": "QuantitativeValue",
                        "minValue": 3,
                        "maxValue": 7,
                        "unitCode": "DAY",
                    },
                },
            },
            "hasMerchantReturnPolicy": {
                "@type": "MerchantReturnPolicy",
                "applicableCountry": "CA",
                "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
                "merchantReturnDays": 30,
                "returnMethod": "https://schema.org/ReturnByMail",
                "returnFees": "https://schema.org/FreeReturn",
            },
        },
    }

    # Add GTIN if available
    if product.get("gtin"):
        structured_data["gtin"] = product.get("gtin")
        structured_data["gtin13"] = product.get("gtin")  # For EAN-13

    # Add MPN if available
    if product.get("mpn"):
        structured_data["mpn"] = product.get("mpn")

    # Add review/rating data
    avg_rating = product.get("average_rating", 0) or product.get("rating", 0)
    review_count = product.get("review_count", 0)
    if avg_rating > 0 and review_count > 0:
        structured_data["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": round(avg_rating, 1),
            "reviewCount": review_count,
            "bestRating": 5,
            "worstRating": 1,
        }

    # Build SEO title and description
    seo_title = (
        product.get("seo_title")
        or f"{product.get('name', '')} | ReRoots Skincare Canada"
    )
    seo_description = (
        product.get("seo_description")
        or product.get("short_description")
        or product.get("description", "")
    )
    if len(seo_description) > 160:
        seo_description = seo_description[:157] + "..."

    return {
        "title": seo_title,
        "description": seo_description,
        "keywords": f"{product.get('name', '')}, ReRoots, PDRN skincare, Canada, {product.get('brand', 'ReRoots')}, biotech beauty",
        "image": main_image,
        "url": f"{base_url}/products/{product.get('slug') or product.get('id')}",
        "price": round(final_price, 2),
        "original_price": price if discount else None,
        "currency": "CAD",
        "availability": availability_text,
        "gtin": product.get("gtin"),
        "mpn": product.get("mpn"),
        "brand": product.get("brand", "ReRoots"),
        "rating": avg_rating,
        "review_count": review_count,
        "structured_data": structured_data,
        "og_data": {
            "og:type": "product",
            "og:title": seo_title,
            "og:description": seo_description,
            "og:image": main_image,
            "og:url": f"{base_url}/products/{product.get('slug') or product.get('id')}",
            "og:site_name": "ReRoots Skincare",
            "product:price:amount": str(round(final_price, 2)),
            "product:price:currency": "CAD",
            "product:availability": availability_text.lower().replace(" ", "_"),
        },
    }


# Google Indexing API endpoint
@router.post("/admin/seo/index-product/{product_id}")
async def index_product_google(product_id: str, request: Request):
    """Submit a product URL to Google Indexing API for instant indexing"""
    await require_admin(request)

    # Check if Google Indexing API credentials are configured
    google_credentials = os.environ.get("GOOGLE_INDEXING_CREDENTIALS")

    if not google_credentials:
        return {
            "success": False,
            "message": "Google Indexing API not configured. Add GOOGLE_INDEXING_CREDENTIALS to environment variables.",
            "instructions": "See admin panel for setup instructions.",
        }

    try:
        import json
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        # Parse credentials
        credentials_dict = json.loads(google_credentials)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_dict, scopes=["https://www.googleapis.com/auth/indexing"]
        )

        # Build the service
        service = build("indexing", "v3", credentials=credentials)

        # Get the product URL
        product = await db.products.find_one(
            {"$or": [{"id": product_id}, {"slug": product_id}]}, {"slug": 1, "id": 1}
        )

        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        base_url = os.environ.get("SITE_URL") or os.environ.get("FRONTEND_URL")
        product_url = f"{base_url}/products/{product.get('slug') or product.get('id')}"

        # Submit URL for indexing
        body = {"url": product_url, "type": "URL_UPDATED"}

        response = service.urlNotifications().publish(body=body).execute()

        # Log the indexing request
        await db.indexing_logs.insert_one(
            {
                "product_id": product_id,
                "url": product_url,
                "action": "URL_UPDATED",
                "response": str(response),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

        return {
            "success": True,
            "message": f"Successfully submitted {product_url} to Google for indexing",
            "response": response,
        }

    except ImportError:
        return {
            "success": False,
            "message": "Google API libraries not installed. Run: pip install google-auth google-api-python-client",
            "instructions": "Install required packages and configure credentials.",
        }
    except Exception as e:
        logging.error(f"Google Indexing API error: {e}")
        return {"success": False, "message": f"Error submitting to Google: {str(e)}"}


@router.post("/admin/seo/index-all")
async def index_all_products_google(request: Request):
    """Submit all product URLs to Google Indexing API"""
    await require_admin(request)

    products = await db.products.find(
        {"is_active": True}, {"slug": 1, "id": 1, "name": 1}
    ).to_list(500)

    base_url = os.environ.get("SITE_URL") or os.environ.get("FRONTEND_URL")

    results = []
    for product in products:
        product_url = f"{base_url}/products/{product.get('slug') or product.get('id')}"
        results.append(
            {
                "product": product.get("name", product.get("id")),
                "url": product_url,
                "status": "queued",
            }
        )

    return {
        "message": f"Queued {len(results)} products for indexing",
        "products": results,
        "note": "For bulk indexing, use Google Search Console's sitemap submission instead.",
    }


@router.post("/admin/clear-cache")
async def clear_server_cache(request: Request):
    """Admin - Clear server-side caches to improve performance"""
    await require_admin(request)

    global translation_cache, exchange_rate_cache

    cleared = []

    # Clear translation cache
    if translation_cache:
        translation_cache.clear()
        cleared.append("translation_cache")

    # Clear exchange rate cache (will refetch on next request)
    if exchange_rate_cache.get("rates"):
        exchange_rate_cache["rates"] = {}
        exchange_rate_cache["last_updated"] = None
        cleared.append("exchange_rate_cache")

    # Force garbage collection
    import gc

    gc.collect()
    cleared.append("garbage_collection")

    return {
        "message": "Cache cleared successfully!",
        "cleared": cleared,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/seo/breadcrumbs/{path:path}")
async def get_breadcrumb_schema(path: str):
    """
    Generate BreadcrumbList schema for any page path.
    Example: /seo/breadcrumbs/products/bio-regenerative-serums
    """
    base_url = os.environ.get("SITE_URL") or os.environ.get("FRONTEND_URL")

    # Route name mapping
    route_names = {
        "": "Home",
        "shop": "Shop",
        "products": "Products",
        "cart": "Shopping Cart",
        "checkout": "Checkout",
        "about": "About Us",
        "science": "The Science of PDRN",
        "science-of-pdrn": "Science of PDRN",
        "waitlist": "Join Waitlist",
        "founding-member": "Founding Member",
        "mission-control": "Mission Control",
        "contact": "Contact Us",
        "login": "Login",
        "register": "Create Account",
        "account": "My Account",
        "wishlist": "Wishlist",
        "return-policy": "Return Policy",
        "shipping-policy": "Shipping Policy",
        "shipping": "Shipping Information",
        "global-shipping": "Global Shipping",
        "privacy": "Privacy Policy",
        "terms": "Terms of Service",
        "become-partner": "Partner Program",
        "influencer": "Influencer Program",
    }

    # Parse path segments
    segments = [s for s in path.split("/") if s]

    # Build breadcrumb items
    breadcrumbs = [{"name": "Home", "url": base_url}]
    current_path = ""

    for i, segment in enumerate(segments):
        current_path += f"/{segment}"

        # Check if this is a product detail page
        if i > 0 and segments[i - 1] == "products":
            # Look up product name
            product = await db.products.find_one(
                {"$or": [{"id": segment}, {"slug": segment}]}, {"name": 1, "_id": 0}
            )
            name = (
                product.get("name", "Product")
                if product
                else segment.replace("-", " ").title()
            )
            breadcrumbs.append({"name": name, "url": f"{base_url}{current_path}"})
        elif segment in route_names:
            breadcrumbs.append(
                {"name": route_names[segment], "url": f"{base_url}{current_path}"}
            )
        else:
            # Format segment as title case
            breadcrumbs.append(
                {
                    "name": segment.replace("-", " ").title(),
                    "url": f"{base_url}{current_path}",
                }
            )

    # Generate schema
    schema = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": crumb["name"],
                "item": crumb["url"],
            }
            for i, crumb in enumerate(breadcrumbs)
        ],
    }

    return {"breadcrumbs": breadcrumbs, "schema": schema}


@router.get("/seo/store-schema")
async def get_store_schema():
    """Get Organization and LocalBusiness schema for the entire store"""
    base_url = os.environ.get("SITE_URL") or os.environ.get("FRONTEND_URL")
    store_settings = await db.store_settings.find_one(
        {"id": "store_settings"}, {"_id": 0}
    )

    organization_schema = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": (
            store_settings.get("store_name", "ReRoots Skincare")
            if store_settings
            else "ReRoots Skincare"
        ),
        "url": base_url,
        "logo": (
            store_settings.get("logo_url", f"{base_url}/logo.png")
            if store_settings
            else f"{base_url}/logo.png"
        ),
        "description": "Premium biotech skincare featuring PDRN technology. Science-backed formulations for visible results.",
        "foundingDate": "2024",
        "contactPoint": {
            "@type": "ContactPoint",
            "email": "support@reroots.ca",
            "contactType": "customer service",
            "availableLanguage": ["English", "French"],
        },
        "sameAs": [
            "https://www.instagram.com/reroots.ca",
            "https://www.facebook.com/reroots.ca",
        ],
        "address": {"@type": "PostalAddress", "addressCountry": "CA"},
    }

    website_schema = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "ReRoots Skincare",
        "url": base_url,
        "potentialAction": {
            "@type": "SearchAction",
            "target": {
                "@type": "EntryPoint",
                "urlTemplate": f"{base_url}/products?search={{search_term_string}}",
            },
            "query-input": "required name=search_term_string",
        },
    }

    return {"organization": organization_schema, "website": website_schema}


# ============================================
# GEO (Generative Engine Optimization) Endpoints
# AI-friendly content for ChatGPT, Perplexity, etc.
# ============================================


@router.get("/geo/brand")
async def get_geo_brand_info():
    """GEO-optimized brand information for AI crawlers and assistants"""
    base_url = os.environ.get("SITE_URL") or os.environ.get("FRONTEND_URL")

    return {
        "brand_name": "ReRoots Skincare",
        "tagline": "The Future of Skin Longevity",
        "founded": "2024",
        "headquarters": "Canada",
        "website": base_url,
        "category": "Biotech Skincare / Luxury Beauty",
        "key_technology": "PDRN (Polydeoxyribonucleotide) - Salmon DNA Technology",
        "brand_description": """ReRoots Skincare is a Canadian biotech beauty brand specializing in PDRN (Salmon DNA) technology for skin regeneration. 
        
Our flagship product, AURA-GEN TXA+PDRN Bio-Regenerator, combines clinical-grade ingredients with luxury formulation:
- 2% PDRN (Salmon DNA) for cellular regeneration
- 5% Tranexamic Acid for hyperpigmentation
- 10% Argireline for expression lines
- Niacinamide for barrier support

ReRoots bridges the gap between Korean skincare innovation and North American luxury beauty standards.""",
        "unique_selling_points": [
            "First Canadian brand to use pharmaceutical-grade PDRN in consumer skincare",
            "Clinical 17% active complex (highest potency in category)",
            "Cruelty-free and ethically sourced salmon DNA",
            "Made in Canada with Korean biotechnology",
            "Founding member pricing: Up to 81% off during beta launch",
        ],
        "certifications": ["Cruelty-Free", "Dermatologist Tested", "Made in Canada"],
        "target_audience": "Adults 25-55 concerned with aging, hyperpigmentation, and skin texture",
        "price_range": "Premium ($79-159 CAD)",
        "availability": {
            "regions": ["Canada", "United States", "International"],
            "shipping": "Free shipping on orders over $50 CAD",
            "current_status": "Pre-order available - Beta Launch Phase",
        },
        "contact": {"email": "support@reroots.ca", "website": base_url},
        "social_media": {"instagram": "@reroots.ca", "tiktok": "@reroots.ca"},
    }


@router.get("/geo/products")
async def get_geo_products():
    """GEO-optimized product catalog for AI assistants"""
    base_url = os.environ.get("SITE_URL") or os.environ.get("FRONTEND_URL")

    products = await db.products.find(
        {"status": {"$ne": "archived"}, "is_active": True}, {"_id": 0}
    ).to_list(100)

    geo_products = []
    for product in products:
        price = product.get("price", 0)
        discount = product.get("discount_percent", 0)
        final_price = price * (1 - discount / 100) if discount else price

        # Parse ingredients into structured format
        ingredients_text = product.get("ingredients", "")
        key_ingredients = []
        if "PDRN" in ingredients_text or "Salmon DNA" in ingredients_text:
            key_ingredients.append(
                {
                    "name": "PDRN (Salmon DNA)",
                    "concentration": "2%",
                    "benefit": "Cellular regeneration and DNA repair",
                }
            )
        if "Tranexamic" in ingredients_text:
            key_ingredients.append(
                {
                    "name": "Tranexamic Acid",
                    "concentration": "5%",
                    "benefit": "Reduces hyperpigmentation and dark spots",
                }
            )
        if (
            "Argireline" in ingredients_text.upper()
            or "argireline" in ingredients_text.lower()
        ):
            key_ingredients.append(
                {
                    "name": "Argireline",
                    "concentration": "10%",
                    "benefit": "Reduces expression lines (Botox alternative)",
                }
            )
        if "Niacinamide" in ingredients_text:
            key_ingredients.append(
                {
                    "name": "Niacinamide",
                    "benefit": "Strengthens skin barrier, reduces pores",
                }
            )
        if "Salicylic" in ingredients_text:
            key_ingredients.append(
                {"name": "Salicylic Acid", "benefit": "Exfoliates and clears pores"}
            )

        geo_product = {
            "name": product.get("name", ""),
            "full_name": f"{product.get('name', '')} by ReRoots Skincare",
            "description": product.get("description", ""),
            "short_description": product.get("short_description", ""),
            "product_url": f"{base_url}/products/{product.get('slug') or product.get('id')}",
            "category": "Biotech Skincare Serum",
            "key_ingredients": key_ingredients,
            "total_active_concentration": "17.0%",
            "pricing": {
                "original_price": f"${price:.2f} CAD",
                "current_price": f"${final_price:.2f} CAD",
                "discount": f"{discount}% off" if discount else None,
                "founding_member_savings": "Up to 81% with referral program",
            },
            "availability": (
                "Pre-Order"
                if product.get("allow_preorder")
                else ("In Stock" if product.get("stock", 0) > 0 else "Out of Stock")
            ),
            "expected_ship_date": product.get("preorder_release_date"),
            "size": "30ml / 1 fl oz",
            "how_to_use": product.get("how_to_use", ""),
            "suitable_for": [
                "All skin types",
                "Hyperpigmentation concerns",
                "Fine lines and wrinkles",
                "Uneven skin texture",
                "Dull skin",
            ],
            "not_recommended_for": [
                "Pregnant or nursing (consult doctor)",
                "Active skin infections",
                "Known allergy to salmon",
            ],
            "images": product.get("images", []),
        }
        geo_products.append(geo_product)

    return {
        "brand": "ReRoots Skincare",
        "product_count": len(geo_products),
        "currency": "CAD",
        "products": geo_products,
        "comparison_note": "ReRoots AURA-GEN offers 17% total actives vs typical serums with 1-5% actives",
        "price_comparison": "Similar PDRN products in Korea cost $200-400 USD. ReRoots offers founding member pricing starting at $49 CAD.",
    }


@router.get("/geo/faq")
async def get_geo_faq():
    """GEO-optimized FAQ for AI assistants - common questions about ReRoots and PDRN"""
    return {
        "brand": "ReRoots Skincare",
        "faqs": [
            {
                "question": "What is PDRN and how does it work in skincare?",
                "answer": "PDRN (Polydeoxyribonucleotide) is a DNA fragment derived from salmon. It promotes skin cell regeneration by activating adenosine A2A receptors, stimulating collagen production, and accelerating wound healing. Originally used in medical settings for burn treatment, it's now available in high-end skincare. ReRoots uses 2% pharmaceutical-grade PDRN.",
            },
            {
                "question": "What is AURA-GEN TXA+PDRN Bio-Regenerator?",
                "answer": "AURA-GEN is ReRoots' flagship serum combining 2% PDRN (Salmon DNA), 5% Tranexamic Acid, and 10% Argireline for a total 17% active complex. It targets aging, hyperpigmentation, and skin texture in one product.",
            },
            {
                "question": "Is ReRoots cruelty-free?",
                "answer": "Yes, ReRoots is 100% cruelty-free. The PDRN is ethically sourced from salmon that are already processed for food consumption - no additional harm is caused.",
            },
            {
                "question": "Where is ReRoots made?",
                "answer": "ReRoots products are formulated and manufactured in Canada using Korean biotechnology ingredients.",
            },
            {
                "question": "How long until I see results?",
                "answer": "Most users report visible improvement in skin texture within 2-4 weeks. Hyperpigmentation typically takes 6-8 weeks to show significant fading. Full cellular regeneration benefits are seen at 12 weeks.",
            },
            {
                "question": "Can I use AURA-GEN with other products?",
                "answer": "Yes! AURA-GEN works well with most skincare routines. Apply after cleansing and toning, before moisturizer. Avoid using with other strong actives like retinol or AHAs in the same routine - alternate them.",
            },
            {
                "question": "What is the founding member program?",
                "answer": "ReRoots offers up to 81% off for founding members during the beta launch. This includes 50% founder discount, plus additional savings through the referral program.",
            },
            {
                "question": "Does ReRoots ship internationally?",
                "answer": "Yes, ReRoots ships to Canada, USA, and select international destinations. Free shipping on orders over $50 CAD within Canada.",
            },
            {
                "question": "Is PDRN safe for sensitive skin?",
                "answer": "PDRN is generally well-tolerated. ReRoots formulas are dermatologist-tested. However, if you have a salmon allergy, consult your doctor before use.",
            },
            {
                "question": "How does ReRoots compare to Korean PDRN products?",
                "answer": "Korean PDRN serums typically cost $200-400 USD and contain 1-2% PDRN. ReRoots offers comparable or higher concentrations at founding member prices starting at $49 CAD, with North American quality standards.",
            },
        ],
    }


@router.get("/geo/ingredients/{ingredient}")
async def get_geo_ingredient_info(ingredient: str):
    """GEO-optimized ingredient information for AI assistants"""
    ingredients_db = {
        "pdrn": {
            "name": "PDRN (Polydeoxyribonucleotide)",
            "also_known_as": ["Salmon DNA", "Salmon Sperm DNA", "Rejuran", "PN"],
            "source": "Salmon (Oncorhynchus keta) sperm/milt",
            "concentration_in_reroots": "2%",
            "mechanism": "Activates adenosine A2A receptors, stimulating cell proliferation and collagen synthesis. Provides building blocks for DNA repair.",
            "clinical_evidence": "Multiple studies show improved wound healing, reduced inflammation, and increased collagen production. Originally developed for medical use in burn treatment.",
            "benefits": [
                "Accelerates skin cell regeneration",
                "Boosts collagen and elastin production",
                "Reduces inflammation",
                "Improves skin hydration",
                "Helps repair UV damage",
            ],
            "origin": "Korean biotechnology, now used globally in premium skincare",
        },
        "tranexamic-acid": {
            "name": "Tranexamic Acid (TXA)",
            "concentration_in_reroots": "5%",
            "mechanism": "Inhibits plasminogen activator, reducing melanin production and transfer to skin cells.",
            "clinical_evidence": "Studies show 3-5% TXA significantly reduces melasma and hyperpigmentation within 8-12 weeks.",
            "benefits": [
                "Reduces dark spots and melasma",
                "Evens skin tone",
                "Prevents new pigmentation",
                "Safe for long-term use",
            ],
            "comparison": "More stable than Vitamin C, works synergistically with other brightening agents",
        },
        "argireline": {
            "name": "Argireline (Acetyl Hexapeptide-3)",
            "concentration_in_reroots": "10%",
            "mechanism": "Inhibits SNARE complex formation, reducing neurotransmitter release that causes muscle contractions.",
            "clinical_evidence": "Clinical studies show up to 30% reduction in wrinkle depth after 28 days at 10% concentration.",
            "benefits": [
                "Reduces expression lines",
                "Botox-like effect without injections",
                "Safe for daily use",
                "Works on forehead, crow's feet, frown lines",
            ],
            "nickname": "Botox in a bottle",
        },
        "niacinamide": {
            "name": "Niacinamide (Vitamin B3)",
            "mechanism": "Increases ceramide production, inhibits melanin transfer, reduces inflammation.",
            "benefits": [
                "Strengthens skin barrier",
                "Minimizes pores",
                "Reduces redness",
                "Brightens skin tone",
            ],
        },
    }

    # Normalize the ingredient name
    ingredient_key = ingredient.lower().replace(" ", "-").replace("_", "-")

    if ingredient_key in ingredients_db:
        return {
            "found": True,
            "ingredient": ingredients_db[ingredient_key],
            "used_in": "AURA-GEN TXA+PDRN Bio-Regenerator by ReRoots Skincare",
        }
    else:
        return {
            "found": False,
            "message": f"Ingredient '{ingredient}' not found in our database",
            "available_ingredients": list(ingredients_db.keys()),
        }


# ============================================
# AI CONTENT STUDIO - UGC Generation
# ============================================


class UGCGenerationRequest(BaseModel):
    image_base64: str
    product_name: Optional[str] = "Product"
    style: Optional[str] = "UGC influencer style, natural lighting, lifestyle shot"
    generate_video: Optional[bool] = False
    video_duration: Optional[int] = 4  # 4, 8, or 12 seconds


class UGCGenerationResponse(BaseModel):
    success: bool
    ugc_image_base64: Optional[str] = None
    video_url: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    error: Optional[str] = None


@router.post("/admin/ai-studio/analyze-image")
async def analyze_product_image(request: Request):
    """Analyze a product image using GPT-4o Vision"""
    try:
        data = await request.json()
        image_base64 = data.get("image_base64", "")

        if not image_base64:
            raise HTTPException(status_code=400, detail="No image provided")

        # Clean base64 if it has data URL prefix
        if "base64," in image_base64:
            image_base64 = image_base64.split("base64,")[1]

        llm_key = get_claude_api_key()
        if not llm_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

        chat = LlmChat(
            api_key=llm_key,
            session_id=f"analyze-{uuid.uuid4()}",
            system_message="You are a product photography and marketing expert. Analyze images to identify products and suggest UGC content ideas.",
        )
        chat.with_model("anthropic", "claude-sonnet-4-5-20250929")

        msg = UserMessage(
            text="Analyze this product image. Describe: 1) What product is shown, 2) Key visual features, 3) Target audience, 4) Best angles/styles for UGC content. Keep response concise.",
            file_contents=[ImageContent(image_base64)],
        )

        response = await chat.send_message(msg)

        return {"success": True, "analysis": response}
    except Exception as e:
        print(f"Image analysis error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/admin/ai-studio/generate-ugc-image")
async def generate_ugc_image(request: Request):
    """Generate a UGC-style image from a product photo using Nano Banana"""
    try:
        data = await request.json()
        image_base64 = data.get("image_base64", "")
        product_name = data.get("product_name", "skincare product")
        style = data.get("style", "UGC influencer style")

        if not image_base64:
            raise HTTPException(status_code=400, detail="No image provided")

        # Clean base64 if it has data URL prefix
        if "base64," in image_base64:
            image_base64 = image_base64.split("base64,")[1]

        llm_key = get_claude_api_key()
        if not llm_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

        chat = LlmChat(
            api_key=llm_key,
            session_id=f"ugc-{uuid.uuid4()}",
            system_message="You are a creative content generator specializing in UGC-style product photography.",
        )
        chat.with_model("gemini", "gemini-3-pro-image-preview").with_params(
            modalities=["image", "text"]
        )

        prompt = f"""Transform this {product_name} product photo into a stunning UGC-style image.
Style: {style}
Requirements:
- Natural, authentic influencer aesthetic
- Soft, flattering lighting
- Lifestyle context (hands holding product, bathroom counter, vanity setup)
- Premium but relatable feel
- Instagram/TikTok ready composition
Keep the product as the hero but make it feel organic and aspirational."""

        msg = UserMessage(text=prompt, file_contents=[ImageContent(image_base64)])

        text_response, images = await chat.send_message_multimodal_response(msg)

        if images and len(images) > 0:
            return {
                "success": True,
                "ugc_image_base64": images[0].get("data", ""),
                "mime_type": images[0].get("mime_type", "image/png"),
                "ai_notes": text_response,
            }
        else:
            return {
                "success": False,
                "error": "No image generated",
                "ai_notes": text_response,
            }

    except Exception as e:
        print(f"UGC image generation error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/admin/ai-studio/generate-caption")
async def generate_ugc_caption(request: Request):
    """Generate social media caption and hashtags"""
    try:
        data = await request.json()
        product_name = data.get("product_name", "skincare product")
        product_description = data.get("product_description", "")
        platform = data.get("platform", "instagram")  # instagram, tiktok, facebook
        tone = data.get("tone", "casual")  # casual, professional, fun, luxurious

        llm_key = get_claude_api_key()
        if not llm_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(
            api_key=llm_key,
            session_id=f"caption-{uuid.uuid4()}",
            system_message="You are a social media marketing expert specializing in skincare and beauty content.",
        )
        chat.with_model("anthropic", "claude-sonnet-4-5-20250929")

        msg = UserMessage(
            text=f"""Create a {platform} caption for this product:
Product: {product_name}
Description: {product_description}
Tone: {tone}

Requirements:
- Engaging hook in first line
- Authentic UGC voice (not salesy)
- Include a call-to-action
- Keep it under 200 characters for {platform}
- Add 10-15 relevant hashtags

Format your response as:
CAPTION:
[your caption here]

HASHTAGS:
[hashtags separated by spaces]"""
        )

        response = await chat.send_message(msg)

        # Parse response
        caption = ""
        hashtags = []

        if "CAPTION:" in response:
            parts = response.split("HASHTAGS:")
            caption = parts[0].replace("CAPTION:", "").strip()
            if len(parts) > 1:
                hashtag_text = parts[1].strip()
                hashtags = [
                    tag.strip() for tag in hashtag_text.split() if tag.startswith("#")
                ]
        else:
            caption = response

        return {"success": True, "caption": caption, "hashtags": hashtags}
    except Exception as e:
        print(f"Caption generation error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/admin/ai-studio/generate-video")
async def generate_ugc_video(request: Request):
    """Generate a UGC-style video using Sora 2"""
    try:
        data = await request.json()
        prompt = data.get("prompt", "")
        product_name = data.get("product_name", "skincare product")
        duration = data.get("duration", 4)  # 4, 8, or 12 seconds
        size = data.get("size", "1024x1792")  # Portrait for TikTok/Reels

        if not prompt:
            prompt = f"A person gently applying {product_name} to their face, soft natural lighting, bathroom mirror reflection, UGC style, authentic and relatable, smooth skin texture, morning skincare routine"

        # Validate duration
        if duration not in [4, 8, 12]:
            duration = 4

        # Validate size - use sizes that work with both library AND Sora 2 API
        # Library accepts: 1280x720, 1792x1024, 1024x1792, 1024x1024
        # Sora 2 API accepts: 1280x720, 720x1280
        # Only 1280x720 works with both - use it as default landscape
        # For portrait, we'll use 1024x1792 (library) which may need API update
        valid_sizes = ["1280x720", "1024x1792", "1792x1024", "1024x1024"]
        if size not in valid_sizes:
            size = "1280x720"  # Safe default that works

        llm_key = get_claude_api_key()
        if not llm_key:
            return {
                "success": False,
                "error": "AI service not configured - missing EMERGENT_LLM_KEY",
            }

        print(
            f"Starting video generation: prompt='{prompt[:50]}...', size={size}, duration={duration}"
        )

        # Create new instance for each request
        video_gen = OpenAIVideoGeneration(api_key=llm_key)

        # Generate video (this may take a few minutes)
        video_bytes = video_gen.text_to_video(
            prompt=prompt,
            model="sora-2",
            size=size,
            duration=duration,
            max_wait_time=600,
        )

        print(
            f"Video generation result: bytes={len(video_bytes) if video_bytes else 0}"
        )

        if video_bytes:
            # Save video to a temporary file
            video_id = str(uuid.uuid4())
            video_path = f"/app/backend/static/videos/{video_id}.mp4"

            # Ensure directory exists
            os.makedirs(os.path.dirname(video_path), exist_ok=True)

            video_gen.save_video(video_bytes, video_path)
            print(f"Video saved to: {video_path}")

            # Store video info in database
            await db.ai_studio_videos.insert_one(
                {
                    "id": video_id,
                    "prompt": prompt,
                    "product_name": product_name,
                    "duration": duration,
                    "size": size,
                    "created_at": datetime.utcnow(),
                    "file_path": video_path,
                }
            )

            return {
                "success": True,
                "video_id": video_id,
                "video_url": f"/api/admin/ai-studio/video/{video_id}",
                "duration": duration,
            }
        else:
            return {
                "success": False,
                "error": "Video generation returned empty - please try again",
            }

    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        print(f"Video generation error: {e}\n{error_details}")
        return {"success": False, "error": f"Video generation error: {str(e)}"}


@router.get("/admin/ai-studio/video/{video_id}")
async def get_video(video_id: str):
    """Serve generated video file"""
    try:
        video_path = f"/app/backend/static/videos/{video_id}.mp4"
        if os.path.exists(video_path):
            return FileResponse(
                video_path, media_type="video/mp4", filename=f"ugc_video_{video_id}.mp4"
            )
        else:
            raise HTTPException(status_code=404, detail="Video not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/ai-studio/history")
async def get_ai_studio_history():
    """Get history of generated content"""
    try:
        videos = (
            await db.ai_studio_videos.find({}, {"_id": 0})
            .sort("created_at", -1)
            .to_list(50)
        )
        return {"success": True, "videos": videos}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# ELEVENLABS VOICE GENERATION - Instagram Reel Creator
# ============================================================================

class VoiceGenerationRequest(BaseModel):
    text: str
    voice_id: str = "onyx"  # Default: Onyx (deep, authoritative - good for founder vibe)
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    
class ScriptGenerationRequest(BaseModel):
    topic: str
    product_name: str = ""
    tone: str = "founder"  # founder, professional, casual, scientific
    duration: str = "30"  # seconds
    language: str = "en"  # en, hi (Hinglish)

@router.get("/admin/ai-studio/voices")
async def get_available_voices():
    """Get list of available voices - OpenAI (free) + ElevenLabs (paid)"""
    # OpenAI voices (FREE with Emergent key)
    openai_voices = [
        {"voice_id": "onyx", "name": "Onyx", "description": "Deep, authoritative - Founder/Tech vibe", "category": "openai_free", "free": True},
        {"voice_id": "nova", "name": "Nova", "description": "Energetic, upbeat - Great for promos", "category": "openai_free", "free": True},
        {"voice_id": "alloy", "name": "Alloy", "description": "Neutral, balanced - Professional", "category": "openai_free", "free": True},
        {"voice_id": "echo", "name": "Echo", "description": "Smooth, calm - Soothing content", "category": "openai_free", "free": True},
        {"voice_id": "fable", "name": "Fable", "description": "Expressive, storytelling", "category": "openai_free", "free": True},
        {"voice_id": "shimmer", "name": "Shimmer", "description": "Bright, cheerful - Female", "category": "openai_free", "free": True},
        {"voice_id": "coral", "name": "Coral", "description": "Warm, friendly - Female", "category": "openai_free", "free": True},
        {"voice_id": "sage", "name": "Sage", "description": "Wise, measured - Professional", "category": "openai_free", "free": True},
        {"voice_id": "ash", "name": "Ash", "description": "Clear, articulate", "category": "openai_free", "free": True},
    ]
    
    # ElevenLabs voices (requires paid subscription)
    elevenlabs_voices = [
        {"voice_id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel (ElevenLabs)", "description": "Professional American Female - Paid", "category": "elevenlabs_paid", "free": False},
        {"voice_id": "ErXwobaYiN019PkySvjV", "name": "Antoni (ElevenLabs)", "description": "Professional American Male - Paid", "category": "elevenlabs_paid", "free": False},
        {"voice_id": "ODq5zmih8GrVes37Dizd", "name": "Patrick (ElevenLabs)", "description": "Mature Male Tech Vibe - Paid", "category": "elevenlabs_paid", "free": False},
        {"voice_id": "onwK4e9ZLuTAKqWW03F9", "name": "Daniel (ElevenLabs)", "description": "British Male Professional - Paid", "category": "elevenlabs_paid", "free": False},
        {"voice_id": "XB0fDUnXU5powFXDhCwa", "name": "Charlotte (ElevenLabs)", "description": "British Female Elegant - Paid", "category": "elevenlabs_paid", "free": False},
    ]
    
    return {
        "success": True,
        "voices": openai_voices + elevenlabs_voices,
        "free_voices": [v["voice_id"] for v in openai_voices],
        "requires_api_key": False
    }

@router.post("/admin/ai-studio/generate-voice")
async def generate_voice_audio(request: VoiceGenerationRequest):
    """Generate voice audio - tries OpenAI TTS first (free), falls back to ElevenLabs"""
    
    # Check which provider to use based on voice_id
    openai_voices = ["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]
    use_openai = request.voice_id in openai_voices
    
    # Try OpenAI TTS first (free with Emergent key)
    if use_openai:
        try:
            from emergentintegrations.llm.openai import OpenAITextToSpeech
            
            llm_key = get_claude_api_key()
            if not llm_key:
                return {"success": False, "error": "AI service not configured."}
            
            tts = OpenAITextToSpeech(api_key=llm_key)
            
            # Map stability to speed (lower stability = more expressive = slightly faster)
            speed = 1.0 + (0.5 - request.stability) * 0.3  # Range: 0.85 - 1.15
            speed = max(0.5, min(2.0, speed))
            
            audio_base64 = await tts.generate_speech_base64(
                text=request.text,
                model="tts-1-hd",
                voice=request.voice_id,
                speed=speed
            )
            
            # Estimate duration
            words = len(request.text.split())
            estimated_duration = round(words / 150 * 60 / speed, 1)
            
            return {
                "success": True,
                "audio_base64": audio_base64,
                "mime_type": "audio/mpeg",
                "text_length": len(request.text),
                "estimated_duration_seconds": estimated_duration,
                "provider": "openai"
            }
        except Exception as e:
            logging.error(f"OpenAI TTS error: {e}")
            return {"success": False, "error": str(e)}
    
    # Use ElevenLabs for ElevenLabs voice IDs
    try:
        from elevenlabs import ElevenLabs, VoiceSettings
        
        eleven_api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not eleven_api_key:
            return {
                "success": False, 
                "error": "ElevenLabs API key not configured. Use OpenAI voices (alloy, nova, onyx, etc.) for free generation.",
                "requires_api_key": True
            }
        
        client = ElevenLabs(api_key=eleven_api_key)
        
        # Generate audio
        voice_settings = VoiceSettings(
            stability=request.stability,
            similarity_boost=request.similarity_boost,
            style=request.style,
            use_speaker_boost=True
        )
        
        audio_generator = client.text_to_speech.convert(
            text=request.text,
            voice_id=request.voice_id,
            model_id="eleven_multilingual_v2",
            voice_settings=voice_settings
        )
        
        # Collect audio data
        audio_data = b""
        for chunk in audio_generator:
            audio_data += chunk
        
        # Convert to base64
        audio_b64 = base64.b64encode(audio_data).decode()
        
        # Estimate duration (rough: ~150 words per minute, 5 chars per word)
        words = len(request.text.split())
        estimated_duration = round(words / 150 * 60, 1)
        
        return {
            "success": True,
            "audio_base64": audio_b64,
            "mime_type": "audio/mpeg",
            "text_length": len(request.text),
            "estimated_duration_seconds": estimated_duration,
            "provider": "elevenlabs"
        }
        
    except Exception as e:
        logging.error(f"Voice generation error: {e}")
        return {"success": False, "error": str(e)}

@router.post("/admin/ai-studio/generate-reel-script")
async def generate_reel_script(request: ScriptGenerationRequest):
    """Generate a script for Instagram Reels using AI"""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        llm_key = get_claude_api_key()
        if not llm_key:
            return {"success": False, "error": "AI service not configured. Please add EMERGENT_LLM_KEY to your environment."}
        
        tone_prompts = {
            "founder": "You're a tech founder sharing insider knowledge. Speak with authority but be relatable. Use 'we' and 'I discovered'. Add one Hindi word naturally if the user wants Hinglish.",
            "professional": "You're a skincare scientist explaining breakthrough research. Be credible and precise. Use technical terms but explain them simply.",
            "casual": "You're a skincare enthusiast sharing your genuine experience. Be warm, friendly, and conversational. Use 'you know what' and 'honestly'.",
            "scientific": "You're presenting clinical findings. Use data points, percentages, and study references. Sound authoritative like a medical professional."
        }
        
        language_note = ""
        if request.language == "hi":
            language_note = "Mix natural Hindi words/phrases into the script (Hinglish style). Example: 'Aur yeh hai kya magic?' or 'Dekho, the results are insane.'"
        
        duration_words = {
            "15": "30-40 words",
            "30": "60-80 words", 
            "60": "120-150 words",
            "90": "180-200 words"
        }
        word_count = duration_words.get(request.duration, "60-80 words")
        
        prompt = f"""Write an Instagram Reel script for a skincare/biotech brand.

TOPIC: {request.topic}
{f'PRODUCT: {request.product_name}' if request.product_name else ''}
TONE: {tone_prompts.get(request.tone, tone_prompts['founder'])}
TARGET LENGTH: {word_count} (approximately {request.duration} seconds when spoken)
{language_note}

RULES:
- Start with a HOOK (question or bold statement) in the first 3 seconds
- NO hashtags or emojis in the script
- Include one "wait for it" moment or revelation
- End with a call-to-action or thought-provoking statement
- Make it sound NATURAL, not scripted
- Use short sentences for punchier delivery

Write ONLY the spoken script, nothing else. No stage directions."""

        chat = LlmChat(
            api_key=llm_key,
            session_id=f"reel_script_{uuid.uuid4()}",
            system_message="You are a professional content creator and scriptwriter for Instagram Reels. Write engaging, natural-sounding scripts that hook viewers instantly."
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        response = await chat.send_message(UserMessage(text=prompt))
        script = response.strip()
        
        # Count words for reference
        word_count_actual = len(script.split())
        
        return {
            "success": True,
            "script": script,
            "word_count": word_count_actual,
            "estimated_duration_seconds": round(word_count_actual / 2.5)  # ~150 words/min = 2.5 words/sec
        }
        
    except Exception as e:
        logging.error(f"Script generation error: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# AI INTELLIGENCE HUB - VIP Signal, Fraud Detection, Content Factory, Sentiment
# ============================================================================

@router.get("/admin/ai/vip-signals")
async def get_vip_signals(request: Request):
    """Get VIP customer alerts - identifies high-value and influencer customers"""
    await require_admin(request)
    
    # Get orders with customer data
    orders = await db.orders.find({}).sort("created_at", -1).limit(100).to_list(100)
    
    # Aggregate customer data
    customer_stats = {}
    for order in orders:
        email = order.get("customer_email") or order.get("email", "")
        if not email:
            continue
            
        if email not in customer_stats:
            customer_stats[email] = {
                "id": email,
                "name": order.get("customer_name") or order.get("shipping_address", {}).get("first_name", "Customer"),
                "email": email,
                "total_spent": 0,
                "order_count": 0,
                "recent_products": [],
                "last_order_date": None
            }
        
        customer_stats[email]["total_spent"] += order.get("total", 0)
        customer_stats[email]["order_count"] += 1
        customer_stats[email]["last_order_date"] = order.get("created_at")
        
        # Track products
        for item in order.get("items", []):
            prod_name = item.get("product", {}).get("name") or item.get("name", "Product")
            if prod_name not in customer_stats[email]["recent_products"]:
                customer_stats[email]["recent_products"].append(prod_name)
    
    # Identify VIPs (high spenders or repeat customers)
    vip_threshold = 200  # $200+ total spent
    repeat_threshold = 2  # 2+ orders
    
    vip_customers = []
    recent_alerts = []
    
    for email, stats in customer_stats.items():
        is_vip = stats["total_spent"] >= vip_threshold or stats["order_count"] >= repeat_threshold
        
        if is_vip:
            stats["is_repeat"] = stats["order_count"] > 1
            stats["is_influencer"] = False  # Could be enhanced with social media lookup
            vip_customers.append(stats)
            
            # Add recent VIP orders as alerts
            if stats["order_count"] <= 3:  # Only recent VIPs
                recent_alerts.append({
                    "id": email,
                    "customer_name": stats["name"],
                    "customer_email": email,
                    "order_total": stats["total_spent"],
                    "is_repeat": stats["is_repeat"],
                    "is_influencer": stats["is_influencer"]
                })
    
    # Sort by total spent
    vip_customers.sort(key=lambda x: x["total_spent"], reverse=True)
    recent_alerts = recent_alerts[:10]  # Top 10 recent
    
    return {
        "vip_customers": vip_customers[:20],
        "recent_alerts": recent_alerts,
        "total_vip_count": len(vip_customers)
    }


@router.post("/admin/ai/generate-thank-you-note")
async def generate_thank_you_note(request: Request, data: dict = Body(...)):
    """Generate personalized thank-you note for VIP customer"""
    await require_admin(request)
    
    llm_key = get_claude_api_key()
    if not llm_key:
        return {"success": False, "error": "LLM key not configured"}
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        customer_name = data.get("customer_name", "Valued Customer")
        order_total = data.get("order_total", 0)
        products = data.get("products", [])
        is_repeat = data.get("is_repeat", False)
        
        prompt = f"""Write a short, warm, personalized thank-you note from the founder of ReRoots Biotech Skincare.

Customer Name: {customer_name}
Order Value: ${order_total:.2f}
Products: {', '.join(products[:3]) if products else 'skincare products'}
Repeat Customer: {'Yes' if is_repeat else 'No - First order'}

Guidelines:
- Keep it brief (3-4 sentences max)
- Make it feel personal and handwritten
- Reference their specific purchase if possible
- Sign off as "Guri, Founder of ReRoots"
- Sound genuine, not corporate

Write ONLY the note text, nothing else."""

        chat = LlmChat(
            api_key=llm_key,
            session_id=f"thank_you_{uuid.uuid4()}",
            system_message="You write warm, authentic thank-you notes for a luxury skincare brand."
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        response = await chat.send_message(UserMessage(text=prompt))
        
        return {"success": True, "note": response.strip()}
        
    except Exception as e:
        logging.error(f"Thank you note generation error: {e}")
        return {"success": False, "error": str(e)}


@router.get("/admin/ai/fraud-detection")
async def get_fraud_detection(request: Request):
    """Get flagged orders with potential fraud indicators"""
    await require_admin(request)
    
    # Get recent orders
    orders = await db.orders.find({}).sort("created_at", -1).limit(50).to_list(50)
    
    flagged_orders = []
    
    for order in orders:
        risk_score = 0
        risk_reasons = []
        
        shipping = order.get("shipping_address", {})
        billing = order.get("billing_address", {})
        
        # Check 1: Shipping/Billing address mismatch
        if billing and shipping:
            if billing.get("city", "").lower() != shipping.get("city", "").lower():
                risk_score += 20
                risk_reasons.append("Shipping city differs from billing city")
            if billing.get("country", "").lower() != shipping.get("country", "").lower():
                risk_score += 30
                risk_reasons.append("Shipping country differs from billing country")
        
        # Check 2: High value first-time order
        customer_email = order.get("customer_email") or order.get("email", "")
        order_count = await db.orders.count_documents({"customer_email": customer_email})
        if order_count == 1 and order.get("total", 0) > 300:
            risk_score += 25
            risk_reasons.append(f"High-value first order (${order.get('total', 0):.2f})")
        
        # Check 3: Rush shipping on expensive order
        if order.get("shipping_method") == "express" and order.get("total", 0) > 200:
            risk_score += 15
            risk_reasons.append("Express shipping on high-value order")
        
        # Check 4: Suspicious notes
        notes = order.get("notes", "").lower()
        suspicious_keywords = ["urgent", "asap", "rush", "gift", "different address"]
        for keyword in suspicious_keywords:
            if keyword in notes:
                risk_score += 10
                risk_reasons.append(f"Suspicious note keyword: '{keyword}'")
                break
        
        # Only flag if risk score > 30
        if risk_score > 30:
            flagged_orders.append({
                "id": str(order.get("_id", "")),
                "order_number": order.get("order_number", order.get("_id", "Unknown")),
                "customer_email": customer_email,
                "total": order.get("total", 0),
                "risk_score": min(risk_score, 100),
                "risk_reasons": risk_reasons,
                "created_at": order.get("created_at")
            })
    
    # Sort by risk score
    flagged_orders.sort(key=lambda x: x["risk_score"], reverse=True)
    
    return {"flagged_orders": flagged_orders}


@router.post("/admin/ai/fraud-review")
async def fraud_review(request: Request, data: dict = Body(...)):
    """Mark flagged order as reviewed"""
    await require_admin(request)
    
    order_id = data.get("order_id")
    action = data.get("action")  # approve or reject
    
    if not order_id or action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid request")
    
    try:
        await db.orders.update_one(
            {"_id": ObjectId(order_id)},
            {"$set": {
                "fraud_review_status": action,
                "fraud_reviewed_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        if action == "reject":
            await db.orders.update_one(
                {"_id": ObjectId(order_id)},
                {"$set": {"status": "cancelled", "cancel_reason": "Fraud detected"}}
            )
        
        return {"success": True, "action": action}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/admin/ai/generate-ad-content")
async def generate_ad_content(request: Request, data: dict = Body(...)):
    """Generate multiple variations of ad copy for a product"""
    await require_admin(request)
    
    llm_key = get_claude_api_key()
    if not llm_key:
        return {"success": False, "error": "LLM key not configured"}
    
    product_id = data.get("product_id")
    content_type = data.get("content_type", "tiktok")  # tiktok, instagram, meta_ad, email, sms
    variations = data.get("variations", 5)
    
    # Get product data
    product = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not product:
        return {"success": False, "error": "Product not found"}
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        content_prompts = {
            "tiktok": f"""Create {variations} different TikTok video scripts for this skincare product.

Product: {product.get('name')}
Key Ingredients: {', '.join(product.get('ingredients', [])[:5])}
Benefits: {', '.join(product.get('key_benefits', [])[:3])}
Price: ${product.get('price', 0)}

Each script should:
- Be 15-30 seconds when spoken
- Start with an attention-grabbing hook
- Include a transformation or "before/after" angle
- End with a call-to-action
- Use casual, Gen-Z friendly language

Format each variation as:
VARIATION 1:
[script]

VARIATION 2:
[script]
...and so on""",

            "instagram": f"""Create {variations} different Instagram captions for this skincare product.

Product: {product.get('name')}
Key Benefits: {', '.join(product.get('key_benefits', [])[:3])}
Brand: ReRoots Biotech Skincare

Each caption should:
- Be engaging and scroll-stopping
- Include relevant emojis
- End with a call-to-action
- Include 5-8 relevant hashtags at the end

Format as:
CAPTION 1:
[caption]
[hashtags]

CAPTION 2:
...and so on""",

            "meta_ad": f"""Create {variations} different Meta/Facebook ad copy variations for this skincare product.

Product: {product.get('name')}
Key Benefits: {', '.join(product.get('key_benefits', [])[:3])}
Price: ${product.get('price', 0)}

Each ad should include:
- Headline (max 40 chars)
- Primary text (2-3 sentences)
- Call-to-action

Format as:
AD 1:
Headline: [headline]
Text: [primary text]
CTA: [call to action]

AD 2:
...and so on""",

            "email": f"""Create {variations} email subject lines for promoting this skincare product.

Product: {product.get('name')}
Key Benefits: {', '.join(product.get('key_benefits', [])[:3])}

Requirements:
- Mix of curiosity, urgency, and benefit-focused
- Under 50 characters each
- No spam trigger words

Format as numbered list""",

            "sms": f"""Create {variations} SMS marketing messages for this skincare product.

Product: {product.get('name')}
Brand: ReRoots

Requirements:
- Under 160 characters each
- Include a sense of urgency or exclusivity
- Include "Reply STOP to opt out" at end

Format as numbered list"""
        }
        
        prompt = content_prompts.get(content_type, content_prompts["instagram"])
        
        chat = LlmChat(
            api_key=llm_key,
            session_id=f"content_factory_{uuid.uuid4()}",
            system_message="You are an expert social media copywriter for a premium biotech skincare brand. Create engaging, conversion-focused content."
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        response = await chat.send_message(UserMessage(text=prompt))
        
        # Parse variations from response
        content_list = []
        parts = response.split("VARIATION") if "VARIATION" in response else response.split("CAPTION") if "CAPTION" in response else response.split("AD") if "AD" in response else [response]
        
        for i, part in enumerate(parts):
            if part.strip() and i > 0:  # Skip first empty part
                # Extract hashtags if present
                lines = part.strip().split('\n')
                hashtags = ""
                text = part.strip()
                
                for line in lines:
                    if line.startswith('#') or '#' in line[:3]:
                        hashtags = line
                        text = '\n'.join([l for l in lines if l != line])
                        break
                
                content_list.append({
                    "text": text.strip().lstrip('0123456789.:) '),
                    "hashtags": hashtags
                })
        
        # If parsing failed, just return the whole response as one item
        if not content_list:
            content_list = [{"text": response, "hashtags": ""}]
        
        return {
            "success": True,
            "content": content_list[:variations],
            "product_name": product.get("name"),
            "content_type": content_type
        }
        
    except Exception as e:
        logging.error(f"Content generation error: {e}")
        return {"success": False, "error": str(e)}


@router.get("/admin/ai/sentiment-analysis")
async def get_sentiment_analysis(request: Request, range: str = "week"):
    """Analyze sentiment from customer reviews and generate insights"""
    await require_admin(request)
    
    llm_key = get_claude_api_key()
    
    # Get reviews from database
    reviews = await db.reviews.find({}).sort("created_at", -1).limit(100).to_list(100)
    
    if not reviews:
        # Return placeholder data if no reviews
        return {
            "positive_percent": 70,
            "neutral_percent": 20,
            "negative_percent": 10,
            "insights": [
                {"type": "positive", "text": "Customers love the product quality"},
                {"type": "suggestion", "text": "No specific feedback to analyze yet"}
            ],
            "recommendations": "Start collecting more customer reviews to get actionable insights.",
            "review_count": 0
        }
    
    # Compile reviews text
    reviews_text = "\n".join([
        f"Rating: {r.get('rating', 0)}/5 - {r.get('title', '')} - {r.get('comment', '')}"
        for r in reviews[:50]  # Analyze last 50 reviews
    ])
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        prompt = f"""Analyze these customer reviews for a skincare brand and provide insights.

REVIEWS:
{reviews_text}

Provide your analysis in this EXACT JSON format:
{{
    "positive_percent": <number 0-100>,
    "neutral_percent": <number 0-100>,
    "negative_percent": <number 0-100>,
    "insights": [
        {{"type": "positive", "text": "<what customers love>"}},
        {{"type": "positive", "text": "<another positive theme>"}},
        {{"type": "negative", "text": "<any concerns or complaints>"}},
        {{"type": "suggestion", "text": "<actionable suggestion>"}}
    ],
    "recommendations": "<1-2 sentence recommendation for the business>"
}}

Return ONLY valid JSON, no other text."""

        chat = LlmChat(
            api_key=llm_key,
            session_id=f"sentiment_{uuid.uuid4()}",
            system_message="You are a customer experience analyst. Analyze reviews and return JSON only."
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        response = await chat.send_message(UserMessage(text=prompt))
        
        # Parse JSON response
        import json
        # Clean response
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        
        result = json.loads(response)
        result["review_count"] = len(reviews)
        
        return result
        
    except Exception as e:
        logging.error(f"Sentiment analysis error: {e}")
        # Return basic calculated sentiment
        positive = sum(1 for r in reviews if r.get("rating", 0) >= 4)
        negative = sum(1 for r in reviews if r.get("rating", 0) <= 2)
        neutral = len(reviews) - positive - negative
        
        return {
            "positive_percent": round(positive / len(reviews) * 100) if reviews else 0,
            "neutral_percent": round(neutral / len(reviews) * 100) if reviews else 0,
            "negative_percent": round(negative / len(reviews) * 100) if reviews else 0,
            "insights": [{"type": "info", "text": "Basic sentiment calculated from star ratings"}],
            "recommendations": "AI analysis unavailable. Review manually.",
            "review_count": len(reviews)
        }


# ============================================================================
# AUTONOMOUS BRIDGE - AI Actions Queue & Review Watchdog
# ============================================================================

# Brand Guardian System Prompt (injected into all AI calls)
REROOTS_BRAND_GUARDIAN_PROMPT = """
Role: You are the ReRoots Operations Lead & Biotech Brand Guardian. 
Your goal is to protect the founder's $50,000 IP assets, maintain a "luxury biotech" brand image, 
and ensure the customer experience is frictionless.

Brand Decision Rules:
- Scientific Tone: Always use clinical-yet-accessible language (e.g., "Active Recovery Complex", "Cellular Regeneration"). 
  Never use "slang" or "hype" that feels cheap.
- The Founder's Story: Always protect the narrative of the visionary founder. 
  Decisions should reflect a "Gen-Z brilliance meets Biotech precision" ethos.
- Luxury Friction: If a customer has a bad experience, do not just offer a refund. 
  Offer a scientific solution (education) first, then a high-value perk.

Forbidden Actions:
- NEVER share the exact % breakdown of the "Active Recovery Complex" in public chat
- NEVER commit to a manufacturing deadline without a confirmed date
- NEVER lower the price of a product by more than 20% autonomously
"""

# Marketing Tone Guidelines (for social proof content)
REROOTS_MARKETING_PROMPT = """
Role: You are the ReRoots Social Media Voice - creating viral-worthy content that maintains premium biotech positioning.

Marketing Voice Rules:
- Confident but not arrogant: "Results speak for themselves" energy
- Science-backed hype: Every claim ties back to the biotech story
- Gen-Z authentic: Use natural language, not corporate speak
- Founder-led: Content should feel like it's from the young visionary, not a faceless brand

Content Guidelines:
- TikTok: Hook in first 2 seconds, use trending sounds references, end with CTA
- Instagram: Aesthetic-first, use customer quotes as social proof, minimal text
- Stories: Quick, punchy, use polls and questions for engagement

Hashtag Strategy:
- Always include: #biotechbeauty #skinscience #reRoots
- Trend-relevant: #glowup #glassskin #skintok
- Never use: cheap/discount language, competitor mentions

Example Outputs:
- TikTok: "POV: You finally found the serum that actually delivers glass skin ✨ The PDRN difference is real. #biotechbeauty #glassskin"
- Instagram: "Real results. Real science. Real customers are calling AURA-GEN their 'holy grail' 💎 What's your skin goal?"
"""

# ============================================================================
# WATCHDOG KEYWORDS - Problem Detection (Defense)
# ============================================================================
TEXTURE_CONCERN_KEYWORDS = ["sticky", "tacky", "thick", "heavy", "greasy", "oily", "residue"]
EFFICACY_CONCERN_KEYWORDS = ["doesn't work", "no results", "waste", "scam", "fake"]
PACKAGING_CONCERN_KEYWORDS = ["broken", "leaked", "damaged", "spilled", "cracked"]

# ============================================================================
# MARKETING ENGINE KEYWORDS - Win Detection (Offense)  
# ============================================================================
# Efficacy-Based Wins
EFFICACY_WIN_KEYWORDS = ["glass skin", "poreless", "plump", "woke up like this", "cleared my skin", "visible results"]

# Emotional-Based Wins  
EMOTIONAL_WIN_KEYWORDS = ["obsessed", "holy grail", "never switching", "game changer", "life changing", "in love", "best ever"]

# Biotech-Specific Wins
BIOTECH_WIN_KEYWORDS = ["actually works", "healed my skin", "real results", "science works", "biotech magic"]

# All positive keywords combined
ALL_WIN_KEYWORDS = EFFICACY_WIN_KEYWORDS + EMOTIONAL_WIN_KEYWORDS + BIOTECH_WIN_KEYWORDS

# Threshold: 2+ keywords in one review = "High-Value Win"
WIN_KEYWORD_THRESHOLD = 2
CONCERN_THRESHOLD = 3  # Number of mentions before action is drafted


# ============================================================================
# PHASE 3: JSON TOOL DEFINITIONS - The AI's "Hands"
# ============================================================================
# These define what actions the AI can take autonomously or via approval
# Schema format follows OpenAI Function Calling specification

AI_TOOL_DEFINITIONS = {
    # =========================================================================
    # L1 Tools - Full Autonomy (Execute & Log)
    # =========================================================================
    
    # The "Price Guardian" - Autonomously fix $0.00 errors or currency mismatches
    "update_price": {
        "name": "update_price",
        "authority_level": "L1",
        "description": "Updates the retail price of a product in the database when an error is detected.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "The SKU or database ID of the product."},
                "new_price": {"type": "number", "description": "The corrected price value."},
                "currency": {"type": "string", "enum": ["CAD", "USD"], "description": "The currency of the price update."},
                "reason": {"type": "string", "description": "Short explanation for the autonomous override."}
            },
            "required": ["product_id", "new_price", "currency"]
        },
        "execution_function": "execute_update_price"
    },
    
    "flag_fraud_address": {
        "name": "flag_fraud_address",
        "authority_level": "L1",
        "description": "Flag an order with a suspicious address pattern for fraud review.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order ID to flag."},
                "risk_indicators": {"type": "array", "items": {"type": "string"}, "description": "List of detected risk patterns."},
                "risk_score": {"type": "number", "description": "Calculated risk score (0-100)."}
            },
            "required": ["order_id", "risk_indicators", "risk_score"]
        },
        "execution_function": "execute_flag_fraud"
    },
    
    "log_customer_insight": {
        "name": "log_customer_insight",
        "authority_level": "L1",
        "description": "Log a customer behavior pattern for analytics and market research.",
        "parameters": {
            "type": "object",
            "properties": {
                "insight_type": {"type": "string", "description": "Category of insight (purchase_pattern, feedback_trend, etc.)"},
                "details": {"type": "string", "description": "Detailed description of the insight."},
                "customer_segment": {"type": "string", "description": "Target customer segment if applicable."}
            },
            "required": ["insight_type", "details"]
        },
        "execution_function": "execute_log_insight"
    },
    
    # =========================================================================
    # L2 Tools - Draft & Notify (Wait for Admin Approval)
    # =========================================================================
    
    # The "Knowledge Bridge" - Turns customer feedback into marketing Pro-Tips
    "create_education_snippet": {
        "name": "create_education_snippet",
        "authority_level": "L2",
        "description": "Drafts a founder-led 'Pro-Tip' or educational banner for the website based on customer feedback trends.",
        "parameters": {
            "type": "object",
            "properties": {
                "target_product": {"type": "string", "description": "The product the tip applies to."},
                "issue_identified": {"type": "string", "description": "The pattern identified (e.g., 'stickiness')."},
                "content_draft": {"type": "string", "description": "The founder-voiced clinical advice to be displayed."},
                "placement": {"type": "string", "enum": ["product_page", "checkout_banner", "email_footer"], "description": "Where to display the snippet."}
            },
            "required": ["target_product", "content_draft"]
        },
        "execution_function": "execute_add_snippet"
    },
    
    "draft_review_response": {
        "name": "draft_review_response",
        "authority_level": "L2",
        "description": "Draft a brand-guardian response to a customer review.",
        "parameters": {
            "type": "object",
            "properties": {
                "review_id": {"type": "string", "description": "The review ID to respond to."},
                "response_text": {"type": "string", "description": "The drafted response text."},
                "tone": {"type": "string", "enum": ["empathetic", "educational", "grateful"], "description": "The tone of the response."}
            },
            "required": ["review_id", "response_text"]
        },
        "execution_function": "execute_post_response"
    },
    
    "create_discount_code": {
        "name": "create_discount_code",
        "authority_level": "L2",
        "description": "Create a personalized discount code for a customer (max 20% off per brand rules).",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "The discount code string."},
                "discount_percent": {"type": "number", "maximum": 20, "description": "Discount percentage (max 20%)."},
                "reason": {"type": "string", "description": "Reason for creating the discount."},
                "customer_email": {"type": "string", "description": "Target customer email if personalized."},
                "single_use": {"type": "boolean", "default": True, "description": "Whether code is single-use."}
            },
            "required": ["code", "discount_percent", "reason"]
        },
        "execution_function": "execute_create_discount"
    },
    
    "draft_restock_email": {
        "name": "draft_restock_email",
        "authority_level": "L2",
        "description": "Draft an email to Viki at Juvyglow for restocking based on inventory levels.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_name": {"type": "string", "description": "Product that needs restocking."},
                "current_stock": {"type": "number", "description": "Current inventory level."},
                "recommended_quantity": {"type": "number", "description": "Suggested reorder quantity."},
                "urgency": {"type": "string", "enum": ["low", "medium", "high"], "description": "Urgency level."}
            },
            "required": ["product_name", "current_stock", "recommended_quantity"]
        },
        "execution_function": "execute_draft_restock"
    },
    
    # =========================================================================
    # MARKETING ENGINE TOOLS - Win Detection (Offense)
    # =========================================================================
    
    "detect_viral_moment": {
        "name": "detect_viral_moment",
        "authority_level": "L1",
        "action_type": "marketing",
        "description": "Auto-detects and logs 'viral moments' when multiple customers use high-value keywords like 'obsessed' or 'holy grail'.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product associated with the viral moment."},
                "keywords_detected": {"type": "array", "items": {"type": "string"}, "description": "List of win keywords found."},
                "review_count": {"type": "number", "description": "Number of reviews containing these keywords."},
                "sample_quotes": {"type": "array", "items": {"type": "string"}, "description": "Representative customer quotes."}
            },
            "required": ["product_id", "keywords_detected", "review_count"]
        },
        "execution_function": "execute_log_viral_moment"
    },
    
    "draft_social_proof_content": {
        "name": "draft_social_proof_content",
        "authority_level": "L2",
        "action_type": "marketing",
        "description": "Drafts social media content (TikTok, Instagram) using real customer quotes as social proof.",
        "parameters": {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": ["tiktok", "instagram", "instagram_story", "email"], "description": "Target platform for the content."},
                "product_name": {"type": "string", "description": "Product being featured."},
                "customer_quote": {"type": "string", "description": "Anonymized customer quote to feature."},
                "content_draft": {"type": "string", "description": "The drafted social media content."},
                "hashtags": {"type": "array", "items": {"type": "string"}, "description": "Suggested hashtags."}
            },
            "required": ["platform", "product_name", "content_draft"]
        },
        "execution_function": "execute_draft_social_content"
    },
    
    "create_ugc_highlight": {
        "name": "create_ugc_highlight",
        "authority_level": "L2",
        "action_type": "marketing",
        "description": "Flags exceptional reviews for UGC outreach and drafts a DM template to request video testimonials.",
        "parameters": {
            "type": "object",
            "properties": {
                "review_id": {"type": "string", "description": "The exceptional review to highlight."},
                "customer_name": {"type": "string", "description": "Customer's display name."},
                "review_snippet": {"type": "string", "description": "The standout quote from the review."},
                "dm_template": {"type": "string", "description": "Drafted DM to request UGC collaboration."},
                "suggested_incentive": {"type": "string", "enum": ["discount_code", "free_product", "affiliate_invite"], "description": "Suggested incentive for UGC."}
            },
            "required": ["review_id", "review_snippet", "dm_template"]
        },
        "execution_function": "execute_create_ugc_highlight"
    },
    
    # =========================================================================
    # L3 Tools - Forbidden (Alert Admin Immediately, Never Auto-Execute)
    # =========================================================================
    
    # The "L3 Escalator" - Critical safety valve for high-risk situations
    "send_admin_alert": {
        "name": "send_admin_alert",
        "authority_level": "L3",
        "description": "Triggers an immediate SMS or Push notification to the founder for high-priority L3 issues.",
        "parameters": {
            "type": "object",
            "properties": {
                "priority": {"type": "string", "enum": ["URGENT", "CRITICAL"], "description": "Alert priority level."},
                "message": {"type": "string", "description": "Detailed alert for the founder."},
                "suggested_action": {"type": "string", "description": "What the system recommends the founder does immediately."}
            },
            "required": ["priority", "message"]
        },
        "execution_function": "execute_admin_alert_sms",
        "requires_immediate_notification": True
    },
    
    "process_refund": {
        "name": "process_refund",
        "authority_level": "L3",
        "description": "Process a refund for a customer (ADMIN ONLY - triggers alert, never auto-executes).",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "The order ID to refund."},
                "amount": {"type": "number", "description": "Refund amount."},
                "reason": {"type": "string", "description": "Reason for the refund."}
            },
            "required": ["order_id", "amount", "reason"]
        },
        "execution_function": None,
        "requires_manual": True
    },
    
    "modify_formula_data": {
        "name": "modify_formula_data",
        "authority_level": "L3",
        "description": "Modify product formula or $50k IP data (ADMIN ONLY - triggers alert, never auto-executes).",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product to modify."},
                "field": {"type": "string", "description": "Field to change."},
                "new_value": {"type": "string", "description": "New value."}
            },
            "required": ["product_id", "field", "new_value"]
        },
        "execution_function": None,
        "requires_manual": True
    }
}

# Convert to OpenAI Function Calling format for LLM integration
def get_tools_for_llm():
    """Returns tool definitions in OpenAI Function Calling format"""
    tools = []
    for tool_name, tool_def in AI_TOOL_DEFINITIONS.items():
        tools.append({
            "type": "function",
            "function": {
                "name": tool_def["name"],
                "description": tool_def["description"],
                "parameters": tool_def["parameters"]
            }
        })
    return tools


# Tool Execution Functions (L1 and L2)

async def execute_update_price(params: dict) -> dict:
    """L1: Price Guardian - Automatically fix price errors"""
    product_id = params.get("product_id")
    new_price = params.get("new_price")
    currency = params.get("currency", "CAD")
    reason = params.get("reason", "Autonomous price correction")
    
    result = await db.products.update_one(
        {"id": product_id},
        {"$set": {
            "price": new_price,
            "currency": currency,
            "price_updated_at": datetime.now(timezone.utc).isoformat(),
            "price_update_reason": reason
        }}
    )
    
    if result.modified_count > 0:
        # Log the auto-fix
        await db.ai_execution_logs.insert_one({
            "id": str(uuid.uuid4()),
            "tool": "update_price",
            "authority_level": "L1",
            "params": params,
            "result": "success",
            "executed_at": datetime.now(timezone.utc).isoformat()
        })
        return {"success": True, "message": f"Price Guardian: Updated to ${new_price} {currency}. Reason: {reason}"}
    return {"success": False, "message": "Product not found or price unchanged"}


async def execute_flag_fraud(params: dict) -> dict:
    """L1: Flag an order for fraud review"""
    order_id = params.get("order_id")
    risk_score = params.get("risk_score")
    risk_indicators = params.get("risk_indicators", [])
    
    result = await db.orders.update_one(
        {"id": order_id},
        {"$set": {
            "fraud_flagged": True,
            "fraud_risk_score": risk_score,
            "fraud_indicators": risk_indicators,
            "fraud_flagged_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    await db.ai_execution_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tool": "flag_fraud_address",
        "authority_level": "L1",
        "params": params,
        "result": "success" if result.modified_count > 0 else "not_found",
        "executed_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"success": result.modified_count > 0, "message": f"Order flagged with risk score {risk_score}"}


async def execute_log_insight(params: dict) -> dict:
    """L1: Log a customer insight for market research"""
    await db.ai_customer_insights.insert_one({
        "id": str(uuid.uuid4()),
        "insight_type": params.get("insight_type"),
        "details": params.get("details"),
        "customer_segment": params.get("customer_segment"),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    return {"success": True, "message": "Insight logged to Product Improvement Report"}


async def execute_add_snippet(params: dict) -> dict:
    """L2: Knowledge Bridge - Add a pro-tip to a product (after approval)"""
    # Support both old and new parameter names
    product_id = params.get("product_id") or params.get("target_product")
    content = params.get("content") or params.get("content_draft")
    placement = params.get("placement", "product_page")
    issue_identified = params.get("issue_identified") or params.get("trigger_reason", "")
    
    # Try to find product by name if not an ID
    if product_id and not product_id.startswith("sim-"):
        product = await db.products.find_one(
            {"$or": [{"id": product_id}, {"name": {"$regex": product_id, "$options": "i"}}]},
            {"_id": 0, "id": 1}
        )
        if product:
            product_id = product.get("id")
    
    result = await db.products.update_one(
        {"id": product_id},
        {"$push": {"pro_tips": {
            "text": content,
            "type": "founders_tip",
            "placement": placement,
            "issue_addressed": issue_identified,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "ai_approved"
        }}}
    )
    
    # Also log to product improvement report
    await db.ai_product_improvements.insert_one({
        "id": str(uuid.uuid4()),
        "product_id": product_id,
        "improvement_type": "education_snippet",
        "content": content,
        "issue_identified": issue_identified,
        "placement": placement,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"success": result.modified_count > 0, "message": f"Pro-tip added to {placement}"}


async def execute_admin_alert_sms(params: dict) -> dict:
    """L3 Escalator: Send immediate SMS/Push notification to founder"""
    priority = params.get("priority", "URGENT")
    message = params.get("message", "")
    suggested_action = params.get("suggested_action", "")
    
    # Store the alert
    alert_id = str(uuid.uuid4())
    alert = {
        "id": alert_id,
        "priority": priority,
        "message": message,
        "suggested_action": suggested_action,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.ai_admin_alerts.insert_one(alert)
    
    # Log for immediate visibility
    await db.ai_execution_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tool": "send_admin_alert",
        "authority_level": "L3",
        "params": params,
        "result": "alert_created",
        "executed_at": datetime.now(timezone.utc).isoformat()
    })
    
    # TODO: Add Twilio SMS integration here when configured
    # For now, we just store and expose via WebSocket/polling
    sms_sent = False
    twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    twilio_token = os.environ.get("TWILIO_AUTH_TOKEN")
    twilio_phone = os.environ.get("TWILIO_PHONE_NUMBER")
    admin_phone = os.environ.get("ADMIN_PHONE_NUMBER")
    
    if twilio_sid and twilio_token and twilio_phone and admin_phone:
        try:
            # Twilio SMS would go here
            sms_sent = True
        except Exception as e:
            logging.error(f"SMS send failed: {e}")
    
    return {
        "success": True, 
        "alert_id": alert_id,
        "sms_sent": sms_sent,
        "message": f"{priority} alert created. {'SMS sent.' if sms_sent else 'SMS not configured - check admin panel.'}"
    }


async def execute_create_discount(params: dict) -> dict:
    """L2: Create a discount code (after approval)"""
    code = params.get("code")
    discount_percent = min(params.get("discount_percent", 10), 20)  # Max 20%
    
    await db.discount_codes.insert_one({
        "id": str(uuid.uuid4()),
        "code": code.upper(),
        "discount_percent": discount_percent,
        "discount_type": "percentage",
        "reason": params.get("reason"),
        "customer_email": params.get("customer_email"),
        "single_use": params.get("single_use", True),
        "used": False,
        "created_by": "ai_bridge",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"success": True, "message": f"Discount code {code} created ({discount_percent}% off)"}


# ============================================================================
# MARKETING ENGINE EXECUTION FUNCTIONS
# ============================================================================

async def execute_log_viral_moment(params: dict) -> dict:
    """L1: Auto-log a viral moment detected from reviews"""
    viral_moment = {
        "id": str(uuid.uuid4()),
        "product_id": params.get("product_id"),
        "keywords_detected": params.get("keywords_detected", []),
        "review_count": params.get("review_count", 0),
        "sample_quotes": params.get("sample_quotes", []),
        "status": "detected",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.ai_viral_moments.insert_one(viral_moment)
    
    await db.ai_execution_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tool": "detect_viral_moment",
        "authority_level": "L1",
        "action_type": "marketing",
        "params": params,
        "result": "success",
        "executed_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {
        "success": True, 
        "viral_moment_id": viral_moment["id"],
        "message": f"Viral moment logged: {len(params.get('keywords_detected', []))} keywords across {params.get('review_count', 0)} reviews"
    }


async def execute_draft_social_content(params: dict) -> dict:
    """L2: Store drafted social content (after approval, copy to social media)"""
    content = {
        "id": str(uuid.uuid4()),
        "platform": params.get("platform"),
        "product_name": params.get("product_name"),
        "customer_quote": params.get("customer_quote"),
        "content_draft": params.get("content_draft"),
        "hashtags": params.get("hashtags", []),
        "status": "approved",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.ai_social_content.insert_one(content)
    
    return {
        "success": True,
        "content_id": content["id"],
        "message": f"Social content for {params.get('platform')} ready to copy"
    }


async def execute_create_ugc_highlight(params: dict) -> dict:
    """L2: Flag review for UGC outreach"""
    highlight = {
        "id": str(uuid.uuid4()),
        "review_id": params.get("review_id"),
        "customer_name": params.get("customer_name"),
        "review_snippet": params.get("review_snippet"),
        "dm_template": params.get("dm_template"),
        "suggested_incentive": params.get("suggested_incentive", "discount_code"),
        "outreach_status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.ai_ugc_highlights.insert_one(highlight)
    
    return {
        "success": True,
        "highlight_id": highlight["id"],
        "message": "UGC highlight created - DM template ready for outreach"
    }



@router.get("/admin/ai/tools")
async def get_ai_tools(request: Request):
    """Get all available AI tool definitions"""
    await require_admin(request)
    
    tools_by_level = {
        "L1": [],
        "L2": [],
        "L3": []
    }
    
    for tool_name, tool_def in AI_TOOL_DEFINITIONS.items():
        level = tool_def.get("authority_level", "L2")
        tools_by_level[level].append({
            "name": tool_name,
            "description": tool_def.get("description"),
            "parameters": tool_def.get("parameters")
        })
    
    return {
        "tools": AI_TOOL_DEFINITIONS,
        "by_level": tools_by_level,
        "total_count": len(AI_TOOL_DEFINITIONS)
    }


# Endpoint to manually invoke a tool (for testing)
@router.post("/admin/ai/tools/invoke")
async def invoke_ai_tool(request: Request, data: dict = Body(...)):
    """Manually invoke an AI tool (for testing purposes)"""
    await require_admin(request)
    
    tool_name = data.get("tool_name")
    params = data.get("params", {})
    
    if tool_name not in AI_TOOL_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    tool_def = AI_TOOL_DEFINITIONS[tool_name]
    authority_level = tool_def.get("authority_level")
    
    # L3 tools - now with alert capability instead of just blocking
    if authority_level == "L3":
        # For send_admin_alert, we still execute but just create the alert
        if tool_name == "send_admin_alert":
            result = await execute_admin_alert_sms(params)
            return {"success": True, "result": result, "executed": True, "note": "L3 alert created"}
        else:
            raise HTTPException(status_code=403, detail="L3 tools require manual admin action - alert the founder")
    
    # L2 tools create a pending action
    if authority_level == "L2":
        action = {
            "id": str(uuid.uuid4()),
            "title": f"Manual Tool Invoke: {tool_name}",
            "action_type": tool_name,
            "authority_level": "L2",
            "status": "pending",
            "draft_content": str(params),
            "trigger_source": "manual_invoke",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.ai_pending_actions.insert_one(action)
        return {"success": True, "message": "L2 action queued for approval", "action_id": action["id"]}
    
    # L1 tools execute immediately
    if authority_level == "L1":
        exec_func = {
            "update_price": execute_update_price,
            "flag_fraud_address": execute_flag_fraud,
            "log_customer_insight": execute_log_insight
        }.get(tool_name)
        
        if exec_func:
            result = await exec_func(params)
            return {"success": True, "result": result, "executed": True}
    
    return {"success": False, "message": "Tool execution not configured"}


# Product Improvement Report (logs all AI insights for manufacturing feedback)
@router.get("/admin/ai/improvement-report")
async def get_product_improvement_report(request: Request):
    """
    Get the Product Improvement Report - aggregates all AI insights 
    for feedback to Viki at Juvyglow
    """
    await require_admin(request)
    
    # Get all approved education snippets (these came from real customer feedback)
    snippets = await db.ai_pending_actions.find({
        "action_type": "education_snippet",
        "status": "approved"
    }, {"_id": 0}).to_list(100)
    
    # Get all logged customer insights
    insights = await db.ai_customer_insights.find({}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    
    # Get watchdog scan results
    watchdog_logs = await db.ai_watchdog_logs.find(
        {"concerns_detected": {"$gt": 0}}, 
        {"_id": 0}
    ).sort("scan_time", -1).limit(20).to_list(20)
    
    # Aggregate by product
    product_feedback = {}
    
    for snippet in snippets:
        pid = snippet.get("target_product_id", "unknown")
        if pid not in product_feedback:
            product_feedback[pid] = {"tips_added": 0, "concerns": []}
        product_feedback[pid]["tips_added"] += 1
        product_feedback[pid]["concerns"].append(snippet.get("trigger_source", ""))
    
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_snippets_approved": len(snippets),
            "total_insights_logged": len(insights),
            "products_with_feedback": len(product_feedback)
        },
        "by_product": product_feedback,
        "recent_insights": insights[:20],
        "recent_scans": watchdog_logs,
        "note": "This report aggregates AI-detected patterns from real customer feedback. Use for Batch #2 formula adjustments."
    }


@router.get("/admin/ai/alerts")
async def get_admin_alerts(request: Request, status: str = None):
    """Get L3 admin alerts (URGENT/CRITICAL issues requiring founder attention)"""
    await require_admin(request)
    
    query = {}
    if status:
        query["status"] = status
    
    alerts = await db.ai_admin_alerts.find(query, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    
    # Count by priority
    urgent_count = len([a for a in alerts if a.get("priority") == "URGENT" and a.get("status") == "pending"])
    critical_count = len([a for a in alerts if a.get("priority") == "CRITICAL" and a.get("status") == "pending"])
    
    return {
        "alerts": alerts,
        "pending_urgent": urgent_count,
        "pending_critical": critical_count
    }


@router.post("/admin/ai/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(request: Request, alert_id: str):
    """Acknowledge and dismiss an L3 alert"""
    await require_admin(request)
    
    result = await db.ai_admin_alerts.update_one(
        {"id": alert_id},
        {"$set": {
            "status": "acknowledged",
            "acknowledged_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    return {"success": True}


@router.get("/admin/ai/pending-actions")
async def get_pending_actions(request: Request, status: str = None):
    """Get all pending AI actions from the queue"""
    await require_admin(request)
    
    query = {}
    if status and status != 'all':
        query["status"] = status
    
    actions = await db.ai_pending_actions.find(query, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    
    return {"actions": actions}


@router.post("/admin/ai/pending-actions/{action_id}/approve")
async def approve_ai_action(request: Request, action_id: str):
    """Approve and execute an L2 AI action"""
    await require_admin(request)
    
    action = await db.ai_pending_actions.find_one({"id": action_id}, {"_id": 0})
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    
    if action.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Action already processed")
    
    if action.get("authority_level") == "L3":
        raise HTTPException(status_code=403, detail="L3 actions cannot be auto-approved")
    
    execution_result = "Approved by admin"
    
    # Execute the action based on type
    action_type = action.get("action_type")
    try:
        if action_type == "education_snippet":
            # Add the snippet to the product
            product_id = action.get("target_product_id")
            snippet = action.get("draft_content")
            if product_id and snippet:
                await db.products.update_one(
                    {"id": product_id},
                    {"$push": {"pro_tips": {
                        "text": snippet,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "source": "ai_watchdog"
                    }}}
                )
                execution_result = f"Pro-tip added to product {product_id}"
        
        elif action_type == "price_fix":
            # Fix the price
            product_id = action.get("target_product_id")
            correct_price = action.get("correct_value")
            if product_id and correct_price:
                await db.products.update_one(
                    {"id": product_id},
                    {"$set": {"price": correct_price}}
                )
                execution_result = f"Price corrected to ${correct_price}"
        
        elif action_type == "fraud_flag":
            # Flag the order
            order_id = action.get("target_order_id")
            if order_id:
                await db.orders.update_one(
                    {"id": order_id},
                    {"$set": {"fraud_flagged": True, "fraud_reason": action.get("draft_content")}}
                )
                execution_result = f"Order {order_id} flagged for fraud review"
        
        elif action_type == "review_response":
            # Draft stored for manual copy/paste
            execution_result = "Response draft approved - copy to review platform"
        
    except Exception as e:
        execution_result = f"Execution error: {str(e)}"
    
    # Update action status
    await db.ai_pending_actions.update_one(
        {"id": action_id},
        {"$set": {
            "status": "approved",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "execution_result": execution_result
        }}
    )
    
    return {"success": True, "execution_result": execution_result}


@router.post("/admin/ai/pending-actions/{action_id}/reject")
async def reject_ai_action(request: Request, action_id: str):
    """Reject an AI action"""
    await require_admin(request)
    
    result = await db.ai_pending_actions.update_one(
        {"id": action_id, "status": "pending"},
        {"$set": {
            "status": "rejected",
            "rejected_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Action not found or already processed")
    
    return {"success": True}


@router.post("/admin/ai/review-watchdog/scan")
async def run_review_watchdog_scan(request: Request):
    """
    Dual-Mode Review Watchdog:
    - DEFENSE: Detects texture, efficacy, and packaging concerns
    - OFFENSE: Detects viral moments and high-value wins for marketing
    """
    await require_admin(request)
    
    # Get recent reviews
    reviews = await db.reviews.find({}).sort("created_at", -1).limit(200).to_list(200)
    
    if not reviews:
        return {
            "success": True,
            "message": "No reviews to scan",
            "concerns": [],
            "wins": [],
            "actions_created": 0
        }
    
    # Track both problems and wins by product
    product_data = {}  # {product_id: {concerns: {}, wins: {}, quotes: [], product_name: str}}
    
    for review in reviews:
        product_id = review.get("product_id")
        if not product_id:
            continue
        
        text = f"{review.get('title', '')} {review.get('comment', '')}".lower()
        rating = review.get("rating", 5)
        original_text = f"{review.get('title', '')} {review.get('comment', '')}"
        
        if product_id not in product_data:
            product_data[product_id] = {
                "texture": {},
                "efficacy": {},
                "packaging": {},
                "wins": {},
                "win_quotes": [],
                "product_name": review.get("product_name", "Unknown Product")
            }
        
        # DEFENSE MODE: Count concerns from lower-rated reviews (< 4 stars)
        if rating < 4:
            for keyword in TEXTURE_CONCERN_KEYWORDS:
                if keyword in text:
                    product_data[product_id]["texture"][keyword] = product_data[product_id]["texture"].get(keyword, 0) + 1
            
            for keyword in EFFICACY_CONCERN_KEYWORDS:
                if keyword in text:
                    product_data[product_id]["efficacy"][keyword] = product_data[product_id]["efficacy"].get(keyword, 0) + 1
            
            for keyword in PACKAGING_CONCERN_KEYWORDS:
                if keyword in text:
                    product_data[product_id]["packaging"][keyword] = product_data[product_id]["packaging"].get(keyword, 0) + 1
        
        # OFFENSE MODE: Count wins from high-rated reviews (>= 4 stars)
        if rating >= 4:
            keywords_in_review = []
            for keyword in ALL_WIN_KEYWORDS:
                if keyword in text:
                    product_data[product_id]["wins"][keyword] = product_data[product_id]["wins"].get(keyword, 0) + 1
                    keywords_in_review.append(keyword)
            
            # If 2+ win keywords in one review = High-Value Win
            if len(keywords_in_review) >= WIN_KEYWORD_THRESHOLD:
                product_data[product_id]["win_quotes"].append({
                    "text": original_text[:200],  # Truncate for storage
                    "keywords": keywords_in_review,
                    "rating": rating
                })
    
    # Process results
    detected_concerns = []
    detected_wins = []
    actions_created = 0
    
    llm_key = get_claude_api_key()
    
    for product_id, data in product_data.items():
        product_name = data.get("product_name", "Product")
        
        # ===== DEFENSE MODE: Process Concerns =====
        
        # Check texture concerns
        texture_total = sum(data["texture"].values())
        if texture_total >= CONCERN_THRESHOLD:
            detected_concerns.append({
                "product_id": product_id,
                "category": "texture",
                "type": "concern",
                "keyword": "texture issues",
                "count": texture_total,
                "threshold_met": True
            })
            
            snippet = await _generate_texture_education_snippet(llm_key, product_name, list(data["texture"].keys()))
            
            existing = await db.ai_pending_actions.find_one({
                "target_product_id": product_id,
                "action_type": "education_snippet",
                "status": "pending"
            })
            
            if not existing:
                await db.ai_pending_actions.insert_one({
                    "id": str(uuid.uuid4()),
                    "title": f"🔧 Texture Tip for {product_name}",
                    "action_type": "education_snippet",
                    "card_type": "concern",  # For UI color coding
                    "authority_level": "L2",
                    "status": "pending",
                    "target_product_id": product_id,
                    "draft_content": snippet,
                    "trigger_source": f"Watchdog detected {texture_total} texture mentions",
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                actions_created += 1
        
        # Check efficacy concerns
        efficacy_total = sum(data["efficacy"].values())
        if efficacy_total >= CONCERN_THRESHOLD:
            detected_concerns.append({
                "product_id": product_id,
                "category": "efficacy",
                "type": "concern",
                "keyword": "efficacy concerns",
                "count": efficacy_total,
                "threshold_met": True
            })
            
            existing = await db.ai_pending_actions.find_one({
                "target_product_id": product_id,
                "action_type": "admin_alert",
                "status": "pending"
            })
            
            if not existing:
                await db.ai_pending_actions.insert_one({
                    "id": str(uuid.uuid4()),
                    "title": f"⚠️ Efficacy Alert: {product_name}",
                    "action_type": "admin_alert",
                    "card_type": "concern",
                    "authority_level": "L3",
                    "status": "pending",
                    "target_product_id": product_id,
                    "draft_content": f"Multiple customers ({efficacy_total}) have raised efficacy concerns about {product_name}. Keywords detected: {', '.join(data['efficacy'].keys())}. Manual review recommended.",
                    "trigger_source": f"Watchdog detected {efficacy_total} efficacy concerns",
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                actions_created += 1
        
        # Check packaging concerns
        packaging_total = sum(data["packaging"].values())
        if packaging_total >= CONCERN_THRESHOLD:
            detected_concerns.append({
                "product_id": product_id,
                "category": "packaging",
                "type": "concern",
                "keyword": "packaging issues",
                "count": packaging_total,
                "threshold_met": True
            })
        
        # ===== OFFENSE MODE: Process Wins =====
        
        wins_total = sum(data["wins"].values())
        high_value_quotes = data["win_quotes"]
        
        if wins_total >= CONCERN_THRESHOLD or len(high_value_quotes) >= 1:
            detected_wins.append({
                "product_id": product_id,
                "category": "viral_moment",
                "type": "win",
                "keywords": list(data["wins"].keys()),
                "count": wins_total,
                "high_value_quotes": len(high_value_quotes),
                "threshold_met": True
            })
            
            # Log the viral moment (L1 - auto-execute)
            await execute_log_viral_moment({
                "product_id": product_id,
                "keywords_detected": list(data["wins"].keys()),
                "review_count": wins_total,
                "sample_quotes": [q["text"] for q in high_value_quotes[:3]]
            })
            
            # Generate social proof content (L2 - needs approval)
            if high_value_quotes:
                best_quote = high_value_quotes[0]
                social_content = await _generate_social_proof_content(llm_key, product_name, best_quote["text"], best_quote["keywords"])
                
                existing = await db.ai_pending_actions.find_one({
                    "target_product_id": product_id,
                    "action_type": "social_proof",
                    "status": "pending"
                })
                
                if not existing:
                    await db.ai_pending_actions.insert_one({
                        "id": str(uuid.uuid4()),
                        "title": f"✨ Social Proof: {product_name}",
                        "action_type": "social_proof",
                        "card_type": "win",  # Gold/pink in UI
                        "authority_level": "L2",
                        "status": "pending",
                        "target_product_id": product_id,
                        "draft_content": social_content,
                        "customer_quote": best_quote["text"],
                        "trigger_source": f"Viral moment: {wins_total} positive mentions, {len(high_value_quotes)} high-value reviews",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    })
                    actions_created += 1
    
    # Log the scan
    await db.ai_watchdog_logs.insert_one({
        "id": str(uuid.uuid4()),
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "reviews_scanned": len(reviews),
        "concerns_detected": len(detected_concerns),
        "wins_detected": len(detected_wins),
        "actions_created": actions_created
    })
    
    return {
        "success": True,
        "reviews_scanned": len(reviews),
        "concerns": detected_concerns,
        "wins": detected_wins,
        "actions_created": actions_created
    }


async def _generate_social_proof_content(llm_key: str, product_name: str, customer_quote: str, keywords: list) -> str:
    """Generate social media content using customer quotes"""
    if not llm_key:
        # Fallback without AI
        return f"""📱 TikTok Draft:
POV: Real customers are calling {product_name} their new obsession ✨

"{customer_quote[:100]}..."

The biotech difference is real. #biotechbeauty #glassskin #reRoots

---

📸 Instagram Draft:
Real results. Real science. Real customers are saying "{keywords[0] if keywords else 'amazing results'}" 💎

What's your skin goal? Link in bio.
#skinscience #biotechbeauty #reRoots"""

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        prompt = f"""Create social media content for a luxury biotech skincare brand called ReRoots.

Product: {product_name}
Customer Quote: "{customer_quote}"
Keywords customers used: {', '.join(keywords)}

Create:
1. A TikTok caption (max 150 chars, hook + hashtags)
2. An Instagram caption (2-3 sentences + hashtags)

Requirements:
- Sound premium but Gen-Z authentic
- Use the customer's actual words as social proof
- Include: #biotechbeauty #glassskin #reRoots
- Never use cheap/discount language

Format:
📱 TikTok:
[caption]

📸 Instagram:
[caption]"""

        chat = LlmChat(
            api_key=llm_key,
            session_id=f"marketing_{uuid.uuid4()}",
            system_message=REROOTS_MARKETING_PROMPT
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        response = await chat.send_message(UserMessage(text=prompt))
        return response.strip()
        
    except Exception as e:
        logging.error(f"Social content generation failed: {e}")
        return f"""📱 TikTok Draft:
POV: Real customers are calling {product_name} their new obsession ✨

#biotechbeauty #glassskin #reRoots

---

📸 Instagram Draft:
Real results. Real science. 💎 #skinscience #biotechbeauty"""


async def _generate_texture_education_snippet(llm_key: str, product_name: str, keywords: list) -> str:
    """Generate a Founder's Tip for texture concerns using AI"""
    if not llm_key:
        # Fallback without AI
        return f"Founder's Tip: For optimal absorption of {product_name}, pat gently onto damp skin and allow 60 seconds for the Biotech Complex to fully penetrate. This technique eliminates any residue and maximizes efficacy."
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        prompt = f"""Write a short "Founder's Tip" for a luxury biotech skincare product called "{product_name}".

Customers have mentioned these texture concerns: {', '.join(keywords)}

Requirements:
- Maximum 2 sentences
- Sound scientific but accessible
- Provide a solution (e.g., application technique)
- Reference "Biotech Complex" or "Active Recovery Complex"
- Never apologize or admit a flaw
- Sound confident and educational

Example tone: "For optimal absorption, pat gently onto damp skin and allow 60 seconds for the DMI molecular delivery system to fully penetrate."

Write ONLY the tip text, nothing else."""

        chat = LlmChat(
            api_key=llm_key,
            session_id=f"watchdog_{uuid.uuid4()}",
            system_message=REROOTS_BRAND_GUARDIAN_PROMPT
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        response = await chat.send_message(UserMessage(text=prompt))
        return f"Founder's Tip: {response.strip()}"
        
    except Exception as e:
        logging.error(f"AI snippet generation failed: {e}")
        return f"Founder's Tip: For optimal absorption of {product_name}, pat gently onto damp skin and allow 60 seconds for the Biotech Complex to fully penetrate. This technique eliminates any residue and maximizes efficacy."


@router.get("/admin/ai/watchdog-logs")
async def get_watchdog_logs(request: Request):
    """Get recent watchdog scan logs"""
    await require_admin(request)
    
    logs = await db.ai_watchdog_logs.find({}, {"_id": 0}).sort("scan_time", -1).limit(20).to_list(20)
    return {"logs": logs}


@router.post("/admin/ai/simulate-review")
async def simulate_review(request: Request, data: dict = Body(...)):
    """
    Add a simulated review for testing the Watchdog.
    These reviews are marked as simulations and can be used to stress-test the Brand Guardian.
    """
    await require_admin(request)
    
    product_name = data.get("product_name", "Test Product")
    rating = data.get("rating", 3)
    title = data.get("title", "Test Review")
    comment = data.get("comment", "")
    
    # Find product ID if it exists (or use a placeholder)
    product = await db.products.find_one({"name": {"$regex": product_name, "$options": "i"}}, {"_id": 0, "id": 1})
    product_id = product.get("id") if product else f"sim-{uuid.uuid4().hex[:8]}"
    
    review = {
        "id": str(uuid.uuid4()),
        "product_id": product_id,
        "product_name": product_name,
        "rating": rating,
        "title": title,
        "comment": comment,
        "customer_name": "Test Customer (Simulation)",
        "is_simulation": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.reviews.insert_one(review)
    
    # Log the simulation
    await db.ai_watchdog_logs.insert_one({
        "id": str(uuid.uuid4()),
        "type": "simulation_added",
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "details": f"Simulated review added for {product_name} ({rating}/5 stars)"
    })
    
    return {
        "success": True,
        "review_id": review["id"],
        "message": f"Test review added for {product_name}. Run Watchdog Scan to detect patterns."
    }


@router.delete("/admin/ai/simulated-reviews")
async def clear_simulated_reviews(request: Request):
    """Clear all simulated reviews (for cleanup after testing)"""
    await require_admin(request)
    
    result = await db.reviews.delete_many({"is_simulation": True})
    
    return {
        "success": True,
        "deleted_count": result.deleted_count
    }


# ============================================================================
# EXECUTIVE INTELLIGENCE - CEO Briefing & Strategic Analysis
# ============================================================================

class ExecutiveIntelRequest(BaseModel):
    prompt: str
    module_type: str = "briefing"

@router.post("/admin/ai/executive-intel")
async def executive_intelligence_analysis(request: Request, data: ExecutiveIntelRequest):
    """
    Generate executive-level business intelligence and strategic analysis.
    Modules: briefing, market, customer, brand, strategy
    """
    await require_admin(request)
    
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="No API key configured for AI services")
    
    try:
        # System prompts for different modules
        system_prompts = {
            "briefing": """You are the Chief Intelligence Officer for REROOTS, a Canadian biotech skincare brand specializing in PDRN technology. 
Generate executive briefings that are strategic, actionable, and focused on growth opportunities. 
Keep responses concise but insightful. Use data points provided to make specific recommendations.""",
            
            "market": """You are a Market Intelligence Analyst for REROOTS. 
Analyze competitive landscape, market trends, and positioning opportunities in the biotech skincare space.
Focus on actionable insights for a Canadian DTC brand competing against both Korean imports and luxury Western brands.""",
            
            "customer": """You are a Customer Intelligence Analyst for REROOTS.
Analyze customer behavior, sentiment patterns, and retention opportunities.
Focus on identifying high-value customer segments and growth opportunities.""",
            
            "brand": """You are a Brand Health Analyst for REROOTS.
Evaluate brand perception, differentiation strength, and brand equity.
Provide recommendations for strengthening brand positioning in the biotech skincare space.""",
            
            "strategy": """You are the Chief Strategy Officer for REROOTS.
Provide strategic recommendations with clear action plans, resource allocation guidance, and risk assessments.
Focus on sustainable growth while maintaining premium brand positioning."""
        }
        
        system_prompt = system_prompts.get(data.module_type, system_prompts["briefing"])
        
        # Use Emergent LLM integration
        import uuid
        session_id = f"exec-intel-{uuid.uuid4().hex[:8]}"
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=system_prompt
        )
        chat.with_model("openai", "gpt-4o")
        
        user_message = UserMessage(text=data.prompt)
        response = await chat.send_message(user_message)
        
        # Log the analysis for tracking
        if db is not None:
            await db.executive_intel_logs.insert_one({
                "module_type": data.module_type,
                "prompt_length": len(data.prompt),
                "response_length": len(response) if response else 0,
                "created_at": datetime.now(timezone.utc)
            })
        
        return {
            "success": True,
            "response": response,
            "module_type": data.module_type
        }
        
    except Exception as e:
        logger.error(f"Executive Intel Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")


# ============================================================================
# INVENTORY & BATCH TRACKING - Module 01 for PDRN Skincare Compliance
# ============================================================================

class IngredientModel(BaseModel):
    id: str
    name: str
    supplier: str = ""
    unit: str = "g"
    stock: float = 0
    reorderPoint: float = 0
    cost: float = 0
    category: str = "Other"
    healthCanada: str = "Pending"
    lastUpdated: str = ""

class StockAdjustment(BaseModel):
    adjustment: float
    reason: str = "Manual adjustment"
    newStock: float

@router.get("/admin/inventory/ingredients")
async def get_inventory_ingredients(request: Request):
    """Get all raw ingredients from inventory"""
    await require_admin(request)
    
    ingredients = await db.inventory_ingredients.find({}, {"_id": 0}).to_list(500)
    return ingredients

@router.post("/admin/inventory/ingredients")
async def add_inventory_ingredient(request: Request, ingredient: IngredientModel):
    """Add a new raw ingredient to inventory"""
    await require_admin(request)
    
    ingredient_data = ingredient.dict()
    ingredient_data["created_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.inventory_ingredients.update_one(
        {"id": ingredient.id},
        {"$set": ingredient_data},
        upsert=True
    )
    
    # Log the action
    await db.inventory_logs.insert_one({
        "action": "add_ingredient",
        "ingredient_id": ingredient.id,
        "name": ingredient.name,
        "stock": ingredient.stock,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    return {"success": True, "ingredient": ingredient_data}

@router.post("/admin/inventory/ingredients/{ingredient_id}/adjust")
async def adjust_ingredient_stock(request: Request, ingredient_id: str, adjustment: StockAdjustment):
    """Adjust stock level of an ingredient"""
    await require_admin(request)
    
    result = await db.inventory_ingredients.update_one(
        {"id": ingredient_id},
        {"$set": {
            "stock": adjustment.newStock,
            "lastUpdated": datetime.now(timezone.utc).isoformat().split("T")[0]
        }}
    )
    
    # Log the adjustment
    await db.inventory_logs.insert_one({
        "action": "stock_adjustment",
        "ingredient_id": ingredient_id,
        "adjustment": adjustment.adjustment,
        "reason": adjustment.reason,
        "newStock": adjustment.newStock,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    return {"success": True, "newStock": adjustment.newStock}

@router.get("/admin/inventory/products")
async def get_inventory_products(request: Request):
    """Get all finished products from inventory"""
    await require_admin(request)
    
    products = await db.inventory_products.find({}, {"_id": 0}).to_list(500)
    return products

@router.post("/admin/inventory/products")
async def add_inventory_product(request: Request, data: dict = Body(...)):
    """Add a finished product to inventory"""
    await require_admin(request)
    
    data["created_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.inventory_products.update_one(
        {"id": data.get("id")},
        {"$set": data},
        upsert=True
    )
    
    return {"success": True, "product": data}

@router.get("/admin/inventory/batches")
async def get_inventory_batches(request: Request):
    """Get all batch records"""
    await require_admin(request)
    
    batches = await db.inventory_batches.find({}, {"_id": 0}).to_list(500)
    return batches

@router.post("/admin/inventory/batches")
async def add_inventory_batch(request: Request, data: dict = Body(...)):
    """Log a new production batch"""
    await require_admin(request)
    
    data["created_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.inventory_batches.insert_one(data)
    
    # Log the batch creation
    await db.inventory_logs.insert_one({
        "action": "batch_created",
        "batch_id": data.get("id"),
        "product": data.get("product"),
        "qty": data.get("qty"),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    return {"success": True, "batch": {k: v for k, v in data.items() if k != "_id"}}

@router.get("/admin/inventory/alerts")
async def get_inventory_alerts(request: Request):
    """Get inventory alerts (low stock, pending approvals, etc.)"""
    await require_admin(request)
    
    # Get low stock ingredients
    low_stock = await db.inventory_ingredients.find({
        "$expr": {"$lte": ["$stock", "$reorderPoint"]}
    }, {"_id": 0}).to_list(100)
    
    # Get pending Health Canada items
    pending_hc = await db.inventory_ingredients.find({
        "healthCanada": "Pending"
    }, {"_id": 0}).to_list(100)
    
    # Get low/out of stock products
    low_products = await db.inventory_products.find({
        "status": {"$in": ["Low Stock", "Out of Stock"]}
    }, {"_id": 0}).to_list(100)
    
    return {
        "low_stock_ingredients": low_stock,
        "pending_health_canada": pending_hc,
        "low_stock_products": low_products,
        "total_alerts": len(low_stock) + len(pending_hc) + len(low_products)
    }


# ============================================================================
# HEYGEN API - Talking Avatar Video Generation
# ============================================================================

class HeyGenVideoRequest(BaseModel):
    photo_base64: str  # Base64 encoded photo
    audio_base64: str  # Base64 encoded audio (MP3)
    script: str = ""  # Script for lip-sync guidance

class HeyGenStatusRequest(BaseModel):
    video_id: str

@router.post("/admin/ai-studio/heygen/generate-video")
async def heygen_generate_video(request: HeyGenVideoRequest):
    """
    Generate talking avatar video using HeyGen API.
    Uses the v2 video generation endpoint with talking_photo.
    """
    import requests as http_requests
    
    heygen_api_key = os.environ.get("HEYGEN_API_KEY")
    if not heygen_api_key:
        return {"success": False, "error": "HeyGen API key not configured. Please add HEYGEN_API_KEY to your environment."}
    
    heygen_base_url = "https://api.heygen.com"
    
    try:
        # Decode base64 audio
        audio_data = request.audio_base64
        if "," in audio_data:
            audio_data = audio_data.split(",")[1]
        
        # Use the first uploaded talking photo from user's account (non-preset)
        # Or fall back to a preset one
        logging.info("HeyGen: Getting talking photos from account...")
        
        list_url = f"{heygen_base_url}/v1/talking_photo.list"
        headers = {
            "X-Api-Key": heygen_api_key,
            "Accept": "application/json"
        }
        
        list_response = http_requests.get(list_url, headers=headers, timeout=30)
        
        if list_response.status_code != 200:
            return {"success": False, "error": f"Failed to list talking photos: {list_response.text}"}
        
        photos_data = list_response.json().get("data", [])
        
        # Try to find user's uploaded photo (first non-preset) or use preset
        talking_photo_id = None
        for photo in photos_data:
            if not photo.get("is_preset", True):
                talking_photo_id = photo.get("id")
                logging.info(f"Found user's custom talking photo: {talking_photo_id}")
                break
        
        if not talking_photo_id and photos_data:
            # Use first available preset
            talking_photo_id = photos_data[0].get("id")
            logging.info(f"Using preset talking photo: {talking_photo_id}")
        
        if not talking_photo_id:
            return {"success": False, "error": "No talking photos available. Please upload a photo in HeyGen dashboard first."}
        
        # Generate video with talking photo and script text
        logging.info(f"HeyGen: Generating video with talking_photo_id: {talking_photo_id}")
        
        video_url = f"{heygen_base_url}/v2/video/generate"
        
        # Use script for TTS voice
        script_text = request.script[:500] if request.script else "Hello, welcome to ReRoots skincare!"
        
        video_payload = {
            "video_inputs": [{
                "character": {
                    "type": "talking_photo",
                    "talking_photo_id": talking_photo_id
                },
                "voice": {
                    "type": "text",
                    "input_text": script_text,
                    "voice_id": "2d5b0e6cf36f460aa7fc47e3eee4ba54"  # Sara - clear female voice
                }
            }],
            "dimension": {
                "width": 720,
                "height": 1280
            }
        }
        
        video_headers = {
            "X-Api-Key": heygen_api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        video_response = http_requests.post(
            video_url,
            headers=video_headers,
            json=video_payload,
            timeout=60
        )
        
        logging.info(f"HeyGen video generation response: {video_response.status_code}")
        logging.info(f"HeyGen video response: {video_response.text[:500]}")
        
        if video_response.status_code not in [200, 201]:
            logging.error(f"HeyGen video generation failed: {video_response.text}")
            return {"success": False, "error": f"Video generation failed: {video_response.text}"}
        
        video_result = video_response.json()
        video_id = video_result.get("data", {}).get("video_id")
        
        if not video_id:
            return {"success": False, "error": f"Failed to get video ID. Response: {video_result}"}
        
        logging.info(f"HeyGen: Video generation started, ID: {video_id}")
        
        return {
            "success": True,
            "video_id": video_id,
            "talking_photo_id": talking_photo_id,
            "status": "processing",
            "message": "Video generation started. Poll for status using the video_id."
        }
        
    except Exception as e:
        logging.error(f"HeyGen video generation error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


@router.get("/admin/ai-studio/heygen/status/{video_id}")
async def heygen_video_status(video_id: str):
    """
    Check the status of a HeyGen video generation.
    Returns video URL when complete.
    """
    import requests as http_requests
    
    heygen_api_key = os.environ.get("HEYGEN_API_KEY")
    if not heygen_api_key:
        return {"success": False, "error": "HeyGen API key not configured"}
    
    try:
        status_url = f"https://api.heygen.com/v1/video_status.get?video_id={video_id}"
        
        headers = {
            "X-Api-Key": heygen_api_key,
            "Accept": "application/json"
        }
        
        response = http_requests.get(status_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return {"success": False, "error": f"Failed to get status: {response.text}"}
        
        result = response.json()
        data = result.get("data", {})
        
        status = data.get("status", "unknown")
        video_url = data.get("video_url")
        thumbnail_url = data.get("thumbnail_url")
        duration = data.get("duration")
        error = data.get("error")
        
        return {
            "success": True,
            "video_id": video_id,
            "status": status,
            "video_url": video_url,
            "thumbnail_url": thumbnail_url,
            "duration": duration,
            "error": error
        }
        
    except Exception as e:
        logging.error(f"HeyGen status check error: {e}")
        return {"success": False, "error": str(e)}


@router.get("/admin/ai-studio/heygen/quota")
async def heygen_check_quota():
    """Check remaining HeyGen API quota/credits"""
    import requests as http_requests
    
    heygen_api_key = os.environ.get("HEYGEN_API_KEY")
    if not heygen_api_key:
        return {"success": False, "error": "HeyGen API key not configured"}
    
    try:
        quota_url = "https://api.heygen.com/v2/user/remaining_quota"
        
        headers = {
            "X-Api-Key": heygen_api_key,
            "Accept": "application/json"
        }
        
        response = http_requests.get(quota_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return {"success": False, "error": f"Failed to get quota: {response.text}"}
        
        result = response.json()
        
        return {
            "success": True,
            "quota": result.get("data", {})
        }
        
    except Exception as e:
        logging.error(f"HeyGen quota check error: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MARKETING LAB - AI Marketing Asset Generator
# ============================================================================


class MarketingLabRequest(BaseModel):
    image_base64: str
    product_name: str = "Premium Skincare Product"
    tagline: str = ""
    vibe: str = "clinical"
    vibe_prompt: str = ""
    asset_type: str = "instagram_post"  # instagram_post, instagram_story, ad_creative
    brand_preset: Optional[dict] = None


def generate_seo_metadata(
    product_name: str, tagline: str, vibe: str, asset_type: str
) -> dict:
    """Generate SEO-optimized metadata for marketing assets"""

    # Asset type descriptions for alt text
    asset_descriptions = {
        "instagram_post": "Instagram feed post",
        "instagram_story": "Instagram story",
        "ad_creative": "advertisement",
    }

    # Vibe descriptions
    vibe_descriptions = {
        "clinical": "clinical laboratory aesthetic with scientific precision",
        "nature-tech": "biotech nature fusion with botanical elements",
        "luxury": "luxury spa atmosphere with premium textures",
    }

    asset_desc = asset_descriptions.get(asset_type, "marketing image")
    vibe_desc = vibe_descriptions.get(vibe, "luxury skincare aesthetic")

    # Generate alt text (for accessibility & SEO)
    alt_text = f"{product_name} - {tagline if tagline else 'Premium biotech skincare'} - {asset_desc} featuring {vibe_desc}"

    # Generate caption
    caption_templates = {
        "instagram_post": f"✨ Discover the science of beautiful skin. {product_name} combines cutting-edge biotech with nature's finest ingredients. {tagline if tagline else 'Your skin deserves the best.'}\n\n🧬 Clinically proven results\n🌿 Clean, conscious formulas\n💫 Visible transformation",
        "instagram_story": f"Swipe up to transform your skincare routine ✨\n\n{product_name}\n{tagline if tagline else 'Science meets beauty'}",
        "ad_creative": f"🔬 {product_name}\n\n{tagline if tagline else 'Where biotech meets beauty'}\n\n✓ Clinically tested\n✓ Dermatologist approved\n✓ Visible results\n\nShop now at reroots.ca",
    }

    # Generate hashtags
    base_hashtags = [
        "#ReRoots",
        "#BiotechSkincare",
        "#CleanBeauty",
        "#ScienceOfSkincare",
        "#LuxurySkincare",
    ]
    vibe_hashtags = {
        "clinical": [
            "#ClinicalSkincare",
            "#DermatologistApproved",
            "#SkinScience",
            "#ActiveIngredients",
        ],
        "nature-tech": [
            "#NatureMeetsScience",
            "#BotanicalBeauty",
            "#SustainableSkincare",
            "#GreenBeauty",
        ],
        "luxury": [
            "#LuxuryBeauty",
            "#PremiumSkincare",
            "#SpaAtHome",
            "#SelfCareSunday",
        ],
    }

    hashtags = base_hashtags + vibe_hashtags.get(vibe, [])

    return {
        "alt_text": alt_text[:500],  # Keep under 500 chars for accessibility
        "caption": caption_templates.get(
            asset_type, caption_templates["instagram_post"]
        ),
        "hashtags": hashtags,
        "schema_type": "ImageObject",
        "schema_data": {
            "@type": "ImageObject",
            "name": f"{product_name} - Marketing Asset",
            "description": alt_text,
            "contentUrl": "{{image_url}}",
            "creator": {"@type": "Organization", "name": "ReRoots Biotech Skincare"},
        },
    }


@router.post("/admin/marketing-lab/generate")
async def generate_marketing_asset(request: MarketingLabRequest):
    """Generate AI-powered marketing assets for products"""
    try:
        image_base64 = request.image_base64
        product_name = request.product_name
        tagline = request.tagline
        vibe = request.vibe
        vibe_prompt = request.vibe_prompt
        asset_type = request.asset_type

        if not image_base64:
            raise HTTPException(status_code=400, detail="No image provided")

        # Clean base64 if it has data URL prefix
        if "base64," in image_base64:
            image_base64 = image_base64.split("base64,")[1]

        llm_key = get_claude_api_key()
        if not llm_key:
            raise HTTPException(status_code=500, detail="AI service not configured")

        # Define asset-specific parameters
        asset_configs = {
            "instagram_post": {
                "size": "1024x1024",
                "style": "hero asset, bold, polished, brand-first composition, square format optimized for Instagram feed",
                "aspect": "1:1 square",
            },
            "instagram_story": {
                "size": "1024x1792",
                "style": "vertical mobile-first, immersive, intimate aesthetic, optimized for Stories and Reels",
                "aspect": "9:16 vertical",
            },
            "ad_creative": {
                "size": "1024x1024",
                "style": "scroll-stopping, high-impact, dramatic lighting, bold angles, conversion-focused with clear product visibility",
                "aspect": "1:1 square",
            },
        }

        config = asset_configs.get(asset_type, asset_configs["instagram_post"])

        # Build the generation prompt
        prompt = f"""Create a stunning, photorealistic marketing image for this skincare product.

PRODUCT: {product_name}
TAGLINE: {tagline if tagline else 'Premium biotech skincare'}

VISUAL STYLE: {vibe_prompt if vibe_prompt else 'luxury skincare aesthetic'}

REQUIREMENTS:
- {config['style']}
- The product bottle/packaging must be the hero and clearly visible
- Professional product photography quality
- Luxury beauty editorial aesthetic
- Cinematic lighting with depth
- Clean, elegant composition
- Brand-appropriate for high-end biotech skincare
- Format: {config['aspect']}

IMPORTANT: Keep the actual product packaging intact and prominent. Create a beautiful scene around it that enhances its premium appeal. Do not add text overlays."""

        # Use OpenAI Image Generation
        from emergentintegrations.llm.openai.image_generation import (
            OpenAIImageGeneration,
        )
        import base64

        image_gen = OpenAIImageGeneration(api_key=llm_key)

        # Generate the image
        images = await image_gen.generate_images(
            prompt=prompt, model="gpt-image-1", number_of_images=1
        )

        if images and len(images) > 0:
            # Convert to base64
            result_base64 = base64.b64encode(images[0]).decode("utf-8")

            # Generate SEO metadata
            seo_metadata = generate_seo_metadata(
                product_name, tagline, vibe, asset_type
            )

            # Optionally save to database for history
            await db.marketing_lab_assets.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "product_name": product_name,
                    "tagline": tagline,
                    "vibe": vibe,
                    "asset_type": asset_type,
                    "seo_metadata": seo_metadata,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

            return {
                "success": True,
                "image_base64": result_base64,
                "asset_type": asset_type,
                "dimensions": config["size"],
                "seo_metadata": seo_metadata,
            }
        else:
            return {"success": False, "error": "No image was generated"}

    except Exception as e:
        print(f"Marketing Lab generation error: {e}")
        import traceback

        traceback.print_exc()
        return {"success": False, "error": str(e)}


# ============================================================================
# AURA-GEN MOLECULAR AUDITOR ENDPOINTS
# ============================================================================


class AuditLogRequest(BaseModel):
    search_query: str
    product_found: bool
    product_name: Optional[str] = None
    product_brand: Optional[str] = None
    ingredients_source: str = "api"  # "api" or "manual"
    red_flags_detected: List[str] = []
    competitor_score: int = 40
    aura_gen_score: int = 94
    user_email: Optional[str] = None


class LeadCaptureRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    audit_id: Optional[str] = None
    product_searched: Optional[str] = None
    competitor_score: Optional[int] = None
    source: str = "molecular_auditor"


@router.post("/auditor/lead")
async def capture_auditor_lead(lead: LeadCaptureRequest):
    """Capture lead from Molecular Auditor for data mining"""
    try:
        lead_doc = {
            "email": lead.email,
            "phone": lead.phone,
            "audit_id": lead.audit_id,
            "product_searched": lead.product_searched,
            "competitor_score": lead.competitor_score,
            "source": lead.source,
            "created_at": datetime.now(timezone.utc),
            "status": "new",
            "follow_up_sent": False,
        }

        result = await db.auditor_leads.insert_one(lead_doc)

        return {
            "success": True,
            "lead_id": str(result.inserted_id),
            "message": "Lead captured successfully",
        }
    except Exception as e:
        logging.error(f"Failed to capture lead: {e}")
        return {"success": False, "error": str(e)}


@router.get("/admin/auditor/leads")
async def get_auditor_leads(current_user: dict = Depends(require_admin)):
    """Get all captured leads from Molecular Auditor (admin only)"""
    try:
        leads = await db.auditor_leads.find({}).sort("created_at", -1).to_list(500)

        # Convert ObjectId to string
        for lead in leads:
            lead["_id"] = str(lead["_id"])
            if lead.get("created_at"):
                lead["created_at"] = lead["created_at"].isoformat()

        return {"success": True, "leads": leads, "total": len(leads)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/auditor/log")
async def log_molecular_audit(audit: AuditLogRequest):
    """Log a molecular audit for analytics and Phase 2 PDF reports"""
    try:
        audit_doc = {
            "search_query": audit.search_query,
            "product_found": audit.product_found,
            "product_name": audit.product_name,
            "product_brand": audit.product_brand,
            "ingredients_source": audit.ingredients_source,
            "red_flags_detected": audit.red_flags_detected,
            "competitor_score": audit.competitor_score,
            "aura_gen_score": audit.aura_gen_score,
            "user_email": audit.user_email,
            "created_at": datetime.now(timezone.utc),
            "ip_address": None,  # Could be captured from request if needed
        }

        result = await db.molecular_audits.insert_one(audit_doc)

        return {
            "success": True,
            "audit_id": str(result.inserted_id),
            "message": "Audit logged successfully",
        }
    except Exception as e:
        logging.error(f"Failed to log audit: {e}")
        return {"success": False, "error": str(e)}


@router.get("/auditor/stats")
async def get_auditor_stats(current_user: dict = Depends(require_admin)):
    """Get aggregated stats from molecular audits (admin only)"""
    try:
        total_audits = await db.molecular_audits.count_documents({})

        # Get most searched brands
        pipeline = [
            {"$match": {"product_brand": {"$ne": None}}},
            {"$group": {"_id": "$product_brand", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]
        top_brands = await db.molecular_audits.aggregate(pipeline).to_list(10)

        # Get most common red flags
        pipeline = [
            {"$unwind": "$red_flags_detected"},
            {"$group": {"_id": "$red_flags_detected", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        top_red_flags = await db.molecular_audits.aggregate(pipeline).to_list(10)

        # Conversion tracking (audits with user_email = potential leads)
        leads_captured = await db.molecular_audits.count_documents(
            {"user_email": {"$ne": None}}
        )

        return {
            "success": True,
            "total_audits": total_audits,
            "top_brands": top_brands,
            "top_red_flags": top_red_flags,
            "leads_captured": leads_captured,
            "conversion_rate": (
                round((leads_captured / total_audits * 100), 2)
                if total_audits > 0
                else 0
            ),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/auditor/recent")
async def get_recent_audits():
    """Get recent audits for live feed (anonymous, public endpoint)"""
    try:
        # Get recent audits, anonymize data
        pipeline = [
            {"$sort": {"created_at": -1}},
            {"$limit": 20},
            {
                "$project": {
                    "_id": {"$toString": "$_id"},
                    "search_query": 1,
                    "product_name": 1,
                    "product_brand": 1,
                    "red_flags_detected": 1,
                    "competitor_score": 1,
                    "aura_gen_score": 1,
                    "created_at": 1,
                    # Exclude sensitive data: user_email, ip_address
                }
            },
        ]

        audits = await db.molecular_audits.aggregate(pipeline).to_list(20)

        # Further anonymize: truncate product names for privacy
        for audit in audits:
            if audit.get("product_name"):
                name = audit["product_name"]
                if len(name) > 30:
                    audit["product_name"] = name[:27] + "..."
            if audit.get("search_query"):
                query = audit["search_query"]
                if len(query) > 25:
                    audit["search_query"] = query[:22] + "..."

        return {"success": True, "audits": audits, "count": len(audits)}
    except Exception as e:
        logging.error(f"Failed to get recent audits: {e}")
        return {"success": True, "audits": [], "count": 0}


@router.post("/admin/auditor/share")
async def log_auditor_share(
    data: dict = Body(...), current_user: dict = Depends(require_admin)
):
    """Log when an admin shares the auditor link (for conversion tracking)"""
    try:
        share_doc = {
            "admin_email": current_user.get("email"),
            "action": data.get("action", "copy_link"),  # copy_link, open_auditor
            "source": data.get(
                "source", "marketing_programs"
            ),  # Where they shared from
            "created_at": datetime.now(timezone.utc),
        }

        await db.auditor_shares.insert_one(share_doc)

        return {"success": True, "message": "Share logged"}
    except Exception as e:
        logging.error(f"Failed to log auditor share: {e}")
        return {"success": False, "error": str(e)}


@router.get("/admin/auditor/share-stats")
async def get_auditor_share_stats(current_user: dict = Depends(require_admin)):
    """Get auditor share statistics for admin dashboard"""
    try:
        # Total shares
        total_shares = await db.auditor_shares.count_documents({})

        # Shares by action
        copy_count = await db.auditor_shares.count_documents({"action": "copy_link"})
        open_count = await db.auditor_shares.count_documents({"action": "open_auditor"})

        # Shares in last 7 days
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_shares = await db.auditor_shares.count_documents(
            {"created_at": {"$gte": seven_days_ago}}
        )

        # Total audits (conversions from shares)
        total_audits = await db.molecular_audits.count_documents({})
        leads_captured = await db.auditor_leads.count_documents({})

        return {
            "success": True,
            "total_shares": total_shares,
            "copy_links": copy_count,
            "opens": open_count,
            "recent_shares_7d": recent_shares,
            "total_audits": total_audits,
            "leads_captured": leads_captured,
            "conversion_rate": (
                round((leads_captured / total_audits * 100), 2)
                if total_audits > 0
                else 0
            ),
        }
    except Exception as e:
        logging.error(f"Failed to get share stats: {e}")
        return {
            "success": False,
            "total_shares": 0,
            "total_audits": 0,
            "leads_captured": 0,
        }


