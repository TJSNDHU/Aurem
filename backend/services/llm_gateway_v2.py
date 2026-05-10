"""
AUREM LLM Gateway — Phase 0 (Sovereign Routing)
================================================
Single entrypoint for every LLM call in the platform.

Routes by **task_type** to the cheapest model that can do the job:
  • Groq (free, sub-300ms) — preferred for chat/triage/review/service-copy
  • Free OpenRouter models — fallback when Groq is rate-limited or key absent
  • Claude Sonnet (via Emergent) — paid last-resort for complex reasoning

Every call is **persisted** in `db.llm_costs` (no try/except swallow).
Each task_type may declare a **fallback chain** (list of (provider, model)
tuples). The chain is walked top-to-bottom until one succeeds.

Public:
  await llm_gateway.route(task_type, prompt, system=None, max_tokens=1500)
"""
from __future__ import annotations

import os
import time
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# ─── Routing table — task_type → CHAIN of (provider, model) ─────────
# A "chain" is just a list of attempts. The first that returns a
# non-empty text wins. A single tuple value is also accepted for
# backwards compatibility and treated as a one-entry chain.
#
# Convention:
#   - Groq llama-3.1-8b  → fast triage / short JSON / quick classifications
#   - Groq llama-3.3-70b → chat / review writing / service copy / Q&A
#   - OpenRouter free    → fallback when Groq missing/429ed
#   - Emergent Claude    → last resort for reasoning-heavy tasks only
Chain = Union[Tuple[str, str], List[Tuple[str, str]]]

ROUTING_TABLE: Dict[str, Chain] = {
    # ─── FAST CHAT / TRIAGE ─────────────────────────────────────────
    # iter 322ag — Groq-first for sub-300ms latency. OpenRouter
    # gpt-oss-20b kept as fallback (existing field-tested behaviour).
    "triage_classify": [
        ("groq",       "llama-3.1-8b-instant"),
        ("openrouter", "openai/gpt-oss-20b:free"),
        ("openrouter", "google/gemma-4-26b-it:free"),
    ],
    "triage": [
        ("groq",       "llama-3.1-8b-instant"),
        ("openrouter", "openai/gpt-oss-20b:free"),
    ],
    "ora_chat": [
        ("groq",       "llama-3.3-70b-versatile"),
        ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
        ("openrouter", "openai/gpt-oss-20b:free"),
    ],

    # ─── CONTENT GENERATION ─────────────────────────────────────────
    # iter 322ag — Groq llama-3.3-70b is the fastest decent-quality
    # path for review/service copy (used by website_enrich since 322ad).
    "content_qa": [
        ("groq",       "llama-3.3-70b-versatile"),
        ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
        ("openrouter", "openai/gpt-oss-20b:free"),
        ("openrouter", "google/gemma-4-26b-it:free"),
    ],
    "review_generate": [
        ("groq",       "llama-3.3-70b-versatile"),
        ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
        ("openrouter", "openai/gpt-oss-20b:free"),
    ],
    "service_describe": [
        ("groq",       "llama-3.1-8b-instant"),
        ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
        ("openrouter", "openai/gpt-oss-20b:free"),
    ],

    # ─── EXISTING ROUTES (kept on OpenRouter free tier) ────────────
    "scout_filter":    ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
    "lead_qualify":    ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
    "blast_compose":   ("openrouter", "zai-org/glm-5.1"),
    "council_vote":    ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
    "sentiment":       ("openrouter", "google/gemma-4-26b-it:free"),
    "heartbeat_check": ("openrouter", "minimax/minimax-m2.5:free"),
    "pattern_match":   ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),

    # ─── PAID — Claude Sonnet via Emergent (complex reasoning only) ─
    "repair_diagnose": ("anthropic",  "claude-sonnet-4-5-20250929"),
    "ora_brain":       ("anthropic",  "claude-sonnet-4-5-20250929"),
    "code_fix":        ("anthropic",  "claude-sonnet-4-5-20250929"),
    "learning_digest": ("anthropic",  "claude-sonnet-4-5-20250929"),
}
DEFAULT: Tuple[str, str] = ("anthropic", "claude-sonnet-4-5-20250929")


def _get_db():
    """Resolve db handle. Prefer the running server's app-state handle;
    fall back to a fresh AsyncIOMotorClient using env config so cost
    logging works from background tasks, scripts, and tests too."""
    try:
        import server
        d = getattr(server, "db", None)
        if d is not None:
            return d
    except Exception:
        pass
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        url = os.environ.get("MONGO_URL")
        name = os.environ.get("DB_NAME")
        if url and name:
            return AsyncIOMotorClient(url)[name]
    except Exception:
        pass
    return None


async def _call_groq(
    model: str, prompt: str, system: Optional[str], max_tokens: int,
) -> Dict[str, Any]:
    """Groq Cloud chat completion (OpenAI-compatible endpoint).

    Free tier: very generous rate limits + sub-300ms typical latency
    (Groq runs on LPU hardware, not GPU). Raises if GROQ_API_KEY is
    missing so the route() fallback chain can try the next provider.
    """
    import httpx
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY missing")
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"model": model, "messages": msgs, "max_tokens": max_tokens},
        )
        r.raise_for_status()
        data = r.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    return {
        "text": text,
        "input_tokens": int(usage.get("prompt_tokens", 0)),
        "output_tokens": int(usage.get("completion_tokens", 0)),
    }


async def _call_openrouter(
    model: str, prompt: str, system: Optional[str], max_tokens: int,
) -> Dict[str, Any]:
    """OpenRouter chat completion (free tier)."""
    import httpx
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY missing")
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://aurem.live",
                "X-Title": "AUREM",
            },
            json={"model": model, "messages": msgs, "max_tokens": max_tokens},
        )
        r.raise_for_status()
        data = r.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    return {
        "text": text,
        "input_tokens": int(usage.get("prompt_tokens", 0)),
        "output_tokens": int(usage.get("completion_tokens", 0)),
    }


async def _call_emergent(
    model: str, prompt: str, system: Optional[str], max_tokens: int,
) -> Dict[str, Any]:
    """Emergent → Anthropic Claude Sonnet."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY missing")
    chat = LlmChat(
        api_key=api_key,
        session_id=f"gateway_{int(time.time())}",
        system_message=system or "You are AUREM's AI gateway.",
    ).with_model("anthropic", model).with_params(max_tokens=max_tokens)
    text = await chat.send_message(UserMessage(text=prompt))
    return {
        "text": text or "",
        "input_tokens": len(prompt) // 4,
        "output_tokens": len(text or "") // 4,
    }


_PROVIDER_DISPATCH = {
    "groq":       _call_groq,
    "openrouter": _call_openrouter,
    "anthropic":  _call_emergent,
}


def _chain_for(task_type: str) -> List[Tuple[str, str]]:
    """Normalize ROUTING_TABLE entries (tuple or list) into a chain."""
    entry = ROUTING_TABLE.get(task_type, DEFAULT)
    if isinstance(entry, tuple):
        return [entry]
    return list(entry)


async def route(
    task_type: str,
    prompt: str,
    *,
    system: Optional[str] = None,
    max_tokens: int = 1500,
) -> Dict[str, Any]:
    """Dispatch to the right model. Walks fallback chain. Logs cost on
    final outcome only (whatever succeeded — or last failure)."""
    chain = _chain_for(task_type)
    start = time.monotonic()
    final: Dict[str, Any] = {"text": "", "input_tokens": 0, "output_tokens": 0}
    final_provider, final_model = chain[0]
    final_err: Optional[str] = None
    attempts: List[str] = []

    for provider, model in chain:
        call = _PROVIDER_DISPATCH.get(provider)
        if call is None:
            final_err = f"unknown provider: {provider}"
            attempts.append(f"{provider}/{model}:unknown-provider")
            continue
        try:
            res = await call(model, prompt, system, max_tokens)
            if (res.get("text") or "").strip():
                final = res
                final_provider, final_model = provider, model
                final_err = None
                break
            attempts.append(f"{provider}/{model}:empty-text")
            final_err = f"{provider}/{model} returned empty text"
        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}"
            attempts.append(f"{provider}/{model}:{type(e).__name__}")
            final_err = err_msg
            final_provider, final_model = provider, model
            logger.info(f"[gateway] {task_type} {provider}/{model} failed → "
                        f"trying next in chain: {err_msg[:120]}")
            continue

    latency_ms = round((time.monotonic() - start) * 1000.0, 1)

    db = _get_db()
    if db is not None:
        try:
            await db.llm_costs.insert_one({
                "provider": final_provider,
                "model": final_model,
                "task_type": task_type,
                "tokens_in": final["input_tokens"],
                "tokens_out": final["output_tokens"],
                "latency_ms": latency_ms,
                "ok": final_err is None,
                "error": final_err,
                "chain_attempts": attempts,
                "ts": datetime.now(timezone.utc),
            })
        except Exception as e:
            logger.debug(f"[gateway] cost log failed: {e}")

    return {
        "text": final["text"],
        "model": final_model,
        "provider": final_provider,
        "latency_ms": latency_ms,
        "ok": final_err is None,
        "error": final_err,
        "tokens_in": final["input_tokens"],
        "tokens_out": final["output_tokens"],
        "chain_attempts": attempts,
    }
