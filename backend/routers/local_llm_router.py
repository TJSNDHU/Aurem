"""
AUREM Sovereign Node — Local LLM Configuration Router
=====================================================
Manage Ollama connection for local inference (llama3.1 via Cloudflare Tunnel).
Hybrid mode: ORA Chat uses local Ollama, deep analysis uses cloud GPT-4o.
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from utils.require_auth import require_admin
from pydantic import BaseModel
from typing import Optional

from services.local_llm_service import (
    get_config, check_ollama_status, chat_local,
    save_config, load_config, set_db,
    _config,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/local-llm", tags=["Local LLM"])

db_ref = None


def set_db_ref(database):
    global db_ref
    db_ref = database
    set_db(database)


class ConfigUpdate(BaseModel):
    ollama_url: Optional[str] = None
    model: Optional[str] = None
    enabled: Optional[bool] = None
    timeout: Optional[int] = None


class ChatTest(BaseModel):
    message: str = "Hello, who are you?"


@router.get("/status")
async def local_llm_status():
    """Check Ollama connection status and available models."""
    status = await check_ollama_status()
    config = get_config()
    return {
        **status,
        "enabled": config["enabled"],
        "fallback": "Emergent LLM Key (GPT-4o via OpenRouter)" if not status["online"] else "Local Gemma 4",
        "cost": "$0.00/request" if status["online"] else "Uses Emergent Key credits",
    }


@router.get("/config")
async def get_llm_config():
    """Get current local LLM configuration."""
    config = get_config()
    return {
        "ollama_url": config["ollama_url"],
        "model": config["model"],
        "enabled": config["enabled"],
        "timeout": config["timeout"],
        "last_status": config["last_status"],
        "last_check": config["last_check"],
    }


@router.post("/config")
async def update_llm_config(update: ConfigUpdate, _admin: dict = Depends(require_admin)):
    """Update local LLM configuration.

    Bug-fix 129 — was unauthenticated; attacker could POST a new
    ollama_url pointing to their own server and proxy all subsequent
    LLM calls through it (read every prompt + return any response).
    Admin-only now.
    """
    if update.ollama_url is not None:
        _config["ollama_url"] = update.ollama_url.rstrip("/")
    if update.model is not None:
        _config["model"] = update.model
    if update.enabled is not None:
        _config["enabled"] = update.enabled
    if update.timeout is not None:
        _config["timeout"] = max(10, min(300, update.timeout))

    await save_config()
    logger.info(f"[LocalLLM] Config updated: url={_config['ollama_url']}, model={_config['model']}, enabled={_config['enabled']}")

    return {"success": True, "config": get_config()}


@router.post("/test")
async def test_local_llm(req: ChatTest):
    """Test the local LLM connection with a sample message."""
    status = await check_ollama_status()

    if not status["online"]:
        return {
            "success": False,
            "online": False,
            "error": f"Ollama not reachable at {_config['ollama_url']}. Install: curl -fsSL https://ollama.ai/install.sh | sh && ollama pull gemma4:4b",
            "fallback_active": True,
        }

    if not status["model_available"]:
        return {
            "success": False,
            "online": True,
            "error": f"Model '{_config['model']}' not found. Available: {', '.join(status['models'])}. Run: ollama pull {_config['model']}",
            "available_models": status["models"],
        }

    response = await chat_local(
        message=req.message,
        system_prompt="You are AUREM ORA, a business AI assistant. Respond in 1-2 sentences.",
    )

    if response:
        return {
            "success": True,
            "online": True,
            "model": _config["model"],
            "response": response,
            "cost": "$0.00",
        }

    return {
        "success": False,
        "online": True,
        "error": "Model loaded but failed to generate response. Check Ollama logs.",
    }


@router.post("/breaker/reset")
async def reset_circuit_breaker(_admin: dict = Depends(require_admin)):
    """iter 323y — manually reset the Sovereign circuit breaker.

    When the Legion tunnel goes down, the breaker opens for 300s and
    skips ALL Sovereign probes. If the founder fixes the tunnel before
    the 300s timer elapses, this endpoint clears the latched state so
    the very next LLM call retries Sovereign.

    Returns prior state for audit. Idempotent.
    """
    prior = {
        "consecutive_failures": _config.get("consecutive_failures"),
        "backoff_until": _config.get("backoff_until"),
        "last_status": _config.get("last_status"),
    }
    _config["consecutive_failures"] = 0
    _config["backoff_until"] = None
    _config["last_status"] = None
    logger.info("[LocalLLM] Circuit breaker manually reset by admin")
    # Immediately probe to update last_status
    try:
        status = await check_ollama_status()
    except Exception as e:
        status = {"online": False, "error": str(e)}
    return {
        "ok": True,
        "prior": prior,
        "now": {
            "consecutive_failures": _config.get("consecutive_failures"),
            "backoff_until": _config.get("backoff_until"),
            "last_status": _config.get("last_status"),
            "online": status.get("online"),
        },
        "probe": status,
    }


@router.get("/usage")
async def local_llm_usage():
    """Get local LLM usage stats."""
    if db_ref is None:
        return {"total_requests": 0, "total_input_chars": 0, "total_output_chars": 0}

    pipeline = [
        {"$group": {
            "_id": None,
            "total_requests": {"$sum": 1},
            "total_input_chars": {"$sum": "$input_chars"},
            "total_output_chars": {"$sum": "$output_chars"},
        }}
    ]

    result = await db_ref.local_llm_usage.aggregate(pipeline).to_list(1)
    if result:
        return {
            "total_requests": result[0]["total_requests"],
            "total_input_chars": result[0]["total_input_chars"],
            "total_output_chars": result[0]["total_output_chars"],
            "cost_saved": f"${result[0]['total_requests'] * 0.002:.2f}",
        }

    return {"total_requests": 0, "total_input_chars": 0, "total_output_chars": 0, "cost_saved": "$0.00"}
