"""
Unified LLM gateway — iter 282al-5 (Legion Sovereign Node priority).

Provider priority chain:
  1. Sovereign Node  (Legion Ollama via Cloudflare Tunnel / ngrok)
  2. OpenRouter      (cloud, cheap, pay-per-token)
  3. Emergent Key    (last resort — budget may be exhausted)

One entry point: `call_llm(system_prompt, user_prompt, ...)` → str.
Never raises — on total failure returns a short disabled-message string
AND sets `failure_reason` on the result. Call sites that want to detect
total failure should check the return prefix.

The function also returns a structured tuple via `call_llm_with_meta()`
for callers that need to know which provider served the request
(composer + morning brief log this for cost tracking).
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Literal, Optional

logger = logging.getLogger(__name__)

Provider = Literal["sovereign", "openrouter", "emergent", "fallback"]

# Fixed fallback string — short + safe.
FAIL_MSG = "(LLM unavailable — all providers exhausted.)"


async def _try_sovereign(system_prompt: str, user_prompt: str,
                           max_tokens: int) -> Optional[str]:
    """Sovereign Node first. Uses existing chat_local() which already
    knows about retries / cold-start tunnel handling."""
    try:
        from services.local_llm_service import chat_local, is_available
        if not await is_available():
            return None
        resp = await asyncio.wait_for(
            chat_local(user_prompt, system_prompt=system_prompt or ""),
            timeout=45.0,
        )
        if resp and isinstance(resp, str) and resp.strip():
            logger.info(f"[llm_gateway] SERVED by sovereign ({len(resp)} chars, $0.00)")
            return resp.strip()[:max_tokens * 6]  # rough token-to-char cap
    except Exception as e:
        logger.debug(f"[llm_gateway] sovereign miss: {e}")
    return None


async def _try_openrouter(system_prompt: str, user_prompt: str,
                            max_tokens: int) -> Optional[str]:
    """OpenRouter via the existing client (has its own emergent failover,
    but we bypass that here — we call OpenRouter directly and let the
    gateway sequence the emergent retry step explicitly)."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import httpx
        payload = {
            "model":        "anthropic/claude-3.5-haiku",
            "messages": [
                {"role": "system", "content": system_prompt or ""},
                {"role": "user",   "content": user_prompt},
            ],
            "temperature": 0.4,
            "max_tokens":  max_tokens,
        }
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  "https://aurem.live",
                    "X-Title":       "AUREM",
                },
                json=payload,
            )
            if r.status_code != 200:
                logger.debug(f"[llm_gateway] openrouter {r.status_code}")
                return None
            data = r.json()
            msg = data.get("choices", [{}])[0].get("message", {})
            content = msg.get("content") or msg.get("reasoning") or ""
            if content:
                logger.info(f"[llm_gateway] SERVED by openrouter ({len(content)} chars)")
                return content.strip()
    except Exception as e:
        logger.debug(f"[llm_gateway] openrouter miss: {e}")
    return None


async def _try_emergent(system_prompt: str, user_prompt: str,
                          max_tokens: int) -> Optional[str]:
    """Last-resort: Emergent universal key. Budget may be exhausted."""
    api_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if not api_key:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = (LlmChat(api_key=api_key, session_id="gateway",
                         system_message=system_prompt or "")
                .with_model("anthropic", "claude-sonnet-4-5-20250929"))
        try:
            chat = chat.with_max_tokens(max_tokens)
        except Exception:
            pass
        resp = await asyncio.wait_for(
            chat.send_message(UserMessage(text=user_prompt)),
            timeout=30.0,
        )
        if isinstance(resp, str) and resp.strip():
            logger.info(f"[llm_gateway] SERVED by emergent ({len(resp)} chars)")
            return resp.strip()
    except Exception as e:
        # Common case: budget exceeded — log once at WARNING
        if "Budget" in str(e) or "exceeded" in str(e).lower():
            logger.warning("[llm_gateway] emergent key budget exhausted")
        else:
            logger.debug(f"[llm_gateway] emergent miss: {e}")
    return None


async def call_llm_with_meta(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 600,
    *,
    skip_sovereign: bool = False,
) -> dict:
    """Return {provider, content, ok} — never raises.

    iter 282al-13 — `skip_sovereign=True` skips the local node and goes
    straight to OpenRouter → Emergent. Useful for long-context dev-mode
    skill calls where the ngrok tunnel adds latency that bursts past
    chat-handler budgets."""
    providers = (
        ("sovereign",   _try_sovereign),
        ("openrouter",  _try_openrouter),
        ("emergent",    _try_emergent),
    )
    if skip_sovereign:
        providers = providers[1:]
    for provider, fn in providers:
        try:
            content = await fn(system_prompt, user_prompt, max_tokens)
        except Exception as e:
            logger.debug(f"[llm_gateway] {provider} raised: {e}")
            continue
        if content:
            return {"provider": provider, "content": content, "ok": True}
    return {"provider": "fallback", "content": FAIL_MSG, "ok": False}


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 600,
    *,
    skip_sovereign: bool = False,
) -> str:
    """String-only convenience wrapper."""
    r = await call_llm_with_meta(
        system_prompt, user_prompt, max_tokens,
        skip_sovereign=skip_sovereign,
    )
    return r["content"]


# ─────────────────────────────────────────────────────────────────────
# Health — for Pillars Map + admin chip
# ─────────────────────────────────────────────────────────────────────
async def sovereign_health() -> dict:
    """GREEN = reachable + tag list returned.
       YELLOW = URL set but not reachable right now.
       GREY = URL not configured."""
    url = (os.environ.get("OLLAMA_URL")
           or os.environ.get("SOVEREIGN_NODE_URL") or "").strip()
    if not url:
        return {"ok": True, "status": "grey",
                "detail": "SOVEREIGN_NODE_URL not configured",
                "url": None, "models": []}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{url}/api/tags")
            if r.status_code != 200:
                return {"ok": False, "status": "yellow",
                        "detail": f"tunnel returned {r.status_code}",
                        "url": url, "models": []}
            data = r.json() or {}
            models = [m.get("name") for m in (data.get("models") or [])
                       if m.get("name")]
            return {
                "ok":     True,
                "status": "green" if models else "yellow",
                "detail": (f"reachable — {len(models)} models"
                           if models else "reachable but no models loaded"),
                "url":    url,
                "models": models[:10],
            }
    except Exception as e:
        # iter 322 — Sovereign is fallback infra (LLM_PROVIDER_ORDER has
        # 3 backups), so an unreachable tunnel is a DEGRADED state, not
        # an outage. Surface as yellow so the admin tile shows the right
        # operational severity instead of a scary red dot.
        return {"ok": False, "status": "yellow",
                "detail": f"unreachable — {type(e).__name__}: {str(e)[:120]}",
                "url": url, "models": []}


LLM_PROVIDER_ORDER = ("sovereign", "openrouter", "emergent", "fallback")

__all__ = [
    "call_llm",
    "call_llm_with_meta",
    "sovereign_health",
    "LLM_PROVIDER_ORDER",
    "FAIL_MSG",
]
