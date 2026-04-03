"""
AUREM Gmail Integration Tests - Phase 3
Tests for Gmail OAuth and Gmail Channel API endpoints

Endpoints tested:
- GET /api/oauth/gmail/health - OAuth health check
- GET /api/oauth/gmail/status/{business_id} - Connection status
- GET /api/oauth/gmail/authorize - OAuth redirect (requires business_id)
- GET /api/gmail/{business_id}/health - Gmail channel health
- GET /api/gmail/{business_id}/messages - List messages (requires connection)
- GET /api/gmail/{business_id}/profile - Get profile (requires connection)
- GET /api/gmail/{business_id}/labels - Get labels (requires connection)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://live-support-test.preview.emergentagent.com').rstrip('/')

class TestGmailOAuthEndpoints:
    """Tests for Gmail OAuth router endpoints"""
    
    def test_oauth_health_endpoint(self):
        """Test Gmail OAuth health endpoint returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/oauth/gmail/health")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "status" in data, "Response should contain 'status' field"
        assert data["status"] == "healthy", f"Expected 'healthy', got {data['status']}"
        assert data.get("google_oauth_configured") == True, "Google OAuth should be configured"
        assert "message" in data, "Response should contain 'message' field"
        print(f"✓ OAuth health check passed: {data}")
    
    def test_oauth_status_disconnected_for_new_business(self):
        """Test Gmail status returns disconnected for a new/unknown business"""
        test_business_id = "test-new-business-xyz-123"
        response = requests.get(f"{BASE_URL}/api/oauth/gmail/status/{test_business_id}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("business_id") == test_business_id, "Business ID should match"
        assert data.get("connected") == False, "New business should not be connected"
        assert data.get("status") == "disconnected", "Status should be 'disconnected'"
        assert data.get("email") is None, "Email should be None for disconnected"
        print(f"✓ Status check for new business passed: {data}")
    
    def test_oauth_authorize_requires_business_id(self):
        """Test OAuth authorize endpoint requires business_id parameter"""
        # Without business_id - should return 422 (validation error)
        response = requests.get(f"{BASE_URL}/api/oauth/gmail/authorize", allow_redirects=False)
        
        assert response.status_code == 422, f"Expected 422 for missing business_id, got {response.status_code}"
        print(f"✓ Authorize endpoint correctly requires business_id")
    
    def test_oauth_authorize_with_invalid_business_redirects_or_errors(self):
        """Test OAuth authorize with invalid business_id returns 404 or redirects"""
        # With invalid business_id - should return 404 (business not found)
        response = requests.get(
            f"{BASE_URL}/api/oauth/gmail/authorize",
            params={"business_id": "nonexistent-business-xyz"},
            allow_redirects=False
        )
        
        # Should return 404 for non-existent business
        assert response.status_code == 404, f"Expected 404 for invalid business, got {response.status_code}"
        print(f"✓ Authorize endpoint correctly validates business_id")
    
    def test_oauth_disconnect_nonexistent_returns_404(self):
        """Test disconnecting non-existent Gmail connection returns 404"""
        response = requests.delete(f"{BASE_URL}/api/oauth/gmail/disconnect/nonexistent-business-xyz")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ Disconnect endpoint correctly returns 404 for non-existent connection")


class TestGmailChannelEndpoints:
    """Tests for Gmail Channel router endpoints"""
    
    def test_gmail_channel_health_disconnected(self):
        """Test Gmail channel health for disconnected business"""
        test_business_id = "test-channel-business-123"
        response = requests.get(f"{BASE_URL}/api/gmail/{test_business_id}/health")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "disconnected", f"Expected 'disconnected', got {data.get('status')}"
        print(f"✓ Gmail channel health check passed: {data}")
    
    def test_gmail_messages_requires_connection(self):
        """Test listing messages requires Gmail connection"""
        test_business_id = "test-messages-business-123"
        response = requests.get(f"{BASE_URL}/api/gmail/{test_business_id}/messages")
        
        # Should return 400 because Gmail is not connected
        assert response.status_code == 400, f"Expected 400 for disconnected, got {response.status_code}"
        
        data = response.json()
        assert "not connected" in data.get("detail", "").lower(), "Should indicate Gmail not connected"
        print(f"✓ Messages endpoint correctly requires connection: {data}")
    
    def test_gmail_profile_requires_connection(self):
        """Test getting profile requires Gmail connection"""
        test_business_id = "test-profile-business-123"
        response = requests.get(f"{BASE_URL}/api/gmail/{test_business_id}/profile")
        
        # Should return 400 because Gmail is not connected
        assert response.status_code == 400, f"Expected 400 for disconnected, got {response.status_code}"
        print(f"✓ Profile endpoint correctly requires connection")
    
    def test_gmail_labels_requires_connection(self):
        """Test getting labels requires Gmail connection"""
        test_business_id = "test-labels-business-123"
        response = requests.get(f"{BASE_URL}/api/gmail/{test_business_id}/labels")
        
        # Should return 400 because Gmail is not connected
        assert response.status_code == 400, f"Expected 400 for disconnected, got {response.status_code}"
        print(f"✓ Labels endpoint correctly requires connection")
    
    def test_gmail_send_requires_connection(self):
        """Test sending email requires Gmail connection"""
        test_business_id = "test-send-business-123"
        response = requests.post(
            f"{BASE_URL}/api/gmail/{test_business_id}/send",
            json={
                "to": "test@example.com",
                "subject": "Test Subject",
                "body_text": "Test body"
            }
        )
        
        # Should return 400 or 429 (quota) because Gmail is not connected
        assert response.status_code in [400, 429], f"Expected 400 or 429 for disconnected, got {response.status_code}"
        print(f"✓ Send endpoint correctly requires connection")
    
    def test_gmail_message_actions_require_connection(self):
        """Test message actions (read/unread/archive) require connection"""
        test_business_id = "test-actions-business-123"
        test_message_id = "test-message-id"
        
        # Test mark as read
        response = requests.put(f"{BASE_URL}/api/gmail/{test_business_id}/messages/{test_message_id}/read")
        assert response.status_code == 500, f"Expected 500 for disconnected mark read, got {response.status_code}"
        
        # Test mark as unread
        response = requests.put(f"{BASE_URL}/api/gmail/{test_business_id}/messages/{test_message_id}/unread")
        assert response.status_code == 500, f"Expected 500 for disconnected mark unread, got {response.status_code}"
        
        # Test archive
        response = requests.put(f"{BASE_URL}/api/gmail/{test_business_id}/messages/{test_message_id}/archive")
        assert response.status_code == 500, f"Expected 500 for disconnected archive, got {response.status_code}"
        
        print(f"✓ Message action endpoints correctly require connection")
    
    def test_gmail_get_single_message_requires_connection(self):
        """Test getting single message requires connection"""
        test_business_id = "test-single-msg-business-123"
        test_message_id = "test-message-id"
        
        response = requests.get(f"{BASE_URL}/api/gmail/{test_business_id}/messages/{test_message_id}")
        
        # Should return 404 because Gmail is not connected
        assert response.status_code == 404, f"Expected 404 for disconnected, got {response.status_code}"
        print(f"✓ Get single message endpoint correctly requires connection")
    
    def test_gmail_thread_requires_connection(self):
        """Test getting thread requires connection"""
        test_business_id = "test-thread-business-123"
        test_thread_id = "test-thread-id"
        
        response = requests.get(f"{BASE_URL}/api/gmail/{test_business_id}/threads/{test_thread_id}")
        
        # Should return 404 because Gmail is not connected
        assert response.status_code == 404, f"Expected 404 for disconnected, got {response.status_code}"
        print(f"✓ Get thread endpoint correctly requires connection")


class TestGmailIntegrationValidation:
    """Tests for input validation on Gmail endpoints"""
    
    def test_send_email_validates_recipient(self):
        """Test send email validates recipient email format"""
        test_business_id = "test-validation-business-123"
        
        # Invalid email format
        response = requests.post(
            f"{BASE_URL}/api/gmail/{test_business_id}/send",
            json={
                "to": "invalid-email",
                "subject": "Test",
                "body_text": "Test"
            }
        )
        
        # Should return 422 for validation error
        assert response.status_code == 422, f"Expected 422 for invalid email, got {response.status_code}"
        print(f"✓ Send email validates recipient format")
    
    def test_send_email_requires_subject(self):
        """Test send email requires subject"""
        test_business_id = "test-validation-business-123"
        
        # Missing subject
        response = requests.post(
            f"{BASE_URL}/api/gmail/{test_business_id}/send",
            json={
                "to": "test@example.com",
                "body_text": "Test"
            }
        )
        
        # Should return 422 for validation error
        assert response.status_code == 422, f"Expected 422 for missing subject, got {response.status_code}"
        print(f"✓ Send email requires subject")
    
    def test_send_email_requires_body(self):
        """Test send email requires body_text"""
        test_business_id = "test-validation-business-123"
        
        # Missing body_text
        response = requests.post(
            f"{BASE_URL}/api/gmail/{test_business_id}/send",
            json={
                "to": "test@example.com",
                "subject": "Test Subject"
            }
        )
        
        # Should return 422 for validation error
        assert response.status_code == 422, f"Expected 422 for missing body, got {response.status_code}"
        print(f"✓ Send email requires body_text")
    
    def test_create_label_validates_name(self):
        """Test create label validates name field"""
        test_business_id = "test-label-validation-123"
        
        # Empty name
        response = requests.post(
            f"{BASE_URL}/api/gmail/{test_business_id}/labels",
            json={
                "name": ""
            }
        )
        
        # Should return 422 for validation error
        assert response.status_code == 422, f"Expected 422 for empty label name, got {response.status_code}"
        print(f"✓ Create label validates name field")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
