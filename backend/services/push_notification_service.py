"""
AUREM Push Notification Service
================================
Fires VAPID web push notifications on key ORA platform events.

Events:
  - New lead detected (Scout)
  - Outreach sent (Closer/Envoy)
  - Invoice created or paid
  - Sentinel fix applied
  - Morning Brief ready
  - P0 alert from Sentinel
"""

import os
import json
import logging
from typing import Optional, Dict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_db = None

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:support@aurem.ai")


def set_db(database):
    global _db
    _db = database


def get_db():
    return _db


async def register_subscription(user_id: str, subscription: dict) -> bool:
    """Store a push subscription for a user."""
    db = get_db()
    if db is None:
        return False

    await db.push_subscriptions.update_one(
        {"user_id": user_id, "endpoint": subscription.get("endpoint")},
        {"$set": {
            "user_id": user_id,
            "subscription": subscription,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return True


async def _send_push(user_id: str, title: str, body: str, data: Optional[Dict] = None):
    """Send push notification to all subscriptions for a user."""
    if not VAPID_PUBLIC_KEY or not VAPID_PRIVATE_KEY:
        logger.debug("[Push] VAPID keys not configured — skipping")
        return

    db = get_db()
    if db is None:
        return

    subs = await db.push_subscriptions.find(
        {"user_id": user_id}, {"_id": 0, "subscription": 1}
    ).to_list(20)

    if not subs:
        return

    payload = json.dumps({
        "title": title,
        "body": body,
        "icon": "/aurem-icon.png",
        "badge": "/aurem-badge.png",
        "data": data or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning("[Push] pywebpush not installed — skipping")
        return

    sent = 0
    for sub_record in subs:
        sub = sub_record.get("subscription", {})
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_SUBJECT},
            )
            sent += 1
        except WebPushException as e:
            if "410" in str(e) or "404" in str(e):
                # Subscription expired — remove it
                await db.push_subscriptions.delete_one(
                    {"user_id": user_id, "endpoint": sub.get("endpoint")}
                )
            else:
                logger.warning(f"[Push] Error sending to {user_id}: {e}")
        except Exception as e:
            logger.warning(f"[Push] Unexpected error: {e}")

    if sent:
        logger.info(f"[Push] Sent '{title}' to {sent} device(s) for user {user_id}")


# ═══════════════════════════════════════════════════
# EVENT TRIGGERS — Call these from platform code
# ═══════════════════════════════════════════════════

async def notify_new_lead(user_id: str, lead_name: str, source: str = "Scout"):
    """Fire when Scout discovers a new lead."""
    await _send_push(
        user_id,
        f"New Lead Detected",
        f"{source} found: {lead_name}",
        {"event": "new_lead", "source": source},
    )


async def notify_outreach_sent(user_id: str, contact_name: str, channel: str = "email"):
    """Fire when Envoy/Closer sends outreach."""
    await _send_push(
        user_id,
        f"Outreach Sent",
        f"Message sent to {contact_name} via {channel}",
        {"event": "outreach_sent", "channel": channel},
    )


async def notify_invoice_event(user_id: str, event_type: str, amount: float = 0):
    """Fire when invoice is created or paid."""
    label = "Invoice Created" if event_type == "created" else "Payment Received"
    body = f"${amount:,.2f}" if amount else event_type
    await _send_push(
        user_id, label, body,
        {"event": f"invoice_{event_type}", "amount": amount},
    )


async def notify_sentinel_fix(user_id: str, site_url: str, fix_count: int):
    """Fire when Sentinel applies a fix."""
    await _send_push(
        user_id,
        f"Sentinel Fix Applied",
        f"{fix_count} fix(es) deployed to {site_url}",
        {"event": "sentinel_fix", "site_url": site_url},
    )


async def notify_morning_brief(user_id: str, digest: str):
    """Fire when Morning Brief is ready."""
    await _send_push(
        user_id,
        "Morning Brief Ready",
        digest[:120],
        {"event": "morning_brief"},
    )


async def notify_p0_alert(user_id: str, alert_msg: str):
    """Fire on any P0 Sentinel alert."""
    await _send_push(
        user_id,
        "P0 ALERT",
        alert_msg[:120],
        {"event": "p0_alert", "urgent": True},
    )


# iter 322v — additional event triggers (HIGH-risk + pipeline + payment + brief)
async def notify_high_risk_proposal(user_id: str, title: str, proposal_id: str):
    """Fire when a HIGH-risk Dev Console proposal is published."""
    await _send_push(
        user_id,
        "HIGH RISK Proposal",
        title[:120],
        {"event": "high_risk_proposal", "proposal_id": proposal_id, "urgent": True},
    )


async def notify_pipeline_complete(user_id: str, summary: str):
    """Fire when an outbound campaign / pipeline run completes."""
    await _send_push(
        user_id,
        "Pipeline Complete",
        summary[:120],
        {"event": "pipeline_complete"},
    )


async def notify_payment_received(user_id: str, amount: float, customer: str = ""):
    """Fire when a payment is captured (Stripe webhook etc.)."""
    body = f"${amount:,.2f}" + (f" from {customer}" if customer else "")
    await _send_push(
        user_id,
        "Payment Received",
        body,
        {"event": "payment_received", "amount": amount},
    )


async def send_test_push(user_id: str, label: str = "Test push"):
    """Founder-callable smoke test."""
    await _send_push(
        user_id,
        "AUREM Test Push",
        label[:120],
        {"event": "test"},
    )
