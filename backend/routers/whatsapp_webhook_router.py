"""
AUREM Commercial Platform - WhatsApp Webhook Router
Handles Meta/WhatsApp Cloud API webhooks and business integration

Endpoints:
- GET /api/whatsapp/webhook - Webhook verification (Meta challenge)
- POST /api/whatsapp/webhook - Receive incoming messages and status updates
- GET /api/whatsapp/{business_id}/status - Get connection status
- POST /api/whatsapp/{business_id}/connect - Initiate Embedded Signup
- GET /api/whatsapp/{business_id}/callback - OAuth callback
- POST /api/whatsapp/{business_id}/disconnect - Disconnect WhatsApp
- POST /api/whatsapp/{business_id}/send - Send a message
- GET /api/whatsapp/{business_id}/messages - Get message history
- GET /api/whatsapp/health - Health check
"""

import logging
import os
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Query, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/whatsapp", tags=["AUREM WhatsApp"])

logger = logging.getLogger(__name__)

_db = None


def set_db(db):
    global _db
    _db = db


def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


# ==================== MODELS ====================

class SendTextRequest(BaseModel):
    to: str = Field(..., description="Recipient phone number (E.164 format)")
    text: str = Field(..., description="Message text")
    preview_url: bool = False


class SendTemplateRequest(BaseModel):
    to: str = Field(..., description="Recipient phone number")
    template_name: str = Field(..., description="Pre-approved template name")
    language_code: str = "en_US"
    components: Optional[list] = None


# ==================== HEALTH CHECK ====================

@router.get("/health")
async def health():
    """Health check for WhatsApp service"""
    import os
    
    has_app_id = bool(os.environ.get("META_APP_ID"))
    has_app_secret = bool(os.environ.get("META_APP_SECRET"))
    
    return {
        "status": "healthy",
        "service": "aurem-whatsapp",
        "meta_configured": has_app_id and has_app_secret,
        "capabilities": [
            "embedded_signup",
            "webhook_verification",
            "send_text",
            "send_template",
            "inbox_integration"
        ]
    }


# ==================== WEBHOOK ENDPOINTS ====================

@router.get("/webhook")
async def verify_webhook(
    request: Request,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    """
    Webhook verification endpoint for Meta.
    
    Meta sends a GET request with hub.mode, hub.verify_token, and hub.challenge.
    If the verify_token matches, return the challenge string.
    """
    from services.aurem_commercial.whatsapp_service import get_whatsapp_service
    
    whatsapp = get_whatsapp_service(get_db())
    
    challenge = whatsapp.verify_webhook(hub_mode, hub_verify_token, hub_challenge)
    
    if challenge:
        logger.info("[WhatsApp Webhook] Verification successful")
        return PlainTextResponse(content=challenge)
    
    logger.warning(f"[WhatsApp Webhook] Verification failed - mode: {hub_mode}")
    raise HTTPException(403, "Verification failed")


@router.post("/webhook")
async def receive_webhook(request: Request):
    """
    Receive incoming webhook events from Meta.
    
    Events include:
    - messages: Incoming messages from users
    - statuses: Message delivery status updates (sent, delivered, read, failed)
    - account_update: Account-level events
    """
    from services.aurem_commercial.whatsapp_service import get_whatsapp_service
    
    whatsapp = get_whatsapp_service(get_db())
    
    # Get raw body for signature verification
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    
    # Verify signature
    if not whatsapp.verify_signature(body, signature):
        logger.warning("[WhatsApp Webhook] Invalid signature")
        raise HTTPException(403, "Invalid signature")
    
    # Parse payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON payload")
    
    # Process webhook
    result = await whatsapp.process_webhook(payload)
    
    logger.info(f"[WhatsApp Webhook] Processed: {result}")
    
    # Always return 200 to acknowledge receipt
    return {"status": "ok"}


# ==================== BUSINESS INTEGRATION ====================

@router.get("/{business_id}/status")
async def get_status(business_id: str):
    """
    Get WhatsApp connection status for a business.
    
    Returns connection state, WABA ID, phone number, etc.
    """
    from services.aurem_commercial.whatsapp_service import get_whatsapp_service
    
    whatsapp = get_whatsapp_service(get_db())
    status = await whatsapp.get_connection_status(business_id)
    
    return status


@router.post("/{business_id}/connect")
async def initiate_connection(business_id: str):
    """
    Initiate WhatsApp connection via Meta Embedded Signup.
    
    Returns an OAuth URL that the user should be redirected to.
    The user will authorize the app on Facebook and connect their
    WhatsApp Business Account.
    """
    from services.aurem_commercial.whatsapp_service import get_whatsapp_service
    
    whatsapp = get_whatsapp_service(get_db())
    result = await whatsapp.initiate_embedded_signup(business_id)
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


@router.get("/{business_id}/callback")
async def oauth_callback(
    business_id: str,
    code: str = Query(...),
    state: str = Query(...)
):
    """
    OAuth callback endpoint after Meta Embedded Signup.
    
    Exchanges the authorization code for an access token and
    retrieves WhatsApp Business Account details.
    """
    from services.aurem_commercial.whatsapp_service import get_whatsapp_service
    
    whatsapp = get_whatsapp_service(get_db())
    result = await whatsapp.complete_embedded_signup(business_id, code, state)
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


@router.post("/{business_id}/disconnect")
async def disconnect(business_id: str):
    """
    Disconnect WhatsApp for a business.
    
    Removes access tokens and connection details.
    """
    from services.aurem_commercial.whatsapp_service import get_whatsapp_service
    
    whatsapp = get_whatsapp_service(get_db())
    result = await whatsapp.disconnect(business_id)
    
    return result


# ==================== MESSAGING ====================

@router.post("/{business_id}/send")
async def send_message(
    business_id: str,
    data: SendTextRequest
):
    """
    Send a text message via WhatsApp.
    
    Requires WhatsApp to be connected for the business.
    """
    from services.aurem_commercial.whatsapp_service import get_whatsapp_service
    
    whatsapp = get_whatsapp_service(get_db())
    result = await whatsapp.send_text_message(
        business_id=business_id,
        to_number=data.to,
        text=data.text,
        preview_url=data.preview_url
    )
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


@router.post("/{business_id}/send-template")
async def send_template(
    business_id: str,
    data: SendTemplateRequest
):
    """
    Send a pre-approved template message via WhatsApp.
    
    Template messages are required for initiating conversations
    or sending messages outside the 24-hour window.
    """
    from services.aurem_commercial.whatsapp_service import get_whatsapp_service
    
    whatsapp = get_whatsapp_service(get_db())
    result = await whatsapp.send_template_message(
        business_id=business_id,
        to_number=data.to,
        template_name=data.template_name,
        language_code=data.language_code,
        components=data.components
    )
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


@router.get("/{business_id}/messages")
async def get_messages(
    business_id: str,
    phone: Optional[str] = Query(None, description="Filter by phone number"),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get WhatsApp message history for a business.
    
    Optionally filter by phone number to get a specific conversation.
    """
    from services.aurem_commercial.whatsapp_service import get_whatsapp_service
    
    whatsapp = get_whatsapp_service(get_db())
    messages = await whatsapp.get_message_history(
        business_id=business_id,
        phone_number=phone,
        limit=limit
    )
    
    return {"messages": messages, "count": len(messages)}


# ==================== PHONE NUMBER MANAGEMENT ====================

@router.get("/{business_id}/phone-numbers")
async def get_phone_numbers(business_id: str):
    """
    Get phone numbers associated with the WhatsApp Business Account.
    """
    from services.aurem_commercial.whatsapp_service import get_whatsapp_service
    import httpx
    import os
    
    whatsapp = get_whatsapp_service(get_db())
    connection = await whatsapp.collection.find_one({"business_id": business_id})
    
    if not connection or not connection.get("waba_id"):
        return {"phone_numbers": [], "error": "WhatsApp not connected"}
    
    access_token = connection.get("access_token")
    waba_id = connection.get("waba_id")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://graph.facebook.com/v21.0/{waba_id}/phone_numbers",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if response.status_code == 200:
                data = response.json().get("data", [])
                return {"phone_numbers": data}
            else:
                return {"phone_numbers": [], "error": response.json().get("error", {}).get("message")}
                
    except Exception as e:
        return {"phone_numbers": [], "error": str(e)}


@router.get("/{business_id}/verify-token")
async def get_verify_token(business_id: str):
    """
    Get the webhook verify token for this AUREM instance.
    
    This token should be entered in the Meta App Dashboard
    when configuring webhooks.
    """
    from services.aurem_commercial.whatsapp_service import get_whatsapp_service
    
    whatsapp = get_whatsapp_service(get_db())
    
    return {
        "verify_token": whatsapp.verify_token,
        "webhook_url": f"{os.environ.get('REACT_APP_BACKEND_URL', '')}/api/whatsapp/webhook",
        "instructions": "Enter these values in Meta App Dashboard > WhatsApp > Configuration"
    }
