"""
iter 282al-17 — Second-Chance Outreach Service
==============================================
After an auto-refund is issued (services.website_repair_service.
auto_refund_paid_repair), the lead is tagged with:
    second_chance_eligible = True
    second_chance_after    = now + 14 days
    second_chance_sent     = absent (False)

This daily 10:00 UTC cron picks leads whose `second_chance_after` has
elapsed, composes a "we want to make it right" email offering the
$297 manual (human-reviewed) repair, and sends it with STOP footer +
Telegram ping.

Capacity: max 5 per run (gentle drip). Idempotent via
`second_chance_sent`.

Public API
----------
    check_eligibility(lead)            -> bool
    should_send(lead, now=None)        -> bool
    build_offer_email(lead, checkout_url) -> dict  {subject, body}
    run_second_chance_outreach(db, max_send=5, now=None) -> dict
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aurem_config as config

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Pure filter helpers (unit-testable, no I/O)
# ─────────────────────────────────────────────────────────────────────
def check_eligibility(lead: Dict[str, Any]) -> bool:
    """True iff the lead was tagged second_chance_eligible=True."""
    return bool((lead or {}).get("second_chance_eligible"))


def should_send(
    lead: Dict[str, Any], now: Optional[datetime] = None,
) -> bool:
    """
    True iff the lead is eligible, the 14-day cooldown has elapsed, the
    lead has an email, and we have not already sent the second chance.
    """
    if not check_eligibility(lead):
        return False
    if (lead or {}).get("second_chance_sent"):
        return False
    if not (lead or {}).get("email"):
        return False
    after = (lead or {}).get("second_chance_after")
    if after is None:
        return False
    _now = now or datetime.now(timezone.utc)
    try:
        # Accept both str-ISO and datetime
        if isinstance(after, str):
            after = datetime.fromisoformat(after.replace("Z", "+00:00"))
        if after.tzinfo is None:
            after = after.replace(tzinfo=timezone.utc)
        return _now >= after
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────
# Email body builder
# ─────────────────────────────────────────────────────────────────────
def build_offer_email(
    lead: Dict[str, Any], checkout_url: Optional[str] = None,
) -> Dict[str, str]:
    """Return {subject, body} for the second-chance $297 manual repair offer."""
    business = (lead or {}).get("business_name") or "your business"
    first = (business.split()[0] if business else "there")
    subject = f"We want to make it right — {business}"
    cta = checkout_url or "https://aurem.live/repair/manual"
    body = (
        f"Hi {first},\n\n"
        "A couple of weeks ago we tried to auto-fix your website and couldn't "
        "get it to our standard — so we refunded your $197 in full.\n\n"
        "That bothered us. So here's our make-it-right offer:\n\n"
        "Manual Website Repair — $297 CAD, one-time.\n"
        "  • Reviewed by a real human (no AI-only pass)\n"
        "  • Fixes the exact issues we flagged in your audit\n"
        "  • If it still doesn't pass our QA, we refund again — no questions\n\n"
        f"Claim it here: {cta}\n\n"
        "Not interested? Reply STOP and we'll stop emailing you.\n\n"
        "— AUREM (Canadian-built · trades-focused · CASL-compliant)"
    )
    return {"subject": subject, "body": body}


# ─────────────────────────────────────────────────────────────────────
# Main cron entry point
# ─────────────────────────────────────────────────────────────────────
async def run_second_chance_outreach(
    db, max_send: int = 5, now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Pick up to `max_send` eligible leads, send the $297 offer. Never raises."""
    if db is None:
        return {"sent": 0, "skipped": "no_db"}

    _now = now or datetime.now(timezone.utc)

    try:
        cursor = db.campaign_leads.find({
            "business_id":            FOUNDER_BIN,
            "second_chance_eligible": True,
            "second_chance_after":    {"$lte": _now},
            "second_chance_sent":     {"$ne": True},
            "email":                  {"$exists": True, "$ne": ""},
        }).limit(max_send)
        leads: List[Dict[str, Any]] = await cursor.to_list(length=max_send)
    except Exception as e:
        logger.warning(f"[second-chance] query failed: {e}")
        return {"sent": 0, "error": str(e)}

    manual_price_id = (
        config.STRIPE_PRICE_MANUAL_REPAIR
        or os.environ.get("STRIPE_PRICE_MANUAL_REPAIR")
        or ""
    ).strip()
    checkout_base = os.environ.get("AUREM_PUBLIC_BASE", "https://aurem.live")

    sent = 0
    for lead in leads:
        if not should_send(lead, now=_now):
            continue

        # Build checkout URL if price is configured
        lead_id = str(lead.get("_id") or lead.get("lead_id") or "")
        checkout_url: Optional[str] = None
        if manual_price_id:
            checkout_url = (
                f"{checkout_base}/api/payments/manual-repair/checkout"
                f"?lead_id={lead_id}"
            )

        msg = build_offer_email(lead, checkout_url)

        # Optional upgrade: compose_outreach handles CASL footer/locale
        try:
            from services.outreach_composer import compose_outreach
            composed = await compose_outreach(
                lead=lead, channel="email", step=1, db=db,
                site_change_context=(
                    "This lead previously paid $197 for auto-repair that "
                    "failed. We refunded them. Offer a $297 manual fix — a "
                    "real human will personally fix their site."
                ),
            )
            if composed and composed.get("body"):
                # Keep our concrete CTA + refund-apology intact
                msg["body"] = composed["body"] + "\n\n" + msg["body"]
        except Exception as e:
            logger.debug(f"[second-chance] compose_outreach skipped: {e}")

        # Send email
        try:
            from services.email_service_resend import send_email
            await send_email(
                to=lead["email"],
                subject=msg["subject"],
                body=msg["body"],
            )
        except Exception as e:
            logger.warning(f"[second-chance] email send failed for {lead_id}: {e}")
            continue

        # Idempotency flag
        try:
            await db.campaign_leads.update_one(
                {"_id": lead["_id"], "business_id": FOUNDER_BIN},
                {"$set": {
                    "second_chance_sent":     True,
                    "second_chance_sent_at":  _now,
                }},
            )
        except Exception:
            pass

        # Telegram
        try:
            from services.telegram_bot_service import send_telegram_alert
            await send_telegram_alert(
                f"Second-chance email sent\n"
                f"{lead.get('business_name') or '—'} · "
                f"{lead.get('city') or '—'}\n"
                f"Previous: $197 refunded · Offering: $297 manual fix"
            )
        except Exception:
            pass

        sent += 1

    return {"sent": sent, "considered": len(leads)}


# ─────────────────────────────────────────────────────────────────────
# Sync wrapper for tests / scheduler lambdas
# ─────────────────────────────────────────────────────────────────────
async def run_second_chance_job():
    """No-arg coroutine for APScheduler. Pulls db from startup globals."""
    try:
        from server import db as _db
    except Exception:
        _db = None
    return await run_second_chance_outreach(_db)
