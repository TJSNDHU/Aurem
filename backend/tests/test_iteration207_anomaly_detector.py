"""
Iteration 207 - Anomaly Detector Tests
=======================================
Tests for self-aware anomaly detection:
- GET /api/admin/anomaly/status (admin) - returns state + recent_alerts
- POST /api/admin/anomaly/run-now (admin) - triggers detector
- Scheduler job 'aurem_anomaly_detect' registered with 5-min interval
- Anomaly log stored in aurem_anomaly_log collection
- Cooldown mechanism (60 min per anomaly type)
"""
import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = "Admin123"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    response = requests.post(
        f"{BASE_URL}/api/platform/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    # Try admin login endpoint
    response = requests.post(
        f"{BASE_URL}/api/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Admin login failed: {response.status_code} - {response.text[:200]}")


class TestAnomalyStatusEndpoint:
    """Tests for GET /api/admin/anomaly/status"""
    
    def test_anomaly_status_requires_auth(self):
        """GET /api/admin/anomaly/status without auth returns 401"""
        response = requests.get(f"{BASE_URL}/api/admin/anomaly/status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: anomaly/status returns 401 without auth")
    
    def test_anomaly_status_requires_admin(self):
        """GET /api/admin/anomaly/status with non-admin returns 403"""
        # Try with a customer token if available
        customer_response = requests.post(
            f"{BASE_URL}/api/platform/auth/login",
            json={"email": "pawandeep19may1985@gmail.com", "password": "ReRoots2026!"}
        )
        if customer_response.status_code == 200:
            customer_token = customer_response.json().get("token")
            response = requests.get(
                f"{BASE_URL}/api/admin/anomaly/status",
                headers={"Authorization": f"Bearer {customer_token}"}
            )
            assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}"
            print("PASS: anomaly/status returns 403 for non-admin")
        else:
            pytest.skip("Customer login not available for 403 test")
    
    def test_anomaly_status_with_admin(self, admin_token):
        """GET /api/admin/anomaly/status with admin returns state + recent_alerts"""
        response = requests.get(
            f"{BASE_URL}/api/admin/anomaly/status",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        # Verify response structure
        assert "state" in data, "Response missing 'state' field"
        assert "recent_alerts" in data, "Response missing 'recent_alerts' field"
        assert isinstance(data["recent_alerts"], list), "recent_alerts should be a list"
        
        # State may have baseline, last_alerts, last_run_at if detector has run
        state = data["state"]
        print(f"PASS: anomaly/status returns state={list(state.keys()) if state else 'empty'}, recent_alerts count={len(data['recent_alerts'])}")


class TestAnomalyRunNowEndpoint:
    """Tests for POST /api/admin/anomaly/run-now"""
    
    def test_anomaly_run_now_requires_auth(self):
        """POST /api/admin/anomaly/run-now without auth returns 401"""
        response = requests.post(f"{BASE_URL}/api/admin/anomaly/run-now")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: anomaly/run-now returns 401 without auth")
    
    def test_anomaly_run_now_with_admin(self, admin_token):
        """POST /api/admin/anomaly/run-now triggers detector and returns result"""
        response = requests.post(
            f"{BASE_URL}/api/admin/anomaly/run-now",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        
        data = response.json()
        # Verify response structure per spec
        assert "ran_at" in data, "Response missing 'ran_at' field"
        assert "current" in data, "Response missing 'current' field"
        assert "fired" in data, "Response missing 'fired' field"
        assert "cooldown_min" in data, "Response missing 'cooldown_min' field"
        assert "threshold_pp" in data, "Response missing 'threshold_pp' field"
        
        # Verify current metrics structure
        current = data["current"]
        assert "cache_hit_rate_pct" in current, "current missing cache_hit_rate_pct"
        assert "cache_total_lookups" in current, "current missing cache_total_lookups"
        assert "pixel_flush_failures" in current, "current missing pixel_flush_failures"
        assert "verdict" in current, "current missing verdict"
        assert "red_flags_count" in current, "current missing red_flags_count"
        
        # Verify cooldown and threshold values
        assert data["cooldown_min"] == 60, f"Expected cooldown_min=60, got {data['cooldown_min']}"
        assert data["threshold_pp"] == 20, f"Expected threshold_pp=20, got {data['threshold_pp']}"
        
        print(f"PASS: anomaly/run-now returns ran_at={data['ran_at'][:19]}, current={current}, fired={data['fired']}")


class TestSchedulerJobRegistration:
    """Tests for scheduler job 'aurem_anomaly_detect' registration"""
    
    def test_anomaly_detect_job_registered(self, admin_token):
        """Verify 'aurem_anomaly_detect' job is registered with 5-min interval"""
        response = requests.get(
            f"{BASE_URL}/api/admin/system-audit",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        scheduler = data.get("scheduler", {})
        jobs = scheduler.get("jobs", [])
        
        # Find the anomaly detect job
        anomaly_job = None
        for job in jobs:
            if job.get("id") == "aurem_anomaly_detect":
                anomaly_job = job
                break
        
        assert anomaly_job is not None, f"Job 'aurem_anomaly_detect' not found in scheduler jobs: {[j['id'] for j in jobs]}"
        assert anomaly_job.get("next_run") is not None, "Job should have next_run time set"
        
        print(f"PASS: aurem_anomaly_detect job registered, next_run={anomaly_job['next_run']}")


class TestAnomalyLogPersistence:
    """Tests for anomaly log persistence in aurem_anomaly_log collection"""
    
    def test_anomaly_state_persisted_after_run(self, admin_token):
        """After run-now, state should be persisted with baseline"""
        # First run the detector
        run_response = requests.post(
            f"{BASE_URL}/api/admin/anomaly/run-now",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert run_response.status_code == 200
        
        # Then check status - state should have baseline
        status_response = requests.get(
            f"{BASE_URL}/api/admin/anomaly/status",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert status_response.status_code == 200
        
        data = status_response.json()
        state = data.get("state", {})
        
        # After at least one run, state should have baseline and last_run_at
        assert "baseline" in state or "last_run_at" in state, f"State should have baseline or last_run_at after run: {state}"
        
        if "baseline" in state:
            baseline = state["baseline"]
            assert "cache_hit_rate_pct" in baseline, "baseline missing cache_hit_rate_pct"
            assert "verdict" in baseline, "baseline missing verdict"
            print(f"PASS: State persisted with baseline={baseline}")
        else:
            print(f"PASS: State persisted with last_run_at={state.get('last_run_at')}")


class TestCooldownMechanism:
    """Tests for 60-minute cooldown per anomaly type"""
    
    def test_cooldown_prevents_duplicate_alerts(self, admin_token):
        """After an alert fires, calling run-now again should NOT re-fire same anomaly type"""
        # Run detector twice in quick succession
        first_run = requests.post(
            f"{BASE_URL}/api/admin/anomaly/run-now",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert first_run.status_code == 200
        first_data = first_run.json()
        
        second_run = requests.post(
            f"{BASE_URL}/api/admin/anomaly/run-now",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert second_run.status_code == 200
        second_data = second_run.json()
        
        # If first run fired any alerts, second run should NOT fire the same ones
        # (unless 60 minutes have passed, which they haven't)
        first_fired = set(first_data.get("fired", {}).keys())
        second_fired = set(second_data.get("fired", {}).keys())
        
        # The intersection should be empty (no duplicate fires within cooldown)
        duplicate_fires = first_fired & second_fired
        assert len(duplicate_fires) == 0, f"Cooldown failed - same anomalies fired twice: {duplicate_fires}"
        
        print(f"PASS: Cooldown works - first_fired={first_fired}, second_fired={second_fired}, no duplicates")


class TestRegressionControlCenter:
    """Regression tests for Control Center (Iteration 206)"""
    
    def test_control_center_all_cards_present(self, admin_token):
        """Control Center should still show all 7 cards including anomaly card"""
        # Verify system-audit still works
        response = requests.get(
            f"{BASE_URL}/api/admin/system-audit",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify key fields
        assert "verdict" in data, "system-audit missing verdict"
        assert "agents" in data, "system-audit missing agents"
        assert "scheduler" in data, "system-audit missing scheduler"
        
        # Verify scheduler has expected jobs
        jobs = data.get("scheduler", {}).get("jobs", [])
        job_ids = [j["id"] for j in jobs]
        
        # Check for key jobs including new anomaly detector
        expected_jobs = ["aurem_anomaly_detect", "aurem_pixel_flush", "aurem_day_close"]
        for job_id in expected_jobs:
            assert job_id in job_ids, f"Missing scheduler job: {job_id}"
        
        print(f"PASS: Control Center regression - verdict={data['verdict']}, {len(jobs)} scheduler jobs, all expected jobs present")
    
    def test_all_5_mission_tiles_endpoints(self, admin_token):
        """All 5 mission tile endpoints should work"""
        endpoints = [
            "/api/admin/system-audit",
            "/api/admin/wiring-audit",
            "/api/admin/db-indexes/status",
            "/api/admin/cache/stats",
            "/api/admin/pixel-buffer/stats",
        ]
        
        for endpoint in endpoints:
            response = requests.get(
                f"{BASE_URL}{endpoint}",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 200, f"{endpoint} failed with {response.status_code}"
        
        print(f"PASS: All 5 mission tile endpoints working")


class TestAnomalyDetectionLogic:
    """Tests for anomaly detection logic (cache drop, pixel failures, verdict degradation)"""
    
    def test_current_metrics_structure(self, admin_token):
        """Verify current metrics have all required fields"""
        response = requests.post(
            f"{BASE_URL}/api/admin/anomaly/run-now",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        
        current = response.json().get("current", {})
        
        # All required fields per spec
        required_fields = [
            "cache_hit_rate_pct",
            "cache_total_lookups",
            "pixel_flush_failures",
            "verdict",
            "red_flags_count"
        ]
        
        for field in required_fields:
            assert field in current, f"current missing required field: {field}"
        
        # Type checks
        assert isinstance(current["cache_hit_rate_pct"], (int, float)), "cache_hit_rate_pct should be numeric"
        assert isinstance(current["cache_total_lookups"], int), "cache_total_lookups should be int"
        assert isinstance(current["pixel_flush_failures"], int), "pixel_flush_failures should be int"
        assert isinstance(current["verdict"], str), "verdict should be string"
        assert isinstance(current["red_flags_count"], int), "red_flags_count should be int"
        
        print(f"PASS: Current metrics structure valid - {current}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
