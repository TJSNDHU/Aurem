"""
AUREM Plans SSOT (Single Source of Truth)
═══════════════════════════════════════════════════════════════════════════
HYBRID model: mandatory base plan + optional à-la-carte add-ons.

NEVER duplicate this config anywhere. Backend route gates, Stripe webhooks,
frontend display, and trial enforcement all import from here.

Service IDs match `db.service_catalog` so the existing 25-service catalog
stays canonical for pricing + add-on UI.
"""

# ────────────────────────────────────────────────────────────────────────────
# CORE BASE PLANS (mandatory subscription)
# ────────────────────────────────────────────────────────────────────────────
PLANS = {
    "trial": {
        "plan_id": "trial",
        "name": "7-Day Trial",
        "price_cad": 0,
        "duration_days": 7,
        # Trial = core demo bundle. Capped at 50% of starter limits.
        "services": [
            "crm_starter",
            "email_campaigns",
            "cwv_monitor",
            "daily_intel",
        ],
        "limits": {
            "leads_limit": 50,
            "email_limit": 250,
            "sms_limit": 50,
            "voice_limit": 0,
            "campaigns_limit": 1,
            "agents_limit": 2,
            "websites_limit": 1,
            "ai_calls_limit": 500,
        },
    },
    "starter": {
        "plan_id": "starter",
        "name": "Starter",
        "price_cad": 97,
        "stripe_price_env": "STRIPE_PRICE_STARTER",  # set $STRIPE_PRICE_STARTER in .env
        "services": [
            "crm_starter",
            "email_campaigns",
            "cwv_monitor",
            "daily_intel",
            "website_repair",
            "casl_compliance",
            "speed_booster",
        ],
        "limits": {
            "leads_limit": 500,
            "email_limit": 2500,
            "sms_limit": 250,
            "voice_limit": 0,
            "campaigns_limit": 5,
            "agents_limit": 5,
            "websites_limit": 2,
            "ai_calls_limit": 5000,
        },
    },
    "growth": {
        "plan_id": "growth",
        "name": "Growth",
        "price_cad": 197,
        "stripe_price_env": "STRIPE_PRICE_GROWTH",
        "services": [
            # Inherits all starter services
            "crm_starter", "email_campaigns", "cwv_monitor", "daily_intel",
            "website_repair", "casl_compliance", "speed_booster",
            # Plus growth additions
            "crm_growth",
            "site_monitor_lite",
            "seo_pro",
        ],
        "limits": {
            "leads_limit": 5000,
            "email_limit": 25000,
            "sms_limit": 2500,
            "voice_limit": 100,
            "campaigns_limit": 25,
            "agents_limit": 15,
            "websites_limit": 10,
            "ai_calls_limit": 50000,
        },
    },
    "pro": {
        "plan_id": "pro",
        "name": "Pro",
        "price_cad": 447,
        "stripe_price_env": "STRIPE_PRICE_PRO",
        "services": [
            # Inherits all growth services
            "crm_starter", "email_campaigns", "cwv_monitor", "daily_intel",
            "website_repair", "casl_compliance", "speed_booster",
            "crm_growth", "site_monitor_lite", "seo_pro",
            # Plus pro additions
            "crm_scale",
            "site_monitor_pro",
            "voice_agent_ai",
            "security_patcher",
            "geo_ai_rank",
        ],
        "limits": {
            "leads_limit": 25000,
            "email_limit": 250000,
            "sms_limit": 10000,
            "voice_limit": 1000,
            "campaigns_limit": 100,
            "agents_limit": 50,
            "websites_limit": 25,
            "ai_calls_limit": 250000,
        },
    },
    "enterprise": {
        "plan_id": "enterprise",
        "name": "Enterprise",
        "price_cad": 997,
        "stripe_price_env": "STRIPE_PRICE_ENTERPRISE",
        "services": ["*"],  # wildcard — all current + future services
        "limits": {
            "leads_limit": 1_000_000,
            "email_limit": 1_000_000,
            "sms_limit": 100_000,
            "voice_limit": 25_000,
            "campaigns_limit": 10_000,
            "agents_limit": 1_000,
            "websites_limit": 1_000,
            "ai_calls_limit": 10_000_000,
        },
    },
    "lifetime_free": {
        "plan_id": "lifetime_free",
        "name": "Lifetime Free (Founder/Dogfood)",
        "price_cad": 0,
        "services": ["*"],
        "limits": {
            "leads_limit": 1_000_000,
            "email_limit": 1_000_000,
            "sms_limit": 100_000,
            "voice_limit": 25_000,
            "campaigns_limit": 10_000,
            "agents_limit": 1_000,
            "websites_limit": 1_000,
            "ai_calls_limit": 10_000_000,
        },
    },
}

# ────────────────────────────────────────────────────────────────────────────
# Service ID → which plan-tier first unlocks it (for UpgradeModal hints)
# ────────────────────────────────────────────────────────────────────────────
SERVICE_TO_MIN_PLAN = {}
for _pid in ("starter", "growth", "pro"):
    for _svc in PLANS[_pid]["services"]:
        if _svc not in SERVICE_TO_MIN_PLAN:
            SERVICE_TO_MIN_PLAN[_svc] = _pid

# ────────────────────────────────────────────────────────────────────────────
# Service ID → which usage_limits key gates its quota (None = no quota)
# ────────────────────────────────────────────────────────────────────────────
SERVICE_TO_LIMIT_KEY = {
    "crm_starter": "leads_limit",
    "crm_growth": "leads_limit",
    "crm_scale": "leads_limit",
    "email_campaigns": "email_limit",
    "voice_agent_ai": "voice_limit",
    # SMS-specific service id (not in catalog yet — will fall through if absent)
    "sms": "sms_limit",
    "scout": "leads_limit",
    "website_repair": "websites_limit",
    "site_monitor_lite": "websites_limit",
    "site_monitor_pro": "websites_limit",
    "site_monitor_enterprise": "websites_limit",
}


def has_wildcard(services_unlocked) -> bool:
    return isinstance(services_unlocked, list) and "*" in services_unlocked


def is_service_unlocked(service_id: str, services_unlocked) -> bool:
    if not services_unlocked:
        return False
    if has_wildcard(services_unlocked):
        return True
    return service_id in services_unlocked
