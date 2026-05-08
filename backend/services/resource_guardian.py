"""
AUREM Resource Guardian — Proactive OOM Prevention
====================================================
Called every cycle from auto_heal_scheduler. Takes silent corrective
action at three memory thresholds so the pod never gets OOM-killed by
K8s.

Levels:
  L1 (≥80% mem) → flush stale Redis cache (TTL > 1h)
  L2 (≥85% mem) → cancel NON_CRITICAL_TASKS
  L3 (≥93% mem) → log CRITICAL + graceful uvicorn reload via SIGUSR1

CPU:
  ≥90% → log cpu_spike event (no auto-action)

No outbound alerts here — all events land in MongoDB auto_heal_log; the
ORA bell consumes that collection and surfaces to the founder.
"""
from __future__ import annotations

import os
import signal
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any

import psutil

logger = logging.getLogger(__name__)

NON_CRITICAL_TASKS = [
    "seo_audit_background",
    "embedding_batch_job",
    "log_rotation_task",
    "analytics_aggregator",
]


async def _flush_stale_cache(redis_client) -> int:
    """Delete Redis keys under cache:* whose TTL > 3600 (stale). Returns count."""
    if redis_client is None:
        return 0
    flushed = 0
    try:
        # SCAN to avoid KEYS's O(N) block in prod
        cursor = 0
        while True:
            cursor, keys = await redis_client.scan(cursor=cursor, match="cache:*", count=200)
            for k in keys:
                try:
                    ttl = await redis_client.ttl(k)
                    if ttl is not None and ttl > 3600:
                        await redis_client.delete(k)
                        flushed += 1
                except Exception:
                    continue
            if cursor == 0:
                break
    except Exception as e:
        logger.warning(f"[resource-guardian] cache scan failed: {e}")
    return flushed


def _cancel_non_critical(task_registry: Dict[str, asyncio.Task]) -> int:
    """Cancel any NON_CRITICAL_TASKS that are currently running."""
    cancelled = 0
    for name in NON_CRITICAL_TASKS:
        task = task_registry.get(name) if task_registry else None
        if task is not None and not task.done():
            task.cancel()
            cancelled += 1
    return cancelled


async def check_and_heal_resources(
    db,
    redis_client=None,
    task_registry: Dict[str, asyncio.Task] = None,
) -> Dict[str, Any]:
    """Inspect memory/CPU; take escalating actions. Always returns a summary."""
    task_registry = task_registry or {}
    actions = []

    try:
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.2)
    except Exception as e:
        logger.warning(f"[resource-guardian] psutil failed: {e}")
        return {"status": "psutil_error", "error": str(e)}

    mem_pct = mem.percent

    # ── Level 3 first (most severe) ─────────────────────────────────
    if mem_pct >= 93:
        actions.append(f"L3: critical memory {mem_pct:.1f}% — triggering graceful reload")
        if db is not None:
            try:
                await db.auto_heal_log.insert_one({
                    "type": "critical_memory_reload",
                    "mem_pct": mem_pct,
                    "cpu_pct": cpu,
                    "timestamp": datetime.now(timezone.utc),
                })
            except Exception:
                pass
        # SIGUSR1 = uvicorn graceful reload (workers). Harmless if single
        # worker: uvicorn will reload it.
        try:
            os.kill(os.getpid(), signal.SIGUSR1)
        except Exception as e:
            logger.error(f"[resource-guardian] SIGUSR1 failed: {e}")
        return {"mem_pct": mem_pct, "cpu_pct": cpu, "actions": actions, "level": 3}

    # ── Level 2 ─────────────────────────────────────────────────────
    if mem_pct >= 85:
        cancelled = _cancel_non_critical(task_registry)
        actions.append(f"L2: mem {mem_pct:.1f}% — cancelled {cancelled} non-critical tasks")

    # ── Level 1 ─────────────────────────────────────────────────────
    if mem_pct >= 80:
        flushed = await _flush_stale_cache(redis_client)
        actions.append(f"L1: mem {mem_pct:.1f}% — flushed {flushed} stale cache keys")

    # ── CPU spike (informational) ───────────────────────────────────
    if cpu >= 90:
        actions.append(f"cpu_spike: {cpu:.1f}%")

    if actions and db is not None:
        try:
            await db.auto_heal_log.insert_one({
                "type": "resource_action",
                "mem_pct": mem_pct,
                "cpu_pct": cpu,
                "actions": actions,
                "timestamp": datetime.now(timezone.utc),
            })
        except Exception as e:
            logger.warning(f"[resource-guardian] auto_heal_log write failed: {e}")

    return {
        "mem_pct": mem_pct,
        "cpu_pct": cpu,
        "actions": actions,
        "level": 2 if mem_pct >= 85 else (1 if mem_pct >= 80 else 0),
    }


__all__ = ["check_and_heal_resources", "NON_CRITICAL_TASKS"]
