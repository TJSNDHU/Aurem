"""
services/recommended_bundles.py — iter 326j Gaps 3 + 5
═══════════════════════════════════════════════════════════════════════════
Bundling strategy + recommended-bundle wizard.

PROBLEM SOLVED
──────────────
1. `subscription_plans` collection has 5 ID-only shells (Free/Starter/
   Professional/Enterprise/Growth) with price/interval/features all NULL.
   The actual sellable units are the 21 services in `service_catalog`.
   This module **re-seeds `subscription_plans`** as proper TIERS that
   map to bundles of catalog services — so the checkout UI never reads
   blank rows.

2. There's no "recommended bundle for industry X" — customers see all
   21 services with no opinionated starting point. We seed 4 industry
   bundles (services_starter, smb_growth, security_pro, enterprise_max)
   plus 4 industry-specific bundles (restaurant, salon, clinic, agency).

DESIGN
──────
• `subscription_plans` rows are now TIER-LEVEL bundles (Starter $99,
  Growth $199, Pro $399, Enterprise $799) with service_ids + features.
• `recommended_bundles` is a separate collection for industry-specific
  picks (restaurant, salon, clinic, agency). Industry param filters them.
• Bundle discount applies AUTOMATICALLY via the existing
  `bundle_rules` collection (3+ → 15%, 5+ → 25%, etc.).

Idempotent — safe to call on every startup.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ── Canonical tier bundles → seed into subscription_plans ─────────
TIER_BUNDLES: list[dict[str, Any]] = [
    {
        "plan_id":          "free_forever",
        "name":             "Free Forever",
        "price_monthly":    0,
        "currency":         "cad",
        "interval":         "month",
        "tagline":          "Pixel + site monitoring. Forever free.",
        "service_ids":      [],  # no paid services — primitives only
        "features": [
            "AUREM Pixel installed on 1 site",
            "Weekly site audit summary by email",
            "Read-only ORA-CTO chat (5 questions/day)",
        ],
        "is_default":       True,
        "tier_order":       0,
    },
    {
        "plan_id":          "starter",
        "name":             "Starter",
        "price_monthly":    99,
        "currency":         "cad",
        "interval":         "month",
        "tagline":          "Repair + Monitor — the autonomous duo.",
        "service_ids": [
            "website_repair",      # $29 — auto-fix broken links/schema
            "speed_booster",       # $29 — Core Web Vitals optimisation
            "site_monitor_lite",   # $29 — 24x7 uptime
            "daily_intel",         # $29 — Tavily competitor digest
        ],
        "features": [
            "Auto-repair broken links + schema errors",
            "Core Web Vitals auto-optimisation",
            "24x7 site uptime monitoring (5 URLs, 10-min checks)",
            "Daily competitor & market intelligence brief",
            "Save 15% (4 services bundle discount applied)",
        ],
        "tier_order":       1,
    },
    {
        "plan_id":          "growth",
        "name":             "Growth",
        "price_monthly":    199,
        "currency":         "cad",
        "interval":         "month",
        "tagline":          "Sales + CRM + Marketing autonomy.",
        "service_ids": [
            "website_repair", "speed_booster", "seo_pro",
            "crm_starter", "email_campaigns",
            "site_monitor_lite",
        ],
        "features": [
            "Everything in Starter",
            "AI Email Campaigns (1,000 emails/mo)",
            "CRM Starter (50 calls / 250 SMS / 1k emails)",
            "SEO Optimizer Pro (schema + meta + sitemap)",
            "Save 25% (6 services bundle discount applied)",
        ],
        "tier_order":       2,
    },
    {
        "plan_id":          "pro",
        "name":             "Pro",
        "price_monthly":    399,
        "currency":         "cad",
        "interval":         "month",
        "tagline":          "Security-first business automation.",
        "service_ids": [
            "website_repair", "speed_booster", "seo_pro", "geo_ai_rank",
            "security_patcher", "auto_heal", "casl_compliance",
            "crm_growth", "email_campaigns",
            "site_monitor_pro",
        ],
        "features": [
            "Everything in Growth",
            "AUREM Vanguard Lead Swarm",
            "Auto-Heal Loop 24/7 (60-second self-repair)",
            "Security Patcher (Shannon) — OWASP Top 10",
            "CASL anti-spam + cookie consent automation",
            "Save 35% (10 services bundle discount applied)",
        ],
        "tier_order":       3,
    },
    {
        "plan_id":          "enterprise",
        "name":             "Enterprise",
        "price_monthly":    799,
        "currency":         "cad",
        "interval":         "month",
        "tagline":          "All-in — sovereign compliance + voice AI.",
        "service_ids": [
            "website_repair", "speed_booster", "seo_pro", "geo_ai_rank", "cwv_monitor",
            "security_patcher", "casl_compliance", "soc2_audit", "auto_heal", "security_vanguard",
            "crm_scale", "email_campaigns", "social_autopilot", "social_reels",
            "voice_agent_ai", "sovereign_privacy", "daily_intel",
            "site_monitor_enterprise",
        ],
        "features": [
            "Everything in Pro",
            "AUREM Voice Agent (AI receptionist, 400 min/mo)",
            "Sovereign Privacy Mode (Canadian data only)",
            "SOC2 Audit Chain (monthly attestation)",
            "Social Media Autopilot + Intelligence Reels",
            "Site Monitor Enterprise (unlimited URLs, 1-min checks, AI RCA)",
            "Save 45% (18 services bundle discount applied)",
        ],
        "tier_order":       4,
    },
]


# ── Industry-specific recommended bundles ──────────────────────────
INDUSTRY_BUNDLES: list[dict[str, Any]] = [
    {
        "bundle_id":        "restaurant_growth",
        "industry":         "restaurant",
        "name":             "Restaurant — Grow Your Tables",
        "tagline":          "Reservations on autopilot + reviews boost.",
        "service_ids": [
            "voice_agent_ai", "crm_starter", "email_campaigns",
            "social_autopilot", "site_monitor_lite",
        ],
        "rationale":        "Voice agent handles after-hours reservations; CRM + email recover no-shows; social drives Instagram traffic.",
    },
    {
        "bundle_id":        "salon_loyalty",
        "industry":         "salon",
        "name":             "Salon — Fill Every Chair",
        "tagline":          "Booking recovery + retention automation.",
        "service_ids": [
            "voice_agent_ai", "crm_starter", "email_campaigns",
            "site_monitor_lite", "daily_intel",
        ],
        "rationale":        "Voice books appointments 24x7; CRM nudges lapsed clients; email runs birthday + retention loops.",
    },
    {
        "bundle_id":        "clinic_compliance",
        "industry":         "clinic",
        "name":             "Clinic — Compliant & Sovereign",
        "tagline":          "PHIPA-safe Canadian data + 24x7 monitoring.",
        "service_ids": [
            "sovereign_privacy", "casl_compliance", "auto_heal",
            "voice_agent_ai", "site_monitor_pro",
        ],
        "rationale":        "Sovereign Privacy keeps patient data on Canadian soil; CASL handles consent; voice triages calls.",
    },
    {
        "bundle_id":        "agency_starter",
        "industry":         "agency",
        "name":             "Agency — Sell Repair as a Service",
        "tagline":          "White-label the repair stack to your clients.",
        "service_ids": [
            "website_repair", "speed_booster", "seo_pro", "geo_ai_rank",
            "site_monitor_pro", "security_patcher",
        ],
        "rationale":        "Repair + GEO + monitor — agencies resell to their book of business at 3-5× markup.",
    },
]


# ── Seeder (idempotent) ──────────────────────────────────────────
async def seed_subscription_plans(db) -> dict[str, Any]:
    """Drop empty shells + upsert proper tier bundles into
    subscription_plans. Returns a per-row outcome summary."""
    if db is None:
        return {"ok": False, "reason": "db not ready"}

    now_iso = datetime.now(timezone.utc).isoformat()
    counts = {"upserted": 0, "removed_empty": 0}

    # Drop rows where every meaningful field is NULL (the 5 shells
    # that block the catalog UI today). Also drop the LEGACY `plan_*`
    # IDs from an earlier seeder that conflict with our new plan_ids
    # — they don't have service_ids so they're guaranteed-empty UX.
    LEGACY_IDS = (
        "plan_free", "plan_starter", "plan_professional",
        "plan_enterprise", "plan_growth",
    )
    res_legacy = await db.subscription_plans.delete_many(
        {"plan_id": {"$in": list(LEGACY_IDS)}}
    )
    res = await db.subscription_plans.delete_many({
        "$and": [
            {"$or": [{"price_monthly": None}, {"price_monthly": {"$exists": False}},
                     {"price": None}, {"price": {"$exists": False}}]},
            {"$or": [{"service_ids": None}, {"service_ids": {"$exists": False}},
                     {"service_ids": []}]},
            {"plan_id": {"$exists": False}},
        ],
    })
    counts["removed_empty"] = res.deleted_count + res_legacy.deleted_count

    for tier in TIER_BUNDLES:
        doc = dict(tier)
        doc["updated_at"] = now_iso
        await db.subscription_plans.update_one(
            {"plan_id": tier["plan_id"]},
            {"$set": doc, "$setOnInsert": {"created_at": now_iso}},
            upsert=True,
        )
        counts["upserted"] += 1

    logger.info(
        f"[recommended-bundles] seeded {counts['upserted']} tier bundles, "
        f"removed {counts['removed_empty']} empty rows"
    )
    return {"ok": True, **counts, "tiers": [t["plan_id"] for t in TIER_BUNDLES]}


async def seed_industry_bundles(db) -> dict[str, Any]:
    """Idempotently seed industry-specific recommended bundles."""
    if db is None:
        return {"ok": False, "reason": "db not ready"}
    now_iso = datetime.now(timezone.utc).isoformat()
    upserted = 0
    for b in INDUSTRY_BUNDLES:
        doc = dict(b)
        doc["updated_at"] = now_iso
        await db.recommended_bundles.update_one(
            {"bundle_id": b["bundle_id"]},
            {"$set": doc, "$setOnInsert": {"created_at": now_iso}},
            upsert=True,
        )
        upserted += 1
    logger.info(f"[recommended-bundles] seeded {upserted} industry bundles")
    return {"ok": True, "upserted": upserted,
            "industries": sorted({b["industry"] for b in INDUSTRY_BUNDLES})}


# ── Compute live pricing for a bundle (resolves catalog + discounts) ──
async def price_bundle(db, service_ids: list[str]) -> dict[str, Any]:
    """Resolve a list of service_ids → live price with bundle discount.

    Returns:
      {
        "ok":              True,
        "service_count":   int,
        "subtotal":        float,  # raw sum from catalog
        "discount_pct":    int,    # 0/15/25/35/45 per bundle_rules
        "discount_label":  "Pick 5+ → Save 25%" | "",
        "total":           float,  # subtotal * (1 - discount/100)
        "missing":         [str],  # service_ids not in catalog
        "items":           [{service_id, name, price_monthly}],
      }
    """
    if db is None:
        return {"ok": False, "reason": "db not ready"}
    if not service_ids:
        return {"ok": True, "service_count": 0, "subtotal": 0.0,
                "discount_pct": 0, "discount_label": "", "total": 0.0,
                "missing": [], "items": []}

    items: list[dict[str, Any]] = []
    subtotal = 0.0
    found_ids: set[str] = set()
    async for s in db.service_catalog.find(
        {"service_id": {"$in": service_ids}, "status": "live"},
        {"_id": 0, "service_id": 1, "name": 1, "price_monthly": 1}
    ):
        items.append({
            "service_id":    s["service_id"],
            "name":          s.get("name", ""),
            "price_monthly": float(s.get("price_monthly") or 0),
        })
        subtotal += float(s.get("price_monthly") or 0)
        found_ids.add(s["service_id"])

    missing = [sid for sid in service_ids if sid not in found_ids]

    # Resolve discount from bundle_rules (already seeded by catalog seeder)
    n = len(found_ids)
    discount_pct = 0
    discount_label = ""
    async for r in db.bundle_rules.find({}, {"_id": 0}).sort("min_services", -1):
        if n >= int(r.get("min_services") or 0):
            discount_pct = int(r.get("discount_pct") or 0)
            discount_label = r.get("label") or ""
            break

    total = round(subtotal * (1 - discount_pct / 100), 2)
    return {
        "ok":             True,
        "service_count":  n,
        "subtotal":       round(subtotal, 2),
        "discount_pct":   discount_pct,
        "discount_label": discount_label,
        "total":          total,
        "missing":        missing,
        "items":          items,
    }
