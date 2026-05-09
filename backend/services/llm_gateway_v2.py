"""
AUREM LLM Gateway — Phase 0 (Sovereign Routing)
================================================
Single entrypoint for every LLM call in the platform.

Routes by **task_type** to the cheapest model that can do the job:
  • Free OpenRouter models for routine work (scout/council/blast)
  • Claude Sonnet (via Emergent) for complex reasoning (repair/brain)

Every call is **persisted** in `db.llm_costs` (no try/except swallow).

Public:
  await llm_gateway.route(task_type, prompt, system=None, max_tokens=1500)
"""
from __future__ import annotations

import os
import time
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ─── Routing table — task_type → (provider, model_id) ────────────────
ROUTING_TABLE: Dict[str, tuple] = {
    # FREE — OpenRouter (zero cost)
    "scout_filter":     ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
    "lead_qualify":     ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
    "blast_compose":    ("openrouter", "zai-org/glm-5.1"),
    "council_vote":     ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
    "content_qa":       ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
    "sentiment":        ("openrouter", "google/gemma-4-26b-it:free"),
    "heartbeat_check":  ("openrouter", "minimax/minimax-m2.5:free"),
    "pattern_match":    ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
    # PAID — Claude Sonnet via Emergent (complex only)
    "repair_diagnose":  ("anthropic",  "claude-sonnet-4-5-20250929"),
    "ora_brain":        ("anthropic",  "claude-sonnet-4-5-20250929"),
    "code_fix":         ("anthropic",  "claude-sonnet-4-5-20250929"),
    "learning_digest":  ("anthropic",  "claude-sonnet-4-5-20250929"),
}
DEFAULT = ("anthropic", "claude-sonnet-4-5-20250929")


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


async def route(
    task_type: str,
    prompt: str,
    *,
    system: Optional[str] = None,
    max_tokens: int = 1500,
) -> Dict[str, Any]:
    """Dispatch to the right model. Logs cost. Never silent."""
    provider, model = ROUTING_TABLE.get(task_type, DEFAULT)
    start = time.monotonic()
    err: Optional[str] = None
    result: Dict[str, Any] = {"text": "", "input_tokens": 0, "output_tokens": 0}

    try:
        if provider == "openrouter":
            result = await _call_openrouter(model, prompt, system, max_tokens)
        else:
            result = await _call_emergent(model, prompt, system, max_tokens)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        logger.warning(f"[gateway] {task_type}/{model} failed: {err}")

    latency_ms = round((time.monotonic() - start) * 1000.0, 1)

    db = _get_db()
    if db is not None:
        await db.llm_costs.insert_one({
            "provider": provider,
            "model": model,
            "task_type": task_type,
            "tokens_in": result["input_tokens"],
            "tokens_out": result["output_tokens"],
            "latency_ms": latency_ms,
            "ok": err is None,
            "error": err,
            "ts": datetime.now(timezone.utc),
        })

    return {
        "text": result["text"],
        "model": model,
        "provider": provider,
        "latency_ms": latency_ms,
        "ok": err is None,
        "error": err,
        "tokens_in": result["input_tokens"],
        "tokens_out": result["output_tokens"],
    }
