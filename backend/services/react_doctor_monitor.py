"""
services/react_doctor_monitor.py — runtime guardian over React Doctor
frontend scores. Iter 325f Phase 5.

Currently the only place React Doctor runs is the GitHub Actions
workflow (`.github/workflows/react-doctor.yml`). This module gives the
score a runtime presence:

  1. CI uploads its score to `/api/admin/react-doctor/ingest` (added
     via the existing system_overview_router family, but we don't add
     a new endpoint here — operators can just `mongo insert` for now
     or wire the upload in a follow-up PR).
  2. Weekly cron (registry.py) reads `db.react_doctor_runs`, compares
     the latest score against the previous run.
  3. A drop of more than 5 points → incident_bus emit (severity=medium).
  4. An absolute score < 50 → Telegram founder alert.

Collection schema (db.react_doctor_runs):
  score : int (0-100)
  diagnostics_count : int
  branch : str
  commit_sha : str (short)
  ts : ISO timestamp
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

DROP_THRESHOLD = int(os.environ.get("REACT_DOCTOR_DROP_THRESHOLD", "5"))
ABS_ALERT = int(os.environ.get("REACT_DOCTOR_ABS_ALERT", "50"))


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


async def react_doctor_monitor_tick(db=None) -> Dict[str, Any]:
    db = db or _get_db()
    if db is None:
        return {"ok": False, "error": "db_unavailable"}

    cursor = db.react_doctor_runs.find({}, {"_id": 0}).sort("ts", -1).limit(2)
    rows = []
    async for r in cursor:
        rows.append(r)
    if not rows:
        return {"ok": True, "reason": "no_runs"}

    latest = rows[0]
    prev = rows[1] if len(rows) > 1 else None
    score = int(latest.get("score") or 0)
    prev_score = int(prev.get("score") or 0) if prev else None
    drop = (prev_score - score) if prev_score is not None else 0

    incident_emitted = False
    if drop > DROP_THRESHOLD:
        try:
            from services import incident_bus
            await incident_bus.report(
                category="frontend_regression",
                signature=f"react_doctor:drop:{latest.get('commit_sha', 'unknown')}",
                severity="medium",
                source="react_doctor_monitor",
                title=f"React Doctor score dropped {drop} points ({prev_score} → {score})",
                detail=f"Latest run on {latest.get('branch','?')}@{latest.get('commit_sha','?')}. "
                       f"Diagnostics: {latest.get('diagnostics_count')}.",
                metadata={"prev": prev_score, "now": score, "drop": drop,
                          "branch": latest.get("branch")},
                actor="react_doctor_monitor",
            )
            incident_emitted = True
        except Exception as e:
            logger.warning(f"[react_doctor_monitor] incident emit failed: {e}")

    telegram_sent = False
    if score < ABS_ALERT:
        try:
            from services.telegram_bot_service import send_telegram_alert
            tg = await send_telegram_alert(
                message=(
                    f"React Doctor score is {score}/100 (threshold {ABS_ALERT}).\n"
                    f"Latest commit: {latest.get('commit_sha','?')} on "
                    f"{latest.get('branch','?')}.\n\n"
                    f"Reviewing this is now P1 to prevent a deploy-time CI block."
                ),
                alert_type="react_doctor_low",
                fingerprint=f"react_doctor:{latest.get('commit_sha','unknown')}",
            )
            telegram_sent = bool(tg.get("ok"))
        except Exception as e:
            logger.debug(f"[react_doctor_monitor] telegram skipped: {e}")

    return {
        "ok": True,
        "score": score,
        "prev_score": prev_score,
        "drop": drop,
        "incident_emitted": incident_emitted,
        "telegram_sent": telegram_sent,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
