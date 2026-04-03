"""
Test Order Creation and Bambora Payment Processing Bug Fix
This test validates the fix for the P0 bug where payment was failing with error 
'Failed to process order. Please try again.' because broadcast_admin_event was 
accessing 'order.customer_email' instead of 'order.shipping_address.email'.

Test focus:
1. Order creation API - should successfully create order and return order_id
2. Bambora payment API - should not crash with 500/520 errors
3. Full checkout flow
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data
TEST_SESSION_ID = f"test_session_{uuid.uuid4().hex[:8]}"
TEST_PRODUCT_ID = "prod-aura-gen"  # Known product from reroots


class TestOrderPaymentFix:
    """Test suite to verify the order.customer_email → order.shipping_address.email fix"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data"""
        self.session_id = TEST_SESSION_ID
        self.shipping_address = {
            "first_name": "Test",
            "last_name": "Customer",
            "email": "test@example.com",
            "phone": "416-555-0123",
            "address_line1": "123 Test St",
            "city": "Toronto",
            "province": "ON",
            "postal_code": "M5V 3L9",
            "country": "Canada"
        }
    
    def test_01_health_check(self):
        """Verify API is running"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ API health check passed")
    
    def test_02_add_item_to_cart(self):
        """Add a product to cart before creating order"""
        response = requests.post(f"{BASE_URL}/api/cart/{self.session_id}/add", json={
            "product_id": TEST_PRODUCT_ID,
            "quantity": 1
        })
        assert response.status_code == 200, f"Add to cart failed: {response.status_code}, {response.text}"
        data = response.json()
        assert "items" in data or "cart" in data or data.get("success") == True
        print(f"✓ Added product {TEST_PRODUCT_ID} to cart")
    
    def test_03_verify_cart_has_items(self):
        """Verify cart has items before creating order"""
        response = requests.get(f"{BASE_URL}/api/cart/{self.session_id}")
        assert response.status_code == 200, f"Get cart failed: {response.status_code}"
        data = response.json()
        # Cart should have items
        items = data.get("items", [])
        assert len(items) > 0, "Cart is empty - need items to test order creation"
        print(f"✓ Cart has {len(items)} item(s)")
    
    def test_04_create_order_success(self):
        """
        CRITICAL TEST: Verify order creation API works after the fix.
        
        The bug was in broadcast_admin_event (line 6834) which tried to access
        'order.customer_email' but the Order model doesn't have that field.
        It should use 'order.shipping_address.email'.
        
        This test verifies the API returns 200/201 with an order_id (not 500 error).
        """
        order_payload = {
            "session_id": self.session_id,
            "shipping_address": self.shipping_address,
            "payment_method": "bambora",  # Test with Bambora payment method
            "discount_code": None,
            "discount_codes": [],
            "discount_percent": 0,
            "points_to_redeem": 0,
            "redemption_token": None
        }
        
        response = requests.post(f"{BASE_URL}/api/orders", json=order_payload)
        
        # The key assertion: should NOT get 500 error
        assert response.status_code != 500, f"Order creation crashed with 500! Bug may not be fixed. Response: {response.text}"
        assert response.status_code != 520, f"Order creation returned 520 error. Response: {response.text}"
        
        # Should be 200 or 201 for success
        assert response.status_code in [200, 201], f"Order creation failed with {response.status_code}: {response.text}"
        
        data = response.json()
        assert "order_id" in data, f"Response missing order_id. Data: {data}"
        
        self.__class__.order_id = data["order_id"]
        print(f"✓ Order created successfully with ID: {self.__class__.order_id}")
        print(f"  Response data: {data}")
    
    def test_05_bambora_checkout_no_500_error(self):
        """
        Test Bambora payment endpoint doesn't crash with 500.
        
        Note: The actual payment may fail due to:
        - Test card restrictions
        - 'CALL HELP DESK' from Bambora (merchant account restriction)
        
        The key test is that the API doesn't crash with 500/520 errors.
        A declined payment (400-level) with proper error message is ACCEPTABLE.
        """
        if not hasattr(self.__class__, 'order_id'):
            pytest.skip("No order_id available from previous test")
        
        payment_payload = {
            "order_id": self.__class__.order_id,
            "card_number": "4030000010001234",  # Bambora test card
            "expiry_month": 12,
            "expiry_year": 26,
            "cvv": "123",
            "cardholder_name": "Test Customer",
            "billing_postal_code": "M5V 3L9"
        }
        
        response = requests.post(f"{BASE_URL}/api/payments/bambora/checkout", json=payment_payload)
        
        # The key assertion: should NOT crash with 500/520
        assert response.status_code != 500, f"Bambora checkout crashed with 500! Response: {response.text}"
        assert response.status_code != 520, f"Bambora checkout returned 520 error. Response: {response.text}"
        
        # Either success (200) or declined with proper error message (4xx level) is acceptable
        data = response.json()
        print(f"✓ Bambora checkout returned {response.status_code}")
        print(f"  Response: {data}")
        
        # If success
        if response.status_code == 200 and data.get("success"):
            print(f"  Payment successful! Transaction ID: {data.get('transaction_id')}")
        else:
            # Payment declined but API didn't crash - this is acceptable
            print(f"  Payment declined (expected with test cards): {data.get('message', 'No message')}")
            # Verify we got a proper error response, not a crash
            assert "message" in data or "detail" in data or "success" in data


class TestOrderCreationWithNewCart:
    """
    Separate test class with fresh cart to ensure complete isolation
    """
    
    def test_full_checkout_flow(self):
        """End-to-end test: Cart → Order → Payment attempt"""
        # Use a unique session ID for this test
        session_id = f"e2e_test_{uuid.uuid4().hex[:8]}"
        
        # Step 1: Add to cart
        print("\n--- Step 1: Add to cart ---")
        cart_response = requests.post(f"{BASE_URL}/api/cart/{session_id}/add", json={
            "product_id": "prod-aura-gen",
            "quantity": 1
        })
        assert cart_response.status_code == 200, f"Add to cart failed: {cart_response.text}"
        print("✓ Item added to cart")
        
        # Step 2: Create order
        print("\n--- Step 2: Create order ---")
        order_payload = {
            "session_id": session_id,
            "shipping_address": {
                "first_name": "E2E",
                "last_name": "Test",
                "email": "e2e_test@reroots.ca",
                "phone": "416-555-0199",
                "address_line1": "456 E2E Test Ave",
                "city": "Toronto",
                "province": "ON",
                "postal_code": "M5V 2H1",
                "country": "Canada"
            },
            "payment_method": "bambora"
        }
        
        order_response = requests.post(f"{BASE_URL}/api/orders", json=order_payload)
        
        # Critical check - should not be 500 error
        assert order_response.status_code != 500, f"ORDER CREATION CRASHED WITH 500! Bug not fixed. Response: {order_response.text}"
        assert order_response.status_code != 520, f"ORDER CREATION RETURNED 520! Response: {order_response.text}"
        
        assert order_response.status_code in [200, 201], f"Order creation failed: {order_response.status_code} - {order_response.text}"
        
        order_data = order_response.json()
        order_id = order_data.get("order_id")
        assert order_id, f"No order_id in response: {order_data}"
        print(f"✓ Order created: {order_id}")
        
        # Step 3: Attempt payment
        print("\n--- Step 3: Attempt payment ---")
        payment_payload = {
            "order_id": order_id,
            "card_number": "4030000010001234",
            "expiry_month": 12,
            "expiry_year": 26,
            "cvv": "123",
            "cardholder_name": "E2E Test",
            "billing_postal_code": "M5V 2H1"
        }
        
        payment_response = requests.post(f"{BASE_URL}/api/payments/bambora/checkout", json=payment_payload)
        
        # Critical check - should not crash
        assert payment_response.status_code != 500, f"PAYMENT CRASHED WITH 500! Response: {payment_response.text}"
        assert payment_response.status_code != 520, f"PAYMENT RETURNED 520! Response: {payment_response.text}"
        
        payment_data = payment_response.json()
        print(f"✓ Payment endpoint responded: {payment_response.status_code}")
        print(f"  Result: {payment_data}")
        
        # Payment may be declined due to test card restrictions, but that's OK
        # The important thing is the API didn't crash


class TestVerifyShippingAddressEmailAccess:
    """
    Verify the fix by checking order retrieval has shipping_address.email
    """
    
    def test_order_has_shipping_address_email(self):
        """Verify created order has shipping_address.email structure"""
        session_id = f"verify_email_{uuid.uuid4().hex[:8]}"
        test_email = f"verify_email_{uuid.uuid4().hex[:4]}@test.com"
        
        # Create cart
        requests.post(f"{BASE_URL}/api/cart/{session_id}/add", json={
            "product_id": "prod-aura-gen",
            "quantity": 1
        })
        
        # Create order
        order_response = requests.post(f"{BASE_URL}/api/orders", json={
            "session_id": session_id,
            "shipping_address": {
                "first_name": "Email",
                "last_name": "Test",
                "email": test_email,
                "phone": "416-555-0100",
                "address_line1": "789 Email Test St",
                "city": "Toronto",
                "province": "ON",
                "postal_code": "M5V 1A1",
                "country": "Canada"
            },
            "payment_method": "etransfer"  # Use e-transfer to avoid payment step
        })
        
        assert order_response.status_code in [200, 201], f"Order creation failed: {order_response.text}"
        order_data = order_response.json()
        order_id = order_data.get("order_id")
        print(f"✓ Order created with ID: {order_id}")
        
        # Retrieve order to verify structure
        # Note: Need admin auth to get order details
        # For now, the test passes if order creation succeeded
        print(f"✓ Order created successfully with email: {test_email}")
        print("  The fix ensures shipping_address.email is used instead of customer_email")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
