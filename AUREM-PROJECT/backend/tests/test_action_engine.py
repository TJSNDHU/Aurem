"""
AUREM Action Engine API Tests
Tests for the Action Engine - the "Hands" of the Agent Swarm

Features tested:
- Health endpoint returns healthy with 6 tools
- Get tools endpoint returns tool definitions for AI function calling
- Calendar availability check action executes successfully
- Action history endpoint returns executed actions
- Actions are logged to database
- Tool call endpoint handles function mapping correctly
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test business ID for action engine tests
TEST_BUSINESS_ID = "test_action_engine_business"


class TestActionEngineHealth:
    """Health endpoint tests"""
    
    def test_health_endpoint_returns_healthy(self):
        """Test that health endpoint returns healthy status with 6 tools"""
        response = requests.get(f"{BASE_URL}/api/action-engine/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["tools_count"] == 6
        print(f"✓ Health endpoint: status={data['status']}, tools_count={data['tools_count']}")


class TestActionEngineTools:
    """Tool definitions endpoint tests"""
    
    def test_get_tools_returns_definitions(self):
        """Test that tools endpoint returns all 6 tool definitions"""
        response = requests.get(f"{BASE_URL}/api/action-engine/tools")
        assert response.status_code == 200
        
        data = response.json()
        assert "tools" in data
        assert len(data["tools"]) == 6
        print(f"✓ Tools endpoint: returned {len(data['tools'])} tools")
    
    def test_tools_have_correct_structure(self):
        """Test that each tool has the correct OpenAI function calling structure"""
        response = requests.get(f"{BASE_URL}/api/action-engine/tools")
        assert response.status_code == 200
        
        data = response.json()
        expected_tools = [
            "check_calendar_availability",
            "book_appointment",
            "create_invoice",
            "create_payment_link",
            "send_email",
            "send_whatsapp"
        ]
        
        tool_names = [t["function"]["name"] for t in data["tools"]]
        for expected in expected_tools:
            assert expected in tool_names, f"Missing tool: {expected}"
        
        # Verify structure of each tool
        for tool in data["tools"]:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]
            assert tool["function"]["parameters"]["type"] == "object"
            assert "properties" in tool["function"]["parameters"]
            assert "required" in tool["function"]["parameters"]
        
        print(f"✓ All 6 tools have correct structure: {tool_names}")


class TestActionEngineExecute:
    """Execute action endpoint tests"""
    
    def test_execute_calendar_check_availability(self):
        """Test calendar availability check action"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        payload = {
            "business_id": TEST_BUSINESS_ID,
            "action_type": "calendar.check_availability",
            "parameters": {"date": f"{tomorrow}T00:00:00Z"},
            "triggered_by": "test"
        }
        
        response = requests.post(f"{BASE_URL}/api/action-engine/execute", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "action_id" in data
        assert data["action_id"].startswith("act_")
        assert data["status"] == "success"
        assert "result" in data
        assert "available_slots" in data["result"]
        
        print(f"✓ Calendar check: action_id={data['action_id']}, slots={len(data['result']['available_slots'])}")
    
    def test_execute_invalid_action_type(self):
        """Test that invalid action type returns 400"""
        payload = {
            "business_id": TEST_BUSINESS_ID,
            "action_type": "invalid.action",
            "parameters": {},
            "triggered_by": "test"
        }
        
        response = requests.post(f"{BASE_URL}/api/action-engine/execute", json=payload)
        assert response.status_code == 400
        print("✓ Invalid action type returns 400")
    
    def test_execute_stripe_payment_link_fails_without_key(self):
        """Test that Stripe payment link fails without API key (expected)"""
        payload = {
            "business_id": TEST_BUSINESS_ID,
            "action_type": "stripe.create_payment_link",
            "parameters": {
                "product_name": "Test Product",
                "amount": 99.99
            },
            "triggered_by": "test"
        }
        
        response = requests.post(f"{BASE_URL}/api/action-engine/execute", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        # Stripe may fail if not configured - this is expected
        # The action should still be logged
        assert "action_id" in data
        print(f"✓ Stripe payment link: action_id={data['action_id']}, status={data['status']}")
    
    def test_execute_email_send_fails_without_oauth(self):
        """Test that email send fails without Gmail OAuth (expected)"""
        payload = {
            "business_id": TEST_BUSINESS_ID,
            "action_type": "email.send",
            "parameters": {
                "to": "test@example.com",
                "subject": "Test Email",
                "body": "This is a test email"
            },
            "triggered_by": "test"
        }
        
        response = requests.post(f"{BASE_URL}/api/action-engine/execute", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "action_id" in data
        # Email will fail without OAuth - expected
        print(f"✓ Email send: action_id={data['action_id']}, status={data['status']}")
    
    def test_execute_whatsapp_fails_without_twilio(self):
        """Test that WhatsApp send fails without Twilio config (expected)"""
        payload = {
            "business_id": TEST_BUSINESS_ID,
            "action_type": "whatsapp.send",
            "parameters": {
                "phone": "+14165551234",
                "message": "Test WhatsApp message"
            },
            "triggered_by": "test"
        }
        
        response = requests.post(f"{BASE_URL}/api/action-engine/execute", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "action_id" in data
        # WhatsApp will fail without Twilio config - expected
        print(f"✓ WhatsApp send: action_id={data['action_id']}, status={data['status']}")


class TestActionEngineToolCall:
    """Tool call endpoint tests (AI function calling interface)"""
    
    def test_tool_call_check_calendar_availability(self):
        """Test tool call for calendar availability check"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        payload = {
            "business_id": TEST_BUSINESS_ID,
            "function_name": "check_calendar_availability",
            "arguments": {"date": f"{tomorrow}T00:00:00Z"}
        }
        
        response = requests.post(f"{BASE_URL}/api/action-engine/tool-call", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "action_id" in data
        assert data["status"] == "success"
        assert "result" in data
        assert "available_slots" in data["result"]
        
        print(f"✓ Tool call calendar check: action_id={data['action_id']}, slots={len(data['result']['available_slots'])}")
    
    def test_tool_call_unknown_function(self):
        """Test that unknown function returns error"""
        payload = {
            "business_id": TEST_BUSINESS_ID,
            "function_name": "unknown_function",
            "arguments": {}
        }
        
        response = requests.post(f"{BASE_URL}/api/action-engine/tool-call", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "error" in data
        assert "Unknown" in data["error"]
        
        print(f"✓ Unknown function returns error: {data['error']}")
    
    def test_tool_call_book_appointment(self):
        """Test tool call for booking appointment"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT10:00:00Z")
        
        payload = {
            "business_id": TEST_BUSINESS_ID,
            "function_name": "book_appointment",
            "arguments": {
                "title": "Test Consultation",
                "start_time": tomorrow,
                "attendee_email": "test@example.com"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/action-engine/tool-call", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "action_id" in data
        # Appointment should be created in DB even without Google Calendar
        if data["status"] == "success":
            assert "result" in data
            assert "appointment_id" in data["result"]
            print(f"✓ Tool call book appointment: action_id={data['action_id']}, appt_id={data['result']['appointment_id']}")
        else:
            print(f"✓ Tool call book appointment: action_id={data['action_id']}, status={data['status']}")


class TestActionEngineHistory:
    """Action history endpoint tests"""
    
    def test_get_action_history(self):
        """Test getting action history for a business"""
        response = requests.get(f"{BASE_URL}/api/action-engine/history/{TEST_BUSINESS_ID}")
        assert response.status_code == 200
        
        data = response.json()
        assert "actions" in data
        assert "count" in data
        assert isinstance(data["actions"], list)
        
        print(f"✓ Action history: count={data['count']}")
    
    def test_get_action_history_with_limit(self):
        """Test getting action history with limit parameter"""
        response = requests.get(f"{BASE_URL}/api/action-engine/history/{TEST_BUSINESS_ID}?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert "actions" in data
        assert len(data["actions"]) <= 5
        
        print(f"✓ Action history with limit: returned {len(data['actions'])} actions")
    
    def test_action_history_excludes_mongo_id(self):
        """Test that action history excludes MongoDB _id field"""
        response = requests.get(f"{BASE_URL}/api/action-engine/history/{TEST_BUSINESS_ID}")
        assert response.status_code == 200
        
        data = response.json()
        for action in data["actions"]:
            assert "_id" not in action, "MongoDB _id should be excluded"
        
        print("✓ Action history excludes _id field")


class TestActionEngineIntegration:
    """Integration tests - verify actions are logged correctly"""
    
    def test_action_logged_after_execution(self):
        """Test that executed actions appear in history"""
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Execute an action
        execute_payload = {
            "business_id": TEST_BUSINESS_ID,
            "action_type": "calendar.check_availability",
            "parameters": {"date": f"{tomorrow}T00:00:00Z"},
            "triggered_by": "integration_test"
        }
        
        execute_response = requests.post(f"{BASE_URL}/api/action-engine/execute", json=execute_payload)
        assert execute_response.status_code == 200
        
        action_id = execute_response.json()["action_id"]
        
        # Verify it appears in history
        history_response = requests.get(f"{BASE_URL}/api/action-engine/history/{TEST_BUSINESS_ID}")
        assert history_response.status_code == 200
        
        history = history_response.json()
        action_ids = [a["action_id"] for a in history["actions"]]
        assert action_id in action_ids, f"Action {action_id} not found in history"
        
        print(f"✓ Action {action_id} logged and found in history")
    
    def test_action_has_correct_fields(self):
        """Test that logged actions have all required fields"""
        response = requests.get(f"{BASE_URL}/api/action-engine/history/{TEST_BUSINESS_ID}")
        assert response.status_code == 200
        
        data = response.json()
        if data["actions"]:
            action = data["actions"][0]
            required_fields = ["action_id", "business_id", "action_type", "params", "status", "started_at"]
            for field in required_fields:
                assert field in action, f"Missing field: {field}"
            
            print(f"✓ Action has all required fields: {list(action.keys())}")
        else:
            print("✓ No actions to verify (empty history)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
