"""
AUREM Voicebox Router — Sovereign Voice API
GET  /api/voicebox/status — health check + engine/voice discovery
GET  /api/voicebox/engines — list TTS engines
GET  /api/voicebox/voices — list available/cloned voices
POST /api/voicebox/tts — generate speech (with fallback chain)
POST /api/voicebox/clone — clone voice from audio sample
GET  /api/voicebox/config — get voicebox configuration
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/voicebox", tags=["Voicebox Sovereign Voice"])
logger = logging.getLogger(__name__)


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        import jwt
        payload = jwt.decode(authorization.replace("Bearer ", ""), os.getenv("JWT_SECRET"), algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def _init():
    from services.voicebox_service import set_db
    try:
        import server
        if hasattr(server, "db"):
            set_db(server.db)
    except Exception:
        pass


@router.get("/status")
async def voicebox_status(authorization: str = Header(None)):
    """Check if Voicebox is running on Legion."""
    await _auth(authorization)
    _init()
    from services.voicebox_service import check_status
    return await check_status()


@router.get("/engines")
async def list_engines(authorization: str = Header(None)):
    """List available TTS engines."""
    await _auth(authorization)
    from services.voicebox_service import list_engines
    engines = await list_engines()
    return {"engines": engines, "count": len(engines)}


@router.get("/voices")
async def list_voices(authorization: str = Header(None)):
    """List available/cloned voices."""
    await _auth(authorization)
    from services.voicebox_service import list_voices
    voices = await list_voices()
    return {"voices": voices, "count": len(voices)}


@router.get("/config")
async def get_config(authorization: str = Header(None)):
    """Get Voicebox configuration and metrics."""
    await _auth(authorization)
    from services.voicebox_service import get_config
    return get_config()


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    engine: Optional[str] = None
    language: Optional[str] = "en"


@router.post("/tts")
async def generate_tts(req: TTSRequest, authorization: str = Header(None)):
    """Generate speech from text. Returns audio bytes with fallback chain."""
    await _auth(authorization)
    _init()
    from services.voicebox_service import generate_tts_with_fallback
    audio, provider = await generate_tts_with_fallback(
        text=req.text, voice=req.voice, engine=req.engine, language=req.language,
    )
    if audio and len(audio) > 100:
        content_type = "audio/wav" if provider == "voicebox" else "audio/mpeg"
        return Response(content=audio, media_type=content_type, headers={
            "X-TTS-Provider": provider,
            "X-TTS-Cost": "$0.00" if provider == "voicebox" else "cloud",
        })
    return {"success": False, "provider": provider, "error": "All TTS engines failed or returned empty audio"}


@router.post("/clone")
async def clone_voice(
    audio: UploadFile = File(...),
    voice_name: str = Form("aura"),
    language: str = Form("en"),
    authorization: str = Header(None),
):
    """Clone a voice from audio sample (VoxCPM2: 3s, others: 6s)."""
    await _auth(authorization)
    from services.voicebox_service import clone_voice as _clone
    audio_data = await audio.read()
    if len(audio_data) < 500:
        raise HTTPException(status_code=400, detail="Audio sample too short (need 3+ seconds for VoxCPM2)")
    result = await _clone(audio_data, voice_name, language)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Clone failed"))
    return result


class DesignVoiceRequest(BaseModel):
    description: str
    voice_name: str = "custom"


@router.post("/design-voice")
async def design_voice(req: DesignVoiceRequest, authorization: str = Header(None)):
    """
    VoxCPM2 Text-based Voice Design — create a voice from text description only.
    No reference audio needed.
    Example: {"description": "(warm, professional, confident woman)", "voice_name": "aura"}
    """
    await _auth(authorization)
    from services.voicebox_service import design_voice as _design
    result = await _design(req.description, req.voice_name)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Voice design failed"))
    return result


@router.get("/voice-designs")
async def get_voice_designs(authorization: str = Header(None)):
    """Get AUREM agent voice design presets (text descriptions for VoxCPM2)."""
    await _auth(authorization)
    from services.voicebox_service import get_voice_designs
    return {"designs": get_voice_designs(), "engine": "voxcpm2", "note": "Text-based voice design — no reference audio needed"}
