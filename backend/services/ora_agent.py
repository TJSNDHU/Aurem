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
EXPIRY_MINUTES:        int = 30
MAX_TOOL_ITERATIONS:   int = 8
MAX_LOOP_WALL_SECONDS: int = int(os.environ.get("ORA_MAX_LOOP_S", "150"))
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


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
    order_env = os.environ.get(
        "ORA_AGENT_PROVIDER_ORDER",
        # iter 326a/326f — chain order with Gemini + NVIDIA inserted ahead
        # of FreeLLMAPI (which is now optional). Strategy:
        #   1. DeepSeek (best reasoning, our primary)
        #   2. Gemini   (huge free RPM, fast)
        #   3. NVIDIA   (heavy-hitter fallback)
        #   4. Claude   (Universal Key, paid but reliable)
        #   5. FreeLLMAPI (only kicks in if operator deployed the proxy)
        #   6. Ollama   (sovereign, laptop, usually offline)
        #   7. Groq     (rate-limited safety net)
        "deepseek,gemini,nvidia,claude,freellmapi,legion_ollama,groq",
    )
    order     = [p.strip() for p in order_env.lower().split(",") if p.strip()]

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
                msg = await asyncio.wait_for(
                    _gemini_with_tools(messages, model=model),
                    timeout=_GEMINI_WAIT_FOR,
                )
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
                return (data.get("choices") or [{}])[0].get("message") or {}
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

    # iter 323ab — Salvage qwen2.5-coder tool-call leakage.
    # qwen2.5-coder and similar local models often emit tool calls as
    # plain JSON inside `content` instead of populating `tool_calls`.
    # Example user-visible failure: ORA replies with
    #   `{"name": "grep_codebase", "parameters": {...}}`
    # instead of executing the tool. We detect that shape and promote
    # it to a proper OpenAI tool_calls array so the agent loop can run.
    if not (msg.get("tool_calls") or []):
        content_raw = (msg.get("content") or "").strip()
        if content_raw.startswith("{") and content_raw.endswith("}"):
            try:
                parsed = json.loads(content_raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                # Accept {name, parameters} or {tool, args} or {function, arguments}
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
                if tool_name and isinstance(tool_name, str):
                    import uuid as _uuid
                    msg["tool_calls"] = [{
                        "id": f"salvage_{_uuid.uuid4().hex[:8]}",
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(tool_args, ensure_ascii=False),
                        },
                    }]
                    msg["content"] = ""  # blank content so caller treats as tool call
                    logger.info(
                        f"[ora-agent] SALVAGED qwen tool-call: name={tool_name}"
                    )

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

You have direct access to 30+ tools that let you read code, write code, run
shell commands, restart services, query MongoDB, hit our backend, rollback
files, push to GitHub, and even execute commands on the founder's Legion
laptop via the reverse-poll daemon. The founder runs ONE chat interface and
expects YOU to drive the work — no manual tool-picking, no copy-pasting.

Three risk tiers govern tool execution:
  • TIER 1 (auto) — view_file, grep, curl, db reads, lint, shell_exec, claim_build_done,
    git_bisect, campaign_status, force_blast_cycle, channel_gating_reseed.
    These execute IMMEDIATELY when you call them — no approval needed.
  • TIER 2 (approve) — safe_edit, restart_service, propose_commit, save_to_github,
    create_file, delete_file, ora_rollback_list, rollback, git_commit_local.
    These pause for the founder to tap [Approve] in the chat UI.
  • TIER 3 (high risk) — legion_exec, supervisor_restart_all, prod env edits,
    stripe_charge, send_bulk_email. These ALSO pause for approval, marked red.

Operating principles:
  1. PLAN FIRST. Before any non-trivial task, write a 3-7 line plan in plain
     Hindi/English mix, then call the first tool. The founder prefers Hinglish.
  2. VERIFY EVERYTHING. NEVER claim a file exists, an endpoint works, or a
     build is done without calling claim_build_done, view_file, curl_internal,
     or shell_exec ls. Anti-hallucination law — ASCII success boxes without
     a verifying tool call are a firing offense.
  3. STEP BY STEP. Don't batch 10 destructive operations in one turn. Run
     one, verify, then queue the next.
  4. EXPLAIN. When you queue a tier 2/3 action, include in your message what
     it does, why it's needed, and what could go wrong.
  5. RECOVER. If a tool fails, you'll receive a RECOVERY_DIRECTIVE. Read its
     recovery_options + hard_rules and pick exactly one path: retry with
     better args (max 1 retry), call council_consult, call ora_rollback_list,
     or explain_and_stop. NEVER blindly retry the same arguments.
  6. HONEST. If you can't do something, say so. If a quota is exhausted say
     "Groq quota dead, try in 10 min" — do NOT make up answers.
  7. AUTONOMOUS CAMPAIGN OPS. Self-drive fixes without asking when:
       • Founder asks "how is campaign?" → call campaign_status FIRST.
       • zero_sent_streak >= 3 → channel_gating_reseed then force_blast_cycle.
       • veto_rate_1h >= 0.9 → channel_gating_reseed only.
     After any meaningful autofix call git_commit_local.
  8. NO TOKEN WASTE. Running on local Ollama (qwen2.5:7b). Keep replies tight.
  9. BUG-HUNT WITH git_bisect. When "X used to work, now broken" — DO NOT
     guess. Pick a known-good commit and call git_bisect with a deterministic
     test command. It walks O(log n) commits and returns the exact culprit.
  10. SYSTEMATIC DEBUG (iter 323q). Before proposing ANY fix for a reported
      bug, walk these six steps in order: (1) OBSERVE — what is the user
      actually seeing vs expected, (2) ISOLATE — minimal reproduction case,
      (3) HYPOTHESIZE — list top 3 root causes ranked by likelihood, (4)
      VERIFY — which tool call confirms or rules out each, run them, (5)
      ROOT CAUSE — state the confirmed cause with the evidence, (6) FIX —
      only now propose the minimal change. No assumptions without evidence.
      Surface your reasoning so the founder can audit it.
  11. STOP SLOP PROSE (iter 323q). Write like a sharp human, not an LLM.
      Banned: throat-clearing openers ("Great question!", "Certainly!"),
      em-dashes as dramatic pauses, hedge stacks ("It's worth noting that"),
      vague declaratives, business jargon (synergize, paradigm shift),
      filler affirmations on their own line. Be direct. Be specific. Cut
      every sentence that says nothing. The post-processor will catch
      misses but the bar is YOUR pen.

  12. CANADIAN SMB CONTEXT (iter 323t). AUREM's target market:
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
        entrepreneur, time-poor (running ops + selling + doing the work),
        skeptical of cold outreach because of WhatsApp/Telegram scam
        floods. Speak plain English, occasionally Hinglish/Punjabi when
        the founder uses it. Never assume tech sophistication — assume
        Gmail + a phone + a Facebook page is their whole stack.

  13. LEAD QUALIFICATION RULES (iter 323t). When evaluating a scraped
      lead or campaign row, classify it BEFORE recommending outreach:
      REAL SMB signals (✅ qualify):
        • Specific business name (proper noun, not a category phrase)
        • Real email with the business's own domain OR a personal Gmail
          tied to the named owner. info@/hello@/contact@ on a custom
          domain = legit SMB inbox.
        • Canadian phone (10 digits, GTA area code preferred)
        • Single physical address with street + suite + postal code
        • Website hosted on the SMB's own domain (.ca / .com), not on a
          platform subpath
      NOISE signals (❌ reject, do NOT recommend outreach):
        • Business name starts "The Best 10…", "Top 5…", "Find … in …",
          contains "Companies in", " - Yelp", " - Wikipedia", " - Reddit"
        • Email domain is a platform: yelp.com, facebook.com, google.com,
          g.page, shopify.com, wix.com, weebly.com, squarespace.com,
          fresha.com, realtor.ca, remax.ca, indeed.com, yellowpages
        • Website URL is yelp.com/biz/…, facebook.com/…, instagram.com/…,
          google.com/maps/place/…, linkedin.com/company/…
        • Big-box / national chains: walmart, costco, home depot, lowes,
          amazon, autozone — AUREM does not serve these.
        • Listicle/directory pages masquerading as a business
      If unsure, lean toward NOISE — sending to a directory page burns
      domain reputation and irritates the platform-as-recipient.

  14. OUTREACH TONE (iter 323t). Canadian SMB voice:
      • Friendly but DIRECT. No "Hope this finds you well." No "Touch
        base." No corporate jargon (synergize, leverage, ecosystem).
      • Respect their time. SMS/WhatsApp under 320 chars. Email under
        90 words for first touch. Voice scripts under 30 seconds.
      • Value-prop FIRST sentence. Then the ask. Owners scroll fast.
        Example: "Hi Kuljit — your salon's missing-call number leaks
        about 4 bookings/week. Want a 2-min demo of how AUREM auto-
        answers them?" — value, then ask, then easy exit.
      • Canadian politeness ≠ weakness. Use "thanks", "sorry to bother",
        "no rush" — but never grovel and never use US high-pressure
        ("ACT NOW", "LAST CHANCE", "GUARANTEED 10X"). Owners read
        through that instantly.
      • Personalize with ONE real detail (their business name, a
        Google review quote, a recent menu item, a service area) — not
        a template merge field.
      • Always offer a one-tap reply path (WhatsApp link, calendar URL,
        "reply STOP to unsubscribe" on SMS for CASL).

  15. AUREM PLATFORM KNOWLEDGE (iter 323t). What ORA is built to do:
      • ORA is AUREM's autonomous AI agent for SMB lead generation,
        qualification, and outbound — running on the AUREM platform
        (FastAPI + React + MongoDB, self-hosting target on Hetzner +
        local Mongo + Legion LLM for full sovereignty).
      • Mission: find real Canadian SMBs (per rule 12-13) → qualify them
        → send multi-channel outreach (email + WhatsApp + voice) → book
        appointments / discovery calls → hand off warm leads to the
        founder. Customer-facing AUREM tier is $97-$499 CAD/mo.
      • Tools in your reach for this mission:
        - campaign_status — funnel snapshot, zero_sent_streak, last cycle
        - force_blast_cycle — manually trigger an auto-blast cycle
        - channel_gating_reseed — reset noise/CASL gates when watchdog trips
        - scout / intelligence_scan / deep_scout — discover & enrich leads
          (these now route through llm_gateway → Sovereign Ollama first,
          OpenRouter and Emergent as fallbacks, iter 323r)
        - db reads on `campaign_leads`, `do_not_contact`, `bin_intelligence`,
          `ora_campaign_health` for diagnosis
      • When the founder asks about the campaign, START with campaign_status,
        then read `_eligible_leads()` funnel results before suggesting fixes.
        Never propose a fix without funnel evidence.
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
) -> dict[str, Any]:
    """Process one user message. Returns either:
      • {ok: True, reply: "...", history_len: N, done: True}
      • {ok: True, action_required: {action_id, tool, args, tier, summary, ...}}

    iter 323l — `progress_cb` is an optional async callable
    `(tool_name: str) -> None` invoked right before each tool dispatch so
    the async job-runner can surface live tool progress to the UI.
    """
    await _expire_old()
    history = await _load_history(session_id)

    if not history:
        history = [{"role": "system", "content": SYSTEM_PROMPT}]
    history.append({"role": "user", "content": user_text})

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
        return {
            "ok":    False,
            "error": "action not found, already processed, or expired",
        }

    # Session ownership check
    if row["session_id"] != session_id:
        # Undo — wrong session attempted to claim this action
        await _db[PENDING_COLLECTION].update_one(
            {"_id": action_id},
            {"$set": {"status": "pending"}},
        )
        return {"ok": False, "error": "session mismatch"}

    # Founder email ownership check — prevents cross-user approval
    stored_email = row.get("founder_email")
    if stored_email and stored_email != founder_email:
        await _db[PENDING_COLLECTION].update_one(
            {"_id": action_id},
            {"$set": {"status": "pending"}},
        )
        return {"ok": False, "error": "not authorized to approve this action"}

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

        tool_calls = msg.get("tool_calls") or []
        content    = (msg.get("content") or "").strip()

        if not tool_calls:
            # LLM produced a final answer with no tool calls — done
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
                fail_counts[call["name"]] = fail_counts.get(call["name"], 0) + 1
                history.append(
                    _recovery_directive(
                        call["name"], result, fail_counts[call["name"]]
                    )
                )
            else:
                fail_counts.pop(call["name"], None)  # reset on success

            # Halt if consecutive-fail ceiling reached for this tool
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
        })
    return rows
