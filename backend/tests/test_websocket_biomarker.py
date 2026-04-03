"""
Test WebSocket status endpoint and Biomarker Benchmarks CRUD operations.
Features tested:
- WebSocket connection status endpoint
- Biomarker Benchmarks CRUD (Create, Read, Update, Delete)
- Biomarker Categories endpoint
"""
import pytest
import requests
import os
import uuid

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@reroots.ca"
ADMIN_PASSWORD = "new_password_123"

class TestWebSocketAndBiomarkerEndpoints:
    """Test WebSocket status and Biomarker Benchmarks endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        token = response.json().get("token")
        assert token, "No token returned from login"
        return {"Authorization": f"Bearer {token}"}
    
    # ============== WebSocket Status Tests ==============
    
    def test_websocket_status_endpoint(self, auth_headers):
        """Test GET /api/admin/websocket/status returns connection count"""
        response = requests.get(
            f"{BASE_URL}/api/admin/websocket/status", 
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"WebSocket status failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "connections" in data, "Missing 'connections' in response"
        assert "timestamp" in data, "Missing 'timestamp' in response"
        
        connections = data["connections"]
        assert "total" in connections, "Missing 'total' in connections"
        assert "admin" in connections, "Missing 'admin' in connections"
        assert "user" in connections, "Missing 'user' in connections"
        
        print(f"✓ WebSocket status: {connections['total']} total, {connections['admin']} admin, {connections['user']} user")
    
    def test_websocket_status_requires_auth(self):
        """Test WebSocket status endpoint requires admin authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/websocket/status")
        # API returns 401 or 403 depending on auth middleware
        assert response.status_code in [401, 403], f"WebSocket status should require auth, got {response.status_code}"
        print("✓ WebSocket status correctly requires authentication")
    
    # ============== Biomarker Categories Tests ==============
    
    def test_get_biomarker_categories(self, auth_headers):
        """Test GET /api/admin/biomarker-benchmarks/categories"""
        response = requests.get(
            f"{BASE_URL}/api/admin/biomarker-benchmarks/categories",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Get categories failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "categories" in data, "Missing 'categories' in response"
        categories = data["categories"]
        
        # Check default categories exist
        category_values = [cat["value"] for cat in categories]
        expected_categories = ["skin_age", "hydration", "elasticity", "pigmentation", "texture", "inflammation", "general"]
        
        for expected in expected_categories:
            assert expected in category_values, f"Missing category: {expected}"
        
        print(f"✓ Categories endpoint returned {len(categories)} categories: {category_values}")
    
    # ============== Biomarker Benchmarks CRUD Tests ==============
    
    def test_get_biomarker_benchmarks(self, auth_headers):
        """Test GET /api/admin/biomarker-benchmarks returns list"""
        response = requests.get(
            f"{BASE_URL}/api/admin/biomarker-benchmarks",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Get benchmarks failed: {response.text}"
        data = response.json()
        
        assert "benchmarks" in data, "Missing 'benchmarks' in response"
        assert "count" in data, "Missing 'count' in response"
        
        print(f"✓ GET benchmarks returned {data['count']} benchmarks")
        return data
    
    def test_create_biomarker_benchmark(self, auth_headers):
        """Test POST /api/admin/biomarker-benchmarks creates a new benchmark"""
        unique_id = str(uuid.uuid4())[:8]
        benchmark_data = {
            "name": f"TEST_Hydration_Level_{unique_id}",
            "category": "hydration",
            "unit": "%",
            "low_threshold": 20,
            "optimal_min": 40,
            "optimal_max": 70,
            "high_threshold": 90,
            "low_label": "Dehydrated",
            "optimal_label": "Well Hydrated",
            "high_label": "Excess Moisture",
            "low_advice": "Increase water intake and use hydrating products",
            "optimal_advice": "Maintain current skincare routine",
            "high_advice": "Consider lighter moisturizers",
            "color_low": "#EF4444",
            "color_optimal": "#22C55E",
            "color_high": "#F59E0B",
            "is_active": True
        }
        
        response = requests.post(
            f"{BASE_URL}/api/admin/biomarker-benchmarks",
            headers=auth_headers,
            json=benchmark_data
        )
        
        assert response.status_code == 200, f"Create benchmark failed: {response.text}"
        data = response.json()
        
        assert data.get("success") == True, "Create response should have success=True"
        assert "benchmark" in data, "Missing 'benchmark' in response"
        
        created = data["benchmark"]
        assert "id" in created, "Created benchmark missing 'id'"
        assert created["name"] == benchmark_data["name"], "Name mismatch"
        assert created["category"] == benchmark_data["category"], "Category mismatch"
        assert created["unit"] == benchmark_data["unit"], "Unit mismatch"
        
        print(f"✓ Created benchmark: {created['name']} (ID: {created['id']})")
        return created["id"]
    
    def test_get_single_biomarker_benchmark(self, auth_headers):
        """Test GET /api/admin/biomarker-benchmarks/{id} returns single benchmark"""
        # First create a benchmark
        unique_id = str(uuid.uuid4())[:8]
        create_data = {
            "name": f"TEST_SingleGet_{unique_id}",
            "category": "elasticity",
            "unit": "score"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/admin/biomarker-benchmarks",
            headers=auth_headers,
            json=create_data
        )
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        benchmark_id = create_response.json()["benchmark"]["id"]
        
        # Now get the single benchmark
        response = requests.get(
            f"{BASE_URL}/api/admin/biomarker-benchmarks/{benchmark_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Get single benchmark failed: {response.text}"
        data = response.json()
        
        assert data["id"] == benchmark_id, "ID mismatch"
        assert data["name"] == create_data["name"], "Name mismatch"
        assert data["category"] == create_data["category"], "Category mismatch"
        
        print(f"✓ Got single benchmark: {data['name']} (ID: {data['id']})")
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/admin/biomarker-benchmarks/{benchmark_id}",
            headers=auth_headers
        )
        return benchmark_id
    
    def test_update_biomarker_benchmark(self, auth_headers):
        """Test PUT /api/admin/biomarker-benchmarks/{id} updates benchmark"""
        # First create a benchmark
        unique_id = str(uuid.uuid4())[:8]
        create_data = {
            "name": f"TEST_Update_Original_{unique_id}",
            "category": "pigmentation",
            "unit": "index",
            "is_active": True
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/admin/biomarker-benchmarks",
            headers=auth_headers,
            json=create_data
        )
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        benchmark_id = create_response.json()["benchmark"]["id"]
        
        # Update the benchmark
        update_data = {
            "name": f"TEST_Update_Modified_{unique_id}",
            "category": "texture",
            "optimal_min": 35,
            "optimal_max": 75,
            "is_active": False
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/biomarker-benchmarks/{benchmark_id}",
            headers=auth_headers,
            json=update_data
        )
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        
        assert data.get("success") == True, "Update should return success=True"
        assert "benchmark" in data, "Missing 'benchmark' in response"
        
        updated = data["benchmark"]
        assert updated["name"] == update_data["name"], "Name not updated"
        assert updated["category"] == update_data["category"], "Category not updated"
        assert updated["optimal_min"] == update_data["optimal_min"], "optimal_min not updated"
        assert updated["optimal_max"] == update_data["optimal_max"], "optimal_max not updated"
        assert updated["is_active"] == update_data["is_active"], "is_active not updated"
        assert updated["updated_at"] is not None, "updated_at should be set"
        
        print(f"✓ Updated benchmark: {updated['name']}")
        
        # Verify update persisted with GET
        get_response = requests.get(
            f"{BASE_URL}/api/admin/biomarker-benchmarks/{benchmark_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched["name"] == update_data["name"], "Update not persisted"
        
        print(f"✓ Update persistence verified with GET")
        
        # Cleanup
        requests.delete(
            f"{BASE_URL}/api/admin/biomarker-benchmarks/{benchmark_id}",
            headers=auth_headers
        )
        return benchmark_id
    
    def test_delete_biomarker_benchmark(self, auth_headers):
        """Test DELETE /api/admin/biomarker-benchmarks/{id} deletes benchmark"""
        # First create a benchmark
        unique_id = str(uuid.uuid4())[:8]
        create_data = {
            "name": f"TEST_Delete_{unique_id}",
            "category": "inflammation"
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/admin/biomarker-benchmarks",
            headers=auth_headers,
            json=create_data
        )
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        benchmark_id = create_response.json()["benchmark"]["id"]
        
        # Delete the benchmark
        response = requests.delete(
            f"{BASE_URL}/api/admin/biomarker-benchmarks/{benchmark_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Delete failed: {response.text}"
        data = response.json()
        assert data.get("success") == True, "Delete should return success=True"
        
        print(f"✓ Deleted benchmark: {benchmark_id}")
        
        # Verify deletion with GET (should 404)
        get_response = requests.get(
            f"{BASE_URL}/api/admin/biomarker-benchmarks/{benchmark_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404, "Deleted benchmark should return 404"
        
        print(f"✓ Delete verification: benchmark no longer exists")
    
    def test_benchmark_not_found(self, auth_headers):
        """Test 404 for non-existent benchmark"""
        fake_id = str(uuid.uuid4())
        
        # GET non-existent
        response = requests.get(
            f"{BASE_URL}/api/admin/biomarker-benchmarks/{fake_id}",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        # PUT non-existent
        response = requests.put(
            f"{BASE_URL}/api/admin/biomarker-benchmarks/{fake_id}",
            headers=auth_headers,
            json={"name": "Test"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        # DELETE non-existent
        response = requests.delete(
            f"{BASE_URL}/api/admin/biomarker-benchmarks/{fake_id}",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        print("✓ Non-existent benchmark returns 404 for GET, PUT, DELETE")
    
    # ============== Cleanup ==============
    
    def test_cleanup_test_benchmarks(self, auth_headers):
        """Clean up any test benchmarks created during testing"""
        response = requests.get(
            f"{BASE_URL}/api/admin/biomarker-benchmarks",
            headers=auth_headers
        )
        
        if response.status_code == 200:
            benchmarks = response.json().get("benchmarks", [])
            deleted_count = 0
            
            for benchmark in benchmarks:
                if benchmark.get("name", "").startswith("TEST_"):
                    delete_response = requests.delete(
                        f"{BASE_URL}/api/admin/biomarker-benchmarks/{benchmark['id']}",
                        headers=auth_headers
                    )
                    if delete_response.status_code == 200:
                        deleted_count += 1
            
            print(f"✓ Cleaned up {deleted_count} test benchmarks")
        else:
            print("⚠ Could not fetch benchmarks for cleanup")


# Run tests directly if executed as script
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
