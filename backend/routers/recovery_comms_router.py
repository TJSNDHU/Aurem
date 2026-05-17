"""
AUREM Omnichannel Recovery Engine
Sends attributed recovery messages via Email, WhatsApp, SMS.
Each message carries a signed aurem_ref tracking link for commission attribution.

Components:
1. Recovery Message Composer — Generates personalized messages per channel
2. Send Engine — Dispatches via channel (mock for now)
3. Campaign Manager — Bulk send to customer segments
4. Recovery Dashboard — Track sent/opened/converted
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import os
import secrets
import logging
import jwt
import hmac
import hashlib
import base64
import json

router = APIRouter()
logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET")
BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "")


def _extract_tenant(authorization: str) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(403, "Authorization required")
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        tenant_id = payload.get("tenant_id") or payload.get("user_id")
        user_id = payload.get("user_id")
        if not tenant_id:
            raise HTTPException(403, "Tenant context required")
        return {"tenant_id": tenant_id, "user_id": user_id}
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


def _generate_tracking_link(user_id: str, customer_email: str, channel: str, campaign_id: str) -> dict:
    """Generate a signed aurem_ref tracking link for attribution."""
    ref_id = f"TRACK-{secrets.token_hex(8).upper()}"
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=30)

    payload = {
        "ref_id": ref_id,
        "user_id": user_id,
        "email": customer_email,
        "channel": channel,
        "campaign_id": campaign_id,
        "created": now.isoformat(),
        "expires": expires.isoformat(),
    }

    payload_json = json.dumps(payload, sort_keys=True)
    signature = hmac.new(
        (JWT_SECRET or "fallback").encode(),
        payload_json.encode(),
        hashlib.sha256
    ).digest()
    token = base64.urlsafe_b64encode(signature).decode().rstrip("=")

    tracking_url = f"{BACKEND_URL}/api/attribution/click/{ref_id}?sig={token}"
    return {"ref_id": ref_id, "tracking_url": tracking_url, "payload": payload}


# ═══════════════════════════════════════════════════════════════
# MESSAGE TEMPLATES
# ═══════════════════════════════════════════════════════════════


async def _mock_send(channel: str, recipient: str, message: dict) -> dict:
    """Stub: simulate message delivery. Replace with real Twilio/Resend/WhatsApp integration."""
    import secrets as _s
    logging.warning(f"_mock_send not implemented — skipping ({channel} to {recipient})")
    return {"message_id": f"mock_{_s.token_urlsafe(8)}", "status": "simulated", "channel": channel}


def _compose_message(channel: str, customer: dict, tracking_url: str, campaign_type: str) -> dict:
    name = customer.get("first_name", "there")
    company = customer.get("company", "your business")

    if campaign_type == "abandoned_cart":
        templates = {
            "email": {
                "subject": f"You left something behind, {name}",
                "body": f"Hi {name},\n\nWe noticed you didn't complete your purchase. Your cart is still waiting for you!\n\nComplete your order now: {tracking_url}\n\nBest,\nThe {company} Team",
            },
            "whatsapp": {
                "body": f"Hi {name}! You left items in your cart. Complete your purchase here: {tracking_url}",
            },
            "sms": {
                "body": f"{name}, your cart is waiting! Complete your order: {tracking_url}",
            },
        }
    elif campaign_type == "win_back":
        templates = {
            "email": {
                "subject": f"We miss you, {name}!",
                "body": f"Hi {name},\n\nIt's been a while since your last visit. We have something special for you.\n\nCheck it out: {tracking_url}\n\nBest regards",
            },
            "whatsapp": {
                "body": f"Hey {name}! We miss you. Here's something special just for you: {tracking_url}",
            },
            "sms": {
                "body": f"{name}, we miss you! Special offer: {tracking_url}",
            },
        }
    elif campaign_type == "new_offer":
        templates = {
            "email": {
                "subject": f"Exclusive offer for {name}",
                "body": f"Hi {name},\n\nWe have a new exclusive offer for you.\n\nClaim it here: {tracking_url}\n\nDon't miss out!",
            },
            "whatsapp": {
                "body": f"Hi {name}! Exclusive offer just for you: {tracking_url}",
            },
            "sms": {
                "body": f"{name}, exclusive deal: {tracking_url}",
            },
        }
    else:
        templates = {
            "email": {
                "subject": "A message from your team",
                "body": f"Hi {name},\n\nWe have something for you: {tracking_url}\n\nBest regards",
            },
            "whatsapp": {"body": f"Hi {name}! Check this out: {tracking_url}"},
            "sms": {"body": f"{name}: {tracking_url}"},
        }

    return templates.get(channel, templates.get("email", {}))


# ═══════════════════════════════════════════════════════════════
# DIY SEND ENGINE — Gmail + Meta WhatsApp Cloud API
# ═══════════════════════════════════════════════════════════════

async def _real_send(channel: str, recipient: str, message: dict, tenant_id: str) -> dict:
    """
    Send messages via the existing DIY infrastructure:
      - Email: GmailService (tenant's connected Gmail via OAuth)
      - WhatsApp: Meta Cloud API (WhatsApp Business, free tier)
      - SMS: Click-to-Chat fallback (logged but not auto-sent)
    """
    from server import db
    msg_id = f"msg_{secrets.token_hex(8)}"
    now = datetime.now(timezone.utc).isoformat()

    try:
        if channel == "email":
            from shared.commercial.gmail_service import get_gmail_service
            gmail = get_gmail_service(db)

            subject = message.get("subject", "A message from your team")
            body_text = message.get("body", "")

            result = await gmail.send_email(
                business_id=tenant_id,
                to=recipient,
                subject=subject,
                body_text=body_text,
            )

            if result.get("success") or result.get("message_id"):
                return {
                    "status": "delivered",
                    "channel": "email",
                    "recipient": recipient,
                    "message_id": result.get("message_id", msg_id),
                    "delivered_at": now,
                    "provider": "gmail_diy",
                }
            else:
                error = result.get("error", "Gmail send failed")
                logger.warning(f"[CommsEngine] Gmail send failed: {error}")
                return {"status": "failed", "channel": "email", "recipient": recipient, "message_id": msg_id, "error": error}

        elif channel == "whatsapp":
            from shared.commercial.whatsapp_service import get_whatsapp_service
            wa = get_whatsapp_service(db)

            body_text = message.get("body", "")
            result = await wa.send_text_message(
                business_id=tenant_id,
                to_number=recipient,
                text=body_text,
            )

            if result.get("success") or result.get("message_id"):
                return {
                    "status": "delivered",
                    "channel": "whatsapp",
                    "recipient": recipient,
                    "message_id": result.get("message_id", msg_id),
                    "delivered_at": now,
                    "provider": "meta_cloud_api",
                }
            else:
                error = result.get("error", "WhatsApp send failed")
                logger.warning(f"[CommsEngine] WhatsApp send failed: {error}")
                return {"status": "failed", "channel": "whatsapp", "recipient": recipient, "message_id": msg_id, "error": error}

        elif channel == "sms":
            # SMS: Log for manual follow-up via click-to-chat URL
            wa_link = f"https://wa.me/{recipient.replace('+', '')}?text={message.get('body', '')[:200]}"
            logger.info(f"[CommsEngine] SMS fallback → WhatsApp click-to-chat: {wa_link}")
            return {
                "status": "logged",
                "channel": "sms",
                "recipient": recipient,
                "message_id": msg_id,
                "delivered_at": now,
                "provider": "click_to_chat_fallback",
                "wa_link": wa_link,
            }

        else:
            return {"status": "failed", "channel": channel, "recipient": recipient, "message_id": msg_id, "error": f"Unknown channel: {channel}"}

    except Exception as e:
        logger.error(f"[CommsEngine] Send error ({channel}): {e}")
        return {"status": "failed", "channel": channel, "recipient": recipient, "message_id": msg_id, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════

class SendRecoveryRequest(BaseModel):
    customer_id: str
    channel: str = "email"  # email | whatsapp | sms
    campaign_type: str = "abandoned_cart"  # abandoned_cart | win_back | new_offer | custom
    custom_message: Optional[str] = ""
    destination_url: Optional[str] = ""


class BulkRecoveryRequest(BaseModel):
    customer_ids: Optional[List[str]] = []
    source_filter: Optional[str] = ""  # shopify_sync | hubspot_sync | all
    channel: str = "email"
    campaign_type: str = "abandoned_cart"
    limit: Optional[int] = 50


class CreateCampaignRequest(BaseModel):
    name: str
    channel: str = "email"
    campaign_type: str = "abandoned_cart"
    source_filter: Optional[str] = ""
    tags_filter: Optional[List[str]] = []
    limit: Optional[int] = 100


@router.post("/api/comms/send-recovery")
async def send_recovery_message(body: SendRecoveryRequest, authorization: str = Header(None)):
    """Send a single recovery message to a customer with attribution tracking."""
    from server import db
    ctx = _extract_tenant(authorization)

    customer = await db.tenant_customers.find_one(
        {"customer_id": body.customer_id, "tenant_id": ctx["tenant_id"], "is_active": True},
        {"_id": 0}
    )
    if not customer:
        raise HTTPException(404, "Customer not found")

    if customer.get("ccpa_opt_out"):
        raise HTTPException(400, "Customer has opted out of communications")

    email = customer.get("email", "")
    phone = customer.get("phone", "")
    recipient = email if body.channel == "email" else phone

    if not recipient:
        raise HTTPException(400, f"No {body.channel} contact info for this customer")

    # Generate attribution tracking link
    campaign_id = f"camp_{secrets.token_hex(6)}"
    link_data = _generate_tracking_link(ctx["user_id"], email, body.channel, campaign_id)

    # Store tracking link in DB
    now = datetime.now(timezone.utc).isoformat()
    await db.tracking_links.insert_one({
        "ref_id": link_data["ref_id"],
        "user_id": ctx["user_id"],
        "tenant_id": ctx["tenant_id"],
        "customer_id": body.customer_id,
        "customer_email": email,
        "channel": body.channel,
        "campaign_id": campaign_id,
        "campaign_type": body.campaign_type,
        "destination_url": body.destination_url or "",
        "tracking_url": link_data["tracking_url"],
        "clicked": False,
        "converted": False,
        "created_at": now,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    })

    # Compose message
    if body.custom_message:
        message = {"body": body.custom_message.replace("{link}", link_data["tracking_url"])}
        if body.channel == "email":
            message["subject"] = "A message from your team"
    else:
        message = _compose_message(body.channel, customer, link_data["tracking_url"], body.campaign_type)

    # Send via DIY engine (Gmail / WhatsApp / SMS fallback)
    delivery = await _real_send(body.channel, recipient, message, ctx["tenant_id"])

    # Store sent message
    await db.sent_messages.insert_one({
        "message_id": delivery["message_id"],
        "tenant_id": ctx["tenant_id"],
        "user_id": ctx["user_id"],
        "customer_id": body.customer_id,
        "customer_email": email,
        "channel": body.channel,
        "campaign_id": campaign_id,
        "campaign_type": body.campaign_type,
        "ref_id": link_data["ref_id"],
        "tracking_url": link_data["tracking_url"],
        "message_content": message,
        "delivery_status": delivery["status"],
        "sent_at": now,
        "delivered_at": delivery.get("delivered_at"),
    })

    return {
        "message_id": delivery["message_id"],
        "customer_id": body.customer_id,
        "channel": body.channel,
        "delivery_status": delivery["status"],
        "tracking_url": link_data["tracking_url"],
        "ref_id": link_data["ref_id"],
        "message": f"Recovery message sent via {body.channel} to {recipient}",
    }


@router.post("/api/comms/bulk-recovery")
async def send_bulk_recovery(body: BulkRecoveryRequest, authorization: str = Header(None)):
    """Send recovery messages to multiple customers in a campaign."""
    from server import db
    ctx = _extract_tenant(authorization)
    now = datetime.now(timezone.utc).isoformat()

    campaign_id = f"camp_{secrets.token_hex(8)}"

    # Get target customers
    if body.customer_ids:
        query = {"tenant_id": ctx["tenant_id"], "customer_id": {"$in": body.customer_ids}, "is_active": True}
    else:
        query = {"tenant_id": ctx["tenant_id"], "is_active": True, "ccpa_opt_out": {"$ne": True}}
        if body.source_filter and body.source_filter != "all":
            query["source"] = body.source_filter

    customers = await db.tenant_customers.find(
        query, {"_id": 0}
    ).limit(body.limit).to_list(body.limit)

    sent = 0
    failed = 0
    skipped = 0

    for customer in customers:
        email = customer.get("email", "")
        phone = customer.get("phone", "")
        recipient = email if body.channel == "email" else phone

        if not recipient or customer.get("ccpa_opt_out"):
            skipped += 1
            continue

        link_data = _generate_tracking_link(ctx["user_id"], email, body.channel, campaign_id)

        await db.tracking_links.insert_one({
            "ref_id": link_data["ref_id"],
            "user_id": ctx["user_id"],
            "tenant_id": ctx["tenant_id"],
            "customer_id": customer["customer_id"],
            "customer_email": email,
            "channel": body.channel,
            "campaign_id": campaign_id,
            "campaign_type": body.campaign_type,
            "tracking_url": link_data["tracking_url"],
            "clicked": False,
            "converted": False,
            "created_at": now,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        })

        message = _compose_message(body.channel, customer, link_data["tracking_url"], body.campaign_type)
        delivery = await _mock_send(body.channel, recipient, message)

        await db.sent_messages.insert_one({
            "message_id": delivery["message_id"],
            "tenant_id": ctx["tenant_id"],
            "user_id": ctx["user_id"],
            "customer_id": customer["customer_id"],
            "customer_email": email,
            "channel": body.channel,
            "campaign_id": campaign_id,
            "campaign_type": body.campaign_type,
            "ref_id": link_data["ref_id"],
            "tracking_url": link_data["tracking_url"],
            "message_content": message,
            "delivery_status": delivery["status"],
            "sent_at": now,
            "delivered_at": delivery.get("delivered_at"),
        })

        if delivery["status"] == "delivered":
            sent += 1
        else:
            failed += 1

    # Store campaign record
    await db.recovery_campaigns.insert_one({
        "campaign_id": campaign_id,
        "tenant_id": ctx["tenant_id"],
        "user_id": ctx["user_id"],
        "name": f"{body.campaign_type.replace('_', ' ').title()} — {body.channel.upper()}",
        "channel": body.channel,
        "campaign_type": body.campaign_type,
        "total_targeted": len(customers),
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "clicked": 0,
        "converted": 0,
        "status": "completed",
        "created_at": now,
    })

    return {
        "campaign_id": campaign_id,
        "channel": body.channel,
        "campaign_type": body.campaign_type,
        "total_targeted": len(customers),
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "message": f"Bulk recovery: {sent} messages sent via {body.channel}, {failed} failed, {skipped} skipped",
    }


@router.get("/api/comms/campaigns")
async def list_campaigns(authorization: str = Header(None)):
    """List all recovery campaigns for the current tenant."""
    from server import db
    ctx = _extract_tenant(authorization)

    campaigns = await db.recovery_campaigns.find(
        {"tenant_id": ctx["tenant_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)

    return {"campaigns": campaigns, "total": len(campaigns)}


@router.get("/api/comms/sent-messages")
async def list_sent_messages(
    authorization: str = Header(None),
    campaign_id: Optional[str] = None,
    channel: Optional[str] = None,
    limit: int = 50,
):
    """List sent messages for the tenant."""
    from server import db
    ctx = _extract_tenant(authorization)

    query = {"tenant_id": ctx["tenant_id"]}
    if campaign_id:
        query["campaign_id"] = campaign_id
    if channel:
        query["channel"] = channel

    messages = await db.sent_messages.find(
        query, {"_id": 0}
    ).sort("sent_at", -1).limit(limit).to_list(limit)

    return {"messages": messages, "total": len(messages)}


@router.get("/api/comms/stats")
async def comm_stats(authorization: str = Header(None)):
    """Get communication stats overview."""
    from server import db
    ctx = _extract_tenant(authorization)
    tid = ctx["tenant_id"]

    total_sent = await db.sent_messages.count_documents({"tenant_id": tid})
    delivered = await db.sent_messages.count_documents({"tenant_id": tid, "delivery_status": "delivered"})
    total_campaigns = await db.recovery_campaigns.count_documents({"tenant_id": tid})

    # Channel breakdown
    channels = await db.sent_messages.aggregate([
        {"$match": {"tenant_id": tid}},
        {"$group": {"_id": "$channel", "count": {"$sum": 1}}},
    ]).to_list(10)

    # Click tracking from tracking_links
    total_clicks = await db.tracking_links.count_documents({"tenant_id": tid, "clicked": True})
    total_links = await db.tracking_links.count_documents({"tenant_id": tid})

    return {
        "total_sent": total_sent,
        "delivered": delivered,
        "delivery_rate": round(delivered / total_sent * 100, 1) if total_sent > 0 else 0,
        "total_campaigns": total_campaigns,
        "total_clicks": total_clicks,
        "click_rate": round(total_clicks / total_links * 100, 1) if total_links > 0 else 0,
        "channels": {c["_id"]: c["count"] for c in channels},
    }
