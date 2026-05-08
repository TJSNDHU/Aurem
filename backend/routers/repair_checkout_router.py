"""
Repair Checkout + Job Trigger (iter 315d cleanup)
==================================================
Public unauth endpoints used by the Repair Report page.

Flow:
  Customer clicks $149 / $299 → /api/repair/checkout?slug=...&tier=basic|full
    → creates Stripe Checkout Session (price_data inline, CAD)
    → 302 redirect to session.url
  After successful payment, the live-mode Stripe webhook (configured at
  /api/payments/webhook/stripe in stripe_payment_router.py) detects
  metadata.product == "website_repair" and:
    - marks the repair_orders row as paid
    - calls _kick_repair_build(order) defined below to fire AWB build

Schema:
  db.repair_orders {order_id, slug, lead_id, scan_id, tier, amount_cad,
                    status, stripe_session_id, paid_at, build_site_id,
                    created_at}
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/repair", tags=["Website Repair Checkout"])

PUBLIC_BASE = os.environ.get("AUREM_PUBLIC_BASE", "https://aurem.live")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_REPAIR_WEBHOOK_SECRET", "")

TIERS = {
    "basic": {"label": "Repair Basic", "amount_cad": 14900, "mode": "repair"},
    "full":  {"label": "Repair Full",  "amount_cad": 29900, "mode": "rebuild"},
}

DOMAIN_ADDON_AMOUNT_CAD = int(float(
    os.environ.get("AUREM_DOMAIN_PRICE_CAD", "29")) * 100)

_db = None


def set_db(db):
    global _db
    _db = db


@router.get("/checkout")
async def repair_checkout(slug: str = Query(...), tier: str = Query("basic"),
                            domain: Optional[str] = Query(None),
                            domain_addon: bool = Query(False)):
    """Create a Stripe Checkout session for a repair tier and redirect.

    Optional domain add-on: ?domain_addon=true&domain=example.com adds a
    $29 CAD/yr line item; on payment success a Namecheap registration is
    auto-fired (silently no-op if Namecheap not configured)."""
    if _db is None:
        raise HTTPException(503, "db unavailable")
    if tier not in TIERS:
        raise HTTPException(400, f"invalid_tier (allowed: {list(TIERS)})")
    tier_def = TIERS[tier]
    domain = (domain or "").strip().lower()
    addon = bool(domain_addon and domain)

    audit = await _db.customer_scans.find_one({"public_slug": slug}, {"_id": 0})
    if not audit:
        raise HTTPException(404, "report not found")
    lead_id = audit.get("lead_id")

    order_id = f"ord_{uuid.uuid4().hex[:14]}"
    success_url = f"{PUBLIC_BASE}/api/repair/success?order_id={order_id}"
    cancel_url = f"{PUBLIC_BASE}/api/repair-report/{slug}"

    total_cad = tier_def["amount_cad"] + (DOMAIN_ADDON_AMOUNT_CAD if addon else 0)

    if not STRIPE_SECRET_KEY:
        # Stub mode — record the order, send to a friendly fallback page so
        # we don't 500 customers when Stripe isn't wired in this env.
        await _db.repair_orders.insert_one({
            "order_id": order_id, "slug": slug, "lead_id": lead_id,
            "scan_id": audit.get("scan_id"), "tier": tier,
            "amount_cad": total_cad, "build_mode": tier_def["mode"],
            "domain_addon": addon, "domain_name": domain if addon else None,
            "status": "stripe_unconfigured",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return RedirectResponse(
            f"{PUBLIC_BASE}/api/repair/manual-checkout?order_id={order_id}",
            status_code=302,
        )

    line_items = [{
        "price_data": {
            "currency": "cad",
            "product_data": {
                "name": f"AUREM {tier_def['label']} — {audit.get('website') or 'website repair'}",
                "description": f"Score before: {audit.get('overall_score')}/100",
            },
            "unit_amount": tier_def["amount_cad"],
        },
        "quantity": 1,
    }]
    if addon:
        line_items.append({
            "price_data": {
                "currency": "cad",
                "product_data": {
                    "name": f"Custom domain — {domain}",
                    "description": "1-year registration · auto DNS · WHOIS privacy",
                },
                "unit_amount": DOMAIN_ADDON_AMOUNT_CAD,
            },
            "quantity": 1,
        })

    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=line_items,
            metadata={
                "product": "website_repair", "tier": tier, "slug": slug,
                "order_id": order_id, "lead_id": lead_id or "",
                "scan_id": audit.get("scan_id") or "",
                "domain_addon": "1" if addon else "0",
                "domain_name": domain if addon else "",
            },
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except Exception as e:
        logger.warning(f"[repair-checkout] stripe failed: {e}")
        raise HTTPException(502, f"stripe_error: {type(e).__name__}")

    await _db.repair_orders.insert_one({
        "order_id": order_id, "slug": slug, "lead_id": lead_id,
        "scan_id": audit.get("scan_id"), "tier": tier,
        "amount_cad": total_cad, "build_mode": tier_def["mode"],
        "domain_addon": addon, "domain_name": domain if addon else None,
        "status": "pending_payment",
        "stripe_session_id": session["id"],
        "stripe_url": session.get("url"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return RedirectResponse(session["url"], status_code=302)


@router.get("/success")
async def repair_success(order_id: str = Query(...)):
    if _db is None:
        raise HTTPException(503, "db unavailable")
    order = await _db.repair_orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "order not found")
    return JSONResponse({
        "ok": True, "order": order,
        "message": "Payment received. Repair build queued — your site will be live within 24-48h.",
    })


@router.get("/manual-checkout")
async def manual_checkout(order_id: str = Query(...)):
    """Fallback when Stripe isn't configured in this env."""
    return JSONResponse({
        "ok": True, "order_id": order_id,
        "message": "Stripe is not configured in this environment. Order recorded; "
                   "the AUREM team will contact you to complete payment.",
    })


# NOTE: /webhook removed (iter 315d) — dead code. The configured Stripe
# webhook in the live dashboard targets /api/payments/webhook/stripe
# (handled by stripe_payment_router.py), which already detects
# metadata.product == "website_repair" and triggers _kick_repair_build.


async def _kick_repair_build(order: Dict[str, Any]) -> None:
    try:
        from services.auto_website_builder import build_site_for_lead
        lead_id = order.get("lead_id")
        if not lead_id:
            return
        scan = await _db.customer_scans.find_one(
            {"scan_id": order.get("scan_id")}, {"_id": 0, "website": 1}
        ) or {}
        result = await build_site_for_lead(
            _db, lead_id,
            mode="repair",   # both basic & full feed mode=repair; "full" tier
            original_url=scan.get("website"),
            audit_id=order.get("scan_id"),
        )
        await _db.repair_orders.update_one(
            {"order_id": order["order_id"]},
            {"$set": {"build_site_id": result.get("site_id"),
                      "build_status": result.get("status") or ("ok" if result.get("ok") else "failed"),
                      "built_at": datetime.now(timezone.utc).isoformat()}},
        )
    except Exception as e:
        logger.exception(f"[repair-webhook] build kick failed: {e}")


async def _kick_domain_register(order: Dict[str, Any]) -> None:
    """Auto-register the customer's custom domain post-payment.
    Silently no-ops if Namecheap not configured; logs progress to the
    repair_orders document."""
    domain = (order.get("domain_name") or "").strip().lower()
    lead_id = order.get("lead_id") or ""
    if not domain or not lead_id:
        return
    try:
        from services.domain_reseller import (
            register_domain, configure_dns_to_aurem,
        )
        # Look up the slug from the AWB build (if already created)
        slug = order.get("slug")
        site_row = await _db.auto_built_sites.find_one(
            {"lead_id": lead_id}, {"_id": 0, "slug": 1},
            sort=[("built_at", -1)],
        ) or {}
        site_slug = site_row.get("slug") or slug
        # Try to grab the lead's contact info as registrant
        lead = await _db.campaign_leads.find_one(
            {"id": lead_id}, {"_id": 0, "phone": 1, "email": 1,
                                "business_name": 1, "city": 1},
        ) or {}
        registrant = {
            "first_name": (lead.get("business_name") or "AUREM")[:30],
            "last_name": "Customer",
            "phone": lead.get("phone") or "+1.4168869408",
            "email": lead.get("email") or "ora@aurem.live",
            "city": lead.get("city") or "Mississauga",
        }
        reg = await register_domain(_db, domain, lead_id, years=1,
                                       registrant=registrant)
        dns = None
        if reg.get("ok") and site_slug:
            dns = await configure_dns_to_aurem(domain, site_slug)
        await _db.repair_orders.update_one(
            {"order_id": order["order_id"]},
            {"$set": {
                "domain_register_result": reg,
                "domain_dns_result": dns,
                "domain_processed_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
    except Exception as e:
        logger.exception(f"[repair-webhook] domain register failed: {e}")
        try:
            await _db.repair_orders.update_one(
                {"order_id": order["order_id"]},
                {"$set": {"domain_register_error": str(e)[:240]}},
            )
        except Exception:
            pass


# Manual admin-trigger (bypass payment in test envs)
@router.post("/admin/start")
async def admin_start_repair(request: Request):
    if _db is None:
        raise HTTPException(503, "db unavailable")
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "auth required")
    secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise HTTPException(500, "jwt secret unset")
    try:
        import jwt as pyjwt
        p = pyjwt.decode(auth.split(" ", 1)[1], secret,
                         algorithms=["HS256"], options={"verify_exp": False})
    except Exception as e:
        raise HTTPException(401, f"invalid token: {e}")
    if not (p.get("is_admin") or p.get("is_super_admin")
            or p.get("role") in ("admin", "super_admin")):
        raise HTTPException(403, "admin only")

    body = await request.json()
    slug = body.get("slug")
    tier = body.get("tier", "basic")
    if tier not in TIERS:
        raise HTTPException(400, "invalid_tier")
    audit = await _db.customer_scans.find_one({"public_slug": slug}, {"_id": 0})
    if not audit:
        raise HTTPException(404, "scan_not_found")
    order_id = f"ord_{uuid.uuid4().hex[:14]}"
    order = {
        "order_id": order_id, "slug": slug, "lead_id": audit.get("lead_id"),
        "scan_id": audit.get("scan_id"), "tier": tier,
        "amount_cad": TIERS[tier]["amount_cad"], "build_mode": TIERS[tier]["mode"],
        "status": "admin_triggered",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.repair_orders.insert_one(order)
    import asyncio
    asyncio.create_task(_kick_repair_build(order))
    return {"ok": True, "order_id": order_id, "build_queued": True}
