"""
ORA Notification Triggers
Wires OODA pipeline events to push notifications.
7 trigger types mapped to business events.
"""
import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_db = None

def set_db(db):
    global _db
    _db = db


TRIGGERS = {
    "vip_lead": {
        "title": "New VIP Lead",
        "body_template": "{lead_name} — {win_prob}% win prob",
        "url": "/ora",
        "tag": "ora-vip-lead",
        "actions": [
            {"action": "approve_outreach", "title": "APPROVE"},
            {"action": "skip", "title": "SKIP"},
        ],
        "vibrate": [200, 100, 200],
    },
    "invoice_paid": {
        "title": "Payment Received",
        "body_template": "${amount} from {client_name}",
        "url": "/ora",
        "tag": "ora-invoice-paid",
        "actions": [{"action": "view_invoice", "title": "VIEW"}],
        "vibrate": [100, 50, 100, 50, 200],
    },
    "approval_needed": {
        "title": "ORA Needs You",
        "body_template": "{action_description}",
        "url": "/ora",
        "tag": "ora-approval",
        "actions": [
            {"action": "approve", "title": "YES"},
            {"action": "reject", "title": "NO"},
        ],
        "vibrate": [300, 100, 300, 100, 300],
    },
    "morning_brief": {
        "title": "Morning Brief",
        "body_template": "{handled_count} done. {attention_count} need you",
        "url": "/ora",
        "tag": "ora-morning-brief",
        "actions": [{"action": "open_brief", "title": "OPEN"}],
        "vibrate": [100],
    },
    "website_issue": {
        "title": "Site Issue Fixed",
        "body_template": "{issue_type} auto-repaired",
        "url": "/ora",
        "tag": "ora-website-issue",
        "actions": [{"action": "view_health", "title": "VIEW"}],
        "vibrate": [100, 50, 100],
    },
    "anomaly_detected": {
        "title": "AUREM Alert",
        "body_template": "{anomaly_description}",
        "url": "/ora",
        "tag": "ora-anomaly",
        "actions": [{"action": "view_sentinel", "title": "CHECK"}],
        "vibrate": [500, 100, 500],
    },
    "pipeline_completed": {
        "title": "OODA Complete",
        "body_template": "{actions_taken} actions today",
        "url": "/ora",
        "tag": "ora-pipeline",
        "actions": [{"action": "view_pipeline", "title": "VIEW"}],
        "vibrate": [150, 75, 150],
    },
    "welcome": {
        "title": "Welcome to AUREM",
        "body_template": "Your Business ID: {business_id}",
        "url": "/ora",
        "tag": "ora-welcome",
        "actions": [],
        "vibrate": [100],
    },
}


async def store_notification(tenant_id: str, trigger_type: str, title: str, body: str, action_url: str = "/ora"):
    """Store notification in DB for history panel."""
    if _db is None:
        return
    await _db.notifications.insert_one({
        "tenant_id": tenant_id,
        "type": trigger_type,
        "title": title,
        "body": body,
        "action_url": action_url,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "read": False,
    })


async def send_push_to_tenant(tenant_id: str, title: str, body: str, url: str = "/ora", tag: str = "ora", trigger: dict = None):
    """Send push notification to all subscriptions for a tenant."""
    if _db is None:
        return 0

    vapid_private = os.environ.get("VAPID_PRIVATE_KEY", "")
    vapid_subject = os.environ.get("VAPID_SUBJECT", "mailto:support@aurem.ai")
    if not vapid_private:
        logger.debug("[NOTIFY] VAPID not configured, storing notification only")
        return 0

    try:
        from pywebpush import webpush
    except ImportError:
        return 0

    payload = json.dumps({
        "title": title,
        "body": body,
        "icon": "/ora-icon.png",
        "badge": "/ora-badge.png",
        "url": url,
        "tag": tag,
        "actions": trigger.get("actions", []) if trigger else [],
        "vibrate": trigger.get("vibrate", [200]) if trigger else [200],
    })

    user = await _db.users.find_one(
        {"$or": [{"id": tenant_id}, {"tenant_id": tenant_id}]},
        {"_id": 0, "id": 1, "email": 1}
    )
    if not user:
        return 0

    user_id = user.get("id", "")
    subs = _db.push_subscriptions.find({"user_id": user_id}, {"_id": 0})
    sent = 0
    stale = []

    async for sub in subs:
        try:
            webpush(
                subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]},
                data=payload,
                vapid_private_key=vapid_private,
                vapid_claims={"sub": vapid_subject},
            )
            sent += 1
        except Exception as e:
            if any(code in str(e) for code in ["410", "404", "400", "401"]):
                stale.append(sub["endpoint"])

    if stale:
        await _db.push_subscriptions.delete_many({"endpoint": {"$in": stale}})

    return sent


async def trigger_notification(tenant_id: str, trigger_type: str, **kwargs):
    """Fire a notification trigger with template data."""
    trigger = TRIGGERS.get(trigger_type)
    if not trigger:
        logger.warning(f"[NOTIFY] Unknown trigger type: {trigger_type}")
        return

    title = trigger["title"]
    try:
        body = trigger["body_template"].format(**kwargs)
    except KeyError as e:
        logger.warning(f"[NOTIFY] Missing template var {e} for {trigger_type}")
        body = trigger["body_template"]

    url = trigger.get("url", "/ora")
    tag = trigger.get("tag", "ora")

    await store_notification(tenant_id, trigger_type, title, body, url)
    sent = await send_push_to_tenant(tenant_id, title, body, url, tag, trigger)
    logger.info(f"[NOTIFY] {trigger_type} -> {tenant_id}: pushed to {sent} devices")
    return sent
