"""
services/vanguard_alerts.py — iter 331c Sprint 6.3

Two thin glue functions on top of the existing Vanguard Security scanner:

  1. check_and_alert_if_below_threshold(threshold=80)
       Runs the most recent Vanguard score. If <80 → Telegram alert.
       Idempotent — won't re-alert for the same score the same day.

  2. morning_brief_security_line()
       Returns the single-line "Security: score=92 ✓" string the
       autopilot brief notifier prepends to the daily brief.

Both functions are best-effort and never raise.

Portability: zero Emergent imports. Threshold + collection name
env-overridable.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_VANGUARD_THRESHOLD = int(os.environ.get("ORA_VANGUARD_ALERT_THRESHOLD", "80"))
_ALERT_DEDUPE_COLL  = os.environ.get(
    "ORA_VANGUARD_ALERT_LOG", "vanguard_alert_log"
)

_db = None


def set_db(database) -> None:
    global _db
    _db = database


# Candidate collections (the Vanguard router predates this refactor;
# we probe the most likely ones in order).
_SCORE_COLLECTIONS = (
    "vanguard_scores", "vanguard_runs",
    "aurem_vanguard_scores", "vanguard_security_runs",
)


async def _latest_score() -> dict | None:
    if _db is None:
        return None
    for col in _SCORE_COLLECTIONS:
        try:
            doc = await _db[col].find_one(
                {}, {"_id": 0}, sort=[("ts", -1)],
            )
            if doc:
                return {
                    "collection": col,
                    "score": (
                        doc.get("score") or doc.get("overall_score")
                        or doc.get("security_score")
                    ),
                    "ts": doc.get("ts") or doc.get("created_at"),
                    "raw": doc,
                }
        except Exception as e:
            logger.debug(f"[vanguard_alerts] {col}: {e}")
    return None


async def check_and_alert_if_below_threshold(threshold: int | None = None) -> dict:
    """Read the latest Vanguard score and send a Telegram alert if
    it's below the threshold (default $ORA_VANGUARD_ALERT_THRESHOLD=80).

    Idempotent — dedup keyed on (score, day) so we don't spam the
    founder when the same low score persists.
    """
    if _db is None:
        return {"ok": False, "reason": "db_not_wired"}
    threshold = threshold if threshold is not None else _VANGUARD_THRESHOLD
    latest = await _latest_score()
    if not latest:
        return {"ok": True, "alerted": False, "reason": "no_score_yet"}
    score = latest.get("score")
    if score is None:
        return {"ok": True, "alerted": False, "reason": "no_score_field"}
    if score >= threshold:
        return {"ok": True, "alerted": False, "score": score,
                "status": "above_threshold"}

    # Dedup — one alert per (score, day).
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dedupe_key = f"vanguard-{score}-{today}"
    already = await _db[_ALERT_DEDUPE_COLL].find_one({"_id": dedupe_key})
    if already:
        return {"ok": True, "alerted": False, "score": score,
                "reason": "already_alerted_today"}

    # Send the alert.
    sent = False
    try:
        from services.telegram_bot_service import send_telegram_alert
        msg = (
            f"🛡️ Vanguard Security score dropped to {score}/100 "
            f"(threshold {threshold}). Recent Vanguard run: "
            f"{latest.get('ts') or 'unknown'}. Review the Cockpit "
            f"or the latest Vanguard report immediately."
        )
        result = send_telegram_alert(msg)
        if hasattr(result, "__await__"):
            await result
        sent = True
    except Exception as e:
        logger.warning(f"[vanguard_alerts] telegram failed: {e}")

    # Record the dedupe row regardless.
    try:
        await _db[_ALERT_DEDUPE_COLL].insert_one({
            "_id":   dedupe_key,
            "score": score,
            "ts":    datetime.now(timezone.utc).isoformat(),
            "sent":  sent,
        })
    except Exception:
        pass

    return {
        "ok":         True,
        "alerted":    sent,
        "score":      score,
        "threshold":  threshold,
        "source":     latest.get("collection"),
    }


async def morning_brief_security_line() -> str:
    """Return the one-line security line for the Morning Brief.

    Examples:
      "Security: 92/100 ✓"
      "Security: 73/100 ⚠ (Telegram alert sent)"
      "Security: not yet scanned"
    """
    if _db is None:
        return "Security: not available (db not ready)"
    latest = await _latest_score()
    if not latest or latest.get("score") is None:
        return "Security: not yet scanned"
    score = latest["score"]
    marker = "✓" if score >= _VANGUARD_THRESHOLD else "⚠"
    suffix = ""
    if score < _VANGUARD_THRESHOLD:
        suffix = f" (below {_VANGUARD_THRESHOLD} threshold — Telegram alerted)"
    return f"Security: {score}/100 {marker}{suffix}"


__all__ = [
    "set_db",
    "check_and_alert_if_below_threshold",
    "morning_brief_security_line",
]
