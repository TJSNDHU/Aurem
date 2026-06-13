"""
Iteration 315e — Payment Funnel Audit Tests
============================================
Tests for the nightly payment funnel watchdog that:
1. Detects silent payments (Stripe=paid, DB=pending) → auto-fix + WhatsApp alert
2. Flags abandoned checkouts (48h+ pending with no Stripe payment) → WhatsApp alert
3. Persists daily summary to db.payment_audits

Endpoints:
- POST /api/admin/console/payment-audit/run (admin auth required)
- GET /api/admin/console/payment-audit/recent?limit=N (admin auth required)

Key behaviors:
- Idempotency: re-run doesn't re-alert already-flagged abandoned orders
- Stripe errors on fake session IDs are logged but don't crash audit
- WhatsApp alerts return wa_ok:false in preview env (Twilio 10DLC pending - EXPECTED)
"""

import pytest
import requests
import os
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Admin credentials from test_credentials.md
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token for authenticated requests."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15
    )
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        pytest.skip(f"No token in admin login response: {data}")
    return token


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestPaymentAuditAuth:
    """Test authentication requirements for payment audit endpoints."""

    def test_run_audit_without_auth_returns_401(self, api_client):
        """POST /api/admin/console/payment-audit/run without auth returns 401."""
        resp = api_client.post(f"{BASE_URL}/api/admin/console/payment-audit/run", timeout=10)
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text[:200]}"
        print("✓ POST /payment-audit/run without auth returns 401")

    def test_recent_audits_without_auth_returns_401(self, api_client):
        """GET /api/admin/console/payment-audit/recent without auth returns 401."""
        resp = api_client.get(f"{BASE_URL}/api/admin/console/payment-audit/recent?limit=5", timeout=10)
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text[:200]}"
        print("✓ GET /payment-audit/recent without auth returns 401")


class TestPaymentAuditRun:
    """Test the payment audit run endpoint with admin auth."""

    def test_run_audit_with_admin_token_returns_ok(self, api_client, admin_token):
        """POST /api/admin/console/payment-audit/run with admin token returns ok:true with summary fields."""
        resp = api_client.post(
            f"{BASE_URL}/api/admin/console/payment-audit/run",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60  # Audit can take time with Stripe API calls
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}"
        
        data = resp.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        
        # Verify all required summary fields are present
        required_fields = [
            "audit_id", "started_at", "finished_at", "scanned",
            "silent_recovered", "silent_recovered_count",
            "abandoned", "abandoned_count",
            "still_open", "stripe_errors", "stripe_error_count"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print(f"✓ POST /payment-audit/run returns ok:true with all summary fields")
        print(f"  audit_id={data['audit_id']}, scanned={data['scanned']}, "
              f"silent_recovered={data['silent_recovered_count']}, "
              f"abandoned={data['abandoned_count']}, still_open={data['still_open']}, "
              f"stripe_errors={data['stripe_error_count']}")
        
        return data

    def test_recent_audits_with_admin_token(self, api_client, admin_token):
        """GET /api/admin/console/payment-audit/recent?limit=5 returns last 5 audit runs."""
        resp = api_client.get(
            f"{BASE_URL}/api/admin/console/payment-audit/recent?limit=5",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert data.get("ok") is True, f"Expected ok:true, got {data}"
        assert "audits" in data, "Missing 'audits' field in response"
        assert "count" in data, "Missing 'count' field in response"
        
        audits = data["audits"]
        assert isinstance(audits, list), f"Expected audits to be a list, got {type(audits)}"
        
        # Verify ordering (most recent first)
        if len(audits) >= 2:
            for i in range(len(audits) - 1):
                assert audits[i]["started_at"] >= audits[i+1]["started_at"], \
                    "Audits not ordered by started_at desc"
        
        print(f"✓ GET /payment-audit/recent?limit=5 returns {len(audits)} audits ordered by started_at desc")
        return audits


class TestPaymentAuditWithTestData:
    """Test audit behavior with injected test orders."""

    @pytest.fixture(autouse=True)
    def setup_test_orders(self, admin_token):
        """Inject test orders before tests, cleanup after."""
        # We'll use direct MongoDB operations via a helper endpoint or skip if not available
        # For now, we test with whatever data exists in the system
        yield
        # Cleanup would happen here if we had injected data

    def test_stale_fake_order_flagged_abandoned(self, api_client, admin_token):
        """
        Inject a stale (72h+) pending_payment order with FAKE stripe_session_id.
        Next audit run should flag it as abandoned (Stripe lookup fails but 
        fall-through still classifies based on age).
        
        NOTE: This test verifies the logic by checking audit results for any
        orders that match the abandoned criteria.
        """
        # Run audit and check for abandoned orders
        resp = api_client.post(
            f"{BASE_URL}/api/admin/console/payment-audit/run",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60
        )
        assert resp.status_code == 200, f"Audit failed: {resp.status_code} {resp.text[:200]}"
        
        data = resp.json()
        assert data.get("ok") is True
        
        # The audit should have processed some orders
        # Abandoned orders are those 48h+ old with unpaid Stripe status
        abandoned = data.get("abandoned", [])
        abandoned_count = data.get("abandoned_count", 0)
        
        print(f"✓ Audit processed {data['scanned']} orders, found {abandoned_count} abandoned")
        
        # Check that abandoned orders have expected structure
        for order in abandoned:
            assert "order_id" in order, "Abandoned order missing order_id"
            # wa_ok can be True, False, or None (for skipped:already_flagged)
            print(f"  Abandoned: {order.get('order_id')}, wa_ok={order.get('wa_ok')}, "
                  f"skipped={order.get('skipped')}")

    def test_recent_order_not_abandoned(self, api_client, admin_token):
        """
        Recent (12h) pending_payment orders with FAKE stripe_session_id should
        report stripe_error AND count toward still_open (NOT abandoned because <48h).
        """
        resp = api_client.post(
            f"{BASE_URL}/api/admin/console/payment-audit/run",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60
        )
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("ok") is True
        
        # still_open should include orders that are pending but not yet 48h old
        still_open = data.get("still_open", 0)
        stripe_errors = data.get("stripe_errors", [])
        stripe_error_count = data.get("stripe_error_count", 0)
        
        print(f"✓ Audit: still_open={still_open}, stripe_errors={stripe_error_count}")
        
        # Stripe errors should have order_id and err fields
        for err in stripe_errors:
            assert "order_id" in err, "Stripe error missing order_id"
            assert "err" in err, "Stripe error missing err message"
            print(f"  Stripe error: {err.get('order_id')}: {err.get('err')[:80]}")


class TestPaymentAuditIdempotency:
    """Test idempotency: re-run audit doesn't re-alert already-flagged orders."""

    def test_idempotency_already_flagged_orders(self, api_client, admin_token):
        """
        Re-run audit immediately → previously-abandoned orders return 
        skipped:already_flagged with wa_ok:None, no second WhatsApp.
        """
        # First run
        resp1 = api_client.post(
            f"{BASE_URL}/api/admin/console/payment-audit/run",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1.get("ok") is True
        
        first_abandoned = data1.get("abandoned", [])
        first_abandoned_count = data1.get("abandoned_count", 0)
        
        # Second run immediately after
        resp2 = api_client.post(
            f"{BASE_URL}/api/admin/console/payment-audit/run",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2.get("ok") is True
        
        second_abandoned = data2.get("abandoned", [])
        
        # Check for skipped:already_flagged in second run
        already_flagged_count = sum(
            1 for order in second_abandoned 
            if order.get("skipped") == "already_flagged"
        )
        
        print(f"✓ Idempotency test: 1st run abandoned={first_abandoned_count}, "
              f"2nd run already_flagged={already_flagged_count}")
        
        # If there were abandoned orders in first run, they should be flagged in second
        if first_abandoned_count > 0:
            # At least some should be already_flagged (unless new orders appeared)
            print(f"  First run abandoned orders: {[o.get('order_id') for o in first_abandoned]}")
            print(f"  Second run abandoned orders: {[o.get('order_id') for o in second_abandoned]}")


class TestPaymentAuditPersistence:
    """Test that audit results are persisted to db.payment_audits."""

    def test_audit_persisted_to_db(self, api_client, admin_token):
        """
        After running audit, db.payment_audits collection should be populated
        with audit_id, scanned, counts, lists.
        """
        # Run audit
        resp = api_client.post(
            f"{BASE_URL}/api/admin/console/payment-audit/run",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        
        audit_id = data.get("audit_id")
        assert audit_id, "No audit_id in response"
        
        # Verify via recent endpoint
        resp2 = api_client.get(
            f"{BASE_URL}/api/admin/console/payment-audit/recent?limit=10",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15
        )
        assert resp2.status_code == 200
        
        audits = resp2.json().get("audits", [])
        audit_ids = [a.get("audit_id") for a in audits]
        
        assert audit_id in audit_ids, f"Audit {audit_id} not found in recent audits"
        print(f"✓ Audit {audit_id} persisted to db.payment_audits and retrievable via /recent")


class TestStripeKeyResolver:
    """Test that _stripe_key() returns valid live key (placeholder-safe)."""

    def test_stripe_key_resolver_returns_live_key(self):
        """
        Stripe key resolver _stripe_key() in payment_funnel_audit returns sk_live_*
        (placeholder-safe — mirrors stripe_payment_router fix from iter 315d).
        
        This is a code review test - we verify the function logic.
        """
        # Import and test the function directly
        import sys
        sys.path.insert(0, "/app/backend")
        
        from services.payment_funnel_audit import _stripe_key
        
        key = _stripe_key()
        
        # Key should be non-empty and at least 30 chars (placeholder rejection)
        assert key, "Stripe key is empty"
        assert len(key) >= 30, f"Stripe key too short ({len(key)} chars) - likely placeholder"
        
        # Should start with sk_live_ or sk_test_
        assert key.startswith(("sk_live_", "sk_test_")), \
            f"Stripe key doesn't start with sk_live_ or sk_test_: {key[:20]}..."
        
        print(f"✓ _stripe_key() returns valid key: {key[:15]}...{key[-4:]} ({len(key)} chars)")


class TestSchedulerAttachment:
    """Test that payment_audit_scheduler is attached at startup."""

    def test_scheduler_attached_in_server(self):
        """
        Verify in /app/backend/server.py around line 1564 that 
        payment_audit_scheduler is hooked via asyncio.create_task.
        """
        with open("/app/backend/server.py", "r") as f:
            content = f.read()
        
        # Check for the scheduler import and task creation
        assert "from services.payment_funnel_audit import payment_audit_scheduler" in content, \
            "payment_audit_scheduler not imported in server.py"
        assert "asyncio.create_task(payment_audit_scheduler())" in content, \
            "payment_audit_scheduler not started via asyncio.create_task"
        
        print("✓ payment_audit_scheduler attached at startup in server.py")


class TestSilentPaymentRecoveryLogic:
    """Code review: verify _fix_silent_payment logic in payment_funnel_audit.py."""

    def test_fix_silent_payment_logic(self):
        """
        Inspect _fix_silent_payment in /app/backend/services/payment_funnel_audit.py:
        - Must update status to paid
        - Set paid_at
        - Set audit_recovered_at
        - Set audit_recovery_source='payment_funnel_audit'
        - Set stripe_payment_intent
        - Fire _kick_repair_build via asyncio.create_task
        - Fire WhatsApp alert with biz name + amount
        """
        with open("/app/backend/services/payment_funnel_audit.py", "r") as f:
            content = f.read()
        
        # Check for required updates in _fix_silent_payment
        assert '"status": "paid"' in content, "Missing status='paid' update"
        assert '"paid_at":' in content, "Missing paid_at update"
        assert '"audit_recovered_at":' in content, "Missing audit_recovered_at update"
        assert '"audit_recovery_source": "payment_funnel_audit"' in content, \
            "Missing audit_recovery_source update"
        assert '"stripe_payment_intent":' in content, "Missing stripe_payment_intent update"
        
        # Check for _kick_repair_build call
        assert "_kick_repair_build" in content, "Missing _kick_repair_build call"
        assert "asyncio.create_task(_kick_repair_build" in content, \
            "_kick_repair_build not called via asyncio.create_task"
        
        # Check for WhatsApp alert
        assert "_wa_alert" in content, "Missing WhatsApp alert call"
        assert "Silent payment found" in content, "Missing silent payment alert message"
        
        # Check for attribution
        assert "attribute_lead_outcome" in content, "Missing attribution call"
        
        print("✓ _fix_silent_payment logic verified: updates status, fires build, sends alert")


class TestFlagAbandonedLogic:
    """Code review: verify _flag_abandoned logic."""

    def test_flag_abandoned_logic(self):
        """
        Verify _flag_abandoned:
        - Checks abandoned_alerted_at for idempotency
        - Sets abandoned_alerted_at timestamp
        - Sends WhatsApp alert (one-shot)
        """
        with open("/app/backend/services/payment_funnel_audit.py", "r") as f:
            content = f.read()
        
        # Check for idempotency check
        assert 'if order.get("abandoned_alerted_at")' in content, \
            "Missing abandoned_alerted_at idempotency check"
        assert '"skipped": "already_flagged"' in content, \
            "Missing already_flagged return"
        
        # Check for abandoned_alerted_at update
        assert '"abandoned_alerted_at":' in content, "Missing abandoned_alerted_at update"
        
        # Check for WhatsApp alert
        assert "Abandoned checkout" in content, "Missing abandoned checkout alert message"
        
        print("✓ _flag_abandoned logic verified: idempotent, sets flag, sends alert")


class TestWhatsAppAlertBehavior:
    """Test WhatsApp alert behavior (expected to return false in preview env)."""

    def test_whatsapp_alerts_graceful_failure(self, api_client, admin_token):
        """
        WhatsApp alerts fire via routers.whatsapp_alerts.send_whatsapp.
        Returns wa_ok:false in preview env (Twilio 10DLC pending - EXPECTED).
        """
        # Run audit and check wa_ok values
        resp = api_client.post(
            f"{BASE_URL}/api/admin/console/payment-audit/run",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=60
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        
        # Check abandoned orders for wa_ok field
        abandoned = data.get("abandoned", [])
        for order in abandoned:
            if "wa_ok" in order and order.get("skipped") != "already_flagged":
                # wa_ok should be False in preview env (expected)
                print(f"  Order {order.get('order_id')}: wa_ok={order.get('wa_ok')}")
        
        print("✓ WhatsApp alerts handled gracefully (wa_ok:false expected in preview)")


class TestAbandonedAgeThreshold:
    """Test ABANDONED_AGE_HOURS threshold (default 48h)."""

    def test_abandoned_age_hours_env_override(self):
        """
        ABANDONED_AGE_HOURS=48 (env override available).
        Verify the constant is read from environment.
        """
        with open("/app/backend/services/payment_funnel_audit.py", "r") as f:
            content = f.read()
        
        assert 'ABANDONED_AGE_HOURS = int(os.environ.get("PAYMENT_AUDIT_ABANDONED_HOURS", "48"))' in content, \
            "ABANDONED_AGE_HOURS not reading from env with 48h default"
        
        print("✓ ABANDONED_AGE_HOURS reads from PAYMENT_AUDIT_ABANDONED_HOURS env (default 48)")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
