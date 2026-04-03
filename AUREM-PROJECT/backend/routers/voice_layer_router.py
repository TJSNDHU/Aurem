"""
ReRoots AI Voice Layer - Voxtral-style TTS with Voice Cloning
Text-to-speech with brand voice, multi-language, and emotional expression
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
import os
import base64
import secrets

router = APIRouter(prefix="/api/voice", tags=["voice-layer"])

# Database reference
db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global db
    db = database


# ═══════════════════════════════════════════════════════════════════════════════
# VOICE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Available voices
VOICES = {
    "brand_aura": {
        "name": "AURA-GEN Brand Voice",
        "description": "Professional, warm, luxury skincare brand voice",
        "language": "en",
        "gender": "female",
        "style": "professional"
    },
    "friendly_assistant": {
        "name": "Friendly Assistant",
        "description": "Casual, helpful customer service voice",
        "language": "en",
        "gender": "female",
        "style": "friendly"
    },
    "professional_male": {
        "name": "Professional Male",
        "description": "Clear, authoritative male voice",
        "language": "en",
        "gender": "male",
        "style": "professional"
    }
}

# Supported languages
LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean"
}

# Emotional tones
TONES = ["neutral", "happy", "calm", "excited", "serious", "empathetic"]


# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class TTSRequest(BaseModel):
    text: str
    voice: str = "brand_aura"
    language: str = "en"
    tone: str = "neutral"
    speed: float = 1.0  # 0.5 to 2.0
    output_format: str = "mp3"  # mp3, wav, ogg

class VoiceCloningRequest(BaseModel):
    voice_name: str
    description: str

class BatchTTSRequest(BaseModel):
    texts: List[str]
    voice: str = "brand_aura"
    language: str = "en"


# ═══════════════════════════════════════════════════════════════════════════════
# TTS GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_tts_openai(text: str, voice: str, speed: float) -> bytes:
    """Generate TTS using OpenAI TTS API"""
    from emergentintegrations.llm.openai.audio_generation import OpenAIAudioGeneration
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise Exception("TTS API key not configured")
    
    # Map voice to OpenAI voices
    voice_map = {
        "brand_aura": "nova",
        "friendly_assistant": "shimmer",
        "professional_male": "onyx"
    }
    
    openai_voice = voice_map.get(voice, "nova")
    
    audio_gen = OpenAIAudioGeneration(api_key=api_key)
    
    audio_bytes = audio_gen.generate_speech(
        text=text,
        voice=openai_voice,
        model="tts-1-hd",
        speed=speed
    )
    
    return audio_bytes


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/voices")
async def get_available_voices():
    """Get all available voices"""
    return {
        "voices": VOICES,
        "languages": LANGUAGES,
        "tones": TONES,
        "custom_voices": await get_custom_voices()
    }


async def get_custom_voices():
    """Get user-created custom voices"""
    if db is None:
        return []
    voices = await db.custom_voices.find(
        {},
        {"_id": 0, "voice_id": 1, "name": 1, "description": 1}
    ).to_list(20)
    return voices


@router.post("/generate")
async def generate_speech(data: TTSRequest):
    """Generate speech from text"""
    try:
        # Validate voice
        if data.voice not in VOICES:
            custom = await db.custom_voices.find_one({"voice_id": data.voice})
            if not custom:
                raise HTTPException(status_code=400, detail=f"Unknown voice: {data.voice}")
        
        # Generate audio
        audio_bytes = await generate_tts_openai(data.text, data.voice, data.speed)
        
        if not audio_bytes:
            raise HTTPException(status_code=500, detail="Failed to generate audio")
        
        # Save to file
        audio_id = f"tts_{secrets.token_hex(8)}"
        output_path = f"/tmp/{audio_id}.{data.output_format}"
        
        with open(output_path, "wb") as f:
            f.write(audio_bytes)
        
        # Log generation
        await db.tts_generations.insert_one({
            "audio_id": audio_id,
            "text": data.text[:200],
            "voice": data.voice,
            "language": data.language,
            "tone": data.tone,
            "duration_estimate": len(data.text) / 15,  # Rough estimate
            "created_at": datetime.now(timezone.utc)
        })
        
        # Return base64 encoded audio
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        
        return {
            "audio_id": audio_id,
            "audio_base64": audio_base64,
            "format": data.output_format,
            "download_url": f"/api/voice/download/{audio_id}",
            "duration_estimate": len(data.text) / 15
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")


@router.get("/download/{audio_id}")
async def download_audio(audio_id: str):
    """Download generated audio file"""
    # Try different formats
    for fmt in ["mp3", "wav", "ogg"]:
        path = f"/tmp/{audio_id}.{fmt}"
        if os.path.exists(path):
            return FileResponse(
                path,
                media_type=f"audio/{fmt}",
                filename=f"{audio_id}.{fmt}"
            )
    
    raise HTTPException(status_code=404, detail="Audio file not found")


@router.post("/batch")
async def batch_generate_speech(data: BatchTTSRequest):
    """Generate speech for multiple texts"""
    results = []
    
    for i, text in enumerate(data.texts[:20]):  # Limit to 20
        try:
            audio_bytes = await generate_tts_openai(text, data.voice, 1.0)
            audio_id = f"tts_{secrets.token_hex(6)}_{i}"
            
            results.append({
                "index": i,
                "text": text[:50] + "..." if len(text) > 50 else text,
                "audio_id": audio_id,
                "audio_base64": base64.b64encode(audio_bytes).decode("utf-8"),
                "success": True
            })
        except Exception as e:
            results.append({
                "index": i,
                "text": text[:50] + "..." if len(text) > 50 else text,
                "success": False,
                "error": str(e)
            })
    
    return {
        "total": len(data.texts),
        "generated": sum(1 for r in results if r["success"]),
        "results": results
    }


@router.post("/clone/upload")
async def upload_voice_sample(
    voice_name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...)
):
    """Upload voice sample for cloning (placeholder for future implementation)"""
    # Validate file type
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="File must be an audio file")
    
    # Read audio file
    audio_bytes = await file.read()
    
    # Save voice sample
    voice_id = f"custom_{secrets.token_hex(8)}"
    sample_path = f"/app/uploads/voice_samples/{voice_id}.wav"
    
    os.makedirs(os.path.dirname(sample_path), exist_ok=True)
    with open(sample_path, "wb") as f:
        f.write(audio_bytes)
    
    # Store voice record
    await db.custom_voices.insert_one({
        "voice_id": voice_id,
        "name": voice_name,
        "description": description,
        "sample_path": sample_path,
        "sample_duration": len(audio_bytes) / 44100 / 2,  # Rough estimate
        "status": "pending_training",
        "created_at": datetime.now(timezone.utc)
    })
    
    return {
        "voice_id": voice_id,
        "name": voice_name,
        "status": "pending_training",
        "message": "Voice sample uploaded. Clone training is a placeholder feature."
    }


@router.post("/whatsapp-voice-note")
async def generate_whatsapp_voice_note(
    text: str,
    voice: str = "brand_aura",
    recipient_phone: Optional[str] = None
):
    """Generate voice note formatted for WhatsApp"""
    # Generate speech
    audio_bytes = await generate_tts_openai(text, voice, 1.0)
    
    audio_id = f"wa_voice_{secrets.token_hex(8)}"
    output_path = f"/tmp/{audio_id}.ogg"
    
    # Save as OGG (WhatsApp preferred format)
    # In production, convert MP3 to OGG using ffmpeg
    with open(output_path.replace(".ogg", ".mp3"), "wb") as f:
        f.write(audio_bytes)
    
    # Log
    await db.whatsapp_voice_notes.insert_one({
        "audio_id": audio_id,
        "text": text[:200],
        "voice": voice,
        "recipient": recipient_phone,
        "created_at": datetime.now(timezone.utc)
    })
    
    return {
        "audio_id": audio_id,
        "audio_base64": base64.b64encode(audio_bytes).decode("utf-8"),
        "format": "mp3",
        "message": "Voice note ready for WhatsApp"
    }


@router.get("/history")
async def get_tts_history(limit: int = 20):
    """Get TTS generation history"""
    history = await db.tts_generations.find(
        {},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"history": history}
