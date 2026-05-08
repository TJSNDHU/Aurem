"""
═══════════════════════════════════════════════════════════════════════════════
AUREM CENTRAL CONFIGURATION — Single Source of Truth
═══════════════════════════════════════════════════════════════════════════════

Change ANY value here and it propagates everywhere automatically.
DO NOT hardcode prices, copy, emails, trial days, or feature lists in any
other file. Import from this module instead:

    from config.aurem_config import AUREM_CONFIG, get_plan, trial_cta_text

Frontend mirror lives at: frontend/src/config/aurem.config.js
Public consumer endpoint:  GET /api/public/config
"""
from __future__ import annotations

AUREM_CONFIG = {

    # ── COMPANY ──────────────────────────────────────────
    "company": {
        "name": "Polaris Built Inc.",
        "brand": "AUREM",
        "tagline": "Your website is losing you customers right now.",
        "email_support": "ora@aurem.live",
        "email_noreply": "noreply@aurem.live",
        "email_sales": "ora@aurem.live",
        "email_abuse": "abuse@aurem.live",
        "website": "https://aurem.live",
        "address": "Mississauga, Ontario, Canada",
        "phone": "+14314500004",
        "founded": "2025",
    },

    # ── TRIAL ────────────────────────────────────────────
    "trial": {
        "days": 7,
        "reminder_day": 6,
        "card_capture_day": 5,
        "grace_period_hours": 24,
    },

    # ── PRICING (CAD) ────────────────────────────────────
    # NOTE: stripe_price_id values are pulled at runtime from
    # env vars STRIPE_PRICE_STARTER / _GROWTH / _ENTERPRISE.
    # The strings here are placeholders for visibility; billing
    # code in shared/commercial/billing_service.py reads env first.
    "pricing": {
        "starter": {
            "name": "Starter",
            "price_cad": 97,
            "price_display": "$97",
            "billing": "CAD/month",
            "stripe_price_id_env": "STRIPE_PRICE_STARTER",
            "voice_minutes": 0,
            "ai_actions": 500,
            "workspaces": 1,
            "tag": "Independent businesses",
        },
        "growth": {
            "name": "Growth",
            "price_cad": 449,
            "price_display": "$449",
            "billing": "CAD/month",
            "stripe_price_id_env": "STRIPE_PRICE_GROWTH",
            "voice_minutes": 300,
            "ai_actions": 5000,
            "workspaces": 3,
            "tag": "Most popular",
            "popular": True,
        },
        "enterprise": {
            "name": "Enterprise",
            "price_cad": 997,
            "price_display": "$997",
            "billing": "CAD/month",
            "stripe_price_id_env": "STRIPE_PRICE_ENTERPRISE",
            "voice_minutes": -1,   # unlimited
            "ai_actions": -1,
            "workspaces": -1,
            "tag": "Agencies + multi-location",
        },
    },

    # ── FEATURES PER PLAN ────────────────────────────────
    "plan_features": {
        "starter": [
            "Website pixel — nightly scan + repair",
            "SEO auto-repair — weekly fixes deployed",
            "ORA Chat on your website — 24/7",
            "Lead follow-up by email + SMS",
            "Morning Brief at 7am daily",
            "500 AI actions/month",
            "GEO Optimization",
            "CASL-compliant outreach",
        ],
        "growth": [
            "Everything in Starter",
            "ORA Voice AI — 300 min/month included",
            "5,000 AI actions/month",
            "Economic Intelligence dashboard",
            "3 workspaces",
            "Partner referral access",
            "Priority support",
        ],
        "enterprise": [
            "Everything in Growth",
            "Unlimited AI actions",
            "25 concurrent voice sessions",
            "White-label — your brand, your domain",
            "WordPress plugin — zero manual install",
            "Unlimited workspaces",
            "Dedicated onboarding call",
            "Slack support channel",
        ],
    },

    # ── ORA VOICE ────────────────────────────────────────
    "ora_voice": {
        "agent_name": "ORA",
        "company_name": "AUREM",
        "from_number": "+14314500004",
        "max_call_duration_seconds": 180,
        "trial_url": "https://aurem.live",
    },

    # ── PILLARS ──────────────────────────────────────────
    "pillars": {
        "P1": {"name": "Infrastructure", "components": ["mongodb", "redis", "emergent", "cloudflare"]},
        "P2": {"name": "Intelligence",   "components": ["ora_brain", "groq", "openai", "soul_md"]},
        "P3": {"name": "Outreach",       "components": ["twilio_voice", "twilio_sms", "waba", "resend", "retell"]},
        "P4": {"name": "Revenue",        "components": ["stripe", "subscriptions", "price_ids", "payout"]},
    },

    # ── AGENTS ───────────────────────────────────────────
    "agents": {
        "scout":    {"id": "scout_ora",    "role": "Lead Intelligence"},
        "envoy":    {"id": "envoy_ora",    "role": "Multi-Channel Outreach"},
        "closer":   {"id": "closer_ora",   "role": "Revenue Conversion"},
        "followup": {"id": "followup_ora", "role": "Pipeline Nurture"},
        "referral": {"id": "referral_ora", "role": "Growth Engine"},
        "hunter":   {"id": "hunter_ora",   "role": "Cold Prospect"},
        "ora_brain":{"id": "ora_brain",    "role": "LLM Orchestration"},
    },

    # ── MORNING BRIEF ────────────────────────────────────
    "morning_brief": {
        "send_time_est": "07:00",
        "from_email": "ora@aurem.live",
        "subject_template": "AUREM Morning Brief — {date}",
        "telegram_enabled": False,
    },

    # ── COMPLIANCE ───────────────────────────────────────
    "compliance": {
        "casl": True,
        "pipeda": True,
        "opt_out_keywords": ["stop", "remove", "opt out", "unsubscribe",
                             "do not call", "not interested"],
        "dnc_collection": "dnc_list",
    },

    # ── SCAN WIDGET ──────────────────────────────────────
    "scan_widget": {
        "free_scans_per_device": 3,
        "cache_minutes": 5,
        "quota_reset_hours": 24,
    },
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_plan(plan_id: str) -> dict | None:
    """Lookup a pricing plan by id (case-insensitive)."""
    return AUREM_CONFIG["pricing"].get((plan_id or "").lower())


def trial_days() -> int:
    return int(AUREM_CONFIG["trial"]["days"])


def trial_cta_text() -> str:
    return f"Start Free {trial_days()}-Day Trial"


def public_config() -> dict:
    """Filtered public-facing slice of config (safe for /api/public/config)."""
    cfg = AUREM_CONFIG
    return {
        "company": cfg["company"],
        "trial": cfg["trial"],
        "pricing": cfg["pricing"],
        "plan_features": cfg["plan_features"],
        "scan_widget": cfg["scan_widget"],
        "copy": {
            "hero_headline": cfg["company"]["tagline"],
            "trial_cta": trial_cta_text(),
            "trial_days": trial_days(),
            "trial_note": "No credit card required",
            "cancel_note": "Cancel anytime in one click",
        },
    }
