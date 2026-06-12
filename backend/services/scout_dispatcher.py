"""
iter 282al-18 · Part 5 — Scout Dispatcher
==========================================
After a lead is validated + enriched by scout, route it to the right
sub-pipeline:

    has_website + website  →  audit existing → outreach with score
    no website / broken    →  build (AWB) → QA loop → notify customer

Helpers from earlier iters are reused, not rebuilt:
    services.website_repair_service.audit_existing_site
    services.auto_website_builder.build_site_for_lead
    services.site_qa_service.qa_repair_loop + send_site_to_customer
    services.shortlink_service.create_shortlink
    services.outreach_composer.compose_outreach

Public API
----------
    dispatch_lead(db, lead)              -> asyncio.Task (fire-and-forget)
    dispatch_lead_sync(db, lead)         -> coroutine (for tests)
    _audit_then_outreach(db, lead)       -> dict
    _build_qa_then_notify(db, lead)      -> dict
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Route detection
# ─────────────────────────────────────────────────────────────────────
def has_website(lead: Dict[str, Any]) -> bool:
    """True iff the lead has a website we should audit rather than rebuild."""
    if not lead:
        return False
    if lead.get("has_website") is False:
        return False
    url = (lead.get("website") or lead.get("website_url") or "").strip()
    if not url:
        return False
    # Treat obvious placeholder strings as "no website"
    bad = ("http://", "https://", "none", "n/a", "na", "-")
    if url.lower() in bad:
        return False
    return True


# ─────────────────────────────────────────────────────────────────────
# Path A — has-website : audit → outreach email w/ score + report link
# ─────────────────────────────────────────────────────────────────────
async def _audit_then_outreach(db, lead: Dict[str, Any]) -> Dict[str, Any]:
    """Audit existing site → email audit score + report link. Never raises."""
    lead_id = str(lead.get("_id") or lead.get("lead_id") or "")
    website = (lead.get("website") or lead.get("website_url") or "").strip()
    if not website:
        return {"ok": False, "reason": "no_website"}

    # 1 — audit
    audit: Dict[str, Any] = {}
    try:
        from services.website_repair_service import audit_existing_site
        audit = await audit_existing_site(db, lead) or {}
    except Exception as e:
        logger.warning(f"[dispatch] audit failed for {lead_id}: {e}")
        return {"ok": False, "reason": "audit_failed", "error": str(e)}

    score = int(audit.get("overall_score") or 0)
    issues_ct = len(audit.get("issues") or [])

    # 2 — persist on lead (so /report page picks it up + cron won't re-audit)
    if db is not None and lead.get("_id"):
        try:
            await db.campaign_leads.update_one(
                {"_id": lead["_id"], "business_id": FOUNDER_BIN},
                {"$set": {
                    "site_score":         score,
                    "site_issues_count":  issues_ct,
                    "audited_at":         datetime.now(timezone.utc),
                    "dispatch_route":     "audit_then_outreach",
                }},
            )
        except Exception:
            pass

    # 3 — shortlink to /report/{lead_id}
    short_url = f"https://aurem.live/report/{lead_id}"
    try:
        from services.shortlink_service import create_shortlink
        sl = await create_shortlink(db, lead_id, short_url)
        short_url = sl.get("short_url") or short_url
    except Exception as e:
        logger.debug(f"[dispatch] shortlink skipped: {e}")

    # 4 — compose outreach w/ CASL + score context
    subject = (
        f"We found {issues_ct} issues on {lead.get('business_name') or 'your'} "
        f"website — free audit"
    )
    body = (
        f"Hi {(lead.get('business_name') or '').split()[0] or 'there'},\n\n"
        f"We ran a free audit on your website and found {issues_ct} issues "
        f"(site score: {score}/100).\n\n"
        f"Full report: {short_url}\n\n"
        "No cost, no card, no pushy follow-ups. Reply STOP to opt out."
    )
    try:
        from services.outreach_composer import compose_outreach
        composed = await compose_outreach(
            lead=lead, channel="email", step=1, db=db,
            site_change_context=(
                f"Site score: {score}/100. {issues_ct} issues found. "
                "Free audit report ready."
            ),
        )
        if composed and composed.get("body"):
            body = composed["body"] + f"\n\nFull report: {short_url}"
    except Exception as e:
        logger.debug(f"[dispatch] compose_outreach skipped: {e}")

    # 5 — send
    sent_channels = []
    if lead.get("email"):
        try:
            from services.email_service_resend import send_email
            await send_email(to=lead["email"], subject=subject, body=body)
            sent_channels.append("email")
        except Exception as e:
            logger.warning(f"[dispatch] email failed {lead_id}: {e}")

    if lead.get("phone"):
        try:
            from services.twilio_whatsapp import send_whatsapp
            await send_whatsapp(
                lead["phone"],
                f"Hi {lead.get('business_name') or 'there'} — "
                f"free site audit ({issues_ct} issues): {short_url} "
                "Reply STOP to opt out.",
            )
            sent_channels.append("whatsapp")
        except Exception as e:
            logger.debug(f"[dispatch] whatsapp skipped: {e}")

    return {
        "ok":             True,
        "route":          "audit_then_outreach",
        "score":          score,
        "issues":         issues_ct,
        "short_url":      short_url,
        "channels":       sent_channels,
    }


# ─────────────────────────────────────────────────────────────────────
# Path B — no-website : AWB build → QA loop → send preview
# ─────────────────────────────────────────────────────────────────────
async def _build_qa_then_notify(db, lead: Dict[str, Any]) -> Dict[str, Any]:
    """Build site → QA repair loop → deliver to customer. Never raises."""
    lead_id = str(lead.get("_id") or lead.get("lead_id") or "")

    # 1 — build
    try:
        from services.auto_website_builder import build_site_for_lead
        site = await build_site_for_lead(db, lead_id)
    except Exception as e:
        logger.warning(f"[dispatch] AWB build failed for {lead_id}: {e}")
        return {"ok": False, "reason": "build_failed", "error": str(e)}

    slug = (site or {}).get("slug") or (site or {}).get("awb_slug") or ""
    live_url = (
        (site or {}).get("live_url")
        or (site or {}).get("preview_url")
        or ""
    )
    if not slug:
        return {"ok": False, "reason": "no_slug", "site": site}

    # 2 — QA loop
    try:
        from services.site_qa_service import qa_repair_loop
        qa = await qa_repair_loop(db, slug, live_url, max_attempts=3)
    except Exception as e:
        logger.warning(f"[dispatch] QA loop failed {slug}: {e}")
        qa = {"final_status": "failed", "ready_to_send": False, "attempts": 0}

    # 3 — deliver (gated on QA-verified OR no-key skip)
    if qa.get("ready_to_send"):
        try:
            from services.site_qa_service import send_site_to_customer
            notify = await send_site_to_customer(db, lead, slug, live_url, qa)
        except Exception as e:
            logger.warning(f"[dispatch] send_site_to_customer failed {slug}: {e}")
            notify = {"channels_sent": [], "short_url": live_url}
    else:
        # QA failed after 3 attempts — sentinel alert
        try:
            from services.telegram_bot_service import send_telegram_alert
            await send_telegram_alert(
                f"Site QA failed after 3 attempts\n"
                f"{lead.get('business_name') or '—'} · "
                f"{lead.get('city') or '—'}\n"
                f"Manual review needed · slug: {slug}"
            )
        except Exception:
            pass
        notify = {"channels_sent": [], "short_url": live_url, "qa_failed": True}

    # 4 — mark dispatch route on lead (audit trail)
    if db is not None and lead.get("_id"):
        try:
            await db.campaign_leads.update_one(
                {"_id": lead["_id"], "business_id": FOUNDER_BIN},
                {"$set": {
                    "dispatch_route": "build_qa_then_notify",
                    "site_slug":      slug,
                }},
            )
        except Exception:
            pass

    return {
        "ok":         True,
        "route":      "build_qa_then_notify",
        "slug":       slug,
        "live_url":   live_url,
        "qa":         qa,
        "notify":     notify,
    }


# ─────────────────────────────────────────────────────────────────────
# Public dispatcher
# ─────────────────────────────────────────────────────────────────────
async def dispatch_lead_sync(db, lead: Dict[str, Any]) -> Dict[str, Any]:
    """Single-call dispatcher. Returns the sub-result. Never raises."""
    if has_website(lead):
        return await _audit_then_outreach(db, lead)
    return await _build_qa_then_notify(db, lead)


def dispatch_lead(db, lead: Dict[str, Any]) -> asyncio.Task:
    """Fire-and-forget variant. Returns the asyncio Task (test-friendly)."""
    return asyncio.create_task(dispatch_lead_sync(db, lead))
