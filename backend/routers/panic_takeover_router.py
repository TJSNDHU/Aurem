"""
Panic Takeover Router
API endpoints for human takeover of AI conversations

Endpoints:
- POST /api/panic/takeover/{conversation_id} - Take control of conversation
- POST /api/panic/resume/{conversation_id} - Resume AI control
- POST /api/panic/resolve/{event_id} - Mark panic event as resolved
- POST /api/panic/send-message - Send manual message while in control
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/panic", tags=["Panic Takeover"])

# MongoDB connection
db = None

def set_db(database):
    global db
    db = database


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
    tenant_id: str = "aurem_platform"  # TODO: Get from JWT
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
    tenant_id: str = "aurem_platform"  # TODO: Get from JWT
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
    tenant_id: str = "aurem_platform"  # TODO: Get from JWT
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
    tenant_id: str = "aurem_platform"  # TODO: Get from JWT
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
