"""
Test Suite for Iteration 175: Content Engine Image Generation + Forensic Miner
================================================================================
Tests:
1. Content Engine - POST /api/content-engine/generate-image (real image via OpenAIImageGeneration)
2. Forensic Miner - POST /api/forensic-miner/scan (DuckDuckGo + Tomba + health scan)
3. Forensic Miner - GET /api/forensic-miner/niches (8 supported niches)
4. Forensic Miner - GET /api/forensic-miner/history (scan history)
5. Auth guards on all endpoints (401 without token)
6. Validation errors (422 for missing prompt)
7. Usage tracking for images_generated
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://ai-platform-preview-3.preview.emergentagent.com"

# Test credentials
TEST_EMAIL = "teji.ss1986@gmail.com"
TEST_PASSWORD = "<REDACTED>"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for testing."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=30
    )
    if response.status_code == 200:
        data = response.json()
        token = data.get("token") or data.get("access_token")
        if token:
            return token
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text[:200]}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Return headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestAuthGuards:
    """Test that all endpoints require authentication (401 without token)."""

    def test_content_engine_generate_image_requires_auth(self):
        """POST /api/content-engine/generate-image returns 401 without auth."""
        response = requests.post(
            f"{BASE_URL}/api/content-engine/generate-image",
            json={"prompt": "test"},
            timeout=10
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: /api/content-engine/generate-image requires auth (401)")

    def test_forensic_miner_scan_requires_auth(self):
        """POST /api/forensic-miner/scan returns 401 without auth."""
        response = requests.post(
            f"{BASE_URL}/api/forensic-miner/scan",
            json={"niche": "skincare"},
            timeout=10
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: /api/forensic-miner/scan requires auth (401)")

    def test_forensic_miner_niches_requires_auth(self):
        """GET /api/forensic-miner/niches returns 401 without auth."""
        response = requests.get(
            f"{BASE_URL}/api/forensic-miner/niches",
            timeout=10
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: /api/forensic-miner/niches requires auth (401)")

    def test_forensic_miner_history_requires_auth(self):
        """GET /api/forensic-miner/history returns 401 without auth."""
        response = requests.get(
            f"{BASE_URL}/api/forensic-miner/history",
            timeout=10
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: /api/forensic-miner/history requires auth (401)")


class TestContentEngineImageGeneration:
    """Test Content Engine image generation via OpenAIImageGeneration."""

    def test_generate_image_validation_error_no_prompt(self, auth_headers):
        """POST /api/content-engine/generate-image with no prompt returns 422."""
        response = requests.post(
            f"{BASE_URL}/api/content-engine/generate-image",
            json={},  # Missing prompt
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text[:200]}"
        print("PASS: Missing prompt returns 422 validation error")

    def test_generate_image_success(self, auth_headers):
        """POST /api/content-engine/generate-image generates a real image."""
        # Get usage before
        usage_before = requests.get(
            f"{BASE_URL}/api/content-engine/usage",
            headers=auth_headers,
            timeout=10
        )
        images_before = 0
        if usage_before.status_code == 200:
            usage_data = usage_before.json()
            images_before = usage_data.get("usage", {}).get("images_generated", 0)
            print(f"Images generated before: {images_before}")

        # Generate image - use 90 second timeout as per instructions
        response = requests.post(
            f"{BASE_URL}/api/content-engine/generate-image",
            json={
                "prompt": "A professional marketing banner for a skincare brand, clean modern design, pastel colors",
                "size": "1024x1024"
            },
            headers=auth_headers,
            timeout=90  # Long timeout for image generation
        )
        
        print(f"Image generation response status: {response.status_code}")
        
        if response.status_code == 500:
            # Check if it's a key issue or actual failure
            error_text = response.text
            print(f"Image generation error: {error_text[:300]}")
            if "no_key" in error_text.lower() or "not configured" in error_text.lower():
                pytest.skip("EMERGENT_LLM_KEY not configured - skipping image generation test")
            pytest.fail(f"Image generation failed with 500: {error_text[:300]}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:300]}"
        
        data = response.json()
        print(f"Image generation response: {list(data.keys())}")
        
        # Verify response structure
        assert data.get("generated") == True, f"Expected generated=True, got {data.get('generated')}"
        assert "image_id" in data, "Missing image_id in response"
        assert data.get("size_bytes", 0) > 0, f"Expected size_bytes > 0, got {data.get('size_bytes')}"
        assert "image_base64" in data, "Missing image_base64 preview in response"
        
        # Verify base64 preview is truncated (first 100 chars + ...)
        base64_preview = data.get("image_base64", "")
        assert len(base64_preview) <= 110, f"Expected truncated base64 preview, got {len(base64_preview)} chars"
        
        print(f"PASS: Image generated successfully")
        print(f"  - image_id: {data.get('image_id')}")
        print(f"  - size_bytes: {data.get('size_bytes')}")
        print(f"  - base64 preview length: {len(base64_preview)}")
        
        # Verify usage tracking incremented
        time.sleep(1)  # Wait for DB update
        usage_after = requests.get(
            f"{BASE_URL}/api/content-engine/usage",
            headers=auth_headers,
            timeout=10
        )
        if usage_after.status_code == 200:
            usage_data_after = usage_after.json()
            images_after = usage_data_after.get("usage", {}).get("images_generated", 0)
            print(f"Images generated after: {images_after}")
            assert images_after > images_before, f"Usage tracking not incremented: before={images_before}, after={images_after}"
            print("PASS: Usage tracking incremented images_generated")


class TestForensicMinerNiches:
    """Test Forensic Miner niches endpoint."""

    def test_get_niches_returns_8_supported(self, auth_headers):
        """GET /api/forensic-miner/niches returns 8 supported niches."""
        response = requests.get(
            f"{BASE_URL}/api/forensic-miner/niches",
            headers=auth_headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        niches = data.get("niches", {})
        count = data.get("count", 0)
        
        print(f"Niches returned: {list(niches.keys())}")
        print(f"Count: {count}")
        
        # Verify 8 niches
        assert count == 8, f"Expected 8 niches, got {count}"
        
        # Verify expected niches are present
        expected_niches = ["beauty", "skincare", "fashion", "health", "fitness", "food", "tech", "pets"]
        for niche in expected_niches:
            assert niche in niches, f"Missing niche: {niche}"
            # Each niche should have keywords
            keywords = niches[niche]
            assert isinstance(keywords, list), f"Niche {niche} keywords should be a list"
            assert len(keywords) > 0, f"Niche {niche} should have keywords"
        
        print(f"PASS: All 8 niches present with keywords")
        print(f"  - beauty: {niches.get('beauty', [])}")
        print(f"  - skincare: {niches.get('skincare', [])}")


class TestForensicMinerScan:
    """Test Forensic Miner scan endpoint."""

    def test_scan_skincare_niche(self, auth_headers):
        """POST /api/forensic-miner/scan with niche=skincare returns stores with health scores."""
        response = requests.post(
            f"{BASE_URL}/api/forensic-miner/scan",
            json={
                "niche": "skincare",
                "limit": 5,
                "zone": "com",
                "auto_outreach": False
            },
            headers=auth_headers,
            timeout=60  # 60 second timeout for scan
        )
        
        print(f"Scan response status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:300]}"
        
        data = response.json()
        print(f"Scan response keys: {list(data.keys())}")
        
        # Verify response structure
        assert "scan_id" in data, "Missing scan_id"
        assert "niche" in data, "Missing niche"
        assert data.get("niche") == "skincare", f"Expected niche=skincare, got {data.get('niche')}"
        assert "stores" in data, "Missing stores array"
        assert "stores_enriched" in data, "Missing stores_enriched count"
        assert "avg_health_score" in data, "Missing avg_health_score"
        
        stores = data.get("stores", [])
        stores_enriched = data.get("stores_enriched", 0)
        avg_score = data.get("avg_health_score", 0)
        
        print(f"Scan results:")
        print(f"  - scan_id: {data.get('scan_id')}")
        print(f"  - stores_enriched: {stores_enriched}")
        print(f"  - avg_health_score: {avg_score}")
        print(f"  - domains_found: {data.get('domains_found', 0)}")
        print(f"  - emails_found: {data.get('emails_found', 0)}")
        
        # Verify stores have required fields
        if stores:
            store = stores[0]
            print(f"\nFirst store sample:")
            print(f"  - domain: {store.get('domain')}")
            print(f"  - score: {store.get('score')}")
            print(f"  - email_count: {store.get('email_count')}")
            print(f"  - social: {store.get('social', {})}")
            
            # Verify store structure
            assert "domain" in store, "Store missing domain"
            assert "score" in store, "Store missing score (health score)"
            assert "health" in store, "Store missing health object"
            
            # Verify health score is 0-100
            score = store.get("score", 0)
            assert 0 <= score <= 100, f"Health score should be 0-100, got {score}"
            
            # Verify health object has issues array
            health = store.get("health", {})
            if health.get("reachable"):
                assert "issues" in health, "Health object missing issues array"
                issues = health.get("issues", [])
                print(f"  - issues: {issues}")
                # Verify issues are valid types
                valid_issues = ["missing_title", "missing_meta_description", "short_meta_description", 
                               "missing_og_tags", "missing_og_image"]
                for issue in issues:
                    assert issue in valid_issues, f"Unknown issue type: {issue}"
            
            # Verify social profiles structure
            social = store.get("social", {})
            if social:
                print(f"  - social profiles found: {list(social.keys())}")
                # Valid social platforms
                valid_platforms = ["instagram", "twitter", "facebook", "tiktok", "linkedin", "youtube", "pinterest"]
                for platform in social.keys():
                    assert platform in valid_platforms, f"Unknown social platform: {platform}"
        
        print(f"\nPASS: Forensic Miner scan completed successfully")


class TestForensicMinerHistory:
    """Test Forensic Miner history endpoint."""

    def test_get_scan_history(self, auth_headers):
        """GET /api/forensic-miner/history returns scan history."""
        response = requests.get(
            f"{BASE_URL}/api/forensic-miner/history",
            headers=auth_headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        scans = data.get("scans", [])
        count = data.get("count", 0)
        
        print(f"Scan history: {count} scans found")
        
        # Verify response structure
        assert "scans" in data, "Missing scans array"
        assert "count" in data, "Missing count"
        
        # If we have scans, verify structure
        if scans:
            scan = scans[0]
            print(f"\nLatest scan:")
            print(f"  - scan_id: {scan.get('scan_id')}")
            print(f"  - niche: {scan.get('niche')}")
            print(f"  - stores_enriched: {scan.get('stores_enriched')}")
            print(f"  - avg_health_score: {scan.get('avg_health_score')}")
            print(f"  - created_at: {scan.get('created_at')}")
            
            # Verify scan has required fields
            assert "scan_id" in scan, "Scan missing scan_id"
            assert "niche" in scan, "Scan missing niche"
            assert "stores_enriched" in scan, "Scan missing stores_enriched"
            assert "avg_health_score" in scan, "Scan missing avg_health_score"
        
        print(f"\nPASS: Scan history endpoint working")


class TestContentEngineUsage:
    """Test Content Engine usage tracking."""

    def test_get_usage(self, auth_headers):
        """GET /api/content-engine/usage returns usage stats."""
        response = requests.get(
            f"{BASE_URL}/api/content-engine/usage",
            headers=auth_headers,
            timeout=10
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        print(f"Usage response: {data}")
        
        # Verify response structure
        assert "usage" in data, "Missing usage object"
        assert "posts" in data, "Missing posts limit info"
        assert "images" in data, "Missing images limit info"
        
        usage = data.get("usage", {})
        images_check = data.get("images", {})
        
        print(f"\nUsage stats:")
        print(f"  - images_generated: {usage.get('images_generated', 0)}")
        print(f"  - content_posts: {usage.get('content_posts', 0)}")
        print(f"  - month: {usage.get('month')}")
        print(f"\nImage limits:")
        print(f"  - used: {images_check.get('used', 0)}")
        print(f"  - limit: {images_check.get('limit')}")
        print(f"  - tier: {images_check.get('tier')}")
        
        print(f"\nPASS: Usage tracking endpoint working")


class TestHealthCheck:
    """Basic health check to ensure backend is running."""

    def test_backend_health(self):
        """GET /api/health returns ok."""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Backend health check failed: {response.status_code}"
        print("PASS: Backend health check OK")

    def test_auth_login(self):
        """POST /api/auth/login works with valid credentials."""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=30
        )
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text[:200]}"
        data = response.json()
        assert "token" in data or "access_token" in data, "Missing token in login response"
        print("PASS: Auth login working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
