"""
Client Portal P0/P1 Backend Tests
=================================
Tests for:
- BIN System (GET /api/client/bin-id, GET /api/client/bin/{bin_id})
- Onboarding (GET /api/client/onboarding-status, POST /api/client/onboarding/step1, POST /api/client/onboarding/complete)
- Activity Feed (GET /api/client/activity)
- Profile (PUT /api/client/profile)
- Notification Preferences (GET/PUT /api/client/notification-preferences)
- Payments (GET /api/payments/subscription, POST /api/payments/portal, GET /api/payments/config)
- Push (GET /api/push/vapid-key)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from test_credentials.md
TEST_EMAIL = "teji.ss1986@gmail.com"
TEST_PASSWORD = "Admin123"
KNOWN_BIN_ID = "BIN-3bc7b8e7-059-E8D9FB"


class TestAuthSetup:
    """Get auth token for subsequent tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get JWT token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=15
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data, f"No token in response: {data}"
        return data["token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Headers with Bearer token"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestBINSystem(TestAuthSetup):
    """BIN (Business Intelligence Node) endpoint tests"""
    
    def test_get_bin_id_requires_auth(self):
        """GET /api/client/bin-id should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/client/bin-id", timeout=10)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_get_bin_id_with_auth(self, auth_headers):
        """GET /api/client/bin-id should return bin_id for logged-in user"""
        response = requests.get(f"{BASE_URL}/api/client/bin-id", headers=auth_headers, timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "bin_id" in data, f"No bin_id in response: {data}"
        assert "tenant_id" in data, f"No tenant_id in response: {data}"
        assert data["bin_id"].startswith("BIN-"), f"Invalid BIN format: {data['bin_id']}"
        print(f"BIN ID: {data['bin_id']}, Tenant: {data['tenant_id']}")
    
    def test_get_bin_public_endpoint(self):
        """GET /api/client/bin/{bin_id} is PUBLIC - no auth needed"""
        response = requests.get(f"{BASE_URL}/api/client/bin/{KNOWN_BIN_ID}", timeout=10)
        # Should return 200 with data or 404 if BIN doesn't exist
        assert response.status_code in [200, 404], f"Expected 200/404, got {response.status_code}: {response.text}"
        if response.status_code == 200:
            data = response.json()
            assert "bin_id" in data, f"No bin_id in response: {data}"
            assert "metrics" in data, f"No metrics in response: {data}"
            assert "generated_at" in data, f"No generated_at in response: {data}"
            print(f"BIN Data: {data}")
    
    def test_get_bin_invalid_id(self):
        """GET /api/client/bin/{invalid} should return 404"""
        response = requests.get(f"{BASE_URL}/api/client/bin/INVALID-BIN-123", timeout=10)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestOnboarding(TestAuthSetup):
    """Onboarding flow endpoint tests"""
    
    def test_onboarding_status_requires_auth(self):
        """GET /api/client/onboarding-status should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/client/onboarding-status", timeout=10)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_onboarding_status_with_auth(self, auth_headers):
        """GET /api/client/onboarding-status should return status flags"""
        response = requests.get(f"{BASE_URL}/api/client/onboarding-status", headers=auth_headers, timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Verify all required fields exist
        assert "onboarding_complete" in data, f"Missing onboarding_complete: {data}"
        assert "has_workspace" in data, f"Missing has_workspace: {data}"
        assert "has_scans" in data, f"Missing has_scans: {data}"
        # Verify types
        assert isinstance(data["onboarding_complete"], bool), f"onboarding_complete should be bool: {data}"
        assert isinstance(data["has_workspace"], bool), f"has_workspace should be bool: {data}"
        assert isinstance(data["has_scans"], bool), f"has_scans should be bool: {data}"
        print(f"Onboarding Status: {data}")
    
    def test_onboarding_step1_requires_auth(self):
        """POST /api/client/onboarding/step1 should return 401 without auth"""
        response = requests.post(
            f"{BASE_URL}/api/client/onboarding/step1",
            json={"business_name": "Test", "website_url": "test.com"},
            timeout=10
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_onboarding_step1_with_auth(self, auth_headers):
        """POST /api/client/onboarding/step1 should save business info"""
        response = requests.post(
            f"{BASE_URL}/api/client/onboarding/step1",
            headers=auth_headers,
            json={
                "business_name": "TEST_Portal_Business",
                "website_url": "testportal.example.com",
                "industry": "technology"
            },
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Expected success=True: {data}"
        assert "website" in data, f"Missing website in response: {data}"
        # Verify URL was normalized with https
        assert data["website"].startswith("https://"), f"Website should have https: {data['website']}"
        print(f"Step1 Response: {data}")
    
    def test_onboarding_complete_requires_auth(self):
        """POST /api/client/onboarding/complete should return 401 without auth"""
        response = requests.post(f"{BASE_URL}/api/client/onboarding/complete", timeout=10)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_onboarding_complete_with_auth(self, auth_headers):
        """POST /api/client/onboarding/complete should mark complete and return bin_id"""
        response = requests.post(
            f"{BASE_URL}/api/client/onboarding/complete",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Expected success=True: {data}"
        assert "bin_id" in data, f"Missing bin_id in response: {data}"
        assert data["bin_id"].startswith("BIN-"), f"Invalid BIN format: {data['bin_id']}"
        print(f"Onboarding Complete: {data}")


class TestActivityFeed(TestAuthSetup):
    """Activity Feed endpoint tests"""
    
    def test_activity_requires_auth(self):
        """GET /api/client/activity should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/client/activity", timeout=10)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_activity_with_auth(self, auth_headers):
        """GET /api/client/activity should return last 10 events"""
        response = requests.get(f"{BASE_URL}/api/client/activity", headers=auth_headers, timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "events" in data, f"Missing events in response: {data}"
        assert isinstance(data["events"], list), f"events should be list: {data}"
        # Verify max 10 events
        assert len(data["events"]) <= 10, f"Should return max 10 events, got {len(data['events'])}"
        # Verify event structure if any events exist
        if data["events"]:
            event = data["events"][0]
            assert "icon" in event, f"Event missing icon: {event}"
            assert "type" in event, f"Event missing type: {event}"
            assert "description" in event, f"Event missing description: {event}"
            assert "timestamp" in event, f"Event missing timestamp: {event}"
        print(f"Activity Feed: {len(data['events'])} events")


class TestProfile(TestAuthSetup):
    """Profile update endpoint tests"""
    
    def test_profile_update_requires_auth(self):
        """PUT /api/client/profile should return 401 without auth"""
        response = requests.put(
            f"{BASE_URL}/api/client/profile",
            json={"business_name": "Test"},
            timeout=10
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_profile_update_with_auth(self, auth_headers):
        """PUT /api/client/profile should update business profile"""
        response = requests.put(
            f"{BASE_URL}/api/client/profile",
            headers=auth_headers,
            json={
                "business_name": "TEST_Updated_Business",
                "business_description": "A test business for portal testing",
                "services": ["consulting", "development"],
                "tone": "professional"
            },
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Expected success=True: {data}"
        assert "updated_fields" in data, f"Missing updated_fields: {data}"
        assert len(data["updated_fields"]) > 0, f"No fields updated: {data}"
        print(f"Profile Update: {data}")


class TestNotificationPreferences(TestAuthSetup):
    """Notification preferences endpoint tests"""
    
    def test_get_preferences_requires_auth(self):
        """GET /api/client/notification-preferences should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/client/notification-preferences", timeout=10)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_get_preferences_with_auth(self, auth_headers):
        """GET /api/client/notification-preferences should return preference flags"""
        response = requests.get(
            f"{BASE_URL}/api/client/notification-preferences",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Verify expected preference fields
        expected_fields = ["scan_complete", "repair_deployed", "new_lead", "ora_action_required", "morning_brief"]
        for field in expected_fields:
            assert field in data, f"Missing preference field {field}: {data}"
            assert isinstance(data[field], bool), f"{field} should be bool: {data}"
        print(f"Notification Preferences: {data}")
    
    def test_update_preferences_requires_auth(self):
        """PUT /api/client/notification-preferences should return 401 without auth"""
        response = requests.put(
            f"{BASE_URL}/api/client/notification-preferences",
            json={"scan_complete": True},
            timeout=10
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_update_preferences_with_auth(self, auth_headers):
        """PUT /api/client/notification-preferences should save preference flags"""
        response = requests.put(
            f"{BASE_URL}/api/client/notification-preferences",
            headers=auth_headers,
            json={
                "scan_complete": True,
                "repair_deployed": True,
                "new_lead": False,
                "ora_action_required": True,
                "morning_brief": False
            },
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Expected success=True: {data}"
        print(f"Preferences Updated: {data}")
        
        # Verify persistence by reading back
        verify_response = requests.get(
            f"{BASE_URL}/api/client/notification-preferences",
            headers=auth_headers,
            timeout=10
        )
        verify_data = verify_response.json()
        assert verify_data.get("new_lead") == False, f"new_lead should be False: {verify_data}"
        assert verify_data.get("morning_brief") == False, f"morning_brief should be False: {verify_data}"


class TestPayments(TestAuthSetup):
    """Payment/Billing endpoint tests"""
    
    def test_subscription_status_requires_auth(self):
        """GET /api/payments/subscription should return 401 without auth"""
        response = requests.get(f"{BASE_URL}/api/payments/subscription", timeout=10)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_subscription_status_with_auth(self, auth_headers):
        """GET /api/payments/subscription should return subscription status"""
        response = requests.get(
            f"{BASE_URL}/api/payments/subscription",
            headers=auth_headers,
            timeout=15
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Verify required fields
        assert "has_subscription" in data, f"Missing has_subscription: {data}"
        assert "plan" in data, f"Missing plan: {data}"
        assert isinstance(data["has_subscription"], bool), f"has_subscription should be bool: {data}"
        print(f"Subscription Status: {data}")
    
    def test_billing_portal_requires_auth(self):
        """POST /api/payments/portal should return 401 without auth"""
        response = requests.post(f"{BASE_URL}/api/payments/portal", timeout=10)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_billing_portal_with_auth(self, auth_headers):
        """POST /api/payments/portal should return Stripe billing portal URL"""
        response = requests.post(
            f"{BASE_URL}/api/payments/portal",
            headers=auth_headers,
            timeout=15
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "url" in data, f"Missing url in response: {data}"
        # Verify it's a Stripe billing portal URL
        assert "stripe.com" in data["url"] or "billing.stripe.com" in data["url"], f"Invalid portal URL: {data['url']}"
        print(f"Billing Portal URL: {data['url'][:80]}...")
    
    def test_payment_config_public(self):
        """GET /api/payments/config should return publishable key and plans (no auth needed)"""
        response = requests.get(f"{BASE_URL}/api/payments/config", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Verify required fields
        assert "publishable_key" in data, f"Missing publishable_key: {data}"
        assert "plans" in data, f"Missing plans: {data}"
        assert "currency" in data, f"Missing currency: {data}"
        # Verify plans structure
        assert isinstance(data["plans"], dict), f"plans should be dict: {data}"
        # Verify at least starter plan exists
        assert "starter" in data["plans"], f"Missing starter plan: {data['plans']}"
        # Verify plan has features
        starter = data["plans"]["starter"]
        assert "name" in starter, f"Plan missing name: {starter}"
        assert "amount" in starter, f"Plan missing amount: {starter}"
        assert "features" in starter, f"Plan missing features: {starter}"
        print(f"Payment Config: {data['currency']}, Plans: {list(data['plans'].keys())}")


class TestPushNotifications(TestAuthSetup):
    """Push notification endpoint tests"""
    
    def test_vapid_key_public(self):
        """GET /api/push/vapid-key should return VAPID public key (no auth needed)"""
        response = requests.get(f"{BASE_URL}/api/push/vapid-key", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "public_key" in data, f"Missing public_key: {data}"
        # VAPID public key should be a base64 string starting with 'B'
        assert data["public_key"].startswith("B"), f"Invalid VAPID key format: {data['public_key'][:20]}"
        assert len(data["public_key"]) > 50, f"VAPID key too short: {len(data['public_key'])}"
        print(f"VAPID Key: {data['public_key'][:40]}...")


class TestStripeStatus:
    """Stripe connection status test"""
    
    def test_stripe_status(self):
        """GET /api/payments/stripe-status should return connection status"""
        response = requests.get(f"{BASE_URL}/api/payments/stripe-status", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "connected" in data, f"Missing connected field: {data}"
        if data["connected"]:
            assert "mode" in data, f"Missing mode when connected: {data}"
            print(f"Stripe Status: Connected ({data.get('mode', 'unknown')} mode)")
        else:
            print(f"Stripe Status: Not connected - {data.get('error', 'unknown error')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
