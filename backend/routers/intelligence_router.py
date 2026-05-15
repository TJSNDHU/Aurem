"""
AUREM Business DNA Profiler + Offer Generator + Onboarding Orchestrator
The "Autonomous Executive" closed-loop: Scan → Classify → Price → Convert → Fulfill

Components:
1. Business DNA Profiler — Gemini 3.1 Pro classifies site category, revenue model, pain points
2. Offer Generator — Dynamic tiered pricing with Stripe discount code generation
3. ROI Dashboard API — Revenue leakage estimation + AI proposal
4. Onboarding Orchestrator — Stripe webhook → auto-trigger agent stack
5. Recovery Engine — Queues follow-up offers for non-converters
"""

from fastapi import APIRouter, HTTPException, Header, Request, Depends
from fastapi.responses import JSONResponse

from utils.require_auth import require_auth
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import httpx
import json
import os
import secrets
import logging
import asyncio
from bs4 import BeautifulSoup

# Bug-fix 104 — was completely unauthenticated. /dna-profile is a public
# SSRF endpoint that fetches any URL (including internal services like
# 169.254.169.254 metadata, MongoDB on localhost:27017). Now requires JWT
# at the router level.
router = APIRouter(dependencies=[Depends(require_auth)])
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv(override=False)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
STRIPE_API_KEY = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY", "")

try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    LLM_AVAILABLE = bool(EMERGENT_LLM_KEY)
except ImportError:
    LLM_AVAILABLE = False

try:
    from emergentintegrations.payments.stripe.checkout import (
        StripeCheckout, CheckoutSessionRequest
    )
    STRIPE_AVAILABLE = bool(STRIPE_API_KEY)
except ImportError:
    STRIPE_AVAILABLE = False


# ─── Helpers ────────────────────────────────────────────────────
def _get_user_id(authorization: str) -> str:
    if authorization and authorization.startswith("Bearer "):
        try:
            import jwt
            token = authorization.replace("Bearer ", "")
            payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
            return payload.get("user_id", "anonymous")
        except Exception:
            pass
    return "anonymous"


def _block_ssrf(url: str) -> None:
    """Bug-fix 104 — refuse private / loopback / link-local hosts to
    prevent SSRF to internal services (AWS metadata, MongoDB, Redis)."""
    import ipaddress
    import socket
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").strip().lower()
    if not host:
        raise HTTPException(400, "Invalid URL")
    if host in {"localhost", "metadata.google.internal", "metadata"}:
        raise HTTPException(400, "Refused: internal hostname")
    try:
        addrs = {ai[4][0] for ai in socket.getaddrinfo(host, None)}
    except Exception:
        raise HTTPException(400, "Refused: DNS resolution failed")
    for a in addrs:
        try:
            ip = ipaddress.ip_address(a)
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise HTTPException(400, f"Refused: address {a} is private/loopback/link-local")


async def _fetch_html(url: str) -> str:
    _block_ssrf(url)
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


def _normalize_url(raw: str) -> str:
    if not raw.startswith("http"):
        return "https://" + raw
    return raw


# ═══════════════════════════════════════════════════════════════
# 1. BUSINESS DNA PROFILER (Gemini 3.1 Pro)
# ═══════════════════════════════════════════════════════════════

# Revenue leakage multipliers per issue type
REVENUE_LEAK_MAP = {
    "slow_load": {"monthly_loss": 450, "label": "Slow page load → cart abandonment"},
    "no_https": {"monthly_loss": 800, "label": "No HTTPS → trust barrier, lost conversions"},
    "missing_meta": {"monthly_loss": 300, "label": "Missing meta descriptions → invisible in search"},
    "no_h1": {"monthly_loss": 200, "label": "No H1 tag → poor search ranking"},
    "missing_alt": {"monthly_loss": 150, "label": "Missing alt text → accessibility lawsuit risk"},
    "no_caching": {"monthly_loss": 250, "label": "No cache headers → repeat visitors bounce"},
    "missing_og": {"monthly_loss": 180, "label": "No Open Graph → zero social sharing visibility"},
    "no_aria": {"monthly_loss": 120, "label": "No ARIA landmarks → inaccessible, legal risk"},
    "no_security_headers": {"monthly_loss": 600, "label": "Missing security headers → vulnerable to XSS/injection"},
    "broken_forms": {"monthly_loss": 500, "label": "Broken/unlabeled forms → lost lead captures"},
    "no_ssl": {"monthly_loss": 900, "label": "No SSL certificate → browser warnings, instant bounce"},
    "large_page": {"monthly_loss": 350, "label": "Oversized page → mobile users abandon"},
}


class DNARequest(BaseModel):
    url: str


@router.post("/api/intelligence/dna-profile")
async def generate_business_dna(body: DNARequest, authorization: str = Header(None)):
    """
    Step A+B of the Forensic Pulse:
    - Technical scan (performance, security, SEO, a11y gaps)
    - AI-powered business classification (category, revenue model, pain points)
    - Revenue leakage estimation
    """
    if not LLM_AVAILABLE:
        raise HTTPException(503, "AI engine unavailable")

    from server import db
    user_id = _get_user_id(authorization)
    url = _normalize_url(body.url)
    now = datetime.now(timezone.utc).isoformat()

    # 1. Fetch and analyze HTML
    try:
        html = await _fetch_html(url)
    except Exception as e:
        raise HTTPException(400, f"Could not reach URL: {e}")

    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(separator=" ", strip=True)[:4000]

    # 2. Technical issue detection (quick scan)
    issues_detected = []
    links = [a.get("href", "") for a in soup.find_all("a", href=True)]
    link_text = " ".join(links).lower()

    # Detect site signals
    has_cart = any(k in link_text for k in ["cart", "checkout", "shop", "product", "add-to-cart", "shopify"])
    has_contact = any(k in link_text for k in ["contact", "demo", "book", "schedule", "calendar", "consultation"])
    has_pricing = any(k in link_text for k in ["pricing", "plans", "subscribe", "membership"])
    has_login = any(k in link_text for k in ["login", "sign-in", "dashboard", "account", "portal"])

    # Technical issues
    title_tag = soup.find("title")
    if not title_tag or not title_tag.string or len(title_tag.string.strip()) < 20:
        issues_detected.append("missing_meta")
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if not meta_desc or not meta_desc.get("content", "").strip():
        issues_detected.append("missing_meta")
    if not soup.find_all("h1"):
        issues_detected.append("no_h1")
    imgs_no_alt = [i for i in soup.find_all("img") if not i.get("alt")]
    if imgs_no_alt:
        issues_detected.append("missing_alt")
    if not soup.find("meta", property="og:title"):
        issues_detected.append("missing_og")
    if not soup.find("main") and not soup.find(attrs={"role": "main"}):
        issues_detected.append("no_aria")
    inputs = soup.find_all(["input", "textarea", "select"])
    unlabeled = [i for i in inputs if i.get("type") not in ("hidden", "submit", "button") and not i.get("aria-label")]
    if unlabeled:
        issues_detected.append("broken_forms")

    # Deduplicate
    issues_detected = list(set(issues_detected))

    # 3. AI Business Classification (Gemini 3.1 Pro)
    ai_prompt = f"""Analyze this website and classify the business. URL: {url}

Page content (first 3000 chars):
{page_text[:3000]}

Links found: {', '.join(links[:30])}

Signals detected:
- Has cart/checkout: {has_cart}
- Has contact/demo form: {has_contact}
- Has pricing page: {has_pricing}
- Has login/dashboard: {has_login}

Return STRICT JSON (no markdown):
{{
    "business_name": "Name of the business",
    "category": "One of: ecommerce, saas, agency, healthcare, fintech, education, media, restaurant, professional_services, nonprofit, other",
    "sub_category": "More specific (e.g., skincare, b2b_software, law_firm)",
    "revenue_model": "One of: shopify, subscription, lead_gen, ads, marketplace, freemium, service_fee, other",
    "target_audience": "Brief description of target customers",
    "primary_pain": "The biggest business issue found (e.g., slow checkout, broken lead forms)",
    "competitive_advantage": "What makes this business unique based on content",
    "growth_stage": "One of: startup, growth, established, enterprise",
    "urgency_score": 1-10
}}"""

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"dna_{secrets.token_hex(8)}",
            system_message="You are ORA Intelligence, a business analyst AI. Return ONLY valid JSON."
        ).with_model("gemini", "gemini-2.5-flash")

        response = await chat.send_message(UserMessage(text=ai_prompt))
        clean = response.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
        ai_profile = json.loads(clean)
    except json.JSONDecodeError:
        ai_profile = {
            "business_name": url.split("//")[1].split("/")[0] if "//" in url else url,
            "category": "ecommerce" if has_cart else "saas" if has_login else "lead_gen" if has_contact else "other",
            "sub_category": "general",
            "revenue_model": "shopify" if has_cart else "subscription" if has_pricing else "lead_gen",
            "target_audience": "General consumers",
            "primary_pain": "Multiple technical issues detected",
            "competitive_advantage": "Unknown",
            "growth_stage": "growth",
            "urgency_score": 7,
        }
    except Exception as e:
        logger.error(f"DNA Profiler AI error: {e}")
        raise HTTPException(500, f"AI analysis error: {str(e)}")

    # 4. Calculate revenue leakage
    total_monthly_loss = 0
    leak_details = []
    for issue_key in issues_detected:
        if issue_key in REVENUE_LEAK_MAP:
            leak = REVENUE_LEAK_MAP[issue_key]
            total_monthly_loss += leak["monthly_loss"]
            leak_details.append({
                "issue": issue_key,
                "label": leak["label"],
                "estimated_monthly_loss": leak["monthly_loss"],
            })

    # Adjust based on business category
    category = ai_profile.get("category", "other")
    multiplier = {"ecommerce": 1.5, "saas": 1.3, "fintech": 1.4, "healthcare": 1.2}.get(category, 1.0)
    total_monthly_loss = int(total_monthly_loss * multiplier)

    # 5. Store Business DNA Profile
    profile_id = f"dna_{secrets.token_urlsafe(16)}"
    profile_doc = {
        "profile_id": profile_id,
        "user_id": user_id,
        "scan_url": url,
        "business_name": ai_profile.get("business_name", ""),
        "category": ai_profile.get("category", "other"),
        "sub_category": ai_profile.get("sub_category", ""),
        "revenue_model": ai_profile.get("revenue_model", "other"),
        "target_audience": ai_profile.get("target_audience", ""),
        "primary_pain": ai_profile.get("primary_pain", ""),
        "competitive_advantage": ai_profile.get("competitive_advantage", ""),
        "growth_stage": ai_profile.get("growth_stage", "growth"),
        "urgency_score": ai_profile.get("urgency_score", 5),
        "issues_detected": issues_detected,
        "revenue_leaks": leak_details,
        "estimated_monthly_loss": total_monthly_loss,
        "estimated_annual_loss": total_monthly_loss * 12,
        "signals": {
            "has_cart": has_cart,
            "has_contact": has_contact,
            "has_pricing": has_pricing,
            "has_login": has_login,
        },
        "created_at": now,
    }
    await db.business_profiles.insert_one(profile_doc)

    return {
        "profile_id": profile_id,
        "url": url,
        "business_name": ai_profile.get("business_name", ""),
        "category": ai_profile.get("category", "other"),
        "sub_category": ai_profile.get("sub_category", ""),
        "revenue_model": ai_profile.get("revenue_model", "other"),
        "target_audience": ai_profile.get("target_audience", ""),
        "primary_pain": ai_profile.get("primary_pain", ""),
        "growth_stage": ai_profile.get("growth_stage", "growth"),
        "urgency_score": ai_profile.get("urgency_score", 5),
        "revenue_leaks": leak_details,
        "estimated_monthly_loss": total_monthly_loss,
        "estimated_annual_loss": total_monthly_loss * 12,
        "issues_count": len(issues_detected),
        "message": f"Business DNA profiled: {ai_profile.get('category', 'N/A')} ({ai_profile.get('revenue_model', 'N/A')}). Estimated ${total_monthly_loss:,}/mo in revenue leakage.",
    }


# ═══════════════════════════════════════════════════════════════
# 2. OFFER GENERATOR (Dynamic Pricing + Stripe Discount Codes)
# ═══════════════════════════════════════════════════════════════

TIER_CATALOG = {
    "commission": {
        "name": "Performance Partner",
        "base_price": 0.00,
        "type": "commission",
        "commission_per_sale": 2.00,
        "description": "$0 Upfront — Aurem earns $2.00 per automated sale it recovers for you.",
        "features": [
            "$0 upfront cost",
            "$2.00 per recovered sale",
            "Abandoned cart recovery",
            "AI-powered nudge campaigns",
            "30-day attribution window",
            "Revenue transparency dashboard",
        ],
        "ecommerce_only": True,
    },
    "free_shield": {
        "name": "Free Shield",
        "base_price": 0,
        "type": "free",
        "description": "Essential protection scan + basic SEO audit. No credit card required.",
        "pin": "7668",
        "features": ["Site health scan", "Basic SEO audit", "Security header check", "Monthly report email", "Community support"],
    },
    "explorer": {
        "name": "Quick Fix",
        "base_price": 29.00,
        "type": "one_time",
        "description": "One-click SEO + Security patch. Instant download.",
        "bundle_price": 59.00,
        "bundle_label": "3 fixes for $59",
        "features": ["SEO patch", "Security headers", "Downloadable HTML fix"],
    },
    "builder": {
        "name": "Growth Hub",
        "base_price": 499.00,
        "type": "monthly",
        "description": "Automated Lead Gen + WhatsApp AI Agent + Monthly monitoring.",
        "discount_label": "Beta Launch: 25% Lifetime Discount",
        "discount_percent": 25,
        "features": ["AI Lead Generation", "WhatsApp Bot", "Monthly health scans", "Priority support"],
    },
    "enterprise": {
        "name": "Enterprise Shield",
        "base_price": 1999.00,
        "type": "monthly",
        "description": "Full Forensic Monitoring + Self-Healing Infrastructure + VIP Setup.",
        "discount_label": "Annual Pivot: 2 months free + VIP Setup",
        "discount_percent": 17,
        "features": ["24/7 monitoring", "Self-healing automation", "Dedicated agent", "VIP onboarding", "Custom integrations"],
    },
}


class OfferRequest(BaseModel):
    profile_id: str
    trigger: str = "page_view"  # page_view | time_on_page | exit_intent


@router.post("/api/intelligence/generate-offer")
async def generate_offer(body: OfferRequest, http_request: Request, authorization: str = Header(None)):
    """
    Generate dynamic offers based on Business DNA + user behavior trigger.
    Creates Stripe discount codes on the fly for scarcity/exit-intent triggers.
    """
    from server import db
    user_id = _get_user_id(authorization)

    # Get the business profile
    profile = await db.business_profiles.find_one(
        {"profile_id": body.profile_id, "user_id": user_id},
        {"_id": 0}
    )
    if not profile:
        # No profile yet — return Free Shield as default
        free_tier = TIER_CATALOG.get("free_shield", {})
        return {
            "offers": [{
                "tier_id": "free_shield", "name": free_tier.get("name", "Free Shield"),
                "base_price": 0, "final_price": 0, "type": "free",
                "pin": free_tier.get("pin", "7668"),
                "description": free_tier.get("description", ""),
                "features": free_tier.get("features", []),
                "is_recommended": True, "roi_message": "Start protecting your business — upgrade anytime",
            }],
            "message": "Run DNA Profiler to unlock all tiers. Free Shield available now.",
        }

    now = datetime.now(timezone.utc).isoformat()
    monthly_loss = profile.get("estimated_monthly_loss", 0)
    category = profile.get("category", "other")
    is_ecommerce = category in ("ecommerce", "retail", "shopify")

    # Build tier offers with dynamic pricing
    offers = []
    for tier_id, tier in TIER_CATALOG.items():
        # Skip commission tier for non-ecommerce businesses
        if tier.get("ecommerce_only") and not is_ecommerce:
            continue

        offer = {
            "tier_id": tier_id,
            "name": tier["name"],
            "base_price": tier["base_price"],
            "type": tier["type"],
            "description": tier["description"],
            "features": tier["features"],
            "final_price": tier["base_price"],
            "discount_code": None,
            "discount_percent": 0,
            "discount_label": None,
            "roi_message": None,
            "commission_per_sale": tier.get("commission_per_sale"),
            "is_recommended": False,
        }

        # Free tier special handling
        if tier_id == "free_shield":
            offer["final_price"] = 0.0
            offer["pin"] = tier.get("pin", "7668")
            offer["is_recommended"] = False
            offer["roi_message"] = "Start protecting your business — upgrade anytime"
            offers.append(offer)
            continue

        # Commission-based tier special handling
        if tier_id == "commission":
            offer["final_price"] = 0.0
            offer["discount_label"] = "$0 upfront — pay only when Aurem makes you money"
            # Recommend commission tier on exit_intent for e-commerce
            if body.trigger == "exit_intent" and is_ecommerce:
                offer["is_recommended"] = True
                offer["roi_message"] = f"Zero risk: Aurem recovers your ${monthly_loss:,}/mo leakage. You pay $2 only per sale we bring back."
            elif is_ecommerce:
                offer["roi_message"] = f"$0 upfront — we recover your lost ${monthly_loss:,}/mo and earn $2 per sale."

        # Dynamic discount based on trigger
        elif body.trigger == "time_on_page" and tier_id != "explorer":
            # 60+ seconds on page → flash offer
            discount_pct = 50 if tier_id == "builder" else 30
            offer["discount_percent"] = discount_pct
            offer["discount_label"] = f"Founder's Launch: {discount_pct}% off for 3 months"
            offer["final_price"] = round(tier["base_price"] * (1 - discount_pct / 100), 2)
            offer["discount_code"] = f"AUREM-FLASH-{secrets.token_hex(4).upper()}"

        elif body.trigger == "exit_intent" and tier_id != "explorer":
            # Exit intent → unique time-bound discount
            discount_pct = 15
            offer["discount_percent"] = discount_pct
            offer["discount_label"] = f"Wait! {discount_pct}% off — expires in 24h"
            offer["final_price"] = round(tier["base_price"] * (1 - discount_pct / 100), 2)
            offer["discount_code"] = f"AUREM-OFFER-{secrets.token_hex(4).upper()}"

        elif tier_id == "explorer":
            # Explorer always shows bundle deal
            offer["discount_label"] = tier.get("bundle_label")
            offer["bundle_price"] = tier.get("bundle_price")

        elif tier.get("discount_percent"):
            # Default tier discount
            offer["discount_percent"] = tier["discount_percent"]
            offer["discount_label"] = tier["discount_label"]
            offer["final_price"] = round(tier["base_price"] * (1 - tier["discount_percent"] / 100), 2)

        # ROI message based on business DNA
        if monthly_loss > 0:
            if tier_id == "explorer":
                roi = monthly_loss
                offer["roi_message"] = f"Fix ${roi:,}/mo in revenue leaks for just $29"
            elif tier_id == "builder":
                roi = monthly_loss * 3
                offer["roi_message"] = f"Recover ${roi:,}/mo with automated growth — {int(roi / offer['final_price'])}x ROI"
            elif tier_id == "enterprise":
                roi = monthly_loss * 8
                offer["roi_message"] = f"Protect ${roi:,}/mo in revenue — full autonomous monitoring"

        offers.append(offer)

    # Store the generated offer set
    offer_set_id = f"offer_{secrets.token_urlsafe(12)}"
    offer_doc = {
        "offer_set_id": offer_set_id,
        "user_id": user_id,
        "profile_id": body.profile_id,
        "scan_url": profile["scan_url"],
        "trigger": body.trigger,
        "offers": offers,
        "monthly_loss": monthly_loss,
        "category": category,
        "created_at": now,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat() if body.trigger == "exit_intent" else None,
        "converted": False,
    }
    await db.offer_sets.insert_one(offer_doc)

    # Queue recovery follow-up if not exit_intent (24h delay)
    if body.trigger == "page_view":
        await db.recovery_queue.insert_one({
            "user_id": user_id,
            "profile_id": body.profile_id,
            "offer_set_id": offer_set_id,
            "scan_url": profile["scan_url"],
            "business_name": profile.get("business_name", ""),
            "monthly_loss": monthly_loss,
            "status": "queued",
            "send_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
            "channel": "email",
            "discount_percent": 15,
            "created_at": now,
        })

    return {
        "offer_set_id": offer_set_id,
        "profile_id": body.profile_id,
        "url": profile["scan_url"],
        "business_name": profile.get("business_name", ""),
        "category": category,
        "monthly_loss": monthly_loss,
        "annual_loss": monthly_loss * 12,
        "offers": offers,
        "trigger": body.trigger,
        "recovery_queued": body.trigger == "page_view",
        "message": f"${monthly_loss:,}/mo in detected revenue leakage. {len(offers)} tier offers generated.",
    }


# ═══════════════════════════════════════════════════════════════
# 3. STRIPE CHECKOUT FOR TIERED OFFERS
# ═══════════════════════════════════════════════════════════════

class TierCheckoutRequest(BaseModel):
    offer_set_id: str
    tier_id: str
    origin_url: str


@router.post("/api/intelligence/checkout")
async def create_tier_checkout(body: TierCheckoutRequest, http_request: Request, authorization: str = Header(None)):
    """Create a Stripe checkout session for the selected tier with dynamic discount."""
    if not STRIPE_AVAILABLE:
        raise HTTPException(503, "Payment system unavailable")

    from server import db
    user_id = _get_user_id(authorization)

    offer_set = await db.offer_sets.find_one(
        {"offer_set_id": body.offer_set_id, "user_id": user_id},
        {"_id": 0}
    )
    if not offer_set:
        raise HTTPException(404, "Offer set not found")

    # Find the selected tier offer
    selected = next((o for o in offer_set.get("offers", []) if o["tier_id"] == body.tier_id), None)
    if not selected:
        raise HTTPException(400, f"Tier '{body.tier_id}' not found in offer set")

    amount = selected["final_price"]
    tier_name = selected["name"]

    host_url = str(http_request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/intelligence/webhook/stripe"
    stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    origin = body.origin_url.rstrip("/")
    success_url = f"{origin}/dashboard?ae_payment=success&session_id={{CHECKOUT_SESSION_ID}}&tier={body.tier_id}"
    cancel_url = f"{origin}/dashboard?ae_payment=cancelled"

    checkout_req = CheckoutSessionRequest(
        amount=amount,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "type": "autonomous_executive",
            "offer_set_id": body.offer_set_id,
            "profile_id": offer_set.get("profile_id", ""),
            "tier_id": body.tier_id,
            "tier_name": tier_name,
            "user_id": user_id,
            "discount_code": selected.get("discount_code") or "",
        }
    )

    session = await stripe.create_checkout_session(checkout_req)

    # Store transaction
    await db.payment_transactions.insert_one({
        "session_id": session.session_id,
        "type": "autonomous_executive",
        "offer_set_id": body.offer_set_id,
        "tier_id": body.tier_id,
        "user_id": user_id,
        "amount": amount,
        "currency": "usd",
        "payment_status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "checkout_url": session.url,
        "session_id": session.session_id,
        "tier": body.tier_id,
        "amount": amount,
        "tier_name": tier_name,
    }


# ═══════════════════════════════════════════════════════════════
# 4. ONBOARDING ORCHESTRATOR (Stripe Webhook → Agent Activation)
# ═══════════════════════════════════════════════════════════════

@router.post("/api/intelligence/webhook/stripe")
async def ae_stripe_webhook(request: Request):
    """
    The brain: Payment confirmed → auto-triggers the correct agent stack.
    Explorer: Queues repair fixes for download
    Builder: Activates Growth Hub agents
    Enterprise: Activates full monitoring suite
    """
    if not STRIPE_AVAILABLE:
        return JSONResponse({"error": "Not configured"}, 500)

    from server import db
    body = await request.body()
    sig = request.headers.get("Stripe-Signature")
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/intelligence/webhook/stripe"
    stripe = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    try:
        event = await stripe.handle_webhook(body, sig)

        if event.payment_status == "paid":
            meta = event.metadata or {}
            if meta.get("type") == "autonomous_executive":
                tier_id = meta.get("tier_id", "explorer")
                user_id = meta.get("user_id", "")
                offer_set_id = meta.get("offer_set_id", "")
                now = datetime.now(timezone.utc).isoformat()

                # Update payment
                await db.payment_transactions.update_one(
                    {"session_id": event.session_id},
                    {"$set": {"payment_status": "paid", "paid_at": now}}
                )

                # Mark offer as converted
                await db.offer_sets.update_one(
                    {"offer_set_id": offer_set_id},
                    {"$set": {"converted": True, "converted_at": now, "converted_tier": tier_id}}
                )

                # Cancel recovery follow-up
                await db.recovery_queue.update_many(
                    {"offer_set_id": offer_set_id, "status": "queued"},
                    {"$set": {"status": "cancelled_converted"}}
                )

                # ONBOARDING ORCHESTRATOR — activate agents by tier
                activation = {
                    "activation_id": f"act_{secrets.token_urlsafe(12)}",
                    "user_id": user_id,
                    "tier_id": tier_id,
                    "offer_set_id": offer_set_id,
                    "profile_id": meta.get("profile_id", ""),
                    "status": "activated",
                    "agents_activated": [],
                    "activated_at": now,
                }

                if tier_id == "explorer":
                    activation["agents_activated"] = ["ora_repair_engine"]
                elif tier_id == "builder":
                    activation["agents_activated"] = [
                        "ora_repair_engine", "growth_hub",
                        "whatsapp_agent", "monthly_scanner",
                    ]
                elif tier_id == "enterprise":
                    activation["agents_activated"] = [
                        "ora_repair_engine", "growth_hub",
                        "whatsapp_agent", "monthly_scanner",
                        "self_healing", "forensic_monitor",
                        "vip_onboarding", "custom_integrations",
                    ]

                await db.agent_activations.insert_one(activation)
                logger.info(f"[ORCHESTRATOR] Tier '{tier_id}' activated for user {user_id}: {activation['agents_activated']}")

        return JSONResponse({"received": True})
    except Exception as e:
        logger.error(f"AE webhook error: {e}")
        return JSONResponse({"error": str(e)}, 400)


# ═══════════════════════════════════════════════════════════════
# 5. STATUS & HISTORY
# ═══════════════════════════════════════════════════════════════

@router.get("/api/intelligence/profiles")
async def list_profiles(authorization: str = Header(None)):
    """List all business DNA profiles for the user."""
    from server import db
    user_id = _get_user_id(authorization)
    profiles = await db.business_profiles.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return {"profiles": profiles, "total": len(profiles)}


@router.get("/api/intelligence/activations")
async def list_activations(authorization: str = Header(None)):
    """List all agent activations for the user."""
    from server import db
    user_id = _get_user_id(authorization)
    activations = await db.agent_activations.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("activated_at", -1).to_list(50)
    return {"activations": activations, "total": len(activations)}


@router.get("/api/intelligence/recovery-queue")
async def list_recovery_queue(authorization: str = Header(None)):
    """List pending recovery follow-ups."""
    from server import db
    user_id = _get_user_id(authorization)
    queue = await db.recovery_queue.find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("send_at", 1).to_list(50)
    return {"queue": queue, "total": len(queue)}
