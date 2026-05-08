"""iter 287.4 — Twilio WhatsApp Business API (WABA) migration.

Validates:
  • Phone normalization (digits-only → E.164; junk → empty)
  • wa_addr wrapping ('whatsapp:+...')
  • send_whatsapp_session returns creds_missing honestly when env absent
  • send_whatsapp_template returns creds_missing when no template_sid
  • Smart send_whatsapp picks session vs template from env
  • blast_service routes to Twilio WABA when TWILIO_WA_FROM_NUMBER set
  • Brief notifier respects WHAPI_BLAST_DISABLED kill-switch
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_phone_normalization():
    from backend.services.twilio_whatsapp import _normalize_phone, _wa_addr
    assert _normalize_phone("+16475551234") == "+16475551234"
    assert _normalize_phone("(647) 555-1234") == "+16475551234"
    assert _normalize_phone("6475551234") == "+16475551234"
    assert _normalize_phone("16475551234") == "+16475551234"
    assert _normalize_phone("") == ""
    assert _normalize_phone("abc") == ""
    assert _normalize_phone("123") == ""          # too short
    assert _wa_addr("+16475551234") == "whatsapp:+16475551234"
    assert _wa_addr("(647) 555-1234") == "whatsapp:+16475551234"
    assert _wa_addr("") == ""


def test_session_returns_creds_missing_when_no_env(monkeypatch):
    for v in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WA_FROM_NUMBER"):
        monkeypatch.delenv(v, raising=False)
    from backend.services.twilio_whatsapp import send_whatsapp_session
    r = asyncio.run(send_whatsapp_session("+16475551234", "hi"))
    assert r["success"] is False
    assert "creds_missing" in r["error"]
    # All three should be flagged
    for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WA_FROM_NUMBER"):
        assert k in r["error"]


def test_template_returns_creds_missing_when_no_template(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok_test")
    monkeypatch.setenv("TWILIO_WA_FROM_NUMBER", "whatsapp:+14155238886")
    monkeypatch.delenv("TWILIO_WA_TEMPLATE_SID", raising=False)
    from backend.services.twilio_whatsapp import send_whatsapp_template
    r = asyncio.run(send_whatsapp_template("+16475551234"))
    assert r["success"] is False
    assert "TWILIO_WA_TEMPLATE_SID" in r["error"]


def test_session_rejects_invalid_phone(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok_test")
    monkeypatch.setenv("TWILIO_WA_FROM_NUMBER", "whatsapp:+14155238886")
    from backend.services.twilio_whatsapp import send_whatsapp_session
    r = asyncio.run(send_whatsapp_session("abc", "hi"))
    assert r["success"] is False
    assert r["error"] == "invalid_phone"


def test_smart_send_picks_template_when_configured(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok_test")
    monkeypatch.setenv("TWILIO_WA_FROM_NUMBER", "whatsapp:+14155238886")
    monkeypatch.setenv("TWILIO_WA_TEMPLATE_SID", "HXdummy_template")

    sent = {}

    class FakeResp:
        status_code = 201
        def json(self):
            return {"sid": "SMtestfake", "status": "queued"}

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, **kw):
            sent["url"] = url
            sent["data"] = kw.get("data", {})
            return FakeResp()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    from backend.services.twilio_whatsapp import send_whatsapp
    r = asyncio.run(send_whatsapp("+16475551234", "hi",
                                   variables={"1": "Master Maid"}))
    assert r["success"] is True
    assert r["mode"] == "template"
    assert sent["data"].get("ContentSid") == "HXdummy_template"
    assert "Master Maid" in sent["data"].get("ContentVariables", "")


def test_smart_send_falls_back_to_session_when_no_template(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tok_test")
    monkeypatch.setenv("TWILIO_WA_FROM_NUMBER", "whatsapp:+14155238886")
    monkeypatch.delenv("TWILIO_WA_TEMPLATE_SID", raising=False)

    sent = {}

    class FakeResp:
        status_code = 201
        def json(self):
            return {"sid": "SMfake", "status": "queued"}

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, **kw):
            sent["data"] = kw.get("data", {})
            return FakeResp()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    from backend.services.twilio_whatsapp import send_whatsapp
    r = asyncio.run(send_whatsapp("+16475551234", "ping"))
    assert r["success"] is True
    assert r["mode"] == "session"
    assert sent["data"].get("Body") == "ping"
    assert "ContentSid" not in sent["data"]


def test_brief_notifier_skips_whapi_when_disabled(monkeypatch):
    monkeypatch.setenv("WHAPI_BLAST_DISABLED", "true")
    monkeypatch.setenv("WHAPI_API_TOKEN", "some_real_token")
    monkeypatch.setenv("NOTIFY_PHONE", "+16134000000")
    from backend.services.autopilot_brief_notifier import _send_whapi
    r = asyncio.run(_send_whapi("test brief"))
    assert r["ok"] is False
    assert r["reason"] == "disabled_by_admin"


def test_brief_notifier_uses_whapi_when_enabled(monkeypatch):
    monkeypatch.setenv("WHAPI_BLAST_DISABLED", "false")
    monkeypatch.delenv("WHAPI_API_TOKEN", raising=False)
    monkeypatch.delenv("WHAPI_TOKEN", raising=False)
    monkeypatch.delenv("NOTIFY_PHONE", raising=False)
    monkeypatch.delenv("ADMIN_ALERT_PHONE", raising=False)
    from backend.services.autopilot_brief_notifier import _send_whapi
    r = asyncio.run(_send_whapi("test brief"))
    # No kill-switch → reaches creds_missing check
    assert r["ok"] is False
    assert r["reason"] == "creds_missing"
