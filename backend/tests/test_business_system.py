"""
Backend API Tests for ReRoots Business System
Testing all 4 modules: Inventory, CRM, Orders, Accounting
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestInventoryModule:
    """Module 01: Inventory & Batch Tracking API Tests"""
    
    def test_get_ingredients(self):
        """GET /api/business/inventory/ingredients returns array of ingredients"""
        response = requests.get(f"{BASE_URL}/api/business/inventory/ingredients")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Ingredients API: {len(data)} ingredients returned")
        
        # Verify data structure if items exist
        if len(data) > 0:
            item = data[0]
            assert "_id" in item  # MongoDB ID
            assert "name" in item
            assert "stock" in item
            print(f"  Sample: {item.get('name')} - Stock: {item.get('stock')}")
    
    def test_get_products(self):
        """GET /api/business/inventory/products returns array of products"""
        response = requests.get(f"{BASE_URL}/api/business/inventory/products")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Products API: {len(data)} products returned")
    
    def test_get_batches(self):
        """GET /api/business/inventory/batches returns array of batches"""
        response = requests.get(f"{BASE_URL}/api/business/inventory/batches")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Batches API: {len(data)} batches returned")


class TestCRMModule:
    """Module 02: CRM & 28-Day Repurchase Engine API Tests"""
    
    def test_get_customers(self):
        """GET /api/business/crm/customers returns array with 28-day cycle calculations"""
        response = requests.get(f"{BASE_URL}/api/business/crm/customers")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ CRM Customers API: {len(data)} customers returned")
        
        # Verify 28-day cycle fields are calculated
        if len(data) > 0:
            customer = data[0]
            assert "_id" in customer
            assert "name" in customer
            # Verify 28-day cycle fields
            assert "cycleDay" in customer
            assert "status" in customer
            assert "nextDue" in customer
            print(f"  Sample: {customer.get('name')} - Day {customer.get('cycleDay')} - Status: {customer.get('status')}")
    
    def test_get_crm_stats(self):
        """GET /api/business/crm/stats returns CRM statistics"""
        response = requests.get(f"{BASE_URL}/api/business/crm/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "total" in data
        assert "dueSoon" in data
        assert "overdue" in data
        assert "lapsed" in data
        assert "vipCount" in data
        assert "totalRevenue" in data
        assert "avgOrderValue" in data
        print(f"✓ CRM Stats API: {data.get('total')} total customers")
        print(f"  Due Soon: {data.get('dueSoon')}, Overdue: {data.get('overdue')}, Lapsed: {data.get('lapsed')}")
    
    def test_get_automations(self):
        """GET /api/business/crm/automations returns array of automations"""
        response = requests.get(f"{BASE_URL}/api/business/crm/automations")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ CRM Automations API: {len(data)} automations returned")


class TestOrdersModule:
    """Module 03: Orders & Fulfillment API Tests"""
    
    def test_get_orders(self):
        """GET /api/business/fulfillment/orders returns array of orders"""
        response = requests.get(f"{BASE_URL}/api/business/fulfillment/orders")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Orders API: {len(data)} orders returned")
        
        # Verify order structure
        if len(data) > 0:
            order = data[0]
            assert "_id" in order
            assert "id" in order  # Order ID (e.g., RR-10001)
            assert "customer" in order
            assert "total" in order
            assert "status" in order
            print(f"  Sample: {order.get('id')} - {order.get('customer')} - ${order.get('total')}")
    
    def test_get_fulfillment_stats(self):
        """GET /api/business/fulfillment/stats returns fulfillment statistics"""
        response = requests.get(f"{BASE_URL}/api/business/fulfillment/stats")
        assert response.status_code == 200
        data = response.json()
        
        assert "revenue" in data
        assert "processing" in data
        assert "shipped" in data
        assert "delivered" in data
        print(f"✓ Fulfillment Stats API: ${data.get('revenue')} revenue, {data.get('processing')} processing")


class TestAccountingModule:
    """Module 04: Accounting & GST/HST API Tests"""
    
    def test_get_transactions(self):
        """GET /api/business/accounting/transactions returns array of transactions"""
        response = requests.get(f"{BASE_URL}/api/business/accounting/transactions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Transactions API: {len(data)} transactions returned")
        
        # Verify transaction structure
        if len(data) > 0:
            txn = data[0]
            assert "_id" in txn
            assert "type" in txn  # Revenue or Expense
            assert "category" in txn
            assert "amount" in txn
            print(f"  Sample: {txn.get('type')} - {txn.get('category')} - ${txn.get('amount')}")
    
    def test_get_accounting_summary(self):
        """GET /api/business/accounting/summary returns P&L summary"""
        response = requests.get(f"{BASE_URL}/api/business/accounting/summary")
        assert response.status_code == 200
        data = response.json()
        
        # Verify P&L fields
        assert "revenue" in data
        assert "cogs" in data
        assert "grossProfit" in data
        assert "grossMargin" in data
        assert "expenses" in data
        assert "netProfit" in data
        assert "netMargin" in data
        assert "taxCollected" in data
        assert "period" in data
        print(f"✓ P&L Summary API: ${data.get('revenue')} revenue, ${data.get('netProfit')} net profit")
        print(f"  Period: {data.get('period')} - Gross Margin: {data.get('grossMargin')}%")
    
    def test_get_accounts(self):
        """GET /api/business/accounting/accounts returns chart of accounts"""
        response = requests.get(f"{BASE_URL}/api/business/accounting/accounts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Accounts API: {len(data)} accounts returned")
    
    def test_get_gst_summary(self):
        """GET /api/business/accounting/gst-summary returns GST/HST tax summary"""
        response = requests.get(f"{BASE_URL}/api/business/accounting/gst-summary")
        assert response.status_code == 200
        data = response.json()
        
        assert "collected" in data
        assert "paid" in data
        assert "netOwing" in data
        assert "byProvince" in data
        print(f"✓ GST Summary API: ${data.get('collected')} collected, ${data.get('netOwing')} net owing")


class TestBusinessAnalytics:
    """Business Analytics / Executive Intelligence API Tests"""
    
    def test_get_business_analytics(self):
        """GET /api/business/business-analytics returns dashboard analytics"""
        response = requests.get(f"{BASE_URL}/api/business/business-analytics")
        assert response.status_code == 200
        data = response.json()
        
        assert "weekly" in data
        assert "repurchaseRate" in data
        assert "lowStockAlerts" in data
        assert "customersDueSoon" in data
        print(f"✓ Business Analytics API: {data.get('weekly', {}).get('revenue')} weekly revenue")
        print(f"  Repurchase Rate: {data.get('repurchaseRate')}, Low Stock: {data.get('lowStockAlerts')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
