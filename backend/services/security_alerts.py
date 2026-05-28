"""
services/security_alerts.py — iter D-47

Fire an audit alert when a customer's security keys rotate (self-rotate
or admin force-rotate). Best-effort: never raise to the caller. Two
optional channels, both env-gated:

  * Email via Resend  — `SECURITY_ALERT_EMAIL` (recipient) + the
                        platform's existing RESEND_API_KEY
  * Slack webhook    — `SECURITY_ALERT_SLACK_WEBHOOK` (incoming-webhook URL)

If neither env var is set, the helper logs the event and returns 0
sent. The function is intentionally side-effect-only.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _send_slack(webhook: str, payload: dict[str, Any]) -> bool:
    text = (
        f":lock: *AUREM security keys rotated*\n"
        f"• user: `{payload.get('email') or payload.get('user_id')}`\n"
        f"• tenant: `{payload.get('tenant_id', 'default')}`\n"
        f"• status: `{payload.get('event_type')}`\n"
        f"• reason: {payload.get('reason') or '—'}\n"
        f"• ip: `{payload.get('ip_address') or '—'}`\n"
        f"• at: `{payload.get('at')}`"
    )
    try:
        async with httpx.AsyncClient(timeout=6.0) as c:
            r = await c.post(webhook, json={"text": text})
        return 200 <= r.status_code < 300
    except Exception as e:
        logger.warning(f"[sec-alert][slack] {type(e).__name__}: {e}")
        return False


async def _send_email(api_key: str, to: str, payload: dict[str, Any]) -> bool:
    subject = "AUREM security keys rotated"
    html = (
        f"<h2>AUREM security keys rotated</h2>"
        f"<table style='font-family:monospace;font-size:13px'>"
        f"<tr><td>user</td><td>{payload.get('email') or payload.get('user_id')}</td></tr>"
        f"<tr><td>tenant</td><td>{payload.get('tenant_id', 'default')}</td></tr>"
        f"<tr><td>event</td><td>{payload.get('event_type')}</td></tr>"
        f"<tr><td>reason</td><td>{payload.get('reason') or '—'}</td></tr>"
        f"<tr><td>ip</td><td>{payload.get('ip_address') or '—'}</td></tr>"
        f"<tr><td>at</td><td>{payload.get('at')}</td></tr>"
        f"</table>"
    )
    try:
        async with httpx.AsyncClient(timeout=6.0) as c:
            r = await c.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type":  "application/json"},
                json={
                    "from":    os.environ.get("SECURITY_ALERT_FROM",
                                              "alerts@aurem.live"),
                    "to":      [to],
                    "subject": subject,
                    "html":    html,
                },
            )
        return 200 <= r.status_code < 300
    except Exception as e:
        logger.warning(f"[sec-alert][email] {type(e).__name__}: {e}")
        return False


async def notify_key_rotation(
    *,
    event_type: str,         # "self_rotated" | "admin_force_rotated"
    user_id: str,
    email: str = "",
    tenant_id: str = "default",
    ip_address: str = "",
    reason: str = "",
) -> dict[str, Any]:
    """Fire and forget. Returns the (best-effort) delivery counts so
    tests can assert the helper at least ATTEMPTED both channels."""
    payload = {
        "event_type":  event_type,
        "user_id":     user_id,
        "email":       email,
        "tenant_id":   tenant_id,
        "ip_address":  ip_address,
        "reason":      reason,
        "at":          _now_iso(),
    }
    logger.info(f"[sec-alert] {event_type} user={user_id} ip={ip_address}")

    slack_url = (os.environ.get("SECURITY_ALERT_SLACK_WEBHOOK") or "").strip()
    email_to  = (os.environ.get("SECURITY_ALERT_EMAIL") or "").strip()
    resend    = (os.environ.get("RESEND_API_KEY") or "").strip()

    slack_ok = False
    email_ok = False
    if slack_url:
        slack_ok = await _send_slack(slack_url, payload)
    if email_to and resend:
        email_ok = await _send_email(resend, email_to, payload)

    return {
        "ok":             slack_ok or email_ok or (not slack_url and not email_to),
        "slack_attempted": bool(slack_url),
        "slack_ok":       slack_ok,
        "email_attempted": bool(email_to and resend),
        "email_ok":       email_ok,
        "payload":        payload,
    }
