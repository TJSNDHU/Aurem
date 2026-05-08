"""
Admin Routes Module
═══════════════════════════════════════════════════════════════════
Extracted from server.py monolith for better maintainability.
Contains all /api/admin/* endpoints.

Groups:
  1. RLS Management (/admin/rls/*)
  2. Brand Configuration (/admin/brands)
  3. Combo Offers CRUD (/admin/combo-offers/*)
  ... more groups to be added incrementally
═══════════════════════════════════════════════════════════════════
"""

from fastapi import APIRouter, HTTPException, Request, Body
from typing import Optional
from datetime import datetime, timezone
import jwt
import uuid
import logging

# Shared auth utilities
from utils.auth_utils import require_admin, init_auth_utils

# Will be set by init_admin_routes()
db = None
JWT_SECRET = None
JWT_ALGORITHM = "HS256"

# Import RLS utilities
from rls_security import (
    BrandID, BRAND_CONFIGS, RLS_PROTECTED_COLLECTIONS,
    migrate_add_brand_id, create_indexes_for_rls
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

logger = logging.getLogger(__name__)


def init_admin_routes(database, jwt_secret: str, default_permissions: dict = None, 
                      super_admin_permissions: dict = None):
    """Initialize admin routes with shared dependencies."""
    global db, JWT_SECRET
    db = database
    JWT_SECRET = jwt_secret
    
    # Initialize shared auth utilities
    init_auth_utils(db, jwt_secret, JWT_ALGORITHM, default_permissions, super_admin_permissions)
    
    logger.info("✓ Admin routes initialized")


# ═══════════════════════════════════════════════════════════════════
# GROUP 1: RLS Management + Brands (3 endpoints)
# ═══════════════════════════════════════════════════════════════════

@router.post("/rls/migrate")
async def run_rls_migration(request: Request):
    """
    Run RLS migration to add brand_id to all existing documents.
    Requires super_admin access.
    """
    # Verify admin access
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        token = auth_header[7:]
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        
        # Check if user is super admin
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if not user or not user.get("is_admin"):
            raise HTTPException(status_code=403, detail="Super admin access required")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Run migration
    results = await migrate_add_brand_id(db, default_brand="reroots")
    
    # Create indexes
    await create_indexes_for_rls(db)
    
    return {
        "status": "success",
        "message": "RLS migration completed",
        "results": results
    }


@router.get("/rls/status")
async def get_rls_status():
    """Get RLS status for all collections"""
    status = {}
    
    for collection_name in RLS_PROTECTED_COLLECTIONS:
        try:
            collection = db[collection_name]
            total = await collection.count_documents({})
            with_brand = await collection.count_documents({"brand_id": {"$exists": True}})
            reroots_count = await collection.count_documents({"brand_id": "reroots"})
            lavela_count = await collection.count_documents({"brand_id": "lavela"})
            
            status[collection_name] = {
                "total": total,
                "with_brand_id": with_brand,
                "without_brand_id": total - with_brand,
                "reroots": reroots_count,
                "lavela": lavela_count,
                "coverage": f"{(with_brand/total*100) if total > 0 else 100:.1f}%"
            }
        except Exception as e:
            status[collection_name] = {"error": str(e)}
    
    return {"collections": status}


@router.get("/brands")
async def get_brands():
    """Get list of all brands with their configurations"""
    return {
        "brands": [
            {
                "id": brand.value,
                "name": config["name"],
                "display_name": config["display_name"],
                "tagline": config["tagline"],
                "domain": config["domain"],
                "theme": config["theme"]
            }
            for brand, config in BRAND_CONFIGS.items()
        ]
    }



# ═══════════════════════════════════════════════════════════════════
# GROUP 2: Combo Offers CRUD (4 endpoints)
# ═══════════════════════════════════════════════════════════════════

def generate_combo_slug(name: str) -> str:
    """Generate URL-friendly slug from combo name"""
    import re
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)  # Remove special chars
    slug = re.sub(r'[\s_]+', '-', slug)  # Replace spaces with hyphens
    slug = re.sub(r'-+', '-', slug)  # Remove multiple hyphens
    slug = slug.strip('-')
    return slug


@router.get("/combo-offers")
async def get_combo_offers(request: Request, brand: Optional[str] = None):
    """Get all combo offers for admin, filtered by brand"""
    await require_admin(request)
    
    # Build brand filter
    query = {}
    active_brand = brand or getattr(request.state, 'brand', 'reroots')
    if active_brand == "lavela":
        query["$or"] = [{"brand": "lavela"}, {"tags": {"$in": ["lavela", "teen"]}}]
    elif active_brand == "reroots":
        query["brand"] = {"$ne": "lavela"}
    
    combos = await db.combo_offers.find(query).sort("created_at", -1).to_list(100)
    for combo in combos:
        combo["id"] = str(combo.pop("_id"))
    return combos


@router.post("/combo-offers")
async def create_combo_offer(data: dict, request: Request):
    """Create a new combo offer with AI-powered dynamic active concentration calculation"""
    await require_admin(request)
    
    if not data.get("name"):
        raise HTTPException(status_code=400, detail="Combo name is required")
    if not data.get("product_ids") or len(data["product_ids"]) < 2:
        raise HTTPException(status_code=400, detail="At least 2 products required")
    
    # AI Dynamic Calculation: Auto-calculate total active concentration from products
    product_ids = data.get("product_ids", [])
    total_active = 0.0
    active_breakdown = {}
    
    for pid in product_ids:
        product = await db.products.find_one({"id": pid})
        if product:
            concentration = product.get("active_concentration", 0) or 0
            total_active += concentration
            active_breakdown[pid] = {
                "concentration": concentration,
                "total": concentration,
                "label": product.get("engine_label", "") or product.get("name", "")[:25],
                "type": product.get("engine_type", "") or ("engine" if len(active_breakdown) == 0 else "buffer"),
                "key_actives": product.get("key_actives", []),
                "primary_benefit": product.get("primary_benefit", "")
            }
    
    # Determine pricing
    discount_type = data.get("discount_type", "percent")
    fixed_price = data.get("fixed_price", 0)
    original_price = data.get("original_price", 0)
    explicit_combo_price = data.get("combo_price")
    
    if explicit_combo_price and explicit_combo_price > 0:
        combo_price = round(float(explicit_combo_price), 2)
        if original_price > 0:
            discount_percent = round(((original_price - combo_price) / original_price) * 100)
        else:
            discount_percent = data.get("discount_percent", 15)
    elif discount_type == "fixed" and fixed_price > 0 and original_price > 0:
        calculated_discount = round(((original_price - fixed_price) / original_price) * 100)
        discount_percent = calculated_discount
        combo_price = fixed_price
    else:
        discount_percent = data.get("discount_percent", 15)
        combo_price = round(original_price * (1 - discount_percent / 100), 2) if original_price > 0 else 0
    
    combo = {
        "id": f"combo-{uuid.uuid4().hex[:8]}",
        "slug": data.get("slug") or generate_combo_slug(data.get("name", "")),
        "name": data.get("name"),
        "tagline": data.get("tagline", ""),
        "description": data.get("description", ""),
        "product_ids": product_ids,
        "discount_percent": discount_percent,
        "discount_type": discount_type,
        "fixed_price": fixed_price,
        "original_price": original_price,
        "combo_price": combo_price,
        "is_active": data.get("is_active", True),
        "popup_enabled": data.get("popup_enabled", True),
        "popup_headline": data.get("popup_headline", ""),
        "popup_message": data.get("popup_message", ""),
        "image": data.get("image", ""),
        "results_timeline": data.get("results_timeline", []),
        "skin_concerns": data.get("skin_concerns", []),
        "usage_order": data.get("usage_order", []),
        "comparison_table": data.get("comparison_table", []),
        "warnings": data.get("warnings", []),
        "do_not_use_with": data.get("do_not_use_with", []),
        "usage_frequency": data.get("usage_frequency", ""),
        "science_notes": data.get("science_notes", ""),
        "total_active_percent": round(total_active, 2),
        "active_breakdown": active_breakdown,
        "synergy_note": data.get("synergy_note", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.combo_offers.insert_one(combo)
    combo.pop("_id", None)
    
    logger.info(f"Combo offer created: {combo['name']} with {total_active:.2f}% total actives")
    return combo


@router.put("/combo-offers/{combo_id}")
async def update_combo_offer(combo_id: str, data: dict, request: Request):
    """Update a combo offer with AI-powered auto-recalculation of active concentration"""
    await require_admin(request)
    
    from bson import ObjectId
    try:
        existing = await db.combo_offers.find_one({"_id": ObjectId(combo_id)})
    except:
        existing = await db.combo_offers.find_one({"id": combo_id})
    
    if not existing:
        raise HTTPException(status_code=404, detail="Combo not found")
    
    # AI Dynamic Calculation
    product_ids = data.get("product_ids", existing.get("product_ids", []))
    total_active = 0.0
    active_breakdown = {}
    
    for pid in product_ids:
        product = await db.products.find_one({"id": pid})
        if product:
            concentration = product.get("active_concentration", 0) or 0
            total_active += concentration
            active_breakdown[pid] = {
                "concentration": concentration,
                "total": concentration,
                "label": product.get("engine_label", "") or product.get("name", "")[:25],
                "type": product.get("engine_type", "") or ("engine" if len(active_breakdown) == 0 else "buffer"),
                "key_actives": product.get("key_actives", []),
                "primary_benefit": product.get("primary_benefit", "")
            }
    
    update_data = {
        "name": data.get("name", existing.get("name")),
        "slug": data.get("slug") or existing.get("slug") or generate_combo_slug(data.get("name", existing.get("name", ""))),
        "tagline": data.get("tagline", existing.get("tagline")),
        "description": data.get("description", existing.get("description")),
        "product_ids": product_ids,
        "discount_type": data.get("discount_type", existing.get("discount_type", "percent")),
        "fixed_price": data.get("fixed_price", existing.get("fixed_price", 0)),
        "original_price": data.get("original_price", existing.get("original_price")),
        "combo_price": data.get("combo_price", existing.get("combo_price")),
        "is_active": data.get("is_active", existing.get("is_active")),
        "popup_enabled": data.get("popup_enabled", existing.get("popup_enabled", True)),
        "popup_headline": data.get("popup_headline", existing.get("popup_headline", "")),
        "popup_message": data.get("popup_message", existing.get("popup_message", "")),
        "image": data.get("image", existing.get("image")),
        "results_timeline": data.get("results_timeline", existing.get("results_timeline")),
        "skin_concerns": data.get("skin_concerns", existing.get("skin_concerns")),
        "usage_order": data.get("usage_order", existing.get("usage_order")),
        "comparison_table": data.get("comparison_table", existing.get("comparison_table", [])),
        "warnings": data.get("warnings", existing.get("warnings", [])),
        "do_not_use_with": data.get("do_not_use_with", existing.get("do_not_use_with", [])),
        "total_active_percent": round(total_active, 2),
        "active_breakdown": active_breakdown,
        "synergy_note": data.get("synergy_note", existing.get("synergy_note", "")),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Auto-calculate pricing
    discount_type = update_data.get("discount_type", "percent")
    fixed_price = update_data.get("fixed_price", 0)
    original_price = update_data.get("original_price", 0)
    explicit_combo_price = data.get("combo_price")
    
    if explicit_combo_price and explicit_combo_price > 0:
        update_data["combo_price"] = round(float(explicit_combo_price), 2)
        if original_price > 0:
            update_data["discount_percent"] = round(((original_price - update_data["combo_price"]) / original_price) * 100)
    elif discount_type == "fixed" and fixed_price > 0 and original_price > 0:
        calculated_discount = round(((original_price - fixed_price) / original_price) * 100)
        update_data["discount_percent"] = calculated_discount
        update_data["combo_price"] = fixed_price
    else:
        update_data["discount_percent"] = data.get("discount_percent", existing.get("discount_percent", 15))
        if original_price > 0:
            update_data["combo_price"] = round(original_price * (1 - update_data["discount_percent"] / 100), 2)
    
    try:
        await db.combo_offers.update_one({"_id": ObjectId(combo_id)}, {"$set": update_data})
    except:
        await db.combo_offers.update_one({"id": combo_id}, {"$set": update_data})
    
    logger.info(f"Combo offer updated: {update_data['name']} with {total_active:.2f}% total actives")
    return {"message": "Combo updated", **update_data}


@router.delete("/combo-offers/{combo_id}")
async def delete_combo_offer(combo_id: str, request: Request):
    """Delete a combo offer"""
    await require_admin(request)
    
    from bson import ObjectId
    try:
        result = await db.combo_offers.delete_one({"_id": ObjectId(combo_id)})
    except:
        result = await db.combo_offers.delete_one({"id": combo_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Combo not found")
    
    logger.info(f"Combo offer deleted: {combo_id}")
    return {"message": "Combo deleted"}



# ═══════════════════════════════════════════════════════════════════
# GROUP 3: Product Sync Status (1 endpoint)
# ═══════════════════════════════════════════════════════════════════

# Brand owner mapping
BRAND_OWNER_MAP = {
    "aura-gen": "Reroots Aesthetics Inc.",
    "la vela bianca": "Reroots Aesthetics Inc.",
    "lavela": "Reroots Aesthetics Inc.",
    "reroots": "Reroots Aesthetics Inc.",
    "oroe": "Polaris Built Inc.",
    "oroé": "Polaris Built Inc.",
}


def get_brand_owner(brand: str) -> str:
    """Get brand owner - critical for compliance."""
    if not brand:
        return "Reroots Aesthetics Inc."
    normalized = brand.lower().strip()
    for key, owner in BRAND_OWNER_MAP.items():
        if key in normalized:
            return owner
    return "Reroots Aesthetics Inc."  # Default


@router.get("/products/sync-status")
async def get_product_sync_status(request: Request):
    """
    Get sync status of all products across brands.
    Returns: name, brand, brand_owner, stock, last_updated, cnf_filed, is_live
    """
    await require_admin(request)
    
    products = await db.products.find({}, {"_id": 0}).to_list(500)
    
    result = []
    for product in products:
        brand = product.get("brand", "")
        
        result.append({
            "id": product.get("id", ""),
            "name": product.get("name", "Unknown"),
            "brand": brand,
            "brand_owner": product.get("brand_owner") or get_brand_owner(brand),
            "stock": product.get("stock", 0) or product.get("quantity", 0) or 0,
            "last_updated": product.get("updated_at") or product.get("last_updated"),
            "cnf_filed": product.get("cnf_filed", False),
            "is_live": product.get("is_active", True) if "is_active" in product else product.get("isActive", True),
        })
    
    return result
