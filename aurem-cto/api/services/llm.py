"""
Direct LLM gateway for aurem-cto — NO emergentintegrations dep.
Groq primary (with retry-on-429), OpenRouter + Emergent fallback.
"""
import asyncio
import os
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
EMERGENT_LLM_KEY = os.getenv("EMERGENT_LLM_KEY")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Emergent universal key is served via the emergentintegrations Python SDK,
# not a public HTTP endpoint. We attempt to use the SDK if installed.


async def call_groq(system: str, user: str, max_tokens: int = 1200,
                     max_retries: int = 2) -> Optional[str]:
    """Call Groq llama-3.3-70b-versatile with retry-on-429.

    iter 322ex — back-to-back tool-loop iterations would hit Groq's
    free-tier RPM cap. Adds exponential backoff (1s, 3s) on 429 only,
    returns None on other errors so callers fall through to next provider.
    """
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set")
        return None

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    backoffs = [1.0, 3.0]
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(GROQ_URL, json=payload, headers=headers)
                if resp.status_code == 429 and attempt < max_retries:
                    wait_s = backoffs[attempt] if attempt < len(backoffs) else 5.0
                    logger.warning(
                        f"Groq 429 (attempt {attempt+1}/{max_retries+1}) — "
                        f"sleeping {wait_s}s and retrying"
                    )
                    await asyncio.sleep(wait_s)
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt >= max_retries:
                logger.error(f"Groq call failed after {attempt+1} attempts: {e}")
                return None
            logger.warning(f"Groq attempt {attempt+1} raised {e!r}, retrying")
            await asyncio.sleep(1.0)
    return None


async def call_openrouter(system: str, user: str, max_tokens: int = 1200) -> Optional[str]:
    """Call OpenRouter claude-3.5-haiku. Returns content or None on failure."""
    if not OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY not set")
        return None
    
    payload = {
        "model": "anthropic/claude-3.5-haiku",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://aurem.live",
        "X-Title": "AUREM CTO"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(OPENROUTER_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"OpenRouter call failed: {e}")
        return None


async def call_emergent(system: str, user: str, max_tokens: int = 1200) -> Optional[str]:
    """Call Emergent universal key via emergentintegrations SDK.

    iter 322ex — Emergent doesn't expose a public OpenAI-compatible HTTP
    endpoint; the universal key works only through the SDK. We lazy-import
    so missing-package on Legion just falls through to None (not crash).
    """
    if not EMERGENT_LLM_KEY:
        logger.warning("EMERGENT_LLM_KEY not set")
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
    except ImportError:
        logger.warning("emergentintegrations not installed — skip Emergent fallback")
        return None
    try:
        import uuid as _uuid
        sid = f"cto-{_uuid.uuid4().hex[:12]}"
        chat = (
            LlmChat(api_key=EMERGENT_LLM_KEY, session_id=sid, system_message=system)
            .with_model("anthropic", "claude-sonnet-4-5-20250929")
        )
        try:
            chat = chat.with_max_tokens(max_tokens)
        except Exception:
            pass
        resp = await asyncio.wait_for(
            chat.send_message(UserMessage(text=user)),
            timeout=30.0,
        )
        if isinstance(resp, str) and resp.strip():
            return resp.strip()
        return None
    except Exception as e:
        logger.error(f"Emergent call failed: {e}")
        return None


async def call_llm_with_meta(system: str, user: str, max_tokens: int = 1200) -> dict:
    """
    Try groq → openrouter → emergent in order.
    Returns {ok, provider, content, fallback_chain}.
    """
    fallback_chain = []
    
    # Try Groq
    fallback_chain.append("groq")
    content = await call_groq(system, user, max_tokens)
    if content:
        return {
            "ok": True,
            "provider": "groq",
            "content": content,
            "fallback_chain": fallback_chain
        }
    
    # Try OpenRouter
    fallback_chain.append("openrouter")
    content = await call_openrouter(system, user, max_tokens)
    if content:
        return {
            "ok": True,
            "provider": "openrouter",
            "content": content,
            "fallback_chain": fallback_chain
        }
    
    # Try Emergent
    fallback_chain.append("emergent")
    content = await call_emergent(system, user, max_tokens)
    if content:
        return {
            "ok": True,
            "provider": "emergent",
            "content": content,
            "fallback_chain": fallback_chain
        }
    
    # All failed
    return {
        "ok": False,
        "provider": None,
        "content": None,
        "fallback_chain": fallback_chain
    }