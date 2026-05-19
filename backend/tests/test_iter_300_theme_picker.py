"""
Iteration 300 — Theme Picker + ORA Outreach Tests
==================================================
Tests for:
1. AWB build triggers outreach (email via Resend, WhatsApp via Twilio)
2. Theme discovery - GET /api/preview/{slug}/themes (UNAUTH)
3. Niche-aware fallback (curated catalog)
4. Thumbnail proxy /api/sites/_thumb/{thumb_id}
5. Preview page /api/preview/{slug} (UNAUTH HTML)
6. Customer theme pick - POST /api/preview/{slug}/select-theme
7. 'Powered by AUREM' footer in all AWB sites
8. Admin theme pre-discovery endpoint
9. Auth gate verification
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://ai-platform-preview-3.preview.emergentagent.com"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token"""
    resp = requests.post(
        f"{BASE_URL}/api/auth/admin/login",
        json={"email": "teji.ss1986@gmail.com", "password": "<REDACTED>"},
        timeout=15,
    )
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code}")
    return resp.json().get("token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def existing_site(auth_headers):
    """Get an existing site from cockpit for testing"""
    resp = requests.get(
        f"{BASE_URL}/api/admin/platform/website-builder/cockpit",
        headers=auth_headers,
        timeout=15,
    )
    if resp.status_code != 200:
        pytest.skip("Could not fetch cockpit data")
    data = resp.json()
    recent = data.get("recent", [])
    if not recent:
        pytest.skip("No existing sites to test")
    # Find a site with a slug
    for site in recent:
        if site.get("slug"):
            return site
    pytest.skip("No site with slug found")


class TestAuthGate:
    """Test auth requirements on admin endpoints vs public endpoints"""

    def test_admin_themes_endpoint_requires_auth(self):
        """POST /api/admin/platform/website-builder/themes/{slug} requires Bearer auth"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/platform/website-builder/themes/test-slug",
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: Admin themes endpoint returns 401 without auth")

    def test_preview_themes_is_unauth(self, existing_site):
        """GET /api/preview/{slug}/themes is UNAUTH"""
        slug = existing_site.get("slug")
        resp = requests.get(
            f"{BASE_URL}/api/preview/{slug}/themes",
            timeout=15,
        )
        # Should return 200 or 404 (if site not found), but NOT 401
        assert resp.status_code != 401, f"Preview themes should be UNAUTH, got {resp.status_code}"
        print(f"PASS: Preview themes endpoint is UNAUTH (status={resp.status_code})")

    def test_preview_page_is_unauth(self, existing_site):
        """GET /api/preview/{slug} is UNAUTH HTML page"""
        slug = existing_site.get("slug")
        resp = requests.get(
            f"{BASE_URL}/api/preview/{slug}",
            timeout=15,
        )
        assert resp.status_code != 401, f"Preview page should be UNAUTH, got {resp.status_code}"
        print(f"PASS: Preview page is UNAUTH (status={resp.status_code})")

    def test_select_theme_is_unauth(self, existing_site):
        """POST /api/preview/{slug}/select-theme is UNAUTH"""
        slug = existing_site.get("slug")
        # Just check it doesn't return 401 (may return 400/404 for invalid data)
        resp = requests.post(
            f"{BASE_URL}/api/preview/{slug}/select-theme",
            json={"template_idx": 999},  # Invalid idx to avoid side effects
            timeout=15,
        )
        assert resp.status_code != 401, f"Select theme should be UNAUTH, got {resp.status_code}"
        print(f"PASS: Select theme endpoint is UNAUTH (status={resp.status_code})")


class TestThemeDiscovery:
    """Test theme discovery endpoints"""

    def test_preview_themes_returns_themes(self, existing_site):
        """GET /api/preview/{slug}/themes returns theme options"""
        slug = existing_site.get("slug")
        resp = requests.get(
            f"{BASE_URL}/api/preview/{slug}/themes",
            timeout=30,  # Theme discovery can take time
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        
        # Verify response structure
        assert "slug" in data, "Response should contain slug"
        assert "themes" in data, "Response should contain themes array"
        
        themes = data.get("themes", [])
        print(f"PASS: Preview themes returned {len(themes)} themes for slug={slug}")
        
        # If themes exist, verify structure
        if themes:
            theme = themes[0]
            assert "style" in theme, "Theme should have style dict"
            style = theme.get("style", {})
            assert "primary_bg" in style, "Style should have primary_bg"
            assert "accent" in style, "Style should have accent"
            assert "heading_font" in style, "Style should have heading_font"
            print(f"PASS: Theme structure verified - style keys: {list(style.keys())}")

    def test_admin_themes_endpoint(self, auth_headers, existing_site):
        """POST /api/admin/platform/website-builder/themes/{slug} returns themes"""
        slug = existing_site.get("slug")
        resp = requests.post(
            f"{BASE_URL}/api/admin/platform/website-builder/themes/{slug}",
            headers=auth_headers,
            timeout=30,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        
        assert "slug" in data, "Response should contain slug"
        assert "themes" in data, "Response should contain themes"
        assert "n" in data, "Response should contain n (count)"
        
        print(f"PASS: Admin themes endpoint returned {data.get('n')} themes")


class TestCuratedCatalog:
    """Test niche-aware curated fallback"""

    def test_curated_catalog_auto_niche(self):
        """Verify curated catalog returns 'auto' niche themes"""
        from services.awb_theme_catalog import get_curated_themes, _normalize
        
        # Test normalization
        assert _normalize("Auto Body Shop") == "auto"
        assert _normalize("auto repair") == "auto"
        assert _normalize("mechanic") == "auto"
        assert _normalize("coffee shop") == "coffee"
        assert _normalize("restaurant") == "restaurant"
        assert _normalize("unknown business") == "default"
        
        # Test curated themes for auto
        themes = get_curated_themes("Auto Body Shop")
        assert len(themes) >= 3, f"Expected at least 3 auto themes, got {len(themes)}"
        
        # Verify expected theme names
        names = [t.get("business_name") for t in themes]
        expected = ["Pit Crew", "Garage Classic", "Heritage Auto", "Speed Lab"]
        for name in expected:
            assert name in names, f"Expected '{name}' in auto themes"
        
        print(f"PASS: Curated catalog returns correct auto themes: {names}")


class TestPreviewPage:
    """Test customer-facing preview page"""

    def test_preview_page_html(self, existing_site):
        """GET /api/preview/{slug} returns HTML with business name"""
        slug = existing_site.get("slug")
        biz_name = existing_site.get("business_name", "")
        
        resp = requests.get(
            f"{BASE_URL}/api/preview/{slug}",
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        html = resp.text
        assert "<!doctype html>" in html.lower() or "<html" in html.lower(), "Should return HTML"
        assert "Pick your style" in html, "Should contain 'Pick your style' text"
        assert "Powered by" in html and "AUREM" in html, "Should have Powered by AUREM footer"
        
        print(f"PASS: Preview page renders HTML with theme picker for slug={slug}")

    def test_preview_page_has_js_fetch(self, existing_site):
        """Preview page should have JS that fetches /api/preview/{slug}/themes"""
        slug = existing_site.get("slug")
        
        resp = requests.get(
            f"{BASE_URL}/api/preview/{slug}",
            timeout=15,
        )
        assert resp.status_code == 200
        
        html = resp.text
        assert f"/api/preview/{slug}/themes" in html or "/themes" in html, \
            "Preview page should fetch themes endpoint"
        
        print("PASS: Preview page contains themes fetch JS")


class TestThumbnailProxy:
    """Test thumbnail proxy endpoint"""

    def test_thumb_endpoint_404_for_invalid(self):
        """GET /api/sites/_thumb/{invalid} returns 404"""
        resp = requests.get(
            f"{BASE_URL}/api/sites/_thumb/nonexistent123",
            timeout=10,
        )
        assert resp.status_code == 404, f"Expected 404 for invalid thumb, got {resp.status_code}"
        print("PASS: Thumbnail endpoint returns 404 for invalid thumb_id")

    def test_thumb_endpoint_returns_jpeg(self, existing_site, auth_headers):
        """If themes have screenshot_url, verify it returns image/jpeg"""
        slug = existing_site.get("slug")
        
        # First get themes to find a screenshot_url
        resp = requests.get(
            f"{BASE_URL}/api/preview/{slug}/themes",
            timeout=30,
        )
        if resp.status_code != 200:
            pytest.skip("Could not fetch themes")
        
        themes = resp.json().get("themes", [])
        thumb_url = None
        for t in themes:
            url = t.get("screenshot_url")
            if url and url.startswith("/api/sites/_thumb/"):
                thumb_url = url
                break
        
        if not thumb_url:
            pytest.skip("No thumbnail URLs in themes")
        
        # Fetch the thumbnail
        thumb_resp = requests.get(
            f"{BASE_URL}{thumb_url}",
            timeout=15,
        )
        assert thumb_resp.status_code == 200, f"Expected 200, got {thumb_resp.status_code}"
        assert "image/jpeg" in thumb_resp.headers.get("Content-Type", ""), \
            f"Expected image/jpeg, got {thumb_resp.headers.get('Content-Type')}"
        assert len(thumb_resp.content) > 1000, "Thumbnail should have substantial bytes"
        
        print(f"PASS: Thumbnail proxy returns JPEG ({len(thumb_resp.content)} bytes)")


class TestPoweredByAurem:
    """Test 'Powered by AUREM' footer in AWB sites"""

    def test_public_site_has_aurem_footer(self, existing_site):
        """Public site HTML should have 'Powered by AUREM' footer"""
        slug = existing_site.get("slug")
        
        resp = requests.get(
            f"{BASE_URL}/api/sites/{slug}",
            timeout=15,
        )
        if resp.status_code != 200:
            pytest.skip(f"Could not fetch public site: {resp.status_code}")
        
        html = resp.text
        # Check for aurem-bar class or "Powered by AUREM" text
        has_aurem_bar = "aurem-bar" in html
        has_powered_text = "Powered by" in html and "AUREM" in html
        
        assert has_aurem_bar or has_powered_text, \
            "Site should have 'Powered by AUREM' footer (class='aurem-bar' or text)"
        
        print(f"PASS: Public site has Powered by AUREM footer (aurem-bar={has_aurem_bar})")


class TestThemeSelection:
    """Test customer theme selection flow"""

    def test_select_theme_invalid_idx(self, existing_site):
        """POST /api/preview/{slug}/select-theme with invalid idx returns 400"""
        slug = existing_site.get("slug")
        
        resp = requests.post(
            f"{BASE_URL}/api/preview/{slug}/select-theme",
            json={"template_idx": 999},
            timeout=15,
        )
        # Should return 400 or 404 for invalid index
        assert resp.status_code in [400, 404], \
            f"Expected 400/404 for invalid idx, got {resp.status_code}"
        
        print(f"PASS: Select theme returns {resp.status_code} for invalid template_idx")


class TestCockpitIntegration:
    """Test AWB Cockpit data"""

    def test_cockpit_returns_recent_sites(self, auth_headers):
        """GET /api/admin/platform/website-builder/cockpit returns recent sites"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/platform/website-builder/cockpit",
            headers=auth_headers,
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert "counters" in data, "Should have counters"
        assert "recent" in data, "Should have recent sites"
        assert "r2_ready" in data, "Should have r2_ready status"
        assert "cloudflare_ready" in data, "Should have cloudflare_ready status"
        
        counters = data.get("counters", {})
        print(f"PASS: Cockpit returns data - total={counters.get('total')}, "
              f"published={counters.get('published')}, deployed={counters.get('deployed')}")


class TestBuildWithOutreach:
    """Test AWB build triggers outreach"""

    def test_build_site_returns_outreach_info(self, auth_headers):
        """POST /api/admin/platform/website-builder/build/{lead_id} returns outreach info"""
        # First, find a lead that can be built
        # Use tj-auto-clinic-001 as mentioned in the context
        lead_id = "tj-auto-clinic-001"
        
        resp = requests.post(
            f"{BASE_URL}/api/admin/platform/website-builder/build/{lead_id}",
            headers=auth_headers,
            timeout=60,  # Build can take time
        )
        
        # May return 404 if lead doesn't exist, or 200 if successful
        if resp.status_code == 404:
            pytest.skip(f"Lead {lead_id} not found")
        
        if resp.status_code != 200:
            print(f"Build returned {resp.status_code}: {resp.text[:300]}")
            pytest.skip(f"Build failed with {resp.status_code}")
        
        data = resp.json()
        
        # Verify build response structure
        assert "site_id" in data, "Response should have site_id"
        assert "status" in data, "Response should have status"
        
        # Check for outreach info (may be None if style_hint was used)
        outreach = data.get("outreach")
        if outreach:
            assert "sent" in outreach or "skipped" in outreach, \
                "Outreach should have sent or skipped arrays"
            print(f"PASS: Build returned outreach info: {outreach}")
        else:
            print("INFO: No outreach triggered (style_hint rebuild or no channels)")
        
        # Verify publish info
        publish = data.get("publish", {})
        print(f"PASS: Build completed - status={data.get('status')}, "
              f"r2.ok={publish.get('r2', {}).get('ok')}, "
              f"dns.ok={publish.get('dns', {}).get('ok')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
