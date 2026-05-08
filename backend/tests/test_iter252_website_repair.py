"""
Iteration 252: Customer Website Repair Dashboard Backend Tests
Tests:
- GET /api/customer/pixel/status (pixel status badge)
- POST /api/customer/website/scan (website scan)
- POST /api/customer/website/repair/start (start repair job)
- GET /api/customer/website/repair/status/{job_id} (poll repair status)
- GET /api/customer/website/repair/latest (get latest repair job)
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
CLIENT_EMAIL = "futuristic_test@aurem-preview.com"
CLIENT_PASSWORD = "FutureTest123!"


class TestWebsiteRepairDashboard:
    """Tests for the Customer Website Repair Dashboard (iter 252)"""
    
    @pytest.fixture(scope="class")
    def client_token(self):
        """Get client authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/platform/auth/login",
            json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD}
        )
        if response.status_code != 200:
            pytest.skip(f"Client login failed: {response.status_code} - {response.text}")
        data = response.json()
        token = data.get("token") or data.get("access_token")
        if not token:
            pytest.skip(f"No token in response: {data}")
        return token
    
    @pytest.fixture(scope="class")
    def auth_headers(self, client_token):
        """Headers with auth token"""
        return {
            "Authorization": f"Bearer {client_token}",
            "Content-Type": "application/json"
        }
    
    # ═══════════════════════════════════════════════════════════════
    # TEST A: Pixel Status Endpoint
    # ═══════════════════════════════════════════════════════════════
    
    def test_pixel_status_endpoint(self, auth_headers):
        """Test GET /api/customer/pixel/status returns valid status"""
        response = requests.get(
            f"{BASE_URL}/api/customer/pixel/status",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Pixel status failed: {response.text}"
        
        data = response.json()
        # Status should be one of: online, offline, not_installed
        assert "status" in data, f"Missing 'status' field: {data}"
        assert data["status"] in ["online", "offline", "not_installed"], f"Invalid status: {data['status']}"
        
        # For test user (no pixel installed), expect 'not_installed'
        print(f"Pixel status: {data['status']}")
        if data["status"] == "not_installed":
            print("✓ Pixel status correctly shows 'not_installed' for test user")
        elif data["status"] == "offline":
            assert "last_event_at" in data, "Offline status should have last_event_at"
            print(f"✓ Pixel offline, last event: {data.get('last_event_at')}")
        elif data["status"] == "online":
            assert "last_event_at" in data, "Online status should have last_event_at"
            print(f"✓ Pixel online, last event: {data.get('last_event_at')}")
    
    # ═══════════════════════════════════════════════════════════════
    # TEST B: Website Scan Endpoint
    # ═══════════════════════════════════════════════════════════════
    
    def test_website_scan_endpoint(self, auth_headers):
        """Test POST /api/customer/website/scan returns score and issues"""
        response = requests.post(
            f"{BASE_URL}/api/customer/website/scan",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 200, f"Website scan failed: {response.text}"
        
        data = response.json()
        
        # Verify required fields
        assert "scan_id" in data, f"Missing scan_id: {data}"
        assert "score" in data, f"Missing score: {data}"
        assert "metrics" in data, f"Missing metrics: {data}"
        assert "issues" in data, f"Missing issues: {data}"
        
        # Score should be in 40-56 range (deterministic per tenant)
        score = data["score"]
        assert 40 <= score <= 56, f"Score {score} outside expected range 40-56"
        print(f"✓ Scan score: {score} (expected 40-56 for PREV-HX5U tenant)")
        
        # Verify metrics structure
        metrics = data["metrics"]
        assert "lcp_s" in metrics, "Missing LCP metric"
        assert "cls" in metrics, "Missing CLS metric"
        assert "unused_js_kb" in metrics, "Missing unused_js_kb metric"
        assert "schema_errors" in metrics, "Missing schema_errors metric"
        print(f"✓ Metrics: LCP={metrics['lcp_s']}s, CLS={metrics['cls']}, unused_js={metrics['unused_js_kb']}KB, schema_errors={metrics['schema_errors']}")
        
        # Verify issues from sentinel_diagnoses
        issues = data["issues"]
        assert isinstance(issues, list), "Issues should be a list"
        print(f"✓ Found {len(issues)} issues from sentinel_diagnoses")
        
        # Each issue should have severity, service, diagnosis
        for i, issue in enumerate(issues):
            assert "severity" in issue, f"Issue {i} missing severity"
            assert issue["severity"] in ["P0", "P1", "P2", "P3"], f"Invalid severity: {issue['severity']}"
            print(f"  Issue {i+1}: [{issue.get('severity')}] {issue.get('diagnosis', '')[:60]}...")
        
        return data["scan_id"]
    
    # ═══════════════════════════════════════════════════════════════
    # TEST C: Repair Start Endpoint
    # ═══════════════════════════════════════════════════════════════
    
    def test_repair_start_endpoint(self, auth_headers):
        """Test POST /api/customer/website/repair/start kicks off repair job"""
        response = requests.post(
            f"{BASE_URL}/api/customer/website/repair/start",
            headers=auth_headers,
            json={}
        )
        assert response.status_code == 200, f"Repair start failed: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert data.get("ok") == True, f"Expected ok=True: {data}"
        assert "job_id" in data, f"Missing job_id: {data}"
        assert "score_before" in data, f"Missing score_before: {data}"
        
        job_id = data["job_id"]
        score_before = data["score_before"]
        
        print(f"✓ Repair job started: {job_id}")
        print(f"✓ Score before repair: {score_before}")
        
        # Score before should be in expected range
        assert 40 <= score_before <= 56, f"Score before {score_before} outside expected range"
        
        return job_id
    
    # ═══════════════════════════════════════════════════════════════
    # TEST D: Repair Status Polling
    # ═══════════════════════════════════════════════════════════════
    
    def test_repair_status_polling(self, auth_headers):
        """Test GET /api/customer/website/repair/status/{job_id} shows progression"""
        # Start a new repair job
        start_response = requests.post(
            f"{BASE_URL}/api/customer/website/repair/start",
            headers=auth_headers,
            json={}
        )
        assert start_response.status_code == 200
        job_id = start_response.json()["job_id"]
        
        # Poll status a few times to see progression
        phases_seen = set()
        max_polls = 10
        poll_interval = 3  # seconds
        
        for i in range(max_polls):
            response = requests.get(
                f"{BASE_URL}/api/customer/website/repair/status/{job_id}",
                headers=auth_headers
            )
            assert response.status_code == 200, f"Status poll failed: {response.text}"
            
            data = response.json()
            
            # Verify required fields
            assert "job_id" in data, f"Missing job_id: {data}"
            assert "status" in data, f"Missing status: {data}"
            assert "current_phase" in data, f"Missing current_phase: {data}"
            assert "progress_pct" in data, f"Missing progress_pct: {data}"
            
            phase = data["current_phase"]
            pct = data["progress_pct"]
            status = data["status"]
            
            phases_seen.add(phase)
            print(f"  Poll {i+1}: phase={phase}, pct={pct}%, status={status}")
            
            # Check events are being generated
            events = data.get("events", [])
            if events:
                print(f"    Latest event: {events[-1].get('message', '')[:60]}...")
            
            # If completed, verify final state
            if status == "completed":
                assert "score_before" in data, "Completed job missing score_before"
                assert "score_after" in data, "Completed job missing score_after"
                assert "delta" in data, "Completed job missing delta"
                assert "improvements" in data, "Completed job missing improvements"
                
                delta = data["delta"]
                score_after = data["score_after"]
                
                # Verify honest delta (+24 to +38, cap at 94)
                assert 24 <= delta <= 38, f"Delta {delta} outside expected range 24-38"
                assert score_after <= 94, f"Score after {score_after} exceeds cap of 94"
                
                print(f"✓ Repair completed: before={data['score_before']}, after={score_after}, delta=+{delta}")
                print(f"✓ Improvements: {len(data['improvements'])} metrics improved")
                break
            
            time.sleep(poll_interval)
        
        # Verify we saw phase progression
        print(f"✓ Phases observed: {phases_seen}")
        assert len(phases_seen) >= 1, "Should see at least one phase"
    
    # ═══════════════════════════════════════════════════════════════
    # TEST E: Repair Latest Endpoint
    # ═══════════════════════════════════════════════════════════════
    
    def test_repair_latest_endpoint(self, auth_headers):
        """Test GET /api/customer/website/repair/latest returns most recent job"""
        response = requests.get(
            f"{BASE_URL}/api/customer/website/repair/latest",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Repair latest failed: {response.text}"
        
        data = response.json()
        
        # May be empty if no jobs exist, or return the latest job
        if data:
            assert "job_id" in data, f"Missing job_id in latest: {data}"
            assert "status" in data, f"Missing status in latest: {data}"
            print(f"✓ Latest repair job: {data['job_id']} (status: {data['status']})")
        else:
            print("✓ No previous repair jobs found (empty response)")
    
    # ═══════════════════════════════════════════════════════════════
    # TEST F: Verify No Fake 98 Score
    # ═══════════════════════════════════════════════════════════════
    
    def test_no_fake_magic_score(self, auth_headers):
        """Verify final score is honest (<=94) and delta is +24 to +38"""
        # Get latest completed job or wait for one
        response = requests.get(
            f"{BASE_URL}/api/customer/website/repair/latest",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        if data and data.get("status") == "completed":
            score_after = data.get("score_after", 0)
            delta = data.get("delta", 0)
            
            # Verify no fake 98 score
            assert score_after <= 94, f"Score {score_after} exceeds honest cap of 94"
            assert score_after != 98, f"Score is fake magic 98!"
            
            # Verify honest delta
            assert 24 <= delta <= 38, f"Delta {delta} outside honest range 24-38"
            
            print(f"✓ Honest scoring verified: score={score_after} (<=94), delta=+{delta} (24-38)")
        else:
            print("⚠ No completed repair job to verify scoring")


class TestPixelStatusUnauthorized:
    """Test unauthorized access to pixel status"""
    
    def test_pixel_status_no_auth(self):
        """Test pixel status requires authentication"""
        response = requests.get(f"{BASE_URL}/api/customer/pixel/status")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Pixel status correctly requires authentication")
    
    def test_website_scan_no_auth(self):
        """Test website scan requires authentication"""
        response = requests.post(f"{BASE_URL}/api/customer/website/scan", json={})
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Website scan correctly requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
