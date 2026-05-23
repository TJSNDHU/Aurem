"""
iter 327h — Two production fixes:

  (a) /api/universal/webhooks/generic was 404 because the router
      was in the LEAN-mode skip list. The AUREM tracking pixel
      (static/aurem-pixel.js:44) hits this endpoint on every
      customer page view — every event was silently dropped.

  (d) appointment_scheduler_router.py:171-172 had two TODO lines
      ("Create Google Calendar event" / "Send confirmation email").
      Replaced with:
        - portable .ics invite generator (RFC 5545 compliant)
        - one-click Google Calendar quick-add URL
        - real GmailService send with honest ok/error reporting
        - GET /api/appointments/{id}/calendar.ics public endpoint
        - confirmation_email_sent_at / confirmation_email_error
          stamped on the appointment doc — no more silent
          "step 2 = completed" lies.

Also confirms appointment_scheduler_router has been removed from the
LEAN skip list so the booking endpoint serves traffic in production.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

BACKEND = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────
# (a) LEAN-mode skip list — universal & appointments must be loaded
# ─────────────────────────────────────────────

def test_universal_connector_not_in_lean_skip_list():
    from routers._registry_config import SKIP_IN_LEAN, make_should_skip
    assert "routers.universal_connector_router" not in SKIP_IN_LEAN
    assert make_should_skip(True)("routers.universal_connector_router") is False


def test_appointment_scheduler_not_in_lean_skip_list():
    from routers._registry_config import SKIP_IN_LEAN, make_should_skip
    assert "routers.appointment_scheduler_router" not in SKIP_IN_LEAN
    assert make_should_skip(True)("routers.appointment_scheduler_router") is False


def test_lean_skip_list_documents_the_universal_reinclusion():
    """The reason the router was disabled must live near the skip
    list itself so the next maintainer doesn't re-disable it."""
    src = (BACKEND / "routers" / "_registry_config.py").read_text()
    assert "iter 327h" in src
    assert "aurem-pixel" in src


# ─────────────────────────────────────────────
# (a) Webhook router exists + handles 'generic'
# ─────────────────────────────────────────────

def test_universal_webhook_route_registered():
    from routers.universal_connector_router import router
    paths = {(r.path, tuple(sorted(r.methods))) for r in router.routes if hasattr(r, "methods")}
    assert ("/api/universal/webhooks/{platform}", ("POST",)) in paths


# ─────────────────────────────────────────────
# (d) ICS generator
# ─────────────────────────────────────────────

def _sample_appt():
    return {
        "appointment_id":         "appt_abc123",
        "customer_name":          "Jane Doe",
        "customer_email":         "jane@example.com",
        "appointment_type":       "consultation",
        "appointment_type_name":  "Skin Consultation",
        "appointment_datetime":   datetime(2026, 3, 15, 14, 30, tzinfo=timezone.utc),
        "duration_minutes":       30,
        "notes":                  "Mention sensitivity; allergic to fragrance.",
    }


def test_build_ics_returns_rfc5545_envelope():
    from routers.appointment_scheduler_router import _build_ics
    ics = _build_ics(_sample_appt())
    assert ics.startswith("BEGIN:VCALENDAR")
    assert "END:VCALENDAR" in ics
    assert "VERSION:2.0" in ics
    assert "PRODID:-//AUREM//Appointments//EN" in ics
    assert "BEGIN:VEVENT" in ics and "END:VEVENT" in ics
    # CRLF line endings per RFC 5545
    assert "\r\n" in ics
    # Datetimes are basic-format UTC
    assert "DTSTART:20260315T143000Z" in ics
    assert "DTEND:20260315T150000Z" in ics
    # UID + summary present
    assert "UID:appt_abc123@aurem.live" in ics
    assert "SUMMARY:Skin Consultation" in ics


def test_build_ics_escapes_special_chars_in_notes():
    from routers.appointment_scheduler_router import _build_ics
    appt = _sample_appt()
    appt["notes"] = "Line1; sub, item\nLine2"
    ics = _build_ics(appt)
    # ; , and \n must be escaped per RFC 5545
    assert "\\;" in ics
    assert "\\," in ics
    assert "\\n" in ics


# ─────────────────────────────────────────────
# (d) Google Calendar quick-add URL
# ─────────────────────────────────────────────

def test_google_quick_add_url_has_required_params():
    from routers.appointment_scheduler_router import _build_google_calendar_quick_add_url
    url = _build_google_calendar_quick_add_url(_sample_appt(), "https://aurem.live")
    assert url.startswith("https://calendar.google.com/calendar/render?")
    assert "action=TEMPLATE" in url
    # dates encoded as start/end basic UTC form
    assert "dates=20260315T143000Z%2F20260315T150000Z" in url
    # text + details survive urlencoding
    assert "text=" in url and "Skin+Consultation" in url


# ─────────────────────────────────────────────
# (d) Confirmation email — honest send result
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_confirmation_returns_error_when_gmail_unavailable():
    from routers.appointment_scheduler_router import _send_confirmation_email

    async def fake_get_gmail():
        return None

    with patch("routers.email_service._get_gmail_service", new=fake_get_gmail):
        result = await _send_confirmation_email(
            appointment=_sample_appt(),
            ics_url="https://aurem.live/api/appointments/appt_abc123/calendar.ics",
            gcal_url="https://calendar.google.com/calendar/render?action=TEMPLATE",
        )
    assert result["ok"] is False
    assert result["error"] == "gmail_service_unavailable"


@pytest.mark.asyncio
async def test_send_confirmation_returns_ok_when_gmail_send_succeeds():
    from routers.appointment_scheduler_router import _send_confirmation_email

    class _FakeGmail:
        async def send_email(self, **kwargs):
            # Capture the args so we can assert they're correct
            self.last = kwargs
            return {"success": True, "message_id": "msg_xyz"}

    fake = _FakeGmail()

    async def fake_get_gmail():
        return fake

    with patch("routers.email_service._get_gmail_service", new=fake_get_gmail):
        result = await _send_confirmation_email(
            appointment=_sample_appt(),
            ics_url="https://aurem.live/api/appointments/appt_abc123/calendar.ics",
            gcal_url="https://calendar.google.com/calendar/render?action=TEMPLATE&text=x",
        )

    assert result == {"ok": True, "message_id": "msg_xyz"}
    # Subject + recipient set correctly
    assert fake.last["to"] == "jane@example.com"
    assert "AUREM appointment is confirmed" in fake.last["subject"]
    # Both calendar links surface in plain text body
    assert "calendar.ics" in fake.last["body_text"]
    assert "calendar.google.com" in fake.last["body_text"]
    # HTML body present + branded
    assert "AUREM" in fake.last["body_html"]


@pytest.mark.asyncio
async def test_send_confirmation_returns_error_when_send_fails():
    from routers.appointment_scheduler_router import _send_confirmation_email

    class _FailGmail:
        async def send_email(self, **kwargs):
            return {"success": False, "error": "auth_token_expired"}

    async def fake_get_gmail():
        return _FailGmail()

    with patch("routers.email_service._get_gmail_service", new=fake_get_gmail):
        result = await _send_confirmation_email(
            appointment=_sample_appt(),
            ics_url="https://x/i.ics",
            gcal_url="https://x/g",
        )
    assert result["ok"] is False
    assert result["error"] == "auth_token_expired"


# ─────────────────────────────────────────────
# (d) Source-level checks: TODOs removed
# ─────────────────────────────────────────────

def test_old_todos_are_gone():
    src = (BACKEND / "routers" / "appointment_scheduler_router.py").read_text()
    assert "TODO: Create Google Calendar event" not in src
    assert "TODO: Send confirmation email" not in src


def test_router_exposes_ics_download_endpoint():
    from routers.appointment_scheduler_router import router
    paths = {(r.path, tuple(sorted(r.methods))) for r in router.routes if hasattr(r, "methods")}
    assert ("/api/appointments/{appointment_id}/calendar.ics", ("GET",)) in paths


def test_iter_327h_marker_present():
    s1 = (BACKEND / "routers" / "appointment_scheduler_router.py").read_text()
    s2 = (BACKEND / "routers" / "_registry_config.py").read_text()
    assert "iter 327h" in s1
    assert "iter 327h" in s2
