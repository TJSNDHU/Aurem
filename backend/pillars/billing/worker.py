"""
Pillar 2 Worker — Billing / Onboarding / Retention scheduler coordinator.
========================================================================
Isolates billing/onboarding background loops from the main uvicorn event
loop. A hung Stripe API call, slow tenant webhook, or unresponsive SMTP
server inside a scheduler no longer blocks the 234 HTTP routers.

Hosted schedulers:
  - abandoned_cart_scheduler   (1h cycle — Stripe cart recovery emails)
  - day21_review_scheduler     (daily — trial → paid conversion nudges)
  - birthday_bonus_scheduler   (daily — customer retention perks)
  - aurem_morning_scheduler    (daily — trial / onboarding drip + digest)
  - compliance_scheduler       (daily midnight UTC — SOC 2 audit snapshot)

Each scheduler is wrapped in _safe_task so unhandled exceptions are
logged and the task auto-restarts; other Pillar 2 loops keep running.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional, Callable

logger = logging.getLogger("pillars.billing.worker")

_worker_tasks: list[asyncio.Task] = []
_worker_started = False


def _safe_task(coro_or_factory, name: str, *, restart: bool = True,
                max_restarts: int = 8, restart_delay: float = 5.0) -> Optional[asyncio.Task]:
    """Wrap a scheduler coroutine in an exception-isolating supervisor.

    Bug-fix #13 — the docstring used to claim auto-restart but the
    implementation only logged the crash and let the task die quietly.
    Now we honour the claim: if `coro_or_factory` is a *callable* that
    returns a fresh coroutine each call, we re-invoke it after the
    crash (up to max_restarts, with restart_delay between attempts).
    If a raw coroutine is passed, we still wrap+log but cannot restart
    (a coroutine object can only be awaited once).
    """
    is_factory = callable(coro_or_factory) and not asyncio.iscoroutine(coro_or_factory)

    async def _wrapper():
        attempts = 0
        while True:
            try:
                if is_factory:
                    await coro_or_factory()
                else:
                    await coro_or_factory
                # Normal completion — no restart unless factory + restart flag.
                if not (is_factory and restart):
                    return
            except asyncio.CancelledError:
                logger.info(f"[p2-worker] task '{name}' cancelled")
                raise
            except BaseException as exc:
                logger.error(f"[p2-worker] task '{name}' crashed: {exc}", exc_info=True)
                if not (is_factory and restart):
                    return
                attempts += 1
                if attempts > max_restarts:
                    logger.error(
                        f"[p2-worker] task '{name}' exceeded {max_restarts} restarts "
                        f"— giving up to avoid restart-loop spam"
                    )
                    return
                logger.warning(
                    f"[p2-worker] task '{name}' restarting "
                    f"({attempts}/{max_restarts}) after {restart_delay}s"
                )
                await asyncio.sleep(restart_delay)
                continue
            # Factory completed normally — re-run on next loop iteration.

    task = asyncio.create_task(_wrapper(), name=f"p2:{name}")
    _worker_tasks.append(task)
    return task


def start_pillar2_worker(
    db,
    abandoned_cart_coro_factory: Optional[Callable] = None,
    day21_coro_factory: Optional[Callable] = None,
    birthday_coro_factory: Optional[Callable] = None,
    aurem_morning_coro_factory: Optional[Callable] = None,
) -> dict:
    """Start Pillar 2 schedulers in an isolated task group.

    The coro_factory callables produce the scheduler coroutines. We take
    them as params because most live as local closures in startup_init.py
    rather than importable module functions.
    """
    global _worker_started
    if _worker_started:
        return {"already_started": True, "tasks": [t.get_name() for t in _worker_tasks]}

    started: list[str] = []
    failed: list[dict] = []

    # ---- Abandoned Cart Recovery (Stripe-driven 1h cycle) -----------
    if abandoned_cart_coro_factory:
        try:
            _safe_task(abandoned_cart_coro_factory(), "abandoned_cart_scheduler")
            started.append("abandoned_cart_scheduler (1h)")
            print("[p2-worker] ✓ Abandoned Cart Recovery scheduler attached", flush=True)
        except Exception as e:
            failed.append({"task": "abandoned_cart_scheduler", "error": str(e)})
            print(f"[p2-worker] ✗ Abandoned Cart failed: {e}", flush=True)

    # ---- Day 21 Retention Review (trial → paid) ---------------------
    if day21_coro_factory:
        try:
            _safe_task(day21_coro_factory(), "day21_review_scheduler")
            started.append("day21_review_scheduler")
            print("[p2-worker] ✓ Day-21 Review scheduler attached", flush=True)
        except Exception as e:
            failed.append({"task": "day21_review_scheduler", "error": str(e)})
            print(f"[p2-worker] ✗ Day-21 Review failed: {e}", flush=True)

    # ---- Birthday Bonus (customer retention perk) -------------------
    if birthday_coro_factory:
        try:
            _safe_task(birthday_coro_factory(), "birthday_bonus_scheduler")
            started.append("birthday_bonus_scheduler")
            print("[p2-worker] ✓ Birthday Bonus scheduler attached", flush=True)
        except Exception as e:
            failed.append({"task": "birthday_bonus_scheduler", "error": str(e)})
            print(f"[p2-worker] ✗ Birthday Bonus failed: {e}", flush=True)

    # ---- AUREM Morning (trial drip + digest) ------------------------
    if aurem_morning_coro_factory:
        try:
            _safe_task(aurem_morning_coro_factory(), "aurem_morning_scheduler")
            started.append("aurem_morning_scheduler (daily)")
            print("[p2-worker] ✓ AUREM Morning / Trial Drip scheduler attached", flush=True)
        except Exception as e:
            failed.append({"task": "aurem_morning_scheduler", "error": str(e)})
            print(f"[p2-worker] ✗ AUREM Morning failed: {e}", flush=True)

    # ---- SOC 2 Daily Compliance (directly importable) ---------------
    try:
        from services.compliance_scheduler import compliance_scheduler, set_db as set_compliance_db
        set_compliance_db(db)
        _safe_task(compliance_scheduler(), "compliance_scheduler")
        started.append("compliance_scheduler (midnight UTC)")
        print("[p2-worker] ✓ SOC 2 Compliance scheduler attached", flush=True)
    except Exception as e:
        failed.append({"task": "compliance_scheduler", "error": str(e)})
        print(f"[p2-worker] ✗ SOC 2 Compliance failed: {e}", flush=True)

    # ---- Trial Win-back (Section 8 — expired-trial 3-step nudges) ----
    try:
        from services.trial_winback import trial_winback_scheduler
        _safe_task(trial_winback_scheduler(), "trial_winback_scheduler")
        started.append("trial_winback_scheduler (30m cycle)")
        print("[p2-worker] ✓ Trial Win-back scheduler attached", flush=True)
    except Exception as e:
        failed.append({"task": "trial_winback_scheduler", "error": str(e)})
        print(f"[p2-worker] ✗ Trial Win-back failed: {e}", flush=True)

    _worker_started = True
    summary = {
        "started_count": len(started),
        "failed_count": len(failed),
        "started": started,
        "failed": failed,
    }
    print(
        f"[p2-worker] Pillar 2 worker ready — {len(started)} schedulers attached, "
        f"{len(failed)} failed",
        flush=True,
    )
    return summary


def get_worker_status() -> dict:
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


async def shutdown_pillar2_worker() -> None:
    for t in _worker_tasks:
        if not t.done():
            t.cancel()
    await asyncio.gather(*_worker_tasks, return_exceptions=True)
    logger.info("[p2-worker] all tasks cancelled")
