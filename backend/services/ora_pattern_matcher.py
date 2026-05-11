"""
ORA Pattern Matcher — iter 322ar
==================================
Before escalating an issue to a paid LLM, ask: "Has ORA seen this kind
of issue before, AND did the previous fix work?"

Read-only against `db.fix_patterns` (populated by
`services.fix_learning_pipeline`).

Returns a decision dict the cost-tier router uses:

    {
      "ora_knows":      bool,
      "confidence":     0.0–1.0,
      "times_worked":   int,
      "suggested_fix":  {...} | None,
      "use_emergent":   bool,
    }
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.fix_learning_pipeline import fingerprint_issue

logger = logging.getLogger(__name__)

# Conservative thresholds — ORA only handles fixes it's seen succeed 3+
# times with ≥75% confidence. Lower bar = risky fixes; higher bar = wasted
# free path.
CONFIDENCE_FLOOR = 0.75
SUCCESS_FLOOR = 3

_db = None


def set_db(database) -> None:
    global _db
    _db = database


async def check_ora_knows(issue: Dict[str, Any]) -> Dict[str, Any]:
    if _db is None:
        return {"ora_knows": False, "use_emergent": True, "reason": "db_unavailable"}

    fp = fingerprint_issue(issue)
    try:
        row = await _db.fix_patterns.find_one(
            {
                "fingerprint": fp,
                "confidence": {"$gte": CONFIDENCE_FLOOR},
                "times_fixed_successfully": {"$gte": SUCCESS_FLOOR},
            },
            {"_id": 0},
        )
    except Exception as e:
        logger.warning(f"[ora-matcher] exact lookup failed: {e}")
        row = None

    if row:
        return {
            "ora_knows": True,
            "match_type": "exact",
            "fingerprint": fp,
            "confidence": float(row.get("confidence", 0)),
            "times_seen": int(row.get("times_seen", 0)),
            "times_worked": int(row.get("times_fixed_successfully", 0)),
            "suggested_fix": row.get("last_fix_applied"),
            "use_emergent": False,
        }

    # Same-agent same-evidence fallback (one bucket coarser): trust if
    # confidence ≥ 0.85 (we're guessing slightly, so demand more proof).
    try:
        sig = await _db.fix_patterns.find_one(
            {
                "issue_signature.agent": issue.get("agent") or issue.get("subject_agent"),
                "issue_signature.evidence_type": issue.get("evidence_type"),
                "confidence": {"$gte": 0.85},
                "times_fixed_successfully": {"$gte": SUCCESS_FLOOR + 2},
            },
            {"_id": 0},
            sort=[("confidence", -1)],
        )
    except Exception:
        sig = None

    if sig:
        return {
            "ora_knows": True,
            "match_type": "similar",
            "fingerprint": fp,
            "confidence": float(sig.get("confidence", 0)) * 0.9,  # soft-derate
            "times_seen": int(sig.get("times_seen", 0)),
            "times_worked": int(sig.get("times_fixed_successfully", 0)),
            "suggested_fix": sig.get("last_fix_applied"),
            "use_emergent": False,
        }

    return {
        "ora_knows": False,
        "match_type": "none",
        "fingerprint": fp,
        "use_emergent": True,
    }
