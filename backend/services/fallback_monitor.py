"""
AUREM Fallback Monitor
======================
Centralized fallback tracking + alert system.

Responsibilities:
  1. Log every fallback event into `fallback_usage_log` (MongoDB)
  2. Track consecutive primary-service failures per (service, tier)
  3. Alert via SMS to ADMIN_ALERT_PHONE when any primary fails 3x in a row

Usage (fire-and-forget from any service):

    from services.fallback_monitor import log_fallback, record_primary_failure

    # When a primary succeeds → clears failure count
    await log_fallback(db, service="video", primary="muapi", used="muapi",
                       result="success", meta={...})

    # When a primary fails and we fell back:
    await log_fallback(db, service="video", primary="muapi", used="modelslab",
                       result="fallback", reason="Muapi 503", meta={...})
    await record_primary_failure(db, service="video", primary="muapi",
                                  reason="Muapi 503")

    # When everything failed:
    await log_fallback(db, service="whatsapp", primary="whapi", used=None,
                       result="error", reason="All channels down")

Silent by design — errors from the monitor never propagate.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

_ALERT_PHONE_ENV = "ADMIN_ALERT_PHONE"          # e.g. "+16134000000"
_ALERT_COOLDOWN_MINUTES = 30                    # don't spam repeat alerts
_FAILURE_THRESHOLD = 3                          # 3 consecutive failures → SMS


async def log_fallback(
    db,
    *,
    service: str,
    primary: str,
    used: Optional[str],
    result: str,                # "success" | "fallback" | "error"
    reason: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Record one fallback decision. Never raises."""
    if db is None:
        return
    try:
        await db.fallback_usage_log.insert_one({
            "service": service,
            "primary": primary,
            "used": used,
            "result": result,
            "reason": (reason or "")[:500],
            "meta": meta or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ttl_at": datetime.now(timezone.utc),  # Iter 206: 30-day TTL
        })
    except Exception as e:
        logger.debug(f"[FallbackMonitor] log_fallback failed: {e}")


async def record_primary_failure(
    db,
    *,
    service: str,
    primary: str,
    reason: Optional[str] = None,
) -> None:
    """
    Increment the consecutive-failure counter for (service, primary).
    If it hits the threshold → fire SMS alert (respecting cooldown).
    """
    if db is None:
        return
    key = {"service": service, "primary": primary}
    now = datetime.now(timezone.utc)
    try:
        doc = await db.fallback_failure_state.find_one_and_update(
            key,
            {"$inc": {"consecutive_failures": 1},
             "$set": {"last_failure_at": now.isoformat(),
                      "last_reason": (reason or "")[:300]}},
            upsert=True,
            return_document=True,  # type: ignore[arg-type]
        ) or {}
        if doc is None:
            doc = await db.fallback_failure_state.find_one(key) or {}

        count = int(doc.get("consecutive_failures") or 0)
        if count < _FAILURE_THRESHOLD:
            return

        # Cooldown check — don't spam the operator
        last_alert_iso = doc.get("last_alert_at")
        if last_alert_iso:
            try:
                last_alert = datetime.fromisoformat(last_alert_iso.replace("Z", "+00:00"))
                if now - last_alert < timedelta(minutes=_ALERT_COOLDOWN_MINUTES):
                    return
            except Exception:
                pass

        # Send SMS alert
        phone = os.environ.get(_ALERT_PHONE_ENV, "").strip()
        if not phone:
            logger.warning(f"[FallbackMonitor] {service}/{primary} failed {count}x — but {_ALERT_PHONE_ENV} not set")
            return

        msg = (
            f"AUREM ALERT: {service}/{primary} has failed {count} times. "
            f"Last reason: {(reason or 'unknown')[:80]}. "
            f"Fallback is active but please investigate."
        )
        sent_ok = await _send_sms_alert(phone, msg)
        await db.fallback_failure_state.update_one(
            key,
            {"$set": {"last_alert_at": now.isoformat(),
                      "last_alert_ok": bool(sent_ok)}},
        )
        logger.warning(f"[FallbackMonitor] ALERT sent for {service}/{primary} (count={count}, sms_ok={sent_ok})")
    except Exception as e:
        logger.debug(f"[FallbackMonitor] record_primary_failure failed: {e}")


async def reset_primary_failure(db, *, service: str, primary: str) -> None:
    """Reset the consecutive-failure counter (call on success)."""
    if db is None:
        return
    try:
        await db.fallback_failure_state.update_one(
            {"service": service, "primary": primary},
            {"$set": {"consecutive_failures": 0,
                      "last_success_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[FallbackMonitor] reset failed: {e}")


async def _send_sms_alert(phone: str, body: str) -> bool:
    """Send the admin-alert SMS via Twilio. Returns True on success."""
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_num = os.environ.get("TWILIO_PHONE_NUMBER", "") or os.environ.get("TWILIO_FROM_NUMBER", "")
    if not (sid and token and from_num):
        logger.warning("[FallbackMonitor] Twilio not configured — cannot send admin alert")
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                auth=(sid, token),
                data={"From": from_num, "To": phone, "Body": body},
            )
        return resp.status_code in (200, 201)
    except Exception as e:
        logger.warning(f"[FallbackMonitor] SMS alert send failed: {e}")
        return False
