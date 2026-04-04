"""
Vapi Voice Integration Router
Webhooks for Vapi Voice-to-Voice AI integration with Tone Sync

Endpoints:
- POST /api/voice/sentiment - Receive live transcript and return tone adjustment
- POST /api/voice/webhook - General Vapi webhook handler
- GET  /api/voice/config - Get voice AI configuration for tenant
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["Vapi Voice AI"])

# MongoDB connection
db = None

def set_db(database):
    global db
    db = database


class VapiTranscript(BaseModel):
    """Vapi live transcript webhook payload"""
    conversation_id: str
    tenant_id: str = "aurem_platform"  # Will come from Vapi metadata
    transcript: str
    speaker: str = "user"  # "user" or "assistant"
    timestamp: Optional[str] = None


class VoiceConfigUpdate(BaseModel):
    """Update voice AI configuration"""
    dynamic_tone: bool = True
    vibe_preference: str = "mirror"  # mirror, de-escalate, concierge


@router.post("/sentiment")
async def analyze_voice_sentiment(payload: VapiTranscript):
    """
    Receive live transcript from Vapi and return tone adjustment
    
    This is called by Vapi in real-time during voice conversations
    
    Body:
        {
            "conversation_id": str,
            "tenant_id": str,
            "transcript": str,
            "speaker": "user" | "assistant",
            "timestamp": str (optional)
        }
    
    Returns:
        {
            "success": true,
            "sentiment_score": float,
            "vibe_label": str,
            "recommended_tone": str,
            "vapi_metadata": {
                "system_prompt_addition": str,
                "voice_settings": {...}
            },
            "should_alert": bool
        }
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        from services.tone_sync_service import get_tone_sync_service
        
        tone_sync = get_tone_sync_service(db)
        
        result = await tone_sync.analyze_voice_sentiment(
            tenant_id=payload.tenant_id,
            conversation_id=payload.conversation_id,
            transcript=payload.transcript,
            speaker=payload.speaker
        )
        
        if "error" in result:
            raise HTTPException(500, result["error"])
        
        # If panic detected, trigger alert
        if result.get("should_alert"):
            logger.warning(f"[VapiVoice] 🚨 PANIC detected in voice call {payload.conversation_id}")
            
            # Trigger panic hook for voice conversation
            from services.aurem_hooks.panic_hook import get_panic_hook
            
            panic_hook = get_panic_hook(db)
            
            # Build conversation history for voice
            conversation_history = [
                {"role": "user", "content": payload.transcript}
            ]
            
            await panic_hook.execute(
                tenant_id=payload.tenant_id,
                conversation_id=payload.conversation_id,
                conversation_history=conversation_history,
                latest_user_message=payload.transcript,
                latest_ai_response="[Voice conversation - AI adjusting tone]",
                metadata={
                    "source": "voice",
                    "vibe_label": result["vibe_label"],
                    "customer": {"name": "Voice Caller", "phone": "N/A", "email": "N/A"}
                }
            )
        
        return {
            "success": True,
            **result
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[VapiVoice] Sentiment analysis error: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.post("/webhook")
async def vapi_webhook_handler(request: Request):
    """
    General Vapi webhook handler
    
    Receives various events from Vapi:
    - call.started
    - call.ended
    - transcript.updated
    - function.called
    
    This endpoint can be configured in Vapi dashboard
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        payload = await request.json()
        
        event_type = payload.get("type")
        conversation_id = payload.get("call", {}).get("id", "unknown")
        
        logger.info(f"[VapiVoice] Webhook received: {event_type} for {conversation_id}")
        
        # Handle different event types
        if event_type == "call.started":
            # Log call start
            await db.voice_calls.insert_one({
                "conversation_id": conversation_id,
                "status": "started",
                "started_at": datetime.now(timezone.utc),
                "call_data": payload.get("call", {})
            })
        
        elif event_type == "call.ended":
            # Update call end
            await db.voice_calls.update_one(
                {"conversation_id": conversation_id},
                {"$set": {
                    "status": "ended",
                    "ended_at": datetime.now(timezone.utc),
                    "duration_seconds": payload.get("call", {}).get("duration")
                }},
                upsert=True
            )
        
        elif event_type == "transcript.updated":
            # Process transcript for tone sync
            transcript = payload.get("transcript", {}).get("text", "")
            speaker = payload.get("transcript", {}).get("role", "user")
            
            if transcript:
                # Analyze sentiment
                from services.tone_sync_service import get_tone_sync_service
                
                tone_sync = get_tone_sync_service(db)
                
                result = await tone_sync.analyze_voice_sentiment(
                    tenant_id="aurem_platform",  # TODO: Get from Vapi metadata
                    conversation_id=conversation_id,
                    transcript=transcript,
                    speaker=speaker
                )
                
                # Return tone adjustment to Vapi
                return {
                    "success": True,
                    "tone_adjustment": result.get("vapi_metadata", {})
                }
        
        return {"success": True, "event_type": event_type}
    
    except Exception as e:
        logger.error(f"[VapiVoice] Webhook error: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.get("/config")
async def get_voice_config(
    tenant_id: str = "aurem_platform"  # TODO: Get from JWT
):
    """
    Get voice AI configuration for tenant
    
    Returns:
        {
            "success": true,
            "config": {
                "dynamic_tone": bool,
                "vibe_preference": str
            }
        }
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        tenant = await db.users.find_one(
            {"tenant_id": tenant_id},
            {"_id": 0, "voice_config": 1}
        )
        
        if not tenant:
            raise HTTPException(404, "Tenant not found")
        
        config = tenant.get("voice_config", {
            "dynamic_tone": True,
            "vibe_preference": "mirror"
        })
        
        return {
            "success": True,
            "config": config
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[VapiVoice] Error getting config: {e}")
        raise HTTPException(500, str(e))


@router.post("/config")
async def update_voice_config(
    config: VoiceConfigUpdate,
    tenant_id: str = "aurem_platform"  # TODO: Get from JWT
):
    """
    Update voice AI configuration
    
    Body:
        {
            "dynamic_tone": bool,
            "vibe_preference": "mirror" | "de-escalate" | "concierge"
        }
    
    Returns:
        {
            "success": true,
            "config": {...}
        }
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Validate vibe preference
        valid_vibes = ["mirror", "de-escalate", "concierge"]
        if config.vibe_preference not in valid_vibes:
            raise HTTPException(400, f"Invalid vibe preference. Must be one of: {valid_vibes}")
        
        # Update tenant config
        result = await db.users.update_one(
            {"tenant_id": tenant_id},
            {"$set": {
                "voice_config": config.dict(),
                "voice_config_updated_at": datetime.now(timezone.utc)
            }}
        )
        
        if result.matched_count == 0:
            raise HTTPException(404, "Tenant not found")
        
        logger.info(f"[VapiVoice] Updated voice config for {tenant_id}")
        
        return {
            "success": True,
            "config": config.dict()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[VapiVoice] Error updating config: {e}")
        raise HTTPException(500, str(e))
