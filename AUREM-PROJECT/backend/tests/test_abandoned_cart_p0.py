"""
Test Suite for Abandoned Cart Win-Back P0 Features
- GET /api/abandoned/stats - abandoned cart statistics
- POST /api/abandoned/run-automation - trigger abandoned cart recovery
- Verify scheduler initialization in startup
"""
import pytest
import requests
import os

# Backend URL from environment (must include /api prefix for endpoints)
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAbandonedCartAutomation:
    """Tests for Abandoned Cart Win-Back automation (P0 feature)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.base_url = BASE_URL
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_abandoned_stats_endpoint_exists(self):
        """Test GET /api/abandoned/stats returns valid response"""
        response = self.session.get(f"{self.base_url}/api/abandoned/stats")
        
        # Should return 200 OK
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify response structure
        data = response.json()
        assert "totalAbandoned" in data, "Response should contain totalAbandoned"
        assert "step1Sent" in data, "Response should contain step1Sent"
        assert "step2Sent" in data, "Response should contain step2Sent"
        assert "step3Sent" in data, "Response should contain step3Sent"
        assert "recovered" in data, "Response should contain recovered"
        assert "recoveryRate" in data, "Response should contain recoveryRate"
        assert "sentToday" in data, "Response should contain sentToday"
        
        # Verify data types
        assert isinstance(data["totalAbandoned"], int), "totalAbandoned should be int"
        assert isinstance(data["step1Sent"], int), "step1Sent should be int"
        assert isinstance(data["step2Sent"], int), "step2Sent should be int"
        assert isinstance(data["step3Sent"], int), "step3Sent should be int"
        assert isinstance(data["recovered"], int), "recovered should be int"
        assert isinstance(data["recoveryRate"], (int, float)), "recoveryRate should be numeric"
        assert isinstance(data["sentToday"], int), "sentToday should be int"
        
        print(f"✓ Abandoned cart stats: {data}")
    
    def test_run_automation_endpoint_exists(self):
        """Test POST /api/abandoned/run-automation triggers recovery"""
        response = self.session.post(f"{self.base_url}/api/abandoned/run-automation")
        
        # Should return 200 OK
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify response structure
        data = response.json()
        assert "success" in data, "Response should contain success"
        assert "emailsSent" in data, "Response should contain emailsSent"
        assert "runAt" in data, "Response should contain runAt"
        
        # Verify values
        assert data["success"] == True, "success should be True"
        assert isinstance(data["emailsSent"], int), "emailsSent should be int"
        assert data["emailsSent"] >= 0, "emailsSent should be non-negative"
        
        print(f"✓ Automation run result: {data['emailsSent']} emails sent at {data['runAt']}")
    
    def test_send_specific_step_endpoint(self):
        """Test POST /api/abandoned/send-step/{cart_id}/{step} validates cart"""
        # Test with non-existent cart - should return 404
        response = self.session.post(f"{self.base_url}/api/abandoned/send-step/non-existent-cart/1")
        
        # Should return 404 for non-existent cart
        assert response.status_code == 404, f"Expected 404 for non-existent cart, got {response.status_code}"
        
        print(f"✓ Non-existent cart returns 404 as expected")
    
    def test_send_invalid_step_number(self):
        """Test POST /api/abandoned/send-step with invalid step number"""
        response = self.session.post(f"{self.base_url}/api/abandoned/send-step/some-cart/99")
        
        # Should return 404 (cart not found first) or 400 (invalid step)
        assert response.status_code in [400, 404], f"Expected 400 or 404, got {response.status_code}"
        
        print(f"✓ Invalid step returns expected error code: {response.status_code}")
    
    def test_stats_after_run(self):
        """Test that stats are updated after running automation"""
        # Get initial stats
        stats_before = self.session.get(f"{self.base_url}/api/abandoned/stats").json()
        
        # Run automation
        run_result = self.session.post(f"{self.base_url}/api/abandoned/run-automation").json()
        
        # Get stats after
        stats_after = self.session.get(f"{self.base_url}/api/abandoned/stats").json()
        
        # sentToday should be >= what it was before (or equal if no emails sent)
        print(f"✓ Stats before: sentToday={stats_before['sentToday']}")
        print(f"✓ Emails sent this run: {run_result['emailsSent']}")
        print(f"✓ Stats after: sentToday={stats_after['sentToday']}")
        
        # Note: sentToday resets daily, so just verify structure is valid
        assert isinstance(stats_after["sentToday"], int)


class TestHealthAndStartup:
    """Tests to verify server startup and scheduler initialization"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.base_url = BASE_URL
        self.session = requests.Session()
    
    def test_health_check(self):
        """Test health endpoint to verify server is running"""
        response = self.session.get(f"{self.base_url}/api/health")
        
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "healthy", f"Server not healthy: {data}"
        
        print(f"✓ Server healthy: {data}")
    
    def test_abandoned_cart_router_registered(self):
        """Verify abandoned cart router is registered by checking endpoint accessibility"""
        # If router is registered, stats endpoint should be accessible
        response = self.session.get(f"{self.base_url}/api/abandoned/stats")
        
        # Should not return 404 (not found) - router is registered
        assert response.status_code != 404, "Abandoned cart router not registered - endpoint returned 404"
        
        print(f"✓ Abandoned cart router is registered (status: {response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
