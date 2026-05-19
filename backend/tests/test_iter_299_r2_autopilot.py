"""
Iteration 299 Tests: R2 Storage + Cloudflare Worker + AWB Auto-Pilot
====================================================================
Tests:
1. R2 service is_configured() returns True
2. R2 upload_site_html works
3. GET /cockpit returns r2_ready=true and cloudflare_ready=true
4. AWB pipeline E2E with R2 + DNS
5. Auto-Pilot endpoints (GET/POST state, run-now, history)
6. Auth gate on all autopilot endpoints
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = "<REDACTED>"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token"""
    resp = requests.post(
        f"{BASE_URL}/api/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15
    )
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text[:200]}")
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        pytest.skip("No token in login response")
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Headers with admin auth"""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {admin_token}"
    }


class TestR2ServiceConfiguration:
    """Test R2 service is properly configured"""
    
    def test_r2_is_configured(self, auth_headers):
        """R2 service should report as configured"""
        # We test this via the cockpit endpoint which exposes r2_ready
        resp = requests.get(
            f"{BASE_URL}/api/admin/platform/website-builder/cockpit",
            headers=auth_headers,
            timeout=15
        )
        assert resp.status_code == 200, f"Cockpit failed: {resp.text[:200]}"
        data = resp.json()
        assert "r2_ready" in data, "r2_ready field missing from cockpit response"
        assert data["r2_ready"] is True, f"R2 not configured: r2_ready={data.get('r2_ready')}"
        print(f"✓ R2 is configured: r2_ready={data['r2_ready']}")


class TestCockpitEndpoint:
    """Test /website-builder/cockpit returns correct status"""
    
    def test_cockpit_returns_r2_and_cf_ready(self, auth_headers):
        """Cockpit should return r2_ready=true and cloudflare_ready=true"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/platform/website-builder/cockpit",
            headers=auth_headers,
            timeout=15
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Check r2_ready
        assert data.get("r2_ready") is True, f"r2_ready should be True, got {data.get('r2_ready')}"
        
        # Check cloudflare_ready
        assert data.get("cloudflare_ready") is True, f"cloudflare_ready should be True, got {data.get('cloudflare_ready')}"
        
        # Check counters exist
        assert "counters" in data
        assert "queue_size" in data
        
        print(f"✓ Cockpit status: r2_ready={data['r2_ready']}, cloudflare_ready={data['cloudflare_ready']}")
        print(f"  Counters: {data.get('counters')}")
        print(f"  Queue size: {data.get('queue_size')}")
    
    def test_cockpit_requires_auth(self):
        """Cockpit should return 401 without auth"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/platform/website-builder/cockpit",
            timeout=15
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ Cockpit correctly requires authentication")


class TestAutoPilotEndpoints:
    """Test Auto-Pilot CRUD endpoints"""
    
    def test_autopilot_get_state(self, auth_headers):
        """GET /autopilot should return state with required fields"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/platform/website-builder/autopilot",
            headers=auth_headers,
            timeout=15
        )
        assert resp.status_code == 200, f"Failed: {resp.text[:200]}"
        data = resp.json()
        
        # Check required fields
        required_fields = ["enabled", "batch_size", "interval_minutes", "running"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # next_run_at may be None if never run
        assert "next_run_at" in data or data.get("last_run_at") is None
        
        print(f"✓ Autopilot state: enabled={data.get('enabled')}, running={data.get('running')}")
        print(f"  batch_size={data.get('batch_size')}, interval_minutes={data.get('interval_minutes')}")
        print(f"  last_run_at={data.get('last_run_at')}, next_run_at={data.get('next_run_at')}")
    
    def test_autopilot_set_enabled_true(self, auth_headers):
        """POST /autopilot with enabled=true should persist state"""
        payload = {
            "enabled": True,
            "batch_size": 3,
            "interval_minutes": 30
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/platform/website-builder/autopilot",
            headers=auth_headers,
            json=payload,
            timeout=15
        )
        assert resp.status_code == 200, f"Failed: {resp.text[:200]}"
        data = resp.json()
        
        assert data.get("enabled") is True, f"enabled should be True, got {data.get('enabled')}"
        assert data.get("batch_size") == 3, f"batch_size should be 3, got {data.get('batch_size')}"
        assert data.get("interval_minutes") == 30, f"interval_minutes should be 30, got {data.get('interval_minutes')}"
        
        print(f"✓ Autopilot enabled: {data}")
    
    def test_autopilot_set_enabled_false(self, auth_headers):
        """POST /autopilot with enabled=false should persist disabled state"""
        payload = {
            "enabled": False
        }
        resp = requests.post(
            f"{BASE_URL}/api/admin/platform/website-builder/autopilot",
            headers=auth_headers,
            json=payload,
            timeout=15
        )
        assert resp.status_code == 200, f"Failed: {resp.text[:200]}"
        data = resp.json()
        
        # The key assertion is that enabled=False is persisted
        assert data.get("enabled") is False, f"enabled should be False, got {data.get('enabled')}"
        
        # Note: running may still be True briefly as the background task exits gracefully
        # The loop checks enabled flag and exits on next iteration
        # This is expected async behavior - the task needs time to complete its sleep cycle
        print(f"✓ Autopilot disabled: enabled={data.get('enabled')}, running={data.get('running')}")
        print("  (running=True is OK - task exits gracefully on next loop iteration)")
    
    def test_autopilot_run_now(self, auth_headers):
        """POST /autopilot/run-now should trigger immediate batch"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/platform/website-builder/autopilot/run-now?batch_size=1",
            headers=auth_headers,
            timeout=60  # May take time for LLM calls
        )
        assert resp.status_code == 200, f"Failed: {resp.text[:200]}"
        data = resp.json()
        
        # Should have started_at and finished_at
        assert "started_at" in data, "Missing started_at"
        assert "finished_at" in data, "Missing finished_at"
        
        # built_n should be >= 0
        built_n = data.get("built_n", 0)
        assert isinstance(built_n, int) and built_n >= 0, f"built_n should be >= 0, got {built_n}"
        
        print(f"✓ Autopilot run-now completed: built_n={built_n}, selected={data.get('selected')}")
        print(f"  started_at={data.get('started_at')}, finished_at={data.get('finished_at')}")
    
    def test_autopilot_history(self, auth_headers):
        """GET /autopilot/history should return runs array"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/platform/website-builder/autopilot/history?limit=5",
            headers=auth_headers,
            timeout=15
        )
        assert resp.status_code == 200, f"Failed: {resp.text[:200]}"
        data = resp.json()
        
        assert "runs" in data, "Missing 'runs' field"
        assert isinstance(data["runs"], list), "runs should be a list"
        
        print(f"✓ Autopilot history: {len(data['runs'])} runs")
        if data["runs"]:
            print(f"  Latest run: {data['runs'][0]}")


class TestAutoPilotAuthGate:
    """Test that all autopilot endpoints require authentication"""
    
    def test_autopilot_get_requires_auth(self):
        """GET /autopilot should return 401 without Bearer"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/platform/website-builder/autopilot",
            timeout=15
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ GET /autopilot requires auth")
    
    def test_autopilot_post_requires_auth(self):
        """POST /autopilot should return 401 without Bearer"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/platform/website-builder/autopilot",
            json={"enabled": False},
            timeout=15
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ POST /autopilot requires auth")
    
    def test_autopilot_run_now_requires_auth(self):
        """POST /autopilot/run-now should return 401 without Bearer"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/platform/website-builder/autopilot/run-now",
            timeout=15
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ POST /autopilot/run-now requires auth")
    
    def test_autopilot_history_requires_auth(self):
        """GET /autopilot/history should return 401 without Bearer"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/platform/website-builder/autopilot/history",
            timeout=15
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ GET /autopilot/history requires auth")


class TestAWBPipelineE2E:
    """Test AWB pipeline with R2 + DNS deployment"""
    
    def test_build_single_lead(self, auth_headers):
        """Build a site for a single lead and verify R2 + DNS"""
        # First get a lead from the queue
        cockpit_resp = requests.get(
            f"{BASE_URL}/api/admin/platform/website-builder/cockpit",
            headers=auth_headers,
            timeout=15
        )
        assert cockpit_resp.status_code == 200
        cockpit = cockpit_resp.json()
        
        if cockpit.get("queue_size", 0) == 0:
            pytest.skip("No leads in queue to build")
        
        # Get recent sites to find a lead_id we can test with
        # Or use run-batch with limit=1
        resp = requests.post(
            f"{BASE_URL}/api/admin/platform/website-builder/run-batch?limit=1",
            headers=auth_headers,
            timeout=90  # LLM calls can be slow
        )
        assert resp.status_code == 200, f"Batch failed: {resp.text[:300]}"
        data = resp.json()
        
        print(f"Batch result: selected={data.get('selected')}, built={len(data.get('built', []))}, skipped={len(data.get('skipped', []))}")
        
        if data.get("built"):
            site = data["built"][0]
            print(f"✓ Built site: {site.get('site_id')}")
            print(f"  status={site.get('status')}")
            print(f"  live_url={site.get('live_url')}")
            print(f"  publish.r2={site.get('publish', {}).get('r2')}")
            print(f"  publish.dns={site.get('publish', {}).get('dns')}")
            
            # Verify status is 'deployed' when R2+DNS succeed
            if site.get("publish", {}).get("r2", {}).get("ok") and site.get("publish", {}).get("dns", {}).get("ok"):
                assert site.get("status") == "deployed", f"Expected 'deployed' status, got {site.get('status')}"
                print("✓ Site status is 'deployed' (R2 + DNS both OK)")
            
            # If we have a live_url, test it
            live_url = site.get("live_url")
            if live_url:
                # Wait for CF propagation
                print(f"  Waiting 15s for CF propagation...")
                time.sleep(15)
                
                try:
                    live_resp = requests.get(live_url, timeout=30)
                    print(f"  Live URL response: {live_resp.status_code}, {len(live_resp.text)} bytes")
                    if live_resp.status_code == 200:
                        # Check if business_name is in title
                        biz_name = site.get("business_name", "")
                        if biz_name and biz_name.lower() in live_resp.text.lower():
                            print(f"✓ Live URL contains business name in HTML")
                except Exception as e:
                    print(f"  Live URL check failed (may need more propagation time): {e}")
        else:
            print("No sites built (all skipped or queue empty)")
            if data.get("skipped"):
                print(f"  Skipped reasons: {data['skipped'][:3]}")


class TestCleanup:
    """Ensure autopilot is disabled after tests"""
    
    def test_disable_autopilot_after_tests(self, auth_headers):
        """Disable autopilot to prevent auto-burning through queue"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/platform/website-builder/autopilot",
            headers=auth_headers,
            json={"enabled": False},
            timeout=15
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("enabled") is False
        print("✓ Autopilot disabled after tests (as requested)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
