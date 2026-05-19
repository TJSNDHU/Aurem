"""
Iteration 191 - Stripe LIVE Checkout Backend Tests
===================================================
Tests for Stripe payment endpoints with LIVE mode.
IMPORTANT: DO NOT make actual payments - only verify checkout URL generation.

Endpoints tested:
- GET /api/payments/stripe-status
- GET /api/payments/packages
- GET /api/payments/config
- POST /api/payments/checkout (starter, growth, enterprise)
- POST /api/payments/checkout (invalid package)
- GET /api/payments/subscription
- GET /api/payments/history
- POST /api/payments/portal
- POST /api/payments/webhook/stripe
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
TEST_EMAIL = "teji.ss1986@gmail.com"
TEST_PASSWORD = "<REDACTED>"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for protected endpoints."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Auth failed: {response.status_code} - {response.text[:200]}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestStripeStatus:
    """Test Stripe connection status endpoint."""

    def test_stripe_status_returns_connected(self):
        """GET /api/payments/stripe-status should return connected=true and mode=live."""
        response = requests.get(f"{BASE_URL}/api/payments/stripe-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("connected") is True, f"Expected connected=true, got {data}"
        assert data.get("mode") == "live", f"Expected mode=live, got {data.get('mode')}"
        print(f"✓ Stripe status: connected={data.get('connected')}, mode={data.get('mode')}")


class TestPackages:
    """Test packages listing endpoint."""

    def test_packages_returns_three_tiers(self):
        """GET /api/payments/packages should return 3 packages with correct amounts."""
        response = requests.get(f"{BASE_URL}/api/payments/packages")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        packages = data.get("packages", [])
        assert len(packages) == 3, f"Expected 3 packages, got {len(packages)}"
        
        # Verify each package
        package_map = {p["id"]: p for p in packages}
        
        assert "starter" in package_map, "Missing starter package"
        assert package_map["starter"]["amount"] == 97.00, f"Starter should be $97, got {package_map['starter']['amount']}"
        
        assert "growth" in package_map, "Missing growth package"
        assert package_map["growth"]["amount"] == 297.00, f"Growth should be $297, got {package_map['growth']['amount']}"
        
        assert "enterprise" in package_map, "Missing enterprise package"
        assert package_map["enterprise"]["amount"] == 997.00, f"Enterprise should be $997, got {package_map['enterprise']['amount']}"
        
        print(f"✓ Packages: starter=$97, growth=$297, enterprise=$997")


class TestConfig:
    """Test payment config endpoint."""

    def test_config_returns_publishable_key(self):
        """GET /api/payments/config should return live publishable key and plans."""
        response = requests.get(f"{BASE_URL}/api/payments/config")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        pk = data.get("publishable_key", "")
        
        # Verify it's a live key (starts with pk_live_)
        assert pk.startswith("pk_live_"), f"Expected live publishable key, got {pk[:20]}..."
        
        # Verify plans are included
        plans = data.get("plans", {})
        assert "starter" in plans, "Missing starter plan in config"
        assert "growth" in plans, "Missing growth plan in config"
        assert "enterprise" in plans, "Missing enterprise plan in config"
        
        print(f"✓ Config: publishable_key=pk_live_..., plans={list(plans.keys())}")


class TestCheckout:
    """Test checkout session creation - LIVE mode, no actual payments."""

    def test_checkout_starter_creates_stripe_url(self, auth_headers):
        """POST /api/payments/checkout with starter should create checkout.stripe.com URL."""
        response = requests.post(
            f"{BASE_URL}/api/payments/checkout",
            headers=auth_headers,
            json={"package_id": "starter", "origin_url": "https://aurem.live"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        url = data.get("url", "")
        session_id = data.get("session_id", "")
        
        assert "checkout.stripe.com" in url, f"Expected checkout.stripe.com URL, got {url[:50]}..."
        assert session_id, "Missing session_id in response"
        
        print(f"✓ Starter checkout: session_id={session_id[:20]}..., url contains checkout.stripe.com")

    def test_checkout_growth_creates_stripe_url(self, auth_headers):
        """POST /api/payments/checkout with growth should create checkout.stripe.com URL."""
        response = requests.post(
            f"{BASE_URL}/api/payments/checkout",
            headers=auth_headers,
            json={"package_id": "growth", "origin_url": "https://aurem.live"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        url = data.get("url", "")
        
        assert "checkout.stripe.com" in url, f"Expected checkout.stripe.com URL, got {url[:50]}..."
        print(f"✓ Growth checkout: url contains checkout.stripe.com")

    def test_checkout_enterprise_creates_stripe_url(self, auth_headers):
        """POST /api/payments/checkout with enterprise should create checkout.stripe.com URL."""
        response = requests.post(
            f"{BASE_URL}/api/payments/checkout",
            headers=auth_headers,
            json={"package_id": "enterprise", "origin_url": "https://aurem.live"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        url = data.get("url", "")
        
        assert "checkout.stripe.com" in url, f"Expected checkout.stripe.com URL, got {url[:50]}..."
        print(f"✓ Enterprise checkout: url contains checkout.stripe.com")

    def test_checkout_invalid_package_returns_400(self, auth_headers):
        """POST /api/payments/checkout with invalid package should return 400."""
        response = requests.post(
            f"{BASE_URL}/api/payments/checkout",
            headers=auth_headers,
            json={"package_id": "invalid_package", "origin_url": "https://aurem.live"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"✓ Invalid package returns 400 as expected")


class TestSubscription:
    """Test subscription status endpoint."""

    def test_subscription_requires_auth(self):
        """GET /api/payments/subscription without auth should return 401."""
        response = requests.get(f"{BASE_URL}/api/payments/subscription")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ Subscription endpoint requires auth (401)")

    def test_subscription_returns_status(self, auth_headers):
        """GET /api/payments/subscription with auth should return subscription status."""
        response = requests.get(
            f"{BASE_URL}/api/payments/subscription",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should have has_subscription and plan fields
        assert "has_subscription" in data, "Missing has_subscription field"
        assert "plan" in data, "Missing plan field"
        
        print(f"✓ Subscription status: has_subscription={data.get('has_subscription')}, plan={data.get('plan')}")


class TestHistory:
    """Test payment history endpoint."""

    def test_history_requires_auth(self):
        """GET /api/payments/history without auth should return 401."""
        response = requests.get(f"{BASE_URL}/api/payments/history")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ History endpoint requires auth (401)")

    def test_history_returns_transactions(self, auth_headers):
        """GET /api/payments/history with auth should return transactions list."""
        response = requests.get(
            f"{BASE_URL}/api/payments/history",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "transactions" in data, "Missing transactions field"
        assert isinstance(data["transactions"], list), "transactions should be a list"
        
        print(f"✓ History: {len(data['transactions'])} transactions found")


class TestPortal:
    """Test billing portal endpoint."""

    def test_portal_requires_auth(self):
        """POST /api/payments/portal without auth should return 401."""
        response = requests.post(f"{BASE_URL}/api/payments/portal")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ Portal endpoint requires auth (401)")

    def test_portal_returns_billing_url(self, auth_headers):
        """POST /api/payments/portal with auth should return billing.stripe.com URL."""
        response = requests.post(
            f"{BASE_URL}/api/payments/portal",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        url = data.get("url", "")
        
        assert "billing.stripe.com" in url, f"Expected billing.stripe.com URL, got {url[:50]}..."
        print(f"✓ Portal: url contains billing.stripe.com")


class TestWebhook:
    """Test Stripe webhook endpoint."""

    def test_webhook_accepts_events(self):
        """POST /api/payments/webhook/stripe should accept events and return received=true."""
        # Send a mock event (no signature verification for testing)
        mock_event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_mock",
                    "payment_status": "paid"
                }
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/payments/webhook/stripe",
            json=mock_event,
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("received") is True, f"Expected received=true, got {data}"
        
        print(f"✓ Webhook: received=true, event_type={data.get('event_type')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
