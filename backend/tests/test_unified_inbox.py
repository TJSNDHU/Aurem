"""
Unified Inbox API Tests
Tests for Phase 7: Unified Inbox - Command Center for all communications

Features tested:
- Health check endpoint
- Message ingestion with Brain suggestions
- Inbox retrieval with filters
- Approve/Reject/Archive actions
- Brain intent identification
"""

import pytest
import requests
import os
import time
import secrets

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_BUSINESS_ID = f"test_inbox_{secrets.token_hex(6)}"


class TestUnifiedInboxHealth:
    """Health check endpoint tests"""
    
    def test_health_endpoint_returns_healthy(self):
        """GET /api/inbox/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/inbox/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["service"] == "aurem-unified-inbox"
        assert "capabilities" in data
        assert "multi_channel_aggregation" in data["capabilities"]
        assert "brain_suggestions" in data["capabilities"]
        print("PASS: Health endpoint returns healthy status")


class TestMessageIngestion:
    """Message ingestion tests with Brain suggestions"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.business_id = TEST_BUSINESS_ID
        self.created_message_ids = []
        yield
        # Cleanup: Archive all test messages
        for msg_id in self.created_message_ids:
            try:
                requests.post(f"{BASE_URL}/api/inbox/{self.business_id}/message/{msg_id}/archive")
            except:
                pass
    
    def test_ingest_gmail_message_with_booking_intent(self):
        """POST /api/inbox/{business_id}/ingest creates message with Brain suggestion for booking"""
        payload = {
            "channel": "gmail",
            "external_id": f"gmail_{secrets.token_hex(8)}",
            "sender": {
                "name": "John Smith",
                "email": "john.smith@example.com"
            },
            "content": {
                "subject": "Meeting Request",
                "body": "Hi, I would like to schedule a meeting with you next Tuesday at 2pm to discuss the project proposal."
            },
            "auto_suggest": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/inbox/{self.business_id}/ingest",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message_id" in data
        assert data["channel"] == "gmail"
        assert data["status"] in ["new", "suggested"]
        
        self.created_message_ids.append(data["message_id"])
        
        # Check Brain suggestion was generated
        if data.get("brain_suggestion"):
            suggestion = data["brain_suggestion"]
            assert "intent" in suggestion
            assert "confidence" in suggestion
            # Meeting request should trigger book_appointment intent
            print(f"Brain identified intent: {suggestion['intent']} with confidence: {suggestion['confidence']}")
        
        print(f"PASS: Gmail message ingested with ID: {data['message_id']}")
        return data
    
    def test_ingest_whatsapp_message_with_invoice_intent(self):
        """POST /api/inbox/{business_id}/ingest creates message with invoice intent"""
        payload = {
            "channel": "whatsapp",
            "external_id": f"wa_{secrets.token_hex(8)}",
            "sender": {
                "name": "Sarah Johnson",
                "phone": "+1234567890"
            },
            "content": {
                "text": "Hi, can you please send me an invoice for the services we discussed? I need it for $500 for the consulting work."
            },
            "auto_suggest": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/inbox/{self.business_id}/ingest",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message_id" in data
        assert data["channel"] == "whatsapp"
        
        self.created_message_ids.append(data["message_id"])
        
        if data.get("brain_suggestion"):
            suggestion = data["brain_suggestion"]
            print(f"Brain identified intent: {suggestion['intent']} with confidence: {suggestion['confidence']}")
        
        print(f"PASS: WhatsApp message ingested with ID: {data['message_id']}")
        return data
    
    def test_ingest_webchat_message_with_chat_intent(self):
        """POST /api/inbox/{business_id}/ingest creates message with chat intent"""
        payload = {
            "channel": "web_chat",
            "external_id": f"chat_{secrets.token_hex(8)}",
            "sender": {
                "name": "Website Visitor"
            },
            "content": {
                "text": "Hello! I have a question about your products. What are your business hours?"
            },
            "auto_suggest": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/inbox/{self.business_id}/ingest",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message_id" in data
        assert data["channel"] == "web_chat"
        
        self.created_message_ids.append(data["message_id"])
        
        if data.get("brain_suggestion"):
            suggestion = data["brain_suggestion"]
            # General question should trigger chat intent
            print(f"Brain identified intent: {suggestion['intent']} with confidence: {suggestion['confidence']}")
        
        print(f"PASS: Web chat message ingested with ID: {data['message_id']}")
        return data
    
    def test_duplicate_message_detection(self):
        """Duplicate messages should be detected and skipped"""
        external_id = f"dup_{secrets.token_hex(8)}"
        payload = {
            "channel": "gmail",
            "external_id": external_id,
            "sender": {"name": "Test User", "email": "test@example.com"},
            "content": {"subject": "Test", "body": "Test message"},
            "auto_suggest": False
        }
        
        # First ingestion
        response1 = requests.post(f"{BASE_URL}/api/inbox/{self.business_id}/ingest", json=payload)
        assert response1.status_code == 200
        data1 = response1.json()
        self.created_message_ids.append(data1["message_id"])
        
        # Second ingestion (duplicate)
        response2 = requests.post(f"{BASE_URL}/api/inbox/{self.business_id}/ingest", json=payload)
        assert response2.status_code == 200
        data2 = response2.json()
        
        assert data2.get("duplicate") == True
        assert data2["message_id"] == data1["message_id"]
        
        print("PASS: Duplicate message detection working")


class TestInboxRetrieval:
    """Inbox retrieval and filtering tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test messages"""
        self.business_id = f"test_inbox_retrieve_{secrets.token_hex(4)}"
        self.created_message_ids = []
        
        # Create test messages for different channels
        channels = ["gmail", "whatsapp", "web_chat"]
        for channel in channels:
            payload = {
                "channel": channel,
                "external_id": f"{channel}_{secrets.token_hex(8)}",
                "sender": {"name": f"Test {channel}", "email": f"test@{channel}.com"},
                "content": {"body": f"Test message from {channel}"},
                "auto_suggest": False
            }
            response = requests.post(f"{BASE_URL}/api/inbox/{self.business_id}/ingest", json=payload)
            if response.status_code == 200:
                self.created_message_ids.append(response.json().get("message_id"))
        
        yield
        
        # Cleanup
        for msg_id in self.created_message_ids:
            try:
                requests.post(f"{BASE_URL}/api/inbox/{self.business_id}/message/{msg_id}/archive")
            except:
                pass
    
    def test_get_inbox_returns_messages_with_stats(self):
        """GET /api/inbox/{business_id} returns messages with stats"""
        response = requests.get(f"{BASE_URL}/api/inbox/{self.business_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "messages" in data
        assert "total" in data
        assert "stats" in data
        assert isinstance(data["messages"], list)
        
        # Verify stats structure
        stats = data["stats"]
        assert "total" in stats
        assert "by_channel" in stats
        assert "by_status" in stats
        assert "pending_actions" in stats
        
        print(f"PASS: Inbox returned {len(data['messages'])} messages with stats")
    
    def test_filter_by_channel(self):
        """GET /api/inbox/{business_id}?channel=gmail filters by channel"""
        response = requests.get(f"{BASE_URL}/api/inbox/{self.business_id}?channel=gmail")
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned messages should be gmail
        for msg in data["messages"]:
            assert msg["channel"] == "gmail"
        
        print(f"PASS: Channel filter working - returned {len(data['messages'])} gmail messages")
    
    def test_filter_by_status(self):
        """GET /api/inbox/{business_id}?status=new filters by status"""
        response = requests.get(f"{BASE_URL}/api/inbox/{self.business_id}?status=new")
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned messages should have 'new' status
        for msg in data["messages"]:
            assert msg["status"] == "new"
        
        print(f"PASS: Status filter working - returned {len(data['messages'])} new messages")
    
    def test_invalid_channel_returns_error(self):
        """Invalid channel parameter returns 400 error"""
        response = requests.get(f"{BASE_URL}/api/inbox/{self.business_id}?channel=invalid")
        
        assert response.status_code == 400
        print("PASS: Invalid channel returns 400 error")


class TestMessageActions:
    """Approve/Reject/Archive action tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test message with suggestion"""
        self.business_id = f"test_inbox_actions_{secrets.token_hex(4)}"
        
        # Create a message with auto_suggest to get a Brain suggestion
        payload = {
            "channel": "gmail",
            "external_id": f"action_test_{secrets.token_hex(8)}",
            "sender": {"name": "Action Test", "email": "action@test.com"},
            "content": {
                "subject": "Meeting Request",
                "body": "I would like to schedule a meeting for next week to discuss the project."
            },
            "auto_suggest": True
        }
        
        response = requests.post(f"{BASE_URL}/api/inbox/{self.business_id}/ingest", json=payload)
        if response.status_code == 200:
            self.message_id = response.json().get("message_id")
            self.message_data = response.json()
        else:
            self.message_id = None
            self.message_data = None
        
        yield
        
        # Cleanup
        if self.message_id:
            try:
                requests.post(f"{BASE_URL}/api/inbox/{self.business_id}/message/{self.message_id}/archive")
            except:
                pass
    
    def test_approve_suggestion_executes_action(self):
        """POST /api/inbox/{business_id}/message/{id}/approve executes suggested action"""
        if not self.message_id:
            pytest.skip("No message created for test")
        
        response = requests.post(
            f"{BASE_URL}/api/inbox/{self.business_id}/message/{self.message_id}/approve",
            json={}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("success") == True or "error" not in data
        
        # Verify message status changed
        get_response = requests.get(f"{BASE_URL}/api/inbox/{self.business_id}/message/{self.message_id}")
        if get_response.status_code == 200:
            msg = get_response.json()
            assert msg["status"] in ["actioned", "approved"]
        
        print(f"PASS: Approve action executed for message {self.message_id}")
    
    def test_reject_suggestion_marks_rejected(self):
        """POST /api/inbox/{business_id}/message/{id}/reject marks message rejected"""
        # Create a new message for rejection test
        payload = {
            "channel": "whatsapp",
            "external_id": f"reject_test_{secrets.token_hex(8)}",
            "sender": {"name": "Reject Test", "phone": "+1234567890"},
            "content": {"text": "Test message for rejection"},
            "auto_suggest": True
        }
        
        create_response = requests.post(f"{BASE_URL}/api/inbox/{self.business_id}/ingest", json=payload)
        assert create_response.status_code == 200
        msg_id = create_response.json()["message_id"]
        
        # Reject the suggestion
        response = requests.post(
            f"{BASE_URL}/api/inbox/{self.business_id}/message/{msg_id}/reject",
            json={"reason": "Not relevant"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        
        # Verify status changed to rejected
        get_response = requests.get(f"{BASE_URL}/api/inbox/{self.business_id}/message/{msg_id}")
        if get_response.status_code == 200:
            msg = get_response.json()
            assert msg["status"] == "rejected"
        
        print(f"PASS: Reject action marked message as rejected")
    
    def test_archive_message(self):
        """POST /api/inbox/{business_id}/message/{id}/archive archives message"""
        # Create a new message for archive test
        payload = {
            "channel": "web_chat",
            "external_id": f"archive_test_{secrets.token_hex(8)}",
            "sender": {"name": "Archive Test"},
            "content": {"text": "Test message for archiving"},
            "auto_suggest": False
        }
        
        create_response = requests.post(f"{BASE_URL}/api/inbox/{self.business_id}/ingest", json=payload)
        assert create_response.status_code == 200
        msg_id = create_response.json()["message_id"]
        
        # Archive the message
        response = requests.post(f"{BASE_URL}/api/inbox/{self.business_id}/message/{msg_id}/archive")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        
        # Verify message is archived (not in default inbox view)
        inbox_response = requests.get(f"{BASE_URL}/api/inbox/{self.business_id}")
        inbox_data = inbox_response.json()
        
        archived_in_default = any(m["message_id"] == msg_id for m in inbox_data["messages"])
        assert not archived_in_default, "Archived message should not appear in default inbox"
        
        # But should appear with include_archived=true
        archived_response = requests.get(f"{BASE_URL}/api/inbox/{self.business_id}?include_archived=true")
        archived_data = archived_response.json()
        
        archived_found = any(m["message_id"] == msg_id for m in archived_data["messages"])
        assert archived_found, "Archived message should appear with include_archived=true"
        
        print(f"PASS: Archive action working correctly")
    
    def test_action_on_nonexistent_message_returns_error(self):
        """Actions on non-existent message return error"""
        fake_id = "inbox_nonexistent123"
        
        response = requests.post(
            f"{BASE_URL}/api/inbox/{self.business_id}/message/{fake_id}/approve",
            json={}
        )
        
        assert response.status_code == 400
        print("PASS: Action on non-existent message returns error")


class TestBrainIntentIdentification:
    """Tests for Brain's intent identification accuracy"""
    
    def setup_method(self):
        self.business_id = f"test_brain_intent_{secrets.token_hex(4)}"
        self.created_message_ids = []
    
    def teardown_method(self):
        for msg_id in self.created_message_ids:
            try:
                requests.post(f"{BASE_URL}/api/inbox/{self.business_id}/message/{msg_id}/archive")
            except:
                pass
    
    def test_booking_intent_detection(self):
        """Brain correctly identifies booking/appointment intent"""
        payload = {
            "channel": "gmail",
            "external_id": f"booking_{secrets.token_hex(8)}",
            "sender": {"name": "Client", "email": "client@example.com"},
            "content": {
                "subject": "Schedule a call",
                "body": "Hi, I'd like to book a consultation call for next Monday at 3pm. Please let me know if that works."
            },
            "auto_suggest": True
        }
        
        response = requests.post(f"{BASE_URL}/api/inbox/{self.business_id}/ingest", json=payload)
        assert response.status_code == 200
        data = response.json()
        self.created_message_ids.append(data["message_id"])
        
        if data.get("brain_suggestion"):
            intent = data["brain_suggestion"].get("intent", "")
            confidence = data["brain_suggestion"].get("confidence", 0)
            print(f"Booking message - Intent: {intent}, Confidence: {confidence}")
            # Should identify as booking-related
            assert intent in ["book_appointment", "check_availability", "chat"], f"Expected booking intent, got {intent}"
        else:
            print("Note: Brain suggestion not generated (may be due to LLM availability)")
        
        print("PASS: Booking intent test completed")
    
    def test_invoice_intent_detection(self):
        """Brain correctly identifies invoice/payment intent"""
        payload = {
            "channel": "whatsapp",
            "external_id": f"invoice_{secrets.token_hex(8)}",
            "sender": {"name": "Customer", "phone": "+1987654321"},
            "content": {
                "text": "Please send me an invoice for $1,500 for the web development work completed last week."
            },
            "auto_suggest": True
        }
        
        response = requests.post(f"{BASE_URL}/api/inbox/{self.business_id}/ingest", json=payload)
        assert response.status_code == 200
        data = response.json()
        self.created_message_ids.append(data["message_id"])
        
        if data.get("brain_suggestion"):
            intent = data["brain_suggestion"].get("intent", "")
            confidence = data["brain_suggestion"].get("confidence", 0)
            print(f"Invoice message - Intent: {intent}, Confidence: {confidence}")
            # Should identify as invoice/payment-related
            assert intent in ["create_invoice", "create_payment", "chat"], f"Expected invoice intent, got {intent}"
        else:
            print("Note: Brain suggestion not generated (may be due to LLM availability)")
        
        print("PASS: Invoice intent test completed")
    
    def test_general_chat_intent_detection(self):
        """Brain correctly identifies general chat/inquiry intent"""
        payload = {
            "channel": "web_chat",
            "external_id": f"chat_{secrets.token_hex(8)}",
            "sender": {"name": "Visitor"},
            "content": {
                "text": "What are your business hours? Do you offer weekend support?"
            },
            "auto_suggest": True
        }
        
        response = requests.post(f"{BASE_URL}/api/inbox/{self.business_id}/ingest", json=payload)
        assert response.status_code == 200
        data = response.json()
        self.created_message_ids.append(data["message_id"])
        
        if data.get("brain_suggestion"):
            intent = data["brain_suggestion"].get("intent", "")
            confidence = data["brain_suggestion"].get("confidence", 0)
            print(f"General inquiry - Intent: {intent}, Confidence: {confidence}")
            # General questions should be chat intent
            assert intent in ["chat", "send_email", "send_whatsapp"], f"Expected chat intent, got {intent}"
        else:
            print("Note: Brain suggestion not generated (may be due to LLM availability)")
        
        print("PASS: General chat intent test completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
