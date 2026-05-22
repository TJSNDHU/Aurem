"""
ora_agent.py — Autonomous CTO mode for ORA (iter 322fi — patched).

Founder mandate: ONE chat interface. No more "CTO Mode tab" or manual tool
picking. ORA reads → plans → executes safe tools autonomously → asks for
inline approval on risky tools → verifies → recovers from failures.

Three risk tiers (every tool in the registry is tagged with one):
    TIER_1_AUTO     : pure observation — view, grep, curl, db read, claim_build_done
    TIER_2_APPROVE  : mutates state but reversible — safe_edit, restart_service,
                      ora_rollback, propose_commit, save_to_github
    TIER_3_HIGH_RISK: irreversible / external — legion_exec (high-risk),
                      production .env edits, paid API calls

State machine for pending tool calls (Mongo `ora_pending_actions`):
    pending → executing → done | failed
                        → rejected
                        → expired (auto-reject after 30 min)

Flow in chat:
    1. User: "Fix the legion 503 on prod"
    2. ORA returns assistant turn — may include up to N tool_calls
    3. For each tool_call:
         tier1 → execute inline, feed result back, repeat
         tier2+ → write pending row, return action_required to UI
    4. UI shows inline card with [Approve] / [Reject] buttons
    5. User clicks → POST /api/ora/agent/approve/{action_id}
    6. Backend executes, attaches result, returns next assistant turn
    7. Repeat until no more pending or assistant outputs final text

PATCHES APPLIED (all bugs from deep-scan):
    #1  ora_rollback_list removed from TIER_1_AUTO (was duplicate / auto-ran)
    #2  resume_after_decision: atomic find_one_and_update TOCTOU fix
    #3  _save_history: system prompt pinned, never sliced off
    #4  _continue_loop: only tool_calls[0] stored in history
    #5  _continue_loop: uuid4() server-side action_id, LLM id never used as Mongo _id
    #6  _continue_loop: wall-clock budget cap (ORA_MAX_LOOP_S env, default 150s)
    #7  git_bisect added to TIER_1_AUTO (system prompt promises autonomous bug-hunt)
    #8  resume_after_decision: _expire_old() called before atomic gate
    #9  _recovery_directive: role changed from "tool" to "system" (OpenAI format fix)
    #10 Groq httpx timeout < asyncio wait_for timeout (no leaked connection)
    #11 All datetime/time/re imports moved to module top (no hot-path re-imports)
    #12 Claude fallback model string made env-configurable
"""
from __future__ import annotations

import json
import logging
import os
import re
import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4

import httpx

from services.ora_tools import invoke_tool, TOOL_REGISTRY

logger = logging.getLogger(__name__)


# ── Constants ─────────────────────────────────────────────────────────
EXPIRY_MINUTES:        int = int(os.environ.get("ORA_APPROVAL_EXPIRY_MIN", "60"))

# iter 326w — 30-second cancel window for Tier 2 actions. Founder
# chose this UX so they don't have to click [Approve] on every safe-edit
# / restart / status-write. The action lands as pending with an
# `auto_execute_at` 30 s in the future; if no /reject within that
# window, the auto-executor (see auto_execute_due_tier2) calls the
# normal approve path and ORA proceeds. Tier 3 (irreversible /
# high-risk) is NOT auto-executed — founder must still click approve.
TIER2_AUTO_EXECUTE_SECONDS: int = 30
MAX_TOOL_ITERATIONS:   int = 8
MAX_LOOP_WALL_SECONDS: int = int(os.environ.get("ORA_MAX_LOOP_S", "300"))
PENDING_COLLECTION:    str = "ora_pending_actions"
HISTORY_COLLECTION:    str = "ora_agent_history"
HISTORY_CAP:           int = 40   # non-system messages kept per session

# Groq timeouts — inner httpx must be LESS than outer asyncio.wait_for
# so asyncio never cancels a mid-flight httpx connection.
_GROQ_HTTPX_TIMEOUT:  float = 18.0   # httpx connect+read
_GROQ_WAIT_FOR:       float = 20.0   # asyncio.wait_for wrapper
# iter 325z — bumped from 15s → 30s. Claude is the safety-net fallback
# when DeepSeek is slow/cold; the old 15s budget often killed it before
# Anthropic finished streaming, producing the spurious "Claude bhi reach
# nahi ho raha" degrade message even though the provider was healthy.
_CLAUDE_WAIT_FOR:     float = 30.0
# iter 325j → iter 325z — DeepSeek V3.1 via OpenRouter (primary chat
# provider). Bumped 22/25s → 42/45s. OpenRouter Novita endpoint cold-
# starts can take 30-40s on the first hit per pod; old budget killed
# perfectly healthy DeepSeek calls and triggered the "primary brain
# unreachable" graceful-degrade message (founder report 2026-05-21).
_DEEPSEEK_HTTPX_TIMEOUT: float = 42.0
_DEEPSEEK_WAIT_FOR:      float = 45.0

# iter 326a — FreeLLMAPI (self-hosted proxy that aggregates 11 free
# LLM providers behind one OpenAI-compatible /v1/chat/completions
# endpoint with automatic failover). When the operator points
# FREELLMAPI_BASE_URL at a running proxy, AUREM's ORA chain treats it
# as a SINGLE upstream — but the proxy itself fails over across Google
# Gemini, Groq, Cerebras, SambaNova, Mistral, OpenRouter, GitHub
# Models, Cloudflare, Cohere, Z.ai, NVIDIA. Net effect: ORA can sustain
# ~1B free tokens/month without ever showing "primary brain
# unreachable". Repo: https://github.com/tashfeenahmed/freellmapi
_FREELLMAPI_HTTPX_TIMEOUT: float = 35.0
_FREELLMAPI_WAIT_FOR:      float = 40.0

# iter 326f — Gemini + NVIDIA budgets. Both are OpenAI-compat endpoints
# with very fast TTFB (Gemini Flash ~400-800 ms; NVIDIA NIM ~1-2 s).
# Keep httpx slightly less than asyncio.wait_for so connections close
# cleanly on cancellation (same invariant as DeepSeek/Groq).
_GEMINI_HTTPX_TIMEOUT: float = 18.0
_GEMINI_WAIT_FOR:      float = 20.0
_NVIDIA_HTTPX_TIMEOUT: float = 22.0
_NVIDIA_WAIT_FOR:      float = 25.0

# Iter 322ex — production safety: Legion Ollama runs on the founder's
# laptop via ngrok. When the tunnel is dead, the previous 120s wait made
# ORA "silently scroll forever" before falling through. We honour
# LEGION_OLLAMA_TIMEOUT_S env so prod can set a short value (15s)
# while preview keeps the long value for cold-model loads.
_OLLAMA_WAIT_FOR:     float = float(os.environ.get("LEGION_OLLAMA_TIMEOUT_S", "45"))

# iter 322fk-3 — Legion/Ollama circuit breaker.
# When the user's local Legion daemon / ngrok tunnel is offline, every
# ORA request used to hang on the 120s ollama timeout before falling
# through to Claude. After ONE failure we skip ollama for 60s and route
# straight to the cloud fallback. Reply time after ngrok drop: 120s → 2s.
_OLLAMA_CB_FAIL_THRESHOLD = int(os.environ.get("ORA_OLLAMA_CB_THRESHOLD", "2"))
_OLLAMA_CB_COOLDOWN_S     = float(os.environ.get("ORA_OLLAMA_CB_COOLDOWN_S", "60"))
_ollama_cb_fails  = 0
_ollama_cb_until  = 0.0  # epoch-seconds; ollama skipped until this time


def _ollama_cb_open() -> bool:
    import time as _t
    return _ollama_cb_until > _t.time()


def _ollama_cb_record_failure() -> None:
    global _ollama_cb_fails, _ollama_cb_until
    import time as _t
    _ollama_cb_fails += 1
    if _ollama_cb_fails >= _OLLAMA_CB_FAIL_THRESHOLD:
        _ollama_cb_until = _t.time() + _OLLAMA_CB_COOLDOWN_S
        logger.warning(
            f"[ora-agent] ollama circuit OPEN for {_OLLAMA_CB_COOLDOWN_S:.0f}s "
            f"(fails={_ollama_cb_fails}). Routing to fallback."
        )


def _ollama_cb_record_success() -> None:
    global _ollama_cb_fails, _ollama_cb_until
    if _ollama_cb_fails or _ollama_cb_until:
        logger.info("[ora-agent] ollama circuit CLOSED — success after failure")
    _ollama_cb_fails = 0
    _ollama_cb_until = 0.0


# iter 326k — Gemini suspended-key shield (circuit breaker).
# When Google suspends the GOOGLE_API_KEY (`Consumer ... has been
# suspended`), every chat hit blows 20s on a known-dead provider before
# falling through to NVIDIA. After 2 consecutive 403s we open the
# circuit for 5 minutes (configurable). Reply time after suspension:
# 20s → 1s.
_GEMINI_CB_FAIL_THRESHOLD = int(os.environ.get("ORA_GEMINI_CB_THRESHOLD", "2"))
_GEMINI_CB_COOLDOWN_S     = float(os.environ.get("ORA_GEMINI_CB_COOLDOWN_S", "300"))
_gemini_cb_fails  = 0
_gemini_cb_until  = 0.0


def _gemini_cb_open() -> bool:
    import time as _t
    return _gemini_cb_until > _t.time()


def _gemini_cb_record_failure(reason: str = "") -> None:
    """Increment failure count; open circuit at threshold.

    Only HTTP 403 / 401 (auth-level) failures count toward the breaker
    — transient 5xx or timeouts use the normal retry path.
    """
    global _gemini_cb_fails, _gemini_cb_until
    import time as _t
    _gemini_cb_fails += 1
    if _gemini_cb_fails >= _GEMINI_CB_FAIL_THRESHOLD:
        _gemini_cb_until = _t.time() + _GEMINI_CB_COOLDOWN_S
        logger.warning(
            f"[ora-agent] gemini circuit OPEN for {_GEMINI_CB_COOLDOWN_S:.0f}s "
            f"(fails={_gemini_cb_fails}, reason={reason[:80]!r}). "
            "Routing to NVIDIA fallback."
        )


def _gemini_cb_record_success() -> None:
    global _gemini_cb_fails, _gemini_cb_until
    if _gemini_cb_fails or _gemini_cb_until:
        logger.info("[ora-agent] gemini circuit CLOSED — success after failure")
    _gemini_cb_fails = 0
    _gemini_cb_until = 0.0


# ─────────────────────────────────────────────────────────────────────
# iter 326q — Shared salvage layer for inline tool-call leakage.
#
# Symptom user saw (verbatim from chat with ORA):
#   Founder: "campaign report?"
#   ORA:     `{"type": "function", "name": "campaign_status", "parameters": {}}`
#
# Root cause: small / poorly-fine-tuned models (qwen2.5-coder local,
# sometimes Claude/Gemini when prompted with tool schemas) emit tool
# calls as plain JSON in `content` instead of populating the OpenAI
# `tool_calls` array. The original salvage only ran inside `_call_ollama`,
# so non-Ollama providers leaked the JSON straight to chat. Even within
# Ollama the parser used `startswith("{") and endswith("}")` — a single
# leading word or a Markdown code fence broke it.
#
# This module-level helper is now called AFTER every provider response
# in the agent loop (right before the "no tool_calls → final reply"
# branch). Tolerates:
#   • Markdown code fences  ```json ... ```
#   • Leading "Sure, here you go:" prose
#   • Trailing commentary after the JSON
#   • Three call-shape conventions ({name,parameters} / {tool,args} /
#     {function,arguments})  AND the OpenAI-schema echo shape
#     {"type":"function","name":...,"parameters":{...}}
# ─────────────────────────────────────────────────────────────────────
_INLINE_TOOL_JSON_RE = re.compile(
    # Matches `{` ... `}` where the body contains at least one of the
    # recognised tool-call keys. We allow ONE level of nested `{...}` so
    # the common `"parameters": {}` and `"args": {"path": "/x"}` shapes
    # work. Deeper nesting bails out — but for our recognised shapes that
    # never happens in practice (tool args are flat dicts).
    r"\{(?:[^{}]|\{[^{}]*\})*?(?:\"name\"|\"tool\"|\"function\")(?:[^{}]|\{[^{}]*\})*\}",
    re.DOTALL,
)
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


def _extract_candidate_json(text: str) -> str | None:
    """Pull the first JSON object out of `text`, tolerating fences and
    surrounding prose. Returns the JSON substring or None."""
    if not text:
        return None
    # 1) Markdown code fence?
    m = _CODE_FENCE_RE.search(text)
    if m:
        inner = m.group(1).strip()
        if inner.startswith("{") and inner.endswith("}"):
            return inner
    # 2) Bare object somewhere in the text?
    m = _INLINE_TOOL_JSON_RE.search(text)
    if m:
        return m.group(0)
    # 3) Whole content is a single JSON object?
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    return None


def _salvage_inline_tool_call(msg: dict[str, Any]) -> bool:
    """If `msg["content"]` carries an inline tool-call JSON instead of
    the structured `tool_calls` field, promote it. Returns True if a
    salvage actually happened. The caller can use the return value to
    log salvage rate per provider."""
    if msg.get("tool_calls"):
        return False  # provider gave us proper tool_calls already
    content_raw = msg.get("content") or ""
    candidate = _extract_candidate_json(content_raw)
    if not candidate:
        return False
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return False
    if not isinstance(parsed, dict):
        return False
    # Accept {name,parameters}, {tool,args}, {function,arguments}, AND
    # the OpenAI-schema echo {"type":"function","name":...,"parameters":...}.
    tool_name = (
        parsed.get("name")
        or parsed.get("tool")
        or parsed.get("function")
    )
    tool_args = (
        parsed.get("parameters")
        or parsed.get("args")
        or parsed.get("arguments")
        or {}
    )
    if not (tool_name and isinstance(tool_name, str)):
        return False
    import uuid as _uuid
    msg["tool_calls"] = [{
        "id": f"salvage_{_uuid.uuid4().hex[:8]}",
        "type": "function",
        "function": {
            "name": tool_name,
            "arguments": json.dumps(tool_args, ensure_ascii=False),
        },
    }]
    msg["content"] = ""  # blank content so caller treats as a tool call
    logger.info(f"[ora-agent] SALVAGED inline tool-call: name={tool_name}")
    return True


def _looks_like_unhandled_tool_call(content: str) -> bool:
    """Final safety net — used in the agent loop's `if not tool_calls`
    branch. If the model emitted what looks like a tool-call JSON BUT
    the salvage already tried and failed (malformed JSON, unrecognised
    shape, etc), we MUST NOT deliver that raw JSON to the founder. The
    caller substitutes an honest 'I couldn't fetch — retry' reply."""
    if not content:
        return False
    txt = content.strip()
    # Common leak markers — pick conservatively to avoid muting valid
    # mentions of these strings inside genuine prose.
    needles = (
        '{"type": "function"',
        '{"type":"function"',
        '"name": "campaign_status"',
        '"name": "view_file"',
        '"function":',
        '"tool_calls":',
        '"parameters": {}',
    )
    return any(n in txt for n in needles) and txt.startswith("{") and txt.endswith("}")


# ─────────────────────────────────────────────────────────────────────
# iter 326t — Hallucination Shield v2: ground numeric claims in facts
#
# iter 326q caught LEAKED TOOL CALLS (raw JSON in chat). It did NOT
# catch FABRICATED CONTENT — when ORA invents plausible-looking numbers
# because the tool didn't run. Examples seen in production today:
#   • "Eligible leads: 8, Sent: 5, Streak: 0" — all three numbers fake
#   • "AUREM is on Windows" — fake platform (fixed in iter 326s via
#     RULE ONE pinning, but only for the platform claim)
#
# Approach: ground numeric claims. Walk the conversation history, pull
# every value tools have returned, build a "facts" set. Before
# delivering the final reply, scan it for numbers. Any number that
# doesn't appear in tool output AND doesn't appear in the user's recent
# message is FABRICATED — flag or replace.
#
# Scope: only applies to DOMAIN-FACTUAL replies (campaign / lead /
# customer state). Code-help / conceptual / chitchat replies pass
# through untouched — otherwise we'd false-positive on every reply
# that happens to contain a number.
# ─────────────────────────────────────────────────────────────────────

_DOMAIN_TRIGGER_WORDS = frozenset({
    "campaign", "campaigns", "leads", "lead", "sent", "emails", "email",
    "queue", "queued", "customers", "customer", "tenants", "tenant",
    "blast", "blasts", "subscribers", "subscriber", "revenue", "mrr",
    "stripe", "subscription", "subscriptions", "active", "inactive",
    "deliveries", "delivered", "opens", "clicks", "watchdog", "streak",
    "eligible", "blocked", "vetoed", "uptime", "watchdogs", "scout",
    "scouted",
})

# Numbers that are always safe — list indices, common round figures.
# Without this, every "5 minutes" / "step 1" / "100%" in a reply
# would false-positive.
_SAFE_NUMBERS = frozenset({
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "12", "24", "60", "100", "1000",
})


def _is_domain_factual_reply(reply: str) -> bool:
    """True only if the reply makes claims about campaign/customer
    state that should be grounded. Very short / non-domain replies
    skip grounding entirely."""
    if not reply or len(reply) < 30:
        return False
    lower = reply.lower()
    return any(w in lower for w in _DOMAIN_TRIGGER_WORDS)


def _extract_tool_facts(
    history: list[dict[str, Any]],
) -> tuple[set[str], str]:
    """Walk history, return (set_of_numbers, lowercased_concatenated_blob).

    The numbers set is for exact-match lookups. The blob is the
    substring fallback so we don't miss numbers embedded inside JSON
    like `"sent_count": 254` (where the raw text always carries the
    sequence even if the regex pass misses it under unusual whitespace)."""
    numbers: set[str] = set()
    blob_parts: list[str] = []
    for msg in history:
        if msg.get("role") not in ("tool", "function"):
            continue
        content = msg.get("content") or ""
        if not content:
            continue
        blob_parts.append(content.lower())
        for m in re.finditer(r"-?\d+(?:\.\d+)?", content):
            numbers.add(m.group(0))
    return numbers, " ".join(blob_parts)


def _ground_reply_against_facts(
    reply: str,
    history: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    """Inspect every multi-digit number in the reply. Each one MUST
    appear in either a tool output OR the user's recent message.
    Numbers that don't match are flagged as fabrication.

    Returns (possibly-rewritten reply, stats dict).

    Strategy:
      • 0 unverified   → return reply unchanged
      • 1-2 unverified → SOFT: append a footer noting uncertain numbers
      • 3+ unverified  → HARD: swap reply for an honest "I can't verify"
                          message and let the founder ask again
    """
    stats: dict[str, Any] = {
        "replaced": False, "softened": False, "unverified": [],
    }
    if not _is_domain_factual_reply(reply):
        stats["skipped"] = "non_domain"
        return reply, stats

    fact_numbers, fact_blob = _extract_tool_facts(history)
    # Also accept numbers the user themselves typed in recent turns —
    # if the founder asked "did we get more than 50 leads?" and ORA
    # replies "Yes, 53 leads landed", the "50" must not be flagged.
    user_blob_parts: list[str] = []
    for msg in history[-8:]:
        if msg.get("role") == "user":
            user_blob_parts.append((msg.get("content") or "").lower())
    user_blob = " ".join(user_blob_parts)

    unverified: list[str] = []
    # iter 326t — match TWO patterns to catch single-digit fabrications:
    #   (a) Multi-digit numbers anywhere — high signal-to-noise.
    #   (b) Single-digit numbers ONLY when paired with a domain noun
    #       (e.g. "Eligible leads: 8" / "5 emails sent" / "Sent: 5").
    # Pattern (b) is what catches the founder's actual reported failure
    # — "Eligible leads: 8, Sent: 5, Streak: 0" all single-digit fakes.
    domain_word_pat = "|".join(_DOMAIN_TRIGGER_WORDS)
    patterns = [
        # Multi-digit anywhere
        re.compile(r"\b(\d{2,})\b"),
        # Single-digit BEFORE a domain noun: "8 leads"
        re.compile(
            rf"\b(\d)\b\s+(?:{domain_word_pat})\b", re.IGNORECASE
        ),
        # Single-digit AFTER a domain noun (with optional colon/dash):
        # "Eligible leads: 8" / "Sent — 5" / "Streak: 0"
        re.compile(
            rf"(?:{domain_word_pat})\s*[:\-—]\s*(\d)\b", re.IGNORECASE
        ),
    ]
    seen: set[str] = set()
    for pat in patterns:
        for m in pat.finditer(reply):
            n = m.group(1)
            if n in seen:
                continue
            if n in _SAFE_NUMBERS:
                # Safe numbers still slip through for multi-digit (e.g. "100")
                # but for single-digit + domain-noun matches we want to
                # CHECK them — "0", "1" claimed as a metric IS verifiable
                # and could be fabricated. Only skip if we're sure.
                if len(n) >= 2:
                    continue
            if n in fact_numbers:
                continue
            if n in fact_blob or n in user_blob:
                continue
            unverified.append(n)
            seen.add(n)

    if not unverified:
        return reply, stats

    stats["unverified"] = unverified

    if len(unverified) >= 3:
        stats["replaced"] = True
        stats["reason"] = "too_many_unverified"
        honest = (
            "I drafted a reply with specific numbers, but I can't "
            "confirm they came from a real tool call this turn. Rather "
            "than risk fabricating data, I'm going to stop here. "
            "Please ask the question again — I'll re-run the right "
            "tool and give you verified numbers."
        )
        return honest, stats

    stats["softened"] = True
    footer = (
        "\n\n_(Heads up — I'm not 100% sure about "
        f"{' and '.join(unverified)}. Ask again if you want me to "
        "re-verify with a fresh tool call.)_"
    )
    return reply + footer, stats


# ─────────────────────────────────────────────────────────────────────
# iter 326v — Token Cost Transparency
#
# Founder ask: "Har chat turn ke neeche dikhega: 'This turn: $0.03 |
# Session: $0.18'. Tu andhere mein hai right now."
#
# Approach: estimate cost from character lengths (rough but reliable;
# tokens ≈ chars/4 for English+code). No provider-side changes needed.
# Track per-session totals in a module-level dict so the footer can
# show both this-turn and session-cumulative.
#
# Pricing is per 1M tokens (as of Feb 2026). Numbers are deliberately
# rounded UP — we'd rather over-report cost (founder under-bills) than
# under-report (founder overpays without knowing). Update the table as
# providers re-price.
# ─────────────────────────────────────────────────────────────────────

_PROVIDER_PRICING_USD_PER_M_TOKENS: dict[str, dict[str, float]] = {
    # Provider:        input price,    output price  (USD / 1M tokens)
    "deepseek":      {"input": 0.27,   "output": 1.10},   # via OpenRouter
    "gemini":        {"input": 0.075,  "output": 0.30},   # Gemini 1.5 Flash
    "nvidia":        {"input": 0.0,    "output": 0.0 },   # NIM free tier
    "claude":        {"input": 3.00,   "output": 15.00},  # Sonnet 4.5
    "groq":          {"input": 0.50,   "output": 0.80},   # Mixtral 8x7B
    "ollama":        {"input": 0.0,    "output": 0.0 },   # local
    "legion_ollama": {"input": 0.0,    "output": 0.0 },   # local
    "freellmapi":    {"input": 0.0,    "output": 0.0 },   # community proxy
}

# Per-session running cost. Bounded by NORMAL session length — if a
# pathological session pumps 10k turns the dict grows but each entry is
# tiny (3 floats), so memory ceiling is well under 1MB even at 10k
# active sessions. We do prune empty sessions on demand below.
_SESSION_COST_USD: dict[str, dict[str, float]] = {}


def _estimate_call_cost_usd(
    provider: str, prompt_chars: int, response_chars: int,
) -> float:
    """Estimate one provider call's cost in USD from string lengths.
    tokens ≈ chars / 4 is the standard rule-of-thumb for English+code."""
    pricing = _PROVIDER_PRICING_USD_PER_M_TOKENS.get(provider)
    if not pricing:
        return 0.0
    input_tokens = max(0, prompt_chars) / 4.0
    output_tokens = max(0, response_chars) / 4.0
    cost = (
        (input_tokens * pricing["input"])
        + (output_tokens * pricing["output"])
    ) / 1_000_000.0
    return round(cost, 6)


def _track_session_cost(session_id: str, provider: str, cost_usd: float) -> None:
    """Add a successful call's cost to the running session total AND
    the current-turn total. The agent loop resets turn-cost back to 0
    after each user message (see `reset_turn_cost`).

    iter 326w — also fires a fire-and-forget Mongo insert into the
    `ora_llm_costs` collection so the daily-spend dashboard has data.
    """
    if not session_id:
        return
    bucket = _SESSION_COST_USD.setdefault(
        session_id, {"session_total": 0.0, "turn_total": 0.0}
    )
    bucket["session_total"] += cost_usd
    bucket["turn_total"] += cost_usd
    bucket["last_provider"] = provider  # type: ignore[assignment]
    # iter 326w — persist per-call cost so the daily-spend dashboard
    # has real numbers. Best-effort: a Mongo hiccup must never break
    # the reply path.
    try:
        if _db is not None and cost_usd > 0:
            asyncio.create_task(_persist_llm_cost(session_id, provider, cost_usd))
    except Exception:
        pass


async def _persist_llm_cost(
    session_id: str, provider: str, cost_usd: float,
) -> None:
    """Fire-and-forget cost log for the daily-spend dashboard."""
    if _db is None:
        return
    try:
        await _db.ora_llm_costs.insert_one({
            "session_id": session_id,
            "provider":   provider,
            "cost_usd":   round(cost_usd, 6),
            "ts":         _now(),
            "day":        _now().strftime("%Y-%m-%d"),
        })
    except Exception as e:
        logger.debug(f"[ora-cost] persist skipped: {e}")


def _reset_turn_cost(session_id: str) -> None:
    """Called by the agent loop at the START of each new user turn,
    so turn_total only reflects THIS turn."""
    if not session_id:
        return
    bucket = _SESSION_COST_USD.get(session_id)
    if bucket:
        bucket["turn_total"] = 0.0


def _format_cost_footer(session_id: str) -> str:
    """Return the user-facing transparency line. Empty string if there's
    nothing to show (zero-cost turn, e.g. local Ollama only)."""
    bucket = _SESSION_COST_USD.get(session_id) or {}
    turn = bucket.get("turn_total", 0.0)
    sess = bucket.get("session_total", 0.0)
    if turn <= 0.0 and sess <= 0.0:
        return ""
    # Show only meaningful precision. Microcents of cost are noise.
    def _fmt(v: float) -> str:
        if v < 0.001:
            return "<$0.001"
        return f"${v:.3f}"
    return f"\n\n_(This turn: {_fmt(turn)} · Session: {_fmt(sess)})_"





# ── Tier policy ───────────────────────────────────────────────────────
# RULE: a tool name must appear in EXACTLY ONE tier set.
# tier_of() short-circuits on TIER_1 → TIER_2 → TIER_3 → default tier2.
# Duplicates make the lower tier silently win, which is always wrong.

TIER_1_AUTO: set[str] = {
    # Pure read / observation — execute immediately, no approval needed.
    "view_file", "view_dir", "grep_codebase", "curl_internal",
    "db_count", "db_distinct", "git_log", "health_check",
    "lint_python", "shell_exec", "claim_build_done",
    # FIX #7 — git_bisect is a read-only commit walk; system prompt
    # promises autonomous bug-hunt so it MUST be tier1, not tier2.
    "git_bisect",
    # iter 322fi-rollback — read-only diagnostics for recovery flows.
    # NOTE: ora_rollback_LIST is tier2 (precursor to destructive restore).
    "council_consult",
    # iter 322g — autonomous campaign ops (cost <$0.10, no approval needed)
    "campaign_status", "force_blast_cycle", "channel_gating_reseed",
    # iter 323q — skill-ports (read-only): systematic debug planner +
    # deterministic code-review pass. Both safe to auto-execute.
    "debug_systematic", "review_code",
    # iter 326i — BUILD MODE tools. Auto-tier so ORA can run the
    # proof-table checklist without founder approval per step.
    "run_pytest", "verify_endpoint",
    # iter 326aa / 326bb / 326z — Phase 2 P1 read-only memory + search.
    # Pure observations: no state change, no external network calls,
    # so safe to auto-execute.
    "recall_past_decisions", "search_codebase_semantic",
    "load_job_checkpoint",
}

TIER_2_APPROVE: set[str] = {
    # Mutates state but reversible — inline [Approve]/[Reject] card.
    "safe_edit", "restart_service", "propose_commit", "save_to_github",
    # FIX #1 — ora_rollback_list lives here ONLY (removed from TIER_1_AUTO).
    # Listing available rollbacks is safe to read but it immediately precedes
    # a destructive restore, so the founder should see it before it runs.
    "ora_rollback_list", "ora_rollback_restore",
    "kv_set", "feature_flag_set",
    "create_file", "delete_file",
    # iter 322g — local git checkpoint (push still needs founder click)
    "git_commit_local",
    # iter 326y — Phase 2 P1: real browser tool. External URLs go to
    # tier 2 so they get the 30-second cancel window (iter 326w). Cost
    # is non-trivial (~3s per call) and we never want ORA crawling a
    # site by mistake without founder visibility.
    "browser_get_text", "browser_screenshot",
}

TIER_3_HIGH_RISK: set[str] = {
    # Destructive / external — approval card is red-banded;
    # founder must type CONFIRM to approve.
    "legion_exec", "supervisor_restart_all", "prod_env_set",
    "stripe_charge", "send_bulk_email",
}


def tier_of(name: str) -> str:
    if name in TIER_1_AUTO:
        return "tier1_auto"
    if name in TIER_2_APPROVE:
        return "tier2_approve"
    if name in TIER_3_HIGH_RISK:
        return "tier3_high_risk"
    # Unknown tool → conservative default (ask before running)
    logger.warning(f"[ora-agent] unknown tool '{name}' — defaulting to tier2_approve")
    return "tier2_approve"


# ── Mongo helpers ─────────────────────────────────────────────────────
_db = None


def set_db(database) -> None:
    global _db
    _db = database
    # iter 326aa / 326z — wire the new memory/checkpoint services to
    # the same Mongo handle. Best-effort: failure is non-fatal.
    try:
        from services import ora_decision_memory, job_checkpoints
        ora_decision_memory.set_db(database)
        job_checkpoints.set_db(database)
    except Exception as e:
        logger.warning(f"[ora-agent] decision_memory/checkpoint wire failed: {e}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# iter 326tt — Transient vs deterministic failure distinction.
# When a tool fails because of a network blip / 5xx / timeout / rate
# limit, we do NOT want to count it toward the 2-strike halt ceiling.
# These errors are environmental, not the LLM's fault, and a retry on
# the next iteration usually clears them. Deterministic failures
# (invalid args, path-not-allowed, unknown tool, dissent reject) still
# count fully — the LLM brain must correct them, not retry.
_TRANSIENT_ERROR_SIGNALS = (
    "timeout",
    "timed out",
    "connection refused",
    "connection reset",
    "connection aborted",
    "connection error",
    "temporarily unavailable",
    "service unavailable",
    "gateway timeout",
    "bad gateway",
    "internal server error",
    "serverselectiontimeout",
    "rate limit",
    "rate-limit",
    "too many requests",
    "http 500",
    "http 502",
    "http 503",
    "http 504",
    "http 429",
    "ssl",
    "eof occurred",
    "remote end closed",
    "dns",
    "name or service not known",
)


def _is_transient_failure(result: dict | None) -> bool:
    """True iff the tool result represents a retryable environmental
    failure (network / 5xx / rate-limit). Deterministic failures
    (bad args, path not allowed, unknown tool, dissent reject)
    return False so they still count toward the strike ceiling."""
    if not isinstance(result, dict):
        return False
    err = (result.get("error") or "").lower()
    if not err:
        return False
    return any(sig in err for sig in _TRANSIENT_ERROR_SIGNALS)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if isinstance(dt, datetime) else None


async def _persist_pending(
    *,
    action_id:     str,
    session_id:    str,
    tool:          str,
    args:          dict,
    tier:          str,
    founder_email: str,
    summary:       str,
) -> None:
    if _db is None:
        return
    # iter 326w — Tier 2 actions auto-execute after the 30-second
    # cancel window. Tier 3 stays manual (None) — irreversible work
    # always needs an explicit founder approve.
    auto_exec_at = None
    if tier == "tier2_approve":
        auto_exec_at = _now() + timedelta(seconds=TIER2_AUTO_EXECUTE_SECONDS)
    await _db[PENDING_COLLECTION].insert_one({
        "_id":           action_id,   # always a server-generated uuid4 (FIX #5)
        "session_id":    session_id,
        "tool":          tool,
        "args":          args,
        "tier":          tier,
        "founder_email": founder_email,
        "summary":       summary,
        "status":        "pending",
        "created_at":    _now(),
        "expires_at":    _now() + timedelta(minutes=EXPIRY_MINUTES),
        "auto_execute_at": auto_exec_at,
        "decided_at":    None,
        "decided_by":    None,
        "result":        None,
    })


async def _expire_old() -> int:
    if _db is None:
        return 0
    res = await _db[PENDING_COLLECTION].update_many(
        {"status": "pending", "expires_at": {"$lt": _now()}},
        {"$set": {
            "status":     "expired",
            "decided_at": _now(),
            "decided_by": "system:auto_expire",
        }},
    )
    return res.modified_count


async def _summarize_for_human(tool: str, args: dict) -> str:
    """Compact one-liner of what a tool would do — shown on the approval card."""
    a = args or {}
    if tool == "safe_edit":
        return f"Edit {a.get('path','?')} (replace block, ~{len(str(a.get('new_str',''))):,} chars)"
    if tool == "restart_service":
        return f"Restart {a.get('service','backend')} via supervisorctl"
    if tool == "save_to_github":
        return f"Commit & push to GitHub ({a.get('message','no msg')[:60]})"
    if tool == "propose_commit":
        return f"Stage commit: {a.get('message','no msg')[:80]}"
    if tool == "ora_rollback_restore":
        return f"Restore backup: {a.get('backup_name','?')}"
    if tool == "ora_rollback_list":
        return "List available rollback snapshots (read-only)"
    if tool == "legion_exec":
        cmd  = (a.get("cmd") or "")[:120]
        risk = a.get("risk_hint") or "auto"
        return f"Run on Legion laptop [{risk}]: {cmd}"
    if tool == "create_file":
        return f"Create {a.get('path','?')} ({len(str(a.get('content',''))):,} bytes)"
    if tool == "delete_file":
        return f"DELETE file {a.get('path','?')}"
    # Generic fallback
    return f"{tool}({json.dumps(a, default=str)[:140]})"


# ── Tool-schema generation ────────────────────────────────────────────
def _tool_schemas_for_tier(*tiers: str) -> list[dict[str, Any]]:
    """Generate Groq/OpenAI function-call schemas for tools in the given tiers."""
    allowed: set[str] = set()
    for t in tiers:
        if t == "tier1_auto":
            allowed |= TIER_1_AUTO
        elif t == "tier2_approve":
            allowed |= TIER_2_APPROVE
        elif t == "tier3_high_risk":
            allowed |= TIER_3_HIGH_RISK

    out: list[dict[str, Any]] = []
    for name in sorted(allowed):
        meta = TOOL_REGISTRY.get(name) or {}
        params_props: dict[str, Any] = {}
        for arg_name, arg_desc in (meta.get("args_spec") or {}).items():
            params_props[arg_name] = {
                "type":        "string",
                "description": str(arg_desc)[:240],
            }
        out.append({
            "type": "function",
            "function": {
                "name":        name,
                "description": (meta.get("description") or name)[:480],
                "parameters":  {
                    "type":       "object",
                    "properties": params_props,
                },
            },
        })
    return out


def all_agent_tool_schemas() -> list[dict[str, Any]]:
    return _tool_schemas_for_tier("tier1_auto", "tier2_approve", "tier3_high_risk")


# iter 322g — lean schema for local Ollama (qwen2.5:7b freezes on 30+ tools)
LEAN_OLLAMA_TOOLS: list[str] = [
    "campaign_status", "force_blast_cycle", "channel_gating_reseed",
    "git_commit_local", "git_bisect", "view_file", "grep_codebase",
    "shell_exec", "curl_internal", "claim_build_done", "ora_rollback_list",
]


def lean_ollama_tool_schemas() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name in LEAN_OLLAMA_TOOLS:
        meta = TOOL_REGISTRY.get(name) or {}
        params_props: dict[str, Any] = {}
        for arg_name, arg_desc in (meta.get("args_spec") or {}).items():
            params_props[arg_name] = {
                "type":        "string",
                "description": str(arg_desc)[:180],
            }
        out.append({
            "type": "function",
            "function": {
                "name":        name,
                "description": (meta.get("description") or name)[:300],
                "parameters":  {"type": "object", "properties": params_props},
            },
        })
    return out


# ── LLM provider chain ────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────
# iter 326u — Cost-Aware Brain Routing.
#
# Before this change the chain order was a STATIC sequence
# (`deepseek,gemini,nvidia,claude,groq`). Every request — from "hi" to
# "rewrite the campaign engine" — burned the same providers in the
# same order. The founder's "campaign report?" question above used
# Claude for synthesis even though DeepSeek/Gemini would have nailed
# it in 200ms at 1/10th the cost.
#
# This module classifies each request into one of three complexity
# tiers and picks a DIFFERENT chain order per tier:
#
#   SIMPLE   — single-word / question / status check / yes/no:
#               • Gemini Flash first (cheapest, fastest)
#               • DeepSeek second   (cheap, strong reasoning)
#               • NVIDIA third      (free, reliable)
#               • Claude only as last-ditch
#   MEDIUM   — explanation, multi-line answer, single-file edit:
#               • DeepSeek first    (best reasoning per dollar)
#               • Gemini second
#               • Claude third
#   COMPLEX  — multi-file refactor, planning, debug a bug from scratch:
#               • Claude first      (top reasoning matters here)
#               • DeepSeek second
#               • NVIDIA / Gemini   (fallbacks)
#
# Classification is a CHEAP keyword + length heuristic. Doing it with
# another LLM would defeat the cost-saving purpose. The heuristic is
# intentionally conservative — when in doubt, classify UP (MEDIUM) so
# we don't underprovision a hard question.
#
# Env override: ORA_AGENT_DISABLE_ROUTING=1 → always uses the legacy
# static chain. Useful for A/B testing the savings.
# ─────────────────────────────────────────────────────────────────────

# Words that signal a deep code task — bumps complexity to COMPLEX.
_COMPLEX_TASK_WORDS = frozenset({
    "refactor", "rewrite", "implement", "build", "architect", "design",
    "debug", "investigate", "trace", "diagnose", "audit", "migration",
    "migrate", "fix.+bug", "root.+cause", "deep.+dive",
})

# Words that signal a quick lookup / status check / chat → SIMPLE.
_SIMPLE_INTENT_WORDS = frozenset({
    "status", "health", "ok", "okay", "hi", "hello", "hey",
    "thanks", "thank", "yes", "no", "got", "good", "great",
    "report", "show", "list", "check", "ping", "test",
})


def _classify_complexity(messages: list[dict[str, Any]]) -> str:
    """Return one of: 'simple', 'medium', 'complex'.
    Heuristic only — no LLM call (that would defeat the cost saving).

    Looks at the LAST user message (the actual question this turn).
    Earlier messages are context for the LLM, not signal for routing.
    """
    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = (m.get("content") or "").strip()
            break
    if not last_user:
        return "medium"

    txt = last_user.lower()
    tokens = re.findall(r"\b\w+\b", txt)
    token_count = len(tokens)

    # Heuristic 1 — anything with deep-code-task words is COMPLEX.
    for word in _COMPLEX_TASK_WORDS:
        if "." in word:  # regex pattern
            if re.search(word, txt):
                return "complex"
        elif word in tokens:
            return "complex"

    # Heuristic 2 — very long messages (>120 tokens) usually mean
    # complex tasks. Founders don't write essays for "campaign status?".
    if token_count > 120:
        return "complex"

    # Heuristic 3 — very short (<= 8 tokens) AND contains a SIMPLE
    # intent word OR is a question → SIMPLE.
    if token_count <= 8:
        ends_question = txt.endswith("?")
        has_simple_word = any(w in tokens for w in _SIMPLE_INTENT_WORDS)
        if ends_question or has_simple_word:
            return "simple"
        # short but no clear intent → medium (don't underprovision)

    # Heuristic 4 — 9-30 tokens with a simple intent word → SIMPLE.
    if token_count <= 30 and any(w in tokens for w in _SIMPLE_INTENT_WORDS):
        return "simple"

    return "medium"


def _chain_order_for(complexity: str) -> list[str]:
    """Pick a provider chain order based on the classified complexity.

    NOTE: Circuit breakers (ollama_cb, gemini_cb) still apply to whichever
    chain we pick — a dead provider gets skipped silently regardless of
    its priority on paper."""
    # Override hook for emergencies / A-B testing.
    if os.environ.get("ORA_AGENT_DISABLE_ROUTING") == "1":
        return ["deepseek", "gemini", "nvidia", "claude", "groq"]

    if complexity == "simple":
        # Cheapest first. Claude is sidelined to last-ditch.
        return ["gemini", "deepseek", "nvidia", "groq", "claude"]
    if complexity == "complex":
        # Claude's reasoning is worth its dollar on hard tasks.
        return ["claude", "deepseek", "gemini", "nvidia", "groq"]
    # medium (default) — keep the original chain order so the change
    # is a strict superset: SIMPLE / COMPLEX paths get cheaper / smarter,
    # MEDIUM stays identical for safety.
    return ["deepseek", "gemini", "nvidia", "claude", "groq"]


async def _llm_turn(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
) -> dict[str, Any] | None:
    """One turn against the LLM provider chain.

    Provider order (overridable via ORA_AGENT_PROVIDER_ORDER env):
        1. deepseek      — DeepSeek V3.1 via OpenRouter (current primary)
        2. legion_ollama — sovereign, local qwen2.5 via Legion daemon
        3. groq          — cloud, fast, daily TPD limit
        4. claude        — plain-text fallback (no tools this turn)

    Returns OpenAI-format message dict (may have tool_calls), or None if
    every provider failed.
    """
    # iter 326u — Cost-aware routing. Classify the request's complexity
    # and pick a chain order that puts the right brain first. If the
    # operator set ORA_AGENT_PROVIDER_ORDER explicitly we respect that
    # (it's a hard override). Otherwise we let the classifier decide.
    _routing_override = os.environ.get("ORA_AGENT_PROVIDER_ORDER")
    if _routing_override:
        order = [p.strip() for p in _routing_override.lower().split(",") if p.strip()]
        _complexity = "override"
    else:
        _complexity = _classify_complexity(messages)
        order = _chain_order_for(_complexity)

    logger.info(
        f"[ora-agent] LLM routing → complexity={_complexity} "
        f"chain={','.join(order)}"
    )

    for provider in order:
        # iter 322fk-3 — skip ollama while the circuit breaker is open.
        if provider in ("legion_ollama", "ollama", "legion") and _ollama_cb_open():
            logger.info("[ora-agent] ollama CB open — skipping legion_ollama")
            continue
        try:
            if provider in ("legion_ollama", "ollama", "legion"):
                msg = await asyncio.wait_for(
                    _ollama_with_tools(messages), timeout=_OLLAMA_WAIT_FOR
                )
                if msg is None:
                    _ollama_cb_record_failure()
                else:
                    _ollama_cb_record_success()
            elif provider in ("deepseek", "openrouter", "deepseek_v3"):
                # iter 325z — DeepSeek is primary; one retry on the FIRST
                # cold-start timeout so the chain doesn't immediately fall
                # to Claude (which is slower) when the only issue was a
                # 30-40s OpenRouter Novita route warm-up. Second attempt
                # almost always succeeds in <8s because the socket is now
                # warm. If both fail, we still fall through normally.
                msg = None
                for attempt in (1, 2):
                    try:
                        msg = await asyncio.wait_for(
                            _deepseek_with_tools(messages, model=model),
                            timeout=_DEEPSEEK_WAIT_FOR,
                        )
                        if msg is not None:
                            break
                    except asyncio.TimeoutError:
                        if attempt == 1:
                            logger.warning(
                                "[ora-agent] deepseek attempt 1 timed out — "
                                "retrying once (cold-start)"
                            )
                            continue
                        raise
            elif provider == "groq":
                msg = await asyncio.wait_for(
                    _groq_with_tools(messages, model=model), timeout=_GROQ_WAIT_FOR
                )
            elif provider == "freellmapi":
                # iter 326a — self-hosted OpenAI-compat proxy (FreeLLMAPI).
                # When FREELLMAPI_BASE_URL isn't configured the helper
                # returns None and we fall through with no logged error.
                msg = await asyncio.wait_for(
                    _freellmapi_with_tools(messages, model=model),
                    timeout=_FREELLMAPI_WAIT_FOR,
                )
            elif provider == "gemini":
                # iter 326f — Google Gemini via OpenAI-compat endpoint.
                # iter 326k — Skip if suspended-key circuit is open.
                if _gemini_cb_open():
                    continue  # silently fall through to next provider
                try:
                    msg = await asyncio.wait_for(
                        _gemini_with_tools(messages, model=model),
                        timeout=_GEMINI_WAIT_FOR,
                    )
                except Exception as _gex:
                    _err_str = str(_gex)
                    if "403" in _err_str or "401" in _err_str or "suspended" in _err_str.lower():
                        _gemini_cb_record_failure(_err_str)
                    raise
            elif provider == "nvidia":
                # iter 326f — NVIDIA NIM via OpenAI-compat endpoint.
                msg = await asyncio.wait_for(
                    _nvidia_with_tools(messages, model=model),
                    timeout=_NVIDIA_WAIT_FOR,
                )
            elif provider == "claude":
                msg = await asyncio.wait_for(
                    _claude_text_fallback(messages), timeout=_CLAUDE_WAIT_FOR
                )
            else:
                logger.warning(f"[ora-agent] unknown provider '{provider}' — skipping")
                continue

            if msg is not None:
                logger.info(f"[ora-agent] provider={provider} served reply")
                # iter 326v — Token Cost Transparency. Attach the
                # winning provider AND a rough char count for cost
                # estimation to the msg. The agent loop reads these
                # after each tool-call round to update session totals.
                try:
                    _prompt_chars = sum(
                        len((m.get("content") or "")) for m in messages
                    )
                    _resp_chars = len(msg.get("content") or "")
                    # Approximate tool-call payload weight too.
                    for tc in (msg.get("tool_calls") or []):
                        fn = (tc or {}).get("function") or {}
                        _resp_chars += len(str(fn.get("arguments") or ""))
                    msg["__ora_provider__"] = provider
                    msg["__ora_prompt_chars__"] = _prompt_chars
                    msg["__ora_resp_chars__"] = _resp_chars
                except Exception:
                    pass  # cost tracking must never break a working reply
                return msg

        except asyncio.TimeoutError:
            logger.warning(f"[ora-agent] provider={provider} hard-timeout — skipping")
            if provider in ("legion_ollama", "ollama", "legion"):
                _ollama_cb_record_failure()
        except Exception as e:
            logger.warning(
                f"[ora-agent] provider={provider} crashed: "
                f"{type(e).__name__}: {e}"
            )
            if provider in ("legion_ollama", "ollama", "legion"):
                _ollama_cb_record_failure()

    return None


async def _deepseek_with_tools(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
) -> dict[str, Any] | None:
    """DeepSeek V3.1 via OpenRouter — current primary chat provider.

    iter 325j — ORA chat was still routing to Legion Ollama (offline)
    and falling through to a hardcoded "fix your laptop" message even
    though the founder switched to DeepSeek. This wires DeepSeek into
    the same OpenAI-style tool-call chain Groq/Claude already use, so
    the chat agent gets the same brain the ORA CTO repair agent uses.

    Returns None on missing key / non-200 / network — caller falls
    through to the next provider.
    """
    api_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        return None

    model_name = (
        model
        or os.environ.get("DEEPSEEK_MODEL")
        or "deepseek/deepseek-chat-v3.1"
    )

    try:
        async with httpx.AsyncClient(timeout=_DEEPSEEK_HTTPX_TIMEOUT) as c:
            r = await c.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  "https://aurem.live",
                    "X-Title":       "AUREM ORA Agent",
                },
                json={
                    "model":       model_name,
                    "messages":    messages,
                    "tools":       all_agent_tool_schemas(),
                    "tool_choice": "auto",
                    "temperature": 0.25,
                    "max_tokens":  1500,
                },
            )
            if r.status_code == 200:
                data = r.json()
                return (data.get("choices") or [{}])[0].get("message") or {}
            logger.warning(
                f"[ora-agent] deepseek {r.status_code}: {r.text[:240]}"
            )
    except Exception as e:
        logger.warning(f"[ora-agent] deepseek error: {type(e).__name__}: {e}")

    return None


async def _freellmapi_with_tools(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
) -> dict[str, Any] | None:
    """FreeLLMAPI — self-hosted OpenAI-compatible proxy that aggregates
    free-tier keys from ~11 LLM providers (Google Gemini, Groq, Cerebras,
    SambaNova, Mistral, OpenRouter, GitHub Models, Cloudflare, Cohere,
    Z.ai, NVIDIA) behind a single endpoint with automatic failover.

    Repo: https://github.com/tashfeenahmed/freellmapi

    Configuration (env):
      FREELLMAPI_BASE_URL  — e.g. http://127.0.0.1:3001/v1
      FREELLMAPI_API_KEY   — the unified `freellmapi-…` bearer token
      FREELLMAPI_MODEL     — optional model pin (default "auto" → proxy
                             picks best healthy upstream)

    Returns None on missing config / non-200 / network — caller falls
    through to the next provider in the ORA chain.
    """
    base = (os.environ.get("FREELLMAPI_BASE_URL") or "").strip().rstrip("/")
    key  = (os.environ.get("FREELLMAPI_API_KEY")  or "").strip()
    if not base or not key:
        return None
    model_name = model or os.environ.get("FREELLMAPI_MODEL") or "auto"
    try:
        async with httpx.AsyncClient(timeout=_FREELLMAPI_HTTPX_TIMEOUT) as c:
            r = await c.post(
                f"{base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":       model_name,
                    "messages":    messages,
                    "tools":       all_agent_tool_schemas(),
                    "tool_choice": "auto",
                    "temperature": 0.25,
                    "max_tokens":  1500,
                },
            )
            if r.status_code == 200:
                data = r.json()
                served_by = r.headers.get("x-routed-via") or "unknown"
                logger.info(f"[ora-agent] freellmapi served via {served_by}")
                return (data.get("choices") or [{}])[0].get("message") or {}
            logger.warning(f"[ora-agent] freellmapi {r.status_code}: {r.text[:240]}")
    except Exception as e:
        logger.warning(f"[ora-agent] freellmapi error: {type(e).__name__}: {e}")
    return None


async def freellmapi_health() -> dict[str, Any]:
    """iter 326a — FreeLLMAPI watchdog probe used by the ORA-CTO health
    panel and the pillars-map drill-down. Hits the proxy's GET /v1/models
    (OpenAI-compat) which is cheap and tells us:
      • is the proxy reachable?
      • how many models are currently routable?
      • what's the routing latency?

    Never raises. Returns {ok, configured, status, models_total,
    latency_ms, reason}.
    """
    base = (os.environ.get("FREELLMAPI_BASE_URL") or "").strip().rstrip("/")
    key  = (os.environ.get("FREELLMAPI_API_KEY")  or "").strip()
    if not base:
        return {"ok": False, "configured": False,
                "reason": "FREELLMAPI_BASE_URL not set"}
    started = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(
                f"{base}/models",
                headers={"Authorization": f"Bearer {key}"} if key else {},
            )
        elapsed_ms = int((asyncio.get_event_loop().time() - started) * 1000)
        if r.status_code != 200:
            return {
                "ok": False, "configured": True, "status": r.status_code,
                "latency_ms": elapsed_ms,
                "reason": f"HTTP {r.status_code}: {r.text[:120]}",
            }
        body   = r.json()
        models = body.get("data") if isinstance(body, dict) else []
        return {
            "ok": True, "configured": True, "status": 200,
            "models_total": len(models or []),
            "latency_ms":   elapsed_ms,
            "reason":       f"{len(models or [])} models routable",
        }
    except Exception as e:
        return {
            "ok": False, "configured": True,
            "reason": f"{type(e).__name__}: {str(e)[:140]}",
        }


async def warm_freellmapi() -> bool:
    """iter 326a — fire-and-forget warmup so the proxy's first real call
    isn't paying a cold socket. Mirrors warm_deepseek pattern. No-op if
    FREELLMAPI_BASE_URL isn't configured."""
    base = (os.environ.get("FREELLMAPI_BASE_URL") or "").strip().rstrip("/")
    key  = (os.environ.get("FREELLMAPI_API_KEY")  or "").strip()
    if not base or not key:
        return False
    warmup_model = (
        os.environ.get("FREELLMAPI_MODEL") or "auto"
    )
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type":  "application/json"},
                json={"model":       warmup_model,
                      "messages":    [{"role": "user", "content": "ping"}],
                      "max_tokens":  4,
                      "temperature": 0},
            )
            ok = r.status_code == 200
            logger.info(
                f"[ora-agent] FreeLLMAPI warmup → {r.status_code}"
                f"{' ✓ ready' if ok else ' (cold)'}"
            )
            return ok
    except Exception as e:
        logger.warning(f"[ora-agent] FreeLLMAPI warmup failed: {type(e).__name__}: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────
# iter 326f — Native Gemini + NVIDIA providers.
#
# We have GOOGLE_API_KEY + NVIDIA_NIM_API_KEY already in the AUREM env
# (verified 2026-05-21). Wiring them directly into the ORA chain gives
# us multi-provider failover WITHOUT the FreeLLMAPI proxy / VPS overhead.
# Both providers expose OpenAI-compatible `/v1/chat/completions` endpoints
# so the request shape (and tool-calling format) is identical to DeepSeek.
# Pattern intentionally mirrors `_freellmapi_with_tools` for consistency.
# ──────────────────────────────────────────────────────────────────────

async def _gemini_with_tools(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
) -> dict[str, Any] | None:
    """Google Gemini via the OpenAI-compatible endpoint at
    `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`.

    Free tier is the most generous of all free providers:
      Gemini 2.5 Flash  →  ~15 RPM · 1M tokens/min · 1500 req/day

    Configuration:
      GOOGLE_API_KEY  — Google AI Studio key (already set in AUREM env)
      GEMINI_MODEL    — optional override (default: gemini-2.5-flash)

    Returns None when key missing or on any non-200 — caller falls
    through to next provider in the chain.
    """
    key = (os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not key:
        return None
    model_name = model or os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
    try:
        async with httpx.AsyncClient(timeout=_GEMINI_HTTPX_TIMEOUT) as c:
            r = await c.post(
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":       model_name,
                    "messages":    messages,
                    "tools":       all_agent_tool_schemas(),
                    "tool_choice": "auto",
                    "temperature": 0.25,
                    "max_tokens":  1500,
                },
            )
            if r.status_code == 200:
                data = r.json()
                logger.info(f"[ora-agent] gemini served by {model_name}")
                _gemini_cb_record_success()
                return (data.get("choices") or [{}])[0].get("message") or {}
            # iter 326k — auth-level failures (suspended key / quota) feed
            # the suspended-key circuit breaker so subsequent calls skip
            # gemini immediately for cooldown window.
            if r.status_code in (401, 403):
                _gemini_cb_record_failure(f"HTTP {r.status_code}: {r.text[:120]}")
                # iter 326pp — silent-failure alert: Gemini key suspended
                # or quota burnt mid-autonomous-loop. Dedup is per provider.
                try:
                    from services.silent_failure_alerts import alert_autonomous_401
                    alert_autonomous_401(
                        context="ora_agent.gemini_call",
                        status_code=r.status_code,
                        detail=r.text[:300],
                        provider="gemini",
                    )
                except Exception:
                    pass
            logger.warning(f"[ora-agent] gemini {r.status_code}: {r.text[:240]}")
    except Exception as e:
        logger.warning(f"[ora-agent] gemini error: {type(e).__name__}: {e}")
    return None


async def warm_gemini() -> bool:
    """iter 326f — startup ping. No-op if GOOGLE_API_KEY missing."""
    key = (os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not key:
        return False
    model_name = os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
    try:
        async with httpx.AsyncClient(timeout=12.0) as c:
            r = await c.post(
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type":  "application/json"},
                json={"model":       model_name,
                      "messages":    [{"role": "user", "content": "ping"}],
                      "max_tokens":  4,
                      "temperature": 0},
            )
            ok = r.status_code == 200
            logger.info(
                f"[ora-agent] Gemini warmup → {r.status_code}"
                f"{' ✓ ready' if ok else ' (cold)'}"
            )
            return ok
    except Exception as e:
        logger.warning(f"[ora-agent] Gemini warmup failed: {type(e).__name__}: {e}")
        return False


async def gemini_health() -> dict[str, Any]:
    """iter 326f — watchdog probe used by /api/admin/ora/providers/health."""
    key = (os.environ.get("GOOGLE_API_KEY") or "").strip()
    if not key:
        return {"ok": False, "configured": False, "reason": "GOOGLE_API_KEY missing"}
    started = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(
                "https://generativelanguage.googleapis.com/v1beta/openai/models",
                headers={"Authorization": f"Bearer {key}"},
            )
        elapsed_ms = int((asyncio.get_event_loop().time() - started) * 1000)
        if r.status_code != 200:
            # iter 326g — surface Google's structured error so suspended
            # keys / quota-blocked keys show the actual reason on the
            # ORA-CTO health panel instead of an opaque "HTTP 403".
            reason = f"HTTP {r.status_code}"
            try:
                body = r.json()
                msg  = (
                    (body.get("error") or {}).get("message")
                    if isinstance(body, dict)
                    else (body[0].get("error") or {}).get("message")
                    if isinstance(body, list) and body
                    else None
                )
                if msg:
                    reason = f"HTTP {r.status_code}: {str(msg)[:160]}"
            except Exception:
                pass
            return {"ok": False, "configured": True, "status": r.status_code,
                    "latency_ms": elapsed_ms,
                    "reason": reason}
        models = (r.json().get("data") or [])
        return {"ok": True, "configured": True, "status": 200,
                "models_total": len(models), "latency_ms": elapsed_ms,
                "reason": f"{len(models)} models routable"}
    except Exception as e:
        return {"ok": False, "configured": True,
                "reason": f"{type(e).__name__}: {str(e)[:120]}"}


async def _nvidia_with_tools(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
) -> dict[str, Any] | None:
    """NVIDIA NIM via the OpenAI-compatible endpoint at
    `https://integrate.api.nvidia.com/v1/chat/completions`.

    Free tier: 1000 requests/day per model. Models include
    `meta/llama-4-maverick-17b-128e-instruct`, `qwen/qwen3-235b-a22b`, etc.

    Configuration:
      NVIDIA_NIM_API_KEY — already set in AUREM env
      NVIDIA_MODEL       — optional (default: meta/llama-4-maverick-17b-128e-instruct)
    """
    key = (os.environ.get("NVIDIA_NIM_API_KEY") or "").strip()
    if not key:
        return None
    model_name = (
        model
        or os.environ.get("NVIDIA_MODEL")
        or "meta/llama-4-maverick-17b-128e-instruct"
    )
    try:
        async with httpx.AsyncClient(timeout=_NVIDIA_HTTPX_TIMEOUT) as c:
            r = await c.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":       model_name,
                    "messages":    messages,
                    "tools":       all_agent_tool_schemas(),
                    "tool_choice": "auto",
                    "temperature": 0.25,
                    "max_tokens":  1500,
                },
            )
            if r.status_code == 200:
                data = r.json()
                logger.info(f"[ora-agent] nvidia served by {model_name}")
                return (data.get("choices") or [{}])[0].get("message") or {}
            logger.warning(f"[ora-agent] nvidia {r.status_code}: {r.text[:240]}")
    except Exception as e:
        logger.warning(f"[ora-agent] nvidia error: {type(e).__name__}: {e}")
    return None


async def warm_nvidia() -> bool:
    key = (os.environ.get("NVIDIA_NIM_API_KEY") or "").strip()
    if not key:
        return False
    model_name = (
        os.environ.get("NVIDIA_MODEL")
        or "meta/llama-4-maverick-17b-128e-instruct"
    )
    try:
        async with httpx.AsyncClient(timeout=12.0) as c:
            r = await c.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type":  "application/json"},
                json={"model":       model_name,
                      "messages":    [{"role": "user", "content": "ping"}],
                      "max_tokens":  4,
                      "temperature": 0},
            )
            ok = r.status_code == 200
            logger.info(
                f"[ora-agent] NVIDIA warmup → {r.status_code}"
                f"{' ✓ ready' if ok else ' (cold)'}"
            )
            return ok
    except Exception as e:
        logger.warning(f"[ora-agent] NVIDIA warmup failed: {type(e).__name__}: {e}")
        return False


async def nvidia_health() -> dict[str, Any]:
    key = (os.environ.get("NVIDIA_NIM_API_KEY") or "").strip()
    if not key:
        return {"ok": False, "configured": False, "reason": "NVIDIA_NIM_API_KEY missing"}
    started = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(
                "https://integrate.api.nvidia.com/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
        elapsed_ms = int((asyncio.get_event_loop().time() - started) * 1000)
        if r.status_code != 200:
            return {"ok": False, "configured": True, "status": r.status_code,
                    "latency_ms": elapsed_ms,
                    "reason": f"HTTP {r.status_code}"}
        models = (r.json().get("data") or [])
        return {"ok": True, "configured": True, "status": 200,
                "models_total": len(models), "latency_ms": elapsed_ms,
                "reason": f"{len(models)} models routable"}
    except Exception as e:
        return {"ok": False, "configured": True,
                "reason": f"{type(e).__name__}: {str(e)[:120]}"}




async def warm_deepseek() -> bool:
    """iter 325z — one-shot warmup ping at startup so the founder's first
    ORA-CTO query doesn't pay the OpenRouter Novita cold-start tax
    (~30s on first hit per pod). Sends a tiny tool-less ping with
    `max_tokens=4` so it returns in <2 s once the route is warm.

    Returns True on success, False otherwise. Failures are logged but
    never raised — warmup is best-effort, not boot-blocking.
    """
    api_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        return False
    model_name = (
        os.environ.get("DEEPSEEK_MODEL") or "deepseek/deepseek-chat-v3.1"
    )
    try:
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  "https://aurem.live",
                    "X-Title":       "AUREM ORA Warmup",
                },
                json={
                    "model":       model_name,
                    "messages":    [{"role": "user", "content": "ping"}],
                    "max_tokens":  4,
                    "temperature": 0,
                },
            )
            ok = r.status_code == 200
            logger.info(
                f"[ora-agent] DeepSeek warmup → {r.status_code}"
                f"{' ✓ ready' if ok else ' (cold)'}"
            )
            return ok
    except Exception as e:
        logger.warning(f"[ora-agent] DeepSeek warmup failed: {type(e).__name__}: {e}")
        return False


async def _groq_with_tools(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
) -> dict[str, Any] | None:
    """Groq function-calling. Returns None on rate-limit / network / no key.

    FIX #10 — httpx timeout (_GROQ_HTTPX_TIMEOUT = 18s) is intentionally
    set LESS than the asyncio.wait_for timeout (_GROQ_WAIT_FOR = 20s) so
    the httpx client cleanly closes its connection before asyncio cancels
    the coroutine. The old code had httpx=30s > asyncio=20s, meaning the
    httpx timeout never fired and connections leaked on every cancellation.
    """
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    model_name = model or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

    try:
        async with httpx.AsyncClient(timeout=_GROQ_HTTPX_TIMEOUT) as c:
            r = await c.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":       model_name,
                    "messages":    messages,
                    "tools":       all_agent_tool_schemas(),
                    "tool_choice": "auto",
                    "temperature": 0.25,
                    "max_tokens":  1000,
                },
            )
            if r.status_code == 200:
                data = r.json()
                return (data.get("choices") or [{}])[0].get("message") or {}
            logger.warning(f"[ora-agent] groq {r.status_code}: {r.text[:240]}")
    except Exception as e:
        logger.warning(f"[ora-agent] groq error: {type(e).__name__}: {e}")

    return None


async def _ollama_with_tools(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Local Ollama (qwen2.5:7b by default) via Legion daemon.

    Uses Ollama's native /api/chat (NOT OpenAI compat) so we can pass
    keep_alive=60m — model stays in GPU RAM between chats.

    iter 322g — fast-fail when daemon is offline; avoids 120s dead wait.
    """
    # ── Daemon liveness gate ──────────────────────────────────────────
    if _db is not None:
        try:
            now_ts = time.time()
            status = await _db.legion_daemon_status.find_one(
                {"_id": "global"}, {"_id": 0, "last_poll_ts": 1}
            )
            last_ts = float((status or {}).get("last_poll_ts") or 0)
            age     = now_ts - last_ts if last_ts else 999.0

            if age > 120:
                # Heartbeat stale — check for in-flight job before giving up
                cutoff    = (
                    _now() - timedelta(seconds=300)
                ).isoformat()
                in_flight = await _db.legion_queue.count_documents({
                    "status":      {"$in": ["claimed", "running", "ack_pending"]},
                    "enqueued_at": {"$gte": cutoff},
                })
                if in_flight == 0:
                    logger.info(
                        f"[ora-agent] ollama skipped: daemon offline "
                        f"(last_poll {age:.0f}s ago, no in-flight jobs)"
                    )
                    return None
                logger.info(
                    f"[ora-agent] ollama: daemon stale poll {age:.0f}s "
                    f"but {in_flight} in-flight job(s) — proceeding"
                )
        except Exception as e:
            logger.debug(f"[ora-agent] ollama liveness check skipped: {e}")
    # ─────────────────────────────────────────────────────────────────

    try:
        from services.legion_tool import legion_exec
    except Exception:
        return None

    import shlex

    model     = os.environ.get("LEGION_OLLAMA_MODEL", "qwen2.5:7b")
    # iter 323aa+ — multi-URL fallback chain. Daemon may run on Windows
    # native (where 127.0.0.1 hits Ollama directly) OR inside WSL (where
    # 127.0.0.1 is the WSL network namespace and Ollama lives on Windows
    # host, reachable via host.docker.internal). The shell `||` chain
    # tries each URL in order — first reachable wins. Operator can
    # override the entire chain via LEGION_OLLAMA_DAEMON_URLS (csv).
    url_chain = os.environ.get(
        "LEGION_OLLAMA_DAEMON_URLS",
        "http://127.0.0.1:11434,http://host.docker.internal:11434",
    )
    urls = [u.strip().rstrip("/") for u in url_chain.split(",") if u.strip()]
    if not urls:
        urls = ["http://127.0.0.1:11434"]
    timeout_s = int(os.environ.get("LEGION_OLLAMA_TIMEOUT_S", "45"))

    payload: dict[str, Any] = {
        "model":      model,
        "messages":   messages,
        "tools":      lean_ollama_tool_schemas(),
        "stream":     False,
        "keep_alive": "60m",
        "options":    {"temperature": 0.25, "num_predict": 500},
    }
    body = json.dumps(payload, ensure_ascii=False)
    body_q = shlex.quote(body)
    # Build a chained curl command — succeed on first reachable URL.
    # Each curl uses -fsS so 4xx/5xx fall through to the next URL.
    parts = []
    for u in urls:
        parts.append(
            f"curl -fsS --max-time {timeout_s} "
            f"-H 'Content-Type: application/json' "
            f"-d {body_q} "
            f"{u}/api/chat"
        )
    cmd = " || ".join(parts)
    result = await legion_exec(
        cmd=cmd, cwd="/tmp",
        timeout_s=timeout_s + 10,
        risk_hint="low",
        wait_max_s=int(os.environ.get("ORA_AGENT_OLLAMA_WAIT_S", "200")),
    )

    if not result.get("ok") or result.get("exit_code") != 0:
        logger.warning(
            f"[ora-agent] ollama miss: ok={result.get('ok')} "
            f"exit={result.get('exit_code')} "
            f"err={result.get('error')!r} "
            f"stderr={(result.get('stderr','') or '')[:160]}"
        )
        return None

    stdout = (result.get("stdout") or "").strip()
    if not stdout:
        logger.warning("[ora-agent] ollama empty stdout")
        return None

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        logger.warning(f"[ora-agent] ollama non-JSON: {e} body={stdout[:300]}")
        return None

    # Ollama native /api/chat returns {message: {...}} directly,
    # NOT OpenAI's {choices:[{message:{...}}]} shape.
    msg = data.get("message") or {}
    if not msg and data.get("choices"):
        # Defensive: Ollama compat layer hit instead of native
        msg = (data["choices"][0] or {}).get("message") or {}

    if not msg:
        logger.warning(
            f"[ora-agent] ollama no msg: keys={list(data.keys())[:8]} "
            f"body={stdout[:200]}"
        )
        return None

    # iter 323ab + iter 326q — Salvage inline tool-call leakage (shared
    # path now — see _salvage_inline_tool_call defined below). Local
    # models AND occasionally Claude/Gemini emit tool calls as plain JSON
    # inside `content` instead of populating `tool_calls`. The shared
    # salvage handles code fences, leading/trailing text, and the 3 most
    # common JSON shapes ({name,parameters}, {tool,args}, {function,arguments}).
    _salvage_inline_tool_call(msg)

    logger.info(
        f"[ora-agent] ollama OK: model={data.get('model')} "
        f"eval_count={data.get('eval_count')} "
        f"total_duration_ms={int((data.get('total_duration') or 0) / 1e6)} "
        f"elapsed={result.get('elapsed_ms')}ms "
        f"content_len={len(msg.get('content') or '')} "
        f"tool_calls={len(msg.get('tool_calls') or [])}"
    )
    return msg


async def _claude_text_fallback(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Plain-text Claude call — no tools. Used when Groq/Ollama unavailable.

    FIX #12 — model string made env-configurable; the hardcoded
    "claude-sonnet-4-5-20250929" was not a valid Anthropic model ID and
    caused silent 404s, making the fallback useless.
    """
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception:
        return None

    # Flatten message history → system + user prompt
    sys_lines:   list[str] = []
    convo_lines: list[str] = []

    for m in messages:
        role    = m.get("role", "")
        content = m.get("content") or ""
        if role == "system":
            sys_lines.append(content)
        elif role == "user":
            convo_lines.append(f"User: {content}")
        elif role == "assistant":
            if content:
                convo_lines.append(f"ORA: {content}")
        elif role == "tool":
            convo_lines.append(
                f"(tool {m.get('name','?')} result: {(content or '')[:600]})"
            )

    sys_msg = "\n\n".join(sys_lines)[:5000] + (
        "\n\n[Note: Tool calls are temporarily unavailable in this reply. "
        "Answer the founder honestly using what you already know — "
        "if you need to verify something, say so explicitly.]"
    )
    user_msg = "\n".join(convo_lines[-12:]) + "\nORA:"

    # FIX #12 — env-configurable model string
    model_id = os.environ.get("CLAUDE_FALLBACK_MODEL", "claude-sonnet-4-5")

    try:
        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=f"ora-agent-fb-{os.urandom(4).hex()}",
            system_message=sys_msg,
        ).with_model("anthropic", model_id)

        text = (
            await chat.send_message(UserMessage(text=user_msg[:6000]))
        ).strip()

        if not text:
            return None
        return {"role": "assistant", "content": text}

    except Exception as e:
        logger.warning(
            f"[ora-agent] claude fallback failed: {type(e).__name__}: {e}"
        )
        return None


# ── Session history persistence ───────────────────────────────────────
async def _load_history(session_id: str) -> list[dict[str, Any]]:
    if _db is None:
        return []
    doc = await _db[HISTORY_COLLECTION].find_one(
        {"_id": session_id}, {"messages": 1, "_id": 0}
    )
    return (doc or {}).get("messages") or []


async def _save_history(session_id: str, messages: list[dict[str, Any]]) -> None:
    """Persist conversation history with a cap on non-system messages.

    FIX #3 — Old code: messages[-40:] which silently dropped the system
    prompt (always at index 0) once the conversation exceeded 40 turns.
    ORA would then load on the next turn with zero instructions: no tier
    rules, no operating principles, no anti-hallucination law.

    New code: system messages are always pinned at the front. The rolling
    cap applies only to non-system turns.
    """
    if _db is None:
        return

    sys_msgs = [m for m in messages if m.get("role") == "system"]
    rest     = [m for m in messages if m.get("role") != "system"]
    cap      = max(1, HISTORY_CAP - len(sys_msgs))
    to_save  = sys_msgs + rest[-cap:]

    await _db[HISTORY_COLLECTION].update_one(
        {"_id": session_id},
        {
            "$set": {
                "messages":   to_save,
                "updated_at": _now(),
            },
            "$setOnInsert": {"created_at": _now()},
        },
        upsert=True,
    )


# ── System prompt ─────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are ORA — AUREM's autonomous CTO and orchestrator.

═══════════════════════════════════════════════════════════════════════════
RULE ONE — RUNTIME TRUTH (NEVER GUESS THE PLATFORM, NEVER INVENT IT)
═══════════════════════════════════════════════════════════════════════════
You are running INSIDE the AUREM backend. The runtime environment is
non-negotiable knowledge — never guess, never qualify, never ask the
founder to confirm what platform AUREM runs on. The truth:

  OS:           Linux (Ubuntu / Debian-based Docker containers)
  Runtime:      Python 3.11, Node.js 20, FastAPI, React (CRA)
  Container:    Docker, orchestrated by Kubernetes on Emergent's cluster
  Process mgr:  supervisord (services: backend, frontend, mongodb, redis, ...)
  Shell tools:  bash, grep, sed, awk, find, curl, ls, cat — ALL available
  DB:           MongoDB (preview: local mongod / production: Atlas)
  AUREM is NOT on Windows. AUREM is NOT on macOS. The founder's LAPTOP
  may be Windows or Mac, but that is irrelevant — your tools run on the
  Linux backend, not on the founder's device.

If a tool you call (grep_codebase, shell_exec, view_file, run_pytest…)
returns an error, the error is about your TOOL CALL or your TARGET, not
about the platform. NEVER reply "this is a Linux tool, your system is
Windows" — that statement is FALSE about AUREM and embarrasses both you
and the founder. When a tool fails:
  1. Read the actual stderr.
  2. Quote the actual error.
  3. Propose the smallest fix to your tool args.
  4. Never blame the OS — the OS is Linux, period.

═══════════════════════════════════════════════════════════════════════════
RULE ZERO — FOUNDER VOICE (HIGHEST PRIORITY, OVERRIDES ALL OTHER STYLE RULES)
═══════════════════════════════════════════════════════════════════════════
The founder is a NON-TECHNICAL VIBECODER. You must speak to them like a
friendly co-founder, not like a developer.

LANGUAGE
  • Plain English ONLY. No Hindi, no Hinglish, no Punjabi — even if the
    founder mixes languages in their question, YOU reply in plain English.
  • Short, calm sentences. No walls of text. Aim for 5-15 lines per reply
    unless the founder asks for detail.
  • Translate ALL technical terms into everyday words:
       MongoDB / database  →  "the customer list" / "your records"
       endpoint / route    →  "the page" / "this feature"
       API / 200 / 502     →  "working" / "broken"
       deploy / push       →  "publish to your live site"
       schema / collection →  "the list of customers" / "the orders"
       env var             →  "a setting on your live site"
       webhook             →  "the notification from Stripe/Twilio/etc"
       cron / scheduler    →  "the auto-runner"
       connection pool     →  "doors to the database"
       circuit breaker     →  "the safety switch"
       commit / git        →  "save"
       repo                →  "your project"
       lint / pytest       →  "automated checks"
       null / None         →  "missing"
       JSON / payload      →  "the data"
       backend / frontend  →  "the engine" / "the screen the user sees"

NEVER USE THESE WITHOUT TRANSLATION
  Stack traces, file paths (/app/backend/...), tool names (safe_edit,
  curl_internal, run_pytest), Docker, Kubernetes, supervisord, ulimit,
  asyncio, FastAPI, React, motor, pymongo, regex, SHA, commit hashes,
  HTTP status codes, "tier 1/2/3", "T3 outage", "watchdog tripped".
  If a technical term is genuinely necessary, follow it with a plain
  English explanation in brackets. Example: "the API key (your password
  for that service)".

REPLY SHAPE
  When you do work for the founder, ALWAYS reply in this two-part shape:

  ─── 1. WHAT I DID (plain English, 3-8 lines) ─────────
  Tell them in everyday language:
    • What was wrong (one sentence — describe the symptom they saw)
    • What you fixed (one sentence — no jargon)
    • What's working now (one sentence)
    • What they need to do next (if anything)

  ─── 2. PROOF (only if technical proof is needed) ──────
  A small table or 3 short bullet points showing the test results.
  Hide the file paths and tool names. Show pass/fail in plain words:
  "Login: working ✓"  "Auto-emails: 254 sent in last 7 hrs ✓"

THINGS TO ALWAYS DO
  • If the founder seems stressed, anxious, or expresses despair — STOP
    the technical reply. Acknowledge them as a human FIRST. Offer mental
    health resources (iCall 9152987821, Vandrevala 1860-2662-345). Then
    handle the technical issue. Code can wait. They cannot.
  • Confirm what they want before destructive actions ("Want me to also
    delete the old records, or just leave them?")
  • When something is broken, tell them WHY it happened in everyday
    language ("your live site has the wrong database address saved")
    not in cause-effect engineering language.

THINGS TO NEVER DO
  • Never paste raw error messages, stack traces, or log dumps unless
    they explicitly ask for them.
  • Never say "PROOF TABLE", "PROOF ROW", "iter 326m", "AutoReconnect",
    "TooManyFilesOpen", or other internal codewords to the founder.
  • Never assume they know what GitHub, Docker, supervisord, npm, or any
    framework name means.
  • Never say "trivially easy" or "this is simple" — what's simple to a
    senior engineer is invisible to a vibecoder.

═══════════════════════════════════════════════════════════════════════════
INTERNAL OPERATING RULES (apply silently — do NOT explain them to founder)
═══════════════════════════════════════════════════════════════════════════

You have direct access to 30+ tools that let you read code, write code, run
shell commands, restart services, query MongoDB, hit our backend, rollback
files, push to GitHub, and even execute commands on the founder's Legion
laptop via the reverse-poll daemon. The founder runs ONE chat interface and
expects YOU to drive the work — no manual tool-picking, no copy-pasting.

Three risk tiers govern tool execution:
  • TIER 1 (auto) — view_file, grep, curl, db reads, lint, shell_exec, claim_build_done,
    git_bisect, campaign_status, force_blast_cycle, channel_gating_reseed,
    recall_past_decisions, search_codebase_semantic, load_job_checkpoint.
    These execute IMMEDIATELY when you call them — no approval needed.
  • TIER 2 (approve) — safe_edit, restart_service, propose_commit, save_to_github,
    create_file, delete_file, ora_rollback_list, rollback, git_commit_local,
    browser_get_text, browser_screenshot.
    These pause for the founder to tap [Approve] in the chat UI (or auto-execute
    after a 30-second cancel window for tier 2 — see iter 326w).
  • TIER 3 (high risk) — legion_exec, supervisor_restart_all, prod env edits,
    stripe_charge, send_bulk_email. These ALSO pause for approval, marked red.

Operating principles:
  1. PLAN FIRST. Before any non-trivial task, write a 3-7 line plan in
     plain English (per Rule Zero), then call the first tool.
  2. VERIFY EVERYTHING. NEVER claim a file exists, an endpoint works, or a
     build is done without calling claim_build_done, view_file, curl_internal,
     or shell_exec ls. Anti-hallucination law — ASCII success boxes without
     a verifying tool call are a firing offense.
  3. STEP BY STEP. Don't batch 10 destructive operations in one turn. Run
     one, verify, then queue the next.
  4. EXPLAIN. When you queue a tier 2/3 action, in your message tell the
     founder in plain English what it does and why it's needed.
  5. RECOVER. If a tool fails, you'll receive a RECOVERY_DIRECTIVE. Read its
     recovery_options + hard_rules and pick exactly one path: retry with
     better args (max 1 retry), call council_consult, call ora_rollback_list,
     or explain_and_stop. NEVER blindly retry the same arguments.
  6. HONEST. If you can't do something, say so in plain English. If a
     service is down say "The Groq AI provider is over its limit, try in
     10 minutes" — do NOT make up answers.
  7. AUTONOMOUS CAMPAIGN OPS. Self-drive fixes without asking when:
       • Founder asks "how is campaign?" → call campaign_status FIRST.
       • zero_sent_streak >= 3 → channel_gating_reseed then force_blast_cycle.
       • veto_rate_1h >= 0.9 → channel_gating_reseed only.
     After any meaningful autofix call git_commit_local. Tell the founder
     in plain English what got triggered, e.g. "Auto-emails were stuck so
     I reset the safety filters and pushed a fresh batch — 12 sent."
  8. NO TOKEN WASTE. Running on local Ollama (qwen2.5:7b). Keep replies tight.
  9. BUG-HUNT WITH git_bisect. When "X used to work, now broken" — DO NOT
     guess. Pick a known-good commit and call git_bisect with a deterministic
     test command. It walks O(log n) commits and returns the exact culprit.
  10. SYSTEMATIC DEBUG. Before proposing ANY fix for a reported bug, walk
      these six steps in order: (1) what is the user actually seeing vs
      expected, (2) minimal reproduction case, (3) list top 3 root causes
      ranked by likelihood, (4) which tool call confirms or rules out each,
      run them, (5) state the confirmed cause with the evidence, (6) only
      now propose the minimal change. No assumptions without evidence.
      When you reply to the founder, hide steps 1-5 and just give them the
      answer from step 6 in plain English.
  11. STOP SLOP PROSE. Write like a sharp human, not an LLM. Banned:
      throat-clearing openers ("Great question!", "Certainly!"), em-dashes
      as dramatic pauses, hedge stacks ("It's worth noting that"), vague
      declaratives, business jargon (synergize, paradigm shift), filler
      affirmations on their own line. Be direct. Be specific. Cut every
      sentence that says nothing.

  12. CANADIAN SMB CONTEXT. AUREM's target market:
      • Geography: Greater Toronto Area — Mississauga, Brampton, Toronto,
        Scarborough, North York, Vaughan, Markham, Oakville, Etobicoke.
        Canadian-specific signals matter: postal codes (L4/L5/M1-M9/L6/L7),
        area codes 416/647/437/905/289/365, .ca domains preferred.
      • Business types AUREM serves: salons, barbershops, restaurants &
        cafes, general contractors, HVAC, plumbing, electrical, dental &
        physio clinics, retail boutiques, auto repair, daycare, fitness
        studios, cleaning services, photographers — independent &
        single-location SMBs, NOT franchises or chains.
      • Owner profile: often first-or-second-generation immigrant
        entrepreneur, time-poor, skeptical of cold outreach because of
        WhatsApp/Telegram scam floods. Owner-facing copy AUREM sends out
        should be plain English. (THIS does NOT change Rule Zero — YOU
        always reply to the founder in plain English regardless.)

  13. LEAD QUALIFICATION RULES. When evaluating a scraped lead or campaign
      row, classify it BEFORE recommending outreach:
      REAL SMB signals: specific business name, real email on own domain
      or owner Gmail, Canadian phone, single physical address, .ca/.com
      website on own domain.
      NOISE: listicle names ("The Best 10…"), platform email domains
      (yelp/facebook/google/wix/squarespace/yellowpages), social URLs as
      website, big-box chains. If unsure, lean toward NOISE.

  14. OUTREACH TONE. Canadian SMB voice: friendly + direct, no corporate
      jargon, value-prop in first sentence, personalize with ONE real
      detail, always offer easy reply path (WhatsApp/calendar/STOP).

  15. AUREM PLATFORM KNOWLEDGE. ORA is AUREM's autonomous AI agent for
      SMB lead generation, qualification, and outbound. Mission: find
      real Canadian SMBs → qualify → multi-channel outreach (email +
      WhatsApp + voice) → book appointments → hand off warm leads to the
      founder. Pricing: $97-$499 CAD/mo. When the founder asks about the
      campaign, START with campaign_status, then read `_eligible_leads()`
      funnel results before suggesting fixes. Never propose a fix without
      funnel evidence. Translate all of this to plain English in replies.

  16. BUILD MODE. When the founder says "build X" / "add Y" / "wire Z" /
      "create endpoint W" — follow this checklist STRICTLY:

      Step 1 — PLAN.  Write 3-7 lines in PLAIN ENGLISH (per Rule Zero)
                      describing: what to add, where, what test will
                      prove it works, expected behaviour. Then call the
                      first tool.

      Step 2 — WIRE.  Use `create_file` (new file) or `safe_edit` (edit).
                      Both are tier-2; the founder will tap [Approve].

      Step 3 — TEST.  After wire approval lands, call `run_pytest` against
                      the test file you created/updated. Required PASS
                      criterion: `passed >= 1` AND `failed == 0`.

      Step 4 — VERIFY. Call `verify_endpoint` against the new route.
                      Required PASS: `matched_status: true`.
                      For DB-only changes (no new HTTP route) skip this
                      step and use `db_count` instead as the proof row.

      Step 5 — REPLY. Emit a "WHAT I DID" plain-English summary FIRST
                      (per Rule Zero reply shape). THEN, only if the
                      founder explicitly asks for proof or it's a
                      tier-2/3 action, append a small proof table.

      If ANY proof row is missing or red — say so explicitly in plain
      English ("the test failed, here's why"). Banned: ASCII success
      boxes without real tool output. Banned: "looks good!" / "should
      be working" — only literal tool output counts.
"""


# ── Helpers ───────────────────────────────────────────────────────────
def _serialise_tool_call(call: dict[str, Any]) -> dict[str, Any]:
    fn      = call.get("function") or {}
    raw_args = fn.get("arguments") or "{}"
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except Exception:
        args = {}
    return {
        "id":   call.get("id") or f"call_{uuid4().hex[:8]}",
        "name": fn.get("name") or "unknown",
        "args": args,
    }


def _format_tool_result(name: str, result: Any) -> str:
    if not isinstance(result, dict):
        return json.dumps({"raw": str(result)[:1200]})
    safe = dict(result)
    for key in ("content", "stdout", "stderr", "output", "body"):
        v = safe.get(key)
        if isinstance(v, str) and len(v) > 1800:
            safe[key] = v[:1800] + f"\n…[truncated {len(v) - 1800}]"
    return json.dumps(safe, default=str)[:4000]


def _recovery_directive(tool: str, result: dict, attempt: int) -> dict[str, Any]:
    """Structured recovery nudge injected as a system message after tool failure.

    FIX #9 — Old code used role:"tool" with a synthetic tool_call_id that
    never appeared in any assistant message. This violates the OpenAI message
    format contract and causes 400 errors on Groq (which validates the chain).
    role:"system" is always valid at any position in the message list and is
    treated as an injected instruction by all LLM providers.
    """
    err  = (result or {}).get("error") or result.get("detail") or "unspecified error"
    body = {
        "RECOVERY_DIRECTIVE":              True,
        "failed_tool":                     tool,
        "consecutive_fails":               attempt,
        "fail_excerpt":                    str(err)[:300],
        "remaining_attempts_before_halt":  max(0, 2 - attempt),
        "recovery_options": [
            "retry_once_with_better_args — Only if you know the EXACT arg that was wrong. "
            "Do NOT retry the same args verbatim.",
            "call_council_consult        — Get a second opinion for risky/architectural calls.",
            "call_ora_rollback_list      — See what backups exist before destructive moves; "
            "restore via tier-2 ora_rollback_restore.",
            "explain_and_stop            — If fix needs founder input (missing creds, "
            "business decision), produce a final message and stop calling tools.",
        ],
        "hard_rules": [
            "If the failed tool is tier 2/3, DO NOT silently retry. "
            "Either explain_and_stop or propose ora_rollback_restore.",
            "Do NOT fabricate success. The previous turn FAILED — say so.",
        ],
    }
    return {
        "role":    "system",
        "content": f"[RECOVERY DIRECTIVE]\n{json.dumps(body, default=str)[:2200]}",
    }


# ── Fast-reply intent classifier ──────────────────────────────────────
# iter 322g — skip Ollama for obvious greetings / status questions.
# qwen2.5:7b on CPU takes 30s+; this keeps 80% of chats sub-2s.

_GREETING_RE = re.compile(
    r"^\s*(hi|hii+|hello+|hey+|namaste|namaskar|salam|good\s+(morning|evening|afternoon|night)|"
    r"ok\.?|okay\.?|cool\.?|nice\.?|wow|gm|gn|tq|thanks?|thank\s+you|thx|"
    r"yo|sup|haan|han|ji|haan?ji|theek\s+hai|tk|tkk|hmm+|hmmmm+|good)"
    r"(\s+(bhai|ji|sir|boss|yaar|man|dear))?"
    r"[\s!.,?]*$",
    re.IGNORECASE,
)
_CAMPAIGN_STATUS_RE = re.compile(
    r"(campaign|blast)\s*(status|kya|ka haal|update|chal raha|chl rha|kaisa)",
    re.IGNORECASE,
)


async def _maybe_fast_reply(text: str) -> str | None:
    t = (text or "").strip()
    if not t or len(t) > 80:
        return None

    if _GREETING_RE.match(t):
        return (
            "Namaste! 🟢 ORA online — sovereign Ollama running, "
            "campaign autopilot ON, watchdog active. Kya kaam karna hai?"
        )

    if _CAMPAIGN_STATUS_RE.search(t):
        try:
            res       = await invoke_tool("campaign_status", {})
            eng       = res.get("engine", {})
            wd        = res.get("watchdog", {})
            tripped   = wd.get("tripped") or []
            health    = "🟢 GREEN" if not tripped else f"🟡 {','.join(tripped)}"
            recent    = res.get("recent_autonomous_actions", [])[:3]
            recent_str = "\n".join(
                f"  • {a.get('ts','')[:16]}  {a.get('playbook')}  "
                f"{a.get('summary','')[:60]}"
                for a in recent
            )
            return (
                f"**Campaign Status — {health}**\n\n"
                f"• Engine: enabled={eng.get('enabled')}  "
                f"last_sent={eng.get('last_run_sent')}  "
                f"last_processed={eng.get('last_run_processed')}\n"
                f"• Watchdog: zero_sent_streak={wd.get('zero_sent_streak')}  "
                f"veto_rate_1h={wd.get('veto_rate_1h')}\n"
                f"• Outreach events today: {res.get('outreach_events_today')}\n\n"
                f"**Last 3 autonomous actions:**\n{recent_str or '  (none yet)'}"
            )
        except Exception as e:
            logger.warning(f"[ora-agent] fast-path campaign_status failed: {e}")
            return None  # fall through to full LLM loop

    return None


# ── Public entry points ───────────────────────────────────────────────
async def run_turn(
    session_id:    str,
    user_text:     str,
    *,
    founder_email: str,
    progress_cb:   Any = None,
    tenant_id:     str | None = None,
) -> dict[str, Any]:
    """Process one user message. Returns either:
      • {ok: True, reply: "...", history_len: N, done: True}
      • {ok: True, action_required: {action_id, tool, args, tier, summary, ...}}

    iter 323l — `progress_cb` is an optional async callable
    `(tool_name: str) -> None` invoked right before each tool dispatch so
    the async job-runner can surface live tool progress to the UI.

    iter 326ff — `tenant_id` (optional) lets us tune ORA's voice
    (tone/formality/signature) per tenant. The voice preamble is
    prepended to SYSTEM_PROMPT on the first turn of a new session.
    """
    await _expire_old()
    history = await _load_history(session_id)

    if not history:
        # iter 326ff — prepend tenant voice preamble so this session
        # adopts the right register from turn 1.
        voice_pre = ""
        try:
            from services.ora_voice_profile import build_voice_preamble
            voice_pre = await build_voice_preamble(tenant_id)
        except Exception as _e:
            logger.debug(f"[ora-agent] voice preamble skipped: {_e}")
        history = [{"role": "system", "content": voice_pre + SYSTEM_PROMPT}]
    history.append({"role": "user", "content": user_text})

    # iter 326v — reset this-turn cost so the footer reports only the
    # cost incurred BY this user message (the session_total keeps
    # accumulating across turns).
    _reset_turn_cost(session_id)

    # Intent fast-path — bypass Ollama for greetings / status queries
    fast_reply = await _maybe_fast_reply(user_text)
    if fast_reply is not None:
        history.append({"role": "assistant", "content": fast_reply})
        await _save_history(session_id, history)
        return {
            "ok":          True,
            "reply":       fast_reply,
            "done":        True,
            "history_len": len(history),
            "fast_path":   True,
        }

    return await _continue_loop(session_id, history, founder_email, progress_cb=progress_cb)


async def resume_after_decision(
    session_id:    str,
    *,
    action_id:     str,
    approved:      bool,
    note:          str,
    founder_email: str,
) -> dict[str, Any]:
    """User clicked Approve or Reject on a pending action card.

    FIX #8 — _expire_old() called here too, not just in run_turn().
             Without this, expired actions were approvable indefinitely
             if the founder went directly to /approve without a new chat.

    FIX #2 — TOCTOU race fixed with find_one_and_update atomic gate.
             Old code: find_one → check status → invoke_tool → update_one.
             Two concurrent approve clicks both passed the status check
             and both executed invoke_tool. For destructive tools this was
             catastrophic. New code: the status transitions "pending" →
             "executing" atomically. The second concurrent request finds no
             document matching {_id, status:"pending"} and returns an error.
    """
    if _db is None:
        return {"ok": False, "error": "DB not wired"}

    # FIX #8 — expire stale actions before checking
    await _expire_old()

    new_status = "executing" if approved else "rejected"

    # FIX #2 — atomic status gate
    row = await _db[PENDING_COLLECTION].find_one_and_update(
        {"_id": action_id, "status": "pending"},
        {"$set": {
            "status":     new_status,
            "decided_at": _now(),
            "decided_by": founder_email,
        }},
        return_document=True,
    )

    if not row:
        # iter 326rr — surface a structured error_code so the UI can
        # render distinct, friendlier messaging per cause without
        # parsing the English string.
        return {
            "ok":         False,
            "error":      "action not found, already processed, or expired",
            "error_code": "expired_or_missing",
        }

    # Session ownership check
    if row["session_id"] != session_id:
        # Undo — wrong session attempted to claim this action
        await _db[PENDING_COLLECTION].update_one(
            {"_id": action_id},
            {"$set": {"status": "pending"}},
        )
        return {"ok": False, "error": "session mismatch",
                "error_code": "session_mismatch"}

    # Founder email ownership check — prevents cross-user approval
    stored_email = row.get("founder_email")
    if stored_email and stored_email != founder_email:
        await _db[PENDING_COLLECTION].update_one(
            {"_id": action_id},
            {"$set": {"status": "pending"}},
        )
        return {"ok": False, "error": "not authorized to approve this action",
                "error_code": "not_authorized"}

    history = await _load_history(session_id)

    if approved:
        result = await invoke_tool(
            row["tool"], row["args"] or {}, actor=f"approved:{founder_email}"
        )
        tool_succeeded = isinstance(result, dict) and result.get("ok", True)
        final_status   = "done" if tool_succeeded else "failed"

        await _db[PENDING_COLLECTION].update_one(
            {"_id": action_id},
            {"$set": {"status": final_status, "result": result}},
        )
        # iter 326aa — log this approved decision into ORA's memory so
        # future "have we done this before?" queries can find it.
        try:
            from services.ora_decision_memory import log_decision
            outcome = "auto_executed" if founder_email.startswith(
                "system:auto_execute") else "approved"
            asyncio.create_task(log_decision(
                session_id=session_id,
                founder_email=founder_email,
                tool=row["tool"],
                summary=row.get("summary") or row["tool"],
                args=row.get("args"),
                outcome=outcome if tool_succeeded else f"{outcome}_failed",
            ))
        except Exception as _e:
            logger.debug(f"[decision-memory] log skipped: {_e}")
        history.append({
            "role":         "tool",
            "tool_call_id": action_id,
            "name":         row["tool"],
            "content":      _format_tool_result(row["tool"], result),
        })
        # Inject recovery directive if the approved tool failed
        if isinstance(result, dict) and result.get("ok") is False:
            history.append(_recovery_directive(row["tool"], result, attempt=1))
    else:
        await _db[PENDING_COLLECTION].update_one(
            {"_id": action_id},
            {"$set": {"rejection_note": (note or "")[:400]}},
        )
        # iter 326aa — log rejections too so ORA learns from no's.
        try:
            from services.ora_decision_memory import log_decision
            asyncio.create_task(log_decision(
                session_id=session_id,
                founder_email=founder_email,
                tool=row["tool"],
                summary=(note or row.get("summary") or row["tool"])[:500],
                args=row.get("args"),
                outcome="rejected",
            ))
        except Exception as _e:
            logger.debug(f"[decision-memory] log skipped: {_e}")
        history.append({
            "role":         "tool",
            "tool_call_id": action_id,
            "name":         row["tool"],
            "content": json.dumps({
                "ok":       False,
                "rejected": True,
                "reason":   note or "founder rejected",
                "guidance": "Do not retry this exact action. "
                            "Propose an alternative or stop.",
            }),
        })

    return await _continue_loop(session_id, history, founder_email)


async def _continue_loop(
    session_id:    str,
    history:       list[dict[str, Any]],
    founder_email: str,
    progress_cb:   Any = None,
) -> dict[str, Any]:
    """Inner agentic loop.

    Runs tier-1 tools automatically. Pauses on tier 2/3 by writing a
    pending action document and returning action_required to the caller.

    FIX #4 — Only tool_calls[0] stored in history (matches what we execute).
              Old code stored the full list, leaving N-1 unanswered tool
              requests that confused the LLM on every subsequent turn.
    FIX #5 — action_id is always a server-generated uuid4().
              Old code used call["id"] from the LLM as MongoDB _id.
    FIX #6 — Wall-clock cap (ORA_MAX_LOOP_S env, default 150s).
              Old code had only an iteration counter; 8 iters × 120s Ollama
              timeout = 20-minute worst-case hang with no escape hatch.
    """
    iterations: int       = 0
    fail_counts: dict     = {}                    # tool_name → consecutive fails
    transient_counts: dict = {}                    # iter 326tt — separate bucket for retryable env failures
    loop_start:  float    = time.monotonic()      # FIX #6

    while iterations < MAX_TOOL_ITERATIONS:

        # FIX #6 — wall-clock guard, checked at the top of every iteration
        elapsed = time.monotonic() - loop_start
        if elapsed > MAX_LOOP_WALL_SECONDS:
            wall_msg = (
                f"Wall-clock budget reached ({int(elapsed)}s / "
                f"{MAX_LOOP_WALL_SECONDS}s). "
                "Ruk gayi taaki HTTP request hang na ho. "
                "Agle message mein continue."
            )
            history.append({"role": "assistant", "content": wall_msg})
            await _save_history(session_id, history)
            return {
                "ok":          True,
                "reply":       wall_msg,
                "iterations":  iterations,
                "done":        True,
                "halted_for":  "wall_clock",
            }

        iterations += 1
        msg = await _llm_turn(history)

        # iter 326v — Token Cost Transparency. If _llm_turn attached
        # provider + char counts to the msg, accumulate the cost on
        # the session bucket. Wrapped in try/except so a cost-tracking
        # bug can NEVER break the reply path.
        try:
            _winning_provider = (msg or {}).get("__ora_provider__")
            if _winning_provider:
                _call_cost = _estimate_call_cost_usd(
                    _winning_provider,
                    (msg or {}).get("__ora_prompt_chars__", 0),
                    (msg or {}).get("__ora_resp_chars__", 0),
                )
                _track_session_cost(session_id, _winning_provider, _call_cost)
        except Exception as _e:
            logger.debug(f"[ora-agent] cost tracking skipped: {_e}")

        if msg is None:
            await _save_history(session_id, history)
            # Graceful degrade — surface campaign health from DB even when
            # Ollama / Groq / Claude are all unreachable.
            diag_lines:     list[str] = []
            campaign_lines: list[str] = []
            try:
                if _db is not None:
                    now_ts = time.time()
                    status = await _db.legion_daemon_status.find_one(
                        {"_id": "global"},
                        {"_id": 0, "last_poll_ts": 1},
                    )
                    last_ts = float((status or {}).get("last_poll_ts") or 0)
                    age     = now_ts - last_ts if last_ts else None

                    if age is None:
                        diag_lines.append(
                            "⚪ Legion daemon: never polled — "
                            "ignore (DeepSeek is primary now)"
                        )
                    elif age < 60:
                        diag_lines.append(
                            f"🟢 Legion daemon alive ({int(age)}s ago) — "
                            "still available as sovereignty fallback"
                        )
                    elif age < 300:
                        diag_lines.append(
                            f"🟡 Legion daemon busy ({int(age)}s since last poll)"
                        )
                    else:
                        diag_lines.append(
                            f"⚪ Legion daemon offline ({int(age/60)} min) — "
                            "doesn't matter, DeepSeek + Claude carry chat"
                        )

                    # Campaign heartbeat
                    cfg = await _db.auto_blast_config.find_one(
                        {"tenant_id": "global"}, {"_id": 0}
                    ) or {}
                    last_run       = cfg.get("last_run_at", "never")
                    last_sent      = cfg.get("last_run_sent", 0)
                    last_processed = cfg.get("last_run_processed", 0)
                    enabled        = cfg.get("enabled", False)

                    since    = (_now() - timedelta(hours=24)).isoformat()
                    sent_24h = await _db.outreach_history.count_documents(
                        {"sent_at": {"$gte": since}}
                    )
                    queued = await _db.campaign_leads.count_documents({
                        "last_blast_at": {"$exists": False},
                        "status": {
                            "$nin": ["signed_up", "not_interested", "unsubscribed"]
                        },
                    })
                    health  = await _db.ora_campaign_health.find_one(
                        {"_id": "global"}, {"_id": 0}
                    ) or {}
                    tripped = health.get("tripped") or []
                    streak  = int(health.get("zero_sent_streak") or 0)

                    health_emoji = (
                        "🟢" if (enabled and sent_24h > 0 and not tripped)
                        else "🟡" if enabled
                        else "🔴"
                    )
                    campaign_lines = [
                        f"{health_emoji} **Campaign Engine: "
                        f"{'ON' if enabled else 'OFF'}** "
                        "(runs on cloud pod 24/7 — laptop independent)",
                        f"  • Sent in last 24h: **{sent_24h}** emails/SMS",
                        f"  • Last cycle: sent={last_sent} "
                        f"processed={last_processed} "
                        f"at {last_run[:16] if last_run != 'never' else 'never'}",
                        f"  • Queued leads: {queued}",
                        f"  • Watchdog: "
                        f"{'🟢 healthy' if not tripped else '🟡 ' + ','.join(tripped) + f' (streak={streak})'}",
                    ]
            except Exception as _e:
                logger.warning(f"[ora-agent] degrade-stats failed: {_e}")

            reply_parts = [
                "**Bhai ORA chat ka primary brain (DeepSeek V3.1) abhi "
                "reach nahi ho raha,** but tension nahi:"
            ]
            if campaign_lines:
                reply_parts += [""] + campaign_lines + [
                    "",
                    "**Campaign cloud pe alag chal raha hai — "
                    "paisa flow uninterrupted.**",
                ]
            reply_parts += (
                [""]
                + diag_lines
                + [
                    "",
                    "**Cloud-side quick checks (laptop irrelevant):**",
                    "1. OpenRouter key: `curl -s https://openrouter.ai/api/v1/models "
                    "-H \"Authorization: Bearer $OPENROUTER_API_KEY\" | head -c 200`",
                    "2. Emergent LLM key (Claude fallback): `echo $EMERGENT_LLM_KEY | head -c 12`",
                    "3. Backend logs: `tail -n 50 /var/log/supervisor/backend.err.log`",
                    "4. Force provider retry: `POST /api/admin/selfcheck/trigger` "
                    "(nightly probe will flag the failed pillar + auto-route to repair queue)",
                ]
            )
            reply = "\n".join(reply_parts)
            return {
                "ok":       True,
                "error":    "llm_unavailable_graceful",
                "reply":    reply,
                "degraded": True,
            }

        # iter 326q — Provider-agnostic salvage. Even though some
        # provider-specific code paths already run this, certain code
        # paths (Claude text fallback, mid-loop NVIDIA retries) can
        # still hand us a `msg` with the tool-call leaked into
        # `content`. Run salvage one more time here so the rest of the
        # loop sees a normalised message regardless of the source.
        _salvage_inline_tool_call(msg)

        tool_calls = msg.get("tool_calls") or []
        content    = (msg.get("content") or "").strip()

        if not tool_calls:
            # iter 326q — Final safety net. If we still have JSON that
            # LOOKS like an unhandled tool-call (e.g. malformed JSON the
            # salvage parser refused to accept, or an OpenAI-schema echo
            # we couldn't normalise), DO NOT deliver it to the founder.
            # The previous behaviour leaked
            #   `{"type": "function", "name": "campaign_status", "parameters": {}}`
            # straight into chat, which made the founder think ORA was
            # broken (it was — but the leak made the symptom worse than
            # the cause). Substitute an honest "couldn't fetch" reply
            # instead — and never fabricate numbers to fill the gap.
            if _looks_like_unhandled_tool_call(content):
                logger.warning(
                    f"[ora-agent] DETECTED leaked tool-call JSON in final "
                    f"reply (len={len(content)}); substituting honest fallback"
                )
                content = (
                    "I tried to fetch that data but my tool call didn't "
                    "execute cleanly this turn. Please ask again — it usually "
                    "works on retry. (I won't make up numbers when I don't "
                    "have real data.)"
                )

            # LLM produced a final answer with no tool calls — done
            # iter 326t — Hallucination Shield v2. Ground domain-factual
            # claims against the conversation's tool outputs. Detects
            # fabricated numbers like "Eligible: 8, Sent: 5" — the lie
            # ORA told the founder on aurem.live this morning.
            content, _grounding_stats = _ground_reply_against_facts(
                content, history
            )
            if _grounding_stats.get("replaced"):
                logger.warning(
                    f"[ora-agent] HALLUCINATION REPLACED: "
                    f"unverified={_grounding_stats.get('unverified')}"
                )
            elif _grounding_stats.get("softened"):
                logger.info(
                    f"[ora-agent] hallucination soft-flag: "
                    f"unverified={_grounding_stats.get('unverified')}"
                )

            # iter 326v — Token Cost Transparency footer. Show the
            # founder what this turn AND the running session cost.
            # Disabled by setting ORA_AGENT_SHOW_COST=0 for any deploy
            # that doesn't want the line in user-visible chat.
            if os.environ.get("ORA_AGENT_SHOW_COST", "1") != "0":
                try:
                    _cost_line = _format_cost_footer(session_id)
                    if _cost_line:
                        content = content + _cost_line
                except Exception as _e:
                    logger.debug(f"[ora-agent] cost footer skipped: {_e}")

            # iter 323q — Stop Slop prose filter on every final assistant
            # turn. Idempotent; logs how many AI-tells it scrubbed.
            try:
                from services.ora_prose_filter import clean_prose
                content, _slop_stats = clean_prose(content)
                if _slop_stats.get("applied") and any(
                    _slop_stats.get(k, 0) for k in
                    ("openers_removed", "hedges_removed",
                     "standalone_filler", "em_dashes", "jargon")
                ):
                    logger.info(f"[ora_prose_filter] scrubbed: {_slop_stats}")
            except Exception as _e:
                logger.warning(f"[ora_prose_filter] skipped: {_e}")
            history.append({"role": "assistant", "content": content})
            await _save_history(session_id, history)
            return {
                "ok":        True,
                "reply":     content,
                "iterations": iterations,
                "done":      True,
            }

        # FIX #4 — deserialise only the first call; store only that one in
        # history so the LLM never sees unanswered tool_call references.
        call_raw = tool_calls[0]
        call     = _serialise_tool_call(call_raw)

        history.append({
            "role":       "assistant",
            "content":    content,
            "tool_calls": [call_raw],  # ← exactly one; the LLM gets one result back
        })

        tier = tier_of(call["name"])

        # ── TIER 1: execute immediately ───────────────────────────────
        if tier == "tier1_auto":
            # iter 323l — surface live tool progress to the UI (async jobs)
            if progress_cb is not None:
                try:
                    await progress_cb(call["name"])
                except Exception:
                    pass  # progress reporting must never crash the loop
            result = await invoke_tool(
                call["name"], call["args"], actor=f"auto:{founder_email}"
            )
            history.append({
                "role":         "tool",
                "tool_call_id": call["id"],
                "name":         call["name"],
                "content":      _format_tool_result(call["name"], result),
            })

            tool_ok = bool(result) and bool(result.get("ok", True))
            if not tool_ok:
                # iter 326tt — transient (network/5xx/rate-limit) failures
                # do not count toward the deterministic strike ceiling.
                # They still receive a recovery directive so the LLM can
                # decide to back off or retry with the same args.
                is_transient = _is_transient_failure(result)
                if is_transient:
                    transient_counts[call["name"]] = (
                        transient_counts.get(call["name"], 0) + 1
                    )
                else:
                    fail_counts[call["name"]] = fail_counts.get(call["name"], 0) + 1
                history.append(
                    _recovery_directive(
                        call["name"], result,
                        fail_counts.get(call["name"], 0)
                        + transient_counts.get(call["name"], 0),
                    )
                )
            else:
                fail_counts.pop(call["name"], None)        # reset on success
                transient_counts.pop(call["name"], None)   # reset on success

            # Halt if consecutive deterministic-fail ceiling reached.
            if fail_counts.get(call["name"], 0) >= 2:
                stop_msg = (
                    f"Tool `{call['name']}` failed twice consecutively. "
                    "Stopping auto-recovery — founder se discuss kar lo."
                )
                history.append({"role": "assistant", "content": stop_msg})
                await _save_history(session_id, history)
                return {
                    "ok":         True,
                    "reply":      stop_msg,
                    "iterations": iterations,
                    "done":       True,
                    "halted_for": "fail_ceiling",
                }
            # iter 326tt — separate, higher cap for pure-transient stalls
            # so a flapping network doesn't loop forever silently.
            if transient_counts.get(call["name"], 0) >= 5:
                stop_msg = (
                    f"Tool `{call['name']}` keeps hitting transient errors "
                    "(network / 5xx / rate-limit) — paused after 5 retries. "
                    "Yeh code ki galti nahi, environment issue lag raha hai."
                )
                history.append({"role": "assistant", "content": stop_msg})
                await _save_history(session_id, history)
                return {
                    "ok":         True,
                    "reply":      stop_msg,
                    "iterations": iterations,
                    "done":       True,
                    "halted_for": "transient_ceiling",
                }
            continue  # next iteration

        # ── TIER 2 / TIER 3: pause for founder approval ───────────────
        # FIX #5 — action_id is ALWAYS a fresh server-side uuid4.
        # The LLM-supplied call["id"] (e.g. from Groq/Claude) is preserved
        # as llm_call_id for UI reference only and never touches Mongo _id.
        action_id = uuid4().hex

        summary = await _summarize_for_human(call["name"], call["args"])
        await _persist_pending(
            action_id=action_id,
            session_id=session_id,
            tool=call["name"],
            args=call["args"],
            tier=tier,
            founder_email=founder_email,
            summary=summary,
        )
        await _save_history(session_id, history)
        # iter 326tt — include expires_at_iso so the UI can render a
        # live countdown instead of a hard-coded "30m" literal.
        _expires_at_iso = _iso(_now() + timedelta(minutes=EXPIRY_MINUTES))
        return {
            "ok": True,
            "action_required": {
                "action_id":          action_id,       # server UUID — use this for /approve
                "llm_call_id":        call["id"],       # LLM ref — for debugging only
                "tool":               call["name"],
                "args":               call["args"],
                "tier":               tier,
                "summary":            summary,
                "preamble":           content or "ORA wants to run this:",
                "expires_in_minutes": EXPIRY_MINUTES,
                "expires_at":         _expires_at_iso,
                # iter 326w — surface 30 s cancel window to UI (tier2 only).
                "auto_execute_in_seconds": (
                    TIER2_AUTO_EXECUTE_SECONDS if tier == "tier2_approve" else None
                ),
                "cancel_window_seconds": (
                    TIER2_AUTO_EXECUTE_SECONDS if tier == "tier2_approve" else 0
                ),
            },
            "iterations": iterations,
            "done":       False,
        }

    # Iteration budget exhausted
    await _save_history(session_id, history)
    return {
        "ok":        True,
        "reply":     (
            "Iteration budget reached — main yahin ruk gayi taaki "
            "infinite loop na ho. Bata kya next?"
        ),
        "iterations": iterations,
        "done":       True,
    }


# ── Query helpers ─────────────────────────────────────────────────────
async def list_pending(session_id: str | None = None) -> list[dict[str, Any]]:
    """Return pending actions, scoped to a session if provided.

    Calling this without a session_id returns ALL pending actions globally —
    intended for admin/debug surfaces only. The router exposes a session-
    scoped path; cross-session callers must explicitly pass session_id=None.
    """
    if _db is None:
        return []
    query: dict[str, Any] = {"status": "pending"}
    if session_id:
        query["session_id"] = session_id
    rows: list[dict[str, Any]] = []
    async for d in (
        _db[PENDING_COLLECTION]
        .find(query)
        .sort([("created_at", -1)])
        .limit(40)
    ):
        rows.append({
            "action_id":  d["_id"],
            "session_id": d.get("session_id"),
            "tool":       d.get("tool"),
            "args":       d.get("args"),
            "tier":       d.get("tier"),
            "summary":    d.get("summary"),
            "created_at": _iso(d.get("created_at")),
            "expires_at": _iso(d.get("expires_at")),
            "auto_execute_at": _iso(d.get("auto_execute_at")),
        })
    return rows


# ── iter 326w — Tier 2 auto-executor ──────────────────────────────────
# Called every 5 s by the scheduler. Atomically claims any tier2
# pending action whose auto_execute_at has passed and runs the standard
# approve path for it. Tier 3 actions are NEVER touched here.
async def auto_execute_due_tier2(now: datetime | None = None) -> dict[str, Any]:
    """Auto-execute tier2 actions whose 30 s cancel window elapsed.

    Returns a tiny summary so the scheduler can log activity. Safe to
    call concurrently — find_one_and_update atomically claims each row.
    """
    if _db is None:
        return {"ok": False, "executed": 0, "error": "DB not wired"}
    cutoff = now or _now()
    executed = 0
    failed   = 0
    while True:
        # Atomic claim: pending → auto_executing in one shot, so two
        # concurrent ticks never run the same action twice.
        row = await _db[PENDING_COLLECTION].find_one_and_update(
            {
                "status":          "pending",
                "tier":            "tier2_approve",
                "auto_execute_at": {"$lte": cutoff, "$ne": None},
            },
            {"$set": {
                "status":     "auto_executing",
                "decided_at": _now(),
                "decided_by": "system:auto_execute_30s",
            }},
            return_document=True,
            projection={"_id": 1, "session_id": 1, "founder_email": 1},
        )
        if not row:
            break
        try:
            await resume_after_decision(
                row.get("session_id", ""),
                action_id=row["_id"],
                approved=True,
                note="auto-executed after 30 s cancel window",
                founder_email=row.get("founder_email") or "system:auto_execute_30s",
            )
            executed += 1
        except Exception as e:
            logger.warning(f"[ora-agent] auto-execute failed for {row['_id']}: {e}")
            failed += 1
            # mark failed so we don't loop on it forever
            await _db[PENDING_COLLECTION].update_one(
                {"_id": row["_id"]},
                {"$set": {"status": "auto_execute_failed",
                          "result": {"error": str(e)}}},
            )
    return {"ok": True, "executed": executed, "failed": failed}

