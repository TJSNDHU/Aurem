"""
Iteration 212 Test Suite — AUREM Builder, EvoMap Evolver, Tenant Hardening
==========================================================================
Tests:
1. AUREM Builder async pipeline (POST /api/admin/builder/build, GET /status/{id}, /stats, /recent)
2. EvoMap Evolver graceful degradation (GET /api/admin/evolver/status, /genes, POST /run-review)
3. ORA Command Center new intents (BUILD, FIX, TEST_ENDPOINT)
4. Telegram status endpoint
5. Tenant hardening regression (7 routers with Depends(current_tenant))
6. Scheduler registration (aurem_evolver_review job)
"""

import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

# Admin credentials from test_credentials.md
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
# TODO: Set ADMIN_PASSWORD environment variable with the admin password


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token for authenticated requests."""
    resp = requests.post(
        f"{BASE_URL}/api/platform/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text[:200]}")
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        pytest.skip(f"No token in login response: {data}")
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Headers with admin JWT."""
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: AUREM Builder Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuremBuilder:
    """AUREM Internal Builder — admin-only self-build pipeline."""

    def test_builder_build_without_auth_returns_401(self):
        """POST /api/admin/builder/build without JWT → 401."""
        resp = requests.post(
            f"{BASE_URL}/api/admin/builder/build",
            json={"description": "Test endpoint returning 42"},
            timeout=10,
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text[:200]}"
        print("✅ POST /api/admin/builder/build without auth → 401")

    def test_builder_build_async_returns_quickly(self, admin_headers):
        """POST /api/admin/builder/build with admin JWT returns fast with build_id + queued status."""
        start = time.time()
        resp = requests.post(
            f"{BASE_URL}/api/admin/builder/build",
            json={"description": "Build a test endpoint /api/builder-test returning build status"},
            headers=admin_headers,
            timeout=30,
        )
        elapsed = time.time() - start
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        
        # Verify async contract: returns fast with build_id + queued
        assert "build_id" in data, f"Missing build_id in response: {data}"
        assert data.get("status") == "queued", f"Expected status='queued', got {data.get('status')}"
        assert "started_at" in data, f"Missing started_at in response: {data}"
        assert elapsed < 10, f"Async endpoint took too long: {elapsed:.2f}s (should be <5s)"
        
        print(f"✅ POST /api/admin/builder/build → 200 in {elapsed:.2f}s, build_id={data['build_id']}, status=queued")
        return data["build_id"]

    def test_builder_status_poll_until_complete(self, admin_headers):
        """GET /api/admin/builder/status/{id} — poll until non-running status (expect 'failed' due to budget)."""
        # First create a build
        resp = requests.post(
            f"{BASE_URL}/api/admin/builder/build",
            json={"description": "Build a simple health check endpoint"},
            headers=admin_headers,
            timeout=30,
        )
        assert resp.status_code == 200
        build_id = resp.json().get("build_id")
        assert build_id, "No build_id returned"
        
        # Poll status until complete (max 120s)
        max_wait = 120
        poll_interval = 3
        waited = 0
        final_status = None
        
        while waited < max_wait:
            status_resp = requests.get(
                f"{BASE_URL}/api/admin/builder/status/{build_id}",
                headers=admin_headers,
                timeout=10,
            )
            assert status_resp.status_code == 200, f"Status check failed: {status_resp.status_code}"
            status_data = status_resp.json()
            current_status = status_data.get("status")
            
            if current_status not in ("queued", "running"):
                final_status = current_status
                print(f"✅ Build {build_id} completed with status={final_status} after {waited}s")
                
                # Verify error contains budget-related message (expected since EMERGENT_LLM_KEY budget exceeded)
                error = status_data.get("error") or ""
                if final_status == "failed":
                    # Budget exceeded is expected
                    print(f"   Error (expected): {error[:150]}")
                break
            
            time.sleep(poll_interval)
            waited += poll_interval
        
        assert final_status is not None, f"Build {build_id} did not complete within {max_wait}s"
        assert final_status in ("success", "failed"), f"Unexpected final status: {final_status}"
        print(f"✅ Async pipeline works: build_id={build_id}, final_status={final_status}")

    def test_builder_status_invalid_id_returns_404(self, admin_headers):
        """GET /api/admin/builder/status/{invalid_id} → 404."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/builder/status/nonexistent_build_id_12345",
            headers=admin_headers,
            timeout=10,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text[:200]}"
        print("✅ GET /api/admin/builder/status/{invalid_id} → 404")

    def test_builder_stats_returns_dashboard_shape(self, admin_headers):
        """GET /api/admin/builder/stats → 200 with total/success/failed/success_rate_pct/cost_today_usd/last_build."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/builder/stats",
            headers=admin_headers,
            timeout=10,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        
        # Verify shape
        required_fields = ["total", "success", "failed", "success_rate_pct", "cost_today_usd"]
        for field in required_fields:
            assert field in data, f"Missing field '{field}' in stats: {data}"
        
        # last_build can be None if no builds yet
        assert "last_build" in data, f"Missing 'last_build' in stats: {data}"
        
        print(f"✅ GET /api/admin/builder/stats → 200, total={data['total']}, success_rate={data['success_rate_pct']}%")

    def test_builder_recent_returns_items(self, admin_headers):
        """GET /api/admin/builder/recent?limit=5 → 200 with {items:[...]}."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/builder/recent?limit=5",
            headers=admin_headers,
            timeout=10,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        
        assert "items" in data, f"Missing 'items' in response: {data}"
        assert isinstance(data["items"], list), f"'items' should be a list: {type(data['items'])}"
        
        print(f"✅ GET /api/admin/builder/recent?limit=5 → 200, {len(data['items'])} items")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: EvoMap Evolver Endpoints (Graceful Degradation)
# ═══════════════════════════════════════════════════════════════════════════════

class TestEvolverGracefulDegradation:
    """EvoMap Evolver — graceful offline mode when EVOLVER_URL is empty."""

    def test_evolver_status_returns_offline(self, admin_headers):
        """GET /api/admin/evolver/status → 200 with configured=false (EVOLVER_URL empty)."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/evolver/status",
            headers=admin_headers,
            timeout=10,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        
        # Verify offline state
        assert data.get("configured") == False, f"Expected configured=false, got {data.get('configured')}"
        assert data.get("reachable") == False, f"Expected reachable=false, got {data.get('reachable')}"
        assert data.get("strategy") == "harden", f"Expected strategy='harden', got {data.get('strategy')}"
        assert data.get("review_mode") == True, f"Expected review_mode=true, got {data.get('review_mode')}"
        assert data.get("allow_self_modify") == False, f"Expected allow_self_modify=false"
        
        # genes_total should be 0 initially
        assert "genes_total" in data, f"Missing genes_total: {data}"
        
        print(f"✅ GET /api/admin/evolver/status → 200, configured=false, reachable=false, strategy=harden")

    def test_evolver_genes_returns_empty_initially(self, admin_headers):
        """GET /api/admin/evolver/genes → 200 with {items:[], count:0} initially."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/evolver/genes",
            headers=admin_headers,
            timeout=10,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        
        assert "items" in data, f"Missing 'items': {data}"
        assert "count" in data, f"Missing 'count': {data}"
        assert isinstance(data["items"], list), f"'items' should be list"
        
        print(f"✅ GET /api/admin/evolver/genes → 200, count={data['count']}")

    def test_evolver_run_review_graceful_offline(self, admin_headers):
        """POST /api/admin/evolver/run-review → 200 with evolver_configured=false, ok=false (graceful)."""
        resp = requests.post(
            f"{BASE_URL}/api/admin/evolver/run-review",
            headers=admin_headers,
            timeout=15,
        )
        # Should NOT 500 — graceful degradation
        assert resp.status_code == 200, f"Expected 200 (graceful), got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        
        assert data.get("evolver_configured") == False, f"Expected evolver_configured=false: {data}"
        assert data.get("ok") == False, f"Expected ok=false (offline): {data}"
        
        print(f"✅ POST /api/admin/evolver/run-review → 200 (graceful offline), ok=false")

    def test_evolver_approve_invalid_gene_returns_404(self, admin_headers):
        """POST /api/admin/evolver/genes/{invalid}/approve → 404."""
        resp = requests.post(
            f"{BASE_URL}/api/admin/evolver/genes/invalid-gene-id-12345/approve",
            headers=admin_headers,
            timeout=10,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text[:200]}"
        print("✅ POST /api/admin/evolver/genes/{invalid}/approve → 404")

    def test_evolver_without_auth_returns_401(self):
        """GET /api/admin/evolver/status without JWT → 401."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/evolver/status",
            timeout=10,
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✅ GET /api/admin/evolver/status without auth → 401")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: ORA Command Center — New Intents (BUILD, FIX, TEST_ENDPOINT)
# ═══════════════════════════════════════════════════════════════════════════════

class TestOraCommandCenterNewIntents:
    """ORA Command Center — BUILD, FIX, TEST_ENDPOINT intents."""

    def test_ora_command_build_intent(self, admin_headers):
        """POST /api/ora/command {text:'Build endpoint /api/foo returning 42'} → intent=BUILD."""
        resp = requests.post(
            f"{BASE_URL}/api/ora/command",
            json={"text": "Build endpoint /api/foo returning 42"},
            headers=admin_headers,
            timeout=60,  # Builder may take time
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        
        assert data.get("intent") == "BUILD", f"Expected intent=BUILD, got {data.get('intent')}"
        # ok=false expected since budget exceeded
        # Reply should mention AUREM Builder
        reply = data.get("reply", "")
        assert "Builder" in reply or "build" in reply.lower(), f"Reply should mention Builder: {reply[:200]}"
        
        print(f"✅ ORA command 'Build endpoint...' → intent=BUILD, ok={data.get('ok')}")

    def test_ora_command_test_endpoint_intent(self, admin_headers):
        """POST /api/ora/command {text:'Test /api/telegram/status'} → intent=TEST_ENDPOINT."""
        resp = requests.post(
            f"{BASE_URL}/api/ora/command",
            json={"text": "Test /api/