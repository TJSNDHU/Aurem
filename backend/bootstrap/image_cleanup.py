"""Image URL cleanup — extracted from the former monolithic server.py.

Replaces broken `/api/uploads/...` legacy URLs across products, homepage_sections,
site_content, and categories with the curated Unsplash fallbacks from
`DEFAULT_IMAGES`. Runs once per startup via `background_init`.
"""
from __future__ import annotations

import logging
import re


DEFAULT_IMAGES = {
    "product": "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=600",
    "hero": "https://images.unsplash.com/photo-1677735476292-0fc57ab097b2?w=800",
    "science": "https://images.unsplash.com/photo-1576086213369-97a306d36557?w=800",
    "category": "https://images.unsplash.com/photo-1556228720-195a672e8a03?w=400",
    "section": "https://images.unsplash.com/photo-1556228578-0d85b1a4d571?w=800",
}


async def cleanup_broken_images(db) -> int:
    """Clean up broken image URLs in the database on startup.

    Returns the number of documents fixed. Failures are swallowed and logged
    so a corrupt record never stalls startup.
    """
    logger = logging.getLogger(__name__)
    broken_patterns = [
        r'https?://[^/]+\.preview\.emergentagent\.com/api/uploads/[^\s"\']+',
        r"/api/uploads/[a-f0-9-]+\.(jpg|png|jpeg|webp)",
    ]

    logger.info("Starting broken image URL cleanup...")
    fixed_count = 0

    try:
        # Fix products
        products = await db.products.find({}).to_list(1000)
        for product in products:
            images = product.get("images", [])
            new_images = []
            needs_update = False

            for img in images:
                is_broken = False
                for pattern in broken_patterns:
                    if re.search(pattern, img):
                        is_broken = True
                        break

                if is_broken or "uploads" in img:
                    new_images.append(DEFAULT_IMAGES["product"])
                    needs_update = True
                else:
                    new_images.append(img)

            if not new_images:
                new_images = [DEFAULT_IMAGES["product"]]
                needs_update = True

            if needs_update:
                await db.products.update_one(
                    {"_id": product["_id"]}, {"$set": {"images": new_images}}
                )
                fixed_count += 1
                logger.info(
                    f"Fixed images for product: {product.get('name', 'unknown')}"
                )

        # Fix homepage_sections
        sections = await db.homepage_sections.find({}).to_list(100)
        for section in sections:
            img = section.get("image_url", section.get("image", ""))
            if img:
                is_broken = "uploads" in img or "emergentagent.com/api/uploads" in img
                if is_broken:
                    await db.homepage_sections.update_one(
                        {"_id": section["_id"]},
                        {
                            "$set": {
                                "image_url": DEFAULT_IMAGES["section"],
                                "image": DEFAULT_IMAGES["section"],
                            }
                        },
                    )
                    fixed_count += 1
                    logger.info(
                        f"Fixed image for section: {section.get('title', 'unknown')}"
                    )

        # Fix site_content
        site_content = await db.site_content.find_one({})
        if site_content:
            updates = {}

            hero = site_content.get("hero", {})
            if hero:
                hero_img = hero.get("image", hero.get("hero_image", ""))
                if hero_img and (
                    "uploads" in hero_img or "emergentagent.com/api/uploads" in hero_img
                ):
                    updates["hero.image"] = DEFAULT_IMAGES["hero"]
                    updates["hero.hero_image"] = DEFAULT_IMAGES["hero"]

            science = site_content.get("science", {})
            if science:
                sci_img = science.get("image", "")
                if sci_img and (
                    "uploads" in sci_img or "emergentagent.com/api/uploads" in sci_img
                ):
                    updates["science.image"] = DEFAULT_IMAGES["science"]

            if updates:
                await db.site_content.update_one(
                    {"_id": site_content["_id"]}, {"$set": updates}
                )
                fixed_count += 1
                logger.info("Fixed site_content images")

        # Fix categories
        categories = await db.categories.find({}).to_list(100)
        for cat in categories:
            img = cat.get("image_url", cat.get("image", ""))
            if img and ("uploads" in img or "emergentagent.com/api/uploads" in img):
                await db.categories.update_one(
                    {"_id": cat["_id"]},
                    {
                        "$set": {
                            "image_url": DEFAULT_IMAGES["category"],
                            "image": DEFAULT_IMAGES["category"],
                        }
                    },
                )
                fixed_count += 1
                logger.info(f"Fixed image for category: {cat.get('name', 'unknown')}")

        logger.info(f"Broken image cleanup complete. Fixed {fixed_count} items.")

    except Exception as e:
        logger.error(f"Error during image cleanup: {e}")

    return fixed_count


__all__ = ["cleanup_broken_images", "DEFAULT_IMAGES"]
