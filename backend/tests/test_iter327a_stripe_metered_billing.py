"""
iter 327a — Stripe metered billing usage record (P1 revenue leak fix)
=====================================================================

Closes the TODO at /app/backend/shared/commercial/billing_service.py:646:
overage_messages were tracked in our own `aurem_usage`
collection but never reported to Stripe → customers on metered plans
were silently NOT being billed for overages. Real money walking out
the door.

Fix:
  - `BillingService.record_overage()` now POSTs a MeterEvent to
    Stripe via `stripe.billing.MeterEvent.create(...)` — the
    Stripe Billing Meters API replaces the legacy UsageRecord call
    that was removed in stripe-python 8.0+. Each event carries the
    business's `stripe_meter_event_name` + `stripe_customer_id`.
  - An audit row lands in `db.stripe_usage_records` on EVERY call —
    success ("ok"), skipped ("no_stripe_meter_event_name" /
    "no_stripe_customer_id" / "no_stripe_api_key"), or failure
    ("fail" + error message).
  - On Stripe `AuthenticationError` (revoked key), the iter-326pp
    `alert_autonomous_401` Telegram channel fires with provider=stripe.
  - Audit write itself is best-effort — a transient Mongo failure
    never blocks the call that already updated internal usage.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import mongomock_motor

BACKEND = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _make_db():
    return mongomock_motor.AsyncMongoMockClient()["test_iter327a"]


async def _make_service(db, *, plan="business",
                         meter_event_name="aurem_messages",
                         stripe_customer_id="cus_test_xyz"):
    """Build a BillingService, seed one business with a billing row."""
    from shared.commercial.billing_service import BillingService
    svc = BillingService(db)
    await db.aurem_billing.insert_one({
        "business_id":              "biz_test_1",
        "plan":                     plan,
        "stripe_meter_event_name":  meter_event_name,
        "stripe_customer_id":       stripe_customer_id,
    })
    return svc


# ─────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_overage_posts_meter_event_and_audits():
    db = _make_db()
    svc = await _make_service(
        db, meter_event_name="aurem_msgs",
        stripe_customer_id="cus_real_999",
    )

    fake_event = MagicMock()
    fake_event.identifier = "evt_test_abc123"

    with patch("shared.commercial.billing_service.stripe.api_key",
                "sk_test_stub"), \
         patch("shared.commercial.billing_service.stripe.billing.MeterEvent.create",
                return_value=fake_event) as me_create:
        await svc.record_overage("biz_test_1", messages=150)

    # Stripe was called once with the right kwargs
    assert me_create.call_count == 1
    call = me_create.call_args
    assert call.kwargs["event_name"] == "aurem_msgs"
    assert isinstance(call.kwargs["timestamp"], int)
    payload = call.kwargs["payload"]
    assert payload["stripe_customer_id"] == "cus_real_999"
    assert payload["value"] == "150"  # MeterEvent value is a string

    # Audit row landed
    audits = await db.stripe_usage_records.find({}).to_list(length=10)
    assert len(audits) == 1
    a = audits[0]
    assert a["status"] == "ok"
    assert a["business_id"] == "biz_test_1"
    assert a["messages"] == 150
    assert a["stripe_meter_event_id"] == "evt_test_abc123"
    assert a["stripe_meter_event_name"] == "aurem_msgs"
    assert a["stripe_customer_id"] == "cus_real_999"


# ─────────────────────────────────────────────
# Skip paths
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_overage_skips_when_no_meter_event_name():
    db = _make_db()
    svc = await _make_service(db, meter_event_name=None)
    await db.aurem_billing.update_one(
        {"business_id": "biz_test_1"},
        {"$unset": {"stripe_meter_event_name": ""}},
    )
    with patch("shared.commercial.billing_service.stripe.api_key",
                "sk_test_stub"), \
         patch("shared.commercial.billing_service.stripe.billing.MeterEvent.create") as me_create:
        await svc.record_overage("biz_test_1", messages=10)

    assert me_create.call_count == 0
    audits = await db.stripe_usage_records.find({}).to_list(length=10)
    assert audits[0]["status"] == "skipped"
    assert audits[0]["reason"] == "no_stripe_meter_event_name"


@pytest.mark.asyncio
async def test_record_overage_skips_when_no_customer_id():
    db = _make_db()
    svc = await _make_service(db)
    await db.aurem_billing.update_one(
        {"business_id": "biz_test_1"},
        {"$unset": {"stripe_customer_id": ""}},
    )
    with patch("shared.commercial.billing_service.stripe.api_key",
                "sk_test_stub"), \
         patch("shared.commercial.billing_service.stripe.billing.MeterEvent.create") as me_create:
        await svc.record_overage("biz_test_1", messages=10)
    assert me_create.call_count == 0
    audits = await db.stripe_usage_records.find({}).to_list(length=10)
    assert audits[0]["status"] == "skipped"
    assert audits[0]["reason"] == "no_stripe_customer_id"


@pytest.mark.asyncio
async def test_record_overage_skips_when_no_stripe_api_key():
    db = _make_db()
    svc = await _make_service(db)
    with patch("shared.commercial.billing_service.stripe.api_key", ""), \
         patch("shared.commercial.billing_service.stripe.billing.MeterEvent.create") as me_create:
        await svc.record_overage("biz_test_1", messages=10)
    assert me_create.call_count == 0
    audits = await db.stripe_usage_records.find({}).to_list(length=10)
    assert audits[0]["status"] == "skipped"
    assert audits[0]["reason"] == "no_stripe_api_key"


# ─────────────────────────────────────────────
# Failure paths
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_overage_failure_logs_audit_and_does_not_raise():
    db = _make_db()
    svc = await _make_service(db)

    def boom(*a, **kw):
        raise RuntimeError("Stripe API rate-limited")
    with patch("shared.commercial.billing_service.stripe.api_key",
                "sk_test_stub"), \
         patch("shared.commercial.billing_service.stripe.billing.MeterEvent.create",
                side_effect=boom):
        await svc.record_overage("biz_test_1", messages=42)

    audits = await db.stripe_usage_records.find({}).to_list(length=10)
    assert audits[0]["status"] == "fail"
    assert "Stripe API rate-limited" in audits[0]["error"]
    assert "RuntimeError" in audits[0]["error"]


@pytest.mark.asyncio
async def test_authentication_error_fires_telegram_alert():
    """Stripe AuthenticationError (revoked key) → single Telegram ping."""
    db = _make_db()
    svc = await _make_service(db)

    class AuthenticationError(Exception):
        pass

    def auth_fail(*a, **kw):
        raise AuthenticationError("Invalid API key provided")

    sent = []
    def fake_alert(**kw):
        sent.append(kw)

    with patch("shared.commercial.billing_service.stripe.api_key",
                "sk_test_stub"), \
         patch("shared.commercial.billing_service.stripe.billing.MeterEvent.create",
                side_effect=auth_fail), \
         patch("services.silent_failure_alerts.alert_autonomous_401",
                side_effect=fake_alert):
        await svc.record_overage("biz_test_1", messages=5)

    assert len(sent) == 1
    assert sent[0]["context"] == "billing.metered_usage_record"
    assert sent[0]["provider"] == "stripe"
    assert sent[0]["status_code"] == 401


@pytest.mark.asyncio
async def test_record_overage_completes_even_when_stripe_skipped():
    """Even on skip paths the call must complete cleanly + write the
    audit row. Internal usage tracking is unrelated and pre-existing."""
    db = _make_db()
    svc = await _make_service(db, meter_event_name=None)
    await db.aurem_billing.update_one(
        {"business_id": "biz_test_1"},
        {"$unset": {"stripe_meter_event_name": ""}},
    )
    with patch("shared.commercial.billing_service.stripe.api_key",
                "sk_test_stub"):
        # Must NOT raise
        await svc.record_overage("biz_test_1", messages=88)
    audits = await db.stripe_usage_records.find({}).to_list(length=10)
    assert len(audits) == 1
    assert audits[0]["status"] == "skipped"
    assert audits[0]["messages"] == 88


# ─────────────────────────────────────────────
# Source-level
# ─────────────────────────────────────────────

def test_billing_service_uses_meter_event_api():
    src = (BACKEND / "shared" / "commercial" / "billing_service.py").read_text()
    assert "stripe.billing.MeterEvent.create" in src
    assert "stripe_usage_records.insert_one" in src
    assert "TODO: Create usage record in Stripe" not in src
    assert "iter 327a" in src


def test_billing_service_emits_telegram_alert_on_auth_failure():
    src = (BACKEND / "shared" / "commercial" / "billing_service.py").read_text()
    assert "alert_autonomous_401" in src
    assert '"billing.metered_usage_record"' in src
    assert "provider=\"stripe\"" in src
