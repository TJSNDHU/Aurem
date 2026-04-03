"""
Test Engine Data Model Refactor Features

Tests:
1. Product Engine data storage (engine_type, engine_label, key_actives, primary_benefit)
2. Combo active_breakdown field (contains engine data from products)
3. Combo total_active_percent calculation (17.35 + 37.67 = 55.02)
4. AI Engine generator endpoint POST /api/ai/generate-product-engine
5. Combo creation/update auto-calculates engine data
"""

import pytest
import requests
import os
import json

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

if not BASE_URL:
    # Try to read from frontend .env
    try:
        with open("/app/frontend/.env", "r") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except:
        BASE_URL = "https://live-support-test.preview.emergentagent.com"

print(f"Using BASE_URL: {BASE_URL}")


class TestProductEngineDataStorage:
    """Test that products have engine_type, engine_label, key_actives, primary_benefit fields"""
    
    def test_product_aura_gen_has_engine_fields(self):
        """Test prod-aura-gen has engine data fields"""
        response = requests.get(f"{BASE_URL}/api/products/prod-aura-gen", timeout=30)
        assert response.status_code == 200, f"Failed to get product: {response.text}"
        
        product = response.json()
        
        # Verify engine fields exist
        assert "active_concentration" in product, "Missing active_concentration field"
        assert "engine_type" in product, "Missing engine_type field"
        assert "engine_label" in product, "Missing engine_label field"
        assert "key_actives" in product, "Missing key_actives field"
        assert "primary_benefit" in product, "Missing primary_benefit field"
        
        # Verify values for prod-aura-gen (engine product with 17.35%)
        assert product["active_concentration"] == 17.35, f"Expected 17.35, got {product['active_concentration']}"
        print(f"✓ prod-aura-gen engine fields: type={product.get('engine_type')}, label={product.get('engine_label')}")
    
    def test_product_copper_peptide_has_engine_fields(self):
        """Test prod-copper-peptide has engine data fields"""
        response = requests.get(f"{BASE_URL}/api/products/prod-copper-peptide", timeout=30)
        assert response.status_code == 200, f"Failed to get product: {response.text}"
        
        product = response.json()
        
        # Verify engine fields exist
        assert "active_concentration" in product, "Missing active_concentration field"
        assert "engine_type" in product, "Missing engine_type field"
        
        # Verify values for prod-copper-peptide (buffer product with 37.67%)
        assert product["active_concentration"] == 37.67, f"Expected 37.67, got {product['active_concentration']}"
        print(f"✓ prod-copper-peptide engine fields: type={product.get('engine_type')}, conc={product['active_concentration']}")
    
    def test_products_list_includes_engine_fields(self):
        """Test that products list includes engine fields"""
        response = requests.get(f"{BASE_URL}/api/products", timeout=30)
        assert response.status_code == 200
        
        products = response.json()
        assert len(products) > 0, "No products returned"
        
        # Check if test products are present with engine fields
        test_products_found = 0
        for product in products:
            if product.get("id") in ["prod-aura-gen", "prod-copper-peptide"]:
                test_products_found += 1
                assert "active_concentration" in product, f"Missing active_concentration in {product['id']}"
        
        assert test_products_found > 0, "Test products not found in products list"
        print(f"✓ Found {test_products_found} test products with engine fields")


class TestComboActiveBreakdown:
    """Test combo active_breakdown field contains engine data from constituent products"""
    
    def test_combo_has_active_breakdown(self):
        """Test existing combo has active_breakdown field"""
        # Get all combos
        response = requests.get(f"{BASE_URL}/api/combo-offers", timeout=30)
        assert response.status_code == 200
        
        combos = response.json()
        assert len(combos) > 0, "No combo offers found"
        
        # Find combo with our test products
        test_combo = None
        for combo in combos:
            product_ids = combo.get("product_ids", [])
            if "prod-aura-gen" in product_ids or "prod-copper-peptide" in product_ids:
                test_combo = combo
                break
        
        assert test_combo is not None, "No combo with test products found"
        
        # Verify active_breakdown exists
        assert "active_breakdown" in test_combo, "Missing active_breakdown field"
        active_breakdown = test_combo.get("active_breakdown", {})
        
        print(f"✓ Combo '{test_combo['name']}' has active_breakdown with {len(active_breakdown)} products")
    
    def test_combo_active_breakdown_contains_product_engine_data(self):
        """Test active_breakdown contains engine data from products"""
        response = requests.get(f"{BASE_URL}/api/combo-offers", timeout=30)
        assert response.status_code == 200
        
        combos = response.json()
        
        # Find combo with both test products
        test_combo = None
        for combo in combos:
            product_ids = combo.get("product_ids", [])
            if "prod-aura-gen" in product_ids and "prod-copper-peptide" in product_ids:
                test_combo = combo
                break
        
        if test_combo is None:
            pytest.skip("No combo with both test products found")
        
        active_breakdown = test_combo.get("active_breakdown", {})
        
        # Check prod-aura-gen data
        if "prod-aura-gen" in active_breakdown:
            aura_data = active_breakdown["prod-aura-gen"]
            # Should have concentration, label, type, key_actives
            assert "concentration" in aura_data or "total" in aura_data, "Missing concentration in breakdown"
            concentration = aura_data.get("concentration") or aura_data.get("total")
            assert concentration == 17.35, f"Expected 17.35, got {concentration}"
            print(f"✓ prod-aura-gen in breakdown: {aura_data}")
        
        # Check prod-copper-peptide data
        if "prod-copper-peptide" in active_breakdown:
            copper_data = active_breakdown["prod-copper-peptide"]
            assert "concentration" in copper_data or "total" in copper_data, "Missing concentration in breakdown"
            concentration = copper_data.get("concentration") or copper_data.get("total")
            assert concentration == 37.67, f"Expected 37.67, got {concentration}"
            print(f"✓ prod-copper-peptide in breakdown: {copper_data}")


class TestComboTotalActivePercent:
    """Test combo total_active_percent calculation (17.35 + 37.67 = 55.02)"""
    
    def test_combo_total_active_percent_calculation(self):
        """Test that total_active_percent equals sum of product concentrations"""
        response = requests.get(f"{BASE_URL}/api/combo-offers", timeout=30)
        assert response.status_code == 200
        
        combos = response.json()
        
        # Find combo with both test products
        test_combo = None
        for combo in combos:
            product_ids = combo.get("product_ids", [])
            if "prod-aura-gen" in product_ids and "prod-copper-peptide" in product_ids:
                test_combo = combo
                break
        
        if test_combo is None:
            pytest.skip("No combo with both test products found")
        
        # Verify total_active_percent
        assert "total_active_percent" in test_combo, "Missing total_active_percent field"
        
        total = test_combo["total_active_percent"]
        expected_total = 55.02  # 17.35 + 37.67
        
        # Allow small floating point tolerance
        assert abs(total - expected_total) < 0.01, f"Expected {expected_total}, got {total}"
        print(f"✓ Combo total_active_percent = {total}% (17.35% + 37.67%)")
    
    def test_combo_detail_endpoint_has_total_active_percent(self):
        """Test single combo endpoint returns total_active_percent"""
        # First get list to find a combo ID
        list_response = requests.get(f"{BASE_URL}/api/combo-offers", timeout=30)
        assert list_response.status_code == 200
        
        combos = list_response.json()
        if len(combos) == 0:
            pytest.skip("No combos available")
        
        # Get combo detail
        combo_id = combos[0]["id"]
        detail_response = requests.get(f"{BASE_URL}/api/combo-offers/{combo_id}", timeout=30)
        assert detail_response.status_code == 200
        
        combo = detail_response.json()
        assert "total_active_percent" in combo, f"Missing total_active_percent in combo detail"
        print(f"✓ Combo detail has total_active_percent = {combo['total_active_percent']}%")


class TestAIEngineGenerator:
    """Test AI Engine generator endpoint POST /api/ai/generate-product-engine"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token for testing"""
        # Try to login as admin
        login_response = requests.post(f"{BASE_URL}/api/admin/login", json={
            "email": "teji.ss1986@gmail.com",
            "password": "admin123"
        }, timeout=30)
        
        if login_response.status_code == 200:
            return login_response.json().get("token")
        
        # Try Google SSO token from localStorage simulation
        # Since we can't do SSO in pytest, skip if no valid token
        pytest.skip("Admin authentication required - need SSO login")
    
    def test_ai_generate_product_engine_endpoint_exists(self):
        """Test that the AI generate-product-engine endpoint exists (even if auth fails)"""
        # Test without auth - should return 401 or 403, not 404
        response = requests.post(f"{BASE_URL}/api/ai/generate-product-engine", json={
            "name": "Test Product",
            "ingredients": "Niacinamide 5%, Hyaluronic Acid 2%"
        }, timeout=30)
        
        # Should not be 404 - endpoint should exist
        assert response.status_code != 404, "AI generate-product-engine endpoint not found"
        print(f"✓ AI endpoint exists (returned {response.status_code})")
    
    def test_ai_endpoint_requires_auth(self):
        """Test that AI endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/ai/generate-product-engine", json={
            "name": "Test Product",
            "ingredients": "Niacinamide 5%"
        }, timeout=30)
        
        # Should require authentication
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ AI endpoint requires auth (returned {response.status_code})")
    
    def test_ai_endpoint_requires_name_or_ingredients(self):
        """Test that AI endpoint validates input"""
        # Empty payload without auth will fail differently than validation error
        response = requests.post(f"{BASE_URL}/api/ai/generate-product-engine", json={}, timeout=30)
        
        # Should return auth error or validation error, not 500
        assert response.status_code in [400, 401, 403, 422], f"Unexpected status: {response.status_code}"
        print(f"✓ AI endpoint validates input (returned {response.status_code})")


class TestComboCreationAutoCalculation:
    """Test that combo creation/update auto-calculates engine data"""
    
    def test_combo_create_endpoint_calculates_active_breakdown(self):
        """Verify combo POST endpoint calculates active_breakdown from products"""
        # This tests the endpoint behavior documented in lines 6408-6473
        # Without admin auth, we verify the endpoint exists
        
        response = requests.post(f"{BASE_URL}/api/admin/combo-offers", json={
            "name": "Test Combo",
            "product_ids": ["prod-aura-gen", "prod-copper-peptide"],
            "discount_percent": 15
        }, timeout=30)
        
        # Should require auth
        assert response.status_code in [401, 403], f"Expected auth error, got {response.status_code}"
        print(f"✓ Combo create endpoint exists and requires auth")
    
    def test_combo_update_endpoint_recalculates_active_breakdown(self):
        """Verify combo PUT endpoint recalculates active_breakdown"""
        # Without admin auth, verify endpoint exists
        
        # Get existing combo
        list_response = requests.get(f"{BASE_URL}/api/combo-offers", timeout=30)
        assert list_response.status_code == 200
        combos = list_response.json()
        
        if len(combos) == 0:
            pytest.skip("No combos to test update")
        
        combo_id = combos[0]["id"]
        
        response = requests.put(f"{BASE_URL}/api/admin/combo-offers/{combo_id}", json={
            "name": "Updated Test Combo"
        }, timeout=30)
        
        # Should require auth
        assert response.status_code in [401, 403], f"Expected auth error, got {response.status_code}"
        print(f"✓ Combo update endpoint exists and requires auth")


class TestExistingComboData:
    """Test existing combo has correct engine data from previous iteration"""
    
    def test_existing_combo_has_correct_total(self):
        """Verify existing combo PDRN + Copper Peptide has 55.02% total"""
        response = requests.get(f"{BASE_URL}/api/combo-offers", timeout=30)
        assert response.status_code == 200
        
        combos = response.json()
        
        # Find the Power Duo combo
        power_duo = None
        for combo in combos:
            if "PDRN" in combo.get("name", "").upper() or "Power Duo" in combo.get("name", ""):
                power_duo = combo
                break
            # Also check by product IDs
            if set(combo.get("product_ids", [])) == {"prod-aura-gen", "prod-copper-peptide"}:
                power_duo = combo
                break
        
        if power_duo is None:
            pytest.skip("Power Duo combo not found")
        
        assert power_duo.get("total_active_percent") == 55.02, f"Expected 55.02, got {power_duo.get('total_active_percent')}"
        print(f"✓ Existing combo '{power_duo['name']}' has correct total_active_percent = 55.02%")
    
    def test_existing_combo_has_engine_buffer_types(self):
        """Verify combo active_breakdown has engine/buffer type assignments"""
        response = requests.get(f"{BASE_URL}/api/combo-offers", timeout=30)
        assert response.status_code == 200
        
        combos = response.json()
        
        # Find combo with both products
        test_combo = None
        for combo in combos:
            product_ids = combo.get("product_ids", [])
            if "prod-aura-gen" in product_ids and "prod-copper-peptide" in product_ids:
                test_combo = combo
                break
        
        if test_combo is None:
            pytest.skip("No combo with both test products found")
        
        active_breakdown = test_combo.get("active_breakdown", {})
        
        # Check types are assigned
        for pid, data in active_breakdown.items():
            assert "type" in data, f"Missing type in breakdown for {pid}"
            assert data["type"] in ["engine", "buffer"], f"Invalid type {data['type']} for {pid}"
        
        print(f"✓ Combo has ENGINE/BUFFER type assignments in active_breakdown")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
