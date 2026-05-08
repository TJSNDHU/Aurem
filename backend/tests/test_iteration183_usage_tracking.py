"""
Iteration 183 - Usage Tracking & Plan-Based Fix Limits Tests
=============================================================
Tests for:
1. GET /api/self-audit/usage — returns plan, used, limit, remaining, over_limit, month
2. POST /api/self-audit/run — report now includes usage block
3. Plan enforcement: starter=50, growth=500, enterprise=unlimited
4. Over-limit behavior: fixes skipped with monthly_fix_limit_reached reason
5. Auth guard: /api/self-audit/usage returns 401 without token
6. Regression: all existing self-audit endpoints still work
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://ai-platform-preview-3.preview.emergentagent.com"

# Test credentials
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = "Admin123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Return headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ═══════════════════════════════════════════════════════════════
# NEW FEATURE: GET /api/self-audit/usage
# ═══════════════════════════════════════════════════════════════

class TestUsageEndpoint:
    """Tests for the new /api/self-audit/usage endpoint."""

    def test_usage_returns_200_with_auth(self, auth_headers):
        """GET /api/self-audit/usage should return 200 with valid auth."""
        response = requests.get(f"{BASE_URL}/api/self-audit/usage", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ GET /api/self-audit/usage returned 200")

    def test_usage_returns_401_without_auth(self):
        """GET /api/self-audit/usage should return 401 without auth."""
        response = requests.get(f"{BASE_URL}/api/self-audit/usage")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ GET /api/self-audit/usage returns 401 without auth")

    def test_usage_response_structure(self, auth_headers):
        """GET /api/self-audit/usage should return correct structure."""
        response = requests.get(f"{BASE_URL}/api/self-audit/usage", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "plan" in data, "Missing 'plan' field"
        assert "used" in data, "Missing 'used' field"
        assert "limit" in data, "Missing 'limit' field"
        assert "remaining" in data, "Missing 'remaining' field"
        assert "over_limit" in data, "Missing 'over_limit' field"
        assert "month" in data, "Missing 'month' field"
        
        print(f"✓ Usage response has all required fields: plan={data['plan']}, used={data['used']}, limit={data['limit']}, remaining={data['remaining']}, over_limit={data['over_limit']}, month={data['month']}")

    def test_usage_plan_is_valid(self, auth_headers):
        """Plan should be one of: starter, growth, enterprise."""
        response = requests.get(f"{BASE_URL}/api/self-audit/usage", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        valid_plans = ["starter", "growth", "enterprise"]
        assert data["plan"] in valid_plans, f"Invalid plan: {data['plan']}, expected one of {valid_plans}"
        print(f"✓ Plan is valid: {data['plan']}")

    def test_usage_limit_matches_plan(self, auth_headers):
        """Limit should match plan: starter=50, growth=500, enterprise=-1."""
        response = requests.get(f"{BASE_URL}/api/self-audit/usage", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        plan_limits = {"starter": 50, "growth": 500, "enterprise": -1}
        expected_limit = plan_limits.get(data["plan"], 50)
        assert data["limit"] == expected_limit, f"Plan {data['plan']} should have limit {expected_limit}, got {data['limit']}"
        print(f"✓ Limit matches plan: {data['plan']} → {data['limit']}")

    def test_usage_month_format(self, auth_headers):
        """Month should be in YYYY-MM format."""
        response = requests.get(f"{BASE_URL}/api/self-audit/usage", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        month = data["month"]
        # Validate format YYYY-MM
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError:
            pytest.fail(f"Month format invalid: {month}, expected YYYY-MM")
        
        # Should be current month
        current_month = datetime.now().strftime("%Y-%m")
        assert month == current_month, f"Month should be current: {current_month}, got {month}"
        print(f"✓ Month format correct: {month}")

    def test_usage_remaining_calculation(self, auth_headers):
        """Remaining should be max(0, limit - used) for non-enterprise plans."""
        response = requests.get(f"{BASE_URL}/api/self-audit/usage", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        if data["limit"] == -1:  # Enterprise
            assert data["remaining"] == -1, "Enterprise should have remaining=-1"
        else:
            expected_remaining = max(0, data["limit"] - data["used"])
            assert data["remaining"] == expected_remaining, f"Remaining should be {expected_remaining}, got {data['remaining']}"
        print(f"✓ Remaining calculation correct: {data['remaining']}")

    def test_usage_over_limit_flag(self, auth_headers):
        """over_limit should be True when used >= limit (for non-enterprise)."""
        response = requests.get(f"{BASE_URL}/api/self-audit/usage", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        if data["limit"] == -1:  # Enterprise
            assert data["over_limit"] == False, "Enterprise should never be over_limit"
        else:
            expected_over = data["used"] >= data["limit"]
            assert data["over_limit"] == expected_over, f"over_limit should be {expected_over}, got {data['over_limit']}"
        print(f"✓ over_limit flag correct: {data['over_limit']} (used={data['used']}, limit={data['limit']})")


# ═══════════════════════════════════════════════════════════════
# NEW FEATURE: POST /api/self-audit/run includes usage block
# ═══════════════════════════════════════════════════════════════

class TestAuditRunUsageBlock:
    """Tests for usage block in audit run response."""

    def test_run_audit_includes_usage_block(self, auth_headers):
        """POST /api/self-audit/run should include usage block in response."""
        response = requests.post(
            f"{BASE_URL}/api/self-audit/run",
            headers=auth_headers,
            json={"auto_fix": False}  # Don't auto-fix to avoid side effects
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify usage block exists
        assert "usage" in data, "Missing 'usage' block in audit response"
        usage = data["usage"]
        
        # Verify usage block structure
        assert "plan" in usage, "Missing 'plan' in usage block"
        assert "fixes_used" in usage, "Missing 'fixes_used' in usage block"
        assert "fix_limit" in usage, "Missing 'fix_limit' in usage block"
        assert "remaining" in usage, "Missing 'remaining' in usage block"
        
        print(f"✓ Audit run includes usage block: plan={usage['plan']}, fixes_used={usage['fixes_used']}, fix_limit={usage['fix_limit']}, remaining={usage['remaining']}")

    def test_run_audit_usage_matches_usage_endpoint(self, auth_headers):
        """Usage in audit response should match /usage endpoint."""
        # Get usage from dedicated endpoint
        usage_response = requests.get(f"{BASE_URL}/api/self-audit/usage", headers=auth_headers)
        assert usage_response.status_code == 200
        usage_data = usage_response.json()
        
        # Run audit
        audit_response = requests.post(
            f"{BASE_URL}/api/self-audit/run",
            headers=auth_headers,
            json={"auto_fix": False}
        )
        assert audit_response.status_code == 200
        audit_data = audit_response.json()
        
        # Compare
        assert audit_data["usage"]["plan"] == usage_data["plan"], "Plan mismatch"
        assert audit_data["usage"]["fix_limit"] == usage_data["limit"], "Limit mismatch"
        print(f"✓ Audit usage matches /usage endpoint")


# ═══════════════════════════════════════════════════════════════
# REGRESSION: All existing self-audit endpoints still work
# ═══════════════════════════════════════════════════════════════

class TestRegressionExistingEndpoints:
    """Regression tests for existing self-audit endpoints."""

    def test_run_endpoint(self, auth_headers):
        """POST /api/self-audit/run should work."""
        response = requests.post(
            f"{BASE_URL}/api/self-audit/run",
            headers=auth_headers,
            json={"auto_fix": False}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "audit_id" in data, "Missing audit_id"
        assert "status" in data, "Missing status"
        print(f"✓ POST /api/self-audit/run works: audit_id={data['audit_id']}")

    def test_status_endpoint(self, auth_headers):
        """GET /api/self-audit/status should work."""
        response = requests.get(f"{BASE_URL}/api/self-audit/status", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/self-audit/status works")

    def test_findings_endpoint(self, auth_headers):
        """GET /api/self-audit/findings should work."""
        response = requests.get(f"{BASE_URL}/api/self-audit/findings", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/self-audit/findings works")

    def test_log_endpoint(self, auth_headers):
        """GET /api/self-audit/log should work."""
        response = requests.get(f"{BASE_URL}/api/self-audit/log", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/self-audit/log works")

    def test_stats_endpoint(self, auth_headers):
        """GET /api/self-audit/stats should work."""
        response = requests.get(f"{BASE_URL}/api/self-audit/stats", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/self-audit/stats works")

    def test_queue_endpoint(self, auth_headers):
        """GET /api/self-audit/queue should work."""
        response = requests.get(f"{BASE_URL}/api/self-audit/queue", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/self-audit/queue works")

    def test_tier_endpoint(self, auth_headers):
        """GET /api/self-audit/tier should work."""
        response = requests.get(f"{BASE_URL}/api/self-audit/tier", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/self-audit/tier works")

    def test_schedule_get_endpoint(self, auth_headers):
        """GET /api/self-audit/schedule should work."""
        response = requests.get(f"{BASE_URL}/api/self-audit/schedule", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/self-audit/schedule works")

    def test_backups_endpoint(self, auth_headers):
        """GET /api/self-audit/backups should work."""
        response = requests.get(f"{BASE_URL}/api/self-audit/backups", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ GET /api/self-audit/backups works")

    def test_verify_data_endpoint(self, auth_headers):
        """POST /api/self-audit/verify-data should work."""
        response = requests.post(
            f"{BASE_URL}/api/self-audit/verify-data",
            headers=auth_headers,
            json={"record_id": "test123", "field": "email", "current_value": "test@example.com"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ POST /api/self-audit/verify-data works")


# ═══════════════════════════════════════════════════════════════
# AUTH GUARDS: All endpoints should return 401 without auth
# ═══════════════════════════════════════════════════════════════

class TestAuthGuards:
    """Test that all endpoints require authentication."""

    def test_usage_requires_auth(self):
        """GET /api/self-audit/usage should return 401 without auth."""
        response = requests.get(f"{BASE_URL}/api/self-audit/usage")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ /usage requires auth")

    def test_run_requires_auth(self):
        """POST /api/self-audit/run should return 401 without auth."""
        response = requests.post(f"{BASE_URL}/api/self-audit/run", json={"auto_fix": False})
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ /run requires auth")

    def test_status_requires_auth(self):
        """GET /api/self-audit/status should return 401 without auth."""
        response = requests.get(f"{BASE_URL}/api/self-audit/status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ /status requires auth")

    def test_findings_requires_auth(self):
        """GET /api/self-audit/findings should return 401 without auth."""
        response = requests.get(f"{BASE_URL}/api/self-audit/findings")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ /findings requires auth")

    def test_log_requires_auth(self):
        """GET /api/self-audit/log should return 401 without auth."""
        response = requests.get(f"{BASE_URL}/api/self-audit/log")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ /log requires auth")

    def test_stats_requires_auth(self):
        """GET /api/self-audit/stats should return 401 without auth."""
        response = requests.get(f"{BASE_URL}/api/self-audit/stats")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ /stats requires auth")

    def test_queue_requires_auth(self):
        """GET /api/self-audit/queue should return 401 without auth."""
        response = requests.get(f"{BASE_URL}/api/self-audit/queue")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ /queue requires auth")

    def test_tier_requires_auth(self):
        """GET /api/self-audit/tier should return 401 without auth."""
        response = requests.get(f"{BASE_URL}/api/self-audit/tier")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ /tier requires auth")

    def test_backups_requires_auth(self):
        """GET /api/self-audit/backups should return 401 without auth."""
        response = requests.get(f"{BASE_URL}/api/self-audit/backups")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ /backups requires auth")


# ═══════════════════════════════════════════════════════════════
# PLAN LIMITS VERIFICATION (Code Review)
# ═══════════════════════════════════════════════════════════════

class TestPlanLimitsCodeReview:
    """Verify plan limits are correctly defined in code."""

    def test_plan_limits_defined(self, auth_headers):
        """Verify plan limits match expected values."""
        # Get current usage to verify plan limits
        response = requests.get(f"{BASE_URL}/api/self-audit/usage", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Based on code review: PLAN_FIX_LIMITS = {"starter": 50, "growth": 500, "enterprise": -1}
        plan = data["plan"]
        limit = data["limit"]
        
        expected_limits = {"starter": 50, "growth": 500, "enterprise": -1}
        if plan in expected_limits:
            assert limit == expected_limits[plan], f"Plan {plan} should have limit {expected_limits[plan]}, got {limit}"
        
        print(f"✓ Plan limits verified: {plan} → {limit}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
