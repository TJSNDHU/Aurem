"""
Pillar 2 (Billing/Onboarding) Worker Isolation Tests
=====================================================
Tests for AUREM microservices migration Phase 3 — Pillar 2 worker isolation.
Verifies 5 billing/onboarding schedulers moved from main uvicorn event loop
to pillars/billing/worker.py.

Schedulers owned by Pillar 2:
  1. abandoned_cart_scheduler (1h cycle — Stripe cart recovery)
  2. day21_review_scheduler (daily — trial → paid conversion)
  3. birthday_bonus_scheduler (daily — customer retention)
  4. aurem_morning_scheduler (daily — trial drip + digest)
  5. compliance_scheduler (daily midnight UTC — SOC 2 audit)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Module-level token cache to avoid rate limiting
_cached_token = None

def get_cached_auth_token():
    """Get admin JWT token with caching to avoid rate limits"""
    global _cached_token
    if _cached_token:
        return _cached_token
    
    admin_email = "teji.ss1986@gmail.com"
    admin_password = "<REDACTED>"
    
    # Retry with backoff for rate limiting
    for attempt in range(3):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": admin_email, "password": admin_password}
        )
        if response.status_code == 200:
            data = response.json()
            _cached_token = data.get("token") or data.get("access_token")
            return _cached_token
        elif response.status_code == 429:
            time.sleep(2 ** attempt)  # Exponential backoff
        else:
            break
    
    raise Exception(f"Login failed after retries: {response.status_code} - {response.text}")


class TestPillar2WorkerIsolation:
    """Tests for Pillar 2 (Billing/Onboarding) worker isolation"""
    
    def auth_headers(self):
        """Get authorization headers"""
        return {"Authorization": f"Bearer {get_cached_auth_token()}"}

    # ========== STARTUP LOG VERIFICATION ==========
    
    def test_backend_boots_without_import_error(self):
        """Backend boots with ZERO ImportError"""
        # If we can hit health endpoint, backend booted successfully
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "ok", f"Health status not ok: {data}"
        print("✓ Backend boots without ImportError - health check passed")
    
    # ========== PILLAR 2 REGRESSION TESTS ==========
    
    def test_subscription_plans_endpoint(self):
        """GET /api/subscription/plans (authenticated) must return 200"""
        response = requests.get(
            f"{BASE_URL}/api/subscription/plans",
            headers=self.auth_headers()
        )
        assert response.status_code == 200, f"Subscription plans failed: {response.status_code} - {response.text}"
        data = response.json()
        # Should return list of plans
        assert isinstance(data, (list, dict)), f"Unexpected response type: {type(data)}"
        print(f"✓ GET /api/subscription/plans returns 200 with {len(data) if isinstance(data, list) else 'dict'} plans")
    
    def test_admin_customers_endpoint(self):
        """GET /api/admin/customers must return 200"""
        response = requests.get(
            f"{BASE_URL}/api/admin/customers",
            headers=self.auth_headers()
        )
        assert response.status_code == 200, f"Admin customers failed: {response.status_code} - {response.text}"
        data = response.json()
        print(f"✓ GET /api/admin/customers returns 200")
    
    # ========== PILLAR 1 REGRESSION TESTS ==========
    
    def test_campaign_auto_blast_status(self):
        """GET /api/campaign/auto-blast/status must return 200 (Pillar 1 regression)"""
        response = requests.get(
            f"{BASE_URL}/api/campaign/auto-blast/status",
            headers=self.auth_headers()
        )
        assert response.status_code == 200, f"Auto-blast status failed: {response.status_code} - {response.text}"
        data = response.json()
        # Should have enabled field
        assert "enabled" in data or "status" in data, f"Missing expected fields: {data.keys()}"
        print(f"✓ GET /api/campaign/auto-blast/status returns 200 (Pillar 1 regression OK)")
    
    # ========== PILLAR 3 REGRESSION TESTS ==========
    
    def test_repair_pending_endpoint(self):
        """GET /api/repair/pending must return 200 with 100+ fixes (Pillar 3 regression)"""
        response = requests.get(
            f"{BASE_URL}/api/repair/pending",
            headers=self.auth_headers()
        )
        assert response.status_code == 200, f"Repair pending failed: {response.status_code} - {response.text}"
        data = response.json()
        # Should return list of fixes
        if isinstance(data, list):
            fix_count = len(data)
        elif isinstance(data, dict) and "fixes" in data:
            fix_count = len(data["fixes"])
        else:
            fix_count = data.get("total", 0) if isinstance(data, dict) else 0
        
        assert fix_count >= 100, f"Expected 100+ fixes, got {fix_count}"
        print(f"✓ GET /api/repair/pending returns 200 with {fix_count} fixes (Pillar 3 regression OK)")
    
    def test_sentinel_overview_endpoint(self):
        """GET /api/admin/sentinel/overview must return 200"""
        response = requests.get(
            f"{BASE_URL}/api/admin/sentinel/overview",
            headers=self.auth_headers()
        )
        assert response.status_code == 200, f"Sentinel overview failed: {response.status_code} - {response.text}"
        print("✓ GET /api/admin/sentinel/overview returns 200")
    
    def test_shannon_posture_endpoint(self):
        """GET /api/security/shannon/posture must return 200"""
        response = requests.get(
            f"{BASE_URL}/api/security/shannon/posture",
            headers=self.auth_headers()
        )
        assert response.status_code == 200, f"Shannon posture failed: {response.status_code} - {response.text}"
        print("✓ GET /api/security/shannon/posture returns 200")
    
    def test_admin_catalog_endpoint(self):
        """GET /api/admin/catalog must return 200"""
        response = requests.get(
            f"{BASE_URL}/api/admin/catalog",
            headers=self.auth_headers()
        )
        assert response.status_code == 200, f"Admin catalog failed: {response.status_code} - {response.text}"
        print("✓ GET /api/admin/catalog returns 200")


class TestPillar2WorkerModule:
    """Tests for Pillar 2 worker module file structure"""
    
    def test_pillar2_worker_file_exists(self):
        """Verify pillars/billing/worker.py exists and has required functions"""
        import os
        worker_path = os.path.join(os.path.dirname(__file__), '..', 'pillars', 'billing', 'worker.py')
        assert os.path.exists(worker_path), f"Pillar 2 worker file not found: {worker_path}"
        
        with open(worker_path, 'r') as f:
            content = f.read()
        
        # Check for required functions
        assert "def start_pillar2_worker" in content, "start_pillar2_worker function not found"
        assert "def get_worker_status" in content, "get_worker_status function not found"
        print("✓ pillars/billing/worker.py exists with required functions")
    
    def test_pillar2_init_file_exists(self):
        """Verify pillars/billing/__init__.py exists"""
        import os
        init_path = os.path.join(os.path.dirname(__file__), '..', 'pillars', 'billing', '__init__.py')
        assert os.path.exists(init_path), f"Pillar 2 init file not found: {init_path}"
        print("✓ pillars/billing/__init__.py exists")
    
    def test_compliance_scheduler_file_exists(self):
        """Verify compliance_scheduler service exists"""
        import os
        scheduler_path = os.path.join(os.path.dirname(__file__), '..', 'services', 'compliance_scheduler.py')
        assert os.path.exists(scheduler_path), f"compliance_scheduler not found: {scheduler_path}"
        
        with open(scheduler_path, 'r') as f:
            content = f.read()
        
        assert "def compliance_scheduler" in content or "async def compliance_scheduler" in content, \
            "compliance_scheduler function not found"
        print("✓ services/compliance_scheduler.py exists with compliance_scheduler function")


class TestNoDuplicateSchedulers:
    """Tests to verify no duplicate scheduler registrations"""
    
    def test_no_compliance_scheduler_in_server_py(self):
        """Verify compliance_scheduler is NOT directly called in server.py"""
        import os
        server_path = os.path.join(os.path.dirname(__file__), '..', 'server.py')
        with open(server_path, 'r') as f:
            content = f.read()
        
        # Should NOT have _safe_task(compliance_scheduler(), ...) in server.py
        # The old pattern was: _safe_task(compliance_scheduler(), "compliance_scheduler")
        assert "_safe_task(compliance_scheduler()" not in content, \
            "Found duplicate compliance_scheduler in server.py - should be owned by Pillar 2 worker"
        print("✓ No duplicate compliance_scheduler in server.py")
    
    def test_pillar2_owns_compliance_scheduler(self):
        """Verify Pillar 2 worker owns compliance_scheduler"""
        import os
        worker_path = os.path.join(os.path.dirname(__file__), '..', 'pillars', 'billing', 'worker.py')
        with open(worker_path, 'r') as f:
            content = f.read()
        
        # Should have compliance_scheduler import and task creation
        assert "compliance_scheduler" in content, \
            "compliance_scheduler not found in Pillar 2 worker"
        assert "SOC 2 Compliance" in content, \
            "SOC 2 Compliance scheduler not found in Pillar 2 worker"
        print("✓ Pillar 2 worker owns compliance_scheduler")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
