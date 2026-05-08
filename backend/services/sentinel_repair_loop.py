"""
sentinel_repair_loop.py — Self-healing pipeline.

Flow:
    Sentinel client_errors (NEW)
        → A2A bus emit  (visibility on Admin Command Center live feed)
        → Council deliberate (CASL + QA vote on whether to auto-fix)
        → APPROVED → apply known fix from auto_repair.AUTO_HEAL_PATTERNS
                  → emit ORA_LEARNING event so the brain ingests the pattern
                  → mark error as "auto-healed"
        → REJECTED → stays in queue for human review (admin/sentinel UI)

Runs every 60s as an APScheduler job. Idempotent via the `status` field on
each client_errors row (only "new" docs are picked up; healed ones go to
"auto_healed", rejected ones to "council_rejected").
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Map sentinel auto_heal_key → human-readable repair action label
# (used by Council so its CASL/QA voters see meaningful context).
AUTO_HEAL_LABELS: Dict[str, str] = {
    "auth_token_expired":   "client_re_login_prompt",
    "rate_limit_exceeded":  "client_throttle_backoff",
    "validation_failed":    "client_field_hint",
    "resource_not_found":   "client_navigate_safely",
    "casl_consent":         "client_show_consent_modal",
    "webhook_unreachable":  "ops_alert_webhook_down",
    "backend_5xx":          "ops_alert_backend_5xx",
    "network_failure":      "client_offline_banner",
}

POLL_LIMIT = 25          # max errors handled per cycle (avoid overwhelming the bus)
MAX_AGE_HOURS = 24       # ignore errors older than this — they're stale


def _get_db():
    """Late-binding DB resolver — keeps this module import-time safe even
    when MONGO_URL is slow on Atlas."""
    try:
        from server import db  # type: ignore
        return db
    except Exception:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            url = os.environ.get("MONGO_URL")
            if not url:
                return None
            return AsyncIOMotorClient(url)[os.environ.get("DB_NAME", "aurem_db")]
        except Exception as e:
            logger.warning(f"[SentinelRepair] db unavailable: {e}")
            return None


async def _emit_a2a(from_agent: str, event: str, payload: Dict[str, Any]) -> None:
    try:
        from services.a2a_bus import bus
        await bus.emit(from_agent, event, payload)
    except Exception as e:
        logger.debug(f"[SentinelRepair] A2A emit skipped: {e}")


async def _record_ora_learning(error_doc: Dict[str, Any], outcome: str) -> None:
    """Append a learning row so ORA's nightly knowledge sweep picks it up."""
    db = _get_db()
    if db is None:
        return
    try:
        await db.ora_brain_thoughts.insert_one({
            "type": "sentinel_pattern",
            "source": "sentinel_repair_loop",
            "classification": error_doc.get("classification"),
            "auto_heal_key": error_doc.get("auto_heal_key"),
            "signature": error_doc.get("signature"),
            "outcome": outcome,
            "url": (error_doc.get("url") or "")[:200],
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.debug(f"[SentinelRepair] ora_brain_thoughts insert skipped: {e}")


async def _heal_one(error_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Run one error through the A2A → Council → ORA loop."""
    classification = error_doc.get("classification") or "unknown"
    auto_heal_key = error_doc.get("auto_heal_key") or ""
    error_id = error_doc.get("error_id") or str(error_doc.get("_id"))

    # 1) Emit on A2A so the live feed shows it being handled
    await _emit_a2a(
        "sentinel",
        "ERROR_PICKED_UP",
        {
            "error_id": error_id,
            "classification": classification,
            "auto_heal_key": auto_heal_key,
            "url": (error_doc.get("url") or "")[:120],
        },
    )

    action_label = AUTO_HEAL_LABELS.get(auto_heal_key, "noop_log_only")

    # 2) Council deliberation — REJECTED errors stay queued for human review
    verdict = "APPROVED"
    council_payload = {"error_id": error_id, "classification": classification}
    try:
        from services.council_deliberate import deliberate
        result = await deliberate(
            action=f"sentinel_auto_repair:{action_label}",
            agent="sentinel",
            payload=council_payload,
            required=["casl", "qa"],
            advisory=["security"],
        )
        verdict = result.get("verdict", "APPROVED")
    except Exception as e:
        # Council unavailable → don't block recovery; log and proceed
        logger.warning(f"[SentinelRepair] council unavailable: {e}")

    if verdict != "APPROVED":
        await _emit_a2a(
            "council",
            "ERROR_REJECTED_FOR_AUTO_REPAIR",
            {"error_id": error_id, "verdict": verdict},
        )
        await _record_ora_learning(error_doc, outcome="council_rejected")
        return {"error_id": error_id, "outcome": "council_rejected", "verdict": verdict}

    # 3) APPROVED — apply the known fix (frontend-facing fixes are advisory
    #    metadata; backend-facing fixes call into auto_repair.apply_known_fix)
    fix_outcome: Dict[str, Any] = {"applied": False}
    try:
        if action_label.startswith("ops_alert_"):
            from services.auto_repair import apply_known_fix
            fix_outcome = await apply_known_fix(
                fix_name=action_label,
                fix_data={"error_id": error_id},
                error_text=str(error_doc.get("message", ""))[:300],
            )
    except Exception as e:
        logger.warning(f"[SentinelRepair] apply_known_fix failed for {action_label}: {e}")
        fix_outcome = {"applied": False, "error": f"{type(e).__name__}: {e}"}

    # 4) Emit ORA learning — so ORA brain ingests the auto-heal pattern
    await _emit_a2a(
        "ora",
        "ORA_LEARNING_INGESTED",
        {
            "error_id": error_id,
            "classification": classification,
            "auto_heal_key": auto_heal_key,
            "fix_applied": bool(fix_outcome.get("applied")),
        },
    )
    await _record_ora_learning(error_doc, outcome="auto_healed")

    return {
        "error_id": error_id,
        "outcome": "auto_healed",
        "verdict": verdict,
        "fix_applied": bool(fix_outcome.get("applied")),
    }


async def run_sentinel_repair_cycle() -> Dict[str, Any]:
    """One full cycle: pull NEW errors → loop → mark healed/rejected."""
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db_unavailable"}

    cutoff = datetime.now(timezone.utc).timestamp() - (MAX_AGE_HOURS * 3600)
    started = datetime.now(timezone.utc).isoformat()

    # Pull a small batch of unprocessed errors (status=new, ai_eligible).
    cursor = (
        db.client_errors
        .find(
            {
                "status": "new",
                "ai_eligible": True,
                "auto_heal_key": {"$exists": True, "$ne": ""},
            },
            {"_id": 1, "error_id": 1, "classification": 1, "auto_heal_key": 1,
             "signature": 1, "url": 1, "message": 1, "ts": 1},
        )
        .sort("ts", -1)
        .limit(POLL_LIMIT)
    )

    handled: List[Dict[str, Any]] = []
    skipped = 0
    async for doc in cursor:
        # Age check — silently skip stale ones
        try:
            ts = doc.get("ts") or ""
            ts_ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
            if ts_ts < cutoff:
                skipped += 1
                continue
        except Exception:
            pass

        outcome = await _heal_one(doc)

        # Update the error row so it isn't re-processed.
        new_status = (
            "auto_healed" if outcome.get("outcome") == "auto_healed"
            else "council_rejected"
        )
        try:
            await db.client_errors.update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    "status": new_status,
                    "outcome": outcome,
                    "healed_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
        except Exception as e:
            logger.debug(f"[SentinelRepair] update skipped: {e}")
        handled.append(outcome)

    return {
        "ok": True,
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "handled": len(handled),
        "skipped_stale": skipped,
        "by_outcome": {
            "auto_healed": sum(1 for h in handled if h.get("outcome") == "auto_healed"),
            "council_rejected": sum(1 for h in handled if h.get("outcome") == "council_rejected"),
        },
    }
