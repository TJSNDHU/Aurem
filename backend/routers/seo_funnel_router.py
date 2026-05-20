"""
Free SEO Audit → Paid Auto-Fix Funnel (iter 325c)
==================================================

Public revenue funnel: aurem.live/free-seo-audit

Flow:
  1. Visitor enters website URL on /free-seo-audit
  2. POST /api/public/seo-funnel/scan  → runs the real website audit
     (reuses services.website_audit_service.real_audit). Returns 3–5
     real, prioritised issues + an overall score. Lead is saved to
     `db.leads` and `db.website_repair_reports` (same schema as
     public_repair_router) so sales sees one unified pipeline.
  3. Visitor clicks "Fix These Issues Automatically — $49/month"
  4. POST /api/public/seo-funnel/checkout  → mints an UN-authenticated
     Stripe Checkout Session for the Starter plan (USD $49 recurring,
     pricing-equivalent to the existing AUREM Starter tier defined in
     aurem_routes.SUBSCRIPTION_TIERS). Email & lead_id are stored in
     session metadata so the existing /api/webhook/stripe handler
     auto-provisions the tenant on payment success.
  5. Stripe redirects to /welcome?session_id={CHECKOUT_SESSION_ID}&source=seo-funnel
     which the existing OnboardingWelcome flow already handles.

No auth required — frictionless lead magnet.
Rate limiting handled at the global middleware layer.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, HttpUrl

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public/seo-funnel", tags=["Public SEO Funnel"])

_db = None

# Mirrors the Starter tier defined in aurem_routes.SUBSCRIPTION_TIERS so the
# funnel charges the same price as the in-app plan picker.
STARTER_PRICE_USD = 49.00
STARTER_PLAN_ID = "plan_starter"


def set_db(db):
    global _db
    _db = db


def _get_db():
    return _db


class ScanRequest(BaseModel):
    url: str = Field(..., min_length=4, max_length=400)
    email: Optional[EmailStr] = None  # optional — accept anon scans, capture email at checkout


class CheckoutRequest(BaseModel):
    email: EmailStr
    scan_id: str = Field(..., min_length=8, max_length=64)
    business_name: Optional[str] = Field(None, max_length=200)


# ─── 1. Scan ──────────────────────────────────────────────────────────────────
@router.get("/health")
async def health():
    return {"ok": True, "db_wired": _get_db() is not None}


def _top_issues(audit: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    """Pick the 3–5 most impactful issues from the real_audit output.
    real_audit returns a flat `issues` list — we just take the first N
    (already prioritised by severity in the audit service)."""
    raw = audit.get("issues") or []
    out = []
    for item in raw[:limit]:
        if isinstance(item, dict):
            out.append({
                "title": item.get("title") or item.get("issue") or item.get("name") or "Issue",
                "severity": item.get("severity") or item.get("priority") or "medium",
                "detail": (item.get("detail") or item.get("description") or "")[:240],
                "fix": (item.get("fix") or item.get("recommendation") or "")[:240],
            })
        elif isinstance(item, str):
            out.append({"title": item, "severity": "medium", "detail": "", "fix": ""})
    return out


@router.post("/scan")
async def public_scan(req: ScanRequest, request: Request):
    """Anonymous website audit. Returns score + top 3–5 issues."""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not ready")

    url = (req.url or "").strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        from services.website_audit_service import real_audit
        audit = await real_audit(url)
    except Exception as e:
        logger.warning(f"[seo-funnel/scan] audit failed: {e}")
        raise HTTPException(500, "Scan engine unavailable, please retry shortly")

    if not audit.get("ok"):
        raise HTTPException(400, f"Could not reach {url}, {audit.get('error', 'unknown')}")

    scan_id = str(uuid.uuid4())
    issues = _top_issues(audit, limit=5)
    score = audit.get("overall_score") or 0
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:200]

    # Persist (single source of truth — same schema as public_repair_router so
    # ORA + admin dashboard see one unified lead stream)
    lead_doc = {
        "lead_id": scan_id,
        "source": "seo_funnel",
        "email": req.email,
        "business_name": url,
        "url": audit.get("url", url),
        "score": score,
        "issues_count": len(audit.get("issues") or []),
        "stage": "scanned",
        "ip": ip,
        "user_agent": ua,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db.leads.insert_one(lead_doc)
    except Exception as e:
        logger.debug(f"[seo-funnel/scan] lead save skipped: {e}")
    lead_doc.pop("_id", None)

    # Mirror into website_repair_reports so the checkout step can look it up.
    try:
        await db.website_repair_reports.insert_one({
            "report_id": scan_id,
            "url": audit.get("url", url),
            "audit": audit,
            "overall_score": score,
            "issues": issues,
            "contact_email": req.email,
            "status": "seo_funnel_scan",
            "created_by": "public:seo-funnel",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "lead_source": "seo_funnel",
            "lead_id": scan_id,
        })
    except Exception as e:
        logger.debug(f"[seo-funnel/scan] report mirror failed: {e}")

    return {
        "ok": True,
        "scan_id": scan_id,
        "url": audit.get("url", url),
        "overall_score": score,
        "issues": issues,
        "summary": (
            f"We found {len(issues)} issue(s) on your site that are likely "
            f"costing you traffic and conversions. Our auto-fix engine can "
            f"resolve them automatically."
        ),
        "plan": {
            "id": STARTER_PLAN_ID,
            "name": "AUREM Starter",
            "price_usd": STARTER_PRICE_USD,
            "cta": f"Fix These Issues Automatically — ${int(STARTER_PRICE_USD)}/month",
        },
    }


# ─── 2. Checkout ──────────────────────────────────────────────────────────────
@router.post("/checkout")
async def public_checkout(req: CheckoutRequest, request: Request):
    """Anonymous Stripe Checkout session for AUREM Starter ($49/mo).
    Email + scan_id are persisted in session metadata so the existing
    /api/webhook/stripe handler can provision the tenant on `paid`."""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not ready")

    # Resolve scan -> bind email to the lead row.
    scan_doc = await db.website_repair_reports.find_one({"report_id": req.scan_id}, {"_id": 0})
    if not scan_doc:
        raise HTTPException(404, "Scan not found, please re-run the scan")

    try:
        from emergentintegrations.payments.stripe.checkout import (
            StripeCheckout, CheckoutSessionRequest,
        )
    except ImportError:
        raise HTTPException(500, "Payment integration not installed")

    # Stripe key — prefer channel_config helper, fall back to env.
    stripe_key = None
    try:
        from services.channel_config import get_stripe_api_key
        stripe_key = get_stripe_api_key()
    except Exception:
        pass
    if not stripe_key:
        stripe_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
    if not stripe_key:
        raise HTTPException(500, "Payment not configured")

    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_key, webhook_url=webhook_url)

    checkout_request = CheckoutSessionRequest(
        amount=STARTER_PRICE_USD,
        currency="usd",
        success_url=f"{host_url}/welcome?session_id={{CHECKOUT_SESSION_ID}}&source=seo-funnel",
        cancel_url=f"{host_url}/free-seo-audit?status=cancelled&scan_id={req.scan_id}",
        metadata={
            "source": "seo_funnel",
            "scan_id": req.scan_id,
            "plan_id": STARTER_PLAN_ID,
            "tier": "starter",
            "user_email": req.email,
            "business_name": (req.business_name or scan_doc.get("url") or "")[:120],
        },
    )

    try:
        session = await stripe_checkout.create_checkout_session(checkout_request)
    except Exception as e:
        logger.error(f"[seo-funnel/checkout] stripe error: {e}")
        raise HTTPException(502, "Stripe is unavailable, please retry")

    # Update lead row + persist transaction (idempotent insert by session_id).
    try:
        await db.leads.update_one(
            {"lead_id": req.scan_id},
            {"$set": {
                "email": req.email,
                "business_name": req.business_name,
                "stage": "checkout_started",
                "stripe_session_id": session.session_id,
                "checkout_started_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[seo-funnel/checkout] lead update skipped: {e}")

    try:
        await db.payment_transactions.insert_one({
            "session_id": session.session_id,
            "source": "seo_funnel",
            "scan_id": req.scan_id,
            "user_email": req.email,
            "tier": "starter",
            "amount": STARTER_PRICE_USD,
            "currency": "usd",
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.debug(f"[seo-funnel/checkout] tx insert skipped: {e}")

    return {
        "ok": True,
        "checkout_url": session.url,
        "session_id": session.session_id,
    }
