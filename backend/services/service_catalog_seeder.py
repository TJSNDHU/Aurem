"""
AUREM Service Catalog Seeder
============================
Seeds `db.service_catalog` with 16 services in 5 clusters + bundle rules.
Idempotent — safe to run multiple times. Runs as background task at startup.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════
# CATALOG — 16 services across 5 clusters
# All prices in CAD, tax-inclusive.
# Margin = (price - cost) / price
# ═════════════════════════════════════════════════════════════════

CATALOG = [
    # ───────── CLUSTER 1: Repair & Performance ─────────
    {
        "service_id": "website_repair",
        "name": "Website Repair Engine",
        "cluster": "repair",
        "cluster_order": 1,
        "description": "Auto-fixes broken links, schema errors, layout shifts. Real-time Sentinel-verified patches.",
        "cost_monthly": 6.00,
        "price_monthly": 29.00,
        "backend_service": "auto_repair.py",
        "dependencies": ["primitive_pixel", "primitive_audit", "primitive_patch"],
        "billing_type": "recurring",
    },
    {
        "service_id": "speed_booster",
        "name": "Speed Test Score Booster",
        "cluster": "repair",
        "cluster_order": 2,
        "description": "Optimizes LCP, CLS, FID. Compress JS, lazy-load images, inline critical CSS.",
        "cost_monthly": 5.00,
        "price_monthly": 29.00,
        "backend_service": "health_score_engine.py",
        "dependencies": ["primitive_audit"],
        "billing_type": "recurring",
    },
    {
        "service_id": "seo_pro",
        "name": "SEO Optimizer Pro",
        "cluster": "repair",
        "cluster_order": 3,
        "description": "Schema markup, meta tags, sitemap auto-gen. Google-first structured data.",
        "cost_monthly": 7.00,
        "price_monthly": 39.00,
        "backend_service": "seo_engine.py",
        "dependencies": ["primitive_audit", "primitive_patch"],
        "billing_type": "recurring",
    },
    {
        "service_id": "geo_ai_rank",
        "name": "GEO — Generative Engine Optimization",
        "cluster": "repair",
        "cluster_order": 4,
        "description": "Rank in ChatGPT, Perplexity, Google AI Overviews. AI-first content & schema.",
        "cost_monthly": 8.00,
        "price_monthly": 49.00,
        "backend_service": "ghost_geo_router.py",
        "dependencies": ["primitive_audit"],
        "billing_type": "recurring",
    },
    {
        "service_id": "cwv_monitor",
        "name": "Core Web Vitals Monitor",
        "cluster": "repair",
        "cluster_order": 5,
        "description": "24/7 performance tracking. Alerts when LCP/CLS regresses. Automatic remediation.",
        "cost_monthly": 4.00,
        "price_monthly": 19.00,
        "backend_service": "nightly_health_check.py",
        "dependencies": ["primitive_pixel"],
        "billing_type": "recurring",
    },
    # ───────── CLUSTER 2: Security & Compliance ─────────
    {
        "service_id": "security_patcher",
        "name": "Security Patcher (Shannon)",
        "cluster": "security",
        "cluster_order": 1,
        "description": "XSS, CSRF, missing headers, weak TLS — auto-patched. OWASP Top 10 coverage.",
        "cost_monthly": 9.00,
        "price_monthly": 49.00,
        "backend_service": "shannon_security.py",
        "dependencies": ["primitive_audit", "primitive_patch"],
        "billing_type": "recurring",
    },
    {
        "service_id": "casl_compliance",
        "name": "CASL Compliance Auto",
        "cluster": "security",
        "cluster_order": 2,
        "description": "Canadian anti-spam + cookie consent banner + privacy policy generator.",
        "cost_monthly": 5.00,
        "price_monthly": 39.00,
        "backend_service": "casl_compliance.py",
        "dependencies": ["primitive_pixel", "primitive_patch"],
        "billing_type": "recurring",
    },
    {
        "service_id": "soc2_audit",
        "name": "SOC2 Audit Chain",
        "cluster": "security",
        "cluster_order": 3,
        "description": "Enterprise-grade audit trail, access logs, compliance reports. Monthly attestation.",
        "cost_monthly": 14.00,
        "price_monthly": 99.00,
        "backend_service": "soc2_compliance_router.py",
        "dependencies": ["primitive_audit"],
        "billing_type": "recurring",
    },
    {
        "service_id": "auto_heal",
        "name": "Auto-Heal Loop 24/7",
        "cluster": "security",
        "cluster_order": 4,
        "description": "Error monitoring + auto-rollback. Self-repair in under 60 seconds.",
        "cost_monthly": 11.00,
        "price_monthly": 59.00,
        "backend_service": "self_repair_loop.py",
        "dependencies": ["primitive_pixel", "primitive_patch"],
        "billing_type": "recurring",
    },
    {
        "service_id": "security_vanguard",
        "name": "AUREM Vanguard — Lead Swarm",
        "cluster": "security",
        "cluster_order": 5,
        "description": "8-endpoint Vanguard swarm: multi-agent lead generation, channel-blast orchestration, live mission tracking. Production-proven with 5,887+ hits/30d.",
        "cost_monthly": 3.00,
        "price_monthly": 49.00,
        "backend_service": "aurem_vanguard_router.py",
        "dependencies": ["primitive_audit"],
        "billing_type": "recurring",
        "limits": {"features": ["multi_agent_swarm", "channel_blast", "live_mission_tracking", "api_access"]},
    },
    # ───────── CLUSTER 3: CRM — 3 Volume Tiers ─────────
    {
        "service_id": "crm_starter",
        "name": "CRM Starter",
        "cluster": "crm",
        "cluster_order": 1,
        "description": "Lead scoring + pipeline + reviews mgmt. 50 calls / 250 SMS / 1,000 emails per month.",
        "cost_monthly": 5.00,
        "price_monthly": 29.00,
        "backend_service": "crm_router.py",
        "limits": {"calls": 50, "sms": 250, "emails": 1000},
        "billing_type": "recurring",
    },
    {
        "service_id": "crm_growth",
        "name": "CRM Growth",
        "cluster": "crm",
        "cluster_order": 2,
        "description": "Everything in Starter + invoice automation + CRM sync (HubSpot/SF/Pipedrive). 250 calls / 1,500 SMS / 5,000 emails.",
        "cost_monthly": 22.00,
        "price_monthly": 79.00,
        "backend_service": "crm_router.py",
        "limits": {"calls": 250, "sms": 1500, "emails": 5000},
        "billing_type": "recurring",
    },
    {
        "service_id": "crm_scale",
        "name": "CRM Scale",
        "cluster": "crm",
        "cluster_order": 3,
        "description": "Everything in Growth + priority routing + custom workflows + API access. 1,000 calls / 7,500 SMS / 25,000 emails.",
        "cost_monthly": 85.00,
        "price_monthly": 249.00,
        "backend_service": "crm_router.py",
        "limits": {"calls": 1000, "sms": 7500, "emails": 25000},
        "billing_type": "recurring",
    },
    # ───────── CLUSTER 4: Marketing & Outreach ─────────
    {
        "service_id": "email_campaigns",
        "name": "AI Email Campaigns",
        "cluster": "marketing",
        "cluster_order": 1,
        "description": "1,000 AI-generated emails/mo. A/B tested subject lines, auto-segmented lists.",
        "cost_monthly": 6.00,
        "price_monthly": 39.00,
        "backend_service": "email_engine.py",
        "billing_type": "recurring",
    },
    {
        "service_id": "social_autopilot",
        "name": "Social Media Autopilot",
        "cluster": "marketing",
        "cluster_order": 2,
        "description": "Auto-post on FB/IG/LinkedIn + AI reply to comments/DMs. 60 posts/mo included.",
        "cost_monthly": 9.00,
        "price_monthly": 59.00,
        "backend_service": "social_media_service.py",
        "billing_type": "recurring",
    },
    {
        "service_id": "social_reels",
        "name": "Social Intelligence Reels",
        "cluster": "marketing",
        "cluster_order": 3,
        "description": "AUREM tracks your social & auto-generates reels showcasing AI wins on your business. Posted with #PoweredByAUREM for brand lift.",
        "cost_monthly": 11.00,
        "price_monthly": 69.00,
        "backend_service": "social_media_service.py",
        "billing_type": "recurring",
    },
    # ───────── CLUSTER 5: Power User ─────────
    {
        "service_id": "voice_agent_ai",
        "name": "AUREM Voice Agent (AI Inbound)",
        "cluster": "power",
        "cluster_order": 1,
        "description": "24/7 AI receptionist. Handles inbound calls, qualifies leads, books appointments, transfers hot ones to you. Retell-powered. 400 minutes/mo included, $0.35/min overage.",
        "cost_monthly": 28.00,
        "price_monthly": 149.00,
        "backend_service": "voice_agent_router.py",
        "dependencies": ["primitive_pixel"],
        "billing_type": "recurring",
        "limits": {"minutes": 400},
    },
    {
        "service_id": "genetic_repair",
        "name": "Genetic Repair (on-demand)",
        "cluster": "power",
        "cluster_order": 2,
        "description": "AI-based code mutation for stubborn bugs. $19 per fix. No subscription required.",
        "cost_monthly": 3.00,
        "price_monthly": 19.00,
        "backend_service": "genetic_repair.py",
        "billing_type": "one_time",
        "unit_label": "per repair",
    },
    {
        "service_id": "sovereign_privacy",
        "name": "Sovereign Privacy Mode",
        "cluster": "compliance",
        "cluster_order": 50,
        "description": "Route ALL LLM calls through the Canadian Sovereign Node (Llama 3.1). Your data never leaves Canadian soil. Required for clinics, legal, finance.",
        "cost_monthly": 8.00,
        "price_monthly": 49.00,
        "backend_service": "privacy_mode_router.py",
        "dependencies": [],
        "billing_type": "recurring",
    },
    {
        "service_id": "daily_intel",
        "name": "Daily Intel Briefing",
        "cluster": "growth",
        "cluster_order": 51,
        "description": "Every morning at 7 AM: a curated digest of competitor launches, industry news, and market signals scraped fresh from the web via Tavily.",
        "cost_monthly": 4.00,
        "price_monthly": 29.00,
        "backend_service": "daily_intel_engine.py",
        "dependencies": [],
        "billing_type": "recurring",
    },
    # ───────── CLUSTER 6: Site Monitoring (NEW - iter 257) ─────────
    {
        "service_id": "site_monitor_lite",
        "name": "Site Monitor — Lite",
        "cluster": "monitor",
        "cluster_order": 1,
        "description": "24x7 website uptime monitoring. 5 URLs tracked every 10 min. Email alerts on downtime + recovery. Live uptime dashboard.",
        "cost_monthly": 1.00,
        "price_monthly": 29.00,
        "backend_service": "site_monitor.py",
        "dependencies": ["primitive_pixel"],
        "billing_type": "recurring",
        "limits": {"max_urls": 5, "check_interval_min": 10, "features": ["email_alerts", "uptime_dashboard"]},
    },
    {
        "service_id": "site_monitor_pro",
        "name": "Site Monitor — Pro",
        "cluster": "monitor",
        "cluster_order": 2,
        "description": "Everything in Lite + 25 URLs, 5-min checks, WhatsApp alerts, incident history, public status page.",
        "cost_monthly": 3.00,
        "price_monthly": 99.00,
        "backend_service": "site_monitor.py",
        "dependencies": ["primitive_pixel", "primitive_audit"],
        "billing_type": "recurring",
        "limits": {"max_urls": 25, "check_interval_min": 5, "features": ["email_alerts", "whatsapp_alerts", "status_page", "incident_history"]},
    },
    {
        "service_id": "site_monitor_enterprise",
        "name": "Site Monitor — Enterprise",
        "cluster": "monitor",
        "cluster_order": 3,
        "description": "Unlimited URLs, 1-min checks, WhatsApp + SMS alerts, AI root-cause analysis, white-label status page, priority SLA.",
        "cost_monthly": 8.00,
        "price_monthly": 249.00,
        "backend_service": "site_monitor.py",
        "dependencies": ["primitive_pixel", "primitive_audit", "primitive_patch"],
        "billing_type": "recurring",
        "limits": {"max_urls": -1, "check_interval_min": 1, "features": ["email_alerts", "whatsapp_alerts", "sms_alerts", "ai_rca", "white_label_status", "priority_sla"]},
    },
]


# Bundle discount tiers — FULLY AUTOMATIC
BUNDLE_RULES = [
    {"min_services": 3, "discount_pct": 15, "label": "Pick 3+ → Save 15%"},
    {"min_services": 5, "discount_pct": 25, "label": "Pick 5+ → Save 25%"},
    {"min_services": 8, "discount_pct": 35, "label": "Pick 8+ → Save 35%"},
    {"min_services": 12, "discount_pct": 45, "label": "All-in → Save 45%"},
]


# Primitives — FREE with any RECURRING paid service (not one-offs)
PRIMITIVES = [
    {"primitive_id": "primitive_pixel", "name": "Pixel + Monitoring", "cost_monthly": 1.00},
    {"primitive_id": "primitive_audit", "name": "Weekly Site Audit", "cost_monthly": 2.00},
    {"primitive_id": "primitive_patch", "name": "Basic Patch Deployment", "cost_monthly": 3.00},
]


async def seed_service_catalog(db):
    """Idempotent seeder. Upserts all 16 services + bundle rules + primitives."""
    if db is None:
        logger.warning("[catalog-seeder] db is None, skipping")
        return

    try:
        now = datetime.now(timezone.utc).isoformat()
        upserted = 0

        for svc in CATALOG:
            svc_doc = dict(svc)
            # Auto-calc margin
            if svc_doc["price_monthly"] > 0:
                svc_doc["margin_pct"] = round(
                    ((svc_doc["price_monthly"] - svc_doc["cost_monthly"]) / svc_doc["price_monthly"]) * 100, 1
                )
            svc_doc["updated_at"] = now

            existing = await db.service_catalog.find_one({"service_id": svc_doc["service_id"]})
            if not existing:
                svc_doc["created_at"] = now
                svc_doc["status"] = svc_doc.get("status", "live")
                await db.service_catalog.insert_one(svc_doc)
                upserted += 1
            else:
                # Only update non-user-editable fields (preserve admin price edits)
                await db.service_catalog.update_one(
                    {"service_id": svc_doc["service_id"]},
                    {"$set": {
                        "cluster": svc_doc["cluster"],
                        "cluster_order": svc_doc["cluster_order"],
                        "description": svc_doc["description"],
                        "backend_service": svc_doc.get("backend_service"),
                        "dependencies": svc_doc.get("dependencies", []),
                        "billing_type": svc_doc.get("billing_type", "recurring"),
                        "limits": svc_doc.get("limits"),
                        "unit_label": svc_doc.get("unit_label"),
                        "updated_at": now,
                    }}
                )

        # Bundle rules
        await db.bundle_rules.delete_many({})
        for rule in BUNDLE_RULES:
            await db.bundle_rules.insert_one({**rule, "updated_at": now})

        # Primitives
        for prim in PRIMITIVES:
            await db.primitives.update_one(
                {"primitive_id": prim["primitive_id"]},
                {"$set": {**prim, "updated_at": now}},
                upsert=True,
            )

        logger.info(f"[catalog-seeder] Seeded {upserted} new services, {len(CATALOG) - upserted} existing updated. Bundle rules: {len(BUNDLE_RULES)}. Primitives: {len(PRIMITIVES)}.")
    except Exception as e:
        logger.exception(f"[catalog-seeder] Failed: {e}")
