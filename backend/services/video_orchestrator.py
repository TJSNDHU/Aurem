"""
AUREM Video Orchestrator — Multi-Provider Fallback Chain
=========================================================
Priority chain:
  1. Muapi Seedance 2.0 (best quality, I2V + T2V)
  2. Muapi HappyHorse 1.0 (1080p + audio)
  3. ModelsLab Ultra (fallback)

Also handles:
  - ORA Lip Sync Avatar (Muapi infinitetalk)
  - Video Extend (Muapi extend)

Tier enforcement:
  - Starter: No video
  - Growth: 480p basic, 10 videos/month (ModelsLab text2video only)
  - Enterprise: Full HD + character + extend + lip sync (all providers)
"""
import os
import logging
import asyncio
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

MUAPI_BASE = "https://api.muapi.ai"
MODELSLAB_BASE = "https://modelslab.com/api/v6"


# ═══════════════════════════════════════════════════════════
# FALLBACK MONITOR HOOKS (silent — never raise)
# ═══════════════════════════════════════════════════════════

def _get_fallback_db():
    """Best-effort DB handle for fallback logging."""
    try:
        from server import db as _db
        if _db is not None:
            return _db
    except Exception:
        pass
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL", "").strip().strip('"').strip("'")
        db_name = os.environ.get("DB_NAME", "aurem_db").strip().strip('"').strip("'")
        if mongo_url:
            return AsyncIOMotorClient(mongo_url)[db_name]
    except Exception:
        pass
    return None


async def _fb_log(db, service, primary, used, result, reason=None):
    try:
        from services.fallback_monitor import log_fallback
        await log_fallback(db, service=service, primary=primary, used=used,
                           result=result, reason=reason)
    except Exception:
        pass


async def _fb_fail(db, service, primary, reason):
    try:
        from services.fallback_monitor import record_primary_failure
        await record_primary_failure(db, service=service, primary=primary, reason=reason)
    except Exception:
        pass


def _muapi_key() -> str:
    return os.environ.get("MUAPI_API_KEY", "")


def _modelslab_key() -> str:
    return os.environ.get("MODELSLAB_API_KEY", "")


# ═══════════════════════════════════════════════════════════
# MUAPI HELPERS (Seedance + HappyHorse + InfiniteTalk)
# ═══════════════════════════════════════════════════════════

async def _muapi_submit(endpoint: str, payload: dict) -> Dict:
    """Submit a job to Muapi API."""
    import httpx
    key = _muapi_key()
    if not key:
        return {"error": "MUAPI_API_KEY not configured"}
    url = f"{MUAPI_BASE}/api/v1/{endpoint}"
    headers = {"Content-Type": "application/json", "x-api-key": key}
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if not resp.is_success:
                return {"error": f"Muapi {endpoint}: {resp.status_code} {resp.text[:200]}"}
            data = resp.json()
            return {"request_id": data.get("request_id") or data.get("id"), "data": data}
    except Exception as e:
        return {"error": f"Muapi {endpoint}: {e}"}


async def _muapi_poll(request_id: str, max_attempts: int = 120, interval: float = 4.0) -> Dict:
    """Poll Muapi for result."""
    import httpx
    key = _muapi_key()
    url = f"{MUAPI_BASE}/api/v1/predictions/{request_id}/result"
    headers = {"Content-Type": "application/json", "x-api-key": key}
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(1, max_attempts + 1):
            await asyncio.sleep(interval)
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code >= 500:
                    continue
                if not resp.is_success:
                    return {"error": f"Poll failed: {resp.status_code}"}
                data = resp.json()
                status = (data.get("status") or "").lower()
                if status in ("completed", "succeeded", "success"):
                    output_url = None
                    if data.get("outputs"):
                        output_url = data["outputs"][0]
                    elif data.get("url"):
                        output_url = data["url"]
                    elif data.get("output", {}).get("url"):
                        output_url = data["output"]["url"]
                    return {"status": "completed", "video_url": output_url, "raw": data}
                if status in ("failed", "error"):
                    return {"error": data.get("error") or "Generation failed"}
            except Exception:
                if attempt == max_attempts:
                    return {"error": "Poll timeout"}
    return {"error": "Poll timeout"}


# ═══════════════════════════════════════════════════════════
# MODELSLAB HELPERS
# ═══════════════════════════════════════════════════════════

async def _modelslab_submit(endpoint: str, payload: dict) -> Dict:
    """Submit a job to ModelsLab API."""
    import httpx
    key = _modelslab_key()
    if not key:
        return {"error": "MODELSLAB_API_KEY not configured"}
    payload["key"] = key
    url = f"{MODELSLAB_BASE}/video/{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            if not resp.is_success:
                return {"error": f"ModelsLab {endpoint}: {resp.status_code} {resp.text[:200]}"}
            data = resp.json()
            status = (data.get("status") or "").lower()
            if status == "success":
                output = data.get("output") or data.get("proxy_links") or []
                return {"status": "completed", "video_url": output[0] if output else None, "data": data}
            if status == "error":
                return {"error": data.get("message") or "ModelsLab error"}
            # Processing — need to poll
            return {"request_id": data.get("id"), "data": data}
    except Exception as e:
        return {"error": f"ModelsLab {endpoint}: {e}"}


async def _modelslab_poll(request_id, max_attempts: int = 120, interval: float = 5.0) -> Dict:
    """Poll ModelsLab for result."""
    import httpx
    key = _modelslab_key()
    url = f"{MODELSLAB_BASE}/video/fetch/{request_id}"
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(1, max_attempts + 1):
            await asyncio.sleep(interval)
            try:
                resp = await client.post(url, json={"key": key}, headers={"Content-Type": "application/json"})
                if not resp.is_success:
                    continue
                data = resp.json()
                status = (data.get("status") or "").lower()
                if status == "success":
                    output = data.get("output") or data.get("proxy_links") or []
                    return {"status": "completed", "video_url": output[0] if output else None}
                if status in ("failed", "error"):
                    return {"error": data.get("message") or "Failed"}
            except Exception:
                if attempt == max_attempts:
                    return {"error": "Poll timeout"}
    return {"error": "Poll timeout"}


# ═══════════════════════════════════════════════════════════
# PROVIDER 1: MUAPI SEEDANCE 2.0 (Best quality)
# ═══════════════════════════════════════════════════════════

async def _try_muapi_seedance(prompt: str, image_url: str = None, duration: int = 5, aspect_ratio: str = "16:9") -> Dict:
    """Try Muapi Seedance 2.0 — I2V or T2V."""
    if image_url:
        payload = {"prompt": prompt, "image_url": image_url, "duration": duration, "aspect_ratio": aspect_ratio}
        result = await _muapi_submit("seedance-2.0-i2v", payload)
    else:
        payload = {"prompt": prompt, "duration": duration, "aspect_ratio": aspect_ratio}
        result = await _muapi_submit("wan2.1-text-to-video", payload)

    if result.get("error"):
        return result
    rid = result.get("request_id")
    if not rid:
        return {"error": "No request_id from Muapi Seedance"}
    poll = await _muapi_poll(rid)
    if poll.get("error"):
        return poll
    return {"video_url": poll.get("video_url"), "provider": "muapi_seedance", "request_id": rid}


# ═══════════════════════════════════════════════════════════
# PROVIDER 2: MUAPI HAPPYHORSE 1.0 (1080p + audio)
# ═══════════════════════════════════════════════════════════

async def _try_muapi_happyhorse(prompt: str, image_url: str = None, duration: int = 5, aspect_ratio: str = "16:9") -> Dict:
    """Try Muapi HappyHorse 1.0 — 1080p with audio."""
    payload = {"prompt": prompt, "duration": duration, "aspect_ratio": aspect_ratio}
    if image_url:
        payload["image_url"] = image_url
    endpoint = "happyhorse-1.0-i2v" if image_url else "happyhorse-1.0-t2v"
    result = await _muapi_submit(endpoint, payload)
    if result.get("error"):
        return result
    rid = result.get("request_id")
    if not rid:
        return {"error": "No request_id from HappyHorse"}
    poll = await _muapi_poll(rid)
    if poll.get("error"):
        return poll
    return {"video_url": poll.get("video_url"), "provider": "muapi_happyhorse", "request_id": rid}


# ═══════════════════════════════════════════════════════════
# PROVIDER 3: MODELSLAB (Fallback)
# ═══════════════════════════════════════════════════════════

async def _try_modelslab(prompt: str, image_url: str = None, duration: int = 5, aspect_ratio: str = "16:9", quality: str = "high") -> Dict:
    """Try ModelsLab text2video_ultra or img2video_ultra."""
    ar_map = {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (720, 720)}
    w, h = ar_map.get(aspect_ratio, (1280, 720))

    if image_url:
        payload = {
            "prompt": prompt, "init_image": image_url, "model_id": "wan2.2",
            "resolution": min(h, 720), "num_frames": max(25, duration * 15),
            "num_inference_steps": 25, "guidance_scale": 4.0,
            "portrait": h > w, "negative_prompt": "blur, distorted, low quality",
        }
        result = await _modelslab_submit("img2video_ultra", payload)
    else:
        payload = {
            "prompt": prompt, "width": w, "height": h, "duration": duration,
            "output_type": "mp4", "negative_prompt": "blur, distorted, low quality",
        }
        endpoint = "text2video_ultra" if quality == "high" else "text2video"
        result = await _modelslab_submit(endpoint, payload)

    if result.get("error"):
        return result
    if result.get("status") == "completed":
        return {"video_url": result.get("video_url"), "provider": "modelslab"}
    rid = result.get("request_id")
    if not rid:
        return {"error": "No request_id from ModelsLab"}
    poll = await _modelslab_poll(rid)
    if poll.get("error"):
        return poll
    return {"video_url": poll.get("video_url"), "provider": "modelslab", "request_id": rid}


# ═══════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR — Fallback Chain
# ═══════════════════════════════════════════════════════════

async def generate_video(
    prompt: str,
    image_url: str = None,
    duration: int = 5,
    aspect_ratio: str = "16:9",
    tier: str = "enterprise",
) -> Dict:
    """
    Generate video with multi-provider fallback chain.
    Enterprise: Muapi Seedance → HappyHorse → ModelsLab (HD)
    Growth: ModelsLab text2video only (480p, no I2V)
    Starter: Blocked
    """
    if tier == "starter":
        return {"error": "upgrade_required", "message": "Video generation requires Growth or Enterprise plan"}

    # Growth tier: ModelsLab 480p text-to-video only
    if tier == "growth":
        if image_url:
            return {"error": "upgrade_required", "message": "Image-to-video requires Enterprise plan. Growth supports text-to-video only."}
        logger.info("[VideoOrch] Growth tier → ModelsLab 480p")
        result = await _try_modelslab(prompt, duration=duration, aspect_ratio=aspect_ratio, quality="basic")
        if result.get("error"):
            return {"error": result["error"], "provider_chain": ["modelslab"]}
        result["quality"] = "480p"
        return result

    # Enterprise tier: Full fallback chain
    providers_tried = []
    db = _get_fallback_db()

    # 1. Muapi Seedance
    logger.info("[VideoOrch] Enterprise → trying Muapi Seedance 2.0")
    r1 = await _try_muapi_seedance(prompt, image_url, duration, aspect_ratio)
    if r1.get("video_url"):
        r1["quality"] = "HD"
        r1["provider_chain"] = ["muapi_seedance"]
        await _fb_log(db, "video", "muapi", "muapi_seedance", "success", None)
        try:
            from services.fallback_monitor import reset_primary_failure
            await reset_primary_failure(db, service="video", primary="muapi")
        except Exception:
            pass
        return r1
    providers_tried.append(f"muapi_seedance: {r1.get('error', 'unknown')}")

    # 2. HappyHorse
    logger.info("[VideoOrch] Seedance failed → trying HappyHorse 1.0")
    r2 = await _try_muapi_happyhorse(prompt, image_url, duration, aspect_ratio)
    if r2.get("video_url"):
        r2["quality"] = "1080p"
        r2["provider_chain"] = providers_tried + ["muapi_happyhorse"]
        await _fb_log(db, "video", "muapi", "muapi_happyhorse", "success", None)
        return r2
    providers_tried.append(f"happyhorse: {r2.get('error', 'unknown')}")

    # Muapi both tiers failed → register one primary-failure for alerting
    await _fb_fail(db, "video", "muapi", providers_tried[-1])

    # 3. ModelsLab fallback
    logger.info("[VideoOrch] HappyHorse failed → trying ModelsLab")
    r3 = await _try_modelslab(prompt, image_url, duration, aspect_ratio, quality="high")
    if r3.get("video_url"):
        r3["quality"] = "HD"
        r3["provider_chain"] = providers_tried + ["modelslab"]
        await _fb_log(db, "video", "muapi", "modelslab", "fallback",
                      reason=f"muapi failed: {providers_tried[-1]}")
        return r3
    providers_tried.append(f"modelslab: {r3.get('error', 'unknown')}")

    await _fb_log(db, "video", "muapi", None, "error",
                  reason=" | ".join(providers_tried))
    return {
        "error": "All video providers failed. Please add credits to Muapi (muapi.ai) or ModelsLab (modelslab.com).",
        "provider_chain": providers_tried,
    }


# ═══════════════════════════════════════════════════════════
# ORA LIP SYNC AVATAR (Enterprise Only)
# ═══════════════════════════════════════════════════════════

async def create_ora_avatar(avatar_image_url: str) -> Dict:
    """Create ORA character via Muapi for lip sync videos."""
    payload = {
        "image_url": avatar_image_url,
        "description": "Professional AI business assistant, gold and black theme, confident executive look",
    }
    result = await _muapi_submit("create-character", payload)
    if result.get("error"):
        return result
    rid = result.get("request_id")
    if rid:
        poll = await _muapi_poll(rid)
        return {"character_id": rid, "status": poll.get("status", "created")}
    return {"character_id": result.get("data", {}).get("id", ""), "status": "created"}


async def generate_lip_sync_video(avatar_image_url: str, audio_url: str) -> Dict:
    """Generate ORA talking avatar via Muapi InfiniteTalk."""
    payload = {
        "image_url": avatar_image_url,
        "audio_url": audio_url,
    }
    result = await _muapi_submit("infinitetalk-image-to-video", payload)
    if result.get("error"):
        return result
    rid = result.get("request_id")
    if not rid:
        return {"error": "No request_id from InfiniteTalk"}
    poll = await _muapi_poll(rid, max_attempts=90)
    if poll.get("error"):
        return poll
    return {"video_url": poll.get("video_url"), "provider": "muapi_infinitetalk", "request_id": rid}


# ═══════════════════════════════════════════════════════════
# VIDEO EXTEND (Enterprise Only)
# ═══════════════════════════════════════════════════════════

async def extend_video(request_id: str, prompt: str, duration: int = 5) -> Dict:
    """Extend an existing video via Muapi."""
    payload = {"request_id": request_id, "prompt": prompt, "duration": duration}
    result = await _muapi_submit("extend-video", payload)
    if result.get("error"):
        return result
    rid = result.get("request_id")
    if not rid:
        return {"error": "No request_id from extend"}
    poll = await _muapi_poll(rid)
    if poll.get("error"):
        return poll
    return {"video_url": poll.get("video_url"), "provider": "muapi_extend", "request_id": rid}
