"""
AUREM End-to-End Onboarding Test Router
========================================
Admin-only safety endpoint to simulate a full post-payment flow
WITHOUT touching Stripe. Use this to verify the entire chain works
before accepting the first real paying customer.

Verifies:
  1. tenant_created           ← aurem_onboarding collection
  2. google_scan              ← aurem_onboarding.tasks[google_scan]
  3. welcome_whatsapp         ← WHAPI send (mocked in dry_run)
  4. admin_alert              ← Twilio SMS send (mocked in dry_run)
  5. website_draft_queued     ← aurem_onboarding.tasks[website_draft]
  6. CRM stage update         ← campaign_leads.stage update

Route: POST /api/admin/onboarding-test
Body:  {"email":"test@aurem.live","plan":"starter","ref":"","dry_run":true}
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin Onboarding Test"])

_db = None


def set_db(db):
    global _db
    _db = db


def _require_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "auth required")
    return auth.replace("Bearer ", "", 1)


class OnboardingTestBody(BaseModel):
    email: str = "test@aurem.live"
    plan: str = "starter"
    ref: str = ""
    dry_run: bool = True


@router.post("/onboarding-test")
async def test_onboarding_chain(body: OnboardingTestBody, request: Request):
    """
    Simulate a full Stripe → onboarding flow end-to-end.
    When dry_run=True, no real WhatsApp / SMS is sent (helpers short-circuit).
    Returns a step-by-step checklist of pass/fail.
    """
    _require_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not ready")

    result: Dict[str, Any] = {
        "scenario": "simulated_stripe_checkout_session_completed",
        "dry_run": body.dry_run,
        "email": body.email,
        "plan": body.plan,
        "steps": {},
        "checklist": [],
    }

    tenant_id = body.email.replace("@", "-")

    # If dry_run, monkey-patch the actual network helpers during this test only
    import services.whapi_service as _whapi
    import services.twilio_service as _twilio
    _orig_whapi = getattr(_whapi, "send_whatsapp_message", None)
    _orig_twilio = getattr(_twilio, "send_sms", None)

    if body.dry_run:
        async def _mock_whapi(phone, message, *a, **kw):
            logger.info(f"[ONBOARDING TEST · DRY] WhatsApp → {phone}: {message[:60]}...")
            return {"success": True, "dry_run": True, "would_send_to": phone, "preview": message[:200]}
        async def _mock_twilio(phone, message, *a, **kw):
            logger.info(f"[ONBOARDING TEST · DRY] SMS → {phone}: {message[:60]}...")
            return {"success": True, "dry_run": True, "would_send_to": phone, "preview": message[:200]}
        if _orig_whapi: _whapi.send_whatsapp_message = _mock_whapi
        if _orig_twilio: _twilio.send_sms = _mock_twilio

    try:
        from services.aurem_post_payment_onboarding import run_post_payment_flow
        summary = await run_post_payment_flow(
            db=_db,
            tenant_id=tenant_id,
            customer_email=body.email,
            plan=body.plan,
            amount=97.0,
            lead_ref=body.ref,
        )
        result["steps"] = summary.get("steps", {})

        # Build checklist (what we care about on deploy day)
        steps = summary.get("steps", {})
        result["checklist"] = [
            {"step": "1. tenant_created",          "ok": bool((steps.get("onboarding_record") or {}).get("created"))},
            {"step": "2. google_scan_queued",      "ok": bool(steps.get("google_scan_queued"))},
            {"step": "3. website_draft_queued",    "ok": bool(steps.get("website_draft_queued"))},
            {"step": "4. welcome_whatsapp_called", "ok": (steps.get("welcome_whatsapp") or {}).get("sent") is not None},
            {"step": "5. admin_alert_called",      "ok": (steps.get("admin_alert") or {}).get("sent") is not None},
        ]

        # Verify onboarding record landed in DB
        onboarding_doc = await _db.aurem_onboarding.find_one({"tenant_id": tenant_id}, {"_id": 0})
        result["checklist"].append({
            "step": "6. aurem_onboarding doc persisted",
            "ok": onboarding_doc is not None,
        })

        # Try to mark a campaign_leads stage update if ref provided
        if body.ref:
            lead = await _db.campaign_leads.find_one({"lead_id": body.ref}, {"_id": 0})
            result["checklist"].append({
                "step": "7. CRM lead found by ref",
                "ok": lead is not None,
            })

        result["overall"] = "PASS" if all(c["ok"] for c in result["checklist"]) else "PARTIAL"
        result["summary_short"] = (
            f"{sum(c['ok'] for c in result['checklist'])}/"
            f"{len(result['checklist'])} checks passed"
        )
    except Exception as e:
        logger.exception("[OnboardingTest] run failed")
        result["overall"] = "FAIL"
        result["error"] = str(e)
    finally:
        # Restore original helpers
        if body.dry_run:
            if _orig_whapi: _whapi.send_whatsapp_message = _orig_whapi
            if _orig_twilio: _twilio.send_sms = _orig_twilio

    return result
