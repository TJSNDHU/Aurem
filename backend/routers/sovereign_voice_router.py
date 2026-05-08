"""
AUREM Sovereign Voice Router — Local TTS API
=============================================
"""
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

router = APIRouter(prefix="/api/sovereign-voice", tags=["Sovereign Voice"])
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


class SynthesizeRequest(BaseModel):
    text: str
    speaker: str = "ORA"
    language: str = "en"


class NarrateSkillRequest(BaseModel):
    skill_name: str
    response_text: str


@router.get("/status")
async def voice_status(authorization: str = Header(None)):
    await _auth(authorization)
    from services.sovereign_voice import check_voice_available, get_voice_stats
    status = await check_voice_available()
    return {**status, "stats": get_voice_stats()}


@router.post("/synthesize")
async def synthesize(req: SynthesizeRequest, authorization: str = Header(None)):
    await _auth(authorization)
    from services.sovereign_voice import synthesize_speech
    return await synthesize_speech(req.text, req.speaker, req.language)


@router.post("/narrate-skill")
async def narrate_skill(req: NarrateSkillRequest, authorization: str = Header(None)):
    await _auth(authorization)
    from services.sovereign_voice import narrate_skill_response
    return await narrate_skill_response(req.skill_name, req.response_text)


@router.get("/config")
async def voice_config(authorization: str = Header(None)):
    await _auth(authorization)
    from services.sovereign_voice import get_voice_config, check_voice_available
    return {
        "config": get_voice_config(),
        "available": await check_voice_available(),
        "setup": {
            "step_1": "pip install TTS==0.22.0 flask numpy",
            "step_2": "Record 6s .wav → voice_samples/ora_voice.wav",
            "step_3": "python tts_server.py --port 5002",
            "step_4": "cloudflared tunnel --url http://localhost:5002",
            "script": "/app/backend/scripts/tts_server.py",
        },
    }


@router.get("/stats")
async def voice_stats(authorization: str = Header(None)):
    await _auth(authorization)
    from services.sovereign_voice import get_voice_stats
    return get_voice_stats()
