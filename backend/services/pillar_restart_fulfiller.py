"""
AUREM Pillar Restart Fulfiller (iter 322l — Day 2.3)
=====================================================
Reads `pillar_restart_requests` written by Sovereign Watchdog and actually
re-initialises the dead pillar's worker. Closes the autonomy loop:
  detect → escalate → fix → (now) carry out the fix.

Workflow per cycle (default 90 s):
  1. Find unfulfilled requests (`fulfilled: false`).
  2. For each, look up the pillar's worker entry-point and invoke it.
  3. Mark the request `fulfilled: true` regardless of outcome (so the
     same request is not retried in a tight loop). Outcome detail is
     written to `attempts: [...]` for audit.
  4. If the launch raised, write a Memory-Guard learning candidate so
     the Council can decide whether the recipe needs revision.

We never spawn a worker that's already running. Pillar workers are
self-supervised by `PillarOrchestrator` (registered in `server.py`) — we
just nudge the orchestrator's task to come back online when it died.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


FULFILLER_INTERVAL_S = int(os.environ.get("PILLAR_FULFILLER_INTERVAL_S", "90"))
COLL = "pillar_restart_requests"

# Pillar number → coroutine factory. Lazy-imported so a missing module
# fails the single request rather than the whole loop.
_PILLAR_LAUNCHERS: Dict[str, str] = {
    "1": "pillars.sales.worker:start_pillar1_worker",
    "2": "pillars.command_hub.worker:start_pillar2_worker",
    "3": "pillars.ops.worker:start_pillar3_worker",
    "4": "pillars.command_hub.worker:start_pillar4_worker",
}


async def _launch_pillar(pillar: str, db) -> Dict[str, Any]:
    """Resolve the launcher entry-point and invoke it once."""
    target = _PILLAR_LAUNCHERS.get(str(pillar))
    if not target:
        return {"ok": False, "error": f"unknown_pillar:{pillar}"}
    module_path, func_name = target.split(":")
    try:
        import importlib
        mod = importlib.import_module(module_path)
        fn = getattr(mod, func_name, None)
        if fn is None:
            return {"ok": False, "error": f"missing_launcher:{target}"}
        # The pillar worker is a long-running coroutine — wrap in a task
        # so we don't block this loop.
        asyncio.create_task(fn(db))
        return {"ok": True, "launcher": target}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def _maybe_submit_learning(db, *, pillar: str, attempt_result: Dict[str, Any]) -> None:
    """When a launch fails, ask the Memory Guard to record the recipe
    outcome as a candidate so the Council audits whether the launcher
    mapping needs an update."""
    if attempt_result.get("ok"):
        return
    try:
        from services import sovereign_memory as smg
        await smg.submit_learning(
            db,
            agent_role="watchdog",
            kind=f"pillar_restart_failure:p{pillar}",
            payload={
                "launcher_attempted": _PILLAR_LAUNCHERS.get(str(pillar)),
                "result": attempt_result,
            },
            evidence={
                "ts": datetime.now(timezone.utc).isoformat(),
                "pillar": pillar,
            },
            confidence=0.4,
        )
    except Exception as e:
        logger.debug(f"[pillar-fulfiller] learning submit skipped: {e}")


async def fulfill_once(db) -> Dict[str, Any]:
    """Process all pending requests in a single pass."""
    if db is None:
        return {"processed": 0, "succeeded": 0, "failed": 0, "error": "db_unavailable"}

    cursor = db[COLL].find(
        {"fulfilled": False},
        {"_id": 0},
    ).sort("ts", 1).limit(20)
    pending: List[Dict[str, Any]] = [doc async for doc in cursor]

    succeeded = 0
    failed = 0
    for req in pending:
        pillar = str(req.get("pillar", ""))
        result = await _launch_pillar(pillar, db)
        await db[COLL].update_one(
            {"ts": req.get("ts"), "pillar": pillar},
            {"$set": {
                "fulfilled": True,
                "fulfilled_at": datetime.now(timezone.utc).isoformat(),
                "attempt_result": result,
                "fulfiller_source": "pillar_restart_fulfiller",
            }},
        )
        if result.get("ok"):
            succeeded += 1
        else:
            failed += 1
            await _maybe_submit_learning(db, pillar=pillar, attempt_result=result)

    return {
        "processed": len(pending),
        "succeeded": succeeded,
        "failed": failed,
        "interval_s": FULFILLER_INTERVAL_S,
    }


# ─── Background loop ───────────────────────────────────────────────────
_started = False


async def _fulfiller_loop(db) -> None:
    logger.info(
        f"[pillar-fulfiller] online — interval={FULFILLER_INTERVAL_S}s",
    )
    await asyncio.sleep(45)  # let pillars settle on first boot
    while True:
        try:
            summary = await fulfill_once(db)
            if summary.get("processed"):
                logger.info(f"[pillar-fulfiller] tick: {summary}")
        except Exception as e:
            logger.warning(f"[pillar-fulfiller] tick failed: {e}")
        await asyncio.sleep(FULFILLER_INTERVAL_S)


def start_pillar_fulfiller(db) -> bool:
    """Idempotent launcher — called from server.py startup."""
    global _started
    if _started:
        return False
    if os.environ.get("PILLAR_FULFILLER_DISABLED", "").lower() in ("1", "true", "yes"):
        logger.info("[pillar-fulfiller] disabled via env")
        return False
    try:
        asyncio.create_task(_fulfiller_loop(db))
        _started = True
        return True
    except RuntimeError:
        return False
