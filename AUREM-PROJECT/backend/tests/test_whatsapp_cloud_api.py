"""
WhatsApp Cloud API Integration Tests
Tests for Phase 5: WhatsApp Cloud API with Meta Embedded Signup

Features tested:
- Health check endpoint
- Connection status endpoint
- Webhook verification (GET)
- Webhook message processing (POST)
- Verify token endpoint
- Connect endpoint (OAuth flow initiation)
"""

import pytest
import requests
import os
import json
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_BUSINESS_ID = "test_biz_001"


class TestWhatsAppHealth:
    """Health check endpoint tests"""
    
    def test_health_returns_healthy_status(self):
        """GET /api/whatsapp/health returns healthy status with capabilities"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["status"] == "healthy"
        assert data["service"] == "aurem-whatsapp"
        assert "meta_configured" in data
        assert isinstance(data["meta_configured"], bool)
        
        # Verify capabilities list
        assert "capabilities" in data
        capabilities = data["capabilities"]
        assert "embedded_signup" in capabilities
        assert "webhook_verification" in capabilities
        assert "send_text" in capabilities
        assert "send_template" in capabilities
        assert "inbox_integration" in capabilities
        
        print(f"✓ Health check passed: {data}")


class TestWhatsAppConnectionStatus:
    """Connection status endpoint tests"""
    
    def test_get_status_not_configured(self):
        """GET /api/whatsapp/{business_id}/status returns not_configured for new business"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/{TEST_BUSINESS_ID}/status")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "connected" in data
        assert "status" in data
        assert data["connected"] == False
        assert data["status"] in ["not_configured", "pending", "disconnected"]
        
        print(f"✓ Status check passed: {data}")
    
    def test_get_status_different_business(self):
        """GET /api/whatsapp/{business_id}/status works for different business IDs"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/another_test_biz/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "connected" in data
        assert "status" in data
        print(f"✓ Different business status check passed: {data}")


class TestWhatsAppVerifyToken:
    """Verify token endpoint tests"""
    
    def test_get_verify_token(self):
        """GET /api/whatsapp/{business_id}/verify-token returns webhook config"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/{TEST_BUSINESS_ID}/verify-token")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "verify_token" in data
        assert "webhook_url" in data
        assert "instructions" in data
        
        # Verify token format (starts with aurem_verify_)
        assert data["verify_token"].startswith("aurem_verify_")
        
        # Verify webhook URL contains the correct path
        assert "/api/whatsapp/webhook" in data["webhook_url"]
        
        # Verify instructions are present
        assert "Meta App Dashboard" in data["instructions"]
        
        print(f"✓ Verify token check passed: verify_token={data['verify_token'][:30]}...")


class TestWhatsAppConnect:
    """Connect endpoint tests (OAuth flow initiation)"""
    
    def test_connect_without_meta_config(self):
        """POST /api/whatsapp/{business_id}/connect returns error when META_APP_ID not configured"""
        response = requests.post(f"{BASE_URL}/api/whatsapp/{TEST_BUSINESS_ID}/connect")
        
        # Should return 400 with error message about missing config
        assert response.status_code == 400
        data = response.json()
        
        # Verify error message mentions META_APP_ID
        assert "detail" in data
        assert "META_APP_ID" in data["detail"]
        
        print(f"✓ Connect without config returns expected error: {data['detail']}")


class TestWhatsAppWebhookVerification:
    """Webhook verification (GET) endpoint tests"""
    
    def test_webhook_verification_success(self):
        """GET /api/whatsapp/webhook handles Meta verification challenge"""
        # First get the verify token
        token_response = requests.get(f"{BASE_URL}/api/whatsapp/{TEST_BUSINESS_ID}/verify-token")
        verify_token = token_response.json()["verify_token"]
        
        # Test webhook verification
        challenge = "test_challenge_12345"
        response = requests.get(
            f"{BASE_URL}/api/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": verify_token,
                "hub.challenge": challenge
            }
        )
        
        assert response.status_code == 200
        assert response.text == challenge
        
        print(f"✓ Webhook verification passed: challenge returned correctly")
    
    def test_webhook_verification_invalid_token(self):
        """GET /api/whatsapp/webhook rejects invalid verify token"""
        response = requests.get(
            f"{BASE_URL}/api/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "invalid_token_123",
                "hub.challenge": "test_challenge"
            }
        )
        
        assert response.status_code == 403
        print(f"✓ Invalid token correctly rejected with 403")
    
    def test_webhook_verification_wrong_mode(self):
        """GET /api/whatsapp/webhook rejects wrong mode"""
        token_response = requests.get(f"{BASE_URL}/api/whatsapp/{TEST_BUSINESS_ID}/verify-token")
        verify_token = token_response.json()["verify_token"]
        
        response = requests.get(
            f"{BASE_URL}/api/whatsapp/webhook",
            params={
                "hub.mode": "unsubscribe",  # Wrong mode
                "hub.verify_token": verify_token,
                "hub.challenge": "test_challenge"
            }
        )
        
        assert response.status_code == 403
        print(f"✓ Wrong mode correctly rejected with 403")


class TestWhatsAppWebhookMessages:
    """Webhook message processing (POST) endpoint tests"""
    
    def test_webhook_receives_text_message(self):
        """POST /api/whatsapp/webhook processes incoming text messages"""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "+1234567890",
                            "phone_number_id": "test_phone_id_001"
                        },
                        "contacts": [{
                            "profile": {"name": "Test Customer"},
                            "wa_id": "15559876543"
                        }],
                        "messages": [{
                            "id": f"wamid.test_{datetime.now().timestamp()}",
                            "from": "15559876543",
                            "timestamp": str(int(datetime.now().timestamp())),
                            "type": "text",
                            "text": {"body": "Hello, I need help with my order"}
                        }]
                    }
                }]
            }]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/webhook",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        
        print(f"✓ Text message webhook processed successfully")
    
    def test_webhook_receives_image_message(self):
        """POST /api/whatsapp/webhook processes incoming image messages"""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "field": "messages",
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "+1234567890",
                            "phone_number_id": "test_phone_id_002"
                        },
                        "contacts": [{
                            "profile": {"name": "Image Sender"},
                            "wa_id": "15551112222"
                        }],
                        "messages": [{
                            "id": f"wamid.img_{datetime.now().timestamp()}",
                            "from": "15551112222",
                            "timestamp": str(int(datetime.now().timestamp())),
                            "type": "image",
                            "image": {
                                "id": "img_media_id_123",
                                "mime_type": "image/jpeg",
                                "sha256": "abc123",
                                "caption": "Check this product"
                            }
                        }]
                    }
                }]
            }]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/webhook",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        
        print(f"✓ Image message webhook processed successfully")
    
    def test_webhook_receives_status_update(self):
        """POST /api/whatsapp/webhook processes message status updates"""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "field": "statuses",
                    "value": {
                        "messaging_product": "whatsapp",
                        "statuses": [{
                            "id": "wamid.status_test_123",
                            "status": "delivered",
                            "timestamp": str(int(datetime.now().timestamp())),
                            "recipient_id": "15559876543"
                        }]
                    }
                }]
            }]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/webhook",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        
        print(f"✓ Status update webhook processed successfully")
    
    def test_webhook_invalid_json(self):
        """POST /api/whatsapp/webhook handles invalid JSON gracefully"""
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/webhook",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
        print(f"✓ Invalid JSON correctly rejected with 400")


class TestWhatsAppMessaging:
    """Send message endpoint tests (will fail without connection)"""
    
    def test_send_message_not_connected(self):
        """POST /api/whatsapp/{business_id}/send returns error when not connected"""
        response = requests.post(
            f"{BASE_URL}/api/whatsapp/{TEST_BUSINESS_ID}/send",
            json={
                "to": "+15551234567",
                "text": "Test message"
            },
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 400 with error about not being connected
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "not connected" in data["detail"].lower()
        
        print(f"✓ Send without connection returns expected error: {data['detail']}")
    
    def test_get_messages_empty(self):
        """GET /api/whatsapp/{business_id}/messages returns empty list for new business"""
        response = requests.get(f"{BASE_URL}/api/whatsapp/{TEST_BUSINESS_ID}/messages")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "messages" in data
        assert "count" in data
        assert isinstance(data["messages"], list)
        
        print(f"✓ Get messages returned: {data['count']} messages")


class TestWhatsAppDisconnect:
    """Disconnect endpoint tests"""
    
    def test_disconnect_not_connected(self):
        """POST /api/whatsapp/{business_id}/disconnect works even when not connected"""
        response = requests.post(f"{BASE_URL}/api/whatsapp/{TEST_BUSINESS_ID}/disconnect")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "disconnected" in data
        # Should return false since nothing was connected
        assert data["disconnected"] == False
        
        print(f"✓ Disconnect returned: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
