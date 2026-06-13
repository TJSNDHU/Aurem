"""
Iteration 275 — Endpoint Governance / Evidence Classifier Tests
================================================================
Tests for the new endpoint-audit module that classifies all 1,700+ backend
endpoints by Dignity (Alive/Ghost/Leaky/Dead) and Tier (T0-T4).

Endpoints tested:
- GET /api/admin/pillars-map/endpoint-audit/health — public health check
- GET /api/admin/pillars-map/endpoint-audit/summary — admin-only summary
- GET /api/admin/pillars-map/endpoint-audit — admin-only full report
- POST /api/admin/pillars-map/endpoint-audit/invalidate — admin-only cache clear
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token for authenticated requests."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15
    )
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.status_code}")
    return response.json().get("token")


@pytest.fixture
def auth_headers(admin_token):
    """Return headers with admin bearer token."""
    return {"Authorization": f"Bearer {admin_token}"}


class TestEndpointAuditHealth:
    """Health endpoint tests (no auth required)."""

    def test_health_returns_200(self):
        """GET /endpoint-audit/health returns 200 with status ok."""
        response = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/endpoint-audit/health",
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["component"] == "endpoint-audit"
        assert "db_ready" in data


class TestEndpointAuditAuth:
    """Authentication tests — all 3 protected endpoints return 401 without token."""

    def test_summary_requires_auth(self):
        """GET /endpoint-audit/summary returns 401 without bearer token."""
        response = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/endpoint-audit/summary",
            timeout=10
        )
        assert response.status_code == 401
        assert "Missing bearer token" in response.json().get("detail", "")

    def test_full_report_requires_auth(self):
        """GET /endpoint-audit returns 401 without bearer token."""
        response = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/endpoint-audit",
            timeout=10
        )
        assert response.status_code == 401
        assert "Missing bearer token" in response.json().get("detail", "")

    def test_invalidate_requires_auth(self):
        """POST /endpoint-audit/invalidate returns 401 without bearer token."""
        response = requests.post(
            f"{BASE_URL}/api/admin/pillars-map/endpoint-audit/invalidate",
            timeout=10
        )
        assert response.status_code == 401
        assert "Missing bearer token" in response.json().get("detail", "")


class TestEndpointAuditSummary:
    """Summary endpoint tests (admin-only)."""

    def test_summary_returns_200(self, auth_headers):
        """GET /endpoint-audit/summary returns 200 with valid structure."""
        response = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/endpoint-audit/summary",
            headers=auth_headers,
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        
        # Required top-level fields
        assert "generated_at" in data
        assert "cached" in data
        assert "totals" in data
        assert "tier_summary" in data

    def test_summary_totals_structure(self, auth_headers):
        """Summary totals has required fields with correct types."""
        response = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/endpoint-audit/summary",
            headers=auth_headers,
            timeout=30
        )
        assert response.status_code == 200
        totals = response.json()["totals"]
        
        # Required totals fields
        assert totals["endpoints"] >= 1700, f"Expected ≥1700 endpoints, got {totals['endpoints']}"
        assert totals["with_audit"] > 0, "Expected with_audit > 0"
        assert totals["with_surface"] > 0, "Expected with_surface > 0"
        assert totals["distinct_tiers"] > 0, "Expected distinct_tiers > 0"
        
        # Dignity breakdown
        by_dignity = totals["by_dignity"]
        assert "alive" in by_dignity
        assert "ghost" in by_dignity
        assert "leaky" in by_dignity
        assert "dead" in by_dignity
        
        # Sum of dignity should equal total endpoints
        dignity_sum = sum(by_dignity.values())
        assert dignity_sum == totals["endpoints"], f"Dignity sum {dignity_sum} != endpoints {totals['endpoints']}"

    def test_summary_tier_summary_structure(self, auth_headers):
        """Tier summary has required tiers with correct structure."""
        response = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/endpoint-audit/summary",
            headers=auth_headers,
            timeout=30
        )
        assert response.status_code == 200
        tier_summary = response.json()["tier_summary"]
        
        # Should have multiple tiers
        assert len(tier_summary) >= 4, f"Expected ≥4 tiers, got {len(tier_summary)}"
        
        # Check required tiers exist
        tier_names = [t["tier"] for t in tier_summary]
        required_tiers = ["T1_P1_acquisition", "T1_P4_cognition", "T0_infra", "T4_unclassified"]
        for required in required_tiers:
            assert required in tier_names, f"Missing required tier: {required}"
        
        # Check tier row structure
        for tier in tier_summary:
            assert "tier" in tier
            assert "endpoint_count" in tier
            assert "dignity" in tier
            assert "total_hits_30d" in tier
            assert "top_routers" in tier
            
            # Dignity breakdown per tier
            assert "alive" in tier["dignity"]
            assert "ghost" in tier["dignity"]
            assert "leaky" in tier["dignity"]
            assert "dead" in tier["dignity"]


class TestEndpointAuditFullReport:
    """Full report endpoint tests (admin-only)."""

    def test_full_report_returns_200(self, auth_headers):
        """GET /endpoint-audit returns 200 with endpoints array."""
        response = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/endpoint-audit",
            headers=auth_headers,
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        
        # Required fields
        assert "generated_at" in data
        assert "cached" in data
        assert "totals" in data
        assert "tier_summary" in data
        assert "endpoints" in data
        
        # Endpoints array should have items
        assert len(data["endpoints"]) >= 1700, f"Expected ≥1700 endpoints, got {len(data['endpoints'])}"

    def test_endpoint_structure(self, auth_headers):
        """Each endpoint has required fields."""
        response = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/endpoint-audit",
            headers=auth_headers,
            timeout=60
        )
        assert response.status_code == 200
        endpoints = response.json()["endpoints"]
        
        # Check first 5 endpoints for structure
        for ep in endpoints[:5]:
            assert "router" in ep
            assert "method" in ep
            assert "path" in ep
            assert "tier" in ep
            assert "audit" in ep
            assert "surfaces" in ep
            assert "signals" in ep
            assert "dignity" in ep
            
            # Audit structure
            audit = ep["audit"]
            assert "hits_30d" in audit
            assert "last_hit" in audit
            assert "err_30d" in audit
            
            # Signals structure
            signals = ep["signals"]
            assert "activity" in signals
            assert "surface" in signals
            assert "data" in signals
            assert "scheduler" in signals
            
            # Dignity is one of 4 values
            assert ep["dignity"] in ["alive", "ghost", "leaky", "dead"]


class TestEndpointAuditCache:
    """Cache behavior tests."""

    def test_cache_works(self, auth_headers):
        """Second call within 5 min returns cached:true with cache_age_seconds."""
        # First call (may or may not be cached)
        response1 = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/endpoint-audit/summary",
            headers=auth_headers,
            timeout=30
        )
        assert response1.status_code == 200
        
        # Second call should be cached
        response2 = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/endpoint-audit/summary",
            headers=auth_headers,
            timeout=30
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["cached"] is True

    def test_invalidate_clears_cache(self, auth_headers):
        """POST /invalidate clears cache, next call returns cached:false."""
        # Invalidate cache
        inv_response = requests.post(
            f"{BASE_URL}/api/admin/pillars-map/endpoint-audit/invalidate",
            headers=auth_headers,
            timeout=10
        )
        assert inv_response.status_code == 200
        inv_data = inv_response.json()
        assert inv_data["ok"] is True
        
        # Next call should not be cached
        response = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/endpoint-audit/summary",
            headers=auth_headers,
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        assert data["cached"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
