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
_CLAUDE_WAIT_FOR:     float = 15.0
# Iter 322ex — production safety: Legion Ollama runs on the founder's
# laptop via ngrok. When the tunnel is dead, the previous 120s wait made
# ORA "silently scroll forever" before falling through. We honour
# LEGION_OLLAMA_TIMEOUT_S env so prod can set a short value (15s)
# while preview keeps the long value for cold-model loads.
_OLLAMA_WAIT_FOR:     float = float(os.environ.get("LEGION_OLLAMA_TIMEOUT_S", "120"))

# iter 322fk-3 — Legion/Ollama circuit breaker.
# When the user's local Legion daemon / ngrok tunnel is offline, every
# ORA request used to hang on the 120s ollama timeout before falling
# through to Claude. After ONE failure we skip ollama for 60s and route
# straight to the cloud fallback. Reply time after ngrok drop: 120s → 2s.
_OLLAMA_CB_FAIL_THRESHOLD = int(os.environ.get("ORA_OLLAMA_CB_THRESHOLD", "1"))
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
        1. legion_ollama — sovereign, local qwen2.5 via Legion daemon
        2. groq          — cloud, fast, daily TPD limit
        3. claude        — plain-text fallback (no tools this turn)

    Returns OpenAI-format message dict (may have tool_calls), or None if
    every provider failed.
    """
    order_env = os.environ.get("ORA_AGENT_PROVIDER_ORDER", "legion_ollama,claude")
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
            elif provider == "groq":
                msg = await asyncio.wait_for(
                    _groq_with_tools(messages, model=model), timeout=_GROQ_WAIT_FOR
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
    url       = os.environ.get("LEGION_OLLAMA_URL",   "http://localhost:11434")
    timeout_s = int(os.environ.get("LEGION_OLLAMA_TIMEOUT_S", "180"))

    payload: dict[str, Any] = {
        "model":      model,
        "messages":   messages,
        "tools":      lean_ollama_tool_schemas(),
        "stream":     False,
        "keep_alive": "60m",
        "options":    {"temperature": 0.25, "num_predict": 1000},
    }
    body = json.dumps(payload, ensure_ascii=False)
    cmd  = (
        f"curl -sS --max-time {timeout_s} "
        f"-H 'Content-Type: application/json' "
        f"-d {shlex.quote(body)} "
        f"{url.rstrip('/')}/api/chat"
    )
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
                            "🔴 Legion daemon: NEVER polled — "
                            "laptop daemon start kar"
                        )
                    elif age < 60:
                        diag_lines.append(
                            f"🟢 Legion daemon alive ({int(age)}s ago) — "
                            "Ollama inference failed, model evicted ho gaya hoga"
                        )
                    elif age < 300:
                        diag_lines.append(
                            f"🟡 Legion daemon busy ({int(age)}s since last poll)"
                        )
                    else:
                        diag_lines.append(
                            f"🔴 Legion daemon OFFLINE ({int(age/60)} min) — "
                            "laptop sleeping/closed"
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
                "**Bhai ORA chat abhi local Ollama pe nahi pahuch paa raha,** "
                "but tension nahi:"
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
                    "**Laptop pe quick checks:**",
                    "1. Daemon: `tail -5 ~/legion_daemon.log`",
                    "2. Ollama: `ollama list` (model loaded hai?)",
                    "3. Restart: `pkill -9 -f legion_daemon.py && "
                    "nohup python3 ~/legion_daemon.py "
                    "> ~/legion_daemon.log 2>&1 &`",
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
