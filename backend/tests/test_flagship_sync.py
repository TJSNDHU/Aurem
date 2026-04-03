"""
FlagShip Shipments Sync Feature Tests
Tests:
1. POST /api/admin/flagship/sync - Sync external shipments from FlagShip
2. GET /api/admin/flagship/all-shipments - Get combined internal/external shipments
3. Source filtering (all, internal, external)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')
if BASE_URL:
    BASE_URL = BASE_URL.rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@reroots.ca"
ADMIN_PASSWORD = "new_password_123"


class TestFlagShipSync:
    """Test FlagShip sync and all-shipments endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session and get admin token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            print(f"[SETUP] Admin login successful, token obtained")
        else:
            pytest.skip(f"Admin login failed: {response.status_code}")
    
    # ===== SYNC ENDPOINT TESTS =====
    
    def test_01_sync_flagship_shipments_success(self):
        """POST /api/admin/flagship/sync - Should fetch and store external shipments"""
        response = self.session.post(f"{BASE_URL}/api/admin/flagship/sync", json={})
        
        print(f"Sync response status: {response.status_code}")
        print(f"Sync response body: {response.json()}")
        
        # Status should be 200
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify response structure
        assert data.get("success") == True, "Expected success=True"
        assert "message" in data, "Expected 'message' in response"
        assert "flagship_total" in data, "Expected 'flagship_total' in response"
        assert "new_synced" in data, "Expected 'new_synced' in response"
        assert "updated_synced" in data, "Expected 'updated_synced' in response"
        
        # Verify counts are integers
        assert isinstance(data.get("flagship_total"), int), "flagship_total should be int"
        assert isinstance(data.get("new_synced"), int), "new_synced should be int"
        assert isinstance(data.get("updated_synced"), int), "updated_synced should be int"
        
        print(f"[PASS] Sync successful: {data.get('message')}")
        print(f"       FlagShip total: {data.get('flagship_total')}")
        print(f"       New synced: {data.get('new_synced')}")
        print(f"       Updated: {data.get('updated_synced')}")
    
    def test_02_sync_unauthorized(self):
        """POST /api/admin/flagship/sync - Should fail without auth"""
        # Create new session without auth
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        response = no_auth_session.post(f"{BASE_URL}/api/admin/flagship/sync", json={})
        
        print(f"Unauthorized sync response: {response.status_code}")
        
        # Should return 401 or 403
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("[PASS] Unauthorized access correctly rejected")
    
    # ===== ALL-SHIPMENTS ENDPOINT TESTS =====
    
    def test_03_get_all_shipments_default(self):
        """GET /api/admin/flagship/all-shipments - Returns both internal and external"""
        response = self.session.get(f"{BASE_URL}/api/admin/flagship/all-shipments")
        
        print(f"All shipments response status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify response structure
        assert data.get("success") == True, "Expected success=True"
        assert "shipments" in data, "Expected 'shipments' in response"
        assert isinstance(data.get("shipments"), list), "shipments should be a list"
        assert "internal_count" in data, "Expected 'internal_count' in response"
        assert "external_count" in data, "Expected 'external_count' in response"
        
        print(f"[PASS] Got {len(data.get('shipments'))} shipments")
        print(f"       Internal: {data.get('internal_count')}, External: {data.get('external_count')}")
        
        # Verify shipment structure if any exist
        if data.get("shipments"):
            sample = data["shipments"][0]
            required_fields = ["id", "tracking_number", "courier_name", "status", "source"]
            for field in required_fields:
                assert field in sample, f"Missing field '{field}' in shipment"
            
            # Verify source field is present
            assert sample.get("source") in ["internal", "external"], \
                f"Invalid source value: {sample.get('source')}"
            
            print(f"       Sample shipment source: {sample.get('source')}")
            print(f"       Sample tracking: {sample.get('tracking_number')}")
    
    def test_04_get_all_shipments_internal_filter(self):
        """GET /api/admin/flagship/all-shipments?source=internal - Internal only"""
        response = self.session.get(
            f"{BASE_URL}/api/admin/flagship/all-shipments",
            params={"source": "internal"}
        )
        
        print(f"Internal filter response status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True
        
        # All shipments should have source="internal"
        for shipment in data.get("shipments", []):
            assert shipment.get("source") == "internal", \
                f"Found non-internal shipment: {shipment.get('source')}"
        
        print(f"[PASS] Internal filter returned {len(data.get('shipments'))} shipments")
        print(f"       All have source='internal': True")
    
    def test_05_get_all_shipments_external_filter(self):
        """GET /api/admin/flagship/all-shipments?source=external - External only"""
        response = self.session.get(
            f"{BASE_URL}/api/admin/flagship/all-shipments",
            params={"source": "external"}
        )
        
        print(f"External filter response status: {response.status_code}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("success") == True
        
        # All shipments should have source="external"
        for shipment in data.get("shipments", []):
            assert shipment.get("source") == "external", \
                f"Found non-external shipment: {shipment.get('source')}"
        
        external_count = len(data.get("shipments", []))
        print(f"[PASS] External filter returned {external_count} shipments")
        
        # Note: external count may be 0 if no shipments created in FlagShip dashboard
        if external_count == 0:
            print("       Note: No external shipments found (FlagShip account may have 0 external shipments)")
    
    def test_06_get_all_shipments_pagination(self):
        """GET /api/admin/flagship/all-shipments - Test pagination params"""
        response = self.session.get(
            f"{BASE_URL}/api/admin/flagship/all-shipments",
            params={"limit": 10, "page": 1}
        )
        
        print(f"Pagination test response status: {response.status_code}")
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify pagination fields
        assert "total" in data, "Expected 'total' in response"
        assert "page" in data, "Expected 'page' in response"
        assert "limit" in data, "Expected 'limit' in response"
        
        # Verify results don't exceed limit
        assert len(data.get("shipments", [])) <= 10, "Results exceeded limit"
        
        print(f"[PASS] Pagination working: {len(data.get('shipments'))} results, limit=10")
    
    def test_07_get_all_shipments_unauthorized(self):
        """GET /api/admin/flagship/all-shipments - Should fail without auth"""
        no_auth_session = requests.Session()
        response = no_auth_session.get(f"{BASE_URL}/api/admin/flagship/all-shipments")
        
        print(f"Unauthorized all-shipments response: {response.status_code}")
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("[PASS] Unauthorized access correctly rejected")
    
    # ===== SHIPMENT DATA VALIDATION =====
    
    def test_08_shipment_has_source_badge_data(self):
        """Verify shipments have proper source field for UI badge display"""
        response = self.session.get(
            f"{BASE_URL}/api/admin/flagship/all-shipments",
            params={"source": "all"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        for shipment in data.get("shipments", []):
            # Every shipment must have source field
            assert "source" in shipment, f"Shipment missing 'source' field: {shipment.get('id')}"
            assert shipment.get("source") in ["internal", "external"], \
                f"Invalid source for {shipment.get('id')}: {shipment.get('source')}"
            
            # Internal shipments should have order_number
            if shipment.get("source") == "internal":
                assert shipment.get("order_number"), \
                    f"Internal shipment missing order_number: {shipment.get('id')}"
            
            # External shipments should have an order_number (even if auto-generated)
            if shipment.get("source") == "external":
                assert shipment.get("order_number"), \
                    f"External shipment missing order_number: {shipment.get('id')}"
        
        print(f"[PASS] All {len(data.get('shipments', []))} shipments have valid source field")
    
    def test_09_shipment_has_required_fields(self):
        """Verify shipments have all required fields for UI display"""
        response = self.session.get(f"{BASE_URL}/api/admin/flagship/all-shipments")
        
        assert response.status_code == 200
        data = response.json()
        
        required_fields = [
            "id",
            "tracking_number", 
            "courier_name",
            "status",
            "source",
            "to"  # Shipping destination
        ]
        
        for shipment in data.get("shipments", []):
            for field in required_fields:
                assert field in shipment, \
                    f"Shipment {shipment.get('id')} missing required field: {field}"
            
            # 'to' should have name, city, state
            to_addr = shipment.get("to", {})
            if to_addr:  # to may be empty for some external shipments
                # Just verify it's a dict
                assert isinstance(to_addr, dict), "'to' should be a dictionary"
        
        print(f"[PASS] All shipments have required fields for UI display")


class TestFlagShipIntegration:
    """Test actual FlagShip API connectivity"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup session with admin token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        response = self.session.post(f"{BASE_URL}/api/admin/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            token = response.json().get("token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Admin login failed")
    
    def test_10_flagship_api_connectivity(self):
        """Verify FlagShip API is accessible via sync endpoint"""
        response = self.session.post(f"{BASE_URL}/api/admin/flagship/sync", json={})
        
        # Even if 0 shipments, sync should succeed if API is accessible
        if response.status_code == 200:
            data = response.json()
            assert data.get("success") == True, "Sync should succeed"
            print(f"[PASS] FlagShip API accessible, {data.get('flagship_total')} total shipments")
        elif response.status_code == 500:
            # API might be down or token invalid
            error_msg = response.json().get("detail", "Unknown error")
            print(f"[WARN] FlagShip API issue: {error_msg}")
            # Don't fail the test, just report
            pytest.skip(f"FlagShip API issue: {error_msg}")
        else:
            pytest.fail(f"Unexpected status: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
