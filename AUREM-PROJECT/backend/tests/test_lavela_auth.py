"""
LA VELA BIANCA Authentication API Tests
Tests for signup and login endpoints at /api/lavela/auth/
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://live-support-test.preview.emergentagent.com"
).rstrip("/")


class TestLaVelaAuthSignup:
    """Test LA VELA signup endpoint"""

    def test_signup_success(self):
        """Test successful customer signup"""
        unique_email = f"test_signup_{int(time.time())}@lavela.com"

        response = requests.post(
            f"{BASE_URL}/api/lavela/auth/signup",
            json={
                "name": "Test Customer",
                "email": unique_email,
                "phone": "+11234567890",
                "password": "secure123",
            },
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert "token" in data, "Response should contain token"
        assert "user" in data, "Response should contain user"
        assert "message" in data, "Response should contain welcome message"

        # Verify user data
        user = data["user"]
        assert user["name"] == "Test Customer"
        assert user["email"] == unique_email.lower()
        assert user["phone"] == "+11234567890"
        assert user["points"] == 100  # Welcome bonus
        assert user["tier"] == "Bronze"
        assert "referral_code" in user
        assert user["referral_code"].startswith("LV")

    def test_signup_duplicate_email(self):
        """Test signup with already registered email"""
        unique_email = f"test_dup_{int(time.time())}@lavela.com"

        # First signup
        response1 = requests.post(
            f"{BASE_URL}/api/lavela/auth/signup",
            json={
                "name": "First Customer",
                "email": unique_email,
                "phone": "+11234567890",
                "password": "secure123",
            },
        )
        assert response1.status_code == 200

        # Second signup with same email
        response2 = requests.post(
            f"{BASE_URL}/api/lavela/auth/signup",
            json={
                "name": "Second Customer",
                "email": unique_email,
                "phone": "+10987654321",
                "password": "different123",
            },
        )

        assert response2.status_code == 400
        data = response2.json()
        assert "already registered" in data.get("detail", "").lower()

    def test_signup_missing_required_fields(self):
        """Test signup with missing required fields"""
        # Missing name
        response = requests.post(
            f"{BASE_URL}/api/lavela/auth/signup",
            json={"email": "test@lavela.com", "password": "secure123"},
        )
        assert response.status_code == 422  # Validation error

        # Missing email
        response = requests.post(
            f"{BASE_URL}/api/lavela/auth/signup",
            json={"name": "Test", "password": "secure123"},
        )
        assert response.status_code == 422

        # Missing password
        response = requests.post(
            f"{BASE_URL}/api/lavela/auth/signup",
            json={"name": "Test", "email": "test@lavela.com"},
        )
        assert response.status_code == 422

    def test_signup_invalid_email(self):
        """Test signup with invalid email format"""
        response = requests.post(
            f"{BASE_URL}/api/lavela/auth/signup",
            json={
                "name": "Test Customer",
                "email": "invalid-email",
                "password": "secure123",
            },
        )
        assert response.status_code == 422


class TestLaVelaAuthLogin:
    """Test LA VELA login endpoint"""

    @pytest.fixture(autouse=True)
    def setup_test_user(self):
        """Create a test user for login tests"""
        import uuid

        self.test_email = f"test_login_{uuid.uuid4().hex[:8]}@lavela.com"
        self.test_password = "secure123"

        response = requests.post(
            f"{BASE_URL}/api/lavela/auth/signup",
            json={
                "name": "Login Test User",
                "email": self.test_email,
                "phone": "+11234567890",
                "password": self.test_password,
            },
        )
        assert response.status_code == 200, f"Setup failed: {response.text}"

    def test_login_success(self):
        """Test successful login"""
        response = requests.post(
            f"{BASE_URL}/api/lavela/auth/login",
            json={"email": self.test_email, "password": self.test_password},
        )

        assert (
            response.status_code == 200
        ), f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert "token" in data, "Response should contain token"
        assert "user" in data, "Response should contain user"

        # Verify user data
        user = data["user"]
        assert user["email"] == self.test_email.lower()
        assert user["name"] == "Login Test User"
        assert "points" in user
        assert "tier" in user

    def test_login_wrong_password(self):
        """Test login with wrong password"""
        response = requests.post(
            f"{BASE_URL}/api/lavela/auth/login",
            json={"email": self.test_email, "password": "wrongpassword"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "invalid" in data.get("detail", "").lower()

    def test_login_nonexistent_email(self):
        """Test login with non-existent email"""
        response = requests.post(
            f"{BASE_URL}/api/lavela/auth/login",
            json={"email": "nonexistent@lavela.com", "password": "anypassword"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "invalid" in data.get("detail", "").lower()

    def test_login_missing_fields(self):
        """Test login with missing fields"""
        # Missing email
        response = requests.post(
            f"{BASE_URL}/api/lavela/auth/login", json={"password": "secure123"}
        )
        assert response.status_code == 422

        # Missing password
        response = requests.post(
            f"{BASE_URL}/api/lavela/auth/login", json={"email": "test@lavela.com"}
        )
        assert response.status_code == 422


class TestLaVelaAuthIntegration:
    """Integration tests for LA VELA auth flow"""

    def test_signup_then_login(self):
        """Test full signup -> login flow"""
        unique_email = f"test_flow_{int(time.time())}@lavela.com"
        password = "secure123"

        # Signup
        signup_response = requests.post(
            f"{BASE_URL}/api/lavela/auth/signup",
            json={
                "name": "Flow Test User",
                "email": unique_email,
                "phone": "+11234567890",
                "password": password,
            },
        )
        assert signup_response.status_code == 200
        signup_data = signup_response.json()
        signup_token = signup_data["token"]

        # Login with same credentials
        login_response = requests.post(
            f"{BASE_URL}/api/lavela/auth/login",
            json={"email": unique_email, "password": password},
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        login_token = login_data["token"]

        # Both tokens should be valid JWT tokens
        assert len(signup_token) > 50  # JWT tokens are long
        assert len(login_token) > 50
        # Note: Tokens may be same if generated in same second (same exp timestamp)

        # User data should match
        assert signup_data["user"]["id"] == login_data["user"]["id"]
        assert signup_data["user"]["email"] == login_data["user"]["email"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
