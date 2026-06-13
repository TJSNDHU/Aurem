"""
Test suite for AUREM iter 322as features:
- Public booking endpoints (401 without auth)
- Admin branding endpoints
- System overview new cards
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ai-platform-preview-3.preview.emergentagent.com')

# Test credentials
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")
CUSTOMER_EMAIL = "teji.ss1986+dogfood@gmail.com"
CUSTOMER_PASSWORD = os.environ.get("AUREM_CUSTOMER_PASSWORD", "")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("token")
    pytest.skip(f"Admin login failed: {response.status_code}")


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Headers with admin auth"""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestPublicBookingEndpoints:
    """Test public booking widget endpoints - should require sk_aurem_ Bearer auth"""
    
    def test_booking_types_no_auth_returns_401(self):
        """GET /api/public/booking/types without auth should return 401"""
        response = requests.get(f"{BASE_URL}/api/public/booking/types")
        assert response.status_code == 401
        assert "Missing or invalid Authorization" in response.json().get("detail", "")
    
    def test_booking_types_bad_key_returns_401(self):
        """GET /api/public/booking/types with invalid sk_aurem_ key should return 401"""
        response = requests.get(
            f"{BASE_URL}/api/public/booking/types",
            headers={"Authorization": "Bearer sk_aurem_live_invalid_key_12345"}
        )
        assert response.status_code == 401
        assert "not recognised" in response.json().get("detail", "").lower()
    
    def test_booking_availability_no_auth_returns_401(self):
        """GET /api/public/booking/availability without auth should return 401"""
        response = requests.get(
            f"{BASE_URL}/api/public/booking/availability",
            params={"service_type": "consultation", "date": "2026-06-01"}
        )
        assert response.status_code == 401
    
    def test_booking_book_no_auth_returns_401(self):
        """POST /api/public/booking/book without auth should return 401"""
        response = requests.post(
            f"{BASE_URL}/api/public/booking/book",
            json={
                "name": "Test User",
                "phone": "555-1234",
                "service_type": "consultation",
                "date": "2026-06-01",
                "slot": "10:00"
            }
        )
        assert response.status_code == 401


class TestAdminBrandingEndpoints:
    """Test admin branding (white-label) endpoints"""
    
    def test_get_branding_requires_auth(self):
        """GET /api/admin/branding/{bin_id} without auth should fail"""
        response = requests.get(f"{BASE_URL}/api/admin/branding/AURE-FNDR-001")
        assert response.status_code in [401, 403]
    
    def test_get_branding_with_admin_token(self, admin_headers):
        """GET /api/admin/branding/{bin_id} with admin token should return branding"""
        response = requests.get(
            f"{BASE_URL}/api/admin/branding/AURE-FNDR-001",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "branding" in data
        branding = data["branding"]
        # Verify branding structure
        assert "brand_name" in branding
        assert "primary_color" in branding
        assert "tenant_id" in branding
    
    def test_update_branding_requires_enterprise(self, admin_headers):
        """POST /api/admin/branding/{bin_id} should require Enterprise plan"""
        response = requests.post(
            f"{BASE_URL}/api/admin/branding/AURE-FNDR-001",
            headers=admin_headers,
            json={
                "brand_name": "Test Brand",
                "logo_url": "https://example.com/logo.png",
                "primary_color": "#D4AF37",
                "domain": ""
            }
        )
        # Should return 402 (Payment Required) for non-Enterprise plans
        # or 200 if the account has Enterprise
        assert response.status_code in [200, 402]
    
    def test_get_cname_instructions(self, admin_headers):
        """GET /api/admin/branding/{bin_id}/cname should return CNAME instructions"""
        response = requests.get(
            f"{BASE_URL}/api/admin/branding/AURE-FNDR-001/cname",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        assert "cname" in data
        cname = data["cname"]
        assert "instructions" in cname
        assert "status" in cname


class TestSystemOverviewStats:
    """Test system overview stats endpoint for new cards"""
    
    def test_system_overview_stats(self, admin_headers):
        """GET /api/admin/system-overview/stats should return platform stats"""
        response = requests.get(
            f"{BASE_URL}/api/admin/system-overview/stats",
            headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check platform section
        assert "platform" in data
        platform = data["platform"]
        assert "iteration" in platform
        # Iteration should contain 322as or higher
        iteration = platform.get("iteration", "")
        assert "322" in iteration, f"Expected iteration 322+, got {iteration}"
        
        # Check audit section exists
        assert "audit" in data


class TestHealthEndpoint:
    """Basic health check"""
    
    def test_health_endpoint(self):
        """GET /api/health should return ok"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
