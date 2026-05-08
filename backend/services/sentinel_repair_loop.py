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

# iter 322 — AI-diagnose budget per cycle. Claude is paid per-call so we
# cap the number of UNIQUE signatures we diagnose autonomously per tick.
# Manual admin clicks remain unlimited (separate route).
AI_DIAGNOSE_BUDGET_PER_CYCLE = int(os.environ.get(
    "SENTINEL_AI_DIAGNOSE_BUDGET", "5",
))


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


async def _diagnose_one_ai_eligible(
    db, sig_doc: Dict[str, Any],
) -> Dict[str, Any]:
    """A2A → Council → ORA pipeline for ONE unique unhealed signature whose
    classification is AI-eligible (e.g. real `backend_5xx`). Calls Claude via
    `services.sentinel_ai_diagnose.diagnose_and_store`, persists the
    suggestion, emits learning events. Returns outcome metadata.
    """
    classification = sig_doc.get("classification") or "unknown"
    error_id = sig_doc.get("error_id") or ""
    signature = sig_doc.get("signature") or ""

    # 1) A2A — visibility on the live feed
    await _emit_a2a(
        "sentinel",
        "AI_DIAGNOSE_PICKED",
        {
            "error_id": error_id,
            "signature": signature,
            "classification": classification,
            "url": (sig_doc.get("url") or "")[:120],
        },
    )

    # 2) Council deliberate — gate the LLM spend
    verdict = "APPROVED"
    try:
        from services.council_deliberate import deliberate
        result = await deliberate(
            action=f"sentinel_ai_diagnose:{classification}",
            agent="sentinel",
            payload={
                "error_id": error_id,
                "signature": signature,
                "classification": classification,
            },
            required=["qa", "security"],
            advisory=["casl"],
        )
        verdict = result.get("verdict", "APPROVED")
    except Exception as e:
        logger.warning(f"[SentinelRepair] AI-diagnose council unavailable: {e}")

    if verdict != "APPROVED":
        await _emit_a2a(
            "council",
            "AI_DIAGNOSE_REJECTED",
            {"error_id": error_id, "verdict": verdict, "signature": signature},
        )
        # Mark all errors with this signature as rejected so we don't burn
        # tokens re-trying next cycle.
        try:
            await db.client_errors.update_many(
                {"signature": signature, "status": "new"},
                {"$set": {"status": "council_rejected"}},
            )
        except Exception:
            pass
        return {"signature": signature, "outcome": "council_rejected"}

    # 3) APPROVED — call Claude via the shared service
    try:
        from services.sentinel_ai_diagnose import diagnose_and_store
        suggestion = await diagnose_and_store(
            db, sig_doc, source="autonomous_a2a"
        )
    except Exception as e:
        logger.warning(f"[SentinelRepair] AI diagnose failed sig={signature}: {e}")
        await _emit_a2a(
            "sentinel",
            "AI_DIAGNOSE_FAILED",
            {"signature": signature, "error": f"{type(e).__name__}: {str(e)[:120]}"},
        )
        return {"signature": signature, "outcome": "diagnose_failed"}

    # 4) ORA learning — feed the brain
    await _emit_a2a(
        "ora",
        "ORA_DIAGNOSED",
        {
            "signature": signature,
            "classification": classification,
            "suggestion_id": (suggestion or {}).get("suggestion_id"),
            "severity": (suggestion or {}).get("severity"),
            "confidence": (suggestion or {}).get("confidence"),
        },
    )
    await _record_ora_learning(sig_doc, outcome="ai_diagnosed")

    return {
        "signature": signature,
        "outcome": "ai_diagnosed",
        "suggestion_id": (suggestion or {}).get("suggestion_id"),
        "severity": (suggestion or {}).get("severity"),
    }


async def _run_ai_diagnose_pass(db) -> Dict[str, Any]:
    """Find up to N UNIQUE unhealed AI-eligible signatures and run them
    through the council + Claude diagnose pipeline. Token-bounded by
    AI_DIAGNOSE_BUDGET_PER_CYCLE.
    """
    if AI_DIAGNOSE_BUDGET_PER_CYCLE <= 0:
        return {"diagnosed": 0, "skipped_existing": 0, "rejected": 0}

    cutoff = datetime.now(timezone.utc).timestamp() - (MAX_AGE_HOURS * 3600)

    # Aggregate: top unique signatures with status=new + ai_eligible + no
    # auto_heal_key (auto_heal queue handled separately above).
    pipeline = [
        {"$match": {
            "status": "new",
            "ai_eligible": True,
            "$or": [
                {"auto_heal_key": {"$in": [None, ""]}},
                {"auto_heal_key": {"$exists": False}},
            ],
        }},
        {"$sort": {"ts": -1}},
        {"$group": {
            "_id": "$signature",
            "doc": {"$first": "$$ROOT"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"count": -1}},
        {"$limit": AI_DIAGNOSE_BUDGET_PER_CYCLE * 3},  # over-fetch for dedup
    ]

    candidates: List[Dict[str, Any]] = []
    try:
        async for row in db.client_errors.aggregate(pipeline):
            doc = row.get("doc") or {}
            sig = doc.get("signature") or row.get("_id")
            if not sig:
                continue
            # Skip if a pending suggestion already exists for this sig.
            existing = await db.repair_suggestions.find_one(
                {"source_signature": sig, "status": "pending"}, {"_id": 1},
            )
            if existing:
                continue
            # Age check
            try:
                ts = doc.get("ts") or ""
                ts_ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                if ts_ts < cutoff:
                    continue
            except Exception:
                pass
            candidates.append(doc)
            if len(candidates) >= AI_DIAGNOSE_BUDGET_PER_CYCLE:
                break
    except Exception as e:
        logger.warning(f"[SentinelRepair] AI-diagnose aggregate failed: {e}")
        return {"diagnosed": 0, "skipped_existing": 0, "rejected": 0, "error": str(e)[:120]}

    diagnosed = 0
    rejected = 0
    failed = 0
    for doc in candidates:
        outcome = await _diagnose_one_ai_eligible(db, doc)
        out = outcome.get("outcome")
        if out == "ai_diagnosed":
            diagnosed += 1
        elif out == "council_rejected":
            rejected += 1
        else:
            failed += 1

    return {
        "diagnosed": diagnosed,
        "rejected": rejected,
        "failed": failed,
        "candidates_seen": len(candidates),
    }


async def run_sentinel_repair_cycle() -> Dict[str, Any]:
    """One full cycle: pull NEW errors → loop → mark healed/rejected."""
    db = _get_db()
    if db is None:
        return {"ok": False, "reason": "db_unavailable"}

    cutoff = datetime.now(timezone.utc).timestamp() - (MAX_AGE_HOURS * 3600)
    started = datetime.now(timezone.utc).isoformat()

    # Pull a small batch of unprocessed errors (status=new, ai_eligible).
    # iter 322 — restrict to docs with a NON-EMPTY string auto_heal_key so
    # `null` / missing values fall through to the AI-diagnose pass below.
    cursor = (
        db.client_errors
        .find(
            {
                "status": "new",
                "ai_eligible": True,
                "auto_heal_key": {"$type": "string", "$ne": ""},
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

    # iter 322 — autonomous AI-diagnose pass: surface real backend_5xx
    # signatures (no auto-heal pattern) to Claude via Council gating.
    ai_summary = {"diagnosed": 0, "rejected": 0, "failed": 0}
    try:
        ai_summary = await _run_ai_diagnose_pass(db)
    except Exception as e:
        logger.warning(f"[SentinelRepair] AI-diagnose pass failed: {e}")

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
        "ai_diagnose": ai_summary,
    }
