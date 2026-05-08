"""
White-Label Command Center — Enterprise tier custom branding per tenant.
Custom logo, name, color, domain (CNAME) support.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import os
        mongo_url = os.environ.get("MONGO_URL", "").strip().strip('"').strip("'")
        if not mongo_url:
            return None
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(mongo_url)
        _db = client[os.environ.get("DB_NAME", "aurem_db")]
        return _db
    except Exception:
        return None


DEFAULT_BRANDING = {
    "brand_name": "AUREM ORA",
    "logo_url": "",
    "primary_color": "#D4A373",
    "sidebar_bg": "#0f1f17",
    "domain": "",
    "favicon_url": "",
    "tagline": "COMMAND CENTER",
}


async def get_branding(tenant_id: str) -> dict:
    """Get white-label branding for a tenant."""
    db = _get_db()
    if db is not None:
        config = await db.white_label_config.find_one(
            {"tenant_id": tenant_id}, {"_id": 0}
        )
        if config:
            return {**DEFAULT_BRANDING, **config}
    return {**DEFAULT_BRANDING, "tenant_id": tenant_id}


async def set_branding(tenant_id: str, data: dict) -> dict:
    """Set white-label branding for a tenant (Enterprise only)."""
    db = _get_db()
    if db is None:
        return {"error": "DB unavailable"}

    # Check tier
    from services.tool_permissions import get_tenant_tier
    tier = await get_tenant_tier(tenant_id)
    if tier != "enterprise":
        return {
            "error": "White-label requires Enterprise plan",
            "current_tier": tier,
            "upgrade_to": "enterprise",
        }

    allowed_fields = [
        "brand_name", "logo_url", "primary_color", "sidebar_bg",
        "domain", "favicon_url", "tagline",
    ]
    update = {k: v for k, v in data.items() if k in allowed_fields}
    update["tenant_id"] = tenant_id
    update["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.white_label_config.update_one(
        {"tenant_id": tenant_id},
        {"$set": update},
        upsert=True,
    )
    return await get_branding(tenant_id)


async def get_cname_instructions(tenant_id: str) -> dict:
    """Get CNAME setup instructions for custom domain."""
    branding = await get_branding(tenant_id)
    domain = branding.get("domain", "")

    return {
        "tenant_id": tenant_id,
        "custom_domain": domain or "(not configured)",
        "instructions": [
            f"1. Go to your DNS provider for {domain or 'yourdomain.com'}",
            "2. Create a CNAME record:",
            "   Host: ai (or subdomain of choice)",
            "   Points to: aurem.live",
            "   TTL: 300",
            "3. Wait 5-10 minutes for DNS propagation",
            "4. Contact support@aurem.ai to activate SSL",
        ],
        "status": "configured" if domain else "not_configured",
    }
