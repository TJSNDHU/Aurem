"""
AUREM Voicebox Service — Free Local TTS (ElevenLabs Replacement)
================================================================
Connects to Voicebox on Legion via Cloudflare Tunnel at voice.aurem.live.

Engine priority: VoxCPM2 (primary) → Chatterbox → Qwen3 → LuxTTS → XTTS v2 → Piper
Fallback chain: VoxCPM2/Voicebox → ElevenLabs → OpenAI TTS → Web Speech API

VoxCPM2: 2B params, 30 languages, 48kHz, Apache 2.0, 85.4% voice similarity
         (ElevenLabs: 61.3%). Text-based Voice Design — no reference audio needed.
         Voice cloning from just 3 seconds of audio.

Cost: $0/month vs $22/month ElevenLabs.
"""
import os
import io
import logging
import asyncio
import time
from datetime import datetime, timezone
from typing import Optional, Dict, List

import httpx

logger = logging.getLogger(__name__)

_db = None

VOICEBOX_URL = os.environ.get("VOICEBOX_URL", os.environ.get("SOVEREIGN_VOICE_URL", "https://voice.aurem.live"))
VOICEBOX_ENABLED = os.environ.get("VOICEBOX_ENABLED", "true").lower() == "true"

_config = {
    "url": VOICEBOX_URL,
    "enabled": VOICEBOX_ENABLED,
    "default_engine": os.environ.get("VOICEBOX_ENGINE", "voxcpm2"),
    "default_voice": os.environ.get("VOICEBOX_VOICE", "aura"),
    "default_language": "en",
    "sample_rate": 48000,
    "timeout": 30,
    "last_status": None,
    "last_check": None,
    "consecutive_failures": 0,
    "backoff_until": None,
}

# AURA Voice Design — text-based (VoxCPM2 supports voice design without reference audio)
AURA_VOICE_DESIGN = "(warm, professional, confident woman, clear and calm)"

# Voice design presets for multi-agent voices
VOICE_DESIGNS = {
    "aura": "(warm, professional, confident woman, clear and calm)",
    "sentinel": "(deep, authoritative male, focused and precise)",
    "envoy": "(friendly, energetic female, approachable and clear)",
    "oracle": "(wise, measured male, thoughtful and calm)",
    "closer": "(persuasive, confident female, dynamic and compelling)",
}

_metrics = {
    "total_requests": 0,
    "total_chars": 0,
    "avg_latency_ms": 0,
    "failures": 0,
    "cache_hits": 0,
}

MAX_RETRIES = 2
RETRY_DELAY_S = 1.5
BACKOFF_AFTER_FAILURES = 5
BACKOFF_DURATION_S = 60


def set_db(database):
    global _db
    _db = database


def get_config() -> Dict:
    return {**_config, "metrics": {**_metrics}}


def _is_backed_off() -> bool:
    if _config["backoff_until"] is None:
        return False
    from datetime import datetime as dt
    now = datetime.now(timezone.utc)
    try:
        backoff = dt.fromisoformat(_config["backoff_until"]) if isinstance(_config["backoff_until"], str) else _config["backoff_until"]
        return now < backoff
    except Exception:
        return False


async def _request_with_retry(method: str, path: str, retries: int = MAX_RETRIES, timeout: float = 10.0, **kwargs) -> Optional[httpx.Response]:
    """HTTP request with retry for Cloudflare Tunnel cold starts."""
    if _is_backed_off():
        return None

    url = f"{_config['url'].rstrip('/')}{path}"

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method == "GET":
                    resp = await client.get(url, **kwargs)
                else:
                    resp = await client.post(url, **kwargs)

                if resp.status_code == 200:
                    _config["consecutive_failures"] = 0
                    _config["backoff_until"] = None
                    return resp

                if resp.status_code == 502 and attempt < retries - 1:
                    await asyncio.sleep(RETRY_DELAY_S)
                    continue

                return resp

        except (httpx.ConnectError, httpx.ConnectTimeout):
            if attempt < retries - 1:
                await asyncio.sleep(RETRY_DELAY_S)
            continue
        except httpx.ReadTimeout:
            break
        except Exception:
            break

    _config["consecutive_failures"] += 1
    if _config["consecutive_failures"] >= BACKOFF_AFTER_FAILURES:
        from datetime import timedelta
        _config["backoff_until"] = (datetime.now(timezone.utc) + timedelta(seconds=BACKOFF_DURATION_S)).isoformat()
        logger.warning(f"[Voicebox] {_config['consecutive_failures']} failures — backoff {BACKOFF_DURATION_S}s")

    return None


# ═══════════════════════════════════════════════════════════════
# STATUS & DISCOVERY
# ═══════════════════════════════════════════════════════════════

async def check_status() -> Dict:
    """Check if Voicebox is running on Legion."""
    resp = await _request_with_retry("GET", "/api/health", retries=2, timeout=5.0)

    if resp and resp.status_code == 200:
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        _config["last_status"] = "online"
        _config["last_check"] = datetime.now(timezone.utc).isoformat()
        return {
            "online": True,
            "url": _config["url"],
            "engines": data.get("engines", []),
            "voices": data.get("voices", []),
            "version": data.get("version", "unknown"),
            "tunnel": "cloudflare" if "voice.aurem.live" in _config["url"] else "direct",
        }

    _config["last_status"] = "offline"
    _config["last_check"] = datetime.now(timezone.utc).isoformat()
    return {
        "online": False,
        "url": _config["url"],
        "tunnel": "cloudflare" if "voice.aurem.live" in _config["url"] else "direct",
        "backed_off": _is_backed_off(),
        "consecutive_failures": _config["consecutive_failures"],
        "setup": {
            "step_1": "Install Voicebox on Legion",
            "step_2": "Start Voicebox server (default port 8000)",
            "step_3": "Cloudflare Tunnel: voice.aurem.live → localhost:8000",
            "step_4": "Verify: GET https://voice.aurem.live/api/health",
        },
    }


async def list_engines() -> List[Dict]:
    """List available TTS engines from Voicebox. VoxCPM2 is primary."""
    resp = await _request_with_retry("GET", "/api/engines", retries=1, timeout=5.0)
    if resp and resp.status_code == 200:
        return resp.json() if isinstance(resp.json(), list) else resp.json().get("engines", [])
    return [
        {"id": "voxcpm2", "name": "VoxCPM2", "params": "2B", "languages": 30, "sample_rate": 48000, "similarity": "85.4%", "license": "Apache 2.0", "voice_design": True, "clone_seconds": 3, "primary": True, "status": "offline"},
        {"id": "chatterbox", "name": "Chatterbox", "status": "offline"},
        {"id": "qwen3", "name": "Qwen3 TTS", "status": "offline"},
        {"id": "luxtts", "name": "LuxTTS", "status": "offline"},
        {"id": "xtts_v2", "name": "XTTS v2", "status": "offline"},
        {"id": "piper", "name": "Piper", "status": "offline"},
    ]


async def list_voices() -> List[Dict]:
    """List available/cloned voices from Voicebox."""
    resp = await _request_with_retry("GET", "/api/voices", retries=1, timeout=5.0)
    if resp and resp.status_code == 200:
        return resp.json() if isinstance(resp.json(), list) else resp.json().get("voices", [])
    return [{"id": "aura", "name": "AURA (default)", "cloned": False, "status": "offline"}]


# ═══════════════════════════════════════════════════════════════
# TTS — Text to Speech
# ═══════════════════════════════════════════════════════════════

async def synthesize(
    text: str,
    voice: str = None,
    engine: str = None,
    language: str = None,
    voice_design: str = None,
) -> Optional[bytes]:
    """
    Generate speech audio from text via Voicebox.
    VoxCPM2 supports voice_design text — no reference audio needed.
    Returns raw audio bytes (WAV/MP3) or None if unavailable.
    """
    if not _config["enabled"]:
        return None

    voice = voice or _config["default_voice"]
    engine = engine or _config["default_engine"]
    language = language or _config["default_language"]

    # Auto-inject voice design for VoxCPM2
    if engine == "voxcpm2" and not voice_design:
        voice_design = VOICE_DESIGNS.get(voice, AURA_VOICE_DESIGN)

    _metrics["total_requests"] += 1
    _metrics["total_chars"] += len(text)

    t0 = time.time()

    # For VoxCPM2: prepend voice design tag to text
    synth_text = text[:10000]
    if engine == "voxcpm2" and voice_design:
        synth_text = f"{voice_design}{synth_text}"

    resp = await _request_with_retry(
        "POST", "/api/tts",
        retries=MAX_RETRIES,
        timeout=float(_config["timeout"]),
        json={
            "text": synth_text,
            "voice": voice,
            "engine": engine,
            "language": language,
            "voice_design": voice_design,
            "sample_rate": 48000 if engine == "voxcpm2" else 24000,
        },
    )

    if resp and resp.status_code == 200:
        audio = resp.content
        latency_ms = int((time.time() - t0) * 1000)

        n = _metrics["total_requests"]
        _metrics["avg_latency_ms"] = round(((_metrics["avg_latency_ms"] * (n - 1)) + latency_ms) / n, 1)

        logger.info(f"[Voicebox] TTS: {len(text)} chars → {len(audio)} bytes ({latency_ms}ms, engine={engine}, voice={voice})")

        if _db is not None:
            await _db.voicebox_usage.insert_one({
                "text_length": len(text),
                "audio_size": len(audio),
                "engine": engine,
                "voice": voice,
                "language": language,
                "latency_ms": latency_ms,
                "cost": 0.0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return audio

    _metrics["failures"] += 1
    logger.debug(f"[Voicebox] TTS failed: {resp.status_code if resp else 'no response'}")
    return None


# ═══════════════════════════════════════════════════════════════
# VOICE CLONING
# ═══════════════════════════════════════════════════════════════

async def clone_voice(audio_data: bytes, voice_name: str = "aura", language: str = "en") -> Dict:
    """
    Clone a voice from audio sample.
    VoxCPM2: only 3 seconds needed (vs 6+ for other engines).
    """
    try:
        resp = await _request_with_retry(
            "POST", "/api/clone",
            retries=1,
            timeout=60.0,
            files={"audio": (f"{voice_name}.wav", audio_data, "audio/wav")},
            data={"voice_name": voice_name, "language": language, "engine": _config["default_engine"]},
        )
        if resp and resp.status_code == 200:
            result = resp.json()
            logger.info(f"[Voicebox] Voice cloned: {voice_name}")
            return {"success": True, "voice_id": result.get("voice_id", voice_name), "voice_name": voice_name, "engine": _config["default_engine"]}
        return {"success": False, "error": f"Clone failed: {resp.status_code if resp else 'no response'}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def design_voice(description: str, voice_name: str = "custom") -> Dict:
    """
    VoxCPM2 Text-based Voice Design — create a voice from text description only.
    No reference audio needed. Example: "(warm, professional, confident woman)"
    """
    try:
        resp = await _request_with_retry(
            "POST", "/api/design-voice",
            retries=1,
            timeout=60.0,
            json={"description": description, "voice_name": voice_name, "engine": "voxcpm2"},
        )
        if resp and resp.status_code == 200:
            result = resp.json()
            logger.info(f"[Voicebox] Voice designed: {voice_name} ({description[:50]})")
            return {"success": True, "voice_id": result.get("voice_id", voice_name), "voice_name": voice_name, "description": description}
        return {"success": False, "error": f"Design failed: {resp.status_code if resp else 'no response'}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_voice_designs() -> Dict:
    """Get all voice design presets for AUREM agents."""
    return VOICE_DESIGNS


# ═══════════════════════════════════════════════════════════════
# HIGH-LEVEL TTS WITH FALLBACK CHAIN
# ═══════════════════════════════════════════════════════════════

async def generate_tts_with_fallback(
    text: str,
    voice: str = None,
    engine: str = None,
    language: str = "en",
    user_id: str = None,
    emotion: str = "neutral",
) -> tuple:
    """
    Master TTS function with full fallback chain:
      1. VoxCPM2 via Voicebox (local, free, 85.4% similarity)
      2. Chatterbox via Voicebox (local, free, fallback engine)
      3. ElevenLabs (cloud, paid)
      4. OpenAI TTS (cloud, paid)
      5. Returns empty bytes (browser Web Speech API)

    Returns: (audio_bytes, provider_name)
    """
    # 0. Kokoro-82M (iter 281.3 — primary, zero-cost local model).
    #    Wire via env: KOKORO_API_URL (optionally KOKORO_API_KEY).
    #    Endpoint contract: POST {KOKORO_API_URL}/tts {text, voice}
    #      → audio bytes (wav/mp3). Returns 200 on success.
    #    Failure / unset → falls through to existing chain.
    kokoro_url = os.environ.get("KOKORO_API_URL", "").strip()
    if kokoro_url:
        try:
            import httpx
            headers = {"content-type": "application/json"}
            kokoro_key = os.environ.get("KOKORO_API_KEY", "").strip()
            if kokoro_key:
                headers["authorization"] = f"Bearer {kokoro_key}"
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(
                    f"{kokoro_url.rstrip('/')}/tts",
                    headers=headers,
                    json={
                        "text": text[:4000],
                        "voice": voice or os.environ.get("KOKORO_DEFAULT_VOICE", "af_bella"),
                        "language": language or "en",
                    },
                )
            if r.status_code == 200 and r.content and len(r.content) > 100:
                logger.info(f"[Voicebox] Kokoro-82M: {len(text)} chars → {len(r.content)} bytes")
                return r.content, "kokoro_82m"
        except Exception as e:
            logger.debug(f"[Voicebox] Kokoro-82M unavailable: {e}")

    # 1. VoxCPM2 (existing primary — best similarity, text-based voice design)
    if _config["enabled"]:
        audio = await synthesize(text, voice=voice, engine=engine or "voxcpm2", language=language)
        if audio and len(audio) > 100:
            return audio, "voxcpm2"

    # 2. Chatterbox via Legion Docker (direct — voice.aurem.live)
    voice_node = os.environ.get("VOICE_NODE_URL", "")
    if voice_node:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(f"{voice_node.rstrip('/')}/predict", json={
                    "text": text[:2000], "exaggeration": 0.5, "cfg_weight": 0.5,
                })
                if r.status_code == 200:
                    audio = r.content
                    if audio and len(audio) > 100:
                        return audio, "chatterbox_legion"
        except Exception:
            pass

    # 3. Chatterbox via Voicebox (if VoxCPM2 unavailable on Voicebox)
    if _config["enabled"] and (engine or "voxcpm2") == "voxcpm2":
        audio = await synthesize(text, voice=voice, engine="chatterbox", language=language)
        if audio and len(audio) > 100:
            return audio, "chatterbox"

    # 2. ElevenLabs (if user has voice profile)
    if user_id:
        try:
            from routers.voice_profile_router import resolve_voice_for_tts, generate_elevenlabs_tts
            resolved = await resolve_voice_for_tts(user_id, emotion)
            if resolved.get("provider") == "elevenlabs" and resolved.get("eleven_voice_id"):
                audio = await generate_elevenlabs_tts(
                    text=text[:4096],
                    voice_id=resolved["eleven_voice_id"],
                    settings=resolved.get("eleven_settings", {}),
                )
                if audio and len(audio) > 100:
                    return audio, "elevenlabs"
        except Exception as e:
            logger.debug(f"[Voicebox] ElevenLabs fallback skipped: {e}")

    # 3. OpenAI TTS via Emergent Key
    try:
        from emergentintegrations.llm.openai import OpenAITextToSpeech
        emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
        if emergent_key:
            tts = OpenAITextToSpeech(api_key=emergent_key)
            audio = await tts.generate_speech(
                text=text[:4096],
                voice=voice or "nova",
                model="tts-1",
            )
            if audio and len(audio) > 100:
                return audio, "openai"
    except Exception as e:
        logger.debug(f"[Voicebox] OpenAI TTS fallback failed: {e}")

    # 4. Empty → browser Web Speech API
    return b"", "web_speech_api"
