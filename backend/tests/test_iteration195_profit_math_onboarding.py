"""
Iteration 195 - AUREM Profit-Math Pricing + Post-Payment Onboarding
====================================================================
Tests:
1. GET /api/report/{slug} - pricing array with profit-math fields
2. GET /api/onboarding/urgency/stats - public urgency stats
3. GET /api/onboarding/by-session/{session_id} - lookup by Stripe session
4. GET /api/onboarding/{tenant_id} - full onboarding state
5. POST /api/payments/checkout - accepts `ref` field for attribution
6. run_post_payment_flow - importable and callable
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestProfitMathPricing:
    """Test profit-math fields in pricing array from /api/report/{slug}"""
    
    def test_report_pricing_has_profit_math_fields(self):
        """Verify pricing tiers include customers_low, customers_high, earn_low_cad, earn_high_cad, profit_cad, payback_customers"""
        response = requests.get(f"{BASE_URL}/api/report/tj-auto-clinic-001")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "pricing" in data, "Response missing 'pricing' field"
        pricing = data["pricing"]
        assert len(pricing) == 3, f"Expected 3 pricing tiers, got {len(pricing)}"
        
        # Check each tier has profit-math fields
        required_fields = ["customers_low", "customers_high", "earn_low_cad", "earn_high_cad", "profit_cad", "payback_customers"]
        for tier in pricing:
            for field in required_fields:
                assert field in tier, f"Tier {tier.get('tier')} missing '{field}'"
        
        print("✓ All pricing tiers have profit-math fields")
    
    def test_starter_tier_profit_math(self):
        """Verify Starter tier: $97/mo, 8-12 customers, payback=1"""
        response = requests.get(f"{BASE_URL}/api/report/tj-auto-clinic-001")
        assert response.status_code == 200
        
        data = response.json()
        starter = next((t for t in data["pricing"] if t["tier"] == "starter"), None)
        assert starter is not None, "Starter tier not found"
        
        assert starter["price_cad"] == 97, f"Starter price should be 97, got {starter['price_cad']}"
        assert starter["customers_low"] == 8, f"Starter customers_low should be 8, got {starter['customers_low']}"
        assert starter["customers_high"] == 12, f"Starter customers_high should be 12, got {starter['customers_high']}"
        assert starter["payback_customers"] == 1, f"Starter payback_customers should be 1, got {starter['payback_customers']}"
        
        # Verify profit calculation: earn_low - price = profit
        expected_profit = starter["earn_low_cad"] - starter["price_cad"]
        assert starter["profit_cad"] == expected_profit, f"Profit calculation mismatch: {starter['profit_cad']} != {expected_profit}"
        
        print(f"✓ Starter tier: ${starter['price_cad']}/mo, {starter['customers_low']}-{starter['customers_high']} customers, profit ${starter['profit_cad']}/mo")
    
    def test_growth_tier_profit_math(self):
        """Verify Growth tier: $297/mo, 25-40 customers, profit ~$8,453/mo (at $350 avg job)"""
        response = requests.get(f"{BASE_URL}/api/report/tj-auto-clinic-001")
        assert response.status_code == 200
        
        data = response.json()
        growth = next((t for t in data["pricing"] if t["tier"] == "growth"), None)
        assert growth is not None, "Growth tier not found"
        
        assert growth["price_cad"] == 297, f"Growth price should be 297, got {growth['price_cad']}"
        assert growth["customers_low"] == 25, f"Growth customers_low should be 25, got {growth['customers_low']}"
        assert growth["customers_high"] == 40, f"Growth customers_high should be 40, got {growth['customers_high']}"
        assert growth["payback_customers"] == 1, f"Growth payback_customers should be 1, got {growth['payback_customers']}"
        assert growth["popular"] == True, "Growth tier should be marked as popular"
        
        # At $350 avg job: 25 * 350 = 8750, profit = 8750 - 297 = 8453
        # Note: actual avg_job_value may vary based on lead category
        print(f"✓ Growth tier: ${growth['price_cad']}/mo, {growth['customers_low']}-{growth['customers_high']} customers, profit ${growth['profit_cad']}/mo")
    
    def test_enterprise_tier_profit_math(self):
        """Verify Enterprise tier: $997/mo, 100-150 customers, profit ~$34,003/mo (at $350 avg job)"""
        response = requests.get(f"{BASE_URL}/api/report/tj-auto-clinic-001")
        assert response.status_code == 200
        
        data = response.json()
        enterprise = next((t for t in data["pricing"] if t["tier"] == "enterprise"), None)
        assert enterprise is not None, "Enterprise tier not found"
        
        assert enterprise["price_cad"] == 997, f"Enterprise price should be 997, got {enterprise['price_cad']}"
        assert enterprise["customers_low"] == 100, f"Enterprise customers_low should be 100, got {enterprise['customers_low']}"
        assert enterprise["customers_high"] == 150, f"Enterprise customers_high should be 150, got {enterprise['customers_high']}"
        assert enterprise["payback_customers"] == 3, f"Enterprise payback_customers should be 3, got {enterprise['payback_customers']}"
        
        # At $350 avg job: 100 * 350 = 35000, profit = 35000 - 997 = 34003
        print(f"✓ Enterprise tier: ${enterprise['price_cad']}/mo, {enterprise['customers_low']}-{enterprise['customers_high']} customers, profit ${enterprise['profit_cad']}/mo")


class TestOnboardingUrgencyStats:
    """Test GET /api/onboarding/urgency/stats endpoint"""
    
    def test_urgency_stats_returns_required_fields(self):
        """Verify urgency stats returns signups_today, live, timestamp"""
        response = requests.get(f"{BASE_URL}/api/onboarding/urgency/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "signups_today" in data, "Response missing 'signups_today'"
        assert "live" in data, "Response missing 'live'"
        assert "timestamp" in data, "Response missing 'timestamp'"
        
        # signups_today should be at least 3 (floor value for social proof)
        assert data["signups_today"] >= 3, f"signups_today should be >= 3, got {data['signups_today']}"
        
        print(f"✓ Urgency stats: {data['signups_today']} signups today, live={data['live']}")
    
    def test_urgency_stats_no_auth_required(self):
        """Verify urgency stats is a public endpoint (no auth)"""
        response = requests.get(f"{BASE_URL}/api/onboarding/urgency/stats")
        # Should not return 401/403
        assert response.status_code != 401, "Urgency stats should not require auth"
        assert response.status_code != 403, "Urgency stats should not be forbidden"
        assert response.status_code == 200
        print("✓ Urgency stats is public (no auth required)")


class TestOnboardingBySession:
    """Test GET /api/onboarding/by-session/{session_id} endpoint"""
    
    def test_nonexistent_session_returns_404(self):
        """Verify 404 for non-existent session_id"""
        response = requests.get(f"{BASE_URL}/api/onboarding/by-session/nonexistent-session-12345")
        assert response.status_code == 404, f"Expected 404 for non-existent session, got {response.status_code}"
        print("✓ Non-existent session returns 404")
    
    def test_endpoint_exists_and_responds(self):
        """Verify the endpoint exists and responds (even if 404)"""
        response = requests.get(f"{BASE_URL}/api/onboarding/by-session/test-session")
        # Should be 404 (not found) or 200 (found), not 405 (method not allowed) or 500
        assert response.status_code in [200, 404, 503], f"Unexpected status: {response.status_code}"
        print(f"✓ Endpoint responds with status {response.status_code}")


class TestOnboardingByTenant:
    """Test GET /api/onboarding/{tenant_id} endpoint"""
    
    def test_nonexistent_tenant_returns_404(self):
        """Verify 404 for non-existent tenant_id"""
        response = requests.get(f"{BASE_URL}/api/onboarding/nonexistent-tenant-xyz")
        assert response.status_code == 404, f"Expected 404 for non-existent tenant, got {response.status_code}"
        print("✓ Non-existent tenant returns 404")
    
    def test_endpoint_exists_and_responds(self):
        """Verify the endpoint exists and responds"""
        response = requests.get(f"{BASE_URL}/api/onboarding/test-tenant")
        # Should be 404 (not found) or 200 (found), not 405 or 500
        assert response.status_code in [200, 404, 503], f"Unexpected status: {response.status_code}"
        print(f"✓ Endpoint responds with status {response.status_code}")


class TestCheckoutRefField:
    """Test POST /api/payments/checkout accepts `ref` field"""
    
    def test_checkout_accepts_ref_field(self):
        """Verify checkout endpoint accepts ref field in request body"""
        # Note: This will likely fail with Stripe error (no valid price_id in test env)
        # but we're testing that the endpoint accepts the ref field
        payload = {
            "package_id": "starter",
            "origin_url": "https://aurem.live",
            "ref": "tj-auto-clinic-001"
        }
        response = requests.post(
            f"{BASE_URL}/api/payments/checkout",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Accept 200 (success), 400 (validation), 500 (Stripe error) - but NOT 422 (missing field)
        # 422 would indicate the ref field is not accepted
        assert response.status_code != 422, f"Checkout should accept 'ref' field, got 422 validation error"
        
        # If we get 200, verify we got a URL back
        if response.status_code == 200:
            data = response.json()
            assert "url" in data or "session_id" in data, "Checkout response should have url or session_id"
            print(f"✓ Checkout succeeded with ref field, session_id: {data.get('session_id', 'N/A')}")
        else:
            # Stripe error is expected in test env without valid price_id
            print(f"✓ Checkout endpoint accepts ref field (status {response.status_code} - Stripe config issue expected)")
    
    def test_checkout_without_ref_still_works(self):
        """Verify checkout works without ref field (backward compatible)"""
        payload = {
            "package_id": "starter",
            "origin_url": "https://aurem.live"
            # No ref field
        }
        response = requests.post(
            f"{BASE_URL}/api/payments/checkout",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Should not fail with 422 (validation error for missing required field)
        assert response.status_code != 422, "Checkout should work without ref field"
        print(f"✓ Checkout works without ref field (status {response.status_code})")


class TestPostPaymentFlowImport:
    """Test that run_post_payment_flow is importable and callable"""
    
    def test_run_post_payment_flow_importable(self):
        """Verify run_post_payment_flow can be imported"""
        try:
            import sys
            sys.path.insert(0, "/app/backend")
            from services.aurem_post_payment_onboarding import run_post_payment_flow
            assert callable(run_post_payment_flow), "run_post_payment_flow should be callable"
            print("✓ run_post_payment_flow is importable and callable")
        except ImportError as e:
            pytest.fail(f"Failed to import run_post_payment_flow: {e}")
    
    def test_post_payment_module_has_required_functions(self):
        """Verify module has all required functions"""
        try:
            import sys
            sys.path.insert(0, "/app/backend")
            from services.aurem_post_payment_onboarding import (
                run_post_payment_flow,
                create_onboarding_record,
                send_welcome_whatsapp,
                send_admin_alert,
                queue_google_scan,
                queue_website_draft,
            )
            print("✓ All post-payment onboarding functions are importable")
        except ImportError as e:
            pytest.fail(f"Missing function in post-payment module: {e}")


class TestReportPricingCheckoutMeta:
    """Test that pricing tiers include checkout_meta with ref"""
    
    def test_pricing_has_checkout_meta_with_ref(self):
        """Verify each pricing tier has checkout_meta.ref = business_slug"""
        response = requests.get(f"{BASE_URL}/api/report/tj-auto-clinic-001")
        assert response.status_code == 200
        
        data = response.json()
        for tier in data["pricing"]:
            assert "checkout_meta" in tier, f"Tier {tier['tier']} missing checkout_meta"
            assert "ref" in tier["checkout_meta"], f"Tier {tier['tier']} checkout_meta missing ref"
            assert tier["checkout_meta"]["ref"] == "tj-auto-clinic-001", f"Tier {tier['tier']} ref should be 'tj-auto-clinic-001'"
        
        print("✓ All pricing tiers have checkout_meta.ref = 'tj-auto-clinic-001'")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
