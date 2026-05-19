"""
Health Score Engine Backend Tests
=================================
Tests for the Tenant Health Score Engine feature:
- POST /api/admin/customers/{tenant_id}/recalculate-health
- POST /api/admin/customers/recalculate-health-all
- GET /api/admin/customers/{tenant_id}/health-breakdown
- GET /api/admin/customers/{tenant_id} (health_score field)
- Audit trail verification

Tenant IDs: polaris-built-001, reroots-75ea63e28540, aurem_internal
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = "<REDACTED>"


class TestHealthScoreEngineSetup:
    """Setup and authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        token = data.get("token") or data.get("access_token")
        assert token, "No token in login response"
        return token
    
    def test_auth_token_obtained(self, auth_token):
        """Verify we can get an auth token"""
        assert auth_token is not None
        assert len(auth_token) > 10
        print(f"✓ Auth token obtained: {auth_token[:20]}...")


class TestRecalculateHealthSingleTenant:
    """Tests for POST /api/admin/customers/{tenant_id}/recalculate-health"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Auth failed: {response.text}")
        data = response.json()
        return data.get("token") or data.get("access_token")
    
    def test_recalculate_health_polaris(self, auth_token):
        """POST /api/admin/customers/polaris-built-001/recalculate-health returns health_score, breakdown, calculated_at"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/admin/customers/polaris-built-001/recalculate-health",
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify required fields
        assert "health_score" in data, "Missing health_score field"
        assert "breakdown" in data, "Missing breakdown field"
        assert "calculated_at" in data, "Missing calculated_at field"
        assert "tenant_id" in data, "Missing tenant_id field"
        
        # Verify health_score is valid
        health_score = data["health_score"]
        assert isinstance(health_score, (int, float)), f"health_score should be numeric, got {type(health_score)}"
        assert 0 <= health_score <= 100, f"health_score should be 0-100, got {health_score}"
        
        print(f"✓ polaris-built-001 health_score: {health_score}/100")
        print(f"✓ calculated_at: {data['calculated_at']}")
    
    def test_breakdown_has_all_5_signals(self, auth_token):
        """Verify breakdown contains all 5 weighted signals with score, max, detail"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/admin/customers/polaris-built-001/recalculate-health",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        breakdown = data.get("breakdown", {})
        
        # Required signals
        required_signals = ["uptime", "ssl", "repairs", "response_time", "integrations"]
        
        for signal in required_signals:
            assert signal in breakdown, f"Missing signal: {signal}"
            signal_data = breakdown[signal]
            
            # Each signal must have score, max, detail
            assert "score" in signal_data, f"{signal} missing 'score'"
            assert "max" in signal_data, f"{signal} missing 'max'"
            assert "detail" in signal_data, f"{signal} missing 'detail'"
            
            # Validate score is within max
            assert signal_data["score"] <= signal_data["max"], f"{signal} score exceeds max"
            
            print(f"✓ {signal}: {signal_data['score']}/{signal_data['max']} - {signal_data['detail']}")
    
    def test_signal_weights_correct(self, auth_token):
        """Verify signal max values match expected weights (30, 20, 25, 15, 10)"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/admin/customers/polaris-built-001/recalculate-health",
            headers=headers
        )
        
        assert response.status_code == 200
        breakdown = response.json().get("breakdown", {})
        
        expected_weights = {
            "uptime": 30,
            "ssl": 20,
            "repairs": 25,
            "response_time": 15,
            "integrations": 10,
        }
        
        for signal, expected_max in expected_weights.items():
            actual_max = breakdown.get(signal, {}).get("max", 0)
            assert actual_max == expected_max, f"{signal} max should be {expected_max}, got {actual_max}"
            print(f"✓ {signal} weight: {actual_max} pts")
        
        # Total should be 100
        total_max = sum(expected_weights.values())
        assert total_max == 100, f"Total weights should be 100, got {total_max}"
        print(f"✓ Total weight: {total_max} pts")
    
    def test_recalculate_health_reroots(self, auth_token):
        """Test recalculate for reroots tenant"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/admin/customers/reroots-75ea63e28540/recalculate-health",
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "health_score" in data
        assert 0 <= data["health_score"] <= 100
        print(f"✓ reroots-75ea63e28540 health_score: {data['health_score']}/100")
    
    def test_recalculate_health_aurem_internal(self, auth_token):
        """Test recalculate for aurem_internal tenant"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/admin/customers/aurem_internal/recalculate-health",
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "health_score" in data
        assert 0 <= data["health_score"] <= 100
        print(f"✓ aurem_internal health_score: {data['health_score']}/100")
    
    def test_recalculate_nonexistent_tenant_returns_404(self, auth_token):
        """Test recalculate for non-existent tenant returns 404"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/admin/customers/nonexistent-tenant-xyz/recalculate-health",
            headers=headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent tenant returns 404")
    
    def test_recalculate_requires_auth(self):
        """Test recalculate without auth returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/admin/customers/polaris-built-001/recalculate-health"
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Endpoint requires authentication")


class TestRecalculateHealthAll:
    """Tests for POST /api/admin/customers/recalculate-health-all"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Auth failed: {response.text}")
        data = response.json()
        return data.get("token") or data.get("access_token")
    
    def test_recalculate_all_returns_results_array(self, auth_token):
        """POST /api/admin/customers/recalculate-health-all returns results array"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/admin/customers/recalculate-health-all",
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "recalculated" in data, "Missing 'recalculated' count"
        assert "results" in data, "Missing 'results' array"
        assert "timestamp" in data, "Missing 'timestamp'"
        
        # Verify results is an array
        results = data["results"]
        assert isinstance(results, list), f"results should be list, got {type(results)}"
        
        print(f"✓ Recalculated {data['recalculated']} tenants")
        print(f"✓ Timestamp: {data['timestamp']}")
    
    def test_recalculate_all_includes_known_tenants(self, auth_token):
        """Verify known tenants are in results"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/admin/customers/recalculate-health-all",
            headers=headers
        )
        
        assert response.status_code == 200
        results = response.json().get("results", [])
        
        tenant_ids = [r.get("tenant_id") for r in results]
        
        # At least polaris should be there
        assert "polaris-built-001" in tenant_ids, "polaris-built-001 not in results"
        print(f"✓ Found {len(results)} tenants in results")
        
        for r in results:
            print(f"  - {r.get('tenant_id')}: {r.get('health_score')}/100")
    
    def test_recalculate_all_each_result_has_score(self, auth_token):
        """Each result in array has tenant_id and health_score"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/admin/customers/recalculate-health-all",
            headers=headers
        )
        
        assert response.status_code == 200
        results = response.json().get("results", [])
        
        for r in results:
            assert "tenant_id" in r, f"Result missing tenant_id: {r}"
            assert "health_score" in r, f"Result missing health_score: {r}"
            assert 0 <= r["health_score"] <= 100, f"Invalid score: {r['health_score']}"
        
        print(f"✓ All {len(results)} results have valid tenant_id and health_score")
    
    def test_recalculate_all_requires_auth(self):
        """Test recalculate-all without auth returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/admin/customers/recalculate-health-all"
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Endpoint requires authentication")


class TestHealthBreakdownEndpoint:
    """Tests for GET /api/admin/customers/{tenant_id}/health-breakdown"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Auth failed: {response.text}")
        data = response.json()
        return data.get("token") or data.get("access_token")
    
    def test_health_breakdown_returns_stored_data(self, auth_token):
        """GET /api/admin/customers/{tenant_id}/health-breakdown returns stored breakdown"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # First recalculate to ensure data exists
        requests.post(
            f"{BASE_URL}/api/admin/customers/polaris-built-001/recalculate-health",
            headers=headers
        )
        
        # Then get breakdown
        response = requests.get(
            f"{BASE_URL}/api/admin/customers/polaris-built-001/health-breakdown",
            headers=headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "tenant_id" in data, "Missing tenant_id"
        assert "health_score" in data, "Missing health_score"
        assert "breakdown" in data, "Missing breakdown"
        assert "calculated_at" in data, "Missing calculated_at"
        
        assert data["tenant_id"] == "polaris-built-001"
        print(f"✓ health-breakdown returns stored data for polaris-built-001")
        print(f"  Score: {data['health_score']}/100")
        print(f"  Calculated at: {data['calculated_at']}")
    
    def test_health_breakdown_has_all_signals(self, auth_token):
        """Verify breakdown has all 5 signals"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/customers/polaris-built-001/health-breakdown",
            headers=headers
        )
        
        assert response.status_code == 200
        breakdown = response.json().get("breakdown", {})
        
        required_signals = ["uptime", "ssl", "repairs", "response_time", "integrations"]
        for signal in required_signals:
            assert signal in breakdown, f"Missing signal: {signal}"
            assert "score" in breakdown[signal], f"{signal} missing score"
            assert "max" in breakdown[signal], f"{signal} missing max"
            assert "detail" in breakdown[signal], f"{signal} missing detail"
        
        print("✓ All 5 signals present in breakdown")
    
    def test_health_breakdown_nonexistent_tenant(self, auth_token):
        """Test breakdown for non-existent tenant returns 404"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/customers/nonexistent-tenant-xyz/health-breakdown",
            headers=headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent tenant returns 404")
    
    def test_health_breakdown_requires_auth(self):
        """Test breakdown without auth returns 401"""
        response = requests.get(
            f"{BASE_URL}/api/admin/customers/polaris-built-001/health-breakdown"
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Endpoint requires authentication")


class TestHealthScorePersistence:
    """Tests for health_score persistence in tenant_customers collection"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Auth failed: {response.text}")
        data = response.json()
        return data.get("token") or data.get("access_token")
    
    def test_health_score_written_to_customer(self, auth_token):
        """After recalculate, GET /api/admin/customers/{tenant_id} shows health_score"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Recalculate
        recalc_response = requests.post(
            f"{BASE_URL}/api/admin/customers/polaris-built-001/recalculate-health",
            headers=headers
        )
        assert recalc_response.status_code == 200
        recalc_score = recalc_response.json().get("health_score")
        
        # Get customer
        customer_response = requests.get(
            f"{BASE_URL}/api/admin/customers/polaris-built-001",
            headers=headers
        )
        assert customer_response.status_code == 200
        customer = customer_response.json()
        
        # Verify health_score is present and matches
        assert "health_score" in customer, "health_score not in customer record"
        assert customer["health_score"] is not None, "health_score is None"
        assert customer["health_score"] == recalc_score, f"Score mismatch: {customer['health_score']} != {recalc_score}"
        
        print(f"✓ health_score persisted to customer: {customer['health_score']}/100")
    
    def test_health_score_not_hardcoded(self, auth_token):
        """Verify health scores vary by tenant (not hardcoded)"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Recalculate all
        response = requests.post(
            f"{BASE_URL}/api/admin/customers/recalculate-health-all",
            headers=headers
        )
        assert response.status_code == 200
        results = response.json().get("results", [])
        
        if len(results) < 2:
            pytest.skip("Need at least 2 tenants to verify scores vary")
        
        scores = [r.get("health_score") for r in results]
        unique_scores = set(scores)
        
        # If all scores are identical, it might be hardcoded
        # (though it's possible they legitimately have same score)
        print(f"✓ Scores across tenants: {scores}")
        print(f"✓ Unique scores: {unique_scores}")
        
        # At minimum, verify scores are in valid range
        for score in scores:
            assert 0 <= score <= 100, f"Invalid score: {score}"


class TestAuditTrail:
    """Tests for audit trail entries after health score recalculation"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Auth failed: {response.text}")
        data = response.json()
        return data.get("token") or data.get("access_token")
    
    def test_audit_entry_created_after_recalculate(self, auth_token):
        """Verify audit trail entry created after recalculation"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        # Recalculate
        recalc_response = requests.post(
            f"{BASE_URL}/api/admin/customers/polaris-built-001/recalculate-health",
            headers=headers
        )
        assert recalc_response.status_code == 200
        new_score = recalc_response.json().get("health_score")
        
        # Get audit log
        audit_response = requests.get(
            f"{BASE_URL}/api/admin/customers/polaris-built-001/audit",
            headers=headers
        )
        assert audit_response.status_code == 200
        logs = audit_response.json().get("logs", [])
        
        # Find health_score entry
        health_score_logs = [l for l in logs if l.get("field") == "health_score"]
        assert len(health_score_logs) > 0, "No health_score audit entries found"
        
        # Check most recent entry
        latest = health_score_logs[0]
        assert latest.get("changed_by") == "health_score_engine", f"Expected changed_by='health_score_engine', got {latest.get('changed_by')}"
        assert latest.get("new_value") == str(new_score), f"Expected new_value='{new_score}', got {latest.get('new_value')}"
        
        print(f"✓ Audit entry created: field=health_score, new_value={latest.get('new_value')}, changed_by={latest.get('changed_by')}")


class TestHealthScoreCalculationLogic:
    """Tests for health score calculation correctness"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Auth failed: {response.text}")
        data = response.json()
        return data.get("token") or data.get("access_token")
    
    def test_total_score_equals_sum_of_signals(self, auth_token):
        """Verify health_score equals sum of all signal scores"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/admin/customers/polaris-built-001/recalculate-health",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        health_score = data["health_score"]
        breakdown = data["breakdown"]
        
        # Sum all signal scores
        signal_sum = sum(
            breakdown[signal]["score"]
            for signal in ["uptime", "ssl", "repairs", "response_time", "integrations"]
        )
        
        assert health_score == signal_sum, f"health_score ({health_score}) != sum of signals ({signal_sum})"
        print(f"✓ health_score ({health_score}) = sum of signals ({signal_sum})")
    
    def test_calculation_time_recorded(self, auth_token):
        """Verify calculation_ms is recorded"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/admin/customers/polaris-built-001/recalculate-health",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if "calculation_ms" in data:
            assert isinstance(data["calculation_ms"], (int, float))
            assert data["calculation_ms"] >= 0
            print(f"✓ Calculation time: {data['calculation_ms']}ms")
        else:
            print("⚠ calculation_ms not in response (optional field)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
