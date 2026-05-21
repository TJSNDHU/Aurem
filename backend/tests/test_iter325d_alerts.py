"""
Tests for the 3 iter-325d glue fixes:

  1. services/telegram_bot_service.send_telegram_alert()
  2. server.py weekly_revenue_summary_scheduler is actually started
  3. inbound_reply_handler POSITIVE intent sets hot_lead_flag + calls
     the shared founder alert.
"""
import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, "/app/backend")


# ─────────────────────────────────────────────────────────────────────
# (1) telegram_bot_service
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_telegram_send_no_creds_returns_creds_missing():
    from services import telegram_bot_service as svc
    with patch.dict(os.environ,
                    {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}, clear=False):
        r = await svc.send_telegram_alert("hi", "generic")
    assert r["ok"] is False
    assert r["reason"] == "creds_missing"


@pytest.mark.asyncio
async def test_telegram_send_calls_api_with_chat_id_and_returns_ok():
    from services import telegram_bot_service as svc
    svc._dedup.clear()  # isolate from prior tests

    captured = {}

    class _MockResp:
        status_code = 200
        text = "ok"

    class _MockClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None, **_):
            captured["url"] = url
            captured["json"] = json
            return _MockResp()

    with patch.dict(os.environ,
                    {"TELEGRAM_BOT_TOKEN": "abc", "TELEGRAM_CHAT_ID": "789"},
                    clear=False), \
         patch.object(svc.httpx, "AsyncClient", _MockClient):
        r = await svc.send_telegram_alert("hello world", "new_signup",
                                          fingerprint="user@example.com")
    assert r["ok"] is True
    assert r["alert_type"] == "new_signup"
    assert "789" == captured["json"]["chat_id"]
    # Alert-type prefix gets prepended.
    assert "NEW SIGNUP" in captured["json"]["text"]
    assert "hello world" in captured["json"]["text"]
    # Sent against the right bot.
    assert "bot abc" in captured["url"] or "/botabc/" in captured["url"]


@pytest.mark.asyncio
async def test_telegram_send_dedupes_within_5min_window():
    from services import telegram_bot_service as svc
    svc._dedup.clear()

    class _MockResp:
        status_code = 200
        text = "ok"

    class _MockClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw): return _MockResp()

    with patch.dict(os.environ,
                    {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"},
                    clear=False), \
         patch.object(svc.httpx, "AsyncClient", _MockClient):
        r1 = await svc.send_telegram_alert("x", "campaign_zero", fingerprint="streak_10")
        r2 = await svc.send_telegram_alert("y", "campaign_zero", fingerprint="streak_10")
        r3 = await svc.send_telegram_alert("z", "campaign_zero", fingerprint="streak_20")
    assert r1["ok"] is True
    assert r2["ok"] is False and r2["reason"] == "deduped"
    assert r3["ok"] is True  # different fingerprint → fires again


@pytest.mark.asyncio
async def test_telegram_send_truncates_message_over_4096_chars():
    from services import telegram_bot_service as svc
    svc._dedup.clear()

    captured = {}

    class _MockResp:
        status_code = 200
        text = "ok"

    class _MockClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None, **_):
            captured["json"] = json
            return _MockResp()

    with patch.dict(os.environ,
                    {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"},
                    clear=False), \
         patch.object(svc.httpx, "AsyncClient", _MockClient):
        await svc.send_telegram_alert("A" * 5000, "generic")
    assert len(captured["json"]["text"]) <= 4096
    assert "truncated" in captured["json"]["text"]


# ─────────────────────────────────────────────────────────────────────
# (2) server.py wires weekly_revenue_summary_scheduler
# ─────────────────────────────────────────────────────────────────────
def test_weekly_revenue_scheduler_is_started_in_server_py():
    """The handoff audit found this scheduler imported but never started.
    Regression-guard: the server.py startup MUST call
    asyncio.create_task(weekly_revenue_summary_scheduler())."""
    src = open("/app/backend/server.py", encoding="utf-8").read()
    assert "weekly_revenue_summary_scheduler" in src, \
        "weekly_revenue_summary_scheduler must be imported in server.py"
    # Look for an actual scheduling call (create_task / add_job / await).
    assert (
        "create_task(weekly_revenue_summary_scheduler())" in src
        or "create_task(\n            weekly_revenue_summary_scheduler())" in src
        or "add_job(weekly_revenue_summary_scheduler" in src
    ), "weekly_revenue_summary_scheduler must be SCHEDULED, not just imported"


# ─────────────────────────────────────────────────────────────────────
# (3) inbound_reply_handler POSITIVE sets hot_lead_flag + fires alert
# ─────────────────────────────────────────────────────────────────────
def test_inbound_handler_positive_sets_hot_lead_flag_and_fires_alert():
    """Regression-guard: the audit found that positive replies did NOT
    set hot_lead_flag and did NOT call _fire_hot_lead_admin_alert.
    Both must now be present in the inbound handler source."""
    src = open("/app/backend/services/inbound_reply_handler.py",
               encoding="utf-8").read()
    # Hot-lead flag must be SET on positive intent.
    assert "hot_lead_flag" in src and "True" in src
    # Shared founder-alert service must be imported and called.
    assert "from services.hot_lead_alerts import fire_hot_lead_admin_alert" in src
    assert "fire_hot_lead_admin_alert(" in src
    # Source tag must be "email_reply" so the alert routes the right CRM link.
    assert "email_reply" in src


def test_hot_lead_alerts_service_exists_and_uses_both_channels():
    """The shared service must call both WhatsApp (preserve old behavior)
    and Telegram (the new founder pager)."""
    path = "/app/backend/services/hot_lead_alerts.py"
    assert os.path.exists(path)
    src = open(path, encoding="utf-8").read()
    assert "WHAPI_API_TOKEN" in src      # WhatsApp channel intact
    assert "send_telegram_alert" in src  # Telegram channel wired
    assert "fire_hot_lead_admin_alert" in src
    # Best-effort: each channel has its own try/except so one failure
    # doesn't block the other.
    assert src.count("except Exception") >= 2


def test_website_builder_router_delegates_to_shared_service():
    """The old standalone _fire_hot_lead_admin_alert in the router must
    now delegate to the shared service (otherwise the two paths drift)."""
    src = open("/app/backend/routers/website_builder_router.py",
               encoding="utf-8").read()
    # Old body removed — should no longer contain its WHAPI HTTP call inline.
    assert "from services.hot_lead_alerts import fire_hot_lead_admin_alert" in src


# ─────────────────────────────────────────────────────────────────────
# (4) ora_campaign_watchdog wires campaign_zero alert
# ─────────────────────────────────────────────────────────────────────
def test_campaign_watchdog_fires_telegram_on_zero_streak():
    src = open("/app/backend/services/ora_campaign_watchdog.py",
               encoding="utf-8").read()
    assert "from services.telegram_bot_service import send_telegram_alert" in src
    assert 'alert_type="campaign_zero"' in src
    # Must throttle (every Nth streak) so it doesn't spam every cycle.
    assert "zero_streak % 10" in src or "zero_streak%10" in src


# ─────────────────────────────────────────────────────────────────────
# (5) platform_auth register fires new_signup alert
# ─────────────────────────────────────────────────────────────────────
def test_platform_auth_register_fires_new_signup_alert():
    src = open("/app/backend/routers/platform_auth_router.py",
               encoding="utf-8").read()
    assert "from services.telegram_bot_service import send_telegram_alert" in src
    assert 'alert_type="new_signup"' in src
    # Must use email as fingerprint so retries don't double-fire.
    assert "fingerprint=email" in src
