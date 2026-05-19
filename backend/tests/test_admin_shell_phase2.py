"""
AUREM AdminShell Phase 2 Backend Tests
=======================================
Tests for:
- Admin login with founder credentials
- 2FA endpoints (status, setup)
- Agent board endpoints (rollup, rates)

Iteration 289.1
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from /app/memory/test_credentials.md
FOUNDER_EMAIL = "teji.ss1986@gmail.com"
FOUNDER_PASSWORD = "<REDACTED>"


class TestAdminAuth:
    """Admin authentication endpoint tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin JWT token via login"""
        response = requests.post(
            f"{BASE_URL}/api/auth/admin/login",
            json={"email": FOUNDER_EMAIL, "password": FOUNDER_PASSWORD}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("token")
        pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
    
    def test_admin_login_success(self):
        """Test admin login returns 8h JWT + refresh_token + totp_enabled flag"""
        response = requests.post(
            f"{BASE_URL}/api/auth/admin/login",
            json={"email": FOUNDER_EMAIL, "password": FOUNDER_PASSWORD}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "token" in data, "Response should contain 'token'"
        assert "user" in data, "Response should contain 'user'"
        
        user = data["user"]
        assert user.get("email") == FOUNDER_EMAIL
        assert user.get("is_admin") == True
        assert user.get("is_super_admin") == True
        assert "totp_enabled" in user, "Response should contain 'totp_enabled' flag"
        assert "refresh_token" in user, "Response should contain 'refresh_token'"
        assert "expires_in" in user, "Response should contain 'expires_in'"
        
        # Verify 8h expiry (28800 seconds)
        assert user["expires_in"] == 28800, f"Expected 8h (28800s) expiry, got {user['expires_in']}"
        
        print(f"✓ Admin login successful - totp_enabled: {user.get('totp_enabled')}")
    
    def test_admin_login_invalid_credentials(self):
        """Test admin login with wrong password"""
        response = requests.post(
            f"{BASE_URL}/api/auth/admin/login",
            json={"email": FOUNDER_EMAIL, "password": "WrongPassword123"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid credentials correctly rejected")
    
    def test_admin_login_non_admin_user(self):
        """Test admin login with non-admin email"""
        response = requests.post(
            f"{BASE_URL}/api/auth/admin/login",
            json={"email": "futuristic_test@aurem-preview.com", "password": "FutureTest123!"}
        )
        # Should be 403 (not admin) or 401 (invalid)
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Non-admin user correctly rejected from admin login")


class TestAdmin2FA:
    """Admin 2FA endpoint tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin JWT token via login"""
        response = requests.post(
            f"{BASE_URL}/api/auth/admin/login",
            json={"email": FOUNDER_EMAIL, "password": FOUNDER_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"Admin login failed: {response.status_code}")
    
    def test_2fa_status_endpoint(self, admin_token):
        """Test /api/auth/admin/2fa/status returns totp_enabled flag"""
        response = requests.get(
            f"{BASE_URL}/api/auth/admin/2fa/status",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "totp_enabled" in data, "Response should contain 'totp_enabled'"
        print(f"✓ 2FA status endpoint works - totp_enabled: {data['totp_enabled']}")
    
    def test_2fa_status_unauthorized(self):
        """Test 2FA status without auth token"""
        response = requests.get(f"{BASE_URL}/api/auth/admin/2fa/status")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ 2FA status correctly requires auth")
    
    def test_2fa_setup_endpoint(self, admin_token):
        """Test /api/auth/admin/2fa/setup returns QR and secret (but don't enable)"""
        response = requests.post(
            f"{BASE_URL}/api/auth/admin/2fa/setup",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "secret" in data, "Response should contain 'secret'"
        assert "otpauth_uri" in data, "Response should contain 'otpauth_uri'"
        assert "qr_data_url" in data, "Response should contain 'qr_data_url'"
        
        # Verify QR is a data URL
        assert data["qr_data_url"].startswith("data:image/"), "QR should be a data URL"
        print("✓ 2FA setup endpoint returns QR and secret")


class TestAgentBoard:
    """Agent Board (Sovereign Boardroom) endpoint tests"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin JWT token via login"""
        response = requests.post(
            f"{BASE_URL}/api/auth/admin/login",
            json={"email": FOUNDER_EMAIL, "password": FOUNDER_PASSWORD}
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"Admin login failed: {response.status_code}")
    
    def test_rollup_endpoint(self, admin_token):
        """Test /api/agents/board/rollup returns gross_burn_usd, realized_revenue_usd, board, firing_line"""
        response = requests.get(
            f"{BASE_URL}/api/agents/board/rollup?days=1",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify required fields
        assert "gross_burn_usd" in data, "Response should contain 'gross_burn_usd'"
        assert "realized_revenue_usd" in data, "Response should contain 'realized_revenue_usd'"
        assert "board" in data, "Response should contain 'board'"
        assert "firing_line" in data, "Response should contain 'firing_line'"
        
        # Verify types
        assert isinstance(data["gross_burn_usd"], (int, float)), "gross_burn_usd should be numeric"
        assert isinstance(data["realized_revenue_usd"], (int, float)), "realized_revenue_usd should be numeric"
        assert isinstance(data["board"], list), "board should be a list"
        assert isinstance(data["firing_line"], list), "firing_line should be a list"
        
        print(f"✓ Rollup endpoint works - burn: ${data['gross_burn_usd']:.2f}, realized: ${data['realized_revenue_usd']:.2f}")
    
    def test_rollup_unauthorized(self):
        """Test rollup without auth token"""
        response = requests.get(f"{BASE_URL}/api/agents/board/rollup?days=1")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Rollup correctly requires auth")
    
    def test_rates_endpoint(self, admin_token):
        """Test /api/agents/board/rates returns rate card with ≥10 rate keys"""
        response = requests.get(
            f"{BASE_URL}/api/agents/board/rates",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Rates should be a dict with rate keys
        assert isinstance(data, dict), "Rates should be a dict"
        
        # Count rate keys
        rate_count = len(data)
        assert rate_count >= 10, f"Expected ≥10 rate keys, got {rate_count}"
        
        # Verify rate structure (each should have key, rate, label, unit)
        for key, rate_obj in data.items():
            assert "rate" in rate_obj, f"Rate {key} should have 'rate' field"
            assert isinstance(rate_obj["rate"], (int, float)), f"Rate {key} should be numeric"
        
        print(f"✓ Rates endpoint works - {rate_count} rate keys found")
    
    def test_rates_unauthorized(self):
        """Test rates without auth token"""
        response = requests.get(f"{BASE_URL}/api/agents/board/rates")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Rates correctly requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
