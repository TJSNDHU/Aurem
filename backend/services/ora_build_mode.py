"""
services/ora_build_mode.py — iter 327q (FIX 3 + P1 self-journaling)

Two Tier-2 tools that give ORA explicit phased authority:

  1. propose_build_plan(plan_md, files, tests, rationale)
     → Founder sees a 30-second approval card with the full plan.
     → On approve: row written to `ora_build_plans` with status=approved.
     → ORA then proceeds to build file-by-file, calling record_proof
       (services.build_verifier) after each file. Plan ID is returned
       so subsequent calls can link to it.

  2. propose_lesson(mistake_summary, lesson_text, code_diff)
     → Founder-supervised self-learning. ORA proposes a lesson she
       wants to add to her own mistakes file. Tier-2 card. On approve:
       lesson appended to `dev_322ey-ora-mistakes-lessons.md` AND a
       diff snapshot is written to `ora_learning_journal` (kind=
       "lesson_proposal_applied"). On reject: discarded.

Both tools are wired into TOOL_REGISTRY and TIER_2_APPROVE so the
existing `auto_execute_due_tier2` mechanism gives the founder the
30-second cancel window for free.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_LESSONS_FILE = Path("/app/backend/ora_skills/dev_322ey-ora-mistakes-lessons.md")
_PLANS_COLLECTION = "ora_build_plans"
_JOURNAL_COLLECTION = "ora_learning_journal"
_MAX_PLAN_CHARS = 8_000
_MAX_LESSON_CHARS = 2_000

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── FIX 3 — propose_build_plan ───────────────────────────────────────


async def propose_build_plan(
    plan_md: str,
    files: list[str] | None = None,
    tests: list[str] | None = None,
    rationale: str = "",
) -> dict:
    """Submit a build plan for founder approval. Returns plan_id.

    Tier-2 wraps this so the 30-second cancel window applies. ORA must
    NOT begin writing files until this returns ok=True; the LLM enforces
    that via SYSTEM_PROMPT rule 16 (BUILD_MODE).
    """
    if _db is None:
        return {"ok": False, "error": "db not ready"}
    if not isinstance(plan_md, str) or not plan_md.strip():
        return {"ok": False, "error": "plan_md required (non-empty markdown)"}
    if len(plan_md) > _MAX_PLAN_CHARS:
        return {"ok": False, "error": f"plan_md exceeds {_MAX_PLAN_CHARS} chars"}
    files = list(files or [])
    tests = list(tests or [])
    if len(files) > 60:
        return {"ok": False, "error": "too many files (cap 60)"}
    if len(tests) > 30:
        return {"ok": False, "error": "too many test files (cap 30)"}
    rationale = (rationale or "").strip()
    if len(rationale) < 10:
        return {"ok": False, "error": "rationale ≥10 chars required"}

    plan_id = uuid.uuid4().hex[:12]
    try:
        await _db[_PLANS_COLLECTION].insert_one({
            "_id":        plan_id,
            "plan_md":    plan_md,
            "files":      files,
            "tests":      tests,
            "rationale":  rationale,
            "status":     "approved",   # Tier-2 auto-execute = founder didn't reject
            "created_at": _now(),
        })
    except Exception as e:
        logger.warning(f"[build-mode] propose_build_plan insert failed: {e}")
        return {"ok": False, "error": str(e)[:200]}
    return {
        "ok":         True,
        "plan_id":    plan_id,
        "files":      files,
        "tests":      tests,
        "next_step":  "Begin building file 1 of {}. Call run_pytest after "
                       "each file, then record_proof at the end.".format(len(files)),
    }


# ── P1 — propose_lesson (self-journaling, founder-supervised) ────────


def _validate_lesson_text(text: str) -> str | None:
    t = (text or "").strip()
    if not t:
        return "lesson_text required"
    if len(t) > _MAX_LESSON_CHARS:
        return f"lesson_text exceeds {_MAX_LESSON_CHARS} chars"
    # No PII patterns (basic): refuse emails / phone-like / secret-like strings.
    if re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", t):
        return "lesson must not contain email addresses"
    if re.search(r"\b(?:sk-|pk-|AKIA|ghp_|xoxb-)[A-Za-z0-9_-]{8,}", t):
        return "lesson must not contain credentials / API keys"
    return None


async def propose_lesson(
    mistake_summary: str,
    lesson_text: str,
    code_diff: str = "",
) -> dict:
    """Append a new lesson to ORA's mistakes file. Tier-2 gated.

    On approve (Tier-2 auto-execute path): appends a dated bullet to
    `dev_322ey-ora-mistakes-lessons.md` AND records the diff in
    `ora_learning_journal` so the founder can roll back.
    """
    if _db is None:
        return {"ok": False, "error": "db not ready"}
    ms = (mistake_summary or "").strip()
    if not ms:
        return {"ok": False, "error": "mistake_summary required"}
    if len(ms) > 500:
        return {"ok": False, "error": "mistake_summary ≤500 chars"}
    err = _validate_lesson_text(lesson_text)
    if err:
        return {"ok": False, "error": err}
    if code_diff and len(code_diff) > 20_000:
        return {"ok": False, "error": "code_diff exceeds 20KB"}

    ts = _now()
    bullet = (
        f"\n\n### {ts.strftime('%Y-%m-%d')} — {ms.strip()}\n"
        f"{lesson_text.strip()}\n"
    )

    # Read previous body so we can record a unified diff in the journal.
    try:
        if _LESSONS_FILE.exists():
            prev_body = _LESSONS_FILE.read_text(encoding="utf-8", errors="replace")
        else:
            prev_body = ""
    except Exception as e:
        return {"ok": False, "error": f"read lessons file: {str(e)[:160]}"}

    new_body = prev_body + bullet

    try:
        _LESSONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LESSONS_FILE.write_text(new_body, encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"write lessons file: {str(e)[:160]}"}

    # Record a journal entry with a small unified diff for rollback.
    try:
        import difflib
        diff_lines = list(difflib.unified_diff(
            prev_body.splitlines(keepends=True),
            new_body.splitlines(keepends=True),
            fromfile="dev_322ey-ora-mistakes-lessons.md (before)",
            tofile="dev_322ey-ora-mistakes-lessons.md (after)",
            n=2,
        ))
        unified_diff = "".join(diff_lines)[:30_000]
        await _db[_JOURNAL_COLLECTION].insert_one({
            "kind":             "lesson_proposal_applied",
            "ts":               ts.isoformat(),
            "mistake_summary":  ms,
            "lesson_text":      lesson_text.strip(),
            "code_diff":        (code_diff or "")[:20_000],
            "unified_diff":     unified_diff,
            "file":             str(_LESSONS_FILE),
            "prev_size":        len(prev_body),
            "new_size":         len(new_body),
        })
    except Exception as e:
        logger.warning(f"[build-mode] lesson journal write failed: {e}")

    # Best-effort: rebuild the tier-1 lessons block so the next backend
    # restart picks up the new lesson immediately. (Tier-1 is cached at
    # module import; this nudges the manifest so admin UI sees it.)
    try:
        from services.ora_lessons_loader import build_lessons_block
        build_lessons_block()
    except Exception:
        pass

    return {
        "ok":              True,
        "appended_chars":  len(bullet),
        "lessons_file":    str(_LESSONS_FILE),
        "next_restart":    "Tier-1 manifest will pick up this lesson on next backend boot.",
    }


# ── Module-level helpers used by the registry ───────────────────────


TOOL_REGISTRY_PATCH = {
    "propose_build_plan": {
        "fn": propose_build_plan,
        "args_spec": {
            "plan_md":   "str ≤8KB — Markdown plan: numbered steps, files to "
                          "touch, tests to add. THIS IS WHAT THE FOUNDER WILL READ.",
            "files":     "list[str] — absolute paths the plan will create/edit (cap 60).",
            "tests":     "list[str] — pytest files that will be added or updated (cap 30).",
            "rationale": "str ≥10 chars — why this build, what it unlocks.",
        },
        "description": (
            "BUILD MODE GATE (iter 327q) — submit a full build plan for "
            "founder approval BEFORE writing any file. Tier-2 (30-second "
            "cancel window). On approve, ORA must build file-by-file and "
            "call run_pytest after each file. Use for any feature >2 files."
        ),
    },
    "propose_lesson": {
        "fn": propose_lesson,
        "args_spec": {
            "mistake_summary": "str ≤500 — one-line description of the mistake to record.",
            "lesson_text":     "str ≤2KB — the rule/heuristic ORA should follow next time.",
            "code_diff":       "str ≤20KB — optional code diff that triggered the lesson.",
        },
        "description": (
            "SELF-LEARNING GATE (iter 327q) — propose a new lesson to add "
            "to ORA's own mistakes file. Tier-2: founder sees a 30-second "
            "approval card. On approve, the lesson is appended to "
            "`dev_322ey-ora-mistakes-lessons.md` (Tier-1 memory) AND a "
            "unified-diff snapshot lands in `ora_learning_journal` so the "
            "edit is reversible. ORA may NOT write to the lessons file "
            "directly — this tool is the only path."
        ),
    },
}
