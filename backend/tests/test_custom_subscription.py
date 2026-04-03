"""
Custom Subscription API Tests
Tests for A-la-carte / Build-Your-Own subscription plans
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCustomSubscriptionAvailableServices:
    """Tests for GET /api/subscriptions/custom/available-services"""
    
    def test_get_available_services_success(self):
        """Test fetching available services returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/custom/available-services")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "services" in data
        assert "base_platform_fee" in data
        assert "annual_discount" in data
        
        # Verify base fee is $49
        assert data["base_platform_fee"] == 49.0
        
        # Verify annual discount is 20%
        assert data["annual_discount"] == 20.0
        
        # Verify services list is not empty
        assert len(data["services"]) > 0
        
        # Verify each service has required fields
        for service in data["services"]:
            assert "service_id" in service
            assert "name" in service
            assert "custom_price_monthly" in service
            assert "available_for_custom" in service
        
        print(f"✅ Available services: {len(data['services'])} services returned")
    
    def test_services_have_custom_pricing(self):
        """Test that services have custom pricing information"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/custom/available-services")
        
        assert response.status_code == 200
        data = response.json()
        
        # Filter services available for custom subscription
        custom_services = [s for s in data["services"] if s["available_for_custom"]]
        
        # Verify we have custom services
        assert len(custom_services) > 0
        
        # Verify pricing is set for custom services
        for service in custom_services:
            assert service["custom_price_monthly"] >= 0
        
        print(f"✅ Custom services available: {len(custom_services)}")


class TestCustomSubscriptionCalculatePricing:
    """Tests for POST /api/subscriptions/custom/calculate-pricing"""
    
    def test_calculate_pricing_single_service(self):
        """Test pricing calculation with single service"""
        response = requests.post(
            f"{BASE_URL}/api/subscriptions/custom/calculate-pricing",
            json={
                "selected_services": ["gpt-4o"],
                "billing_cycle": "monthly"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "base_fee" in data
        assert "service_fees" in data
        assert "total_monthly" in data
        assert "total_annual" in data
        assert "annual_savings" in data
        assert "selected_services" in data
        
        # Verify base fee
        assert data["base_fee"] == 49.0
        
        # Verify service fee for gpt-4o ($20)
        assert "gpt-4o" in data["service_fees"]
        assert data["service_fees"]["gpt-4o"] == 20.0
        
        # Verify total monthly = base + service
        assert data["total_monthly"] == 69.0  # $49 + $20
        
        print(f"✅ Single service pricing: ${data['total_monthly']}/month")
    
    def test_calculate_pricing_multiple_services(self):
        """Test pricing calculation with multiple services"""
        response = requests.post(
            f"{BASE_URL}/api/subscriptions/custom/calculate-pricing",
            json={
                "selected_services": ["gpt-4o", "voxtral-tts", "claude-sonnet-4"],
                "billing_cycle": "monthly"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all services are in fees
        assert "gpt-4o" in data["service_fees"]
        assert "voxtral-tts" in data["service_fees"]
        assert "claude-sonnet-4" in data["service_fees"]
        
        # Verify total = base + all services
        # $49 + $20 (gpt-4o) + $20 (voxtral-tts) + $25 (claude-sonnet-4) = $114
        expected_total = 49.0 + 20.0 + 20.0 + 25.0
        assert data["total_monthly"] == expected_total
        
        print(f"✅ Multiple services pricing: ${data['total_monthly']}/month")
    
    def test_calculate_pricing_empty_services(self):
        """Test pricing calculation with no services selected"""
        response = requests.post(
            f"{BASE_URL}/api/subscriptions/custom/calculate-pricing",
            json={
                "selected_services": [],
                "billing_cycle": "monthly"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only have base fee
        assert data["base_fee"] == 49.0
        assert data["total_monthly"] == 49.0
        assert len(data["service_fees"]) == 0
        
        print(f"✅ Empty services pricing: ${data['total_monthly']}/month (base only)")
    
    def test_calculate_pricing_annual_discount(self):
        """Test annual billing cycle applies 20% discount"""
        response = requests.post(
            f"{BASE_URL}/api/subscriptions/custom/calculate-pricing",
            json={
                "selected_services": ["gpt-4o"],
                "billing_cycle": "annual"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Monthly total = $69
        assert data["total_monthly"] == 69.0
        
        # Annual = monthly * 12 * 0.8 (20% discount)
        expected_annual = 69.0 * 12 * 0.8
        assert abs(data["total_annual"] - expected_annual) < 0.01
        
        # Savings = monthly * 12 * 0.2
        expected_savings = 69.0 * 12 * 0.2
        assert abs(data["annual_savings"] - expected_savings) < 0.01
        
        print(f"✅ Annual pricing: ${data['total_annual']:.2f}/year (saves ${data['annual_savings']:.2f})")
    
    def test_calculate_pricing_invalid_service(self):
        """Test pricing with invalid service ID (should be ignored)"""
        response = requests.post(
            f"{BASE_URL}/api/subscriptions/custom/calculate-pricing",
            json={
                "selected_services": ["gpt-4o", "invalid_service_xyz"],
                "billing_cycle": "monthly"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Invalid service should be ignored, only gpt-4o counted
        assert "gpt-4o" in data["service_fees"]
        assert "invalid_service_xyz" not in data["service_fees"]
        
        # Total should only include valid service
        assert data["total_monthly"] == 69.0  # $49 + $20
        
        print(f"✅ Invalid service ignored correctly")
    
    def test_calculate_pricing_free_service(self):
        """Test pricing with free service (stripe-payments)"""
        response = requests.post(
            f"{BASE_URL}/api/subscriptions/custom/calculate-pricing",
            json={
                "selected_services": ["stripe-payments"],
                "billing_cycle": "monthly"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Stripe is free ($0)
        assert data["service_fees"]["stripe-payments"] == 0.0
        
        # Total should only be base fee
        assert data["total_monthly"] == 49.0
        
        print(f"✅ Free service (stripe-payments) pricing correct")


class TestCustomSubscriptionCreate:
    """Tests for POST /api/subscriptions/custom/create"""
    
    def test_create_subscription_success(self):
        """Test creating a custom subscription"""
        test_user_id = "TEST_create_sub_user"
        
        response = requests.post(
            f"{BASE_URL}/api/subscriptions/custom/create",
            json={
                "user_id": test_user_id,
                "selected_services": ["gpt-4o", "openai-tts"],
                "billing_cycle": "monthly"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["success"] == True
        assert "plan_id" in data
        assert data["plan_id"].startswith("custom_")
        assert "pricing" in data
        assert data["status"] == "pending_payment"
        assert "checkout_url" in data
        
        # Verify pricing is included
        assert data["pricing"]["total_monthly"] == 84.0  # $49 + $20 + $15
        
        print(f"✅ Subscription created: {data['plan_id']}")
        
        # Cleanup - verify we can fetch it
        get_response = requests.get(f"{BASE_URL}/api/subscriptions/custom/user/{test_user_id}")
        assert get_response.status_code == 200
        
        return data["plan_id"]
    
    def test_create_subscription_annual(self):
        """Test creating annual subscription"""
        test_user_id = "TEST_annual_sub_user"
        
        response = requests.post(
            f"{BASE_URL}/api/subscriptions/custom/create",
            json={
                "user_id": test_user_id,
                "selected_services": ["gpt-4o"],
                "billing_cycle": "annual"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        
        # Verify annual pricing
        assert data["pricing"]["total_annual"] == 69.0 * 12 * 0.8
        
        print(f"✅ Annual subscription created: {data['plan_id']}")
    
    def test_create_subscription_invalid_service(self):
        """Test creating subscription with invalid service returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/subscriptions/custom/create",
            json={
                "user_id": "TEST_invalid_service_user",
                "selected_services": ["nonexistent_service_xyz"],
                "billing_cycle": "monthly"
            }
        )
        
        # Should return 404 for invalid service
        assert response.status_code == 404
        
        print(f"✅ Invalid service correctly rejected with 404")


class TestCustomSubscriptionGetUser:
    """Tests for GET /api/subscriptions/custom/user/{user_id}"""
    
    def test_get_user_subscription_success(self):
        """Test fetching user's subscription"""
        test_user_id = "TEST_get_user_sub"
        
        # First create a subscription
        create_response = requests.post(
            f"{BASE_URL}/api/subscriptions/custom/create",
            json={
                "user_id": test_user_id,
                "selected_services": ["gpt-4o"],
                "billing_cycle": "monthly"
            }
        )
        assert create_response.status_code == 200
        created_plan_id = create_response.json()["plan_id"]
        
        # Now fetch it
        response = requests.get(f"{BASE_URL}/api/subscriptions/custom/user/{test_user_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify subscription data
        assert data["user_id"] == test_user_id
        assert data["plan_id"] == created_plan_id
        assert data["plan_type"] == "custom"
        assert "gpt-4o" in data["selected_services"]
        assert data["status"] in ["active", "pending_payment"]
        
        print(f"✅ User subscription fetched: {data['plan_id']}")
    
    def test_get_user_subscription_not_found(self):
        """Test fetching non-existent user subscription returns 404"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/custom/user/nonexistent_user_xyz_123")
        
        assert response.status_code == 404
        
        print(f"✅ Non-existent user correctly returns 404")


class TestCustomSubscriptionCancel:
    """Tests for DELETE /api/subscriptions/custom/{plan_id}"""
    
    def test_cancel_subscription_success(self):
        """Test cancelling a subscription"""
        test_user_id = "TEST_cancel_sub_user"
        
        # First create a subscription
        create_response = requests.post(
            f"{BASE_URL}/api/subscriptions/custom/create",
            json={
                "user_id": test_user_id,
                "selected_services": ["gpt-4o"],
                "billing_cycle": "monthly"
            }
        )
        assert create_response.status_code == 200
        plan_id = create_response.json()["plan_id"]
        
        # Cancel it
        response = requests.delete(f"{BASE_URL}/api/subscriptions/custom/{plan_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert "cancelled" in data["message"].lower()
        
        print(f"✅ Subscription cancelled: {plan_id}")
    
    def test_cancel_nonexistent_subscription(self):
        """Test cancelling non-existent subscription returns 404"""
        response = requests.delete(f"{BASE_URL}/api/subscriptions/custom/nonexistent_plan_xyz")
        
        assert response.status_code == 404
        
        print(f"✅ Non-existent plan correctly returns 404")


class TestCustomSubscriptionEdgeCases:
    """Edge case tests for custom subscription system"""
    
    def test_all_services_selection(self):
        """Test selecting all available services"""
        # Get all available services first
        services_response = requests.get(f"{BASE_URL}/api/subscriptions/custom/available-services")
        services_data = services_response.json()
        
        all_service_ids = [s["service_id"] for s in services_data["services"] if s["available_for_custom"]]
        
        # Calculate pricing for all services
        response = requests.post(
            f"{BASE_URL}/api/subscriptions/custom/calculate-pricing",
            json={
                "selected_services": all_service_ids,
                "billing_cycle": "monthly"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all services are included
        assert len(data["service_fees"]) == len(all_service_ids)
        
        print(f"✅ All {len(all_service_ids)} services pricing calculated: ${data['total_monthly']}/month")
    
    def test_duplicate_services_in_request(self):
        """Test handling duplicate services in request"""
        response = requests.post(
            f"{BASE_URL}/api/subscriptions/custom/calculate-pricing",
            json={
                "selected_services": ["gpt-4o", "gpt-4o", "gpt-4o"],
                "billing_cycle": "monthly"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only count once
        assert data["service_fees"]["gpt-4o"] == 20.0
        
        print(f"✅ Duplicate services handled correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
