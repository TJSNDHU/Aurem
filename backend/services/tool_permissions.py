"""
Tool Permissions per Subscription Tier — Starter/Growth/Enterprise
Denies access to premium tools for lower tiers with upgrade prompts.
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


# ═══════════════════════════════════════
# TIER DEFINITIONS
# ═══════════════════════════════════════

TIER_TOOLS = {
    "starter": {
        "allowed": [
            "lead_score", "invoice_reminder", "seo_fix", "css_fix",
            "morning_brief", "chat", "knowledge_sync", "cache_warm",
            "sentiment_analysis", "message_draft", "pixel_css_fix",
            "seo_meta_fix", "inject_css", "compile_origin", "update_knowledge",
        ],
        "denied": [
            "v2v_voice", "bulk_outreach", "negotiation_engine", "white_label",
            "ghost_mode", "geo_dashboard", "ucp_protocol", "outreach_sequences",
            "custom_training", "multi_agent_rag", "deep_scout",
        ],
    },
    "growth": {
        "allowed": [
            "lead_score", "invoice_reminder", "seo_fix", "css_fix",
            "morning_brief", "chat", "knowledge_sync", "cache_warm",
            "sentiment_analysis", "message_draft", "pixel_css_fix",
            "seo_meta_fix", "inject_css", "compile_origin", "update_knowledge",
            "v2v_voice", "geo_dashboard", "ucp_protocol", "outreach_sequences",
            "bulk_outreach", "negotiation_engine", "multi_agent_rag",
            "deep_scout", "ghost_mode",
        ],
        "denied": [
            "white_label", "custom_training",
        ],
    },
    "enterprise": {
        "allowed": ["*"],
        "denied": [],
    },
}

TIER_UPGRADE_MAP = {
    "starter": "growth",
    "growth": "enterprise",
    "enterprise": None,
}


async def get_tenant_tier(tenant_id: str) -> str:
    """Get tenant's subscription tier."""
    if _db is None:
        return "starter"
    tenant = await _db.tenants.find_one(
        {"tenant_id": tenant_id}, {"_id": 0, "subscription_tier": 1}
    )
    if tenant:
        return tenant.get("subscription_tier", "starter")
    # Check users collection as fallback
    user = await _db.users.find_one(
        {"id": tenant_id}, {"_id": 0, "subscription_tier": 1}
    )
    return user.get("subscription_tier", "starter") if user else "starter"


def check_tool_permission(tier: str, tool_name: str) -> dict:
    """Check if a tool is allowed for the given tier."""
    tier_config = TIER_TOOLS.get(tier, TIER_TOOLS["starter"])

    if "*" in tier_config["allowed"]:
        return {"allowed": True, "tier": tier, "tool": tool_name}

    if tool_name in tier_config["allowed"]:
        return {"allowed": True, "tier": tier, "tool": tool_name}

    if tool_name in tier_config["denied"]:
        next_tier = TIER_UPGRADE_MAP.get(tier, "enterprise")
        return {
            "allowed": False,
            "tier": tier,
            "tool": tool_name,
            "message": f"This feature requires {next_tier or 'enterprise'} plan. Upgrade at aurem.live/upgrade",
            "upgrade_to": next_tier,
        }

    # Unknown tool — allow by default
    return {"allowed": True, "tier": tier, "tool": tool_name}


async def check_permission(tenant_id: str, tool_name: str) -> dict:
    """Full permission check for a tenant + tool combination."""
    tier = await get_tenant_tier(tenant_id)
    result = check_tool_permission(tier, tool_name)
    result["tenant_id"] = tenant_id
    return result


def get_tier_tools(tier: str) -> dict:
    """Get allowed/denied tools for a tier."""
    config = TIER_TOOLS.get(tier, TIER_TOOLS["starter"])
    return {
        "tier": tier,
        "allowed": config["allowed"],
        "denied": config["denied"],
        "total_allowed": "unlimited" if "*" in config["allowed"] else len(config["allowed"]),
    }


async def set_tenant_tier(tenant_id: str, tier: str) -> dict:
    """Set tenant subscription tier."""
    if tier not in TIER_TOOLS:
        return {"error": f"Invalid tier: {tier}. Must be starter/growth/enterprise"}
    if _db is None:
        return {"error": "DB unavailable"}

    await _db.tenants.update_one(
        {"tenant_id": tenant_id},
        {"$set": {
            "tenant_id": tenant_id,
            "subscription_tier": tier,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"status": "ok", "tenant_id": tenant_id, "tier": tier}
