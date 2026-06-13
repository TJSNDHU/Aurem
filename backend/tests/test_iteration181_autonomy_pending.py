"""
Iteration 181 — AUREM Autonomy Pending Items Testing
=====================================================
Tests for 5 pending Autonomy items:
1. Nightly 2 AM auto-audit cron (scheduler registered)
2. WhatsApp notification when needs_review items found
3. POST /api/self-audit/approve — approve/reject fixes
4. POST /api/self-audit/schedule — set daily/weekly/disabled + GET schedule
5. Data replacement via Free APIs: Tomba (email), Numverify (phone), IPstack (location)

Also includes regression tests for existing autonomy endpoints.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://ai-platform-preview-3.preview.emergentagent.com"

# Test credentials
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


class TestAuthSetup:
    """Get auth token for subsequent tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get JWT token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        token = data.get("token") or data.get("access_token")
        assert token, f"No token in response: {data}"
        return token
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Return headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestAuthGuards(TestAuthSetup):
    """Test that all new endpoints return 401 without token"""
    
    def test_schedule_get_no_auth(self):
        """GET /api/self-audit/schedule returns 401 without token"""
        response = requests.get(f"{BASE_URL}/api/self-audit/schedule")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_schedule_post_no_auth(self):
        """POST /api/self-audit/schedule returns 401 without token"""
        response = requests.post(f"{BASE_URL}/api/self-audit/schedule", json={
            "frequency": "daily", "hour": 2, "minute": 0
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_approve_no_auth(self):
        """POST /api/self-audit/approve returns 401 without token"""
        response = requests.post(f"{BASE_URL}/api/self-audit/approve", json={
            "audit_id": "test", "issue_type": "test"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_verify_data_no_auth(self):
        """POST /api/self-audit/verify-data returns 401 without token"""
        response = requests.post(f"{BASE_URL}/api/self-audit/verify-data", json={
            "record_id": "test", "field": "email", "current_value": "test@test.com"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestScheduleEndpoints(TestAuthSetup):
    """Test schedule GET and POST endpoints"""
    
    def test_get_schedule(self, auth_headers):
        """GET /api/self-audit/schedule returns current schedule"""
        response = requests.get(f"{BASE_URL}/api/self-audit/schedule", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "schedule" in data, f"Missing 'schedule' key: {data}"
        schedule = data["schedule"]
        assert "enabled" in schedule, f"Missing 'enabled' in schedule: {schedule}"
        assert "frequency" in schedule, f"Missing 'frequency' in schedule: {schedule}"
        assert "hour" in schedule, f"Missing 'hour' in schedule: {schedule}"
        assert "minute" in schedule, f"Missing 'minute' in schedule: {schedule}"
        print(f"Current schedule: {schedule}")
    
    def test_set_schedule_daily(self, auth_headers):
        """POST /api/self-audit/schedule with daily frequency"""
        response = requests.post(f"{BASE_URL}/api/self-audit/schedule", headers=auth_headers, json={
            "frequency": "daily",
            "hour": 3,
            "minute": 30,
            "enabled": True
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("updated") == True, f"Expected updated=True: {data}"
        assert data.get("schedule", {}).get("frequency") == "daily", f"Frequency not set: {data}"
        assert data.get("schedule", {}).get("hour") == 3, f"Hour not set: {data}"
        assert data.get("schedule", {}).get("minute") == 30, f"Minute not set: {data}"
        print(f"Set daily schedule: {data}")
    
    def test_set_schedule_weekly(self, auth_headers):
        """POST /api/self-audit/schedule with weekly frequency"""
        response = requests.post(f"{BASE_URL}/api/self-audit/schedule", headers=auth_headers, json={
            "frequency": "weekly",
            "hour": 2,
            "minute": 0,
            "enabled": True
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("schedule", {}).get("frequency") == "weekly", f"Frequency not weekly: {data}"
        print(f"Set weekly schedule: {data}")
    
    def test_set_schedule_disabled(self, auth_headers):
        """POST /api/self-audit/schedule with disabled frequency"""
        response = requests.post(f"{BASE_URL}/api/self-audit/schedule", headers=auth_headers, json={
            "frequency": "disabled",
            "hour": 2,
            "minute": 0,
            "enabled": False
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("schedule", {}).get("enabled") == False, f"Not disabled: {data}"
        print(f"Disabled schedule: {data}")
    
    def test_restore_default_schedule(self, auth_headers):
        """Restore default 2 AM daily schedule"""
        response = requests.post(f"{BASE_URL}/api/self-audit/schedule", headers=auth_headers, json={
            "frequency": "daily",
            "hour": 2,
            "minute": 0,
            "enabled": True
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("Restored default schedule")


class TestVerifyDataEndpoints(TestAuthSetup):
    """Test data verification via Free APIs (Tomba, Numverify, IPstack)"""
    
    def test_verify_email_graceful_no_key(self, auth_headers):
        """POST /api/self-audit/verify-data with email field — graceful error when TOMBA_API_KEY not set"""
        response = requests.post(f"{BASE_URL}/api/self-audit/verify-data", headers=auth_headers, json={
            "record_id": "test_record_123",
            "field": "email",
            "current_value": "test@example.com"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("field") == "email", f"Field mismatch: {data}"
        assert data.get("old_value") == "test@example.com", f"Old value mismatch: {data}"
        # Should return graceful error since TOMBA_API_KEY is not set
        if "reason" in data:
            assert "TOMBA_API_KEY not set" in data.get("reason", ""), f"Expected TOMBA key error: {data}"
        print(f"Email verification (no key): {data}")
    
    def test_verify_phone_numverify(self, auth_headers):
        """POST /api/self-audit/verify-data with phone field — uses Numverify or regex fallback"""
        response = requests.post(f"{BASE_URL}/api/self-audit/verify-data", headers=auth_headers, json={
            "record_id": "test_record_456",
            "field": "phone",
            "current_value": "+14165551234"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("field") == "phone", f"Field mismatch: {data}"
        assert data.get("old_value") == "+14165551234", f"Old value mismatch: {data}"
        # Should have verification result (either from Numverify or regex fallback)
        if "verification" in data:
            assert "source" in data["verification"], f"Missing source in verification: {data}"
            print(f"Phone verification: {data['verification']}")
        elif "reason" in data:
            print(f"Phone verification fallback: {data}")
        print(f"Phone verification result: {data}")
    
    def test_verify_location_ipstack(self, auth_headers):
        """POST /api/self-audit/verify-data with location field — uses IPstack or ip-api fallback"""
        response = requests.post(f"{BASE_URL}/api/self-audit/verify-data", headers=auth_headers, json={
            "record_id": "test_record_789",
            "field": "location",
            "current_value": "8.8.8.8"  # Google DNS IP for testing
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("field") == "location", f"Field mismatch: {data}"
        assert data.get("old_value") == "8.8.8.8", f"Old value mismatch: {data}"
        # Should have verification result with location data
        if "verification" in data:
            verification = data["verification"]
            assert "source" in verification, f"Missing source: {data}"
            assert "confidence" in verification, f"Missing confidence: {data}"
            # If confidence > 0.85, should have replaced
            if verification.get("confidence", 0) > 0.85:
                assert data.get("replaced") == True or "new_value" in data, f"Should have replaced: {data}"
            print(f"Location verification: {verification}")
        print(f"Location verification result: {data}")
    
    def test_verify_unsupported_field(self, auth_headers):
        """POST /api/self-audit/verify-data with unsupported field"""
        response = requests.post(f"{BASE_URL}/api/self-audit/verify-data", headers=auth_headers, json={
            "record_id": "test_record_000",
            "field": "unsupported_field",
            "current_value": "some_value"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("replaced") == False, f"Should not replace unsupported field: {data}"
        assert "unsupported" in data.get("reason", "").lower(), f"Should mention unsupported: {data}"
        print(f"Unsupported field result: {data}")


class TestApproveEndpoint(TestAuthSetup):
    """Test approve/reject fix endpoint"""
    
    def test_approve_nonexistent_audit(self, auth_headers):
        """POST /api/self-audit/approve with non-existent audit_id"""
        response = requests.post(f"{BASE_URL}/api/self-audit/approve", headers=auth_headers, json={
            "audit_id": "audit_nonexistent_12345",
            "issue_type": "stale_data",
            "action": "approve"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("approved") == False, f"Should not approve non-existent: {data}"
        assert "not_found" in data.get("reason", "").lower() or "audit_not_found" in data.get("reason", ""), f"Should mention not found: {data}"
        print(f"Non-existent audit result: {data}")
    
    def test_run_audit_then_approve(self, auth_headers):
        """Run audit with auto_fix=false, then approve a fix"""
        # Step 1: Run audit with auto_fix=false to generate needs_review items
        run_response = requests.post(f"{BASE_URL}/api/self-audit/run", headers=auth_headers, json={
            "auto_fix": False
        })
        assert run_response.status_code == 200, f"Run audit failed: {run_response.text}"
        run_data = run_response.json()
        audit_id = run_data.get("audit_id")
        assert audit_id, f"No audit_id in response: {run_data}"
        print(f"Audit ID: {audit_id}")
        
        needs_review = run_data.get("needs_human_review", [])
        print(f"Needs review count: {len(needs_review)}")
        
        if len(needs_review) > 0:
            # Step 2: Approve the first issue
            issue = needs_review[0]
            issue_type = issue.get("type")
            print(f"Approving issue: {issue_type}")
            
            approve_response = requests.post(f"{BASE_URL}/api/self-audit/approve", headers=auth_headers, json={
                "audit_id": audit_id,
                "issue_type": issue_type,
                "action": "approve"
            })
            assert approve_response.status_code == 200, f"Approve failed: {approve_response.text}"
            approve_data = approve_response.json()
            print(f"Approve result: {approve_data}")
            
            # Verify the approval
            assert approve_data.get("issue_type") == issue_type, f"Issue type mismatch: {approve_data}"
        else:
            print("No issues to approve (clean database)")
            pytest.skip("No issues in needs_review to test approve")
    
    def test_run_audit_then_reject(self, auth_headers):
        """Run audit with auto_fix=false, then reject a fix"""
        # Step 1: Run audit with auto_fix=false
        run_response = requests.post(f"{BASE_URL}/api/self-audit/run", headers=auth_headers, json={
            "auto_fix": False
        })
        assert run_response.status_code == 200, f"Run audit failed: {run_response.text}"
        run_data = run_response.json()
        audit_id = run_data.get("audit_id")
        
        needs_review = run_data.get("needs_human_review", [])
        
        if len(needs_review) > 0:
            # Step 2: Reject the first issue
            issue = needs_review[0]
            issue_type = issue.get("type")
            print(f"Rejecting issue: {issue_type}")
            
            reject_response = requests.post(f"{BASE_URL}/api/self-audit/approve", headers=auth_headers, json={
                "audit_id": audit_id,
                "issue_type": issue_type,
                "action": "reject"
            })
            assert reject_response.status_code == 200, f"Reject failed: {reject_response.text}"
            reject_data = reject_response.json()
            print(f"Reject result: {reject_data}")
            
            # Verify the rejection
            assert reject_data.get("action") == "rejected", f"Action not rejected: {reject_data}"
            assert reject_data.get("issue_type") == issue_type, f"Issue type mismatch: {reject_data}"
        else:
            print("No issues to reject (clean database)")
            pytest.skip("No issues in needs_review to test reject")


class TestRegressionExistingEndpoints(TestAuthSetup):
    """Regression tests for existing autonomy endpoints"""
    
    def test_run_audit_auto_fix_true(self, auth_headers):
        """POST /api/self-audit/run with auto_fix=true (regression)"""
        response = requests.post(f"{BASE_URL}/api/self-audit/run", headers=auth_headers, json={
            "auto_fix": True
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "audit_id" in data, f"Missing audit_id: {data}"
        assert "status" in data, f"Missing status: {data}"
        assert "tier" in data, f"Missing tier: {data}"
        assert "agents_scanned" in data, f"Missing agents_scanned: {data}"
        assert data.get("agents_scanned") == 5, f"Expected 5 agents: {data}"
        print(f"Audit with auto_fix=true: {data.get('total_issues')} issues, {data.get('auto_fixed')} fixed")
    
    def test_run_audit_auto_fix_false(self, auth_headers):
        """POST /api/self-audit/run with auto_fix=false (regression)"""
        response = requests.post(f"{BASE_URL}/api/self-audit/run", headers=auth_headers, json={
            "auto_fix": False
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("auto_fixed") == 0, f"auto_fixed should be 0: {data}"
        # All issues should be in needs_human_review
        total_issues = data.get("total_issues", 0)
        needs_review = data.get("needs_review", 0)
        print(f"Audit with auto_fix=false: {total_issues} issues, {needs_review} need review")
    
    def test_get_status(self, auth_headers):
        """GET /api/self-audit/status (regression)"""
        response = requests.get(f"{BASE_URL}/api/self-audit/status", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Should have audit_id or status=no_audits
        assert "audit_id" in data or data.get("status") == "no_audits", f"Unexpected response: {data}"
        print(f"Status: {data}")
    
    def test_get_findings(self, auth_headers):
        """GET /api/self-audit/findings (regression)"""
        response = requests.get(f"{BASE_URL}/api/self-audit/findings", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "findings" in data or "count" in data, f"Missing findings/count: {data}"
        print(f"Findings count: {data.get('count', len(data.get('findings', [])))}")
    
    def test_get_log(self, auth_headers):
        """GET /api/self-audit/log (regression)"""
        response = requests.get(f"{BASE_URL}/api/self-audit/log", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "audits" in data, f"Missing audits: {data}"
        print(f"Audit log count: {data.get('count', len(data.get('audits', [])))}")
    
    def test_get_stats(self, auth_headers):
        """GET /api/self-audit/stats (regression)"""
        response = requests.get(f"{BASE_URL}/api/self-audit/stats", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "agents" in data, f"Missing agents: {data}"
        print(f"Agent stats count: {data.get('count', len(data.get('agents', [])))}")
    
    def test_get_queue(self, auth_headers):
        """GET /api/self-audit/queue (regression)"""
        response = requests.get(f"{BASE_URL}/api/self-audit/queue", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "problems" in data, f"Missing problems: {data}"
        print(f"Problem queue count: {data.get('count', len(data.get('problems', [])))}")
    
    def test_get_tier(self, auth_headers):
        """GET /api/self-audit/tier (regression)"""
        response = requests.get(f"{BASE_URL}/api/self-audit/tier", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "tier" in data, f"Missing tier: {data}"
        assert data.get("tier") in ["abundant", "economical", "survival", "death"], f"Invalid tier: {data}"
        print(f"Survival tier: {data.get('tier')}")


class TestRegressionAuthGuards(TestAuthSetup):
    """Regression: All existing endpoints return 401 without token"""
    
    def test_run_no_auth(self):
        """POST /api/self-audit/run returns 401 without token"""
        response = requests.post(f"{BASE_URL}/api/self-audit/run", json={"auto_fix": True})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_status_no_auth(self):
        """GET /api/self-audit/status returns 401 without token"""
        response = requests.get(f"{BASE_URL}/api/self-audit/status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_findings_no_auth(self):
        """GET /api/self-audit/findings returns 401 without token"""
        response = requests.get(f"{BASE_URL}/api/self-audit/findings")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_log_no_auth(self):
        """GET /api/self-audit/log returns 401 without token"""
        response = requests.get(f"{BASE_URL}/api/self-audit/log")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_stats_no_auth(self):
        """GET /api/self-audit/stats returns 401 without token"""
        response = requests.get(f"{BASE_URL}/api/self-audit/stats")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_queue_no_auth(self):
        """GET /api/self-audit/queue returns 401 without token"""
        response = requests.get(f"{BASE_URL}/api/self-audit/queue")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_tier_no_auth(self):
        """GET /api/self-audit/tier returns 401 without token"""
        response = requests.get(f"{BASE_URL}/api/self-audit/tier")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
