"""
Token Compression Middleware (iter 297 — P1 #2)
================================================
Rolling-summary layer for long ORA / Council / Founders-Console sessions.

When a session has > N_KEEP raw turns, compress everything older than the
last N_KEEP into a single structured summary block via Claude Sonnet 4.5.

Storage: `session_summaries` collection
  {session_id, scope, summary, turn_count, generated_at, source_model}

Public API:
  await compress_session(db, session_id, scope="founders_console", keep_last=8)
  await build_context(db, session_id, raw_msgs, scope, keep_last=8)
      → "<<SUMMARY>>...<<RECENT>>...turn1...turn2..." string ready to send to LLM
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_KEEP_LAST = 8
COMPRESS_TRIGGER = 12  # only compress when we have at least this many turns
SUMMARY_CHAR_BUDGET = 1400


async def _summarize_via_claude(turns: List[Dict[str, Any]]) -> Optional[str]:
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
    except Exception:
        return None
    transcript_lines: List[str] = []
    for t in turns:
        role = t.get("role", "?")
        msg = (t.get("message") or "")[:600]
        meta = []
        if t.get("intent"):
            meta.append(f"intent={t['intent']}")
        if t.get("decision"):
            meta.append(f"council={t['decision']}")
        if t.get("task_ids"):
            meta.append(f"tasks={len(t['task_ids'])}")
        suffix = f" [{', '.join(meta)}]" if meta else ""
        transcript_lines.append(f"{role}: {msg}{suffix}")
    transcript = "\n".join(transcript_lines)[:8000]
    try:
        chat = LlmChat(
            api_key=api_key,
            session_id=f"compress-{uuid.uuid4().hex[:8]}",
            system_message=(
                "You compress AUREM Founders-Console / Council deliberation logs. "
                "Output a TIGHT structured summary (≤ 1200 chars). Sections:\n"
                "DECISIONS: <bullet list of council verdicts + reasons>\n"
                "ACTIONS_TAKEN: <agent → task with ids>\n"
                "OPEN_LOOPS: <pending escalations / questions>\n"
                "FACTS: <numbers, lead_ids, domains TJ cares about>\n"
                "Skip pleasantries. No prose. No markdown headers other than these 4 keys."
            ),
        ).with_model("anthropic", "claude-sonnet-4.5").with_max_tokens(700)
        out = await asyncio.wait_for(
            chat.send_message(UserMessage(text=transcript)),
            timeout=10.0,
        )
        return (out or "").strip()[:SUMMARY_CHAR_BUDGET] or None
    except Exception as e:
        logger.debug(f"[compress] claude summary failed: {e}")
        return None


def _heuristic_summary(turns: List[Dict[str, Any]]) -> str:
    """Fallback when LLM unavailable — extracts decisions/intents/task_ids."""
    decisions: List[str] = []
    intents: List[str] = []
    tasks: List[str] = []
    for t in turns:
        if t.get("decision"):
            decisions.append(f"{t.get('intent','?')}:{t['decision']}")
        elif t.get("intent"):
            intents.append(t["intent"])
        if t.get("task_ids"):
            tasks.extend(t["task_ids"])
    parts = [
        f"DECISIONS: {', '.join(decisions[:10]) or '—'}",
        f"ACTIONS_TAKEN: {', '.join(tasks[:10]) or '—'}",
        "OPEN_LOOPS: —",
        f"FACTS: turns={len(turns)} intents={','.join(set(intents))[:120] or '—'}",
    ]
    return "\n".join(parts)[:SUMMARY_CHAR_BUDGET]


async def compress_session(
    db,
    session_id: str,
    raw_msgs: List[Dict[str, Any]],
    scope: str = "founders_console",
    keep_last: int = DEFAULT_KEEP_LAST,
) -> Optional[str]:
    """
    Compress all but the last `keep_last` turns into a stored summary.
    Returns the summary string (or None if no compression was needed).
    """
    if db is None or len(raw_msgs) < COMPRESS_TRIGGER:
        return None
    older = raw_msgs[:-keep_last] if keep_last > 0 else raw_msgs
    if not older:
        return None
    summary = await _summarize_via_claude(older) or _heuristic_summary(older)
    record = {
        "session_id": session_id,
        "scope": scope,
        "summary": summary,
        "turn_count": len(older),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_model": "claude-sonnet-4.5" if summary and len(summary) > 200 else "heuristic",
    }
    try:
        await db.session_summaries.update_one(
            {"session_id": session_id, "scope": scope},
            {"$set": record},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"[compress] persist failed: {e}")
    return summary


async def build_context(
    db,
    session_id: str,
    raw_msgs: List[Dict[str, Any]],
    scope: str = "founders_console",
    keep_last: int = DEFAULT_KEEP_LAST,
) -> str:
    """
    Returns a single context string with stored summary + last N turns,
    ready to inject into an LLM prompt. Triggers fresh compression when
    raw_msgs grows past the threshold.
    """
    summary: Optional[str] = None
    if db is not None:
        try:
            row = await db.session_summaries.find_one(
                {"session_id": session_id, "scope": scope}, {"_id": 0, "summary": 1, "turn_count": 1},
            )
            if row:
                summary = row.get("summary")
        except Exception:
            pass

    # Refresh summary if many uncompressed turns
    if len(raw_msgs) >= COMPRESS_TRIGGER:
        new_sum = await compress_session(db, session_id, raw_msgs, scope=scope, keep_last=keep_last)
        if new_sum:
            summary = new_sum

    recent = raw_msgs[-keep_last:] if keep_last > 0 else raw_msgs
    recent_lines = [
        f"{t.get('role','?')}: {(t.get('message') or '')[:400]}" for t in recent
    ]
    parts: List[str] = []
    if summary:
        parts.append("<<SUMMARY>>\n" + summary)
    parts.append("<<RECENT>>\n" + "\n".join(recent_lines))
    return "\n\n".join(parts)
