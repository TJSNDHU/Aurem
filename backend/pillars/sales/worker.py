"""
Pillar 1 Worker — Sales / Outreach / Lead Gen scheduler coordinator.
====================================================================
Isolates the Sales-domain background loops from the main uvicorn event
loop so a slow WHAPI/Twilio/Resend call inside a scheduler never blocks
the 234 HTTP routers.

Hosted schedulers (currently):
  - auto_blast_scheduler       (5m cycle — verify + 4-channel blast)
  - proactive_outreach_scheduler
  - news_monitor_scheduler     (2h cycle — scan for lead-signal news)

Each scheduler is wrapped in _safe_task so unhandled exceptions are
logged and the task auto-restarts; the rest of Pillar 1 keeps running.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("pillars.sales.worker")

_worker_tasks: list[asyncio.Task] = []
_worker_started = False


def _safe_task(coro, name: str) -> Optional[asyncio.Task]:
    """Wrap a coroutine so unhandled exceptions never crash the pod."""

    async def _wrapper():
        try:
            await coro
        except asyncio.CancelledError:
            logger.info(f"[p1-worker] task '{name}' cancelled")
            raise
        except BaseException as exc:
            logger.error(f"[p1-worker] task '{name}' crashed: {exc}", exc_info=True)

    task = asyncio.create_task(_wrapper(), name=f"p1:{name}")
    _worker_tasks.append(task)
    return task


def start_pillar1_worker(db, news_monitor_coro_factory=None) -> dict:
    """Start all Pillar 1 schedulers in an isolated task group.

    news_monitor_coro_factory: callable that returns an awaitable (since
    _news_monitor_scheduler lives inside startup_init.py as a local
    closure, we take it as a parameter rather than importing).
    """
    global _worker_started
    if _worker_started:
        return {"already_started": True, "tasks": [t.get_name() for t in _worker_tasks]}

    started: list[str] = []
    failed: list[dict] = []

    # ---- Auto-Blast Engine (5m cycle — 4-channel outreach) ----------
    try:
        from services.auto_blast_engine import auto_blast_scheduler, set_db as set_auto_blast_db
        set_auto_blast_db(db)
        _safe_task(auto_blast_scheduler(), "auto_blast_scheduler")
        started.append("auto_blast_scheduler (5m cycle)")
        print("[p1-worker] ✓ Auto-Blast scheduler attached", flush=True)
    except Exception as e:
        failed.append({"task": "auto_blast_scheduler", "error": str(e)})
        print(f"[p1-worker] ✗ Auto-Blast failed: {e}", flush=True)

    # ---- Blast-Chain Advancer (Section 7 — staggered 4-touch chains) ---
    try:
        from services.blast_chain import chain_advance_scheduler
        _safe_task(chain_advance_scheduler(), "chain_advance_scheduler")
        started.append("chain_advance_scheduler (5m cycle)")
        print("[p1-worker] ✓ Blast-Chain advance scheduler attached", flush=True)
    except Exception as e:
        failed.append({"task": "chain_advance_scheduler", "error": str(e)})
        print(f"[p1-worker] ✗ Blast-Chain advancer failed: {e}", flush=True)

    # ---- ORA Campaign Watchdog (iter 322g — campaign uptime sentinel) ---
    try:
        from services.ora_campaign_watchdog import watchdog_loop, set_db as set_wd_db
        set_wd_db(db)
        _safe_task(watchdog_loop(), "ora_campaign_watchdog")
        started.append("ora_campaign_watchdog (60s poll)")
        print("[p1-worker] ✓ ORA Campaign Watchdog attached", flush=True)
    except Exception as e:
        failed.append({"task": "ora_campaign_watchdog", "error": str(e)})
        print(f"[p1-worker] ✗ ORA Campaign Watchdog failed: {e}", flush=True)

    # ---- Ollama Model Warmer (DISABLED iter 322g — daemon is single-threaded;
    # warmer pings were jamming the queue. qwen2.5:7b-instruct stays in
    # RAM for ~5min after last use by Ollama's default keepalive, which
    # is sufficient for chat-active sessions. Re-enable if multi-threaded
    # daemon is built.
    # try:
    #     from services.ollama_warmer import warmer_loop, set_db as set_warm_db
    #     set_warm_db(db)
    #     _safe_task(warmer_loop(), "ollama_warmer")
    #     started.append("ollama_warmer (3min cycle)")
    #     print("[p1-worker] ✓ Ollama warmer attached", flush=True)
    # except Exception as e:
    #     failed.append({"task": "ollama_warmer", "error": str(e)})
    #     print(f"[p1-worker] ✗ Ollama warmer failed: {e}", flush=True)

    # ---- Autonomous Ops (iter 322g — 4x/day warmer + watchdog auto-fix) -
    try:
        from services.ora_autonomous_ops import (
            ollama_warmer_autonomous_loop,
            watchdog_autofix_loop,
            set_db as set_auto_db,
        )
        set_auto_db(db)
        _safe_task(ollama_warmer_autonomous_loop(), "autonomous_warmer")
        _safe_task(watchdog_autofix_loop(), "autonomous_autofix")
        started.append("autonomous_warmer (6h cycle)")
        started.append("autonomous_autofix (90s cycle)")
        print("[p1-worker] ✓ Autonomous warmer + autofix attached", flush=True)
    except Exception as e:
        failed.append({"task": "autonomous_ops", "error": str(e)})
        print(f"[p1-worker] ✗ Autonomous ops failed: {e}", flush=True)

    # ---- Phase 1: T1 Pipeline subscriptions (Closer + Followup + Referral) ─
    # Register A2A bus handlers once at boot.
    try:
        from services.agents import closer_ora, followup_ora, referral_ora
        closer_ora.register_subscriptions()
        followup_ora.register_subscriptions()
        referral_ora.register_subscriptions()
        # Schedulers
        _safe_task(closer_ora.closer_window_scheduler(), "closer_window_scheduler")
        _safe_task(followup_ora.followup_tick_scheduler(), "followup_tick_scheduler")
        _safe_task(referral_ora.referral_tick_scheduler(), "referral_tick_scheduler")
        started.append("closer/followup/referral A2A subscriptions + 3 schedulers")
        print("[p1-worker] ✓ Phase 1 T1 pipeline (Closer/Followup/Referral) attached",
              flush=True)
    except Exception as e:
        failed.append({"task": "phase1_t1_pipeline", "error": str(e)})
        print(f"[p1-worker] ✗ Phase 1 T1 pipeline failed: {e}", flush=True)

    # ---- Proactive AI Outreach --------------------------------------
    try:
        from services.proactive_outreach import proactive_outreach_scheduler
        _safe_task(proactive_outreach_scheduler(), "proactive_outreach")
        started.append("proactive_outreach")
        print("[p1-worker] ✓ Proactive Outreach scheduler attached", flush=True)
    except ImportError:
        pass  # optional service
    except Exception as e:
        failed.append({"task": "proactive_outreach", "error": str(e)})
        print(f"[p1-worker] ✗ Proactive Outreach failed: {e}", flush=True)

    # ---- News Auto-Monitor (2h cycle — lead-signal discovery) --------
    if news_monitor_coro_factory:
        try:
            _safe_task(news_monitor_coro_factory(), "news_monitor_scheduler")
            started.append("news_monitor_scheduler (2h cycle)")
            print("[p1-worker] ✓ News Auto-Monitor scheduler attached", flush=True)
        except Exception as e:
            failed.append({"task": "news_monitor_scheduler", "error": str(e)})
            print(f"[p1-worker] ✗ News Auto-Monitor failed: {e}", flush=True)

    _worker_started = True
    summary = {
        "started_count": len(started),
        "failed_count": len(failed),
        "started": started,
        "failed": failed,
    }
    print(
        f"[p1-worker] Pillar 1 worker ready — {len(started)} schedulers attached, "
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


async def shutdown_pillar1_worker() -> None:
    for t in _worker_tasks:
        if not t.done():
            t.cancel()
    await asyncio.gather(*_worker_tasks, return_exceptions=True)
    logger.info("[p1-worker] all tasks cancelled")
