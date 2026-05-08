"""
iter 282al-16 — Tests for auto-refund flow in website_repair_service
====================================================================
Verifies:
  1. auto_refund_paid_repair skips when lead is not paid
  2. Skips when no payment_intent_id is stored
  3. Skips when STRIPE_SECRET_KEY missing
  4. On paid + intent + key → calls stripe.Refund.create, updates
     repair_orders + campaign_leads + db.refunds, returns ok=True
  5. repair_existing_site emits `refund` key in its failure path
"""
from __future__ import annotations

import sys
import types
import pytest
from unittest.mock import AsyncMock, MagicMock


# ───────────────────────── helpers ─────────────────────────
def _stub_stripe_module(monkeypatch, refund_id="re_test_001",
                         should_raise: bool = False):
    """Install a fake `stripe` module that captures Refund.create calls."""
    captured: dict = {}

    class _FakeRefund:
        @staticmethod
        def create(**kwargs):
            captured["kwargs"] = kwargs
            if should_raise:
                raise RuntimeError("stripe_down")
            return {"id": refund_id}

    fake_stripe = types.ModuleType("stripe")
    fake_stripe.Refund = _FakeRefund
    fake_stripe.api_key = ""
    monkeypatch.setitem(sys.modules, "stripe", fake_stripe)
    return captured, fake_stripe


def _build_mock_db(order=None):
    db = MagicMock()
    db.repair_orders.find_one = AsyncMock(return_value=order)
    db.repair_orders.update_one = AsyncMock(return_value=None)
    db.campaign_leads.update_one = AsyncMock(return_value=None)
    db.refunds.insert_one = AsyncMock(return_value=None)
    return db


# ───────────────────────── tests ─────────────────────────
@pytest.mark.asyncio
async def test_refund_skips_when_not_paid(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
    _stub_stripe_module(monkeypatch)
    from services.website_repair_service import auto_refund_paid_repair

    db = _build_mock_db(order=None)  # no paid order found
    out = await auto_refund_paid_repair(
        db, {"_id": "l1", "repair_paid": False}, reason="qa_failed",
    )
    assert out["ok"] is False
    assert out["skipped"] == "not_paid"
    db.refunds.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_refund_skips_when_no_payment_intent(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
    _stub_stripe_module(monkeypatch)
    from services.website_repair_service import auto_refund_paid_repair

    order = {"order_id": "ord_1", "status": "paid", "amount_cad": 19700}
    db = _build_mock_db(order=order)
    out = await auto_refund_paid_repair(
        db, {"_id": "l1"}, reason="qa_failed",
    )
    assert out["ok"] is False
    assert out["skipped"] == "no_payment_intent"


@pytest.mark.asyncio
async def test_refund_skips_when_no_stripe_key(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    _stub_stripe_module(monkeypatch)
    from services.website_repair_service import auto_refund_paid_repair

    order = {"order_id": "ord_1", "status": "paid",
             "stripe_payment_intent": "pi_123", "amount_cad": 19700}
    db = _build_mock_db(order=order)
    out = await auto_refund_paid_repair(
        db, {"_id": "l1"}, reason="qa_failed",
    )
    assert out["ok"] is False
    assert out["skipped"] == "no_stripe_key"


@pytest.mark.asyncio
async def test_refund_fires_when_paid_and_intent_present(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
    captured, _fake = _stub_stripe_module(monkeypatch, refund_id="re_OK_001")
    from services.website_repair_service import auto_refund_paid_repair

    order = {"order_id": "ord_1", "status": "paid",
             "stripe_payment_intent": "pi_paid_123", "amount_cad": 19700}
    db = _build_mock_db(order=order)

    out = await auto_refund_paid_repair(
        db, {"_id": "l1", "business_name": "ACME", "email": "a@b.ca"},
        reason="qa_failed_3_attempts",
    )

    assert out["ok"] is True
    assert out["refund_id"] == "re_OK_001"
    assert out["reason"] == "qa_failed_3_attempts"
    # Stripe was called with the right PI
    assert captured["kwargs"]["payment_intent"] == "pi_paid_123"
    # DB side-effects
    db.repair_orders.update_one.assert_awaited_once()
    upd_call = db.repair_orders.update_one.await_args
    assert upd_call.args[1]["$set"]["status"] == "refunded"
    db.campaign_leads.update_one.assert_awaited_once()
    db.refunds.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_refund_records_stripe_error_but_does_not_raise(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
    _stub_stripe_module(monkeypatch, should_raise=True)
    from services.website_repair_service import auto_refund_paid_repair

    order = {"order_id": "ord_1", "status": "paid",
             "stripe_payment_intent": "pi_paid_123", "amount_cad": 19700}
    db = _build_mock_db(order=order)
    out = await auto_refund_paid_repair(
        db, {"_id": "l1"}, reason="qa_failed",
    )

    # Function should not raise — but it logs error and still records the attempt
    assert out["ok"] is False
    assert out["error"] == "stripe_down"
    # refunds row still inserted so ops has a trail
    db.refunds.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_repair_existing_site_returns_refund_key_on_qa_failure(monkeypatch):
    """repair_existing_site should include `refund` in its failure return."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test")
    _stub_stripe_module(monkeypatch, refund_id="re_FAIL_PATH")
    import services.website_repair_service as svc

    # Stub internal helpers so we bypass AWB + QA loop
    async def _fake_qa_loop(db, slug, url, max_attempts=3):
        return {"final_status": "failed", "ready_to_send": False,
                "attempts": 3, "last_result": {"failed": 5}}

    import services.site_qa_service as qa
    monkeypatch.setattr(qa, "qa_repair_loop", _fake_qa_loop, raising=False)

    async def _fake_build(db, lead_id, style_hint=None):
        return {"slug": "acme-slug", "live_url": "https://x.ca",
                "preview_url": "https://x.ca"}
    import services.auto_website_builder as awb
    monkeypatch.setattr(awb, "build_site_for_lead", _fake_build, raising=False)

    audit_row = {
        "lead_id": "l1", "website_url": "https://x.ca",
        "overall_score": 40, "issues": [
            {"priority": "critical", "fix": "Add phone link"},
        ],
    }
    order = {"order_id": "ord_77", "status": "paid",
             "stripe_payment_intent": "pi_77",
             "amount_cad": 19700, "lead_id": "l1"}

    db = MagicMock()
    db.site_audits.find_one = AsyncMock(return_value=audit_row)
    db.repair_orders.find_one = AsyncMock(return_value=order)
    db.repair_orders.update_one = AsyncMock(return_value=None)
    db.campaign_leads.update_one = AsyncMock(return_value=None)
    db.refunds.insert_one = AsyncMock(return_value=None)
    db.sentinel_alerts.insert_one = AsyncMock(return_value=None)

    out = await svc.repair_existing_site(
        db, {"_id": "l1", "business_name": "ACME", "email": "a@b.ca"},
    )
    assert out["ok"] is False
    assert out["reason"] == "qa_failed"
    assert "refund" in out
    assert out["refund"]["refund_id"] == "re_FAIL_PATH"
