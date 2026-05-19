"""
Iteration 168: Shopify Pulse Scanner, Recovery, Billing, and GDPR Webhooks
==========================================================================
Tests for the new Shopify endpoints:
- POST /api/shopify/pulse/scan — health scan (scaffold mode)
- POST /api/shopify/pulse/fix/alt-text — SSE stream for alt-text fixes
- GET /api/shopify/pulse/recovery/stats — abandoned/recovered/revenue stats
- GET /api/shopify-billing/plans — billing plans
- POST /api/shopify/pulse/webhook/checkout-created — abandoned cart capture
- GDPR webhooks (customers-redact, customers-data-request, shop-redact)
"""

import pytest
import requests
import os
import json
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-platform-preview-3.preview.emergentagent.com").rstrip("/")


class TestShopifyPulseBilling:
    """Test Shopify Pulse Scanner, Recovery, and Billing endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for authenticated requests"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "teji.ss1986@gmail.com", "password": "<REDACTED>"}
        )
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("token")
        assert token, "No token in login response"
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    # ═══════════════════════════════════════════════════
    # PULSE SCANNER TESTS
    # ═══════════════════════════════════════════════════

    def test_pulse_scan_scaffold_mode(self):
        """POST /api/shopify/pulse/scan — returns health_score, issues, revenue_at_risk in scaffold mode"""
        resp = self.session.post(
            f"{BASE_URL}/api/shopify/pulse/scan",
            json={"shop": "demo-store"}
        )
        assert resp.status_code == 200, f"Pulse scan failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        # Verify scaffold mode response structure
        assert "health_score" in data, "Missing health_score in response"
        assert "issues" in data, "Missing issues in response"
        assert "revenue_at_risk_monthly" in data, "Missing revenue_at_risk_monthly in response"
        assert "mode" in data and data["mode"] == "scaffold", "Expected scaffold mode"
        
        # Verify health score is a number between 0-100
        assert isinstance(data["health_score"], (int, float)), "health_score should be numeric"
        assert 0 <= data["health_score"] <= 100, "health_score should be 0-100"
        
        # Verify issues is a list with expected structure
        assert isinstance(data["issues"], list), "issues should be a list"
        if data["issues"]:
            issue = data["issues"][0]
            assert "type" in issue, "Issue missing type"
            assert "severity" in issue, "Issue missing severity"
            assert "description" in issue, "Issue missing description"
        
        print(f"✓ Pulse scan returned health_score={data['health_score']}, issues={len(data['issues'])}, revenue_at_risk=${data['revenue_at_risk_monthly']}")

    def test_pulse_scan_with_custom_shop(self):
        """POST /api/shopify/pulse/scan — accepts custom shop domain"""
        resp = self.session.post(
            f"{BASE_URL}/api/shopify/pulse/scan",
            json={"shop": "test-store.myshopify.com"}
        )
        assert resp.status_code == 200, f"Pulse scan failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert data.get("shop") == "test-store.myshopify.com", "Shop domain not echoed correctly"
        print(f"✓ Pulse scan accepted custom shop domain")

    # ═══════════════════════════════════════════════════
    # ALT-TEXT FIX SSE STREAM TESTS
    # ═══════════════════════════════════════════════════

    def test_alt_text_fix_sse_stream(self):
        """POST /api/shopify/pulse/fix/alt-text — returns SSE stream with fix events"""
        resp = self.session.post(
            f"{BASE_URL}/api/shopify/pulse/fix/alt-text",
            json={"shop": "demo-store"},
            stream=True
        )
        assert resp.status_code == 200, f"Alt-text fix failed: {resp.status_code}"
        assert "text/event-stream" in resp.headers.get("content-type", ""), "Expected SSE content-type"
        
        # Read SSE events
        events = []
        for line in resp.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                try:
                    event_data = json.loads(line[6:])
                    events.append(event_data)
                    # Stop after getting complete event
                    if event_data.get("type") == "complete":
                        break
                except json.JSONDecodeError:
                    pass
            # Limit to prevent infinite loop
            if len(events) > 20:
                break
        
        assert len(events) > 0, "No SSE events received"
        
        # Verify we got expected event types
        event_types = [e.get("type") for e in events]
        assert "complete" in event_types or "fix" in event_types or "info" in event_types, \
            f"Expected fix/info/complete events, got: {event_types}"
        
        # Check complete event structure
        complete_events = [e for e in events if e.get("type") == "complete"]
        if complete_events:
            complete = complete_events[0]
            assert "fixed" in complete, "Complete event missing 'fixed' count"
            assert "errors" in complete, "Complete event missing 'errors' count"
            print(f"✓ Alt-text fix SSE stream: fixed={complete['fixed']}, errors={complete['errors']}")
        else:
            print(f"✓ Alt-text fix SSE stream received {len(events)} events: {event_types}")

    # ═══════════════════════════════════════════════════
    # RECOVERY STATS TESTS
    # ═══════════════════════════════════════════════════

    def test_recovery_stats(self):
        """GET /api/shopify/pulse/recovery/stats — returns abandoned/recovered/revenue/commission"""
        resp = self.session.get(f"{BASE_URL}/api/shopify/pulse/recovery/stats")
        assert resp.status_code == 200, f"Recovery stats failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        # Verify required fields
        assert "abandoned" in data, "Missing 'abandoned' count"
        assert "recovered" in data, "Missing 'recovered' count"
        assert "revenue_recovered" in data, "Missing 'revenue_recovered'"
        assert "commission_earned" in data, "Missing 'commission_earned'"
        
        # Verify types
        assert isinstance(data["abandoned"], int), "abandoned should be int"
        assert isinstance(data["recovered"], int), "recovered should be int"
        assert isinstance(data["revenue_recovered"], (int, float)), "revenue_recovered should be numeric"
        assert isinstance(data["commission_earned"], (int, float)), "commission_earned should be numeric"
        
        # Verify recovery_rate if present
        if "recovery_rate" in data:
            assert isinstance(data["recovery_rate"], (int, float)), "recovery_rate should be numeric"
        
        print(f"✓ Recovery stats: abandoned={data['abandoned']}, recovered={data['recovered']}, revenue=${data['revenue_recovered']}, commission=${data['commission_earned']}")

    # ═══════════════════════════════════════════════════
    # BILLING PLANS TESTS
    # ═══════════════════════════════════════════════════

    def test_billing_plans(self):
        """GET /api/shopify-billing/plans — returns 3 billing plans"""
        resp = self.session.get(f"{BASE_URL}/api/shopify-billing/plans")
        assert resp.status_code == 200, f"Billing plans failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert "plans" in data, "Missing 'plans' in response"
        plans = data["plans"]
        
        # Verify we have 3 plans
        assert len(plans) == 3, f"Expected 3 plans, got {len(plans)}"
        
        # Verify plan structure
        expected_plan_ids = {"starter", "professional", "enterprise"}
        actual_plan_ids = {p.get("id") for p in plans}
        assert expected_plan_ids == actual_plan_ids, f"Expected plans {expected_plan_ids}, got {actual_plan_ids}"
        
        # Verify each plan has required fields
        for plan in plans:
            assert "id" in plan, "Plan missing 'id'"
            assert "name" in plan, "Plan missing 'name'"
            assert "price" in plan, "Plan missing 'price'"
            assert "features" in plan, "Plan missing 'features'"
            assert "trial_days" in plan, "Plan missing 'trial_days'"
            assert isinstance(plan["features"], list), "features should be a list"
            assert len(plan["features"]) > 0, "features should not be empty"
        
        # Verify pricing order (starter < professional < enterprise)
        prices = {p["id"]: p["price"] for p in plans}
        assert prices["starter"] < prices["professional"] < prices["enterprise"], \
            f"Pricing order incorrect: {prices}"
        
        plan_summary = [f"{p['id']}=${p['price']}" for p in plans]
        print(f"✓ Billing plans: {plan_summary}")

    # ═══════════════════════════════════════════════════
    # CHECKOUT WEBHOOK TESTS
    # ═══════════════════════════════════════════════════

    def test_checkout_created_webhook(self):
        """POST /api/shopify/pulse/webhook/checkout-created — captures abandoned cart"""
        test_token = f"test_checkout_{int(time.time())}"
        
        resp = self.session.post(
            f"{BASE_URL}/api/shopify/pulse/webhook/checkout-created",
            json={
                "token": test_token,
                "email": "test@example.com",
                "phone": "+16134000000",
                "total_price": "99.99",
                "line_items": [
                    {"title": "Test Product", "quantity": 1, "price": "99.99"}
                ]
            },
            headers={
                **self.session.headers,
                "X-Shopify-Shop-Domain": "test-store.myshopify.com"
            }
        )
        assert resp.status_code == 200, f"Checkout webhook failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert data.get("status") == "captured", f"Expected status='captured', got {data.get('status')}"
        assert data.get("checkout_token") == test_token, "checkout_token not echoed"
        
        print(f"✓ Checkout webhook captured: token={test_token}")

    def test_checkout_webhook_no_token(self):
        """POST /api/shopify/pulse/webhook/checkout-created — handles missing token"""
        resp = self.session.post(
            f"{BASE_URL}/api/shopify/pulse/webhook/checkout-created",
            json={"email": "test@example.com"}
        )
        assert resp.status_code == 200, f"Webhook failed: {resp.status_code}"
        
        data = resp.json()
        assert data.get("status") == "no_token", "Expected status='no_token' for missing token"
        print(f"✓ Checkout webhook handles missing token correctly")

    # ═══════════════════════════════════════════════════
    # GDPR WEBHOOK TESTS
    # ═══════════════════════════════════════════════════

    def test_gdpr_customers_redact(self):
        """POST /api/shopify/pulse/webhooks/customers-redact — returns status=ok"""
        resp = self.session.post(
            f"{BASE_URL}/api/shopify/pulse/webhooks/customers-redact",
            json={
                "shop_domain": "test-store.myshopify.com",
                "customer": {"id": "12345"}
            }
        )
        assert resp.status_code == 200, f"GDPR customers-redact failed: {resp.status_code}"
        
        data = resp.json()
        assert data.get("status") == "ok", f"Expected status='ok', got {data}"
        print(f"✓ GDPR customers-redact returns status=ok")

    def test_gdpr_customers_data_request(self):
        """POST /api/shopify/pulse/webhooks/customers-data-request — returns status=ok"""
        resp = self.session.post(
            f"{BASE_URL}/api/shopify/pulse/webhooks/customers-data-request",
            json={
                "shop_domain": "test-store.myshopify.com",
                "customer": {"id": "12345"}
            }
        )
        assert resp.status_code == 200, f"GDPR customers-data-request failed: {resp.status_code}"
        
        data = resp.json()
        assert data.get("status") == "ok", f"Expected status='ok', got {data}"
        print(f"✓ GDPR customers-data-request returns status=ok")

    def test_gdpr_shop_redact(self):
        """POST /api/shopify/pulse/webhooks/shop-redact — returns status=ok"""
        resp = self.session.post(
            f"{BASE_URL}/api/shopify/pulse/webhooks/shop-redact",
            json={"shop_domain": "test-store.myshopify.com"}
        )
        assert resp.status_code == 200, f"GDPR shop-redact failed: {resp.status_code}"
        
        data = resp.json()
        assert data.get("status") == "ok", f"Expected status='ok', got {data}"
        print(f"✓ GDPR shop-redact returns status=ok")

    # ═══════════════════════════════════════════════════
    # ROUTE REGISTRATION VERIFICATION
    # ═══════════════════════════════════════════════════

    def test_routes_registered(self):
        """Verify all Shopify routes are registered in the backend"""
        # Test that routes exist by checking they don't return 404
        routes_to_check = [
            ("POST", "/api/shopify/pulse/scan"),
            ("POST", "/api/shopify/pulse/fix/alt-text"),
            ("GET", "/api/shopify/pulse/recovery/stats"),
            ("GET", "/api/shopify-billing/plans"),
            ("POST", "/api/shopify/pulse/webhook/checkout-created"),
            ("POST", "/api/shopify/pulse/webhooks/customers-redact"),
            ("POST", "/api/shopify/pulse/webhooks/customers-data-request"),
            ("POST", "/api/shopify/pulse/webhooks/shop-redact"),
        ]
        
        for method, path in routes_to_check:
            if method == "GET":
                resp = self.session.get(f"{BASE_URL}{path}")
            else:
                resp = self.session.post(f"{BASE_URL}{path}", json={})
            
            # 404 means route not registered, anything else means it exists
            assert resp.status_code != 404, f"Route {method} {path} not registered (404)"
            print(f"✓ Route {method} {path} is registered (status={resp.status_code})")


class TestShopifyBillingSubscribe:
    """Test Shopify Billing subscription flow (scaffold mode)"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "teji.ss1986@gmail.com", "password": "<REDACTED>"}
        )
        assert login_resp.status_code == 200
        token = login_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def test_subscribe_scaffold_mode(self):
        """POST /api/shopify-billing/subscribe — returns scaffold mode response"""
        resp = self.session.post(
            f"{BASE_URL}/api/shopify-billing/subscribe",
            json={
                "plan_id": "professional",
                "shop": "demo-store"
            }
        )
        # Should return 200 with scaffold mode info (no real Shopify token)
        assert resp.status_code == 200, f"Subscribe failed: {resp.status_code} - {resp.text}"
        
        data = resp.json()
        assert data.get("mode") == "scaffold", "Expected scaffold mode"
        assert "setup_required" in data, "Missing setup_required in scaffold response"
        print(f"✓ Subscribe returns scaffold mode with setup instructions")

    def test_subscribe_invalid_plan(self):
        """POST /api/shopify-billing/subscribe — rejects invalid plan"""
        resp = self.session.post(
            f"{BASE_URL}/api/shopify-billing/subscribe",
            json={
                "plan_id": "invalid_plan",
                "shop": "demo-store"
            }
        )
        assert resp.status_code == 400, f"Expected 400 for invalid plan, got {resp.status_code}"
        print(f"✓ Subscribe rejects invalid plan with 400")

    def test_subscription_status(self):
        """GET /api/shopify-billing/status/{shop} — returns subscription status"""
        resp = self.session.get(f"{BASE_URL}/api/shopify-billing/status/demo-store")
        assert resp.status_code == 200, f"Status check failed: {resp.status_code}"
        
        data = resp.json()
        assert "status" in data, "Missing 'status' in response"
        assert "shop" in data, "Missing 'shop' in response"
        print(f"✓ Subscription status: {data.get('status')} for {data.get('shop')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
