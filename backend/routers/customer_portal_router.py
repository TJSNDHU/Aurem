"""
Customer Portal Router — Backs the 8-item Customer Dashboard
============================================================
Endpoints (all under /api/customer/*):
    GET  /api/customer/website               — View site data
    PUT  /api/customer/website               — Edit essentials (phone, hours, services, etc.)
    GET  /api/customer/reviews               — List reviews + stats
    POST /api/customer/reviews/request-batch — Queue review requests via WhatsApp
    GET  /api/customer/social/status         — Social media (Postiz) status
    POST /api/customer/social/toggle         — Enable/disable auto-posting
    GET  /api/customer/reports               — List monthly PDF reports
    POST /api/customer/reports/generate       — Queue new report (WhatsApp + Email)
    GET  /api/customer/billing                — Plan + invoices
    POST /api/customer/billing/portal         — Open Stripe portal
    GET  /api/customer/referrals              — List referrals + rewards
    POST /api/customer/referrals/track       — Track a referral signup

All endpoints authenticated via Bearer JWT.
"""

import os
import re
import logging
import random
import string
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List

import jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/customer", tags=["Customer Portal"])

JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET:
    raise RuntimeError("CRITICAL: JWT_SECRET not set.")

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    if _db is None:
        raise HTTPException(503, "Database not available")
    return _db


async def _auth(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        payload = jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


async def _get_user(db, payload: dict) -> dict:
    email = (payload.get("email") or payload.get("sub") or "").lower()
    if not email:
        raise HTTPException(401, "Invalid token")
    user = await db.platform_users.find_one({"email": email}, {"_id": 0}) \
        or await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")
    user["_email"] = email
    return user


# ═══════════════════════════════════════════════════════════════
# WEBSITE
# ═══════════════════════════════════════════════════════════════

class WebsiteEdit(BaseModel):
    phone: Optional[str] = None
    hours: Optional[str] = None
    services: Optional[List[str]] = None
    tagline: Optional[str] = None
    about: Optional[str] = None


@router.get("/website")
async def get_website(request: Request):
    payload = await _auth(request)
    db = _get_db()
    user = await _get_user(db, payload)
    email = user["_email"]

    site = await db.customer_sites.find_one({"email": email}, {"_id": 0}) or {}
    ws = await db.aurem_workspaces.find_one({"owner_email": email}, {"_id": 0}) or {}

    return {
        "url": site.get("url") or ws.get("sample_website_url") or ws.get("website") or "",
        "phone": site.get("phone", user.get("phone", "")),
        "hours": site.get("hours", ""),
        "services": site.get("services", []),
        "tagline": site.get("tagline", ""),
        "about": site.get("about", ""),
        "last_synced_at": site.get("last_synced_at", ""),
    }


@router.put("/website")
async def edit_website(body: WebsiteEdit, request: Request):
    payload = await _auth(request)
    db = _get_db()
    user = await _get_user(db, payload)
    email = user["_email"]

    updates = {k: v for k, v in body.dict().items() if v is not None}
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updates["updated_by"] = email

    await db.customer_sites.update_one(
        {"email": email},
        {"$set": updates, "$setOnInsert": {"email": email, "bin": user.get("business_id", "")}},
        upsert=True,
    )

    # Log activity
    try:
        await db.audit_chain.insert_one({
            "event_type": "customer.site.edit",
            "description": f"Customer edited website essentials ({', '.join(updates.keys())})",
            "tenant_id": user.get("id") or user.get("tenant_id") or email,
            "email": email,
            "timestamp": updates["updated_at"],
        })
    except Exception:
        pass

    site = await db.customer_sites.find_one({"email": email}, {"_id": 0})
    return {"success": True, "url": site.get("url", ""), "updated_fields": list(updates.keys())}


# ═══════════════════════════════════════════════════════════════
# REVIEWS (Google Reviews via Places API when configured)
# ═══════════════════════════════════════════════════════════════

@router.get("/reviews")
async def get_reviews(request: Request):
    payload = await _auth(request)
    db = _get_db()
    user = await _get_user(db, payload)
    email = user["_email"]

    reviews_cursor = db.google_reviews.find(
        {"email": email},
        {"_id": 0, "author": 1, "rating": 1, "text": 1, "date": 1, "source": 1},
    ).sort("date", -1).limit(50)
    reviews = [r async for r in reviews_cursor]

    # Stats
    total = len(reviews)
    avg = sum(r.get("rating", 0) for r in reviews) / total if total else 0

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    req_sent = await db.review_requests.count_documents({"email": email, "sent_at": {"$gte": month_start}})
    new_revs = await db.google_reviews.count_documents({"email": email, "date": {"$gte": month_start}})

    return {
        "reviews": reviews,
        "stats": {
            "total": total,
            "avg_rating": round(avg, 2),
            "requests_sent": req_sent,
            "new_reviews": new_revs,
        },
    }


@router.post("/reviews/request-batch")
async def request_reviews_batch(request: Request):
    payload = await _auth(request)
    db = _get_db()
    user = await _get_user(db, payload)
    email = user["_email"]

    # Find recent customers (campaign_leads converted/visited last 30 days)
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    recent_cursor = db.campaign_leads.find(
        {"tenant_email": email, "updated_at": {"$gte": cutoff}, "status": {"$in": ["converted", "visited", "closed_won"]}},
        {"_id": 0, "phone": 1, "email": 1, "name": 1},
    ).limit(20)
    recent = [x async for x in recent_cursor]

    if not recent:
        return {"success": True, "message": "No recent customers to request reviews from yet.", "queued": 0}

    review_url = (await db.customer_sites.find_one({"email": email}, {"_id": 0, "google_review_url": 1}) or {}).get("google_review_url") \
        or f"https://g.page/r/{user.get('business_id', '')}"

    queued = 0
    try:
        from routers.whatsapp_alerts import send_whatsapp
        for lead in recent:
            phone = (lead.get("phone") or "").strip()
            if not phone:
                continue
            msg = (f"Hi {lead.get('name', 'there')}! Hope you enjoyed your visit.\n"
                   f"If you have 30 seconds, we'd love your review: {review_url}\n\n"
                   f"Reply STOP to unsubscribe.")
            try:
                await send_whatsapp(phone, msg)
                await db.review_requests.insert_one({
                    "email": email,
                    "to_phone": phone,
                    "to_name": lead.get("name", ""),
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "channel": "whatsapp",
                })
                queued += 1
            except Exception as e:
                logger.warning(f"[CUSTOMER] Review request failed for {phone}: {e}")
    except Exception as e:
        logger.warning(f"[CUSTOMER] WhatsApp unavailable: {e}")

    return {"success": True, "message": f"Queued {queued} review requests.", "queued": queued}


# ═══════════════════════════════════════════════════════════════
# SOCIAL (Postiz)
# ═══════════════════════════════════════════════════════════════

@router.get("/social/status")
async def social_status(request: Request):
    payload = await _auth(request)
    db = _get_db()
    user = await _get_user(db, payload)
    email = user["_email"]

    configured = bool(os.environ.get("POSTIZ_API_KEY"))
    doc = await db.customer_social.find_one({"email": email}, {"_id": 0}) or {}
    return {
        "configured": configured,
        "enabled": bool(doc.get("enabled", False)),
        "accounts": doc.get("accounts", []),
        "last_post_at": doc.get("last_post_at", ""),
    }


class SocialToggle(BaseModel):
    enabled: bool


@router.post("/social/toggle")
async def social_toggle(body: SocialToggle, request: Request):
    payload = await _auth(request)
    db = _get_db()
    user = await _get_user(db, payload)
    email = user["_email"]

    await db.customer_social.update_one(
        {"email": email},
        {"$set": {"enabled": body.enabled, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"success": True, "enabled": body.enabled}


# ═══════════════════════════════════════════════════════════════
# REPORTS
# ═══════════════════════════════════════════════════════════════

@router.get("/reports")
async def list_reports(request: Request):
    payload = await _auth(request)
    db = _get_db()
    user = await _get_user(db, payload)
    email = user["_email"]

    cursor = db.customer_reports.find(
        {"email": email},
        {"_id": 0, "title": 1, "month": 1, "url": 1, "generated_at": 1, "status": 1},
    ).sort("generated_at", -1).limit(12)
    reports = [r async for r in cursor]
    return {"reports": reports}


@router.post("/reports/generate")
async def generate_report_now(request: Request):
    payload = await _auth(request)
    db = _get_db()
    user = await _get_user(db, payload)
    email = user["_email"]
    now = datetime.now(timezone.utc)

    # Queue job: insert pending report record, let nightly/queued worker render PDF
    await db.customer_reports.insert_one({
        "email": email,
        "bin": user.get("business_id", ""),
        "title": f"Report — {now.strftime('%b %Y')}",
        "month": now.strftime("%Y-%m"),
        "status": "queued",
        "generated_at": now.isoformat(),
        "url": "",
    })

    # Try to trigger immediate generation via existing report service if present
    try:
        from services.customer_monthly_report import generate_for_user  # type: ignore
        import asyncio
        asyncio.get_event_loop().create_task(generate_for_user(email))
        return {"success": True, "message": "Report queued. We'll notify you when it's ready."}
    except Exception:
        return {"success": True, "message": "Report queued. It will be generated on the next cycle."}


# ═══════════════════════════════════════════════════════════════
# BILLING (Stripe)
# ═══════════════════════════════════════════════════════════════

@router.get("/billing")
async def billing_info(request: Request):
    payload = await _auth(request)
    db = _get_db()
    user = await _get_user(db, payload)
    email = user["_email"]

    plan_doc = await db.tenant_plans.find_one(
        {"$or": [{"tenant_email": email}, {"tenant_id": user.get("id")}]},
        {"_id": 0},
    ) or {}

    invoices_cursor = db.stripe_invoices.find({"email": email}, {"_id": 0, "amount": 1, "date": 1, "status": 1, "url": 1}).sort("date", -1).limit(12)
    invoices = [i async for i in invoices_cursor]

    pm = {}
    pm_doc = await db.stripe_payment_methods.find_one({"email": email}, {"_id": 0, "last4": 1, "brand": 1})
    if pm_doc:
        pm = {"last4": pm_doc.get("last4", ""), "brand": pm_doc.get("brand", "")}

    return {
        "plan_name": plan_doc.get("plan_name", "Trial"),
        "status": plan_doc.get("status", "trial"),
        "next_invoice_amount": plan_doc.get("next_invoice_amount"),
        "next_invoice_date": plan_doc.get("next_invoice_date"),
        "payment_method": pm,
        "invoices": invoices,
    }


@router.post("/billing/portal")
async def billing_portal(request: Request):
    payload = await _auth(request)
    db = _get_db()
    user = await _get_user(db, payload)
    email = user["_email"]

    try:
        import stripe
        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
        customer_id = user.get("stripe_customer_id")
        if not customer_id:
            # Try to find from invoices or create
            inv_doc = await db.stripe_invoices.find_one({"email": email}, {"_id": 0, "customer_id": 1})
            if inv_doc:
                customer_id = inv_doc.get("customer_id")
        if not customer_id:
            raise HTTPException(400, "No Stripe customer on file yet. Subscribe first.")

        return_url = os.environ.get("APP_BASE_URL", "https://aurem.live") + "/my/billing"
        session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
        return {"url": session.url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CUSTOMER] Stripe portal error: {e}")
        raise HTTPException(502, "Unable to open billing portal")


# ═══════════════════════════════════════════════════════════════
# REFERRALS
# ═══════════════════════════════════════════════════════════════

@router.get("/referrals")
async def list_referrals(request: Request):
    payload = await _auth(request)
    db = _get_db()
    user = await _get_user(db, payload)
    email = user["_email"]
    bin_code = user.get("business_id", "")

    cursor = db.referrals.find(
        {"referrer_email": email},
        {"_id": 0, "referee_email": 1, "status": 1, "created_at": 1, "subscribed_at": 1},
    ).sort("created_at", -1).limit(50)
    referrals = []
    count_successful = 0
    async for r in cursor:
        em = r.get("referee_email", "")
        masked = (em[:2] + "•••" + em.split("@")[-1]) if "@" in em else em
        referrals.append({
            "masked_email": masked,
            "status": r.get("status", "pending"),
            "created_at": r.get("created_at", ""),
        })
        if r.get("status") == "subscribed":
            count_successful += 1

    rewards_earned = count_successful  # 1 month per successful referral
    return {
        "referrals": referrals,
        "count_successful": count_successful,
        "rewards_earned": rewards_earned,
        "your_bin": bin_code,
    }


class TrackReferral(BaseModel):
    referrer_bin: str
    referee_email: str


@router.post("/referrals/track")
async def track_referral(body: TrackReferral):
    """Called when a new signup includes ?ref=BIN query. Public (no auth)."""
    db = _get_db()
    from services.bin_generator import normalize_bin

    bid = normalize_bin(body.referrer_bin)
    owner = await db.platform_users.find_one({"business_id": bid}, {"_id": 0, "email": 1}) \
        or await db.users.find_one({"business_id": bid}, {"_id": 0, "email": 1})
    if not owner:
        return {"success": False, "reason": "Invalid BIN"}

    await db.referrals.update_one(
        {"referrer_email": owner["email"], "referee_email": body.referee_email.lower()},
        {"$set": {
            "referrer_email": owner["email"],
            "referrer_bin": bid,
            "referee_email": body.referee_email.lower(),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"success": True}


# ═══════════════════════════════════════════════════════════════
# API KEY + PIXEL INSTALL INFO for current customer
# ═══════════════════════════════════════════════════════════════

@router.get("/api-key")
async def get_customer_api_key(request: Request):
    """Return the current customer's plaintext API key + pixel install snippet.
    For new hashed keys (rr_live_*), only preview is returned since we don't store plaintext.
    """
    payload = await _auth(request)
    db = _get_db()
    user = await _get_user(db, payload)
    email = user["_email"]

    # Prefer legacy plaintext key (ReRoots style)
    key_doc = await db.api_keys.find_one(
        {"$or": [{"owner_email": email}, {"owner_email": {"$regex": f"^{email}$", "$options": "i"}}], "is_active": True},
        {"_id": 0, "key": 1, "created_at": 1, "last_used": 1, "tenant_id": 1, "business_name": 1, "permissions": 1, "hit_count": 1},
        sort=[("created_at", -1)],
    )
    plain = key_doc.get("key") if key_doc else None
    retrievable = bool(plain)

    if not key_doc:
        # Try new hashed key doc
        key_doc = await db.api_keys.find_one(
            {"email": email, "active": True},
            {"_id": 0, "key_preview": 1, "created_at": 1, "last_used": 1, "tenant_id": 1, "client_name": 1, "usage_count": 1},
            sort=[("created_at", -1)],
        )

    if not key_doc:
        return {"has_key": False, "message": "No API key issued yet. One is generated automatically on first welcome package."}

    # Last ping
    last_used = key_doc.get("last_used")
    tenant_id = key_doc.get("tenant_id", "")
    events_total = await db.pixel_events.count_documents({"tenant_id": tenant_id}) if tenant_id else 0

    base_url = os.environ.get("APP_BASE_URL", "https://aurem.live")
    key_value = plain or (key_doc.get("key_preview") or "")
    snippet = (f'<script src="{base_url}/api/pixel/aurem-pixel.js" '
               f'data-aurem-key="{key_value}"></script>')

    return {
        "has_key": True,
        "retrievable": retrievable,
        "key": plain if retrievable else "",
        "key_preview": key_doc.get("key_preview") or (plain[:14] + "..." + plain[-4:] if plain else ""),
        "created_at": key_doc.get("created_at"),
        "last_used": last_used,
        "connected": bool(last_used),
        "events_total": events_total,
        "tenant_id": tenant_id,
        "business_name": key_doc.get("business_name") or key_doc.get("client_name", ""),
        "snippet": snippet,
        "install_instructions": "Paste this 1-line script tag right before </head> on every page.",
    }


class RegenerateKeyRequest(BaseModel):
    confirm: bool = True


@router.post("/api-key/regenerate")
async def regenerate_api_key(body: RegenerateKeyRequest, request: Request):
    payload = await _auth(request)
    if not body.confirm:
        raise HTTPException(400, "Please confirm key regeneration.")
    db = _get_db()
    user = await _get_user(db, payload)
    email = user["_email"]

    import secrets
    new_key = f"aurem_rr_{secrets.token_hex(16)}"

    now = datetime.now(timezone.utc).isoformat()
    # Revoke existing
    await db.api_keys.update_many(
        {"$and": [
            {"$or": [{"owner_email": email}, {"email": email}]},
            {"$or": [{"is_active": True}, {"active": True}]},
        ]},
        {"$set": {"is_active": False, "active": False, "revoked_at": now}},
    )
    # Insert new
    await db.api_keys.insert_one({
        "key": new_key,
        "business_id": user.get("business_id", ""),
        "business_name": user.get("company_name") or user.get("business_name", ""),
        "owner_email": email,
        "created_at": now,
        "is_active": True,
        "permissions": ["pixel", "webhooks", "ai_chat", "scanner"],
        "tenant_id": user.get("id") or user.get("tenant_id") or email,
    })

    base_url = os.environ.get("APP_BASE_URL", "https://aurem.live")
    return {
        "success": True,
        "key": new_key,
        "snippet": f'<script src="{base_url}/api/pixel/aurem-pixel.js" data-aurem-key="{new_key}"></script>',
    }


@router.get("/health")
async def health():
    return {"status": "ok", "service": "customer-portal"}


# ═══════════════════════════════════════════════════════════════
# SCAN HISTORY (Feb 2026 — Gap 4)
# ═══════════════════════════════════════════════════════════════

@router.get("/scan-history")
async def scan_history(request: Request, limit: int = 30):
    """Return last N scans + auto-fixes for the logged-in customer's site(s)."""
    payload = await _auth(request)
    db = _get_db()
    user = await _get_user(db, payload)
    email = user["_email"]

    ws = await db.aurem_workspaces.find_one(
        {"owner_email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}},
        {"_id": 0, "website": 1}
    ) or {}
    site_url = ws.get("website") or user.get("website") or ""

    history = []
    if site_url:
        repair_cursor = db.system_auto_repairs.find(
            {"site_url": site_url},
            {"_id": 0, "site_url": 1, "overall_score": 1, "scores": 1, "issues_total": 1,
             "critical_count": 1, "warning_count": 1, "repairs": 1, "scanned_at": 1, "completed_at": 1, "label": 1},
        ).sort("scanned_at", -1).limit(max(1, min(limit, 100)))
        async for r in repair_cursor:
            history.append({
                "type": "scan",
                "site_url": r.get("site_url", ""),
                "overall_score": r.get("overall_score", 0),
                "scores": r.get("scores", {}),
                "issues_total": r.get("issues_total", 0),
                "critical_count": r.get("critical_count", 0),
                "warning_count": r.get("warning_count", 0),
                "fixes_applied": sum(1 for rp in (r.get("repairs") or []) if rp.get("status") == "completed"),
                "scanned_at": r.get("scanned_at", ""),
                "completed_at": r.get("completed_at", ""),
                "label": r.get("label", ""),
            })

    # Also pull user-scoped scan_history
    tenant_id = user.get("id") or user.get("tenant_id", "")
    if tenant_id:
        legacy = db.scan_history.find(
            {"user_id": tenant_id},
            {"_id": 0, "scan_id": 1, "website_url": 1, "overall_score": 1, "scores": 1, "summary": 1, "created_at": 1, "share_id": 1},
        ).sort("created_at", -1).limit(20)
        async for r in legacy:
            history.append({
                "type": "legacy_scan",
                "scan_id": r.get("scan_id", ""),
                "site_url": r.get("website_url", ""),
                "overall_score": r.get("overall_score", 0),
                "scores": r.get("scores", {}),
                "summary": r.get("summary", {}),
                "share_id": r.get("share_id", ""),
                "scanned_at": r.get("created_at", ""),
            })

    # Sort combined
    history.sort(key=lambda x: x.get("scanned_at", ""), reverse=True)

    # Summary
    latest = history[0] if history else None
    total_fixes = sum(h.get("fixes_applied", 0) for h in history)

    return {
        "site_url": site_url,
        "latest": latest,
        "total_scans": len(history),
        "total_fixes_applied": total_fixes,
        "history": history[:limit],
    }


# ═══════════════════════════════════════════════════════════════
# GITHUB CONNECT (Feb 2026 — Gap 2)
# ═══════════════════════════════════════════════════════════════

@router.get("/github/status")
async def github_connection_status(request: Request):
    """Return whether customer has connected GitHub + which repo."""
    payload = await _auth(request)
    db = _get_db()
    user = await _get_user(db, payload)
    tenant_id = user.get("id") or user.get("tenant_id") or user["_email"]

    try:
        from services.github_deploy_service import get_connection_status
        return await get_connection_status(tenant_id)
    except Exception as e:
        logger.warning(f"[CUSTOMER] GitHub status error: {e}")
        return {"connected": False, "error": "unavailable"}


class GitHubConnect(BaseModel):
    token: str
    repo: Optional[str] = None  # "owner/name"


@router.post("/github/connect")
async def github_connect(body: GitHubConnect, request: Request):
    """Store customer's personal access token (PAT) + optional default repo."""
    payload = await _auth(request)
    db = _get_db()
    user = await _get_user(db, payload)
    tenant_id = user.get("id") or user.get("tenant_id") or user["_email"]

    try:
        from services.github_deploy_service import connect_github
        result = await connect_github(tenant_id, body.token)
        if body.repo and result.get("success"):
            await db.nexus_credentials.update_one(
                {"tenant_id": tenant_id, "service": "github"},
                {"$set": {"default_repo": body.repo, "updated_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )
        return result
    except Exception as e:
        logger.error(f"[CUSTOMER] GitHub connect error: {e}")
        raise HTTPException(502, "Failed to connect GitHub")


@router.get("/github/prs")
async def github_pr_list(request: Request, limit: int = 20):
    """List recent AUREM-opened PRs for this tenant."""
    payload = await _auth(request)
    db = _get_db()
    user = await _get_user(db, payload)
    tenant_id = user.get("id") or user.get("tenant_id") or user["_email"]

    cursor = db.github_deployments.find(
        {"tenant_id": tenant_id},
        {"_id": 0, "repo": 1, "branch": 1, "pr_url": 1, "pr_number": 1, "fix_title": 1, "status": 1, "created_at": 1},
    ).sort("created_at", -1).limit(limit)
    prs = [p async for p in cursor]
    return {"prs": prs, "count": len(prs)}
