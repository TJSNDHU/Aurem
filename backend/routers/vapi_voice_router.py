"""
AUREM DIY Voice Router — Tone Sync + Web Speech API
Real-time voice sentiment analysis and tone adjustment for AUREM voice calls.
No third-party Vapi dependency — uses browser-native Web Speech API on the client
and AUREM's own Tone Sync engine on the backend.

Endpoints:
- POST /api/voice/sentiment - Receive live transcript and return tone adjustment
- POST /api/voice/webhook - General voice event handler
- GET  /api/voice/config - Get voice AI configuration for tenant
- POST /api/voice/config - Update voice AI configuration
"""

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import logging

from utils.tenant import current_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["AUREM DIY Voice AI"])

# MongoDB connection
db = None


def set_db(database):
    global db
    db = database


class VoiceTranscript(BaseModel):
    """Live transcript payload from AUREM Web Speech API client"""
    conversation_id: str
    transcript: str
    speaker: str = "user"  # "user" or "assistant"
    timestamp: Optional[str] = None


class VoiceConfigUpdate(BaseModel):
    """Update voice AI configuration"""
    dynamic_tone: bool = True
    vibe_preference: str = "mirror"  # mirror, de-escalate, concierge


@router.post("/sentiment")
async def analyze_voice_sentiment(
    payload: VoiceTranscript,
    tenant_id: str = Depends(current_tenant),
):
    """
    Receive live transcript from AUREM Web Speech client and return tone adjustment.
    Called in real-time during voice conversations via the DIY voice engine.
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")

    try:
        from services.tone_sync_service import get_tone_sync_service

        tone_sync = get_tone_sync_service(db)

        result = await tone_sync.analyze_voice_sentiment(
            tenant_id=tenant_id,
            conversation_id=payload.conversation_id,
            transcript=payload.transcript,
            speaker=payload.speaker,
        )

        if "error" in result:
            raise HTTPException(500, result["error"])

        # If panic detected, trigger alert
        if result.get("should_alert"):
            logger.warning(f"[AuremVoice] PANIC detected in call {payload.conversation_id}")

            from services.aurem_hooks.panic_hook import get_panic_hook

            panic_hook = get_panic_hook(db)

            conversation_history = [{"role": "user", "content": payload.transcript}]

            await panic_hook.execute(
                tenant_id=tenant_id,
                conversation_id=payload.conversation_id,
                conversation_history=conversation_history,
                latest_user_message=payload.transcript,
                latest_ai_response="[Voice conversation - AI adjusting tone]",
                metadata={
                    "source": "voice",
                    "vibe_label": result["vibe_label"],
                    "customer": {"name": "Voice Caller", "phone": "N/A", "email": "N/A"},
                },
            )

        return {"success": True, **result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AuremVoice] Sentiment analysis error: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.post("/webhook")
async def voice_event_handler(request: Request):
    """
    General voice event handler for the AUREM DIY engine.
    Receives events: call.started, call.ended, transcript.updated

    Bug-fix #97 — previously accepted `tenant_id` from the attacker-
    controlled request payload, allowing fake calls to be injected under
    any tenant's account. Now `tenant_id` is derived strictly from a
    verified JWT in the Authorization header; we never trust the body.
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")

    # Authenticate the caller — JWT required
    import os, jwt as _jwt
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(503, "Auth not configured")
    try:
        token_payload = _jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
    except _jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except _jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    tenant_id = (
        token_payload.get("tenant_id") or token_payload.get("business_id")
        or token_payload.get("sub") or token_payload.get("email")
    )
    if not tenant_id:
        raise HTTPException(403, "No tenant in token")

    try:
        payload = await request.json()

        event_type = payload.get("type")
        conversation_id = payload.get("call", {}).get("id", payload.get("conversation_id", "unknown"))
        # tenant_id comes from the verified JWT above — NEVER from payload.

        logger.info(f"[AuremVoice] Event received: {event_type} for {conversation_id}")

        if event_type == "call.started":
            await db.voice_calls.insert_one({
                "conversation_id": conversation_id,
                "status": "started",
                "started_at": datetime.now(timezone.utc),
                "provider": "aurem_diy",
                "call_data": payload.get("call", {}),
            })

        elif event_type == "call.ended":
            await db.voice_calls.update_one(
                {"conversation_id": conversation_id},
                {"$set": {
                    "status": "ended",
                    "ended_at": datetime.now(timezone.utc),
                    "duration_seconds": payload.get("call", {}).get("duration"),
                }},
                upsert=True,
            )

        elif event_type == "transcript.updated":
            transcript = payload.get("transcript", {}).get("text", "")
            speaker = payload.get("transcript", {}).get("role", "user")

            if transcript:
                from services.tone_sync_service import get_tone_sync_service

                tone_sync = get_tone_sync_service(db)

                result = await tone_sync.analyze_voice_sentiment(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    transcript=transcript,
                    speaker=speaker,
                )

                return {"success": True, "tone_adjustment": result.get("voice_settings", {})}

        return {"success": True, "event_type": event_type}

    except Exception as e:
        logger.error(f"[AuremVoice] Webhook error: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.get("/config")
async def get_voice_config(tenant_id: str = Depends(current_tenant)):
    """Get voice AI configuration for tenant"""
    if db is None:
        raise HTTPException(500, "Database not initialized")

    try:
        tenant = await db.users.find_one(
            {"tenant_id": tenant_id},
            {"_id": 0, "voice_config": 1},
        )

        config = (tenant or {}).get("voice_config", {
            "dynamic_tone": True,
            "vibe_preference": "mirror",
        })

        return {"success": True, "config": config}

    except Exception as e:
        logger.error(f"[AuremVoice] Error getting config: {e}")
        raise HTTPException(500, str(e))


@router.post("/config")
async def update_voice_config(config: VoiceConfigUpdate, tenant_id: str = Depends(current_tenant)):
    """Update voice AI configuration"""
    if db is None:
        raise HTTPException(500, "Database not initialized")

    try:
        valid_vibes = ["mirror", "de-escalate", "concierge"]
        if config.vibe_preference not in valid_vibes:
            raise HTTPException(400, f"Invalid vibe preference. Must be one of: {valid_vibes}")

        result = await db.users.update_one(
            {"tenant_id": tenant_id},
            {"$set": {
                "voice_config": config.dict(),
                "voice_config_updated_at": datetime.now(timezone.utc),
            }},
        )

        if result.matched_count == 0:
            raise HTTPException(404, "Tenant not found")

        logger.info(f"[AuremVoice] Updated voice config for {tenant_id}")

        return {"success": True, "config": config.dict()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AuremVoice] Error updating config: {e}")
        raise HTTPException(500, str(e))
