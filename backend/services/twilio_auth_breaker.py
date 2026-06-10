"""
services/twilio_auth_breaker.py — iter D-72.

Process-level circuit breaker for Twilio auth.

Problem
-------
When TWILIO_AUTH_TOKEN is stale / rotated / wrong, every SMS + voice send
in `pillars.sales.routes.blast_service` returns HTTP 401 from Twilio with
message "Authenticate". The auto-blast engine then:

  • burns 30+ seconds per lead (15s SMS HTTP + 15s voice HTTP),
  • produces a flood of identical "Authenticate" warnings in logs,
  • times out the autonomous-restart_blast task at 90s,
  • leaves the founder with no clear signal that the cause is creds, not code.

This breaker
------------
* Records the first 401 we see from Twilio (one Telegram alert per day).
* Skips all subsequent Twilio calls (SMS + voice) for the rest of the
  process lifetime → cycles complete in ms instead of seconds.
* Auto-resets on backend restart (so rotating the token + restarting
  re-arms the channels).
* Successful Twilio response clears the breaker (in-flight recovery).

This is PROCESS state only. No persistence. No mocks. No fake success.
The user side action is to rotate the Twilio AUTH_TOKEN in `.env` and
restart the backend.

Usage
-----
    from services.twilio_auth_breaker import (
        is_open, record_response, mark_invalid_from_exception,
    )

    if is_open():
        return {"success": False, "error": "twilio_auth_invalid",
                "skipped_by_breaker": True}

    resp = await client.post(...)
    record_response(resp.status_code, resp.text)  # closes / opens as needed
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Single source of truth (process-level)
_lock = threading.Lock()
_open: bool = False
_opened_at: Optional[float] = None
_reason: str = ""
_failure_count: int = 0  # number of 401s observed in this process lifetime
_last_alert_at: float = 0.0  # epoch — gates Telegram so we send at most once / 24h
_ALERT_INTERVAL_S = 24 * 3600  # 24 hours


def _send_one_alert(reason: str) -> None:
    """Best-effort Telegram alert. Never raises, never blocks the breaker."""
    try:
        import asyncio
        from services.telegram_bot_service import send_telegram_alert
        msg = (
            "Twilio auth invalid — campaign SMS + voice are now "
            "SKIPPED process-wide until backend restart with a fresh "
            "TWILIO_AUTH_TOKEN.\n\n"
            f"Reason: {reason[:200]}\n\n"
            "Action: rotate TWILIO_AUTH_TOKEN in /app/backend/.env, then "
            "`sudo supervisorctl restart backend`."
        )
        coro = send_telegram_alert(
            message=msg,
            alert_type="twilio_auth_invalid",
            fingerprint=time.strftime("%Y-%m-%d"),
        )
        # Run if we have an event loop, schedule if not
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            asyncio.run(coro)
    except Exception as e:
        logger.debug(f"[twilio-breaker] telegram alert skipped: {e}")


def mark_invalid(reason: str) -> None:
    """Open the breaker. Idempotent — calling repeatedly never re-alerts
    unless the 24h window has expired."""
    global _open, _opened_at, _reason, _failure_count, _last_alert_at
    with _lock:
        _failure_count += 1
        first_time = not _open
        if first_time:
            _open = True
            _opened_at = time.time()
            _reason = reason
            logger.error(
                "[twilio-breaker] OPENED — Twilio SMS + voice now skipped "
                "process-wide. Reason: %s. Fix: rotate TWILIO_AUTH_TOKEN "
                "in /app/backend/.env and restart backend.",
                reason[:200],
            )

        # Alert at most once per 24h regardless of failure volume
        now = time.time()
        if now - _last_alert_at > _ALERT_INTERVAL_S:
            _last_alert_at = now
            _send_one_alert(reason)


def mark_valid() -> None:
    """Close the breaker after a confirmed-successful Twilio response.
    Logs the recovery so the founder sees the auto-recovery."""
    global _open, _opened_at, _reason
    with _lock:
        if _open:
            logger.info(
                "[twilio-breaker] CLOSED — Twilio responded with success "
                "after being marked invalid. Channels re-enabled."
            )
            _open = False
            _opened_at = None
            _reason = ""


def is_open() -> bool:
    """Cheap thread-safe peek. Returns True if Twilio calls should skip."""
    return _open


def status() -> dict:
    """Snapshot for /api/admin/campaign-health surface."""
    with _lock:
        return {
            "open": _open,
            "opened_at": (
                datetime.fromtimestamp(_opened_at, tz=timezone.utc).isoformat()
                if _opened_at else None
            ),
            "reason": _reason,
            "failure_count": _failure_count,
            "auth_token_tail": (
                (os.environ.get("TWILIO_AUTH_TOKEN") or "")[-4:]
                if os.environ.get("TWILIO_AUTH_TOKEN") else ""
            ),
        }


def record_response(status_code: int, body: str = "") -> None:
    """Observe one Twilio HTTP response. Opens or closes the breaker.

    * 401 → open (auth invalid)
    * 200/201/202 → close (recovery)
    * everything else → no-op (don't conflate transient errors with auth)
    """
    if status_code == 401:
        # Body usually has {"code":20003,"message":"Authenticate",...}
        snippet = (body or "")[:160]
        mark_invalid(f"HTTP 401 from Twilio: {snippet}")
    elif status_code in (200, 201, 202):
        mark_valid()


def mark_invalid_from_exception(exc: BaseException) -> None:
    """For callers that can't always inspect status_code (e.g. exception
    path). Only opens the breaker when the exception string clearly
    indicates an auth problem — otherwise no-op (transient network blip
    must NOT open the breaker)."""
    text = str(exc).lower()
    if any(k in text for k in ("401", "authenticate", "unauthorized")):
        mark_invalid(f"{type(exc).__name__}: {str(exc)[:160]}")


def _force_reset_for_tests() -> None:
    """ONLY for pytest. Restores the module to pristine state between
    test cases without touching the rest of the codebase."""
    global _open, _opened_at, _reason, _failure_count, _last_alert_at
    with _lock:
        _open = False
        _opened_at = None
        _reason = ""
        _failure_count = 0
        _last_alert_at = 0.0
