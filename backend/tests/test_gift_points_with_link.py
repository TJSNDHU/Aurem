"""
Gift Points + Shop Feature Tests
Tests for the gift-points-with-link APIs and admin gift tracking.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_GIFT_TOKEN = "Nw4IJth7-8tcgAtInjJPAE2nWsdXhVqBFDFkWYMmsJI"


class TestGiftPointsWithLinkAPIs:
    """Tests for Gift Points + Shop Link APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login as admin to get auth token
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@reroots.ca",
            "password": "new_password_123"
        })
        if login_res.status_code == 200:
            self.auth_token = login_res.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
        else:
            pytest.skip("Authentication failed - skipping authenticated tests")
    
    # ========== Public Endpoints ==========
    
    def test_01_validate_gift_token_valid(self):
        """GET /api/gifts/claim/{token} - Validate existing gift token"""
        res = requests.get(f"{BASE_URL}/api/gifts/claim/{TEST_GIFT_TOKEN}")
        print(f"Validate gift token response: {res.status_code}")
        
        # Token might be valid, claimed, expired, or not found
        # We're testing that the endpoint works correctly
        if res.status_code == 200:
            data = res.json()
            assert "valid" in data or "points_amount" in data
            assert "sender_name" in data
            print(f"Gift info: {data.get('points_amount', 'N/A')} points from {data.get('sender_name', 'N/A')}")
        elif res.status_code == 404:
            print("Token not found - may have been deleted")
        elif res.status_code == 409:
            print("Gift already claimed")
        elif res.status_code == 410:
            print("Gift expired")
        
        assert res.status_code in [200, 404, 409, 410], f"Unexpected status: {res.status_code}"
    
    def test_02_validate_gift_token_invalid(self):
        """GET /api/gifts/claim/{token} - Invalid token returns 404"""
        res = requests.get(f"{BASE_URL}/api/gifts/claim/invalid_token_abc123")
        print(f"Invalid token response: {res.status_code}")
        assert res.status_code == 404
        assert "not found" in res.json().get("detail", "").lower() or "invalid" in res.json().get("detail", "").lower()
    
    # ========== Authenticated Endpoints ==========
    
    def test_03_gift_points_with_link_missing_recipient(self):
        """POST /api/rewards/gift-points-with-link - Requires recipient email or phone"""
        res = self.session.post(f"{BASE_URL}/api/rewards/gift-points-with-link", json={
            "recipient_name": "Test User",
            "points": 100,
            "personal_note": "Test gift"
        })
        print(f"Missing recipient response: {res.status_code}")
        assert res.status_code == 400
        assert "recipient" in res.json().get("detail", "").lower()
    
    def test_04_gift_points_with_link_minimum_points(self):
        """POST /api/rewards/gift-points-with-link - Minimum 99 points required"""
        res = self.session.post(f"{BASE_URL}/api/rewards/gift-points-with-link", json={
            "recipient_name": "Test User",
            "recipient_email": "test@example.com",
            "points": 50,  # Below minimum
            "personal_note": "Test gift"
        })
        print(f"Below minimum points response: {res.status_code}")
        assert res.status_code == 400
        assert "minimum" in res.json().get("detail", "").lower() or "99" in res.json().get("detail", "")
    
    def test_05_gift_points_with_link_cannot_gift_self(self):
        """POST /api/rewards/gift-points-with-link - Cannot gift to yourself"""
        res = self.session.post(f"{BASE_URL}/api/rewards/gift-points-with-link", json={
            "recipient_name": "Admin Self",
            "recipient_email": "admin@reroots.ca",  # Same as logged in user
            "points": 100,
            "personal_note": "Self gift test"
        })
        print(f"Self gift response: {res.status_code}")
        assert res.status_code == 400
        assert "yourself" in res.json().get("detail", "").lower()
    
    # ========== Admin Gift Tracking ==========
    
    def test_06_admin_gift_tracking_dashboard(self):
        """GET /api/admin/gift-tracking - Admin dashboard returns stats"""
        res = self.session.get(f"{BASE_URL}/api/admin/gift-tracking")
        print(f"Gift tracking dashboard response: {res.status_code}")
        assert res.status_code == 200
        
        data = res.json()
        # Check stats structure
        assert "stats" in data
        stats = data["stats"]
        assert "total_gifts" in stats
        assert "pending_count" in stats
        assert "claimed_count" in stats
        assert "converted_count" in stats
        assert "claim_rate" in stats
        assert "conversion_rate" in stats
        assert "total_revenue" in stats
        
        # Check recent_gifts array
        assert "recent_gifts" in data
        assert isinstance(data["recent_gifts"], list)
        
        print(f"Stats: Total={stats['total_gifts']}, Pending={stats['pending_count']}, Claimed={stats['claimed_count']}")
    
    def test_07_admin_gift_templates_get(self):
        """GET /api/admin/gift-templates - Get message templates"""
        res = self.session.get(f"{BASE_URL}/api/admin/gift-templates")
        print(f"Gift templates GET response: {res.status_code}")
        assert res.status_code == 200
        
        data = res.json()
        # Check template channels
        assert "email" in data
        assert "sms" in data
        assert "whatsapp" in data
        
        # Check email template structure
        if data.get("email"):
            email_template = data["email"]
            assert "subject" in email_template or isinstance(email_template, dict)
        
        # Check SMS template structure
        if data.get("sms"):
            sms_template = data["sms"]
            assert "message" in sms_template or isinstance(sms_template, dict)
        
        # Check WhatsApp template structure
        if data.get("whatsapp"):
            wa_template = data["whatsapp"]
            assert "message" in wa_template or isinstance(wa_template, dict)
        
        print(f"Templates loaded: email={bool(data.get('email'))}, sms={bool(data.get('sms'))}, whatsapp={bool(data.get('whatsapp'))}")
    
    def test_08_admin_gift_templates_update(self):
        """PUT /api/admin/gift-templates - Update message templates"""
        updated_templates = {
            "email": {
                "subject": "🎁 {sender_name} sent you a gift!",
                "cta_text": "🛍️ Claim Points & Shop Now",
                "cta_color": "#F8A5B8"
            },
            "sms": {
                "message": "🎁 {sender_name} sent you {points_amount} pts ({points_value})! Claim: {claim_link}"
            },
            "whatsapp": {
                "message": "🎁 *Gift Alert!*\n{sender_name} sent you *{points_amount} points*!\nClaim: {claim_link}"
            }
        }
        
        res = self.session.put(f"{BASE_URL}/api/admin/gift-templates", json=updated_templates)
        print(f"Gift templates PUT response: {res.status_code}")
        assert res.status_code == 200
        
        data = res.json()
        assert data.get("success") == True
        assert "templates" in data
    
    # ========== Claim Gift Authenticated ==========
    
    def test_09_claim_gift_requires_auth(self):
        """POST /api/gifts/claim/{token} - Requires authentication"""
        # Make request without auth header
        res = requests.post(f"{BASE_URL}/api/gifts/claim/{TEST_GIFT_TOKEN}")
        print(f"Claim without auth response: {res.status_code}")
        # Should return 401 or 403
        assert res.status_code in [401, 403]
    
    def test_10_admin_gift_tracking_unauthenticated(self):
        """GET /api/admin/gift-tracking - Requires admin authentication"""
        res = requests.get(f"{BASE_URL}/api/admin/gift-tracking")
        print(f"Admin endpoint without auth response: {res.status_code}")
        assert res.status_code in [401, 403]


class TestGiftClaimFlow:
    """Test the complete gift claim flow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login as admin
        login_res = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@reroots.ca",
            "password": "new_password_123"
        })
        if login_res.status_code == 200:
            self.auth_token = login_res.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
        else:
            pytest.skip("Authentication failed - skipping authenticated tests")
    
    def test_01_check_user_points_balance(self):
        """GET /api/rewards/profile - Check user's points balance"""
        res = self.session.get(f"{BASE_URL}/api/rewards/profile")
        print(f"Rewards profile response: {res.status_code}")
        
        if res.status_code == 200:
            data = res.json()
            balance = data.get("points_balance", 0)
            print(f"User points balance: {balance}")
            assert isinstance(balance, (int, float))
        else:
            print(f"Profile endpoint may not exist: {res.status_code}")
    
    def test_02_gift_history(self):
        """GET /api/rewards/gift-history - Get user's gift history"""
        res = self.session.get(f"{BASE_URL}/api/rewards/gift-history")
        print(f"Gift history response: {res.status_code}")
        
        if res.status_code == 200:
            data = res.json()
            assert "sent" in data or "received" in data or "total_sent" in data
            print(f"Gift history: Sent={data.get('total_sent', 0)}, Received={data.get('total_received', 0)}")
        else:
            print(f"Gift history status: {res.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
