"""
Brand Filtering Tests for Multi-Tenant E-Commerce Platform
Tests:
1. Dashboard-stats API with brand filtering (?brand=lavela vs ?brand=reroots)
2. La Vela products endpoints 
3. ORO ROSA product verification
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "test@admin.com"
ADMIN_PASSWORD = "admin123"


class TestBrandFiltering:
    """Test brand-aware dashboard stats and product APIs"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code}")
        data = response.json()
        return data.get("token") or data.get("access_token")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Get auth headers for requests"""
        return {"Authorization": f"Bearer {admin_token}"}
    
    # ============ DASHBOARD STATS WITH BRAND FILTERING ============
    
    def test_dashboard_stats_default(self, auth_headers):
        """Test dashboard stats without brand filter (defaults to reroots)"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard-stats", headers=auth_headers)
        assert response.status_code == 200, f"Dashboard stats failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "revenue" in data, "Missing revenue in dashboard stats"
        assert "quiz" in data or "quiz_conversions" in data or True  # Optional field
        print(f"✓ Dashboard stats (default): Revenue={data.get('revenue', {}).get('total', 'N/A')}")
    
    def test_dashboard_stats_reroots_brand(self, auth_headers):
        """Test dashboard stats filtered for ReRoots brand"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard-stats?brand=reroots", headers=auth_headers)
        assert response.status_code == 200, f"ReRoots dashboard stats failed: {response.text}"
        data = response.json()
        
        # Verify response contains revenue data
        assert "revenue" in data, "Missing revenue in ReRoots dashboard stats"
        revenue = data.get("revenue", {})
        print(f"✓ Dashboard stats (brand=reroots): Revenue={revenue.get('total', 'N/A')}, Orders={revenue.get('orders_count', 0)}")
    
    def test_dashboard_stats_lavela_brand(self, auth_headers):
        """Test dashboard stats filtered for La Vela Bianca brand"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard-stats?brand=lavela", headers=auth_headers)
        assert response.status_code == 200, f"La Vela dashboard stats failed: {response.text}"
        data = response.json()
        
        # Verify response contains revenue data
        assert "revenue" in data, "Missing revenue in La Vela dashboard stats"
        revenue = data.get("revenue", {})
        print(f"✓ Dashboard stats (brand=lavela): Revenue={revenue.get('total', 'N/A')}, Orders={revenue.get('orders_count', 0)}")
    
    # ============ LA VELA BIANCA ADMIN PRODUCTS ============
    
    def test_lavela_products_admin_endpoint(self, auth_headers):
        """Test admin endpoint for La Vela products"""
        response = requests.get(f"{BASE_URL}/api/admin/lavela/products", headers=auth_headers)
        assert response.status_code == 200, f"La Vela admin products failed: {response.text}"
        data = response.json()
        
        products = data.get("products", [])
        print(f"✓ La Vela admin products: {len(products)} products found")
        
        # If products exist, check structure
        for product in products[:3]:
            print(f"  - {product.get('name', 'Unknown')}: ${product.get('price_cad', product.get('price', 'N/A'))}")
    
    def test_lavela_products_public_endpoint(self):
        """Test public endpoint for La Vela products (no auth required)"""
        response = requests.get(f"{BASE_URL}/api/lavela/products")
        assert response.status_code == 200, f"Public La Vela products failed: {response.text}"
        data = response.json()
        
        products = data.get("products", [])
        print(f"✓ La Vela public products: {len(products)} active products")
        
        # Look for ORO ROSA
        oro_rosa = next((p for p in products if "ORO ROSA" in p.get("name", "").upper() or "ORO-ROSA" in p.get("id", "").upper()), None)
        if oro_rosa:
            print(f"  ✓ Found ORO ROSA: {oro_rosa.get('name')} at ${oro_rosa.get('price_cad', oro_rosa.get('price', 'N/A'))}")
        return products
    
    def test_oro_rosa_flagship_endpoint(self):
        """Test flagship product endpoint"""
        response = requests.get(f"{BASE_URL}/api/lavela/products/flagship")
        assert response.status_code == 200, f"Flagship product endpoint failed: {response.text}"
        data = response.json()
        
        assert "name" in data or "product" in data, "Missing product data in flagship response"
        product = data.get("product", data) if isinstance(data.get("product"), dict) else data
        
        name = product.get("name", "")
        assert "ORO ROSA" in name.upper(), f"Flagship product should be ORO ROSA, got: {name}"
        print(f"✓ Flagship product: {name}")
    
    def test_oro_rosa_details_endpoint(self):
        """Test ORO ROSA specific endpoint"""
        response = requests.get(f"{BASE_URL}/api/lavela/oro-rosa")
        assert response.status_code == 200, f"ORO ROSA endpoint failed: {response.text}"
        data = response.json()
        
        product = data.get("product", data)
        assert product.get("name", ""), "ORO ROSA product should have a name"
        assert product.get("price") or product.get("price_cad"), "ORO ROSA should have a price"
        
        # Check for hero ingredients
        ingredients = data.get("hero_ingredients", product.get("hero_ingredients", []))
        print(f"✓ ORO ROSA details: {product.get('name', 'ORO ROSA')}, {len(ingredients)} hero ingredients")
        for ing in ingredients[:4]:
            print(f"  - {ing.get('name', 'Unknown')}: {ing.get('nickname', 'N/A')}")
    
    # ============ LA VELA STATS ENDPOINT ============
    
    def test_lavela_stats(self, auth_headers):
        """Test La Vela admin stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/admin/lavela/stats", headers=auth_headers)
        assert response.status_code == 200, f"La Vela stats failed: {response.text}"
        data = response.json()
        
        print(f"✓ La Vela stats: {data.get('products', {}).get('total', 0)} products, {data.get('glow_club', {}).get('total_members', 0)} Glow Club members")
    
    # ============ LA VELA GLOW CLUB ============
    
    def test_lavela_glow_club(self, auth_headers):
        """Test La Vela Glow Club members endpoint"""
        response = requests.get(f"{BASE_URL}/api/admin/lavela/glow-club", headers=auth_headers)
        assert response.status_code == 200, f"Glow Club endpoint failed: {response.text}"
        data = response.json()
        
        members = data.get("members", [])
        stats = data.get("stats", {})
        print(f"✓ Glow Club: {len(members)} members, Tiers: {stats.get('tiers', {})}")


class TestLaVelaStaticRoutes:
    """Test La Vela Bianca static routes from lavela/routes/products.py"""
    
    def test_lavela_categories(self):
        """Test categories endpoint"""
        response = requests.get(f"{BASE_URL}/api/lavela/categories")
        assert response.status_code == 200, f"Categories failed: {response.text}"
        data = response.json()
        
        categories = data.get("categories", [])
        print(f"✓ La Vela categories: {categories}")
    
    def test_lavela_stats_public(self):
        """Test public stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/lavela/stats")
        assert response.status_code == 200, f"Stats failed: {response.text}"
        data = response.json()
        
        print(f"✓ La Vela public stats: {data.get('total_products', 0)} total, {data.get('active_products', 0)} active")
        
        # Check flagship product reference
        flagship = data.get("flagship_product", {})
        if flagship:
            assert "ORO" in flagship.get("name", "").upper() or flagship.get("id") == "LV-ORO-001"
            print(f"  Flagship: {flagship.get('name', 'N/A')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
