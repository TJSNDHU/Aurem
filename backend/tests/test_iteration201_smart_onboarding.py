"""
Iteration 201 — Smart Onboarding Tests
======================================
Tests for the new Smart Onboarding feature:
- GET /api/smart-onboarding/health
- POST /api/smart-onboarding/detect (auth required)
- POST /api/smart-onboarding/start (auth required)
- GET /api/smart-onboarding/me (auth required)
- GET /api/bin-auth/customer-context (smart_onboarding_complete field)
- Regression: legacy /api/onboarding/* routes still work
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from test_credentials.md
REROOTS_EMAIL = "pawandeep19may1985@gmail.com"
REROOTS_PASSWORD = "ReRoots2026!"
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")
TESTBIN_EMAIL = "testbin@aurem.live"
TESTBIN_PASSWORD = "TempPass123!"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def reroots_token(api_client):
    """Get auth token for ReRoots customer"""
    response = api_client.post(f"{BASE_URL}/api/platform/auth/login", json={
        "email": REROOTS_EMAIL,
        "password": REROOTS_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"ReRoots login failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def admin_token(api_client):
    """Get auth token for admin"""
    response = api_client.post(f"{BASE_URL}/api/platform/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def testbin_token(api_client):
    """Get auth token for testbin user (no website)"""
    response = api_client.post(f"{BASE_URL}/api/platform/auth/login", json={
        "email": TESTBIN_EMAIL,
        "password": TESTBIN_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"TestBIN login failed: {response.status_code} - {response.text}")


class TestSmartOnboardingHealth:
    """Health endpoint tests"""

    def test_health_returns_ok(self, api_client):
        """GET /api/smart-onboarding/health returns {status:ok}"""
        response = api_client.get(f"{BASE_URL}/api/smart-onboarding/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "ok", f"Expected status=ok, got {data}"
        assert "service" in data or "smart-onboarding" in str(data).lower()
        print(f"✓ Health check passed: {data}")


class TestSmartOnboardingDetect:
    """POST /api/smart-onboarding/detect tests"""

    def test_detect_requires_auth(self, api_client):
        """POST /detect without Bearer token returns 401"""
        response = api_client.post(f"{BASE_URL}/api/smart-onboarding/detect", json={
            "business_name": "Test Business",
            "website_url": "https://example.com",
            "city": "Toronto"
        })
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Detect requires auth (401 without Bearer)")

    def test_detect_reroots_real_business(self, api_client, reroots_token):
        """POST /detect with ReRoots data returns detected platform, socials, places"""
        response = api_client.post(
            f"{BASE_URL}/api/smart-onboarding/detect",
            headers={"Authorization": f"Bearer {reroots_token}"},
            json={
                "business_name": "ReRoots Aesthetics",
                "website_url": "https://reroots.ca",
                "city": "Toronto"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "business_name" in data, "Missing business_name in response"
        assert "website" in data, "Missing website in response"
        assert "social_media" in data, "Missing social_media in response"
        assert "google_places" in data, "Missing google_places in response"
        assert "recommended_connection" in data, "Missing recommended_connection"
        assert "detected_at" in data, "Missing detected_at timestamp"
        
        # Validate website detection
        website = data.get("website", {})
        assert website.get("exists") == True, f"Expected website.exists=true, got {website}"
        assert website.get("platform") is not None, "Missing platform detection"
        assert website.get("confidence") in ["high", "medium", "none"], f"Invalid confidence: {website.get('confidence')}"
        
        # Validate Google Places (should find ReRoots in Toronto)
        places = data.get("google_places", {})
        # Note: places.found may be False if API key not set or rate limited
        if places.get("available"):
            print(f"  Google Places: found={places.get('found')}, rating={places.get('rating')}")
        
        # Validate social media detection
        socials = data.get("social_media", {})
        print(f"  Detected socials: {list(socials.keys())}")
        
        print(f"✓ Detect ReRoots: platform={website.get('platform')}, confidence={website.get('confidence')}")
        print(f"  Recommended connection: {data.get('recommended_connection')}")

    def test_detect_no_website_user(self, api_client, testbin_token):
        """POST /detect for user without website returns platform=no_website"""
        response = api_client.post(
            f"{BASE_URL}/api/smart-onboarding/detect",
            headers={"Authorization": f"Bearer {testbin_token}"},
            json={
                "business_name": "Test BIN Business",
                "website_url": "",  # No website
                "city": "Toronto"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        website = data.get("website", {})
        assert website.get("exists") == False or website.get("platform") == "no_website", \
            f"Expected no_website for empty URL, got {website}"
        assert data.get("recommended_connection") == "aurem_free_site", \
            f"Expected aurem_free_site recommendation, got {data.get('recommended_connection')}"
        
        print(f"✓ Detect no-website user: platform={website.get('platform')}, recommended={data.get('recommended_connection')}")


class TestSmartOnboardingStart:
    """POST /api/smart-onboarding/start tests"""

    def test_start_requires_auth(self, api_client):
        """POST /start without Bearer token returns 401"""
        response = api_client.post(f"{BASE_URL}/api/smart-onboarding/start", json={
            "business_name": "Test",
            "website_url": "https://example.com",
            "platform": "custom",
            "connection_method": "gtm",
            "social_media": {},
            "google_places": {}
        })
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Start requires auth (401 without Bearer)")

    def test_start_with_valid_data(self, api_client, reroots_token):
        """POST /start with valid form data returns success + actions"""
        response = api_client.post(
            f"{BASE_URL}/api/smart-onboarding/start",
            headers={"Authorization": f"Bearer {reroots_token}"},
            json={
                "business_name": "ReRoots Aesthetics",
                "website_url": "https://reroots.ca",
                "platform": "custom",
                "connection_method": "gtm",
                "social_media": {"instagram": "https://instagram.com/rerootsaesthetics"},
                "google_places": {"place_id": "test_place_id", "rating": 4.8, "review_count": 50}
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("success") == True, f"Expected success=true, got {data}"
        assert "tenant_id" in data, "Missing tenant_id in response"
        assert "actions" in data, "Missing actions in response"
        assert isinstance(data.get("actions"), list), "actions should be a list"
        
        print(f"✓ Start AUREM: tenant_id={data.get('tenant_id')}, actions={data.get('actions')}")


class TestSmartOnboardingMe:
    """GET /api/smart-onboarding/me tests"""

    def test_me_requires_auth(self, api_client):
        """GET /me without Bearer token returns 401"""
        response = api_client.get(f"{BASE_URL}/api/smart-onboarding/me")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ /me requires auth (401 without Bearer)")

    def test_me_returns_onboarding_state(self, api_client, reroots_token):
        """GET /me returns current onboarding state"""
        response = api_client.get(
            f"{BASE_URL}/api/smart-onboarding/me",
            headers={"Authorization": f"Bearer {reroots_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "email" in data, "Missing email in response"
        assert "onboarded" in data, "Missing onboarded flag"
        assert "platform" in data, "Missing platform"
        assert "business_name" in data, "Missing business_name"
        assert "website" in data, "Missing website"
        
        print(f"✓ /me: email={data.get('email')}, onboarded={data.get('onboarded')}, platform={data.get('platform')}")


class TestCustomerContextSmartOnboarding:
    """GET /api/bin-auth/customer-context smart_onboarding_complete field"""

    def test_customer_context_has_smart_onboarding_field(self, api_client, reroots_token):
        """customer-context returns smart_onboarding_complete field"""
        response = api_client.get(
            f"{BASE_URL}/api/bin-auth/customer-context",
            headers={"Authorization": f"Bearer {reroots_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "smart_onboarding_complete" in data, \
            f"Missing smart_onboarding_complete field in customer-context: {data.keys()}"
        assert isinstance(data.get("smart_onboarding_complete"), bool), \
            f"smart_onboarding_complete should be bool, got {type(data.get('smart_onboarding_complete'))}"
        
        print(f"✓ customer-context has smart_onboarding_complete={data.get('smart_onboarding_complete')}")

    def test_admin_context_has_smart_onboarding_field(self, api_client, admin_token):
        """Admin customer-context also has smart_onboarding_complete"""
        response = api_client.get(
            f"{BASE_URL}/api/bin-auth/customer-context",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "smart_onboarding_complete" in data, "Missing smart_onboarding_complete for admin"
        assert data.get("role") == "admin", f"Expected role=admin, got {data.get('role')}"
        
        print(f"✓ Admin context: role={data.get('role')}, smart_onboarding_complete={data.get('smart_onboarding_complete')}")


class TestLegacyOnboardingRegression:
    """Regression tests: legacy /api/onboarding/* routes still work"""

    def test_legacy_onboarding_status(self, api_client, reroots_token):
        """GET /api/onboarding/status (QuickStartWizard) still works"""
        response = api_client.get(
            f"{BASE_URL}/api/onboarding/status",
            headers={"Authorization": f"Bearer {reroots_token}"}
        )
        # Should return 200 or 404 (if not implemented), but NOT 500
        assert response.status_code in [200, 404], \
            f"Legacy /api/onboarding/status broken: {response.status_code} - {response.text}"
        
        if response.status_code == 200:
            print(f"✓ Legacy /api/onboarding/status works: {response.json()}")
        else:
            print(f"✓ Legacy /api/onboarding/status returns 404 (expected if not implemented)")

    def test_legacy_onboarding_tenant(self, api_client, admin_token):
        """GET /api/onboarding/{tenant_id} (AuremReport) still works"""
        # Use a known tenant_id
        tenant_id = "reroots-75ea63e28540"
        response = api_client.get(
            f"{BASE_URL}/api/onboarding/{tenant_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Should return 200 or 404, but NOT 500
        assert response.status_code in [200, 404], \
            f"Legacy /api/onboarding/{{tenant_id}} broken: {response.status_code} - {response.text}"
        
        if response.status_code == 200:
            print(f"✓ Legacy /api/onboarding/{tenant_id} works")
        else:
            print(f"✓ Legacy /api/onboarding/{tenant_id} returns 404 (expected if not found)")


class TestSmartOnboardingEdgeCases:
    """Edge case tests"""

    def test_detect_missing_business_name(self, api_client, reroots_token):
        """POST /detect with empty business_name returns 400"""
        response = api_client.post(
            f"{BASE_URL}/api/smart-onboarding/detect",
            headers={"Authorization": f"Bearer {reroots_token}"},
            json={
                "business_name": "",
                "website_url": "https://example.com",
                "city": "Toronto"
            }
        )
        assert response.status_code == 400, f"Expected 400 for empty business_name, got {response.status_code}"
        print("✓ Detect rejects empty business_name (400)")

    def test_detect_invalid_url(self, api_client, reroots_token):
        """POST /detect with invalid URL handles gracefully"""
        response = api_client.post(
            f"{BASE_URL}/api/smart-onboarding/detect",
            headers={"Authorization": f"Bearer {reroots_token}"},
            json={
                "business_name": "Test Business",
                "website_url": "not-a-valid-url",
                "city": "Toronto"
            }
        )
        # Should return 200 with exists=false, not crash
        assert response.status_code == 200, f"Expected 200 for invalid URL, got {response.status_code}: {response.text}"
        data = response.json()
        website = data.get("website", {})
        assert website.get("exists") == False or website.get("platform") == "no_website", \
            f"Expected exists=false for invalid URL, got {website}"
        print(f"✓ Detect handles invalid URL gracefully: {website}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
