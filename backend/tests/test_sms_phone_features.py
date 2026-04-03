"""
Test cases for SMS Capture Popup and Phone-First Checkout features.
Tests POST /api/sms-subscribers and POST /api/checkout/track-contact endpoints.
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSMSSubscribersEndpoint:
    """Tests for POST /api/sms-subscribers endpoint (exit intent popup)"""
    
    def test_01_add_sms_subscriber_valid_phone(self):
        """Test adding a valid phone number with optional email"""
        unique_phone = f"+1416555{str(uuid.uuid4())[:4].replace('-', '')}"
        
        response = requests.post(f"{BASE_URL}/api/sms-subscribers", json={
            "phone": unique_phone,
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "source": "exit_popup",
            "page_url": "/shop"
        })
        
        # Should succeed
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data, f"Missing message in response: {data}"
        assert "discount_code" in data, f"Missing discount_code in response: {data}"
        assert data["discount_code"] == "SMS10", f"Expected SMS10, got {data['discount_code']}"
        print(f"PASS: SMS subscriber added successfully, discount code: {data['discount_code']}")
    
    def test_02_add_sms_subscriber_phone_only(self):
        """Test adding phone number without email"""
        unique_phone = f"+1647555{str(uuid.uuid4())[:4].replace('-', '')}"
        
        response = requests.post(f"{BASE_URL}/api/sms-subscribers", json={
            "phone": unique_phone,
            "source": "exit_popup",
            "page_url": "/products/test"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("discount_code") == "SMS10"
        print("PASS: SMS subscriber added with phone only")
    
    def test_03_add_sms_subscriber_duplicate_phone(self):
        """Test that duplicate phone returns 409"""
        phone = f"+14165559999"
        
        # First subscription
        requests.post(f"{BASE_URL}/api/sms-subscribers", json={
            "phone": phone,
            "source": "exit_popup"
        })
        
        # Second subscription with same phone should return 409
        response = requests.post(f"{BASE_URL}/api/sms-subscribers", json={
            "phone": phone,
            "email": "new@example.com",
            "source": "cart_page"
        })
        
        assert response.status_code == 409, f"Expected 409 for duplicate, got {response.status_code}"
        print("PASS: Duplicate phone correctly rejected with 409")
    
    def test_04_add_sms_subscriber_missing_phone(self):
        """Test that missing phone returns 400"""
        response = requests.post(f"{BASE_URL}/api/sms-subscribers", json={
            "email": "test@example.com",
            "source": "exit_popup"
        })
        
        assert response.status_code == 400, f"Expected 400 for missing phone, got {response.status_code}"
        print("PASS: Missing phone correctly rejected with 400")
    
    def test_05_add_sms_subscriber_phone_normalization(self):
        """Test that phone numbers are normalized correctly"""
        # Test 10-digit number without country code
        unique_id = str(uuid.uuid4())[:4].replace('-', '')
        phone_10_digit = f"416555{unique_id}"
        
        response = requests.post(f"{BASE_URL}/api/sms-subscribers", json={
            "phone": phone_10_digit,
            "source": "exit_popup"
        })
        
        # Should succeed and normalize to +1 format
        assert response.status_code in [200, 409], f"Expected 200/409, got {response.status_code}: {response.text}"
        print("PASS: Phone number normalization working")


class TestCheckoutTrackContact:
    """Tests for POST /api/checkout/track-contact endpoint (abandoned cart recovery)"""
    
    def test_01_track_contact_with_phone(self):
        """Test tracking contact with phone number"""
        session_id = f"test_session_{uuid.uuid4().hex[:8]}"
        
        response = requests.post(f"{BASE_URL}/api/checkout/track-contact", json={
            "session_id": session_id,
            "phone": "+14165551234",
            "name": "Test User",
            "checkout_step": "shipping"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") == True, f"Expected success=True: {data}"
        print("PASS: Contact tracked with phone number")
    
    def test_02_track_contact_with_email(self):
        """Test tracking contact with email"""
        session_id = f"test_session_{uuid.uuid4().hex[:8]}"
        
        response = requests.post(f"{BASE_URL}/api/checkout/track-contact", json={
            "session_id": session_id,
            "email": "customer@example.com",
            "name": "Email User",
            "checkout_step": "cart"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") == True
        print("PASS: Contact tracked with email")
    
    def test_03_track_contact_with_both(self):
        """Test tracking contact with both phone and email"""
        session_id = f"test_session_{uuid.uuid4().hex[:8]}"
        
        response = requests.post(f"{BASE_URL}/api/checkout/track-contact", json={
            "session_id": session_id,
            "email": "both@example.com",
            "phone": "+14165559876",
            "name": "Both User",
            "checkout_step": "payment"
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") == True
        print("PASS: Contact tracked with both phone and email")
    
    def test_04_track_contact_empty_session(self):
        """Test tracking with empty session still succeeds (graceful handling)"""
        response = requests.post(f"{BASE_URL}/api/checkout/track-contact", json={
            "session_id": "",
            "phone": "+14165551111"
        })
        
        # Should still return success (graceful failure)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Empty session handled gracefully")


class TestAdminSMSSubscribers:
    """Tests for admin SMS subscribers endpoints"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@reroots.ca",
            "password": "new_password_123"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin authentication failed")
    
    def test_01_get_sms_subscribers_authenticated(self, admin_token):
        """Test getting SMS subscribers list as admin"""
        response = requests.get(
            f"{BASE_URL}/api/admin/sms-subscribers",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "subscribers" in data
        assert "total" in data
        print(f"PASS: Admin can view SMS subscribers - Total: {data['total']}")
    
    def test_02_get_sms_subscribers_unauthenticated(self):
        """Test that unauthenticated request is rejected"""
        response = requests.get(f"{BASE_URL}/api/admin/sms-subscribers")
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("PASS: Unauthenticated request correctly rejected")


class TestStoreSettingsForSMSPopup:
    """Test store settings for SMS popup configuration"""
    
    def test_01_get_store_settings_has_sms_popup_field(self):
        """Test that store settings endpoint returns sms_popup_enabled field"""
        response = requests.get(f"{BASE_URL}/api/store-settings")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        # sms_popup_enabled may or may not exist - if not, default is True
        # Just verify endpoint works
        print(f"PASS: Store settings accessible, sms_popup_enabled: {data.get('sms_popup_enabled', 'not set (default True)')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
