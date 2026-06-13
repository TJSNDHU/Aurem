"""
Iteration 185 - AUREM Cron Monitor & Auto-Audit Testing
========================================================
Tests for:
- GET /api/self-audit/cron-status (schedule, in_memory, persistent, recent_runs)
- POST /api/self-audit/cron-trigger (manual trigger)
- POST /api/self-audit/run (existing audit endpoint)
- GET /api/self-audit/schedule (current schedule config)
- POST /api/self-audit/schedule (update schedule)
- GET /api/self-audit/backups (backup list)
- Auth guards (401 without token)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://ai-platform-preview-3.preview.emergentagent.com"

# Test credentials
TEST_EMAIL = "teji.ss1986@gmail.com"
TEST_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for testing."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        token = data.get("token") or data.get("access_token")
        if token:
            return token
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text[:200]}")


@pytest.fixture
def auth_headers(auth_token):
    """Headers with auth token."""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }


class TestAuthGuards:
    """All endpoints should return 401 without auth token."""
    
    def test_cron_status_requires_auth(self):
        """GET /api/self-audit/cron-status returns 401 without token."""
        response = requests.get(f"{BASE_URL}/api/self-audit/cron-status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_cron_trigger_requires_auth(self):
        """POST /api/self-audit/cron-trigger returns 401 without token."""
        response = requests.post(f"{BASE_URL}/api/self-audit/cron-trigger")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_run_audit_requires_auth(self):
        """POST /api/self-audit/run returns 401 without token."""
        response = requests.post(f"{BASE_URL}/api/self-audit/run", json={"auto_fix": True})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_schedule_get_requires_auth(self):
        """GET /api/self-audit/schedule returns 401 without token."""
        response = requests.get(f"{BASE_URL}/api/self-audit/schedule")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_schedule_post_requires_auth(self):
        """POST /api/self-audit/schedule returns 401 without token."""
        response = requests.post(f"{BASE_URL}/api/self-audit/schedule", json={"frequency": "daily"})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_backups_requires_auth(self):
        """GET /api/self-audit/backups returns 401 without token."""
        response = requests.get(f"{BASE_URL}/api/self-audit/backups")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestCronStatus:
    """Tests for GET /api/self-audit/cron-status endpoint."""
    
    def test_cron_status_returns_schedule(self, auth_headers):
        """Cron status should return schedule configuration."""
        response = requests.get(f"{BASE_URL}/api/self-audit/cron-status", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        assert "schedule" in data, "Response should contain 'schedule'"
        
        schedule = data["schedule"]
        assert "enabled" in schedule, "Schedule should have 'enabled' field"
        assert "frequency" in schedule, "Schedule should have 'frequency' field"
        assert "hour" in schedule, "Schedule should have 'hour' field"
        assert "minute" in schedule, "Schedule should have 'minute' field"
    
    def test_cron_status_returns_in_memory_state(self, auth_headers):
        """Cron status should return in-memory state."""
        response = requests.get(f"{BASE_URL}/api/self-audit/cron-status", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "in_memory" in data, "Response should contain 'in_memory'"
        
        in_memory = data["in_memory"]
        assert "status" in in_memory, "in_memory should have 'status' field"
    
    def test_cron_status_returns_persistent_state(self, auth_headers):
        """Cron status should return persistent state from MongoDB."""
        response = requests.get(f"{BASE_URL}/api/self-audit/cron-status", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "persistent" in data, "Response should contain 'persistent'"
    
    def test_cron_status_returns_recent_runs(self, auth_headers):
        """Cron status should return recent_runs array."""
        response = requests.get(f"{BASE_URL}/api/self-audit/cron-status", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "recent_runs" in data, "Response should contain 'recent_runs'"
        assert isinstance(data["recent_runs"], list), "recent_runs should be a list"


class TestCronTrigger:
    """Tests for POST /api/self-audit/cron-trigger endpoint."""
    
    def test_cron_trigger_executes_audit(self, auth_headers):
        """Manual cron trigger should execute an audit and return report."""
        response = requests.post(f"{BASE_URL}/api/self-audit/cron-trigger", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        assert "triggered" in data, "Response should contain 'triggered'"
        
        if data.get("triggered"):
            assert "report" in data, "Successful trigger should return 'report'"
            assert "run_record" in data, "Successful trigger should return 'run_record'"
            
            report = data["report"]
            assert "audit_id" in report, "Report should have audit_id"
            assert "status" in report, "Report should have status"
            
            run_record = data["run_record"]
            assert run_record.get("trigger") == "manual", "Run record should show manual trigger"
            assert "duration_ms" in run_record, "Run record should have duration_ms"
    
    def test_cron_trigger_logs_execution(self, auth_headers):
        """After cron trigger, recent_runs should be populated."""
        # First trigger
        trigger_response = requests.post(f"{BASE_URL}/api/self-audit/cron-trigger", headers=auth_headers)
        assert trigger_response.status_code == 200
        
        # Then check cron status
        status_response = requests.get(f"{BASE_URL}/api/self-audit/cron-status", headers=auth_headers)
        assert status_response.status_code == 200
        
        data = status_response.json()
        recent_runs = data.get("recent_runs", [])
        
        # Should have at least one run now
        assert len(recent_runs) >= 1, "recent_runs should have at least one entry after trigger"
        
        # Check latest run has expected fields
        if recent_runs:
            latest = recent_runs[0]
            assert "status" in latest, "Run should have status"
            assert "started_at" in latest, "Run should have started_at"
            assert "duration_ms" in latest, "Run should have duration_ms"


class TestExistingAuditEndpoint:
    """Tests for POST /api/self-audit/run (existing endpoint)."""
    
    def test_run_audit_works(self, auth_headers):
        """POST /api/self-audit/run should execute full audit."""
        response = requests.post(
            f"{BASE_URL}/api/self-audit/run",
            headers=auth_headers,
            json={"auto_fix": True}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        assert "audit_id" in data, "Response should have audit_id"
        assert "status" in data, "Response should have status"
        assert "total_issues" in data, "Response should have total_issues"
        assert "auto_fixed" in data, "Response should have auto_fixed"
        assert "needs_review" in data, "Response should have needs_review"
    
    def test_run_audit_returns_agent_reports(self, auth_headers):
        """Audit should return reports from all 5 agents."""
        response = requests.post(
            f"{BASE_URL}/api/self-audit/run",
            headers=auth_headers,
            json={"auto_fix": True}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "agent_reports" in data, "Response should have agent_reports"
        
        agent_reports = data["agent_reports"]
        assert len(agent_reports) == 5, f"Should have 5 agent reports, got {len(agent_reports)}"
        
        # Check each agent is represented
        agents_found = [r.get("agent") for r in agent_reports if isinstance(r, dict)]
        expected_agents = ["scout", "shannon", "architect", "hermes", "repair"]
        for agent in expected_agents:
            assert agent in agents_found, f"Agent '{agent}' should be in reports"


class TestScheduleEndpoints:
    """Tests for schedule management endpoints."""
    
    def test_get_schedule_returns_config(self, auth_headers):
        """GET /api/self-audit/schedule should return current schedule."""
        response = requests.get(f"{BASE_URL}/api/self-audit/schedule", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "schedule" in data, "Response should contain 'schedule'"
        
        schedule = data["schedule"]
        assert "enabled" in schedule
        assert "frequency" in schedule
        assert "hour" in schedule
        assert "minute" in schedule
    
    def test_update_schedule_daily(self, auth_headers):
        """POST /api/self-audit/schedule should update to daily."""
        response = requests.post(
            f"{BASE_URL}/api/self-audit/schedule",
            headers=auth_headers,
            json={"frequency": "daily", "hour": 3, "minute": 30, "enabled": True}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "schedule" in data, "Response should contain 'schedule'"
        assert data["schedule"]["frequency"] == "daily"
        assert data["schedule"]["hour"] == 3
        assert data["schedule"]["minute"] == 30
        assert data["schedule"]["enabled"] == True
    
    def test_update_schedule_weekly(self, auth_headers):
        """POST /api/self-audit/schedule should update to weekly."""
        response = requests.post(
            f"{BASE_URL}/api/self-audit/schedule",
            headers=auth_headers,
            json={"frequency": "weekly", "hour": 2, "minute": 0, "enabled": True}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["schedule"]["frequency"] == "weekly"
    
    def test_update_schedule_disabled(self, auth_headers):
        """POST /api/self-audit/schedule should allow disabling."""
        response = requests.post(
            f"{BASE_URL}/api/self-audit/schedule",
            headers=auth_headers,
            json={"frequency": "disabled", "hour": 2, "minute": 0, "enabled": False}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["schedule"]["enabled"] == False
    
    def test_restore_default_schedule(self, auth_headers):
        """Restore default schedule (daily at 2 AM)."""
        response = requests.post(
            f"{BASE_URL}/api/self-audit/schedule",
            headers=auth_headers,
            json={"frequency": "daily", "hour": 2, "minute": 0, "enabled": True}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["schedule"]["frequency"] == "daily"
        assert data["schedule"]["hour"] == 2


class TestBackupsEndpoint:
    """Tests for GET /api/self-audit/backups endpoint."""
    
    def test_backups_returns_list(self, auth_headers):
        """GET /api/self-audit/backups should return backup list."""
        response = requests.get(f"{BASE_URL}/api/self-audit/backups", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "backups" in data, "Response should contain 'backups'"
        assert "count" in data, "Response should contain 'count'"
        assert isinstance(data["backups"], list), "backups should be a list"
    
    def test_backups_have_expected_fields(self, auth_headers):
        """Backups should have expected fields if any exist."""
        response = requests.get(f"{BASE_URL}/api/self-audit/backups", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        backups = data.get("backups", [])
        
        if backups:
            backup = backups[0]
            # Check expected fields
            expected_fields = ["backup_id", "tenant_id", "fix_action", "created_at"]
            for field in expected_fields:
                assert field in backup, f"Backup should have '{field}' field"


class TestRegressionExistingEndpoints:
    """Regression tests for existing autonomy endpoints."""
    
    def test_audit_status_endpoint(self, auth_headers):
        """GET /api/self-audit/status should work."""
        response = requests.get(f"{BASE_URL}/api/self-audit/status", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_audit_findings_endpoint(self, auth_headers):
        """GET /api/self-audit/findings should work."""
        response = requests.get(f"{BASE_URL}/api/self-audit/findings", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_audit_log_endpoint(self, auth_headers):
        """GET /api/self-audit/log should work."""
        response = requests.get(f"{BASE_URL}/api/self-audit/log?limit=5", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "audits" in data
        assert "count" in data
    
    def test_audit_stats_endpoint(self, auth_headers):
        """GET /api/self-audit/stats should work."""
        response = requests.get(f"{BASE_URL}/api/self-audit/stats", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "agents" in data
    
    def test_audit_queue_endpoint(self, auth_headers):
        """GET /api/self-audit/queue should work."""
        response = requests.get(f"{BASE_URL}/api/self-audit/queue", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "problems" in data
    
    def test_audit_tier_endpoint(self, auth_headers):
        """GET /api/self-audit/tier should work."""
        response = requests.get(f"{BASE_URL}/api/self-audit/tier", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "tier" in data
    
    def test_audit_usage_endpoint(self, auth_headers):
        """GET /api/self-audit/usage should work."""
        response = requests.get(f"{BASE_URL}/api/self-audit/usage", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "used" in data
        assert "limit" in data
        assert "plan" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
