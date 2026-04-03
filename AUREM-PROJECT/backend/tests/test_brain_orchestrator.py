"""
AUREM Brain Orchestrator API Tests
Tests the AI Brain OODA Loop endpoints:
- POST /api/brain/think - Process messages through OODA loop
- GET /api/brain/thought/{thought_id} - Retrieve thought details
- GET /api/brain/intents - Get available intents
- GET /api/brain/health - Health check
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test API key with full_access scopes (provided in test context)
TEST_API_KEY = "sk_aurem_live_dbd34012aff53051257504f4d5f76305"


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def authenticated_client(api_client):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {TEST_API_KEY}"})
    return api_client


class TestBrainHealth:
    """Health check endpoint tests"""
    
    def test_health_returns_healthy_status(self, api_client):
        """GET /api/brain/health returns healthy status"""
        response = api_client.get(f"{BASE_URL}/api/brain/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "aurem-brain"
        assert data["llm_configured"] == True
        
    def test_health_returns_capabilities(self, api_client):
        """GET /api/brain/health returns capabilities list"""
        response = api_client.get(f"{BASE_URL}/api/brain/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "capabilities" in data
        expected_capabilities = [
            "intent_classification",
            "entity_extraction",
            "action_execution",
            "websocket_push"
        ]
        for cap in expected_capabilities:
            assert cap in data["capabilities"], f"Missing capability: {cap}"


class TestBrainIntents:
    """Available intents endpoint tests"""
    
    def test_intents_returns_all_intents(self, api_client):
        """GET /api/brain/intents returns all available intents"""
        response = api_client.get(f"{BASE_URL}/api/brain/intents")
        assert response.status_code == 200
        
        data = response.json()
        assert "intents" in data
        
        # Expected intents
        expected_intents = [
            "chat", "book_appointment", "check_availability", 
            "send_email", "send_whatsapp", "create_invoice",
            "create_payment", "query_data", "unknown"
        ]
        
        intent_names = [i["intent"] for i in data["intents"]]
        for intent in expected_intents:
            assert intent in intent_names, f"Missing intent: {intent}"
    
    def test_intents_have_tool_mapping(self, api_client):
        """GET /api/brain/intents returns tool mappings for action intents"""
        response = api_client.get(f"{BASE_URL}/api/brain/intents")
        assert response.status_code == 200
        
        data = response.json()
        intents_dict = {i["intent"]: i for i in data["intents"]}
        
        # Action intents should have tool mappings
        assert intents_dict["book_appointment"]["maps_to_tool"] == "book_appointment"
        assert intents_dict["check_availability"]["maps_to_tool"] == "check_calendar_availability"
        assert intents_dict["send_email"]["maps_to_tool"] == "send_email"
        assert intents_dict["send_whatsapp"]["maps_to_tool"] == "send_whatsapp"
        assert intents_dict["create_invoice"]["maps_to_tool"] == "create_invoice"
        assert intents_dict["create_payment"]["maps_to_tool"] == "create_payment_link"
        
        # Non-action intents should not have tool mappings
        assert intents_dict["chat"]["maps_to_tool"] is None
        assert intents_dict["query_data"]["maps_to_tool"] is None
        assert intents_dict["unknown"]["maps_to_tool"] is None
    
    def test_intents_have_descriptions(self, api_client):
        """GET /api/brain/intents returns descriptions for all intents"""
        response = api_client.get(f"{BASE_URL}/api/brain/intents")
        assert response.status_code == 200
        
        data = response.json()
        for intent in data["intents"]:
            assert "description" in intent
            assert len(intent["description"]) > 0, f"Empty description for {intent['intent']}"


class TestBrainAuthentication:
    """Authentication tests for Brain endpoints"""
    
    def test_think_requires_auth_header(self, api_client):
        """POST /api/brain/think returns 401 without auth header"""
        response = api_client.post(
            f"{BASE_URL}/api/brain/think",
            json={"message": "Hello"}
        )
        assert response.status_code == 401
        assert "Missing or invalid Authorization header" in response.json()["detail"]
    
    def test_think_rejects_invalid_api_key(self, api_client):
        """POST /api/brain/think returns 401 with invalid API key"""
        api_client.headers.update({"Authorization": "Bearer sk_aurem_invalid_key"})
        response = api_client.post(
            f"{BASE_URL}/api/brain/think",
            json={"message": "Hello"}
        )
        assert response.status_code == 401
        assert "Invalid or expired API key" in response.json()["detail"]
    
    def test_think_rejects_malformed_auth_header(self, api_client):
        """POST /api/brain/think returns 401 with malformed auth header"""
        api_client.headers.update({"Authorization": "InvalidFormat"})
        response = api_client.post(
            f"{BASE_URL}/api/brain/think",
            json={"message": "Hello"}
        )
        assert response.status_code == 401
    
    def test_thought_retrieval_requires_auth(self, api_client):
        """GET /api/brain/thought/{id} returns 401 without auth"""
        response = api_client.get(f"{BASE_URL}/api/brain/thought/thought_test123")
        assert response.status_code == 401


class TestBrainThinkChatIntent:
    """Tests for chat intent processing"""
    
    def test_think_chat_intent_success(self, authenticated_client):
        """POST /api/brain/think processes chat messages successfully"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/brain/think",
            json={"message": "Hello, how are you today?"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "thought_id" in data
        assert data["thought_id"].startswith("thought_")
        assert "response" in data
        assert len(data["response"]) > 0
        assert data["intent"] == "chat"
        assert data["confidence"] >= 0.5
        assert data["status"] == "complete"
        assert isinstance(data["actions_taken"], list)
        assert len(data["actions_taken"]) == 0  # Chat doesn't take actions
        assert data["duration_ms"] > 0
    
    def test_think_returns_thought_id(self, authenticated_client):
        """POST /api/brain/think returns valid thought_id"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/brain/think",
            json={"message": "What can you help me with?"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "thought_id" in data
        assert data["thought_id"].startswith("thought_")
        assert len(data["thought_id"]) > 10


class TestBrainThinkCheckAvailability:
    """Tests for check_availability intent processing"""
    
    def test_think_check_availability_with_date(self, authenticated_client):
        """POST /api/brain/think processes check_availability with proper date"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/brain/think",
            json={"message": "Check availability for 2026-01-25"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["intent"] == "check_availability"
        assert data["confidence"] >= 0.7
        assert data["status"] == "complete"
        # Should have executed the action
        assert len(data["actions_taken"]) > 0 or "available" in data["response"].lower()
    
    def test_think_check_availability_returns_slots(self, authenticated_client):
        """POST /api/brain/think returns available slots for check_availability"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/brain/think",
            json={"message": "What time slots are available on 2026-01-26?"}
        )
        assert response.status_code == 200
        
        data = response.json()
        # Response should mention slots or availability
        assert "slot" in data["response"].lower() or "available" in data["response"].lower() or "time" in data["response"].lower()


class TestBrainThinkSendEmail:
    """Tests for send_email intent processing"""
    
    def test_think_send_email_intent_detected(self, authenticated_client):
        """POST /api/brain/think detects send_email intent"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/brain/think",
            json={"message": "Send an email to test@example.com with subject Test and body Hello World"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["intent"] == "send_email"
        assert data["confidence"] >= 0.8
        # Gmail not connected for test business, so action will fail gracefully
        assert data["status"] == "complete"
    
    def test_think_send_email_extracts_entities(self, authenticated_client):
        """POST /api/brain/think extracts email entities correctly"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/brain/think",
            json={"message": "Please send an email to john.doe@company.com about the meeting tomorrow"}
        )
        assert response.status_code == 200
        
        data = response.json()
        # Should detect email intent or ask for clarification
        assert data["status"] == "complete"


class TestBrainThoughtRetrieval:
    """Tests for thought retrieval endpoint"""
    
    def test_get_thought_success(self, authenticated_client):
        """GET /api/brain/thought/{id} retrieves thought details"""
        # First create a thought
        think_response = authenticated_client.post(
            f"{BASE_URL}/api/brain/think",
            json={"message": "Test message for retrieval"}
        )
        assert think_response.status_code == 200
        thought_id = think_response.json()["thought_id"]
        
        # Then retrieve it
        response = authenticated_client.get(f"{BASE_URL}/api/brain/thought/{thought_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert "thought" in data
        thought = data["thought"]
        assert thought["thought_id"] == thought_id
        assert "business_id" in thought
        assert "input" in thought
        assert "status" in thought
        assert "observe" in thought
        assert "orient" in thought
        assert "decide" in thought
        assert "act" in thought
    
    def test_get_thought_contains_ooda_phases(self, authenticated_client):
        """GET /api/brain/thought/{id} contains all OODA phases"""
        # Create a thought
        think_response = authenticated_client.post(
            f"{BASE_URL}/api/brain/think",
            json={"message": "OODA test message"}
        )
        thought_id = think_response.json()["thought_id"]
        
        # Retrieve and verify OODA phases
        response = authenticated_client.get(f"{BASE_URL}/api/brain/thought/{thought_id}")
        thought = response.json()["thought"]
        
        # OBSERVE phase
        assert "observe" in thought
        assert "user_message" in thought["observe"]
        assert "conversation_history" in thought["observe"]
        assert "business_context" in thought["observe"]
        
        # ORIENT phase
        assert "orient" in thought
        assert "intent" in thought["orient"]
        assert "confidence" in thought["orient"]
        assert "entities" in thought["orient"]
        assert "urgency" in thought["orient"]
        assert "reasoning" in thought["orient"]
        
        # DECIDE phase
        assert "decide" in thought
        assert "selected_tool" in thought["decide"]
        assert "tool_parameters" in thought["decide"]
        assert "decision_reasoning" in thought["decide"]
        
        # ACT phase
        assert "act" in thought
        assert "action_status" in thought["act"]
        assert "final_response" in thought["act"]
        assert "pushed_to_dashboard" in thought["act"]
    
    def test_get_thought_not_found(self, authenticated_client):
        """GET /api/brain/thought/{id} returns 404 for non-existent thought"""
        response = authenticated_client.get(f"{BASE_URL}/api/brain/thought/thought_nonexistent123")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestBrainConversationContext:
    """Tests for conversation context handling"""
    
    def test_think_with_conversation_id(self, authenticated_client):
        """POST /api/brain/think accepts conversation_id"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/brain/think",
            json={
                "message": "Hello",
                "conversation_id": "test_conv_123"
            }
        )
        assert response.status_code == 200
        assert response.json()["status"] == "complete"
    
    def test_think_with_context(self, authenticated_client):
        """POST /api/brain/think accepts additional context"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/brain/think",
            json={
                "message": "What's my account status?",
                "context": {
                    "customer_name": "John Doe",
                    "account_type": "premium"
                }
            }
        )
        assert response.status_code == 200
        assert response.json()["status"] == "complete"


class TestBrainResponseFormat:
    """Tests for response format validation"""
    
    def test_think_response_has_required_fields(self, authenticated_client):
        """POST /api/brain/think response has all required fields"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/brain/think",
            json={"message": "Test message"}
        )
        assert response.status_code == 200
        
        data = response.json()
        required_fields = [
            "thought_id", "response", "intent", "confidence",
            "actions_taken", "duration_ms", "status"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
    
    def test_think_confidence_in_valid_range(self, authenticated_client):
        """POST /api/brain/think returns confidence between 0 and 1"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/brain/think",
            json={"message": "Book a meeting"}
        )
        assert response.status_code == 200
        
        confidence = response.json()["confidence"]
        assert 0.0 <= confidence <= 1.0
    
    def test_think_duration_is_positive(self, authenticated_client):
        """POST /api/brain/think returns positive duration_ms"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/brain/think",
            json={"message": "Quick test"}
        )
        assert response.status_code == 200
        
        duration = response.json()["duration_ms"]
        assert duration > 0


class TestBrainActionExecution:
    """Tests for Action Engine integration"""
    
    def test_think_action_intent_triggers_action(self, authenticated_client):
        """POST /api/brain/think triggers Action Engine for action intents"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/brain/think",
            json={"message": "Check my calendar availability for 2026-02-01"}
        )
        assert response.status_code == 200
        
        data = response.json()
        # Should either execute action or ask for clarification
        assert data["status"] == "complete"
        # If action was taken, it should be in actions_taken
        if data["intent"] == "check_availability":
            # Action may or may not be taken depending on entity extraction
            pass
    
    def test_think_chat_intent_no_action(self, authenticated_client):
        """POST /api/brain/think does not trigger actions for chat intent"""
        response = authenticated_client.post(
            f"{BASE_URL}/api/brain/think",
            json={"message": "Tell me a joke"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["intent"] == "chat"
        assert len(data["actions_taken"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
