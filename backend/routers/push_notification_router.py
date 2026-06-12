"""
ORA Push Notification Service
Handles VAPID-based web push subscriptions and dispatches
"Repair Complete" notifications when the AI Forensic Suite finishes.
"""
import os
import json
import logging
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/push", tags=["push"])

_db = None

def set_db(db):
    global _db
    _db = db

def _get_db():
    global _db
    return _db


class PushSubscription(BaseModel):
    endpoint: str
    keys: dict


class PushMessage(BaseModel):
    title: str
    body: str
    icon: Optional[str] = "/ora-icon.png"
    url: Optional[str] = "/dashboard"
    tag: Optional[str] = "ora-notification"


@router.get("/vapid-key")
async def get_vapid_public_key():
    """Return the VAPID public key so the frontend can subscribe."""
    key = os.environ.get("VAPID_PUBLIC_KEY", "")
    if not key:
        raise HTTPException(400, "VAPID keys not configured")
    return {"public_key": key}


@router.post("/subscribe")
async def subscribe(subscription: PushSubscription, request: Request):
    """Store a push subscription for later notification delivery."""
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not available")

    user_id = "anonymous"
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from utils.aurem_jwt import decode_token
            payload = decode_token(auth_header.split(" ")[1])
            user_id = payload.get("user_id", "anonymous")
        except Exception:
            pass

    await db.push_subscriptions.update_one(
        {"endpoint": subscription.endpoint},
        {"$set": {
            "endpoint": subscription.endpoint,
            "keys": subscription.keys,
            "user_id": user_id,
        }},
        upsert=True,
    )
    return {"success": True, "message": "Subscribed to push notifications"}


@router.post("/unsubscribe")
async def unsubscribe(subscription: PushSubscription):
    """Remove a push subscription."""
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not available")
    await db.push_subscriptions.delete_one({"endpoint": subscription.endpoint})
    return {"success": True}


async def send_push_to_all(title: str, body: str, url: str = "/dashboard", tag: str = "ora"):
    """Send a push notification to ALL active subscriptions."""
    db = _get_db()
    if db is None:
        logger.warning("[PUSH] Database not available")
        return 0

    vapid_private = os.environ.get("VAPID_PRIVATE_KEY", "")
    vapid_subject = os.environ.get("VAPID_SUBJECT", "mailto:support@aurem.ai")
    if not vapid_private:
        logger.warning("[PUSH] VAPID_PRIVATE_KEY not configured")
        return 0

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.error("[PUSH] pywebpush not installed")
        return 0

    payload = json.dumps({
        "title": title,
        "body": body,
        "icon": "/ora-icon.png",
        "badge": "/ora-badge.png",
        "url": url,
        "tag": tag,
    })

    sent = 0
    stale_endpoints = []

    cursor = db.push_subscriptions.find({}, {"_id": 0})
    async for sub in cursor:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": sub["keys"],
                },
                data=payload,
                vapid_private_key=vapid_private,
                vapid_claims={"sub": vapid_subject},
            )
            sent += 1
        except Exception as e:
            err_str = str(e)
            if "410" in err_str or "404" in err_str or "400" in err_str or "401" in err_str or "403" in err_str:
                stale_endpoints.append(sub["endpoint"])
            logger.warning(f"[PUSH] Failed to send to {sub['endpoint'][:40]}...: {err_str[:80]}")

    # Clean stale subscriptions
    if stale_endpoints:
        await db.push_subscriptions.delete_many({"endpoint": {"$in": stale_endpoints}})
        logger.info(f"[PUSH] Cleaned {len(stale_endpoints)} stale subscriptions")

    logger.info(f"[PUSH] Sent {sent} notifications: {title}")
    return sent


async def notify_repair_complete(scan_url: str, fixes_deployed: int, success_count: int):
    """Fire a push notification when the ORA Repair Engine finishes."""
    return await send_push_to_all(
        title="ORA Repair Complete",
        body=f"Deployed {success_count}/{fixes_deployed} fixes for {scan_url}",
        url="/dashboard",
        tag="ora-repair-complete",
    )


async def send_actionable_push(title: str, body: str, actions: list, url: str = "/dashboard", tag: str = "ora-action"):
    """
    Send a push notification with action buttons.
    Actions format: [{"action": "approve", "title": "Approve", "url": "/api/...", "confirm": "Done!"}]
    Works on phone notifications AND smartwatch (WearOS).
    """
    db = _get_db()
    if db is None:
        return 0

    vapid_private = os.environ.get("VAPID_PRIVATE_KEY", "")
    vapid_subject = os.environ.get("VAPID_SUBJECT", "mailto:support@aurem.ai")
    if not vapid_private:
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
        "require_interaction": True,
        "actions": actions,
    })

    sent = 0
    stale = []

    cursor = db.push_subscriptions.find({}, {"_id": 0})
    async for sub in cursor:
        try:
            webpush(
                subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]},
                data=payload,
                vapid_private_key=vapid_private,
                vapid_claims={"sub": vapid_subject},
            )
            sent += 1
        except Exception as e:
            if any(c in str(e) for c in ["410", "404", "400", "401", "403"]):
                stale.append(sub["endpoint"])

    if stale:
        await db.push_subscriptions.delete_many({"endpoint": {"$in": stale}})

    logger.info(f"[PUSH] Sent {sent} actionable notifications: {title}")
    return sent


async def notify_new_lead(business_name: str, score: int, lead_id: str):
    """Push notification when a new lead arrives — with Approve/Skip action buttons."""
    base_url = os.environ.get("REACT_APP_BACKEND_URL", "")
    return await send_actionable_push(
        title=f"New Lead — {business_name}",
        body=f"Site score: {score}/100. Ready to pitch.",
        actions=[
            {"action": "approve", "title": "Approve Outreach", "url": f"{base_url}/api/pipeline/approve/{lead_id}", "confirm": "Outreach approved!"},
            {"action": "skip", "title": "Skip", "url": f"{base_url}/api/pipeline/skip/{lead_id}", "confirm": "Lead skipped."},
        ],
        url="/dashboard",
        tag=f"lead-{lead_id}",
    )


async def notify_campaign_response(name: str, action: str, lead_id: str):
    """Push notification when a lead responds to a campaign."""
    base_url = os.environ.get("REACT_APP_BACKEND_URL", "")
    return await send_actionable_push(
        title="Lead Responded",
        body=f"{name} {action}",
        actions=[
            {"action": "followup", "title": "Send Follow-up", "url": f"{base_url}/api/pipeline/approve/{lead_id}", "confirm": "Follow-up sent!"},
            {"action": "view", "title": "View Lead", "url": f"/leads?id={lead_id}", "confirm": ""},
        ],
        url="/dashboard",
        tag=f"response-{lead_id}",
    )


# ═══════════════════════════════════════════════════
# iter 315k — Founder-tier notifications (revenue / signup / NPS)
# Hook into db.founder_notifications so every bell-write also phones TJ.
# ═══════════════════════════════════════════════════
PRIORITY_TYPES = {"revenue", "signup", "nps_alert", "nps_detractor",
                    "payment_recovered", "payment_abandoned"}


async def _emit_founder_push(ntype: str, title: str, subtitle: str = "",
                                  url: Optional[str] = None,
                                  priority: bool = False) -> int:
    """Persist to db.founder_notifications + fan-out VAPID push.

    Emojis prepended per type so the lock-screen preview conveys urgency
    without extra body text. Priority notifications set
    `require_interaction=True` so phone holds the card until tapped.
    """
    from datetime import datetime, timezone
    db = _get_db()
    if db is None:
        return 0
    emoji = {
        "revenue": "🟢",
        "payment_recovered": "🟢",
        "signup": "👤",
        "nps_alert": "⚠️",
        "nps_detractor": "⚠️",
        "payment_abandoned": "🟡",
        "daily_brief": "📊",
        "campaign": "🎯",
        "sites_built": "🔨",
    }.get(ntype, "🔔")
    display_title = f"AUREM · {ntype.replace('_', ' ').title()}"
    display_body = f"{emoji} {title}" + (f" — {subtitle}" if subtitle else "")
    target_url = url or "https://aurem.live/admin/console"
    try:
        await db.founder_notifications.insert_one({
            "type": ntype, "title": title, "subtitle": subtitle,
            "url": target_url, "priority": priority,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "read": False,
        })
    except Exception as e:
        logger.warning(f"[PUSH] founder_notifications persist failed: {e}")
    try:
        payload = {
            "title": display_title, "body": display_body,
            "icon": "/ora-icon.png", "badge": "/ora-badge.png",
            "url": target_url, "tag": f"aurem-{ntype}",
            "require_interaction": priority or ntype in PRIORITY_TYPES,
            "vibrate": [200, 100, 200] if priority else [100],
        }
        return await _send_push_payload(payload)
    except Exception as e:
        logger.warning(f"[PUSH] fan-out failed: {e}")
        return 0


async def _send_push_payload(payload: dict) -> int:
    """Internal fan-out used by _emit_founder_push. Shares retry/cleanup
    logic with send_push_to_all but accepts a full pre-built payload."""
    db = _get_db()
    if db is None:
        return 0
    vapid_private = os.environ.get("VAPID_PRIVATE_KEY", "")
    vapid_subject = os.environ.get("VAPID_SUBJECT", "mailto:support@aurem.ai")
    if not vapid_private:
        logger.warning("[PUSH] VAPID_PRIVATE_KEY not configured")
        return 0
    try:
        from pywebpush import webpush
    except ImportError:
        logger.error("[PUSH] pywebpush not installed")
        return 0
    sent, stale = 0, []
    data = json.dumps(payload)
    cursor = db.push_subscriptions.find({}, {"_id": 0})
    async for sub in cursor:
        try:
            webpush(
                subscription_info={"endpoint": sub["endpoint"],
                                      "keys": sub["keys"]},
                data=data,
                vapid_private_key=vapid_private,
                vapid_claims={"sub": vapid_subject},
            )
            sent += 1
        except Exception as e:
            if any(c in str(e) for c in ["410", "404", "400", "401", "403"]):
                stale.append(sub["endpoint"])
            logger.warning(
                f"[PUSH] send failed {sub['endpoint'][:40]}…: {str(e)[:80]}")
    if stale:
        await db.push_subscriptions.delete_many(
            {"endpoint": {"$in": stale}})
    return sent


# Public helpers — call these anywhere in the backend
async def push_revenue(amount_cad: float, biz: str = "",
                          order_id: str = "") -> int:
    return await _emit_founder_push(
        "revenue",
        f"${amount_cad:.2f} CAD{' from ' + biz if biz else ''}",
        subtitle=f"Order {order_id}" if order_id else "Stripe paid",
        priority=True)


async def push_signup(email: str, plan: str = "", bin_: str = "") -> int:
    return await _emit_founder_push(
        "signup",
        f"{email}",
        subtitle=f"{plan or 'new user'}{' · ' + bin_ if bin_ else ''}",
        priority=True)


async def push_nps_alert(score: int, biz: str = "", site_id: str = "") -> int:
    return await _emit_founder_push(
        "nps_alert",
        f"Detractor {score}/5{' — ' + biz if biz else ''}",
        subtitle=f"site: {site_id}" if site_id else "",
        priority=True)


async def push_daily_brief(summary_line: str) -> int:
    return await _emit_founder_push(
        "daily_brief", summary_line[:80], priority=False)


# ═══════════════════════════════════════════════════
# Test endpoint — founder presses "Enable Notifications"
# then hits this to confirm device is reachable.
# ═══════════════════════════════════════════════════
@router.post("/test")
async def test_push(request: Request, body: Optional[dict] = None):
    """Fire a test notification to all registered subscriptions."""
    body = body or {}
    priority = bool(body.get("priority", True))
    sent = await _emit_founder_push(
        "revenue" if priority else "daily_brief",
        title=body.get("title") or "Test notification",
        subtitle=body.get("subtitle") or "If you see this on your phone, it's working.",
        priority=priority,
    )
    return {"ok": True, "sent": sent,
            "note": "0 sent means no device has subscribed yet — open "
                     "/admin/console on your phone and tap Enable Notifications."}


# ═══════════════════════════════════════════════════
# PIPELINE ACTION ENDPOINTS (for push notification buttons)
# ═══════════════════════════════════════════════════

@router.post("/api/pipeline/approve/{lead_id}")
async def pipeline_approve_lead(lead_id: str):
    """Approve outreach for a lead — called from push notification action buttons."""
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not available")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    # Update lead status in campaign_leads or envoy_outreach
    result = await db.campaign_leads.update_one(
        {"lead_id": lead_id, "business_id": FOUNDER_BIN},
        {"$set": {"status": "approved", "approved_at": now, "approved_via": "push_notification"}},
    )
    if result.modified_count == 0:
        # Try envoy_outreach
        await db.envoy_outreach.update_one(
            {"lead_id": lead_id},
            {"$set": {"status": "approved", "approved_at": now, "approved_via": "push_notification"}},
        )

    # Log to audit
    await db.audit_chain.insert_one({
        "event_type": "lead_approved",
        "description": f"Lead {lead_id} approved via push notification",
        "lead_id": lead_id,
        "timestamp": now,
        "agent": "push_action",
    })

    logger.info(f"[PIPELINE] Lead {lead_id} approved via push notification")
    return {"success": True, "lead_id": lead_id, "action": "approved"}


@router.post("/api/pipeline/skip/{lead_id}")
async def pipeline_skip_lead(lead_id: str):
    """Skip a lead — called from push notification action buttons."""
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not available")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    result = await db.campaign_leads.update_one(
        {"lead_id": lead_id, "business_id": FOUNDER_BIN},
        {"$set": {"status": "skipped", "skipped_at": now, "skipped_via": "push_notification"}},
    )
    if result.modified_count == 0:
        await db.envoy_outreach.update_one(
            {"lead_id": lead_id},
            {"$set": {"status": "skipped", "skipped_at": now, "skipped_via": "push_notification"}},
        )

    await db.audit_chain.insert_one({
        "event_type": "lead_skipped",
        "description": f"Lead {lead_id} skipped via push notification",
        "lead_id": lead_id,
        "timestamp": now,
        "agent": "push_action",
    })

    logger.info(f"[PIPELINE] Lead {lead_id} skipped via push notification")
    return {"success": True, "lead_id": lead_id, "action": "skipped"}


# ═══════════════════════════════════════════════════
# MANUAL PUSH TRIGGERS (for testing)
# ═══════════════════════════════════════════════════

@router.post("/test-lead-notification")
async def test_lead_notification():
    """Test: send a mock new-lead actionable notification."""
    sent = await notify_new_lead("Test Business Co", 42, "test-lead-001")
    return {"sent": sent}


@router.post("/test-repair-notification")
async def test_repair_notification():
    """Test: send a mock repair-complete notification."""
    sent = await notify_repair_complete("https://example.com", 5, 4)
    return {"sent": sent}
