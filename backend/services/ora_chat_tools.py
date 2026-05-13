"""
ora_chat_tools.py — Auto tool-calling for ORA in the chat path (iter 322fe).

Why this exists:
  Until iter 322fd, ORA's chat endpoint (/api/public/ora/chat) was
  text-only — she could DESCRIBE tool calls but never EXECUTE them.
  That created the conditions for the iter 322fc hallucination
  (fake incident_bus.py with fabricated 8.4KB metadata).

  This module wires Groq's OpenAI-compatible function-calling so ORA
  can autonomously invoke READ-ONLY safety-vetted tools mid-conversation
  to verify her own claims before answering.

Scope:
  - Only SAFE_AUTO_TOOLS are exposed in chat (read-only + claim_build_done).
  - Destructive tools (safe_edit, restart_service, legion_exec, etc.) stay
    behind the CTO Mode tab where the founder still approves each call.
  - Max 5 tool-call iterations per turn to bound latency + cost.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from services.ora_tools import invoke_tool

logger = logging.getLogger(__name__)

# ── Tools that ORA can call WITHOUT founder approval in chat ─────────
# These are all read-only (or self-verification), argv-bound, sandboxed.
SAFE_AUTO_TOOLS: tuple[str, ...] = (
    "view_file",
    "view_dir",
    "grep_codebase",
    "curl_internal",
    "db_count",
    "db_distinct",
    "git_log",
    "health_check",
    "lint_python",
    "shell_exec",          # whitelist-bound (whoami/ls/find/stat/wc/etc.)
    "claim_build_done",    # anti-hallucination receipt
)

# ── JSON-Schema descriptors per safe tool (Groq/OpenAI function format) ──
# Hand-curated to match each tool's real signature in ora_tools.py.
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "view_file",
            "description": (
                "Read the real contents of a file under /app. Returns "
                "{ok, path, content, lines, size_bytes}. Use this when "
                "the founder asks 'what's in file X' or before claiming "
                "a file contains code C."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path":      {"type": "string", "description": "Absolute path inside /app/{backend,frontend,memory,ora_skills,scripts,aurem-cto}"},
                    "max_lines": {"type": "integer", "minimum": 1, "maximum": 500, "default": 200},
                    "start":     {"type": "integer", "minimum": 1, "default": 1},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_dir",
            "description": "List a directory's entries (name/type/bytes). Use to discover real file structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path":        {"type": "string"},
                    "max_entries": {"type": "integer", "minimum": 1, "maximum": 200, "default": 60},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_codebase",
            "description": "Real grep -rn over the codebase. Returns matched lines with file:line:body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern":     {"type": "string"},
                    "file_glob":   {"type": "string", "description": "e.g. '*.py' or '*.jsx'"},
                    "root":        {"type": "string", "description": "Must be /app/{backend,frontend,memory,ora_skills}"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 200, "default": 40},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "curl_internal",
            "description": "GET our own backend (localhost:8001). Returns real http_status + body fingerprint. Use to verify an endpoint exists before claiming so.",
            "parameters": {
                "type": "object",
                "properties": {
                    "endpoint": {"type": "string", "description": "Must start with /api/"},
                    "method":   {"type": "string", "enum": ["GET"], "default": "GET"},
                },
                "required": ["endpoint"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "db_count",
            "description": "Real MongoDB count_documents on an allowlisted collection. Use before claiming any number of leads/customers/events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string"},
                    "filter_":    {"type": "object", "default": {}},
                },
                "required": ["collection"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "db_distinct",
            "description": "Distinct field values on an allowlisted collection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string"},
                    "field":      {"type": "string"},
                    "filter_":    {"type": "object", "default": {}},
                    "limit":      {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
                },
                "required": ["collection", "field"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "Recent git commits on /app — proves what is deployed.",
            "parameters": {
                "type": "object",
                "properties": {"n": {"type": "integer", "minimum": 1, "maximum": 30, "default": 5}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "health_check",
            "description": "Hit /api/platform/health — proves the backend is up.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lint_python",
            "description": "Run ruff check on a Python file under /app/backend. Read-only.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "shell_exec",
            "description": (
                "Real subprocess.run against the Linux kernel — argv-only, shell=False. "
                "Whitelist: whoami, id, pwd, hostname, uname, uptime, date, env "
                "(secrets redacted), ls, find, wc, stat, du, file, df, free, ps, "
                "which, whereis, python3 --version, node --version, pip list, yarn "
                "--version, ruff, git (log/status/diff/show/branch), supervisorctl status. "
                "Use 'ls' with args ['-la', path] to verify a file exists."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command name (must be in whitelist)"},
                    "args":    {"type": "array", "items": {"type": "string"}, "description": "Sanitised argv list"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "claim_build_done",
            "description": (
                "ANTI-HALLUCINATION RECEIPT — call this BEFORE telling the founder "
                "you built/shipped/deployed something. Performs real os.stat() on every "
                "claimed file and real curl on every claimed endpoint. Returns "
                "verified=true only if every proof checks out. If verified=false, you "
                "MUST NOT show a success message."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "files":     {"type": "array", "items": {"type": "string"}, "description": "Absolute paths the build claims to have created"},
                    "endpoints": {"type": "array", "items": {"type": "string"}, "description": "/api/... routes the build claims to expose"},
                    "label":     {"type": "string"},
                },
            },
        },
    },
]


def _normalize_tool_args(name: str, raw: dict[str, Any] | None) -> dict[str, Any]:
    """Some LLMs send `filter` instead of `filter_`. Soft-normalize."""
    if not isinstance(raw, dict):
        return {}
    args = dict(raw)
    # db_count / db_distinct use Python-reserved-ish `filter_`. LLMs often emit `filter`.
    if "filter" in args and "filter_" not in args:
        args["filter_"] = args.pop("filter")
    return args


def _summarize_tool_result(name: str, result: dict[str, Any]) -> str:
    """Compact tool result to keep token cost low when fed back to the LLM.

    The LLM does NOT need the full raw body — it needs the ground-truth
    fingerprint (status, count, ok-flag, error). Verbose outputs (file
    bodies, grep hits) are kept but capped.
    """
    if not isinstance(result, dict):
        return json.dumps({"raw": str(result)[:1200]})
    safe = dict(result)
    # Trim large fields
    for key in ("content", "stdout", "stderr", "output", "body"):
        v = safe.get(key)
        if isinstance(v, str) and len(v) > 1800:
            safe[key] = v[:1800] + f"\n…[truncated {len(v) - 1800} chars]"
    # Trim hit-lists (grep, db_distinct)
    for key in ("hits", "rows", "entries", "values", "lines"):
        v = safe.get(key)
        if isinstance(v, list) and len(v) > 30:
            safe[key] = v[:30] + [f"…[truncated {len(v) - 30} items]"]
    return json.dumps(safe, default=str)[:4000]


async def groq_chat_with_tools(
    messages: list[dict[str, Any]],
    *,
    client: httpx.AsyncClient,
    model: str | None = None,
    max_iters: int = 5,
    actor: str = "ora-chat-auto",
) -> tuple[str | None, list[dict[str, Any]]]:
    """Call Groq with function-calling enabled and execute tool calls in a loop.

    Returns:
        (final_reply_text_or_None, tool_invocations_audit_trail)
    """
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return None, []

    convo: list[dict[str, Any]] = list(messages)  # mutable copy
    audit: list[dict[str, Any]] = []
    model_name = model or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

    for iteration in range(max_iters):
        try:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={
                    "model":       model_name,
                    "messages":    convo,
                    "tools":       TOOL_SCHEMAS,
                    "tool_choice": "auto",
                    "temperature": float(os.environ.get("ORA_GROQ_TEMP", "0.3")),
                    "max_tokens":  900,
                },
                timeout=25.0,
            )
            if resp.status_code != 200:
                logger.warning(
                    f"[ora-chat-tools] groq {resp.status_code}: {resp.text[:240]}"
                )
                return None, audit

            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            tool_calls = msg.get("tool_calls") or []

            # No more tool calls → final answer
            if not tool_calls:
                content = (msg.get("content") or "").strip()
                return (content or None), audit

            # Echo the assistant turn (with tool_calls) into conversation
            convo.append({
                "role":       "assistant",
                "content":    msg.get("content") or "",
                "tool_calls": tool_calls,
            })

            # Execute each tool sequentially (Groq sometimes batches several)
            for call in tool_calls:
                fn = (call.get("function") or {})
                name = fn.get("name") or ""
                raw_args = fn.get("arguments") or "{}"
                try:
                    parsed = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    parsed = {}

                if name not in SAFE_AUTO_TOOLS:
                    tool_result = {
                        "ok": False,
                        "error": f"tool '{name}' is not enabled for auto-execution in chat. "
                                 f"Available: {sorted(SAFE_AUTO_TOOLS)}",
                    }
                else:
                    args = _normalize_tool_args(name, parsed)
                    tool_result = await invoke_tool(name, args, actor=actor)

                audit.append({
                    "tool":      name,
                    "args":      parsed,
                    "ok":        bool(tool_result.get("ok")),
                    "elapsed_ms": tool_result.get("elapsed_ms"),
                    "iteration": iteration + 1,
                })

                # Feed tool output back to the LLM
                convo.append({
                    "role":         "tool",
                    "tool_call_id": call.get("id") or f"call_{iteration}_{name}",
                    "name":         name,
                    "content":      _summarize_tool_result(name, tool_result),
                })

        except httpx.RequestError as e:
            logger.warning(f"[ora-chat-tools] network error iter {iteration}: {e}")
            return None, audit
        except Exception as e:
            logger.warning(f"[ora-chat-tools] unexpected iter {iteration}: {type(e).__name__}: {e}")
            return None, audit

    # Hit max iterations without final answer — synthesize a closer
    logger.info(f"[ora-chat-tools] hit max_iters={max_iters}, returning what we have")
    return None, audit
