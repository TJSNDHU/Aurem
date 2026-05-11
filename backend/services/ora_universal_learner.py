"""
ORA Universal Learner — iter 322ar
====================================
Single async fire-and-forget entry point: every significant event in
AUREM flows through `ora_learn(event_data)` and lands in
`db.ora_brain_thoughts`. Over time this corpus replaces paid LLM calls
for routine reasoning.

Contract (event_data dict):

    source        str   — short id of the producer (scout|hunter|...)
    event         str   — UPPER_SNAKE event name (SCOUT_RUN, HUNT_CYCLE…)
    category      str   — coarse bucket the brain learns by:
                          lead_intelligence | agent_performance |
                          council_decision | customer_action |
                          site_generated   | pixel_intelligence |
                          ora_conversation | system_health |
                          fix_applied
    summary       str   — human-readable one-liner (no PII)
    outcome       str   — short tag (success/failed/converted/...)
    agent         str?  — owning agent id, optional
    bin_id        str?  — tenant scope, defaults to "system"
    confidence    float — defaults to 0.8

Usage pattern from every caller:

    try:
        asyncio.create_task(ora_learn({...}))   # fire-and-forget
    except Exception:
        pass                                     # never break hot path
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _redact(text: Any) -> str:
    """Trim summaries + strip the most common PII patterns (email/phone)."""
    if text is None:
        return ""
    s = str(text)[:600]
    import re
    s = re.sub(r"[\w\.\-+]+@[\w\.\-]+\.\w+", "<email>", s)
    s = re.sub(r"\+?\d[\d\-\s\(\)]{8,}\d", "<phone>", s)
    return s


async def ora_learn(event_data: Optional[Dict[str, Any]] = None) -> None:
    """Persist one learnable thought + emit an A2A event. Never raises.
    Designed to be wrapped in `asyncio.create_task()` so hot-path latency
    is unaffected."""
    if not event_data or _db is None:
        return
    try:
        thought = {
            "ts": _now(),
            "source": str(event_data.get("source") or "unknown"),
            "event": str(event_data.get("event") or "EVENT"),
            "category": str(event_data.get("category") or "system_health"),
            "summary": _redact(event_data.get("summary")),
            "outcome": str(event_data.get("outcome") or "n/a"),
            "agent": event_data.get("agent"),
            "bin_id": str(event_data.get("bin_id") or "system"),
            "confidence": float(event_data.get("confidence", 0.8)),
            "learnable": True,
        }
        # Drop None/empty optional keys to keep docs small
        thought = {k: v for k, v in thought.items() if v not in (None, "")}
        await _db.ora_brain_thoughts.insert_one(thought)
    except Exception as e:
        logger.debug(f"[ora-learn] write skipped: {e}")
        return

    # A2A bus best-effort
    try:
        from services.a2a_bus import bus
        await bus.emit(
            from_agent="ora_learner",
            event="ORA_LEARNED",
            payload={
                "category": event_data.get("category"),
                "source": event_data.get("source"),
                "outcome": event_data.get("outcome"),
            },
        )
    except Exception:
        pass


def fire(event_data: Dict[str, Any]) -> None:
    """Synchronous helper — schedules ora_learn() as a background task.
    Wrap your hot-path call with this when you don't want to await."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(ora_learn(event_data))
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────
# ADMIN — Brain Growth tile data
# ─────────────────────────────────────────────────────────────────────

async def brain_growth_summary() -> Dict[str, Any]:
    """Counts + category breakdown for /admin/brain Brain Growth tile."""
    if _db is None:
        return {"total": 0, "categories": {}, "sources": []}
    from datetime import timedelta
    now = _now()
    try:
        total = await _db.ora_brain_thoughts.estimated_document_count()
        # New since 24h / 7d
        d1 = await _db.ora_brain_thoughts.count_documents({"ts": {"$gte": now - timedelta(days=1)}})
        d7 = await _db.ora_brain_thoughts.count_documents({"ts": {"$gte": now - timedelta(days=7)}})
        # Category breakdown over last 30d
        cur = _db.ora_brain_thoughts.aggregate([
            {"$match": {"ts": {"$gte": now - timedelta(days=30)}}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ])
        cat_rows = await cur.to_list(40)
        categories = {(r["_id"] or "uncategorized"): int(r["count"]) for r in cat_rows}
        # Active sources (last 24h)
        cur2 = _db.ora_brain_thoughts.aggregate([
            {"$match": {"ts": {"$gte": now - timedelta(days=1)}}},
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ])
        src_rows = await cur2.to_list(40)
        sources = [{"source": r["_id"] or "unknown", "count": int(r["count"])} for r in src_rows]
        # Latest thought
        latest = await _db.ora_brain_thoughts.find_one(
            {}, {"_id": 0, "ts": 1, "category": 1, "source": 1, "summary": 1},
            sort=[("ts", -1)],
        )
        if latest and isinstance(latest.get("ts"), datetime):
            latest["ts"] = latest["ts"].isoformat()
        return {
            "total": total,
            "new_24h": d1,
            "new_7d": d7,
            "categories": categories,
            "sources": sources,
            "active_sources_count": len(sources),
            "latest": latest,
        }
    except Exception as e:
        logger.warning(f"[ora-learn] brain_growth_summary failed: {e}")
        return {"total": 0, "categories": {}, "sources": [], "error": str(e)[:120]}
