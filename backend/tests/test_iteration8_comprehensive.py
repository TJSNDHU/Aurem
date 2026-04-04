"""
Comprehensive Backend API Tests for AUREM Platform - Iteration 8
Tests: Authentication, Leads API, Admin Cache, Health endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthEndpoints:
    """Health check endpoint tests"""
    
    def test_health_endpoint(self):
        """Test /api/health returns 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print(f"✓ Health endpoint: {response.status_code}")
    
    def test_health_response_structure(self):
        """Test health response has expected fields"""
        response = requests.get(f"{BASE_URL}/api/health")
        data = response.json()
        assert "status" in data or "healthy" in str(data).lower()
        print(f"✓ Health response: {data}")


class TestAuthentication:
    """Authentication endpoint tests"""
    
    def test_login_success(self):
        """Test successful login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/platform/auth/login",
            json={"email": "teji.ss1986@gmail.com", "password": "Admin123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "email" in data
        assert data["email"] == "teji.ss1986@gmail.com"
        print(f"✓ Login success: token received, email={data['email']}")
    
    def test_login_returns_user_info(self):
        """Test login returns user details"""
        response = requests.post(
            f"{BASE_URL}/api/platform/auth/login",
            json={"email": "teji.ss1986@gmail.com", "password": "Admin123"}
        )
        data = response.json()
        assert "tier" in data
        assert "role" in data
        print(f"✓ User info: tier={data.get('tier')}, role={data.get('role')}")
    
    def test_login_invalid_credentials(self):
        """Test login fails with invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/platform/auth/login",
            json={"email": "invalid@test.com", "password": "wrongpass"}
        )
        # Should return 401 or 400 for invalid credentials
        assert response.status_code in [400, 401, 403]
        print(f"✓ Invalid login rejected: {response.status_code}")


class TestLeadsAPI:
    """Leads Dashboard API tests - Verifies 307 redirect fix"""
    
    def test_leads_endpoint_no_redirect(self):
        """Test /api/leads returns 200 (not 307 redirect)"""
        response = requests.get(
            f"{BASE_URL}/api/leads",
            params={"tenant_id": "test_tenant"},
            allow_redirects=False  # Don't follow redirects
        )
        # Should be 200, NOT 307
        assert response.status_code == 200, f"Expected 200, got {response.status_code} (307 redirect bug not fixed)"
        print(f"✓ Leads endpoint: {response.status_code} (no redirect)")
    
    def test_leads_response_structure(self):
        """Test leads response has expected structure"""
        response = requests.get(
            f"{BASE_URL}/api/leads",
            params={"tenant_id": "test_tenant"}
        )
        data = response.json()
        assert "success" in data
        assert "leads" in data
        assert isinstance(data["leads"], list)
        print(f"✓ Leads response: success={data['success']}, count={len(data['leads'])}")
    
    def test_leads_stats_endpoint(self):
        """Test /api/leads/stats returns stats"""
        response = requests.get(
            f"{BASE_URL}/api/leads/stats",
            params={"tenant_id": "test_tenant"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "stats" in data
        stats = data["stats"]
        assert "total_leads" in stats
        assert "conversion_rate" in stats
        print(f"✓ Leads stats: total={stats['total_leads']}, rate={stats['conversion_rate']}")


class TestAdminCacheAPI:
    """Admin Cache Clear endpoint tests"""
    
    def test_cache_clear_with_admin_key(self):
        """Test /api/admin/cache/clear works with valid admin key"""
        response = requests.post(
            f"{BASE_URL}/api/admin/cache/clear",
            headers={"X-Admin-Key": "aurem_admin_2024_secure"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert data["success"] == True
        print(f"✓ Cache clear: success={data['success']}")
    
    def test_cache_clear_without_admin_key(self):
        """Test /api/admin/cache/clear fails without admin key"""
        response = requests.post(f"{BASE_URL}/api/admin/cache/clear")
        # Should return 401 or 403 without admin key
        assert response.status_code in [401, 403]
        print(f"✓ Cache clear without key rejected: {response.status_code}")
    
    def test_cache_clear_with_invalid_key(self):
        """Test /api/admin/cache/clear fails with invalid admin key"""
        response = requests.post(
            f"{BASE_URL}/api/admin/cache/clear",
            headers={"X-Admin-Key": "invalid_key"}
        )
        # Should return 401 or 403 with invalid key
        assert response.status_code in [401, 403]
        print(f"✓ Cache clear with invalid key rejected: {response.status_code}")


class TestAUREMEndpoints:
    """AUREM AI Platform specific endpoints"""
    
    def test_aurem_metrics(self):
        """Test /api/aurem/metrics endpoint"""
        response = requests.get(f"{BASE_URL}/api/aurem/metrics")
        # May require auth, so accept 200 or 401
        assert response.status_code in [200, 401, 403]
        if response.status_code == 200:
            print(f"✓ AUREM metrics: {response.json()}")
        else:
            print(f"✓ AUREM metrics requires auth: {response.status_code}")
    
    def test_aurem_agents_status(self):
        """Test /api/aurem/agents/status endpoint"""
        response = requests.get(f"{BASE_URL}/api/aurem/agents/status")
        assert response.status_code in [200, 401, 403]
        if response.status_code == 200:
            print(f"✓ Agents status: {response.json()}")
        else:
            print(f"✓ Agents status requires auth: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
