"""
AUREM Pillar Orchestrator
=========================
Supervises 4 pillar coroutines as isolated asyncio tasks. If one crashes,
only that pillar is restarted — the other 3 keep running. Per-pillar
restart counts, Redis liveness heartbeats, and MongoDB crash events.

Usage:
    orch = PillarOrchestrator(db, redis_client)
    orch.register("scout",    scout_pillar_fn)        # async callable
    orch.register("envoy",    envoy_pillar_fn)
    orch.register("closer",   closer_pillar_fn)
    orch.register("sentinel", sentinel_pillar_fn)
    asyncio.create_task(orch.run())
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Callable, Dict, Any

logger = logging.getLogger(__name__)


class PillarOrchestrator:
    HEARTBEAT_TTL_SEC = 15       # Redis key TTL — stale means dead
    HEARTBEAT_INTERVAL = 5       # Write heartbeat every N seconds
    RESTART_BACKOFF_SEC = 0.05   # Initial backoff after crash

    def __init__(self, db, redis_client=None):
        self.db = db
        self.redis = redis_client
        self._tasks: Dict[str, asyncio.Task] = {}
        self._fns: Dict[str, Callable] = {}
        self._restart_counts: Dict[str, int] = {}
        self._running = False

    def register(self, name: str, fn: Callable):
        """Register a pillar coroutine factory.

        `fn` must be a zero-arg async callable that, when awaited, runs
        the pillar's long-lived work loop.
        """
        self._fns[name] = fn
        self._restart_counts[name] = 0
        logger.info(f"[orchestrator] registered pillar '{name}'")

    async def _supervised_run(self, name: str):
        """Run the pillar fn forever; on crash, log + restart with backoff."""
        fn = self._fns[name]
        while True:
            try:
                await fn()
                # Pillar returned cleanly — treat as unexpected completion
                # and relaunch after brief delay.
                logger.info(f"[orchestrator] pillar '{name}' returned — relaunching")
                await asyncio.sleep(self.RESTART_BACKOFF_SEC)
            except asyncio.CancelledError:
                logger.info(f"[orchestrator] pillar '{name}' cancelled (clean shutdown)")
                raise
            except Exception as e:
                self._restart_counts[name] += 1
                rc = self._restart_counts[name]
                logger.error(f"[orchestrator] pillar '{name}' crashed (#{rc}): {e}", exc_info=True)

                # Record in MongoDB (never let a logging failure kill the loop)
                if self.db is not None:
                    try:
                        await self.db.pillar_events.insert_one({
                            "pillar": name,
                            "event": "crash_restart",
                            "error": str(e)[:500],
                            "restart_count": rc,
                            "timestamp": datetime.now(timezone.utc),
                        })
                    except Exception as dbe:
                        logger.warning(f"[orchestrator] pillar_events write failed: {dbe}")

                # Record last restart timestamp in Redis
                if self.redis is not None:
                    try:
                        self.redis.setex(
                            f"pillar:{name}:last_restart",
                            3600,
                            datetime.now(timezone.utc).isoformat(),
                        )
                    except Exception:
                        pass

                # Exponential-ish backoff capped at 5s to avoid tight crash loops
                backoff = min(self.RESTART_BACKOFF_SEC * (2 ** min(rc, 7)), 5.0)
                await asyncio.sleep(backoff)

    async def start_all(self):
        """Launch all registered pillar tasks.

        iter 322p — stagger pillar starts so the lazy imports inside each
        `start_pillarN_worker()` don't burn 3-4s of GIL back-to-back, which
        starves the /health ASGI shim under the K8s 10s upstream timeout.
        """
        stagger_s = float(os.environ.get("PILLAR_STAGGER_S", "3.0"))
        for i, name in enumerate(self._fns):
            task = asyncio.create_task(
                self._supervised_run(name),
                name=f"pillar_{name}",
            )
            self._tasks[name] = task
            logger.info(f"[orchestrator] pillar '{name}' launched (T+{i*stagger_s:.0f}s offset)")
            # Yield + delay between pillar boots so the loop can serve probes.
            if i < len(self._fns) - 1:
                await asyncio.sleep(stagger_s)
        self._running = True

    async def monitor(self):
        """Write heartbeat keys + relaunch any task that finished unexpectedly."""
        while self._running:
            for name, task in list(self._tasks.items()):
                # Heartbeat — Redis key with short TTL
                if self.redis is not None:
                    try:
                        self.redis.setex(f"pillar:{name}:alive", self.HEARTBEAT_TTL_SEC, "1")
                    except Exception:
                        pass

                # Relaunch safety net — _supervised_run should never exit
                # except on cancel, but belt + suspenders.
                if task.done() and not task.cancelled():
                    logger.warning(f"[orchestrator] pillar '{name}' task ended unexpectedly — relaunching")
                    new_task = asyncio.create_task(
                        self._supervised_run(name),
                        name=f"pillar_{name}",
                    )
                    self._tasks[name] = new_task

            await asyncio.sleep(self.HEARTBEAT_INTERVAL)

    async def run(self):
        """Start all pillars + monitor loop."""
        await self.start_all()
        await self.monitor()

    async def stop_all(self):
        """Cancel all pillar tasks and wait for clean shutdown."""
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        logger.info("[orchestrator] all pillars stopped")

    def status(self) -> Dict[str, Any]:
        """Snapshot of live pillar state."""
        return {
            name: {
                "alive": not task.done(),
                "restart_count": self._restart_counts.get(name, 0),
            }
            for name, task in self._tasks.items()
        }


__all__ = ["PillarOrchestrator"]
