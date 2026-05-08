"""
iter 282al-26 — ORA Sovereign Truth (Founder-only Anti-Sycophancy Mode)
========================================================================

Injects a **data-grounded** adversarial challenge into ORA's response when:
  1. The authenticated user is the founder, AND
  2. `admin_users.founder_prefs.sovereign_truth` is True, AND
  3. The detected intent is a strategy / decision / outreach / close / casl / followup.

When inactive, this module is a no-op (never touches the response).

Guardrails (hard-coded):
  - **No hallucinated negatives**: if no data-backed critique exists →
    return `"aligns with metrics, no objective friction detected"`.
  - **Sample-size honesty**: any metric cited from N<20 is prefixed
    "(early signal, small sample)".
  - **Actionable close**: every truth block ends with the best
    path-forward given the risks, not a downer.

Public API (all async, never raise)
-----------------------------------
    is_founder(user_id, email, db)              -> bool
    get_founder_prefs(db, user_id_or_email)     -> dict
    set_founder_prefs(db, user_id_or_email, **) -> dict
    is_strategy_intent(intent, message)         -> bool
    build_truth_block(db, message, intent, ctx) -> str
    augment_response(original, truth_block)     -> str
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Founder allowlist — single source of truth. Mirrors
# routers/admin_founder_customers_router.FOUNDER_EMAILS + PRD.
_FOUNDER_EMAILS = {
    (os.environ.get("FOUNDER_EMAIL") or "teji.ss1986@gmail.com").lower(),
    "admin@aurem.live",
}

_SNAPSHOT_FILE = (
    Path(__file__).resolve().parent.parent / "ora_skills"
    / "ora_knowledge_snapshot.md"
)

# Intents that always qualify as "decision" intents — already detected
# upstream by ora_god_mode._detect_intent.
_DECISION_INTENTS = frozenset({
    "outreach", "close", "casl", "followup", "strategy",
})

# Extra keyword-based detector for "strategy" questions that don't fall
# into the canonical intents (e.g. "should I launch this serum?").
_STRATEGY_PATTERNS = re.compile(
    r"\b("
    r"should\s+i|should\s+we|"
    r"worth\s+(?:it|the)|"
    r"approve(?:d|s|ing)?|"
    r"launch(?:ing)?|kill(?:ing)?|pivot(?:ing)?|"
    r"hire|fire|"
    r"pricing|bet\s+on|scale|double\s+down|"
    r"go\s+(?:hard|big|live)|cut\s+it|"
    r"ship\s+it"
    r")\b",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────
# Founder identity
# ─────────────────────────────────────────────────────────────────────
async def is_founder(
    user_id: Optional[str], email: Optional[str], db=None,
) -> bool:
    """True if JWT sub is on the founder allowlist. Accepts either id or email."""
    em = (email or "").strip().lower()
    if em and em in _FOUNDER_EMAILS:
        return True
    if not user_id or db is None:
        return False
    try:
        doc = await db.admin_users.find_one(
            {"$or": [{"id": user_id}, {"email": user_id}]},
            {"_id": 0, "email": 1, "role": 1},
        )
    except Exception:
        return False
    if not doc:
        return False
    if (doc.get("email") or "").lower() in _FOUNDER_EMAILS:
        return True
    return (doc.get("role") or "").lower() in ("founder", "owner")


# ─────────────────────────────────────────────────────────────────────
# Pref storage (admin_users.founder_prefs.sovereign_truth)
# ─────────────────────────────────────────────────────────────────────
async def get_founder_prefs(db, user_id_or_email: str) -> Dict[str, Any]:
    """Return {sovereign_truth: bool, ...}. Defaults to off."""
    defaults: Dict[str, Any] = {"sovereign_truth": False}
    if db is None or not user_id_or_email:
        return defaults
    try:
        doc = await db.admin_users.find_one(
            {"$or": [
                {"id": user_id_or_email},
                {"email": user_id_or_email.lower()},
            ]},
            {"_id": 0, "founder_prefs": 1},
        )
    except Exception:
        return defaults
    if not doc:
        return defaults
    prefs = doc.get("founder_prefs") or {}
    return {
        "sovereign_truth": bool(prefs.get("sovereign_truth")),
        **{k: v for k, v in prefs.items() if k != "sovereign_truth"},
    }


async def set_founder_prefs(
    db, user_id_or_email: str, **updates,
) -> Dict[str, Any]:
    """Upsert selected pref keys under `founder_prefs`. Never raises.

    Upserts the admin_users row keyed by email if not present. Callers are
    expected to have already verified `is_founder()` so upsert is safe.
    """
    if db is None or not user_id_or_email or not updates:
        return {"ok": False, "reason": "no_db_or_no_updates"}
    key = user_id_or_email.lower()
    _set = {f"founder_prefs.{k}": bool(v) if isinstance(v, bool) else v
            for k, v in updates.items()}
    _set["founder_prefs.updated_at"] = datetime.now(timezone.utc).isoformat()
    # Pick the right filter: if it looks like an email, match on email; else id.
    _filter = {"email": key} if "@" in key else {
        "$or": [{"id": user_id_or_email}, {"email": key}],
    }
    try:
        await db.admin_users.update_one(
            _filter,
            {
                "$set": _set,
                "$setOnInsert": {
                    "email": key if "@" in key else None,
                    "role": "founder",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"[sovereign_truth] pref save failed: {e}")
        return {"ok": False, "error": str(e)[:200]}
    return {"ok": True, "updated": list(updates.keys())}


# ─────────────────────────────────────────────────────────────────────
# Intent gating
# ─────────────────────────────────────────────────────────────────────
def is_strategy_intent(intent: Optional[str], message: Optional[str]) -> bool:
    """True if the question is a judgement/strategy ask (not a fact ask)."""
    if intent and intent.lower() in _DECISION_INTENTS:
        return True
    if not message:
        return False
    return bool(_STRATEGY_PATTERNS.search(message))


# ─────────────────────────────────────────────────────────────────────
# Data-backed critique builder
# ─────────────────────────────────────────────────────────────────────
_MIN_SAMPLE = 20  # below this → prefix "(early signal, small sample)"


def _sample_prefix(n: int) -> str:
    return "(early signal, small sample) " if n < _MIN_SAMPLE else ""


def _load_snapshot_body() -> str:
    try:
        if _SNAPSHOT_FILE.exists():
            return _SNAPSHOT_FILE.read_text(encoding="utf-8")[:3000]
    except Exception:
        pass
    return ""


async def _fetch_reply_rate_30d(db) -> Optional[Dict[str, Any]]:
    """Return {n, replies, rate_pct} or None."""
    if db is None:
        return None
    since = datetime.now(timezone.utc) - timedelta(days=30)
    try:
        rows = await db.outreach_history.find(
            {"sent_at": {"$gte": since}},
            {"_id": 0, "reply_received": 1},
        ).to_list(length=10000)
    except Exception:
        return None
    if not rows:
        return None
    n = len(rows)
    replies = sum(1 for r in rows if r.get("reply_received"))
    return {"n": n, "replies": replies,
            "rate_pct": round(100 * replies / max(1, n), 1)}


async def _fetch_casl_pass_30d(db) -> Optional[Dict[str, Any]]:
    if db is None:
        return None
    since = datetime.now(timezone.utc) - timedelta(days=30)
    try:
        rows = await db.casl_scores.find(
            {"ts": {"$gte": since}},
            {"_id": 0, "passed": 1},
        ).to_list(length=5000)
    except Exception:
        return None
    if not rows:
        return None
    n = len(rows)
    passed = sum(1 for r in rows if r.get("passed"))
    return {"n": n, "passed": passed,
            "pass_pct": round(100 * passed / max(1, n), 1)}


async def _fetch_site_score_30d(db) -> Optional[Dict[str, Any]]:
    if db is None:
        return None
    since = datetime.now(timezone.utc) - timedelta(days=30)
    try:
        rows = await db.site_audits.find(
            {"audit_ts": {"$gte": since}},
            {"_id": 0, "overall_score": 1},
        ).to_list(length=5000)
    except Exception:
        return None
    if not rows:
        return None
    n = len(rows)
    avg = sum(r.get("overall_score") or 0 for r in rows) // max(1, n)
    return {"n": n, "avg_score": avg}


async def build_truth_block(
    db,
    message: str,
    intent: Optional[str],
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """Return a self-contained '--- SOVEREIGN TRUTH ---' footer, or '' if no
    data-backed critique is available. Never raises. Never hallucinates."""
    if db is None:
        return ""
    metrics: List[str] = []

    reply = await _fetch_reply_rate_30d(db)
    if reply:
        pfx = _sample_prefix(reply["n"])
        # Reply rate only a *critique* if < 10% for outreach/close intents
        if intent in ("outreach", "close") and reply["rate_pct"] < 10:
            metrics.append(
                f"- {pfx}Last 30d reply rate is {reply['rate_pct']}% "
                f"({reply['replies']}/{reply['n']}). Below-industry. This plan "
                f"will likely compound low-signal sends — fix copy before scaling."
            )

    casl = await _fetch_casl_pass_30d(db)
    if casl and casl["pass_pct"] < 90:
        pfx = _sample_prefix(casl["n"])
        metrics.append(
            f"- {pfx}CASL pass rate is {casl['pass_pct']}% "
            f"({casl['passed']}/{casl['n']}). Under 90% means outbound risk — "
            f"every failing send is a regulatory exposure, not a marketing cost."
        )

    audit = await _fetch_site_score_30d(db)
    if audit and audit["avg_score"] < 50 and intent in (
        "outreach", "close", "strategy",
    ):
        pfx = _sample_prefix(audit["n"])
        metrics.append(
            f"- {pfx}Avg scouted site-score is {audit['avg_score']}/100. "
            f"Low scores = easy wins for our pitch, but also mean the buyers "
            f"don't prioritise digital — expect longer sales cycles."
        )

    # No data-backed critique → hard guardrail: do not invent friction.
    if not metrics:
        return (
            "\n\n--- SOVEREIGN TRUTH ---\n"
            "Aligns with current performance metrics. No objective friction "
            "detected in the last 30 days of data.\n"
        )

    # Path forward: always close constructively.
    path = "Recommended next move: address the single biggest friction above before execution."
    return (
        "\n\n--- SOVEREIGN TRUTH ---\n"
        + "\n".join(metrics)
        + f"\n\n{path}\n"
    )


def augment_response(original: str, truth_block: str) -> str:
    """Append the truth block. Idempotent — does not re-append on re-call."""
    if not truth_block:
        return original or ""
    if "--- SOVEREIGN TRUTH ---" in (original or ""):
        return original
    return (original or "").rstrip() + truth_block
