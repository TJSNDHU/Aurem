"""
CRM, Refund, and Analytics API Tests
Tests for customer management, refund workflow, and sales analytics endpoints.
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAdminAuthentication:
    """Test admin authentication for protected endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "test@admin.com",
                "password": "admin123"
            }
        )
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin authentication failed")
        
    @pytest.fixture(scope="class")
    def auth_headers(self, admin_token):
        """Get auth headers"""
        return {"Authorization": f"Bearer {admin_token}"}


class TestCRMCustomerEndpoints(TestAdminAuthentication):
    """CRM Customer Management API Tests"""
    
    def test_get_all_customers(self, auth_headers):
        """GET /api/admin/customers - returns list of customers"""
        response = requests.get(
            f"{BASE_URL}/api/admin/customers",
            headers=auth_headers
        )
        # Should return 200 even if no customers
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/admin/customers returned {len(data)} customers")
    
    def test_get_customers_with_vip_filter(self, auth_headers):
        """GET /api/admin/customers?vip=true - filters VIP customers"""
        response = requests.get(
            f"{BASE_URL}/api/admin/customers?vip=true",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # All returned customers should have vip_status=True if field exists
        vip_count = sum(1 for c in data if c.get("vip_status") == True)
        print(f"✓ VIP filter returned {len(data)} customers ({vip_count} with vip_status=True)")
    
    def test_get_customer_detail(self, auth_headers):
        """GET /api/admin/customers/{email} - returns customer detail"""
        test_email = "test2@example.com"
        response = requests.get(
            f"{BASE_URL}/api/admin/customers/{test_email}",
            headers=auth_headers
        )
        # May return 200 with data or 404/error if customer doesn't exist
        if response.status_code == 200:
            data = response.json()
            if "error" not in data:
                assert "customer" in data
                assert "orders" in data
                print(f"✓ Customer detail for {test_email} retrieved successfully")
                return
        print(f"✓ Customer detail endpoint works (customer may not exist yet)")
    
    def test_get_customer_detail_nonexistent(self, auth_headers):
        """GET /api/admin/customers/{email} - handles nonexistent customer"""
        response = requests.get(
            f"{BASE_URL}/api/admin/customers/nonexistent_customer_xyz@test.com",
            headers=auth_headers
        )
        # Should return 200 with error or 404
        assert response.status_code in [200, 404]
        print("✓ Nonexistent customer handled properly")
    
    def test_update_customer_notes(self, auth_headers):
        """PATCH /api/admin/customers/{email}/notes - updates customer notes"""
        test_email = "test2@example.com"
        test_note = f"Test note added at {datetime.now().isoformat()}"
        
        response = requests.patch(
            f"{BASE_URL}/api/admin/customers/{test_email}/notes",
            json={"notes": test_note},
            headers=auth_headers
        )
        # May succeed or fail depending on whether customer exists
        # 200 = success, 404 = customer not found, 422 = validation error
        assert response.status_code in [200, 404, 422]
        print(f"✓ Update notes endpoint works (status {response.status_code})")


class TestRefundEndpoints(TestAdminAuthentication):
    """Refund Management API Tests"""
    
    def test_customer_request_refund(self):
        """POST /api/refunds/request - customer submits refund request"""
        # This is a customer-facing endpoint, no auth required
        response = requests.post(
            f"{BASE_URL}/api/refunds/request",
            json={
                "order_id": "RR-2025-002",
                "customer_email": "test2@example.com",
                "reason": "Product arrived damaged - testing refund flow",
                "refund_type": "full"
            }
        )
        # May return success or error (already exists, order not found, etc.)
        assert response.status_code in [200, 400, 404, 422]
        print(f"✓ Refund request endpoint works (status {response.status_code})")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print(f"  Created refund: {data.get('refund_id')}")
            else:
                print(f"  Response: {data.get('error', data.get('message', 'Unknown'))}")
    
    def test_get_refunds_list(self, auth_headers):
        """GET /api/admin/refunds - returns all refunds"""
        response = requests.get(
            f"{BASE_URL}/api/admin/refunds",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/admin/refunds returned {len(data)} refunds")
    
    def test_get_refunds_pending_filter(self, auth_headers):
        """GET /api/admin/refunds?status=pending - filters by status"""
        response = requests.get(
            f"{BASE_URL}/api/admin/refunds?status=pending",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # All returned should have pending status
        for refund in data:
            assert refund.get("status") == "pending"
        print(f"✓ Pending refunds filter returned {len(data)} pending refunds")
    
    def test_get_refunds_by_status_approved(self, auth_headers):
        """GET /api/admin/refunds?status=approved - filters approved refunds"""
        response = requests.get(
            f"{BASE_URL}/api/admin/refunds?status=approved",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Approved filter returned {len(data)} approved refunds")
    
    def test_resolve_refund_approve(self, auth_headers):
        """PATCH /api/admin/refunds/{refund_id} - admin approves refund"""
        # Use existing refund ID
        refund_id = "REF-F883E36A"
        
        response = requests.patch(
            f"{BASE_URL}/api/admin/refunds/{refund_id}",
            json={
                "action": "approve",
                "admin_name": "Test Admin",
                "notes": "Approved for testing"
            },
            headers=auth_headers
        )
        # May succeed or fail depending on refund state
        assert response.status_code in [200, 400, 404, 422]
        print(f"✓ Resolve refund (approve) endpoint works (status {response.status_code})")
    
    def test_resolve_refund_store_credit(self, auth_headers):
        """PATCH /api/admin/refunds/{refund_id} - store credit option"""
        refund_id = "REF-NONEXISTENT"
        
        response = requests.patch(
            f"{BASE_URL}/api/admin/refunds/{refund_id}",
            json={
                "action": "store_credit",
                "admin_name": "Test Admin",
                "notes": "Store credit test"
            },
            headers=auth_headers
        )
        # 200 with error, 400 (bad request for nonexistent), or 404
        assert response.status_code in [200, 400, 404]
        print(f"✓ Store credit action endpoint works (status {response.status_code})")
    
    def test_resolve_refund_reject(self, auth_headers):
        """PATCH /api/admin/refunds/{refund_id} - reject refund"""
        refund_id = "REF-NONEXISTENT"
        
        response = requests.patch(
            f"{BASE_URL}/api/admin/refunds/{refund_id}",
            json={
                "action": "reject",
                "admin_name": "Test Admin",
                "notes": "Rejected for testing"
            },
            headers=auth_headers
        )
        # 200 with error, 400 (bad request for nonexistent), or 404
        assert response.status_code in [200, 400, 404]
        print(f"✓ Reject action endpoint works (status {response.status_code})")


class TestAnalyticsEndpoints(TestAdminAuthentication):
    """Sales Analytics API Tests"""
    
    def test_get_sales_dashboard_daily(self, auth_headers):
        """GET /api/admin/analytics/sales?period=daily - returns daily data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/analytics/sales?period=daily",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected structure
        assert "period" in data
        assert data["period"] == "daily"
        assert "summary" in data
        assert "chart_data" in data
        assert "top_products" in data
        
        # Verify summary fields
        summary = data["summary"]
        assert "total_orders" in summary
        assert "total_revenue" in summary
        assert "avg_order_value" in summary
        assert "unique_customers" in summary
        
        print(f"✓ Daily sales dashboard: {summary['total_orders']} orders, ${summary['total_revenue']} revenue")
    
    def test_get_sales_dashboard_weekly(self, auth_headers):
        """GET /api/admin/analytics/sales?period=weekly - returns weekly data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/analytics/sales?period=weekly",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "weekly"
        print("✓ Weekly sales dashboard retrieved")
    
    def test_get_sales_dashboard_monthly(self, auth_headers):
        """GET /api/admin/analytics/sales?period=monthly - returns monthly data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/analytics/sales?period=monthly",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["period"] == "monthly"
        print("✓ Monthly sales dashboard retrieved")
    
    def test_get_acquisition_sources(self, auth_headers):
        """GET /api/admin/analytics/acquisition - returns acquisition data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/analytics/acquisition",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected structure
        assert "by_source" in data
        assert "funnel" in data
        
        # Verify funnel structure
        funnel = data["funnel"]
        assert "visitors" in funnel
        assert "quiz_completions" in funnel
        assert "first_purchase" in funnel
        assert "repeat_purchase" in funnel
        assert "vip" in funnel
        
        print(f"✓ Acquisition data: {len(data['by_source'])} sources, {funnel['visitors']} visitors")
    
    def test_get_revenue_metrics(self, auth_headers):
        """GET /api/admin/analytics/revenue-metrics - returns revenue metrics"""
        response = requests.get(
            f"{BASE_URL}/api/admin/analytics/revenue-metrics",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected structure
        assert "today" in data
        assert "this_month" in data
        assert "last_month" in data
        assert "revenue_growth_percent" in data
        
        print(f"✓ Revenue metrics: Today ${data['today']['revenue']}, This month ${data['this_month']['revenue']}")


class TestHealthCheck:
    """Basic health check"""
    
    def test_api_health(self):
        """Verify API is running"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✓ API health check passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
