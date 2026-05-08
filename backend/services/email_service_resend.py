"""
AUREM Email Service — Resend Wrapper
=====================================
Drop-in replacement for the legacy SendGrid pattern used across 9 services.

Usage:
    from services.email_service_resend import send_email

    await send_email(
        to="user@example.com",
        subject="Welcome to AUREM",
        html="<h1>Hello</h1>",
        reply_to="support@aurem.live",  # optional
    )

Returns (ok: bool, message_id_or_error: str).
"""
from __future__ import annotations

import os
import logging
import httpx
from typing import Optional, List, Union

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
DEFAULT_FROM = os.environ.get("RESEND_FROM_EMAIL", "AUREM <ora@aurem.live>")


async def send_email(
    to: Union[str, List[str]],
    subject: str,
    html: str,
    from_email: Optional[str] = None,
    reply_to: Optional[str] = None,
    text: Optional[str] = None,
) -> tuple[bool, str]:
    """Send email via Resend. Backward-compatible API for SendGrid migration."""
    if not RESEND_KEY:
        logger.warning("[email] RESEND_API_KEY missing — email not sent")
        return False, "no_api_key"

    to_list = [to] if isinstance(to, str) else list(to)
    payload = {
        "from": from_email or DEFAULT_FROM,
        "to": to_list,
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text
    if reply_to:
        payload["reply_to"] = reply_to

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                RESEND_API_URL,
                headers={"Authorization": f"Bearer {RESEND_KEY}"},
                json=payload,
            )
            if r.status_code >= 400:
                logger.warning(f"[email] Resend {r.status_code}: {r.text[:200]}")
                return False, f"{r.status_code}: {r.text[:100]}"
            data = r.json()
            return True, data.get("id", "sent")
    except Exception as e:
        logger.exception("[email] Resend send failed")
        return False, str(e)


# Synchronous wrapper for legacy non-async callers
def send_email_sync(to, subject, html, **kwargs) -> tuple[bool, str]:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Can't block — schedule and return optimistic
            asyncio.create_task(send_email(to, subject, html, **kwargs))
            return True, "scheduled"
    except RuntimeError:
        pass
    return asyncio.run(send_email(to, subject, html, **kwargs))
