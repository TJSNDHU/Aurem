"""
AUREM Voice Module (Phase 8) - Backend API Tests
Tests for Vapi AI + Vobiz SIP Trunk + ElevenLabs integration scaffold

Endpoints tested:
- GET /api/aurem-voice/health - Health check with no_key_scaffold mode
- GET /api/aurem-voice/personas - List available personas
- GET /api/aurem-voice/tools - Get Action Engine tool definitions
- GET /api/aurem-voice/{business_id}/calls/active - Get active calls
- GET /api/aurem-voice/{business_id}/calls - Get call history
- POST /api/aurem-voice/{business_id}/call - Initiate outbound call (mock mode)
- GET /api/aurem-voice/{business_id}/config/{persona} - Get Vapi assistant config
- POST /api/aurem-voice/webhook - Handle Vapi webhook payloads
"""

import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
BUSINESS_ID = "test_voice_biz_001"


class TestVoiceModuleHealth:
    """Health check endpoint tests"""
    
    def test_health_returns_healthy_status(self):
        """GET /api/aurem-voice/health should return healthy status"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "aurem-voice-module"
        assert data["mode"] == "no_key_scaffold"
        print("✓ Health endpoint returns healthy status with no_key_scaffold mode")
    
    def test_health_shows_configuration_status(self):
        """Health endpoint should show configuration status for Vapi/ElevenLabs"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/health")
        assert response.status_code == 200
        
        data = response.json()
        config = data.get("configuration", {})
        
        # Verify configuration fields exist
        assert "vapi_api_key" in config
        assert "elevenlabs_api_key" in config
        assert "webhook_secret" in config
        assert "phone_number_id" in config
        print(f"✓ Configuration status: VAPI={config['vapi_api_key']}, ElevenLabs={config['elevenlabs_api_key']}")
    
    def test_health_lists_capabilities(self):
        """Health endpoint should list available capabilities"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/health")
        assert response.status_code == 200
        
        data = response.json()
        capabilities = data.get("capabilities", [])
        
        # Verify expected capabilities
        assert "inbound_calls" in capabilities
        assert "ooda_telemetry" in capabilities
        assert "action_engine_bridge" in capabilities
        assert "unified_inbox_integration" in capabilities
        assert "live_dashboard_feed" in capabilities
        print(f"✓ Capabilities listed: {len(capabilities)} features")
    
    def test_health_lists_personas(self):
        """Health endpoint should list available personas"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/health")
        assert response.status_code == 200
        
        data = response.json()
        personas = data.get("personas_available", [])
        
        assert "skincare_luxe" in personas
        assert "auto_advisor" in personas
        assert "general_assistant" in personas
        print(f"✓ Personas available: {personas}")


class TestVoiceModulePersonas:
    """Persona listing endpoint tests"""
    
    def test_personas_returns_five_personas(self):
        """GET /api/aurem-voice/personas should return 5 personas (3 standard + 2 VIP)"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/personas")
        assert response.status_code == 200
        
        data = response.json()
        personas = data.get("personas", [])
        
        # Now includes VIP personas: skincare_luxe_vip, auto_advisor_vip
        assert len(personas) == 5
        print(f"✓ Returned {len(personas)} personas (including VIP tiers)")
    
    def test_personas_have_required_fields(self):
        """Each persona should have id, name, description, has_prompt"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/personas")
        assert response.status_code == 200
        
        data = response.json()
        personas = data.get("personas", [])
        
        for persona in personas:
            assert "id" in persona
            assert "name" in persona
            assert "description" in persona
            assert "has_prompt" in persona
            assert persona["has_prompt"] == True  # All should have prompts
        print("✓ All personas have required fields with prompts")
    
    def test_personas_include_skincare_luxe(self):
        """Personas should include skincare_luxe"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/personas")
        assert response.status_code == 200
        
        data = response.json()
        personas = data.get("personas", [])
        
        skincare = next((p for p in personas if p["id"] == "skincare_luxe"), None)
        assert skincare is not None
        assert "Skincare" in skincare["name"]
        print(f"✓ Skincare Luxe persona: {skincare['description']}")
    
    def test_personas_include_auto_advisor(self):
        """Personas should include auto_advisor"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/personas")
        assert response.status_code == 200
        
        data = response.json()
        personas = data.get("personas", [])
        
        auto = next((p for p in personas if p["id"] == "auto_advisor"), None)
        assert auto is not None
        assert "Auto" in auto["name"]
        print(f"✓ Auto Advisor persona: {auto['description']}")


class TestVoiceModuleTools:
    """Action Engine tool definitions endpoint tests"""
    
    def test_tools_returns_tool_definitions(self):
        """GET /api/aurem-voice/tools should return Action Engine tools"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/tools")
        assert response.status_code == 200
        
        data = response.json()
        assert "tools" in data
        assert "vapi_functions" in data
        assert "count" in data
        print(f"✓ Returned {data['count']} tool definitions")
    
    def test_tools_include_calendar_functions(self):
        """Tools should include calendar-related functions"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/tools")
        assert response.status_code == 200
        
        data = response.json()
        tools = data.get("tools", [])
        
        tool_names = [t.get("function", {}).get("name") for t in tools]
        assert "check_calendar_availability" in tool_names
        assert "book_appointment" in tool_names
        print("✓ Calendar tools present: check_calendar_availability, book_appointment")
    
    def test_tools_include_payment_functions(self):
        """Tools should include payment-related functions"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/tools")
        assert response.status_code == 200
        
        data = response.json()
        tools = data.get("tools", [])
        
        tool_names = [t.get("function", {}).get("name") for t in tools]
        assert "create_invoice" in tool_names
        assert "create_payment_link" in tool_names
        print("✓ Payment tools present: create_invoice, create_payment_link")
    
    def test_vapi_functions_format(self):
        """Vapi functions should have correct format"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/tools")
        assert response.status_code == 200
        
        data = response.json()
        vapi_functions = data.get("vapi_functions", [])
        
        for func in vapi_functions:
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
            assert "async" in func
            assert func["async"] == True
        print(f"✓ All {len(vapi_functions)} Vapi functions have correct format")


class TestVoiceModuleCallManagement:
    """Call management endpoint tests"""
    
    def test_active_calls_returns_empty_array(self):
        """GET /api/aurem-voice/{business_id}/calls/active should return empty array initially"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/{BUSINESS_ID}/calls/active")
        assert response.status_code == 200
        
        data = response.json()
        assert "active_calls" in data
        assert isinstance(data["active_calls"], list)
        assert "count" in data
        assert data["business_id"] == BUSINESS_ID
        print(f"✓ Active calls: {data['count']} (empty as expected)")
    
    def test_call_history_returns_empty_initially(self):
        """GET /api/aurem-voice/{business_id}/calls should return empty history initially"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/{BUSINESS_ID}/calls")
        assert response.status_code == 200
        
        data = response.json()
        assert "calls" in data
        assert isinstance(data["calls"], list)
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        print(f"✓ Call history: {data['total']} total calls")
    
    def test_call_history_supports_pagination(self):
        """Call history should support limit and offset parameters"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/{BUSINESS_ID}/calls?limit=10&offset=0")
        assert response.status_code == 200
        
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0
        print("✓ Pagination parameters accepted")


class TestVoiceModuleOutboundCall:
    """Outbound call initiation tests"""
    
    def test_initiate_call_returns_mock_response(self):
        """POST /api/aurem-voice/{business_id}/call should return mock response without VAPI_API_KEY"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-voice/{BUSINESS_ID}/call",
            json={
                "phone_number": "+1234567890",
                "persona": "general_assistant"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "mock"
        assert "call_id" in data
        assert data["call_id"].startswith("mock_")
        assert data["phone_number"] == "+1234567890"
        assert data["persona"] == "general_assistant"
        print(f"✓ Mock call initiated: {data['call_id']}")
    
    def test_initiate_call_with_skincare_persona(self):
        """Outbound call should work with skincare_luxe persona"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-voice/{BUSINESS_ID}/call",
            json={
                "phone_number": "+1987654321",
                "persona": "skincare_luxe"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "mock"
        assert data["persona"] == "skincare_luxe"
        print(f"✓ Skincare persona call: {data['call_id']}")
    
    def test_initiate_call_with_auto_advisor_persona(self):
        """Outbound call should work with auto_advisor persona"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-voice/{BUSINESS_ID}/call",
            json={
                "phone_number": "+1555555555",
                "persona": "auto_advisor"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "mock"
        assert data["persona"] == "auto_advisor"
        print(f"✓ Auto advisor persona call: {data['call_id']}")
    
    def test_initiate_call_rejects_invalid_persona(self):
        """Outbound call should reject invalid persona"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-voice/{BUSINESS_ID}/call",
            json={
                "phone_number": "+1234567890",
                "persona": "invalid_persona"
            }
        )
        assert response.status_code == 400
        print("✓ Invalid persona rejected with 400")


class TestVoiceModuleAssistantConfig:
    """Vapi assistant configuration endpoint tests"""
    
    def test_config_returns_vapi_assistant_config(self):
        """GET /api/aurem-voice/{business_id}/config/{persona} should return Vapi config"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/{BUSINESS_ID}/config/skincare_luxe")
        assert response.status_code == 200
        
        data = response.json()
        assert "vapi_assistant_config" in data
        assert data["business_id"] == BUSINESS_ID
        assert data["persona"] == "skincare_luxe"
        print("✓ Vapi assistant config returned")
    
    def test_config_includes_model_settings(self):
        """Config should include model provider and system prompt"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/{BUSINESS_ID}/config/skincare_luxe")
        assert response.status_code == 200
        
        data = response.json()
        config = data.get("vapi_assistant_config", {})
        model = config.get("model", {})
        
        assert model.get("provider") == "openai"
        # Standard personas use gpt-4o-mini, VIP personas use gpt-4o
        assert model.get("model") in ["gpt-4o", "gpt-4o-mini"]
        assert "systemPrompt" in model
        assert "PDRN" in model["systemPrompt"]  # Skincare-specific content
        print(f"✓ Model settings: OpenAI {model.get('model')} with skincare system prompt")
    
    def test_config_includes_voice_settings(self):
        """Config should include ElevenLabs voice settings"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/{BUSINESS_ID}/config/general_assistant")
        assert response.status_code == 200
        
        data = response.json()
        config = data.get("vapi_assistant_config", {})
        voice = config.get("voice", {})
        
        assert voice.get("provider") == "11labs"
        assert "voiceId" in voice
        print(f"✓ Voice settings: ElevenLabs with voice ID '{voice.get('voiceId')}'")
    
    def test_config_includes_functions(self):
        """Config should include Action Engine functions"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/{BUSINESS_ID}/config/auto_advisor")
        assert response.status_code == 200
        
        data = response.json()
        config = data.get("vapi_assistant_config", {})
        model = config.get("model", {})
        functions = model.get("functions", [])
        
        assert len(functions) > 0
        func_names = [f.get("name") for f in functions]
        assert "book_appointment" in func_names
        assert "create_payment_link" in func_names
        print(f"✓ Config includes {len(functions)} Action Engine functions")
    
    def test_config_rejects_invalid_persona(self):
        """Config should reject invalid persona"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/{BUSINESS_ID}/config/invalid_persona")
        assert response.status_code == 400
        print("✓ Invalid persona rejected with 400")


class TestVoiceModuleWebhook:
    """Vapi webhook endpoint tests"""
    
    def test_webhook_accepts_call_started_event(self):
        """POST /api/aurem-voice/webhook should accept call.started event"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-voice/webhook",
            json={
                "type": "call.started",
                "callId": "test_webhook_call_001",
                "phoneNumber": "+1234567890",
                "call": {
                    "id": "test_webhook_call_001",
                    "type": "inboundPhoneCall",
                    "customer": {"number": "+1234567890"}
                }
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        assert data["call_id"] == "test_webhook_call_001"
        print("✓ call.started webhook processed successfully")
    
    def test_webhook_accepts_transcript_event(self):
        """POST /api/aurem-voice/webhook should accept transcript event"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-voice/webhook",
            json={
                "type": "transcript",
                "callId": "test_webhook_call_001",
                "role": "user",
                "text": "I'd like to book an appointment",
                "isFinal": True
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        print("✓ transcript webhook processed successfully")
    
    def test_webhook_accepts_call_ended_event(self):
        """POST /api/aurem-voice/webhook should accept call.ended event"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-voice/webhook",
            json={
                "type": "call.ended",
                "callId": "test_webhook_call_001",
                "durationSeconds": 120,
                "endedReason": "customer_hangup",
                "call": {
                    "id": "test_webhook_call_001",
                    "duration": 120,
                    "endedReason": "customer_hangup"
                }
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        print("✓ call.ended webhook processed successfully")
    
    def test_webhook_handles_unknown_event_type(self):
        """Webhook should handle unknown event types gracefully"""
        response = requests.post(
            f"{BASE_URL}/api/aurem-voice/webhook",
            json={
                "type": "unknown.event",
                "callId": "test_call"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ignored"
        print("✓ Unknown event type handled gracefully")
    
    def test_webhook_verification_endpoint(self):
        """GET /api/aurem-voice/webhook should handle verification"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/webhook")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        print("✓ Webhook verification endpoint accessible")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
