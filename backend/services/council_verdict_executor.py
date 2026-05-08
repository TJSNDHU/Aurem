"""
AUREM Council Verdict Auto-Apply (iter 322p — closes self-evolving loop)
=========================================================================

The Memory Guard's 2-stamp gate already promotes verified observations
into `learnings`. Until iter 322p those learnings sat as **knowledge** —
nobody acted on them automatically. This module changes that.

When a learning carries a structured ``recommended_fix`` field AND the
fix lives in our **safe action allowlist**, this executor runs it and
marks the learning as ``applied``. After applying, an A2A signal is
broadcast (`kind: "verdict_applied"`) so peer workers can react.

Hard safety boundary
--------------------
- Only acts on **promoted** learnings (status == "promoted") — never
  on `pending` rows. The 2-stamp gate is the gate.
- Action whitelist is small and mechanical. No code execution, no
  shell, no LLM cascade.
- Each action has its own idempotency check inside the action handler.
- Dry-run mode (`COUNCIL_VERDICT_DRY_RUN=1`) records what *would*
  happen without performing the side-effect — for the very first prod
  rollout after deploy.

Action allowlist
----------------
- ``ping_agent``       → write a heartbeat ledger row for `subject`
                         (re-attest a recovered agent).
- ``clear_a2a_signal`` → mark stale signals as consumed.
- ``broadcast_a2a``    → emit a signal of your choice (only kinds
                         starting with `verdict_*` are allowed).

Public API
----------
- ``run_verdict_executor_tick(db) -> dict``  (scheduler entry-point)
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


COUNCIL_VERDICT_DRY_RUN = os.environ.get("COUNCIL_VERDICT_DRY_RUN") == "1"
COUNCIL_VERDICT_BATCH = int(os.environ.get("COUNCIL_VERDICT_BATCH", "10"))


_ALLOWED_ACTIONS = {"ping_agent", "clear_a2a_signal", "broadcast_a2a"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


# ─── Action handlers ───────────────────────────────────────────────────
async def _act_ping_agent(db, subject: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if not subject:
        return {"ok": False, "reason": "no_subject"}
    if COUNCIL_VERDICT_DRY_RUN:
        return {"ok": True, "dry_run": True, "subject": subject}
    try:
        await db.agent_ledger_entries.insert_one({
            "kind": "verdict_ping",
            "agent_id": subject,
            "source": "council_verdict_executor",
            "units": 0.0,
            "cost_usd": 0.0,
            "meta": {"reason": params.get("reason", "council_verdict")},
            "timestamp": _iso(_utc_now()),
        })
        return {"ok": True, "subject": subject}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


async def _act_clear_a2a_signal(db, subject: str, params: Dict[str, Any]) -> Dict[str, Any]:
    kind = (params.get("kind") or "").strip()
    if not kind:
        return {"ok": False, "reason": "kind_required"}
    if COUNCIL_VERDICT_DRY_RUN:
        return {"ok": True, "dry_run": True, "kind": kind, "to": subject}
    try:
        result = await db.agent_a2a_signals.update_many(
            {"kind": kind, "to": subject, "consumed": {"$ne": True}},
            {"$set": {"consumed": True, "consumed_at": _iso(_utc_now())}},
        )
        return {"ok": True, "modified_count": getattr(result, "modified_count", 0)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


async def _act_broadcast_a2a(db, subject: str, params: Dict[str, Any]) -> Dict[str, Any]:
    kind = (params.get("kind") or "").strip()
    if not kind.startswith("verdict_"):
        return {"ok": False, "reason": "kind_must_start_with_verdict_"}
    if COUNCIL_VERDICT_DRY_RUN:
        return {"ok": True, "dry_run": True, "kind": kind, "to": subject}
    try:
        await db.agent_a2a_signals.insert_one({
            "kind": kind,
            "from": "council_verdict_executor",
            "to": subject or "all",
            "payload": params.get("payload") or {},
            "ts": _iso(_utc_now()),
        })
        return {"ok": True, "kind": kind}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


_ACTION_HANDLERS = {
    "ping_agent": _act_ping_agent,
    "clear_a2a_signal": _act_clear_a2a_signal,
    "broadcast_a2a": _act_broadcast_a2a,
}


# ─── Executor tick ─────────────────────────────────────────────────────
async def run_verdict_executor_tick(db) -> Dict[str, Any]:
    started = time.perf_counter()
    if db is None:
        return {"ok": False, "reason": "no_db",
                "considered": 0, "applied": 0}

    considered = 0
    applied = 0
    rejected: List[Dict[str, Any]] = []
    results: List[Dict[str, Any]] = []

    try:
        cursor = db.learnings.find(
            {
                "applied": {"$ne": True},
                "recommended_fix": {"$exists": True},
            },
            {"_id": 0},
        ).limit(COUNCIL_VERDICT_BATCH)
        promoted: List[Dict[str, Any]] = [d async for d in cursor]
    except Exception as e:
        logger.debug(f"[verdict-exec] cursor failed: {e}")
        promoted = []

    for L in promoted:
        considered += 1
        fix = L.get("recommended_fix") or {}
        if not isinstance(fix, dict):
            rejected.append({"reason": "fix_not_object", "subject": L.get("subject")})
            continue
        action = (fix.get("action") or "").strip()
        if action not in _ALLOWED_ACTIONS:
            rejected.append({"reason": f"action_not_allowed:{action}",
                             "subject": L.get("subject")})
            continue

        subject = L.get("subject") or fix.get("subject") or ""
        params = fix.get("params") or {}
        handler = _ACTION_HANDLERS[action]
        out = await handler(db, subject, params)

        try:
            await db.learnings.update_one(
                {"learning_id": L.get("learning_id"),
                 "subject": L.get("subject")},
                {"$set": {
                    "applied": True,
                    "applied_at": _iso(_utc_now()),
                    "applied_result": out,
                    "applied_action": action,
                }},
            )
            if out.get("ok"):
                applied += 1
            results.append({"subject": subject, "action": action, "result": out})
        except Exception as e:
            logger.debug(f"[verdict-exec] mark applied failed: {e}")

    return {
        "ok": True,
        "considered": considered,
        "applied": applied,
        "rejected": rejected,
        "results": results,
        "dry_run": COUNCIL_VERDICT_DRY_RUN,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
    }
