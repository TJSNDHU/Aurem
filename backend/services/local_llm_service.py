"""
AUREM Sovereign Node — Local LLM via Cloudflare Tunnel
=======================================================
Connects to Ollama on Legion laptop via Cloudflare Tunnel at sovereign.aurem.live.
Auto-retry for tunnel cold starts (Windows sleep/wake).
Falls back to cloud (Emergent LLM Key) when Sovereign is unavailable.
"""
import os
import httpx
import logging
import asyncio
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

db = None

SOVEREIGN_URL = os.environ.get("OLLAMA_URL", os.environ.get("SOVEREIGN_NODE_URL", "https://sovereign.aurem.live"))
SOVEREIGN_MODEL = os.environ.get("LOCAL_LLM_MODEL", os.environ.get("SOVEREIGN_MODEL", "llama3.1"))

_config = {
    "ollama_url": SOVEREIGN_URL,
    "model": SOVEREIGN_MODEL,
    "enabled": os.environ.get("LOCAL_LLM_ENABLED", "true").lower() == "true",
    "timeout": int(os.environ.get("LOCAL_LLM_TIMEOUT_S", "5")),  # iter 322p — was 60, now 5s default
    "last_status": None,
    "last_check": None,
    "consecutive_failures": 0,
    "backoff_until": None,
}

# Retry config for Cloudflare Tunnel cold starts
# iter 322p — production hardening: when the Sovereign tunnel is fully down
# (Legion laptop offline), the previous defaults (60s timeout × 3 retries
# × 2s sleep) kept the asyncio loop blocked for ~180s per call → APScheduler
# missed jobs by 5-9s → /health probe queued → K8s killed pod. New defaults
# fail FAST so the event loop never gets starved.
MAX_RETRIES = 1                  # was 3 — extra retries serve no purpose if tunnel is dead
RETRY_DELAY_S = 0.5              # was 2.0 — minimal back-off
BACKOFF_AFTER_FAILURES = 1       # open the breaker after the very first miss
BACKOFF_DURATION_S = 300         # 5-minute cool-down (was 120s) — fewer probe storms


def is_backed_off() -> bool:
    """Public helper — returns True if Sovereign circuit breaker is currently open.

    Callers should check this BEFORE awaiting any Sovereign call, to avoid
    the 2-3s probe cost when the node is already known to be down.
    """
    return _is_backed_off()


def set_db(database):
    global db
    db = database


async def load_config():
    global _config
    if db is None:
        return
    saved = await db.local_llm_config.find_one({"_id": "default"})
    if saved:
        _config["ollama_url"] = saved.get("ollama_url", _config["ollama_url"])
        _config["model"] = saved.get("model", _config["model"])
        _config["enabled"] = saved.get("enabled", _config["enabled"])
        _config["timeout"] = saved.get("timeout", _config["timeout"])
    # Always clear backoff on startup — fresh start
    _config["consecutive_failures"] = 0
    _config["backoff_until"] = None


async def save_config():
    if db is None:
        return
    await db.local_llm_config.update_one(
        {"_id": "default"},
        {"$set": {
            "ollama_url": _config["ollama_url"],
            "model": _config["model"],
            "enabled": _config["enabled"],
            "timeout": _config["timeout"],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )


def get_config():
    return {k: v for k, v in _config.items()}


def _is_backed_off() -> bool:
    """Check if we're in backoff period after too many failures.

    iter 322p — also returns True when the service is fully disabled, so
    callers using `is_backed_off()` as a fast pre-check skip Sovereign
    entirely without paying the connect-timeout cost.
    """
    if not _config.get("enabled", True):
        return True
    if _config["backoff_until"] is None:
        return False
    now = datetime.now(timezone.utc)
    if isinstance(_config["backoff_until"], str):
        from datetime import datetime as dt
        try:
            backoff_time = dt.fromisoformat(_config["backoff_until"])
            return now < backoff_time
        except Exception:
            return False
    return now < _config["backoff_until"]


async def _request_with_retry(method: str, url: str, retries: int = MAX_RETRIES, **kwargs) -> Optional[httpx.Response]:
    """HTTP request with retry for Cloudflare Tunnel cold starts."""
    if _is_backed_off():
        return None

    kwargs.setdefault("timeout", 10.0)
    last_err = None

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=kwargs.pop("timeout", 10.0)) as client:
                if method == "GET":
                    resp = await client.get(url, **kwargs)
                else:
                    resp = await client.post(url, **kwargs)

                if resp.status_code == 200:
                    _config["consecutive_failures"] = 0
                    _config["backoff_until"] = None
                    return resp

                if resp.status_code == 502 and attempt < retries - 1:
                    logger.debug(f"[Sovereign] 502 on attempt {attempt+1}, retrying in {RETRY_DELAY_S}s (tunnel cold start)")
                    await asyncio.sleep(RETRY_DELAY_S)
                    continue

                return resp

        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            last_err = e
            if attempt < retries - 1:
                logger.debug(f"[Sovereign] Connect error attempt {attempt+1}/{retries}: {e}")
                await asyncio.sleep(RETRY_DELAY_S)
            continue
        except httpx.ReadTimeout as e:
            last_err = e
            break
        except Exception as e:
            last_err = e
            break

    # Track consecutive failures for backoff
    _config["consecutive_failures"] += 1
    if _config["consecutive_failures"] >= BACKOFF_AFTER_FAILURES:
        from datetime import timedelta
        _config["backoff_until"] = (datetime.now(timezone.utc) + timedelta(seconds=BACKOFF_DURATION_S)).isoformat()
        logger.warning(f"[Sovereign] {_config['consecutive_failures']} consecutive failures — backing off for {BACKOFF_DURATION_S}s")

    if last_err:
        logger.debug(f"[Sovereign] All {retries} attempts failed: {last_err}")
    return None


async def check_ollama_status() -> dict:
    """Check if Sovereign Node is running and which models are available."""
    url = _config["ollama_url"]
    resp = await _request_with_retry("GET", f"{url}/api/tags", retries=2, timeout=5.0)

    if resp and resp.status_code == 200:
        data = resp.json()
        models = [m["name"] for m in data.get("models", [])]
        model_available = (
            _config["model"] in models
            or f"{_config['model']}:latest" in models
            or any(m.startswith(_config["model"]) for m in models)
        )
        _config["last_status"] = "online"
        _config["last_check"] = datetime.now(timezone.utc).isoformat()
        return {
            "online": True,
            "url": url,
            "models": models,
            "model_count": len(models),
            "has_gemma4": any("gemma" in m.lower() for m in models),
            "configured_model": _config["model"],
            "model_available": model_available,
            "tunnel": "cloudflare" if "sovereign.aurem.live" in url else "direct",
        }

    _config["last_status"] = "offline"
    _config["last_check"] = datetime.now(timezone.utc).isoformat()
    return {
        "online": False,
        "url": url,
        "models": [],
        "model_count": 0,
        "has_gemma4": False,
        "configured_model": _config["model"],
        "model_available": False,
        "tunnel": "cloudflare" if "sovereign.aurem.live" in url else "direct",
        "backed_off": _is_backed_off(),
        "consecutive_failures": _config["consecutive_failures"],
    }


async def chat_local(
    message: str,
    system_prompt: str = "",
    history: Optional[list] = None,
) -> Optional[str]:
    """
    Send a chat message to the Sovereign Node (Ollama via Cloudflare Tunnel).
    Returns the response text, or None if unavailable.
    Auto-retries on tunnel cold starts (502/connect errors).
    """
    if not _config["enabled"]:
        return None

    url = _config["ollama_url"]
    model = _config["model"]

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": message})

    resp = await _request_with_retry(
        "POST",
        f"{url}/v1/chat/completions",
        retries=MAX_RETRIES,
        timeout=float(_config["timeout"]),
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024,
            "stream": False,
        },
    )

    if resp and resp.status_code == 200:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        logger.info(f"[Sovereign] Response from {model} ({len(content)} chars, $0.00)")

        if db is not None:
            await db.local_llm_usage.insert_one({
                "model": model,
                "input_chars": len(message),
                "output_chars": len(content),
                "tunnel": "cloudflare" if "sovereign.aurem.live" in url else "direct",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return content

    return None


async def is_available() -> bool:
    """Quick gate-check: is Sovereign Node reachable right now?

    This is a FAST probe used to decide between local vs cloud routing —
    never retries, never waits longer than 2s total. Callers that need
    cold-start tolerance should use chat_local() directly (which retries).
    If the circuit breaker is open we short-circuit to False immediately.
    """
    if _is_backed_off():
        return False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{_config['ollama_url']}/api/tags")
            if resp.status_code == 200:
                _config["consecutive_failures"] = 0
                _config["backoff_until"] = None
                return True
    except Exception as e:
        logger.debug(f"[Sovereign] probe failed: {type(e).__name__}")

    # Miss — bump failure counter for circuit breaker
    _config["consecutive_failures"] += 1
    if _config["consecutive_failures"] >= BACKOFF_AFTER_FAILURES:
        from datetime import timedelta
        _config["backoff_until"] = (datetime.now(timezone.utc) + timedelta(seconds=BACKOFF_DURATION_S)).isoformat()
        logger.warning(f"[Sovereign] Circuit breaker opened after {_config['consecutive_failures']} fails — skipping for {BACKOFF_DURATION_S}s")
    return False
