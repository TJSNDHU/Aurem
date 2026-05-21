"""
services/qa_guardian.py — pattern guardian over QA Bot pulse runs
(iter 325f Phase 3b).

QA Bot already emits per-failure rows to db.qa_bot_endpoint_log. The
guardian groups by endpoint and detects "same endpoint failed 3+ runs
in a row" — a stronger signal than the 2-run alert that QA Bot already
sends. When that happens, the guardian:

  1. Emits to incident_bus with `auto_fixable=True` metadata so the
     downstream triage/repair stack can fire restart playbooks.
  2. Records the streak escalation in db.qa_guardian_alerts.

Intended call site: end of `services/qa_bot.run_pulse_once()` (after
_maybe_alert finishes).

Collection written:
  db.qa_guardian_alerts  — every escalation, 24h history
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# How many consecutive pulse runs an endpoint can fail before the
# guardian escalates. QA Bot itself alerts at 2; we escalate at 3+
# because by then "same problem, multiple cycles" looks systemic.
STREAK_ESCALATE = 3
LOOKBACK_HOURS = 6


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


async def _last_n_runs_failed_consecutively(db, endpoint_id: str, n: int) -> bool:
    """True iff the most recent N rows for this endpoint all failed."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).isoformat()
    cursor = db.qa_bot_endpoint_log.find(
        {"endpoint_id": endpoint_id, "ts": {"$gte": cutoff}},
        {"_id": 0, "passed": 1, "ts": 1},
    ).sort("ts", -1).limit(n)
    rows: List[Dict[str, Any]] = []
    async for r in cursor:
        rows.append(r)
    if len(rows) < n:
        return False
    return all(not r.get("passed") for r in rows)


async def run_guardian_tick(db=None) -> Dict[str, Any]:
    """Inspect every endpoint that failed in the most recent pulse run
    and emit incident_bus + record an escalation for any endpoint with a
    STREAK_ESCALATE-run failure streak."""
    db = db or _get_db()
    if db is None:
        return {"ok": False, "error": "db_unavailable"}

    # Pull the most recent pulse row to know which endpoints were checked.
    latest = await db.qa_bot_runs.find_one({}, sort=[("ts", -1)])
    if not latest:
        return {"ok": True, "escalations": 0, "reason": "no_pulse_rows"}

    failing = [c["id"] for c in (latest.get("checks") or []) if not c.get("passed")]
    if not failing:
        return {"ok": True, "escalations": 0, "reason": "no_failures"}

    escalations: List[str] = []
    for ep_id in failing:
        try:
            if await _last_n_runs_failed_consecutively(db, ep_id, STREAK_ESCALATE):
                escalations.append(ep_id)
        except Exception as e:
            logger.debug(f"[qa_guardian] streak check failed for {ep_id}: {e}")

    for ep_id in escalations:
        # Idempotency — one escalation row per (endpoint, calendar hour).
        bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H")
        try:
            await db.qa_guardian_alerts.update_one(
                {"endpoint_id": ep_id, "bucket": bucket},
                {"$setOnInsert": {
                    "endpoint_id": ep_id,
                    "bucket": bucket,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "streak": STREAK_ESCALATE,
                }},
                upsert=True,
            )
        except Exception as e:
            logger.debug(f"[qa_guardian] alert write failed: {e}")

        try:
            from services import incident_bus
            await incident_bus.report(
                category="endpoint_failure",
                signature=f"qa_guardian:{ep_id}:streak_{STREAK_ESCALATE}",
                severity="high",
                source="qa_guardian",
                title=f"QA Guardian: {ep_id} failed {STREAK_ESCALATE}+ consecutive runs",
                detail=f"Endpoint has been red for at least {STREAK_ESCALATE} pulse sweeps. Restart playbook recommended.",
                metadata={"endpoint_id": ep_id, "auto_fixable": True,
                          "streak_threshold": STREAK_ESCALATE},
                actor="qa_guardian",
            )
        except Exception as e:
            logger.warning(f"[qa_guardian] incident emit failed: {e}")

    return {"ok": True, "escalations": len(escalations),
            "endpoint_ids": escalations}
