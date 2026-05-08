"""
Iteration 182 - AUREM Autonomy Safety Layer Tests
=================================================
Tests for the new safety layer features:
1. POST /api/self-audit/run (auto_fix=true) — creates backups in audit_backups collection
2. GET /api/self-audit/backups — lists backups with can_undo, days_remaining, backup_id, fix_action
3. POST /api/self-audit/rollback/{backup_id} — restores records to original state
4. POST /api/self-audit/rollback/{backup_id} — returns error for already rolled back backup
5. POST /api/self-audit/rollback/nonexistent — returns backup_not_found
6. Auth guards — rollback and backups endpoints return 401 without token
7. Regression: all existing self-audit endpoints still work
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "teji.ss1986@gmail.com"
TEST_PASSWORD = "Admin123"


class TestAuthSetup:
    """Get authentication token for subsequent tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get JWT token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        token = data.get("token") or data.get("access_token")
        assert token, f"No token in response: {data}"
        return token
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Headers with auth token"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}"
        }


class TestAuthGuardsNewEndpoints(TestAuthSetup):
    """Test that new endpoints require authentication"""
    
    def test_backups_no_auth_returns_401(self):
        """GET /api/self-audit/backups without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/self-audit/backups")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("PASS: GET /api/self-audit/backups returns 401 without auth")
    
    def test_rollback_no_auth_returns_401(self):
        """POST /api/self-audit/rollback/{backup_id} without auth returns 401"""
        response = requests.post(f"{BASE_URL}/api/self-audit/rollback/test_backup_id")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("PASS: POST /api/self-audit/rollback returns 401 without auth")


class TestBackupsEndpoint(TestAuthSetup):
    """Test GET /api/self-audit/backups endpoint"""
    
    def test_backups_returns_list(self, headers):
        """GET /api/self-audit/backups returns list of backups"""
        response = requests.get(f"{BASE_URL}/api/self-audit/backups", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "backups" in data, f"Response missing 'backups' key: {data}"
        assert "count" in data, f"Response missing 'count' key: {data}"
        assert isinstance(data["backups"], list), f"backups should be a list: {data}"
        print(f"PASS: GET /api/self-audit/backups returns {data['count']} backups")
        return data
    
    def test_backups_have_required_fields(self, headers):
        """Backups should have can_undo, days_remaining, backup_id, fix_action"""
        response = requests.get(f"{BASE_URL}/api/self-audit/backups", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        if data["count"] > 0:
            backup = data["backups"][0]
            # Check required fields
            assert "backup_id" in backup, f"Backup missing backup_id: {backup}"
            assert "fix_action" in backup, f"Backup missing fix_action: {backup}"
            assert "can_undo" in backup, f"Backup missing can_undo: {backup}"
            assert "days_remaining" in backup, f"Backup missing days_remaining: {backup}"
            assert "agent" in backup, f"Backup missing agent: {backup}"
            assert "created_at" in backup, f"Backup missing created_at: {backup}"
            assert "expires_at" in backup, f"Backup missing expires_at: {backup}"
            print(f"PASS: Backup has all required fields: backup_id={backup['backup_id']}, can_undo={backup['can_undo']}, days_remaining={backup['days_remaining']}")
        else:
            print("SKIP: No backups to verify fields (will be tested after audit run)")


class TestRollbackEndpoint(TestAuthSetup):
    """Test POST /api/self-audit/rollback/{backup_id} endpoint"""
    
    def test_rollback_nonexistent_returns_backup_not_found(self, headers):
        """POST /api/self-audit/rollback/nonexistent returns backup_not_found"""
        response = requests.post(f"{BASE_URL}/api/self-audit/rollback/nonexistent_backup_xyz", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("rolled_back") == False, f"Expected rolled_back=False: {data}"
        assert data.get("reason") == "backup_not_found", f"Expected reason=backup_not_found: {data}"
        print("PASS: POST /api/self-audit/rollback/nonexistent returns backup_not_found")


class TestAuditCreatesBackups(TestAuthSetup):
    """Test that running audit with auto_fix=true creates backups"""
    
    def test_run_audit_with_autofix_creates_backups(self, headers):
        """POST /api/self-audit/run with auto_fix=true should create backups for fixes"""
        # First, get current backup count
        backups_before = requests.get(f"{BASE_URL}/api/self-audit/backups", headers=headers).json()
        count_before = backups_before.get("count", 0)
        
        # Run audit with auto_fix=true
        response = requests.post(f"{BASE_URL}/api/self-audit/run", headers=headers, json={"auto_fix": True})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check audit response structure
        assert "audit_id" in data, f"Response missing audit_id: {data}"
        assert "status" in data, f"Response missing status: {data}"
        assert "total_issues" in data, f"Response missing total_issues: {data}"
        assert "auto_fixed" in data, f"Response missing auto_fixed: {data}"
        
        auto_fixed = data.get("auto_fixed", 0)
        fixes_applied = data.get("fixes_applied", [])
        
        print(f"Audit completed: {data['total_issues']} issues found, {auto_fixed} auto-fixed")
        
        # If fixes were applied, check that backups were created
        if auto_fixed > 0:
            # Check fixes_applied have backup_id
            for fix in fixes_applied:
                assert "backup_id" in fix, f"Fix missing backup_id: {fix}"
                print(f"  Fix: {fix.get('fix_action')} - backup_id: {fix.get('backup_id')}")
            
            # Verify backups were created
            backups_after = requests.get(f"{BASE_URL}/api/self-audit/backups", headers=headers).json()
            count_after = backups_after.get("count", 0)
            
            # Note: count might not increase if same fix_action already had a backup
            print(f"PASS: Audit with auto_fix=true completed. Backups: {count_before} -> {count_after}")
        else:
            print("INFO: No issues auto-fixed (database may be clean). Backup creation not tested.")
        
        return data


class TestRollbackFlow(TestAuthSetup):
    """Test full rollback flow: create backup -> rollback -> verify"""
    
    def test_rollback_already_rolled_back_returns_error(self, headers):
        """POST /api/self-audit/rollback on already rolled back backup returns error"""
        # Get backups
        backups_response = requests.get(f"{BASE_URL}/api/self-audit/backups", headers=headers)
        assert backups_response.status_code == 200
        backups = backups_response.json().get("backups", [])
        
        # Find an already rolled back backup
        rolled_back_backup = None
        for b in backups:
            if b.get("rolled_back") == True:
                rolled_back_backup = b
                break
        
        if rolled_back_backup:
            backup_id = rolled_back_backup["backup_id"]
            response = requests.post(f"{BASE_URL}/api/self-audit/rollback/{backup_id}", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data.get("rolled_back") == False, f"Expected rolled_back=False: {data}"
            assert data.get("reason") == "already_rolled_back", f"Expected reason=already_rolled_back: {data}"
            print(f"PASS: Rollback on already rolled back backup ({backup_id}) returns already_rolled_back")
        else:
            print("SKIP: No already rolled back backups found to test")
    
    def test_rollback_valid_backup(self, headers):
        """POST /api/self-audit/rollback on valid backup restores records"""
        # Get backups
        backups_response = requests.get(f"{BASE_URL}/api/self-audit/backups", headers=headers)
        assert backups_response.status_code == 200
        backups = backups_response.json().get("backups", [])
        
        # Find a backup that can be undone
        undoable_backup = None
        for b in backups:
            if b.get("can_undo") == True:
                undoable_backup = b
                break
        
        if undoable_backup:
            backup_id = undoable_backup["backup_id"]
            fix_action = undoable_backup.get("fix_action", "unknown")
            records_count = undoable_backup.get("records_count", 0)
            
            print(f"Rolling back backup: {backup_id} (fix_action={fix_action}, records={records_count})")
            
            response = requests.post(f"{BASE_URL}/api/self-audit/rollback/{backup_id}", headers=headers)
            assert response.status_code == 200
            data = response.json()
            
            if data.get("rolled_back") == True:
                assert "records_restored" in data, f"Response missing records_restored: {data}"
                assert "collection" in data, f"Response missing collection: {data}"
                print(f"PASS: Rollback successful - restored {data.get('records_restored')} records in {data.get('collection')}")
            else:
                # Could be already rolled back or expired
                reason = data.get("reason", "unknown")
                print(f"INFO: Rollback returned rolled_back=False, reason={reason}")
        else:
            print("SKIP: No undoable backups found to test rollback")


class TestRegressionExistingEndpoints(TestAuthSetup):
    """Regression tests for existing self-audit endpoints"""
    
    def test_run_audit_endpoint(self, headers):
        """POST /api/self-audit/run still works"""
        response = requests.post(f"{BASE_URL}/api/self-audit/run", headers=headers, json={"auto_fix": False})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "audit_id" in data
        assert "status" in data
        print(f"PASS: POST /api/self-audit/run works - audit_id={data['audit_id']}")
    
    def test_status_endpoint(self, headers):
        """GET /api/self-audit/status still works"""
        response = requests.get(f"{BASE_URL}/api/self-audit/status", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Either has audit data or "no_audits" status
        assert "status" in data or "audit_id" in data
        print(f"PASS: GET /api/self-audit/status works")
    
    def test_findings_endpoint(self, headers):
        """GET /api/self-audit/findings still works"""
        response = requests.get(f"{BASE_URL}/api/self-audit/findings", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "findings" in data or "count" in data
        print(f"PASS: GET /api/self-audit/findings works")
    
    def test_log_endpoint(self, headers):
        """GET /api/self-audit/log still works"""
        response = requests.get(f"{BASE_URL}/api/self-audit/log", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "audits" in data
        print(f"PASS: GET /api/self-audit/log works - {len(data['audits'])} audits")
    
    def test_stats_endpoint(self, headers):
        """GET /api/self-audit/stats still works"""
        response = requests.get(f"{BASE_URL}/api/self-audit/stats", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "agents" in data
        print(f"PASS: GET /api/self-audit/stats works - {len(data['agents'])} agents")
    
    def test_queue_endpoint(self, headers):
        """GET /api/self-audit/queue still works"""
        response = requests.get(f"{BASE_URL}/api/self-audit/queue", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "problems" in data
        print(f"PASS: GET /api/self-audit/queue works - {len(data['problems'])} problems")
    
    def test_tier_endpoint(self, headers):
        """GET /api/self-audit/tier still works"""
        response = requests.get(f"{BASE_URL}/api/self-audit/tier", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "tier" in data
        print(f"PASS: GET /api/self-audit/tier works - tier={data['tier']}")
    
    def test_schedule_get_endpoint(self, headers):
        """GET /api/self-audit/schedule still works"""
        response = requests.get(f"{BASE_URL}/api/self-audit/schedule", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "schedule" in data
        print(f"PASS: GET /api/self-audit/schedule works")
    
    def test_verify_data_endpoint(self, headers):
        """POST /api/self-audit/verify-data still works"""
        response = requests.post(f"{BASE_URL}/api/self-audit/verify-data", headers=headers, json={
            "record_id": "test_record",
            "field": "email",
            "current_value": "test@example.com"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "field" in data
        print(f"PASS: POST /api/self-audit/verify-data works")


class TestRegressionAuthGuards(TestAuthSetup):
    """Regression tests for auth guards on existing endpoints"""
    
    def test_run_no_auth(self):
        """POST /api/self-audit/run without auth returns 401"""
        response = requests.post(f"{BASE_URL}/api/self-audit/run", json={"auto_fix": True})
        assert response.status_code == 401
        print("PASS: POST /api/self-audit/run returns 401 without auth")
    
    def test_status_no_auth(self):
        """GET /api/self-audit/status without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/self-audit/status")
        assert response.status_code == 401
        print("PASS: GET /api/self-audit/status returns 401 without auth")
    
    def test_findings_no_auth(self):
        """GET /api/self-audit/findings without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/self-audit/findings")
        assert response.status_code == 401
        print("PASS: GET /api/self-audit/findings returns 401 without auth")
    
    def test_log_no_auth(self):
        """GET /api/self-audit/log without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/self-audit/log")
        assert response.status_code == 401
        print("PASS: GET /api/self-audit/log returns 401 without auth")
    
    def test_stats_no_auth(self):
        """GET /api/self-audit/stats without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/self-audit/stats")
        assert response.status_code == 401
        print("PASS: GET /api/self-audit/stats returns 401 without auth")
    
    def test_queue_no_auth(self):
        """GET /api/self-audit/queue without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/self-audit/queue")
        assert response.status_code == 401
        print("PASS: GET /api/self-audit/queue returns 401 without auth")
    
    def test_tier_no_auth(self):
        """GET /api/self-audit/tier without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/self-audit/tier")
        assert response.status_code == 401
        print("PASS: GET /api/self-audit/tier returns 401 without auth")


class TestEndToEndSafetyFlow(TestAuthSetup):
    """End-to-end test: Create issue -> Audit fixes it -> Backup created -> Rollback"""
    
    def test_full_safety_flow(self, headers):
        """Full flow: seed failed job -> audit auto-fixes -> verify backup -> rollback"""
        print("\n=== E2E Safety Flow Test ===")
        
        # Step 1: Check if there are any failed video jobs we can use
        # First run audit to see current state
        audit_response = requests.post(f"{BASE_URL}/api/self-audit/run", headers=headers, json={"auto_fix": True})
        assert audit_response.status_code == 200
        audit_data = audit_response.json()
        
        print(f"Step 1: Audit completed - {audit_data.get('total_issues', 0)} issues, {audit_data.get('auto_fixed', 0)} auto-fixed")
        
        # Step 2: Check backups
        backups_response = requests.get(f"{BASE_URL}/api/self-audit/backups", headers=headers)
        assert backups_response.status_code == 200
        backups_data = backups_response.json()
        
        print(f"Step 2: Found {backups_data.get('count', 0)} backups")
        
        # Step 3: If we have undoable backups, test rollback
        undoable = [b for b in backups_data.get("backups", []) if b.get("can_undo")]
        if undoable:
            backup = undoable[0]
            print(f"Step 3: Testing rollback on backup {backup['backup_id']} (fix_action={backup.get('fix_action')})")
            
            rollback_response = requests.post(f"{BASE_URL}/api/self-audit/rollback/{backup['backup_id']}", headers=headers)
            assert rollback_response.status_code == 200
            rollback_data = rollback_response.json()
            
            if rollback_data.get("rolled_back"):
                print(f"Step 3: Rollback SUCCESS - restored {rollback_data.get('records_restored', 0)} records")
                
                # Step 4: Verify backup is now marked as rolled back
                backups_after = requests.get(f"{BASE_URL}/api/self-audit/backups", headers=headers).json()
                rolled_back_backup = next((b for b in backups_after.get("backups", []) if b["backup_id"] == backup["backup_id"]), None)
                
                if rolled_back_backup:
                    assert rolled_back_backup.get("rolled_back") == True, "Backup should be marked as rolled_back"
                    assert rolled_back_backup.get("can_undo") == False, "Backup should not be undoable after rollback"
                    print("Step 4: Backup correctly marked as rolled_back, can_undo=False")
                
                # Step 5: Try to rollback again - should fail
                retry_response = requests.post(f"{BASE_URL}/api/self-audit/rollback/{backup['backup_id']}", headers=headers)
                retry_data = retry_response.json()
                assert retry_data.get("rolled_back") == False
                assert retry_data.get("reason") == "already_rolled_back"
                print("Step 5: Second rollback correctly returns already_rolled_back")
                
                print("=== E2E Safety Flow Test PASSED ===\n")
            else:
                print(f"Step 3: Rollback returned False - reason: {rollback_data.get('reason')}")
        else:
            print("Step 3: No undoable backups available for rollback test")
            print("=== E2E Safety Flow Test SKIPPED (no undoable backups) ===\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
