"""
Developer-portal CTO chat service — iter 332b D-11
================================================

Powers the chat box on /developers/dashboard. Strategy per founder
directive (no Emergent LLM key for free-tier devs):

  FREE TIER (no BYOK) — all routed through OpenRouter:
    1. deepseek/deepseek-chat            (primary,  $0.27/1M)
    2. meta-llama/llama-3.3-70b-instruct:free  (fallback, free)
    3. mistralai/mistral-7b-instruct:free      (last resort, free)
  One key for everything: OPENROUTER_API_KEY.

  BYOK USERS:
    Use whichever provider key they configured. Picked in this order so
    users with multiple keys get the smartest model first:
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

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Hard per-model timeout. Cloudflare's edge gives us ~100s upstream.
# With 3 models in the ladder we keep each attempt under 28s so even a
# full primary→fallback→last-resort traversal lands inside the budget.
_OPENROUTER_TIMEOUT_S = 28.0

# Free-tier OpenRouter model ladder (primary → fallback → last resort).
# We deliberately use the PAID-rate `meta-llama/llama-3.3-70b-instruct`
# and `mistralai/mistral-7b-instruct` (no `:free` suffix) as the
# fallback rungs — the `:free` variants queue behind paid traffic and
# routinely exceed Cloudflare's 100s upstream timeout, returning HTML
# 524 instead of a clean JSON error. Pennies per million tokens on
# these paid rungs is worth not breaking the UX.
FREE_TIER_MODELS = (
    ("deepseek/deepseek-chat",                  "deepseek"),
    ("meta-llama/llama-3.3-70b-instruct",       "llama"),
    ("mistralai/mistral-7b-instruct",           "mistral"),
)

# OpenAI-compatible endpoints + default models for BYOK users
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
    "Skip pleasantries. Never refuse a legitimate engineering question.\n"
    "\n"
    "INTERNET ACCESS — you DO have live web search. When the developer asks "
    "about \"latest\", \"current\", \"recent\", a specific URL, or says "
    "\"/search …\" or \"look up …\", a tool layer fetches fresh Tavily web "
    "results and injects them into your context as a system message *before* "
    "the user's question. Read those results and ground your reply in them. "
    "If you weren't given search results, just say so plainly — don't claim "
    "you have no internet access ever.\n"
    "\n"
    "OUTPUT CONTRACT — follow this format on EVERY reply:\n"
    "\n"
    "1. If the developer asked for a build / feature / debug task, ALWAYS "
    "open with a short numbered plan like `Plan (5 steps): 1) ... 2) ...`. "
    "Then immediately start executing step 1. Inside the body, prefix each "
    "step you're currently working on with the literal marker `[step N/M]` "
    "(e.g. `[step 2/5] Wiring the POST route...`) so the UI can render a "
    "progress bar. Keep these markers short.\n"
    "\n"
    "2. FRONTEND-FIRST RULE: when building any feature that has a UI, "
    "always design and propose the frontend layout (component tree, props, "
    "states, key data-testids) BEFORE writing any backend code. Only after "
    "the developer confirms the frontend shape should you wire the backend.\n"
    "\n"
    "3. Code: return runnable, well-commented snippets that follow best "
    "practices. Match the repo's existing style if you can infer it.\n"
    "\n"
    "4. NEXT-STEPS CONTRACT — end EVERY reply with EXACTLY one line in this "
    "format so the UI can render clickable chips:\n"
    "   NEXT_STEPS: [\"<short action 1>\", \"<short action 2>\", \"<short action 3>\"]\n"
    "Each action must be at most 5 words and phrased as something the "
    "developer can click to continue (e.g. \"Continue with step 3\", "
    "\"Show me the test file\", \"Refactor for performance\"). If the task is "
    "truly complete, use [\"Mark as done\", \"Start next task\", \"Show summary\"].\n"
    "\n"
    "5. PROGRESS CONTRACT (iter D-32) — when the conversation is part of a "
    "build project, emit these three lines on a NEW LINE somewhere in your "
    "reply so the workspace UI can update the project preview live:\n"
    "   progress: 0.XX     (a float 0.0 → 1.0 estimating completeness)\n"
    "   phase: <one of: drafting | designing | building | polishing | shipping>\n"
    "   MANIFEST_PATCH: {\"title\": \"...\", \"tagline\": \"...\", \"sections\": [...]}\n"
    "Only emit MANIFEST_PATCH when there's a real visible change (new "
    "hero copy, new feature block, new CTA). Sections is a JSON array of "
    "{\"kind\": \"hero\"|\"feature\"|\"cta\"|\"block\", \"heading\": \"...\", "
    "\"text\": \"...\"}. Keep the JSON small — under 1KB. The preview at "
    "preview.aurem.live/<project-id> re-renders from this manifest, so each "
    "MANIFEST_PATCH the dev approves is what they'll see live. When "
    "progress reaches 0.80 the Go-Live checklist auto-unlocks for the "
    "customer (GitHub → server → domain → BYOK), so be honest about the "
    "number."
)


# ── Web search injection — iter 332b D-29 ─────────────────────────────
#
# Why this exists:
#   Founder noticed the Dev CTO chat said it had no internet access. We
#   already pay for Tavily (used by Scout) so the LLM can absolutely
#   look stuff up — we just weren't wiring those results in.
#
# How it works:
#   1. Sniff the latest user message for search intent.
#   2. If found, call services.tier1_upgrades.tavily_search() with a
#      hard 6-second budget.
#   3. Inject the top 3 hits as a "tool_result"-style system message
#      right before the user turn.  The LLM grounds its reply on
#      those facts (URLs, titles, 300-char snippets) instead of
#      guessing or refusing.
#
# Search-intent triggers (case-insensitive):
#   • Explicit prefix:   "/search ", "/web "
#   • Direct keywords:   "search for", "look up", "google", "find me"
#   • Recency triggers:  "latest", "today", "current", "recent",
#                         "in 2026", "this week", "right now"
#   • URLs in the prompt (the LLM probably needs to read them).
import re as _re

_SEARCH_PREFIX_RE = _re.compile(r"^\s*/(search|web)\s+(.+)$", _re.I)
_SEARCH_INTENT_RE = _re.compile(
    r"\b(search for|look\s*up|google|find me|fetch|latest|today's|today|"
    r"current|recent|right now|this (?:week|month|year)|in (?:202[4-9]|203\d))\b",
    _re.I,
)
_URL_RE = _re.compile(r"https?://[^\s)<>\"']+", _re.I)


def _extract_search_query(user_msg: str) -> str | None:
    """Returns a query string when the user's message implies they
    want fresh web info, or None to skip search. Heuristics only —
    we don't want to spend Tavily quota on every "hello"."""
    if not user_msg or len(user_msg) > 1000:
        return None
    m = _SEARCH_PREFIX_RE.match(user_msg)
    if m:
        return m.group(2).strip()[:200]
    # URL anywhere → research the URL.
    urls = _URL_RE.findall(user_msg)
    if urls:
        return urls[0]
    if _SEARCH_INTENT_RE.search(user_msg):
        # Use the whole question as the query (Tavily handles natural language).
        return user_msg.strip()[:200]
    return None


async def _maybe_inject_web_search(
    full_messages: list[dict[str, str]],
    original_messages: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Detect search-intent on the last user turn and inject Tavily
    results as a system message. Never raises — silently no-ops on
    any failure (no key, network down, etc.).

    iter 332b D-29.
    """
    if not original_messages:
        return full_messages
    last = original_messages[-1]
    if last.get("role") != "user":
        return full_messages
    query = _extract_search_query(str(last.get("content") or ""))
    if not query:
        return full_messages
    try:
        import asyncio as _aio
        from services.tier1_upgrades import tavily_search
        result = await _aio.wait_for(
            tavily_search(query, max_results=3, search_depth="basic"),
            timeout=6.0,
        )
        hits = result.get("results") or []
        if not hits:
            return full_messages

        # Build a compact tool-result block. Keep it short so it doesn't
        # eat the whole context window.
        lines = [f"[Live web search results for: {query!r}]"]
        ans = (result.get("answer") or "").strip()
        if ans:
            lines.append(f"Summary: {ans[:400]}")
        for i, h in enumerate(hits[:3], 1):
            title = (h.get("title") or "")[:90]
            url = h.get("url") or ""
            content = (h.get("content") or "")[:280].replace("\n", " ")
            lines.append(f"{i}. {title}\n   {url}\n   {content}")
        lines.append(
            "[Use these results to answer. If they don't cover the question, "
            "say so plainly — don't hallucinate.]"
        )
        injection = {"role": "system", "content": "\n".join(lines)}
        # Insert RIGHT BEFORE the user's question so the LLM sees the
        # fresh facts as immediate context.
        out = list(full_messages)
        out.insert(-1, injection)
        return out
    except Exception as e:
        logger.warning(f"[cto_chat] web search injection skipped: {e}")
        return full_messages





def _free_tier_key() -> str | None:
    """Returns OPENROUTER_API_KEY or None if unset."""
    k = os.environ.get("OPENROUTER_API_KEY", "").strip()
    return k or None


def _pick_byok_provider(byok: dict[str, str]) -> tuple[str, str] | None:
    for name in BYOK_PREFERENCE:
        v = (byok or {}).get(name)
        if v and isinstance(v, str) and v.strip():
            return (name, v.strip())
    return None


async def _call_openrouter(
    api_key: str, model: str, messages: list[dict[str, str]],
) -> str:
    payload = {"model": model, "messages": messages,
               "max_tokens": 1024, "temperature": 0.4}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://aurem.live",
        "X-Title":       "AUREM CTO",
    }
    # iter 332b D-14 — hard timeout per model so we always fit under
    # Cloudflare's 100s ceiling and never let it return HTML 524.
    async with httpx.AsyncClient(timeout=_OPENROUTER_TIMEOUT_S) as c:
        r = await c.post(OPENROUTER_URL, json=payload, headers=headers)
    if r.status_code >= 400:
        raise RuntimeError(f"openrouter HTTP {r.status_code}: {r.text[:200]}")
    j = r.json()
    return (j.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()


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


async def _dispatch_byok(provider: str, api_key: str,
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


async def _dispatch_free_tier(api_key: str,
                               messages: list[dict[str, str]]) -> tuple[str, str]:
    """Walk the FREE_TIER_MODELS ladder, return (reply, label_used).
    Raises if every model fails."""
    last_err: Exception | None = None
    for model, label in FREE_TIER_MODELS:
        try:
            reply = await _call_openrouter(api_key, model, messages)
            return reply, label
        except Exception as e:
            logger.warning(f"[cto_chat] free-tier {model} failed: {e}")
            last_err = e
            continue
    raise RuntimeError(f"all free-tier models failed; last error: {last_err}")


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

    # Choose tier
    picked_byok = _pick_byok_provider(byok_plain)
    tier = "byok" if picked_byok else "free"

    if tier == "free" and not _free_tier_key():
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

    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]
    # iter 332b D-29 — inject web-search context (see helper docstring).
    full_messages = await _maybe_inject_web_search(full_messages, messages)
    try:
        if tier == "byok":
            provider, api_key = picked_byok  # type: ignore[misc]
            reply = await _dispatch_byok(provider, api_key, full_messages)
        else:
            api_key = _free_tier_key() or ""
            reply, provider = await _dispatch_free_tier(api_key, full_messages)
    except Exception as e:
        return {
            "ok": False, "error": "llm_failed", "tier": tier,
            "message": str(e),
        }

    tokens_remaining = deduct.get("tokens_remaining")
    if tokens_remaining is None:
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


# ───────────────────────── Streaming (iter 332b D-15) ────────────────
#
# Server-Sent Events stream. Each line over the wire is JSON, terminated
# by "\n\n" so browser EventSource / fetch-stream readers can parse.
#   {"type":"meta","tier":"free","provider":"deepseek","tokens_remaining":499}
#   {"type":"token","content":"Python "}
#   {"type":"token","content":"decorators "}
#   ...
#   {"type":"done"}
# On error:
#   {"type":"error","message":"...","action_required":"add_byok"}
#
# All upstream JSON parsing failures surface as a single "error" event so
# the frontend never sees raw HTML or partial JSON.

import json as _json


async def _stream_openrouter(api_key: str, model: str,
                              messages: list[dict[str, str]]):
    """Async-iter over OpenRouter SSE chunks for one model. Yields
    plain text deltas. Raises on HTTP error so the caller can fall
    through to the next rung on the free-tier ladder."""
    payload = {"model": model, "messages": messages,
               "max_tokens": 1024, "temperature": 0.4, "stream": True}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://aurem.live",
        "X-Title":       "AUREM CTO",
        "Accept":        "text/event-stream",
    }
    async with httpx.AsyncClient(timeout=_OPENROUTER_TIMEOUT_S) as c:
        async with c.stream("POST", OPENROUTER_URL,
                             json=payload, headers=headers) as r:
            if r.status_code >= 400:
                body = (await r.aread()).decode("utf-8", "replace")[:200]
                raise RuntimeError(f"openrouter HTTP {r.status_code}: {body}")
            async for raw in r.aiter_lines():
                if not raw or not raw.startswith("data:"):
                    continue
                data = raw[5:].strip()
                if data == "[DONE]":
                    return
                try:
                    j = _json.loads(data)
                except Exception:
                    continue
                delta = (j.get("choices") or [{}])[0].get("delta", {})
                txt = delta.get("content") or ""
                if txt:
                    yield txt


async def cto_chat_stream(
    *, account: dict[str, Any], messages: list[dict[str, str]],
):
    """Async generator that emits SSE-formatted JSON lines. Always emits
    at least a `meta` then either tokens+done OR an `error`. Never
    raises out of the generator — the FastAPI route streams whatever
    we yield."""
    def _evt(payload: dict) -> str:
        return f"data: {_json.dumps(payload)}\n\n"

    # Decrypt BYOK
    byok_envelope = account.get("byok_keys")
    byok_plain: dict[str, str] = {}
    if byok_envelope and isinstance(byok_envelope, dict):
        try:
            from services.developer_portal_core import decrypt_byok
            byok_plain = decrypt_byok(byok_envelope) or {}
        except Exception as e:
            logger.warning(f"[cto_chat_stream] BYOK decrypt failed: {e}")

    picked_byok = _pick_byok_provider(byok_plain)
    tier = "byok" if picked_byok else "free"

    if tier == "free" and not _free_tier_key():
        yield _evt({"type": "error", "tier": "free",
                     "error": "no_llm_configured",
                     "action_required": "add_byok",
                     "message": (
                         "Free-tier LLM is currently unavailable. "
                         "Please add your own API key on the Connect page."
                     )})
        return

    from services.developer_portal_core import deduct_tokens
    deduct = await deduct_tokens(account["user_id"], "chat")
    if not deduct.get("ok", True) and not deduct.get("internal"):
        yield _evt({"type": "error", "tier": tier,
                     "error": "token_wall",
                     "action_required": "add_byok",
                     "tokens_remaining": deduct.get("tokens_remaining", 0),
                     "message": (
                         "You're out of free tokens. Add your own API "
                         "key on the Connect page."
                     )})
        return

    full_messages = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]

    # iter D-33 — Gap 1: inject the customer's codebase index as an
    # extra system message before the user turn. Best-effort, never
    # raises. Skips silently when the customer hasn't connected GitHub
    # or hasn't called /aurem-cto/codebase/refresh yet.
    try:
        if account and account.get("user_id"):
            from aurem_cto.services.codebase_indexer import build_context_block
            ctx = await build_context_block(account["user_id"], max_chars=6000)
            if ctx:
                full_messages = [
                    full_messages[0],
                    {"role": "system", "content": ctx},
                    *full_messages[1:],
                ]
    except Exception as _ctx_err:
        import logging as _lg
        _lg.getLogger(__name__).debug(
            f"[dev-cto] codebase context skipped: {_ctx_err}")

    # iter 332b D-29 — internet access for the Dev CTO chat.
    # Detect a search-intent in the user's latest message (the word
    # "search" / "look up" / "latest" / "/search ..." prefix etc.) and
    # inject the top Tavily hits as an extra system message so the LLM
    # has fresh facts to ground its reply.
    full_messages = await _maybe_inject_web_search(full_messages, messages)

    tokens_remaining = deduct.get("tokens_remaining", 0)

    # BYOK path is non-streaming (we'd need per-provider streaming
    # logic; not worth the LOC tonight). Emit the meta then the whole
    # reply as one token event so the frontend code stays unchanged.
    if tier == "byok":
        provider, api_key = picked_byok  # type: ignore[misc]
        yield _evt({"type": "meta", "tier": tier, "provider": provider,
                     "tokens_remaining": int(tokens_remaining or 0)})
        try:
            reply = await _dispatch_byok(provider, api_key, full_messages)
        except Exception as e:
            yield _evt({"type": "error", "tier": tier,
                         "error": "llm_failed", "message": str(e)})
            return
        yield _evt({"type": "token", "content": reply})
        yield _evt({"type": "done",
                     "tokens_remaining": int(tokens_remaining or 0),
                     "low_balance": int(tokens_remaining or 0) < 100})
        return

    # Free tier: walk the OpenRouter ladder, emit tokens as they arrive
    api_key = _free_tier_key() or ""
    last_err: Exception | None = None
    for model, label in FREE_TIER_MODELS:
        try:
            # Emit meta as soon as we know which model we're trying.
            yield _evt({"type": "meta", "tier": tier, "provider": label,
                         "model": model,
                         "tokens_remaining": int(tokens_remaining or 0)})
            got_any = False
            async for delta in _stream_openrouter(api_key, model, full_messages):
                got_any = True
                yield _evt({"type": "token", "content": delta})
            if got_any:
                yield _evt({"type": "done",
                             "tokens_remaining": int(tokens_remaining or 0),
                             "low_balance": int(tokens_remaining or 0) < 100})
                return
            # Empty stream — try next model
            last_err = RuntimeError(f"{model}: empty stream")
        except Exception as e:
            logger.warning(f"[cto_chat_stream] {model} failed: {e}")
            last_err = e
            continue

    yield _evt({"type": "error", "tier": tier,
                 "error": "llm_failed",
                 "message": f"All free-tier models failed: {last_err}"})
