"""
Developer-portal CTO chat service — iter 332b D-10
================================================

Powers the chat box on /developers/dashboard. Strategy per founder
directive (no Emergent LLM key for free-tier devs):

  FREE TIER (no BYOK):
    Primary  : DeepSeek V3   (deepseek-chat, $0.27/1M tokens)
    Fallback : Groq Llama 3.3 70B (free)

  BYOK USERS:
    Use whichever provider key they configured. We pick the first
    available in this order so users with multiple keys get the
    smartest model first:
      anthropic > openai > deepseek > gemini > groq > mistral > custom

Every call deducts 1 token via deduct_tokens(...). If the developer's
balance is below 1 token we refuse with action_required="add_byok".
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# OpenAI-compatible endpoints + default models
PROVIDER_ROUTES = {
    "deepseek":  {"url": "https://api.deepseek.com/chat/completions",
                  "model": "deepseek-chat"},
    "groq":      {"url": "https://api.groq.com/openai/v1/chat/completions",
                  "model": "llama-3.3-70b-versatile"},
    "openai":    {"url": "https://api.openai.com/v1/chat/completions",
                  "model": "gpt-4o-mini"},
    "mistral":   {"url": "https://api.mistral.ai/v1/chat/completions",
                  "model": "mistral-small-latest"},
}

# Native (non-OpenAI-compatible) providers handled separately
NATIVE_PROVIDERS = {"anthropic", "gemini"}

# Preferred order when a BYOK user has multiple keys
BYOK_PREFERENCE = (
    "anthropic", "openai", "deepseek", "gemini",
    "groq", "mistral", "custom",
)

SYSTEM_PROMPT = (
    "You are AUREM CTO, a senior staff engineer who helps developers ship "
    "production-grade code. Be direct, practical, and concise. Plain English. "
    "Skip pleasantries. When the developer asks for code, return runnable, "
    "well-commented snippets that follow best practices. Never refuse a "
    "legitimate engineering question."
)


def _free_tier_provider() -> tuple[str, str] | None:
    """Returns (provider_name, api_key) for free-tier requests, or None
    if neither DeepSeek nor Groq is configured on the platform."""
    if k := os.environ.get("DEEPSEEK_API_KEY", "").strip():
        return ("deepseek", k)
    if k := os.environ.get("GROQ_API_KEY", "").strip():
        return ("groq", k)
    return None


def _pick_byok_provider(byok: dict[str, str]) -> tuple[str, str] | None:
    for name in BYOK_PREFERENCE:
        v = (byok or {}).get(name)
        if v and isinstance(v, str) and v.strip():
            return (name, v.strip())
    return None


async def _call_openai_compatible(
    url: str, api_key: str, model: str,
    messages: list[dict[str, str]],
) -> str:
    payload = {"model": model, "messages": messages,
               "max_tokens": 1024, "temperature": 0.4}
    async with httpx.AsyncClient(timeout=45.0) as c:
        r = await c.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}",
                      "Content-Type": "application/json"},
        )
    if r.status_code >= 400:
        raise RuntimeError(f"provider HTTP {r.status_code}: {r.text[:200]}")
    j = r.json()
    return (j.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()


async def _call_anthropic(api_key: str, messages: list[dict[str, str]]) -> str:
    url = "https://api.anthropic.com/v1/messages"
    body = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [m for m in messages if m["role"] != "system"],
    }
    async with httpx.AsyncClient(timeout=45.0) as c:
        r = await c.post(url, json=body, headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        })
    if r.status_code >= 400:
        raise RuntimeError(f"anthropic HTTP {r.status_code}: {r.text[:200]}")
    j = r.json()
    blocks = j.get("content") or []
    return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()


async def _call_gemini(api_key: str, messages: list[dict[str, str]]) -> str:
    user_text = "\n\n".join(m["content"] for m in messages if m["role"] != "system")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={api_key}"
    )
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.4},
    }
    async with httpx.AsyncClient(timeout=45.0) as c:
        r = await c.post(url, json=body, headers={"Content-Type": "application/json"})
    if r.status_code >= 400:
        raise RuntimeError(f"gemini HTTP {r.status_code}: {r.text[:200]}")
    j = r.json()
    cand = (j.get("candidates") or [{}])[0]
    parts = (cand.get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()


async def _dispatch(provider: str, api_key: str,
                     messages: list[dict[str, str]]) -> str:
    if provider == "anthropic":
        return await _call_anthropic(api_key, messages)
    if provider == "gemini":
        return await _call_gemini(api_key, messages)
    if provider not in PROVIDER_ROUTES:
        raise RuntimeError(f"unknown provider {provider!r}")
    route = PROVIDER_ROUTES[provider]
    return await _call_openai_compatible(
        route["url"], api_key, route["model"], messages,
    )


async def cto_chat(
    *,
    account: dict[str, Any],
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """Returns {ok, reply, tokens_remaining, model_used, provider, tier}."""
    # Decrypt BYOK keys if present
    byok_envelope = account.get("byok_keys")
    byok_plain: dict[str, str] = {}
    if byok_envelope and isinstance(byok_envelope, dict):
        try:
            from services.developer_portal_core import decrypt_byok
            byok_plain = decrypt_byok(byok_envelope) or {}
        except Exception as e:
            logger.warning(f"[cto_chat] BYOK decrypt failed: {e}")
            byok_plain = {}

    # Choose tier + provider
    picked = _pick_byok_provider(byok_plain)
    tier = "byok"
    if picked is None:
        picked = _free_tier_provider()
        tier = "free"

    if picked is None:
        return {
            "ok": False,
            "error": "no_llm_configured",
            "tier": "free",
            "message": (
                "Free-tier LLM is currently unavailable. "
                "Please add your own DeepSeek, OpenAI, or Anthropic key "
                "on the Connect page to keep building."
            ),
            "action_required": "add_byok",
        }
    provider, api_key = picked

    # Token-wall check (1 token per chat reply)
    from services.developer_portal_core import deduct_tokens
    deduct = await deduct_tokens(account["user_id"], "chat")
    if not deduct.get("ok", True) and not deduct.get("internal"):
        return {
            "ok": False,
            "error": "token_wall",
            "tier": tier,
            "tokens_remaining": deduct.get("tokens_remaining", 0),
            "action_required": "add_byok",
            "message": (
                "You're out of free tokens. Add your own API key on the "
                "Connect page — your BYOK key will be used for every "
                "future call and you won't hit this wall again."
            ),
        }

    # Make the LLM call. On free-tier DeepSeek failure, try Groq fallback.
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]
    try:
        reply = await _dispatch(provider, api_key, full_messages)
    except Exception as e:
        logger.warning(f"[cto_chat] {provider} call failed: {e}")
        if tier == "free" and provider == "deepseek":
            groq_key = os.environ.get("GROQ_API_KEY", "").strip()
            if groq_key:
                try:
                    reply = await _dispatch("groq", groq_key, full_messages)
                    provider = "groq"
                except Exception as e2:
                    return {
                        "ok": False, "error": "llm_failed",
                        "tier": tier,
                        "message": f"Both DeepSeek and Groq failed: {e2}",
                    }
            else:
                return {
                    "ok": False, "error": "llm_failed", "tier": tier,
                    "message": str(e),
                }
        else:
            return {
                "ok": False, "error": "llm_failed", "tier": tier,
                "message": str(e),
            }

    tokens_remaining = deduct.get("tokens_remaining")
    if tokens_remaining is None:
        # Refresh from DB if deduct was an internal/no-op
        try:
            from services.developer_portal_core import _get_db
            db = _get_db()
            row = await db.developer_accounts.find_one(
                {"user_id": account["user_id"]},
                {"_id": 0, "tokens_remaining": 1},
            )
            tokens_remaining = (row or {}).get("tokens_remaining", 0)
        except Exception:
            tokens_remaining = 0

    return {
        "ok": True,
        "reply": reply,
        "provider": provider,
        "tier": tier,
        "tokens_remaining": int(tokens_remaining or 0),
        "low_balance": int(tokens_remaining or 0) < 100,
    }
