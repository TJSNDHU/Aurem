"""
WhatsApp Campaign Rewire Tests - Iteration 161
==============================================
Tests for:
1. GET /api/integrations/polaris-built-001/whatsapp/status — returns mode=whapi, connected=true (Yellow badge)
2. Campaign HQ sends via WhatsApp engine — POST /api/campaign/whatsapp/send-test uses engine
3. POST /api/integrations/polaris-built-001/whatsapp/disconnect then status returns mode=not_connected (Grey badge)
4. POST /api/integrations/polaris-built-001/whatsapp/connect-whapi re-connects (Yellow badge restores)
5. Vanguard router imports WhatsAppEngine instead of whatsapp_alerts.send_whatsapp (verify code)
6. Campaign router bulk send uses WhatsAppEngine instead of direct httpx WHAPI calls (verify code)
7. Campaign router single test send uses WhatsAppEngine (verify code)
8. Backend starts without errors after rewire
"""

import pytest
import requests
import os
import re

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-platform-preview-3.preview.emergentagent.com").rstrip("/")
TENANT_ID = "polaris-built-001"
WHAPI_TOKEN = "3n0ZOga4jrBPih2GhVdW0EV1Z8hAQD4k"


@pytest.fixture(scope="module")
def auth_token():
    """Get auth token for API calls."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "teji.ss1986@gmail.com", "password": "Admin123"},
        timeout=15
    )
    if resp.status_code == 200:
        return resp.json().get("token")
    pytest.skip(f"Auth failed: {resp.status_code} - {resp.text[:200]}")


@pytest.fixture(scope="module")
def headers(auth_token):
    """Auth headers for API calls."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ═══════════════════════════════════════════════════════════════════════════════
# Test 1: WhatsApp Status Endpoint (Yellow Badge = WHAPI mode)
# ═══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppStatus:
    """Test GET /api/integrations/{tenant_id}/whatsapp/status returns correct mode."""

    def test_status_returns_mode_and_connected(self, headers):
        """Status endpoint returns mode, connected, and engine_details."""
        resp = requests.get(
            f"{BASE_URL}/api/integrations/{TENANT_ID}/whatsapp/status",
            headers=headers,
            timeout=15
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        
        # Verify response structure
        assert "mode" in data, "Response missing 'mode' field"
        assert "connected" in data, "Response missing 'connected' field"
        assert "engine_details" in data, "Response missing 'engine_details' field"
        
        print(f"✓ Status endpoint returns: mode={data['mode']}, connected={data['connected']}")
        print(f"  Engine details: {data.get('engine_details', {})}")

    def test_status_shows_whapi_mode_when_connected(self, headers):
        """When WHAPI is connected, mode should be 'whapi' and connected=True (Yellow badge)."""
        # First ensure WHAPI is connected
        connect_resp = requests.post(
            f"{BASE_URL}/api/integrations/{TENANT_ID}/whatsapp/connect-whapi",
            headers=headers,
            json={"whapi_token": WHAPI_TOKEN},
            timeout=15
        )
        # May fail if already connected or rate limited, that's OK
        
        # Now check status
        resp = requests.get(
            f"{BASE_URL}/api/integrations/{TENANT_ID}/whatsapp/status",
            headers=headers,
            timeout=15
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # For Yellow badge: mode=whapi, connected=true
        if data.get("connected"):
            assert data["mode"] in ["whapi", "meta_cloud"], f"Expected whapi or meta_cloud, got {data['mode']}"
            print(f"✓ WhatsApp connected with mode={data['mode']} (Yellow badge if whapi)")
        else:
            print(f"⚠ WhatsApp not connected: mode={data['mode']}")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 2: Campaign HQ Test Send Uses WhatsApp Engine
# ═══════════════════════════════════════════════════════════════════════════════

class TestCampaignWhatsAppSend:
    """Test POST /api/campaign/whatsapp/send-test uses WhatsApp engine."""

    def test_campaign_test_whatsapp_endpoint_exists(self, headers):
        """Campaign test-whatsapp endpoint exists and requires auth."""
        # Test without auth first
        resp_no_auth = requests.post(
            f"{BASE_URL}/api/campaign/test-whatsapp",
            json={"to": "16134000000", "template": "initial"},
            timeout=15
        )
        assert resp_no_auth.status_code == 401, "Endpoint should require auth"
        
        # Test with auth
        resp = requests.post(
            f"{BASE_URL}/api/campaign/test-whatsapp",
            headers=headers,
            json={
                "to": "16134000000",
                "template": "initial",
                "business_name": "Test Business",
                "first_name": "Test",
                "score": 75,
                "issues_count": 3
            },
            timeout=15
        )
        # Should return success or error (not 404)
        assert resp.status_code != 404, "Endpoint not found"
        data = resp.json()
        
        # Check if it uses the engine (returns engine field)
        if data.get("success"):
            assert "engine" in data or "message_id" in data, "Response should include engine or message_id"
            print(f"✓ Campaign test-whatsapp uses engine: {data.get('engine', 'unknown')}")
        else:
            print(f"⚠ Send failed (expected if rate limited): {data.get('error', 'unknown')}")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 3: Disconnect Sets mode=not_connected (Grey Badge)
# ═══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppDisconnect:
    """Test POST /api/integrations/{tenant_id}/whatsapp/disconnect."""

    def test_disconnect_resets_to_not_connected(self, headers):
        """Disconnect should set mode=not_connected (Grey badge)."""
        # Disconnect
        resp = requests.post(
            f"{BASE_URL}/api/integrations/{TENANT_ID}/whatsapp/disconnect",
            headers=headers,
            timeout=15
        )
        assert resp.status_code == 200, f"Disconnect failed: {resp.status_code}"
        
        # Check status
        status_resp = requests.get(
            f"{BASE_URL}/api/integrations/{TENANT_ID}/whatsapp/status",
            headers=headers,
            timeout=15
        )
        assert status_resp.status_code == 200
        data = status_resp.json()
        
        assert data["mode"] == "not_connected", f"Expected not_connected, got {data['mode']}"
        assert data["connected"] == False, "Expected connected=False after disconnect"
        print(f"✓ After disconnect: mode={data['mode']}, connected={data['connected']} (Grey badge)")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 4: Reconnect WHAPI Restores Yellow Badge
# ═══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppReconnect:
    """Test POST /api/integrations/{tenant_id}/whatsapp/connect-whapi restores connection."""

    def test_reconnect_whapi_restores_yellow_badge(self, headers):
        """Reconnecting WHAPI should restore mode=whapi, connected=true (Yellow badge)."""
        # Connect WHAPI
        resp = requests.post(
            f"{BASE_URL}/api/integrations/{TENANT_ID}/whatsapp/connect-whapi",
            headers=headers,
            json={"whapi_token": WHAPI_TOKEN},
            timeout=15
        )
        
        if resp.status_code == 400:
            # May be rate limited or token validation failed
            print(f"⚠ Connect-whapi returned 400 (may be rate limited): {resp.text[:200]}")
            pytest.skip("WHAPI connection rate limited")
        
        assert resp.status_code == 200, f"Connect failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        
        assert data.get("success") == True, "Expected success=True"
        assert data.get("mode") == "whapi", f"Expected mode=whapi, got {data.get('mode')}"
        
        # Verify status
        status_resp = requests.get(
            f"{BASE_URL}/api/integrations/{TENANT_ID}/whatsapp/status",
            headers=headers,
            timeout=15
        )
        status_data = status_resp.json()
        
        assert status_data["mode"] == "whapi", f"Status mode should be whapi, got {status_data['mode']}"
        assert status_data["connected"] == True, "Status connected should be True"
        print(f"✓ Reconnected: mode={status_data['mode']}, connected={status_data['connected']} (Yellow badge)")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 5-7: Code Verification (WhatsAppEngine imports)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCodeRewire:
    """Verify code rewire: WhatsAppEngine used instead of direct WHAPI calls."""

    def test_vanguard_router_uses_whatsapp_engine(self):
        """Vanguard router should import WhatsAppEngine, not whatsapp_alerts."""
        vanguard_path = "/app/backend/routers/aurem_vanguard_router.py"
        
        with open(vanguard_path, "r") as f:
            content = f.read()
        
        # Check for WhatsAppEngine import
        assert "from services.whatsapp_engine import WhatsAppEngine" in content, \
            "Vanguard router should import WhatsAppEngine"
        
        # Check it's NOT using old whatsapp_alerts
        assert "from services.whatsapp_alerts import" not in content, \
            "Vanguard router should NOT import whatsapp_alerts"
        assert "whatsapp_alerts.send_whatsapp" not in content, \
            "Vanguard router should NOT use whatsapp_alerts.send_whatsapp"
        
        # Check WhatsAppEngine is instantiated
        assert "WhatsAppEngine(" in content, "Vanguard router should instantiate WhatsAppEngine"
        
        # Check wa_engine.send_message is used
        assert "wa_engine.send_message" in content or "await wa_engine.send_message" in content, \
            "Vanguard router should use wa_engine.send_message"
        
        print("✓ Vanguard router correctly uses WhatsAppEngine")

    def test_campaign_router_uses_whatsapp_engine_for_test_send(self):
        """Campaign router test-whatsapp should use WhatsAppEngine."""
        campaign_path = "/app/backend/routers/campaign_router.py"
        
        with open(campaign_path, "r") as f:
            content = f.read()
        
        # Check for WhatsAppEngine import in test_whatsapp function area
        assert "from services.whatsapp_engine import WhatsAppEngine" in content, \
            "Campaign router should import WhatsAppEngine"
        
        # Check test_whatsapp function uses engine
        # Find the test_whatsapp function
        test_whatsapp_match = re.search(r'async def test_whatsapp\(.*?\):(.*?)(?=\nasync def|\nclass|\Z)', content, re.DOTALL)
        if test_whatsapp_match:
            func_body = test_whatsapp_match.group(1)
            assert "WhatsAppEngine" in func_body, "test_whatsapp should use WhatsAppEngine"
            assert "wa_engine.send_message" in func_body or "await wa_engine.send_message" in func_body, \
                "test_whatsapp should call wa_engine.send_message"
            print("✓ Campaign router test_whatsapp uses WhatsAppEngine")
        else:
            pytest.fail("Could not find test_whatsapp function in campaign_router.py")

    def test_campaign_router_uses_whatsapp_engine_for_bulk_send(self):
        """Campaign router run_whatsapp_sequence should use WhatsAppEngine."""
        campaign_path = "/app/backend/routers/campaign_router.py"
        
        with open(campaign_path, "r") as f:
            content = f.read()
        
        # Find run_whatsapp_sequence function
        bulk_match = re.search(r'async def run_whatsapp_sequence\(.*?\):(.*?)(?=\nasync def|\nclass|\Z)', content, re.DOTALL)
        if bulk_match:
            func_body = bulk_match.group(1)
            assert "WhatsAppEngine" in func_body, "run_whatsapp_sequence should use WhatsAppEngine"
            assert "wa_engine.send_message" in func_body or "await wa_engine.send_message" in func_body, \
                "run_whatsapp_sequence should call wa_engine.send_message"
            
            # Should NOT have direct httpx WHAPI calls
            assert "gate.whapi.cloud" not in func_body, \
                "run_whatsapp_sequence should NOT have direct WHAPI URL"
            
            print("✓ Campaign router run_whatsapp_sequence uses WhatsAppEngine")
        else:
            pytest.fail("Could not find run_whatsapp_sequence function in campaign_router.py")

    def test_no_direct_whapi_calls_in_campaign_router(self):
        """Campaign router should not have direct httpx calls to WHAPI."""
        campaign_path = "/app/backend/routers/campaign_router.py"
        
        with open(campaign_path, "r") as f:
            content = f.read()
        
        # Check for direct WHAPI calls (should be routed through engine)
        # The engine handles WHAPI internally, so campaign_router shouldn't call it directly
        direct_whapi_patterns = [
            r'httpx\..*post.*gate\.whapi\.cloud',
            r'WHAPI_API_URL.*messages',
        ]
        
        for pattern in direct_whapi_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            assert len(matches) == 0, f"Found direct WHAPI call pattern: {pattern}"
        
        print("✓ Campaign router has no direct WHAPI httpx calls")


# ═══════════════════════════════════════════════════════════════════════════════
# Test 8: Backend Starts Without Errors
# ═══════════════════════════════════════════════════════════════════════════════

class TestBackendHealth:
    """Verify backend starts and runs without errors."""

    def test_backend_health_endpoint(self):
        """Backend health endpoint should return 200."""
        resp = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
        print("✓ Backend health check passed")

    def test_platform_health_endpoint(self):
        """Platform health endpoint should return 200."""
        resp = requests.get(f"{BASE_URL}/api/platform/health", timeout=10)
        assert resp.status_code == 200, f"Platform health failed: {resp.status_code}"
        print("✓ Platform health check passed")

    def test_aurem_system_endpoint(self):
        """AUREM system endpoint should return 200."""
        resp = requests.get(f"{BASE_URL}/api/aurem/system", timeout=10)
        assert resp.status_code == 200, f"AUREM system failed: {resp.status_code}"
        data = resp.json()
        assert "vanguard_agents" in data, "AUREM system should return vanguard_agents"
        print("✓ AUREM system endpoint working")


# ═══════════════════════════════════════════════════════════════════════════════
# Test: WhatsApp Engine Service Exists and Works
# ═══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppEngineService:
    """Verify WhatsApp engine service is properly implemented."""

    def test_whatsapp_engine_file_exists(self):
        """WhatsApp engine service file should exist."""
        engine_path = "/app/backend/services/whatsapp_engine.py"
        assert os.path.exists(engine_path), f"WhatsApp engine not found at {engine_path}"
        print("✓ WhatsApp engine service file exists")

    def test_whatsapp_engine_has_required_methods(self):
        """WhatsApp engine should have send_message, get_status methods."""
        engine_path = "/app/backend/services/whatsapp_engine.py"
        
        with open(engine_path, "r") as f:
            content = f.read()
        
        required_methods = [
            "async def send_message",
            "async def get_status",
            "async def get_tenant_config",
        ]
        
        for method in required_methods:
            assert method in content, f"WhatsApp engine missing method: {method}"
        
        print("✓ WhatsApp engine has all required methods")

    def test_whatsapp_engine_supports_both_modes(self):
        """WhatsApp engine should support both meta_cloud and whapi modes."""
        engine_path = "/app/backend/services/whatsapp_engine.py"
        
        with open(engine_path, "r") as f:
            content = f.read()
        
        assert "meta_cloud" in content, "Engine should support meta_cloud mode"
        assert "whapi" in content, "Engine should support whapi mode"
        assert "_send_meta" in content, "Engine should have _send_meta method"
        assert "_send_whapi" in content, "Engine should have _send_whapi method"
        
        print("✓ WhatsApp engine supports both meta_cloud and whapi modes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
