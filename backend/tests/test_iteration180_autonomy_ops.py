"""
Iteration 180 - AUREM Autonomous Operations (Self-Audit + A2A Database Repair) Tests
=====================================================================================
Tests for 7 endpoints under /api/self-audit/:
  POST /run       — Run full 5-agent audit with A2A bidding and auto-fix
  GET  /status    — Latest audit status
  GET  /findings  — All findings from latest audit
  GET  /log       — Audit history
  GET  /stats     — Agent performance statistics
  GET  /queue     — Problems needing human review
  GET  /tier      — Survival tier (abundant/economical/survival/death)

Also tests auth guards (401 without token).
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "teji.ss1986@gmail.com"
TEST_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tests."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def headers(auth_token):
    """Headers with auth token."""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }


class TestAuthGuards:
    """Test that all endpoints return 401 without auth."""

    def test_run_audit_requires_auth(self):
        """POST /api/self-audit/run returns 401 without auth."""
        response = requests.post(f"{BASE_URL}/api/self-audit/run", json={"auto_fix": True})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: POST /api/self-audit/run returns 401 without auth")

    def test_status_requires_auth(self):
        """GET /api/self-audit/status returns 401 without auth."""
        response = requests.get(f"{BASE_URL}/api/self-audit/status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/self-audit/status returns 401 without auth")

    def test_findings_requires_auth(self):
        """GET /api/self-audit/findings returns 401 without auth."""
        response = requests.get(f"{BASE_URL}/api/self-audit/findings")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/self-audit/findings returns 401 without auth")

    def test_log_requires_auth(self):
        """GET /api/self-audit/log returns 401 without auth."""
        response = requests.get(f"{BASE_URL}/api/self-audit/log")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/self-audit/log returns 401 without auth")

    def test_stats_requires_auth(self):
        """GET /api/self-audit/stats returns 401 without auth."""
        response = requests.get(f"{BASE_URL}/api/self-audit/stats")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/self-audit/stats returns 401 without auth")

    def test_queue_requires_auth(self):
        """GET /api/self-audit/queue returns 401 without auth."""
        response = requests.get(f"{BASE_URL}/api/self-audit/queue")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/self-audit/queue returns 401 without auth")

    def test_tier_requires_auth(self):
        """GET /api/self-audit/tier returns 401 without auth."""
        response = requests.get(f"{BASE_URL}/api/self-audit/tier")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: GET /api/self-audit/tier returns 401 without auth")


class TestSurvivalTier:
    """Test survival tier endpoint."""

    def test_get_survival_tier(self, headers):
        """GET /api/self-audit/tier returns tier info."""
        response = requests.get(f"{BASE_URL}/api/self-audit/tier", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "tier" in data, "Response should contain 'tier' field"
        assert data["tier"] in ["abundant", "economical", "survival", "death"], f"Invalid tier: {data['tier']}"
        
        # Verify tier has expected fields
        assert "label" in data, "Response should contain 'label' field"
        assert "agents" in data, "Response should contain 'agents' field"
        assert "models" in data, "Response should contain 'models' field"
        assert "auto_fixes" in data, "Response should contain 'auto_fixes' field"
        
        print(f"PASS: GET /api/self-audit/tier returns tier={data['tier']}, label={data['label']}")


class TestAuditRun:
    """Test running full audit."""

    def test_run_full_audit(self, headers):
        """POST /api/self-audit/run executes 5-agent audit."""
        response = requests.post(
            f"{BASE_URL}/api/self-audit/run",
            headers=headers,
            json={"auto_fix": True}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify audit report structure
        assert "audit_id" in data, "Response should contain 'audit_id'"
        assert "status" in data, "Response should contain 'status'"
        assert "tier" in data, "Response should contain 'tier'"
        assert "timestamp" in data, "Response should contain 'timestamp'"
        
        # Verify agent scan results
        assert "agents_scanned" in data, "Response should contain 'agents_scanned'"
        assert data["agents_scanned"] == 5, f"Expected 5 agents, got {data['agents_scanned']}"
        
        # Verify issue tracking
        assert "total_issues" in data, "Response should contain 'total_issues'"
        assert "auto_fixed" in data, "Response should contain 'auto_fixed'"
        assert "needs_review" in data, "Response should contain 'needs_review'"
        
        # Verify agent reports
        assert "agent_reports" in data, "Response should contain 'agent_reports'"
        assert len(data["agent_reports"]) == 5, f"Expected 5 agent reports, got {len(data['agent_reports'])}"
        
        # Verify each agent is present
        agent_names = [r.get("agent") for r in data["agent_reports"]]
        expected_agents = ["scout", "shannon", "architect", "hermes", "repair"]
        for agent in expected_agents:
            assert agent in agent_names, f"Missing agent report for {agent}"
        
        print(f"PASS: POST /api/self-audit/run - audit_id={data['audit_id']}, status={data['status']}, "
              f"issues={data['total_issues']}, fixed={data['auto_fixed']}, review={data['needs_review']}")
        
        return data

    def test_run_audit_without_autofix(self, headers):
        """POST /api/self-audit/run with auto_fix=false."""
        response = requests.post(
            f"{BASE_URL}/api/self-audit/run",
            headers=headers,
            json={"auto_fix": False}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "audit_id" in data
        assert "status" in data
        # When auto_fix is false, all issues should go to needs_review
        assert data["auto_fixed"] == 0, "With auto_fix=false, no issues should be auto-fixed"
        
        print(f"PASS: POST /api/self-audit/run (auto_fix=false) - all issues go to review")


class TestAuditStatus:
    """Test audit status endpoint."""

    def test_get_audit_status(self, headers):
        """GET /api/self-audit/status returns latest audit status."""
        response = requests.get(f"{BASE_URL}/api/self-audit/status", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Either we have an audit or no_audits status
        if data.get("status") == "no_audits":
            assert "message" in data
            print("PASS: GET /api/self-audit/status - no audits yet")
        else:
            assert "audit_id" in data, "Response should contain 'audit_id'"
            assert "status" in data, "Response should contain 'status'"
            assert "timestamp" in data, "Response should contain 'timestamp'"
            assert "total_issues" in data, "Response should contain 'total_issues'"
            assert "auto_fixed" in data, "Response should contain 'auto_fixed'"
            assert "needs_review" in data, "Response should contain 'needs_review'"
            assert "tier" in data, "Response should contain 'tier'"
            
            print(f"PASS: GET /api/self-audit/status - audit_id={data['audit_id']}, "
                  f"issues={data['total_issues']}, fixed={data['auto_fixed']}")


class TestAuditFindings:
    """Test audit findings endpoint."""

    def test_get_audit_findings(self, headers):
        """GET /api/self-audit/findings returns findings from latest audit."""
        response = requests.get(f"{BASE_URL}/api/self-audit/findings", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify structure
        assert "findings" in data, "Response should contain 'findings'"
        assert "count" in data, "Response should contain 'count'"
        
        # If there are findings, verify structure
        if data["count"] > 0:
            assert "audit_id" in data, "Response should contain 'audit_id'"
            assert "fixes_applied" in data, "Response should contain 'fixes_applied'"
            assert "needs_review" in data, "Response should contain 'needs_review'"
            assert "suggestions" in data, "Response should contain 'suggestions'"
            
            # Verify findings structure
            for finding in data["findings"]:
                assert "issue_type" in finding, "Finding should have 'issue_type'"
                assert "assigned_to" in finding, "Finding should have 'assigned_to'"
                assert "confidence" in finding, "Finding should have 'confidence'"
        
        print(f"PASS: GET /api/self-audit/findings - count={data['count']}")


class TestAuditLog:
    """Test audit history endpoint."""

    def test_get_audit_log(self, headers):
        """GET /api/self-audit/log returns audit history."""
        response = requests.get(f"{BASE_URL}/api/self-audit/log?limit=5", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert "audits" in data, "Response should contain 'audits'"
        assert "count" in data, "Response should contain 'count'"
        assert isinstance(data["audits"], list), "'audits' should be a list"
        
        # Verify audit entries structure
        for audit in data["audits"]:
            assert "audit_id" in audit, "Audit entry should have 'audit_id'"
            assert "status" in audit, "Audit entry should have 'status'"
            assert "timestamp" in audit, "Audit entry should have 'timestamp'"
            assert "total_issues" in audit, "Audit entry should have 'total_issues'"
        
        print(f"PASS: GET /api/self-audit/log - count={data['count']}")


class TestAgentStats:
    """Test agent performance stats endpoint."""

    def test_get_agent_stats(self, headers):
        """GET /api/self-audit/stats returns agent performance statistics."""
        response = requests.get(f"{BASE_URL}/api/self-audit/stats", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert "agents" in data, "Response should contain 'agents'"
        assert "count" in data, "Response should contain 'count'"
        assert isinstance(data["agents"], list), "'agents' should be a list"
        
        # Verify agent stats structure if any exist
        for agent in data["agents"]:
            assert "agent" in agent, "Agent stat should have 'agent'"
            assert "problems_solved" in agent, "Agent stat should have 'problems_solved'"
            assert "records_fixed" in agent, "Agent stat should have 'records_fixed'"
        
        print(f"PASS: GET /api/self-audit/stats - count={data['count']}")


class TestProblemQueue:
    """Test problem queue endpoint."""

    def test_get_problem_queue(self, headers):
        """GET /api/self-audit/queue returns problems needing human review."""
        response = requests.get(f"{BASE_URL}/api/self-audit/queue", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert "problems" in data, "Response should contain 'problems'"
        assert "count" in data, "Response should contain 'count'"
        assert isinstance(data["problems"], list), "'problems' should be a list"
        
        # Verify problem structure if any exist
        for problem in data["problems"]:
            assert "type" in problem, "Problem should have 'type'"
            assert "severity" in problem, "Problem should have 'severity'"
            assert "description" in problem, "Problem should have 'description'"
        
        print(f"PASS: GET /api/self-audit/queue - count={data['count']}")


class TestEndToEndAuditFlow:
    """Test complete audit flow: run → status → findings → log."""

    def test_full_audit_flow(self, headers):
        """Run audit and verify all related endpoints return consistent data."""
        # Step 1: Run audit
        run_response = requests.post(
            f"{BASE_URL}/api/self-audit/run",
            headers=headers,
            json={"auto_fix": True}
        )
        assert run_response.status_code == 200
        audit_data = run_response.json()
        audit_id = audit_data["audit_id"]
        print(f"Step 1: Ran audit {audit_id}")
        
        # Step 2: Check status matches
        status_response = requests.get(f"{BASE_URL}/api/self-audit/status", headers=headers)
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data.get("audit_id") == audit_id, "Status should show latest audit"
        print(f"Step 2: Status shows audit {audit_id}")
        
        # Step 3: Check findings match
        findings_response = requests.get(f"{BASE_URL}/api/self-audit/findings", headers=headers)
        assert findings_response.status_code == 200
        findings_data = findings_response.json()
        if findings_data["count"] > 0:
            assert findings_data.get("audit_id") == audit_id, "Findings should be from latest audit"
        print(f"Step 3: Findings count={findings_data['count']}")
        
        # Step 4: Check log contains this audit
        log_response = requests.get(f"{BASE_URL}/api/self-audit/log?limit=1", headers=headers)
        assert log_response.status_code == 200
        log_data = log_response.json()
        if log_data["count"] > 0:
            assert log_data["audits"][0]["audit_id"] == audit_id, "Log should have latest audit first"
        print(f"Step 4: Log shows audit {audit_id} at top")
        
        # Step 5: Check tier is consistent
        tier_response = requests.get(f"{BASE_URL}/api/self-audit/tier", headers=headers)
        assert tier_response.status_code == 200
        tier_data = tier_response.json()
        assert tier_data["tier"] == audit_data["tier"]["tier"], "Tier should match audit tier"
        print(f"Step 5: Tier={tier_data['tier']} matches audit")
        
        print("PASS: Full audit flow completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
