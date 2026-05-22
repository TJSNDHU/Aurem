"""
services/ora_decision_memory.py — iter 326aa (Phase 2 P1.3).

Vector memory of past ORA decisions. Lets ORA-CTO ask "have we done this
before? what was the outcome?" so it doesn't repeat fixes or contradict
last week's choices.

We don't run a vector DB — Mongo `$text` index + tag matching is enough
at AUREM's scale (< 50k decisions in a year). The contract is:

    await log_decision(...)
        — append a row to `ora_decisions`. Called from
          ora_agent.resume_after_decision and auto_execute_due_tier2.

    await recall_past_decisions(query, *, limit=5, tags=None)
        — Mongo $text search across summary/tool/args.
          Returns at most `limit` rows newest-first.

Schema (collection `ora_decisions`)
───────────────────────────────────
    _id            uuid hex
    session_id     str
    founder_email  str
    tool           str        — tool name
    summary        str        — human-readable summary of what ORA did
    args_preview   str        — first 200 chars of args (for grounding)
    outcome        str        — "approved" | "rejected" | "auto_executed" | "expired"
    tags           list[str]
    ts             datetime
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

_COLLECTION = "ora_decisions"
_db = None
_indexes_ensured = False


def set_db(database) -> None:
    global _db, _indexes_ensured
    _db = database
    _indexes_ensured = False


async def _ensure_indexes() -> None:
    global _indexes_ensured
    if _indexes_ensured or _db is None:
        return
    try:
        await _db[_COLLECTION].create_index([("summary", "text"),
                                              ("tool", "text"),
                                              ("args_preview", "text")])
        await _db[_COLLECTION].create_index("ts")
        await _db[_COLLECTION].create_index("tags")
        _indexes_ensured = True
    except Exception as e:
        logger.warning(f"[decision-memory] index ensure failed: {e}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _auto_tags(tool: str, summary: str) -> list[str]:
    """Cheap keyword extraction — keeps the tag space small and useful."""
    tags = set()
    if tool:
        tags.add(tool)
    text = (summary or "").lower()
    for kw in (
        "cors", "auth", "login", "mongo", "atlas", "stripe", "twilio",
        "resend", "email", "whatsapp", "campaign", "lead", "scout",
        "deploy", "playwright", "browser", "ora_agent", "checkpoint",
        "rollback", "schedule", "cron", "race", "leak", "timeout",
        "rate_limit", "hallucination", "cost",
    ):
        if kw in text:
            tags.add(kw)
    return sorted(tags)


async def log_decision(
    *,
    session_id: str,
    founder_email: str,
    tool: str,
    summary: str,
    args: Any = None,
    outcome: str = "approved",
    extra_tags: Optional[list[str]] = None,
) -> dict:
    """Append a decision row. Best-effort — never raises."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    await _ensure_indexes()
    args_preview = ""
    try:
        args_preview = str(args)[:200] if args is not None else ""
    except Exception:
        args_preview = ""
    tags = _auto_tags(tool, summary)
    if extra_tags:
        tags = sorted(set(tags) | {str(t)[:32] for t in extra_tags})
    doc = {
        "_id":           uuid.uuid4().hex,
        "session_id":    session_id or "",
        "founder_email": founder_email or "",
        "tool":          tool or "",
        "summary":       (summary or "")[:1000],
        "args_preview":  args_preview,
        "outcome":       outcome,
        "tags":          tags,
        "ts":            _now(),
    }
    try:
        await _db[_COLLECTION].insert_one(doc)
    except Exception as e:
        logger.warning(f"[decision-memory] log failed: {e}")
        return {"ok": False, "error": str(e)[:200]}
    return {"ok": True, "id": doc["_id"], "tags": tags}


_QUOTE_RE = re.compile(r'"')


async def recall_past_decisions(
    query: str,
    limit: int = 5,
    tags: Optional[list[str]] = None,
) -> dict:
    """Find past decisions semantically related to `query`. Uses Mongo
    `$text` index over (summary, tool, args_preview). `tags` filters by
    any of the listed tags.

    Returns: {ok, query, matches: [{id, ts, tool, outcome, summary, tags}]}
    """
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    if not isinstance(query, str) or not query.strip():
        return {"ok": False, "error": "query required"}
    await _ensure_indexes()
    limit = max(1, min(int(limit or 5), 50))
    # Mongo $text doesn't like raw quotes — sanitise.
    safe_q = _QUOTE_RE.sub("", query.strip())
    filt: dict[str, Any] = {"$text": {"$search": safe_q}}
    if tags:
        filt["tags"] = {"$in": [str(t)[:32] for t in tags]}
    rows: list[dict] = []
    try:
        cur = (
            _db[_COLLECTION]
            .find(filt, {
                "_id": 1, "tool": 1, "outcome": 1, "summary": 1,
                "tags": 1, "ts": 1,
                "score": {"$meta": "textScore"},
            })
            .sort([("score", {"$meta": "textScore"}), ("ts", -1)])
            .limit(limit)
        )
        async for d in cur:
            ts = d.get("ts")
            rows.append({
                "id":      d.get("_id"),
                "ts":      ts.isoformat() if isinstance(ts, datetime) else ts,
                "tool":    d.get("tool"),
                "outcome": d.get("outcome"),
                "summary": d.get("summary"),
                "tags":    d.get("tags") or [],
            })
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
    return {"ok": True, "query": query, "matches": rows, "count": len(rows)}
