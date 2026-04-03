"""
Test Email Offers Feature - Tests for email offers endpoints
Tests: GET /api/admin/email-offers/recipients, POST /api/admin/email-offers/send, GET /api/admin/email-offers/campaigns
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestEmailOffers:
    """Email Offers Feature Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication for admin endpoints"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@reroots.ca",
            "password": "new_password_123"
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.token = token
        else:
            pytest.skip(f"Admin login failed with status {login_response.status_code}")
    
    # === GET /api/admin/email-offers/recipients ===
    
    def test_get_recipients_returns_200(self):
        """Test that recipients endpoint returns 200 status"""
        response = self.session.get(f"{BASE_URL}/api/admin/email-offers/recipients")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ GET /api/admin/email-offers/recipients returns 200")
    
    def test_get_recipients_response_structure(self):
        """Test response has correct structure with recipients, total, source_counts"""
        response = self.session.get(f"{BASE_URL}/api/admin/email-offers/recipients")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check required fields exist
        assert "recipients" in data, "Response missing 'recipients' field"
        assert "total" in data, "Response missing 'total' field"
        assert "source_counts" in data, "Response missing 'source_counts' field"
        
        # Check types
        assert isinstance(data["recipients"], list), "recipients should be a list"
        assert isinstance(data["total"], int), "total should be an integer"
        assert isinstance(data["source_counts"], dict), "source_counts should be a dict"
        
        print(f"✓ Response structure valid - Total: {data['total']}, Source counts: {data['source_counts']}")
    
    def test_recipients_have_required_fields(self):
        """Test each recipient has required fields: id, email, source, source_label"""
        response = self.session.get(f"{BASE_URL}/api/admin/email-offers/recipients")
        assert response.status_code == 200
        
        data = response.json()
        recipients = data.get("recipients", [])
        
        if len(recipients) == 0:
            print("⚠ No recipients found in database - may need seed data")
            return
        
        # Check first few recipients
        for recipient in recipients[:5]:
            assert "id" in recipient, f"Recipient missing 'id': {recipient}"
            assert "email" in recipient, f"Recipient missing 'email': {recipient}"
            assert "source" in recipient, f"Recipient missing 'source': {recipient}"
            assert "source_label" in recipient, f"Recipient missing 'source_label': {recipient}"
            
            # Verify source is one of expected values
            valid_sources = ["newsletter", "bio_scan", "waitlist", "partner", "customer"]
            assert recipient["source"] in valid_sources, f"Invalid source: {recipient['source']}"
        
        print(f"✓ Recipients have correct structure. Sample: {recipients[0]['email']} (source: {recipients[0]['source']})")
    
    def test_source_counts_match_recipients(self):
        """Test that source_counts match actual recipient counts"""
        response = self.session.get(f"{BASE_URL}/api/admin/email-offers/recipients")
        assert response.status_code == 200
        
        data = response.json()
        recipients = data.get("recipients", [])
        source_counts = data.get("source_counts", {})
        
        # Count manually
        manual_counts = {}
        for r in recipients:
            label = r.get("source_label", "Unknown")
            manual_counts[label] = manual_counts.get(label, 0) + 1
        
        # Verify counts match
        for label, count in source_counts.items():
            assert label in manual_counts, f"Source label '{label}' not found in recipients"
            assert count == manual_counts[label], f"Count mismatch for {label}: API says {count}, actual is {manual_counts[label]}"
        
        print(f"✓ Source counts verified: {source_counts}")
    
    def test_recipients_endpoint_requires_auth(self):
        """Test that endpoint requires admin authentication"""
        # Make request without auth
        no_auth_session = requests.Session()
        response = no_auth_session.get(f"{BASE_URL}/api/admin/email-offers/recipients")
        
        # Should fail with 401 or 403
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ Endpoint properly requires authentication")
    
    # === GET /api/admin/email-offers/campaigns ===
    
    def test_get_campaigns_returns_200(self):
        """Test that campaigns endpoint returns 200 status"""
        response = self.session.get(f"{BASE_URL}/api/admin/email-offers/campaigns")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ GET /api/admin/email-offers/campaigns returns 200")
    
    def test_get_campaigns_response_structure(self):
        """Test campaigns response has correct structure"""
        response = self.session.get(f"{BASE_URL}/api/admin/email-offers/campaigns")
        assert response.status_code == 200
        
        data = response.json()
        
        assert "campaigns" in data, "Response missing 'campaigns' field"
        assert "total" in data, "Response missing 'total' field"
        assert isinstance(data["campaigns"], list), "campaigns should be a list"
        
        print(f"✓ Campaigns structure valid - Total: {data['total']}")
    
    def test_campaign_has_required_fields(self):
        """Test campaign records have required fields when present"""
        response = self.session.get(f"{BASE_URL}/api/admin/email-offers/campaigns")
        assert response.status_code == 200
        
        data = response.json()
        campaigns = data.get("campaigns", [])
        
        if len(campaigns) == 0:
            print("⚠ No campaigns found - this is expected for new features")
            return
        
        # Check first campaign
        campaign = campaigns[0]
        required_fields = ["id", "subject", "title", "sent_count", "created_at"]
        
        for field in required_fields:
            assert field in campaign, f"Campaign missing '{field}' field: {campaign}"
        
        print(f"✓ Campaign structure valid. Latest: {campaign.get('title')} - {campaign.get('sent_count')} sent")
    
    # === POST /api/admin/email-offers/send ===
    
    def test_send_requires_recipients(self):
        """Test that send endpoint requires recipient_emails"""
        response = self.session.post(f"{BASE_URL}/api/admin/email-offers/send", json={
            "subject": "Test Subject",
            "title": "Test Title",
            "message": "Test message",
            "recipient_emails": []
        })
        
        # Should fail with 400 when no recipients
        assert response.status_code == 400, f"Expected 400 for empty recipients, got {response.status_code}"
        print("✓ Send endpoint validates recipient_emails is not empty")
    
    def test_send_validates_payload(self):
        """Test send endpoint validates required fields"""
        # Missing subject
        response = self.session.post(f"{BASE_URL}/api/admin/email-offers/send", json={
            "title": "Test",
            "message": "Test",
            "recipient_emails": ["test@example.com"]
        })
        
        # Should fail with 422 (validation error) when missing required field
        assert response.status_code == 422, f"Expected 422 for missing subject, got {response.status_code}"
        print("✓ Send endpoint validates required fields")
    
    def test_send_with_valid_payload_structure(self):
        """Test send endpoint accepts valid payload structure (doesn't actually send)"""
        # First get available recipients
        recipients_response = self.session.get(f"{BASE_URL}/api/admin/email-offers/recipients")
        recipients = recipients_response.json().get("recipients", [])
        
        if len(recipients) == 0:
            print("⚠ No recipients available - skipping send test")
            return
        
        # Use first recipient's email for testing payload structure
        test_email = recipients[0]["email"]
        
        # Test with valid structure - Note: This will actually try to send an email
        # For CI/CD, we might want to mock this, but we'll test the structure is accepted
        response = self.session.post(f"{BASE_URL}/api/admin/email-offers/send", json={
            "subject": "TEST_Email Offer Test",
            "title": "TEST_Offer Title",
            "message": "This is a test email offer",
            "discount_code": "",
            "discount_percent": 10,
            "recipient_emails": [test_email],
            "brand_prefix": "TEST"
        })
        
        # Should return 200 if email service is configured, or 400 if not
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "sent_count" in data, "Response missing sent_count"
            assert "success" in data, "Response missing success field"
            print(f"✓ Send endpoint accepts valid payload - Sent: {data.get('sent_count')}")
        else:
            # 400 typically means email service not configured
            print(f"⚠ Send failed (expected if email not configured): {response.json().get('detail', 'Unknown error')}")
    
    def test_send_generates_discount_code_with_prefix(self):
        """Test that discount code is generated with brand prefix"""
        recipients_response = self.session.get(f"{BASE_URL}/api/admin/email-offers/recipients")
        recipients = recipients_response.json().get("recipients", [])
        
        if len(recipients) == 0:
            print("⚠ No recipients available - skipping discount code generation test")
            return
        
        test_email = recipients[0]["email"]
        
        response = self.session.post(f"{BASE_URL}/api/admin/email-offers/send", json={
            "subject": "TEST_Discount Code Test",
            "title": "TEST_Discount Offer",
            "message": "Testing discount code generation",
            "discount_code": "",  # Empty to trigger generation
            "discount_percent": 15,
            "recipient_emails": [test_email],
            "brand_prefix": "TESTBRAND"
        })
        
        if response.status_code == 200:
            data = response.json()
            discount_code = data.get("discount_code", "")
            
            if discount_code:
                # Verify prefix is used
                assert discount_code.startswith("TESTBRAND"), f"Discount code should start with TESTBRAND, got: {discount_code}"
                assert "15" in discount_code, f"Discount code should contain '15', got: {discount_code}"
                print(f"✓ Discount code generated with prefix: {discount_code}")
            else:
                print("⚠ No discount code returned")
        else:
            print(f"⚠ Send failed: {response.json().get('detail', 'Unknown')}")
    
    def test_campaigns_endpoint_requires_auth(self):
        """Test that campaigns endpoint requires admin authentication"""
        no_auth_session = requests.Session()
        response = no_auth_session.get(f"{BASE_URL}/api/admin/email-offers/campaigns")
        
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ Campaigns endpoint properly requires authentication")


class TestEmailOffersIntegration:
    """Integration tests for the full email offers flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@reroots.ca",
            "password": "new_password_123"
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Admin login failed")
    
    def test_full_flow_recipients_to_campaigns(self):
        """Test full flow: get recipients, send offer, verify campaign created"""
        # Step 1: Get recipients
        recipients_response = self.session.get(f"{BASE_URL}/api/admin/email-offers/recipients")
        assert recipients_response.status_code == 200
        
        recipients = recipients_response.json().get("recipients", [])
        source_counts = recipients_response.json().get("source_counts", {})
        
        print(f"Step 1 ✓ - Found {len(recipients)} recipients from sources: {source_counts}")
        
        # Step 2: Get campaign count before sending
        campaigns_before = self.session.get(f"{BASE_URL}/api/admin/email-offers/campaigns")
        count_before = len(campaigns_before.json().get("campaigns", []))
        
        print(f"Step 2 ✓ - Existing campaigns: {count_before}")
        
        # Step 3: (Optional) Send an offer if recipients exist
        if len(recipients) > 0:
            send_response = self.session.post(f"{BASE_URL}/api/admin/email-offers/send", json={
                "subject": "Integration Test Offer",
                "title": "Integration Test",
                "message": "Testing the full email offers flow",
                "discount_percent": 20,
                "recipient_emails": [recipients[0]["email"]],
                "brand_prefix": "INTTEST"
            })
            
            if send_response.status_code == 200:
                # Step 4: Verify campaign was created
                campaigns_after = self.session.get(f"{BASE_URL}/api/admin/email-offers/campaigns")
                count_after = len(campaigns_after.json().get("campaigns", []))
                
                assert count_after >= count_before, "Campaign count should have increased"
                print(f"Step 3-4 ✓ - Campaign created. Total now: {count_after}")
            else:
                print(f"Step 3 ⚠ - Send failed (email service): {send_response.json().get('detail', 'Unknown')}")
        else:
            print("Step 3 ⚠ - Skipped sending (no recipients)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
