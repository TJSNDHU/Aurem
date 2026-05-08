"""
A2A Daily Learning Scheduler — iter 282
═══════════════════════════════════════════════════════════════════════

Closes the A2A ↔ Hermes feedback loop.

    pillar_heartbeat  ──health_event──▶  a2a_events
                                              │
                                              ▼
    autonomous_repair ──cycle/verify──▶ autonomous_repair_events
                                              │
                     2AM UTC daily    ┌────────┴────────┐
                                      ▼                 ▼
                              daily_learning     Learning Bus
                              (a2a_learning_       broadcast
                               router)                 │
                                      │                ▼
                                      ▼         a2a_bus.emit
                              Hermes memory     (learning_summary)
                              (platform tenant)
                                      │
                                      ▼
                              ORA chat recall ← smarter context
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Run at 02:00 UTC every day. Configurable via env for tests.
import os
_HOUR_UTC = int(os.environ.get("A2A_LEARNING_HOUR_UTC", "2"))
_MIN_UTC = int(os.environ.get("A2A_LEARNING_MINUTE_UTC", "0"))

# Poll interval for checking "is it 2am?"
_CHECK_EVERY_SEC = 300  # 5 min
_LAST_RUN_KEY = "a2a_learning_scheduler"

_db = None


def set_db(database) -> None:
    global _db
    _db = database


async def _seconds_until_next_run() -> float:
    now = datetime.now(timezone.utc)
    target = now.replace(hour=_HOUR_UTC, minute=_MIN_UTC, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return (target - now).total_seconds()


async def _already_ran_today() -> bool:
    if _db is None:
        return False
    try:
        doc = await _db.system_config.find_one(
            {"config_key": _LAST_RUN_KEY}, {"_id": 0}
        )
        if not doc:
            return False
        last = doc.get("last_run_date")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return last == today
    except Exception:
        return False


async def _mark_ran_today() -> None:
    if _db is None:
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        await _db.system_config.update_one(
            {"config_key": _LAST_RUN_KEY},
            {"$set": {
                "config_key": _LAST_RUN_KEY,
                "last_run_date": today,
                "last_run_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.debug("[a2a-learning-sched] mark ran failed: %s", e)


async def run_learning_now() -> dict:
    """Trigger the daily_learning flow directly. Callable by admin or cron."""
    try:
        import secrets
        from routers.a2a_learning_router import run_daily_learning, db as _ll_db
        # Ensure the learning router sees the same db we have
        session_id = f"learn_{secrets.token_hex(8)}"
        if _ll_db is None:
            logger.warning("[a2a-learning-sched] learning_router.db is None; skipping")
            return {"ok": False, "error": "learning_router_db_unset"}
        await _ll_db.learning_sessions.insert_one({
            "session_id": session_id,
            "type": "daily_learning_cron",
            "status": "started",
            "started_at": datetime.now(timezone.utc),
        })
        # Run inline (not BackgroundTasks) so we capture outcome
        await run_daily_learning(session_id)
        return {"ok": True, "session_id": session_id}
    except Exception as e:
        logger.warning("[a2a-learning-sched] run failed: %s", e)
        return {"ok": False, "error": str(e)[:200]}


async def a2a_learning_daily_scheduler() -> None:
    """P4 worker task. Wakes every 5 min, runs once at the configured hour."""
    logger.info(
        "[a2a-learning-sched] starting — daily at %02d:%02d UTC",
        _HOUR_UTC, _MIN_UTC,
    )
    while True:
        try:
            now = datetime.now(timezone.utc)
            if (
                now.hour == _HOUR_UTC
                and abs(now.minute - _MIN_UTC) < 5
                and not await _already_ran_today()
            ):
                logger.info("[a2a-learning-sched] window hit — running daily learning")
                res = await run_learning_now()
                if res.get("ok"):
                    await _mark_ran_today()
                    logger.info("[a2a-learning-sched] daily run complete: %s",
                                res.get("session_id"))
                else:
                    logger.warning("[a2a-learning-sched] run result: %s", res)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("[a2a-learning-sched] tick failed: %s", e)
        await asyncio.sleep(_CHECK_EVERY_SEC)
