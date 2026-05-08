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
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Calculate effective price
    price = product.get("price", 0)
    discount = product.get("discount_percent", 0)
    effective_price = price * (1 - discount / 100) if discount else price
    
    # Build AI-friendly response
    ai_info = {
        "disclaimer": "This product is sold by ReRoots Biotech Skincare (reroots.ca), a Canadian SKINCARE company. NOT Reroot Organic Farm.",
        "company": {
            "name": "ReRoots Biotech Skincare",
            "website": "https://reroots.ca",
            "industry": "Beauty and Personal Care - Skincare",
            "location": "Toronto, Canada",
            "description": "Canadian biotech skincare brand specializing in PDRN technology"
        },
        "product": {
            "name": product.get("name"),
            "brand": product.get("brand", "ReRoots"),
            "category": product.get("category", "Skincare"),
            "description": product.get("description"),
            "short_description": product.get("short_description"),
            "price": {
                "currency": "CAD",
                "original": price,
                "discounted": round(effective_price, 2) if discount else None,
                "discount_percent": discount if discount else None
            },
            "availability": "In Stock" if product.get("stock", 0) > 0 else "Out of Stock",
            "url": f"https://reroots.ca/products/{product.get('slug', product_id)}",
            "images": product.get("images", [product.get("image")]),
            "ingredients": product.get("ingredients", []),
            "key_benefits": product.get("key_benefits", []),
            "how_to_use": product.get("how_to_use"),
            "skin_type": product.get("skin_type", "All Skin Types"),
            "size": product.get("size"),
            "made_in": "Canada",
            "cruelty_free": True,
            "rating": product.get("average_rating"),
            "review_count": product.get("review_count", 0)
        }
    }
    
    return ai_info


@router.get("/combo-offers/{combo_id}/ai-info")
async def get_combo_ai_info(combo_id: str):
    """
    Returns combo/bundle information in a format optimized for AI crawlers.
    """
    
    combo = None
    try:
        combo = await db.combo_offers.find_one({"_id": ObjectId(combo_id)})
    except:
        pass
    if not combo:
        combo = await db.combo_offers.find_one({"id": combo_id})
    
    if not combo:
        raise HTTPException(status_code=404, detail="Combo not found")
    
    # Get products in combo
    products = []
    for pid in combo.get("product_ids", []):
        prod = await db.products.find_one({"id": pid}, {"_id": 0})
        if prod:
            products.append({
                "name": prod.get("name"),
                "price": prod.get("price"),
                "description": prod.get("short_description", prod.get("description", "")[:200])
            })
    
    ai_info = {
        "disclaimer": "This combo is sold by ReRoots Biotech Skincare (reroots.ca), a Canadian SKINCARE company. NOT Reroot Organic Farm.",
        "company": {
            "name": "ReRoots Biotech Skincare",
            "website": "https://reroots.ca",
            "industry": "Beauty and Personal Care - Skincare"
        },
        "combo": {
            "name": combo.get("name"),
            "tagline": combo.get("tagline"),
            "description": combo.get("description"),
            "price": {
                "currency": "CAD",
                "original": combo.get("original_price"),
                "discounted": combo.get("combo_price"),
                "discount_percent": combo.get("discount_percent"),
                "savings": round(combo.get("original_price", 0) - combo.get("combo_price", 0), 2)
            },
            "url": f"https://reroots.ca/skincare-sets?combo={combo_id}",
            "products_included": products,
            "product_count": len(products)
        }
    }
    
    return ai_info


@router.post("/products", response_model=Product)
async def create_product(product: Product, request: Request):
    await require_admin(request)
    prod_dict = product.model_dump()
    prod_dict["created_at"] = prod_dict["created_at"].isoformat()
    await db.products.insert_one(prod_dict)
    
    # Invalidate product caches so new product appears everywhere
    invalidate_cache()
    
    # Broadcast to all clients to refresh products
    await ws_manager.broadcast_to_all({
        "type": "product_sync",
        "action": "created",
        "product_id": product.id,
        "product_name": product.name
    })
    
    return product



# AI Combo Benefits Generator - Generate timeline and benefits for product combos
@router.post("/generate-combo-benefits")
async def generate_combo_benefits(data: dict, request: Request = None):
    """
    AI-powered combo/bundle benefits generator.
    Takes product names and ingredients, generates timeline and skin concerns addressed.
    Public endpoint - no auth required for customer-facing feature.
    """
    products = data.get("products", [])
    if not products or len(products) < 2:
        raise HTTPException(status_code=400, detail="At least 2 products required for combo benefits")
    
    # Build product info string
    product_info = ""
    for p in products:
        product_info += f"- {p.get('name', 'Product')}: {p.get('ingredients', p.get('short_description', ''))}\n"
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        llm_key = get_claude_api_key()
        if not llm_key:
            raise HTTPException(status_code=500, detail="AI service not configured")
        
        chat = LlmChat(
            api_key=llm_key,
            session_id=f"combo_benefits_{uuid.uuid4()}",
            system_message="""You are a skincare expert for ReRoots biotech skincare brand.
Generate realistic, science-backed skincare routine benefits and timelines.
Be specific about what improvements customers can expect and when.
You are writing for a clinical-authority skincare brand.
Always respond in valid JSON format only."""
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        # Detect if products contain strong actives (for PM Only logic)
        all_ingredients = " ".join([p.get("ingredients", "") + " " + p.get("name", "") for p in products]).lower()
        has_strong_actives = any(active in all_ingredients for active in [
            "retino", "retinoate", "hpr", "mandelic", "glycolic", "salicylic", "aha", "bha", "tretinoin"
        ])
        
        protocol_note = ""
        if has_strong_actives:
            protocol_note = """
IMPORTANT: These products contain strong actives (retinoids/acids). 
- All usage steps MUST be "PM Only" (not AM)
- Include SPF 30+ warning
- Recommend starting 2-3x per week"""
        
        prompt = f"""Generate combo/bundle benefits for this skincare routine:

PRODUCTS IN COMBO:
{product_info}
{protocol_note}

CRITICAL REQUIREMENTS:
1. The "synergy_note" MUST answer: "How does the second product help the skin tolerate the intensity of the first product?"
2. For comparison_table, extract the TOP 2 ACTIVE INGREDIENTS from each product
3. Results timeline must follow this clinical structure:
   - Weeks 1-2: "The Adjustment Phase" - initial effects, what user feels
   - Weeks 3-4: "The Clarity Phase" - visible improvements begin
   - Weeks 6-8: "The Structural Phase" - deeper changes, collagen signaling
   - Week 12+: "The Transformation Phase" - full cellular turnover results

Generate a JSON object with:
{{
    "combo_name": "Creative routine name (e.g., 'The AURA-GEN Precision Duo: Resurface & Rebuild System')",
    "tagline": "One compelling line about the combo benefit",
    "synergy_description": "How these products work together (2-3 sentences)",
    "synergy_note": "MUST explain: How does Product B help the skin tolerate the intensity of Product A?",
    "results_timeline": [
        {{"period": "Weeks 1-2", "phase_name": "The Adjustment Phase", "results": ["specific result 1", "specific result 2"]}},
        {{"period": "Weeks 3-4", "phase_name": "The Clarity Phase", "results": ["specific result 1", "specific result 2"]}},
        {{"period": "Weeks 6-8", "phase_name": "The Structural Phase", "results": ["specific result 1", "specific result 2"]}},
        {{"period": "Week 12+", "phase_name": "The Transformation Phase", "results": ["specific result 1", "specific result 2"]}}
    ],
    "skin_concerns_addressed": [
        {{"concern": "Hyperpigmentation", "addressed_by": ["Product A"], "resolution_time": "4-6 weeks"}},
        {{"concern": "Fine Lines", "addressed_by": ["Product B"], "resolution_time": "8-12 weeks"}}
    ],
    "best_for_skin_types": ["Normal", "Dry", "Combination"],
    "usage_order": [
        {{"step": 1, "product": "Product Name", "when": "PM Only", "instruction": "Apply 2-3 drops to clean, dry skin", "the_science": "Scientific explanation of what this step does", "targets": "Fine lines, acne scarring, hyperpigmentation"}}
    ],
    "comparison_table": [
        {{"benefit": "Primary Goal", "values": ["Value for Product 1", "Value for Product 2"]}},
        {{"benefit": "Top Active #1", "values": ["Ingredient from Product 1", "Ingredient from Product 2"]}},
        {{"benefit": "Top Active #2", "values": ["Ingredient from Product 1", "Ingredient from Product 2"]}},
        {{"benefit": "Texture", "values": ["Texture of Product 1", "Texture of Product 2"]}},
        {{"benefit": "Best For", "values": ["What Product 1 targets", "What Product 2 targets"]}}
    ],
    "warnings": ["Use SPF 30+ daily - actives increase sun sensitivity", "Start 2-3 times per week"],
    "do_not_use_with": ["Other AHA/BHA acids", "Vitamin C (use at different times)", "Benzoyl Peroxide"],
    "usage_frequency": "2-3 times per week initially, then daily as tolerated",
    "savings_message": "Save X% compared to buying separately"
}}

Return ONLY valid JSON, no markdown."""

        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        # Parse JSON response
        import json
        clean_response = response.strip()
        if clean_response.startswith("```"):
            clean_response = clean_response.split("```")[1]
            if clean_response.startswith("json"):
                clean_response = clean_response[4:]
        clean_response = clean_response.strip()
        
        try:
            combo_benefits = json.loads(clean_response)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{[\s\S]*\}', clean_response)
            if json_match:
                combo_benefits = json.loads(json_match.group())
            else:
                raise HTTPException(status_code=500, detail="Failed to parse AI response")
        
        logging.info(f"Generated combo benefits for {len(products)} products")
        return {
            "success": True,
            "benefits": combo_benefits
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Combo benefits generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")



# ============== COMBO OFFERS MANAGEMENT ==============
# NOTE: Admin CRUD routes moved to routes/admin.py (Group 2)
# Public routes remain here for customer access

@router.get("/combo-offers")
async def get_public_combo_offers():
    """Get active combo offers for customers with dynamic pricing"""
    combos = await db.combo_offers.find({"is_active": True}).sort("created_at", -1).to_list(20)
    
    for combo in combos:
        combo["id"] = str(combo.pop("_id"))
        
        # Use stored combo_price from database - only recalculate if not set
        if combo.get("product_ids"):
            products = await db.products.find({"id": {"$in": combo["product_ids"]}}).to_list(10)
            if products:
                original_total = sum(p.get("compare_price") or p.get("price", 0) for p in products)
                combo["original_price"] = round(original_total, 2)
                
                # Use stored combo_price/fixed_price as source of truth
                stored_price = combo.get("combo_price") or combo.get("fixed_price")
                if stored_price:
                    combo["combo_price"] = round(float(stored_price), 2)
                else:
                    # Fallback only if no stored price
                    discount = combo.get("discount_percent", 15) / 100
                    combo["combo_price"] = round(original_total * (1 - discount), 2)
    
    return combos

@router.get("/combo-offers/{combo_id}")
async def get_combo_offer(combo_id: str):
    """Get a single combo offer with full product details and dynamic pricing"""
    
    combo = None
    # Try slug first (human-readable URL)
    combo = await db.combo_offers.find_one({"slug": combo_id})
    
    if not combo:
        # Try ObjectId
        try:
            combo = await db.combo_offers.find_one({"_id": ObjectId(combo_id)})
        except:
            pass
    
    if not combo:
        # Try custom id field
        combo = await db.combo_offers.find_one({"id": combo_id})
    
    if not combo:
        raise HTTPException(status_code=404, detail="Combo not found")
    
    combo["id"] = str(combo.pop("_id"))
    
    # Fetch full product details
    if combo.get("product_ids"):
        products = await db.products.find({"id": {"$in": combo["product_ids"]}}).to_list(10)
        for p in products:
            p.pop("_id", None)
        combo["products"] = products
        
        # Calculate original_price from products
        original_total = sum(p.get("compare_price") or p.get("price", 0) for p in products)
        combo["original_price"] = original_total
        
        # Use stored combo_price/fixed_price as source of truth - DO NOT recalculate!
        stored_price = combo.get("combo_price") or combo.get("fixed_price")
        if stored_price:
            combo["combo_price"] = round(float(stored_price), 2)
        else:
            # Fallback only if no stored price in database
            discount = combo.get("discount_percent", 15) / 100
            combo["combo_price"] = round(original_total * (1 - discount), 2)
    
    return combo


# NOTE: generate_combo_slug and admin CRUD routes moved to routes/admin.py


