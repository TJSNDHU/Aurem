"""
AUREM Real-Time Voice-to-Voice (V2V) WebSocket Engine
=====================================================
True duplex voice conversation: Browser <-> WebSocket <-> Backend

Architecture:
  Station 1 (Capture):  Browser MediaRecorder captures audio chunks
  Station 2 (Transport): WebSocket streams chunks to/from backend
  Station 3 (Process):   Whisper STT -> Sentiment Side-Process -> GPT-4o LLM -> OpenAI TTS
  Station 4 (Playback):  Browser AudioContext plays streamed audio

Pipeline (Emotion-Aware):
  User Audio → STT (Whisper) → Text Transcript
  Text Transcript → [parallel]
    ├─ Fast Sentiment (keyword, <1ms) → EmotionalState
    └─ Full AI Sentiment (background, for panic/logging)
  (EmotionalState + Transcript) → Brain/LLM → Response + TTS Instruction
  TTS Instruction → Voice Selection → Audio Output

Features:
  - Sub-500ms latency via streaming orchestration
  - Voice Activity Detection (VAD) — server-side silence detection
  - Barge-in / Natural Interruption — client sends interrupt signal
  - Emotion-Aware Response Generation — sentiment feeds into LLM context
  - Dynamic TTS Voice Selection — voice adapts to caller's emotional state
  - Full call transcript logging to MongoDB
"""

import os
import io
import re
import uuid
import json
import asyncio
import logging
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request
from pydantic import BaseModel
import jwt as pyjwt
from config import JWT_SECRET, JWT_ALGORITHM

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["AUREM V2V Engine"])

db = None

# Concurrent connection tracking per tenant
_active_ws_connections: dict[str, int] = {}
MAX_WS_PER_TENANT = 5


def set_db(database):
    global db
    db = database


# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
TTS_VOICE = "nova"  # OpenAI TTS voice: alloy, echo, fable, onyx, nova, shimmer
TTS_MODEL = "tts-1"  # tts-1 (fast) or tts-1-hd (quality)
STT_MODEL = "whisper-1"
LLM_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT_VOICE = """ORA — AUREM voice assistant. 1-2 sentences max. Direct, no filler. Use LIVE CONTEXT below."""

SYSTEM_PROMPT_BASE = """You are ORA, a personal AI assistant powered by AUREM.
You are speaking in a real-time voice conversation. Keep your responses:
- Concise (1-3 sentences max unless asked for detail)
- Natural and conversational
- Professional but warm
- Actionable and specific

You have access to LIVE business data, CRM intelligence, weather, and web search.
Always use the LIVE CONTEXT injected below — not your training knowledge.
If the user sounds rushed, be brief. If they want detail, elaborate.
If the user tells you their name, acknowledge it warmly and remember it.
Never mention that you are an AI unless directly asked."""

# Keep backward compat for any imports
SYSTEM_PROMPT = SYSTEM_PROMPT_BASE


# ═══════════════════════════════════════════════════════════════════
# EMOTION-AWARE ENGINE
# ═══════════════════════════════════════════════════════════════════

# Keyword sets for instant emotional state classification (<1ms, no API call)
_EMOTION_KEYWORDS = {
    "frustrated": [
        "frustrated", "frustrating", "annoyed", "annoying", "ugh",
        "not working", "doesn't work", "broken", "useless", "waste",
        "still waiting", "again", "how many times", "ridiculous",
    ],
    "angry": [
        "angry", "furious", "mad", "terrible", "horrible", "awful",
        "worst", "unacceptable", "scam", "fraud", "sue", "lawyer",
        "report you", "legal action", "demand",
    ],
    "confused": [
        "confused", "don't understand", "what do you mean",
        "makes no sense", "unclear", "lost", "huh", "how does",
        "can you explain", "i'm not sure",
    ],
    "happy": [
        "great", "awesome", "perfect", "love it", "excellent",
        "amazing", "thank you", "thanks", "wonderful", "fantastic",
        "brilliant", "impressed",
    ],
    "concerned": [
        "worried", "concern", "nervous", "hesitant", "unsure",
        "risky", "problem", "issue", "trouble", "afraid",
    ],
    "urgent": [
        "asap", "immediately", "urgent", "emergency", "right now",
        "hurry", "deadline", "critical", "time sensitive",
    ],
}

# EmotionalState → TTS voice + instruction mapping
_EMOTION_VOICE_MAP = {
    "frustrated": {
        "voice": "nova",
        "tts_instruction": "Speak in a soothing, professional tone. Slower pace, warmer pitch.",
        "system_addendum": (
            "The caller sounds frustrated. Respond with calm empathy and patience. "
            "Acknowledge their concern naturally without saying 'I sense you are frustrated'. "
            "Provide a clear path to resolution. Be concise and solution-oriented."
        ),
    },
    "angry": {
        "voice": "nova",
        "tts_instruction": "Speak calmly and empathetically. Low pitch, steady pace, generous pauses.",
        "system_addendum": (
            "The caller is upset. De-escalate with a calm, reassuring presence. "
            "Do NOT be defensive. Validate their experience, then offer a concrete next step. "
            "Keep it brief — angry callers don't want long explanations."
        ),
    },
    "confused": {
        "voice": "echo",
        "tts_instruction": "Speak clearly and patiently. Moderate pace with deliberate pauses.",
        "system_addendum": (
            "The caller seems confused. Use simple, clear language. "
            "Break down complex ideas into small steps. Ask one clarifying question if needed. "
            "Be patient and reassuring."
        ),
    },
    "happy": {
        "voice": "shimmer",
        "tts_instruction": "Speak with warm enthusiasm. Bright tone, natural energy.",
        "system_addendum": (
            "The caller is in a positive mood. Match their energy — be upbeat and enthusiastic. "
            "This is a good moment to suggest next steps or upsell opportunities naturally."
        ),
    },
    "concerned": {
        "voice": "nova",
        "tts_instruction": "Speak with gentle reassurance. Slightly slower, warmer tone.",
        "system_addendum": (
            "The caller has concerns. Respond with reassurance and specifics. "
            "Provide facts and data to ease their worry. Be thorough but not overwhelming."
        ),
    },
    "urgent": {
        "voice": "alloy",
        "tts_instruction": "Speak efficiently and directly. Brisk pace, action-oriented.",
        "system_addendum": (
            "The caller is in a hurry. Be extremely concise and action-focused. "
            "Skip pleasantries. Lead with the answer, then details if asked."
        ),
    },
    "neutral": {
        "voice": TTS_VOICE,
        "tts_instruction": "Speak professionally and warmly. Balanced pace.",
        "system_addendum": "",
    },
}


def _fast_emotional_state(text: str) -> dict:
    """
    Instant keyword-based emotional state classification (<1ms).
    Runs as a side-process on every incoming text buffer.
    Returns: {"emotion": str, "confidence": float, "keywords_detected": list}
    """
    text_lower = text.lower()
    best_emotion = "neutral"
    best_score = 0
    detected_keywords = []

    for emotion, keywords in _EMOTION_KEYWORDS.items():
        hits = [kw for kw in keywords if kw in text_lower]
        if len(hits) > best_score:
            best_score = len(hits)
            best_emotion = emotion
            detected_keywords = hits

    confidence = min(0.95, 0.3 + best_score * 0.2) if best_score > 0 else 0.1

    return {
        "emotion": best_emotion,
        "confidence": confidence,
        "keywords_detected": detected_keywords,
    }


def _get_emotion_config(emotion: str) -> dict:
    """Get voice + system prompt config for a given emotional state."""
    return _EMOTION_VOICE_MAP.get(emotion, _EMOTION_VOICE_MAP["neutral"])


# ═══════════════════════════════════════════════════════════════════
# DATA MODELS
# ═══════════════════════════════════════════════════════════════════

class V2VCallResponse(BaseModel):
    call_id: str
    status: str
    engine: str = "aurem_v2v"
    ws_url: str


class VoiceRespondRequest(BaseModel):
    call_id: Optional[str] = None
    message: str
    conversation_history: Optional[list] = None


# ═══════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════

@router.get("/health")
async def v2v_health():
    """V2V Engine health status"""
    return {
        "status": "ok",
        "service": "v2v-stream-engine",
        "llm_configured": bool(EMERGENT_LLM_KEY),
        "tts_voice": TTS_VOICE,
        "tts_model": TTS_MODEL,
        "stt_model": STT_MODEL,
        "llm_model": LLM_MODEL,
        "db_connected": db is not None,
        "active_ws_connections": sum(_active_ws_connections.values()),
    }


# ═══════════════════════════════════════════════════════════════════
# REST ENDPOINTS (for non-WebSocket fallback)
# ═══════════════════════════════════════════════════════════════════

@router.post("/respond")
async def voice_respond(req: VoiceRespondRequest, request: Request):
    """
    REST fallback: Generate AI voice response text.
    Used when WebSocket is unavailable (e.g., older browsers).
    """
    import time as _t
    _t0 = _t.time()
    logger.info(f"[V2V-REST] /respond called: msg={req.message[:30]}")
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        logger.info(f"[V2V-REST] import done {_t.time()-_t0:.2f}s")

        # Build conversation context
        context_parts = []
        for msg in (req.conversation_history or []):
            role = msg.get("role", "user")
            content = msg.get("content", "")
            context_parts.append(f"{'User' if role == 'user' else 'Assistant'}: {content}")
        context_parts.append(f"User: {req.message}")
        full_context = "\n".join(context_parts[-6:])

        # Skip live context entirely for voice — speed is priority
        system_with_context = SYSTEM_PROMPT_VOICE

        logger.info(f"[V2V-REST] calling LLM {_t.time()-_t0:.2f}s")
        llm = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=req.call_id or "voice_session",
            system_message=system_with_context,
        ).with_model("openai", LLM_MODEL)

        response = await asyncio.wait_for(
            llm.send_message(UserMessage(text=full_context)),
            timeout=8.0,
        )
        logger.info(f"[V2V-REST] LLM done {_t.time()-_t0:.2f}s len={len(response)}")

        # Log to DB (fire-and-forget)
        if db is not None and req.call_id:
            try:
                await asyncio.wait_for(
                    db.aurem_voice_calls.update_one(
                        {"call_id": req.call_id},
                        {"$push": {"transcripts": {
                            "user": req.message,
                            "assistant": response,
                            "ts": datetime.now(timezone.utc).isoformat(),
                        }}},
                        upsert=True,
                    ),
                    timeout=2.0,
                )
            except Exception:
                pass

        return {"success": True, "response": response}

    except asyncio.TimeoutError:
        logger.error(f"[V2V-REST] TIMEOUT at {_t.time()-_t0:.2f}s")
        return {"success": False, "response": "Sorry, I took too long. Please try again."}
    except Exception as e:
        logger.error(f"[V2V-REST] ERROR at {_t.time()-_t0:.2f}s: {e}")
        return {"success": False, "response": "I'm sorry, could you repeat that?", "error": str(e)}


@router.post("/web-call")
async def create_web_call(request: Request):
    """Create a new V2V call session and return config + session token."""
    call_id = str(uuid.uuid4())

    # Parse optional user email from body
    user_email = None
    user_name = None
    try:
        body = await request.json()
        user_email = body.get("email", "").strip().lower() if body else None
    except Exception:
        pass

    # If caller sent a platform auth Bearer token, decode is_admin / email from it
    # so founder status propagates into the voice WebSocket session.
    is_admin_flag = False
    try:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            caller_payload = pyjwt.decode(
                auth_header.split(" ", 1)[1], JWT_SECRET,
                algorithms=[JWT_ALGORITHM], options={"verify_exp": False},
            )
            is_admin_flag = bool(caller_payload.get("is_admin") or caller_payload.get("is_super_admin"))
            if not user_email:
                user_email = (caller_payload.get("email") or "").lower() or None
    except Exception:
        pass

    # Look up user name from ora_leads if email provided
    if user_email and db is not None:
        lead = await db.ora_leads.find_one({"email": user_email}, {"_id": 0, "full_name": 1})
        if lead:
            user_name = lead.get("full_name", "")

    # Generate a short-lived session token for WebSocket auth (no login required)
    session_token = pyjwt.encode(
        {
            "call_id": call_id,
            "type": "v2v_session",
            "tenant_id": "ora_pwa",
            "user_email": user_email or "",
            "user_name": user_name or "",
            "is_admin": is_admin_flag,
            "exp": datetime.now(timezone.utc) + timedelta(hours=2),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    # Determine WebSocket URL (respect X-Forwarded-Proto from reverse proxy)
    host = request.headers.get("host", "localhost:8001")
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    scheme = "wss" if forwarded_proto == "https" else "ws"
    ws_url = f"{scheme}://{host}/api/voice/stream?call_id={call_id}&token={session_token}"

    config = {
        "call_id": call_id,
        "status": "ready",
        "engine": "aurem_v2v",
        "ws_url": ws_url,
        "session_token": session_token,
        "assistant_config": {
            "name": "ORA",
            "firstMessage": "Hello, I'm ORA, your AI business partner.",
            "language": "en-US",
            "voice": {"provider": "openai", "name": TTS_VOICE, "model": TTS_MODEL},
            "stt": {"provider": "openai", "model": STT_MODEL},
        },
        "available": True,
    }

    if db is not None:
        await db.aurem_voice_calls.insert_one({
            "call_id": call_id,
            "provider": "aurem_v2v",
            "status": "ready",
            "created_at": datetime.now(timezone.utc),
            "transcripts": [],
        })

    return config


@router.post("/tts")
async def text_to_speech(request: Request):
    """
    Convert text to speech audio using OpenAI TTS.
    Returns raw audio bytes (mp3).
    """
    body = await request.json()
    text = body.get("text", "")
    voice = body.get("voice", TTS_VOICE)

    if not text:
        raise HTTPException(400, "No text provided")

    try:
        audio_bytes = await _generate_tts(text, voice)
        from starlette.responses import Response
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"[V2V] TTS error: {e}")
        raise HTTPException(500, str(e))


# ═══════════════════════════════════════════════════════════════════
# WEBSOCKET V2V STREAM (The Core Engine)
# ═══════════════════════════════════════════════════════════════════

@router.websocket("/stream")
async def voice_stream(websocket: WebSocket, call_id: str = None, token: str = None, tz_offset: int = 0):
    """
    Real-time duplex voice stream.
    Requires a valid JWT token (passed as ?token= query param).

    Client sends:
      {"type": "audio", "data": "<base64 audio chunk>", "format": "webm"}
      {"type": "text",  "text": "user said this"}  (fallback if using Web Speech API)
      {"type": "interrupt"}  (barge-in: stop AI audio immediately)
      {"type": "end"}

    Server sends:
      {"type": "transcript", "text": "...", "speaker": "user"}
      {"type": "response_start"}
      {"type": "audio_chunk", "data": "<base64 audio>", "index": 0}
      {"type": "response_text", "text": "..."}
      {"type": "response_end"}
      {"type": "tone_sync", "vibe": "...", "adjustment": "..."}
      {"type": "error", "message": "..."}
    """
    # ── AUTH GATE: Validate JWT before accepting ──
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        tenant_id = payload.get("tenant_id", payload.get("user_id", "unknown"))
    except pyjwt.ExpiredSignatureError:
        await websocket.close(code=4001, reason="Token expired")
        return
    except pyjwt.InvalidTokenError:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Extract user name from token for personalized greeting
    user_name = payload.get("user_name", "")
    user_email = payload.get("user_email", "")
    is_founder = bool(payload.get("is_admin") or payload.get("is_super_admin"))
    current = _active_ws_connections.get(tenant_id, 0)
    if current >= MAX_WS_PER_TENANT:
        await websocket.close(code=4002, reason="Too many concurrent connections")
        return

    _active_ws_connections[tenant_id] = current + 1

    await websocket.accept()

    if not call_id:
        call_id = str(uuid.uuid4())

    conversation_history = []
    is_ai_speaking = False
    interrupted = False

    logger.info(f"[V2V] WebSocket connected: call_id={call_id}")

    # Update call status
    if db is not None:
        await db.aurem_voice_calls.update_one(
            {"call_id": call_id},
            {"$set": {"status": "connected", "ws_connected_at": datetime.now(timezone.utc)}},
            upsert=True,
        )

    # Build time-aware greeting using CLIENT's local time
    from datetime import timedelta
    utc_now = datetime.now(timezone.utc)
    # tz_offset from JS is minutes AHEAD of UTC (e.g. EST = 300, IST = -330)
    # JS: new Date().getTimezoneOffset() returns minutes behind UTC
    client_now = utc_now - timedelta(minutes=int(tz_offset))
    hour = client_now.hour
    if hour < 12:
        time_greeting = "Good morning"
    elif hour < 17:
        time_greeting = "Good afternoon"
    else:
        time_greeting = "Good evening"
    day_name = client_now.strftime("%A")
    time_str = client_now.strftime("%-I:%M %p")
    if user_name:
        greeting = f"{time_greeting}, {user_name}! It's {day_name}, {time_str}. I'm ORA, your personal AI assistant. How can I help you today?"
    else:
        greeting = f"{time_greeting}! It's {day_name}, {time_str}. I'm ORA, your personal AI assistant. Before we begin, may I know your name?"
    conversation_history.append({"role": "assistant", "content": greeting})

    try:
        # Generate and send greeting audio
        greeting_audio = await _generate_tts(greeting)
        if greeting_audio:
            import base64
            await websocket.send_json({
                "type": "response_start",
            })
            await websocket.send_json({
                "type": "response_text",
                "text": greeting,
            })
            await websocket.send_json({
                "type": "audio_chunk",
                "data": base64.b64encode(greeting_audio).decode("utf-8"),
                "index": 0,
                "format": "mp3",
            })
            await websocket.send_json({"type": "response_end"})
    except Exception as e:
        logger.warning(f"[V2V] Greeting TTS failed: {e}")
        await websocket.send_json({"type": "response_text", "text": greeting})

    try:
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type", "")

            if msg_type == "end":
                logger.info(f"[V2V] Call ended by client: {call_id}")
                break

            elif msg_type == "interrupt":
                # Barge-in: client detected user speaking while AI was talking
                await websocket.send_json({"type": "interrupted", "message": "AI audio cleared"})
                continue

            elif msg_type == "text":
                # Fallback path: client sent text directly (Web Speech API STT on client)
                user_text = msg.get("text", "").strip()
                if not user_text:
                    continue

                await websocket.send_json({"type": "transcript", "text": user_text, "speaker": "user"})
                conversation_history.append({"role": "user", "content": user_text})

                # Try to extract and save user name if not yet known
                if not user_name and user_email:
                    await _try_save_user_name(user_email, user_text)

                # Process and respond
                await _process_and_respond(websocket, call_id, user_text, conversation_history, tenant_id, is_founder=is_founder)

            elif msg_type == "audio":
                # Full V2V path: client sent raw audio chunk
                import base64
                audio_b64 = msg.get("data", "")
                audio_format = msg.get("format", "webm")

                if not audio_b64:
                    continue

                audio_bytes = base64.b64decode(audio_b64)

                # STT: Transcribe audio using Whisper
                user_text = await _transcribe_audio(audio_bytes, audio_format)

                if not user_text or len(user_text.strip()) < 2:
                    # Notify client that STT returned no result so it can reset state
                    await websocket.send_json({"type": "stt_empty", "message": "Could not detect speech. Tap and try again."})
                    continue

                await websocket.send_json({"type": "transcript", "text": user_text, "speaker": "user"})
                conversation_history.append({"role": "user", "content": user_text})

                # Try to extract and save user name if not yet known
                if not user_name and user_email:
                    await _try_save_user_name(user_email, user_text)

                # Process and respond
                await _process_and_respond(websocket, call_id, user_text, conversation_history, tenant_id, is_founder=is_founder)

    except WebSocketDisconnect:
        logger.info(f"[V2V] WebSocket disconnected: {call_id}")
    except Exception as e:
        logger.error(f"[V2V] WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        # Decrement tenant connection counter
        _active_ws_connections[tenant_id] = max(0, _active_ws_connections.get(tenant_id, 1) - 1)
        if db is not None:
            await db.aurem_voice_calls.update_one(
                {"call_id": call_id},
                {"$set": {
                    "status": "ended",
                    "ended_at": datetime.now(timezone.utc),
                    "transcript_count": len(conversation_history),
                }},
            )
        logger.info(f"[V2V] Call session closed: {call_id}")


# ═══════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════

async def _process_and_respond(websocket: WebSocket, call_id: str, user_text: str, history: list, tenant_id: str = "aurem_platform", is_founder: bool = False):
    """
    Emotion-Aware Response Pipeline.

    Flow:
      1. Input Guardrail
      2. Command Center check (founder-gated admin commands first)
      3. Fast Sentiment Side-Process → EmotionalState (<1ms)
      4. Full AI Sentiment (background task, for panic/logging)
      5. Brain receives (EmotionalState + TextTranscript) → generates response
      6. TTS Instruction selects voice based on EmotionalState
      7. Audio generated with emotion-matched voice
    """
    import base64

    try:
        # ── STEP 1: INPUT GUARDRAIL ──
        from services.guardrail_proxy import guard_input, guard_output, scrub_pii
        guard = await guard_input(user_text, tenant_id=tenant_id)

        if guard["action"] == "kill":
            await websocket.send_json({"type": "response_text", "text": ""})
            await websocket.send_json({"type": "response_end"})
            logger.warning(f"[V2V] Jailbreak KILLED for call {call_id}: score={guard['jailbreak_score']}")
            return

        if guard["action"] == "warn":
            warn_text = guard.get("voice_response", "I'm sorry, I can't help with that request.")
            await websocket.send_json({"type": "response_start"})
            await websocket.send_json({"type": "response_text", "text": warn_text})
            try:
                warn_audio = await _generate_tts(warn_text)
                if warn_audio:
                    await websocket.send_json({"type": "audio_chunk", "data": base64.b64encode(warn_audio).decode("utf-8"), "index": 0, "format": "mp3"})
            except Exception:
                pass
            await websocket.send_json({"type": "response_end"})
            return

        # ── STEP 2: COMMAND CENTER CHECK (any-language, founder-gated) ──
        # If the user spoke a real command ("show system health", "kitne leads aaye",
        # "revenue today"), run it directly and pipe the structured reply through TTS.
        try:
            from services.ora_command_center import execute_command
            global db
            _cmd_res = await execute_command(
                db, user_text, channel="voice",
                user=tenant_id, is_founder=is_founder,
            )
            _cmd_intent = _cmd_res.get("intent", "UNKNOWN")
            if _cmd_intent not in ("UNKNOWN", "CHAT", "FORBIDDEN"):
                cmd_reply = _cmd_res.get("reply") or "Command executed."
                # Strip markdown (*, `, #) for cleaner TTS
                tts_text = re.sub(r"[*_`#]", "", cmd_reply)
                history.append({"role": "assistant", "content": cmd_reply})
                await websocket.send_json({"type": "response_start"})
                await websocket.send_json({"type": "response_text", "text": cmd_reply})
                try:
                    aud = await _generate_tts(tts_text[:600])
                    if aud:
                        await websocket.send_json({"type": "audio_chunk", "data": base64.b64encode(aud).decode("utf-8"), "index": 0, "format": "mp3"})
                except Exception as _tts_err:
                    logger.debug(f"[V2V] Command TTS failed: {_tts_err}")
                await websocket.send_json({"type": "response_end"})
                logger.info(f"[V2V] Command Center handled '{user_text[:40]}' → {_cmd_intent}")
                return
            if _cmd_intent == "FORBIDDEN":
                deny_text = _cmd_res.get("reply") or "Not allowed."
                await websocket.send_json({"type": "response_start"})
                await websocket.send_json({"type": "response_text", "text": deny_text})
                try:
                    aud = await _generate_tts(deny_text)
                    if aud:
                        await websocket.send_json({"type": "audio_chunk", "data": base64.b64encode(aud).decode("utf-8"), "index": 0, "format": "mp3"})
                except Exception:
                    pass
                await websocket.send_json({"type": "response_end"})
                return
        except Exception as _cc_err:
            logger.debug(f"[V2V] Command Center check skipped: {_cc_err}")

        # ── STEP 3: FAST SENTIMENT SIDE-PROCESS (instant, <1ms) ──
        emotional_state = _fast_emotional_state(user_text)
        emotion_config = _get_emotion_config(emotional_state["emotion"])

        logger.info(
            f"[V2V] EmotionalState: {emotional_state['emotion']} "
            f"(confidence={emotional_state['confidence']:.2f}, "
            f"keywords={emotional_state['keywords_detected']})"
        )

        # Send emotional state to client immediately
        await websocket.send_json({
            "type": "emotional_state",
            "emotion": emotional_state["emotion"],
            "confidence": emotional_state["confidence"],
            "keywords": emotional_state["keywords_detected"],
            "tts_instruction": emotion_config["tts_instruction"],
        })

        # ── STEP 3: FULL AI SENTIMENT (background, for panic detection + logging) ──
        tone_task = asyncio.create_task(_analyze_tone(user_text, tenant_id))

        # ── STEP 4: BRAIN RECEIVES (EmotionalState + Transcript + LIVE CONTEXT) → Response ──
        ai_text = await _generate_emotion_aware_response(
            history=history,
            emotional_state=emotional_state,
            emotion_config=emotion_config,
            user_text=user_text,
        )

        if not ai_text:
            ai_text = "I'm sorry, could you repeat that?"

        # ── OUTPUT GUARDRAIL ──
        out_guard = guard_output(ai_text, tenant_id=tenant_id)
        if not out_guard["allowed"]:
            ai_text = out_guard["text"]

        history.append({"role": "assistant", "content": ai_text})

        # Send response start
        await websocket.send_json({"type": "response_start"})
        await websocket.send_json({"type": "response_text", "text": ai_text})

        # ── Get Full Tone Sync result (for panic + detailed logging) ──
        tone_result = {}
        try:
            tone_result = await asyncio.wait_for(tone_task, timeout=3.0)
            if tone_result and not tone_result.get("error"):
                await websocket.send_json({
                    "type": "tone_sync",
                    "vibe": tone_result.get("vibe_label", "NEUTRAL"),
                    "emotion": tone_result.get("emotion", "neutral"),
                    "sentiment_score": tone_result.get("sentiment_score", 0.0),
                    "adjustment": tone_result.get("voice_settings", {}),
                    "detected_language": tone_result.get("detected_language", "en"),
                })
        except (asyncio.TimeoutError, Exception) as e:
            logger.debug(f"[V2V] Tone sync timeout/error: {e}")

        # ── PANIC HOOK ──
        panic_triggered = False
        if tone_result.get("should_alert"):
            try:
                panic_result = await _execute_panic_hook(
                    call_id=call_id,
                    user_text=user_text,
                    ai_text=ai_text,
                    history=history,
                    tone_result=tone_result,
                    tenant_id=tenant_id,
                )
                if panic_result.get("panic_triggered"):
                    panic_triggered = True
                    await websocket.send_json({
                        "type": "panic_triggered",
                        "event_id": panic_result.get("event_id", ""),
                        "sentiment_score": panic_result.get("sentiment_score", 0),
                        "emotion": panic_result.get("emotion", ""),
                        "keywords": panic_result.get("detected_keywords", []),
                        "action": panic_result.get("action_taken", "alerts_sent"),
                        "message": "Customer distress detected. Owner has been alerted.",
                    })
                    logger.warning(f"[V2V] PANIC triggered for call {call_id}: {panic_result.get('event_id')}")
            except Exception as e:
                logger.error(f"[V2V] Panic hook error: {e}")

        # ── STEP 5: TTS WITH SENTENCE-LEVEL STREAMING ──
        # 8-word minimum per TTS call to avoid choppy audio.
        # Buffer short sentences into the next chunk.
        selected_voice = emotion_config["voice"]

        if not panic_triggered:
            try:
                import re as _re_tts
                MIN_WORDS_PER_CHUNK = 8

                # Split on sentence boundaries
                raw_sentences = _re_tts.split(r'(?<=[.!?\n])\s+', ai_text)
                raw_sentences = [s.strip() for s in raw_sentences if s.strip()]

                # Buffer short sentences together (8-word minimum)
                tts_chunks = []
                buffer = ""
                for s in raw_sentences:
                    if buffer:
                        buffer += " " + s
                    else:
                        buffer = s
                    if len(buffer.split()) >= MIN_WORDS_PER_CHUNK:
                        tts_chunks.append(buffer)
                        buffer = ""
                if buffer:
                    if tts_chunks:
                        tts_chunks[-1] += " " + buffer  # Append remainder to last chunk
                    else:
                        tts_chunks.append(buffer)

                # Stream each chunk as audio
                for idx, chunk in enumerate(tts_chunks):
                    audio_bytes = await _generate_tts(
                        chunk,
                        voice=selected_voice,
                        user_id=call_id.split("_")[0] if "_" in call_id else None,
                        emotion=emotional_state["emotion"],
                    )
                    if audio_bytes:
                        await websocket.send_json({
                            "type": "audio_chunk",
                            "data": base64.b64encode(audio_bytes).decode("utf-8"),
                            "index": idx,
                            "format": "mp3",
                        })
            except Exception as e:
                logger.warning(f"[V2V] TTS failed, sending text only: {e}")
        else:
            pause_msg = "I understand this is important to you. I'm connecting you with our team right now so they can assist you personally."
            await websocket.send_json({"type": "response_text", "text": pause_msg})
            try:
                pause_audio = await _generate_tts(pause_msg, voice="nova")
                if pause_audio:
                    await websocket.send_json({
                        "type": "audio_chunk",
                        "data": base64.b64encode(pause_audio).decode("utf-8"),
                        "index": 0,
                        "format": "mp3",
                    })
            except Exception:
                pass

        await websocket.send_json({"type": "response_end"})

        # ── LOG TO DB ──
        if db is not None:
            log_data = {
                "user": scrub_pii(user_text),
                "assistant": scrub_pii(ai_text),
                "ts": datetime.now(timezone.utc).isoformat(),
                "emotional_state": emotional_state["emotion"],
                "emotion_confidence": emotional_state["confidence"],
                "emotion_keywords": emotional_state["keywords_detected"],
                "tts_voice": selected_voice,
                "tts_instruction": emotion_config["tts_instruction"],
            }
            if tone_result and not tone_result.get("error"):
                log_data["vibe"] = tone_result.get("vibe_label", "NEUTRAL")
                log_data["sentiment_score"] = tone_result.get("sentiment_score", 0)
            if panic_triggered:
                log_data["panic_triggered"] = True
            await db.aurem_voice_calls.update_one(
                {"call_id": call_id},
                {"$push": {"transcripts": log_data}},
            )

    except Exception as e:
        logger.error(f"[V2V] Process error: {e}")
        await websocket.send_json({"type": "error", "message": str(e)})


async def _transcribe_audio(audio_bytes: bytes, audio_format: str = "webm") -> str:
    """Transcribe audio bytes using Whisper via Emergent LLM Key."""
    try:
        from emergentintegrations.llm.openai import OpenAISpeechToText

        stt = OpenAISpeechToText(api_key=EMERGENT_LLM_KEY)

        # Write to temp file and pass open file handle (not string path)
        suffix = f".{audio_format}" if audio_format in ("webm", "mp3", "wav", "m4a", "mp4") else ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as audio_file:
                result = await stt.transcribe(file=audio_file)
            if result and hasattr(result, 'text'):
                return result.text.strip()
            return str(result).strip()
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"[V2V] Whisper STT error: {e}")
        return ""



import re as _re

async def _try_save_user_name(email: str, user_text: str):
    """Extract name from user's first message and save to ora_leads."""
    if db is None or not email:
        return
    # Common name introduction patterns
    patterns = [
        r"(?:my name is|i'm|i am|this is|call me|it's)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)[\.\,\!]?\s*$",  # Just a name by itself
    ]
    for pat in patterns:
        match = _re.search(pat, user_text, _re.IGNORECASE)
        if match:
            name = match.group(1).strip().title()
            if len(name) >= 2 and len(name) <= 40:
                await db.ora_leads.update_one(
                    {"email": email},
                    {"$set": {"full_name": name, "name_source": "voice", "name_updated_at": datetime.now(timezone.utc).isoformat()}},
                )
                logger.info(f"[V2V] Saved user name: {name} for {email}")
                return


async def _generate_emotion_aware_response(
    history: list,
    emotional_state: dict,
    emotion_config: dict,
    user_text: str = "",
    tz_offset: int = 0,
) -> str:
    """
    Generate AI response with EmotionalState + LIVE CONTEXT via OpenRouter.

    Priority:
    1. OpenRouter with web_search tool (GPT-4o or Claude based on query type)
    2. Emergent LLM Key (GPT-4o) as failover
    """
    try:
        from services.ora_live_context import get_live_context, needs_web_search

        # Build emotion-aware system prompt
        system = SYSTEM_PROMPT_VOICE

        # Inject LIVE CONTEXT (weather, leads, revenue, web search)
        try:
            live_ctx = await get_live_context(db, user_message=user_text, tz_offset=tz_offset)
            system += live_ctx["context_string"]
        except Exception as ctx_err:
            logger.warning(f"[V2V] Live context injection failed: {ctx_err}")

        addendum = emotion_config.get("system_addendum", "")
        if addendum:
            system += f"\n\n--- EMOTIONAL CONTEXT (DO NOT DISCLOSE) ---\n{addendum}"
            system += f"\nDetected emotion: {emotional_state['emotion']} (confidence: {emotional_state['confidence']:.0%})"
            system += f"\nTTS instruction for this turn: {emotion_config['tts_instruction']}"

        # VOICE PRIORITY: Emergent LLM Key (gpt-4o-mini) FIRST for lowest latency.
        # Skip OpenRouter free model rotation — it adds 3-8s of unnecessary latency.
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        context_parts = []
        for msg in history[-6:]:
            role = msg["role"]
            content = msg["content"]
            context_parts.append(f"{'User' if role == 'user' else 'Assistant'}: {content}")
        full_context = "\n".join(context_parts)

        llm = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id="v2v_ws",
            system_message=system,
        ).with_model("openai", LLM_MODEL)

        response = await llm.send_message(UserMessage(text=full_context))
        if response:
            logger.info(f"[V2V] Voice response via Emergent {LLM_MODEL}, {len(response)} chars")
            return response

    except Exception as e:
        logger.error(f"[V2V] LLM error (all paths): {e}")
        return ""


async def _generate_llm_response(history: list, user_text: str = "") -> str:
    """Legacy LLM response (no emotion context). Used by REST fallback."""
    return await _generate_emotion_aware_response(
        history=history,
        emotional_state={"emotion": "neutral", "confidence": 0.1, "keywords_detected": []},
        emotion_config=_get_emotion_config("neutral"),
        user_text=user_text,
    )



async def _generate_tts(text: str, voice: str = None, user_id: str = None, emotion: str = "neutral") -> bytes:
    """
    Dynamic TTS generation with graceful degradation:

    Priority:
    1. Voicebox (local, free, sovereign — via voice.aurem.live)
    2. ElevenLabs (if user has cloned voice AND key is valid)
    3. OpenAI TTS via Emergent Key (default, always available)
    4. Returns empty bytes → frontend uses Web Speech API as final fallback
    """
    try:
        from services.voicebox_service import generate_tts_with_fallback
        audio, provider = await generate_tts_with_fallback(
            text=text[:4096],
            voice=voice or TTS_VOICE,
            language="en",
            user_id=user_id,
            emotion=emotion,
        )
        if audio and len(audio) > 100:
            logger.info(f"[V2V] TTS via {provider} ({len(audio)} bytes)")
            return audio
    except Exception as e:
        logger.warning(f"[V2V] Voicebox fallback chain error: {e}")

    # Final safety net — direct OpenAI TTS
    try:
        from emergentintegrations.llm.openai import OpenAITextToSpeech
        tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
        audio_bytes = await tts.generate_speech(
            text=text[:4096],
            voice=voice or TTS_VOICE,
            model=TTS_MODEL,
        )
        return audio_bytes
    except Exception as e:
        logger.error(f"[V2V] All TTS engines failed: {e}")
        return b""


async def _analyze_tone(text: str, tenant_id: str = "aurem_platform") -> dict:
    """Run Tone Sync sentiment analysis on user speech."""
    try:
        if db is None:
            return {}
        from services.tone_sync_service import get_tone_sync_service
        tone_sync = get_tone_sync_service(db)
        result = await tone_sync.analyze_voice_sentiment(
            tenant_id=tenant_id,
            conversation_id="v2v_stream",
            transcript=text,
            speaker="user",
        )
        return result
    except Exception:
        return {}


async def _execute_panic_hook(call_id: str, user_text: str, ai_text: str, history: list, tone_result: dict, tenant_id: str = "aurem_platform") -> dict:
    """Execute the Panic Hook when PANIC vibe is detected during a V2V call."""
    try:
        if db is None:
            return {"panic_triggered": False}

        from services.aurem_hooks.panic_hook import get_panic_hook
        panic_hook = get_panic_hook(db)

        result = await panic_hook.execute(
            tenant_id=tenant_id,
            conversation_id=call_id,
            conversation_history=history,
            latest_user_message=user_text,
            latest_ai_response=ai_text,
            metadata={
                "source": "v2v_voice",
                "customer": {
                    "name": "Voice Caller",
                    "phone": "N/A",
                    "email": "N/A",
                },
                "tone_result": {
                    "vibe": tone_result.get("vibe_label"),
                    "emotion": tone_result.get("emotion"),
                    "score": tone_result.get("sentiment_score"),
                },
            },
        )
        return result
    except Exception as e:
        logger.error(f"[V2V] Panic hook execution error: {e}")
        return {"panic_triggered": False, "error": str(e)}
