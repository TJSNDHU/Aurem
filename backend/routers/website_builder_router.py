"""
AUREM Website Builder Router
============================
REUSES: campaign_leads (CRM), existing blast-all endpoint, Stripe, WHAPI, Twilio.
NEW: /api/website-builder/* endpoints + auto-trigger hook for Scout.

Public routes:
  GET  /api/website-builder/{slug}               — full sample website data
  GET  /api/website-builder/status/{slug}        — quality check status
  GET  /api/website-builder/legal/{slug}/privacy — auto privacy policy
  GET  /api/website-builder/legal/{slug}/terms   — auto terms of service

Admin routes:
  POST /api/website-builder/generate             — manual generate for a lead_id
  POST /api/website-builder/send-campaign/{slug} — trigger blast-all with sample URL
  GET  /api/website-builder/list                 — list all generated sites
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from services.website_builder import generate_website

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/website-builder", tags=["AUREM Website Builder"])

_db = None

COLLECTION = "aurem_websites"
ACTIVE_WINDOW_SECS = 120  # viewer is "live" if last heartbeat < 2 minutes ago
HOT_LEAD_ADMIN_PHONE = os.environ.get("AUREM_HOT_LEAD_PHONE", "+16134000000")


def set_db(db):
    global _db
    _db = db


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


def _verify_admin(request: Request):
    """Light admin gate — reuses existing JWT if present."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Admin auth required")


# ─────────────────────────────────────────────────────────────
# GENERATE
# ─────────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    lead_id: str
    force_regenerate: Optional[bool] = False


@router.post("/generate")
async def generate(body: GenerateRequest, request: Request):
    """Generate a sample website from a scouted lead (reuses Google Places data)."""
    _verify_admin(request)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    lead = await db.campaign_leads.find_one({"lead_id": body.lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")

    # Check cache
    if not body.force_regenerate:
        existing = await db[COLLECTION].find_one({"lead_id": body.lead_id}, {"_id": 0})
        if existing:
            return {"cached": True, **existing}

    website = generate_website(lead)
    await db[COLLECTION].update_one(
        {"lead_id": body.lead_id},
        {"$set": website},
        upsert=True,
    )
    # Log in lead history
    await db.campaign_leads.update_one(
        {"lead_id": body.lead_id},
        {"$push": {"outreach_history": {
            "type": "website_generated",
            "slug": website["slug"],
            "industry": website["industry"],
            "qc_passed": website["quality_check"]["passed"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }}},
    )
    return {"cached": False, **website}


# ─────────────────────────────────────────────────────────────
# PUBLIC: NO-WEBSITE INSTANT STARTER (7-day trial, no auth needed)
# iter 322ab — customer chooses their OWN password (no temp generation),
# website-generation runs in background, welcome email fires, JWT issued
# for auto-login → redirect to /dashboard. NO password ever shown on
# screen or stored in plaintext.
# ─────────────────────────────────────────────────────────────
class NoWebsiteRequest(BaseModel):
    business_name: str
    email: str
    password: str  # iter 322ab — customer-chosen, min 8 chars
    confirm_password: Optional[str] = None  # client validates; server re-checks
    phone: Optional[str] = ""
    city: Optional[str] = ""
    category: Optional[str] = ""  # e.g. "Roofing", "HVAC", "Realtor"
    # iter 322ad — retention fixes:
    customer_services: Optional[str] = ""  # e.g. "Oil change, Brake repair, Tires"
    website_url: Optional[str] = ""        # existing site / facebook URL for brand match
    consent: bool = True


async def _generate_site_background(db, lead: dict, final_slug: str) -> None:
    """Run the (synchronous) Playwright + Claude generator in a thread
    so it doesn't block the request response. Persists final state on
    completion. Idempotent — re-runs upsert by slug.

    iter 322ad: after the sync spec is built we run the async enrichment
    layer (AI reviews + customer services + URL brand-color extraction)
    so the final stored doc reflects what the customer actually told us
    on signup instead of generic placeholder copy."""
    import asyncio as _asyncio
    try:
        website = await _asyncio.to_thread(generate_website, lead)
        # iter 322ad — async enrichment (best-effort, never raises)
        try:
            from services.website_enrich import enrich_website
            website = await enrich_website(website, lead, db=db)
        except Exception as e:
            logger.warning(f"[NO-WEBSITE bg] enrich failed for {final_slug}: {e}")
        website["lead_id"] = lead["lead_id"]
        website["slug"] = final_slug
        website["status"] = website.get("status") or "approved"
        website["generation_state"] = "ready"
        website["generated_at"] = datetime.now(timezone.utc).isoformat()
        await db[COLLECTION].update_one(
            {"slug": final_slug}, {"$set": website}, upsert=True,
        )
        logger.info(f"[NO-WEBSITE bg] site ready: {final_slug}")
    except Exception as e:
        logger.warning(f"[NO-WEBSITE bg] generation failed for {final_slug}: {e}")
        await db[COLLECTION].update_one(
            {"slug": final_slug},
            {"$set": {
                "generation_state": "failed",
                "generation_error": str(e)[:300],
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )


async def _send_starter_welcome_email(
    email: str, business_name: str, bin_code: str,
    final_slug: str, trial_ends_iso: str, trial_ends_human: str,
    public_base: str,
) -> None:
    """Fire the welcome email to the new starter customer. Best-effort
    — never raises (logged on failure so it surfaces in admin panel)."""
    try:
        from services.welcome_package import _render_email_template, _send_via_resend
    except Exception as e:
        logger.warning(f"[starter-welcome] email service import failed: {e}")
        return

    sample_url = f"{public_base}/sample/{final_slug}"
    dashboard_url = f"{public_base}/dashboard"

    email_data = {
        "first_name": business_name.split()[0] if business_name else "Founder",
        "business_name": business_name,
        "business_id": bin_code,
        "dashboard_url": dashboard_url,
        "ora_url": f"{public_base}/ora?id={bin_code}",
        "api_key": "(retrieve from your dashboard → Settings → API Keys)",
        "pixel_snippet": f'<script src="{public_base}/api/pixel/aurem-pixel.js" data-aurem-key="YOUR_KEY"></script>',
        "trial_ends_at": trial_ends_iso,
        "trial_ends_human": trial_ends_human,
        "support_email": "ora@aurem.live",
        "sample_url": sample_url,
    }
    try:
        html_body = _render_email_template(email_data)
        subject = f"Welcome to AUREM — Your Business ID: {bin_code}"
        await _send_via_resend(email, subject, html_body, email_data)
        logger.info(f"[starter-welcome] sent to {email} ({bin_code})")
    except Exception as e:
        logger.warning(f"[starter-welcome] send failed for {email}: {e}")


@router.post("/no-website")
async def no_website_instant(
    body: NoWebsiteRequest, request: Request, background_tasks: BackgroundTasks,
):
    """
    Public, no-auth endpoint for the homepage "I don't have a website" CTA.
    iter 322ab flow:
      1. Customer chooses their OWN password (min 8 chars) — NO temp password.
      2. Account created in `tenants` + `platform_users` + `users` (mirrors).
      3. Website generation queued as background task (non-blocking).
      4. Welcome email queued as background task.
      5. JWT issued for auto-login → frontend redirects to /dashboard.
      6. Response carries `token`, `bin`, `sample_url`, `dashboard_url`,
         `trial_ends_at`. Response does NOT carry any password.
    """
    import secrets as _secrets
    import bcrypt as _bcrypt
    import jwt as _jwt
    from datetime import timedelta as _timedelta

    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    business_name = (body.business_name or "").strip()
    email = (body.email or "").strip().lower()
    password = (body.password or "").strip()

    if not business_name or not email or "@" not in email:
        raise HTTPException(400, "business_name and a valid email are required")
    if not body.consent:
        raise HTTPException(400, "Consent (CASL) is required")
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if body.confirm_password is not None and body.confirm_password != password:
        raise HTTPException(400, "Passwords do not match")

    now = datetime.now(timezone.utc)
    trial_ends = now + _timedelta(days=7)

    # 1) Build the lead doc the existing generator expects.
    from services.website_builder import slugify
    lead_id = f"nws_{_secrets.token_hex(6)}"
    slug = slugify(business_name)
    lead = {
        "lead_id": lead_id,
        "business_name": business_name,
        "email": email,
        "phone": (body.phone or "").strip(),
        "location": (body.city or "").strip(),
        "category": (body.category or "").strip() or "Local Business",
        "rating": "5.0",
        "reviews_count": 0,
        "hours": {},
        "source": "no_website_signup",
        "created_at": now.isoformat(),
        # iter 322ad — retention fixes (passed through to enrichment layer):
        "customer_services": (body.customer_services or "").strip(),
        "website_url": (body.website_url or "").strip(),
    }
    await db.campaign_leads.update_one(
        {"lead_id": lead_id}, {"$setOnInsert": lead}, upsert=True
    )

    # 2) Reserve the slug + queue background generation. Pre-write a
    #    placeholder doc so /sample/{slug} can render a "Building..."
    #    state immediately instead of 404.
    final_slug = f"{slug or 'site'}-{lead_id[-6:]}"
    await db[COLLECTION].update_one(
        {"slug": final_slug},
        {"$set": {
            "slug": final_slug,
            "lead_id": lead_id,
            "business": {"name": business_name,
                         "category": lead["category"],
                         "city": lead["location"]},
            "status": "generating",
            "generation_state": "in_progress",
            "trial_started_at": now.isoformat(),
            "trial_ends_at": trial_ends.isoformat(),
            "trial_expired": False,
            "queued_at": now.isoformat(),
        }},
        upsert=True,
    )
    background_tasks.add_task(_generate_site_background, db, lead, final_slug)

    # 3) Provision (or upsert) a customer account with the customer's
    #    OWN password. Stored as bcrypt hash. NEVER returned in plaintext.
    existing_user = await db.platform_users.find_one({"email": email}, {"_id": 0})
    user_id = (existing_user or {}).get("user_id") or f"u_{_secrets.token_hex(8)}"
    bin_code = (existing_user or {}).get("bin") or f"AURE-NWS-{_secrets.token_hex(3).upper()}"
    hashed = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()

    user_doc = {
        "user_id": user_id,
        "email": email,
        "password_hash": hashed,
        "bin": bin_code,
        "business_id": bin_code,
        "full_name": business_name,
        "company_name": business_name,
        "phone": (body.phone or "").strip(),
        "city": (body.city or "").strip(),
        "industry": (body.category or "").strip(),
        "tier": "starter",
        "tier_status": "trial",
        "plan": "trial",
        "subscription_status": "trialing",
        "trial_started_at": now.isoformat(),
        "trial_ends_at": trial_ends.isoformat(),
        "sample_site_slug": final_slug,
        "source": "homepage_instant_trial",
        "created_at": (existing_user or {}).get("created_at", now.isoformat()),
        "updated_at": now.isoformat(),
    }
    await db.platform_users.update_one(
        {"email": email},
        {"$set": user_doc, "$setOnInsert": {"_first_seen": now.isoformat()}},
        upsert=True,
    )
    # Mirror to legacy `users` collection so existing /api/auth/login works.
    await db.users.update_one(
        {"email": email},
        {"$set": {
            "id": user_id,
            "email": email,
            "first_name": business_name.split()[0] if business_name else "Founder",
            "last_name": " ".join(business_name.split()[1:]) if len(business_name.split()) > 1 else "",
            "password": hashed,
            "password_hash": hashed,
            "name": business_name,
            "is_admin": False,
            "tier": "starter",
            "tier_status": "trial",
            "trial_ends_at": trial_ends.isoformat(),
        }},
        upsert=True,
    )
    # Mirror to `tenants` collection so /admin/customers panel sees them.
    await db.tenants.update_one(
        {"bin_id": bin_code},
        {"$set": {
            "bin_id": bin_code,
            "user_id": user_id,
            "email": email,
            "business_name": business_name,
            "city": (body.city or "").strip(),
            "industry": (body.category or "").strip(),
            "phone": (body.phone or "").strip(),
            "plan": "trial",
            "trial_ends_at": trial_ends.isoformat(),
            "source": "homepage_instant_trial",
            "sample_site_slug": final_slug,
            "updated_at": now.isoformat(),
        }, "$setOnInsert": {"created_at": now.isoformat()}},
        upsert=True,
    )

    # 4) Issue JWT for auto-login (matches /api/auth/login claims).
    jwt_secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
    if not jwt_secret:
        raise HTTPException(500, "JWT_SECRET not configured")
    token = _jwt.encode(
        {
            "sub": user_id, "id": user_id, "email": email,
            "is_admin": False,
            "exp": int((now + _timedelta(hours=8)).timestamp()),
            "iat": int(now.timestamp()),
        },
        jwt_secret, algorithm="HS256",
    )

    # 5) Queue welcome email — NEVER blocks the response.
    public_base = (os.environ.get("PUBLIC_APP_URL")
                   or os.environ.get("APP_BASE_URL")
                   or "https://aurem.live").rstrip("/")
    sample_url = f"{public_base}/sample/{final_slug}"
    dashboard_url = f"{public_base}/dashboard"
    background_tasks.add_task(
        _send_starter_welcome_email,
        email, business_name, bin_code, final_slug,
        trial_ends.isoformat(), trial_ends.strftime("%B %d, %Y"),
        public_base,
    )

    logger.info(f"[NO-WEBSITE] new starter site for {email} → /sample/{final_slug}")

    # 6) Response — token + redirect info, ZERO password leak.
    return {
        "ok": True,
        "token": token,
        "user": {
            "id": user_id, "email": email, "first_name": business_name,
            "last_name": "", "is_admin": False,
        },
        "bin": bin_code,
        "slug": final_slug,
        "sample_url": sample_url,
        "dashboard_url": dashboard_url,
        "trial_ends_at": trial_ends.isoformat(),
        "trial_ends_human": trial_ends.strftime("%B %d, %Y"),
        "site_status": "generating",
        "redirect": "/dashboard",
        "message": (
            "Your starter site is being built — check back in 30-60 seconds. "
            "Welcome email is on its way."
        ),
    }


# ─────────────────────────────────────────────────────────────
# LIST (must be before /{slug} to avoid route conflict)
# ─────────────────────────────────────────────────────────────
@router.get("/list")
async def list_sites(request: Request):
    _verify_admin(request)
    db = _get_db()
    if db is None:
        return {"sites": []}
    cursor = db[COLLECTION].find(
        {},
        {"_id": 0, "slug": 1, "lead_id": 1, "industry": 1, "status": 1, "generated_at": 1, "business.name": 1, "quality_check.passed": 1},
    ).sort("generated_at", -1).limit(100)
    sites = await cursor.to_list(length=100)
    return {"total": len(sites), "sites": sites}


@router.get("/live-viewers")
async def live_viewers(request: Request):
    """Admin: return prospects currently on their sample page (heartbeat < 2min ago)."""
    _verify_admin(request)
    db = _get_db()
    if db is None:
        return {"viewers": []}
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(seconds=ACTIVE_WINDOW_SECS)).isoformat()
    day_cutoff = (now - timedelta(hours=24)).isoformat()
    cursor = db.aurem_live_viewers.find(
        {"last_heartbeat_at": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("last_heartbeat_at", -1).limit(50)
    docs = await cursor.to_list(length=50)
    public_base = os.environ.get("PUBLIC_APP_URL", "https://aurem.live").rstrip("/")
    # Unique-IP counter for last 24h
    unique_ips_24h = len(await db.aurem_live_viewers.distinct("ip", {"started_at": {"$gte": day_cutoff}}))
    total_views_24h = await db.aurem_live_viewers.count_documents({"started_at": {"$gte": day_cutoff}})
    out = []
    for d in docs:
        try:
            started = datetime.fromisoformat(d["started_at"].replace("Z", "+00:00"))
            duration = int((now - started).total_seconds())
        except Exception:
            duration = 0
        out.append({
            "session_id": d.get("session_id"),
            "business_name": d.get("business_name"),
            "slug": d.get("slug"),
            "slug_url": f"{public_base}/sample/{d.get('slug','')}",
            "started_at": d.get("started_at"),
            "last_heartbeat_at": d.get("last_heartbeat_at"),
            "duration_seconds": duration,
            "ping_count": d.get("ping_count", 1),
            "engagement_nudge_fired": bool(d.get("engagement_nudge_fired")),
            "referrer": d.get("referrer", ""),
        })
    return {
        "viewers": out, "count": len(out),
        "checked_at": now.isoformat(), "active_window_secs": ACTIVE_WINDOW_SECS,
        "unique_ips_24h": unique_ips_24h, "total_views_24h": total_views_24h,
    }


# ─────────────────────────────────────────────────────────────
# PUBLIC READS
# ─────────────────────────────────────────────────────────────
@router.get("/status/{slug}")
async def get_status(slug: str):
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    site = await db[COLLECTION].find_one({"slug": slug}, {"_id": 0, "quality_check": 1, "status": 1, "generated_at": 1})
    if not site:
        raise HTTPException(404, "Website not found")
    return site


@router.get("/{slug}")
async def get_website(slug: str):
    """Public endpoint — returns full website spec for /sample/{slug} frontend."""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    site = await db[COLLECTION].find_one({"slug": slug}, {"_id": 0})
    if not site:
        # Try lookup by lead_id as fallback
        site = await db[COLLECTION].find_one({"lead_id": slug}, {"_id": 0})
    if not site:
        raise HTTPException(404, "Website not found — generate it first")
    return site


@router.get("/legal/{slug}/privacy")
async def get_privacy_page(slug: str):
    """Auto-generated privacy policy for the demo website."""
    db = _get_db()
    site = await db[COLLECTION].find_one({"slug": slug}, {"business.name": 1, "generated_at": 1}) if db is not None else None
    if not site:
        raise HTTPException(404, "Website not found")
    name = site.get("business", {}).get("name", "This Business")
    now = datetime.now().strftime("%B %d, %Y")
    return {
        "title": f"Privacy Policy — {name}",
        "effective_date": now,
        "sections": [
            {"heading": "1. Demo Preview Notice", "body": f"This website is a sample preview generated by AUREM Intelligence AI on behalf of {name} for demonstration purposes. No real customer data is collected through this preview."},
            {"heading": "2. Information We Collect", "body": "If this website becomes live, we may collect: (a) information you voluntarily provide (name, email, phone, inquiries); (b) automatically-collected data (IP address, browser type, pages visited, cookies)."},
            {"heading": "3. How We Use Information", "body": "To respond to inquiries, provide services, improve our website, and communicate with you. We will never sell your personal information to third parties."},
            {"heading": "4. Your Rights (Canada/PIPEDA)", "body": "You have the right to access, correct, or delete your personal data. To exercise these rights, email opt-out@aurem.live or contact us directly."},
            {"heading": "5. Cookies", "body": "We use essential cookies to make the site work. Optional analytics cookies require your consent."},
            {"heading": "6. Third-Party Services", "body": "We may use: Google Maps (embedded), Cloudinary (image hosting), Stripe (payments if applicable). Each has their own privacy policy."},
            {"heading": "7. Contact", "body": "Questions about this privacy policy? Email ora@aurem.live or reply to any communication from us."},
        ],
        "footer": "This policy template was generated by AUREM Intelligence AI. Review and customize before going live.",
    }


@router.get("/legal/{slug}/terms")
async def get_terms_page(slug: str):
    db = _get_db()
    site = await db[COLLECTION].find_one({"slug": slug}, {"business.name": 1}) if db is not None else None
    if not site:
        raise HTTPException(404, "Website not found")
    name = site.get("business", {}).get("name", "This Business")
    now = datetime.now().strftime("%B %d, %Y")
    return {
        "title": f"Terms of Service — {name}",
        "effective_date": now,
        "sections": [
            {"heading": "1. Acceptance", "body": "By using this website, you agree to these terms. If you do not agree, please do not use this site."},
            {"heading": "2. Demo Nature", "body": f"This is a sample website generated for {name} by AUREM Intelligence AI. Services, hours, and contact information shown may not be final."},
            {"heading": "3. No Warranty", "body": "Content is provided 'as is' without warranties. We make no representations about accuracy, completeness, or fitness for a particular purpose."},
            {"heading": "4. Limitation of Liability", "body": "AUREM Intelligence AI and the business owner are not liable for any indirect, incidental, or consequential damages arising from use of this website."},
            {"heading": "5. Intellectual Property", "body": "All content (text, logos, images) belongs to the business owner or is used with permission. AUREM retains rights to the template system."},
            {"heading": "6. Modifications", "body": "We may update these terms at any time. Continued use of the site constitutes acceptance of the updated terms."},
            {"heading": "7. Governing Law", "body": "These terms are governed by the laws of Ontario, Canada."},
        ],
        "footer": "Template generated by AUREM Intelligence AI. Review before going live.",
    }


@router.get("/legal/{slug}/unsubscribe")
async def unsubscribe_page(slug: str, email: Optional[str] = None, phone: Optional[str] = None):
    """Log unsubscribe intent + return confirmation (CASL compliance)."""
    db = _get_db()
    if db is not None and (email or phone):
        await db.unsubscribes.insert_one({
            "slug": slug,
            "email": email,
            "phone": phone,
            "source": "website_footer",
            "processed_at": datetime.now(timezone.utc).isoformat(),
        })
    return {
        "title": "Unsubscribe Request Received",
        "message": "You have been unsubscribed from AUREM communications. Your request will be fully processed within 10 days as required by CASL.",
        "sla_days": 10,
        "support": "Questions? Email opt-out@aurem.live",
    }


# ─────────────────────────────────────────────────────────────
# LIVE VIEWER TRACKING (visit → heartbeat → engagement nudge)
# ─────────────────────────────────────────────────────────────
class VisitEvent(BaseModel):
    referrer: Optional[str] = None
    user_agent: Optional[str] = None


@router.post("/sample/{slug}/visit")
async def sample_visit(slug: str, event: VisitEvent, request: Request):
    """Mark prospect as currently viewing — creates aurem_live_viewers doc."""
    db = _get_db()
    if db is None:
        return {"logged": False, "reason": "no_db"}
    site = await db[COLLECTION].find_one({"slug": slug}, {"_id": 0, "lead_id": 1, "business.name": 1})
    if not site:
        return {"logged": False, "reason": "website_not_found"}

    # Bot filter — block known scrapers/crawlers so WhatsApp alerts stay high-signal
    ua_lower = (event.user_agent or "").lower()
    BOT_KEYWORDS = [
        "bot", "spider", "crawler", "curl", "wget", "python-requests", "httpx",
        "scraper", "slackbot", "googlebot", "bingbot", "yandex", "baidu",
        "facebookexternalhit", "twitterbot", "linkedinbot", "whatsapp", "telegrambot",
        "pingdom", "lighthouse", "headless", "phantom", "selenium", "playwright",
        "axios/", "go-http-client", "java/", "okhttp",
    ]
    if any(bot in ua_lower for bot in BOT_KEYWORDS):
        return {"logged": False, "reason": "bot_filtered", "ua_snippet": ua_lower[:80]}

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    client_ip = request.client.host if request.client else "unknown"
    session_id = f"{slug}-{client_ip}-{int(now.timestamp() // 300)}"  # 5-min bucket per IP

    # Unique-IP dedupe for 24h admin alerts
    from datetime import timedelta
    day_cutoff = (now - timedelta(hours=24)).isoformat()
    already_alerted = await db.aurem_live_viewers.find_one(
        {"slug": slug, "ip": client_ip, "started_at": {"$gte": day_cutoff}, "admin_alert_fired": True},
        {"_id": 1},
    )

    await db.aurem_live_viewers.update_one(
        {"session_id": session_id},
        {
            "$set": {
                "session_id": session_id,
                "slug": slug,
                "lead_id": site.get("lead_id"),
                "business_name": site.get("business", {}).get("name", ""),
                "started_at": now_iso,
                "last_heartbeat_at": now_iso,
                "ip": client_ip,
                "referrer": (event.referrer or "")[:200],
                "user_agent": (event.user_agent or "")[:180],
                "engagement_nudge_fired": False,
            },
            "$inc": {"ping_count": 1},
        },
        upsert=True,
    )

    # Also log a one-time visit in the lead's outreach history
    await db.campaign_leads.update_one(
        {"lead_id": site.get("lead_id")},
        {
            "$push": {
                "outreach_history": {
                    "type": "sample_view",
                    "slug": slug,
                    "session_id": session_id,
                    "ip": client_ip,
                    "timestamp": now_iso,
                }
            },
            "$inc": {"sample_view_count": 1},
            "$set": {"last_sample_view_at": now_iso},
        },
    )

    # Adaptive ORA: record conviction signals (P1 shadow mode — no auto-agent).
    # site_visit on first ping; site_return on any subsequent ping.
    try:
        from services.adaptive_ora import record_signal
        doc_now = await db.aurem_live_viewers.find_one({"session_id": session_id}, {"ping_count": 1})
        pings = int((doc_now or {}).get("ping_count", 1))
        lead_id_for_signal = site.get("lead_id")
        if lead_id_for_signal:
            if pings <= 1:
                await record_signal(db, lead_id_for_signal, "site_visit", {"slug": slug, "ip": client_ip})
            else:
                await record_signal(db, lead_id_for_signal, "site_return", {"slug": slug, "ping": pings})
    except Exception as e:
        logger.debug(f"[AdaptiveORA] site_visit signal skipped: {e}")

    # Fire admin WhatsApp alert ONLY for unique IPs per 24h (suppresses re-visit spam)
    try:
        doc = await db.aurem_live_viewers.find_one({"session_id": session_id}, {"ping_count": 1, "admin_alert_fired": 1})
        if doc and doc.get("ping_count") == 1 and not doc.get("admin_alert_fired") and not already_alerted:
            await _fire_hot_lead_admin_alert(db, site.get("business", {}).get("name", ""), slug)
            await db.aurem_live_viewers.update_one({"session_id": session_id}, {"$set": {"admin_alert_fired": True}})
    except Exception as e:
        logger.warning(f"[HotLead] admin alert failed: {e}")

    # Lifecycle: prospect opened their sample site → mark as 'engaged'
    try:
        from services.lead_lifecycle import transition, record_touchpoint
        if site.get("lead_id"):
            await record_touchpoint(
                db, site["lead_id"], "web", "sample_site_visit", "engaged",
                details={"slug": slug, "session_id": session_id, "referrer": event.referrer or "direct"},
            )
            await transition(db, site["lead_id"], "engaged", reason="sample_site_visit")
    except Exception as e:
        logger.warning(f"[Lifecycle] engaged transition failed: {e}")

    return {"logged": True, "session_id": session_id, "timestamp": now_iso, "ip_alerted_today": bool(already_alerted)}


@router.post("/sample/{slug}/heartbeat")
async def sample_heartbeat(slug: str, request: Request):
    """Called every 15s by the sample page. Extends live-viewer record."""
    db = _get_db()
    if db is None:
        return {"ok": False}
    body = await request.json()
    session_id = body.get("session_id", "")
    if not session_id:
        return {"ok": False, "reason": "no_session"}
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.aurem_live_viewers.update_one(
        {"session_id": session_id},
        {"$set": {"last_heartbeat_at": now_iso}, "$inc": {"ping_count": 1}},
    )

    # Adaptive ORA: fire site_dwell_60s once when dwell crosses ~60s (~4 heartbeats)
    try:
        doc = await db.aurem_live_viewers.find_one(
            {"session_id": session_id},
            {"_id": 0, "lead_id": 1, "ping_count": 1, "dwell_signal_fired": 1, "started_at": 1},
        )
        if doc and not doc.get("dwell_signal_fired") and int(doc.get("ping_count", 0)) >= 4:
            from services.adaptive_ora import record_signal
            lid = doc.get("lead_id")
            if lid:
                await record_signal(db, lid, "site_dwell_60s", {"pings": doc.get("ping_count", 0)})
            await db.aurem_live_viewers.update_one(
                {"session_id": session_id},
                {"$set": {"dwell_signal_fired": True}},
            )
    except Exception:
        pass

    return {"ok": True, "ts": now_iso}


@router.post("/sample/{slug}/engaged")
async def sample_engaged(slug: str, request: Request):
    """Fired client-side at 30s. Sends prospect a WhatsApp nudge. Idempotent per session."""
    db = _get_db()
    if db is None:
        return {"sent": False, "reason": "no_db"}
    body = await request.json()
    session_id = body.get("session_id", "")
    vd = await db.aurem_live_viewers.find_one({"session_id": session_id}, {"_id": 0, "engagement_nudge_fired": 1, "lead_id": 1})
    if not vd:
        return {"sent": False, "reason": "no_session"}
    if vd.get("engagement_nudge_fired"):
        return {"sent": False, "reason": "already_fired"}

    lead = await db.campaign_leads.find_one({"lead_id": vd.get("lead_id")}, {"_id": 0})
    if not lead:
        return {"sent": False, "reason": "no_lead"}

    phone = (lead.get("phone") or "").replace("+", "").replace("-", "").replace(" ", "")
    if not phone:
        return {"sent": False, "reason": "no_phone"}

    name = lead.get("business_name", "there")
    nudge = (
        f"Hi {name}! 👋\n\n"
        f"I see you're checking out your free website sample — any questions?\n\n"
        f"Reply *YES* and we'll activate it for you in 24 hours.\n"
        f"7-day free trial, no credit card needed.\n\n"
        f"_— ORA, AUREM Intelligence_\n"
        f"_Reply STOP to opt out_"
    )
    try:
        import httpx
        whapi_token = os.environ.get("WHAPI_API_TOKEN", "")
        whapi_url = os.environ.get("WHAPI_API_URL", "")
        if not (whapi_token and whapi_url):
            return {"sent": False, "reason": "whapi_not_configured"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{whapi_url}/messages/text",
                headers={"authorization": f"Bearer {whapi_token}", "content-type": "application/json"},
                json={"to": f"{phone}@s.whatsapp.net", "body": nudge},
            )
        ok = resp.status_code == 200
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.aurem_live_viewers.update_one({"session_id": session_id}, {"$set": {"engagement_nudge_fired": True, "engagement_nudge_at": now_iso}})
        await db.campaign_leads.update_one(
            {"lead_id": vd.get("lead_id")},
            {"$push": {"outreach_history": {
                "type": "sample_engagement_nudge", "channel": "whatsapp", "to": phone,
                "status": "sent" if ok else "failed", "template": "sample_30s_nudge_v1", "timestamp": now_iso,
            }}},
        )
        return {"sent": ok, "channel": "whatsapp", "timestamp": now_iso}
    except Exception as e:
        logger.warning(f"[SampleEngaged] {slug}: {e}")
        return {"sent": False, "reason": str(e)}


async def _fire_hot_lead_admin_alert(db, business_name: str, slug: str):
    """WhatsApp the admin line — '🔥 HOT LEAD: X is on their sample page now!'"""
    import httpx
    phone = HOT_LEAD_ADMIN_PHONE.replace("+", "").replace("-", "").replace(" ", "")
    if not phone:
        return
    whapi_token = os.environ.get("WHAPI_API_TOKEN", "")
    whapi_url = os.environ.get("WHAPI_API_URL", "")
    if not (whapi_token and whapi_url):
        return
    public_base = os.environ.get("PUBLIC_APP_URL", "https://aurem.live").rstrip("/")
    msg = (
        f"🔥 *HOT LEAD*\n\n"
        f"*{business_name}* is on their sample page RIGHT NOW!\n\n"
        f"👉 {public_base}/sample/{slug}\n\n"
        f"Campaign HQ — react in the next 30 sec.\n"
        f"_AUREM Intelligence_"
    )
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{whapi_url}/messages/text",
                headers={"authorization": f"Bearer {whapi_token}", "content-type": "application/json"},
                json={"to": f"{phone}@s.whatsapp.net", "body": msg},
            )
    except Exception as e:
        logger.warning(f"[HotLead] admin WA error: {e}")


# ─────────────────────────────────────────────────────────────
# AUTO-TRIGGER HOOK (used by scout agent + campaign flows)
# ─────────────────────────────────────────────────────────────
async def auto_generate_if_missing(db, lead: dict) -> Optional[dict]:
    """
    Called by Scout when a business is found without a website.
    Reuses the same generate pipeline but runs in background without auth.
    """
    if not lead:
        return None
    if lead.get("website_url"):
        return None  # already has a website
    lead_id = lead.get("lead_id")
    if not lead_id:
        return None
    existing = await db[COLLECTION].find_one({"lead_id": lead_id}, {"_id": 0, "slug": 1})
    if existing:
        return existing
    website = generate_website(lead)
    await db[COLLECTION].update_one({"lead_id": lead_id}, {"$set": website}, upsert=True)
    logger.info(f"[WebsiteBuilder] Auto-generated site for {lead_id} (industry={website['industry']}, qc={website['quality_check']['passed']})")
    return website


# ─────────────────────────────────────────────────────────────
# CAMPAIGN SEND
# ─────────────────────────────────────────────────────────────
@router.post("/send-campaign/{slug}")
async def send_website_campaign(slug: str, request: Request):
    """Reuses existing blast-all pipeline but overrides the sample URL in the content."""
    _verify_admin(request)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    site = await db[COLLECTION].find_one({"slug": slug}, {"_id": 0})
    if not site:
        raise HTTPException(404, "Website not found")
    lead_id = site["lead_id"]
    lead = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")

    # Build AUREM website-launch messages using the sample URL
    name = lead.get("business_name", "")
    public_base = os.environ.get("PUBLIC_APP_URL", "https://aurem.live").rstrip("/")
    slug_url = f"{public_base}/sample/{slug}"
    rating = lead.get("rating", "5.0")
    # Messages
    wa = (
        f"Hi *{name}*! 👋\n\n"
        f"_World's First AI Business Intelligence_\nfrom *AUREM*\n\n"
        f"🎁 We built your *FREE website!*\n\n"
        f"Your business deserves to be found online.\nSo we built it for you — completely FREE.\n\n"
        f"👉 *See it here:*\n{slug_url}\n\n"
        f"✅ Your services listed\n"
        f"✅ Your {rating}⭐ reviews shown\n"
        f"✅ Call + WhatsApp buttons\n"
        f"✅ Mobile optimized\n"
        f"✅ Google SEO ready\n\n"
        f"_Reply *YES* to activate in 24 hours!_\n"
        f"7-day free trial — no credit card 💪\n\n"
        f"_Reply STOP to unsubscribe_"
    )
    # Carrier-safe SMS: no ALL-CAPS marketing words, no emojis, short.
    sms = (
        f"Hi {name}, this is ORA from AUREM. "
        f"We built a sample site for you: {slug_url} "
        f"Reply YES if you'd like us to activate it. Reply STOP to opt out."
    )
    email_subject = f"{name} — Your FREE website is ready! 🎉"
    email_html = f"""
<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f4f4f4;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 0;background:#f4f4f4;">
<tr><td align="center"><table role="presentation" width="640" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
<tr><td style="background:#000;padding:36px 40px 28px;text-align:left;">
<div style="font-family:'Cinzel',Georgia,serif;font-size:32px;font-weight:700;letter-spacing:4px;color:#C9A227;">AUREM</div>
<div style="margin-top:6px;font-size:12px;letter-spacing:3px;text-transform:uppercase;color:#C9A227;font-weight:600;">World's First AI Business Intelligence</div>
</td></tr>
<tr><td style="padding:36px 40px;color:#111827;">
<h1 style="margin:0 0 14px;font-size:22px;color:#0b0b0f;">Hi {name} Team,</h1>
<p style="font-size:15px;line-height:1.65;color:#374151;">🎁 We built you a <strong style="color:#C9A227;">FREE website</strong> — see it live below.</p>
<div style="text-align:center;margin:30px 0;">
<a href="{slug_url}" style="display:inline-block;background:#C9A227;color:#000;font-weight:700;font-size:15px;padding:16px 34px;border-radius:10px;text-decoration:none;letter-spacing:1px;">See Your Free Website →</a>
<div style="margin-top:12px;font-size:12px;color:#6b7280;">{slug_url}</div>
</div>
<ul style="font-size:14px;line-height:1.9;color:#1f2937;padding-left:20px;">
<li>✅ Your services listed</li>
<li>✅ Your {rating}⭐ reviews shown</li>
<li>✅ Call + WhatsApp buttons</li>
<li>✅ Mobile optimized + Google SEO ready</li>
</ul>
<p style="font-size:15px;color:#374151;">Reply <strong>YES</strong> and we'll activate it within 24 hours. 7-day free trial — no credit card needed.</p>
<p style="margin:0 0 4px;">— ORA</p>
<p style="margin:0;font-size:12px;color:#6b7280;">AUREM Intelligence AI</p>
</td></tr>
<tr><td style="background:#0b0b0f;padding:18px 40px;text-align:center;font-size:11px;color:#9ca3af;">
<a href="https://aurem.live" style="color:#C9A227;text-decoration:none;">aurem.live</a> · <a href="mailto:opt-out@aurem.live" style="color:#9ca3af;text-decoration:none;">Unsubscribe</a>
<div style="margin-top:6px;">Reply STOP to opt out. AUREM · Mississauga, ON Canada.</div>
</td></tr>
</table></td></tr></table></body></html>
"""
    voice = (
        f"Hi! I'm ORA from AUREM Intelligence AI. "
        f"We built a free sample website for {name}. "
        f"Check your email or WhatsApp for the link — "
        f"we can have it live and attracting customers within 24 hours, "
        f"completely free trial. Reply YES to activate! Thank you."
    )

    # Reuse the existing /api/campaign blast flow inline (avoid import cycle)
    from routers.campaign_router import blast_all_channels  # type: ignore
    # Not ideal — call the low-level sends directly for cleanliness
    import httpx
    now = datetime.now(timezone.utc).isoformat()
    results = {}
    email = lead.get("email", "")
    phone = (lead.get("phone") or "").replace("+", "").replace("-", "").replace(" ", "")

    if email:
        try:
            import resend
            resend.api_key = os.environ.get("RESEND_API_KEY", "")
            email_payload = {"from": "ORA <ora@aurem.live>", "to": [email], "subject": email_subject, "html": email_html, "reply_to": "support@aurem.live"}
            bcc = os.environ.get("AUREM_SALES_BCC_EMAIL", "").strip()
            if bcc:
                email_payload["bcc"] = [bcc]
            r = resend.Emails.send(email_payload)
            results["email"] = {"success": True, "id": r.get("id", str(r)), "bcc": bool(bcc)}
        except Exception as e:
            results["email"] = {"success": False, "error": str(e)}
    if phone:
        try:
            whapi_token = os.environ.get("WHAPI_API_TOKEN", "")
            whapi_url = os.environ.get("WHAPI_API_URL", "")
            async with httpx.AsyncClient(timeout=15) as c:
                rw = await c.post(f"{whapi_url}/messages/text", headers={"authorization": f"Bearer {whapi_token}", "content-type": "application/json"}, json={"to": f"{phone}@s.whatsapp.net", "body": wa})
            results["whatsapp"] = {"success": rw.status_code == 200}
        except Exception as e:
            results["whatsapp"] = {"success": False, "error": str(e)}
        try:
            sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
            tok = os.environ.get("TWILIO_AUTH_TOKEN", "")
            fn = os.environ.get("TWILIO_PHONE_NUMBER", "")
            async with httpx.AsyncClient(timeout=15) as c:
                rs = await c.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", auth=(sid, tok), data={"From": fn, "To": f"+{phone}", "Body": sms})
            results["sms"] = {"success": rs.status_code in (200, 201), "sid": rs.json().get("sid")}
        except Exception as e:
            results["sms"] = {"success": False, "error": str(e)}
        try:
            sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
            tok = os.environ.get("TWILIO_AUTH_TOKEN", "")
            fn = os.environ.get("TWILIO_PHONE_NUMBER", "")
            twiml = f'<Response><Say voice="Polly.Joanna">{voice}</Say></Response>'
            async with httpx.AsyncClient(timeout=15) as c:
                rc = await c.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json", auth=(sid, tok), data={"From": fn, "To": f"+{phone}", "Twiml": twiml})
            results["voice"] = {"success": rc.status_code in (200, 201), "call_sid": rc.json().get("sid")}
        except Exception as e:
            results["voice"] = {"success": False, "error": str(e)}

    sent = sum(1 for r in results.values() if r.get("success"))
    await db.campaign_leads.update_one(
        {"lead_id": lead_id},
        {"$push": {"outreach_history": {"type": "website_campaign", "slug": slug, "sent_count": sent, "template": "aurem_website_v1", "timestamp": now}}, "$set": {"updated_at": now}},
    )
    await db[COLLECTION].update_one({"slug": slug}, {"$set": {"campaign_sent_at": now, "campaign_results": results}})
    return {"slug": slug, "sent_count": sent, "total_channels": 4, "results": results, "sample_url": slug_url}
