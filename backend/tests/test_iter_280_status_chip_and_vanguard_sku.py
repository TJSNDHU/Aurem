"""
iter 280 regression tests — SystemStatusChip + Vanguard $49/mo SKU.

Covers:
  1. SystemStatusChip visibility: hidden on public pages, visible on authenticated pages
  2. SystemStatusChip data: shows git-SHA from /api/health, uptime, pulse dot from /api/admin/pillars-map/overview
  3. Chip click navigates to /admin/pillars-map
  4. Vanguard SKU in public catalog: service_id='security_vanguard', price_monthly=49.0, cluster='security'
  5. Vanguard SKU DB integrity: cost_monthly=3, margin_pct≈93.9
  6. AdminVanguard page CTA: data-testid='vanguard-revenue-cta' with subscribe/catalog links
  7. Stripe subscribe endpoint accepts security_vanguard SKU
  8. No regression on existing endpoints
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import requests


BACKEND_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "http://localhost:8001",
)
API = f"{BACKEND_URL.rstrip('/')}/api"

TEST_ADMIN_EMAIL = "teji.ss1986@gmail.com"
TEST_ADMIN_PASSWORD = "<REDACTED>"
TEST_PLATFORM_EMAIL = "futuristic_test@aurem-preview.com"
TEST_PLATFORM_PASSWORD = "FutureTest123!"


@pytest.fixture(scope="module")
def admin_token() -> str:
    """Get admin JWT token."""
    r = requests.post(
        f"{API}/auth/login",
        json={"email": TEST_ADMIN_EMAIL, "password": TEST_ADMIN_PASSWORD},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"Login did not return a token: {data}"
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def platform_token() -> str:
    """Get platform user JWT token."""
    r = requests.post(
        f"{API}/platform/auth/login",
        json={"email": TEST_PLATFORM_EMAIL, "password": TEST_PLATFORM_PASSWORD},
        timeout=10,
    )
    r.raise_for_status()
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    assert tok, f"Platform login did not return a token: {data}"
    return tok


@pytest.fixture(scope="module")
def platform_headers(platform_token: str) -> dict:
    return {"Authorization": f"Bearer {platform_token}"}


# ═══════════════════════════════════════════════════════════════════
# Part A — SystemStatusChip Backend Data Sources
# ═══════════════════════════════════════════════════════════════════

class TestSystemStatusChipBackend:
    """Verify backend endpoints that feed the SystemStatusChip."""

    def test_health_endpoint_returns_version(self):
        """GET /api/health must return 'v' field with git-SHA."""
        r = requests.get(f"{API}/health", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "v" in d, "Health endpoint missing 'v' field"
        assert d["v"].startswith("git-"), f"Version should start with 'git-', got {d['v']}"
        assert "uptime_seconds" in d, "Health endpoint missing 'uptime_seconds'"
        assert d["uptime_seconds"] >= 0

    def test_pillars_map_overview_returns_pillars(self, admin_headers):
        """GET /api/admin/pillars-map/overview must return pillars array for pulse dot."""
        r = requests.get(
            f"{API}/admin/pillars-map/overview",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200
        d = r.json()
        assert "pillars" in d, "Overview missing 'pillars' array"
        assert isinstance(d["pillars"], list)
        assert len(d["pillars"]) > 0, "No pillars returned"
        # Each pillar should have status
        for p in d["pillars"]:
            assert "status" in p or "overall" in p, f"Pillar missing status: {p}"


# ═══════════════════════════════════════════════════════════════════
# Part B — SystemStatusChip Frontend Component
# ═══════════════════════════════════════════════════════════════════

class TestSystemStatusChipFrontend:
    """Verify SystemStatusChip.jsx implementation."""

    CHIP_FILE = Path("/app/frontend/src/platform/SystemStatusChip.jsx")
    APP_FILE = Path("/app/frontend/src/App.js")

    def test_chip_component_exists(self):
        """SystemStatusChip.jsx must exist."""
        assert self.CHIP_FILE.exists(), "SystemStatusChip.jsx not found"

    def test_chip_has_data_testid(self):
        """Chip must have data-testid='system-status-chip'."""
        src = self.CHIP_FILE.read_text()
        assert 'data-testid="system-status-chip"' in src

    def test_chip_polls_health_endpoint(self):
        """Chip must poll /api/health for version and uptime."""
        src = self.CHIP_FILE.read_text()
        assert "/api/health" in src

    def test_chip_polls_pillars_overview(self):
        """Chip must poll /api/admin/pillars-map/overview for pulse dot."""
        src = self.CHIP_FILE.read_text()
        assert "/api/admin/pillars-map/overview" in src

    def test_chip_navigates_to_pillars_map(self):
        """Chip click must navigate to /admin/pillars-map."""
        src = self.CHIP_FILE.read_text()
        assert '"/admin/pillars-map"' in src

    def test_chip_hides_on_public_pages(self):
        """Chip must hide on /, /login, /register, /privacy, /terms."""
        src = self.CHIP_FILE.read_text()
        for path in ["/", "/login", "/register", "/privacy", "/terms"]:
            assert f'"{path}"' in src, f"Public path {path} not in hideOnPublic list"

    def test_chip_mounted_in_app_js(self):
        """SystemStatusChip must be imported and mounted in App.js."""
        src = self.APP_FILE.read_text()
        assert "SystemStatusChip" in src
        assert "import('./platform/SystemStatusChip')" in src or "SystemStatusChip" in src


# ═══════════════════════════════════════════════════════════════════
# Part C — Vanguard SKU in Public Catalog
# ═══════════════════════════════════════════════════════════════════

class TestVanguardSKUCatalog:
    """Verify security_vanguard SKU is in public catalog."""

    def test_catalog_returns_23_services(self):
        """GET /api/catalog/services must return 23 live services."""
        r = requests.get(f"{API}/catalog/services", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "services" in d
        assert len(d["services"]) == 23, f"Expected 23 services, got {len(d['services'])}"

    def test_security_vanguard_in_catalog(self):
        """security_vanguard must be in public catalog with correct fields."""
        r = requests.get(f"{API}/catalog/services", timeout=10)
        assert r.status_code == 200
        services = r.json()["services"]
        
        vanguard = next((s for s in services if s["service_id"] == "security_vanguard"), None)
        assert vanguard is not None, "security_vanguard not found in catalog"
        
        # Verify required fields
        assert vanguard["price_monthly"] == 49.0, f"Expected price_monthly=49.0, got {vanguard['price_monthly']}"
        assert vanguard["cluster"] == "security", f"Expected cluster=security, got {vanguard['cluster']}"
        assert vanguard["billing_type"] == "recurring", f"Expected billing_type=recurring, got {vanguard['billing_type']}"
        assert vanguard["status"] == "live", f"Expected status=live, got {vanguard['status']}"
        assert vanguard["backend_service"] == "aurem_vanguard_router.py"

    def test_vanguard_has_dependencies(self):
        """security_vanguard must have primitive_audit dependency."""
        r = requests.get(f"{API}/catalog/services", timeout=10)
        services = r.json()["services"]
        vanguard = next((s for s in services if s["service_id"] == "security_vanguard"), None)
        
        assert "dependencies" in vanguard
        assert "primitive_audit" in vanguard["dependencies"]


# ═══════════════════════════════════════════════════════════════════
# Part D — Vanguard SKU DB Integrity
# ═══════════════════════════════════════════════════════════════════

class TestVanguardSKUDBIntegrity:
    """Verify security_vanguard DB document has correct cost and margin."""

    def test_vanguard_db_cost_and_margin(self, admin_headers):
        """Admin catalog must show cost_monthly=3, margin_pct≈93.9."""
        r = requests.get(f"{API}/admin/catalog", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        d = r.json()
        
        services = d.get("services", [])
        vanguard = next((s for s in services if s["service_id"] == "security_vanguard"), None)
        assert vanguard is not None, "security_vanguard not found in admin catalog"
        
        assert vanguard["cost_monthly"] == 3.0, f"Expected cost_monthly=3.0, got {vanguard['cost_monthly']}"
        assert vanguard["price_monthly"] == 49.0, f"Expected price_monthly=49.0, got {vanguard['price_monthly']}"
        
        # Margin should be (49-3)/49 * 100 = 93.877... ≈ 93.9
        expected_margin = round(((49.0 - 3.0) / 49.0) * 100, 1)
        assert abs(vanguard["margin_pct"] - expected_margin) < 0.2, (
            f"Expected margin_pct≈{expected_margin}, got {vanguard['margin_pct']}"
        )


# ═══════════════════════════════════════════════════════════════════
# Part E — AdminVanguard Page CTA
# ═══════════════════════════════════════════════════════════════════

class TestAdminVanguardCTA:
    """Verify AdminVanguard.jsx has revenue CTA with correct links."""

    VANGUARD_FILE = Path("/app/frontend/src/platform/AdminVanguard.jsx")

    def test_vanguard_page_exists(self):
        """AdminVanguard.jsx must exist."""
        assert self.VANGUARD_FILE.exists()

    def test_revenue_cta_testid(self):
        """Page must have data-testid='vanguard-revenue-cta'."""
        src = self.VANGUARD_FILE.read_text()
        assert 'data-testid="vanguard-revenue-cta"' in src

    def test_subscribe_link_testid(self):
        """CTA must have data-testid='vanguard-subscribe-link' pointing to /my/website."""
        src = self.VANGUARD_FILE.read_text()
        assert 'data-testid="vanguard-subscribe-link"' in src
        assert 'href="/my/website"' in src

    def test_catalog_link_testid(self):
        """CTA must have data-testid='vanguard-catalog-link' pointing to /admin/catalog."""
        src = self.VANGUARD_FILE.read_text()
        assert 'data-testid="vanguard-catalog-link"' in src
        assert 'href="/admin/catalog"' in src

    def test_cta_mentions_49_price(self):
        """CTA must mention $49/mo price."""
        src = self.VANGUARD_FILE.read_text()
        assert "$49/mo" in src or "$49" in src

    def test_cta_mentions_security_vanguard(self):
        """CTA must mention security_vanguard service_id."""
        src = self.VANGUARD_FILE.read_text()
        assert "security_vanguard" in src


# ═══════════════════════════════════════════════════════════════════
# Part F — Stripe Subscribe Endpoint
# ═══════════════════════════════════════════════════════════════════

class TestStripeSubscribeEndpoint:
    """Verify POST /api/customer/subscriptions/subscribe accepts security_vanguard."""

    def test_subscribe_returns_checkout_url(self, platform_headers):
        """Subscribe to security_vanguard must return Stripe checkout URL."""
        r = requests.post(
            f"{API}/customer/subscriptions/subscribe",
            json={
                "service_id": "security_vanguard",
                "origin_url": BACKEND_URL,
            },
            headers=platform_headers,
            timeout=30,
        )
        # 200 = new checkout, 409 = already subscribed (both are valid)
        assert r.status_code in [200, 409], f"Unexpected status {r.status_code}: {r.text[:200]}"
        
        if r.status_code == 200:
            d = r.json()
            assert "url" in d, "Response missing 'url' field"
            assert "session_id" in d, "Response missing 'session_id'"
            assert "checkout.stripe.com" in d["url"], "URL should be Stripe checkout"
            print(f"✓ Stripe checkout URL created: {d['url'][:80]}...")
        else:
            # 409 = already subscribed, which is fine
            print("✓ Already subscribed to security_vanguard (409)")

    def test_subscribe_invalid_service_404(self, platform_headers):
        """Subscribe to nonexistent service must return 404."""
        r = requests.post(
            f"{API}/customer/subscriptions/subscribe",
            json={"service_id": "nonexistent_service_xyz"},
            headers=platform_headers,
            timeout=10,
        )
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Part G — No Regression on Existing Endpoints
# ═══════════════════════════════════════════════════════════════════

class TestNoRegression:
    """Verify existing endpoints still work."""

    def test_health_endpoint_200(self):
        """GET /api/health must return 200."""
        r = requests.get(f"{API}/health", timeout=10)
        assert r.status_code == 200

    def test_pillars_map_overview_200(self, admin_headers):
        """GET /api/admin/pillars-map/overview must return 200."""
        r = requests.get(
            f"{API}/admin/pillars-map/overview",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200

    def test_vanguard_subproduct_200(self, admin_headers):
        """GET /api/admin/pillars-map/subproduct/T2_subproduct_vanguard must return 200."""
        r = requests.get(
            f"{API}/admin/pillars-map/subproduct/T2_subproduct_vanguard",
            headers=admin_headers,
            timeout=30,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["endpoint_count"] >= 6

    def test_catalog_services_200(self):
        """GET /api/catalog/services must return 200."""
        r = requests.get(f"{API}/catalog/services", timeout=10)
        assert r.status_code == 200

    def test_admin_catalog_200(self, admin_headers):
        """GET /api/admin/catalog must return 200."""
        r = requests.get(f"{API}/admin/catalog", headers=admin_headers, timeout=10)
        assert r.status_code == 200
