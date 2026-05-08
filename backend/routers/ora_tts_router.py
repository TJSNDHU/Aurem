"""
ORA TTS Router — text-to-speech for ORA chat replies (iter 282t)
================================================================

Single endpoint `POST /api/ora/tts` that accepts {text, voice} and returns
a base64-encoded mp3 so the frontend can play ORA's reply through the
phone speaker. Uses OpenAI TTS via the Emergent universal LLM key — no
extra credentials required.

Frontend usage:
  const r = await fetch('/api/ora/tts', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({text, voice: 'shimmer'})
  });
  const {audio_base64} = await r.json();
  new Audio(`data:audio/mp3;base64,${audio_base64}`).play();
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ora", tags=["ora-tts"])

_VALID_VOICES = {"alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"}
_MAX_CHARS = 4000  # OpenAI hard cap is 4096; trim for safety.

# Cached engine (lazy init — avoids import-time crash if key missing)
_tts_engine = None


def _get_tts():
    global _tts_engine
    if _tts_engine is not None:
        return _tts_engine
    key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if not key:
        raise RuntimeError("EMERGENT_LLM_KEY not configured")
    from emergentintegrations.llm.openai import OpenAITextToSpeech
    _tts_engine = OpenAITextToSpeech(api_key=key)
    return _tts_engine


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=_MAX_CHARS)
    voice: Optional[str] = "shimmer"  # warm, friendly default for ORA
    speed: Optional[float] = 1.0
    model: Optional[str] = "tts-1"  # tts-1 = fast; tts-1-hd = better quality


class TTSResponse(BaseModel):
    audio_base64: str
    voice: str
    model: str
    chars: int


@router.post("/tts", response_model=TTSResponse)
async def ora_tts(req: TTSRequest):
    """Generate an mp3 from ORA's reply text. Returns base64 so the frontend
    can build a `data:audio/mp3;base64,...` URI and play with HTMLAudioElement.
    """
    voice = (req.voice or "shimmer").lower().strip()
    if voice not in _VALID_VOICES:
        voice = "shimmer"

    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text cannot be empty")
    if len(text) > _MAX_CHARS:
        text = text[:_MAX_CHARS]

    speed = max(0.25, min(float(req.speed or 1.0), 4.0))
    model = "tts-1-hd" if (req.model or "").lower() == "tts-1-hd" else "tts-1"

    try:
        tts = _get_tts()
        audio_b64 = await tts.generate_speech_base64(
            text=text,
            model=model,
            voice=voice,
            speed=speed,
        )
    except RuntimeError as e:
        logger.warning(f"[ora-tts] config error: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[ora-tts] generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"tts_error: {str(e)[:200]}")

    return TTSResponse(
        audio_base64=audio_b64,
        voice=voice,
        model=model,
        chars=len(text),
    )
