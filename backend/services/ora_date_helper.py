"""
ORA Date Header
================
Single source of truth for the "current date and time" block injected
into every ORA system prompt. Stops LLMs from drifting back to their
training-cutoff date (e.g. "January 22, 2025").

Used by:
- routers/aurem_chat.py (main chat endpoint, voice + text)
- routers/founders_console_router.py (Founders Console)
- services/morning_brief.py (LLM narrative generation)
- services/consortium_service.py (race-mode synthesizer)
"""
from __future__ import annotations

from datetime import datetime, timezone


def get_authoritative_date_block() -> str:
    """Return a date/time header that LLMs MUST treat as the current
    timestamp. Always Toronto (AUREM HQ); falls back to UTC if
    zoneinfo isn't available."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/Toronto"))
        tz_label = "Toronto"
    except Exception:
        now = datetime.now(timezone.utc)
        tz_label = "UTC"
    return (
        "CURRENT DATE AND TIME (authoritative — use this, do NOT use training data):\n"
        f"  Date: {now.strftime('%A, %B %d, %Y')}\n"
        f"  Time: {now.strftime('%I:%M %p')} {tz_label} time\n"
        f"  Day:  {now.strftime('%A')}\n"
        f"  ISO:  {now.isoformat()}\n"
        "When the user asks the date, day, time, year, 'today', 'aaj', "
        "'kya date hai', 'what's today' — use ONLY the values above. "
        "NEVER use your training cutoff. NEVER guess. "
        "If asked for a date in the past or future, calculate it from "
        "the value above.\n"
    )


def prepend_date(system_prompt: str) -> str:
    """Prepend the authoritative date block to a system prompt. The block
    sits at the TOP of the prompt so the LLM reads it before any
    competing 'as a language model my training cutoff is…' instinct."""
    return get_authoritative_date_block() + "\n" + (system_prompt or "")
