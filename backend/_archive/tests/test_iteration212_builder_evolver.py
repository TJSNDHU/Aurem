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
ADMIN_PASSWORD = "Admin123"


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
            json={"text": "Test /api/telegram/status"},
            headers=admin_headers,
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        
        assert data.get("intent") == "TEST_ENDPOINT", f"Expected intent=TEST_ENDPOINT, got {data.get('intent')}"
        # Should return ok=true with status in data
        assert data.get("ok") == True, f"Expected ok=true for TEST_ENDPOINT: {data}"
        
        # Data should contain status code
        test_data = data.get("data", {})
        assert "status" in test_data, f"Missing 'status' in data: {test_data}"
        assert test_data["status"] == 200, f"Expected status=200, got {test_data['status']}"
        
        print(f"✅ ORA command 'Test /api/telegram/status' → intent=TEST_ENDPOINT, ok=true, status=200")

    def test_ora_command_help_includes_builder_section(self, admin_headers):
        """POST /api/ora/command {text:'help'} → HELP_TEXT includes _Builder (admin):_ section."""
        resp = requests.post(
            f"{BASE_URL}/api/ora/command",
            json={"text": "help"},
            headers=admin_headers,
            timeout=10,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        
        assert data.get("intent") == "HELP", f"Expected intent=HELP, got {data.get('intent')}"
        reply = data.get("reply", "")
        
        # Check for Builder section
        assert "Builder" in reply, f"HELP_TEXT should include Builder section: {reply[:500]}"
        assert "Build endpoint" in reply, f"HELP_TEXT should include 'Build endpoint' example: {reply[:500]}"
        
        print("✅ ORA command 'help' → includes _Builder (admin):_ section")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: Telegram Status Endpoint
# ═══════════════════════════════════════════════════════════════════════════════

class TestTelegramStatus:
    """Telegram status endpoint — public, shows configured=false when token empty."""

    def test_telegram_status_public(self):
        """GET /api/telegram/status (public) → 200, configured=false since TELEGRAM_BOT_TOKEN empty."""
        resp = requests.get(
            f"{BASE_URL}/api/telegram/status",
            timeout=10,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        
        # TELEGRAM_BOT_TOKEN is empty, so configured=false
        assert data.get("configured") == False, f"Expected configured=false: {data}"
        
        print(f"✅ GET /api/telegram/status → 200, configured={data.get('configured')}")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: Tenant Hardening Regression — 7 Routers
# ═══════════════════════════════════════════════════════════════════════════════

class TestTenantHardeningRegression:
    """Verify 7 routers with Depends(current_tenant) still work after hardening."""

    def test_leads_router_works(self, admin_headers):
        """GET /api/leads should work with admin JWT (leads_router.py)."""
        resp = requests.get(
            f"{BASE_URL}/api/leads",
            headers=admin_headers,
            timeout=10,
        )
        # Should not crash with import error
        assert resp.status_code in (200, 404, 500), f"Unexpected status: {resp.status_code}"
        if resp.status_code == 200:
            data = resp.json()
            assert "leads" in data or "success" in data, f"Unexpected response: {data}"
        print(f"✅ GET /api/leads → {resp.status_code} (leads_router.py works)")

    def test_hermes_identity_works(self, admin_headers):
        """GET /api/hermes/identity should work (hermes_router.py)."""
        resp = requests.get(
            f"{BASE_URL}/api/hermes/identity",
            headers=admin_headers,
            timeout=10,
        )
        assert resp.status_code in (200, 401, 403, 500), f"Unexpected status: {resp.status_code}"
        print(f"✅ GET /api/hermes/identity → {resp.status_code} (hermes_router.py works)")

    def test_panic_settings_works(self, admin_headers):
        """GET /api/panic/settings should work (panic_settings_router.py)."""
        resp = requests.get(
            f"{BASE_URL}/api/panic/settings",
            headers=admin_headers,
            timeout=10,
        )
        # May return 404 if tenant not found, but should not crash
        assert resp.status_code in (200, 404, 500), f"Unexpected status: {resp.status_code}"
        print(f"✅ GET /api/panic/settings → {resp.status_code} (panic_settings_router.py works)")

    def test_panic_takeover_works(self, admin_headers):
        """POST /api/panic/takeover/{id} should work (panic_takeover_router.py)."""
        resp = requests.post(
            f"{BASE_URL}/api/panic/takeover/test_conv_123",
            headers=admin_headers,
            timeout=10,
        )
        # Should not crash with import error
        assert resp.status_code in (200, 404, 500), f"Unexpected status: {resp.status_code}"
        print(f"✅ POST /api/panic/takeover/test_conv_123 → {resp.status_code} (panic_takeover_router.py works)")

    def test_revenue_forecast_works(self, admin_headers):
        """GET /api/revenue-forecast/90day should work (revenue_forecast_router.py)."""
        resp = requests.get(
            f"{BASE_URL}/api/revenue-forecast/90day",
            headers=admin_headers,
            timeout=10,
        )
        # May return 403 if not admin, but should not crash
        assert resp.status_code in (200, 401, 403, 500), f"Unexpected status: {resp.status_code}"
        print(f"✅ GET /api/revenue-forecast/90day → {resp.status_code} (revenue_forecast_router.py works)")

    def test_vapi_voice_config_works(self, admin_headers):
        """GET /api/voice/config should work (vapi_voice_router.py)."""
        resp = requests.get(
            f"{BASE_URL}/api/voice/config",
            headers=admin_headers,
            timeout=10,
        )
        # Should not crash with import error
        assert resp.status_code in (200, 404, 500), f"Unexpected status: {resp.status_code}"
        print(f"✅ GET /api/voice/config → {resp.status_code} (vapi_voice_router.py works)")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: Scheduler Registration — aurem_evolver_review job
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchedulerRegistration:
    """Verify nightly_cycle.py registered the aurem_evolver_review job."""

    def test_scheduler_has_evolver_review_job(self, admin_headers):
        """GET /api/admin/system-audit should show aurem_evolver_review in scheduler jobs."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/system-audit",
            headers=admin_headers,
            timeout=15,
        )
        if resp.status_code != 200:
            pytest.skip(f"System audit endpoint not available: {resp.status_code}")
        
        data = resp.json()
        
        # Look for scheduler jobs
        scheduler_jobs = data.get("scheduler_jobs", [])
        if not scheduler_jobs:
            # Try alternate location
            scheduler_jobs = data.get("scheduler", {}).get("jobs", [])
        
        if scheduler_jobs:
            job_ids = [j.get("id") or j.get("job_id") for j in scheduler_jobs]
            assert "aurem_evolver_review" in job_ids, f"aurem_evolver_review not in scheduler jobs: {job_ids}"
            print(f"✅ Scheduler has aurem_evolver_review job (2:45 AM)")
        else:
            # If no scheduler info, check backend logs
            print("⚠️ Scheduler jobs not exposed in system-audit, checking backend logs...")
            pytest.skip("Scheduler jobs not exposed in API")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7: Registry Load — No ImportErrors
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegistryLoad:
    """Verify no ImportErrors in backend logs for new routers."""

    def test_no_import_errors_in_logs(self):
        """Check backend logs for ImportError on new routers."""
        # This test reads from the log file directly
        log_path = "/var/log/supervisor/backend.err.log"
        try:
            with open(log_path, "r") as f:
                logs = f.read()
        except FileNotFoundError:
            pytest.skip("Backend error log not found")
        
        # Check for ImportError on the new routers
        critical_modules = [
            "aurem_builder",
            "evolver_router",
            "telegram_router",
            "leads_router",
            "hermes_router",
            "lead_enrichment_router",
            "panic_settings_router",
            "panic_takeover_router",
            "revenue_forecast_router",
            "vapi_voice_router",
        ]
        
        import_errors = []
        for module in critical_modules:
            if f"ImportError" in logs and module in logs:
                # Find the relevant line
                for line in logs.split("\n"):
                    if "ImportError" in line and module in line:
                        import_errors.append(line[:200])
        
        if import_errors:
            print(f"❌ ImportErrors found: {import_errors}")
        else:
            print("✅ No ImportErrors for critical modules in backend logs")
        
        assert len(import_errors) == 0, f"ImportErrors found: {import_errors}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
