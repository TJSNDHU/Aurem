"""
services/ora_fork_context.py — iter 331b Sprint 5

Spawn a fresh-context ORA sub-session for a single, bounded task.

Why this matters
----------------
Main-session ORA accumulates tool-result JSON, debug logs, and
implementation work in one context window. By the time a 200k-token
session needs to also run QA + integration-check, those tokens
compete with the actual work. The result: bad signal-to-noise.

`fork_context` solves this by spawning a SUB-session of ORA with:
  - Zero history from the main session
  - Only the specified `relevant_files` injected
  - A task-type-specific system prompt (debug / qa / integration_check)
  - A strict structured-return contract:
      {"verdict": "pass"|"fail", "findings": [...], "fix_suggestion": "..."}

The sub-session calls the LLM, gets a structured answer, and returns
that answer to the main agent. The sub-session is destroyed after
returning — no state leaks back.

This is the same architectural pattern Emergent E1's `testing_agent_v3_fork`,
`troubleshoot_agent`, and `integration_playbook_expert_v2` use.

Portability: zero Emergent imports. Uses the same `_llm_turn()`
dispatcher as the main agent, which is provider-agnostic.

Public API:
    fork_context(task_type, brief, relevant_files=[], return_schema=None)
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Task-type-specific system prompts ────────────────────────────────
# These prompts are intentionally short. The sub-session is single-turn:
# given the brief + files, produce a structured JSON answer.

_PROMPT_DEBUG = """You are a focused root-cause-analysis assistant.

Your sole job: given a debug brief + the listed files, identify the
root cause of the bug and propose ONE specific fix.

Rules:
- Be terse. No preamble, no "Certainly". No restating the brief.
- Walk the traceback or error bottom-up if one is present.
- Verify your hypothesis against the file contents — never guess.
- Return STRICT JSON in this shape and NOTHING else:
  {
    "verdict": "pass" | "fail",
    "findings": ["specific observation 1", "specific observation 2"],
    "fix_suggestion": "exact, actionable next step — one sentence"
  }
"verdict": "pass" means no bug found; "fail" means a real bug was found."""

_PROMPT_QA = """You are a focused QA reviewer.

Your sole job: given a QA brief + the listed files, return a verdict
on whether the change is acceptable to ship.

Rules:
- Read the brief carefully — only assess what was asked.
- Check the listed files against the AUREM CODE_STANDARDS (Pydantic
  models on endpoints, /api prefix, Motor async, _id excluded from
  responses, datetime tz-aware, type hints, data-testid on UI).
- Return STRICT JSON in this shape and NOTHING else:
  {
    "verdict": "pass" | "fail",
    "findings": ["concrete issue 1", "concrete issue 2"],
    "fix_suggestion": "exact, actionable next step — one sentence"
  }"""

_PROMPT_INTEGRATION_CHECK = """You are a focused 3rd-party-integration auditor.

Your sole job: given an integration brief + the listed files, verify
the integration follows AUREM's playbook rules:
  - Env var present (e.g. STRIPE_SECRET_KEY).
  - Webhook signature verified BEFORE trusting the body.
  - Retry only on 5xx; never on 4xx.
  - Calls persisted to an audit collection.
  - No hardcoded keys, URLs, or fallbacks.

Rules:
- Be terse. No preamble.
- Return STRICT JSON in this shape and NOTHING else:
  {
    "verdict": "pass" | "fail",
    "findings": ["concrete observation 1", "concrete observation 2"],
    "fix_suggestion": "exact, actionable next step — one sentence"
  }"""

_PROMPTS = {
    "debug":              _PROMPT_DEBUG,
    "qa":                 _PROMPT_QA,
    "integration_check":  _PROMPT_INTEGRATION_CHECK,
    # iter 332a-1 — aliases used by the new mode parameter
    "integration":        _PROMPT_INTEGRATION_CHECK,
    "design":             _PROMPT_QA,   # design review uses the same one-shot QA prompt
}

_VALID_MODES = {"ora", "emergent"}

# Hard caps so a sub-session can never blow up the main budget.
_MAX_FILES = 10
_MAX_FILE_CHARS = 8000
_MAX_BRIEF_CHARS = 2000


# ── Result schema enforcement ───────────────────────────────────────

_DEFAULT_SCHEMA = {
    "verdict": "pass | fail",
    "findings": "list of strings",
    "fix_suggestion": "one sentence",
}


def _extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of `text`. Tolerant of code-fence
    wrappers like ```json {...} ``` — the LLM occasionally adds them
    despite the instruction."""
    if not text:
        return None
    # Strip code fences first.
    fence_pat = re.compile(r"```(?:json)?\s*(\{[\s\S]+?\})\s*```", re.MULTILINE)
    m = fence_pat.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Otherwise find the outermost {...}.
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    return None
    return None


def _validate_result(raw: dict | None) -> dict:
    """Coerce the LLM's JSON into a guaranteed-shape result."""
    if not isinstance(raw, dict):
        return {
            "verdict":        "fail",
            "findings":       ["sub-session returned no parseable JSON"],
            "fix_suggestion": "Retry with a clearer brief, or inspect logs.",
        }
    verdict = raw.get("verdict")
    if verdict not in ("pass", "fail"):
        verdict = "fail"
    findings = raw.get("findings")
    if not isinstance(findings, list):
        findings = [str(findings)] if findings else []
    findings = [str(f)[:500] for f in findings][:10]
    fix = raw.get("fix_suggestion")
    if not isinstance(fix, str):
        fix = ""
    fix = fix[:500]
    return {
        "verdict":        verdict,
        "findings":       findings,
        "fix_suggestion": fix,
    }


# ── File loader (with safety + secrets scrub) ────────────────────────

def _load_files(paths: list[str]) -> tuple[str, list[dict]]:
    """Read the listed files, applying the safety guard + secrets
    scrubber. Returns (joined_text_for_prompt, manifest)."""
    from services.ora_safety import assert_path_safe, PathOutsideRoot, scrub_secrets
    pieces: list[str] = []
    manifest: list[dict] = []
    for raw in (paths or [])[:_MAX_FILES]:
        try:
            p = assert_path_safe(raw, mode="read")
        except PathOutsideRoot as e:
            manifest.append({"path": raw, "ok": False, "error": str(e)})
            continue
        if not p.exists() or not p.is_file():
            manifest.append({"path": str(p), "ok": False, "error": "not a file"})
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            manifest.append({"path": str(p), "ok": False, "error": str(e)[:200]})
            continue
        text, n_redacted = scrub_secrets(text)
        if len(text) > _MAX_FILE_CHARS:
            text = text[:_MAX_FILE_CHARS] + f"\n…[truncated {len(text) - _MAX_FILE_CHARS} chars]"
        pieces.append(f"\n--- FILE: {p} ---\n{text}\n--- END FILE ---")
        manifest.append({"path": str(p), "ok": True, "size": len(text),
                          "secrets_redacted": n_redacted})
    return "".join(pieces), manifest


# ── Main entrypoint ─────────────────────────────────────────────────

async def fork_context(
    task_type: str,
    brief: str,
    relevant_files: list[str] | None = None,
    return_schema: dict | None = None,
    *,
    mode: str = "ora",
    session_id: str = "",
) -> dict:
    """Spawn a fresh-context sub-session of ORA.

    iter 332a-1 — new optional kwargs:
      mode        : "ora" (default) | "emergent". "emergent" tags the
                    cost-log row appropriately so the cockpit knows
                    this was a higher-tier specialist call. Actual
                    sub-agent dispatch shares the same LLM path; the
                    auto-escalation routing rules ship in iter 332a-2.
      session_id  : caller's session id, used only for cost-log audit.

    Self-learning: BEFORE calling the LLM, hash a problem signature
    from (task_type, brief, files) and check `ora_validated_solutions`.
    If a cached answer exists and its use_count < threshold, return it
    directly at $0 cost. AFTER a successful LLM call, the answer is
    persisted under that signature so the next identical problem is free.

    Args:
      task_type:      "debug" | "qa" | "integration" | "integration_check" | "design"
      brief:          one paragraph describing the focused task
      relevant_files: up to 10 file paths to load into the sub-context
      return_schema:  reserved for future schema customisation;
                      currently fixed (verdict / findings / fix_suggestion).

    Returns:
      ok                     : True
      task_type              : echo
      mode                   : echo ("ora" | "emergent")
      verdict                : "pass" | "fail"
      findings               : list[str]
      fix_suggestion         : str
      files_loaded           : manifest
      elapsed_s              : float
      provider               : which LLM provider answered
      used_validated_solution: bool
      signature              : sha256 — for debugging / cache eviction
    """
    if task_type not in _PROMPTS:
        return {
            "ok":    False,
            "error": f"unknown task_type '{task_type}'. "
                     f"Valid: {sorted(_PROMPTS)}",
        }
    if mode not in _VALID_MODES:
        return {
            "ok":    False,
            "error": f"unknown mode '{mode}'. Valid: {sorted(_VALID_MODES)}",
        }
    if not brief or len(brief.strip()) < 5:
        return {"ok": False, "error": "brief is empty or too short (<5 chars)"}

    brief = brief.strip()[:_MAX_BRIEF_CHARS]
    system_prompt = _PROMPTS[task_type]
    files_block, manifest = _load_files(relevant_files or [])

    # ── iter 332a-1 — self-learning cache lookup ─────────────────────
    from services import ora_validated_solutions as _VS
    file_type = ""
    if manifest:
        first_path = manifest[0].get("path") or ""
        if "." in first_path:
            file_type = "." + first_path.rsplit(".", 1)[-1].lower()
    signature = _VS.compute_signature(
        task_type=task_type if task_type != "integration_check" else "integration",
        error_message=brief,
        file_type=file_type,
    )
    cached = await _VS.lookup_solution(signature)
    if cached:
        # Cache hit — return at $0
        elapsed = 0.0
        # Log cost row (still recorded so cockpit shows the win)
        await _VS.log_specialist_call(
            session_id=session_id,
            mode=mode,
            task_type=task_type,
            specialist_name="cache",
            verdict="pass",
            used_validated_solution=True,
            tokens_used=0,
            elapsed_ms=0,
        )
        logger.info(
            f"[fork_context] sig={signature[:12]}… CACHE HIT — "
            f"use_count={cached.get('use_count')}"
        )
        return {
            "ok":                True,
            "task_type":         task_type,
            "mode":              mode,
            "verdict":           "pass",
            "findings":          cached.get("findings") or [],
            "fix_suggestion":    cached.get("fix_suggestion") or "",
            "files_loaded":      manifest,
            "elapsed_s":         elapsed,
            "used_validated_solution": True,
            "signature":         signature,
            "validated_use_count": cached.get("use_count"),
        }

    user_content = f"BRIEF:\n{brief}"
    if files_block:
        user_content += "\n\nRELEVANT FILES:\n" + files_block
    user_content += (
        "\n\nReturn STRICT JSON only, in the exact shape specified in your "
        "system prompt. No prose, no code fences."
    )

    messages = [
        {"role": "system",  "content": system_prompt},
        {"role": "user",    "content": user_content},
    ]

    t0 = time.time()
    try:
        # iter 331b — Sprint 5. We deliberately DO NOT call `_llm_turn`
        # because that dispatcher sends a full `tools` schema to the LLM,
        # which causes the model to try to "call view_file" instead of
        # answering with JSON. Sub-sessions must be one-shot: no tools.
        content = await _llm_no_tools(messages)
    except Exception as e:
        logger.exception("[fork_context] LLM call failed")
        # Cost log even on failure so the cockpit reflects spend
        await _VS.log_specialist_call(
            session_id=session_id, mode=mode, task_type=task_type,
            specialist_name=mode, verdict="fail",
            used_validated_solution=False,
            elapsed_ms=int((time.time() - t0) * 1000),
        )
        return {
            "ok":         False,
            "task_type":  task_type,
            "mode":       mode,
            "error":      f"LLM dispatcher raised: {type(e).__name__}: {e}",
            "files_loaded": manifest,
            "signature":  signature,
        }
    elapsed = round(time.time() - t0, 2)

    if not content:
        await _VS.log_specialist_call(
            session_id=session_id, mode=mode, task_type=task_type,
            specialist_name=mode, verdict="fail",
            used_validated_solution=False,
            elapsed_ms=int(elapsed * 1000),
        )
        return {
            "ok":         False,
            "task_type":  task_type,
            "mode":       mode,
            "error":      "every LLM provider failed",
            "files_loaded": manifest,
            "elapsed_s":  elapsed,
            "signature":  signature,
        }

    parsed = _extract_json(content)
    validated = _validate_result(parsed)

    # iter 332a-2 — update failure counter for auto-escalation policy.
    # Caller can opt-in by passing session_id; absent → no-op.
    if session_id:
        try:
            from services.ora_guards import (
                record_task_failure, record_task_success,
            )
            if validated["verdict"] == "fail":
                record_task_failure(session_id, task_type)
            else:
                record_task_success(session_id, task_type)
        except Exception:
            pass

    # Persist the validated answer — so the next identical problem is $0.
    files_involved = [m.get("path") for m in manifest if m.get("path")]
    await _VS.save_solution(
        signature=signature,
        task_type=task_type,
        fix_suggestion=validated["fix_suggestion"],
        findings=validated["findings"],
        files_involved=files_involved,
        specialist=mode,
    )
    # Cost log
    await _VS.log_specialist_call(
        session_id=session_id, mode=mode, task_type=task_type,
        specialist_name=mode, verdict=validated["verdict"],
        used_validated_solution=False,
        elapsed_ms=int(elapsed * 1000),
    )

    out: dict[str, Any] = {
        "ok":           True,
        "task_type":    task_type,
        "mode":         mode,
        "verdict":      validated["verdict"],
        "findings":     validated["findings"],
        "fix_suggestion": validated["fix_suggestion"],
        "files_loaded": manifest,
        "elapsed_s":    elapsed,
        "used_validated_solution": False,
        "signature":    signature,
        "raw_llm_text": content[:2000],  # for debugging
    }
    logger.info(
        f"[fork_context] task={task_type} mode={mode} "
        f"verdict={validated['verdict']} "
        f"findings={len(validated['findings'])} elapsed={elapsed}s "
        f"sig={signature[:12]}…"
    )
    return out


# ── Tools-free LLM call (used by fork_context only) ─────────────────

async def _llm_no_tools(messages: list[dict]) -> str:
    """One-shot LLM call WITHOUT tool-calling capability.

    Sub-sessions never call tools — they answer with structured JSON
    or fail. Routes through OpenRouter (deepseek) primary, Emergent
    LLM key (claude) fallback. Returns plain text content or "".
    """
    import os
    import httpx
    import json as _json
    timeout = float(os.environ.get("FORK_CONTEXT_TIMEOUT", "30"))

    # Primary: OpenRouter deepseek (same provider as main session).
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if api_key:
        try:
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type":  "application/json",
                        "HTTP-Referer":  "https://aurem.live",
                        "X-Title":       "AUREM fork_context",
                    },
                    json={
                        "model":       os.environ.get(
                            "DEEPSEEK_MODEL", "deepseek/deepseek-chat-v3.1"
                        ),
                        "messages":    messages,
                        # NO tools field — that's the whole point.
                        "temperature": 0.1,   # lower for JSON adherence
                        "max_tokens":  1000,
                    },
                )
                if r.status_code == 200:
                    data = r.json()
                    msg = (data.get("choices") or [{}])[0].get("message") or {}
                    return (msg.get("content") or "").strip()
                logger.warning(
                    f"[fork_context] openrouter {r.status_code}: {r.text[:200]}"
                )
        except Exception as e:
            logger.warning(f"[fork_context] openrouter error: {e}")

    # Fallback: Emergent LLM key (Claude via emergentintegrations).
    elk = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if elk:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            # Extract system + user
            sys_prompt = ""
            user_text = ""
            for m in messages:
                if m.get("role") == "system":
                    sys_prompt = m.get("content") or ""
                elif m.get("role") == "user":
                    user_text = m.get("content") or ""
            chat = LlmChat(
                api_key=elk,
                session_id=f"fork-{int(time.time())}",
                system_message=sys_prompt,
            ).with_model("anthropic", "claude-sonnet-4-5-20250929")
            resp = await chat.send_message(UserMessage(text=user_text))
            return (str(resp) if resp else "").strip()
        except Exception as e:
            logger.warning(f"[fork_context] emergent claude error: {e}")

    return ""


# ── Registry patch ──────────────────────────────────────────────────

TOOL_REGISTRY_PATCH = {
    "fork_context": {
        "fn": fork_context,
        "args_spec": {
            "task_type":      "str — 'debug' | 'qa' | 'integration_check'",
            "brief":          "str — one paragraph (≤2000 chars)",
            "relevant_files": "list[str] — up to 10 file paths",
            "return_schema":  "dict — reserved (currently fixed schema)",
        },
        "description": (
            "TIER 1 (auto, returns structured JSON). Spawn a fresh-context "
            "sub-session of ORA for debug/QA/integration-check work. The "
            "sub-session gets ONLY the brief + relevant_files, runs ONE "
            "LLM turn, and returns {verdict, findings, fix_suggestion}. "
            "Use this for complex debugging WITHOUT polluting the main "
            "session's context window."
        ),
    },
}


def splice_into(tool_registry: dict) -> int:
    tool_registry.update(TOOL_REGISTRY_PATCH)
    return len(TOOL_REGISTRY_PATCH)


__all__ = ["fork_context", "splice_into", "TOOL_REGISTRY_PATCH"]
