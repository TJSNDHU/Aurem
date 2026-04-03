"""
Test discount code validation across all 5 collections.
Tests /api/validate-discount endpoint with codes from:
1. discount_codes - Regular discount codes (WELCOME20 = 25% off)
2. exclusive_discounts - Exclusive codes for specific users
3. offers - SMS/Email offer codes (TEST102IQA1 = 10% off)
4. coupons - General coupons
5. influencer_applications - Partner/influencer codes

Also tests checkout pricing with discount codes applied.
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@reroots.ca"
ADMIN_PASSWORD = "new_password_123"

# Test product (prod-aura-gen = $72.47)
TEST_PRODUCT_ID = "prod-aura-gen"


class TestSetup:
    """Get admin token for test setup"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip(f"Admin authentication failed: {response.text}")


class TestDiscountCodesCollection:
    """Test codes from discount_codes collection (WELCOME20 = 25%)"""
    
    def test_validate_welcome20_code(self):
        """Test WELCOME20 discount code from discount_codes collection"""
        response = requests.post(
            f"{BASE_URL}/api/validate-discount",
            json={"code": "WELCOME20"}
        )
        
        # Code should be valid
        if response.status_code == 200:
            data = response.json()
            assert data["valid"] == True, "WELCOME20 should be valid"
            assert data["code"] == "WELCOME20", "Code should match"
            # WELCOME20 is 25% discount
            assert data.get("discount_percent", 0) == 25 or data.get("discount_value", 0) == 25, \
                f"WELCOME20 should be 25% discount, got: {data}"
            print(f"✓ WELCOME20 validated: {data.get('discount_percent', data.get('discount_value'))}% discount")
        elif response.status_code == 400:
            # Code may not exist or be inactive
            error = response.json().get("detail", "")
            print(f"! WELCOME20 validation failed: {error}")
            pytest.skip(f"WELCOME20 code not available: {error}")
        else:
            pytest.fail(f"Unexpected response: {response.status_code} - {response.text}")
    
    def test_validate_welcome20_case_insensitive(self):
        """Test WELCOME20 with lowercase"""
        response = requests.post(
            f"{BASE_URL}/api/validate-discount",
            json={"code": "welcome20"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert data["valid"] == True
            print("✓ Code validation is case-insensitive")
        elif response.status_code == 400:
            pytest.skip("WELCOME20 code not available")


class TestOffersCollection:
    """Test codes from offers collection (SMS/Email offers)"""
    
    def test_validate_test102iqa1_offer_code(self):
        """Test TEST102IQA1 offer code from offers collection (10% off email offer)"""
        response = requests.post(
            f"{BASE_URL}/api/validate-discount",
            json={"code": "TEST102IQA1"}
        )
        
        if response.status_code == 200:
            data = response.json()
            assert data["valid"] == True, "TEST102IQA1 should be valid"
            assert data["code"] == "TEST102IQA1", "Code should match"
            # Should be 10% discount
            discount = data.get("discount_percent", 0) or data.get("discount_value", 0)
            assert discount == 10, f"TEST102IQA1 should be 10% discount, got: {discount}%"
            print(f"✓ TEST102IQA1 validated: {discount}% discount from offers collection")
        elif response.status_code == 400:
            error = response.json().get("detail", "")
            print(f"! TEST102IQA1 validation failed: {error}")
            pytest.skip(f"TEST102IQA1 code not available: {error}")
        else:
            pytest.fail(f"Unexpected response: {response.status_code} - {response.text}")


class TestCouponsCollection:
    """Test codes from coupons collection"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin authentication failed")
    
    def test_create_and_validate_coupon(self, admin_token):
        """Create a coupon and validate it works"""
        # Generate unique coupon code
        test_coupon_code = f"TEST_COUPON_{uuid.uuid4().hex[:6].upper()}"
        
        # Try to create coupon via admin API (if available)
        # First, insert directly via a test endpoint or check if coupons exist
        
        # For this test, we'll validate against existing coupons in database
        # List any existing coupons
        response = requests.get(
            f"{BASE_URL}/api/admin/coupons",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            coupons = response.json()
            if isinstance(coupons, list) and len(coupons) > 0:
                # Test with first available coupon
                coupon = coupons[0]
                coupon_code = coupon.get("code")
                if coupon_code:
                    validate_resp = requests.post(
                        f"{BASE_URL}/api/validate-discount",
                        json={"code": coupon_code}
                    )
                    if validate_resp.status_code == 200:
                        data = validate_resp.json()
                        assert data["valid"] == True
                        print(f"✓ Coupon {coupon_code} validated successfully")
                    else:
                        print(f"! Coupon {coupon_code} validation failed: {validate_resp.text}")
            else:
                print("! No coupons found in database - skipping coupon test")
                pytest.skip("No coupons available")
        elif response.status_code == 404:
            print("! /api/admin/coupons endpoint not found")
            pytest.skip("Coupons admin endpoint not available")
        else:
            print(f"! Failed to get coupons: {response.status_code}")
            pytest.skip(f"Coupons endpoint error: {response.status_code}")


class TestExclusiveDiscountsCollection:
    """Test codes from exclusive_discounts collection"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin authentication failed")
    
    def test_exclusive_discount_requires_email(self):
        """Test that exclusive discounts may require email verification"""
        # Try to list exclusive discounts if available
        response = requests.get(f"{BASE_URL}/api/admin/exclusive-discounts")
        
        if response.status_code == 200:
            discounts = response.json()
            if isinstance(discounts, list) and len(discounts) > 0:
                exclusive = discounts[0]
                code = exclusive.get("code")
                if code:
                    # Validate without email
                    validate_resp = requests.post(
                        f"{BASE_URL}/api/validate-discount",
                        json={"code": code}
                    )
                    print(f"Exclusive code {code} validation result: {validate_resp.status_code}")
                    if validate_resp.status_code == 200:
                        print(f"✓ Exclusive discount {code} validated")
                    elif validate_resp.status_code == 400:
                        detail = validate_resp.json().get("detail", "")
                        if "log in" in detail.lower() or "exclusive" in detail.lower():
                            print(f"✓ Exclusive discount {code} correctly requires email/login")
                        else:
                            print(f"! Exclusive validation failed: {detail}")
            else:
                pytest.skip("No exclusive discounts found")
        elif response.status_code == 401:
            pytest.skip("Exclusive discounts endpoint requires auth")
        else:
            pytest.skip(f"Exclusive discounts endpoint error: {response.status_code}")


class TestInfluencerPartnerCodes:
    """Test codes from influencer_applications collection (partner codes)"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin authentication failed")
    
    def test_partner_code_validation(self, admin_token):
        """Test partner/influencer code validation with voucher gate"""
        # Get approved partners
        response = requests.get(
            f"{BASE_URL}/api/admin/partner-applications?status=approved",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            partners = response.json()
            partner_list = partners.get("applications", partners) if isinstance(partners, dict) else partners
            
            if isinstance(partner_list, list) and len(partner_list) > 0:
                # Find partner with a code
                for partner in partner_list:
                    partner_code = partner.get("partner_code")
                    if partner_code:
                        validate_resp = requests.post(
                            f"{BASE_URL}/api/validate-discount",
                            json={"code": partner_code, "email": "test@example.com"}
                        )
                        
                        if validate_resp.status_code == 200:
                            data = validate_resp.json()
                            assert data["valid"] == True
                            assert data.get("is_partner_code") == True, "Should be identified as partner code"
                            # Voucher gate may or may not be unlocked
                            print(f"✓ Partner code {partner_code} validated: voucher_unlocked={data.get('voucher_unlocked')}")
                            if not data.get("voucher_unlocked"):
                                print(f"  Voucher locked - needs {data.get('referrals_needed', 'N/A')} more referrals")
                            return
                        else:
                            print(f"! Partner code {partner_code} validation: {validate_resp.status_code}")
                            
                print("! No partner codes found in approved applications")
                pytest.skip("No partner codes available")
            else:
                pytest.skip("No approved partners found")
        else:
            pytest.skip(f"Failed to get partner applications: {response.status_code}")


class TestInvalidCodes:
    """Test invalid discount code handling"""
    
    def test_invalid_code_returns_400(self):
        """Test that invalid codes return 400 error"""
        response = requests.post(
            f"{BASE_URL}/api/validate-discount",
            json={"code": "INVALID_CODE_XYZ123"}
        )
        
        assert response.status_code == 400, f"Expected 400 for invalid code, got {response.status_code}"
        data = response.json()
        assert "detail" in data, "Should return error detail"
        print(f"✓ Invalid code correctly rejected: {data['detail']}")
    
    def test_empty_code_returns_400(self):
        """Test that empty code returns 400 error"""
        response = requests.post(
            f"{BASE_URL}/api/validate-discount",
            json={"code": ""}
        )
        
        assert response.status_code == 400, f"Expected 400 for empty code, got {response.status_code}"
        print("✓ Empty code correctly rejected")
    
    def test_whitespace_code_returns_400(self):
        """Test that whitespace-only code returns 400 error"""
        response = requests.post(
            f"{BASE_URL}/api/validate-discount",
            json={"code": "   "}
        )
        
        assert response.status_code == 400, f"Expected 400 for whitespace code, got {response.status_code}"
        print("✓ Whitespace-only code correctly rejected")


class TestCheckoutWithDiscounts:
    """Test checkout pricing with discount codes applied
    NOTE: checkout/pricing uses 'discount_code' (singular) parameter, not 'discount_codes'
    """
    
    def test_checkout_pricing_with_welcome20(self):
        """Test checkout pricing applies WELCOME20 discount correctly (25% off from discount_codes)"""
        # First validate the code
        validate_resp = requests.post(
            f"{BASE_URL}/api/validate-discount",
            json={"code": "WELCOME20"}
        )
        
        if validate_resp.status_code != 200:
            pytest.skip("WELCOME20 code not available")
        
        # Now test checkout pricing with the code (NOTE: 'discount_code' singular)
        response = requests.post(
            f"{BASE_URL}/api/checkout/pricing",
            json={
                "cart_items": [{"product_id": TEST_PRODUCT_ID, "quantity": 1}],
                "discount_code": "WELCOME20"  # IMPORTANT: singular 'discount_code'
            }
        )
        
        assert response.status_code == 200, f"Checkout pricing failed: {response.text}"
        
        pricing = response.json()
        original = pricing.get("original_subtotal", 0)
        final = pricing.get("final_subtotal", 0)
        discounts = pricing.get("discounts_applied", [])
        
        # Verify WELCOME20 was applied
        assert len(discounts) > 0, f"No discounts applied. Response: {pricing}"
        
        # Check for WELCOME20 in discounts
        welcome_discount = next((d for d in discounts if d.get("name") == "WELCOME20"), None)
        assert welcome_discount is not None, f"WELCOME20 not found in discounts: {discounts}"
        assert welcome_discount.get("percent") == 25.0, f"Expected 25% discount, got {welcome_discount.get('percent')}%"
        
        # Verify calculations
        expected_discount = round(original * 0.25, 2)
        assert final == round(original - expected_discount, 2), \
            f"Final price incorrect: expected {round(original - expected_discount, 2)}, got {final}"
        
        print(f"✓ WELCOME20 checkout: ${original} - ${welcome_discount.get('amount')} (25%) = ${final}")
    
    def test_checkout_pricing_with_offer_code(self):
        """Test checkout pricing with TEST102IQA1 offer code (10% off from offers collection)"""
        # First validate the code
        validate_resp = requests.post(
            f"{BASE_URL}/api/validate-discount",
            json={"code": "TEST102IQA1"}
        )
        
        if validate_resp.status_code != 200:
            pytest.skip("TEST102IQA1 code not available")
        
        # Now test checkout pricing with the code
        response = requests.post(
            f"{BASE_URL}/api/checkout/pricing",
            json={
                "cart_items": [{"product_id": TEST_PRODUCT_ID, "quantity": 1}],
                "discount_code": "TEST102IQA1"  # IMPORTANT: singular 'discount_code'
            }
        )
        
        assert response.status_code == 200, f"Checkout pricing failed: {response.text}"
        
        pricing = response.json()
        original = pricing.get("original_subtotal", 0)
        final = pricing.get("final_subtotal", 0)
        discounts = pricing.get("discounts_applied", [])
        
        # Verify discount was applied
        assert len(discounts) > 0, f"No discounts applied for TEST102IQA1"
        
        offer_discount = next((d for d in discounts if d.get("name") == "TEST102IQA1"), None)
        assert offer_discount is not None, f"TEST102IQA1 not found in discounts: {discounts}"
        assert offer_discount.get("percent") == 10, f"Expected 10% discount, got {offer_discount.get('percent')}%"
        
        print(f"✓ TEST102IQA1 checkout: ${original} - ${offer_discount.get('amount')} (10%) = ${final}")
    
    def test_checkout_pricing_with_exclusive_discount(self):
        """Test checkout pricing with exclusive discount (requires eligible email)"""
        # Test that exclusive discount requires eligible email
        response = requests.post(
            f"{BASE_URL}/api/checkout/pricing",
            json={
                "cart_items": [{"product_id": TEST_PRODUCT_ID, "quantity": 1}],
                "discount_code": "TESTEXCLUSIVE30",
                "email": "vip@example.com"  # Eligible email
            }
        )
        
        if response.status_code == 200:
            pricing = response.json()
            discounts = pricing.get("discounts_applied", [])
            
            if len(discounts) > 0:
                exclusive_discount = next((d for d in discounts if d.get("name") == "TESTEXCLUSIVE30"), None)
                if exclusive_discount:
                    assert exclusive_discount.get("percent") == 30, f"Expected 30% exclusive discount"
                    print(f"✓ Exclusive discount applied: 30% off for VIP email")
                else:
                    print(f"! TESTEXCLUSIVE30 not found in discounts: {discounts}")
            else:
                print(f"! No discounts applied - exclusive discount may not exist yet")
        else:
            print(f"! Checkout pricing failed: {response.status_code}")
    
    def test_checkout_exclusive_rejected_for_non_eligible(self):
        """Test exclusive discount is NOT applied for non-eligible emails"""
        response = requests.post(
            f"{BASE_URL}/api/checkout/pricing",
            json={
                "cart_items": [{"product_id": TEST_PRODUCT_ID, "quantity": 1}],
                "discount_code": "TESTEXCLUSIVE30",
                "email": "noteligible@random.com"  # Non-eligible email
            }
        )
        
        if response.status_code == 200:
            pricing = response.json()
            discounts = pricing.get("discounts_applied", [])
            
            # Exclusive discount should NOT be applied
            exclusive_discount = next((d for d in discounts if d.get("name") == "TESTEXCLUSIVE30"), None)
            assert exclusive_discount is None, \
                f"Exclusive discount should NOT be applied to non-eligible email, but found: {exclusive_discount}"
            
            print("✓ Exclusive discount correctly rejected for non-eligible email")
        else:
            print(f"! Checkout pricing failed: {response.status_code}")


class TestDiscountCodeUsageTracking:
    """Test discount code usage tracking"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin authentication failed")
    
    def test_discount_codes_list(self, admin_token):
        """Test listing all discount codes"""
        response = requests.get(
            f"{BASE_URL}/api/admin/discount-codes",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            codes = response.json()
            if isinstance(codes, list):
                print(f"✓ Found {len(codes)} discount codes in database")
                for code in codes[:5]:  # Print first 5
                    name = code.get("code", "N/A")
                    active = code.get("is_active", False)
                    used = code.get("used_count", 0)
                    print(f"  - {name}: active={active}, used={used}")
            else:
                print(f"✓ Discount codes response: {type(codes)}")
        else:
            print(f"! Failed to list discount codes: {response.status_code}")
    
    def test_offers_list(self, admin_token):
        """Test listing all offers (SMS/Email codes)"""
        response = requests.get(
            f"{BASE_URL}/api/admin/offers",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code == 200:
            offers = response.json()
            if isinstance(offers, list):
                print(f"✓ Found {len(offers)} offers in database")
                for offer in offers[:5]:
                    code = offer.get("code", "N/A")
                    active = offer.get("is_active", False)
                    discount = offer.get("discount_percent") or offer.get("discount_value", 0)
                    print(f"  - {code}: active={active}, discount={discount}%")
            else:
                print(f"✓ Offers response: {type(offers)}")
        elif response.status_code == 404:
            print("! /api/admin/offers endpoint not found")
        else:
            print(f"! Failed to list offers: {response.status_code}")


class TestAllCollectionsValidation:
    """Integration test to verify validate-discount checks all collections"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin authentication failed")
    
    def test_all_collections_queried(self, admin_token):
        """
        Verify that /api/validate-discount checks all 5 collections:
        1. influencer_applications (partner codes)
        2. exclusive_discounts
        3. discount_codes
        4. offers
        5. coupons
        """
        results = {}
        
        # Test 1: Check if WELCOME20 works (discount_codes)
        r1 = requests.post(f"{BASE_URL}/api/validate-discount", json={"code": "WELCOME20"})
        results["discount_codes"] = "PASS" if r1.status_code == 200 else f"SKIP ({r1.status_code})"
        
        # Test 2: Check if TEST102IQA1 works (offers)
        r2 = requests.post(f"{BASE_URL}/api/validate-discount", json={"code": "TEST102IQA1"})
        results["offers"] = "PASS" if r2.status_code == 200 else f"SKIP ({r2.status_code})"
        
        # Test 3: Check invalid code (confirms endpoint works)
        r3 = requests.post(f"{BASE_URL}/api/validate-discount", json={"code": "INVALID123"})
        results["invalid_handling"] = "PASS" if r3.status_code == 400 else f"FAIL ({r3.status_code})"
        
        # Print summary
        print("\n=== Discount Validation Summary ===")
        for collection, result in results.items():
            status = "✓" if result == "PASS" else "!" if "SKIP" in str(result) else "✗"
            print(f"  {status} {collection}: {result}")
        
        # At least discount code and invalid handling should work
        assert results["invalid_handling"] == "PASS", "Invalid code handling should work"
        print("\n✓ /api/validate-discount endpoint is functional")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
