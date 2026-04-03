"""
Test Suite for Task 5: WhatsApp CRM Actions (28-Day Templates via wa.me links)

Tests the following endpoints:
- GET /api/admin/crm-actions - Returns pending WhatsApp CRM actions
- POST /api/admin/crm-actions/run-scheduler - Generates actions for all days (0,7,14,21,25,28,35)
- POST /api/admin/crm-actions/{order_id}/day/{day}/sent - Marks action as sent
- DELETE /api/admin/crm-actions/{order_id}/day/{day} - Deletes an action
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "test@admin.com"
ADMIN_PASSWORD = "admin123"


class TestWhatsAppCRMActions:
    """WhatsApp CRM Actions API tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("token") or data.get("access_token")
        pytest.skip(f"Authentication failed with status {response.status_code}: {response.text}")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get authentication headers"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    # ============================================
    # Test GET /api/admin/crm-actions
    # ============================================
    
    def test_get_crm_actions_requires_auth(self):
        """Test that CRM actions endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/crm-actions")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✅ GET /api/admin/crm-actions requires authentication")
    
    def test_get_crm_actions_success(self, auth_headers):
        """Test getting CRM actions with valid auth"""
        response = requests.get(
            f"{BASE_URL}/api/admin/crm-actions",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "actions" in data, "Response should contain 'actions'"
        assert "stats" in data, "Response should contain 'stats'"
        assert isinstance(data["actions"], list), "Actions should be a list"
        
        # Verify stats structure
        stats = data["stats"]
        assert "pending" in stats, "Stats should contain 'pending'"
        assert "sent" in stats, "Stats should contain 'sent'"
        assert "total" in stats, "Stats should contain 'total'"
        
        print(f"✅ GET /api/admin/crm-actions returned {len(data['actions'])} actions")
        print(f"   Stats: pending={stats['pending']}, sent={stats['sent']}, total={stats['total']}")
    
    def test_get_crm_actions_with_status_filter(self, auth_headers):
        """Test getting CRM actions with status filter"""
        # Test pending status
        response = requests.get(
            f"{BASE_URL}/api/admin/crm-actions?status=pending",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Test all status
        response = requests.get(
            f"{BASE_URL}/api/admin/crm-actions?status=all",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        print("✅ GET /api/admin/crm-actions works with status filters")
    
    def test_get_crm_actions_with_limit(self, auth_headers):
        """Test getting CRM actions with limit parameter"""
        response = requests.get(
            f"{BASE_URL}/api/admin/crm-actions?limit=5",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert len(data["actions"]) <= 5, "Should respect limit parameter"
        
        print("✅ GET /api/admin/crm-actions respects limit parameter")
    
    # ============================================
    # Test POST /api/admin/crm-actions/run-scheduler
    # ============================================
    
    def test_run_scheduler_requires_auth(self):
        """Test that scheduler endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/admin/crm-actions/run-scheduler")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✅ POST /api/admin/crm-actions/run-scheduler requires authentication")
    
    def test_run_scheduler_all_days(self, auth_headers):
        """Test running scheduler for all days (0,7,14,21,25,28,35)"""
        response = requests.post(
            f"{BASE_URL}/api/admin/crm-actions/run-scheduler",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Response should indicate success"
        assert "results" in data, "Response should contain 'results'"
        assert "total_actions_created" in data, "Response should contain 'total_actions_created'"
        
        # Verify all expected days are in results
        expected_days = ["day_0", "day_7", "day_14", "day_21", "day_25", "day_28", "day_35"]
        for day in expected_days:
            assert day in data["results"], f"Results should contain {day}"
        
        print(f"✅ POST /api/admin/crm-actions/run-scheduler executed successfully")
        print(f"   Total actions created: {data['total_actions_created']}")
        print(f"   Results per day: {data['results']}")
    
    def test_run_scheduler_specific_day(self, auth_headers):
        """Test running scheduler for a specific day"""
        response = requests.post(
            f"{BASE_URL}/api/admin/crm-actions/run-scheduler?day=7",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Response should indicate success"
        assert "results" in data, "Response should contain 'results'"
        
        # Should only have day_7 in results
        assert "day_7" in data["results"], "Results should contain day_7"
        
        print("✅ POST /api/admin/crm-actions/run-scheduler works with specific day parameter")
    
    # ============================================
    # Test POST /api/admin/crm-actions/{order_id}/day/{day}/sent
    # ============================================
    
    def test_mark_sent_requires_auth(self):
        """Test that mark-sent endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/admin/crm-actions/test-order-123/day/7/sent"
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✅ POST /api/admin/crm-actions/{order_id}/day/{day}/sent requires authentication")
    
    def test_mark_sent_nonexistent_action(self, auth_headers):
        """Test marking non-existent action as sent returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/admin/crm-actions/nonexistent-order-{uuid.uuid4()}/day/7/sent",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✅ POST /api/admin/crm-actions/{order_id}/day/{day}/sent returns 404 for non-existent action")
    
    # ============================================
    # Test DELETE /api/admin/crm-actions/{order_id}/day/{day}
    # ============================================
    
    def test_delete_action_requires_auth(self):
        """Test that delete endpoint requires authentication"""
        response = requests.delete(
            f"{BASE_URL}/api/admin/crm-actions/test-order-123/day/7"
        )
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✅ DELETE /api/admin/crm-actions/{order_id}/day/{day} requires authentication")
    
    def test_delete_nonexistent_action(self, auth_headers):
        """Test deleting non-existent action returns 404"""
        response = requests.delete(
            f"{BASE_URL}/api/admin/crm-actions/nonexistent-order-{uuid.uuid4()}/day/7",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✅ DELETE /api/admin/crm-actions/{order_id}/day/{day} returns 404 for non-existent action")


class TestWhatsAppTemplateGeneration:
    """Test the template message generation utilities"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("token") or data.get("access_token")
        pytest.skip(f"Authentication failed with status {response.status_code}")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get authentication headers"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_stats_by_day_returned(self, auth_headers):
        """Test that stats include breakdown by day"""
        response = requests.get(
            f"{BASE_URL}/api/admin/crm-actions",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        stats = data.get("stats", {})
        
        # by_day should exist in stats
        assert "by_day" in stats, "Stats should contain 'by_day' breakdown"
        
        print(f"✅ Stats include by_day breakdown: {stats.get('by_day', {})}")


class TestCRMActionsIntegration:
    """Integration tests for CRM actions workflow"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("token") or data.get("access_token")
        pytest.skip(f"Authentication failed with status {response.status_code}")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get authentication headers"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_full_workflow_scheduler_to_actions(self, auth_headers):
        """Test the full workflow: run scheduler -> get actions"""
        # Step 1: Run scheduler
        scheduler_response = requests.post(
            f"{BASE_URL}/api/admin/crm-actions/run-scheduler",
            headers=auth_headers
        )
        assert scheduler_response.status_code == 200, f"Scheduler failed: {scheduler_response.text}"
        
        scheduler_data = scheduler_response.json()
        total_created = scheduler_data.get("total_actions_created", 0)
        
        # Step 2: Get actions
        actions_response = requests.get(
            f"{BASE_URL}/api/admin/crm-actions?status=pending&limit=100",
            headers=auth_headers
        )
        assert actions_response.status_code == 200, f"Get actions failed: {actions_response.text}"
        
        actions_data = actions_response.json()
        
        print(f"✅ Full workflow test passed")
        print(f"   Scheduler created {total_created} new actions")
        print(f"   Total pending actions: {actions_data['stats']['pending']}")
        print(f"   Total sent actions: {actions_data['stats']['sent']}")
    
    def test_action_structure_validation(self, auth_headers):
        """Test that action objects have the expected structure"""
        response = requests.get(
            f"{BASE_URL}/api/admin/crm-actions?status=all&limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        actions = data.get("actions", [])
        
        if len(actions) > 0:
            action = actions[0]
            
            # Verify action structure
            expected_fields = ["customer_email", "customer_phone", "order_id", "day", "type", "message", "link", "status"]
            for field in expected_fields:
                assert field in action, f"Action should contain '{field}' field"
            
            # Verify type is whatsapp
            assert action["type"] == "whatsapp", "Action type should be 'whatsapp'"
            
            # Verify day is one of the expected values
            valid_days = [0, 7, 14, 21, 25, 28, 35]
            assert action["day"] in valid_days, f"Day {action['day']} not in expected days"
            
            # Verify link is a wa.me link
            if action.get("link"):
                assert "wa.me" in action["link"], "Link should be a wa.me link"
            
            print(f"✅ Action structure validated")
            print(f"   Sample action: customer={action.get('customer_email')}, day={action['day']}, status={action['status']}")
        else:
            print("⚠️ No actions found to validate structure - this is expected if no orders exist")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
