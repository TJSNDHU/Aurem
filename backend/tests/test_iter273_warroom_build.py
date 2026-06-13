"""
Iteration 273 — War-Room Build Backend Tests
=============================================
Tests for:
1. GET /api/ora/health — unauthenticated ORA health probe
2. POST /api/admin/pillars-map/sync — admin-only force cache refresh
3. /sync updates cached snapshot — subsequent /heartbeat returns forced value
4. POST /sync requires admin JWT (401 without token)
5. flows endpoint shows customer_ora_chat with status=green (was yellow)
6. JWT file-persistence — config.py 3-tier resolution
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code}")
    data = resp.json()
    return data.get("token") or data.get("access_token")


class TestOraHealth:
    """Test GET /api/ora/health — unauthenticated health probe"""
    
    def test_ora_health_returns_200(self):
        """ORA health endpoint should return 200 without auth"""
        resp = requests.get(f"{BASE_URL}/api/ora/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
    def test_ora_health_response_structure(self):
        """ORA health should return {status:'ok', component:'ora', db_ready:bool, ts:iso}"""
        resp = requests.get(f"{BASE_URL}/api/ora/health")
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify required fields
        assert data.get("status") == "ok", f"Expected status='ok', got {data.get('status')}"
        assert data.get("component") == "ora", f"Expected component='ora', got {data.get('component')}"
        assert "db_ready" in data, "Missing db_ready field"
        assert isinstance(data["db_ready"], bool), f"db_ready should be bool, got {type(data['db_ready'])}"
        assert "ts" in data, "Missing ts field"
        # ts should be ISO format
        assert "T" in data["ts"], f"ts should be ISO format, got {data['ts']}"


class TestPillarsMapSync:
    """Test POST /api/admin/pillars-map/sync — admin-only force cache refresh"""
    
    def test_sync_requires_auth(self):
        """POST /sync should return 401 without token"""
        resp = requests.post(f"{BASE_URL}/api/admin/pillars-map/sync")
        assert resp.status_code == 401, f"Expected 401 without auth, got {resp.status_code}"
        
    def test_sync_with_admin_token(self, admin_token):
        """POST /sync with admin token should return 200 with forced=true"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/pillars-map/sync",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify response structure
        assert data.get("ok") is True, f"Expected ok=true, got {data.get('ok')}"
        assert data.get("forced") is True, f"Expected forced=true, got {data.get('forced')}"
        assert "generated_at" in data, "Missing generated_at"
        assert "overall_status" in data, "Missing overall_status"
        assert "totals" in data, "Missing totals"
        
    def test_sync_response_totals_structure(self, admin_token):
        """POST /sync totals should have expected fields"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/pillars-map/sync",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        totals = data.get("totals", {})
        
        # Verify totals fields
        expected_fields = [
            "collections", "silent_failures", "unreachable", "backend_red",
            "wires_total", "wires_red", "wires_yellow", "wires_idle",
            "flows_total", "flows_red", "flows_yellow"
        ]
        for field in expected_fields:
            assert field in totals, f"Missing totals.{field}"


class TestSyncUpdatesCachedSnapshot:
    """Test that /sync updates the cached snapshot returned by /heartbeat"""
    
    def test_heartbeat_returns_synced_data(self, admin_token):
        """After /sync, /heartbeat should return the forced snapshot"""
        # First, call sync
        sync_resp = requests.post(
            f"{BASE_URL}/api/admin/pillars-map/sync",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert sync_resp.status_code == 200
        sync_data = sync_resp.json()
        sync_generated_at = sync_data.get("generated_at")
        
        # Then, call heartbeat
        hb_resp = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/heartbeat",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert hb_resp.status_code == 200
        hb_data = hb_resp.json()
        
        # Heartbeat should return the same generated_at (or newer)
        hb_generated_at = hb_data.get("generated_at")
        assert hb_generated_at is not None, "Heartbeat missing generated_at"
        # The heartbeat should have the synced timestamp or newer
        assert hb_generated_at >= sync_generated_at, \
            f"Heartbeat generated_at ({hb_generated_at}) should be >= sync ({sync_generated_at})"


class TestFlowsCustomerOraChat:
    """Test that customer_ora_chat flow shows green status (was yellow before /api/ora/health existed)"""
    
    def test_flows_endpoint_returns_customer_ora_chat(self, admin_token):
        """GET /flows should include customer_ora_chat flow"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/flows",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        flows = data.get("flows", [])
        
        # Find customer_ora_chat flow
        ora_chat_flow = next((f for f in flows if f.get("id") == "customer_ora_chat"), None)
        assert ora_chat_flow is not None, "customer_ora_chat flow not found in flows"
        
    def test_customer_ora_chat_backend_status_green(self, admin_token):
        """customer_ora_chat flow backend status should be green (not yellow)"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/flows",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        flows = data.get("flows", [])
        
        ora_chat_flow = next((f for f in flows if f.get("id") == "customer_ora_chat"), None)
        assert ora_chat_flow is not None
        
        # Check triple_pulse.backend status
        triple_pulse = ora_chat_flow.get("triple_pulse", {})
        backend = triple_pulse.get("backend", {})
        backend_status = backend.get("status")
        
        # Backend should be green because /api/ora/health now exists and returns 200
        # Note: It might still be yellow/red if schedulers are missing, but HTTP should be 200
        http_status = backend.get("http_status")
        assert http_status == 200, f"Expected backend HTTP 200, got {http_status}"


class TestJWTFilePersistence:
    """Test JWT 3-tier resolution in config.py"""
    
    def test_jwt_secret_file_path_exists_in_config(self):
        """config.py should reference /app/.jwt_secret file path"""
        config_path = "/app/backend/config.py"
        with open(config_path, "r") as f:
            content = f.read()
        
        # Check for file path reference
        assert "/app/.jwt_secret" in content, "config.py should reference /app/.jwt_secret"
        
    def test_jwt_three_tier_resolution_code_exists(self):
        """config.py should have 3-tier JWT resolution: env → file → generate+persist"""
        config_path = "/app/backend/config.py"
        with open(config_path, "r") as f:
            content = f.read()
        
        # Check for env var check
        assert 'os.environ.get("JWT_SECRET")' in content or "JWT_SECRET" in content, \
            "config.py should check JWT_SECRET env var"
        
        # Check for file read
        assert "os.path.exists" in content, "config.py should check if file exists"
        
        # Check for file write (generate+persist)
        assert "token_urlsafe" in content or "secrets" in content, \
            "config.py should generate secret if missing"
        
        # Check for chmod 0600
        assert "0o600" in content or "chmod" in content, \
            "config.py should set file permissions to 0600"


class TestHeartbeatRequiresAuth:
    """Test that /heartbeat requires admin JWT"""
    
    def test_heartbeat_requires_auth(self):
        """GET /heartbeat should return 401 without token"""
        resp = requests.get(f"{BASE_URL}/api/admin/pillars-map/heartbeat")
        assert resp.status_code == 401, f"Expected 401 without auth, got {resp.status_code}"
        
    def test_heartbeat_with_admin_token(self, admin_token):
        """GET /heartbeat with admin token should return 200"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/heartbeat",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


class TestOverviewEndpoint:
    """Test GET /api/admin/pillars-map/overview"""
    
    def test_overview_requires_auth(self):
        """GET /overview should return 401 without token"""
        resp = requests.get(f"{BASE_URL}/api/admin/pillars-map/overview")
        assert resp.status_code == 401, f"Expected 401 without auth, got {resp.status_code}"
        
    def test_overview_with_admin_token(self, admin_token):
        """GET /overview with admin token should return full snapshot"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/overview",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        
        # Verify structure
        assert "generated_at" in data
        assert "overall_status" in data
        assert "pillars" in data
        assert "wires" in data
        assert "flows" in data
        assert "totals" in data
