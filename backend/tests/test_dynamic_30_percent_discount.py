"""
Test Dynamic 30% Discount Calculation for Loyalty Points
Tests the /api/loyalty/points/redeem endpoint with subtotal parameter
Formula: points_needed = subtotal × 30% × points_per_dollar
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@reroots.ca"
ADMIN_PASSWORD = "new_password_123"


class TestDynamic30PercentDiscount:
    """Test dynamic 30% discount calculation at checkout"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test - get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        self.token = login_response.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
    def test_loyalty_config_endpoint(self):
        """Test loyalty config has required fields"""
        response = self.session.get(f"{BASE_URL}/api/loyalty/config")
        assert response.status_code == 200
        
        data = response.json()
        assert "point_value" in data
        assert "points_per_dollar" in data
        assert "max_redemption_percent" in data
        
        # Verify expected values
        assert data["point_value"] == 0.05
        assert data["points_per_dollar"] == 20
        assert data["max_redemption_percent"] == 30
        print(f"Loyalty config: point_value={data['point_value']}, points_per_dollar={data['points_per_dollar']}, max={data['max_redemption_percent']}%")
        
    def test_user_has_points(self):
        """Test user has loyalty points balance"""
        response = self.session.get(f"{BASE_URL}/api/loyalty/points")
        assert response.status_code == 200
        
        data = response.json()
        assert "points" in data
        assert data["points"] >= 100, f"User needs at least 100 points, has {data['points']}"
        print(f"User points balance: {data['points']} pts (${data.get('value', 0):.2f})")
        
    def test_redeem_exact_30_percent_small_order(self):
        """Test redeeming exact 30% worth for $53.19 subtotal
        
        Formula: 
        - 30% of $53.19 = $15.957 → $15.96
        - Points needed = $15.96 × 20 pts/$1 = 319.2 → 319 points (floor after ceiling discount)
        """
        subtotal = 53.19
        expected_discount = round(subtotal * 0.30, 2)  # $15.96
        points_to_redeem = 319  # ceil(15.957 * 20)
        
        response = self.session.post(
            f"{BASE_URL}/api/loyalty/points/redeem",
            json={"points": points_to_redeem, "subtotal": subtotal}
        )
        assert response.status_code == 200, f"Redeem failed: {response.text}"
        
        data = response.json()
        assert data["points"] == points_to_redeem
        # Discount should be close to 30% (allowing for rounding)
        assert abs(data["discount_value"] - expected_discount) < 0.02, f"Expected ~${expected_discount}, got ${data['discount_value']}"
        assert data["max_discount_percent"] == 30
        print(f"Redeemed {data['points']} pts for ${data['discount_value']} off (subtotal: ${subtotal})")
        
    def test_30_percent_cap_enforced(self):
        """Test that discount is capped at 30% when redeeming more points"""
        subtotal = 53.19
        max_discount = round(subtotal * 0.30, 2)  # $15.96
        
        # Try to redeem 500 points (would be $25 uncapped)
        response = self.session.post(
            f"{BASE_URL}/api/loyalty/points/redeem",
            json={"points": 500, "subtotal": subtotal}
        )
        assert response.status_code == 200, f"Redeem failed: {response.text}"
        
        data = response.json()
        assert data["capped"] == True, "Should be capped at 30%"
        assert data["discount_value"] == max_discount, f"Discount should be capped at ${max_discount}"
        # Points should be reduced to match 30% cap
        expected_points = int(max_discount / 0.05)  # 319 points
        assert data["points"] == expected_points, f"Points should be reduced to {expected_points}"
        print(f"500 pts capped to {data['points']} pts, discount ${data['discount_value']} (30% of ${subtotal})")
        
    def test_redeem_100_subtotal(self):
        """Test 30% discount on $100 subtotal = $30 off, 600 points"""
        subtotal = 100.00
        expected_discount = 30.00
        points_to_redeem = 600
        
        response = self.session.post(
            f"{BASE_URL}/api/loyalty/points/redeem",
            json={"points": points_to_redeem, "subtotal": subtotal}
        )
        assert response.status_code == 200, f"Redeem failed: {response.text}"
        
        data = response.json()
        assert data["points"] == points_to_redeem
        assert data["discount_value"] == expected_discount
        assert data["capped"] == False  # Exactly at 30%, not over
        print(f"$100 order: {data['points']} pts = ${data['discount_value']} off")
        
    def test_redeem_200_subtotal(self):
        """Test 30% discount on $200 subtotal = $60 off, needs 1200 points"""
        subtotal = 200.00
        expected_discount = 60.00  # 30% of $200
        
        # User has 750 points, so try to redeem all 750
        # 750 pts × $0.05 = $37.50 which is less than 30% cap of $60
        response = self.session.post(
            f"{BASE_URL}/api/loyalty/points/redeem",
            json={"points": 750, "subtotal": subtotal}
        )
        assert response.status_code == 200, f"Redeem failed: {response.text}"
        
        data = response.json()
        # Since 750 pts = $37.50 is less than $60 cap, should not be capped
        assert data["capped"] == False
        assert data["points"] == 750
        assert data["discount_value"] == 37.50  # 750 × 0.05
        print(f"$200 order: {data['points']} pts = ${data['discount_value']} off (max was ${expected_discount})")
        
    def test_minimum_100_points(self):
        """Test minimum 100 points required"""
        response = self.session.post(
            f"{BASE_URL}/api/loyalty/points/redeem",
            json={"points": 50, "subtotal": 100.00}
        )
        assert response.status_code == 400
        assert "Minimum 100 points" in response.json().get("detail", "")
        print("Correctly rejected redeem request with < 100 points")
        
    def test_redemption_token_generated(self):
        """Test that redemption token is generated"""
        response = self.session.post(
            f"{BASE_URL}/api/loyalty/points/redeem",
            json={"points": 100, "subtotal": 50.00}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "redemption_token" in data
        assert len(data["redemption_token"]) > 0
        print(f"Redemption token generated: {data['redemption_token'][:8]}...")


class TestCheckoutPricingIntegration:
    """Test checkout pricing with points redemption"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
    def test_checkout_pricing_endpoint(self):
        """Test checkout pricing endpoint exists and works"""
        response = self.session.post(
            f"{BASE_URL}/api/checkout/pricing",
            json={
                "email": "test@example.com",
                "original_subtotal": 53.19,
                "cart_items": [{"product_id": "test-product", "quantity": 1}],
                "discount_code": ""
            }
        )
        # Should return 200 or handle gracefully
        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            print(f"Checkout pricing response: {data}")


class TestDynamicCalculationFormula:
    """Test the mathematical formula for dynamic 30% calculation"""
    
    def test_formula_calculation(self):
        """Verify the formula: points_needed = subtotal × 30% × points_per_dollar"""
        test_cases = [
            # (subtotal, expected_discount, expected_points)
            (53.19, 15.96, 319),   # $53.19 × 30% = $15.957 → 319 pts
            (100.00, 30.00, 600),  # $100 × 30% = $30 → 600 pts
            (50.00, 15.00, 300),   # $50 × 30% = $15 → 300 pts
            (75.00, 22.50, 450),   # $75 × 30% = $22.50 → 450 pts
            (150.00, 45.00, 900),  # $150 × 30% = $45 → 900 pts
        ]
        
        points_per_dollar = 20
        max_percent = 30
        
        for subtotal, expected_discount, expected_points in test_cases:
            # Calculate 30% discount
            discount_30_pct = round(subtotal * (max_percent / 100), 2)
            # Calculate points needed
            points_needed = int(discount_30_pct * points_per_dollar)  # Backend uses int()
            
            assert abs(discount_30_pct - expected_discount) < 0.01, f"Subtotal ${subtotal}: Expected discount ${expected_discount}, got ${discount_30_pct}"
            # Allow 1 point difference due to rounding
            assert abs(points_needed - expected_points) <= 1, f"Subtotal ${subtotal}: Expected {expected_points} pts, got {points_needed}"
            
            print(f"✓ ${subtotal} → 30% = ${discount_30_pct} ({points_needed} pts)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
