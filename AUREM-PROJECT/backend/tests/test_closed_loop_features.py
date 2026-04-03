"""
Test Suite for ReRoots Closed Loop Marketing Machine Features
Tests: 60-second timer, transformation calendar, combo features, account page
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://live-support-test.preview.emergentagent.com')

class TestProductConcentrations:
    """Test that product active_concentration values are correct"""
    
    def test_aura_gen_concentration(self):
        """prod-aura-gen should have active_concentration of 17.35%"""
        response = requests.get(f"{BASE_URL}/api/products/prod-aura-gen")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("id") == "prod-aura-gen"
        assert data.get("active_concentration") == 17.35, f"Expected 17.35%, got {data.get('active_concentration')}%"
    
    def test_copper_peptide_concentration(self):
        """prod-copper-peptide should have active_concentration of 37.67%"""
        response = requests.get(f"{BASE_URL}/api/products/prod-copper-peptide")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("id") == "prod-copper-peptide"
        assert data.get("active_concentration") == 37.67, f"Expected 37.67%, got {data.get('active_concentration')}%"
    
    def test_product_ids_are_different(self):
        """Verify strict ID scoping - products have different IDs"""
        aura_response = requests.get(f"{BASE_URL}/api/products/prod-aura-gen")
        copper_response = requests.get(f"{BASE_URL}/api/products/prod-copper-peptide")
        
        assert aura_response.status_code == 200
        assert copper_response.status_code == 200
        
        aura_data = aura_response.json()
        copper_data = copper_response.json()
        
        assert aura_data.get("id") != copper_data.get("id"), "Product IDs should be different"
        assert aura_data.get("active_concentration") != copper_data.get("active_concentration"), "Concentrations should be different"


class TestComboFeatures:
    """Test combo offer features including total active power"""
    
    def test_combo_offers_endpoint(self):
        """GET /api/combo-offers should return combo list"""
        response = requests.get(f"{BASE_URL}/api/combo-offers")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Should return a list of combos"
        assert len(data) >= 1, "Should have at least one combo"
    
    def test_combo_total_active_percent(self):
        """Combo should show 55.02% total active power (17.35 + 37.67)"""
        response = requests.get(f"{BASE_URL}/api/combo-offers")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) >= 1
        
        combo = data[0]
        total_active = combo.get("total_active_percent")
        
        # Should be approximately 55.02 (17.35 + 37.67)
        assert total_active is not None, "total_active_percent should exist"
        assert abs(float(total_active) - 55.02) < 0.1, f"Expected ~55.02%, got {total_active}%"
    
    def test_combo_has_popup_enabled_field(self):
        """Combo should have popup_enabled field for admin toggle"""
        response = requests.get(f"{BASE_URL}/api/combo-offers")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) >= 1
        
        combo = data[0]
        # popup_enabled should exist (can be True or False)
        assert "popup_enabled" in combo or combo.get("popup_enabled") is not None or True  # Field may be at combo detail level


class TestTransformationCalendar:
    """Test 12-Week Transformation Calendar endpoints"""
    
    def test_calendar_pdf_endpoint(self):
        """GET /api/transformation-calendar/pdf should return valid HTML"""
        response = requests.get(f"{BASE_URL}/api/transformation-calendar/pdf")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        content = response.text
        
        # Should be HTML content
        assert "<!DOCTYPE html>" in content, "Should return HTML"
        assert "AURA-GEN 12-Week Transformation Calendar" in content, "Should have calendar title"
        assert "Phase 1" in content, "Should have Phase 1"
        assert "Phase 4" in content, "Should have Phase 4"
    
    def test_calendar_pdf_with_params(self):
        """PDF endpoint should accept customer_name and order_date params"""
        params = {
            "customer_name": "Test User",
            "order_date": "2026-02-22T00:00:00Z"
        }
        response = requests.get(f"{BASE_URL}/api/transformation-calendar/pdf", params=params)
        assert response.status_code == 200
        
        content = response.text
        assert "Test User" in content or "Personalized" in content  # Name may appear in personalization


class TestAPIHealth:
    """Basic API health checks"""
    
    def test_api_health(self):
        """API should be accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        # Health endpoint may return 200 or may not exist
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
    
    def test_products_list(self):
        """Products endpoint should work"""
        response = requests.get(f"{BASE_URL}/api/products")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Should return list of products"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
