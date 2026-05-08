"""
AUREM LLM Model Failover (Emergent-key primary)
================================================
Rotates through a priority chain of models via the Emergent Universal
Key (`EMERGENT_LLM_KEY`) using `emergentintegrations.llm.chat`. All
calls share a single universal key; credits deduct from the founder's
Emergent balance.

Chain (in order): gemini-2.5-flash (fast/cheap) → gemini-2.5-pro →
claude-sonnet-4-5 → gpt-5.1. Breaker wraps the whole provider layer —
a persistently failing key trips it, not individual 4xx responses.

Failures across every model → graceful degraded response (never
raises). Callers must survive an LLM outage.
"""
from __future__ import annotations

import os
import time
import logging
import uuid
from typing import Optional

import pybreaker

from services.breakers import openrouter_breaker  # reused as the "LLM" breaker

logger = logging.getLogger(__name__)

# (provider, model_id, tier). Tier is informational.
MODEL_CHAIN = [
    ("gemini",    "gemini-2.5-flash",            "cheap"),
    ("gemini",    "gemini-2.5-pro",              "mid"),
    ("anthropic", "claude-sonnet-4-5-20250929",  "mid"),
    ("openai",    "gpt-5.1",                     "premium"),
]


async def _call_with_breaker(breaker, coro_fn, *args, **kwargs):
    """Manual async adapter for pybreaker.

    Only infrastructure failures (5xx / timeouts / connection errors)
    trip the breaker. 4xx from the upstream API is treated as a
    per-model issue and simply fails over to the next one.
    """
    state = breaker.current_state
    if state == pybreaker.STATE_OPEN:
        raise pybreaker.CircuitBreakerError(
            f"Breaker '{breaker.name}' is OPEN — refusing call"
        )
    try:
        result = await coro_fn(*args, **kwargs)
    except Exception as exc:
        should_count = True
        # httpx 4xx → not infra failure
        try:
            import httpx as _httpx
            if isinstance(exc, _httpx.HTTPStatusError):
                code = exc.response.status_code
                if 400 <= code < 500:
                    should_count = False
        except Exception:
            pass

        if should_count and not any(
            isinstance(exc, cls) for cls in (breaker.excluded_exceptions or [])
        ):
            try:
                breaker._state_storage.increment_counter()
                if (breaker._state_storage.counter >= breaker.fail_max
                        and state != pybreaker.STATE_OPEN):
                    breaker._state_storage.state = pybreaker.STATE_OPEN
                    breaker._state_storage.opened_at = time.time()
            except Exception:
                pass
        raise

    # Success → reset counter / close if half-open
    try:
        breaker._state_storage.reset_counter()
        if state == pybreaker.STATE_HALF_OPEN:
            breaker._state_storage.state = pybreaker.STATE_CLOSED
    except Exception:
        pass
    return result


async def _emergent_llm_request(
    provider: str,
    model_id: str,
    prompt: str,
    system: str,
    max_tokens: int,
    timeout: float = 10.0,
) -> str:
    """One-shot LLM call via emergentintegrations."""
    api_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY not configured")

    # Lazy import — avoids adding load cost at module init.
    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore

    session_id = f"a2a-{uuid.uuid4().hex[:10]}"
    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=system or "You are a helpful assistant.",
    ).with_model(provider, model_id)

    msg = UserMessage(text=prompt)
    result = await chat.send_message(msg)
    # emergentintegrations returns a string of the assistant reply
    return result if isinstance(result, str) else str(result)


async def llm_call_with_failover(
    prompt: str,
    system: str = "",
    max_tokens: int = 1000,
    prefer_free: bool = True,
    timeout: float = 10.0,
) -> dict:
    """Try each model in MODEL_CHAIN; return on first success.

    Returns:
        {
          "content": str,
          "model_used": str,       # "<provider>/<model_id>"
          "is_free": bool,
          "failover_used": bool,
          "degraded": bool (only True if every model failed)
        }
    """
    primary = f"{MODEL_CHAIN[0][0]}/{MODEL_CHAIN[0][1]}"
    last_error: Optional[str] = None

    for provider, model_id, tier in MODEL_CHAIN:
        model_key = f"{provider}/{model_id}"
        try:
            content = await _call_with_breaker(
                openrouter_breaker,  # kept name for backward compat with Redis state
                _emergent_llm_request,
                provider, model_id, prompt, system, max_tokens, timeout,
            )
            return {
                "content": content or "",
                "model_used": model_key,
                "is_free": True,   # Emergent key — cost comes from the universal balance
                "failover_used": model_key != primary,
                "degraded": False,
            }
        except pybreaker.CircuitBreakerError:
            last_error = f"breaker_open:{model_key}"
            logger.warning(f"[llm-failover] breaker open — skipping {model_key}")
            continue
        except Exception as e:
            last_error = f"{type(e).__name__}:{str(e)[:120]}"
            logger.warning(f"[llm-failover] {model_key} failed: {last_error}")
            continue

    logger.error(f"[llm-failover] all models failed, last_error={last_error}")
    return {
        "content": "System temporarily in degraded mode. Request queued.",
        "model_used": "fallback_cache",
        "is_free": True,
        "failover_used": True,
        "degraded": True,
        "last_error": last_error,
    }


__all__ = ["llm_call_with_failover", "MODEL_CHAIN"]
