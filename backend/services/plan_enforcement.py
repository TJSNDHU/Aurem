"""
AUREM AI Platform — Proprietary Software
Copyright (c) 2026 Polaris Built Inc.

Plan Enforcement Service
========================
Subscription tier enforcement with usage tracking.
Gates pipeline actions, feature access, and resource limits.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

db = None


def set_db(database):
    global db
    db = database


# ═══════════════════════════════════════════════════════════════
# PLAN DEFINITIONS — Canonical source of truth
# ═══════════════════════════════════════════════════════════════

PLAN_TIERS = {
    "starter": {
        "plan_id": "plan_starter",
        "name": "Starter",
        "price_monthly": 97,
        "price_annual": 970,
        "currency": "CAD",
        "limits": {
            "actions_per_month": 500,
            "pipeline_runs_per_day": 3,
            "lead_enrichment_per_month": 50,
            "workspaces": 1,
            "v2v_concurrent_sessions": 0,
            "content_posts_per_month": 50,
            "images_per_month": 50,
            "social_channels": 2,
            "email_sequences_active": 1,
            "video_generation": False,
        },
        "features": {
            "ora_voice": "text_only",
            "v2v_voice": False,
            "morning_brief": True,
            "morning_brief_time": "07:00",
            "scout_scan_interval_hours": 48,
            "approval_queue": True,
            "geo_tracking": False,
            "sentiment_analysis": False,
            "deep_scout": False,
            "revenue_forecasting": False,
            "partner_referral": False,
            "white_label": False,
            "cname": False,
            "tenant_personas": False,
            "priority_support": False,
        },
        "tagline": "Perfect for solo founders and small teams",
    },
    "growth": {
        "plan_id": "plan_growth",
        "name": "Growth",
        "price_monthly": 297,
        "price_annual": 2970,
        "currency": "CAD",
        "limits": {
            "actions_per_month": 5000,
            "pipeline_runs_per_day": 20,
            "lead_enrichment_per_month": 500,
            "workspaces": 3,
            "v2v_concurrent_sessions": 5,
            "content_posts_per_month": 500,
            "images_per_month": 500,
            "social_channels": 7,
            "email_sequences_active": 10,
            "video_generation": "basic",
            "videos_per_month": 10,
        },
        "features": {
            "ora_voice": "v2v",
            "v2v_voice": True,
            "morning_brief": True,
            "morning_brief_time": "07:00",
            "scout_scan_interval_hours": 12,
            "approval_queue": True,
            "geo_tracking": True,
            "sentiment_analysis": True,
            "deep_scout": True,
            "revenue_forecasting": True,
            "partner_referral": True,
            "white_label": False,
            "cname": False,
            "tenant_personas": False,
            "priority_support": False,
        },
        "tagline": "For scaling businesses that need AI automation",
        "is_popular": True,
    },
    "enterprise": {
        "plan_id": "plan_enterprise",
        "name": "Enterprise",
        "price_monthly": 997,
        "price_annual": 9970,
        "currency": "CAD",
        "limits": {
            "actions_per_month": -1,  # -1 = unlimited
            "pipeline_runs_per_day": -1,
            "lead_enrichment_per_month": -1,
            "workspaces": -1,
            "v2v_concurrent_sessions": 25,
            "content_posts_per_month": -1,
            "images_per_month": -1,
            "social_channels": -1,
            "email_sequences_active": -1,
            "video_generation": True,
            "videos_per_month": -1,
            "ora_avatar": True,
            "video_extend": True,
        },
        "features": {
            "ora_voice": "v2v",
            "v2v_voice": True,
            "morning_brief": True,
            "morning_brief_time": "configurable",
            "scout_scan_interval_hours": 6,
            "approval_queue": True,
            "geo_tracking": True,
            "sentiment_analysis": True,
            "deep_scout": True,
            "revenue_forecasting": True,
            "partner_referral": True,
            "white_label": True,
            "cname": True,
            "tenant_personas": True,
            "priority_support": True,
        },
        "tagline": "Full platform with white-label and unlimited resources",
    },
}

# Add-on definitions
ADDONS = {
    "proximity_blast": {
        "addon_id": "addon_proximity_blast",
        "name": "Proximity Blast (Local Domination)",
        "price_monthly": 49,
        "currency": "CAD",
        "description": "Geofenced local lead discovery — 5km to 50km radius targeting",
        "available_for": ["starter", "growth", "enterprise"],
    },
}


async def seed_plans():
    """Seed/update plan definitions in MongoDB. Idempotent."""
    if db is None:
        return
    for tier_key, plan in PLAN_TIERS.items():
        plan_doc = {**plan, "tier": tier_key, "active": True, "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.subscription_plans.update_one(
            {"plan_id": plan["plan_id"]},
            {"$set": plan_doc},
            upsert=True,
        )
    # Deactivate old plans not in new system
    await db.subscription_plans.update_many(
        {"plan_id": {"$nin": [p["plan_id"] for p in PLAN_TIERS.values()]}},
        {"$set": {"active": False}},
    )
    logger.info("[Plans] Seeded 3 AUREM tiers (Starter/Growth/Enterprise)")


# ═══════════════════════════════════════════════════════════════
# USAGE TRACKING
# ═══════════════════════════════════════════════════════════════

def _current_month():
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def get_usage(tenant_id: str) -> dict:
    """Get current month usage for a tenant."""
    if db is None:
        return {"actions_used": 0, "voice_minutes_used": 0, "leads_enriched": 0, "pipeline_runs": 0}
    month = _current_month()
    usage = await db.usage_tracking.find_one(
        {"tenant_id": tenant_id, "month": month}, {"_id": 0}
    )
    if not usage:
        usage = {
            "tenant_id": tenant_id,
            "month": month,
            "actions_used": 0,
            "voice_minutes_used": 0,
            "leads_enriched": 0,
            "pipeline_runs": 0,
            "pipeline_runs_today": 0,
            "pipeline_runs_today_date": _today(),
        }
    # Reset daily counter if date changed
    if usage.get("pipeline_runs_today_date") != _today():
        usage["pipeline_runs_today"] = 0
        usage["pipeline_runs_today_date"] = _today()
    return usage


async def increment_usage(tenant_id: str, field: str, amount: int = 1):
    """Increment a usage counter for the current month."""
    if db is None:
        return
    month = _current_month()
    update = {"$inc": {field: amount}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}

    # Also track daily pipeline runs
    if field == "pipeline_runs":
        today = _today()
        update["$inc"]["pipeline_runs_today"] = amount
        update["$set"]["pipeline_runs_today_date"] = today

    await db.usage_tracking.update_one(
        {"tenant_id": tenant_id, "month": month},
        {**update, "$setOnInsert": {"tenant_id": tenant_id, "month": month, "created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


# ═══════════════════════════════════════════════════════════════
# PLAN ENFORCEMENT — The Gate
# ═══════════════════════════════════════════════════════════════

async def get_tenant_plan(tenant_id: str) -> dict:
    """Get the plan tier config for a tenant."""
    if db is None:
        return PLAN_TIERS["starter"]

    # Check workspace for plan assignment
    workspace = await db.aurem_workspaces.find_one(
        {"tenant_id": tenant_id}, {"_id": 0, "plan": 1, "tier": 1}
    )
    tier = "starter"
    if workspace:
        t = workspace.get("tier") or workspace.get("plan") or "starter"
        if t in PLAN_TIERS:
            tier = t
        elif t in ("trial", "free"):
            tier = "starter"

    # Also check user record
    user = await db.users.find_one(
        {"tenant_id": tenant_id}, {"_id": 0, "tier": 1}
    )
    if user and user.get("tier") in PLAN_TIERS:
        tier = user["tier"]

    # Get plan from DB (may have admin overrides)
    plan_doc = await db.subscription_plans.find_one(
        {"tier": tier, "active": True}, {"_id": 0}
    )
    if plan_doc:
        return plan_doc
    return {**PLAN_TIERS.get(tier, PLAN_TIERS["starter"]), "tier": tier}


async def check_action_limit(tenant_id: str) -> dict:
    """Check if tenant can perform another action. Returns gate result."""
    plan = await get_tenant_plan(tenant_id)
    usage = await get_usage(tenant_id)
    limits = plan.get("limits", {})

    actions_limit = limits.get("actions_per_month", 500)
    actions_used = usage.get("actions_used", 0)

    # -1 = unlimited
    if actions_limit == -1:
        return {"allowed": True, "actions_used": actions_used, "actions_limit": "unlimited", "tier": plan.get("tier", "starter")}

    if actions_used >= actions_limit:
        return {
            "allowed": False,
            "reason": "monthly_action_limit",
            "actions_used": actions_used,
            "actions_limit": actions_limit,
            "tier": plan.get("tier", "starter"),
            "message": f"Monthly limit reached ({actions_used}/{actions_limit} actions). Upgrade at aurem.live/pricing",
        }

    pct = round(actions_used / max(actions_limit, 1) * 100)
    return {
        "allowed": True,
        "actions_used": actions_used,
        "actions_limit": actions_limit,
        "usage_pct": pct,
        "tier": plan.get("tier", "starter"),
    }


async def check_pipeline_limit(tenant_id: str) -> dict:
    """Check if tenant can run another pipeline today."""
    plan = await get_tenant_plan(tenant_id)
    usage = await get_usage(tenant_id)
    limits = plan.get("limits", {})

    daily_limit = limits.get("pipeline_runs_per_day", 3)

    # Reset daily counter if date changed
    if usage.get("pipeline_runs_today_date") != _today():
        runs_today = 0
    else:
        runs_today = usage.get("pipeline_runs_today", 0)

    if daily_limit == -1:
        return {"allowed": True, "runs_today": runs_today, "daily_limit": "unlimited"}

    if runs_today >= daily_limit:
        return {
            "allowed": False,
            "reason": "daily_pipeline_limit",
            "runs_today": runs_today,
            "daily_limit": daily_limit,
            "message": f"Daily pipeline limit reached ({runs_today}/{daily_limit}). Resets at midnight UTC.",
        }

    return {"allowed": True, "runs_today": runs_today, "daily_limit": daily_limit}


async def check_feature_access(tenant_id: str, feature: str) -> dict:
    """Check if a feature is enabled for the tenant's plan."""
    plan = await get_tenant_plan(tenant_id)
    features = plan.get("features", {})

    enabled = features.get(feature, False)
    if enabled is False:
        return {
            "allowed": False,
            "reason": "feature_not_in_plan",
            "feature": feature,
            "tier": plan.get("tier", "starter"),
            "message": f"'{feature}' is not available on the {plan.get('name', 'Starter')} plan. Upgrade at aurem.live/pricing",
        }
    return {"allowed": True, "feature": feature, "value": enabled}


async def get_usage_summary(tenant_id: str) -> dict:
    """Get full usage summary for sidebar widget."""
    plan = await get_tenant_plan(tenant_id)
    usage = await get_usage(tenant_id)
    limits = plan.get("limits", {})

    actions_limit = limits.get("actions_per_month", 500)
    actions_used = usage.get("actions_used", 0)

    if actions_limit == -1:
        pct = 0
        status = "unlimited"
    else:
        pct = round(actions_used / max(actions_limit, 1) * 100)
        if pct >= 100:
            status = "exceeded"
        elif pct >= 80:
            status = "warning"
        else:
            status = "ok"

    return {
        "tenant_id": tenant_id,
        "tier": plan.get("tier", "starter"),
        "plan_name": plan.get("name", "Starter"),
        "price_monthly": plan.get("price_monthly", 97),
        "currency": plan.get("currency", "CAD"),
        "actions_used": actions_used,
        "actions_limit": actions_limit if actions_limit != -1 else "unlimited",
        "usage_pct": pct,
        "status": status,
        "month": _current_month(),
        "voice_minutes_used": usage.get("voice_minutes_used", 0),
        "leads_enriched": usage.get("leads_enriched", 0),
        "pipeline_runs": usage.get("pipeline_runs", 0),
        "pipeline_runs_today": usage.get("pipeline_runs_today", 0),
        "features": plan.get("features", {}),
    }
