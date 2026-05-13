"""
ora_agent.py — Autonomous CTO mode for ORA (iter 322fi).

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
    pending → approved → executing → done | failed
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
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4

import httpx

from services.ora_tools import invoke_tool, TOOL_REGISTRY

logger = logging.getLogger(__name__)

# ── Tier policy ──────────────────────────────────────────────────────
TIER_1_AUTO: set[str] = {
    # Pure read / observation — no founder approval needed.
    "view_file", "view_dir", "grep_codebase", "curl_internal",
    "db_count", "db_distinct", "git_log", "health_check",
    "lint_python", "shell_exec", "claim_build_done",
    # iter 322fi-rollback — read-only diagnostics for recovery flows
    "council_consult", "ora_rollback_list",
}
TIER_2_APPROVE: set[str] = {
    # Mutates state but reversible — inline [Approve]/[Reject] card.
    "safe_edit", "restart_service", "propose_commit", "save_to_github",
    "ora_rollback_list", "ora_rollback_restore", "kv_set", "feature_flag_set",
    "create_file", "delete_file",
}
TIER_3_HIGH_RISK: set[str] = {
    # Destructive / external — same inline UI but card is red-banded and
    # tagged "high risk", and the founder must type CONFIRM to approve.
    "legion_exec", "supervisor_restart_all", "prod_env_set",
    "stripe_charge", "send_bulk_email",
}

EXPIRY_MINUTES = 30        # pending actions auto-expire
MAX_TOOL_ITERATIONS = 8    # bound per "run" turn
PENDING_COLLECTION = "ora_pending_actions"
HISTORY_COLLECTION = "ora_agent_history"


def tier_of(name: str) -> str:
    if name in TIER_1_AUTO:
        return "tier1_auto"
    if name in TIER_2_APPROVE:
        return "tier2_approve"
    if name in TIER_3_HIGH_RISK:
        return "tier3_high_risk"
    # Unknown tool name → treat as tier2 (safe default — ask before running)
    return "tier2_approve"


# ── Mongo helpers ────────────────────────────────────────────────────
_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if isinstance(dt, datetime) else None


async def _persist_pending(
    *, action_id: str, session_id: str, tool: str, args: dict,
    tier: str, founder_email: str, summary: str,
) -> None:
    if _db is None:
        return
    await _db[PENDING_COLLECTION].insert_one({
        "_id":           action_id,
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
        {"$set": {"status": "expired", "decided_at": _now(),
                  "decided_by": "system:auto_expire"}},
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
    if tool == "legion_exec":
        cmd = (a.get("cmd") or "")[:120]
        risk = a.get("risk_hint") or "auto"
        return f"Run on Legion laptop [{risk}]: {cmd}"
    if tool == "create_file":
        return f"Create {a.get('path','?')} ({len(str(a.get('content',''))):,} bytes)"
    if tool == "delete_file":
        return f"DELETE file {a.get('path','?')}"
    # Generic
    return f"{tool}({json.dumps(a, default=str)[:140]})"


# ── Tool-schema generation (function-calling) ────────────────────────
def _tool_schemas_for_tier(*tiers: str) -> list[dict[str, Any]]:
    """Generate Groq/OpenAI function-call schemas for every tool whose
    tier is in `tiers`. Each tier set is precomputed."""
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
            params_props[arg_name] = {"type": "string", "description": str(arg_desc)[:240]}
        out.append({
            "type": "function",
            "function": {
                "name": name,
                "description": (meta.get("description") or name)[:480],
                "parameters": {
                    "type": "object",
                    "properties": params_props,
                },
            },
        })
    return out


def all_agent_tool_schemas() -> list[dict[str, Any]]:
    """Every tool ORA can invoke autonomously or via approval."""
    return _tool_schemas_for_tier("tier1_auto", "tier2_approve", "tier3_high_risk")


# ── Groq LLM call with tools ─────────────────────────────────────────
async def _llm_turn(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
) -> dict[str, Any] | None:
    """One turn against the LLM provider chain with full agent tool schema.

    Provider order (overridable via ORA_AGENT_PROVIDER_ORDER env):
        1. legion_ollama   — sovereign, local qwen2.5 via Legion daemon
        2. groq            — cloud, fast, daily TPD limit
        3. claude          — plain-text fallback (no tools this turn)

    Returns the raw OpenAI-format message dict (may have tool_calls), or
    None if every provider failed.
    """
    order_env = os.environ.get(
        "ORA_AGENT_PROVIDER_ORDER", "legion_ollama,groq,claude"
    )
    order = [p.strip() for p in order_env.lower().split(",") if p.strip()]

    for provider in order:
        try:
            if provider in ("legion_ollama", "ollama", "legion"):
                msg = await _ollama_with_tools(messages)
            elif provider == "groq":
                msg = await _groq_with_tools(messages, model=model)
            elif provider == "claude":
                msg = await _claude_text_fallback(messages)
            else:
                continue
            if msg is not None:
                return msg
        except Exception as e:
            logger.warning(
                f"[ora-agent] provider={provider} crashed: {type(e).__name__}: {e}"
            )
            continue
    return None


async def _groq_with_tools(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
) -> dict[str, Any] | None:
    """Groq function-calling. Returns None on rate-limit / network / no key."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return None
    model_name = model or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}",
                          "Content-Type":  "application/json"},
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

    Uses Ollama's OpenAI-compatible /v1/chat/completions which supports
    function-calling for qwen2.5 / llama3.1+ / mistral-nemo models. The
    call is made FROM the Legion laptop (curl localhost:11434) — pod
    just enqueues + waits.

    Returns the OpenAI-format `message` dict (may have tool_calls).
    """
    try:
        from services.legion_tool import legion_exec
    except Exception:
        return None
    import json as _json
    import shlex

    model = os.environ.get("LEGION_OLLAMA_MODEL", "qwen2.5:7b")
    url   = os.environ.get("LEGION_OLLAMA_URL", "http://localhost:11434")
    timeout_s = int(os.environ.get("LEGION_OLLAMA_TIMEOUT_S", "180"))

    payload: dict[str, Any] = {
        "model":       model,
        "messages":    messages,
        "tools":       all_agent_tool_schemas(),
        "tool_choice": "auto",
        "temperature": 0.25,
        "max_tokens":  1000,
        "stream":      False,
    }
    body = _json.dumps(payload, ensure_ascii=False)
    cmd = (
        f"curl -sS --max-time {timeout_s} "
        f"-H 'Content-Type: application/json' "
        f"-d {shlex.quote(body)} "
        f"{url.rstrip('/')}/v1/chat/completions"
    )
    result = await legion_exec(
        cmd=cmd, cwd="/opt/aurem-cto",
        timeout_s=timeout_s + 10, risk_hint="low",
        wait_max_s=int(os.environ.get("ORA_AGENT_OLLAMA_WAIT_S", "120")),
    )
    if not result.get("ok") or int(result.get("exit_code", -1)) != 0:
        logger.info(
            f"[ora-agent] ollama miss: ok={result.get('ok')} "
            f"exit={result.get('exit_code')} stderr={(result.get('stderr','') or '')[:160]}"
        )
        return None
    stdout = (result.get("stdout") or "").strip()
    if not stdout:
        return None
    try:
        data = _json.loads(stdout)
    except _json.JSONDecodeError as e:
        logger.info(f"[ora-agent] ollama non-JSON: {e} body={stdout[:200]}")
        return None
    return (data.get("choices") or [{}])[0].get("message") or {}


async def _claude_text_fallback(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Plain-text Claude call. Used when Groq is unavailable so ORA can
    still respond, just without tool execution this turn. The founder
    can ask again once Groq recovers (or we can wire claude function-
    calling separately in a future iter)."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
    except Exception:
        return None
    # Flatten messages → one user prompt + a synthetic system
    sys_lines: list[str] = []
    convo_lines: list[str] = []
    for m in messages:
        role = m.get("role", "")
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
    try:
        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=f"ora-agent-fb-{os.urandom(4).hex()}",
            system_message=sys_msg,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        text = (await chat.send_message(UserMessage(text=user_msg[:6000]))).strip()
        if not text:
            return None
        return {"role": "assistant", "content": text}
    except Exception as e:
        logger.warning(f"[ora-agent] claude fallback failed: {type(e).__name__}: {e}")
        return None


# ── Session history persistence ──────────────────────────────────────
async def _load_history(session_id: str) -> list[dict[str, Any]]:
    if _db is None:
        return []
    doc = await _db[HISTORY_COLLECTION].find_one(
        {"_id": session_id}, {"messages": 1, "_id": 0}
    )
    return (doc or {}).get("messages") or []


async def _save_history(session_id: str, messages: list[dict[str, Any]]) -> None:
    if _db is None:
        return
    await _db[HISTORY_COLLECTION].update_one(
        {"_id": session_id},
        {"$set": {"messages": messages[-40:],  # cap conversation
                  "updated_at": _now()},
         "$setOnInsert": {"created_at": _now()}},
        upsert=True,
    )


# ── Public entry points ──────────────────────────────────────────────
SYSTEM_PROMPT = """You are ORA — AUREM's autonomous CTO and orchestrator.

You have direct access to 30+ tools that let you read code, write code, run
shell commands, restart services, query MongoDB, hit our backend, rollback
files, push to GitHub, and even execute commands on the founder's Legion
laptop via the reverse-poll daemon. The founder runs ONE chat interface and
expects YOU to drive the work — no manual tool-picking, no copy-pasting
commands.

Three risk tiers govern tool execution:
  • TIER 1 (auto) — view_file, grep, curl, db reads, lint, shell_exec, claim_build_done.
    These execute IMMEDIATELY when you call them — no approval needed.
  • TIER 2 (approve) — safe_edit, restart_service, propose_commit, save_to_github,
    create_file, delete_file, rollback. These pause for the founder to tap
    [Approve] in the chat UI. Be SPECIFIC in your request so they can decide fast.
  • TIER 3 (high risk) — legion_exec, supervisor_restart_all, prod env edits,
    stripe_charge, send_bulk_email. These ALSO pause for approval, marked red.

Operating principles:
  1. PLAN FIRST. Before any non-trivial task, write a 3-7 line plan in plain
     Hindi/English mix, then call the first tool. The founder prefers Hinglish.
  2. VERIFY EVERYTHING. NEVER claim a file exists, an endpoint works, or a
     build is done without calling claim_build_done, view_file, curl_internal,
     or shell_exec ls. Anti-hallucination law from iter 322fd applies — ASCII
     success boxes without a verifying tool call are a firing offense.
  3. STEP BY STEP. Don't batch 10 destructive operations in one turn. Run
     one, verify, then queue the next. The founder wants progress visible.
  4. EXPLAIN. When you queue a tier 2/3 action, include in your message what
     it does, why it's needed, and what could go wrong. The approval card
     shows your summary — make it useful.
  5. RECOVER. If a tool fails, you'll receive a `_recovery_directive` tool
     observation. Read its recovery_options + hard_rules and pick exactly
     one path: retry with better args (max 1 retry), call council_consult,
     call ora_rollback_list, or explain_and_stop. NEVER blindly retry the
     same arguments. NEVER claim success when a tool returned ok:false.
  6. HONEST. If you can't do something, say so. If a quota is exhausted,
     say "Groq quota dead, try in 10 min" — do NOT make up answers.
"""


def _serialise_tool_call(call: dict[str, Any]) -> dict[str, Any]:
    fn = call.get("function") or {}
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


async def run_turn(
    session_id: str,
    user_text: str,
    *,
    founder_email: str,
) -> dict[str, Any]:
    """Process one user message. Returns either:
      • {ok: True, reply: "...", history_len: N, done: True}
      • {ok: True, action_required: {action_id, tool, args, tier, summary, ...}}
    """
    await _expire_old()
    history = await _load_history(session_id)

    if not history:
        history = [{"role": "system", "content": SYSTEM_PROMPT}]
    history.append({"role": "user", "content": user_text})

    return await _continue_loop(session_id, history, founder_email)


async def resume_after_decision(
    session_id: str,
    *,
    action_id: str,
    approved: bool,
    note: str,
    founder_email: str,
) -> dict[str, Any]:
    """User clicked Approve or Reject. Pick up where we left off."""
    if _db is None:
        return {"ok": False, "error": "DB not wired"}
    row = await _db[PENDING_COLLECTION].find_one({"_id": action_id}, {"_id": 0, "tool": 1,
                                                                       "args": 1, "status": 1,
                                                                       "session_id": 1})
    if not row:
        return {"ok": False, "error": "action not found"}
    if row["session_id"] != session_id:
        return {"ok": False, "error": "session mismatch"}
    if row["status"] != "pending":
        return {"ok": False, "error": f"already {row['status']}"}

    history = await _load_history(session_id)

    if approved:
        # Execute the tool now
        result = await invoke_tool(row["tool"], row["args"] or {}, actor=f"approved:{founder_email}")
        await _db[PENDING_COLLECTION].update_one(
            {"_id": action_id},
            {"$set": {"status": "done", "decided_at": _now(),
                      "decided_by": founder_email, "result": result}},
        )
        # Feed tool result back into the conversation
        history.append({
            "role": "tool",
            "tool_call_id": action_id,
            "name": row["tool"],
            "content": _format_tool_result(row["tool"], result),
        })
        # iter 322fi-rollback: tier-2 destructive call failed? Inject a
        # recovery directive so ORA's next turn can suggest rollback.
        if isinstance(result, dict) and result.get("ok") is False:
            history.append(_recovery_directive(row["tool"], result, attempt=1))
    else:
        await _db[PENDING_COLLECTION].update_one(
            {"_id": action_id},
            {"$set": {"status": "rejected", "decided_at": _now(),
                      "decided_by": founder_email, "rejection_note": note[:400]}},
        )
        history.append({
            "role": "tool",
            "tool_call_id": action_id,
            "name": row["tool"],
            "content": json.dumps({
                "ok": False,
                "rejected": True,
                "reason": note or "founder rejected",
                "guidance": "Do not retry this exact action. Propose an alternative or stop.",
            }),
        })

    return await _continue_loop(session_id, history, founder_email)


async def _continue_loop(
    session_id: str,
    history: list[dict[str, Any]],
    founder_email: str,
) -> dict[str, Any]:
    """Inner loop — keep calling tier-1 tools automatically; pause on
    tier 2/3 by writing a pending action and returning action_required.

    iter 322fi-rollback: when a tool execution fails (ok=False), we
    inject a structured RECOVERY_DIRECTIVE so the LLM picks one of:
      • retry with adjusted args (max 2 attempts per tool)
      • call ora_rollback_list / council_consult to diagnose
      • stop and ask founder
    Same-tool consecutive-fail counter is tracked per turn.
    """
    iterations = 0
    fail_counts: dict[str, int] = {}    # tool_name → consecutive fails
    while iterations < MAX_TOOL_ITERATIONS:
        iterations += 1
        msg = await _llm_turn(history)
        if msg is None:
            await _save_history(session_id, history)
            return {"ok": False, "error": "llm_unavailable",
                    "reply": "Groq + Claude dono down. 10 min me retry kar."}

        tool_calls = msg.get("tool_calls") or []
        content = (msg.get("content") or "").strip()

        if not tool_calls:
            # Final answer
            history.append({"role": "assistant", "content": content})
            await _save_history(session_id, history)
            return {"ok": True, "reply": content, "iterations": iterations, "done": True}

        # Echo assistant turn with tool_calls into history
        history.append({
            "role":       "assistant",
            "content":    content,
            "tool_calls": tool_calls,
        })

        # We only process the first tool call per turn — keeps step-by-step
        # progress visible and simplifies the approval state machine.
        call = _serialise_tool_call(tool_calls[0])
        tier = tier_of(call["name"])

        if tier == "tier1_auto":
            # Execute immediately, feed result, keep looping
            result = await invoke_tool(call["name"], call["args"], actor=f"auto:{founder_email}")
            history.append({
                "role":         "tool",
                "tool_call_id": call["id"],
                "name":         call["name"],
                "content":      _format_tool_result(call["name"], result),
            })

            # Auto-recovery: did this tool fail?
            tool_ok = bool(result) and bool(result.get("ok", True))
            if not tool_ok:
                fail_counts[call["name"]] = fail_counts.get(call["name"], 0) + 1
                history.append(_recovery_directive(call["name"], result,
                                                    fail_counts[call["name"]]))
            else:
                # Success resets the consecutive-fail counter for this tool
                fail_counts.pop(call["name"], None)

            # If we've hit the recovery ceiling for this tool, stop & ask
            if fail_counts.get(call["name"], 0) >= 2:
                stop_msg = (
                    f"Tool `{call['name']}` failed twice consecutively. "
                    f"Stopping auto-recovery loop — founder se discuss kar lo."
                )
                history.append({"role": "assistant", "content": stop_msg})
                await _save_history(session_id, history)
                return {"ok": True, "reply": stop_msg, "iterations": iterations,
                        "done": True, "halted_for": "fail_ceiling"}
            continue

        # Tier 2 / Tier 3 → pause, write pending row, return to UI
        summary = await _summarize_for_human(call["name"], call["args"])
        await _persist_pending(
            action_id=call["id"],
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
                "action_id":  call["id"],
                "tool":       call["name"],
                "args":       call["args"],
                "tier":       tier,
                "summary":    summary,
                "preamble":   content or "ORA wants to run this:",
                "expires_in_minutes": EXPIRY_MINUTES,
            },
            "iterations": iterations,
            "done":       False,
        }

    # Loop budget exhausted
    await _save_history(session_id, history)
    return {
        "ok":   True,
        "reply": ("Iteration budget reached — main yahin ruk gayi taaki "
                  "infinite loop na ho. Bata kya next?"),
        "iterations": iterations,
        "done": True,
    }


def _recovery_directive(tool: str, result: dict, attempt: int) -> dict[str, Any]:
    """Build a 'tool' role message that nudges the LLM toward recovery.

    The directive is JSON so the model treats it as a tool observation and
    plans a next action accordingly. We never prescribe a SPECIFIC tool —
    we just describe the options. The LLM picks.
    """
    err = (result or {}).get("error") or result.get("detail") or "unspecified error"
    body = {
        "RECOVERY_DIRECTIVE":         True,
        "failed_tool":                tool,
        "consecutive_fails":          attempt,
        "fail_excerpt":               str(err)[:300],
        "remaining_attempts_before_halt": max(0, 2 - attempt),
        "recovery_options": [
            ("retry_once_with_better_args  — Only if you know the exact arg "
             "that was wrong. Do NOT retry the same args verbatim."),
            ("call_council_consult       — Get a second opinion from the "
             "AUREM council for risky/architectural calls."),
            ("call_ora_rollback_list     — See what backups exist before "
             "destructive moves; restore via tier-2 ora_rollback_restore."),
            ("explain_and_stop           — If the fix needs founder input "
             "(missing creds, business decision), produce a final assistant "
             "message describing what happened and stop calling tools."),
        ],
        "hard_rules": [
            "If the failed tool is tier 2/3 (mutating), DO NOT silently retry. "
            "Either explain_and_stop or propose ora_rollback_restore so the "
            "founder can approve.",
            "Do NOT fabricate success. The previous turn FAILED — say so.",
        ],
    }
    return {
        "role":         "tool",
        "tool_call_id": f"_recovery_{tool}_{attempt}",
        "name":         "_recovery_directive",
        "content":      json.dumps(body, default=str)[:2200],
    }


async def list_pending(session_id: str | None = None) -> list[dict[str, Any]]:
    if _db is None:
        return []
    q: dict[str, Any] = {"status": "pending"}
    if session_id:
        q["session_id"] = session_id
    rows: list[dict[str, Any]] = []
    async for d in _db[PENDING_COLLECTION].find(q).sort([("created_at", -1)]).limit(40):
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
