"""
silent_failure_alerts.py — iter 326pp

Three production "silent failure" alert channels that all reuse the
existing `services.telegram_bot_service.send_telegram_alert` plumbing
(with built-in 5-minute dedup + audit log to `telegram_alert_log`).

Wire-up points:
  - `services/db_backup_service.py::run_backup`     → alert_backup_failure
  - `routers/registry.py` (after aurem_scheduler.start) → alert_scheduler_crash
  - `services/ora_agent.py` (Gemini 401/403 path)   → alert_autonomous_401

Each helper is fire-and-forget: it never raises and never blocks the
caller. If Telegram creds are missing the underlying
`send_telegram_alert` returns `{"ok": False, "reason": "creds_missing"}`
and we just log+return.

Founder directive (Watchdog Mode): no jargon in the Telegram body —
plain English so the founder can triage from phone.
"""
from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


async def _send(message: str, alert_type: str, fingerprint: str) -> Dict[str, Any]:
    """Thin wrapper that swallows all errors and logs at WARNING."""
    try:
        from services.telegram_bot_service import send_telegram_alert
        return await send_telegram_alert(
            message=message,
            alert_type=alert_type,
            fingerprint=fingerprint,
        )
    except Exception as e:
        logger.warning(
            f"[silent_failure_alerts] send failed type={alert_type} "
            f"fp={fingerprint}: {type(e).__name__}: {e}"
        )
        return {"ok": False, "reason": "exception", "detail": str(e)[:200]}


def _fire(coro) -> None:
    """Schedule `coro` on the running loop, or run it synchronously if no
    loop is active (e.g. when called from a thread inside
    `asyncio.to_thread`). Never raises."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    try:
        if loop and loop.is_running():
            asyncio.ensure_future(coro)
        else:
            asyncio.run(coro)
    except Exception as e:
        logger.warning(f"[silent_failure_alerts] _fire dispatch failed: {e}")


# ─────────────────────────────────────────────────────────────────────
# 1) Backup cron failures
# ─────────────────────────────────────────────────────────────────────

def alert_backup_failure(
    run_id: str,
    status: str,
    reason: str,
    triggered_by: str = "scheduler",
) -> None:
    """Called from `db_backup_service.run_backup` on any non-ok exit.

    `status` is one of: "fail" (exception raised mid-run) or "skipped"
    (DNS pre-flight, circuit breaker, missing config, collection cap).

    Dedup fingerprint = run_id so each run sends at most one ping
    even if the same exception fires from multiple call sites.
    """
    if status == "ok":
        return  # never alert on success
    body = (
        f"DR Backup *{status.upper()}* — primary → secondary mirror "
        f"did not complete.\n\n"
        f"Run ID: {run_id}\n"
        f"Trigger: {triggered_by}\n"
        f"When: {_now_iso()}\n\n"
        f"Reason:\n{reason[:1500]}\n\n"
        f"Action: check db_backup_runs collection for full report. "
        f"Next scheduled run: tomorrow 03:00 UTC."
    )
    _fire(_send(body, alert_type="backup_failure", fingerprint=run_id))


# ─────────────────────────────────────────────────────────────────────
# 2) Scheduler crashes (APScheduler job errors)
# ─────────────────────────────────────────────────────────────────────

def alert_scheduler_crash(
    job_id: str,
    job_name: str,
    exception: Optional[BaseException],
    tb_str: Optional[str] = None,
) -> None:
    """Called from the APScheduler EVENT_JOB_ERROR listener.

    Dedup fingerprint = job_id + exception class name, so a job that
    crashes every cycle only pings once per 5-min window per error type.
    """
    exc_type = type(exception).__name__ if exception else "UnknownError"
    exc_msg = str(exception)[:400] if exception else ""
    tb_tail = (tb_str or "")[-1200:]
    body = (
        f"Scheduler job *CRASHED*.\n\n"
        f"Job: {job_name} ({job_id})\n"
        f"When: {_now_iso()}\n"
        f"Error: {exc_type}: {exc_msg}\n\n"
        f"Traceback (last lines):\n{tb_tail}\n\n"
        f"Action: job will retry on its next cron. If this repeats, "
        f"check /var/log/supervisor/backend.err.log."
    )
    fingerprint = f"{job_id}:{exc_type}"
    _fire(_send(body, alert_type="scheduler_crash", fingerprint=fingerprint))


# ─────────────────────────────────────────────────────────────────────
# 3) Auth 401/403 during an autonomous run
# ─────────────────────────────────────────────────────────────────────

def alert_autonomous_401(
    context: str,
    status_code: int,
    detail: str = "",
    provider: Optional[str] = None,
) -> None:
    """Called when ORA's autonomous loop hits an unexpected 401/403.

    `context`  — short label of the call site ("gemini_llm",
                 "ora_tool_http", "internal_admin_probe", ...).
    `provider` — optional upstream name (Gemini, Resend, Stripe…)
                 used in the dedup fingerprint so simultaneous
                 outages across providers still send distinct pings.

    Dedup fingerprint = context+provider+status_code. Same provider
    keeps failing → one ping per 5 min.
    """
    if status_code not in (401, 403):
        return
    label = provider or context
    body = (
        f"Autonomous run hit *HTTP {status_code}*.\n\n"
        f"Where: {context}{f' ({provider})' if provider else ''}\n"
        f"When: {_now_iso()}\n"
        f"Detail: {detail[:600]}\n\n"
        f"Likely cause: API key suspended, rotated, or quota exhausted. "
        f"ORA has paused this provider — check the relevant env var and "
        f"rotate if needed."
    )
    fingerprint = f"{context}:{label}:{status_code}"
    _fire(_send(body, alert_type="autonomous_401", fingerprint=fingerprint))


__all__ = [
    "alert_backup_failure",
    "alert_scheduler_crash",
    "alert_autonomous_401",
]
