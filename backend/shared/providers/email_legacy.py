"""
SendGrid → Resend Compat Shim
==============================
Drop-in replacement for:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

Usage (unchanged in callers):
    from services.sendgrid_compat import SendGridAPIClient, Mail
    sg = SendGridAPIClient(api_key=RESEND_KEY)  # key arg preserved for compat
    mail = Mail(from_email="x@y.com", to_emails="a@b.com", subject="Hi", html_content="<p>Hello</p>")
    sg.send(mail)

Under the hood: all sends go to Resend. Legacy SendGrid key is ignored.
"""
from __future__ import annotations

import os
import logging
from typing import Any, Union, Tuple
import httpx

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
_RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
_DEFAULT_FROM = os.environ.get("RESEND_FROM_EMAIL", "AUREM <ora@aurem.live>")


def _parse_from(value: Any) -> str:
    """SendGrid accepts ('email', 'name') tuples or plain strings — normalize to Resend format 'Name <email>'."""
    if isinstance(value, tuple) and len(value) == 2:
        email_addr, name = value
        return f"{name} <{email_addr}>"
    if isinstance(value, str):
        return value
    # From object with email/name attrs
    email_addr = getattr(value, "email", None)
    name = getattr(value, "name", None)
    if email_addr:
        return f"{name} <{email_addr}>" if name else str(email_addr)
    return _DEFAULT_FROM


def _parse_to(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_parse_to(v)[0] if isinstance(v, list) else str(v) for v in value]
    if isinstance(value, str):
        return [value]
    # SendGrid To object
    email_addr = getattr(value, "email", None)
    if email_addr:
        return [str(email_addr)]
    return [str(value)]


class Mail:
    """SendGrid Mail() stand-in. Captures fields used by existing code."""

    def __init__(
        self,
        from_email: Any = None,
        to_emails: Any = None,
        subject: str = "",
        html_content: Union[str, Any] = "",
        plain_text_content: Union[str, Any] = None,
        **kwargs: Any,
    ) -> None:
        self.from_email = _parse_from(from_email) if from_email else _DEFAULT_FROM
        self.to_list = _parse_to(to_emails) if to_emails else []
        self.subject = subject
        # html_content can be a SendGrid Content() object with .content attr
        if hasattr(html_content, "content"):
            self.html = str(html_content.content)
        else:
            self.html = str(html_content) if html_content else ""
        if hasattr(plain_text_content, "content"):
            self.text = str(plain_text_content.content)
        elif plain_text_content:
            self.text = str(plain_text_content)
        else:
            self.text = None
        self._extras = kwargs

    def _to_resend_payload(self) -> dict:
        payload = {
            "from": self.from_email,
            "to": self.to_list,
            "subject": self.subject,
            "html": self.html,
        }
        if self.text:
            payload["text"] = self.text
        return payload


class _Response:
    """Mimic SendGrid response object."""

    def __init__(self, ok: bool, status: int, body: str):
        self.status_code = status
        self.body = body
        self.ok = ok


class SendGridAPIClient:
    """Drop-in replacement for sendgrid.SendGridAPIClient. The `api_key` arg is accepted and ignored."""

    def __init__(self, api_key: str | None = None) -> None:
        # api_key preserved for signature compatibility; real auth uses RESEND_API_KEY from env
        self._ignored_key = api_key

    def send(self, message: Mail) -> _Response:
        """Synchronous send — matches SendGrid's `sg.send(mail)` pattern."""
        if not _RESEND_KEY:
            logger.warning("[sendgrid-shim] RESEND_API_KEY not set — email dropped")
            return _Response(False, 503, "no_api_key")
        try:
            with httpx.Client(timeout=10) as c:
                r = c.post(
                    RESEND_API_URL,
                    headers={"Authorization": f"Bearer {_RESEND_KEY}"},
                    json=message._to_resend_payload(),
                )
                if r.status_code >= 400:
                    logger.warning(f"[sendgrid-shim] Resend {r.status_code}: {r.text[:200]}")
                    return _Response(False, r.status_code, r.text)
                return _Response(True, r.status_code, r.text)
        except Exception as e:
            logger.exception("[sendgrid-shim] Resend send failed")
            return _Response(False, 500, str(e))
