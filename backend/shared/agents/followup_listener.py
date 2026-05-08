"""
Follow-up ORA Event Listener — Iteration 215
=============================================
Background task that subscribes to the A2A bus for `new_leads_batch` events
addressed to `followup_ora` and wakes the Follow-up ORA to process the fresh
batch immediately (instead of waiting for the nightly cycle).

Events consumed:
  - from_agent=hunter_ora          event=new_leads_batch   (Hunter → Follow-up)
  - from_agent=openfang_ingest     event=new_leads_batch   (OpenFang webhook → Follow-up)

Behaviour:
  - On each event, emits a "listener_ack" on the bus so the Admin UI sees the
    reaction in the activity feed.
  - Triggers FollowupORA.run_cycle() in dry-run-safe mode (respects existing
    agent state like paused / dry_run flag).
  - Any exception is swallowed to keep the listener alive.

Started from: routers/registry.py right after register_agents(db).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from services.a2a_bus import bus
from services.agents import get_agent

logger = logging.getLogger(__name__)

_TASK: Optional[asyncio.Task] = None


async def _run_loop() -> None:
    queue = bus.subscribe_queue("followup_ora")
    logger.info("[FollowupListener] subscribed to a2a_bus for 'followup_ora'")
    while True:
        try:
            event = await queue.get()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"[FollowupListener] queue error: {e}")
            await asyncio.sleep(1)
            continue

        try:
            if event.get("event") != "new_leads_batch":
                continue

            payload = event.get("payload") or {}
            source = payload.get("source") or event.get("from_agent")
            count = payload.get("count") or 0
            run_id = payload.get("run_id") or payload.get("hunt_id") or "—"

            logger.info(
                f"[FollowupListener] new_leads_batch received · "
                f"source={source} · count={count} · run={run_id}"
            )

            # Ack so the admin sees it in the activity feed
            await bus.emit(
                "followup_ora",
                "listener_ack",
                {
                    "source": source,
                    "run_id": run_id,
                    "count": count,
                    "received_at": datetime.now(timezone.utc).isoformat(),
                },
            )

            # Wake the agent — but skip if paused / DB unavailable
            agent = get_agent("followup_ora")
            if agent is None:
                logger.warning("[FollowupListener] followup_ora agent not registered")
                continue
            if agent.paused:
                logger.info("[FollowupListener] agent paused — skipping wake-up")
                continue

            stats = await agent.run_cycle()
            await bus.emit(
                "followup_ora",
                "listener_cycle_complete",
                {"trigger": source, "run_id": run_id, "stats": stats or {}},
            )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"[FollowupListener] event processing failed: {e}")


def start_followup_listener() -> asyncio.Task:
    """Start (or return existing) background listener task."""
    global _TASK
    if _TASK and not _TASK.done():
        return _TASK
    loop = asyncio.get_event_loop()
    _TASK = loop.create_task(_run_loop(), name="followup_ora_listener")
    logger.info("[FollowupListener] background task started")
    return _TASK


def stop_followup_listener() -> None:
    global _TASK
    if _TASK and not _TASK.done():
        _TASK.cancel()
        _TASK = None
