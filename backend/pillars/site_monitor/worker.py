"""
Pillar 3 Worker — Dedicated scheduler coordinator.
==================================================
In the current monolith, every scheduler runs on the SAME uvicorn event
loop that also handles the 234 HTTP routers. A slow WHAPI call inside a
scheduler blocks every incoming HTTP request for up to 15 seconds,
which is exactly why production showed `nginx connect() failed (111)`
under load.

This worker isolates the Pillar 3 schedulers into their OWN asyncio task
group. In a future deployment split, this exact file becomes the entry
point for a separate Kubernetes pod — the app container stays pristine,
and the worker pod carries the scheduler load.

Currently hosted schedulers:
  - shannon_runner_scheduler       (weekly pentest against aurem.live)
  - site_monitor_scheduler         (uptime probes for all tenants)
  - self_repair_loop               (6h discovery + auto-fix)
  - self_scan_automation           (self-repair from aurem.live scans)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("pillars.site_monitor.worker")

# Module-level handle on the task group so callers can inspect / cancel.
_worker_tasks: list[asyncio.Task] = []
_worker_started = False


def _safe_task(coro, name: str) -> Optional[asyncio.Task]:
    """Wrap a coroutine so unhandled exceptions never crash the pod."""

    async def _wrapper():
        try:
            await coro
        except asyncio.CancelledError:
            logger.info(f"[p3-worker] task '{name}' cancelled")
            raise
        except BaseException as exc:
            logger.error(f"[p3-worker] task '{name}' crashed: {exc}", exc_info=True)

    task = asyncio.create_task(_wrapper(), name=f"p3:{name}")
    _worker_tasks.append(task)
    return task


def start_pillar3_worker(db) -> dict:
    """Start all Pillar 3 schedulers in an isolated task group.

    Returns a dict summarising what started and what failed. Safe to call
    repeatedly — subsequent calls are no-ops.
    """
    global _worker_started
    if _worker_started:
        return {"already_started": True, "tasks": [t.get_name() for t in _worker_tasks]}

    started: list[str] = []
    failed: list[dict] = []

    # ---- Shannon Runner (weekly pentest against aurem.live) --------
    try:
        from services.shannon_runner import shannon_runner_scheduler
        _safe_task(shannon_runner_scheduler(), "shannon_runner")
        started.append("shannon_runner (7d cycle)")
        print("[p3-worker] ✓ Shannon Runner scheduler attached", flush=True)
    except Exception as e:
        failed.append({"task": "shannon_runner", "error": str(e)})
        print(f"[p3-worker] ✗ Shannon Runner failed: {e}", flush=True)

    # ---- Self-Repair Loop (6h discovery + auto-fix) ----------------
    try:
        from services.self_repair_loop import self_repair_loop, set_db as set_sr_db
        set_sr_db(db)
        _safe_task(self_repair_loop(), "self_repair_loop")
        started.append("self_repair_loop (6h cycle)")
        print("[p3-worker] ✓ Self-Repair Loop scheduler attached", flush=True)
    except Exception as e:
        failed.append({"task": "self_repair_loop", "error": str(e)})
        print(f"[p3-worker] ✗ Self-Repair Loop failed: {e}", flush=True)

    # ---- Self-Scan Automation (continuous scan pipeline) -----------
    try:
        from services.self_scan_automation import self_scan_loop, set_db as set_ss_db
        set_ss_db(db)
        _safe_task(self_scan_loop(), "self_scan_automation")
        started.append("self_scan_automation")
        print("[p3-worker] ✓ Self-Scan Automation attached", flush=True)
    except ImportError:
        # Optional — skip gracefully if the module doesn't export a loop
        pass
    except Exception as e:
        failed.append({"task": "self_scan_automation", "error": str(e)})
        print(f"[p3-worker] ✗ Self-Scan Automation failed: {e}", flush=True)

    # ---- Site Monitor (5-min uptime probes per-tenant) ---------------
    try:
        from services.site_monitor import site_monitor_scheduler, set_db as set_sm_db
        set_sm_db(db)
        _safe_task(site_monitor_scheduler(), "site_monitor_scheduler")
        started.append("site_monitor_scheduler (5m cycle)")
        print("[p3-worker] ✓ Site Monitor scheduler attached", flush=True)
    except Exception as e:
        failed.append({"task": "site_monitor_scheduler", "error": str(e)})
        print(f"[p3-worker] ✗ Site Monitor failed: {e}", flush=True)

    _worker_started = True
    summary = {
        "started_count": len(started),
        "failed_count": len(failed),
        "started": started,
        "failed": failed,
    }
    print(
        f"[p3-worker] Pillar 3 worker ready — {len(started)} schedulers attached, "
        f"{len(failed)} failed",
        flush=True,
    )
    return summary


def get_worker_status() -> dict:
    """Introspect live worker state for admin dashboards."""
    active = [t for t in _worker_tasks if not t.done()]
    finished = [t for t in _worker_tasks if t.done()]
    return {
        "started": _worker_started,
        "active_tasks": len(active),
        "finished_tasks": len(finished),
        "tasks": [
            {
                "name": t.get_name(),
                "done": t.done(),
                "cancelled": t.cancelled() if t.done() else False,
                "exception": (
                    str(t.exception()) if t.done() and not t.cancelled() and t.exception() else None
                ),
            }
            for t in _worker_tasks
        ],
    }


async def shutdown_pillar3_worker() -> None:
    """Cancel all Pillar 3 tasks cleanly on shutdown."""
    for t in _worker_tasks:
        if not t.done():
            t.cancel()
    await asyncio.gather(*_worker_tasks, return_exceptions=True)
    logger.info("[p3-worker] all tasks cancelled")
