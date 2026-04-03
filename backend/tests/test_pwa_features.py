"""
ReRoots AI PWA Backend API Tests
Tests for PWA endpoints: /api/pwa/test, /api/pwa/vapid-key, /api/pwa/voice/config
"""

import pytest
import requests
import os

# Get backend URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://live-support-test.preview.emergentagent.com').rstrip('/')


class TestPWAEndpoints:
    """PWA API endpoint tests"""
    
    def test_pwa_test_endpoint(self):
        """Test /api/pwa/test returns status ok"""
        response = requests.get(f"{BASE_URL}/api/pwa/test")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["status"] == "ok"
        assert "message" in data
        assert "ReRoots AI PWA Backend Active" in data["message"]
        assert "vapid_configured" in data
        assert "voxtral_configured" in data
        assert "ai_configured" in data
        assert "timestamp" in data
        
        print(f"PWA Test endpoint: status={data['status']}, vapid={data['vapid_configured']}, ai={data['ai_configured']}")
    
    def test_pwa_vapid_key_endpoint(self):
        """Test /api/pwa/vapid-key returns VAPID public key"""
        response = requests.get(f"{BASE_URL}/api/pwa/vapid-key")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify VAPID key is present
        assert "publicKey" in data
        assert len(data["publicKey"]) > 50  # VAPID keys are typically 87 chars
        
        # Verify it matches expected format (Base64 URL-safe)
        vapid_key = data["publicKey"]
        assert vapid_key.startswith("BI")  # VAPID public keys start with BI
        
        print(f"VAPID key returned: {vapid_key[:20]}...")
    
    def test_pwa_voice_config_endpoint(self):
        """Test /api/pwa/voice/config returns voice configuration"""
        response = requests.get(f"{BASE_URL}/api/pwa/voice/config")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "voxtral_available" in data
        assert "fallback" in data
        assert data["fallback"] == "web_speech_api"
        
        print(f"Voice config: voxtral_available={data['voxtral_available']}, fallback={data['fallback']}")


class TestProductsEndpoint:
    """Products API tests for PWA Shop tab"""
    
    def test_products_list(self):
        """Test /api/products returns products list"""
        response = requests.get(f"{BASE_URL}/api/products")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify products are returned
        assert isinstance(data, list) or "products" in data
        
        products = data if isinstance(data, list) else data.get("products", [])
        assert len(products) > 0
        
        # Verify product structure
        product = products[0]
        assert "name" in product
        assert "price" in product
        assert "id" in product or "_id" in product
        
        print(f"Products endpoint: {len(products)} products returned")
    
    def test_products_with_limit(self):
        """Test /api/products with limit parameter"""
        response = requests.get(f"{BASE_URL}/api/products?limit=5")
        
        assert response.status_code == 200
        data = response.json()
        
        products = data if isinstance(data, list) else data.get("products", [])
        assert len(products) <= 5
        
        print(f"Products with limit=5: {len(products)} products returned")
    
    def test_products_featured(self):
        """Test /api/products with featured filter"""
        response = requests.get(f"{BASE_URL}/api/products?featured=true")
        
        assert response.status_code == 200
        data = response.json()
        
        products = data if isinstance(data, list) else data.get("products", [])
        
        # Verify featured products have is_featured flag
        for product in products:
            if "is_featured" in product:
                assert product["is_featured"] == True
        
        print(f"Featured products: {len(products)} products returned")


class TestHealthEndpoint:
    """Health check endpoint test"""
    
    def test_health_endpoint(self):
        """Test /api/health returns ok"""
        response = requests.get(f"{BASE_URL}/api/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("status") == "ok"
        print("Health endpoint: status=ok")


# Fixtures
@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
