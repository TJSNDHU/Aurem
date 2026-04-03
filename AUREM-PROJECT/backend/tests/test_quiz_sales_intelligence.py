"""
Test Suite: Quiz API + Sales Intelligence Dashboard + Email Templates
Tests the new conversion-optimized quiz flow, Sales Intelligence dashboard, and email templates module
"""
import pytest
import requests
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestQuizSubmitAPI:
    """Quiz API endpoint POST /api/quiz/submit tests"""
    
    def test_quiz_submit_basic(self):
        """Test basic quiz submission with required fields"""
        payload = {
            "email": "TEST_quiz_user@example.com",
            "name": "Test Quiz User",
            "answers": {
                "q1": "aging",
                "q2": "dry",
                "q3": "forehead",
                "q4": "mostly",
                "q5": "sun",
                "q6": "30s"
            },
            "score": {"PDRN": 14, "TXA": 10, "ARG": 12},
            "recommended_product": "AURA-GEN PDRN+TXA+ARGIRELINE 17%",
            "concerns": ["fine lines & aging", "dehydration", "sun damage"],
            "protocol": "28-Day Science Protocol",
            "source": "website_quiz"
        }
        
        response = requests.post(f"{BASE_URL}/api/quiz/submit", json=payload)
        print(f"Quiz submit status: {response.status_code}")
        print(f"Quiz submit response: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True, "Expected success=True"
        assert "message" in data, "Expected message in response"
    
    def test_quiz_submit_without_email_fails(self):
        """Test quiz submission fails without email"""
        payload = {
            "name": "Test User",
            "answers": {"q1": "aging"}
        }
        
        response = requests.post(f"{BASE_URL}/api/quiz/submit", json=payload)
        print(f"Quiz submit without email status: {response.status_code}")
        
        assert response.status_code == 400, f"Expected 400 for missing email, got {response.status_code}"
    
    def test_quiz_submit_with_full_data(self):
        """Test quiz submission with complete conversion-optimized quiz data"""
        payload = {
            "email": "TEST_full_quiz@example.com",
            "name": "Full Quiz Test",
            "answers": {
                "q1": "pigmentation",
                "q2": "combo",
                "q3": "cheeks",
                "q4": "strict",
                "q5": "stress",
                "q6": "40s"
            },
            "score": {"PDRN": 15, "TXA": 13, "ARG": 14},
            "recommended_product": "AURA-GEN PDRN+TXA+ARGIRELINE 17%",
            "concerns": ["dark spots", "stress-related skin changes"],
            "protocol": "28-Day Regeneration Protocol",
            "source": "website_quiz"
        }
        
        response = requests.post(f"{BASE_URL}/api/quiz/submit", json=payload)
        print(f"Full quiz submit status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True


class TestQuizSubmissions:
    """Test quiz submissions retrieval"""
    
    def test_get_quiz_submissions(self):
        """Test retrieving quiz submissions"""
        response = requests.get(f"{BASE_URL}/api/quiz/submissions")
        print(f"Quiz submissions status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "submissions" in data, "Expected submissions in response"
        assert "total" in data, "Expected total count"
        print(f"Total quiz submissions: {data.get('total', 0)}")


class TestAdminQuizSubmissions:
    """Test admin quiz submissions endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@admin.com",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            return login_response.json().get("token")
        pytest.skip("Admin login failed")
    
    def test_admin_quiz_submissions(self, auth_token):
        """Test admin can view quiz submissions"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/quiz-submissions", headers=headers)
        print(f"Admin quiz submissions status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"


class TestSalesIntelligenceAPIs:
    """Test Sales Intelligence dashboard API endpoints"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "test@admin.com",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            return login_response.json().get("token")
        pytest.skip("Admin login failed")
    
    def test_abandoned_stats(self, auth_token):
        """Test abandoned carts stats endpoint used by Sales Intelligence"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/abandoned/stats", headers=headers)
        print(f"Abandoned stats status: {response.status_code}")
        print(f"Abandoned stats response: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "totalAbandoned" in data, "Expected totalAbandoned in response"
    
    def test_admin_subscribers(self, auth_token):
        """Test admin subscribers endpoint used by Sales Intelligence"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/subscribers", headers=headers)
        print(f"Admin subscribers status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_crm_customers(self, auth_token):
        """Test CRM customers endpoint used by Sales Intelligence"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/business/crm/customers", headers=headers)
        print(f"CRM customers status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_ad_campaigns(self, auth_token):
        """Test ad campaigns endpoint used by Sales Intelligence"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/ad-campaigns", headers=headers)
        print(f"Ad campaigns status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"


class TestEmailTemplatesModule:
    """Test email templates module is importable and functional"""
    
    def test_email_templates_importable(self):
        """Test that email templates module can be imported"""
        try:
            from routes.reroots_email_templates import (
                order_confirmation,
                shipping_notification,
                quiz_protocol_email,
                abandoned_cart_step1,
                abandoned_cart_step2,
                abandoned_cart_step3,
                cycle_day7_checkin,
                cycle_day14_progress,
                review_request_d21,
                cycle_day25_nudge,
                welcome_subscriber,
                waitlist_restock,
                partner_welcome
            )
            print("All 13 email templates imported successfully")
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import email templates: {e}")
    
    def test_quiz_protocol_email_generation(self):
        """Test quiz protocol email template generates correctly"""
        from routes.reroots_email_templates import quiz_protocol_email
        
        result = quiz_protocol_email(
            name="Test User",
            concerns=["aging", "dark spots"],
            recommended_product="AURA-GEN PDRN+TXA+ARGIRELINE 17%"
        )
        
        assert "subject" in result, "Expected subject in result"
        assert "html" in result, "Expected html in result"
        assert "Test" in result["subject"], "Expected name in subject"
        assert "AURA-GEN" in result["html"], "Expected product in HTML"
        print(f"Quiz email subject: {result['subject']}")
    
    def test_order_confirmation_email(self):
        """Test order confirmation email template"""
        from routes.reroots_email_templates import order_confirmation
        
        mock_order = {
            "_id": "test123456",
            "customerName": "John Doe",
            "total": 99.00,
            "items": [{"name": "AURA-GEN Serum", "quantity": 1, "price": 99.00}]
        }
        
        result = order_confirmation(mock_order)
        
        assert "subject" in result, "Expected subject"
        assert "html" in result, "Expected html"
        assert "test1234" in result["subject"], "Expected order ID in subject"
        print(f"Order confirmation subject: {result['subject']}")


class TestP0FixesFunctions:
    """Test P0 fix functions are importable"""
    
    def test_p0_fixes_importable(self):
        """Test P0 fixes module can be imported"""
        try:
            from routes.reroots_p0_fixes import (
                apply_auto_discount,
                track_partner_referral,
                sendgrid_send_email,
                post_quiz_crm_and_email,
                get_loyalty_users_fixed
            )
            print("P0 fix functions imported successfully")
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import P0 fixes: {e}")
    
    def test_apply_auto_discount_founder(self):
        """Test founder discount applies correctly"""
        from routes.reroots_p0_fixes import apply_auto_discount
        
        # Test founder tag gets 50% discount
        result = apply_auto_discount(["founder", "vip"])
        assert result["pct"] == 0.50, "Expected 50% for founders"
        assert result["type"] == "founder"
        print(f"Founder discount: {result}")
    
    def test_apply_auto_discount_regular(self):
        """Test regular customer gets no auto discount"""
        from routes.reroots_p0_fixes import apply_auto_discount
        
        # Test regular customer gets 0% auto discount
        result = apply_auto_discount([])
        assert result["pct"] == 0.0, "Expected 0% for regular customers"
        assert result["type"] == "none"
        print(f"Regular customer discount: {result}")


class TestCleanup:
    """Clean up test data"""
    
    def test_cleanup_test_quiz_submissions(self):
        """Clean up test quiz submissions"""
        # Note: This would need admin access to delete, just logging for now
        print("Test data cleanup: TEST_ prefixed quiz submissions should be cleaned")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
