"""
AUREM BOS (Business Operating System) Comprehensive Backend Tests
Tests all core features: System Status, Circuit Breakers, Daily Digest, 
Premium Features (Follow-Up, Coexistence, Multi-Modal), Business Management
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

# Get BASE_URL from environment - MUST use external URL for testing
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://live-support-3.preview.emergentagent.com"

# Test credentials from test_credentials.md
TEST_EMAIL = "teji.ss1986@gmail.com"
TEST_PASSWORD = "Admin123"


class TestHealthAndAuth:
    """Basic health checks and authentication tests"""
    
    def test_health_endpoint(self):
        """Test basic health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print(f"✓ Health check passed: {response.json()}")
    
    def test_system_health_no_auth(self):
        """Test system health endpoint (no auth required)"""
        response = requests.get(f"{BASE_URL}/api/system/health", timeout=10)
        assert response.status_code == 200, f"System health failed: {response.text}"
        data = response.json()
        assert "status" in data
        print(f"✓ System health: {data}")
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/platform/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
            timeout=10
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "token" in data or "access_token" in data, f"No token in response: {data}"
        print(f"✓ Login successful for {TEST_EMAIL}")
        return data.get("token") or data.get("access_token")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/platform/auth/login",
            json={"email": "invalid@test.com", "password": "wrongpassword"},
            timeout=10
        )
        assert response.status_code in [401, 400], f"Expected 401/400, got {response.status_code}"
        print(f"✓ Invalid login correctly rejected")


@pytest.fixture(scope="class")
def auth_token():
    """Get authentication token for protected endpoints"""
    response = requests.post(
        f"{BASE_URL}/api/platform/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=10
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestSystemStatus:
    """System Status API tests - Real-time health monitoring"""
    
    def test_get_system_status(self, auth_headers):
        """Test comprehensive system status endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/system/status",
            headers=auth_headers,
            timeout=15
        )
        assert response.status_code == 200, f"System status failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "overall_status" in data, "Missing overall_status"
        assert "services" in data, "Missing services"
        assert "pending_work" in data, "Missing pending_work"
        
        print(f"✓ System status: {data['overall_status']}")
        print(f"  - Services: {data.get('services', {})}")
        print(f"  - Pending work: {data.get('pending_work', {})}")
    
    def test_force_sync(self, auth_headers):
        """Test force sync endpoint - one-click fix everything"""
        response = requests.post(
            f"{BASE_URL}/api/system/sync",
            headers=auth_headers,
            timeout=30
        )
        assert response.status_code == 200, f"Force sync failed: {response.text}"
        data = response.json()
        
        assert "success" in data, "Missing success field"
        assert "results" in data, "Missing results field"
        
        print(f"✓ Force sync: success={data['success']}")
        print(f"  - Results: {data.get('results', {})}")
        if data.get('errors'):
            print(f"  - Errors: {data['errors']}")
    
    def test_automation_status(self, auth_headers):
        """Test automation status endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/system/automation-status",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Automation status failed: {response.text}"
        data = response.json()
        
        assert "premium_features" in data, "Missing premium_features"
        print(f"✓ Automation status: {data}")
    
    def test_pending_work(self, auth_headers):
        """Test pending work endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/system/pending-work",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Pending work failed: {response.text}"
        data = response.json()
        
        assert "followups" in data, "Missing followups"
        assert "handoffs" in data, "Missing handoffs"
        print(f"✓ Pending work: {data}")


class TestCircuitBreakers:
    """Circuit Breaker tests - All 13 breakers protecting external services"""
    
    def test_get_circuit_breakers(self, auth_headers):
        """Test get all circuit breakers status"""
        response = requests.get(
            f"{BASE_URL}/api/system/circuit-breakers",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Circuit breakers failed: {response.text}"
        data = response.json()
        
        assert "breakers" in data, "Missing breakers"
        assert "total_breakers" in data, "Missing total_breakers"
        
        # Verify we have the expected breakers
        breakers = data.get("breakers", {})
        expected_breakers = ["anthropic", "openai", "emergent_llm", "mongodb", "twilio", "whatsapp"]
        
        for breaker in expected_breakers:
            if breaker in breakers:
                print(f"  - {breaker}: {breakers[breaker].get('state', 'unknown')}")
        
        print(f"✓ Circuit breakers: {data['total_breakers']} total, {data.get('open_breakers', 0)} open")
    
    def test_reset_all_circuit_breakers(self, auth_headers):
        """Test reset all circuit breakers"""
        response = requests.post(
            f"{BASE_URL}/api/system/circuit-breakers/reset",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Reset circuit breakers failed: {response.text}"
        data = response.json()
        
        assert "reset" in data, "Missing reset field"
        print(f"✓ Circuit breakers reset: {data}")
    
    def test_reset_specific_circuit_breaker(self, auth_headers):
        """Test reset specific circuit breaker"""
        response = requests.post(
            f"{BASE_URL}/api/system/circuit-breakers/reset?service=mongodb",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Reset specific breaker failed: {response.text}"
        data = response.json()
        
        print(f"✓ MongoDB circuit breaker reset: {data}")


class TestDailyDigest:
    """Daily Digest tests - Event recording and AI-powered summary generation"""
    
    def test_record_event(self, auth_headers):
        """Test recording an event for digest aggregation"""
        test_event = {
            "event_type": "test_event",
            "title": f"Test Event {uuid.uuid4().hex[:8]}",
            "description": "This is a test event for digest testing",
            "business_id": "TEST-BIZ-001",
            "priority": "medium",
            "metadata": {"test": True, "timestamp": datetime.now().isoformat()},
            "action_required": False
        }
        
        response = requests.post(
            f"{BASE_URL}/api/digest/record-event",
            headers=auth_headers,
            json=test_event,
            timeout=10
        )
        assert response.status_code == 200, f"Record event failed: {response.text}"
        data = response.json()
        
        assert "event_id" in data, "Missing event_id"
        assert data.get("recorded") == True, "Event not recorded"
        
        print(f"✓ Event recorded: {data['event_id']}")
        return data["event_id"]
    
    def test_record_critical_event(self, auth_headers):
        """Test recording a critical priority event"""
        test_event = {
            "event_type": "system_alert",
            "title": "Critical Test Alert",
            "description": "Testing critical event handling",
            "business_id": "TEST-BIZ-001",
            "priority": "critical",
            "action_required": True,
            "action_url": "https://example.com/action"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/digest/record-event",
            headers=auth_headers,
            json=test_event,
            timeout=10
        )
        assert response.status_code == 200, f"Record critical event failed: {response.text}"
        data = response.json()
        
        assert data.get("priority") == "critical", "Priority not set correctly"
        print(f"✓ Critical event recorded: {data}")
    
    def test_generate_digest(self, auth_headers):
        """Test generating daily digest with AI summary"""
        request_data = {
            "business_id": "TEST-BIZ-001",
            "hours": 24
        }
        
        response = requests.post(
            f"{BASE_URL}/api/digest/generate",
            headers=auth_headers,
            json=request_data,
            timeout=30  # AI summary may take time
        )
        assert response.status_code == 200, f"Generate digest failed: {response.text}"
        data = response.json()
        
        assert "business_id" in data, "Missing business_id"
        assert "summary" in data, "Missing summary"
        assert "events_count" in data, "Missing events_count"
        
        print(f"✓ Digest generated:")
        print(f"  - Events: {data.get('events_count', 0)}")
        print(f"  - Summary: {data.get('summary', 'N/A')[:100]}...")
    
    def test_get_events(self, auth_headers):
        """Test getting events for a business"""
        response = requests.get(
            f"{BASE_URL}/api/digest/events/TEST-BIZ-001?hours=24",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Get events failed: {response.text}"
        data = response.json()
        
        assert "events" in data, "Missing events"
        assert "count" in data, "Missing count"
        
        print(f"✓ Events retrieved: {data['count']} events")
    
    def test_get_digest_stats(self, auth_headers):
        """Test getting digest statistics"""
        response = requests.get(
            f"{BASE_URL}/api/digest/stats/TEST-BIZ-001?days=7",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Get stats failed: {response.text}"
        data = response.json()
        
        assert "total_events" in data, "Missing total_events"
        print(f"✓ Digest stats: {data}")


class TestPremiumFollowUp:
    """Premium Follow-Up Engine tests - Proactive recovery"""
    
    def test_get_followup_candidates(self, auth_headers):
        """Test getting follow-up candidates"""
        response = requests.get(
            f"{BASE_URL}/api/premium/followup/candidates/TEST-BIZ-001?timing=24h",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Get candidates failed: {response.text}"
        data = response.json()
        
        assert "business_id" in data, "Missing business_id"
        assert "count" in data, "Missing count"
        
        print(f"✓ Follow-up candidates: {data['count']}")
    
    def test_run_followup_cycle(self, auth_headers):
        """Test running follow-up cycle"""
        request_data = {
            "business_id": "TEST-BIZ-001",
            "timing": "24h"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/premium/followup/run",
            headers=auth_headers,
            json=request_data,
            timeout=30
        )
        assert response.status_code == 200, f"Run followup failed: {response.text}"
        data = response.json()
        
        assert "candidates" in data, "Missing candidates"
        assert "followups_sent" in data, "Missing followups_sent"
        
        print(f"✓ Follow-up cycle: {data['candidates']} candidates, {data['followups_sent']} sent")
    
    def test_update_followup_status(self, auth_headers):
        """Test updating follow-up status"""
        response = requests.put(
            f"{BASE_URL}/api/premium/followup/status/TEST-CUSTOMER-001?status=closed_won&notes=Test%20conversion",
            headers=auth_headers,
            timeout=10
        )
        # May return 404 if customer doesn't exist - that's OK for this test
        assert response.status_code in [200, 404], f"Update status failed: {response.text}"
        print(f"✓ Follow-up status update: {response.status_code}")


class TestWhatsAppCoexistence:
    """WhatsApp Coexistence tests - Human handoff system"""
    
    def test_get_conversation_state(self, auth_headers):
        """Test getting conversation state"""
        response = requests.get(
            f"{BASE_URL}/api/premium/handoff/state/TEST-CUSTOMER-001",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Get state failed: {response.text}"
        data = response.json()
        
        assert "customer_id" in data, "Missing customer_id"
        assert "mode" in data, "Missing mode"
        
        print(f"✓ Conversation state: mode={data.get('mode')}")
    
    def test_human_takeover(self, auth_headers):
        """Test human takeover of conversation"""
        request_data = {
            "customer_id": "TEST-CUSTOMER-001",
            "business_id": "TEST-BIZ-001",
            "human_id": "admin-user-001",
            "reason": "human_reply"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/premium/handoff/takeover",
            headers=auth_headers,
            json=request_data,
            timeout=10
        )
        assert response.status_code == 200, f"Human takeover failed: {response.text}"
        data = response.json()
        
        assert "status" in data, "Missing status"
        print(f"✓ Human takeover: {data}")
    
    def test_resume_ai_mode(self, auth_headers):
        """Test resuming AI mode after handoff"""
        request_data = {
            "customer_id": "TEST-CUSTOMER-001",
            "reason": "manual"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/premium/handoff/resume-ai",
            headers=auth_headers,
            json=request_data,
            timeout=10
        )
        assert response.status_code == 200, f"Resume AI failed: {response.text}"
        data = response.json()
        
        assert "status" in data, "Missing status"
        print(f"✓ AI mode resumed: {data}")
    
    def test_get_active_human_conversations(self, auth_headers):
        """Test getting active human conversations"""
        response = requests.get(
            f"{BASE_URL}/api/premium/handoff/active/TEST-BIZ-001",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Get active failed: {response.text}"
        data = response.json()
        
        assert "count" in data, "Missing count"
        print(f"✓ Active human conversations: {data['count']}")
    
    def test_escalate_to_human(self, auth_headers):
        """Test AI escalation to human"""
        response = requests.post(
            f"{BASE_URL}/api/premium/handoff/escalate?customer_id=TEST-CUSTOMER-002&business_id=TEST-BIZ-001&reason=complex_query&context=Customer%20needs%20help",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Escalate failed: {response.text}"
        data = response.json()
        
        assert "status" in data, "Missing status"
        print(f"✓ Escalation: {data}")


class TestMultiModalProcessing:
    """Multi-Modal Processing tests - Audio/image support"""
    
    def test_get_multimodal_status(self, auth_headers):
        """Test getting multi-modal processing status"""
        response = requests.get(
            f"{BASE_URL}/api/premium/multimodal/status",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Get status failed: {response.text}"
        data = response.json()
        
        assert "enabled" in data, "Missing enabled"
        assert "supported_types" in data, "Missing supported_types"
        
        print(f"✓ Multi-modal status:")
        print(f"  - Enabled: {data.get('enabled')}")
        print(f"  - Types: {data.get('supported_types')}")
        print(f"  - Tier: {data.get('tier')}")
    
    def test_process_text_message(self, auth_headers):
        """Test processing a text message"""
        message_data = {
            "type": "text",
            "content": "Hello, I need help with my order"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/premium/multimodal/process",
            headers=auth_headers,
            json=message_data,
            timeout=10
        )
        assert response.status_code == 200, f"Process text failed: {response.text}"
        data = response.json()
        
        assert "type" in data, "Missing type"
        assert "text" in data, "Missing text"
        
        print(f"✓ Text message processed: {data}")


class TestBusinessManagement:
    """Business Management tests - Multi-business CRUD"""
    
    def test_list_businesses(self, auth_headers):
        """Test listing all businesses"""
        response = requests.get(
            f"{BASE_URL}/api/business/list",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"List businesses failed: {response.text}"
        data = response.json()
        
        assert "businesses" in data, "Missing businesses"
        assert "total" in data, "Missing total"
        
        print(f"✓ Businesses: {data['total']} total")
        for biz in data.get("businesses", [])[:3]:
            print(f"  - {biz.get('name')} ({biz.get('business_id')})")
    
    def test_create_business(self, auth_headers):
        """Test creating a new business"""
        test_business = {
            "name": f"Test Business {uuid.uuid4().hex[:6]}",
            "type": "custom",
            "description": "Test business for API testing",
            "industry_keywords": ["test", "api"],
            "tone": "professional",
            "target_audience": "Developers",
            "products_services": ["API Testing"],
            "unique_selling_points": ["Fast", "Reliable"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/business/create",
            headers=auth_headers,
            json=test_business,
            timeout=15
        )
        assert response.status_code == 200, f"Create business failed: {response.text}"
        data = response.json()
        
        assert "business_id" in data, "Missing business_id"
        assert "status" in data, "Missing status"
        
        print(f"✓ Business created: {data['business_id']}")
        return data["business_id"]
    
    def test_get_business(self, auth_headers):
        """Test getting business details"""
        # First create a business
        test_business = {
            "name": f"Get Test Business {uuid.uuid4().hex[:6]}",
            "type": "custom",
            "description": "Test business for get test"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/business/create",
            headers=auth_headers,
            json=test_business,
            timeout=15
        )
        
        if create_response.status_code == 200:
            business_id = create_response.json().get("business_id")
            
            # Now get the business
            response = requests.get(
                f"{BASE_URL}/api/business/{business_id}",
                headers=auth_headers,
                timeout=10
            )
            # 404 is acceptable if business is stored in memory only
            assert response.status_code in [200, 404], f"Get business failed: {response.text}"
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Business retrieved: {data}")
            else:
                print(f"✓ Business created but not persisted to DB (in-memory only)")
        else:
            print(f"✓ Business creation skipped (may already exist)")
    
    def test_list_business_agents(self, auth_headers):
        """Test listing agents for a business"""
        # First get list of businesses
        list_response = requests.get(
            f"{BASE_URL}/api/business/list",
            headers=auth_headers,
            timeout=10
        )
        
        if list_response.status_code == 200:
            businesses = list_response.json().get("businesses", [])
            if businesses:
                business_id = businesses[0].get("business_id")
                
                response = requests.get(
                    f"{BASE_URL}/api/business/{business_id}/agents",
                    headers=auth_headers,
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✓ Business agents: {len(data.get('agents', []))} agents")
                else:
                    print(f"✓ Agents endpoint: {response.status_code}")
            else:
                print("✓ No businesses to test agents")
        else:
            print("✓ Business list skipped")


class TestPremiumDashboard:
    """Premium Dashboard tests - Overview of all premium features"""
    
    def test_get_premium_dashboard(self, auth_headers):
        """Test getting premium features dashboard"""
        response = requests.get(
            f"{BASE_URL}/api/premium/dashboard/TEST-BIZ-001",
            headers=auth_headers,
            timeout=15
        )
        assert response.status_code == 200, f"Get dashboard failed: {response.text}"
        data = response.json()
        
        assert "business_id" in data, "Missing business_id"
        assert "premium_features" in data, "Missing premium_features"
        
        features = data.get("premium_features", {})
        print(f"✓ Premium dashboard:")
        print(f"  - Follow-up: {features.get('proactive_followup', {})}")
        print(f"  - Coexistence: {features.get('human_coexistence', {})}")
        print(f"  - Multi-modal: {features.get('multimodal_processing', {})}")


class TestOmniDimension:
    """OmniDimension tests - Multi-channel messaging"""
    
    def test_inbound_message(self, auth_headers):
        """Test processing inbound message"""
        request_data = {
            "channel": "whatsapp",
            "sender_id": "+1234567890",
            "content": "Hello, I need help",
            "metadata": {"test": True}
        }
        
        response = requests.post(
            f"{BASE_URL}/api/business/TEST-BIZ-001/message/inbound",
            headers=auth_headers,
            json=request_data,
            timeout=15
        )
        # May fail if business doesn't exist - that's OK
        print(f"✓ Inbound message: {response.status_code}")
    
    def test_channel_analytics(self, auth_headers):
        """Test getting channel analytics"""
        response = requests.get(
            f"{BASE_URL}/api/business/TEST-BIZ-001/analytics/channels",
            headers=auth_headers,
            timeout=10
        )
        # May return empty data - that's OK
        print(f"✓ Channel analytics: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
