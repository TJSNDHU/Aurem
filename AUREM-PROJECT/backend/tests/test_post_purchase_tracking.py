"""
Post-Purchase Experience Tests - Order Tracking & Receipt Generation
Tests for /api/track, /api/receipt/{order_id}, and related endpoints
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestOrderTrackingEndpoint:
    """Tests for GET /api/track - Public order tracking endpoint"""
    
    def test_track_requires_order_and_email(self):
        """Test that endpoint requires both order number and email"""
        # Missing both
        response = requests.get(f"{BASE_URL}/api/track")
        assert response.status_code == 400
        assert "required" in response.json().get("detail", "").lower()
        
        # Missing email
        response = requests.get(f"{BASE_URL}/api/track", params={"order": "RR-2025-002"})
        assert response.status_code == 400
        
        # Missing order
        response = requests.get(f"{BASE_URL}/api/track", params={"email": "test@example.com"})
        assert response.status_code == 400
    
    def test_track_valid_order_success(self):
        """Test tracking with valid order number and matching email"""
        response = requests.get(f"{BASE_URL}/api/track", params={
            "order": "RR-2025-002",
            "email": "test2@example.com"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert data.get("success") == True
        assert "order" in data
        assert "shipping" in data
        assert "tracking" in data
        assert "timeline" in data
        
        # Validate order data
        order = data["order"]
        assert order.get("order_number") == "RR-2025-002"
        assert "order_status" in order
        assert "payment_status" in order
        assert "total" in order
        assert "items" in order
        assert "items_count" in order
        
        # Validate shipping data
        shipping = data["shipping"]
        assert "recipient" in shipping
        assert "address" in shipping
        assert "city" in shipping
        assert "province" in shipping
        assert "postal_code" in shipping
        assert "country" in shipping
        
        # Validate timeline structure
        timeline = data["timeline"]
        assert isinstance(timeline, list)
        assert len(timeline) > 0
        for step in timeline:
            assert "status" in step
            assert "description" in step
            assert "completed" in step
    
    def test_track_invalid_order_returns_404(self):
        """Test that non-existent order returns 404"""
        response = requests.get(f"{BASE_URL}/api/track", params={
            "order": "NONEXISTENT-ORDER-123",
            "email": "test@example.com"
        })
        
        assert response.status_code == 404
        assert "not found" in response.json().get("detail", "").lower()
    
    def test_track_email_mismatch_returns_403(self):
        """Test that wrong email returns 403"""
        response = requests.get(f"{BASE_URL}/api/track", params={
            "order": "RR-2025-002",
            "email": "wrongemail@example.com"
        })
        
        assert response.status_code == 403
        assert "email" in response.json().get("detail", "").lower()
    
    def test_track_timeline_has_order_placed(self):
        """Test that timeline includes order placed step"""
        response = requests.get(f"{BASE_URL}/api/track", params={
            "order": "RR-2025-002",
            "email": "test2@example.com"
        })
        
        assert response.status_code == 200
        timeline = response.json().get("timeline", [])
        
        # First step should be Order Placed
        order_placed = next((step for step in timeline if step["status"] == "Order Placed"), None)
        assert order_placed is not None
        assert order_placed["completed"] == True


class TestReceiptEndpoint:
    """Tests for GET /api/receipt/{order_id} - PDF receipt generation"""
    
    def test_receipt_requires_email(self):
        """Test that receipt endpoint requires email parameter"""
        response = requests.get(f"{BASE_URL}/api/receipt/RR-2025-002")
        
        assert response.status_code == 400
        assert "email" in response.json().get("detail", "").lower()
    
    def test_receipt_invalid_order_returns_404(self):
        """Test that non-existent order returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/receipt/NONEXISTENT-ORDER",
            params={"email": "test@example.com"}
        )
        
        assert response.status_code == 404
    
    def test_receipt_email_mismatch_returns_403(self):
        """Test that wrong email returns 403"""
        response = requests.get(
            f"{BASE_URL}/api/receipt/RR-2025-002",
            params={"email": "wrongemail@example.com"}
        )
        
        assert response.status_code == 403
        assert "email" in response.json().get("detail", "").lower()
    
    def test_receipt_valid_order_generates_pdf(self):
        """Test that valid paid order generates PDF receipt"""
        response = requests.get(
            f"{BASE_URL}/api/receipt/RR-2025-002",
            params={"email": "test2@example.com"}
        )
        
        # Should return PDF or error if order not paid
        if response.status_code == 200:
            # Validate PDF response
            assert response.headers.get("content-type") == "application/pdf"
            assert "content-disposition" in response.headers
            assert "attachment" in response.headers["content-disposition"]
            assert "ReRoots_Receipt" in response.headers["content-disposition"]
            
            # Validate PDF content starts with PDF magic bytes
            assert response.content[:4] == b'%PDF'
        elif response.status_code == 400:
            # Order not paid - acceptable behavior
            assert "not paid" in response.json().get("detail", "").lower()
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")


class TestReceiptSendEndpoint:
    """Tests for POST /api/receipt/{order_id}/send - Admin receipt email sending"""
    
    def test_send_receipt_requires_admin_auth(self):
        """Test that send receipt endpoint requires admin authentication"""
        response = requests.post(f"{BASE_URL}/api/receipt/RR-2025-002/send")
        
        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403]
    
    def test_send_receipt_with_admin_auth(self):
        """Test send receipt endpoint with admin authentication"""
        # First login as admin
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@admin.com",
            "password": "admin123"
        })
        
        if login_response.status_code != 200:
            pytest.skip("Admin login failed - skipping authenticated test")
        
        token = login_response.json().get("token")
        
        # Try to send receipt using Bearer token
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(
            f"{BASE_URL}/api/receipt/RR-2025-002/send",
            headers=headers
        )
        
        # Should succeed or fail gracefully due to SendGrid not configured
        # Status 200 = success, 500 = SendGrid not configured (expected)
        assert response.status_code in [200, 500]
        
        if response.status_code == 500:
            # Verify it's the expected SendGrid error (expected since SendGrid is MOCKED)
            detail = response.json().get("detail", "")
            assert "send" in detail.lower() or "email" in detail.lower() or "failed" in detail.lower()


class TestHealthAndIntegration:
    """Basic health and integration tests"""
    
    def test_api_health(self):
        """Test that API is responding"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
    
    def test_orders_exist_for_tracking(self):
        """Verify test orders exist in database for tracking tests"""
        # This is a diagnostic test to ensure seed data exists
        response = requests.get(f"{BASE_URL}/api/track", params={
            "order": "RR-2025-002",
            "email": "test2@example.com"
        })
        
        if response.status_code == 404:
            pytest.skip("Test order RR-2025-002 not found - seed data may be missing")
        
        assert response.status_code in [200, 403]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
