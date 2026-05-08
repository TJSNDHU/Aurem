"""
iter 282al-18 · Part 5 Tests — Scout dispatcher routing split
==============================================================
Verifies:
  1. has_website() filter handles common cases (empty, placeholder, real)
  2. dispatch_lead_sync routes has-website → _audit_then_outreach
  3. dispatch_lead_sync routes no-website → _build_qa_then_notify
  4. _audit_then_outreach persists score on lead + returns route=audit…
  5. _build_qa_then_notify calls send_site_to_customer on QA ready
"""
from __future__ import annotations

import sys
import types
import pytest
from unittest.mock import AsyncMock, MagicMock


# ───────────────────────── has_website filter ─────────────────────────
def test_has_website_true_for_real_url():
    from services.scout_dispatcher import has_website
    assert has_website({"website": "https://acme.ca"}) is True
    assert has_website({"website_url": "https://acme.ca"}) is True


def test_has_website_false_for_empty_or_missing():
    from services.scout_dispatcher import has_website
    assert has_website({}) is False
    assert has_website({"website": ""}) is False
    assert has_website({"website": None}) is False


def test_has_website_false_for_placeholder_strings():
    from services.scout_dispatcher import has_website
    assert has_website({"website": "n/a"}) is False
    assert has_website({"website": "-"}) is False
    assert has_website({"website": "None"}) is False


def test_has_website_respects_explicit_false_flag():
    from services.scout_dispatcher import has_website
    lead = {"has_website": False, "website": "https://acme.ca"}
    assert has_website(lead) is False


# ───────────────────────── routing split ─────────────────────────
@pytest.mark.asyncio
async def test_dispatch_routes_has_website_to_audit(monkeypatch):
    calls = []

    async def _fake_audit(db, lead):
        calls.append(("audit", lead.get("_id")))
        return {"ok": True, "route": "audit_then_outreach"}

    async def _fake_build(db, lead):
        calls.append(("build", lead.get("_id")))
        return {"ok": True, "route": "build_qa_then_notify"}

    import services.scout_dispatcher as sd
    monkeypatch.setattr(sd, "_audit_then_outreach", _fake_audit)
    monkeypatch.setattr(sd, "_build_qa_then_notify", _fake_build)

    out = await sd.dispatch_lead_sync(
        MagicMock(),
        {"_id": "l1", "business_name": "ACME", "website": "https://acme.ca"},
    )
    assert out["route"] == "audit_then_outreach"
    assert calls == [("audit", "l1")]


@pytest.mark.asyncio
async def test_dispatch_routes_no_website_to_build(monkeypatch):
    calls = []

    async def _fake_audit(db, lead):
        calls.append("audit")
        return {"ok": True}

    async def _fake_build(db, lead):
        calls.append("build")
        return {"ok": True, "route": "build_qa_then_notify"}

    import services.scout_dispatcher as sd
    monkeypatch.setattr(sd, "_audit_then_outreach", _fake_audit)
    monkeypatch.setattr(sd, "_build_qa_then_notify", _fake_build)

    out = await sd.dispatch_lead_sync(
        MagicMock(),
        {"_id": "l2", "business_name": "No-Web Co"},
    )
    assert out["route"] == "build_qa_then_notify"
    assert calls == ["build"]


# ───────────────────────── audit path end-to-end ─────────────────────────
@pytest.mark.asyncio
async def test_audit_then_outreach_persists_score_and_calls_email(monkeypatch):
    # Stub audit_existing_site
    async def _fake_audit(db, lead):
        return {"overall_score": 45, "issues": [{"x": 1}, {"y": 2}, {"z": 3}]}

    import services.website_repair_service as wrs
    monkeypatch.setattr(wrs, "audit_existing_site", _fake_audit)

    # Stub compose_outreach
    async def _fake_compose(**kw):
        return {"body": "composed body"}
    import services.outreach_composer as oc
    monkeypatch.setattr(oc, "compose_outreach", _fake_compose, raising=False)

    # Stub email
    sent = {}
    async def _fake_email(**kw):
        sent.update(kw)
        return {"ok": True}
    import services.email_service_resend as er
    monkeypatch.setattr(er, "send_email", _fake_email, raising=False)

    # Stub shortlink — may not exist as module; install via sys.modules
    fake_sl = types.ModuleType("services.shortlink_service")
    async def _fake_create(db, lid, url, **kw):
        return {"short_url": "https://aur.ly/xyz"}
    fake_sl.create_shortlink = _fake_create
    monkeypatch.setitem(sys.modules, "services.shortlink_service", fake_sl)

    # Stub twilio whatsapp — skip
    fake_tw = types.ModuleType("services.twilio_whatsapp")
    async def _fake_wa(phone, body, **kw):
        return True
    fake_tw.send_whatsapp = _fake_wa
    monkeypatch.setitem(sys.modules, "services.twilio_whatsapp", fake_tw)

    db = MagicMock()
    db.campaign_leads.update_one = AsyncMock(return_value=None)

    from services.scout_dispatcher import _audit_then_outreach
    out = await _audit_then_outreach(
        db,
        {"_id": "l1", "business_name": "ACME Plumbing",
         "website": "https://acme.ca", "email": "a@b.ca"},
    )

    assert out["ok"] is True
    assert out["route"] == "audit_then_outreach"
    assert out["score"] == 45
    assert out["issues"] == 3
    assert "email" in out["channels"]
    # Persisted to lead
    db.campaign_leads.update_one.assert_awaited()
    set_fields = db.campaign_leads.update_one.await_args.args[1]["$set"]
    assert set_fields["site_score"] == 45
    assert set_fields["site_issues_count"] == 3
    assert set_fields["dispatch_route"] == "audit_then_outreach"
    # Email subject includes issue count
    assert "ACME" in sent["subject"]
    assert "3" in sent["subject"]


# ───────────────────────── build path end-to-end ─────────────────────────
@pytest.mark.asyncio
async def test_build_qa_then_notify_delivers_when_ready(monkeypatch):
    # Stub AWB build
    async def _fake_build(db, lead_id, style_hint=None):
        return {"slug": "acme-x", "live_url": "https://aurem.live/api/sites/acme-x"}
    import services.auto_website_builder as awb
    monkeypatch.setattr(awb, "build_site_for_lead", _fake_build, raising=False)

    # Stub QA loop
    async def _fake_qa(db, slug, url, max_attempts=3):
        return {"final_status": "verified", "ready_to_send": True, "attempts": 1}
    import services.site_qa_service as qs
    monkeypatch.setattr(qs, "qa_repair_loop", _fake_qa, raising=False)

    # Stub send
    sent = {}
    async def _fake_send(db, lead, slug, live_url, qa):
        sent.update({"slug": slug, "live_url": live_url})
        return {"channels_sent": ["email"], "short_url": live_url}
    monkeypatch.setattr(qs, "send_site_to_customer", _fake_send, raising=False)

    db = MagicMock()
    db.campaign_leads.update_one = AsyncMock(return_value=None)

    from services.scout_dispatcher import _build_qa_then_notify
    out = await _build_qa_then_notify(
        db, {"_id": "l2", "business_name": "No-Web Co", "email": "n@w.ca"},
    )

    assert out["ok"] is True
    assert out["route"] == "build_qa_then_notify"
    assert out["slug"] == "acme-x"
    assert out["notify"]["channels_sent"] == ["email"]
    assert sent["slug"] == "acme-x"


@pytest.mark.asyncio
async def test_build_qa_skips_send_when_qa_fails(monkeypatch):
    async def _fake_build(db, lid, style_hint=None):
        return {"slug": "bad-slug", "live_url": "https://x.ca"}
    import services.auto_website_builder as awb
    monkeypatch.setattr(awb, "build_site_for_lead", _fake_build, raising=False)

    async def _fake_qa(db, slug, url, max_attempts=3):
        return {"final_status": "failed", "ready_to_send": False, "attempts": 3}
    import services.site_qa_service as qs
    monkeypatch.setattr(qs, "qa_repair_loop", _fake_qa, raising=False)

    send_calls = []
    async def _fake_send(*a, **kw):
        send_calls.append(1)
        return {"channels_sent": ["email"]}
    monkeypatch.setattr(qs, "send_site_to_customer", _fake_send, raising=False)

    # Stub telegram (module doesn't exist in prod)
    fake_tg = types.ModuleType("services.telegram_bot_service")
    async def _fake_tg(*a, **kw): return True
    fake_tg.send_telegram_alert = _fake_tg
    monkeypatch.setitem(sys.modules, "services.telegram_bot_service", fake_tg)

    db = MagicMock()
    db.campaign_leads.update_one = AsyncMock(return_value=None)

    from services.scout_dispatcher import _build_qa_then_notify
    out = await _build_qa_then_notify(db, {"_id": "l3"})

    assert out["ok"] is True
    assert out["notify"]["qa_failed"] is True
    assert send_calls == []  # send_site_to_customer was NOT called
