"""
services/prompt_injection_guard.py — iter 329e

Detects the most common prompt-injection / jailbreak patterns in user
input. Used by `ora_agent.run_turn` to block the request BEFORE any
LLM call is made. Adversary never gets to see the system prompt or
fool ORA into role-playing.

Public API
──────────
    classify(text) → ("clean", None) | ("blocked", reason_str)

`blocked` ⇒ caller MUST refuse the turn and reply with a stock
"I can't process that request" message. Block is logged to
`db.prompt_injection_blocks` and Telegram'd via silent_failure_alerts.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Patterns are intentionally narrow — they're written to match the
# adversarial PHRASES the founder listed, not arbitrary keywords. False
# positives would hurt legitimate use ("ignore that, what's the price?"
# is fine).
_INJECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("ignore_previous_instructions",
     re.compile(r"\bignore\b.{0,40}\b(previous|prior|earlier|above)\b.{0,40}\binstruction", re.IGNORECASE)),
    ("you_are_now_different",
     re.compile(r"\byou\s+are\s+now\b.{0,30}\b(a|an|the)?\s*(different|new|other)\s+(ai|assistant|bot|agent|model)\b", re.IGNORECASE)),
    ("forget_your_rules",
     re.compile(r"\bforget\b.{0,30}\b(your|the|all)?\s*(rules|instructions|guidelines|system\s*prompt)\b", re.IGNORECASE)),
    ("pretend_you_are",
     re.compile(r"\bpretend\b.{0,20}\byou\s+(?:are|were|to\s+be)\b", re.IGNORECASE)),
    ("real_instructions_are",
     re.compile(r"\b(your|the)\s+real\s+instructions\b", re.IGNORECASE)),
    # Common "DAN" / "developer mode" jailbreak templates.
    ("dan_mode",
     re.compile(r"\b(dan\s+mode|developer\s+mode|jailbreak\s+mode)\b", re.IGNORECASE)),
    # Disclosing the system prompt
    ("reveal_system_prompt",
     re.compile(r"\b(reveal|show|print|leak|dump)\b.{0,30}\b(system\s*prompt|instructions|rules)\b", re.IGNORECASE)),
]

# The fixed reply we hand back to the caller. Plain English per Rule
# Zero — no jargon, no triggers in the response that would reinforce
# the attempt.
BLOCK_REPLY = "I can't process that request."


def classify(text: str) -> tuple[str, str | None]:
    """Return ('blocked', pattern_name) or ('clean', None)."""
    if not text or not isinstance(text, str):
        return "clean", None
    for name, pat in _INJECTION_PATTERNS:
        if pat.search(text):
            return "blocked", name
    return "clean", None


async def record_and_alert_block(
    db,
    *,
    text: str,
    pattern: str,
    session_id: str | None = None,
    founder_email: str | None = None,
) -> None:
    """Persist the attempt to Mongo and fire a Telegram alert.

    Best-effort — failure to record never blocks the response path.
    """
    if db is None:
        return
    from datetime import datetime, timezone
    try:
        await db.prompt_injection_blocks.insert_one({
            "ts":            datetime.now(timezone.utc),
            "pattern":       pattern,
            "session_id":    session_id,
            "founder_email": founder_email,
            "text_excerpt":  (text or "")[:500],
        })
    except Exception as e:
        logger.debug(f"[injection-guard] persist failed: {e}")
    try:
        from services.silent_failure_alerts import _send as _tg
        excerpt = (text or "").strip()[:120]
        await _tg(
            f"🛡️ Prompt-injection blocked — pattern `{pattern}` "
            f"session={session_id or '-'} excerpt={excerpt!r}",
            fingerprint=f"prompt_injection_{pattern}_{(session_id or 'na')[:24]}",
        )
    except Exception as e:
        logger.debug(f"[injection-guard] alert failed: {e}")
