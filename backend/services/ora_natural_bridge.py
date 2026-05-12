"""
ORA Natural Language Bridge (iter 322ev) — Open Interpreter wrapper.

Lets ORA plan multi-step OS tasks autonomously via natural language. The
underlying engine is Open Interpreter (https://github.com/OpenInterpreter/
open-interpreter), which uses a function-calling LLM + LiteLLM to convert
plain English into shell/python commands.

P1 SCOPE — DRY RUN ONLY
-----------------------
This bridge returns PROPOSED steps; it does NOT execute them.  Founder
must route the steps through the existing safety-gated tools
(`shell_exec`, `safe_edit`, `docker_compose`, ...) for actual execution.

Design notes:
  - Lazy import of `interpreter` inside the function so the module loads
    cleanly even before pip install lands.
  - `auto_run = False`        — never auto-executes generated code.
  - `offline = True`          — disables OI's cloud Procedures feature.
  - `safe_mode = "ask"`       — second safety belt.
  - Model: `groq/llama-3.3-70b-versatile` (fast, free-tier Groq key).
  - Fresh `interpreter.messages = []` per call so plans don't leak across
    invocations.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_MODEL = "groq/llama-3.3-70b-versatile"


async def ora_run_natural(
    task: str,
    dry_run: bool = True,
    max_steps: int = 5,
) -> dict[str, Any]:
    """Plan a multi-step OS task via Open Interpreter (dry-run only in P1).

    Args:
        task:      Plain English instruction (e.g. "install postgresql 16
                   on Ubuntu and create an `aurem` database").
        dry_run:   Must be True in P1. False is rejected — execution
                   must route through the existing council/founder gates.
        max_steps: Hard cap on the number of code blocks returned (1-10).

    Returns:
        {ok, task, dry_run, planned_steps, steps:[{language, code}],
         model, scope, [error]}.
    """
    # ── Input validation ────────────────────────────────────────────
    if not task or not isinstance(task, str):
        return {"ok": False, "error": "task must be a non-empty string"}
    if len(task) > 2000:
        return {"ok": False, "error": "task exceeds 2000 char limit"}
    if not (1 <= max_steps <= 10):
        return {"ok": False, "error": "max_steps must be in 1..10"}

    # ── P1 execution gate ───────────────────────────────────────────
    if not dry_run:
        return {
            "ok": False,
            "error": (
                "execution disabled in P1 — route the returned steps via "
                "shell_exec / safe_edit / docker_compose tools with "
                "founder approval (council gate enforced)."
            ),
        }

    # ── Lazy import (fails gracefully if package not installed) ─────
    try:
        from interpreter import interpreter  # type: ignore
    except ModuleNotFoundError:
        return {
            "ok": False,
            "error": "open-interpreter not installed",
            "hint": "Run `pip install open-interpreter==0.4.3` and restart "
                    "the backend.",
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"interpreter import failed: {e!r}"}

    # ── Configure interpreter (safety-first) ────────────────────────
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "GROQ_API_KEY missing in .env"}

    interpreter.auto_run = False
    interpreter.offline = True
    interpreter.safe_mode = "ask"
    interpreter.verbose = False
    interpreter.llm.model = _MODEL
    interpreter.llm.api_key = api_key
    interpreter.llm.context_window = 8000
    interpreter.llm.max_tokens = 1500
    interpreter.messages = []  # fresh context each call

    # ── Run in worker thread (interpreter.chat is blocking) ─────────
    try:
        plan_msg = (
            f"OBJECTIVE: {task}\n\n"
            "PROVIDE A PLAN ONLY. List each step as a numbered item with "
            "the exact shell or python code in a fenced code block. Do "
            "NOT execute anything — just describe the plan."
        )
        result = await asyncio.wait_for(
            asyncio.to_thread(
                interpreter.chat,
                plan_msg,
                display=False,
                stream=False,
            ),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        return {"ok": False, "error": "interpreter.chat exceeded 60s"}
    except Exception as e:  # noqa: BLE001
        logger.exception("[ora_run_natural] interpreter.chat raised")
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}

    # ── Extract proposed steps from the result transcript ──────────
    steps: list[dict[str, str]] = []
    plan_text_parts: list[str] = []
    for msg in (result or []):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "assistant":
            mtype = msg.get("type")
            if mtype == "message":
                content = msg.get("content")
                if isinstance(content, str):
                    plan_text_parts.append(content)
            elif mtype == "code":
                lang = msg.get("format") or msg.get("language") or "shell"
                code = msg.get("content") or ""
                if code:
                    steps.append({"language": str(lang), "code": str(code)})

    # If OI didn't emit separate `type:code` messages (offline-plan mode),
    # parse fenced code blocks out of the plain-text plan ourselves so the
    # caller gets structured `steps` either way.
    plan_text = "\n".join(plan_text_parts).strip()
    if not steps and plan_text:
        import re as _re
        _FENCE = _re.compile(
            r"```(\w+)?\n([\s\S]*?)```", _re.MULTILINE,
        )
        for m in _FENCE.finditer(plan_text):
            lang = (m.group(1) or "shell").lower().strip()
            code = (m.group(2) or "").strip()
            if code:
                steps.append({"language": lang, "code": code})

    steps = steps[:max_steps]
    return {
        "ok": True,
        "task": task,
        "dry_run": True,
        "planned_steps": len(steps),
        "steps": steps,
        "plan_text": plan_text[:4000],
        "model": _MODEL,
        "scope": "emergent-pod",
        "note": (
            "Steps are PROPOSED only. Execute via shell_exec / safe_edit / "
            "docker_compose with founder approval."
        ),
    }


__all__ = ["ora_run_natural"]
