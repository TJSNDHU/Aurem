"""
AUREM ModelsLab Video Generation Service
==========================================
Integrates ModelsLab API v6 for video generation using Seedance 2 Multi-Reference.
Enterprise tier only ($997/mo).

API Pattern:
  1. POST /api/v6/video/seedance2_multi_reference → get request id
  2. POST /api/v6/video/fetch/{id} → poll until output ready
"""
import os
import logging
import httpx
import asyncio
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

MODELSLAB_BASE = "https://modelslab.com/api/v6"


def _get_key() -> str:
    return os.environ.get("MODELSLAB_API_KEY", "")


async def _poll_result(request_id, api_key: str = None, max_attempts: int = 120, interval: float = 5.0) -> Dict:
    """Poll ModelsLab fetch endpoint until video is ready."""
    key = api_key or _get_key()
    url = f"{MODELSLAB_BASE}/video/fetch/{request_id}"

    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(1, max_attempts + 1):
            await asyncio.sleep(interval)
            try:
                resp = await client.post(url, json={"key": key}, headers={"Content-Type": "application/json"})
                if resp.status_code >= 500:
                    continue
                if not resp.is_success:
                    return {"error": f"Fetch failed: {resp.status_code} {resp.text[:200]}"}

                data = resp.json()
                status = (data.get("status") or "").lower()

                if status == "success":
                    output = data.get("output") or data.get("proxy_links") or []
                    video_url = output[0] if output else None
                    return {"status": "completed", "video_url": video_url, "output": output, "raw": data}

                if status in ("failed", "error"):
                    return {"error": data.get("message") or "Generation failed", "status": "failed"}

                # Still processing
                if attempt % 12 == 0:
                    eta = data.get("eta", "?")
                    logger.info(f"[ModelsLab] Still polling {request_id} (attempt {attempt}, eta={eta}s)")

            except httpx.TimeoutException:
                continue
            except Exception as e:
                if attempt == max_attempts:
                    return {"error": str(e)}

    return {"error": "Generation timed out after polling"}


async def generate_video(
    prompt: str,
    ref_images: Optional[List[str]] = None,
    negative_prompt: str = "blur, distorted, low quality, watermark, text overlay",
    width: int = 1280,
    height: int = 720,
    duration: int = 5,
    api_key: str = None,
) -> Dict:
    """
    Generate video via ModelsLab Seedance 2 Multi-Reference.
    Supports product image references for brand-consistent video.
    Returns {video_url, request_id, ...} or {error}.
    """
    key = api_key or _get_key()
    if not key:
        return {"error": "MODELSLAB_API_KEY not configured. Get key at modelslab.com"}

    payload = {
        "key": key,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "webhook": None,
        "track_id": None,
    }

    if ref_images:
        # Image-to-Video Ultra — uses init_image + portrait mode
        payload["init_image"] = ref_images[0]
        payload["model_id"] = "wan2.2"
        payload["resolution"] = min(height, 720)
        payload["num_frames"] = max(25, duration * 15)
        payload["num_inference_steps"] = 25
        payload["guidance_scale"] = 4.0
        payload["portrait"] = height > width  # 9:16 = portrait
        url = f"{MODELSLAB_BASE}/video/img2video_ultra"
        mode = "i2v"
        model_name = "img2video-ultra"
    else:
        # Text-to-Video Ultra
        payload["width"] = width
        payload["height"] = height
        payload["duration"] = duration
        payload["output_type"] = "mp4"
        url = f"{MODELSLAB_BASE}/video/text2video_ultra"
        mode = "t2v"
        model_name = "text2video-ultra"

    logger.info(f"[ModelsLab] {mode} | endpoint={url.split('/')[-1]} | prompt={prompt[:60]}...")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers={"Content-Type": "application/json"})
            if not resp.is_success:
                return {"error": f"ModelsLab submit failed: {resp.status_code} {resp.text[:300]}"}

            data = resp.json()
            status = (data.get("status") or "").lower()

            # Immediate success (rare but possible)
            if status == "success":
                output = data.get("output") or data.get("proxy_links") or []
                video_url = output[0] if output else None
                return {
                    "video_url": video_url,
                    "output": output,
                    "model": model_name,
                    "mode": mode,
                    "status": "completed",
                }

            if status == "error":
                return {"error": data.get("message") or "ModelsLab error", "raw": data}

            # Processing — need to poll
            request_id = data.get("id")
            if not request_id:
                # Check future_links
                future = data.get("future_links") or []
                if future:
                    return {
                        "video_url": future[0],
                        "future_links": future,
                        "model": model_name,
                        "mode": mode,
                        "status": "processing",
                        "eta": data.get("eta"),
                    }
                return {"error": "No request ID returned", "raw": data}

        # Poll for result
        result = await _poll_result(request_id, key)
        if result.get("error"):
            return result

        return {
            "video_url": result.get("video_url"),
            "output": result.get("output", []),
            "request_id": request_id,
            "model": model_name,
            "mode": mode,
            "status": "completed",
        }

    except Exception as e:
        logger.warning(f"[ModelsLab] Generation failed: {e}")
        return {"error": str(e)}
