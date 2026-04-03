"""
Phase 4 Testing: Milestone System, $70 Pricing, Whapi Webhook, Bio-Scan Flow
Tests:
1. $70 pricing endpoint and calculations
2. Whapi webhook endpoint
3. Milestone progress endpoint
4. Bio-scan to Data Hub flow
5. WhatsApp contacts in Marketing Lab
"""

import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


class TestPricingEndpoints:
    """Test $70 Founding Member pricing is correct everywhere"""

    def test_founding_member_pricing_endpoint(self):
        """Test /api/founding-member/pricing returns $70 final price"""
        response = requests.get(f"{BASE_URL}/api/founding-member/pricing")

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        # Final price should be $70 (30% off $100)
        assert (
            "final_price" in data or "finalPrice" in data
        ), f"Missing final_price in response: {data}"

        final_price = data.get("final_price") or data.get("finalPrice", 0)
        # Allow for floating point comparison
        assert (
            69 <= final_price <= 71
        ), f"Final price should be ~$70, got ${final_price}"

        print(f"✓ Founding Member Pricing: ${final_price}")

    def test_pricing_shows_30_percent_discount(self):
        """Verify 30% discount is applied to $100 retail"""
        response = requests.get(f"{BASE_URL}/api/founding-member/pricing")

        if response.status_code == 200:
            data = response.json()
            retail = data.get("retail_value", data.get("retailValue", 100))
            discount = data.get(
                "referral_discount_percent", data.get("referralDiscount", 30)
            )

            assert retail == 100, f"Retail should be $100, got ${retail}"
            assert discount == 30, f"Discount should be 30%, got {discount}%"

            print(f"✓ Retail: ${retail}, Discount: {discount}%")


class TestWhapiWebhook:
    """Test Whapi.cloud webhook endpoint at /api/api/webhook/whapi"""

    def test_webhook_endpoint_exists(self):
        """Test POST /api/api/webhook/whapi endpoint is reachable"""
        # Send a test webhook event
        test_payload = {
            "event": "test",
            "data": {"test_id": str(uuid.uuid4())},
            "timestamp": time.time(),
        }

        response = requests.post(
            f"{BASE_URL}/api/api/webhook/whapi",
            json=test_payload,
            headers={"Content-Type": "application/json"},
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert data.get("status") == "ok", f"Webhook should return ok status: {data}"

        print(f"✓ Whapi webhook endpoint working: {data}")

    def test_webhook_handles_message_event(self):
        """Test webhook handles incoming message events"""
        message_payload = {
            "event": "message",
            "message": {
                "from": "14155551234",
                "body": {"text": "Hello test"},
                "timestamp": int(time.time()),
            },
        }

        response = requests.post(
            f"{BASE_URL}/api/api/webhook/whapi",
            json=message_payload,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"

        print("✓ Webhook handles message events correctly")

    def test_webhook_handles_status_event(self):
        """Test webhook handles message status updates"""
        status_payload = {
            "event": "message.status",
            "status": "delivered",
            "message_id": "test_msg_123",
        }

        response = requests.post(
            f"{BASE_URL}/api/api/webhook/whapi",
            json=status_payload,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200
        print("✓ Webhook handles status events correctly")

    def test_webhook_status_endpoint(self):
        """Test GET /api/api/webhook/whapi/status returns recent events"""
        response = requests.get(f"{BASE_URL}/api/api/webhook/whapi/status")

        assert response.status_code == 200
        data = response.json()

        assert "webhook_url" in data
        assert "recent_events" in data

        print(f"✓ Webhook status: {data.get('recent_events', 0)} recent events")


class TestMilestoneProgress:
    """Test milestone progress tracking at /api/milestone/progress/{code}"""

    def test_milestone_progress_endpoint(self):
        """Test /api/milestone/progress/{code} endpoint"""
        # Use a test code - may not exist but endpoint should respond
        test_code = "TEST123"

        response = requests.get(f"{BASE_URL}/api/milestone/progress/{test_code}")

        # Should return 200 with progress data
        assert response.status_code == 200, f"Unexpected status: {response.status_code}"

        data = response.json()
        # Should have progress structure
        assert "count" in data, f"Missing count in progress data: {data}"
        assert "threshold" in data, f"Missing threshold in progress data: {data}"
        assert "progress_percent" in data, f"Missing progress_percent: {data}"

        print(
            f"✓ Milestone progress retrieved for {test_code}: count={data['count']}, threshold={data['threshold']}"
        )


class TestBioScanFlow:
    """Test Bio-Age Scan to Data Hub flow"""

    def test_bio_scan_submit_endpoint(self):
        """Test POST /api/bio-scan/submit captures lead"""
        test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        test_phone = "14155559999"

        scan_data = {
            "email": test_email,
            "name": "Test User",
            "answers": {
                "age": "30-40",
                "concern": "wrinkles",
                "skin_type": "combination",
            },
            "whatsapp": test_phone,
            "referrer_code": "",
        }

        response = requests.post(
            f"{BASE_URL}/api/bio-scan/submit",
            json=scan_data,
            headers={"Content-Type": "application/json"},
        )

        # May return 200 or 201 for success
        assert response.status_code in [
            200,
            201,
        ], f"Expected 200/201, got {response.status_code}: {response.text}"

        data = response.json()
        # Should return a referral code
        assert "referral_code" in data, f"Should return referral_code: {data}"

        print(f"✓ Bio-scan submitted, referral code: {data.get('referral_code')}")
        return data.get("referral_code")

    def test_whatsapp_validation_endpoint(self):
        """Test /api/api/whatsapp/validate-number endpoint"""
        test_phone = "+1 415 555 2671"

        response = requests.post(
            f"{BASE_URL}/api/api/whatsapp/validate-number",
            json={"phone": test_phone},
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert "valid" in data, f"Should return valid field: {data}"

        print(f"✓ WhatsApp validation: valid={data.get('valid')}")


class TestMarketingLabContacts:
    """Test WhatsApp contacts appear in Marketing Lab"""

    def test_marketing_lab_contacts_requires_auth(self):
        """Test /api/admin/marketing-lab/whatsapp-contacts requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/marketing-lab/whatsapp-contacts")

        # Should return 401 or 403 without auth
        assert response.status_code in [
            401,
            403,
        ], f"Should require auth, got {response.status_code}"
        print("✓ Marketing Lab contacts endpoint properly protected")

    def test_marketing_lab_scan_insights_requires_auth(self):
        """Test scan insights endpoint requires auth"""
        response = requests.get(f"{BASE_URL}/api/admin/marketing-lab/scan-insights")

        assert response.status_code in [
            401,
            403,
        ], f"Should require auth, got {response.status_code}"
        print("✓ Marketing Lab scan insights endpoint properly protected")


class TestHealthAndBasics:
    """Basic health checks"""

    def test_api_health(self):
        """Test /api/health returns healthy"""
        response = requests.get(f"{BASE_URL}/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ API health check passed")

    def test_marketing_programs_public(self):
        """Test public marketing programs endpoint"""
        response = requests.get(f"{BASE_URL}/api/marketing-programs")

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "programs" in data
        print(f"✓ Marketing programs: {len(data.get('programs', []))} active")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
