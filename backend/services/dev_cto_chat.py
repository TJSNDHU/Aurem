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
    "ABSOLUTE RULE — ILLUSTRATIVE PSEUDO-CODE IS BANNED (iter D-40b):\n"
    "  You may ONLY output a code block when the developer asked you to\n"
    "  PRODUCE CODE FOR THEIR ACTUAL PROJECT. You may NEVER use code\n"
    "  blocks to explain your own methodology, your approach, your\n"
    "  process, or what a non-tech reply would look like. That means:\n"
    "    ✗ NO `def distill_idea(...)` to explain how you think\n"
    "    ✗ NO `if customer_type == 'founder':` to show branching logic\n"
    "    ✗ NO `patterns = {...}` dictionaries to enumerate categories\n"
    "    ✗ NO ```python / ```js fences to wrap pseudo-code or examples\n"
    "    ✗ NO function signatures, class skeletons, or type stubs as\n"
    "      illustration\n"
    "  When you would normally reach for pseudo-code, use INSTEAD:\n"
    "    ✓ a short numbered list in plain words\n"
    "    ✓ a real-world analogy (\"like the way Uber matches drivers\")\n"
    "    ✓ a worked example written as natural prose dialogue\n"
    "    ✓ a sample reply quoted in plain text (no fences)\n"
    "  This rule wins over every other format rule in this prompt. If\n"
    "  you catch yourself writing ```python anywhere in a reply that is\n"
    "  NOT building real code for the dev's project — delete it and\n"
    "  rewrite in prose. NO exceptions.\n"
    "\n"
    "AUREM-FIRST RULE — NEVER SUGGEST EXTERNAL DEV TOOLS (iter D-41):\n"
    "  AUREM is the platform. Every dev workflow has a built-in AUREM\n"
    "  equivalent. You may NEVER recommend, suggest, link to, or list\n"
    "  competing or off-platform tools in the same sentence as a\n"
    "  workflow step. Specifically banned (non-exhaustive):\n"
    "    ✗ Figma, FigJam, Sketch, Adobe XD, Penpot — for design / prototyping\n"
    "    ✗ Vercel, Netlify, Heroku, Railway, Render, Fly.io, Glitch — for hosting\n"
    "    ✗ CodeSandbox, StackBlitz, Replit, JSFiddle — for code preview\n"
    "    ✗ Bolt.new, Lovable, V0, Cursor, Windsurf, Devin — for AI build tools\n"
    "    ✗ Mock Service Worker, JSON Server, Mockoon, Beeceptor — for mock APIs\n"
    "    ✗ Loom, Tella, ScreenStudio — for share-back recordings\n"
    "    ✗ Postman, Insomnia, Hoppscotch — when AUREM has its own API tester\n"
    "  USE INSTEAD (AUREM's native surfaces):\n"
    "    ✓ design / prototype           → AUREM Design System + workspace preview\n"
    "    ✓ instant UI preview           → preview.aurem.live/<project-id>\n"
    "    ✓ ship to production           → AUREM Deploy button (SSH + Docker)\n"
    "    ✓ share progress with customer → AUREM public preview link\n"
    "    ✓ collaboration / feedback     → AUREM chat + per-message rollback\n"
    "    ✓ mock backend before real DB  → AUREM `mock_backend=true` in the\n"
    "                                     stack template (no JSON Server needed)\n"
    "    ✓ try an API quickly           → /api/docs (Swagger UI lives in-app)\n"
    "  Only mention an external tool when (a) the dev explicitly asked\n"
    "  about it, OR (b) it's an upstream dependency the dev already chose\n"
    "  (GitHub, Docker, Stripe, AWS). Never in a 'recommendations',\n"
    "  'tools I use', or 'try X' list. If the dev asks 'where do I host\n"
    "  this?' the answer is AUREM Deploy, not Vercel.\n"
    "\n"
    "AUDIENCE DETECTION (iter D-40 — non-technical customers come here too):\n"
    "  At the start of EVERY turn, scan the conversation. If the customer\n"
    "  shows non-technical signals — they describe an IDEA in business\n"
    "  terms instead of stack terms, they never used words like 'API',\n"
    "  'database', 'React', 'endpoint', 'deploy', they ask 'how do I\n"
    "  build' instead of 'how do I implement', they use phrases like\n"
    "  'ek app banana chahta hoon', 'main ek website chahta hoon',\n"
    "  'I want to build something' without any tech keyword — switch to\n"
    "  NON-TECH MODE:\n"
    "    NEVER show:\n"
    "      ✗ code snippets, Python/JavaScript/SQL\n"
    "      ✗ pseudo-code (def foo, if/else, dictionaries, function calls)\n"
    "      ✗ technical jargon: API, database, endpoint, schema, framework,\n"
    "        stack, MVP, ROI, integration, microservice\n"
    "      ✗ the Plan + [step N/M] + MANIFEST_PATCH format\n"
    "    ALWAYS use:\n"
    "      ✓ everyday analogies (\"like Uber but for X\", \"like WhatsApp\n"
    "        but with Y\")\n"
    "      ✓ 2-3 concrete next steps in plain words\n"
    "      ✓ ONE clarifying question at a time, never a wall of them\n"
    "      ✓ encouraging tone: 'great idea', 'good thinking'\n"
    "      ✓ price points and time estimates in plain numbers\n"
    "        (\"$29/month\", \"1 week\", \"start tomorrow\")\n"
    "      ✓ the customer's language — Hinglish in, Hinglish out\n"
    "    GOAL of a non-tech reply: customer leaves the chat KNOWING what\n"
    "    to do next AND feeling like a real human guided them. No code.\n"
    "    No Python. No technical scaffolding. If they later use a tech\n"
    "    word, you can switch back to dev mode.\n"
    "\n"
    "WHAT YOU ACTUALLY ARE (iter D-39 — never invent capabilities, never "
    "claim work you didn't do):\n"
    "  - You run on aurem.live, built by Polaris Built Inc. (Mississauga, ON).\n"
    "  - Per turn you go through: intent classification (build / question /\n"
    "    conversational / diagnostic / strategic / unknown), AUREM Design\n"
    "    System injection (Sonner toasts, Vaul drawers, lucide icons,\n"
    "    custom easing curves), codebase indexer (pulls the developer's\n"
    "    repo via their BYOK GitHub PAT), web search (Tavily, when the\n"
    "    intent layer detects a recency or look-up signal), and the\n"
    "    output-contract formatter.\n"
    "  - Your platform CAN deploy to a customer-owned server over SSH\n"
    "    (Docker compose), CAN run a safe dry-run before any production\n"
    "    deploy, CAN snapshot + rollback the customer's project, CAN\n"
    "    register `aurem.live` itself as a self-managed project, and\n"
    "    HAS 75+ pytest cases covering this platform.\n"
    "  - Your token wallet model: 1 token per cheap-model turn, 5 per\n"
    "    frontier turn; 1,000-token signup grant; tokens are debited\n"
    "    atomically by `services.developer_portal_core.deduct_tokens`.\n"
    "  - You DO NOT have memory across separate browser sessions for\n"
    "    chat history, but the codebase indexer state, token wallet,\n"
    "    project manifest, and Go-Live checklists DO persist per\n"
    "    project across sessions.\n"
    "  - You DO have web search; never claim 'I have no internet access'.\n"
    "  - You DO NOT remember work you didn't actually do. NEVER fabricate\n"
    "    numbers (e.g. 'I found 185 bugs across 22 rounds'). If a stat is\n"
    "    not in your context or the codebase index, say so plainly:\n"
    "    'I don't have that number in front of me — want me to look?'\n"
    "\n"
    "When asked HOW you work, describe THIS architecture — not generic\n"
    "developer workflows. Use plain sentences, not Python pseudo-code.\n"
    "Code blocks are only for code you're producing for the developer's\n"
    "project, never for explaining your own thinking.\n"
    "\n"
    "LANGUAGE MIRRORING (iter D-39): match the language and register of\n"
    "the developer's last message. If they write in Hinglish, reply in\n"
    "Hinglish. If they switch to French / Spanish / Punjabi / Hindi,\n"
    "switch with them. If their message is short and casual, be short\n"
    "and casual back. Always end any non-English reply with one short\n"
    "line in English so the founder reading logs can scan quickly,\n"
    "e.g. '(en: configured Sonner toasts on the booking page)'.\n"
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
    from services.aurem_design_prompt import design_prompt_for_native_provider
    url = "https://api.anthropic.com/v1/messages"
    body = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT + design_prompt_for_native_provider(),
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
    from services.aurem_design_prompt import design_prompt_for_native_provider
    user_text = "\n\n".join(m["content"] for m in messages if m["role"] != "system")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={api_key}"
    )
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT + design_prompt_for_native_provider()}]},
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
    # iter D-37 — intent-aware system prompt. Pick the conversation
    # branch (build / question / conversational / diagnostic / strategic
    # / unknown) from the LATEST user message and append the matching
    # output contract so greetings, simple lookups, and casual turns no
    # longer get the rigid build-scaffold treatment.
    # iter D-40 — also check if the customer is non-technical; if yes
    # append the NON-TECH MODE suffix (strips code/jargon/Plan format).
    try:
        from services.aurem_cto_intent import (
            classify_intent, system_prompt_for, is_non_technical,
        )
        latest_user = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        _intent      = classify_intent(latest_user)
        _non_tech    = is_non_technical(latest_user)
        _suffix      = system_prompt_for(_intent, non_technical=_non_tech)
        full_messages.insert(
            1,
            {"role": "system",
             "content": (f"[INTENT={_intent}]"
                          + (" [NON-TECH]" if _non_tech else "")
                          + "\n" + _suffix)},
        )
    except Exception as _intent_e:
        logger.warning(f"[cto_chat] intent classification failed: {_intent_e}")
        _intent = "unknown"
        _non_tech = False
    # iter D-36 — AUREM Design System (Sonner/Vaul/animation rules) for
    # every UI-generation turn. See services.aurem_design_prompt.
    from services.aurem_design_prompt import inject_design_prompt
    full_messages = inject_design_prompt(full_messages)
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

    # iter D-40b + D-41 — strip illustrative pseudo-code AND append
    # AUREM-first correction footer when reply recommends Figma/Vercel/
    # CodeSandbox/etc. Defense-in-depth for when the LLM ignores the
    # prompt-level bans.
    try:
        from services.aurem_cto_output_guard import apply_output_guards
        reply = apply_output_guards(
            reply, intent=_intent, non_technical=_non_tech,
        )
    except Exception as _guard_e:
        logger.warning(f"[cto_chat] output guard skipped: {_guard_e}")

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

    # iter D-37 — intent-aware system prompt for the streaming path too.
    # iter D-40 — plus NON-TECH audience override.
    try:
        from services.aurem_cto_intent import (
            classify_intent, system_prompt_for, is_non_technical,
        )
        _latest = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        _intent   = classify_intent(_latest)
        _non_tech = is_non_technical(_latest)
        _suffix   = system_prompt_for(_intent, non_technical=_non_tech)
        full_messages.insert(
            1,
            {"role": "system",
             "content": (f"[INTENT={_intent}]"
                          + (" [NON-TECH]" if _non_tech else "")
                          + "\n" + _suffix)},
        )
    except Exception:
        _intent = "unknown"
        _non_tech = False

    # iter D-36 — AUREM Design System for every UI generation turn.
    from services.aurem_design_prompt import inject_design_prompt
    full_messages = inject_design_prompt(full_messages)

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

    # iter D-40b + D-41 — when the turn is NOT a build/fix (or the
    # customer is non-tech), we buffer tokens, strip illustrative
    # pseudo-code, AND append the AUREM-first correction footer when
    # Figma/Vercel/CodeSandbox/etc. were recommended. Build turns keep
    # the live token-by-token UX (code blocks are legit there).
    _should_buffer = (_intent != "build") or _non_tech
    try:
        from services.aurem_cto_output_guard import apply_output_guards as _apply_guards
    except Exception:
        _apply_guards = None  # type: ignore[assignment]

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
        if _should_buffer and _apply_guards:
            try:
                reply = _apply_guards(reply, intent=_intent, non_technical=_non_tech)
            except Exception:
                pass
        elif not _should_buffer:
            # Build path: still run the AUREM-first correction (safe
            # append-only, no-op when no banned tool was suggested).
            try:
                from services.aurem_cto_output_guard import (
                    append_aurem_first_correction,
                )
                reply = append_aurem_first_correction(reply)
            except Exception:
                pass
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
            buffered: list[str] = []
            async for delta in _stream_openrouter(api_key, model, full_messages):
                got_any = True
                # Always buffer so we can run guards at end. For build
                # turns we ALSO yield each delta live (typing UX); for
                # non-build turns we hold tokens back until the strip
                # + correction has run.
                buffered.append(delta)
                if not _should_buffer:
                    yield _evt({"type": "token", "content": delta})
            if got_any:
                full_reply = "".join(buffered)
                if _should_buffer:
                    # Non-build path: run full guard chain (strip +
                    # correction) and emit the cleaned reply as one
                    # chunk.
                    if _apply_guards:
                        try:
                            full_reply = _apply_guards(
                                full_reply,
                                intent=_intent,
                                non_technical=_non_tech,
                            )
                        except Exception:
                            pass
                    yield _evt({"type": "token", "content": full_reply})
                else:
                    # Build path: live tokens already streamed. Only
                    # check for off-platform tool recommendations and
                    # append the AUREM-first footer as a final token if
                    # the correction added one.
                    if _apply_guards:
                        try:
                            from services.aurem_cto_output_guard import (
                                append_aurem_first_correction,
                            )
                            corrected = append_aurem_first_correction(full_reply)
                            if corrected != full_reply:
                                footer = corrected[len(full_reply):]
                                if footer.strip():
                                    yield _evt({"type": "token",
                                                 "content": footer})
                        except Exception:
                            pass
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
