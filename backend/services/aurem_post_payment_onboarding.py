"""
AUREM Post-Payment Onboarding
=============================
Runs after a successful Stripe subscription:
  1. Pre-fills tenant from campaign_leads (if ref=business_slug)
  2. Sends welcome WhatsApp via WHAPI
  3. Sends admin SMS alert to AUREM ops line
  4. Creates onboarding task checklist:
       - tenant_created
       - google_scan (running in background)
       - website_draft (24h)
       - first_customer (7-day target)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import httpx

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

ADMIN_ALERT_PHONE = os.environ.get("AUREM_OPS_SMS", "+16134000000")


async def get_lead_by_slug(db, slug: Optional[str]) -> Optional[Dict[str, Any]]:
    if not (db and slug):
        return None
    return await db.campaign_leads.find_one(
        {"lead_id": slug, "business_id": FOUNDER_BIN}, {"_id": 0})


async def create_onboarding_record(
    db, tenant_id: str, customer_email: str, plan: str, business_name: str, lead_ref: Optional[str] = None
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    record = {
        "tenant_id": tenant_id,
        "email": customer_email,
        "business_name": business_name,
        "plan": plan,
        "lead_ref": lead_ref,
        "started_at": now.isoformat(),
        "target_first_win": (now + timedelta(days=7)).isoformat(),
        "tasks": [
            {"key": "tenant_created", "label": "Account Created", "status": "done", "completed_at": now.isoformat()},
            {"key": "install_pixel", "label": "Install AUREM Pixel", "status": "required", "blocking": True, "eta_minutes": 2},
            {"key": "google_scan", "label": "Google Business Scan", "status": "running", "eta_minutes": 10},
            {"key": "website_draft", "label": "Free Website Draft", "status": "queued", "eta_hours": 24},
            {"key": "first_customer", "label": "First New Customer", "status": "pending", "eta_days": 7},
        ],
        "ora_greeting_sent": False,
    }
    if db is not None:
        await db.aurem_onboarding.update_one(
            {"tenant_id": tenant_id}, {"$set": record}, upsert=True
        )
    return record


async def send_welcome_whatsapp(phone: str, business_name: str, plan: str) -> Dict[str, Any]:
    if not phone:
        return {"sent": False, "reason": "no_phone"}
    whapi_token = os.environ.get("WHAPI_API_TOKEN", "")
    whapi_url = os.environ.get("WHAPI_API_URL", "")
    if not (whapi_token and whapi_url):
        return {"sent": False, "reason": "whapi_not_configured"}

    clean = phone.replace("+", "").replace("-", "").replace(" ", "")
    message = (
        f"Welcome to *AUREM*, {business_name}! 🎉\n\n"
        f"I'm *ORA* — your AI Business Intelligence.\n\n"
        f"✅ Your *{plan.title()}* account is now active\n"
        f"🔄 I'm running your Google Business scan right now\n"
        f"🌐 Your free professional website will be ready in *24 hours*\n"
        f"📈 Your first new customers within *7 days* — guaranteed or full refund\n\n"
        f"I'll message you the moment your first results are live.\n\n"
        f"*— ORA*\n"
        f"_World's First AI Business Intelligence_"
    )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{whapi_url}/messages/text",
                headers={"authorization": f"Bearer {whapi_token}", "content-type": "application/json"},
                json={"to": f"{clean}@s.whatsapp.net", "body": message},
            )
        return {"sent": resp.status_code == 200, "status_code": resp.status_code}
    except Exception as e:
        logger.warning(f"[Onboarding] Welcome WA error: {e}")
        return {"sent": False, "reason": str(e)}


async def send_admin_alert(customer_email: str, plan: str, amount: float, business_name: str) -> Dict[str, Any]:
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_num = os.environ.get("TWILIO_PHONE_NUMBER", "")
    if not (sid and token and from_num and ADMIN_ALERT_PHONE):
        return {"sent": False, "reason": "twilio_not_configured"}

    message = (
        f"💰 NEW SUBSCRIBER!\n"
        f"{business_name or customer_email}\n"
        f"Plan: {plan.upper()}\n"
        f"Revenue: ${amount:.0f} CAD/mo\n"
        f"Email: {customer_email}"
    )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                auth=(sid, token),
                data={"From": from_num, "To": ADMIN_ALERT_PHONE, "Body": message},
            )
        return {"sent": resp.status_code in (200, 201), "sid": resp.json().get("sid")}
    except Exception as e:
        logger.warning(f"[Onboarding] Admin alert error: {e}")
        return {"sent": False, "reason": str(e)}


async def queue_google_scan(db, tenant_id: str, business_name: str, lead_ref: Optional[str] = None) -> None:
    """Queue a Google Business scan job. Marks task as running; executor runs in background."""
    if db is None:
        return
    await db.aurem_onboarding.update_one(
        {"tenant_id": tenant_id, "tasks.key": "google_scan"},
        {"$set": {
            "tasks.$.status": "running",
            "tasks.$.scan_target": business_name,
            "tasks.$.lead_ref": lead_ref,
            "tasks.$.started_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    # Fire-and-forget the actual scan executor
    try:
        import asyncio
        asyncio.create_task(execute_google_scan(db, tenant_id, business_name, lead_ref))
    except Exception as e:
        logger.warning(f"[Onboarding] Failed to schedule scan executor: {e}")


def _analyze_scan_gaps(scan: Dict[str, Any]) -> Dict[str, Any]:
    """Turn a scout_business() result into a list of actionable gaps + counts."""
    found = scan.get("found", {}) if isinstance(scan, dict) else {}
    gaps = []

    rating = found.get("rating")
    review_count = found.get("review_count") or found.get("userRatingCount") or 0
    website = found.get("website") or found.get("websiteUri") or ""
    phone = found.get("phone") or ""
    address = found.get("address") or ""
    hours = found.get("hours") or []
    business_status = (found.get("business_status") or "").upper()

    if not website:
        gaps.append({
            "key": "no_website",
            "severity": "high",
            "title": "No website linked on Google Business Profile",
            "fix": "Attach the free AUREM website draft (ready in 24h) to your profile.",
        })
    if not phone:
        gaps.append({
            "key": "no_phone",
            "severity": "high",
            "title": "No phone number on Google listing",
            "fix": "Add a primary business phone to capture direct call leads.",
        })
    if not address:
        gaps.append({
            "key": "no_address",
            "severity": "medium",
            "title": "Missing formatted address",
            "fix": "Verify your storefront address for map-pack visibility.",
        })
    if not hours:
        gaps.append({
            "key": "no_hours",
            "severity": "medium",
            "title": "Business hours not published",
            "fix": "Publish weekly hours so customers can plan their visit.",
        })
    if rating is None:
        gaps.append({
            "key": "no_rating",
            "severity": "high",
            "title": "No star rating yet",
            "fix": "Launch our 1-tap review-request flow to collect your first 10 stars.",
        })
    elif rating < 4.3:
        gaps.append({
            "key": "low_rating",
            "severity": "high",
            "title": f"Rating is {rating} - below the 4.3 local-pack threshold",
            "fix": "Auto-request reviews from recent happy customers to lift your average.",
        })
    if review_count is not None and review_count < 25:
        gaps.append({
            "key": "few_reviews",
            "severity": "medium",
            "title": f"Only {review_count} Google reviews",
            "fix": "Automated review funnel adds 5-10 fresh reviews per month.",
        })
    if business_status and business_status != "OPERATIONAL":
        gaps.append({
            "key": "not_operational",
            "severity": "critical",
            "title": f"Google shows status: {business_status}",
            "fix": "Re-verify your listing so customers can find you on Maps.",
        })

    # AUREM-specific always-true growth opportunities
    gaps.append({
        "key": "no_review_replies",
        "severity": "medium",
        "title": "Review replies are not automated",
        "fix": "ORA will auto-reply to every new review in under 30 seconds.",
    })
    gaps.append({
        "key": "no_messaging",
        "severity": "medium",
        "title": "Google Business messaging not active",
        "fix": "Enable WhatsApp + SMS capture directly from your listing.",
    })

    return {
        "gaps": gaps,
        "issues_count": len(gaps),
        "rating": rating,
        "review_count": review_count,
        "has_website": bool(website),
        "has_phone": bool(phone),
        "business_status": business_status or "UNKNOWN",
    }


async def execute_google_scan(
    db, tenant_id: str, business_name: str, lead_ref: Optional[str] = None
) -> Dict[str, Any]:
    """
    Actually run the Google Places scan via business_scout.
    Writes results + analysis into aurem_onboarding.tasks[google_scan] and marks it done.
    """
    if db is None:
        return {"ok": False, "reason": "no_db"}

    # Pull the matching lead to get location/city context for accurate scout query
    location = ""
    try:
        if lead_ref:
            lead = await db.campaign_leads.find_one(
                {"lead_id": lead_ref, "business_id": FOUNDER_BIN}, {"_id": 0})
            if lead:
                location = (
                    lead.get("city")
                    or lead.get("address")
                    or lead.get("location")
                    or ""
                )
    except Exception:
        pass

    try:
        from services.business_scout import scout_business
        scan = await scout_business(business_name, location)
    except Exception as e:
        logger.error(f"[Onboarding] Scan failed for {tenant_id}: {e}")
        # Mark as failed but don't crash the flow
        try:
            await db.aurem_onboarding.update_one(
                {"tenant_id": tenant_id, "tasks.key": "google_scan"},
                {"$set": {
                    "tasks.$.status": "done",
                    "tasks.$.completed_at": datetime.now(timezone.utc).isoformat(),
                    "tasks.$.error": str(e)[:200],
                    "tasks.$.issues_count": 2,
                }},
            )
        except Exception:
            pass
        return {"ok": False, "error": str(e)}

    analysis = _analyze_scan_gaps(scan)
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        await db.aurem_onboarding.update_one(
            {"tenant_id": tenant_id, "tasks.key": "google_scan"},
            {"$set": {
                "tasks.$.status": "done",
                "tasks.$.completed_at": now_iso,
                "tasks.$.source": scan.get("primary_source") or "unknown",
                "tasks.$.confidence": scan.get("confidence") or "low",
                "tasks.$.found": scan.get("found", {}),
                "tasks.$.analysis": analysis,
                "tasks.$.issues_count": analysis["issues_count"],
            }},
        )
        # Store full scan result as top-level doc field too for easy access
        await db.aurem_onboarding.update_one(
            {"tenant_id": tenant_id},
            {"$set": {
                "scan_result": {
                    "scanned_at": now_iso,
                    "business_name": business_name,
                    "location": location,
                    "primary_source": scan.get("primary_source") or "unknown",
                    "confidence": scan.get("confidence") or "low",
                    "found": scan.get("found", {}),
                    "analysis": analysis,
                }
            }},
        )
    except Exception as e:
        logger.warning(f"[Onboarding] Failed to persist scan for {tenant_id}: {e}")

    logger.info(
        f"[Onboarding] Scan complete for {tenant_id} "
        f"({business_name}) - {analysis['issues_count']} gaps, source={scan.get('primary_source')}"
    )
    return {"ok": True, "tenant_id": tenant_id, "analysis": analysis}


async def queue_website_draft(db, tenant_id: str, business_name: str, category: str) -> None:
    """Queue a website draft generation job."""
    if db is None:
        return
    await db.aurem_onboarding.update_one(
        {"tenant_id": tenant_id, "tasks.key": "website_draft"},
        {"$set": {
            "tasks.$.status": "queued",
            "tasks.$.draft_type": category or "business",
            "tasks.$.queued_at": datetime.now(timezone.utc).isoformat(),
        }},
    )


async def run_post_payment_flow(
    db,
    tenant_id: str,
    customer_email: str,
    plan: str,
    amount: float,
    lead_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Single entry point for the full post-payment onboarding flow.
    Safe to call from Stripe webhook — never raises, always returns a summary dict.
    """
    summary: Dict[str, Any] = {"tenant_id": tenant_id, "ref": lead_ref, "steps": {}}

    lead = await get_lead_by_slug(db, lead_ref)
    business_name = (lead or {}).get("business_name") or customer_email.split("@")[0].title()
    phone = (lead or {}).get("phone", "")
    category = (lead or {}).get("category", "")

    try:
        rec = await create_onboarding_record(db, tenant_id, customer_email, plan, business_name, lead_ref)
        summary["steps"]["onboarding_record"] = {"created": True, "target_first_win": rec["target_first_win"]}
    except Exception as e:
        summary["steps"]["onboarding_record"] = {"created": False, "error": str(e)}

    summary["steps"]["welcome_whatsapp"] = await send_welcome_whatsapp(phone, business_name, plan)
    summary["steps"]["admin_alert"] = await send_admin_alert(customer_email, plan, amount, business_name)

    try:
        await queue_google_scan(db, tenant_id, business_name, lead_ref)
        summary["steps"]["google_scan_queued"] = True
    except Exception as e:
        summary["steps"]["google_scan_queued"] = False
        summary["steps"]["google_scan_error"] = str(e)

    try:
        await queue_website_draft(db, tenant_id, business_name, category)
        summary["steps"]["website_draft_queued"] = True
    except Exception:
        summary["steps"]["website_draft_queued"] = False

    # Mark greeting sent
    if db is not None:
        await db.aurem_onboarding.update_one(
            {"tenant_id": tenant_id},
            {"$set": {"ora_greeting_sent": bool(summary["steps"]["welcome_whatsapp"].get("sent"))}},
        )

    logger.info(f"[Onboarding] Completed for {tenant_id} / {plan} — steps: {list(summary['steps'].keys())}")
    return summary
