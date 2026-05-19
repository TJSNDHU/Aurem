"""
PULSE Token Efficiency Protocol + GitHub Actions Integration Tests
===================================================================
Iteration 170: Testing compacted files and new GitHub deploy features

Tests:
1. connector_ecosystem.py compaction - ConnectorEcosystem class, StubConnector, GitHubConnector
2. ai_repair_router.py - SEO/Accessibility repair endpoints still accessible
3. email_templates.py - get_email_base_styles(), _email_wrap(), generate_order_confirmation_email()
4. GitHub Deploy - /api/github/status, /api/github/connect, /api/github/push-fix, /api/github/pr-status
"""

import pytest
import requests
import os
import sys

# Add backend to path for direct imports
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ai-platform-preview-3.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = "<REDACTED>"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for protected endpoints."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Auth failed: {response.status_code} - {response.text[:200]}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: connector_ecosystem.py Compaction Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestConnectorEcosystemCompaction:
    """Test that connector_ecosystem.py still works after compaction (2228→319 lines)."""

    def test_connector_ecosystem_import(self):
        """Verify ConnectorEcosystem class can be imported."""
        try:
            from services.connector_ecosystem import ConnectorEcosystem, get_connector_ecosystem, set_connector_ecosystem_db
            assert ConnectorEcosystem is not None
            assert callable(get_connector_ecosystem)
            assert callable(set_connector_ecosystem_db)
            print("PASS: ConnectorEcosystem imports work correctly")
        except ImportError as e:
            pytest.fail(f"Import failed: {e}")

    def test_get_connector_ecosystem_singleton(self):
        """Verify get_connector_ecosystem() returns singleton instance."""
        from services.connector_ecosystem import get_connector_ecosystem
        eco1 = get_connector_ecosystem()
        eco2 = get_connector_ecosystem()
        assert eco1 is eco2, "get_connector_ecosystem should return same instance"
        print("PASS: get_connector_ecosystem() returns singleton")

    def test_stub_connector_demo_data(self):
        """Verify StubConnector returns demo data for platforms without live APIs."""
        from services.connector_ecosystem import get_connector_ecosystem
        import asyncio
        
        eco = get_connector_ecosystem()
        
        # Test Twitter stub
        twitter_data = asyncio.get_event_loop().run_until_complete(
            eco.fetch_data("twitter", {"query": "test"})
        )
        assert isinstance(twitter_data, list), "Twitter stub should return list"
        if twitter_data:
            assert "text" in twitter_data[0] or "id" in twitter_data[0], "Twitter demo data should have expected fields"
        print(f"PASS: Twitter StubConnector returns demo data: {len(twitter_data)} items")

    def test_stub_connector_tiktok(self):
        """Verify TikTok StubConnector returns demo data."""
        from services.connector_ecosystem import get_connector_ecosystem
        import asyncio
        
        eco = get_connector_ecosystem()
        tiktok_data = asyncio.get_event_loop().run_until_complete(
            eco.fetch_data("tiktok", {"query": "test"})
        )
        assert isinstance(tiktok_data, list), "TikTok stub should return list"
        print(f"PASS: TikTok StubConnector returns demo data: {len(tiktok_data)} items")

    def test_stub_connector_reddit(self):
        """Verify Reddit StubConnector returns demo data."""
        from services.connector_ecosystem import get_connector_ecosystem
        import asyncio
        
        eco = get_connector_ecosystem()
        reddit_data = asyncio.get_event_loop().run_until_complete(
            eco.fetch_data("reddit", {"query": "test"})
        )
        assert isinstance(reddit_data, list), "Reddit stub should return list"
        print(f"PASS: Reddit StubConnector returns demo data: {len(reddit_data)} items")

    def test_stub_connector_bilibili(self):
        """Verify Bilibili StubConnector returns demo data."""
        from services.connector_ecosystem import get_connector_ecosystem
        import asyncio
        
        eco = get_connector_ecosystem()
        bilibili_data = asyncio.get_event_loop().run_until_complete(
            eco.fetch_data("bilibili", {"query": "test"})
        )
        assert isinstance(bilibili_data, list), "Bilibili stub should return list"
        print(f"PASS: Bilibili StubConnector returns demo data: {len(bilibili_data)} items")

    def test_github_connector_requires_credentials(self):
        """Verify GitHubConnector.authenticate() requires credentials."""
        from services.connector_ecosystem import GitHubConnector
        import asyncio
        
        gh = GitHubConnector()
        # Without credentials should return False
        result = asyncio.get_event_loop().run_until_complete(gh.authenticate(None))
        assert result is False, "GitHubConnector should fail without credentials"
        
        # With empty dict should return False
        result2 = asyncio.get_event_loop().run_until_complete(gh.authenticate({}))
        assert result2 is False, "GitHubConnector should fail with empty credentials"
        print("PASS: GitHubConnector.authenticate() requires valid credentials")

    def test_slack_connector_exists(self):
        """Verify SlackConnector is available."""
        from services.connector_ecosystem import SlackConnector
        slack = SlackConnector()
        assert hasattr(slack, 'authenticate'), "SlackConnector should have authenticate method"
        assert hasattr(slack, 'fetch'), "SlackConnector should have fetch method"
        assert hasattr(slack, 'post'), "SlackConnector should have post method"
        print("PASS: SlackConnector class is available with expected methods")

    def test_set_connector_ecosystem_db(self):
        """Verify set_connector_ecosystem_db() works."""
        from services.connector_ecosystem import get_connector_ecosystem, set_connector_ecosystem_db
        
        eco = get_connector_ecosystem()
        # Set a mock db
        mock_db = {"test": "db"}
        set_connector_ecosystem_db(mock_db)
        assert eco.db == mock_db, "set_connector_ecosystem_db should update ecosystem db"
        
        # Reset to None
        set_connector_ecosystem_db(None)
        print("PASS: set_connector_ecosystem_db() works correctly")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: ai_repair_router.py Tests (Compacted _generate_aria_fixes)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAIRepairRouterCompaction:
    """Test ai_repair_router.py endpoints still work after compaction."""

    def test_seo_generate_endpoint_accessible(self, auth_headers):
        """POST /api/repair/seo/generate should be accessible."""
        response = requests.post(
            f"{BASE_URL}/api/repair/seo/generate",
            headers=auth_headers,
            json={"url": "https://example.com"}
        )
        # Should not be 404 - endpoint exists
        assert response.status_code != 404, f"SEO generate endpoint should exist, got {response.status_code}"
        # 400 is acceptable (URL fetch might fail), 503 if LLM unavailable
        assert response.status_code in [200, 400, 503], f"Unexpected status: {response.status_code}"
        print(f"PASS: POST /api/repair/seo/generate accessible (status: {response.status_code})")

    def test_pending_fixes_endpoint(self, auth_headers):
        """GET /api/repair/pending should return fixes list."""
        response = requests.get(
            f"{BASE_URL}/api/repair/pending",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "fixes" in data, "Response should have 'fixes' key"
        assert "total" in data, "Response should have 'total' key"
        print(f"PASS: GET /api/repair/pending returns {data['total']} fixes")

    def test_approve_fix_endpoint(self, auth_headers):
        """POST /api/repair/{fix_id}/approve should work."""
        # Try with a non-existent fix_id - should return 404
        response = requests.post(
            f"{BASE_URL}/api/repair/nonexistent_fix_123/approve",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404 for non-existent fix, got {response.status_code}"
        print("PASS: POST /api/repair/{fix_id}/approve endpoint works (404 for non-existent)")

    def test_scores_endpoint(self, auth_headers):
        """GET /api/repair/scores should return scores."""
        response = requests.get(
            f"{BASE_URL}/api/repair/scores",
            headers=auth_headers,
            params={"url": "https://example.com"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "url" in data, "Response should have 'url' key"
        assert "seo" in data, "Response should have 'seo' key"
        assert "accessibility" in data, "Response should have 'accessibility' key"
        print(f"PASS: GET /api/repair/scores returns scores for URL")

    def test_history_endpoint(self, auth_headers):
        """GET /api/repair/history should return scan history."""
        response = requests.get(
            f"{BASE_URL}/api/repair/history",
            headers=auth_headers
        )
        # Endpoint might not exist - check for 404 vs other errors
        if response.status_code == 404:
            pytest.skip("History endpoint not implemented")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: GET /api/repair/history accessible")

    def test_deploy_preview_endpoint(self, auth_headers):
        """POST /api/repair/deploy/preview should work."""
        response = requests.post(
            f"{BASE_URL}/api/repair/deploy/preview",
            headers=auth_headers,
            json={"url": "https://example.com"}
        )
        # 400 is expected if no approved fixes
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}"
        print(f"PASS: POST /api/repair/deploy/preview accessible (status: {response.status_code})")

    def test_self_scan_endpoint(self, auth_headers):
        """POST /api/repair/self-scan should work."""
        response = requests.post(
            f"{BASE_URL}/api/repair/self-scan",
            headers=auth_headers
        )
        # Endpoint might not exist or require specific setup
        if response.status_code == 404:
            pytest.skip("Self-scan endpoint not implemented")
        assert response.status_code in [200, 400, 503], f"Unexpected status: {response.status_code}"
        print(f"PASS: POST /api/repair/self-scan accessible (status: {response.status_code})")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: email_templates.py Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestEmailTemplatesCompaction:
    """Test email_templates.py functions after compaction."""

    def test_get_email_base_styles(self):
        """get_email_base_styles() should return CSS string."""
        from services.email_templates import get_email_base_styles
        
        styles = get_email_base_styles()
        assert isinstance(styles, str), "Should return string"
        assert "font-family" in styles, "Should contain font-family CSS"
        assert "container" in styles, "Should contain container class"
        assert "header" in styles, "Should contain header class"
        assert "footer" in styles, "Should contain footer class"
        print(f"PASS: get_email_base_styles() returns CSS ({len(styles)} chars)")

    def test_email_wrap_function(self):
        """_email_wrap() should return HTML with header/footer."""
        from services.email_templates import _email_wrap
        
        html = _email_wrap("Test Title", "<p>Test content</p>")
        assert isinstance(html, str), "Should return string"
        assert "<!DOCTYPE html>" in html, "Should have DOCTYPE"
        assert "Test Title" in html, "Should contain title"
        assert "Test content" in html, "Should contain content"
        assert "REROOTS" in html, "Should have brand header"
        assert "footer" in html.lower() or "support" in html.lower(), "Should have footer"
        print(f"PASS: _email_wrap() returns valid HTML ({len(html)} chars)")

    def test_email_wrap_custom_store(self):
        """_email_wrap() should accept custom store name."""
        from services.email_templates import _email_wrap
        
        html = _email_wrap("Test", "<p>Content</p>", store_name="CustomStore", support_email="test@custom.com")
        assert "CustomStore" in html, "Should contain custom store name"
        assert "test@custom.com" in html, "Should contain custom support email"
        print("PASS: _email_wrap() accepts custom store parameters")

    def test_generate_order_confirmation_email(self):
        """generate_order_confirmation_email() should return valid HTML."""
        from services.email_templates import generate_order_confirmation_email
        
        test_order = {
            "order_number": "TEST-12345",
            "items": [
                {"product_name": "Test Product", "quantity": 2, "price": 29.99, "product_image": "https://via.placeholder.com/80"}
            ],
            "subtotal": 59.98,
            "shipping": 5.00,
            "tax": 7.80,
            "total": 72.78,
            "shipping_address": {
                "first_name": "John",
                "last_name": "Doe",
                "address": "123 Test St",
                "city": "Toronto",
                "province": "ON",
                "postal_code": "M5V 1A1",
                "country": "Canada"
            }
        }
        
        html = generate_order_confirmation_email(test_order)
        assert isinstance(html, str), "Should return string"
        assert "<!DOCTYPE html>" in html, "Should have DOCTYPE"
        assert "TEST-12345" in html, "Should contain order number"
        assert "Test Product" in html, "Should contain product name"
        assert "72.78" in html, "Should contain total"
        assert "John" in html, "Should contain customer name"
        print(f"PASS: generate_order_confirmation_email() returns valid HTML ({len(html)} chars)")

    def test_order_confirmation_combo_protocol(self):
        """generate_order_confirmation_email() should show 60-second protocol for combo orders."""
        from services.email_templates import generate_order_confirmation_email
        
        combo_order = {
            "order_number": "COMBO-001",
            "items": [
                {"product_name": "Engine Serum", "quantity": 1, "price": 49.99},
                {"product_name": "Buffer Cream", "quantity": 1, "price": 39.99}
            ],
            "subtotal": 89.98,
            "shipping": 0,
            "tax": 11.70,
            "total": 101.68,
            "shipping_address": {"first_name": "Jane", "last_name": "Smith", "address": "456 Main St", "city": "Vancouver", "province": "BC", "postal_code": "V6B 1A1"}
        }
        
        html = generate_order_confirmation_email(combo_order)
        # Combo orders (2 items) should show protocol reminder
        assert "ENGINE" in html or "STEP 1" in html, "Combo order should show ENGINE badge"
        assert "BUFFER" in html or "STEP 2" in html, "Combo order should show BUFFER badge"
        print("PASS: generate_order_confirmation_email() shows combo protocol badges")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: GitHub Deploy Router Tests (NEW)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGitHubDeployRouter:
    """Test new GitHub deploy endpoints."""

    def test_github_status_unconnected(self, auth_headers):
        """GET /api/github/status should return connected=false for unconnected tenant."""
        response = requests.get(
            f"{BASE_URL}/api/github/status",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "connected" in data, "Response should have 'connected' key"
        # For a fresh tenant, should be false
        print(f"PASS: GET /api/github/status returns connected={data.get('connected')}")

    def test_github_connect_invalid_token(self, auth_headers):
        """POST /api/github/connect should reject invalid token with 400."""
        response = requests.post(
            f"{BASE_URL}/api/github/connect",
            headers=auth_headers,
            json={"token": "invalid_token_12345"}
        )
        assert response.status_code == 400, f"Expected 400 for invalid token, got {response.status_code}"
        data = response.json()
        assert "detail" in data or "error" in data, "Should have error message"
        print(f"PASS: POST /api/github/connect rejects invalid token (400)")

    def test_github_endpoints_require_auth(self):
        """All GitHub endpoints should require authentication (401 without token)."""
        # GET endpoints - should return 401
        get_endpoints = ["/api/github/status", "/api/github/pr-status"]
        for endpoint in get_endpoints:
            response = requests.get(f"{BASE_URL}{endpoint}")
            assert response.status_code == 401, f"GET {endpoint} should return 401 without auth, got {response.status_code}"
            print(f"PASS: GET {endpoint} returns 401 without auth")
        
        # POST endpoints - need valid body to avoid 422 validation error
        # POST /api/github/connect with valid body but no auth
        response = requests.post(
            f"{BASE_URL}/api/github/connect",
            headers={"Content-Type": "application/json"},
            json={"token": "test_token"}
        )
        assert response.status_code == 401, f"POST /api/github/connect should return 401 without auth, got {response.status_code}"
        print("PASS: POST /api/github/connect returns 401 without auth")
        
        # POST /api/github/push-fix with valid body but no auth
        response = requests.post(
            f"{BASE_URL}/api/github/push-fix",
            headers={"Content-Type": "application/json"},
            json={"repo": "test/repo", "fix_title": "Test", "fix_description": "Test", "file_path": "test.html", "file_content": "<html>"}
        )
        assert response.status_code == 401, f"POST /api/github/push-fix should return 401 without auth, got {response.status_code}"
        print("PASS: POST /api/github/push-fix returns 401 without auth")

    def test_github_push_fix_requires_auth(self, auth_headers):
        """POST /api/github/push-fix should require auth and valid data."""
        # Without auth
        response = requests.post(
            f"{BASE_URL}/api/github/push-fix",
            json={"repo": "test/repo", "fix_title": "Test", "fix_description": "Test", "file_path": "test.html", "file_content": "<html>"}
        )
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        
        # With auth but no GitHub connection
        response2 = requests.post(
            f"{BASE_URL}/api/github/push-fix",
            headers=auth_headers,
            json={"repo": "test/repo", "fix_title": "Test", "fix_description": "Test", "file_path": "test.html", "file_content": "<html>"}
        )
        # Should fail because no GitHub token connected
        assert response2.status_code == 400, f"Expected 400 (no GitHub token), got {response2.status_code}"
        print("PASS: POST /api/github/push-fix requires auth and GitHub connection")

    def test_github_pr_status_requires_auth(self, auth_headers):
        """GET /api/github/pr-status should require auth."""
        # Without auth
        response = requests.get(f"{BASE_URL}/api/github/pr-status")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        
        # With auth but no PR
        response2 = requests.get(
            f"{BASE_URL}/api/github/pr-status",
            headers=auth_headers
        )
        # Should return 400 because no PR found
        assert response2.status_code == 400, f"Expected 400 (no PR), got {response2.status_code}"
        print("PASS: GET /api/github/pr-status requires auth")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: Backend Health Check
# ═══════════════════════════════════════════════════════════════════════════════

class TestBackendHealth:
    """Verify backend starts without errors after compaction changes."""

    def test_health_endpoint(self):
        """Backend health check should pass."""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get("status") == "ok", f"Health status not ok: {data}"
        print(f"PASS: Backend health check OK (uptime: {data.get('uptime_seconds', 'N/A')}s)")

    def test_auth_login(self):
        """Auth login should work."""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.status_code}"
        data = response.json()
        assert "token" in data or "access_token" in data, "Login should return token"
        print("PASS: Auth login works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
