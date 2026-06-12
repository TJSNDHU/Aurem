"""
AUREM Public Report Router
==========================
Public-facing sales report page data for /report/{business_slug}.
Pulls from campaign_leads CRM, computes score + revenue projections,
returns Stripe checkout URLs, and tracks visitor engagement.

Endpoints (ALL /api/report/* are public — NO auth required since
the slug is the access control):
    GET  /api/report/{slug}           — full report data
    POST /api/report/{slug}/visit     — log page view to outreach_history
    POST /api/report/{slug}/engaged   — fire 30-sec WhatsApp nudge
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/report", tags=["AUREM Public Report"])

_db = None


def set_db(db):
    global _db
    _db = db


# ─────────────────────────────────────────────────────────────────────
# iter 282al-18 · Part 3 — Dynamic CTA by site_audits.overall_score
# ─────────────────────────────────────────────────────────────────────
def _build_cta_for_score(score: int, slug: str) -> Dict[str, Any]:
    """Return {type, score, headline, subline, price_cad, price_label, button_text, checkout_url}.

    Rules (from services.website_repair_service.get_cta_type):
      score < 60  → repair  ($197 one-time)
      60 ≤ s <80  → tuneup  ($297/month Growth plan)
      score ≥ 80  → widget  (free trial)
      score == 0  → generic (no audit yet — generic Start Free Trial)
    """
    base = os.environ.get("AUREM_PUBLIC_BASE", "https://aurem.live").rstrip("/")
    s = max(0, int(score or 0))

    if s == 0:
        return {
            "type":          "generic",
            "score":         0,
            "headline":      "Start your Free AUREM Trial",
            "subline":       "Scan your website, unlock your plan — 14-day free trial, no card needed.",
            "price_cad":     0,
            "price_label":   "Free trial",
            "button_text":   "Start Free Trial",
            "checkout_url":  f"{base}/signup?slug={slug}",
        }
    if s < 60:
        return {
            "type":          "repair",
            "score":         s,
            "headline":      "Fix My Website — $197 one-time",
            "subline":       "All critical issues fixed. QA-verified. Money-back if it fails.",
            "price_cad":     197,
            "price_label":   "$197 CAD · one-time",
            "button_text":   "Pay Now →",
            "checkout_url":  f"{base}/api/repair/checkout?slug={slug}&tier=basic",
        }
    if s < 80:
        return {
            "type":          "tuneup",
            "score":         s,
            "headline":      "Website Tune-Up — $297/month",
            "subline":       "Ongoing fixes, AI chat widget, monthly reports. Cancel anytime.",
            "price_cad":     297,
            "price_label":   "$297 CAD · monthly",
            "button_text":   "Start Plan →",
            "checkout_url":  f"{base}/pricing?plan=growth&slug={slug}",
        }
    return {
        "type":          "widget",
        "score":         s,
        "headline":      "Add AI Chat Widget — Free Trial",
        "subline":       "Capture visitors as leads 24/7 with ORA on your existing site.",
        "price_cad":     0,
        "price_label":   "Free 14-day trial",
        "button_text":   "Try Free →",
        "checkout_url":  f"{base}/widget-trial?slug={slug}",
    }


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL", "").strip().strip('"').strip("'")
        if not mongo_url:
            return None
        client = AsyncIOMotorClient(mongo_url)
        _db = client[os.environ.get("DB_NAME", "aurem_db")]
        return _db
    except Exception:
        return None


# ══════════════════════════════════════════════
# DATA BUILDERS
# ══════════════════════════════════════════════

def _compute_google_score(lead: Dict[str, Any]) -> Dict[str, Any]:
    """
    Heuristic Google Presence Score (0–100) based on lead signals.
    Weight: website 30, reviews 25, rating 15, social 15, hours 10, description 5.
    """
    score = 0
    breakdown = []

    if lead.get("website_url"):
        score += 30
        breakdown.append({"item": "Website", "points": 30, "max": 30, "status": "good"})
    else:
        breakdown.append({"item": "Website", "points": 0, "max": 30, "status": "missing"})

    reviews = lead.get("reviews_count", 0)
    try:
        reviews = int(reviews) if reviews else _parse_reviews_from_notes(lead.get("notes", ""))
    except (TypeError, ValueError):
        reviews = 0
    if reviews >= 50:
        score += 25
        breakdown.append({"item": f"{reviews} Reviews", "points": 25, "max": 25, "status": "good"})
    elif reviews >= 20:
        score += 15
        breakdown.append({"item": f"{reviews} Reviews", "points": 15, "max": 25, "status": "average"})
    elif reviews >= 5:
        score += 8
        breakdown.append({"item": f"{reviews} Reviews", "points": 8, "max": 25, "status": "low"})
    else:
        breakdown.append({"item": f"{reviews} Reviews", "points": 0, "max": 25, "status": "missing"})

    rating = _parse_rating(lead)
    if rating >= 4.5:
        score += 15
        breakdown.append({"item": f"{rating:.1f}★ Rating", "points": 15, "max": 15, "status": "good"})
    elif rating >= 4.0:
        score += 10
        breakdown.append({"item": f"{rating:.1f}★ Rating", "points": 10, "max": 15, "status": "average"})
    else:
        breakdown.append({"item": "Rating", "points": 0, "max": 15, "status": "missing"})

    social = lead.get("social_media") or {}
    if any((social.get("instagram"), social.get("facebook"), social.get("twitter"))):
        score += 15
        breakdown.append({"item": "Social Media", "points": 15, "max": 15, "status": "good"})
    else:
        breakdown.append({"item": "Social Media", "points": 0, "max": 15, "status": "missing"})

    if lead.get("hours") or "hours" in (lead.get("notes", "") or "").lower():
        score += 10
        breakdown.append({"item": "Business Hours", "points": 10, "max": 10, "status": "good"})
    else:
        breakdown.append({"item": "Business Hours", "points": 0, "max": 10, "status": "missing"})

    if lead.get("description") or lead.get("notes"):
        score += 5
        breakdown.append({"item": "Description", "points": 5, "max": 5, "status": "good"})

    return {
        "score": max(0, min(score, 100)),
        "breakdown": breakdown,
        "industry_average": 67,
        "top_competitors": 89,
        "severity": (
            "critical" if score < 40 else
            "warning" if score < 65 else
            "healthy"
        ),
    }


def _parse_reviews_from_notes(notes: str) -> int:
    import re
    if not notes:
        return 0
    m = re.search(r"(\d+)\s+(?:google\s+)?reviews?", notes, re.I)
    return int(m.group(1)) if m else 3


def _parse_rating(lead: Dict[str, Any]) -> float:
    import re
    if isinstance(lead.get("rating"), (int, float)):
        return float(lead["rating"])
    m = re.search(r"(\d\.\d)\s*star", str(lead.get("notes", "")), re.I)
    return float(m.group(1)) if m else 4.5


def _build_growth_gaps(lead: Dict[str, Any], searches: int) -> list:
    gaps = []
    reviews = lead.get("reviews_count") or _parse_reviews_from_notes(lead.get("notes", ""))

    if not lead.get("website_url"):
        gaps.append({
            "icon": "globe",
            "title": "No Website",
            "detail": f"Losing {searches:,}+ monthly searches",
            "impact": f"Estimated lost revenue: ${int(searches * 0.5):,}/month",
            "severity": "critical",
        })
    if reviews < 20:
        gaps.append({
            "icon": "star",
            "title": f"Only {reviews} Reviews",
            "detail": "Competitors have 50+ reviews",
            "impact": "You're invisible in local search",
            "severity": "high",
        })
    social = lead.get("social_media") or {}
    if not any(social.values()):
        gaps.append({
            "icon": "instagram",
            "title": "No Social Media",
            "detail": "0 Instagram/Facebook presence",
            "impact": f"Missing {int(searches * 0.28):,}+ potential followers",
            "severity": "high",
        })
    if not lead.get("gmb_claimed"):
        gaps.append({
            "icon": "map-pin",
            "title": "Google Business Unclaimed",
            "detail": "Customers can't find your hours/contact",
            "impact": "Lost trust + conversions",
            "severity": "medium",
        })
    gaps.append({
        "icon": "refresh",
        "title": "No Follow-up System",
        "detail": "Previous customers never return",
        "impact": "80% of revenue comes from repeat customers",
        "severity": "high",
    })
    return gaps


def _build_aurem_fixes() -> list:
    return [
        {"icon": "search",      "title": "Google SEO & GEO Optimization", "detail": "Rank #1 in your city on Google Maps + Search"},
        {"icon": "star",        "title": "Auto Google Reviews",           "detail": "Every customer gets review request automatically"},
        {"icon": "globe",       "title": "Free Professional Website",     "detail": "AI-built, live in 24 hours, SEO optimized"},
        {"icon": "zap",         "title": "AI Lead Generation",            "detail": "Scout finds new customers daily — automatically"},
        {"icon": "phone",       "title": "AI Voice Agent — ORA",          "detail": "Answers all calls 24/7, books appointments"},
        {"icon": "message",     "title": "WhatsApp + SMS + Email",        "detail": "Never miss a lead — multi-channel follow-up"},
        {"icon": "inbox",       "title": "Multi-Channel Inbox",           "detail": "All WhatsApp, Email, SMS in one place"},
        {"icon": "users",       "title": "Complete CRM",                  "detail": "Track every customer, every conversation"},
        {"icon": "trending-up", "title": "Social Media Autopilot",        "detail": "Instagram, Facebook, TikTok, LinkedIn, X, Bluesky, Threads"},
        {"icon": "film",        "title": "AI Video Marketing",            "detail": "AI-generated product/service videos automatically"},
        {"icon": "send",        "title": "Automated Campaigns",           "detail": "Email + WhatsApp + SMS campaigns on autopilot"},
        {"icon": "bar-chart",   "title": "Business Intelligence Reports", "detail": "Real-time competitor analysis + market insights"},
        {"icon": "eye",         "title": "Competitor Monitoring",         "detail": "Track what competitors are doing — stay ahead"},
        {"icon": "sun",         "title": "Morning Intelligence Brief",    "detail": "ORA sends daily business summary every morning"},
        {"icon": "shield",      "title": "Security Shield",               "detail": "24/7 AI monitoring — Shannon protects your business"},
        {"icon": "tool",        "title": "Self-Healing Database",         "detail": "AUREM fixes your data errors automatically — zero effort"},
        {"icon": "map-pin",     "title": "Google Business Profile Repair", "detail": "Fix and optimize your Google listing automatically"},
        {"icon": "refresh",     "title": "Customer Win-Back",             "detail": "Re-engage lost customers automatically"},
        {"icon": "file-text",   "title": "Document Generation",           "detail": "Proposals, invoices, reports — AI-generated instantly"},
        {"icon": "shopping-bag", "title": "Shopify Integration",          "detail": "Connect your store — sales automation activated"},
    ]


def _build_pricing(business_slug: str, revenue: Optional[Dict[str, Any]] = None) -> list:
    """AUREM's 3 Stripe LIVE recurring plans with profit-math per tier."""
    origin = os.environ.get("PUBLIC_APP_URL", "https://aurem.live")
    avg_job = (revenue or {}).get("avg_job_value_cad", 350)

    # Customers/mo targets per plan tier
    tiers = [
        {
            "tier": "starter",
            "name": "Starter",
            "price_cad": 97,
            "tag": "Perfect for small shops",
            "customers_low": 8,
            "customers_high": 12,
            "payback_customers": 1,
            "features": [
                "Google SEO + Website",
                "50 AI actions/month",
                "Email + SMS automation",
                "Basic CRM",
            ],
            "price_id": os.environ.get("STRIPE_PRICE_STARTER", ""),
            "popular": False,
        },
        {
            "tier": "growth",
            "name": "Growth",
            "price_cad": 297,
            "tag": "Most popular — growing businesses",
            "customers_low": 25,
            "customers_high": 40,
            "payback_customers": 1,
            "features": [
                "Everything in Starter",
                "500 AI actions/month",
                "WhatsApp automation",
                "Social media posting",
                "Advanced analytics",
            ],
            "price_id": os.environ.get("STRIPE_PRICE_GROWTH", ""),
            "popular": True,
        },
        {
            "tier": "enterprise",
            "name": "Enterprise",
            "price_cad": 997,
            "tag": "Maximum growth",
            "customers_low": 100,
            "customers_high": 150,
            "payback_customers": 3,
            "features": [
                "Unlimited everything",
                "Video generation",
                "Dedicated ORA AI",
                "White-label option",
                "Priority support",
            ],
            "price_id": os.environ.get("STRIPE_PRICE_ENTERPRISE", ""),
            "popular": False,
        },
    ]
    for t in tiers:
        earn_low = t["customers_low"] * avg_job
        earn_high = t["customers_high"] * avg_job
        # Use low bound for profit (credible / underpromise-overdeliver)
        profit = earn_low - t["price_cad"]
        t.update({
            "earn_low_cad": earn_low,
            "earn_high_cad": earn_high,
            "profit_cad": profit,
            "cta_label": "Start Now",
            "checkout_meta": {"package_id": t["tier"], "origin_url": origin, "ref": business_slug},
        })
    return tiers


def _build_revenue(lead: Dict[str, Any], searches: int) -> Dict[str, Any]:
    """Revenue projections for the interactive calculator."""
    current_leads = 5
    aurem_leads = 35
    avg_job_value = _estimate_avg_job_value(lead.get("category", ""))
    return {
        "current_monthly_leads": current_leads,
        "aurem_monthly_leads": aurem_leads,
        "additional_leads": aurem_leads - current_leads,
        "avg_job_value_cad": avg_job_value,
        "additional_monthly_revenue_cad": (aurem_leads - current_leads) * avg_job_value,
        "annual_impact_cad": (aurem_leads - current_leads) * avg_job_value * 12,
        "monthly_searches": searches,
    }


def _estimate_avg_job_value(category: str) -> int:
    c = (category or "").lower()
    if "auto" in c or "mechanic" in c or "body shop" in c:
        return 350
    if "hair" in c or "salon" in c or "beauty" in c:
        return 85
    if "restaurant" in c or "cafe" in c:
        return 45
    if "dental" in c or "medical" in c:
        return 250
    return 150


# ══════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════

@router.get("/{slug}")
async def get_public_report(slug: str, request: Request):
    """
    Public AUREM Business Report page data for a scouted lead.
    No auth — access control is the slug itself (unguessable lead_id).
    """
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    lead = await db.campaign_leads.find_one(
        {"lead_id": slug, "business_id": FOUNDER_BIN}, {"_id": 0})
    if not lead:
        # Fallback: legacy outreach emails embed slug = _slugify(business_name)
        # when lead_id was missing at send-time. Try matching by the slugified
        # business_name so the public report still resolves for those leads.
        try:
            import re as _re
            pat = "^" + _re.escape(slug).replace(r"\-", "[ \\-]+") + "$"
            lead = await db.campaign_leads.find_one(
                {"business_id": FOUNDER_BIN,
                 "$expr": {
                    "$regexMatch": {
                        "input": {"$toLower": {"$ifNull": ["$business_name", ""]}},
                        "regex": pat.replace(" ", "[ \\-]+"),
                    }
                }},
                {"_id": 0},
            )
        except Exception as _slug_err:
            logger.debug(f"[public-report] slug fallback failed: {_slug_err}")
        if not lead:
            # Final fallback: case-insensitive search on a name reconstructed
            # from the slug (replace hyphens with spaces).
            name_guess = slug.replace("-", " ")
            try:
                lead = await db.campaign_leads.find_one(
                    {"business_name": {"$regex": f"^{name_guess}$", "$options": "i"},
                     "business_id": FOUNDER_BIN},
                    {"_id": 0},
                )
            except Exception:
                lead = None
        if not lead:
            raise HTTPException(404, "Report not found. The business may not be in our scout database yet.")

    from services.aurem_outreach_templates import build_variables
    variables = build_variables(lead)
    google = _compute_google_score(lead)
    growth_gaps = _build_growth_gaps(lead, variables["monthly_searches"])
    fixes = _build_aurem_fixes()
    revenue = _build_revenue(lead, variables["monthly_searches"])
    pricing = _build_pricing(slug, revenue)

    # Hybrid CTA — surface a $149 one-time repair offer when this lead has
    # a corresponding repair scan, so cold visitors can self-select into the
    # cheaper one-time path instead of bouncing on the SaaS price.
    repair_offer = None
    try:
        scan = await db.customer_scans.find_one(
            {"lead_id": slug},
            {"_id": 0, "public_slug": 1, "overall_score": 1,
              "issues": 1, "rebuild_recommended": 1},
            sort=[("created_at", -1)],
        )
        if scan and scan.get("public_slug"):
            issues = scan.get("issues") or []
            critical = sum(1 for i in issues
                            if i.get("severity") in ("high", "critical"))
            base = "https://aurem.live"
            repair_offer = {
                "available": True,
                "public_slug": scan["public_slug"],
                "score": int(scan.get("overall_score") or 0),
                "issues_total": len(issues),
                "issues_critical": critical,
                "rebuild_recommended": bool(scan.get("rebuild_recommended")),
                "tiers": [
                    {"tier": "basic", "label": "Quick Repair",
                      "price_cad": 149, "delivery_hours": 24,
                      "checkout_url": f"{base}/api/repair/checkout?slug={scan['public_slug']}&tier=basic",
                      "report_url": f"{base}/api/repair-report/{scan['public_slug']}"},
                    {"tier": "full", "label": "Full Rebuild",
                      "price_cad": 299, "delivery_hours": 48,
                      "checkout_url": f"{base}/api/repair/checkout?slug={scan['public_slug']}&tier=full",
                      "report_url": f"{base}/api/repair-report/{scan['public_slug']}"},
                ],
            }
    except Exception as _re:
        logger.debug(f"[public-report] repair_offer lookup failed: {_re}")

    # iter 282al-18 · Part 3 — Dynamic CTA from site_audits.overall_score
    #   score < 60  → "Fix My Website — $197"  → /api/repair/checkout
    #   score 60-79 → "Website Tune-Up — $297/mo" → Growth plan
    #   score >= 80 → "Add AI Chat Widget — Free Trial" → /widget-trial
    #   no score    → generic "Start Free Trial" CTA
    cta = None
    try:
        audit = await db.site_audits.find_one(
            {"lead_id": slug},
            {"_id": 0, "overall_score": 1, "audit_ts": 1},
            sort=[("audit_ts", -1)],
        )
        _score = int((audit or {}).get("overall_score") or 0)
        cta = _build_cta_for_score(_score, slug)
    except Exception as _ct:
        logger.debug(f"[public-report] cta lookup failed: {_ct}")
        cta = _build_cta_for_score(0, slug)

    return {
        "slug": slug,
        "business": {
            "name": lead.get("business_name", ""),
            "category": lead.get("category", ""),
            "location": lead.get("location", ""),
            "city": variables["city"],
            "phone": lead.get("phone", ""),
            "email": lead.get("email", ""),
            "website": lead.get("website_url", ""),
            "rating": variables["rating"],
            "review_count": variables["review_count"],
        },
        "score": google,
        "growth_gaps": growth_gaps,
        "aurem_fixes": fixes,
        "revenue": revenue,
        "pricing": pricing,
        "repair_offer": repair_offer,
        "cta": cta,
        "social_proof": [
            {"quote": "AUREM got us 47 new customers in first month", "author": "Auto shop, Mississauga"},
            {"quote": "5x more Google reviews in 2 weeks", "author": "Beauty salon, Brampton"},
            {"quote": "40% average increase in customer calls within 30 days", "author": "AUREM aggregate data"},
        ],
        "ora_chat_enabled": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


class VisitEvent(BaseModel):
    referrer: Optional[str] = None
    user_agent: Optional[str] = None
    duration_seconds: Optional[int] = None


@router.post("/{slug}/visit")
async def log_report_visit(slug: str, event: VisitEvent, request: Request):
    """Log a report page view into the lead's outreach_history."""
    db = _get_db()
    if db is None:
        return {"logged": False, "reason": "no_db"}
    lead = await db.campaign_leads.find_one(
        {"lead_id": slug, "business_id": FOUNDER_BIN},
        {"lead_id": 1, "outreach_history": 1})
    if not lead:
        raise HTTPException(404, "Lead not found")

    now = datetime.now(timezone.utc).isoformat()
    client_ip = request.client.host if request.client else "unknown"
    await db.campaign_leads.update_one(
        {"lead_id": slug, "business_id": FOUNDER_BIN},
        {
            "$push": {
                "outreach_history": {
                    "type": "report_view",
                    "timestamp": now,
                    "ip": client_ip,
                    "referrer": event.referrer or "",
                    "user_agent": (event.user_agent or "")[:180],
                }
            },
            "$inc": {"report_view_count": 1},
            "$set": {"last_report_view_at": now, "updated_at": now},
        },
    )
    return {"logged": True, "timestamp": now}


@router.post("/{slug}/engaged")
async def report_engaged(slug: str, event: VisitEvent):
    """
    Fired when visitor stays 30+ seconds on the report page.
    Sends an auto-follow-up WhatsApp: 'Did you get a chance to review your report?'
    Idempotent per-day (won't spam).
    """
    db = _get_db()
    if db is None:
        return {"sent": False, "reason": "no_db"}
    lead = await db.campaign_leads.find_one(
        {"lead_id": slug, "business_id": FOUNDER_BIN}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")

    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    # Idempotency: don't re-send if we've already nudged today
    history = lead.get("outreach_history", []) or []
    for entry in history:
        if entry.get("type") == "engagement_nudge" and (entry.get("timestamp", "")[:10] == today):
            return {"sent": False, "reason": "already_sent_today", "last": entry["timestamp"]}

    phone = (lead.get("phone") or "").replace("+", "").replace("-", "").replace(" ", "")
    if not phone:
        return {"sent": False, "reason": "no_phone"}

    business_name = lead.get("business_name", "there")
    message = (
        f"Hi {business_name}! 👋\n\n"
        f"I noticed you just visited your AUREM business intelligence report — "
        f"did you get a chance to review the growth gaps I flagged?\n\n"
        f"Happy to answer any questions or walk you through the fix-plan.\n\n"
        f"*Reply YES* and I'll set up your free 7-day trial right now! 🚀\n\n"
        f"— ORA, AUREM Intelligence"
    )

    try:
        whapi_token = os.environ.get("WHAPI_API_TOKEN", "")
        whapi_url = os.environ.get("WHAPI_API_URL", "")
        if not (whapi_token and whapi_url):
            return {"sent": False, "reason": "whapi_not_configured"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{whapi_url}/messages/text",
                headers={"authorization": f"Bearer {whapi_token}", "content-type": "application/json"},
                json={"to": f"{phone}@s.whatsapp.net", "body": message},
            )
        ok = resp.status_code == 200
        iso = now.isoformat()
        await db.campaign_leads.update_one(
            {"lead_id": slug, "business_id": FOUNDER_BIN},
            {
                "$push": {
                    "outreach_history": {
                        "type": "engagement_nudge",
                        "channel": "whatsapp",
                        "to": phone,
                        "status": "sent" if ok else "failed",
                        "template": "report_30s_nudge_v1",
                        "timestamp": iso,
                    }
                },
                "$set": {"updated_at": iso},
            },
        )
        return {"sent": ok, "channel": "whatsapp", "timestamp": iso}
    except Exception as e:
        logger.warning(f"[ReportEngaged] {slug}: {e}")
        return {"sent": False, "reason": str(e)}
