"""
Test suite for Canadian Postal Code Auto-fill Feature.
Tests the keyless postal code lookup API that auto-fills City and Province
based on Forward Sortation Area (FSA) codes.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://live-support-test.preview.emergentagent.com').rstrip('/')


class TestPostalCodeLookup:
    """Tests for /api/postal-code/lookup endpoint"""

    def test_toronto_postal_code_m5v3l9(self):
        """Test Toronto postal code M5V 3L9 returns Toronto, ON"""
        response = requests.get(f"{BASE_URL}/api/postal-code/lookup", params={"postal_code": "M5V3L9"})
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert data["found"] == True
        assert data["fsa"] == "M5V"
        assert data["city"] == "Toronto"
        assert data["province"] == "ON"
        assert data["province_name"] == "Ontario"

    def test_vancouver_postal_code_v6b1h7(self):
        """Test Vancouver postal code V6B 1H7 returns Vancouver, BC"""
        response = requests.get(f"{BASE_URL}/api/postal-code/lookup", params={"postal_code": "V6B1H7"})
        assert response.status_code == 200
        data = response.json()
        
        assert data["found"] == True
        assert data["fsa"] == "V6B"
        assert data["city"] == "Vancouver"
        assert data["province"] == "BC"
        assert data["province_name"] == "British Columbia"

    def test_calgary_postal_code_t2p3p4(self):
        """Test Calgary postal code T2P 3P4 returns Calgary, AB"""
        response = requests.get(f"{BASE_URL}/api/postal-code/lookup", params={"postal_code": "T2P3P4"})
        assert response.status_code == 200
        data = response.json()
        
        assert data["found"] == True
        assert data["fsa"] == "T2P"
        assert data["city"] == "Calgary"
        assert data["province"] == "AB"
        assert data["province_name"] == "Alberta"

    def test_montreal_postal_code_h3a1a1(self):
        """Test Montreal postal code H3A 1A1 returns Montreal, QC"""
        response = requests.get(f"{BASE_URL}/api/postal-code/lookup", params={"postal_code": "H3A1A1"})
        assert response.status_code == 200
        data = response.json()
        
        assert data["found"] == True
        assert data["fsa"] == "H3A"
        assert data["city"] == "Montreal"
        assert data["province"] == "QC"
        assert data["province_name"] == "Quebec"

    def test_postal_code_with_spaces(self):
        """Test that postal codes with spaces are handled correctly"""
        response = requests.get(f"{BASE_URL}/api/postal-code/lookup", params={"postal_code": "M5V 3L9"})
        assert response.status_code == 200
        data = response.json()
        
        assert data["found"] == True
        assert data["fsa"] == "M5V"
        assert data["city"] == "Toronto"
        assert data["province"] == "ON"

    def test_postal_code_lowercase(self):
        """Test that lowercase postal codes are converted correctly"""
        response = requests.get(f"{BASE_URL}/api/postal-code/lookup", params={"postal_code": "v6b1h7"})
        assert response.status_code == 200
        data = response.json()
        
        assert data["found"] == True
        assert data["fsa"] == "V6B"
        assert data["city"] == "Vancouver"
        assert data["province"] == "BC"

    def test_postal_code_too_short(self):
        """Test that postal codes shorter than 3 characters return found=False"""
        response = requests.get(f"{BASE_URL}/api/postal-code/lookup", params={"postal_code": "M5"})
        assert response.status_code == 200
        data = response.json()
        
        assert data["found"] == False

    def test_postal_code_invalid_first_letter(self):
        """Test that invalid postal code first letters return found=False"""
        # D, F, I, O, Q, U, W, Z are not valid Canadian postal code first letters
        response = requests.get(f"{BASE_URL}/api/postal-code/lookup", params={"postal_code": "D1A1A1"})
        assert response.status_code == 200
        data = response.json()
        
        assert data["found"] == False

    def test_ottawa_postal_code_k1a(self):
        """Test Ottawa postal code K1A returns Ottawa, ON"""
        response = requests.get(f"{BASE_URL}/api/postal-code/lookup", params={"postal_code": "K1A0B1"})
        assert response.status_code == 200
        data = response.json()
        
        assert data["found"] == True
        assert data["fsa"] == "K1A"
        assert data["city"] == "Ottawa"
        assert data["province"] == "ON"

    def test_edmonton_postal_code_t5j(self):
        """Test Edmonton postal code T5J returns Edmonton, AB"""
        response = requests.get(f"{BASE_URL}/api/postal-code/lookup", params={"postal_code": "T5J2R1"})
        assert response.status_code == 200
        data = response.json()
        
        assert data["found"] == True
        assert data["fsa"] == "T5J"
        assert data["city"] == "Edmonton"
        assert data["province"] == "AB"

    def test_fsa_only_returns_province_when_city_not_mapped(self):
        """Test that FSA with unmapped city still returns province"""
        # Using a less common FSA that might not have a city mapping
        response = requests.get(f"{BASE_URL}/api/postal-code/lookup", params={"postal_code": "X0A0A0"})
        assert response.status_code == 200
        data = response.json()
        
        # Even if city is None, province should be returned
        assert data["found"] == True
        assert data["province"] == "NT"  # Northwest Territories
        assert data["province_name"] == "Northwest Territories"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
