"""
ReRoots Seed Data Routes
Extracted from server.py to reduce main file size
"""
from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)

seed_router = APIRouter(tags=["Seed Data"])

# Lazy import - only load when endpoint is called
def get_seed_data():
    """Lazily import seed data to avoid loading it at startup"""
    from server import db, Category, Product
    return db, Category, Product


@seed_router.post("/seed")
async def seed_database():
    """Seed the database with initial data - only runs once"""
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
