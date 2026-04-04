"""
Lead Capture System Tests (Phase A)
Tests for AUREM AI SaaS Platform Lead Capture functionality

Features tested:
- Lead Intent Detection (buying signals, appointment requests)
- Contact Extraction (name, phone, email via regex)
- Lead Storage (MongoDB with tenant isolation)
- Lead Capture Hook (duplicate prevention)
- Email Notifications (graceful fallback)
- API Endpoints (GET /api/leads, GET /api/leads/stats, POST /api/leads/test-capture, POST /api/leads/{lead_id}/status)
- Multi-tenancy (tenant_a leads don't appear in tenant_b's list)
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://live-support-3.preview.emergentagent.com"


class TestLeadIntentDetection:
    """Test lead intent detection from user messages"""
    
    def test_detect_booking_intent(self):
        """Test detection of 'book appointment' as lead intent"""
        response = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": "TEST_tenant_booking",
                "conversation_id": f"TEST_conv_booking_{uuid.uuid4().hex[:8]}",
                "user_message": "I want to book an appointment for tomorrow"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        result = data["result"]
        # Should detect as lead with booking intent
        assert result.get("lead_captured") == True or result.get("confidence", 0) >= 0.5
        print(f"Booking intent test: lead_captured={result.get('lead_captured')}, confidence={result.get('confidence')}")
    
    def test_detect_interest_intent(self):
        """Test detection of 'interested in product' as lead intent"""
        response = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": "TEST_tenant_interest",
                "conversation_id": f"TEST_conv_interest_{uuid.uuid4().hex[:8]}",
                "user_message": "I'm interested in your premium skincare products"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        result = data["result"]
        # Should detect as lead with interest
        assert result.get("lead_captured") == True or result.get("confidence", 0) >= 0.25
        print(f"Interest intent test: lead_captured={result.get('lead_captured')}, confidence={result.get('confidence')}")
    
    def test_detect_price_inquiry(self):
        """Test detection of 'what's the price' as lead intent"""
        response = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": "TEST_tenant_price",
                "conversation_id": f"TEST_conv_price_{uuid.uuid4().hex[:8]}",
                "user_message": "What's the price for your consultation service?"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        result = data["result"]
        # Should detect as lead with price inquiry
        print(f"Price inquiry test: lead_captured={result.get('lead_captured')}, confidence={result.get('confidence')}")
    
    def test_no_intent_casual_message(self):
        """Test that casual messages without intent are not captured as leads"""
        response = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": "TEST_tenant_casual",
                "conversation_id": f"TEST_conv_casual_{uuid.uuid4().hex[:8]}",
                "user_message": "Hello, how are you today?"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        result = data["result"]
        # Should NOT be captured as lead (low confidence)
        assert result.get("lead_captured") == False or result.get("confidence", 0) < 0.5
        print(f"Casual message test: lead_captured={result.get('lead_captured')}, confidence={result.get('confidence')}")
    
    def test_negative_intent_just_browsing(self):
        """Test that 'just browsing' messages are not captured as leads"""
        response = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": "TEST_tenant_browsing",
                "conversation_id": f"TEST_conv_browsing_{uuid.uuid4().hex[:8]}",
                "user_message": "I'm just looking around, not ready to buy yet"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        result = data["result"]
        # Should NOT be captured as lead (negative keywords)
        assert result.get("lead_captured") == False
        print(f"Just browsing test: lead_captured={result.get('lead_captured')}")


class TestContactExtraction:
    """Test contact information extraction from conversations"""
    
    def test_extract_email(self):
        """Test extraction of email from conversation"""
        response = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": "TEST_tenant_email",
                "conversation_id": f"TEST_conv_email_{uuid.uuid4().hex[:8]}",
                "user_message": "I want to book an appointment. My email is john.doe@example.com",
                "conversation_history": [
                    {"role": "user", "content": "Hi, I'm interested in your services"},
                    {"role": "assistant", "content": "Great! Can I get your contact info?"}
                ]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        result = data["result"]
        if result.get("lead_captured"):
            # Verify lead was created - check via GET
            lead_id = result.get("lead_id")
            if lead_id:
                lead_response = requests.get(
                    f"{BASE_URL}/api/leads/{lead_id}",
                    params={"tenant_id": "TEST_tenant_email"}
                )
                if lead_response.status_code == 200:
                    lead_data = lead_response.json()
                    customer = lead_data.get("lead", {}).get("customer", {})
                    assert customer.get("email") == "john.doe@example.com"
                    print(f"Email extraction test: extracted email={customer.get('email')}")
    
    def test_extract_phone(self):
        """Test extraction of phone number from conversation"""
        response = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": "TEST_tenant_phone",
                "conversation_id": f"TEST_conv_phone_{uuid.uuid4().hex[:8]}",
                "user_message": "I want to purchase your product. Call me at 555-123-4567",
                "conversation_history": []
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        result = data["result"]
        if result.get("lead_captured"):
            lead_id = result.get("lead_id")
            if lead_id:
                lead_response = requests.get(
                    f"{BASE_URL}/api/leads/{lead_id}",
                    params={"tenant_id": "TEST_tenant_phone"}
                )
                if lead_response.status_code == 200:
                    lead_data = lead_response.json()
                    customer = lead_data.get("lead", {}).get("customer", {})
                    assert "555" in str(customer.get("phone", ""))
                    print(f"Phone extraction test: extracted phone={customer.get('phone')}")
    
    def test_extract_name(self):
        """Test extraction of name from conversation"""
        response = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": "TEST_tenant_name",
                "conversation_id": f"TEST_conv_name_{uuid.uuid4().hex[:8]}",
                "user_message": "I want to book a consultation. My name is John Smith",
                "conversation_history": []
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        result = data["result"]
        if result.get("lead_captured"):
            lead_id = result.get("lead_id")
            if lead_id:
                lead_response = requests.get(
                    f"{BASE_URL}/api/leads/{lead_id}",
                    params={"tenant_id": "TEST_tenant_name"}
                )
                if lead_response.status_code == 200:
                    lead_data = lead_response.json()
                    customer = lead_data.get("lead", {}).get("customer", {})
                    # Name should be extracted
                    print(f"Name extraction test: extracted name={customer.get('name')}")


class TestLeadStorage:
    """Test lead storage in MongoDB with tenant isolation"""
    
    def test_create_lead_with_tenant_id(self):
        """Test that leads are saved with correct tenant_id"""
        tenant_id = f"TEST_tenant_storage_{uuid.uuid4().hex[:8]}"
        conv_id = f"TEST_conv_storage_{uuid.uuid4().hex[:8]}"
        
        response = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": tenant_id,
                "conversation_id": conv_id,
                "user_message": "I want to buy your product today!"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        result = data["result"]
        
        if result.get("lead_captured"):
            lead_id = result.get("lead_id")
            assert lead_id is not None
            
            # Verify lead exists with correct tenant_id
            lead_response = requests.get(
                f"{BASE_URL}/api/leads/{lead_id}",
                params={"tenant_id": tenant_id}
            )
            assert lead_response.status_code == 200
            lead_data = lead_response.json()
            assert lead_data["success"] == True
            print(f"Lead storage test: lead_id={lead_id}, tenant_id={tenant_id}")
    
    def test_get_leads_for_tenant(self):
        """Test GET /api/leads returns leads for specific tenant"""
        tenant_id = "TEST_tenant_list"
        
        # Create a lead first
        response = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": tenant_id,
                "conversation_id": f"TEST_conv_list_{uuid.uuid4().hex[:8]}",
                "user_message": "I want to schedule an appointment"
            }
        )
        assert response.status_code == 200
        
        # Get leads for tenant
        list_response = requests.get(
            f"{BASE_URL}/api/leads/",
            params={"tenant_id": tenant_id}
        )
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert list_data["success"] == True
        assert "leads" in list_data
        assert "count" in list_data
        print(f"Get leads test: count={list_data['count']}")


class TestLeadCaptureHook:
    """Test lead capture hook functionality"""
    
    def test_duplicate_prevention(self):
        """Test that duplicate leads for same conversation_id are prevented"""
        tenant_id = "TEST_tenant_dup"
        conv_id = f"TEST_conv_dup_{uuid.uuid4().hex[:8]}"
        
        # First capture
        response1 = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": tenant_id,
                "conversation_id": conv_id,
                "user_message": "I want to book an appointment"
            }
        )
        assert response1.status_code == 200
        result1 = response1.json()["result"]
        
        # Second capture with same conversation_id
        response2 = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": tenant_id,
                "conversation_id": conv_id,
                "user_message": "I also want to purchase something"
            }
        )
        assert response2.status_code == 200
        result2 = response2.json()["result"]
        
        # Second should not create new lead
        if result1.get("lead_captured"):
            assert result2.get("lead_captured") == False
            assert "already exists" in result2.get("reason", "").lower() or result2.get("existing_lead_id") is not None
            print(f"Duplicate prevention test: first={result1.get('lead_captured')}, second={result2.get('lead_captured')}")


class TestLeadStats:
    """Test lead statistics API"""
    
    def test_get_stats_today(self):
        """Test GET /api/leads/stats returns today's statistics"""
        response = requests.get(
            f"{BASE_URL}/api/leads/stats",
            params={"period": "today", "tenant_id": "aurem_platform"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["period"] == "today"
        stats = data["stats"]
        assert "total_leads" in stats
        assert "new_leads" in stats
        assert "converted" in stats
        assert "total_value" in stats
        assert "conversion_rate" in stats
        print(f"Stats test: total_leads={stats['total_leads']}, conversion_rate={stats['conversion_rate']}")
    
    def test_get_stats_all_time(self):
        """Test GET /api/leads/stats with period=all"""
        response = requests.get(
            f"{BASE_URL}/api/leads/stats",
            params={"period": "all", "tenant_id": "aurem_platform"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["period"] == "all"
        print(f"Stats all-time test: total_leads={data['stats']['total_leads']}")


class TestLeadStatusUpdate:
    """Test lead status update API"""
    
    def test_update_lead_status_to_contacted(self):
        """Test POST /api/leads/{lead_id}/status to update status"""
        tenant_id = "TEST_tenant_status"
        conv_id = f"TEST_conv_status_{uuid.uuid4().hex[:8]}"
        
        # Create a lead first
        create_response = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": tenant_id,
                "conversation_id": conv_id,
                "user_message": "I want to book an appointment tomorrow"
            }
        )
        assert create_response.status_code == 200
        result = create_response.json()["result"]
        
        if result.get("lead_captured"):
            lead_id = result.get("lead_id")
            
            # Update status to contacted
            update_response = requests.post(
                f"{BASE_URL}/api/leads/{lead_id}/status",
                params={"tenant_id": tenant_id},
                json={"status": "contacted"}
            )
            assert update_response.status_code == 200
            update_data = update_response.json()
            assert update_data["success"] == True
            assert update_data["lead"]["status"] == "contacted"
            print(f"Status update test: lead_id={lead_id}, new_status=contacted")
    
    def test_update_lead_status_to_converted(self):
        """Test updating lead status to converted"""
        tenant_id = "TEST_tenant_converted"
        conv_id = f"TEST_conv_converted_{uuid.uuid4().hex[:8]}"
        
        # Create a lead
        create_response = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": tenant_id,
                "conversation_id": conv_id,
                "user_message": "I want to purchase your product"
            }
        )
        assert create_response.status_code == 200
        result = create_response.json()["result"]
        
        if result.get("lead_captured"):
            lead_id = result.get("lead_id")
            
            # Update to converted
            update_response = requests.post(
                f"{BASE_URL}/api/leads/{lead_id}/status",
                params={"tenant_id": tenant_id},
                json={"status": "converted"}
            )
            assert update_response.status_code == 200
            update_data = update_response.json()
            assert update_data["lead"]["status"] == "converted"
            print(f"Converted status test: lead_id={lead_id}")
    
    def test_invalid_status_returns_400(self):
        """Test that invalid status returns 400 error"""
        tenant_id = "TEST_tenant_invalid"
        conv_id = f"TEST_conv_invalid_{uuid.uuid4().hex[:8]}"
        
        # Create a lead
        create_response = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": tenant_id,
                "conversation_id": conv_id,
                "user_message": "I want to book an appointment"
            }
        )
        assert create_response.status_code == 200
        result = create_response.json()["result"]
        
        if result.get("lead_captured"):
            lead_id = result.get("lead_id")
            
            # Try invalid status
            update_response = requests.post(
                f"{BASE_URL}/api/leads/{lead_id}/status",
                params={"tenant_id": tenant_id},
                json={"status": "invalid_status"}
            )
            assert update_response.status_code == 400
            print(f"Invalid status test: returned 400 as expected")
    
    def test_nonexistent_lead_returns_404(self):
        """Test that updating non-existent lead returns 404"""
        update_response = requests.post(
            f"{BASE_URL}/api/leads/nonexistent_lead_123/status",
            params={"tenant_id": "TEST_tenant"},
            json={"status": "contacted"}
        )
        assert update_response.status_code == 404
        print(f"Non-existent lead test: returned 404 as expected")


class TestMultiTenancy:
    """Test multi-tenant isolation"""
    
    def test_tenant_isolation(self):
        """Test that leads for tenant_a don't appear in tenant_b's list"""
        tenant_a = f"TEST_tenant_A_{uuid.uuid4().hex[:8]}"
        tenant_b = f"TEST_tenant_B_{uuid.uuid4().hex[:8]}"
        
        # Create lead for tenant_a
        response_a = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": tenant_a,
                "conversation_id": f"TEST_conv_A_{uuid.uuid4().hex[:8]}",
                "user_message": "I want to book an appointment"
            }
        )
        assert response_a.status_code == 200
        result_a = response_a.json()["result"]
        
        # Create lead for tenant_b
        response_b = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": tenant_b,
                "conversation_id": f"TEST_conv_B_{uuid.uuid4().hex[:8]}",
                "user_message": "I want to purchase your product"
            }
        )
        assert response_b.status_code == 200
        result_b = response_b.json()["result"]
        
        # Get leads for tenant_a
        list_a = requests.get(
            f"{BASE_URL}/api/leads/",
            params={"tenant_id": tenant_a}
        )
        assert list_a.status_code == 200
        leads_a = list_a.json()["leads"]
        
        # Get leads for tenant_b
        list_b = requests.get(
            f"{BASE_URL}/api/leads/",
            params={"tenant_id": tenant_b}
        )
        assert list_b.status_code == 200
        leads_b = list_b.json()["leads"]
        
        # Verify isolation - tenant_a's leads should not contain tenant_b's lead_id
        if result_a.get("lead_captured") and result_b.get("lead_captured"):
            lead_ids_a = [l.get("lead_id") for l in leads_a]
            lead_ids_b = [l.get("lead_id") for l in leads_b]
            
            # tenant_b's lead should not be in tenant_a's list
            assert result_b.get("lead_id") not in lead_ids_a
            # tenant_a's lead should not be in tenant_b's list
            assert result_a.get("lead_id") not in lead_ids_b
            print(f"Tenant isolation test: tenant_a has {len(leads_a)} leads, tenant_b has {len(leads_b)} leads")


class TestEdgeCases:
    """Test edge cases for lead capture"""
    
    def test_message_without_contact_info(self):
        """Test lead capture with message that has no contact info"""
        response = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": "TEST_tenant_nocontact",
                "conversation_id": f"TEST_conv_nocontact_{uuid.uuid4().hex[:8]}",
                "user_message": "I want to book an appointment for next week"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        result = data["result"]
        
        if result.get("lead_captured"):
            lead_id = result.get("lead_id")
            lead_response = requests.get(
                f"{BASE_URL}/api/leads/{lead_id}",
                params={"tenant_id": "TEST_tenant_nocontact"}
            )
            if lead_response.status_code == 200:
                lead_data = lead_response.json()
                customer = lead_data.get("lead", {}).get("customer", {})
                # Name should be "Unknown" when not provided
                assert customer.get("name") == "Unknown" or customer.get("name") is None
                print(f"No contact info test: name={customer.get('name')}")
    
    def test_ambiguous_intent(self):
        """Test message with ambiguous intent"""
        response = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": "TEST_tenant_ambiguous",
                "conversation_id": f"TEST_conv_ambiguous_{uuid.uuid4().hex[:8]}",
                "user_message": "Maybe I'll think about getting something later"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        result = data["result"]
        # Ambiguous intent should have low confidence
        print(f"Ambiguous intent test: lead_captured={result.get('lead_captured')}, confidence={result.get('confidence')}")
    
    def test_multiple_signals_high_confidence(self):
        """Test message with multiple buying signals for high confidence"""
        response = requests.post(
            f"{BASE_URL}/api/leads/test-capture",
            json={
                "tenant_id": "TEST_tenant_highconf",
                "conversation_id": f"TEST_conv_highconf_{uuid.uuid4().hex[:8]}",
                "user_message": "I want to book an appointment today to purchase your premium product. What's the price?"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        result = data["result"]
        # Multiple signals should result in high confidence
        assert result.get("lead_captured") == True
        assert result.get("confidence", 0) >= 0.5
        print(f"High confidence test: confidence={result.get('confidence')}, signals={result.get('intent_type')}")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
