"""
Panic Takeover Router
API endpoints for human takeover of AI conversations

Endpoints:
- POST /api/panic/takeover/{conversation_id} - Take control of conversation
- POST /api/panic/resume/{conversation_id} - Resume AI control
- POST /api/panic/resolve/{event_id} - Mark panic event as resolved
- POST /api/panic/send-message - Send manual message while in control
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import logging
import os

from utils.tenant import current_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/panic", tags=["Panic Takeover"])

# MongoDB connection
db = None

def set_db(database):
    global db
    db = database


# Bug-fix #77 — previously these endpoints relied on `current_tenant()`
# which silently falls back to "aurem_platform" when the request has no
# JWT. That meant an attacker could POST /api/panic/takeover/{id} +
# /api/panic/send-message with NO auth and inject messages stored as
# role:"assistant" delivered to customers as if from the business owner
# (social-engineering at scale). Now we require a real JWT for every
# panic route.
def _require_tenant(request: Request) -> str:
    import jwt as _jwt
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise HTTPException(503, "Auth not configured")
    try:
        payload = _jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
    except _jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except _jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    tid = (
        payload.get("tenant_id") or payload.get("business_id")
        or payload.get("sub") or payload.get("email") or ""
    )
    if not tid:
        raise HTTPException(403, "No tenant in token")
    return tid


class ManualMessage(BaseModel):
    """Manual message from business owner"""
    conversation_id: str
    message: str
    sender_name: Optional[str] = "Business Owner"


class ResolveEvent(BaseModel):
    """Resolve panic event"""
    resolution_notes: Optional[str] = None


@router.post("/takeover/{conversation_id}")
async def take_control(
    conversation_id: str,
    tenant_id: str = Depends(_require_tenant)
):
    """
    Take manual control of a conversation (pause AI)
    
    Returns:
        {
            "success": true,
            "conversation_id": str,
            "status": "human_controlling"
        }
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Update conversation status
        result = await db.conversations.update_one(
            {"conversation_id": conversation_id},
            {"$set": {
                "ai_paused": True,
                "needs_human_intervention": True,
                "human_in_control": True,
                "taken_over_at": datetime.now(timezone.utc)
            }},
            upsert=True
        )
        
        # Update associated panic event
        await db.panic_events.update_one(
            {"conversation_id": conversation_id, "status": "triggered"},
            {"$set": {
                "status": "human_controlling",
                "taken_over_at": datetime.now(timezone.utc)
            }}
        )
        
        logger.info(f"[PanicTakeover] Human took control of {conversation_id}")
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "status": "human_controlling",
            "message": "You are now in control. AI responses are paused."
        }
    
    except Exception as e:
        logger.error(f"[PanicTakeover] Error taking control: {e}")
        raise HTTPException(500, str(e))


@router.post("/resume/{conversation_id}")
async def resume_ai_control(
    conversation_id: str,
    tenant_id: str = Depends(_require_tenant)
):
    """
    Resume AI control of conversation
    
    Returns:
        {
            "success": true,
            "conversation_id": str,
            "status": "ai_active"
        }
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Update conversation status
        await db.conversations.update_one(
            {"conversation_id": conversation_id},
            {"$set": {
                "ai_paused": False,
                "needs_human_intervention": False,
                "human_in_control": False,
                "resumed_at": datetime.now(timezone.utc)
            }}
        )
        
        logger.info(f"[PanicTakeover] AI control resumed for {conversation_id}")
        
        return {
            "success": True,
            "conversation_id": conversation_id,
            "status": "ai_active",
            "message": "AI control resumed. Bot will respond to new messages."
        }
    
    except Exception as e:
        logger.error(f"[PanicTakeover] Error resuming AI: {e}")
        raise HTTPException(500, str(e))


@router.post("/resolve/{event_id}")
async def resolve_panic_event(
    event_id: str,
    resolution: ResolveEvent,
    tenant_id: str = Depends(_require_tenant)
):
    """
    Mark panic event as resolved
    
    Body:
        {
            "resolution_notes": "Optional notes about resolution"
        }
    
    Returns:
        {
            "success": true,
            "event_id": str,
            "status": "resolved"
        }
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Update panic event
        result = await db.panic_events.update_one(
            {"event_id": event_id, "tenant_id": tenant_id},
            {"$set": {
                "status": "resolved",
                "resolved_at": datetime.now(timezone.utc),
                "resolution_notes": resolution.resolution_notes
            }}
        )
        
        if result.matched_count == 0:
            raise HTTPException(404, "Panic event not found")
        
        logger.info(f"[PanicTakeover] Panic event {event_id} resolved")
        
        return {
            "success": True,
            "event_id": event_id,
            "status": "resolved"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PanicTakeover] Error resolving event: {e}")
        raise HTTPException(500, str(e))


@router.post("/send-message")
async def send_manual_message(
    message: ManualMessage,
    tenant_id: str = Depends(_require_tenant)
):
    """
    Send a manual message while in human control mode
    
    Body:
        {
            "conversation_id": str,
            "message": str,
            "sender_name": "Business Owner" (optional)
        }
    
    Returns:
        {
            "success": true,
            "message_id": str
        }
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Check if human is in control
        conversation = await db.conversations.find_one(
            {"conversation_id": message.conversation_id},
            {"_id": 0, "human_in_control": 1}
        )
        
        if not conversation or not conversation.get("human_in_control"):
            raise HTTPException(403, "Must take control before sending manual messages")
        
        # Store manual message in conversation history
        import uuid
        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        
        message_doc = {
            "message_id": message_id,
            "conversation_id": message.conversation_id,
            "tenant_id": tenant_id,
            "role": "assistant",  # Goes to customer as if from AI
            "content": message.message,
            "sender": message.sender_name,
            "manual_message": True,
            "sent_at": datetime.now(timezone.utc)
        }
        
        await db.messages.insert_one(message_doc)
        
        logger.info(f"[PanicTakeover] Manual message sent to {message.conversation_id}")
        
        # TODO: Actually send the message via appropriate channel (WhatsApp, SMS, etc.)
        # This would integrate with your existing messaging services
        
        return {
            "success": True,
            "message_id": message_id,
            "sent_at": message_doc["sent_at"].isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PanicTakeover] Error sending manual message: {e}")
        raise HTTPException(500, str(e))
