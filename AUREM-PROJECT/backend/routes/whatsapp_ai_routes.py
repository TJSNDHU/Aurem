"""
WhatsApp AI Assistant API Routes
Admin panel endpoints for managing the WhatsApp AI auto-reply bot.
"""

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/whatsapp-ai", tags=["WhatsApp AI"])

# Database reference (set by main server)
db = None


def set_db(database):
    """Set the database reference."""
    global db
    db = database


# ============= Pydantic Models =============

class AISettings(BaseModel):
    enabled: bool = False
    mode: str = "brand"  # "brand" or "personal"
    provider: str = "openai"  # "openai" or "anthropic"
    model: Optional[str] = None
    auto_reply_delay_ms: int = 1000
    excluded_contacts: List[str] = []
    business_hours_only: bool = False
    business_hours: Dict[str, str] = {"start": "09:00", "end": "18:00"}


class BrandVoiceConfig(BaseModel):
    brand_name: str = "ReRoots"
    tone: str = "friendly and knowledgeable"
    personality_traits: List[str] = ["helpful", "skincare-expert", "warm"]
    key_phrases: List[str] = []
    avoid_phrases: List[str] = []
    response_guidelines: List[str] = []
    product_knowledge: str = ""


class TestMessageRequest(BaseModel):
    message: str
    provider: str = "openai"
    mode: str = "brand"


class ConversationQuery(BaseModel):
    phone: Optional[str] = None
    limit: int = 50
    offset: int = 0


# ============= Helper Functions =============

async def get_assistant():
    """Get the WhatsApp AI Assistant instance."""
    from services.whatsapp_ai_assistant import init_whatsapp_assistant
    return await init_whatsapp_assistant(db)


# ============= API Endpoints =============

@router.get("/settings")
async def get_settings(request: Request):
    """Get current WhatsApp AI settings."""
    assistant = await get_assistant()
    return {
        "settings": assistant.settings,
        "brand_voice": assistant.brand_voice.config,
        "style_patterns": assistant.style_analyzer.patterns
    }


@router.put("/settings")
async def update_settings(settings: AISettings, request: Request):
    """Update WhatsApp AI settings."""
    assistant = await get_assistant()
    assistant.settings.update(settings.model_dump())
    await assistant.save_settings()
    
    return {"success": True, "settings": assistant.settings}


@router.put("/brand-voice")
async def update_brand_voice(config: BrandVoiceConfig, request: Request):
    """Update brand voice configuration."""
    assistant = await get_assistant()
    assistant.brand_voice.set_config(config.model_dump())
    await assistant.save_brand_voice()
    
    return {"success": True, "brand_voice": assistant.brand_voice.config}


@router.post("/upload-chat-history")
async def upload_chat_history(
    request: Request,
    file: UploadFile = File(...),
    is_closest_person: bool = Form(False)
):
    """
    Upload WhatsApp chat export to learn texting style.
    
    Args:
        file: .txt file exported from WhatsApp
        is_closest_person: If True, give extra weight to this chat's style
    """
    if not file.filename.endswith('.txt'):
        raise HTTPException(status_code=400, detail="Only .txt files are supported")
    
    try:
        content = await file.read()
        chat_text = content.decode('utf-8')
        
        assistant = await get_assistant()
        patterns = assistant.style_analyzer.analyze_chat_export(chat_text, is_closest_person)
        await assistant.save_style_patterns()
        
        return {
            "success": True,
            "message": "Chat history analyzed successfully",
            "patterns": patterns,
            "sample_count": len(assistant.style_analyzer.sample_messages)
        }
        
    except Exception as e:
        logger.error(f"Error processing chat export: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-reply")
async def test_reply(req: TestMessageRequest, request: Request):
    """
    Test the AI reply without sending to WhatsApp.
    Useful for testing style and configuration.
    """
    from services.whatsapp_ai_assistant import get_or_create_chat_session, UserMessage
    
    assistant = await get_assistant()
    
    # Temporarily update settings for test
    original_provider = assistant.settings["provider"]
    original_mode = assistant.settings["mode"]
    
    assistant.settings["provider"] = req.provider
    assistant.settings["mode"] = req.mode
    
    try:
        # Create a test session
        session_id = f"test_{datetime.now().timestamp()}"
        chat = await get_or_create_chat_session(
            session_id=session_id,
            system_message=assistant.get_system_prompt(),
            provider=req.provider,
            model=assistant.settings.get("model")
        )
        
        user_message = UserMessage(text=req.message)
        reply = await chat.send_message(user_message)
        
        # Clear test session
        from services.whatsapp_ai_assistant import clear_chat_session
        clear_chat_session(session_id)
        
        return {
            "success": True,
            "input": req.message,
            "reply": reply,
            "provider": req.provider,
            "mode": req.mode
        }
        
    finally:
        # Restore original settings
        assistant.settings["provider"] = original_provider
        assistant.settings["mode"] = original_mode


@router.get("/conversations")
async def get_conversations(
    phone: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    request: Request = None
):
    """Get conversation history."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    query = {}
    if phone:
        query["phone"] = phone
    
    conversations = await db.whatsapp_conversations.find(query)\
        .sort("timestamp", -1)\
        .skip(offset)\
        .limit(limit)\
        .to_list(limit)
    
    # Convert ObjectId to string
    for conv in conversations:
        conv["_id"] = str(conv["_id"])
        if "timestamp" in conv:
            conv["timestamp"] = conv["timestamp"].isoformat()
    
    total = await db.whatsapp_conversations.count_documents(query)
    
    return {
        "conversations": conversations,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/conversations/contacts")
async def get_conversation_contacts(request: Request):
    """Get list of unique contacts with conversation counts."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    pipeline = [
        {"$group": {
            "_id": "$phone",
            "message_count": {"$sum": 1},
            "last_message": {"$max": "$timestamp"},
            "ai_replies": {"$sum": {"$cond": [{"$eq": ["$ai_generated", True]}, 1, 0]}}
        }},
        {"$sort": {"last_message": -1}},
        {"$limit": 100}
    ]
    
    contacts = await db.whatsapp_conversations.aggregate(pipeline).to_list(100)
    
    for contact in contacts:
        contact["phone"] = contact.pop("_id")
        if contact.get("last_message"):
            contact["last_message"] = contact["last_message"].isoformat()
    
    return {"contacts": contacts}


@router.delete("/conversations/{phone}")
async def clear_conversation(phone: str, request: Request):
    """Clear conversation history for a specific phone number."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    result = await db.whatsapp_conversations.delete_many({"phone": phone})
    
    # Also clear the chat session
    from services.whatsapp_ai_assistant import clear_chat_session
    clear_chat_session(f"whatsapp_{phone}")
    
    return {
        "success": True,
        "deleted_count": result.deleted_count
    }


@router.post("/webhook")
async def whapi_webhook(request: Request):
    """
    WHAPI webhook endpoint for receiving incoming messages.
    Configure this URL in your WHAPI dashboard.
    """
    try:
        webhook_data = await request.json()
        
        assistant = await get_assistant()
        reply = await assistant.handle_webhook(webhook_data)
        
        return {
            "success": True,
            "reply_sent": reply is not None
        }
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"success": False, "error": str(e)}


@router.get("/stats")
async def get_stats(request: Request):
    """Get WhatsApp AI statistics."""
    if db is None:
        return {
            "total_conversations": 0,
            "total_ai_replies": 0,
            "unique_contacts": 0,
            "today_messages": 0
        }
    
    from datetime import timedelta
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    total = await db.whatsapp_conversations.count_documents({})
    ai_replies = await db.whatsapp_conversations.count_documents({"ai_generated": True})
    
    unique_contacts = len(await db.whatsapp_conversations.distinct("phone"))
    
    today_messages = await db.whatsapp_conversations.count_documents({
        "timestamp": {"$gte": today_start}
    })
    
    return {
        "total_conversations": total,
        "total_ai_replies": ai_replies,
        "unique_contacts": unique_contacts,
        "today_messages": today_messages
    }


@router.post("/toggle")
async def toggle_assistant(request: Request):
    """Quick toggle to enable/disable the AI assistant."""
    assistant = await get_assistant()
    assistant.settings["enabled"] = not assistant.settings["enabled"]
    await assistant.save_settings()
    
    return {
        "success": True,
        "enabled": assistant.settings["enabled"]
    }


@router.post("/switch-provider")
async def switch_provider(provider: str, model: Optional[str] = None, request: Request = None):
    """Switch between OpenAI, Claude, and Gemini."""
    if provider not in ["openai", "anthropic", "gemini"]:
        raise HTTPException(status_code=400, detail="Provider must be 'openai', 'anthropic', or 'gemini'")
    
    assistant = await get_assistant()
    assistant.settings["provider"] = provider
    if model:
        assistant.settings["model"] = model
    else:
        # Clear model to use default for the new provider
        assistant.settings["model"] = None
    await assistant.save_settings()
    
    # Return the default model for each provider
    default_models = {
        "openai": "gpt-4o",
        "anthropic": "claude-sonnet-4-5-20250929",
        "gemini": "gemini-2.0-flash"
    }
    
    return {
        "success": True,
        "provider": provider,
        "model": model or default_models.get(provider, "gpt-4o")
    }
