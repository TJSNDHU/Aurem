"""
services/aurem_rules.py — iter D-79.

Per-customer `.aurem-rules.md` for the CTO agent.

Idea (lifted from `.cursorrules` + `CLAUDE.md` conventions): each
account stores a free-form Markdown blob of personal coding
conventions, naming preferences, tech-stack constraints, and
"don't ever do X" rules. The CTO chat agent then injects that blob
into the system prompt on every turn — so the model behaves like
it actually knows the customer's house style.

ZERO MOCKS: stored in Mongo (`aurem_user_rules` collection),
loaded per-request, attached to the CTO chat prompt. Empty string
when no rules set — no fake placeholder.

Persistence schema (`aurem_user_rules`):
  {
    user_id:    str  (one row per user; unique index)
    rules_md:   str  (free-form Markdown, max 16 KB)
    updated_at: datetime (UTC, ISO string)
    updated_by: str  (the email of whoever last saved)
    version:    int  (auto-incremented on save)
  }
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Hard cap so a runaway customer can't blow up the LLM context window.
MAX_RULES_LEN = 16 * 1024  # 16 KB

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_rules(user_id: str) -> dict[str, Any]:
    """Return the customer's rules envelope. Always returns a dict
    with `rules_md` (str) and `updated_at` (str | None) so the
    caller never has to defend against None."""
    if not user_id or _db is None:
        return {"rules_md": "", "updated_at": None, "version": 0}
    doc = await _db.aurem_user_rules.find_one(
        {"user_id": user_id}, {"_id": 0},
    )
    if not doc:
        return {"rules_md": "", "updated_at": None, "version": 0}
    return {
        "rules_md": (doc.get("rules_md") or "")[:MAX_RULES_LEN],
        "updated_at": doc.get("updated_at"),
        "updated_by": doc.get("updated_by"),
        "version": int(doc.get("version") or 0),
    }


async def set_rules(
    user_id: str, rules_md: str, *, updated_by: Optional[str] = None,
) -> dict[str, Any]:
    """Persist the customer's rules. Returns the saved envelope so
    the caller can confirm round-trip integrity. Trims to
    MAX_RULES_LEN — no silent truncation, we return `truncated: True`
    so the UI can warn the user."""
    if not user_id:
        raise ValueError("user_id required")
    if _db is None:
        raise RuntimeError("aurem_rules db not wired (set_db not called)")
    raw = rules_md or ""
    truncated = len(raw) > MAX_RULES_LEN
    clean = raw[:MAX_RULES_LEN]

    # Atomic upsert with version bump
    res = await _db.aurem_user_rules.find_one_and_update(
        {"user_id": user_id},
        {
            "$set": {
                "user_id": user_id,
                "rules_md": clean,
                "updated_at": _now_iso(),
                "updated_by": updated_by or "self",
            },
            "$inc": {"version": 1},
        },
        upsert=True,
        return_document=True,  # ReturnDocument.AFTER
    )
    saved = res or await _db.aurem_user_rules.find_one(
        {"user_id": user_id}, {"_id": 0},
    )
    return {
        "rules_md": (saved or {}).get("rules_md", ""),
        "updated_at": (saved or {}).get("updated_at"),
        "updated_by": (saved or {}).get("updated_by"),
        "version": int((saved or {}).get("version") or 0),
        "truncated": truncated,
        "size_bytes": len(clean),
    }


async def clear_rules(user_id: str) -> bool:
    """Wipe a user's rules entirely. Returns True if a row was deleted."""
    if not user_id or _db is None:
        return False
    res = await _db.aurem_user_rules.delete_one({"user_id": user_id})
    return res.deleted_count > 0


def build_rules_prompt_block(rules_md: str) -> str:
    """Render the rules into a system-prompt section. Empty string if
    the customer hasn't set any rules yet — we DON'T inject a fake
    placeholder."""
    if not rules_md or not rules_md.strip():
        return ""
    # Strict, scoped header so the LLM treats this as authoritative
    # without bleeding into other system blocks.
    return (
        "[CUSTOMER .aurem-rules.md — TREAT AS AUTHORITATIVE HOUSE STYLE]\n"
        + rules_md.strip()
        + "\n[END .aurem-rules.md]"
    )
