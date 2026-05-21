"""
Stripe Payment Router — AUREM SaaS Subscription Payments
=========================================================
Handles checkout sessions, payment status polling, webhooks,
and plan activation for AUREM's 3-tier pricing (CAD).
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["Payments"])

_db = None


def set_db(database):
    global _db
    _db = database


# ═══════════════════════════════════════════════════
# FIXED PACKAGES — server-side only, never trust frontend amounts
# All prices in CAD (Canadian Dollars)
# ═══════════════════════════════════════════════════

PACKAGES = {
    "starter": {
        "name": "Starter",
        "amount": 97.00,
        "currency": "cad",
        "billing": "monthly",
        "stripe_price_id": os.environ.get("STRIPE_PRICE_STARTER", ""),
        "actions_limit": 500,
        "pipeline_runs_limit": 3,
        "features": [
            "500 AI actions/month",
            "Lead scoring + follow-up",
            "Invoice automation",
            "Morning Brief",
            "Website repair",
            "ORA chat assistant",
        ],
    },
    "growth": {
        "name": "Growth",
        "amount": 297.00,
        "currency": "cad",
        "billing": "monthly",
        "stripe_price_id": os.environ.get("STRIPE_PRICE_GROWTH", ""),
        "actions_limit": 5000,
        "pipeline_runs_limit": 10,
        "features": [
            "5,000 AI actions/month",
            "ORA voice AI",
            "Economic Intelligence",
            "3 workspaces",
            "Partner referral access",
            "Video generation (480p, 10/month)",
        ],
    },
    "enterprise": {
        "name": "Enterprise",
        "amount": 997.00,
        "currency": "cad",
        "billing": "monthly",
        "stripe_price_id": os.environ.get("STRIPE_PRICE_ENTERPRISE", ""),
        "actions_limit": 999999,
        "pipeline_runs_limit": 999,
        "features": [
            "Unlimited actions",
            "White-label",
            "25 concurrent voice",
            "Dedicated onboarding",
            "HD Video generation (unlimited)",
            "CONSORTIUM multi-model AI",
            "PentAGI security pentest",
            "ORA Avatar lip sync",
        ],
    },
}


# ═══════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════

class CheckoutRequest(BaseModel):
    package_id: str
    origin_url: str
    ref: Optional[str] = None  # business_slug from /report/{slug} page for attribution


class CheckoutStatusRequest(BaseModel):
    session_id: str


# ═══════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════

def _get_stripe_key():
    """Return the configured Stripe secret key."""
    return os.environ.get("STRIPE_SECRET_KEY") or ""


def _get_user_from_request(request: Request) -> dict:
    import jwt
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return {}
    try:
        payload = jwt.decode(auth.split(" ", 1)[1], (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured"))), algorithms=["HS256"])
        return payload
    except Exception:
        return {}


# ═══════════════════════════════════════════════════
# STRIPE CONNECTION TEST
# ═══════════════════════════════════════════════════

@router.get("/stripe-status")
async def stripe_status():
    """Test Stripe API connection."""
    api_key = _get_stripe_key()
    if not api_key:
        return {"connected": False, "error": "No Stripe API key configured"}

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.stripe.com/v1/balance",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                available = data.get("available", [{}])
                amount = available[0].get("amount", 0) / 100 if available else 0
                currency = available[0].get("currency", "cad") if available else "cad"
                return {
                    "connected": True,
                    "mode": "test" if "test" in api_key else "live",
                    "balance": f"${amount:.2f} {currency.upper()}",
                }
            else:
                return {"connected": False, "error": f"Stripe returned {resp.status_code}"}
    except Exception as e:
        return {"connected": False, "error": str(e)}


# ═══════════════════════════════════════════════════
# PACKAGES
# ═══════════════════════════════════════════════════

@router.get("/packages")
async def list_packages():
    """List available subscription packages."""
    return {
        "packages": [
            {"id": k, **{kk: vv for kk, vv in v.items()}}
            for k, v in PACKAGES.items()
        ]
    }


# ═══════════════════════════════════════════════════
# CHECKOUT SESSION
# ═══════════════════════════════════════════════════

@router.post("/checkout")
async def create_checkout(body: CheckoutRequest, request: Request):
    """Create a Stripe Checkout session for a subscription."""
    if body.package_id not in PACKAGES:
        raise HTTPException(400, f"Invalid package: {body.package_id}. Available: {list(PACKAGES.keys())}")

    package = PACKAGES[body.package_id]
    api_key = _get_stripe_key()
    if not api_key:
        raise HTTPException(500, "Stripe API key not configured")

    user = _get_user_from_request(request)
    user_email = user.get("email", user.get("user_id", ""))

    # Pull business context from campaign_leads if this came from a public report page
    ref_slug = (getattr(body, "ref", None) or "").strip()
    if ref_slug and _db is not None:
        lead = await _db.campaign_leads.find_one({"lead_id": ref_slug}, {"_id": 0})
        if lead:
            if not user_email:
                user_email = lead.get("email", "")

    origin = body.origin_url.rstrip("/")
    success_url = f"{origin}/welcome?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/report/{ref_slug}" if ref_slug else f"{origin}/pricing?payment=cancelled"

    price_id = package.get("stripe_price_id", "")

    try:
        import stripe as stripe_lib
        stripe_lib.api_key = api_key

        # Use Stripe Price ID for proper recurring subscription
        if price_id:
            session_params = {
                "mode": "subscription",
                "line_items": [{"price": price_id, "quantity": 1}],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "allow_promotion_codes": True,
                "subscription_data": {
                    "trial_period_days": 7,
                    "metadata": {
                        "package_id": body.package_id,
                        "ref": ref_slug,
                    },
                },
                "metadata": {
                    "package_id": body.package_id,
                    "package_name": package["name"],
                    "user_email": user_email,
                    "ref": ref_slug,
                    "source": "aurem_saas",
                },
            }
            if user_email:
                session_params["customer_email"] = user_email

            session = stripe_lib.checkout.Session.create(**session_params)

            # Record transaction
            if _db is not None:
                await _db.payment_transactions.insert_one({
                    "session_id": session.id,
                    "package_id": body.package_id,
                    "package_name": package["name"],
                    "amount": package["amount"],
                    "currency": package["currency"],
                    "user_email": user_email,
                    "ref": ref_slug,
                    "payment_status": "initiated",
                    "mode": "subscription",
                    "plan_activated": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })

            logger.info(f"[Stripe] Subscription checkout: {session.id} for {body.package_id} (${package['amount']} CAD/mo)")
            return {"url": session.url, "session_id": session.id}

        # Fallback: emergentintegrations one-time checkout
        from emergentintegrations.payments.stripe.checkout import (
            StripeCheckout, CheckoutSessionRequest, CheckoutSessionResponse
        )

        host_url = str(request.base_url)
        webhook_url = f"{host_url}api/payments/webhook/stripe"
        stripe_checkout = StripeCheckout(api_key=api_key, webhook_url=webhook_url)

        checkout_req = CheckoutSessionRequest(
            amount=package["amount"],
            currency=package["currency"],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "package_id": body.package_id,
                "package_name": package["name"],
                "user_email": user_email,
                "amount_cad": str(package["amount"]),
                "source": "aurem_saas",
            }
        )

        session: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(checkout_req)

        if _db is not None:
            await _db.payment_transactions.insert_one({
                "session_id": session.session_id,
                "package_id": body.package_id,
                "package_name": package["name"],
                "amount": package["amount"],
                "currency": package["currency"],
                "user_email": user_email,
                "payment_status": "initiated",
                "mode": "one_time",
                "plan_activated": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        logger.info(f"[Stripe] Checkout created: {session.session_id} for {body.package_id} (${package['amount']} CAD)")
        return {"url": session.url, "session_id": session.session_id}

    except ImportError:
        raise HTTPException(500, "Stripe integration library not available")
    except Exception as e:
        logger.error(f"[Stripe] Checkout error: {e}")
        raise HTTPException(500, f"Payment error: {str(e)}")


# ═══════════════════════════════════════════════════
# CHECKOUT STATUS (poll from frontend)
# ═══════════════════════════════════════════════════

@router.get("/checkout/status/{session_id}")
async def get_checkout_status(session_id: str, request: Request):
    """Get status of a Stripe checkout session and activate plan if paid."""
    api_key = _get_stripe_key()
    if not api_key:
        raise HTTPException(500, "Stripe API key not configured")

    try:
        import stripe as stripe_lib
        stripe_lib.api_key = api_key

        session = stripe_lib.checkout.Session.retrieve(session_id)
        payment_status = session.payment_status or "unpaid"
        status = session.status or "open"

        # Update transaction and activate plan
        if _db is not None:
            existing = await _db.payment_transactions.find_one(
                {"session_id": session_id}, {"_id": 0}
            )

            if existing:
                update = {
                    "payment_status": payment_status,
                    "status": status,
                    "stripe_subscription_id": session.subscription,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }

                if payment_status == "paid" and not existing.get("plan_activated"):
                    update["plan_activated"] = True
                    await _activate_plan(existing)

                await _db.payment_transactions.update_one(
                    {"session_id": session_id},
                    {"$set": update}
                )

        return {
            "status": status,
            "payment_status": payment_status,
            "amount_total": session.amount_total,
            "currency": session.currency,
            "subscription_id": session.subscription,
            "metadata": dict(session.metadata) if session.metadata else {},
        }

    except Exception as e:
        logger.error(f"[Stripe] Status check error: {e}")
        raise HTTPException(500, f"Status check error: {str(e)}")


async def _activate_plan(transaction: dict):
    """Activate or upgrade a customer's plan after successful payment."""
    if _db is None:
        return

    package_id = transaction.get("package_id", "starter")
    user_email = transaction.get("user_email", "")
    package = PACKAGES.get(package_id, PACKAGES["starter"])
    now = datetime.now(timezone.utc).isoformat()

    logger.info(f"[Stripe] Activating {package_id} plan for {user_email}")

    # Find existing tenant_customer by email
    customer = await _db.tenant_customers.find_one({"email": user_email})

    if customer:
        # Upgrade existing customer
        await _db.tenant_customers.update_one(
            {"email": user_email},
            {"$set": {
                "plan": package_id,
                "plan_price_cad": package["amount"],
                "plan_started": now,
                "plan_ends": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                "plan_status": "active",
                "usage.actions_limit": package["actions_limit"],
                "usage.actions_remaining": package["actions_limit"],
                "usage.pipeline_runs_limit": package["pipeline_runs_limit"],
                "last_active": now,
            }}
        )
        # Audit log
        await _db.customer_audit_log.insert_one({
            "tenant_id": customer.get("tenant_id"),
            "changed_by": "stripe",
            "changed_at": now,
            "field": "plan",
            "old_value": customer.get("plan", "none"),
            "new_value": package_id,
        })
    else:
        # Create new customer from Stripe payment
        import secrets
        tenant_id = user_email.split("@")[0][:20].lower().replace(" ", "-") + "-" + secrets.token_hex(4)
        business_id = "CUST-" + secrets.token_hex(2).upper()

        await _db.tenant_customers.insert_one({
            "tenant_id": tenant_id,
            "business_id": business_id,
            "full_name": "",
            "company_name": "",
            "email": user_email,
            "phone": "",
            "website_url": "",
            "industry": "",
            "category": "",
            "sub_category": "",
            "plan": package_id,
            "plan_price_cad": package["amount"],
            "plan_started": now,
            "plan_ends": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "plan_status": "active",
            "billing_cycle": "monthly",
            "usage": {
                "actions_limit": package["actions_limit"],
                "actions_used": 0,
                "actions_remaining": package["actions_limit"],
                "pipeline_runs_today": 0,
                "pipeline_runs_limit": package["pipeline_runs_limit"],
                "last_reset_date": now,
                "reset_cycle": "daily",
            },
            "performance": {
                "website_score": 0, "last_scan_date": None, "total_scans": 0,
                "leads_found": 0, "leads_converted": 0, "invoices_sent": 0,
                "invoices_paid": 0, "revenue_tracked": 0, "automations_run": 0,
                "issues_fixed": 0,
            },
            "company_address": {},
            "joined_date": now,
            "last_active": now,
            "created_by": "stripe_checkout",
            "notes": f"Created from Stripe payment — {package['name']} plan",
            "is_active": True,
            "is_self_client": False,
        })

    logger.info(f"[Stripe] Plan {package_id} activated for {user_email}")

    # CRITICAL: Also update workspaces + aurem_workspaces (used by video/consortium/pentest tier gates)
    tier_update = {"tier": package_id, "plan": package_id, "plan_updated_at": now}
    if customer:
        tid = customer.get("tenant_id", "")
        if tid:
            await _db.workspaces.update_one({"tenant_id": tid}, {"$set": tier_update}, upsert=True)
            await _db.aurem_workspaces.update_one({"tenant_id": tid}, {"$set": tier_update}, upsert=True)
    # Also update the default workspace
    await _db.workspaces.update_one({"tenant_id": "aurem_platform"}, {"$set": tier_update}, upsert=True)
    await _db.aurem_workspaces.update_one({"tenant_id": "aurem_platform"}, {"$set": tier_update}, upsert=True)
    logger.info(f"[Stripe] Workspace tier synced to {package_id}")

    # ═══ ONBOARDING: WhatsApp Notifications ═══
    try:
        from routers.whatsapp_alerts import send_whatsapp
        # 1. Notify admin (Tj) about new payment
        admin_phone = os.environ.get("ADMIN_WHATSAPP", "16134000000")
        admin_msg = (
            f"💰 *New AUREM Payment!*\n\n"
            f"Plan: {package['name']} (${package['amount']} CAD/mo)\n"
            f"Client: {user_email}\n"
            f"Time: {now}\n\n"
            f"Total active subscriptions pending check."
        )
        await send_whatsapp(admin_phone, admin_msg)

        # 2. Send welcome message to client (if phone available)
        client_phone = ""
        if customer:
            client_phone = customer.get("phone", "")
        if client_phone:
            welcome = (
                f"Welcome to AUREM {package['name']}! 🚀\n\n"
                f"Your {package['name']} plan is now active.\n"
                f"Access your dashboard: https://live-support-3.emergent.host/dashboard\n\n"
                f"Need help? Reply here or email support@aurem.live"
            )
            await send_whatsapp(client_phone, welcome)

        logger.info(f"[Stripe] Onboarding notifications sent for {user_email}")
    except Exception as notif_err:
        logger.debug(f"[Stripe] Notification send failed (non-critical): {notif_err}")

    # ═══ NEW: Full Post-Payment Onboarding (welcome + tenant tasks + admin SMS alert) ═══
    try:
        from services.aurem_post_payment_onboarding import run_post_payment_flow
        # Recompute tenant_id for the newly created (or updated) customer
        cust = await _db.tenant_customers.find_one({"email": user_email}, {"_id": 0})
        tenant_id = (cust or {}).get("tenant_id") or user_email.replace("@", "-")
        ref_slug = transaction.get("ref", "") or ""
        summary = await run_post_payment_flow(
            _db,
            tenant_id=tenant_id,
            customer_email=user_email,
            plan=package_id,
            amount=float(package["amount"]),
            lead_ref=ref_slug,
        )
        logger.info(f"[Stripe] Post-payment flow: {summary['steps']}")
    except Exception as e:
        logger.warning(f"[Stripe] Post-payment onboarding failed (non-critical): {e}")


# ═══════════════════════════════════════════════════
# WEBHOOK
# ═══════════════════════════════════════════════════

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events for subscriptions and payments.

    Signature verification supports multiple secrets (comma-separated
    STRIPE_WEBHOOK_SECRET) so live + test endpoints, or rotation, both work.
    """
    api_key = _get_stripe_key()
    if not api_key:
        return {"received": True, "error": "Stripe not configured"}

    try:
        import stripe as stripe_lib
        stripe_lib.api_key = api_key
        body = await request.body()
        sig = request.headers.get("Stripe-Signature", "")
        raw_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        # Support comma-separated secrets (rotation / multiple endpoints)
        secrets_list = [s.strip() for s in raw_secret.split(",") if s.strip()]

        # Suppress noise from internal health-check pings (Pillars Map probe)
        is_health_ping = (sig == "t=0,v1=ping") or (b"evt_pillars_map_health_ping" in body[:200])

        event = None
        sig_verified = False
        last_err = None
        if secrets_list and sig and not is_health_ping:
            for secret in secrets_list:
                try:
                    event = stripe_lib.Webhook.construct_event(body, sig, secret)
                    sig_verified = True
                    break
                except Exception as e:
                    last_err = e
            if not sig_verified:
                # Diagnostic info — no secrets leaked
                sig_preview = sig.split(",")[0] if sig else ""
                logger.warning(
                    f"[Stripe] Webhook sig verification failed across "
                    f"{len(secrets_list)} secret(s): {last_err} | body_len={len(body)} "
                    f"sig_t={sig_preview}"
                )
                # Bug-fix #19: previously, when sig_verified was False
                # the code logged a warning and FELL THROUGH into the
                # normal event processing (including _activate_plan()).
                # An attacker could POST a forged checkout.session.completed
                # payload and activate a paid subscription for free.
                # Refuse the request hard.
                if not is_health_ping:
                    return {
                        "received": False,
                        "error": "signature_invalid",
                        "verified": False,
                    }
                # health-ping case: parse for visibility but never act on it
                import json
                try:
                    event = json.loads(body)
                except Exception:
                    return {"received": False, "error": "bad payload"}
        else:
            import json
            try:
                event = json.loads(body)
            except Exception:
                return {"received": False, "error": "bad payload"}

        event_type = event.get("type", "") if isinstance(event, dict) else event.type
        data_obj = event.get("data", {}).get("object", {}) if isinstance(event, dict) else event.data.object

        if not is_health_ping:
            logger.info(f"[Stripe] Webhook: {event_type} (verified={sig_verified})")

        # iter 322 — bridge to plan_resolver for base-plan lifecycle events
        try:
            metadata = data_obj.get("metadata", {}) if isinstance(data_obj, dict) else {}
            # capture sub id for downstream persistence
            if event_type.startswith("customer.subscription.") and isinstance(data_obj, dict):
                metadata = dict(metadata or {})
                metadata.setdefault("subscription_id", data_obj.get("id"))
            await _recompute_bin_after_stripe_event(metadata, event_type)
        except Exception as _b_e:
            logger.debug(f"[Stripe] plan_resolver bridge skipped: {_b_e}")

        # Persist event for idempotency + dashboard health (skip ping spam)
        if _db is not None and not is_health_ping:
            try:
                event_id = event.get("id", "") if isinstance(event, dict) else getattr(event, "id", "")
                if event_id:
                    await _db.stripe_webhook_events.update_one(
                        {"event_id": event_id},
                        {"$set": {
                            "event_id": event_id,
                            "event_type": event_type,
                            "signature_verified": sig_verified,
                            "received_at": datetime.now(timezone.utc).isoformat(),
                        }},
                        upsert=True,
                    )
            except Exception as _persist_err:
                logger.debug(f"[Stripe] Webhook event persist failed: {_persist_err}")

        session_id = None
        if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            session_id = data_obj.get("id") if isinstance(data_obj, dict) else data_obj.id
            payment_status = data_obj.get("payment_status") if isinstance(data_obj, dict) else data_obj.payment_status

            # ── SEO Audit $49 unlock (Phase 1) ──
            try:
                metadata = data_obj.get("metadata", {}) if isinstance(data_obj, dict) else {}
                if metadata.get("product") == "seo_audit_49" and payment_status == "paid" and session_id:
                    from routers.seo_audit_router import mark_paid as _seo_mark_paid
                    await _seo_mark_paid(session_id)
                    logger.info(f"[Stripe] SEO audit unlocked via session {session_id}")
            except Exception as _seo_err:
                logger.warning(f"[Stripe] SEO audit unlock failed: {_seo_err}")

            # ── Iter 304 — Website Repair order paid → kick AWB build ──
            try:
                metadata = data_obj.get("metadata", {}) if isinstance(data_obj, dict) else {}
                if metadata.get("product") == "website_repair" and payment_status == "paid":
                    order_id = metadata.get("order_id")
                    if _db is not None and order_id:
                        order = await _db.repair_orders.find_one({"order_id": order_id})
                        if order:
                            paid_at = datetime.now(timezone.utc).isoformat()
                            await _db.repair_orders.update_one(
                                {"order_id": order_id},
                                {"$set": {"status": "paid", "paid_at": paid_at,
                                          "stripe_payment_intent": data_obj.get("payment_intent")}},
                            )
                            from routers.repair_checkout_router import _kick_repair_build
                            import asyncio as _aio
                            _aio.create_task(_kick_repair_build(order))
                            logger.info(f"[Stripe] website_repair order {order_id} paid → AWB build queued")
            except Exception as _rep_err:
                logger.warning(f"[Stripe] website_repair handler failed: {_rep_err}")

            if _db is not None and session_id:
                existing = await _db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})

                # ── Add-on subscription path (Phase 4) ──
                metadata = data_obj.get("metadata", {}) if isinstance(data_obj, dict) else {}
                if metadata.get("type") == "addon_subscription" and payment_status == "paid":
                    service_id = metadata.get("service_id")
                    tenant_bin = metadata.get("tenant_bin", "")
                    user_email = metadata.get("user_email") or (
                        data_obj.get("customer_details", {}).get("email") if isinstance(data_obj, dict) else None
                    )
                    stripe_sub_id = data_obj.get("subscription") if isinstance(data_obj, dict) else None
                    if service_id and user_email:
                        try:
                            # Activate the pending subscription doc
                            await _db.customer_subscriptions.update_one(
                                {"email": user_email, "service_id": service_id, "stripe_session_id": session_id},
                                {"$set": {
                                    "status": "active",
                                    "activated_at": datetime.now(timezone.utc).isoformat(),
                                    "stripe_subscription_id": stripe_sub_id,
                                }}
                            )
                            # Live catalog event for polling refresh
                            await _db.catalog_events.insert_one({
                                "type": "subscription_activated",
                                "email": user_email,
                                "service_id": service_id,
                                "tenant_bin": tenant_bin,
                                "at": datetime.now(timezone.utc).isoformat(),
                            })
                            logger.info(f"[Stripe] Add-on {service_id} activated for {user_email}")

                            # If Voice Agent service → provision Retell agent
                            if service_id == "voice_agent_ai":
                                try:
                                    from routers.voice_agent_router import _upsert_retell_agent, VoiceAgentConfig
                                    default_cfg = VoiceAgentConfig().dict()
                                    default_cfg["tenant_bin"] = tenant_bin
                                    await _upsert_retell_agent(tenant_bin, default_cfg)
                                    await _db.voice_agent_configs.update_one(
                                        {"tenant_bin": tenant_bin},
                                        {"$set": {**default_cfg, "auto_provisioned_at": datetime.now(timezone.utc).isoformat()}},
                                        upsert=True,
                                    )
                                except Exception as vp_err:
                                    logger.warning(f"[Stripe] Voice agent provision skipped: {vp_err}")
                        except Exception as addon_err:
                            logger.warning(f"[Stripe] Add-on activation failed: {addon_err}")
                    # Skip plan activation path below for add-ons
                elif existing and not existing.get("plan_activated") and payment_status == "paid":
                    # ── Legacy combo plan activation path ──
                    await _db.payment_transactions.update_one(
                        {"session_id": session_id},
                        {"$set": {"plan_activated": True, "payment_status": "paid",
                                  "webhook_received_at": datetime.now(timezone.utc).isoformat()}}
                    )
                    await _activate_plan(existing)

                    # Lifecycle: transition winning lead to 'won' + stop drip
                    try:
                        from services.lead_lifecycle import transition, record_touchpoint
                        customer_email = (
                            data_obj.get("customer_details", {}).get("email")
                            if isinstance(data_obj, dict) else None
                        ) or data_obj.get("customer_email") if isinstance(data_obj, dict) else None
                        if customer_email:
                            lead = await _db.campaign_leads.find_one({"email": customer_email}, {"_id": 0, "lead_id": 1})
                            if lead and lead.get("lead_id"):
                                await record_touchpoint(
                                    _db, lead["lead_id"], "payment", "stripe_paid", "sent",
                                    details={"session_id": session_id, "amount": data_obj.get("amount_total")},
                                )
                                await transition(_db, lead["lead_id"], "won", reason="stripe_payment", by="stripe_webhook", force=True)
                                logger.info(f"[Lifecycle] Lead {lead['lead_id']} transitioned to 'won' via Stripe")
                    except Exception as e:
                        logger.warning(f"[Lifecycle] Stripe → won transition failed: {e}")

        elif event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
        ):
            # iter 326j Gap 1 — bridge subscription lifecycle to
            # customer_subscriptions. Without this branch, when Stripe
            # creates the subscription BEFORE the checkout-session
            # completes (rare race, or for migrated subs created via
            # API not Checkout), the row stays at `status=pending` and
            # `stripe_subscription_id=None` forever. Founder then has
            # to manually reconcile in admin, every. single. time.
            sub_id          = data_obj.get("id") if isinstance(data_obj, dict) else None
            stripe_customer = data_obj.get("customer") if isinstance(data_obj, dict) else None
            sub_status      = data_obj.get("status") if isinstance(data_obj, dict) else None
            sub_metadata    = data_obj.get("metadata", {}) if isinstance(data_obj, dict) else {}
            service_id      = (sub_metadata or {}).get("service_id")
            cust_email      = (sub_metadata or {}).get("user_email")

            if _db and sub_id:
                # 1) Direct hit: row already has this stripe_subscription_id.
                stamped = await _db.customer_subscriptions.update_one(
                    {"stripe_subscription_id": sub_id},
                    {"$set": {
                        "status": "active" if sub_status in ("active", "trialing") else (sub_status or "pending"),
                        "stripe_status": sub_status,
                        "last_stripe_sync_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
                # 2) Fallback path — row was inserted at checkout-time WITH
                #    stripe_session_id but no stripe_subscription_id yet.
                #    Stamp it now using (email, service_id) as the join key.
                if stamped.matched_count == 0 and cust_email and service_id:
                    await _db.customer_subscriptions.update_one(
                        {
                            "email": cust_email,
                            "service_id": service_id,
                            "status": {"$in": ["pending", "active"]},
                            "$or": [
                                {"stripe_subscription_id": None},
                                {"stripe_subscription_id": {"$exists": False}},
                                {"stripe_subscription_id": ""},
                            ],
                        },
                        {"$set": {
                            "stripe_subscription_id": sub_id,
                            "stripe_customer_id":     stripe_customer,
                            "stripe_status":          sub_status,
                            "status": "active" if sub_status in ("active", "trialing") else "pending",
                            "activated_at":           datetime.now(timezone.utc).isoformat() if sub_status == "active" else None,
                            "last_stripe_sync_at":    datetime.now(timezone.utc).isoformat(),
                        }},
                    )
                logger.info(
                    f"[Stripe] subscription {event_type.rsplit('.', 1)[-1]}: "
                    f"id={sub_id} status={sub_status} stamped={stamped.matched_count}"
                )

        elif event_type == "customer.subscription.deleted":
            # Detect add-on vs combo plan by checking metadata
            customer_email = data_obj.get("customer_email") if isinstance(data_obj, dict) else getattr(data_obj, "customer_email", "")
            sub_id = data_obj.get("id") if isinstance(data_obj, dict) else getattr(data_obj, "id", "")
            metadata = data_obj.get("metadata", {}) if isinstance(data_obj, dict) else {}

            if _db and sub_id:
                # Try add-on first — find by stripe_subscription_id
                addon_sub = await _db.customer_subscriptions.find_one(
                    {"stripe_subscription_id": sub_id, "status": "active"}
                )
                if addon_sub:
                    await _db.customer_subscriptions.update_one(
                        {"sub_id": addon_sub["sub_id"]},
                        {"$set": {
                            "status": "cancelled",
                            "cancelled_at": datetime.now(timezone.utc).isoformat(),
                            "cancelled_via": "stripe_webhook",
                        }}
                    )
                    await _db.catalog_events.insert_one({
                        "type": "subscription_cancelled",
                        "email": addon_sub.get("email"),
                        "service_id": addon_sub.get("service_id"),
                        "at": datetime.now(timezone.utc).isoformat(),
                    })
                    logger.info(f"[Stripe] Add-on {addon_sub.get('service_id')} cancelled for {addon_sub.get('email')}")
                elif customer_email:
                    # Legacy combo plan cancellation → downgrade to starter
                    await _db.tenant_customers.update_one(
                        {"email": customer_email},
                        {"$set": {"plan": "starter", "plan_status": "cancelled"}}
                    )
                    logger.info(f"[Stripe] Combo plan cancelled for {customer_email} → downgraded to starter")

        return {"received": True, "event_type": event_type}

    except Exception as e:
        logger.error(f"[Stripe] Webhook error: {e}")
        return {"received": True, "error": str(e)}


async def _recompute_bin_after_stripe_event(metadata: Dict[str, Any], event_type: str):
    """iter 322 — bridge Stripe events → plan_resolver so services_unlocked
    stays fresh. Called inline from the webhook handler for base-plan and
    add-on lifecycle events. Best-effort, never raises out."""
    try:
        bin_id = (metadata or {}).get("business_id")
        if not bin_id:
            return
        if _db is None:
            return
        # On payment success / subscription updates, persist plan + recompute
        # services_unlocked. On payment failure, suspend access until cure.
        from services.plan_resolver import recompute_services_unlocked
        if event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
            "checkout.session.completed",
            "invoice.payment_succeeded",
        ):
            plan = (metadata or {}).get("plan")
            if plan:
                await _db.aurem_billing.update_one(
                    {"business_id": bin_id},
                    {"$set": {
                        "plan": plan,
                        "status": "active",
                        "stripe_subscription_id": (metadata or {}).get("subscription_id") or None,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True,
                )
            await recompute_services_unlocked(_db, bin_id)
        elif event_type == "invoice.payment_failed":
            await _db.aurem_billing.update_one(
                {"business_id": bin_id},
                {"$set": {
                    "status": "past_due",
                    "payment_failed_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            # Don't immediately suspend — Stripe retries 3x. Suspension
            # happens on customer.subscription.deleted if Stripe gives up.
        elif event_type == "customer.subscription.deleted":
            await _db.aurem_billing.update_one(
                {"business_id": bin_id},
                {"$set": {
                    "status": "cancelled",
                    "cancelled_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            await recompute_services_unlocked(_db, bin_id)
    except Exception as e:
        logger.warning(f"[Stripe] iter322 plan_resolver bridge failed: {e}")


# ═══════════════════════════════════════════════════
# PAYMENT HISTORY
# ═══════════════════════════════════════════════════

@router.get("/history")
async def payment_history(request: Request):
    """Get payment history for the current user."""
    user = _get_user_from_request(request)
    if not user:
        raise HTTPException(401, "Authentication required")

    if _db is None:
        return {"transactions": []}

    user_email = user.get("email", user.get("user_id", ""))
    cursor = _db.payment_transactions.find(
        {"user_email": user_email}, {"_id": 0}
    ).sort("created_at", -1).limit(50)

    transactions = await cursor.to_list(length=50)
    return {"transactions": transactions}


# ═══════════════════════════════════════════════════
# PUBLISHABLE KEY (for frontend)
# ═══════════════════════════════════════════════════

@router.get("/config")
async def payment_config():
    """Return publishable key for frontend Stripe integration."""
    pk = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    return {
        "publishable_key": pk,
        "currency": "cad",
        "plans": {k: {"name": v["name"], "amount": v["amount"], "features": v["features"]} for k, v in PACKAGES.items()},
    }


# ═══════════════════════════════════════════════════
# STRIPE CUSTOMER PORTAL
# ═══════════════════════════════════════════════════

@router.post("/portal")
async def create_billing_portal(request: Request):
    """Create a Stripe Customer Portal session for subscription management."""
    import stripe
    user = _get_user_from_request(request)
    if not user:
        raise HTTPException(401, "Authentication required")

    api_key = _get_stripe_key()
    if not api_key:
        raise HTTPException(503, "Stripe not configured")

    stripe.api_key = api_key
    user_email = user.get("email", "")

    # Find or create Stripe customer
    try:
        customers = stripe.Customer.list(email=user_email, limit=1)
        if customers.data:
            customer_id = customers.data[0].id
        else:
            customer = stripe.Customer.create(email=user_email, name=user.get("first_name", "AUREM User"))
            customer_id = customer.id
    except Exception as e:
        raise HTTPException(500, f"Stripe customer error: {e}")

    # Get origin URL for return
    origin = request.headers.get("origin", request.headers.get("referer", "https://aurem.live"))
    if origin.endswith("/"):
        origin = origin[:-1]

    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{origin}/dashboard",
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(500, f"Portal session error: {e}")


@router.get("/subscription")
async def get_subscription_status(request: Request):
    """Get current subscription status for the logged-in user."""
    import stripe
    user = _get_user_from_request(request)
    if not user:
        raise HTTPException(401, "Authentication required")

    api_key = _get_stripe_key()
    if not api_key:
        return {"has_subscription": False, "plan": "trial", "message": "Stripe not configured"}

    stripe.api_key = api_key
    user_email = user.get("email", "")

    try:
        customers = stripe.Customer.list(email=user_email, limit=1)
        if not customers.data:
            return {"has_subscription": False, "plan": "trial", "next_billing": None}

        customer_id = customers.data[0].id
        subs = stripe.Subscription.list(customer=customer_id, status="active", limit=1)

        if not subs.data:
            return {"has_subscription": False, "plan": "trial", "next_billing": None}

        sub = subs.data[0]
        plan_amount = sub.plan.amount / 100 if sub.plan else 0
        plan_name = "starter"
        if plan_amount >= 900:
            plan_name = "enterprise"
        elif plan_amount >= 250:
            plan_name = "growth"

        return {
            "has_subscription": True,
            "plan": plan_name,
            "plan_label": PACKAGES.get(plan_name, {}).get("name", plan_name.title()),
            "amount": plan_amount,
            "currency": sub.plan.currency if sub.plan else "cad",
            "status": sub.status,
            "current_period_end": sub.current_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end,
        }
    except Exception as e:
        logger.error(f"[Stripe] Subscription check error: {e}")
        return {"has_subscription": False, "plan": "trial", "error": str(e)}
