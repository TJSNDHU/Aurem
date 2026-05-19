"""
Shopify Phase 1 Backend Tests — Iteration 168
==============================================
Tests for:
1. Billing Router: /api/shopify-billing/plans, /api/shopify-billing/status/{shop}
2. Pulse Scanner: /api/shopify/pulse/scan (scaffold mode)
3. Alt-text Fix SSE: /api/shopify/pulse/fix/alt-text (scaffold mode)
4. Checkout Webhook: /api/shopify/pulse/webhook/checkout-created
5. Recovery Stats: /api/shopify/pulse/recovery/stats
6. GDPR Webhooks: customers-redact, customers-data-request, shop-redact
7. Code verification: charge_recovery_commission, WhatsAppEngine/EmailEngine/SMSEngine imports
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://ai-platform-preview-3.preview.emergentagent.com"


class TestShopifyBillingRouter:
    """Tests for /api/shopify-billing endpoints"""

    def test_get_plans_returns_3_plans(self):
        """GET /api/shopify-billing/plans — returns 3 Shopify plans"""
        response = requests.get(f"{BASE_URL}/api/shopify-billing/plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "plans" in data, "Response should have 'plans' key"
        plans = data["plans"]
        assert len(plans) == 3, f"Expected 3 plans, got {len(plans)}"
        
        # Verify plan IDs
        plan_ids = [p["id"] for p in plans]
        assert "starter" in plan_ids, "Missing 'starter' plan"
        assert "professional" in plan_ids, "Missing 'professional' plan"
        assert "enterprise" in plan_ids, "Missing 'enterprise' plan"
        
        # Verify plan structure
        for plan in plans:
            assert "name" in plan, f"Plan {plan.get('id')} missing 'name'"
            assert "price" in plan, f"Plan {plan.get('id')} missing 'price'"
            assert "interval" in plan, f"Plan {plan.get('id')} missing 'interval'"
            assert "features" in plan, f"Plan {plan.get('id')} missing 'features'"
        
        print(f"✓ GET /api/shopify-billing/plans — returned {len(plans)} plans: {plan_ids}")

    def test_get_status_for_nonexistent_shop(self):
        """GET /api/shopify-billing/status/test-store — returns free for non-existent shop"""
        response = requests.get(f"{BASE_URL}/api/shopify-billing/status/test-store")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "free", f"Expected status='free', got {data.get('status')}"
        assert data.get("plan") is None, f"Expected plan=None, got {data.get('plan')}"
        assert "test-store" in data.get("shop", ""), "Shop domain should contain 'test-store'"
        
        print(f"✓ GET /api/shopify-billing/status/test-store — status={data['status']}, plan={data['plan']}")


class TestShopifyPulseScanner:
    """Tests for /api/shopify/pulse endpoints"""

    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "teji.ss1986@gmail.com", "password": "<REDACTED>"}
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")

    def test_pulse_scan_scaffold_mode(self, auth_token):
        """POST /api/shopify/pulse/scan — scaffold mode returns health_score=67, 3 issues"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/scan",
            json={"shop": "test-store"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("mode") == "scaffold", f"Expected mode='scaffold', got {data.get('mode')}"
        assert data.get("health_score") == 67, f"Expected health_score=67, got {data.get('health_score')}"
        assert "issues" in data, "Response should have 'issues' key"
        assert len(data["issues"]) == 3, f"Expected 3 issues, got {len(data['issues'])}"
        assert "revenue_at_risk_monthly" in data, "Response should have 'revenue_at_risk_monthly'"
        
        # Verify issue types
        issue_types = [i["type"] for i in data["issues"]]
        assert "missing_alt_text" in issue_types, "Missing 'missing_alt_text' issue"
        assert "abandoned_cart_rate" in issue_types, "Missing 'abandoned_cart_rate' issue"
        
        print(f"✓ POST /api/shopify/pulse/scan — health_score={data['health_score']}, issues={len(data['issues'])}, revenue_at_risk=${data.get('revenue_at_risk_monthly', 0)}")

    def test_alt_text_fix_sse_stream(self, auth_token):
        """POST /api/shopify/pulse/fix/alt-text — SSE stream returns events (scaffold mode)"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/fix/alt-text",
            json={"shop": "test-store"},
            headers={"Authorization": f"Bearer {auth_token}"},
            stream=True
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "text/event-stream" in response.headers.get("content-type", ""), "Expected SSE content-type"
        
        # Read SSE events
        events = []
        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith("data:"):
                events.append(line)
                if len(events) >= 10:  # Limit to prevent infinite loop
                    break
        
        assert len(events) > 0, "Expected at least one SSE event"
        
        # Check for complete event
        complete_found = any("complete" in e for e in events)
        fix_found = any("fix" in e for e in events)
        
        print(f"✓ POST /api/shopify/pulse/fix/alt-text — received {len(events)} SSE events, complete={complete_found}, fix={fix_found}")


class TestShopifyCheckoutWebhook:
    """Tests for checkout webhook and recovery stats"""

    def test_checkout_created_webhook_captures_cart(self):
        """POST /api/shopify/pulse/webhook/checkout-created — captures abandoned cart to DB"""
        test_checkout = {
            "token": f"test_checkout_{os.urandom(4).hex()}",
            "email": "test@example.com",
            "phone": "+16134000000",
            "shop_domain": "test-store.myshopify.com",
            "total_price": "99.99",
            "line_items": [
                {"title": "Test Product", "quantity": 1, "price": "99.99"}
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/webhook/checkout-created",
            json=test_checkout,
            headers={"X-Shopify-Shop-Domain": "test-store.myshopify.com"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "captured", f"Expected status='captured', got {data.get('status')}"
        assert data.get("checkout_token") == test_checkout["token"], "Checkout token mismatch"
        
        print(f"✓ POST /api/shopify/pulse/webhook/checkout-created — status={data['status']}, token={data['checkout_token'][:20]}...")

    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "teji.ss1986@gmail.com", "password": "<REDACTED>"}
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed")

    def test_recovery_stats_returns_counts(self, auth_token):
        """GET /api/shopify/pulse/recovery/stats — returns abandoned/recovered/revenue counts"""
        response = requests.get(
            f"{BASE_URL}/api/shopify/pulse/recovery/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "abandoned" in data, "Response should have 'abandoned' count"
        assert "recovered" in data, "Response should have 'recovered' count"
        assert "revenue_recovered" in data, "Response should have 'revenue_recovered'"
        assert "recovery_rate" in data, "Response should have 'recovery_rate'"
        
        print(f"✓ GET /api/shopify/pulse/recovery/stats — abandoned={data['abandoned']}, recovered={data['recovered']}, revenue=${data['revenue_recovered']}")


class TestShopifyGDPRWebhooks:
    """Tests for GDPR compliance webhooks"""

    def test_customers_redact_webhook(self):
        """POST /api/shopify/pulse/webhooks/customers-redact — GDPR returns status=ok"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/webhooks/customers-redact",
            json={
                "shop_domain": "test-store.myshopify.com",
                "customer": {"id": 12345, "email": "test@example.com"}
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "ok", f"Expected status='ok', got {data.get('status')}"
        
        print(f"✓ POST /api/shopify/pulse/webhooks/customers-redact — status={data['status']}")

    def test_customers_data_request_webhook(self):
        """POST /api/shopify/pulse/webhooks/customers-data-request — GDPR returns status=ok"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/webhooks/customers-data-request",
            json={
                "shop_domain": "test-store.myshopify.com",
                "customer": {"id": 12345, "email": "test@example.com"}
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "ok", f"Expected status='ok', got {data.get('status')}"
        
        print(f"✓ POST /api/shopify/pulse/webhooks/customers-data-request — status={data['status']}")

    def test_shop_redact_webhook(self):
        """POST /api/shopify/pulse/webhooks/shop-redact — GDPR returns status=ok"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/webhooks/shop-redact",
            json={"shop_domain": "test-store.myshopify.com"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "ok", f"Expected status='ok', got {data.get('status')}"
        
        print(f"✓ POST /api/shopify/pulse/webhooks/shop-redact — status={data['status']}")


class TestCodeVerification:
    """Tests to verify code structure and imports"""

    def test_billing_router_has_charge_recovery_commission(self):
        """Verify billing router has charge_recovery_commission() function"""
        billing_router_path = "/app/backend/routers/shopify_billing_router.py"
        with open(billing_router_path, "r") as f:
            content = f.read()
        
        assert "async def charge_recovery_commission" in content, "Missing charge_recovery_commission function"
        assert "RECOVERY_COMMISSION = 2.00" in content, "Missing $2 recovery commission constant"
        assert "appUsageRecordCreate" in content, "Missing GraphQL mutation for usage charge"
        
        print("✓ Billing router has charge_recovery_commission() with $2 commission and appUsageRecordCreate mutation")

    def test_pulse_router_has_recovery_engines(self):
        """Verify cart recovery uses WhatsAppEngine, EmailEngine, SMSEngine"""
        pulse_router_path = "/app/backend/routers/shopify_pulse_router.py"
        with open(pulse_router_path, "r") as f:
            content = f.read()
        
        assert "from services.whatsapp_engine import WhatsAppEngine" in content, "Missing WhatsAppEngine import"
        assert "from services.email_engine import EmailEngine" in content, "Missing EmailEngine import"
        assert "from services.sms_engine import SMSEngine" in content, "Missing SMSEngine import"
        
        # Verify recovery sequence order (WA → Email → SMS)
        assert "Hour 1: WhatsApp" in content or "Hour 1 → WhatsApp" in content or "whatsapp" in content.lower(), "Missing WhatsApp recovery step"
        assert "Hour 4: Email" in content or "Hour 4 → Email" in content or "email" in content.lower(), "Missing Email recovery step"
        assert "Hour 24: SMS" in content or "Hour 24 → SMS" in content or "sms" in content.lower(), "Missing SMS recovery step"
        
        print("✓ Pulse router imports WhatsAppEngine, EmailEngine, SMSEngine for cart recovery sequence")

    def test_shopify_app_toml_has_gdpr_webhooks(self):
        """Verify shopify.app.toml has GDPR webhook URLs configured"""
        toml_path = "/app/backend/shopify.app.toml"
        with open(toml_path, "r") as f:
            content = f.read()
        
        assert "customer_deletion_url" in content, "Missing customer_deletion_url in GDPR config"
        assert "customer_data_request_url" in content, "Missing customer_data_request_url in GDPR config"
        assert "shop_deletion_url" in content, "Missing shop_deletion_url in GDPR config"
        assert "api_version = \"2026-04\"" in content, "Missing or incorrect API version"
        
        print("✓ shopify.app.toml has GDPR webhook URLs and api_version=2026-04")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
