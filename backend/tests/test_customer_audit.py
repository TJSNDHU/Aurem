"""
Customer Audit API Tests — iter 322ca
Tests for the $49/mo SEO + Ads Waste Detector feature.

Endpoints tested:
- GET /api/customer/audit/_/health
- POST /api/customer/audit/run (with/without auth)
- GET /api/customer/audit/latest
- GET /api/customer/audit/history
- GET /api/customer/audit/{audit_id}
- Regression: GET /api/admin/antigravity-skills/library/meta
- Regression: GET /health
"""
import os
import pytest
import requests
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://ai-platform-preview-3.preview.emergentagent.com"

# Test credentials from test_credentials.md
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = "Aurem@Founder2026!"


class TestCustomerAuditHealth:
    """Health endpoint tests"""

    def test_audit_health_endpoint(self):
        """GET /api/customer/audit/_/health returns ok=true and psi_key_configured=true"""
        response = requests.get(f"{BASE_URL}/api/customer/audit/_/health", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("ok") is True, "Expected ok=true"
        assert data.get("psi_key_configured") is True, "Expected psi_key_configured=true"
        assert data.get("service") == "customer-audit", "Expected service=customer-audit"
        print(f"✓ Health endpoint: ok={data['ok']}, psi_key_configured={data['psi_key_configured']}")

    def test_main_health_endpoint_fast(self):
        """GET /health responds 200 in <1s (deploy fix regression check)"""
        start = time.time()
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        elapsed = time.time() - start
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert elapsed < 1.0, f"Health endpoint took {elapsed:.2f}s, expected <1s"
        print(f"✓ Main health endpoint: {response.status_code} in {elapsed:.3f}s")


class TestCustomerAuditAuth:
    """Authentication tests for audit endpoints"""

    def test_audit_run_without_auth_returns_401(self):
        """POST /api/customer/audit/run WITHOUT auth returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/customer/audit/run",
            json={"url": "https://www.example.com", "strategy": "mobile"},
            timeout=10
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ No auth returns 401: {response.json().get('detail', '')}")

    def test_audit_run_with_invalid_token_returns_401(self):
        """POST /api/customer/audit/run with invalid token returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/customer/audit/run",
            headers={"Authorization": "Bearer invalid_token_here"},
            json={"url": "https://www.example.com", "strategy": "mobile"},
            timeout=10
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ Invalid token returns 401: {response.json().get('detail', '')}")


class TestCustomerAuditRun:
    """Audit run endpoint tests"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/platform/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code != 200:
            pytest.skip(f"Authentication failed: {response.status_code}")
        return response.json().get("token")

    def test_audit_run_with_valid_jwt(self, auth_token):
        """POST /api/customer/audit/run with valid customer JWT returns 200 with expected fields"""
        response = requests.post(
            f"{BASE_URL}/api/customer/audit/run",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"url": "https://www.airbnb.com", "strategy": "mobile"},
            timeout=90  # PSI can take up to 60s
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        
        # Verify required fields
        assert data.get("status") == "completed", f"Expected status=completed, got {data.get('status')}"
        assert "psi_status" in data, "Missing psi_status field"
        assert "scores" in data, "Missing scores field"
        assert "seo" in data, "Missing seo field"
        assert "ads" in data, "Missing ads field"
        assert "top_issues" in data, "Missing top_issues field"
        
        # Verify psi_status is one of expected values
        valid_psi_statuses = ["ok", "psi_api_not_enabled", "rate_limited", "no_api_key", "network_error"]
        assert data["psi_status"] in valid_psi_statuses, f"Unexpected psi_status: {data['psi_status']}"
        
        # Verify ads structure
        ads = data["ads"]
        assert "waste_signals" in ads, "Missing ads.waste_signals"
        assert isinstance(ads["waste_signals"], list), "ads.waste_signals should be a list"
        assert "estimated_monthly_waste_usd" in ads, "Missing ads.estimated_monthly_waste_usd"
        assert isinstance(ads["estimated_monthly_waste_usd"], int), "estimated_monthly_waste_usd should be int"
        assert ads["estimated_monthly_waste_usd"] >= 0, "estimated_monthly_waste_usd should be >= 0"
        
        # Verify SEO fields are populated from HTML scrape (not zero/null)
        seo = data["seo"]
        assert seo.get("title") is not None, "seo.title should not be null"
        assert "has_schema" in seo, "Missing seo.has_schema"
        assert "h1_count" in seo, "Missing seo.h1_count"
        assert "img_alt_missing" in seo, "Missing seo.img_alt_missing"
        
        print(f"✓ Audit run completed: status={data['status']}, psi_status={data['psi_status']}")
        print(f"  SEO: title_length={seo.get('title_length')}, h1_count={seo.get('h1_count')}, has_schema={seo.get('has_schema')}")
        print(f"  Ads: waste_signals={len(ads['waste_signals'])}, estimated_waste=${ads['estimated_monthly_waste_usd']}")
        
        # Store audit_id for later tests
        TestCustomerAuditRun.last_audit_id = data.get("id")


class TestCustomerAuditRetrieval:
    """Audit retrieval endpoint tests"""

    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/platform/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code != 200:
            pytest.skip(f"Authentication failed: {response.status_code}")
        return response.json().get("token")

    def test_get_latest_audit(self, auth_token):
        """GET /api/customer/audit/latest with valid JWT returns the most recent audit"""
        response = requests.get(
            f"{BASE_URL}/api/customer/audit/latest",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Either returns an audit or a message saying no audit yet
        if "audit" in data and data["audit"] is None:
            print("✓ Latest audit: No audit yet (expected for new users)")
        else:
            assert "id" in data, "Expected audit to have id field"
            assert "status" in data, "Expected audit to have status field"
            print(f"✓ Latest audit: id={data.get('id')}, status={data.get('status')}")

    def test_get_audit_history(self, auth_token):
        """GET /api/customer/audit/history?limit=5 with valid JWT returns {items: [...]} sorted by started_at desc"""
        response = requests.get(
            f"{BASE_URL}/api/customer/audit/history?limit=5",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "items" in data, "Expected response to have 'items' field"
        assert isinstance(data["items"], list), "items should be a list"
        
        # Verify sorting (if multiple items)
        items = data["items"]
        if len(items) > 1:
            for i in range(len(items) - 1):
                assert items[i]["started_at"] >= items[i + 1]["started_at"], \
                    "Items should be sorted by started_at desc"
        
        print(f"✓ Audit history: {len(items)} items returned")

    def test_get_audit_by_id_own_audit(self, auth_token):
        """GET /api/customer/audit/{audit_id} for own audit returns audit"""
        # First get the latest audit to get an ID
        latest_response = requests.get(
            f"{BASE_URL}/api/customer/audit/latest",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=10
        )
        if latest_response.status_code != 200:
            pytest.skip("Could not get latest audit")
        
        latest_data = latest_response.json()
        if "audit" in latest_data and latest_data["audit"] is None:
            pytest.skip("No audits available to test")
        
        audit_id = latest_data.get("id")
        if not audit_id:
            pytest.skip("No audit ID available")
        
        # Now get the specific audit
        response = requests.get(
            f"{BASE_URL}/api/customer/audit/{audit_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("id") == audit_id, f"Expected id={audit_id}, got {data.get('id')}"
        print(f"✓ Get audit by ID: {audit_id}")

    def test_get_audit_by_id_nonexistent_returns_404(self, auth_token):
        """GET /api/customer/audit/{audit_id} for non-existent audit returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/customer/audit/audit_nonexistent_12345",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=10
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ Non-existent audit returns 404")


class TestRegressionChecks:
    """Regression tests for previous iteration features"""

    def test_antigravity_skills_library_meta(self):
        """GET /api/admin/antigravity-skills/library/meta still returns total_in_db=1453"""
        response = requests.get(
            f"{BASE_URL}/api/admin/antigravity-skills/library/meta",
            timeout=10
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        total = data.get("total_in_db", 0)
        assert total == 1453, f"Expected total_in_db=1453, got {total}"
        print(f"✓ Skills library regression: total_in_db={total}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
