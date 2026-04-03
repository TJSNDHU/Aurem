"""
WhatsApp AI Assistant API Tests
Tests all endpoints for the WhatsApp AI auto-reply bot admin panel.

Endpoints tested:
- GET /api/admin/whatsapp-ai/settings - Get current AI settings
- PUT /api/admin/whatsapp-ai/settings - Update AI settings  
- PUT /api/admin/whatsapp-ai/brand-voice - Update brand voice configuration
- POST /api/admin/whatsapp-ai/test-reply - Test AI reply generation
- POST /api/admin/whatsapp-ai/toggle - Toggle assistant on/off
- POST /api/admin/whatsapp-ai/switch-provider - Switch LLM provider (openai/anthropic)
- GET /api/admin/whatsapp-ai/stats - Get conversation statistics
- GET /api/admin/whatsapp-ai/conversations - Get conversation history
- GET /api/admin/whatsapp-ai/conversations/contacts - Get unique contacts list
- POST /api/admin/whatsapp-ai/webhook - WHAPI webhook endpoint
"""

import pytest
import requests
import os
import time

# Base URL from environment - MUST be production URL
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://live-support-test.preview.emergentagent.com').rstrip('/')

# Test fixtures
@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestWhatsAppAISettings:
    """Tests for WhatsApp AI Settings endpoints"""
    
    def test_get_settings_returns_200(self, api_client):
        """GET /api/admin/whatsapp-ai/settings should return current settings"""
        response = api_client.get(f"{BASE_URL}/api/admin/whatsapp-ai/settings")
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions - validate response structure
        data = response.json()
        assert "settings" in data, "Response should contain 'settings' key"
        assert "brand_voice" in data, "Response should contain 'brand_voice' key"
        assert "style_patterns" in data, "Response should contain 'style_patterns' key"
        
        # Validate settings structure
        settings = data["settings"]
        assert "enabled" in settings, "Settings should contain 'enabled' field"
        assert "mode" in settings, "Settings should contain 'mode' field"
        assert "provider" in settings, "Settings should contain 'provider' field"
        assert isinstance(settings["enabled"], bool), "enabled should be a boolean"
        assert settings["mode"] in ["brand", "personal"], "mode should be 'brand' or 'personal'"
        assert settings["provider"] in ["openai", "anthropic"], "provider should be 'openai' or 'anthropic'"
        
        print(f"✓ GET /settings: enabled={settings['enabled']}, mode={settings['mode']}, provider={settings['provider']}")

    def test_update_settings_mode(self, api_client):
        """PUT /api/admin/whatsapp-ai/settings should update settings"""
        # First get current settings
        get_response = api_client.get(f"{BASE_URL}/api/admin/whatsapp-ai/settings")
        current = get_response.json()["settings"]
        
        # Update with new mode
        new_mode = "personal" if current.get("mode") == "brand" else "brand"
        update_payload = {
            "enabled": current.get("enabled", False),
            "mode": new_mode,
            "provider": current.get("provider", "openai"),
            "auto_reply_delay_ms": 2000,
            "business_hours_only": False,
            "excluded_contacts": [],
            "business_hours": {"start": "09:00", "end": "18:00"}
        }
        
        response = api_client.put(
            f"{BASE_URL}/api/admin/whatsapp-ai/settings",
            json=update_payload
        )
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert data.get("success") == True, "Response should indicate success"
        assert "settings" in data, "Response should contain updated settings"
        assert data["settings"]["mode"] == new_mode, f"Mode should be updated to {new_mode}"
        assert data["settings"]["auto_reply_delay_ms"] == 2000, "Delay should be updated"
        
        # Verify persistence by getting settings again
        verify_response = api_client.get(f"{BASE_URL}/api/admin/whatsapp-ai/settings")
        verified = verify_response.json()["settings"]
        assert verified["mode"] == new_mode, "Mode change should persist"
        
        print(f"✓ PUT /settings: mode updated to {new_mode}, delay=2000ms")
        
        # Restore original mode
        update_payload["mode"] = current.get("mode", "brand")
        api_client.put(f"{BASE_URL}/api/admin/whatsapp-ai/settings", json=update_payload)

    def test_update_settings_business_hours(self, api_client):
        """PUT /api/admin/whatsapp-ai/settings should handle business hours setting"""
        update_payload = {
            "enabled": False,
            "mode": "brand",
            "provider": "openai",
            "auto_reply_delay_ms": 1000,
            "business_hours_only": True,
            "excluded_contacts": [],
            "business_hours": {"start": "10:00", "end": "20:00"}
        }
        
        response = api_client.put(
            f"{BASE_URL}/api/admin/whatsapp-ai/settings",
            json=update_payload
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["settings"]["business_hours_only"] == True
        assert data["settings"]["business_hours"]["start"] == "10:00"
        assert data["settings"]["business_hours"]["end"] == "20:00"
        
        print(f"✓ PUT /settings: business hours set to 10:00-20:00")
        
        # Reset
        update_payload["business_hours_only"] = False
        api_client.put(f"{BASE_URL}/api/admin/whatsapp-ai/settings", json=update_payload)


class TestBrandVoiceConfiguration:
    """Tests for Brand Voice configuration endpoint"""
    
    def test_update_brand_voice(self, api_client):
        """PUT /api/admin/whatsapp-ai/brand-voice should update brand voice config"""
        brand_voice_payload = {
            "brand_name": "TEST_ReRoots",
            "tone": "friendly and professional",
            "personality_traits": ["helpful", "warm", "knowledgeable"],
            "key_phrases": ["Happy to help!", "Let me check that for you"],
            "avoid_phrases": ["I don't know"],
            "response_guidelines": ["Always be polite", "Offer solutions"],
            "product_knowledge": "ReRoots specializes in PDRN skincare products for anti-aging."
        }
        
        response = api_client.put(
            f"{BASE_URL}/api/admin/whatsapp-ai/brand-voice",
            json=brand_voice_payload
        )
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert data.get("success") == True, "Response should indicate success"
        assert "brand_voice" in data, "Response should contain brand_voice"
        assert data["brand_voice"]["brand_name"] == "TEST_ReRoots"
        assert data["brand_voice"]["tone"] == "friendly and professional"
        assert len(data["brand_voice"]["personality_traits"]) == 3
        
        print(f"✓ PUT /brand-voice: brand_name=TEST_ReRoots, traits={data['brand_voice']['personality_traits']}")
        
        # Verify persistence
        verify_response = api_client.get(f"{BASE_URL}/api/admin/whatsapp-ai/settings")
        verified = verify_response.json()["brand_voice"]
        assert verified["brand_name"] == "TEST_ReRoots", "Brand name should persist"
        
        # Restore original
        original_payload = {
            "brand_name": "ReRoots",
            "tone": "friendly and knowledgeable",
            "personality_traits": ["helpful", "skincare-expert", "warm"],
            "key_phrases": [],
            "avoid_phrases": [],
            "response_guidelines": [],
            "product_knowledge": ""
        }
        api_client.put(f"{BASE_URL}/api/admin/whatsapp-ai/brand-voice", json=original_payload)


class TestToggleAssistant:
    """Tests for toggling the AI assistant on/off"""
    
    def test_toggle_assistant(self, api_client):
        """POST /api/admin/whatsapp-ai/toggle should toggle enabled state"""
        # Get current state
        get_response = api_client.get(f"{BASE_URL}/api/admin/whatsapp-ai/settings")
        initial_enabled = get_response.json()["settings"]["enabled"]
        
        # Toggle
        response = api_client.post(f"{BASE_URL}/api/admin/whatsapp-ai/toggle")
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert data.get("success") == True, "Response should indicate success"
        assert "enabled" in data, "Response should contain enabled state"
        expected_enabled = not initial_enabled
        assert data["enabled"] == expected_enabled, f"Enabled should toggle from {initial_enabled} to {expected_enabled}"
        
        print(f"✓ POST /toggle: toggled from {initial_enabled} to {data['enabled']}")
        
        # Verify persistence
        verify_response = api_client.get(f"{BASE_URL}/api/admin/whatsapp-ai/settings")
        verified = verify_response.json()["settings"]["enabled"]
        assert verified == expected_enabled, "Toggle should persist"
        
        # Toggle back to original
        api_client.post(f"{BASE_URL}/api/admin/whatsapp-ai/toggle")


class TestSwitchProvider:
    """Tests for switching LLM provider"""
    
    def test_switch_to_openai(self, api_client):
        """POST /api/admin/whatsapp-ai/switch-provider?provider=openai should switch provider"""
        response = api_client.post(f"{BASE_URL}/api/admin/whatsapp-ai/switch-provider?provider=openai")
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert data.get("success") == True
        assert data["provider"] == "openai"
        assert "gpt" in data.get("model", "").lower() or data["model"] is None
        
        print(f"✓ POST /switch-provider: provider=openai, model={data.get('model')}")
        
        # Verify persistence
        verify_response = api_client.get(f"{BASE_URL}/api/admin/whatsapp-ai/settings")
        assert verify_response.json()["settings"]["provider"] == "openai"

    def test_switch_to_anthropic(self, api_client):
        """POST /api/admin/whatsapp-ai/switch-provider?provider=anthropic should switch provider"""
        response = api_client.post(f"{BASE_URL}/api/admin/whatsapp-ai/switch-provider?provider=anthropic")
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert data.get("success") == True
        assert data["provider"] == "anthropic"
        assert "claude" in data.get("model", "").lower() or data["model"] is None
        
        print(f"✓ POST /switch-provider: provider=anthropic, model={data.get('model')}")
        
        # Switch back to openai
        api_client.post(f"{BASE_URL}/api/admin/whatsapp-ai/switch-provider?provider=openai")

    def test_switch_provider_invalid(self, api_client):
        """POST /api/admin/whatsapp-ai/switch-provider with invalid provider should return 400"""
        response = api_client.post(f"{BASE_URL}/api/admin/whatsapp-ai/switch-provider?provider=invalid")
        
        # Status assertion - should reject invalid provider
        assert response.status_code == 400, f"Expected 400 for invalid provider, got {response.status_code}"
        
        print(f"✓ POST /switch-provider: correctly rejected invalid provider with 400")


class TestConversationStats:
    """Tests for conversation statistics endpoint"""
    
    def test_get_stats(self, api_client):
        """GET /api/admin/whatsapp-ai/stats should return conversation statistics"""
        response = api_client.get(f"{BASE_URL}/api/admin/whatsapp-ai/stats")
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions - validate structure
        data = response.json()
        assert "total_conversations" in data, "Stats should contain total_conversations"
        assert "total_ai_replies" in data, "Stats should contain total_ai_replies"
        assert "unique_contacts" in data, "Stats should contain unique_contacts"
        assert "today_messages" in data, "Stats should contain today_messages"
        
        # Validate types
        assert isinstance(data["total_conversations"], int), "total_conversations should be int"
        assert isinstance(data["total_ai_replies"], int), "total_ai_replies should be int"
        assert isinstance(data["unique_contacts"], int), "unique_contacts should be int"
        assert isinstance(data["today_messages"], int), "today_messages should be int"
        
        print(f"✓ GET /stats: total={data['total_conversations']}, ai_replies={data['total_ai_replies']}, contacts={data['unique_contacts']}, today={data['today_messages']}")


class TestConversations:
    """Tests for conversation history endpoints"""
    
    def test_get_conversations(self, api_client):
        """GET /api/admin/whatsapp-ai/conversations should return conversation list"""
        response = api_client.get(f"{BASE_URL}/api/admin/whatsapp-ai/conversations")
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "conversations" in data, "Response should contain conversations list"
        assert "total" in data, "Response should contain total count"
        assert "limit" in data, "Response should contain limit"
        assert "offset" in data, "Response should contain offset"
        
        assert isinstance(data["conversations"], list), "conversations should be a list"
        assert data["limit"] == 50, "Default limit should be 50"
        assert data["offset"] == 0, "Default offset should be 0"
        
        print(f"✓ GET /conversations: total={data['total']}, returned={len(data['conversations'])}")

    def test_get_conversations_with_pagination(self, api_client):
        """GET /api/admin/whatsapp-ai/conversations with limit/offset should work"""
        response = api_client.get(f"{BASE_URL}/api/admin/whatsapp-ai/conversations?limit=5&offset=0")
        
        # Status assertion
        assert response.status_code == 200
        
        # Data assertions
        data = response.json()
        assert data["limit"] == 5, "Limit should be 5"
        assert len(data["conversations"]) <= 5, "Should return at most 5 conversations"
        
        print(f"✓ GET /conversations with pagination: limit=5, returned={len(data['conversations'])}")

    def test_get_conversation_contacts(self, api_client):
        """GET /api/admin/whatsapp-ai/conversations/contacts should return contacts list"""
        response = api_client.get(f"{BASE_URL}/api/admin/whatsapp-ai/conversations/contacts")
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "contacts" in data, "Response should contain contacts list"
        assert isinstance(data["contacts"], list), "contacts should be a list"
        
        # Validate contact structure if contacts exist
        if data["contacts"]:
            contact = data["contacts"][0]
            assert "phone" in contact, "Contact should have phone"
            assert "message_count" in contact, "Contact should have message_count"
            
        print(f"✓ GET /conversations/contacts: {len(data['contacts'])} contacts found")


class TestAIReplyGeneration:
    """Tests for AI reply generation - the core functionality"""
    
    def test_test_reply_openai(self, api_client):
        """POST /api/admin/whatsapp-ai/test-reply should generate AI response with OpenAI"""
        # First ensure we're using OpenAI
        api_client.post(f"{BASE_URL}/api/admin/whatsapp-ai/switch-provider?provider=openai")
        
        test_payload = {
            "message": "Hi, do you sell PDRN products?",
            "provider": "openai",
            "mode": "brand"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/admin/whatsapp-ai/test-reply",
            json=test_payload
        )
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert data.get("success") == True, "Response should indicate success"
        assert "reply" in data, "Response should contain AI reply"
        assert "input" in data, "Response should contain input message"
        assert data["provider"] == "openai", "Provider should be openai"
        assert data["mode"] == "brand", "Mode should be brand"
        
        # Validate reply is not empty
        assert len(data["reply"]) > 0, "Reply should not be empty"
        assert isinstance(data["reply"], str), "Reply should be a string"
        
        print(f"✓ POST /test-reply (OpenAI): Input='{test_payload['message'][:30]}...', Reply='{data['reply'][:50]}...'")

    def test_test_reply_anthropic(self, api_client):
        """POST /api/admin/whatsapp-ai/test-reply should generate AI response with Claude"""
        test_payload = {
            "message": "What skincare products do you recommend for dry skin?",
            "provider": "anthropic",
            "mode": "brand"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/admin/whatsapp-ai/test-reply",
            json=test_payload
        )
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert data.get("success") == True, "Response should indicate success"
        assert "reply" in data, "Response should contain AI reply"
        assert data["provider"] == "anthropic", "Provider should be anthropic"
        
        # Validate reply
        assert len(data["reply"]) > 0, "Reply should not be empty"
        
        print(f"✓ POST /test-reply (Claude): Input='{test_payload['message'][:30]}...', Reply='{data['reply'][:50]}...'")

    def test_test_reply_personal_mode(self, api_client):
        """POST /api/admin/whatsapp-ai/test-reply with personal mode should work"""
        test_payload = {
            "message": "Hey! How's it going?",
            "provider": "openai",
            "mode": "personal"
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/admin/whatsapp-ai/test-reply",
            json=test_payload
        )
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert data.get("success") == True
        assert data["mode"] == "personal", "Mode should be personal"
        assert len(data["reply"]) > 0, "Reply should not be empty"
        
        print(f"✓ POST /test-reply (Personal mode): Reply='{data['reply'][:50]}...'")


class TestWebhook:
    """Tests for WHAPI webhook endpoint"""
    
    def test_webhook_empty_payload(self, api_client):
        """POST /api/admin/whatsapp-ai/webhook should handle empty payload"""
        response = api_client.post(
            f"{BASE_URL}/api/admin/whatsapp-ai/webhook",
            json={}
        )
        
        # Should not crash with empty payload
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Either success=True with no reply or handles gracefully
        assert "success" in data
        
        print(f"✓ POST /webhook: handles empty payload gracefully")

    def test_webhook_with_message(self, api_client):
        """POST /api/admin/whatsapp-ai/webhook should process incoming message"""
        # Simulate WHAPI webhook payload
        webhook_payload = {
            "messages": [
                {
                    "id": "TEST_msg_12345",
                    "from": "TEST15551234567@s.whatsapp.net",
                    "from_me": False,
                    "type": "text",
                    "text": {
                        "body": "TEST_Hello, I have a question about your products"
                    },
                    "timestamp": int(time.time())
                }
            ]
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/admin/whatsapp-ai/webhook",
            json=webhook_payload
        )
        
        # Status assertion
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Data assertions
        data = response.json()
        assert "success" in data
        # Note: reply_sent may be False if assistant is disabled
        assert "reply_sent" in data
        
        print(f"✓ POST /webhook: processed message, reply_sent={data.get('reply_sent')}")

    def test_webhook_ignores_own_messages(self, api_client):
        """POST /api/admin/whatsapp-ai/webhook should ignore from_me messages"""
        webhook_payload = {
            "messages": [
                {
                    "id": "TEST_msg_own_12345",
                    "from": "TEST15551234567@s.whatsapp.net",
                    "from_me": True,  # This is our own message
                    "type": "text",
                    "text": {
                        "body": "TEST_This is my own message"
                    },
                    "timestamp": int(time.time())
                }
            ]
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/admin/whatsapp-ai/webhook",
            json=webhook_payload
        )
        
        # Status assertion
        assert response.status_code == 200
        
        # Should not send reply to own messages
        data = response.json()
        # reply_sent should be None or False since we ignore own messages
        assert data.get("reply_sent") != True, "Should not reply to own messages"
        
        print(f"✓ POST /webhook: correctly ignores from_me messages")


# Run cleanup after tests
@pytest.fixture(scope="module", autouse=True)
def cleanup(api_client):
    """Cleanup test data after tests"""
    yield
    # Reset settings to defaults
    try:
        reset_payload = {
            "enabled": False,
            "mode": "brand",
            "provider": "openai",
            "auto_reply_delay_ms": 1000,
            "business_hours_only": False,
            "excluded_contacts": [],
            "business_hours": {"start": "09:00", "end": "18:00"}
        }
        api_client.put(f"{BASE_URL}/api/admin/whatsapp-ai/settings", json=reset_payload)
        
        # Reset brand voice to defaults
        brand_reset = {
            "brand_name": "ReRoots",
            "tone": "friendly and knowledgeable",
            "personality_traits": ["helpful", "skincare-expert", "warm"],
            "key_phrases": [],
            "avoid_phrases": [],
            "response_guidelines": [],
            "product_knowledge": ""
        }
        api_client.put(f"{BASE_URL}/api/admin/whatsapp-ai/brand-voice", json=brand_reset)
        print("✓ Cleanup: Settings reset to defaults")
    except Exception as e:
        print(f"⚠ Cleanup warning: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
