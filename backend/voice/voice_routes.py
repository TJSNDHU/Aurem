"""
Voice Agent API Routes
═══════════════════════════════════════════════════════════════════
WebSocket and REST API endpoints for voice AI.
═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

import os
import json
import logging
import asyncio
import base64
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["Voice AI"])

# Database reference
_db = None


def set_db(database):
    """Set database reference from server.py startup."""
    global _db
    _db = database
    logger.info("Voice AI routes: Database reference set")


# ═══════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════

class InboundCallRequest(BaseModel):
    """Webhook payload for inbound calls."""
    phone_number: str
    call_id: Optional[str] = None


class CallResponse(BaseModel):
    """Response for call endpoints."""
    session_id: str
    phone_number: str
    start_time: str
    duration_seconds: Optional[float] = None
    status: str
    outcome: str
    transcript: Optional[list] = None


# ═══════════════════════════════════════════════════════════════════
# WEBSOCKET ENDPOINT
# ═══════════════════════════════════════════════════════════════════

@router.websocket("/ws/{session_id}")
async def voice_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time voice conversation.
    
    Protocol:
    - Client sends: {"type": "audio", "data": "<base64 audio>", "mime_type": "audio/webm"}
    - Server responds: {"type": "response", "text": "...", "audio": "<base64 audio>"}
    - Client can send: {"type": "end"} to end the session
    """
    await websocket.accept()
    logger.info(f"Voice WebSocket connected: {session_id}")
    
    if _db is None:
        await websocket.send_json({"type": "error", "message": "Service not ready"})
        await websocket.close()
        return
    
    from voice.voice_agent import get_voice_agent
    agent = get_voice_agent(_db)
    
    # Start session
    phone = websocket.query_params.get("phone", "web")
    session = await agent.start_session(session_id, phone)
    
    # Send welcome message
    welcome = "Hello! I'm Reroots AI Voice, your skincare advisor. How can I help you today?"
    welcome_audio = await agent.synthesize_speech(welcome)
    
    await websocket.send_json({
        "type": "response",
        "text": welcome,
        "audio": base64.b64encode(welcome_audio).decode() if welcome_audio else None
    })
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            msg_type = data.get("type", "")
            
            if msg_type == "end":
                # End session
                result = await agent.end_session(session_id, "completed")
                await websocket.send_json({
                    "type": "ended",
                    "duration": result.get("duration", 0) if result else 0
                })
                break
            
            elif msg_type == "audio":
                # Process audio
                audio_b64 = data.get("data", "")
                mime_type = data.get("mime_type", "audio/webm")
                
                if not audio_b64:
                    await websocket.send_json({
                        "type": "error",
                        "message": "No audio data provided"
                    })
                    continue
                
                # Decode audio
                try:
                    audio_data = base64.b64decode(audio_b64)
                except Exception:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid audio data"
                    })
                    continue
                
                # Process through pipeline
                result = await agent.process_audio(session_id, audio_data, mime_type)
                
                if "error" in result:
                    await websocket.send_json({
                        "type": "error",
                        "message": result["error"]
                    })
                else:
                    response_audio = result.get("audio", b"")
                    await websocket.send_json({
                        "type": "response",
                        "user_text": result.get("user_text", ""),
                        "text": result.get("response_text", ""),
                        "audio": base64.b64encode(response_audio).decode() if response_audio else None
                    })
            
            elif msg_type == "text":
                # Text-only input (for testing)
                user_text = data.get("text", "")
                if user_text:
                    response = await agent.generate_response(session_id, user_text)
                    audio = await agent.synthesize_speech(response)
                    await websocket.send_json({
                        "type": "response",
                        "user_text": user_text,
                        "text": response,
                        "audio": base64.b64encode(audio).decode() if audio else None
                    })
            
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}"
                })
    
    except WebSocketDisconnect:
        logger.info(f"Voice WebSocket disconnected: {session_id}")
        await agent.end_session(session_id, "disconnected")
    except Exception as e:
        logger.error(f"Voice WebSocket error: {e}")
        await agent.end_session(session_id, "error")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass


# ═══════════════════════════════════════════════════════════════════
# INBOUND CALL WEBHOOK
# ═══════════════════════════════════════════════════════════════════

@router.post("/inbound")
async def inbound_call(request: Request, body: InboundCallRequest):
    """
    Webhook for inbound voice calls.
    Creates a session and returns connection details.
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    from voice.voice_agent import get_voice_agent
    import uuid
    
    agent = get_voice_agent(_db)
    session_id = body.call_id or str(uuid.uuid4())
    
    session = await agent.start_session(session_id, body.phone_number)
    
    # Generate WebSocket URL
    host = request.headers.get("host", "localhost:8001")
    protocol = "wss" if request.url.scheme == "https" else "ws"
    ws_url = f"{protocol}://{host}/api/voice/ws/{session_id}"
    
    return {
        "success": True,
        "session_id": session_id,
        "websocket_url": ws_url,
        "greeting": "Hello! I'm Reroots AI Voice, your skincare advisor. How can I help you today?"
    }


# ═══════════════════════════════════════════════════════════════════
# ADMIN ROUTES
# ═══════════════════════════════════════════════════════════════════

@router.get("/calls")
async def get_calls(request: Request, limit: int = 50):
    """Get recent voice call history."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    from voice.voice_agent import get_voice_agent
    
    agent = get_voice_agent(_db)
    calls = await agent.get_calls(limit)
    
    return {
        "success": True,
        "count": len(calls),
        "calls": calls
    }


@router.get("/calls/{session_id}")
async def get_call(request: Request, session_id: str):
    """Get a specific call by session ID."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    from voice.voice_agent import get_voice_agent
    
    agent = get_voice_agent(_db)
    call = await agent.get_call(session_id)
    
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    
    return {
        "success": True,
        "call": call
    }


@router.get("/stats")
async def get_stats(request: Request, days: int = 7):
    """Get voice call statistics."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    from voice.voice_agent import get_voice_agent
    
    agent = get_voice_agent(_db)
    stats = await agent.get_call_stats(days)
    
    return {
        "success": True,
        "stats": stats
    }


@router.get("/health")
async def health():
    """Health check for voice service."""
    has_deepgram = bool(os.environ.get("DEEPGRAM_API_KEY"))
    has_elevenlabs = bool(os.environ.get("ELEVENLABS_API_KEY"))
    has_telnyx = bool(os.environ.get("TELNYX_API_KEY"))
    
    return {
        "status": "ok",
        "service": "voice-ai",
        "deepgram_configured": has_deepgram,
        "elevenlabs_configured": has_elevenlabs,
        "telnyx_configured": has_telnyx
    }


# ═══════════════════════════════════════════════════════════════════
# TELNYX INTEGRATION
# ═══════════════════════════════════════════════════════════════════

@router.post("/telnyx/call-control")
async def telnyx_call_control(request: Request):
    """
    Telnyx Call Control webhook for managing voice calls.
    
    Handles events like:
    - call.initiated
    - call.answered
    - call.hangup
    - call.speak.ended
    - streaming.started/stopped
    """
    try:
        body = await request.json()
        event_type = body.get("data", {}).get("event_type", "")
        payload = body.get("data", {}).get("payload", {})
        
        call_control_id = payload.get("call_control_id", "")
        call_leg_id = payload.get("call_leg_id", "")
        
        logger.info(f"[TELNYX] Call Control event: {event_type}")
        
        if event_type == "call.initiated":
            # Log incoming call
            from_number = payload.get("from", "")
            to_number = payload.get("to", "")
            
            logger.info(f"[TELNYX] Call initiated: {from_number} -> {to_number}")
            
            # Detect caller language
            from utils.phone_manager import detect_country_from_number
            caller_country = detect_country_from_number(from_number)
            
            if _db:
                await _db.voice_calls.insert_one({
                    "call_control_id": call_control_id,
                    "call_leg_id": call_leg_id,
                    "from_number": from_number,
                    "to_number": to_number,
                    "caller_country": caller_country,
                    "status": "initiated",
                    "started_at": datetime.now(timezone.utc).isoformat()
                })
        
        elif event_type == "call.answered":
            logger.info(f"[TELNYX] Call answered: {call_control_id}")
            
            if _db:
                await _db.voice_calls.update_one(
                    {"call_control_id": call_control_id},
                    {"$set": {"status": "answered", "answered_at": datetime.now(timezone.utc).isoformat()}}
                )
        
        elif event_type == "call.hangup":
            hangup_cause = payload.get("hangup_cause", "unknown")
            logger.info(f"[TELNYX] Call hangup: {call_control_id} ({hangup_cause})")
            
            if _db:
                await _db.voice_calls.update_one(
                    {"call_control_id": call_control_id},
                    {"$set": {
                        "status": "completed",
                        "hangup_cause": hangup_cause,
                        "ended_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
        
        return {"status": "ok", "event": event_type}
        
    except Exception as e:
        logger.error(f"[TELNYX] Call control error: {e}")
        return {"status": "error", "message": str(e)}
