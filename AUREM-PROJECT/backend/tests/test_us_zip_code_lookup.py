"""
US ZIP Code Auto-Fill Backend API Tests

Tests the /api/zip-code/lookup endpoint which enables auto-filling
City and State fields for US addresses during checkout.
"""
import pytest
import requests
import os

# Get BASE_URL from environment - MUST use public URL for testing
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL not set in environment")


class TestUSZipCodeLookup:
    """Tests for US ZIP code lookup API endpoint"""

    # Test major US cities - as specified in requirements
    def test_new_york_zip_10001(self):
        """New York ZIP 10001 returns city=New York, state=NY"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "10001"})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data["found"] == True, "Expected found=True"
        assert data["city"] == "New York", f"Expected city='New York', got '{data.get('city')}'"
        assert data["state"] == "NY", f"Expected state='NY', got '{data.get('state')}'"
        print(f"PASS: 10001 -> {data['city']}, {data['state']}")

    def test_los_angeles_zip_90001(self):
        """Los Angeles ZIP 90001 returns city=Los Angeles, state=CA"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "90001"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "Los Angeles", f"Expected city='Los Angeles', got '{data.get('city')}'"
        assert data["state"] == "CA", f"Expected state='CA', got '{data.get('state')}'"
        print(f"PASS: 90001 -> {data['city']}, {data['state']}")

    def test_chicago_zip_60601(self):
        """Chicago ZIP 60601 returns city=Chicago, state=IL"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "60601"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "Chicago", f"Expected city='Chicago', got '{data.get('city')}'"
        assert data["state"] == "IL", f"Expected state='IL', got '{data.get('state')}'"
        print(f"PASS: 60601 -> {data['city']}, {data['state']}")

    def test_seattle_zip_98101(self):
        """Seattle ZIP 98101 returns city=Seattle, state=WA"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "98101"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "Seattle", f"Expected city='Seattle', got '{data.get('city')}'"
        assert data["state"] == "WA", f"Expected state='WA', got '{data.get('state')}'"
        print(f"PASS: 98101 -> {data['city']}, {data['state']}")

    def test_miami_zip_33101(self):
        """Miami ZIP 33101 returns city=Miami, state=FL"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "33101"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "Miami", f"Expected city='Miami', got '{data.get('city')}'"
        assert data["state"] == "FL", f"Expected state='FL', got '{data.get('state')}'"
        print(f"PASS: 33101 -> {data['city']}, {data['state']}")

    def test_unknown_zip_returns_state_only(self):
        """Unknown ZIP with valid prefix (12345) returns state=NY only (no city)"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "12345"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True, "Expected found=True for valid state prefix"
        assert data["state"] == "NY", f"Expected state='NY', got '{data.get('state')}'"
        # City might be None or empty for unknown ZIP
        print(f"PASS: 12345 -> city={data.get('city')}, state={data['state']}")

    def test_invalid_zip_00000(self):
        """Invalid ZIP 00000 returns found=false"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "00000"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == False, f"Expected found=False for 00000, got {data.get('found')}"
        print(f"PASS: 00000 -> found=False")


class TestAdditionalUSCities:
    """Tests for additional major US cities in the mapping"""
    
    def test_houston_zip_77001(self):
        """Houston ZIP 77001 returns city=Houston, state=TX"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "77001"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "Houston"
        assert data["state"] == "TX"
        print(f"PASS: 77001 -> {data['city']}, {data['state']}")

    def test_phoenix_zip_85001(self):
        """Phoenix ZIP 85001 returns city=Phoenix, state=AZ"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "85001"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "Phoenix"
        assert data["state"] == "AZ"
        print(f"PASS: 85001 -> {data['city']}, {data['state']}")

    def test_san_francisco_zip_94102(self):
        """San Francisco ZIP 94102 returns city=San Francisco, state=CA"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "94102"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "San Francisco"
        assert data["state"] == "CA"
        print(f"PASS: 94102 -> {data['city']}, {data['state']}")

    def test_denver_zip_80202(self):
        """Denver ZIP 80202 returns city=Denver, state=CO"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "80202"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "Denver"
        assert data["state"] == "CO"
        print(f"PASS: 80202 -> {data['city']}, {data['state']}")

    def test_boston_zip_02101(self):
        """Boston ZIP 02101 returns city=Boston, state=MA"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "02101"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "Boston"
        assert data["state"] == "MA"
        print(f"PASS: 02101 -> {data['city']}, {data['state']}")

    def test_dallas_zip_75201(self):
        """Dallas ZIP 75201 returns city=Dallas, state=TX"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "75201"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "Dallas"
        assert data["state"] == "TX"
        print(f"PASS: 75201 -> {data['city']}, {data['state']}")

    def test_atlanta_zip_30301(self):
        """Atlanta ZIP 30301 returns city=Atlanta, state=GA"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "30301"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "Atlanta"
        assert data["state"] == "GA"
        print(f"PASS: 30301 -> {data['city']}, {data['state']}")

    def test_san_diego_zip_92101(self):
        """San Diego ZIP 92101 returns city=San Diego, state=CA"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "92101"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "San Diego"
        assert data["state"] == "CA"
        print(f"PASS: 92101 -> {data['city']}, {data['state']}")

    def test_austin_zip_78701(self):
        """Austin ZIP 78701 returns city=Austin, state=TX"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "78701"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "Austin"
        assert data["state"] == "TX"
        print(f"PASS: 78701 -> {data['city']}, {data['state']}")

    def test_washington_dc_zip_20001(self):
        """Washington DC ZIP 20001 returns city=Washington, state=DC"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "20001"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "Washington"
        assert data["state"] == "DC"
        print(f"PASS: 20001 -> {data['city']}, {data['state']}")

    def test_las_vegas_zip_89101(self):
        """Las Vegas ZIP 89101 returns city=Las Vegas, state=NV"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "89101"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "Las Vegas"
        assert data["state"] == "NV"
        print(f"PASS: 89101 -> {data['city']}, {data['state']}")

    def test_portland_zip_97201(self):
        """Portland ZIP 97201 returns city=Portland, state=OR"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "97201"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "Portland"
        assert data["state"] == "OR"
        print(f"PASS: 97201 -> {data['city']}, {data['state']}")

    def test_philadelphia_zip_19102(self):
        """Philadelphia ZIP 19102 returns city=Philadelphia, state=PA"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "19102"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "Philadelphia"
        assert data["state"] == "PA"
        print(f"PASS: 19102 -> {data['city']}, {data['state']}")


class TestCanadianPostalCodeStillWorks:
    """Verify Canadian postal code lookup still works alongside US ZIP"""
    
    def test_toronto_postal_m5v(self):
        """Canadian postal code M5V returns Toronto, ON"""
        response = requests.get(f"{BASE_URL}/api/postal-code/lookup", params={"postal_code": "M5V"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "Toronto"
        assert data["province"] == "ON"
        print(f"PASS: M5V -> {data['city']}, {data['province']}")


class TestUSZipCodeEdgeCases:
    """Edge case tests for US ZIP code lookup"""

    def test_zip_with_dash(self):
        """ZIP with dash (e.g., 10001-1234) is handled correctly"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "10001-1234"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "New York"
        assert data["state"] == "NY"
        print(f"PASS: 10001-1234 -> {data['city']}, {data['state']}")

    def test_zip_with_spaces(self):
        """ZIP with spaces is handled correctly"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "100 01"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["city"] == "New York"
        assert data["state"] == "NY"
        print(f"PASS: '100 01' -> {data['city']}, {data['state']}")

    def test_3_digit_prefix_only(self):
        """3-digit prefix returns state only"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "981"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["state"] == "WA"
        print(f"PASS: 981 -> state={data['state']}")

    def test_too_short_zip(self):
        """ZIP code less than 3 digits returns found=False"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "12"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == False
        print(f"PASS: '12' -> found=False")

    def test_non_numeric_zip(self):
        """Non-numeric ZIP returns found=False"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "ABCDE"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == False
        print(f"PASS: 'ABCDE' -> found=False")

    def test_state_name_included(self):
        """Response includes state_name (full name)"""
        response = requests.get(f"{BASE_URL}/api/zip-code/lookup", params={"zip_code": "10001"})
        assert response.status_code == 200
        data = response.json()
        assert data["found"] == True
        assert data["state_name"] == "New York"
        print(f"PASS: 10001 -> state_name={data['state_name']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
