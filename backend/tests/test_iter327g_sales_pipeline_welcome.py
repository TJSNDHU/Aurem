"""
iter 327g — Wire welcome email + customer account creation on contract
signing (sales_pipeline.py:515 TODO).

Founder mandate:
  "Pass customer_email + customer_name into trigger_onboarding. Check
   if tenant exists. If yes → call send_welcome_package. If no → mint
   user account, then send. Mark step 2 completed only on real success;
   failed with the error otherwise. Do NOT build a third welcome system."

What this iter delivers:
  1. `ProposalRequest.customer_email` (Optional) added; persisted on
     proposal + contract docs.
  2. `trigger_onboarding(contract_id, customer_company, customer_email,
     customer_name)` — new signature, threaded through `generate_contract`.
  3. `_provision_customer_and_send_welcome` worker:
        - finds platform_users / users by email
        - if missing, inserts a platform_users row (role=customer)
        - calls business_id_router.ensure_business_id()
        - calls services.welcome_package.send_welcome_package()
        - marks step 1 / step 2 completed or failed with error text
  4. Step 2 is no longer pre-marked 'completed' (the old lie).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import mongomock_motor
import pytest

BACKEND = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────
# ProposalRequest schema
# ─────────────────────────────────────────────

def test_proposalrequest_has_customer_email_optional():
    from routers.sales_pipeline import ProposalRequest
    fields = ProposalRequest.model_fields
    assert "customer_email" in fields
    # Default None (i.e. backward-compatible)
    assert fields["customer_email"].default is None


# ─────────────────────────────────────────────
# trigger_onboarding signature
# ─────────────────────────────────────────────

def test_trigger_onboarding_signature_accepts_email_and_name():
    import inspect
    from routers.sales_pipeline import trigger_onboarding
    sig = inspect.signature(trigger_onboarding)
    params = sig.parameters
    assert "customer_email" in params
    assert "customer_name" in params
    # Both optional / kw-friendly
    assert params["customer_email"].default is None
    assert params["customer_name"].default is None


# ─────────────────────────────────────────────
# Worker — happy path: new customer, no prior account
# ─────────────────────────────────────────────

class _FakeDBHolder:
    """Patches `server.db` for the duration of a test."""
    def __init__(self, db):
        self.db = db
    def __enter__(self):
        import server
        self._orig = getattr(server, "db", None)
        server.db = self.db
        return self
    def __exit__(self, *a):
        import server
        server.db = self._orig
        return False


@pytest.mark.asyncio
async def test_provision_mints_user_and_sends_welcome():
    from routers.sales_pipeline import (
        _provision_customer_and_send_welcome,
        trigger_onboarding,
    )

    db = mongomock_motor.AsyncMongoMockClient()["test327g_happy"]

    # Seed the onboarding row that trigger_onboarding would have created.
    await db.onboarding_sessions.insert_one({
        "onboarding_id": "onboard_test_happy",
        "contract_id": "ctx_1",
        "customer_company": "Acme",
        "customer_email": "owner@acme.test",
        "customer_name": "Acme Owner",
        "status": "in_progress",
        "steps": [
            {"step": 1, "name": "Account Setup", "status": "pending"},
            {"step": 2, "name": "Welcome Email Sent", "status": "pending"},
            {"step": 3, "name": "Onboarding Call Scheduled", "status": "pending"},
            {"step": 4, "name": "System Integration", "status": "pending"},
            {"step": 5, "name": "Go Live", "status": "pending"},
        ],
    })

    # Patch the two integration points we own. ensure_business_id stamps
    # the user; send_welcome_package returns success.
    async def fake_ensure_business_id(user_doc):
        bid = "AUR-TOR-TEST"
        await db.platform_users.update_one(
            {"email": user_doc["email"]},
            {"$set": {"business_id": bid}},
        )
        return bid

    async def fake_send_welcome_package(tenant_id, user_doc=None):
        return {"ok": True, "status": "sent", "resend_id": "resend_abc"}

    with _FakeDBHolder(db):
        with patch("routers.business_id_router.ensure_business_id",
                    new=fake_ensure_business_id), \
             patch("services.welcome_package.send_welcome_package",
                    new=fake_send_welcome_package):
            await _provision_customer_and_send_welcome(
                onboarding_id="onboard_test_happy",
                customer_company="Acme",
                customer_email="owner@acme.test",
                customer_name="Acme Owner",
            )

    # platform_users row was created
    u = await db.platform_users.find_one({"email": "owner@acme.test"}, {"_id": 0})
    assert u is not None
    assert u["role"] == "customer"
    assert u["company_name"] == "Acme"
    assert u["must_set_password"] is True
    assert u["business_id"] == "AUR-TOR-TEST"

    # Onboarding row: steps 1 + 2 = completed; resend_id captured
    o = await db.onboarding_sessions.find_one(
        {"onboarding_id": "onboard_test_happy"}, {"_id": 0}
    )
    by_step = {s["step"]: s for s in o["steps"]}
    assert by_step[1]["status"] == "completed"
    assert by_step[2]["status"] == "completed"
    assert by_step[2].get("resend_id") == "resend_abc"
    assert by_step[2].get("business_id") == "AUR-TOR-TEST"


# ─────────────────────────────────────────────
# Worker — existing customer (no mint, just send)
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_provision_reuses_existing_customer():
    from routers.sales_pipeline import _provision_customer_and_send_welcome

    db = mongomock_motor.AsyncMongoMockClient()["test327g_existing"]
    await db.platform_users.insert_one({
        "email": "ceo@bigcorp.test",
        "full_name": "Big Corp CEO",
        "company_name": "BigCorp",
        "role": "user",
        "business_id": "AUR-MTL-OLD1",
    })
    await db.onboarding_sessions.insert_one({
        "onboarding_id": "ob_existing",
        "steps": [
            {"step": 1, "name": "Account Setup", "status": "pending"},
            {"step": 2, "name": "Welcome Email Sent", "status": "pending"},
            {"step": 3, "name": "x", "status": "pending"},
            {"step": 4, "name": "y", "status": "pending"},
            {"step": 5, "name": "z", "status": "pending"},
        ],
    })

    insert_calls = []
    original_insert = db.platform_users.insert_one
    async def tracking_insert(doc):
        insert_calls.append(doc)
        return await original_insert(doc)

    # ensure_business_id should be a no-op for an existing bid
    async def fake_ensure(user_doc):
        return user_doc.get("business_id") or "AUR-NEW"
    async def fake_send(tid, user_doc=None):
        return {"ok": True, "status": "sent"}

    with _FakeDBHolder(db):
        with patch.object(db.platform_users, "insert_one", new=tracking_insert), \
             patch("routers.business_id_router.ensure_business_id", new=fake_ensure), \
             patch("services.welcome_package.send_welcome_package", new=fake_send):
            await _provision_customer_and_send_welcome(
                onboarding_id="ob_existing",
                customer_company="BigCorp",
                customer_email="ceo@bigcorp.test",
                customer_name="Big Corp CEO",
            )

    # No new platform_users row inserted
    assert insert_calls == []
    o = await db.onboarding_sessions.find_one({"onboarding_id": "ob_existing"}, {"_id": 0})
    by_step = {s["step"]: s for s in o["steps"]}
    assert by_step[1]["status"] == "completed"
    assert by_step[2]["status"] == "completed"


# ─────────────────────────────────────────────
# Worker — missing email = both steps marked failed
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_provision_no_email_marks_both_steps_failed():
    from routers.sales_pipeline import _provision_customer_and_send_welcome
    db = mongomock_motor.AsyncMongoMockClient()["test327g_noemail"]
    await db.onboarding_sessions.insert_one({
        "onboarding_id": "ob_noemail",
        "steps": [
            {"step": 1, "name": "Account Setup", "status": "pending"},
            {"step": 2, "name": "Welcome Email Sent", "status": "pending"},
            {"step": 3, "name": "x", "status": "pending"},
            {"step": 4, "name": "y", "status": "pending"},
            {"step": 5, "name": "z", "status": "pending"},
        ],
    })
    with _FakeDBHolder(db):
        await _provision_customer_and_send_welcome(
            onboarding_id="ob_noemail",
            customer_company="Anonymous Ltd",
            customer_email=None,
            customer_name="Anon",
        )
    o = await db.onboarding_sessions.find_one({"onboarding_id": "ob_noemail"}, {"_id": 0})
    by_step = {s["step"]: s for s in o["steps"]}
    assert by_step[1]["status"] == "failed"
    assert by_step[2]["status"] == "failed"
    assert "customer_email missing" in by_step[2]["error"]


# ─────────────────────────────────────────────
# Worker — send_welcome_package returns ok:False
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_provision_send_failure_marks_step_2_failed():
    from routers.sales_pipeline import _provision_customer_and_send_welcome
    db = mongomock_motor.AsyncMongoMockClient()["test327g_sendfail"]
    await db.onboarding_sessions.insert_one({
        "onboarding_id": "ob_sendfail",
        "steps": [
            {"step": 1, "name": "Account Setup", "status": "pending"},
            {"step": 2, "name": "Welcome Email Sent", "status": "pending"},
            {"step": 3, "name": "x", "status": "pending"},
            {"step": 4, "name": "y", "status": "pending"},
            {"step": 5, "name": "z", "status": "pending"},
        ],
    })
    async def fake_ensure(u):
        bid = "AUR-FAIL"
        await db.platform_users.update_one(
            {"email": u["email"]}, {"$set": {"business_id": bid}}
        )
        return bid
    async def fake_send(tid, user_doc=None):
        return {"ok": False, "status": "failed", "error": "resend 4xx: domain not verified"}
    with _FakeDBHolder(db):
        with patch("routers.business_id_router.ensure_business_id", new=fake_ensure), \
             patch("services.welcome_package.send_welcome_package", new=fake_send):
            await _provision_customer_and_send_welcome(
                onboarding_id="ob_sendfail",
                customer_company="FailCo",
                customer_email="boss@failco.test",
                customer_name="Boss",
            )

    o = await db.onboarding_sessions.find_one({"onboarding_id": "ob_sendfail"}, {"_id": 0})
    by_step = {s["step"]: s for s in o["steps"]}
    # Account was minted successfully
    assert by_step[1]["status"] == "completed"
    # Welcome send failed — error string captured
    assert by_step[2]["status"] == "failed"
    assert "domain not verified" in by_step[2]["error"]


# ─────────────────────────────────────────────
# Source-level checks
# ─────────────────────────────────────────────

def test_old_lying_completed_marker_removed():
    """The pre-iter-327g code marked step 2 'completed' BEFORE doing any
    real work. That line must be gone."""
    src = (BACKEND / "routers" / "sales_pipeline.py").read_text()
    # The exact pre-fix line that marked the welcome as sent before sending
    assert '"name": "Welcome Email Sent",\n                    "status": "completed"' not in src
    # The old TODO comment must be gone too
    assert "TODO: Send welcome email, create customer account" not in src


def test_provision_helper_imports_existing_welcome_stack():
    src = (BACKEND / "routers" / "sales_pipeline.py").read_text()
    # Reuses what exists — no third welcome system
    assert "from services.welcome_package import send_welcome_package" in src
    assert "from routers.business_id_router import ensure_business_id" in src


def test_iter_327g_marker_present():
    src = (BACKEND / "routers" / "sales_pipeline.py").read_text()
    assert "iter 327g" in src
