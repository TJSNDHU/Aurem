"""
AUREM Muapi Video Generation Service
=====================================
Integrates Muapi.ai API for text-to-video and image-to-video generation.
Enterprise tier only ($997/mo).

API Pattern:
  1. POST /api/v1/{endpoint} → get request_id
  2. GET /api/v1/predictions/{request_id}/result → poll until completed
  3. POST /api/v1/upload_file → upload product image, get hosted URL
"""
import os
import logging
import httpx
import asyncio
from typing import Dict, Optional

logger = logging.getLogger(__name__)

MUAPI_BASE = "https://api.muapi.ai"

# Default video models (exact Muapi endpoint IDs)
DEFAULT_T2V_MODEL = "wan2.1-text-to-video"
DEFAULT_I2V_MODEL = "wan2.1-image-to-video"

# Style → model mapping (exact Muapi endpoint IDs)
STYLE_MODELS = {
    "product_demo": {"t2v": "wan2.1-text-to-video", "i2v": "wan2.1-image-to-video"},
    "brand_story": {"t2v": "wan2.1-text-to-video", "i2v": "wan2.1-image-to-video"},
    "social_ad": {"t2v": "wan2.1-text-to-video", "i2v": "wan2.1-image-to-video"},
    "tutorial": {"t2v": "wan2.1-text-to-video", "i2v": "wan2.1-image-to-video"},
}


def _get_key() -> str:
    return os.environ.get("MUAPI_API_KEY", "")


def _headers(api_key: str = None) -> Dict:
    key = api_key or _get_key()
    return {"Content-Type": "application/json", "x-api-key": key}


async def _poll_result(request_id: str, api_key: str = None, max_attempts: int = 180, interval: float = 3.0) -> Dict:
    """Poll Muapi for generation result. Videos can take 1-5 minutes."""
    key = api_key or _get_key()
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
                    return {"error": f"Poll failed: {resp.status_code} {resp.text[:200]}"}

                data = resp.json()
                status = (data.get("status") or "").lower()

                if status in ("completed", "succeeded", "success"):
                    output_url = None
                    if data.get("outputs") and len(data["outputs"]) > 0:
                        output_url = data["outputs"][0]
                    elif data.get("url"):
                        output_url = data["url"]
                    elif data.get("output", {}).get("url"):
                        output_url = data["output"]["url"]
                    return {"status": "completed", "video_url": output_url, "raw": data}

                if status in ("failed", "error"):
                    return {"error": data.get("error") or "Generation failed", "status": "failed"}

                # Still processing
                if attempt % 20 == 0:
                    logger.info(f"[Muapi] Still polling {request_id} (attempt {attempt}/{max_attempts})")

            except httpx.TimeoutException:
                continue
            except Exception as e:
                if attempt == max_attempts:
                    return {"error": str(e)}

    return {"error": "Generation timed out after polling"}


async def upload_file(file_bytes: bytes, filename: str, api_key: str = None) -> Dict:
    """Upload a product image to Muapi, get hosted URL."""
    key = api_key or _get_key()
    if not key:
        return {"error": "MUAPI_API_KEY not configured"}

    url = f"{MUAPI_BASE}/api/v1/upload_file"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                url,
                headers={"x-api-key": key},
                files={"file": (filename, file_bytes)},
            )
            if not resp.is_success:
                return {"error": f"Upload failed: {resp.status_code} {resp.text[:200]}"}
            data = resp.json()
            file_url = data.get("url") or data.get("file_url") or (data.get("data", {}).get("url"))
            if not file_url:
                return {"error": "No URL returned from upload"}
            return {"url": file_url}
    except Exception as e:
        return {"error": f"Upload error: {e}"}


async def generate_video(
    prompt: str,
    image_url: Optional[str] = None,
    style: str = "brand_story",
    aspect_ratio: str = "16:9",
    duration: int = 5,
    api_key: str = None,
) -> Dict:
    """
    Generate video via Muapi. Uses image-to-video if image_url provided, else text-to-video.
    Returns {video_url, request_id, model, ...} or {error}.
    """
    key = api_key or _get_key()
    if not key:
        return {"error": "MUAPI_API_KEY not configured. Add key at muapi.ai"}

    style_config = STYLE_MODELS.get(style, STYLE_MODELS["brand_story"])
    is_i2v = bool(image_url)
    model_endpoint = style_config["i2v"] if is_i2v else style_config["t2v"]

    payload = {"prompt": prompt}
    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio
    if duration:
        payload["duration"] = duration
    if is_i2v:
        payload["image_url"] = image_url

    url = f"{MUAPI_BASE}/api/v1/{model_endpoint}"
    logger.info(f"[Muapi] {'I2V' if is_i2v else 'T2V'} → {model_endpoint} | prompt={prompt[:60]}...")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=_headers(key), json=payload)
            if not resp.is_success:
                return {"error": f"Muapi submit failed: {resp.status_code} {resp.text[:300]}"}

            data = resp.json()
            request_id = data.get("request_id") or data.get("id")
            if not request_id:
                # Some models return result immediately
                output_url = data.get("outputs", [None])[0] if data.get("outputs") else data.get("url")
                if output_url:
                    return {"video_url": output_url, "model": model_endpoint, "mode": "i2v" if is_i2v else "t2v"}
                return {"error": "No request_id returned", "raw": data}

        # Poll for result
        result = await _poll_result(request_id, key)
        if result.get("error"):
            return result

        return {
            "video_url": result.get("video_url"),
            "request_id": request_id,
            "model": model_endpoint,
            "mode": "i2v" if is_i2v else "t2v",
            "status": "completed",
        }

    except Exception as e:
        logger.warning(f"[Muapi] Generation failed: {e}")
        return {"error": str(e)}


async def get_balance(api_key: str = None) -> Dict:
    """Check Muapi account balance."""
    key = api_key or _get_key()
    if not key:
        return {"error": "MUAPI_API_KEY not configured"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{MUAPI_BASE}/api/v1/account/balance", headers=_headers(key))
            if resp.is_success:
                return resp.json()
            return {"error": f"Balance check failed: {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}
