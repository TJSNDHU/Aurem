"""
AUREM Voice Profile Router
===========================
Manages voice presets and custom voice cloning.

Presets:
  - "aura"  → Female warm voice (OpenAI nova)
  - "atlas" → Male authoritative voice (OpenAI onyx)
  - "custom" → User-cloned voice via ElevenLabs IVC

Endpoints:
  GET  /api/voice-profile/         → Get user's voice profile
  PUT  /api/voice-profile/         → Update voice preset
  POST /api/voice-profile/clone    → Clone voice from 30s recording
  GET  /api/voice-profile/presets  → List available presets
"""

import os
import io
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice-profile", tags=["voice-profile"])

db = None

def set_db(database):
    global db
    db = database


# ── Voice Presets ─────────────────────────────────────────────────
VOICE_PRESETS = {
    "aura": {
        "id": "aura",
        "name": "Aura",
        "gender": "Female",
        "description": "Warm, professional female voice with natural cadence",
        "openai_voice": "nova",
        "provider": "openai",
    },
    "atlas": {
        "id": "atlas",
        "name": "Atlas",
        "gender": "Male",
        "description": "Deep, authoritative male voice with confident tone",
        "openai_voice": "onyx",
        "provider": "openai",
    },
}

# ── Emotion → ElevenLabs VoiceSettings overlay ───────────────────
EMOTION_VOICE_SETTINGS = {
    "neutral":    {"stability": 0.50, "similarity_boost": 0.75, "style": 0.0},
    "frustrated": {"stability": 0.70, "similarity_boost": 0.80, "style": 0.3},
    "angry":      {"stability": 0.80, "similarity_boost": 0.85, "style": 0.2},
    "confused":   {"stability": 0.65, "similarity_boost": 0.70, "style": 0.1},
    "happy":      {"stability": 0.40, "similarity_boost": 0.70, "style": 0.5},
    "concerned":  {"stability": 0.65, "similarity_boost": 0.80, "style": 0.2},
    "urgent":     {"stability": 0.55, "similarity_boost": 0.75, "style": 0.4},
}


def _get_eleven_client():
    """Get ElevenLabs async client. Returns None if no API key configured."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        return None
    try:
        from elevenlabs.client import AsyncElevenLabs
        return AsyncElevenLabs(api_key=api_key, timeout=60.0)
    except Exception as e:
        logger.error(f"[VoiceProfile] ElevenLabs client init failed: {e}")
        return None


# ── Models ────────────────────────────────────────────────────────
class VoiceProfileUpdate(BaseModel):
    voice_preset: str  # "aura", "atlas", or "custom"


class VoiceProfileResponse(BaseModel):
    user_id: str
    voice_preset: str
    voice_name: str
    custom_voice_id: Optional[str] = None
    eleven_voice_id: Optional[str] = None
    provider: str
    openai_voice: Optional[str] = None
    updated_at: str


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/presets")
async def list_presets():
    """List all available voice presets."""
    eleven_available = os.environ.get("ELEVENLABS_API_KEY", "") != ""
    presets = list(VOICE_PRESETS.values())
    presets.append({
        "id": "custom",
        "name": "Sync My Voice",
        "gender": "Custom",
        "description": "Clone your own voice from a 30-second recording",
        "provider": "elevenlabs",
        "available": eleven_available,
        "requires": "ElevenLabs API key" if not eleven_available else None,
    })
    return {"presets": presets}


@router.get("/")
async def get_voice_profile(user_id: str = "default"):
    """Get user's current voice profile."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    profile = await db.voice_profiles.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )

    if not profile:
        # Return default profile
        return {
            "user_id": user_id,
            "voice_preset": "aura",
            "voice_name": "Aura",
            "custom_voice_id": None,
            "eleven_voice_id": None,
            "provider": "openai",
            "openai_voice": "nova",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    return profile


@router.put("/")
async def update_voice_profile(body: VoiceProfileUpdate, user_id: str = "default"):
    """Update voice preset selection."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    preset_id = body.voice_preset

    if preset_id in VOICE_PRESETS:
        preset = VOICE_PRESETS[preset_id]
        update_data = {
            "user_id": user_id,
            "voice_preset": preset_id,
            "voice_name": preset["name"],
            "provider": "openai",
            "openai_voice": preset["openai_voice"],
            "custom_voice_id": None,
            "eleven_voice_id": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    elif preset_id == "custom":
        existing = await db.voice_profiles.find_one(
            {"user_id": user_id}, {"_id": 0}
        )
        if not existing or not existing.get("eleven_voice_id"):
            raise HTTPException(
                status_code=400,
                detail="No cloned voice found. Record a voice sample first."
            )
        update_data = {
            "user_id": user_id,
            "voice_preset": "custom",
            "voice_name": existing.get("voice_name", "My Voice"),
            "provider": "elevenlabs",
            "openai_voice": None,
            "custom_voice_id": existing.get("custom_voice_id"),
            "eleven_voice_id": existing.get("eleven_voice_id"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unknown preset: {preset_id}")

    await db.voice_profiles.update_one(
        {"user_id": user_id},
        {"$set": update_data},
        upsert=True,
    )

    return update_data


@router.post("/clone")
async def clone_voice(
    audio_file: UploadFile = File(...),
    voice_name: str = Form("My Voice"),
    user_id: str = Form("default"),
):
    """
    Clone a user's voice from a 30-second audio recording.
    Uses ElevenLabs Instant Voice Cloning (IVC).
    """
    client = _get_eleven_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Voice cloning unavailable. ElevenLabs API key not configured."
        )

    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        audio_content = await audio_file.read()

        if len(audio_content) < 1000:
            raise HTTPException(status_code=400, detail="Audio sample too short. Record at least 30 seconds.")

        logger.info(f"[VoiceProfile] Cloning voice for user {user_id}, {len(audio_content)} bytes")

        voice = await client.voices.ivc.create(
            name=f"AUREM_{user_id}_{voice_name}",
            files=[io.BytesIO(audio_content)],
            description=f"Custom voice clone for AUREM user {user_id}",
        )

        eleven_voice_id = voice.voice_id

        profile_data = {
            "user_id": user_id,
            "voice_preset": "custom",
            "voice_name": voice_name,
            "provider": "elevenlabs",
            "openai_voice": None,
            "custom_voice_id": f"custom_{user_id}",
            "eleven_voice_id": eleven_voice_id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        await db.voice_profiles.update_one(
            {"user_id": user_id},
            {"$set": profile_data},
            upsert=True,
        )

        logger.info(f"[VoiceProfile] Voice cloned: {eleven_voice_id} for user {user_id}")

        return {
            "success": True,
            "voice_id": eleven_voice_id,
            "voice_name": voice_name,
            "message": "Voice cloned successfully. Select 'Sync My Voice' to use it.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[VoiceProfile] Clone failed: {e}")
        raise HTTPException(status_code=500, detail=f"Voice cloning failed: {str(e)}")


# ── Helper: Resolve voice for TTS ────────────────────────────────

async def resolve_voice_for_tts(user_id: str, emotion: str = "neutral") -> dict:
    """
    Resolve which voice + settings to use for TTS.
    Called by v2v_stream_engine before generating audio.

    Returns:
        {
            "provider": "openai" | "elevenlabs",
            "openai_voice": str | None,
            "eleven_voice_id": str | None,
            "eleven_settings": dict | None,  # stability, similarity_boost, style
            "voice_name": str,
        }
    """
    profile = None
    if db is not None:
        profile = await db.voice_profiles.find_one(
            {"user_id": user_id}, {"_id": 0}
        )

    if not profile or profile.get("voice_preset") != "custom":
        # Use OpenAI preset (aura/atlas) — emotion already mapped in v2v engine
        preset_id = (profile or {}).get("voice_preset", "aura")
        preset = VOICE_PRESETS.get(preset_id, VOICE_PRESETS["aura"])
        return {
            "provider": "openai",
            "openai_voice": preset["openai_voice"],
            "eleven_voice_id": None,
            "eleven_settings": None,
            "voice_name": preset["name"],
        }

    # Custom ElevenLabs voice — apply emotion overlay
    eleven_id = profile.get("eleven_voice_id")
    if not eleven_id:
        # Fallback to Aura if clone is missing
        return {
            "provider": "openai",
            "openai_voice": "nova",
            "eleven_voice_id": None,
            "eleven_settings": None,
            "voice_name": "Aura (fallback)",
        }

    # Check ElevenLabs is available
    if not os.environ.get("ELEVENLABS_API_KEY"):
        return {
            "provider": "openai",
            "openai_voice": "nova",
            "eleven_voice_id": None,
            "eleven_settings": None,
            "voice_name": "Aura (ElevenLabs credits exhausted)",
        }

    # Apply emotion → voice settings overlay
    settings = EMOTION_VOICE_SETTINGS.get(emotion, EMOTION_VOICE_SETTINGS["neutral"])

    return {
        "provider": "elevenlabs",
        "openai_voice": None,
        "eleven_voice_id": eleven_id,
        "eleven_settings": settings,
        "voice_name": profile.get("voice_name", "My Voice"),
    }


async def generate_elevenlabs_tts(text: str, voice_id: str, settings: dict) -> bytes:
    """Generate TTS audio using ElevenLabs with emotion-adjusted settings."""
    client = _get_eleven_client()
    if client is None:
        return b""

    try:
        from elevenlabs import VoiceSettings

        voice_settings = VoiceSettings(
            stability=settings.get("stability", 0.5),
            similarity_boost=settings.get("similarity_boost", 0.75),
            style=settings.get("style", 0.0),
            use_speaker_boost=True,
        )

        audio_generator = await client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id="eleven_turbo_v2",
            voice_settings=voice_settings,
            optimize_streaming_latency=4,
        )

        audio_data = b""
        async for chunk in audio_generator:
            audio_data += chunk

        return audio_data

    except Exception as e:
        logger.error(f"[VoiceProfile] ElevenLabs TTS failed: {e}")
        return b""
