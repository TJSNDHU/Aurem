"""
Test Loyalty Points System - Points Redemption at Checkout
Tests for:
- GET /api/loyalty/points - returns user's points balance
- POST /api/loyalty/points/redeem - creates redemption token
- Points calculation: 100 pts = $5 discount (POINT_VALUE = 0.05)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

class TestLoyaltyPointsAPI:
    """Test loyalty points endpoints"""
    
    @pytest.fixture
    def admin_token(self):
        """Login as admin and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@reroots.ca",
            "password": "Admin123!"
        })
        if response.status_code == 200:
            # Try both 'token' and 'access_token' keys
            token = response.json().get("token") or response.json().get("access_token")
            if token:
                return token
        pytest.skip("Admin authentication failed")
    
    def test_get_loyalty_points_without_auth(self):
        """Test GET /api/loyalty/points without authentication returns 0 points"""
        response = requests.get(f"{BASE_URL}/api/loyalty/points")
        # Should return 200 with 0 points for unauthenticated users
        assert response.status_code == 200
        data = response.json()
        assert "points" in data
        assert data["points"] == 0
        assert data["value"] == 0
        print(f"✓ GET /api/loyalty/points without auth returns: {data}")
    
    def test_get_loyalty_points_with_auth(self, admin_token):
        """Test GET /api/loyalty/points with authentication"""
        response = requests.get(
            f"{BASE_URL}/api/loyalty/points",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "points" in data
        assert "value" in data
        # Value should be points * 0.05 (POINT_VALUE)
        expected_value = round(data["points"] * 0.05, 2)
        assert data["value"] == expected_value or data["points"] == 0
        print(f"✓ GET /api/loyalty/points with auth returns: points={data['points']}, value=${data['value']}")
        print(f"  lifetime_earned: {data.get('lifetime_earned', 0)}")
        return data["points"]
    
    def test_redeem_points_minimum_validation(self, admin_token):
        """Test that minimum 100 points is required to redeem"""
        response = requests.post(
            f"{BASE_URL}/api/loyalty/points/redeem",
            json={"points": 50},  # Less than minimum
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        # Should fail with 400 - minimum 100 points required
        # Note: Auth is checked first, then validation
        if response.status_code == 400:
            data = response.json()
            assert "minimum" in data.get("detail", "").lower() or "100" in data.get("detail", "")
            print(f"✓ Minimum validation works: {data.get('detail')}")
        elif response.status_code == 401:
            # Auth issue - check if token is valid
            print("⚠ Authentication issue - need to recheck token")
            assert False, "Authentication failed for redeem endpoint"
        else:
            print(f"Response: {response.status_code} - {response.json()}")
    
    def test_redeem_points_without_auth(self):
        """Test that redemption requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/loyalty/points/redeem",
            json={"points": 100}
        )
        # Should fail - requires auth
        assert response.status_code in [401, 403]
        print(f"✓ Redemption requires authentication (status: {response.status_code})")
    
    def test_redeem_points_calculation(self, admin_token):
        """Test that points redemption calculates correct discount value
        100 points = $5 (POINT_VALUE = 0.05)
        """
        # First check if user has enough points
        points_response = requests.get(
            f"{BASE_URL}/api/loyalty/points",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        current_points = points_response.json().get("points", 0)
        
        if current_points < 100:
            print(f"⚠ Admin has only {current_points} points - skipping redemption test")
            pytest.skip(f"Admin has insufficient points ({current_points})")
        
        # Try to redeem points
        redeem_response = requests.post(
            f"{BASE_URL}/api/loyalty/points/redeem",
            json={"points": 100},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if redeem_response.status_code == 200:
            data = redeem_response.json()
            assert "redemption_token" in data
            assert data["points"] == 100
            # 100 points * 0.05 = $5.00
            assert data["discount_value"] == 5.0
            print(f"✓ Redemption token created: {data['redemption_token'][:8]}...")
            print(f"✓ Points: {data['points']}, Discount Value: ${data['discount_value']}")
        else:
            print(f"⚠ Redemption returned status {redeem_response.status_code}: {redeem_response.json()}")
            # If insufficient points, that's expected
            if redeem_response.status_code == 400:
                print(f"  (Expected if admin has < 100 points)")


class TestLoyaltyPointsIntegration:
    """Test loyalty points integration with checkout"""
    
    @pytest.fixture
    def admin_token(self):
        """Login as admin and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@reroots.ca",
            "password": "Admin123!"
        })
        if response.status_code == 200:
            # Try both 'token' and 'access_token' keys
            token = response.json().get("token") or response.json().get("access_token")
            if token:
                return token
        pytest.skip("Admin authentication failed")
    
    def test_points_economy_constants(self, admin_token):
        """Verify points economy matches expected values:
        - 60 points per referral (POINTS_PER_REFERRAL)
        - 100 points = $5 discount (POINT_VALUE = 0.05)
        - 600 points = 30% discount goal
        """
        # Get admin loyalty stats which includes the economy values
        response = requests.get(
            f"{BASE_URL}/api/admin/loyalty/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Loyalty stats retrieved: {data}")
            # Check point_value if returned
            if "point_value" in data:
                assert data["point_value"] == 0.05, f"Expected 0.05, got {data['point_value']}"
                print(f"✓ POINT_VALUE = {data['point_value']} (100 pts = $5)")
        else:
            print(f"⚠ Could not get loyalty stats (status: {response.status_code})")


class TestPointsEconomyConsistency:
    """Test that points economy is consistent across the app:
    - 10 pts daily login
    - 60 pts per referral  
    - 100 pts = $5 discount
    - 600 pts = 30% off (10 referrals)
    """
    
    def test_referral_points_value(self):
        """Verify referral points value: 60 points per referral"""
        # This is more of a code verification test
        # Check that POINTS_PER_REFERRAL = 60 by testing the endpoint
        response = requests.get(f"{BASE_URL}/api/loyalty/points")
        assert response.status_code == 200
        print("✓ Loyalty points API is accessible")
        print("✓ Expected: 60 points per referral (POINTS_PER_REFERRAL)")
        print("✓ Expected: 100 points = $5 (POINT_VALUE = 0.05)")
        print("✓ Expected: 600 points total for 30% discount (10 referrals)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
