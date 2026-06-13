"""
Iteration 198 - BIN Login System + Customer Portal Tests
=========================================================
Tests for:
- BIN Generator (format, is_bin detection)
- BIN Login (identifier field accepts BIN or email)
- BIN Auth endpoints (first-login, forgot-password, admin search, customer-context)
- Customer Portal endpoints (website, reviews, social, reports, billing, referrals)
"""

import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://ai-platform-preview-3.preview.emergentagent.com"

# Test credentials from test_credentials.md
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")
BIN_TEST_EMAIL = "testbin@aurem.live"
BIN_TEST_PASSWORD = "TempPass123!"
BIN_TEST_BIN = "RST-TOR-9K82"


class TestBINGenerator:
    """Test BIN format and detection"""
    
    def test_bin_format_regex(self):
        """BIN format should be 3-3-4 alphanumeric"""
        bin_regex = re.compile(r"^[A-Z]{3}-[A-Z]{3}-[A-Z0-9]{4}$", re.IGNORECASE)
        
        # Valid BINs
        assert bin_regex.match("RST-TOR-9K82")
        assert bin_regex.match("AUT-MSS-7K92")
        assert bin_regex.match("SAL-VAN-3M41")
        assert bin_regex.match("rst-tor-9k82")  # case insensitive
        
        # Invalid BINs
        assert not bin_regex.match("RST-TOR-9K8")  # too short
        assert not bin_regex.match("RST-TOR-9K823")  # too long
        assert not bin_regex.match("RSTT-TOR-9K82")  # first part too long
        assert not bin_regex.match("test@email.com")  # email
        assert not bin_regex.match("RST_TOR_9K82")  # wrong separator


class TestBINLogin:
    """Test login with BIN identifier"""
    
    def test_login_with_bin_identifier(self):
        """Login should accept BIN in identifier field"""
        response = requests.post(f"{BASE_URL}/api/platform/auth/login", json={
            "identifier": BIN_TEST_BIN,
            "password": BIN_TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["email"] == BIN_TEST_EMAIL
        assert data["role"] == "user"
    
    def test_login_with_email_identifier(self):
        """Login should accept email in identifier field"""
        response = requests.post(f"{BASE_URL}/api/platform/auth/login", json={
            "identifier": BIN_TEST_EMAIL,
            "password": BIN_TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["email"] == BIN_TEST_EMAIL
    
    def test_login_with_email_field(self):
        """Login should still accept email field (backward compat)"""
        response = requests.post(f"{BASE_URL}/api/platform/auth/login", json={
            "email": BIN_TEST_EMAIL,
            "password": BIN_TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
    
    def test_login_invalid_bin(self):
        """Login with invalid BIN should fail"""
        response = requests.post(f"{BASE_URL}/api/platform/auth/login", json={
            "identifier": "XXX-XXX-0000",
            "password": "wrongpass"
        })
        assert response.status_code == 401
    
    def test_login_admin_with_email(self):
        """Admin login should work with email"""
        response = requests.post(f"{BASE_URL}/api/platform/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"


@pytest.fixture(scope="module")
def bin_user_token():
    """Get token for BIN test user"""
    response = requests.post(f"{BASE_URL}/api/platform/auth/login", json={
        "identifier": BIN_TEST_BIN,
        "password": BIN_TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("BIN user login failed")


@pytest.fixture(scope="module")
def admin_token():
    """Get token for admin user"""
    response = requests.post(f"{BASE_URL}/api/platform/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json()["token"]
    pytest.skip("Admin login failed")


class TestBINAuthEndpoints:
    """Test /api/bin-auth/* endpoints"""
    
    def test_first_login_status(self, bin_user_token):
        """GET /api/bin-auth/first-login/status should return wizard state"""
        response = requests.get(
            f"{BASE_URL}/api/bin-auth/first-login/status",
            headers={"Authorization": f"Bearer {bin_user_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "must_set_password" in data
        assert "wizard_complete" in data
        assert "wizard_step" in data
        assert "business_id" in data
        assert data["business_id"] == BIN_TEST_BIN
    
    def test_first_login_status_no_auth(self):
        """GET /api/bin-auth/first-login/status without auth should fail"""
        response = requests.get(f"{BASE_URL}/api/bin-auth/first-login/status")
        assert response.status_code == 401
    
    def test_customer_context(self, bin_user_token):
        """GET /api/bin-auth/customer-context should return user context"""
        response = requests.get(
            f"{BASE_URL}/api/bin-auth/customer-context",
            headers={"Authorization": f"Bearer {bin_user_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["bin"] == BIN_TEST_BIN
        assert data["email"] == BIN_TEST_EMAIL
        assert "business_name" in data
        assert "industry" in data
        assert "city" in data
        assert "must_set_password" in data
        assert "wizard_complete" in data
    
    def test_forgot_password_valid_email(self):
        """POST /api/bin-auth/forgot-password with valid email"""
        response = requests.post(
            f"{BASE_URL}/api/bin-auth/forgot-password",
            json={"identifier": BIN_TEST_EMAIL}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "message" in data
    
    def test_forgot_password_valid_bin(self):
        """POST /api/bin-auth/forgot-password with valid BIN"""
        response = requests.post(
            f"{BASE_URL}/api/bin-auth/forgot-password",
            json={"identifier": BIN_TEST_BIN}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
    
    def test_forgot_password_nonexistent(self):
        """POST /api/bin-auth/forgot-password with nonexistent user (no leak)"""
        response = requests.post(
            f"{BASE_URL}/api/bin-auth/forgot-password",
            json={"identifier": "nonexistent@test.com"}
        )
        assert response.status_code == 200  # Should not leak user existence
        data = response.json()
        assert data["success"] == True
    
    def test_admin_search_requires_admin(self, bin_user_token):
        """GET /api/bin-auth/admin/search should require admin role"""
        response = requests.get(
            f"{BASE_URL}/api/bin-auth/admin/search?q=test",
            headers={"Authorization": f"Bearer {bin_user_token}"}
        )
        assert response.status_code == 403
    
    def test_admin_search_by_email(self, admin_token):
        """GET /api/bin-auth/admin/search by email fragment"""
        response = requests.get(
            f"{BASE_URL}/api/bin-auth/admin/search?q=teji",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "count" in data
        assert data["count"] >= 1
        # Should find admin user
        emails = [r["email"] for r in data["results"]]
        assert ADMIN_EMAIL in emails
    
    def test_admin_search_by_bin(self, admin_token):
        """GET /api/bin-auth/admin/search by BIN"""
        response = requests.get(
            f"{BASE_URL}/api/bin-auth/admin/search?q=RST-TOR",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        bins = [r.get("business_id", "") for r in data["results"]]
        assert BIN_TEST_BIN in bins


class TestCustomerPortalEndpoints:
    """Test /api/customer/* endpoints"""
    
    def test_customer_website_get(self, bin_user_token):
        """GET /api/customer/website should return site data"""
        response = requests.get(
            f"{BASE_URL}/api/customer/website",
            headers={"Authorization": f"Bearer {bin_user_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert "phone" in data
        assert "hours" in data
        assert "services" in data
    
    def test_customer_website_put(self, bin_user_token):
        """PUT /api/customer/website should update site data"""
        response = requests.put(
            f"{BASE_URL}/api/customer/website",
            headers={"Authorization": f"Bearer {bin_user_token}"},
            json={"tagline": "Test Tagline from pytest"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "updated_fields" in data
    
    def test_customer_reviews_get(self, bin_user_token):
        """GET /api/customer/reviews should return reviews + stats"""
        response = requests.get(
            f"{BASE_URL}/api/customer/reviews",
            headers={"Authorization": f"Bearer {bin_user_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "reviews" in data
        assert "stats" in data
        assert "total" in data["stats"]
        assert "avg_rating" in data["stats"]
    
    def test_customer_social_status(self, bin_user_token):
        """GET /api/customer/social/status should return Postiz status"""
        response = requests.get(
            f"{BASE_URL}/api/customer/social/status",
            headers={"Authorization": f"Bearer {bin_user_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "configured" in data
        assert "enabled" in data
        assert "accounts" in data
    
    def test_customer_social_toggle(self, bin_user_token):
        """POST /api/customer/social/toggle should toggle auto-posting"""
        response = requests.post(
            f"{BASE_URL}/api/customer/social/toggle",
            headers={"Authorization": f"Bearer {bin_user_token}"},
            json={"enabled": True}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["enabled"] == True
    
    def test_customer_reports_get(self, bin_user_token):
        """GET /api/customer/reports should return report list"""
        response = requests.get(
            f"{BASE_URL}/api/customer/reports",
            headers={"Authorization": f"Bearer {bin_user_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "reports" in data
        assert isinstance(data["reports"], list)
    
    def test_customer_reports_generate(self, bin_user_token):
        """POST /api/customer/reports/generate should queue report"""
        response = requests.post(
            f"{BASE_URL}/api/customer/reports/generate",
            headers={"Authorization": f"Bearer {bin_user_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "message" in data
    
    def test_customer_billing_get(self, bin_user_token):
        """GET /api/customer/billing should return plan + invoices"""
        response = requests.get(
            f"{BASE_URL}/api/customer/billing",
            headers={"Authorization": f"Bearer {bin_user_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "plan_name" in data
        assert "status" in data
        assert "invoices" in data
    
    def test_customer_referrals_get(self, bin_user_token):
        """GET /api/customer/referrals should return referral list"""
        response = requests.get(
            f"{BASE_URL}/api/customer/referrals",
            headers={"Authorization": f"Bearer {bin_user_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "referrals" in data
        assert "count_successful" in data
        assert "rewards_earned" in data
        assert "your_bin" in data
        assert data["your_bin"] == BIN_TEST_BIN
    
    def test_customer_referrals_track(self):
        """POST /api/customer/referrals/track should track referral (public)"""
        response = requests.post(
            f"{BASE_URL}/api/customer/referrals/track",
            json={
                "referrer_bin": BIN_TEST_BIN,
                "referee_email": "pytest_referee@test.com"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
    
    def test_customer_health(self):
        """GET /api/customer/health should return ok"""
        response = requests.get(f"{BASE_URL}/api/customer/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "customer-portal"
    
    def test_customer_endpoints_require_auth(self):
        """Customer endpoints should require authentication"""
        endpoints = [
            "/api/customer/website",
            "/api/customer/reviews",
            "/api/customer/social/status",
            "/api/customer/reports",
            "/api/customer/billing",
            "/api/customer/referrals",
        ]
        for endpoint in endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}")
            assert response.status_code == 401, f"{endpoint} should require auth"


class TestServiceWorkerChunkFix:
    """Test service worker v3 deployment"""
    
    def test_service_worker_version(self):
        """Service worker should be v3 with chunk fix"""
        response = requests.get(f"{BASE_URL}/service-worker.js")
        assert response.status_code == 200
        content = response.text
        assert "aurem-sw-v3-20260212" in content
        assert "ChunkLoadError" in content or "network-only" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
