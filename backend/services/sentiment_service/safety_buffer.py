"""
Safety Buffer — Panic Hook Migration Guard

Prevents false UI 'flicker' and spurious Panic Hooks during
Phase C migration. Scores between -0.7 and -0.9 are buffered
unless sustained across 3+ consecutive calls.

Source: /app/memory/safety_buffer_and_execution_auth.md
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)

# Track sustained negative scores per conversation
_sustained_scores: Dict[str, int] = {}
SUSTAINED_THRESHOLD = 3


def safety_buffer_check(
    sentiment_score: float,
    mode: str = "MIGRATION",
    conversation_id: str = "",
) -> bool:
    """
    Returns True if a Panic Hook should fire, False if buffered.

    Rules:
      MIGRATION mode:
        - Score < -0.9  -> always fire (absolute panic)
        - Score between -0.7 and -0.9 -> fire only if sustained 3+ calls
        - Score >= -0.7  -> buffer (no fire)
      NORMAL mode:
        - Standard threshold at -0.8
    """
    if mode != "MIGRATION":
        return sentiment_score < -0.8

    # Absolute panic — always fire
    if sentiment_score < -0.9:
        _sustained_scores.pop(conversation_id, None)
        return True

    # Buffered zone (-0.7 to -0.9): require sustained signal
    if sentiment_score < -0.7:
        count = _sustained_scores.get(conversation_id, 0) + 1
        _sustained_scores[conversation_id] = count
        if count >= SUSTAINED_THRESHOLD:
            _sustained_scores.pop(conversation_id, None)
            logger.warning(
                f"[SafetyBuffer] Sustained panic for {conversation_id} "
                f"({count} consecutive hits)"
            )
            return True
        return False

    # Score >= -0.7: reset counter, no fire
    _sustained_scores.pop(conversation_id, None)
    return False
