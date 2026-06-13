"""
Phase 3 Feature Tests - Scout Unified + Lead Enrichment
Tests for:
1. POST /api/scout/unified endpoint
2. POST /api/enrichment/enrich/<lead_id> endpoint
3. Health check
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


def get_admin_token():
    """Get admin token for authenticated requests"""
    login_resp = requests.post(
        f"{BASE_URL}/api/platform/auth/login",
        json={"email": "teji.ss1986@gmail.com", "password": os.environ.get("AUREM_ADMIN_PASSWORD", "")}
    )
    if login_resp.status_code == 200:
        return login_resp.json().get("token", "")
    return None


class TestScoutUnified:
    """Tests for unified scout endpoint"""
    
    def test_scout_unified_without_auth_returns_401(self):
        """POST /api/scout/unified without auth should return 401"""
        resp = requests.post(
            f"{BASE_URL}/api/scout/unified",
            json={"query": "test", "depth": "surface"}
        )
        assert resp.status_code == 401
        assert "Authentication required" in resp.json().get("detail", "")
    
    def test_scout_unified_with_auth_surface_depth(self):
        """POST /api/scout/unified with admin JWT and depth=surface should return 200"""
        token = get_admin_token()
        if not token:
            pytest.skip("Could not authenticate")
        
        resp = requests.post(
            f"{BASE_URL}/api/scout/unified",
            json={"query": "salons toronto", "depth": "surface"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"
        assert data.get("query") == "salons toronto"
        assert data.get("depth") == "surface"
    
    def test_scout_unified_empty_query_returns_400(self):
        """POST /api/scout/unified with empty query should return 400"""
        token = get_admin_token()
        if not token:
            pytest.skip("Could not authenticate")
        
        resp = requests.post(
            f"{BASE_URL}/api/scout/unified",
            json={"query": "", "depth": "surface"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 400
        assert "query" in resp.json().get("detail", "").lower()
    
    def test_scout_unified_invalid_depth_returns_400(self):
        """POST /api/scout/unified with invalid depth should return 400"""
        token = get_admin_token()
        if not token:
            pytest.skip("Could not authenticate")
        
        resp = requests.post(
            f"{BASE_URL}/api/scout/unified",
            json={"query": "test", "depth": "invalid"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 400
        assert "depth" in resp.json().get("detail", "").lower()


class TestLeadEnrichment:
    """Tests for lead enrichment endpoint"""
    
    def test_enrichment_without_auth_returns_401(self):
        """POST /api/enrichment/enrich/<lead_id> without auth should return 401"""
        resp = requests.post(f"{BASE_URL}/api/enrichment/enrich/test-lead-123")
        assert resp.status_code == 401
        assert "Authentication required" in resp.json().get("detail", "")
    
    def test_enrichment_with_auth_returns_200(self):
        """POST /api/enrichment/enrich/<lead_id> with admin JWT should be reachable"""
        token = get_admin_token()
        if not token:
            pytest.skip("Could not authenticate")
        
        resp = requests.post(
            f"{BASE_URL}/api/enrichment/enrich/test-lead-123",
            headers={"Authorization": f"Bearer {token}"}
        )
        # Should return 200 with enriched=false for non-existent lead
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"
        assert data.get("enriched") == False
        assert data.get("reason") == "lead_not_found"


class TestHealthCheck:
    """Tests for health endpoint"""
    
    def test_health_returns_200(self):
        """GET /api/health should return 200"""
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"
        # Check schedulers in checks field
        checks = data.get("checks", {})
        schedulers_status = checks.get("schedulers", "")
        assert "4/4" in schedulers_status, f"Expected 4/4 schedulers, got {schedulers_status}"
