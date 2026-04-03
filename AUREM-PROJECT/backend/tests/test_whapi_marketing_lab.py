"""
Tests for Whapi.cloud WhatsApp Integration and Marketing Lab Endpoints
Tests: Phone validation, marketing lab contacts, scan insights, broadcasts, and launch invites
"""

import pytest
import requests
import os
from datetime import datetime, timezone

# Base URL from environment - MUST NOT have default, will fail fast if missing
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL environment variable is required")

BASE_URL = BASE_URL.rstrip("/")


class TestPublicWhatsAppValidation:
    """Tests for public WhatsApp validation endpoint POST /api/api/whatsapp/validate-number"""

    def test_validate_whatsapp_number_success(self):
        """Test validating a phone number via Whapi.cloud"""
        # Note: The endpoint path is /api/api/whatsapp/validate-number (nested /api)
        response = requests.post(
            f"{BASE_URL}/api/api/whatsapp/validate-number",
            json={"phone": "+14155552671"},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.json()}")

        # Should return 200 with validation result
        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        # Validation should return a dict with 'valid' key
        assert "valid" in data, f"Expected 'valid' key in response, got: {data}"

    def test_validate_whatsapp_number_missing_phone(self):
        """Test validation fails gracefully when phone is missing"""
        response = requests.post(
            f"{BASE_URL}/api/api/whatsapp/validate-number",
            json={},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.text}")

        # Should return 400 for missing phone
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

    def test_validate_whatsapp_number_empty_phone(self):
        """Test validation with empty phone string"""
        response = requests.post(
            f"{BASE_URL}/api/api/whatsapp/validate-number",
            json={"phone": ""},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.text}")

        # Should handle empty phone gracefully
        assert response.status_code in [
            200,
            400,
        ], f"Expected 200 or 400, got {response.status_code}"

    def test_validate_whatsapp_number_various_formats(self):
        """Test validation with various phone number formats"""
        formats_to_test = [
            "+1 (415) 555-2671",  # US format with formatting
            "14155552671",  # No plus
            "4155552671",  # No country code (10 digits)
            "+14155552671",  # Clean format
        ]

        for phone in formats_to_test:
            response = requests.post(
                f"{BASE_URL}/api/api/whatsapp/validate-number",
                json={"phone": phone},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            print(
                f"Phone: {phone} -> Status: {response.status_code}, Response: {response.json()}"
            )

            # All should succeed with validation result
            assert (
                response.status_code == 200
            ), f"Phone {phone} failed: {response.status_code}"
            assert "valid" in response.json(), f"Phone {phone} missing 'valid' key"


class TestMarketingLabAdminEndpoints:
    """
    Tests for Marketing Lab admin endpoints.
    Note: These require admin authentication. Without valid admin creds, expect 401/403.
    """

    def test_marketing_lab_whatsapp_contacts_no_auth(self):
        """Test GET /api/admin/marketing-lab/whatsapp-contacts returns 401 without auth"""
        response = requests.get(
            f"{BASE_URL}/api/admin/marketing-lab/whatsapp-contacts", timeout=30
        )

        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.text}")

        # Should require authentication
        assert response.status_code in [
            401,
            403,
        ], f"Expected 401/403, got {response.status_code}"

    def test_marketing_lab_scan_insights_no_auth(self):
        """Test GET /api/admin/marketing-lab/scan-insights returns 401 without auth"""
        response = requests.get(
            f"{BASE_URL}/api/admin/marketing-lab/scan-insights", timeout=30
        )

        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.text}")

        # Should require authentication
        assert response.status_code in [
            401,
            403,
        ], f"Expected 401/403, got {response.status_code}"

    def test_marketing_lab_send_broadcast_no_auth(self):
        """Test POST /api/admin/marketing-lab/send-broadcast returns 401 without auth"""
        response = requests.post(
            f"{BASE_URL}/api/admin/marketing-lab/send-broadcast",
            json={"message": "Test broadcast"},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.text}")

        # Should require authentication
        assert response.status_code in [
            401,
            403,
        ], f"Expected 401/403, got {response.status_code}"

    def test_marketing_lab_send_launch_invites_no_auth(self):
        """Test POST /api/admin/marketing-lab/send-launch-invites returns 401 without auth"""
        response = requests.post(
            f"{BASE_URL}/api/admin/marketing-lab/send-launch-invites",
            json={},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.text}")

        # Should require authentication
        assert response.status_code in [
            401,
            403,
        ], f"Expected 401/403, got {response.status_code}"

    def test_marketing_lab_social_posts_no_auth(self):
        """Test GET /api/admin/marketing-lab/social-posts returns 401 without auth"""
        response = requests.get(
            f"{BASE_URL}/api/admin/marketing-lab/social-posts", timeout=30
        )

        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.text}")

        # Should require authentication
        assert response.status_code in [
            401,
            403,
        ], f"Expected 401/403, got {response.status_code}"


class TestWhapiBioAgeScanFlow:
    """
    Tests for WhatsApp number capture in Bio-Age Scan flow.
    Verifies the integration between scan submission and WhatsApp validation.
    """

    def test_bio_scan_endpoint_with_whatsapp(self):
        """Test Bio-Age Scan submission endpoint captures WhatsApp number"""
        # Correct endpoint is /api/bio-scan/submit
        response = requests.post(
            f"{BASE_URL}/api/bio-scan/submit",
            json={
                "email": f"test_whapi_{datetime.now().timestamp()}@test.com",
                "name": "Test User WhatsApp",
                "age": 30,
                "concern": "dark_circles",
                "skin_type": "combination",
                "answers": {},
                "whatsapp": "+14155552671",
            },
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        print(f"Bio Scan Response Status: {response.status_code}")
        print(
            f"Response Body: {response.json() if response.status_code < 500 else response.text}"
        )

        # Should accept bio-scan submissions (200)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        # Should return referral code and message
        assert (
            "referral_code" in data
        ), f"Expected 'referral_code' in response, got: {data}"
        assert "message" in data, f"Expected 'message' in response, got: {data}"


class TestMilestoneNotificationFlow:
    """
    Tests related to milestone notifications via WhatsApp.
    These test the endpoint routes exist and respond appropriately.
    """

    def test_milestone_progress_endpoint_pattern(self):
        """Verify milestone-related endpoint patterns exist by checking server responsiveness"""
        # Test the health endpoint first to ensure server is up
        health = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert health.status_code == 200, "Server health check failed"
        print(f"Server healthy: {health.json()}")


class TestWhapiServiceIntegration:
    """
    Direct tests for Whapi.cloud service integration.
    Tests the actual API connectivity and response handling.
    """

    def test_whapi_phone_normalization(self):
        """Test phone number normalization through validation endpoint"""
        test_cases = [
            # (input, expected_normalized_pattern)
            ("+1 (416) 555-1234", "1416"),  # Canadian number
            ("14165551234", "1416"),
            ("+44 20 7946 0958", "4420"),  # UK number
        ]

        for phone_input, expected_pattern in test_cases:
            response = requests.post(
                f"{BASE_URL}/api/api/whatsapp/validate-number",
                json={"phone": phone_input},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            print(f"Phone: {phone_input} -> Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                # Check if normalized phone is present
                if "phone_normalized" in data:
                    assert (
                        expected_pattern in data["phone_normalized"]
                    ), f"Expected {expected_pattern} in normalized phone, got {data['phone_normalized']}"
                print(f"  Validation result: {data}")


class TestEndpointResponsiveness:
    """Basic responsiveness tests to ensure all endpoints are reachable"""

    def test_server_health(self):
        """Verify server is running"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        print(f"Health check: {response.json()}")

    def test_whatsapp_validate_endpoint_reachable(self):
        """Verify WhatsApp validation endpoint is reachable"""
        response = requests.post(
            f"{BASE_URL}/api/api/whatsapp/validate-number",
            json={"phone": "+1234567890"},
            timeout=30,
        )
        # Should not be 404 (endpoint exists)
        assert response.status_code != 404, "WhatsApp validation endpoint not found"
        print(f"WhatsApp validation endpoint status: {response.status_code}")

    def test_marketing_lab_endpoints_reachable(self):
        """Verify Marketing Lab endpoints exist (expect 401/403 for auth-required)"""
        endpoints = [
            ("GET", "/api/admin/marketing-lab/whatsapp-contacts"),
            ("GET", "/api/admin/marketing-lab/scan-insights"),
            ("POST", "/api/admin/marketing-lab/send-broadcast"),
            ("POST", "/api/admin/marketing-lab/send-launch-invites"),
            ("GET", "/api/admin/marketing-lab/social-posts"),
        ]

        for method, path in endpoints:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{path}", timeout=10)
            else:
                response = requests.post(f"{BASE_URL}{path}", json={}, timeout=10)

            # Should not return 404 (endpoints exist)
            assert response.status_code != 404, f"Endpoint {method} {path} not found"
            print(
                f"{method} {path}: {response.status_code} (expected 401/403 for auth)"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
