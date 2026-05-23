"""
iter 331g — Beta ticker + Swagger UI + Stripe Checkout
=======================================================

Backend tests for:
  • GET /api/developers/public/stats (beta ticker counter)
  • GET /api/developers/openapi.json (Swagger feed, BearerAuth)
  • GET /api/developers/packages       (Stripe price table)
  • POST /api/developers/checkout/start (Stripe checkout creation)
  • GET /api/developers/checkout/status/{id} (idempotent credit)
  • POST /api/webhook/stripe (idempotent webhook routing)
  • Idempotency contract (poll + webhook race must credit once)
  • 3-day grace logic on invoice.payment_failed
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


@pytest_asyncio.fixture
async def fresh_dev(db):
    """Insert a verified synthetic developer account and yield the doc."""
    from services import developer_portal_core as _D
    from services import developer_stripe as _S
    _D.set_db(db)
    _S.set_db(db)
    user_id = f"stripe-{uuid.uuid4().hex[:12]}"
    doc = {
        "user_id":           user_id,
        "email":             f"stripe+{uuid.uuid4().hex[:8]}@example.com",
        "email_verified":    True,
        "name":              "Stripe Tester",
        "password_hash":     "sha256$x$y",
        "tokens_remaining":  100,
        "tokens_total_used": 0,
        "subscription_status": "free",
        "created_at":        datetime.now(timezone.utc).isoformat(),
    }
    await db.developer_accounts.insert_one(doc)
    yield doc
    await db.developer_accounts.delete_one({"user_id": user_id})
    await db.payment_transactions.delete_many({"user_id": user_id})


# ═══════════════════════════════════════════════════════════════════
# Public stats (beta ticker)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_public_stats_returns_verified_count(db, fresh_dev):
    from fastapi.testclient import TestClient
    from server import app
    with TestClient(app) as client:
        r = client.get("/api/developers/public/stats")
        assert r.status_code == 200
        j = r.json()
        assert "verified_developers" in j
        assert isinstance(j["verified_developers"], int)
        assert j["verified_developers"] >= 1  # at least our fresh_dev


# ═══════════════════════════════════════════════════════════════════
# OpenAPI feed (Swagger)
# ═══════════════════════════════════════════════════════════════════

def test_developers_openapi_returns_bearer_scheme_and_paths():
    from fastapi.testclient import TestClient
    from server import app
    with TestClient(app) as client:
        r = client.get("/api/developers/openapi.json")
        assert r.status_code == 200
        j = r.json()
        assert j.get("info", {}).get("title") == "AUREM CTO — Developer Portal API"
        assert "BearerAuth" in (j.get("components", {}).get("securitySchemes") or {})
        paths = j.get("paths") or {}
        assert "/api/developers/signup" in paths
        assert "/api/developers/verify-otp" in paths
        assert "/api/developers/me" in paths
        # No admin paths leak through
        admin_paths = [p for p in paths if p.startswith("/api/admin/")]
        assert admin_paths == []


# ═══════════════════════════════════════════════════════════════════
# Packages
# ═══════════════════════════════════════════════════════════════════

def test_package_table_has_all_three_tiers():
    from services.developer_stripe import package_table, PACKAGES
    rows = package_table()
    ids = {r["id"] for r in rows}
    assert ids == {"starter", "builder", "pro"}
    by_id = {r["id"]: r for r in rows}
    assert by_id["starter"]["amount_usd"] == 9.0
    assert by_id["starter"]["tokens_grant"] == 10_000
    assert by_id["builder"]["amount_usd"] == 39.0
    assert by_id["builder"]["tokens_grant"] == 50_000
    assert by_id["pro"]["amount_usd"] == 99.0
    assert by_id["pro"]["days_paid"] == 30


# ═══════════════════════════════════════════════════════════════════
# start_checkout — happy path with mocked StripeCheckout
# ═══════════════════════════════════════════════════════════════════

class _FakeStripe:
    """Mock that mimics the emergentintegrations StripeCheckout API."""
    def __init__(self):
        self.sessions = {}
        self.last_request = None

    async def create_checkout_session(self, req):
        sid = f"cs_test_{uuid.uuid4().hex[:16]}"
        self.last_request = req
        self.sessions[sid] = {"payment_status": "unpaid", "status": "open"}
        return SimpleNamespace(
            session_id=sid,
            url=f"https://checkout.stripe.com/c/pay/{sid}",
        )

    async def get_checkout_status(self, sid):
        st = self.sessions.get(sid, {})
        return SimpleNamespace(
            payment_status=st.get("payment_status", "unpaid"),
            status=st.get("status", "open"),
            amount_total=int(float(self.last_request.amount if self.last_request else 0) * 100),
            currency=self.last_request.currency if self.last_request else "usd",
        )

    def mark_paid(self, sid):
        if sid in self.sessions:
            self.sessions[sid] = {"payment_status": "paid", "status": "complete"}


@pytest_asyncio.fixture
def stripe_mock(monkeypatch):
    from services import developer_stripe as _S
    fake = _FakeStripe()
    monkeypatch.setattr(_S, "_get_client", lambda host_url=None: fake)
    yield fake


@pytest.mark.asyncio
async def test_start_checkout_persists_pending_row(db, fresh_dev, stripe_mock):
    from services.developer_stripe import start_checkout
    r = await start_checkout(
        user_id=fresh_dev["user_id"], email=fresh_dev["email"],
        tier="builder", origin_url="https://aurem.live",
    )
    assert r["ok"] is True
    assert r["url"].startswith("https://checkout.stripe.com/")
    assert r["session_id"].startswith("cs_test_")
    # Persisted as pending
    row = await db.payment_transactions.find_one({"session_id": r["session_id"]})
    assert row is not None
    assert row["payment_status"] == "pending"
    assert row["credited"] is False
    assert row["tier"] == "builder"
    assert row["amount_usd"] == 39.0


@pytest.mark.asyncio
async def test_start_checkout_rejects_unknown_tier(db, fresh_dev, stripe_mock):
    from services.developer_stripe import start_checkout
    r = await start_checkout(
        user_id=fresh_dev["user_id"], email=fresh_dev["email"],
        tier="enterprise-mega-zillion", origin_url="https://aurem.live",
    )
    assert r["ok"] is False
    assert r["error"] == "unknown_package"


# ═══════════════════════════════════════════════════════════════════
# Idempotent credit
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_credit_for_session_grants_tokens_once(db, fresh_dev, stripe_mock):
    from services.developer_stripe import start_checkout, get_status
    s = await start_checkout(
        user_id=fresh_dev["user_id"], email=fresh_dev["email"],
        tier="starter", origin_url="https://aurem.live",
    )
    sid = s["session_id"]
    # Simulate Stripe flipping to paid
    stripe_mock.mark_paid(sid)
    # First poll → credits
    r1 = await get_status(sid)
    assert r1["payment_status"] == "paid"
    assert r1["credited"] is True
    assert r1["tokens_granted"] == 10_000
    # Second poll → should NOT re-credit
    r2 = await get_status(sid)
    assert r2["payment_status"] == "paid"
    assert r2["credited"] is False or r2.get("reason") == "already_credited"
    # Account got exactly +10k
    acc = await db.developer_accounts.find_one({"user_id": fresh_dev["user_id"]})
    assert acc["tokens_remaining"] == fresh_dev["tokens_remaining"] + 10_000


@pytest.mark.asyncio
async def test_credit_for_session_pro_flips_subscription(db, fresh_dev, stripe_mock):
    from services.developer_stripe import start_checkout, get_status
    s = await start_checkout(
        user_id=fresh_dev["user_id"], email=fresh_dev["email"],
        tier="pro", origin_url="https://aurem.live",
    )
    stripe_mock.mark_paid(s["session_id"])
    r = await get_status(s["session_id"])
    assert r["credited"] is True
    assert r["kind"] == "subscription"
    assert r["days_paid"] == 30
    acc = await db.developer_accounts.find_one({"user_id": fresh_dev["user_id"]})
    assert acc["subscription_status"] == "paid"
    assert acc.get("subscription_paid_until")


@pytest.mark.asyncio
async def test_poll_webhook_race_credits_only_once(db, fresh_dev, stripe_mock):
    """Critical idempotency contract: when the polling status route AND
    the webhook handler both observe the same paid session, only one
    must actually credit tokens."""
    from services.developer_stripe import (
        start_checkout, credit_for_session, process_webhook_event,
    )
    s = await start_checkout(
        user_id=fresh_dev["user_id"], email=fresh_dev["email"],
        tier="builder", origin_url="https://aurem.live",
    )
    sid = s["session_id"]
    stripe_mock.mark_paid(sid)
    # Mark the transaction paid (poll would do this via get_status update)
    await db.payment_transactions.update_one(
        {"session_id": sid},
        {"$set": {"payment_status": "paid"}},
    )
    # Race: 5 concurrent credit_for_session calls
    results = await asyncio.gather(*[credit_for_session(sid) for _ in range(5)])
    credited_count = sum(1 for r in results if r.get("credited"))
    assert credited_count == 1, f"expected exactly 1 credit, got {credited_count}"
    # And then a webhook event also arrives
    wh = await process_webhook_event(
        event_id=f"evt_test_{uuid.uuid4().hex[:8]}",
        event_type="checkout.session.completed",
        session_id=sid,
    )
    assert wh["processed"] is True
    # Webhook found already_credited and didn't grant again
    acc = await db.developer_accounts.find_one({"user_id": fresh_dev["user_id"]})
    assert acc["tokens_remaining"] == fresh_dev["tokens_remaining"] + 50_000


# ═══════════════════════════════════════════════════════════════════
# Webhook idempotency
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_webhook_dedupes_on_event_id(db):
    from services.developer_stripe import process_webhook_event, set_db
    set_db(db)
    eid = f"evt_test_{uuid.uuid4().hex[:8]}"
    try:
        r1 = await process_webhook_event(
            event_id=eid,
            event_type="checkout.session.completed",
            session_id="cs_nonexistent_xyz",
        )
        assert r1["processed"] is True
        r2 = await process_webhook_event(
            event_id=eid,
            event_type="checkout.session.completed",
            session_id="cs_nonexistent_xyz",
        )
        assert r2["processed"] is False
        assert r2["reason"] == "duplicate"
    finally:
        await db.stripe_events_processed.delete_one({"event_id": eid})


# ═══════════════════════════════════════════════════════════════════
# 3-day grace logic
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_invoice_payment_failed_starts_grace(db, fresh_dev):
    from services.developer_stripe import _handle_payment_failed, set_db
    set_db(db)
    # Tag the account with a stripe_customer_id so the lookup hits
    await db.developer_accounts.update_one(
        {"user_id": fresh_dev["user_id"]},
        {"$set": {"stripe_customer_id": "cus_test_grace1",
                   "subscription_status": "paid"}},
    )
    raw = {"data": {"object": {"customer": "cus_test_grace1"}}}
    action = await _handle_payment_failed(raw)
    assert action == "grace_started"
    acc = await db.developer_accounts.find_one({"user_id": fresh_dev["user_id"]})
    assert acc.get("grace_period_ends_at")
    # subscription_status still paid (grace window active)
    assert acc["subscription_status"] == "paid"


@pytest.mark.asyncio
async def test_invoice_payment_failed_downgrades_after_grace(db, fresh_dev):
    from services.developer_stripe import _handle_payment_failed, set_db
    set_db(db)
    # Set grace already expired 1 hour ago
    expired = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    await db.developer_accounts.update_one(
        {"user_id": fresh_dev["user_id"]},
        {"$set": {
            "stripe_customer_id":   "cus_test_grace2",
            "subscription_status":  "paid",
            "grace_period_ends_at": expired,
        }},
    )
    raw = {"data": {"object": {"customer": "cus_test_grace2"}}}
    action = await _handle_payment_failed(raw)
    assert action == "downgraded"
    acc = await db.developer_accounts.find_one({"user_id": fresh_dev["user_id"]})
    assert acc["subscription_status"] == "free"
    assert acc.get("grace_period_ends_at") is None


@pytest.mark.asyncio
async def test_invoice_payment_failed_no_account_returns_clean(db):
    from services.developer_stripe import _handle_payment_failed, set_db
    set_db(db)
    raw = {"data": {"object": {"customer": "cus_nobody_here"}}}
    action = await _handle_payment_failed(raw)
    assert action == "no_account"


# ═══════════════════════════════════════════════════════════════════
# Route wire-up sanity
# ═══════════════════════════════════════════════════════════════════

def test_stripe_endpoints_registered_in_router():
    from pathlib import Path
    src = Path("/app/backend/routers/developer_portal_router.py").read_text()
    assert "/api/developers/checkout/start" in src
    assert "/api/developers/checkout/status" in src
    assert "/api/webhook/stripe" in src
    assert "/api/developers/packages" in src
    assert "/api/developers/public/stats" in src
    assert "/api/developers/openapi.json" in src


def test_stripe_collections_indexed():
    from pathlib import Path
    src = Path("/app/backend/services/developer_portal_core.py").read_text()
    assert 'payment_transactions.create_index("session_id"' in src
    assert 'stripe_events_processed.create_index("event_id"' in src
