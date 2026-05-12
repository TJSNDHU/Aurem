import asyncio
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "qwen2.5-coder:7b-instruct-q4_K_M")


async def is_alive() -> bool:
    """Check if Ollama is reachable and has the configured model."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            if resp.status_code != 200:
                return False
            data = resp.json()
            models = data.get("models", [])
            model_names = [m.get("name", "") for m in models]
            return LOCAL_MODEL in model_names
    except Exception as e:
        logger.debug(f"[llm_local] is_alive check failed: {e}")
        return False


async def ensure_model(model: Optional[str] = None) -> dict:
    """
    Verify model is available; if not, trigger async pull.
    Returns {ok, model, status: 'available' | 'pulling' | 'unreachable'}.
    """
    target_model = model or LOCAL_MODEL
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            if resp.status_code != 200:
                return {"ok": False, "model": target_model, "status": "unreachable"}
            data = resp.json()
            models = data.get("models", [])
            model_names = [m.get("name", "") for m in models]
            if target_model in model_names:
                return {"ok": True, "model": target_model, "status": "available"}
            # Model not present — trigger pull in background
            asyncio.create_task(_pull_model_background(target_model))
            logger.info(f"[llm_local] Model '{target_model}' not found — pulling in background")
            return {"ok": False, "model": target_model, "status": "pulling"}
    except Exception as e:
        logger.debug(f"[llm_local] ensure_model failed: {e}")
        return {"ok": False, "model": target_model, "status": "unreachable"}


async def _pull_model_background(model_name: str):
    """Fire-and-forget model pull."""
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            logger.info(f"[llm_local] Starting pull for '{model_name}'...")
            resp = await client.post(
                f"{OLLAMA_URL}/api/pull",
                json={"name": model_name}
            )
            if resp.status_code == 200:
                logger.info(f"[llm_local] Pull completed for '{model_name}'")
            else:
                logger.warning(f"[llm_local] Pull failed for '{model_name}': HTTP {resp.status_code}")
    except Exception as e:
        logger.error(f"[llm_local] Pull error for '{model_name}': {e}")


async def call_local(
    system: str,
    user: str,
    max_tokens: int = 1200,
    timeout_s: float = 90.0
) -> Optional[str]:
    """
    Call Ollama /api/generate with raw prompt (Qwen2.5 chat template).
    Returns generated text or None on failure.
    """
    _BT = chr(96) * 3
    prompt = (
        f"<|im_start|>system\n{system}<|im_end|>\n"
        f"<|im_start|>user\n{user}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": LOCAL_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.7
                    }
                }
            )
            if resp.status_code != 200:
                logger.warning(f"[llm_local] call_local returned HTTP {resp.status_code}")
                return None
            data = resp.json()
            return data.get("response", "").strip() or None
    except Exception as e:
        logger.debug(f"[llm_local] call_local failed: {e}")
        return None


async def call_local_chat(
    messages: list[dict],
    max_tokens: int = 1200,
    timeout_s: float = 90.0
) -> Optional[str]:
    """
    Call Ollama /api/chat with standard messages array.
    Returns assistant content or None on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": LOCAL_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.7
                    }
                }
            )
            if resp.status_code != 200:
                logger.warning(f"[llm_local] call_local_chat returned HTTP {resp.status_code}")
                return None
            data = resp.json()
            msg = data.get("message", {})
            return msg.get("content", "").strip() or None
    except Exception as e:
        logger.debug(f"[llm_local] call_local_chat failed: {e}")
        return None