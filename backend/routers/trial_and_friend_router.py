"""
Trial + Friend Scanner + Viral Referrals Router (Phase 3+5)
============================================================
Endpoints:
  - POST /api/trial/activate              Create 7-day Power Trial on signup
  - GET  /api/trial/status                Trial days remaining + quotas
  - POST /api/customer/friend-scan        Scan friend's site (rate-limited)
  - GET  /api/customer/friend-scans       List my friend scans + referral clicks
  - GET  /api/public/report/{slug}        Signup-gated report page
  - GET  /api/customer/pixel/install      4-method install UX data
  - GET  /api/pricing-pro                 Hidden combo plans (Starter/Growth/Enterprise)
"""
import os
import uuid
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Trial + Viral Growth"])
_db = None


def set_db(database):
    global _db
    _db = database


# ═════ Auth helpers ═════
def _decode_jwt(request: Request) -> dict:
    import jwt
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(500, "JWT_SECRET not configured")
    try:
        return jwt.decode(auth[7:], secret, algorithms=["HS256"])
    except Exception as e:
        raise HTTPException(401, f"invalid token: {e}")


async def _verify_platform_user(request: Request) -> dict:
    user = _decode_jwt(request)
    email = (user.get("email") or "").lower()
    if not email or _db is None:
        raise HTTPException(401, "unauthorized")
    doc = await _db.platform_users.find_one({"email": email}, {"_id": 0, "password_hash": 0})
    if not doc:
        raise HTTPException(404, "user not found")
    doc["bin"] = doc.get("bin") or doc.get("business_id") or doc.get("tenant_id")
    return doc


# ═════ Trial State Machine ═════

async def _ensure_trial(tenant_bin: str, email: str) -> dict:
    """Idempotent trial creation. Called from multiple entry points."""
    if _db is None:
        return {}
    existing = await _db.trial_sessions.find_one({"email": email}, {"_id": 0})
    if existing:
        # Recalculate days_remaining
        try:
            ends = datetime.fromisoformat(existing.get("ends_at", "").replace("Z", "+00:00"))
            delta = (ends - datetime.now(timezone.utc)).days
            existing["days_remaining"] = max(0, delta)
            if delta <= 0 and existing.get("state") == "active":
                # Time-based auto-downgrade fallback (scheduler also runs daily)
                existing["state"] = "expired"
                await _db.trial_sessions.update_one(
                    {"email": email}, {"$set": {"state": "expired", "days_remaining": 0}}
                )
                # Section 8 — arm trial-expiry winback (idempotent)
                try:
                    from services.trial_winback import arm_trial_winback
                    await arm_trial_winback(_db, email, tenant_bin)
                except Exception as e:
                    logger.debug(f"[trial] winback arm skipped: {e}")
        except Exception:
            pass
        return existing

    now = datetime.now(timezone.utc)
    doc = {
        "tenant_bin": tenant_bin,
        "email": email,
        "started_at": now.isoformat(),
        "ends_at": (now + timedelta(days=7)).isoformat(),
        "days_remaining": 7,
        "state": "active",
        "scanner_used": 0,
        "scanner_quota": 1,
        "friend_scans_used": 0,
        "friend_scans_quota": 5,
        "ora_msgs_used": 0,
        "ora_msgs_quota": 50,
        "free_reel_generated": False,
        "downgrades_to": "forever_free",
        "drip_sent": {},
    }
    await _db.trial_sessions.insert_one(doc)
    doc.pop("_id", None)
    logger.info(f"[trial] Activated for {email} (BIN {tenant_bin}) — 7 days")
    return doc


@router.post("/api/trial/activate")
async def trial_activate(user: dict = Depends(_verify_platform_user)):
    """Create trial on signup. Idempotent."""
    trial = await _ensure_trial(user.get("bin", ""), user.get("email", ""))
    return {"ok": True, "trial": trial}


@router.get("/api/trial/status")
async def trial_status(user: dict = Depends(_verify_platform_user)):
    """Frontend polls this to render trial meter."""
    trial = await _ensure_trial(user.get("bin", ""), user.get("email", ""))
    return {"trial": trial}


# ═════ Friend Scanner (Viral Growth) ═════

class FriendScanRequest(BaseModel):
    friend_website: str = Field(..., max_length=300)
    friend_email: Optional[str] = None
    friend_name: Optional[str] = None
    share_via: Optional[str] = None  # whatsapp | email | copy


@router.post("/api/customer/friend-scan")
async def friend_scan(body: FriendScanRequest, user: dict = Depends(_verify_platform_user)):
    """
    Scan a friend's website. Rate-limited:
      - Trial: 5/week
      - Paid customers: unlimited
    Generates a referral slug → friend clicks → /report/{slug} → MUST signup to view.
    """
    email = user.get("email", "")
    bin_id = user.get("bin", "")

    trial = await _ensure_trial(bin_id, email)

    # Check if customer has any paid services (unlimited scan) or is in trial (5/week cap)
    has_paid = await _db.customer_subscriptions.count_documents({"email": email, "status": "active"})
    if has_paid == 0:
        # Trial user — enforce 5/week cap
        if trial.get("state") != "active":
            raise HTTPException(403, "Trial expired. Subscribe to any service for unlimited scans.")
        if trial.get("friend_scans_used", 0) >= trial.get("friend_scans_quota", 5):
            raise HTTPException(429, "Friend scan limit reached (5/week). Subscribe for unlimited.")

    # Generate referral slug
    slug = f"ref_{hashlib.sha256(f'{email}{body.friend_website}{uuid.uuid4().hex}'.encode()).hexdigest()[:10]}"
    now = datetime.now(timezone.utc).isoformat()

    # Generate hardcoded scan result (deterministic per URL so repeat views stable)
    h = hashlib.sha256(body.friend_website.lower().encode()).hexdigest()
    score = 40 + (int(h[:2], 16) % 20)   # 40-59 range — always shows issues
    issues_count = 18 + (int(h[2:4], 16) % 10)  # 18-27 issues

    doc = {
        "scan_id": f"fscan_{uuid.uuid4().hex[:12]}",
        "referral_slug": slug,
        "scanner_email": email,
        "scanner_bin": bin_id,
        "friend_website": body.friend_website,
        "friend_email": body.friend_email,
        "friend_name": body.friend_name,
        "share_via": body.share_via,
        "score": score,
        "issues_count": issues_count,
        "created_at": now,
        "clicks": 0,
        "signups": 0,
        "converted_to_paid": False,
        "reward_credited": False,
    }
    await _db.friend_scans.insert_one(doc)

    # Bump trial quota
    if has_paid == 0:
        await _db.trial_sessions.update_one(
            {"email": email}, {"$inc": {"friend_scans_used": 1}}
        )

    doc.pop("_id", None)
    share_url = f"/report/{slug}"
    return {"ok": True, "scan": doc, "share_url": share_url, "referral_slug": slug}


@router.get("/api/customer/friend-scans")
async def my_friend_scans(user: dict = Depends(_verify_platform_user)):
    """List all friend scans + their conversion status."""
    rows = await _db.friend_scans.find({"scanner_email": user.get("email", "")}, {"_id": 0})\
        .sort("created_at", -1).to_list(length=50)
    total_clicks = sum(r.get("clicks", 0) for r in rows)
    signups = sum(1 for r in rows if r.get("signups", 0) > 0)
    converted = sum(1 for r in rows if r.get("converted_to_paid"))
    credit = converted * 20  # $20 per paid friend
    return {
        "scans": rows,
        "total": len(rows),
        "total_clicks": total_clicks,
        "signups": signups,
        "converted": converted,
        "credit_earned_cad": credit,
    }


# ═════ Signup-Gated Public Report ═════

@router.get("/api/public/report/{slug}")
async def public_report(slug: str, request: Request):
    """
    SIGNUP-GATED report page.
    - No token → returns 401 + lightweight metadata (friend_name/website) for signup modal
    - Valid token → returns full report (hardcoded score/issues, locked until subscription)
    """
    if _db is None:
        raise HTTPException(503, "db not ready")

    scan = await _db.friend_scans.find_one({"referral_slug": slug}, {"_id": 0})
    if not scan:
        raise HTTPException(404, "report not found")

    # Track click
    await _db.friend_scans.update_one({"referral_slug": slug}, {"$inc": {"clicks": 1}})

    # Check if requester is signed in
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        # Return signup-gated preview
        return {
            "locked": True,
            "requires_signup": True,
            "preview": {
                "friend_name": scan.get("friend_name"),
                "friend_website": scan.get("friend_website"),
                "score_preview": "45",  # Tease a number but don't reveal full
                "issues_preview": f"{scan.get('issues_count', 20)} issues found",
            },
            "cta": "Sign up for a free AUREM account to view the full report and get 7 days of repair access free.",
        }

    # Verify token
    try:
        user = _decode_jwt(request)
        email = (user.get("email") or "").lower()
    except Exception:
        raise HTTPException(401, "invalid token")

    # Mark signup if this is first time this viewer signed up
    viewer = await _db.platform_users.find_one({"email": email}, {"_id": 0})
    if viewer and scan.get("scanner_email") != email:
        # Bump signup counter (only once per viewer-slug pair)
        viewed = await _db.friend_scan_views.find_one({"slug": slug, "viewer": email})
        if not viewed:
            await _db.friend_scan_views.insert_one({
                "slug": slug, "viewer": email, "at": datetime.now(timezone.utc).isoformat()
            })
            await _db.friend_scans.update_one({"referral_slug": slug}, {"$inc": {"signups": 1}})

    # Return hardcoded report (locked until subscription)
    # Check if viewer has any active paid service → unlock
    has_paid = await _db.customer_subscriptions.count_documents(
        {"email": email, "status": "active"}
    ) if email else 0

    return {
        "locked": has_paid == 0,
        "unlocked_service_needed": "website_repair",
        "scan": {
            "friend_website": scan.get("friend_website"),
            "friend_name": scan.get("friend_name"),
            "score": scan.get("score"),
            "issues_count": scan.get("issues_count"),
            "created_at": scan.get("created_at"),
        },
        "hardcoded_notice": "This is a fixed snapshot. Results don't change until you subscribe for live monitoring.",
    }


# ═════ Pixel Install UX (4 methods) ═════

@router.get("/api/customer/pixel/install")
async def pixel_install_options(user: dict = Depends(_verify_platform_user)):
    """Returns 4 install methods + progress gauge."""
    email = user.get("email", "")
    bin_id = user.get("bin", "")

    # Event count to gauge installation progress
    evt_count = 0
    try:
        evt_count = await _db.pixel_events.count_documents({
            "$or": [{"tenant_id": bin_id}, {"email": email}]
        })
    except Exception:
        pass

    # Pull current API key snippet from api_keys collection (existing system)
    api_key_doc = await _db.api_keys.find_one(
        {"tenant_id": bin_id}, {"_id": 0, "api_key": 1}
    )
    api_key = (api_key_doc or {}).get("api_key", "")
    base = os.environ.get("PIXEL_BASE_URL", "https://aurem.live")
    snippet = f'<script src="{base}/api/pixel/aurem-pixel.js" data-aurem-key="{api_key}" defer></script>' if api_key else ""

    # Progress gauge
    if evt_count >= 100:
        progress_step, progress_label = 4, "Active — collecting rich analytics"
    elif evt_count >= 10:
        progress_step, progress_label = 3, f"Collecting baseline ({evt_count}/100)"
    elif evt_count >= 1:
        progress_step, progress_label = 2, "First ping received"
    elif snippet:
        progress_step, progress_label = 1, "Snippet ready — paste on your site"
    else:
        progress_step, progress_label = 0, "Generate API key first"

    return {
        "progress": {"step": progress_step, "label": progress_label, "events_total": evt_count},
        "snippet": snippet,
        "api_key": api_key,
        "methods": [
            {
                "id": "shopify",
                "name": "Shopify (1-click)",
                "description": "Connect your Shopify store → we inject the pixel automatically.",
                "cta": "Connect Shopify Store",
                "endpoint": "/api/customer/pixel/shopify-connect",
                "ready": False,   # Placeholder until OAuth is wired
                "icon": "shopify",
            },
            {
                "id": "wordpress",
                "name": "WordPress Plugin",
                "description": "Download our plugin zip, upload to WordPress, activate. Takes 2 minutes.",
                "cta": "Download Plugin",
                "download_url": f"{base}/static/aurem-pixel.zip",
                "ready": False,   # Placeholder — actual zip to be uploaded to static
                "icon": "wordpress",
            },
            {
                "id": "email_developer",
                "name": "Email to my Developer",
                "description": "We'll email install instructions + snippet to your dev.",
                "cta": "Send to Developer",
                "endpoint": "/api/customer/pixel/email-dev",
                "ready": True,
                "icon": "mail",
            },
            {
                "id": "manual",
                "name": "Manual HTML Snippet",
                "description": "Copy the snippet below, paste before </head> on your site.",
                "cta": "Copy Snippet",
                "snippet": snippet,
                "ready": True,
                "icon": "code",
            },
        ],
    }


class EmailDevRequest(BaseModel):
    developer_email: str
    note: Optional[str] = None


@router.post("/api/customer/pixel/email-dev")
async def email_developer_install(body: EmailDevRequest, user: dict = Depends(_verify_platform_user)):
    """Email install instructions to developer via Resend."""
    # Log request (email delivery via existing email_service — lazy import to avoid loops)
    doc = {
        "email": user.get("email", ""),
        "bin": user.get("bin", ""),
        "developer_email": body.developer_email,
        "note": body.note or "",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "status": "queued",
    }
    await _db.pixel_dev_emails.insert_one(doc)
    try:
        from services.email_service import send_email
        api_key_doc = await _db.api_keys.find_one({"tenant_id": user.get("bin", "")}, {"_id": 0, "api_key": 1})
        api_key = (api_key_doc or {}).get("api_key", "")
        base = os.environ.get("PIXEL_BASE_URL", "https://aurem.live")
        snippet = f'<script src="{base}/api/pixel/aurem-pixel.js" data-aurem-key="{api_key}" defer></script>'
        subject = f"[AUREM] Install instructions for {user.get('business_name') or user.get('bin')}"
        body_html = f"""
        <h3>AUREM Pixel Install</h3>
        <p>Hi developer,</p>
        <p>{user.get('full_name') or user.get('email')} has asked us to send you the AUREM pixel install snippet.</p>
        <p>Paste this before <code>&lt;/head&gt;</code> on every page:</p>
        <pre style='background:#f5f5f5;padding:12px;border-radius:6px;'>{snippet}</pre>
        <p>Note: <em>{body.note or '(none)'}</em></p>
        <p>Questions? Reply to this email.</p>
        """
        await send_email(to=body.developer_email, subject=subject, html=body_html)
        await _db.pixel_dev_emails.update_one(
            {"_id": doc.get("_id")}, {"$set": {"status": "sent"}}
        )
    except Exception as e:
        logger.warning(f"[pixel-email-dev] send failed (logged anyway): {e}")
    return {"ok": True, "queued_to": body.developer_email}


# ═════ /pricing-pro — Hidden Combo Plans ═════

@router.get("/api/pricing-pro")
async def pricing_pro():
    """
    Returns the 3 combo plans (Starter/Growth/Enterprise).
    NOT shown in main frontend. Accessible via direct URL for enterprise customers.
    """
    # Import old PACKAGES dict from stripe router (source of truth)
    try:
        from routers.stripe_payment_router import PACKAGES
        pkgs = [{"id": k, **v} for k, v in PACKAGES.items()]
        return {
            "packages": pkgs,
            "notice": "These combo plans include premium features (voice AI, white-label, HD video, CONSORTIUM, PentAGI) NOT available as individual add-ons.",
            "checkout_endpoint": "/api/payments/checkout",
        }
    except Exception as e:
        logger.warning(f"[pricing-pro] failed to read PACKAGES: {e}")
        return {"packages": [], "error": str(e)}
