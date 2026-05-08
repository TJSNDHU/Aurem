"""
iter 282al-17 — Tests for second-chance outreach bucket
========================================================
Verifies:
  1. auto_refund_paid_repair flips `second_chance_eligible=True` +
     `second_chance_after = now + 14d` on refunded leads
  2. check_eligibility / should_send pure filters
  3. build_offer_email shape (subject + body includes $297 + STOP)
  4. run_second_chance_outreach picks eligible leads, sends email,
     flips second_chance_sent, and skips already-sent + pre-window
"""
from __future__ import annotations

import sys
import types
from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ───────────────────────── helpers ─────────────────────────
def _stub_stripe(monkeypatch, refund_id="re_sc_001"):
    class _FakeRefund:
        @staticmethod
        def create(**kw):
            return {"id": refund_id}
    fake = types.ModuleType("stripe")
    fake.Refund = _FakeRefund
    fake.api_key = ""
    monkeypatch.setitem(sys.modules, "stripe", fake)


# ═══════════════════════ TASK 1: flags set on refund ═══════════════════════
@pytest.mark.asyncio
async def test_refund_sets_second_chance_eligible(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
    _stub_stripe(monkeypatch)
    from services.website_repair_service import auto_refund_paid_repair

    order = {"order_id": "ord_1", "status": "paid",
             "stripe_payment_intent": "pi_777",
             "amount_cad": 19700, "lead_id": "l1"}
    db = MagicMock()
    db.repair_orders.find_one = AsyncMock(return_value=order)
    db.repair_orders.update_one = AsyncMock(return_value=None)
    db.campaign_leads.update_one = AsyncMock(return_value=None)
    db.refunds.insert_one = AsyncMock(return_value=None)

    out = await auto_refund_paid_repair(
        db, {"_id": "l1", "business_name": "ACME", "email": "a@b.ca"},
        reason="qa_failed_3_attempts",
    )
    assert out["ok"] is True

    # The campaign_leads update must include both second_chance flags
    call = db.campaign_leads.update_one.await_args
    set_fields = call.args[1]["$set"]
    assert set_fields["repair_status"] == "refunded"
    assert set_fields["second_chance_eligible"] is True
    assert "second_chance_after" in set_fields
    assert isinstance(set_fields["second_chance_after"], datetime)

    # Roughly 14 days in the future (allow ±1h drift)
    delta = set_fields["second_chance_after"] - set_fields["refunded_at"]
    assert timedelta(days=14) - timedelta(hours=1) <= delta <= timedelta(days=14) + timedelta(hours=1)


# ═══════════════════════ TASK 2: pure filters ═══════════════════════
def test_check_eligibility_false_by_default():
    from services.second_chance_service import check_eligibility
    assert check_eligibility({}) is False
    assert check_eligibility({"second_chance_eligible": False}) is False


def test_check_eligibility_true_when_flagged():
    from services.second_chance_service import check_eligibility
    assert check_eligibility({"second_chance_eligible": True}) is True


def test_should_send_skips_if_not_eligible():
    from services.second_chance_service import should_send
    lead = {"second_chance_eligible": False,
            "email": "a@b.ca",
            "second_chance_after": datetime.now(timezone.utc) - timedelta(days=1)}
    assert should_send(lead) is False


def test_should_send_skips_if_already_sent():
    from services.second_chance_service import should_send
    lead = {
        "second_chance_eligible": True,
        "second_chance_sent":     True,
        "email":                  "a@b.ca",
        "second_chance_after":    datetime.now(timezone.utc) - timedelta(days=1),
    }
    assert should_send(lead) is False


def test_should_send_skips_before_window():
    from services.second_chance_service import should_send
    lead = {
        "second_chance_eligible": True,
        "second_chance_sent":     False,
        "email":                  "a@b.ca",
        "second_chance_after":    datetime.now(timezone.utc) + timedelta(days=2),
    }
    assert should_send(lead) is False


def test_should_send_skips_without_email():
    from services.second_chance_service import should_send
    lead = {
        "second_chance_eligible": True,
        "second_chance_sent":     False,
        "second_chance_after":    datetime.now(timezone.utc) - timedelta(days=1),
        "email":                  "",
    }
    assert should_send(lead) is False


def test_should_send_returns_true_when_window_elapsed():
    from services.second_chance_service import should_send
    lead = {
        "second_chance_eligible": True,
        "second_chance_sent":     False,
        "email":                  "a@b.ca",
        "second_chance_after":    datetime.now(timezone.utc) - timedelta(days=1),
    }
    assert should_send(lead) is True


def test_should_send_accepts_iso_string_dates():
    from services.second_chance_service import should_send
    past_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    lead = {
        "second_chance_eligible": True,
        "second_chance_sent":     False,
        "email":                  "a@b.ca",
        "second_chance_after":    past_iso,
    }
    assert should_send(lead) is True


# ═══════════════════════ TASK 3: offer email shape ═══════════════════════
def test_build_offer_email_has_required_bits():
    from services.second_chance_service import build_offer_email
    msg = build_offer_email(
        {"business_name": "Brampton Plumbing", "email": "a@b.ca"},
        checkout_url="https://aurem.live/pay/XYZ",
    )
    assert "Brampton Plumbing" in msg["subject"]
    body = msg["body"]
    assert "$297" in body
    assert "STOP" in body
    assert "https://aurem.live/pay/XYZ" in body
    # Acknowledges the failure
    assert "refund" in body.lower() or "make it right" in body.lower()


# ═══════════════════════ TASK 4: cron happy + skip paths ═══════════════════════
@pytest.mark.asyncio
async def test_run_second_chance_sends_to_eligible_lead(monkeypatch):
    monkeypatch.setenv("STRIPE_PRICE_MANUAL_REPAIR", "price_manual_test")

    # Stub email sender
    sent_box = {}
    async def _fake_email(**kw):
        sent_box.update(kw)
        return {"ok": True}
    import services.email_service_resend as er
    monkeypatch.setattr(er, "send_email", _fake_email, raising=False)

    # Stub compose_outreach to a no-op so output is deterministic
    async def _fake_compose(**kw):
        return {"body": ""}
    import services.outreach_composer as oc
    monkeypatch.setattr(oc, "compose_outreach", _fake_compose, raising=False)

    # Stub telegram (module doesn't exist — stub via sys.modules)
    fake_tg = types.ModuleType("services.telegram_bot_service")
    async def _fake_tg(*a, **kw):
        return True
    fake_tg.send_telegram_alert = _fake_tg
    monkeypatch.setitem(sys.modules, "services.telegram_bot_service", fake_tg)

    now = datetime.now(timezone.utc)
    eligible = {
        "_id": "lead_A",
        "business_name": "ACME Plumbing",
        "city": "Brampton",
        "email": "lead@acme.ca",
        "second_chance_eligible": True,
        "second_chance_sent":     False,
        "second_chance_after":    now - timedelta(days=1),
    }

    # Async cursor mock
    class _Cursor:
        def __init__(self, rows): self._rows = rows
        def limit(self, *_): return self
        async def to_list(self, length=None): return self._rows

    db = MagicMock()
    db.campaign_leads.find = MagicMock(return_value=_Cursor([eligible]))
    db.campaign_leads.update_one = AsyncMock(return_value=None)

    from services.second_chance_service import run_second_chance_outreach
    out = await run_second_chance_outreach(db, max_send=5, now=now)

    assert out["sent"] == 1
    assert sent_box["to"] == "lead@acme.ca"
    assert "ACME Plumbing" in sent_box["subject"]
    assert "$297" in sent_box["body"]

    # Idempotency: flag flipped
    call = db.campaign_leads.update_one.await_args
    assert call.args[1]["$set"]["second_chance_sent"] is True
    assert "second_chance_sent_at" in call.args[1]["$set"]


@pytest.mark.asyncio
async def test_run_second_chance_skips_already_sent(monkeypatch):
    """If Mongo query returns a lead that already has second_chance_sent=True
    (data drift), should_send() should still refuse to re-send."""
    from services.second_chance_service import should_send
    now = datetime.now(timezone.utc)
    lead = {
        "second_chance_eligible": True,
        "second_chance_sent":     True,
        "email":                  "a@b.ca",
        "second_chance_after":    now - timedelta(days=1),
    }
    assert should_send(lead, now=now) is False


@pytest.mark.asyncio
async def test_run_second_chance_handles_no_db():
    from services.second_chance_service import run_second_chance_outreach
    out = await run_second_chance_outreach(None)
    assert out["sent"] == 0
    assert out["skipped"] == "no_db"
