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


# iter 322g+ prod-guard — in production deployment (aurem.live), the
# sovereign tunnel (sovereign.aurem.live → founder's laptop) is unreachable
# from the pod's network, so every call returns 5xx. Without this gate the
# circuit breaker hammers 80+ retries during startup, floods logs, and
# starves the asyncio loop → K8s health-probe times out → deployment fails.
# Auto-disable Sovereign entirely when running in production.
def _is_prod() -> bool:
    try:
        from services.prod_guard import is_production_pod
        return is_production_pod()
    except Exception:
        # Fallback signal detection if prod_guard import fails for any reason
        if os.environ.get("AUREM_ENV", "").strip().lower() == "production":
            return True
        app_url = (os.environ.get("APP_URL", "") or "").lower()
        if "aurem.live" in app_url or "aurem.live" in app_url:
            return True
        return False


_PROD_DETECTED = _is_prod()

_config = {
    "ollama_url": SOVEREIGN_URL,
    "model": SOVEREIGN_MODEL,
    # iter 323x — production now ATTEMPTS Sovereign on every call (subject
    # to circuit breaker). Founder enabled the Legion tunnel
    # sovereign.aurem.live → 127.0.0.1:11434; when it's up, prod serves
    # free locally. When it's down, the breaker (BACKOFF_AFTER_FAILURES=2,
    # ~6s detection) opens immediately and OpenRouter/Emergent take over.
    # The prod-hard-disable from iter 322g+ is removed.
    "enabled": (os.environ.get("LOCAL_LLM_ENABLED", "true").lower() == "true"),
    # iter 322ai — timeout split:
    #   "connect_timeout": fast (5s) — TCP+TLS handshake to ngrok edge.
    #       If this exceeds 5s the tunnel is effectively dead — fail fast
    #       so we don't starve the asyncio loop.
    #   "timeout" (read): generous (30s) — actual chat completion needs
    #       3-15s on Legion's CPU/GPU when the model is cold. The old 5s
    #       hard cap guaranteed every chat call timed out at ~5072ms.
    "timeout": int(os.environ.get("LOCAL_LLM_TIMEOUT_S", "30")),
    "connect_timeout": int(os.environ.get("LOCAL_LLM_CONNECT_TIMEOUT_S", "3")),
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
# iter 322ai — re-balanced: connect-timeout stays tight (5s, fails fast on
# dead tunnel), but read-timeout bumped to 30s for slow Ollama generation,
# and retries restored to 3 (with 5s gap) per user spec. Net worst-case
# blocking time when tunnel is reachable but model is loading: ~45s.
# When tunnel is dead: ~5s connect-fail × 3 = 15s before circuit opens.
# iter 322bs — Production-safe defaults. With BACKOFF_AFTER_FAILURES=2
# (was 3) and connect-timeout 3s, a dead tunnel trips the breaker in <8s
# total worst case (2 connect attempts × 3s + 5s retry sleep), well below
# K8s probe interval (10s). Once the breaker opens, ALL subsequent calls
# return None instantly (no event loop blocking) for 300s.
MAX_RETRIES = int(os.environ.get("LOCAL_LLM_RETRIES", "2"))
RETRY_DELAY_S = float(os.environ.get("LOCAL_LLM_RETRY_DELAY_S", "3.0"))
BACKOFF_AFTER_FAILURES = int(os.environ.get("LOCAL_LLM_BACKOFF_AFTER", "2"))
BACKOFF_DURATION_S = int(os.environ.get("LOCAL_LLM_BACKOFF_DURATION", "300"))


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
    """Internal hot-path circuit-breaker check.

    iter 322p — also returns True when the service is fully disabled, so
    callers using `is_backed_off()` as a fast pre-check skip Sovereign
    entirely without paying the connect-timeout cost.

    iter 323x — prod-hard-disable removed. The breaker now governs prod
    just like preview: when the tunnel is reachable, Sovereign serves;
    when it's not, the breaker opens within ~6s and stays open 300s.
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
    """HTTP request with retry for Cloudflare Tunnel cold starts.

    iter 322ai — split timeout: connect timeout stays tight (default 5s)
    so a dead tunnel fails fast and doesn't starve the asyncio loop, but
    read timeout is generous (default 30s) so a live tunnel + cold Ollama
    model loading from disk (3-15s) doesn't get killed mid-generation.
    """
    # iter 322bs — Hard gate. If we've already accumulated failures past
    # threshold, refuse new calls immediately (no HTTP, no retries) so the
    # event loop never stalls. Backoff state is rechecked only after
    # BACKOFF_DURATION_S has passed.
    if _is_backed_off():
        return None
    if _config["consecutive_failures"] >= BACKOFF_AFTER_FAILURES:
        # We were past threshold but backoff_until expired — open a fresh
        # window and bail. The single test-probe below will set things
        # right once Sovereign comes back.
        from datetime import timedelta as _td
        _config["backoff_until"] = (
            datetime.now(timezone.utc) + _td(seconds=BACKOFF_DURATION_S)
        ).isoformat()
        return None

    read_timeout = kwargs.pop("timeout", _config["timeout"])
    connect_timeout = kwargs.pop("connect_timeout", _config["connect_timeout"])
    httpx_timeout = httpx.Timeout(read_timeout, connect=connect_timeout)
    last_err = None

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=httpx_timeout) as client:
                if method == "GET":
                    resp = await client.get(url, **kwargs)
                else:
                    resp = await client.post(url, **kwargs)

                if resp.status_code == 200:
                    _config["consecutive_failures"] = 0
                    _config["backoff_until"] = None
                    return resp

                if resp.status_code == 502 and attempt < retries - 1:
                    logger.info(f"[Sovereign] 502 on attempt {attempt+1}, retrying in {RETRY_DELAY_S}s (tunnel cold start)")
                    await asyncio.sleep(RETRY_DELAY_S)
                    continue

                # iter 323x — non-200 (404/5xx) means tunnel hostname is
                # not claimed (Cloudflare "Site not found"), Ollama is
                # rejecting the path, or the upstream is mis-routed.
                # Count as a failure so the circuit breaker opens just
                # like a connect-error. Returning resp here would have
                # masked the failure from the breaker.
                last_err = f"HTTP {resp.status_code}"
                logger.info(f"[Sovereign] non-200 {resp.status_code} attempt {attempt+1}/{retries}")
                break

        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            # iter 322ai — connect failures mean the tunnel itself is unreachable
            # (laptop offline / ngrok down). Don't waste retry budget — bail
            # immediately so circuit breaker opens fast.
            last_err = e
            logger.info(f"[Sovereign] Connect error attempt {attempt+1}/{retries}: {e}")
            break
        except httpx.ReadTimeout as e:
            # Read-timeouts mean Ollama is up but slow (model still loading).
            # Worth retrying — next attempt may catch model already warm.
            last_err = e
            if attempt < retries - 1:
                logger.info(f"[Sovereign] Read timeout attempt {attempt+1}/{retries}, retrying in {RETRY_DELAY_S}s")
                await asyncio.sleep(RETRY_DELAY_S)
                continue
            break
        except Exception as e:
            last_err = e
            break

    # Track consecutive failures for backoff
    _config["consecutive_failures"] += 1
    if _config["consecutive_failures"] == BACKOFF_AFTER_FAILURES:
        # Open the circuit breaker — log ONCE.
        from datetime import timedelta
        _config["backoff_until"] = (datetime.now(timezone.utc) + timedelta(seconds=BACKOFF_DURATION_S)).isoformat()
        logger.warning(f"[Sovereign] {_config['consecutive_failures']} consecutive failures — backing off for {BACKOFF_DURATION_S}s")

    if last_err:
        logger.info(f"[Sovereign] All {retries} attempts failed: {last_err}")
    return None


async def check_ollama_status() -> dict:
    """Check if Sovereign Node is running and which models are available."""
    url = _config["ollama_url"]
    resp = await _request_with_retry(
        "GET", f"{url}/api/tags",
        retries=2, timeout=5.0,
        headers={"ngrok-skip-browser-warning": "1"},
    )

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
        headers={"ngrok-skip-browser-warning": "1"},
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

    iter 323x — prod-hard-skip removed. Production now probes Sovereign
    just like preview. The 2s timeout + circuit breaker keep the cost
    bounded when the tunnel is dead.
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
            # iter 323x — 404 / 5xx still counts as a miss for the breaker.
            # Cloudflare returns 404 "Site not found" when no tunnel has
            # claimed the hostname; treat that as Sovereign unavailable
            # exactly like a connect-error.
            logger.debug(f"[Sovereign] probe non-200: HTTP {resp.status_code}")
    except Exception as e:
        logger.debug(f"[Sovereign] probe failed: {type(e).__name__}")

    # Miss — bump failure counter for circuit breaker
    _config["consecutive_failures"] += 1
    if _config["consecutive_failures"] >= BACKOFF_AFTER_FAILURES:
        from datetime import timedelta
        _config["backoff_until"] = (datetime.now(timezone.utc) + timedelta(seconds=BACKOFF_DURATION_S)).isoformat()
        logger.info(f"[Sovereign] Circuit breaker opened after {_config['consecutive_failures']} fails — skipping for {BACKOFF_DURATION_S}s")
    return False
