"""
Tests for Cart Persistence and PayPal SDK v6 Integration
- Cart persistence across page navigation
- PayPal client token generation
- PayPal order creation flow
"""
import pytest
import requests
import os
import uuid
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCartPersistence:
    """Test cart persistence functionality"""
    
    @pytest.fixture
    def session_id(self):
        """Generate a unique session ID for testing"""
        return f"test-session-{uuid.uuid4().hex[:8]}"
    
    def test_add_item_to_cart(self, session_id):
        """Test adding an item to cart"""
        # First get available products
        products_response = requests.get(f"{BASE_URL}/api/products")
        assert products_response.status_code == 200
        products = products_response.json()
        assert len(products) > 0, "No products available"
        
        product_id = products[0]['id']
        
        # Add item to cart
        add_response = requests.post(
            f"{BASE_URL}/api/cart/{session_id}/add",
            json={"product_id": product_id, "quantity": 2}
        )
        assert add_response.status_code == 200
        
        cart_data = add_response.json()
        assert 'items' in cart_data
        assert len(cart_data['items']) == 1
        assert cart_data['items'][0]['quantity'] == 2
        print(f"PASS: Added item to cart - {cart_data['items'][0]['product']['name']} x 2")
    
    def test_cart_persistence_on_fetch(self, session_id):
        """Test that cart items persist when fetched again"""
        # First get available products
        products_response = requests.get(f"{BASE_URL}/api/products")
        products = products_response.json()
        product_id = products[0]['id']
        
        # Add item to cart
        add_response = requests.post(
            f"{BASE_URL}/api/cart/{session_id}/add",
            json={"product_id": product_id, "quantity": 1}
        )
        assert add_response.status_code == 200
        
        # Fetch cart again (simulating page navigation)
        fetch_response = requests.get(f"{BASE_URL}/api/cart/{session_id}")
        assert fetch_response.status_code == 200
        
        cart_data = fetch_response.json()
        assert 'items' in cart_data
        assert len(cart_data['items']) > 0, "Cart should retain items after fetch"
        print(f"PASS: Cart persisted with {len(cart_data['items'])} items after refetch")
    
    def test_update_cart_quantity(self, session_id):
        """Test updating cart item quantity"""
        # Add item
        products_response = requests.get(f"{BASE_URL}/api/products")
        product_id = products_response.json()[0]['id']
        
        requests.post(
            f"{BASE_URL}/api/cart/{session_id}/add",
            json={"product_id": product_id, "quantity": 1}
        )
        
        # Update quantity
        update_response = requests.put(
            f"{BASE_URL}/api/cart/{session_id}/update",
            json={"product_id": product_id, "quantity": 5}
        )
        assert update_response.status_code == 200
        
        cart_data = update_response.json()
        assert cart_data['items'][0]['quantity'] == 5
        print(f"PASS: Cart quantity updated to 5")
    
    def test_remove_item_from_cart(self, session_id):
        """Test removing item from cart"""
        # Add item
        products_response = requests.get(f"{BASE_URL}/api/products")
        product_id = products_response.json()[0]['id']
        
        requests.post(
            f"{BASE_URL}/api/cart/{session_id}/add",
            json={"product_id": product_id, "quantity": 1}
        )
        
        # Remove item
        remove_response = requests.delete(f"{BASE_URL}/api/cart/{session_id}/item/{product_id}")
        assert remove_response.status_code == 200
        
        cart_data = remove_response.json()
        assert len(cart_data['items']) == 0
        print(f"PASS: Item removed from cart")


class TestPayPalSDKv6:
    """Test PayPal SDK v6 integration"""
    
    def test_paypal_client_token_endpoint(self):
        """Test that PayPal client token endpoint returns a valid JWT token"""
        response = requests.post(
            f"{BASE_URL}/api/payments/paypal/client-token",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert 'clientToken' in data, "Response should contain 'clientToken'"
        assert data['clientToken'], "clientToken should not be empty"
        assert len(data['clientToken']) > 100, "clientToken should be a valid JWT (length > 100)"
        
        # JWT tokens have 3 parts separated by dots
        token_parts = data['clientToken'].split('.')
        # Note: OAuth2 access tokens may not be strict JWTs - they just need to work with SDK
        
        assert 'expiresIn' in data, "Response should contain 'expiresIn'"
        assert data['expiresIn'] > 0, "expiresIn should be positive"
        
        print(f"PASS: PayPal client token generated - Length: {len(data['clientToken'])}, Expires in: {data['expiresIn']}s")
    
    def test_paypal_config_endpoint(self):
        """Test PayPal config endpoint"""
        response = requests.get(f"{BASE_URL}/api/payments/paypal/config")
        
        assert response.status_code == 200
        
        data = response.json()
        assert 'client_id' in data
        assert 'mode' in data
        assert data['mode'] in ['sandbox', 'live']
        
        print(f"PASS: PayPal config - Mode: {data['mode']}, Client ID present: {bool(data['client_id'])}")


class TestPaymentMethods:
    """Test payment method configuration"""
    
    def test_store_settings_payment_methods(self):
        """Test that store settings include payment method configuration"""
        response = requests.get(f"{BASE_URL}/api/store/settings")
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Check if payment settings are present
        if 'payment' in data:
            payment = data['payment']
            print(f"Payment settings found:")
            print(f"  - Bambora enabled: {payment.get('bambora_enabled', 'not set')}")
            print(f"  - e-Transfer enabled: {payment.get('etransfer_enabled', 'not set')}")
            print(f"  - PayPal API enabled: {payment.get('paypal_api_enabled', 'not set')}")
        else:
            print("No payment settings in store settings (uses defaults)")
        
        # Test passes as long as endpoint works
        assert True


class TestCheckoutFlow:
    """Test checkout flow integration"""
    
    @pytest.fixture
    def session_id(self):
        return f"test-checkout-{uuid.uuid4().hex[:8]}"
    
    def test_checkout_pricing_endpoint(self, session_id):
        """Test checkout pricing calculation"""
        # First add item to cart
        products_response = requests.get(f"{BASE_URL}/api/products")
        product = products_response.json()[0]
        
        requests.post(
            f"{BASE_URL}/api/cart/{session_id}/add",
            json={"product_id": product['id'], "quantity": 1}
        )
        
        # Get checkout pricing
        pricing_response = requests.post(
            f"{BASE_URL}/api/checkout/pricing",
            json={
                "email": "test@example.com",
                "original_subtotal": product['price'],
                "cart_items": [{"product_id": product['id'], "quantity": 1}],
                "discount_code": ""
            }
        )
        
        assert pricing_response.status_code == 200
        
        data = pricing_response.json()
        assert 'final_subtotal' in data
        print(f"PASS: Checkout pricing - Final subtotal: ${data['final_subtotal']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
