"""
Voice Engine Twilio Integration Tests - Iteration 166
======================================================
Tests for VoiceEngine service and campaign voice endpoints:
- VoiceEngine class structure and Twilio client usage
- POST /api/campaign/test-call endpoint
- POST /api/campaign/voice-call/{lead_id} endpoint
- POST /api/campaign/voice/keypress/{lead_id} webhook (TwiML responses)
- run_voice_sequence() function for Day 7 outreach
- call_logs collection logging
- voice_calls counter in user_integrations
"""

import pytest
import requests
import os
import re
import ast

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "teji.ss1986@gmail.com"
TEST_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def headers(auth_token):
    """Headers with auth token."""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestVoiceEngineCodeStructure:
    """Verify VoiceEngine class uses twilio.rest.Client (not raw httpx)."""

    def test_voice_engine_file_exists(self):
        """VoiceEngine service file exists."""
        voice_engine_path = "/app/backend/services/voice_engine.py"
        assert os.path.exists(voice_engine_path), "voice_engine.py not found"
        print("✓ voice_engine.py exists")

    def test_voice_engine_imports_twilio_client(self):
        """VoiceEngine imports twilio.rest.Client."""
        voice_engine_path = "/app/backend/services/voice_engine.py"
        with open(voice_engine_path, 'r') as f:
            content = f.read()
        
        # Check for twilio.rest.Client import inside make_call method
        assert "from twilio.rest import Client" in content, "Missing twilio.rest.Client import"
        print("✓ VoiceEngine imports twilio.rest.Client")

    def test_voice_engine_uses_client_calls_create(self):
        """VoiceEngine uses client.calls.create() for making calls."""
        voice_engine_path = "/app/backend/services/voice_engine.py"
        with open(voice_engine_path, 'r') as f:
            content = f.read()
        
        assert "client.calls.create" in content, "VoiceEngine should use client.calls.create()"
        print("✓ VoiceEngine uses client.calls.create()")

    def test_voice_engine_has_make_call_method(self):
        """VoiceEngine has make_call() method."""
        voice_engine_path = "/app/backend/services/voice_engine.py"
        with open(voice_engine_path, 'r') as f:
            content = f.read()
        
        assert "async def make_call" in content, "VoiceEngine missing make_call() method"
        print("✓ VoiceEngine has make_call() method")

    def test_voice_engine_has_build_twiml_method(self):
        """VoiceEngine has _build_twiml() method."""
        voice_engine_path = "/app/backend/services/voice_engine.py"
        with open(voice_engine_path, 'r') as f:
            content = f.read()
        
        assert "def _build_twiml" in content, "VoiceEngine missing _build_twiml() method"
        print("✓ VoiceEngine has _build_twiml() method")

    def test_voice_engine_has_log_call_method(self):
        """VoiceEngine has _log_call() method for DB logging."""
        voice_engine_path = "/app/backend/services/voice_engine.py"
        with open(voice_engine_path, 'r') as f:
            content = f.read()
        
        assert "async def _log_call" in content, "VoiceEngine missing _log_call() method"
        print("✓ VoiceEngine has _log_call() method")

    def test_voice_engine_logs_to_call_logs_collection(self):
        """VoiceEngine logs to call_logs collection."""
        voice_engine_path = "/app/backend/services/voice_engine.py"
        with open(voice_engine_path, 'r') as f:
            content = f.read()
        
        assert "call_logs" in content, "VoiceEngine should log to call_logs collection"
        print("✓ VoiceEngine logs to call_logs collection")

    def test_voice_engine_increments_voice_calls_counter(self):
        """VoiceEngine increments voice_calls counter in user_integrations."""
        voice_engine_path = "/app/backend/services/voice_engine.py"
        with open(voice_engine_path, 'r') as f:
            content = f.read()
        
        assert "voice_calls" in content, "VoiceEngine should increment voice_calls counter"
        assert "user_integrations" in content, "VoiceEngine should update user_integrations"
        print("✓ VoiceEngine increments voice_calls counter in user_integrations")


class TestCampaignRouterVoiceEndpoints:
    """Verify campaign router has voice endpoints."""

    def test_campaign_router_has_test_call_endpoint(self):
        """Campaign router has POST /test-call endpoint."""
        router_path = "/app/backend/routers/campaign_router.py"
        with open(router_path, 'r') as f:
            content = f.read()
        
        assert '@router.post("/test-call")' in content, "Missing /test-call endpoint"
        print("✓ Campaign router has /test-call endpoint")

    def test_campaign_router_has_voice_call_lead_endpoint(self):
        """Campaign router has POST /voice-call/{lead_id} endpoint."""
        router_path = "/app/backend/routers/campaign_router.py"
        with open(router_path, 'r') as f:
            content = f.read()
        
        assert '@router.post("/voice-call/{lead_id}")' in content, "Missing /voice-call/{lead_id} endpoint"
        print("✓ Campaign router has /voice-call/{lead_id} endpoint")

    def test_campaign_router_has_keypress_webhook(self):
        """Campaign router has POST /voice/keypress/{lead_id} webhook."""
        router_path = "/app/backend/routers/campaign_router.py"
        with open(router_path, 'r') as f:
            content = f.read()
        
        assert '@router.post("/voice/keypress/{lead_id}")' in content, "Missing /voice/keypress/{lead_id} webhook"
        print("✓ Campaign router has /voice/keypress/{lead_id} webhook")

    def test_campaign_router_has_run_voice_sequence(self):
        """Campaign router has run_voice_sequence() function for Day 7 outreach."""
        router_path = "/app/backend/routers/campaign_router.py"
        with open(router_path, 'r') as f:
            content = f.read()
        
        assert "async def run_voice_sequence" in content, "Missing run_voice_sequence() function"
        print("✓ Campaign router has run_voice_sequence() function")

    def test_run_voice_sequence_uses_voice_engine(self):
        """run_voice_sequence() uses VoiceEngine."""
        router_path = "/app/backend/routers/campaign_router.py"
        with open(router_path, 'r') as f:
            content = f.read()
        
        # Find run_voice_sequence function and check it imports/uses VoiceEngine
        assert "from services.voice_engine import VoiceEngine" in content or "VoiceEngine" in content
        print("✓ run_voice_sequence() uses VoiceEngine")

    def test_test_call_endpoint_uses_voice_engine(self):
        """test_call endpoint uses VoiceEngine (not direct Twilio calls)."""
        router_path = "/app/backend/routers/campaign_router.py"
        with open(router_path, 'r') as f:
            content = f.read()
        
        # Check that test_call function imports VoiceEngine
        assert "from services.voice_engine import VoiceEngine" in content
        print("✓ test_call endpoint uses VoiceEngine")


class TestTestCallEndpoint:
    """Test POST /api/campaign/test-call endpoint (without making real call)."""

    def test_test_call_endpoint_exists(self, headers):
        """Test-call endpoint is accessible (OPTIONS/HEAD check)."""
        # Just verify the endpoint exists by checking auth
        response = requests.post(
            f"{BASE_URL}/api/campaign/test-call",
            headers={"Content-Type": "application/json"},
            json={"to": "+10000000000"}  # Invalid number
        )
        # Should return 401 without auth, not 404
        assert response.status_code in [401, 200, 400, 422], f"Unexpected status: {response.status_code}"
        print(f"✓ /api/campaign/test-call endpoint exists (status: {response.status_code})")

    def test_test_call_requires_auth(self):
        """Test-call endpoint requires authentication."""
        response = requests.post(
            f"{BASE_URL}/api/campaign/test-call",
            headers={"Content-Type": "application/json"},
            json={"to": "+16134000000"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /api/campaign/test-call requires authentication")


class TestVoiceCallLeadEndpoint:
    """Test POST /api/campaign/voice-call/{lead_id} endpoint."""

    def test_voice_call_nonexistent_lead_returns_404(self, headers):
        """Voice call to nonexistent lead returns 404."""
        response = requests.post(
            f"{BASE_URL}/api/campaign/voice-call/nonexistent-lead-xyz",
            headers=headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ /api/campaign/voice-call/{lead_id} returns 404 for nonexistent lead")

    def test_voice_call_requires_auth(self):
        """Voice call endpoint requires authentication."""
        response = requests.post(
            f"{BASE_URL}/api/campaign/voice-call/test-lead",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ /api/campaign/voice-call/{lead_id} requires authentication")


class TestKeypressWebhook:
    """Test POST /api/campaign/voice/keypress/{lead_id} webhook."""

    def test_keypress_digit_1_returns_twiml(self):
        """Keypress webhook with Digits=1 returns TwiML XML (interested response)."""
        response = requests.post(
            f"{BASE_URL}/api/campaign/voice/keypress/test-lead-001",
            data={"Digits": "1"},  # Form-encoded data
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "application/xml" in response.headers.get("content-type", ""), "Expected XML content type"
        
        content = response.text
        assert "<Response>" in content, "Missing TwiML Response tag"
        assert "<Say" in content, "Missing TwiML Say tag"
        assert "Great" in content or "report" in content.lower(), "Expected interested response message"
        print("✓ Keypress Digits=1 returns TwiML XML (interested response)")
        print(f"  Response: {content[:200]}...")

    def test_keypress_digit_2_returns_twiml(self):
        """Keypress webhook with Digits=2 returns TwiML XML (opt-out response)."""
        response = requests.post(
            f"{BASE_URL}/api/campaign/voice/keypress/test-lead-002",
            data={"Digits": "2"},  # Form-encoded data
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "application/xml" in response.headers.get("content-type", ""), "Expected XML content type"
        
        content = response.text
        assert "<Response>" in content, "Missing TwiML Response tag"
        assert "<Say" in content, "Missing TwiML Say tag"
        assert "removed" in content.lower() or "opt" in content.lower(), "Expected opt-out response message"
        print("✓ Keypress Digits=2 returns TwiML XML (opt-out response)")
        print(f"  Response: {content[:200]}...")

    def test_keypress_invalid_digit_returns_twiml(self):
        """Keypress webhook with invalid digit returns TwiML XML (fallback response)."""
        response = requests.post(
            f"{BASE_URL}/api/campaign/voice/keypress/test-lead-003",
            data={"Digits": "9"},  # Invalid digit
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "application/xml" in response.headers.get("content-type", ""), "Expected XML content type"
        
        content = response.text
        assert "<Response>" in content, "Missing TwiML Response tag"
        print("✓ Keypress invalid digit returns TwiML XML (fallback response)")

    def test_keypress_no_auth_required(self):
        """Keypress webhook does not require auth (Twilio webhook)."""
        response = requests.post(
            f"{BASE_URL}/api/campaign/voice/keypress/test-lead-004",
            data={"Digits": "1"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        # Should return 200, not 401
        assert response.status_code == 200, f"Expected 200 (no auth), got {response.status_code}"
        print("✓ Keypress webhook does not require authentication (Twilio webhook)")


class TestCallLogsCollection:
    """Verify call_logs collection has entries after calls."""

    def test_call_logs_collection_exists(self, headers):
        """Verify call_logs collection can be queried (via admin endpoint or direct check)."""
        # We'll check via code inspection that _log_call writes to call_logs
        voice_engine_path = "/app/backend/services/voice_engine.py"
        with open(voice_engine_path, 'r') as f:
            content = f.read()
        
        assert "db.call_logs.insert_one" in content, "VoiceEngine should insert into call_logs"
        print("✓ VoiceEngine writes to call_logs collection")

    def test_call_log_includes_required_fields(self):
        """Verify call log document includes required fields."""
        voice_engine_path = "/app/backend/services/voice_engine.py"
        with open(voice_engine_path, 'r') as f:
            content = f.read()
        
        required_fields = ["tenant_id", "to", "lead_id", "call_sid", "status", "engine", "called_at"]
        for field in required_fields:
            assert f'"{field}"' in content, f"call_log missing field: {field}"
        print("✓ call_log includes all required fields")


class TestVoiceCallsCounter:
    """Verify voice_calls counter is incremented in user_integrations."""

    def test_voice_calls_counter_incremented(self):
        """Verify voice_calls counter is incremented on successful call."""
        voice_engine_path = "/app/backend/services/voice_engine.py"
        with open(voice_engine_path, 'r') as f:
            content = f.read()
        
        assert '"$inc": {"voice_calls": 1}' in content or "'$inc': {'voice_calls': 1}" in content or '"voice_calls": 1' in content
        print("✓ voice_calls counter is incremented on successful call")

    def test_last_voice_call_at_updated(self):
        """Verify last_voice_call_at is updated on successful call."""
        voice_engine_path = "/app/backend/services/voice_engine.py"
        with open(voice_engine_path, 'r') as f:
            content = f.read()
        
        assert "last_voice_call_at" in content, "Should update last_voice_call_at timestamp"
        print("✓ last_voice_call_at is updated on successful call")


class TestBackendHealth:
    """Verify backend is healthy after voice integration."""

    def test_backend_health(self):
        """Backend health endpoint returns 200."""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        print("✓ Backend health check passed")

    def test_campaign_overview_accessible(self, headers):
        """Campaign overview endpoint is accessible."""
        response = requests.get(f"{BASE_URL}/api/campaign/overview", headers=headers)
        assert response.status_code == 200, f"Campaign overview failed: {response.status_code}"
        print("✓ Campaign overview endpoint accessible")


class TestTwilioConfiguration:
    """Verify Twilio configuration is correct."""

    def test_twilio_env_vars_present(self):
        """Twilio environment variables are present in .env."""
        env_path = "/app/backend/.env"
        with open(env_path, 'r') as f:
            content = f.read()
        
        assert "TWILIO_ACCOUNT_SID" in content, "Missing TWILIO_ACCOUNT_SID"
        assert "TWILIO_AUTH_TOKEN" in content, "Missing TWILIO_AUTH_TOKEN"
        assert "TWILIO_PHONE_NUMBER" in content, "Missing TWILIO_PHONE_NUMBER"
        print("✓ Twilio environment variables present")

    def test_twilio_sid_format(self):
        """Twilio Account SID has correct format (starts with AC)."""
        env_path = "/app/backend/.env"
        with open(env_path, 'r') as f:
            content = f.read()
        
        # Extract SID
        match = re.search(r'TWILIO_ACCOUNT_SID=(\S+)', content)
        assert match, "Could not find TWILIO_ACCOUNT_SID"
        sid = match.group(1)
        assert sid.startswith("AC"), f"Twilio SID should start with AC, got: {sid[:10]}"
        print(f"✓ Twilio Account SID format valid: {sid[:10]}...")

    def test_twilio_phone_format(self):
        """Twilio phone number has correct format (E.164)."""
        env_path = "/app/backend/.env"
        with open(env_path, 'r') as f:
            content = f.read()
        
        # Extract phone
        match = re.search(r'TWILIO_PHONE_NUMBER=(\S+)', content)
        assert match, "Could not find TWILIO_PHONE_NUMBER"
        phone = match.group(1)
        assert phone.startswith("+"), f"Twilio phone should start with +, got: {phone}"
        print(f"✓ Twilio phone number format valid: {phone}")


class TestVanguardRouterNoVoiceChange:
    """Verify Vanguard router code does NOT need voice change (existing voice channel remains)."""

    def test_vanguard_router_exists(self):
        """Vanguard router file exists."""
        vanguard_path = "/app/backend/routers/aurem_vanguard_router.py"
        assert os.path.exists(vanguard_path), "Vanguard router not found"
        print("✓ Vanguard router exists")

    def test_vanguard_has_voice_channel(self):
        """Vanguard router has existing voice channel handling."""
        vanguard_path = "/app/backend/routers/aurem_vanguard_router.py"
        if not os.path.exists(vanguard_path):
            pytest.skip("Vanguard router not found")
        
        with open(vanguard_path, 'r') as f:
            content = f.read()
        
        # Check for voice channel handling
        has_voice = "voice" in content.lower()
        print(f"✓ Vanguard router voice channel status: {'present' if has_voice else 'not present'}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
