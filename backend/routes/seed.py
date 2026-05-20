"""
AUREM Seed Data Routes
Extracted from server.py to reduce main file size
"""
import os
from fastapi import APIRouter, HTTPException, Request
import logging

logger = logging.getLogger(__name__)

seed_router = APIRouter(tags=["Seed Data"])


def _require_admin(request: Request):
    """Bug-fix #64 — seed endpoint was unauthenticated. If products got
    deleted (intentionally or via a wipe), anyone could re-seed with
    hardcoded data and trash any customer customisations."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    import jwt as _jwt
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(500, "JWT not configured")
    try:
        payload = _jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    from utils.admin_guard import is_admin_email
    if not (payload.get("is_admin") or payload.get("is_super_admin")
            or payload.get("role") in ("admin", "super_admin")
            or is_admin_email(payload.get("email"))):
        raise HTTPException(403, "Admin access required")


# Lazy import - only load when endpoint is called
def get_seed_data():
    """Lazily import seed data to avoid loading it at startup"""
    from server import db, Category, Product
    return db, Category, Product


@seed_router.post("/seed")
async def seed_database(request: Request):
    """Seed the database with initial data - only runs once"""
    _require_admin(request)  # Bug-fix #64
    db, Category, Product = get_seed_data()
    
    # Check if already seeded
    existing_products = await db.products.count_documents({})
    if existing_products > 0:
        return {"message": "Database already seeded", "product_count": existing_products}
    
    logger.info("Seeding database with initial data...")
    
    # Import seed data only when needed
    from seed_data import SEED_CATEGORIES, SEED_PRODUCTS
    
    # Create categories
    for cat_data in SEED_CATEGORIES:
        cat = Category(**cat_data)
        await db.categories.insert_one(cat.model_dump())
    
    # Create products
    for prod_data in SEED_PRODUCTS:
        prod = Product(**prod_data)
        await db.products.insert_one(prod.model_dump())
    
    logger.info(f"Seeded {len(SEED_CATEGORIES)} categories and {len(SEED_PRODUCTS)} products")
    
    return {
        "message": "Database seeded successfully",
        "categories": len(SEED_CATEGORIES),
        "products": len(SEED_PRODUCTS)
    }
