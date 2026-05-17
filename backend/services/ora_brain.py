"""
ORA Brain v2.2 — Sovereign Orchestrator
=========================================

Implements user-spec'd Phase 2.2 architecture:

  1. Mode classifier (Claude Sonnet, ~200ms) — General vs Software Engineer
  2. Mode 1 (General Intelligence) — reuses ULTRAPLINIAN multi-model race
     in `aurem_chat` for any non-codebase question
  3. Mode 2 (Software Engineer) — proposes diffs only, NEVER auto-applies.
     Stores pending actions in `db.ora_dev_actions` for admin approval.
  4. Hybrid local-first stub — if `OLLAMA_HOST` is set, classifier and
     small-talk go through Ollama; otherwise gracefully fall back to
     Emergent LLM key (Claude/GPT/Gemini).

Design constraints honored:
  - Sealed files NEVER touched: utils/admin_guard.py, SystemStatusChip.jsx
  - No new routes — wires into existing /api/ora/command via dispatch
  - No new dependencies (uses httpx + emergentintegrations already in stack)
  - Existing `services.ora_command_center.execute_command()` still
    handles all explicit AUREM commands (status/leads/scan/etc.) — the
    orchestrator only kicks in when the user message isn't a registered
    command.

iter 281.2
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Sealed paths — never propose edits to these ─────────────────────
SEALED_PATHS = {
    "/app/backend/utils/admin_guard.py",
    "/app/frontend/src/platform/SystemStatusChip.jsx",
    # Anything inside .git or .emergent
}

# Heuristic markers that strongly suggest Mode 2 (codebase work).
# Used as a cheap pre-filter before invoking the LLM classifier.
_DEV_KEYWORDS = re.compile(
    r"\b(fix|bug|error|500|404|patch|deploy|router|endpoint|"
    r"add\s+\w+\s+(endpoint|route|component|api)|"
    r"why is /api/|why does /api/|"
    r"refactor|rollback|migrate|schema|collection|"
    r"webhook|stripe|mongo|redis|"
    r"file\s+(/app/|backend/|frontend/)|"
    r"diff|commit|push|pull|test\s+(pass|fail))\b",
    re.IGNORECASE,
)


# ── Hybrid Provider Stub (Pick 2c) ──────────────────────────────────
async def _hybrid_classify(text: str) -> str:
    """Return 'mode_1' or 'mode_2'.

    Order:
      1. Cheap keyword pre-filter — strong dev signals → mode_2 immediately
      2. Sovereign Legion (LEGION_OLLAMA_URL / OLLAMA_URL) — FREE & local
      3. Otherwise ask Claude Sonnet via Emergent LLM key (paid, fallback)
      4. On any failure → default to mode_1 (safe — Mode 1 can still answer
         most things correctly, while Mode 2 incorrectly entered would
         clutter the approval queue).
    """
    if _DEV_KEYWORDS.search(text):
        return "mode_2"

    # iter 323 — route classify through the FREE Sovereign Legion node first.
    # Order of preference: LEGION_OLLAMA_URL (Legion daemon ngrok) →
    # OLLAMA_URL (alt mount) → OLLAMA_HOST (legacy). Picks the first set.
    ollama_host = (
        os.environ.get("LEGION_OLLAMA_URL")
        or os.environ.get("OLLAMA_URL")
        or os.environ.get("OLLAMA_HOST")
        or ""
    ).strip()
    if ollama_host:
        try:
            import httpx
            classify_model = (
                os.environ.get("OLLAMA_CLASSIFY_MODEL")
                or os.environ.get("LOCAL_LLM_MODEL")
                or os.environ.get("LEGION_OLLAMA_MODEL")
                or "llama3.1"
            )
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.post(
                    f"{ollama_host.rstrip('/')}/api/generate",
                    json={
                        "model": classify_model,
                        "prompt": _CLASSIFY_PROMPT.format(text=text[:500]),
                        "stream": False,
                        "options": {"temperature": 0.0, "num_predict": 6},
                    },
                )
            if r.status_code == 200:
                out = (r.json().get("response") or "").strip().lower()
                logger.info(f"[ORA-brain] sovereign classify → {out[:20]}")
                return "mode_2" if "mode_2" in out or "engineer" in out else "mode_1"
        except Exception as e:
            logger.warning(f"[ORA-brain] Sovereign Legion classifier failed: {e}")

    # Cloud classifier via Emergent LLM key
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=f"ora_classify_{uuid.uuid4()}",
            system_message=(
                "You are a fast classifier. Given a user message, output exactly "
                "one token: `mode_1` if the message is a general question "
                "(weather, advice, definitions, market trends, knowledge), or "
                "`mode_2` if the message is about modifying / debugging the "
                "AUREM codebase (writing endpoints, fixing bugs, adding "
                "components, querying logs, running shell). No prose."
            ),
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        out = (await chat.send_message(UserMessage(text=text[:500]))).strip().lower()
        return "mode_2" if "mode_2" in out else "mode_1"
    except Exception as e:
        logger.warning(f"[ORA-brain] Cloud classifier failed: {e}")
        return "mode_1"


_CLASSIFY_PROMPT = """\
Classify this user message into exactly one mode. Output only the token.

mode_1 = general question (weather, knowledge, advice, market trends)
mode_2 = AUREM codebase work (write endpoint, fix bug, add component,
        query logs, run shell, modify file)

Message: {text}
Mode:"""


# ── Mode 1: General Intelligence (reuse ULTRAPLINIAN) ───────────────
async def _run_mode_1(text: str, session_id: str, user: str) -> Dict[str, Any]:
    """Delegate to the existing aurem_chat ULTRAPLINIAN multi-model race.
    Reuse, don't reimplement. iter 281.2 / Pick 3a"""
    try:
        from routers.aurem_chat import _aurem_chat_inner, ChatRequest
        req = ChatRequest(message=text, session_id=session_id, user_id=user)
        # http_request=None → JWT-bound founder detection skipped, which is
        # fine because /api/ora/command does its own auth upstream.
        result = await _aurem_chat_inner(req, http_request=None)
        return {
            "ok": True,
            "mode": "mode_1",
            "intent": "general",
            "reply": result.response,
            "params": {},
            "data": {
                "llm_source": result.llm_source,
                "session_id": result.session_id,
            },
        }
    except Exception as e:
        logger.exception(f"[ORA-brain] mode_1 failed: {e}")
        return {
            "ok": False,
            "mode": "mode_1",
            "intent": "general",
            "reply": (
                f"I hit a {type(e).__name__} on my general-intelligence path. "
                "Try again — I auto-route to a different model on retry. "
                "Anything else, boss?"
            ),
            "params": {},
            "data": {"error": str(e)[:120]},
        }


# ── Mode 2: Software Engineer (propose-only, approval-gated) ────────
async def _run_mode_2(db, text: str, session_id: str, user: str) -> Dict[str, Any]:
    """Generate a code-change proposal. Does NOT apply changes. Inserts
    a row into `db.ora_dev_actions` with status='pending' and returns
    the proposal id so the admin can review/approve via the Dev Console.

    The actual file diffs are deliberately deferred — Mode 2 v1 is a
    'reasoned proposal' (target file + intent + reasoning + suggested
    patch sketch). Admin reads the sketch, then either:
      a) applies it manually (current default — safest)
      b) calls POST /api/admin/ora-dev/approve/{id} with verified diff
         (future hook, not auto-wired this iter)

    This pattern matches user spec: 'ORA NEVER auto-applies code'.
    """
    if db is None:
        return {
            "ok": False, "mode": "mode_2", "intent": "dev_proposal",
            "reply": "Database unavailable — can't log proposal.",
            "params": {}, "data": {},
        }

    # Generate a proposal via Claude Sonnet (best for code reasoning).
    proposal_text = "Generation failed."
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=f"ora_devmode_{session_id}",
            system_message=_MODE_2_SYSTEM_PROMPT,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        proposal_text = (await chat.send_message(UserMessage(text=text))).strip()
    except Exception as e:
        logger.warning(f"[ORA-brain] mode_2 LLM failed: {e}")
        proposal_text = (
            f"I couldn't reach the code-reasoning model ({type(e).__name__}). "
            "Try again, or rephrase the request more concretely."
        )

    # Detect any sealed-file mentions and warn instead of proposing.
    sealed_mentioned = [p for p in SEALED_PATHS if p in proposal_text or p.split("/")[-1] in proposal_text]
    if sealed_mentioned:
        proposal_text = (
            f"⚠️ Refusing to propose changes to sealed file(s): "
            f"{', '.join(sealed_mentioned)}. These are protected by policy. "
            "Pick a different target file."
        )

    proposal_id = str(uuid.uuid4())
    doc = {
        "proposal_id": proposal_id,
        "user": user,
        "session_id": session_id,
        "request_text": text,
        "proposal_text": proposal_text,
        "status": "pending",
        "sealed_blocked": bool(sealed_mentioned),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved_by": None,
        "approved_at": None,
        "applied_at": None,
        "rolled_back_at": None,
    }
    try:
        await db.ora_dev_actions.insert_one(doc)
    except Exception as e:
        logger.warning(f"[ORA-brain] failed to log proposal: {e}")

    reply = (
        f"📐 Engineering proposal queued (id `{proposal_id[:8]}`):\n\n"
        f"{proposal_text}\n\n"
        "I will NOT auto-apply this. Open ORA Dev Console to review & approve, "
        "or apply manually. Anything else, boss?"
    )
    return {
        "ok": True,
        "mode": "mode_2",
        "intent": "dev_proposal",
        "reply": reply,
        "params": {"proposal_id": proposal_id},
        "data": {
            "proposal_id": proposal_id,
            "status": "pending",
            "sealed_blocked": bool(sealed_mentioned),
        },
    }


_MODE_2_SYSTEM_PROMPT = """\
You are ORA — AUREM platform's Sovereign Orchestrator running in Software \
Engineer mode (Mode 2). Stack: FastAPI + React + MongoDB + Redis + Cloudflare. \
Persona: sharp, confident, direct. End complex answers with: "Anything else, boss?"

Your job: produce an ENGINEERING PROPOSAL for the user's request. The proposal \
will be reviewed by a human admin before any code is applied. Do NOT pretend to \
have applied changes.

Format your output as:

  TARGET FILE(S):  /absolute/path/file.ext  (one per line)
  INTENT:          one-sentence summary
  REASONING:       why this is the right change (3-6 lines)
  SUGGESTED PATCH: pseudocode or unified-diff sketch (≤40 lines)
  RISKS:           bullet list of regressions to watch for
  TEST PLAN:       how the admin should verify after applying

Sealed files (REFUSE to propose changes — say so explicitly if asked):
  /app/backend/utils/admin_guard.py
  /app/frontend/src/platform/SystemStatusChip.jsx

If the request is vague or ambiguous, ask ONE clarifying question instead of \
guessing. Be brief — no preamble."""


# ── Public entry point ─────────────────────────────────────────────
async def run_brain(
    db,
    text: str,
    *,
    session_id: Optional[str] = None,
    user: str = "admin",
) -> Dict[str, Any]:
    """Single entry point for the Sovereign Orchestrator.

    Returns a dict shaped like `execute_command` so the existing
    /api/ora/command endpoint can pass it through unchanged.
    """
    sid = session_id or str(uuid.uuid4())
    mode = await _hybrid_classify(text)
    if mode == "mode_2":
        result = await _run_mode_2(db, text, sid, user)
    else:
        result = await _run_mode_1(text, sid, user)
    result.setdefault("data", {})["mode_classified"] = mode
    return result
