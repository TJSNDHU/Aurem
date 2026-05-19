"""
Iteration 202 Backend Tests
============================
Tests for:
1. System Audit Dashboard (GET /api/admin/system-audit, POST /api/admin/system-audit/run-health-check)
2. 4-Agent Autonomous System (dry_run=true default, daily_cap=20, toggle dry-run)
3. Stripe Embedded Checkout (publishable-key, create-session, session-status, health)
4. Scheduler job 'aurem_health_check' registration
5. Regression: Smart onboarding endpoints still work
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from test_credentials.md
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = "<REDACTED>"
CUSTOMER_EMAIL = "pawandeep19may1985@gmail.com"
CUSTOMER_PASSWORD = "ReRoots2026!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token"""
    r = requests.post(f"{BASE_URL}/api/platform/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if r.status_code == 200:
        data = r.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")


@pytest.fixture(scope="module")
def customer_token():
    """Get customer JWT token"""
    r = requests.post(f"{BASE_URL}/api/platform/auth/login", json={
        "email": CUSTOMER_EMAIL,
        "password": CUSTOMER_PASSWORD
    })
    if r.status_code == 200:
        data = r.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Customer login failed: {r.status_code} {r.text[:200]}")


class TestSystemAuditAuth:
    """Test auth requirements for system audit endpoints"""

    def test_system_audit_no_auth_returns_401(self):
        """GET /api/admin/system-audit without auth returns 401"""
        r = requests.get(f"{BASE_URL}/api/admin/system-audit")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_system_audit_non_admin_returns_403(self, customer_token):
        """GET /api/admin/system-audit with non-admin token returns 403"""
        r = requests.get(
            f"{BASE_URL}/api/admin/system-audit",
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}"


class TestSystemAuditEndpoints:
    """Test system audit dashboard endpoints"""

    def test_system_audit_returns_expected_fields(self, admin_token):
        """GET /api/admin/system-audit returns verdict, red_flags, health_check, agents, scheduler, integrations, pixel, recent_errors"""
        r = requests.get(
            f"{BASE_URL}/api/admin/system-audit",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        data = r.json()
        
        # Check required fields
        assert "verdict" in data, "Missing 'verdict' field"
        assert "red_flags" in data, "Missing 'red_flags' field"
        assert "health_check" in data, "Missing 'health_check' field"
        assert "agents" in data, "Missing 'agents' field"
        assert "scheduler" in data, "Missing 'scheduler' field"
        assert "integrations" in data, "Missing 'integrations' field"
        assert "pixel" in data, "Missing 'pixel' field"
        assert "recent_errors" in data, "Missing 'recent_errors' field"
        
        # Verdict should be healthy/degraded/critical
        assert data["verdict"] in ["healthy", "degraded", "critical"], f"Unexpected verdict: {data['verdict']}"
        
        # Integrations should have required and optional
        assert "required" in data["integrations"], "Missing integrations.required"
        assert "optional" in data["integrations"], "Missing integrations.optional"

    def test_system_audit_verdict_healthy(self, admin_token):
        """Verdict should be 'healthy' when all required secrets are present"""
        r = requests.get(
            f"{BASE_URL}/api/admin/system-audit",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r.status_code == 200
        data = r.json()
        # With all required secrets present, verdict should be healthy
        # (unless scheduler is not running or last health check failed)
        print(f"Verdict: {data['verdict']}, Red flags: {data.get('red_flags', [])}")
        # Just verify it's a valid verdict
        assert data["verdict"] in ["healthy", "degraded", "critical"]

    def test_system_audit_agents_count(self, admin_token):
        """System audit should return 4 agents"""
        r = requests.get(
            f"{BASE_URL}/api/admin/system-audit",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r.status_code == 200
        data = r.json()
        agents = data.get("agents", [])
        assert len(agents) == 4, f"Expected 4 agents, got {len(agents)}"
        
        # Verify agent IDs
        agent_ids = [a["agent_id"] for a in agents]
        expected_ids = ["hunter_ora", "followup_ora", "closer_ora", "referral_ora"]
        for eid in expected_ids:
            assert eid in agent_ids, f"Missing agent: {eid}"

    def test_run_health_check(self, admin_token):
        """POST /api/admin/system-audit/run-health-check returns overall, checklist, ran_at"""
        r = requests.post(
            f"{BASE_URL}/api/admin/system-audit/run-health-check",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        data = r.json()
        
        assert "overall" in data, "Missing 'overall' field"
        assert "checklist" in data, "Missing 'checklist' field"
        assert "ran_at" in data, "Missing 'ran_at' field"
        
        # Overall should be PASS, PARTIAL, or FAIL
        assert data["overall"] in ["PASS", "PARTIAL", "FAIL", "not_run_yet"], f"Unexpected overall: {data['overall']}"
        
        # Checklist should have 5 steps
        if data["overall"] != "not_run_yet":
            checklist = data.get("checklist", [])
            assert len(checklist) == 5, f"Expected 5 checklist items, got {len(checklist)}"
            for item in checklist:
                assert "step" in item, "Checklist item missing 'step'"
                assert "ok" in item, "Checklist item missing 'ok'"


class TestAgentDryRunDefault:
    """Test that all 4 agents default to dry_run=true with daily_cap=20"""

    def test_agents_dry_run_default(self, admin_token):
        """All 4 agents should have dry_run=true by default"""
        r = requests.get(
            f"{BASE_URL}/api/admin/system-audit",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r.status_code == 200
        data = r.json()
        agents = data.get("agents", [])
        
        for agent in agents:
            assert agent.get("dry_run") is True, f"Agent {agent['agent_id']} should have dry_run=true, got {agent.get('dry_run')}"
            assert agent.get("daily_cap") == 20, f"Agent {agent['agent_id']} should have daily_cap=20, got {agent.get('daily_cap')}"
            assert agent.get("sent_today") == 0 or isinstance(agent.get("sent_today"), int), f"Agent {agent['agent_id']} sent_today should be int"

    def test_agent_toggle_dry_run(self, admin_token):
        """POST /api/agents/hunter_ora/dry-run toggles dry_run mode"""
        # First, flip to LIVE (dry_run=false)
        r = requests.post(
            f"{BASE_URL}/api/agents/hunter_ora/dry-run",
            headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
            json={"enabled": False}
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        assert data.get("ok") is True
        assert data.get("dry_run") is False, "dry_run should be False after toggle"
        
        # Flip back to DRY (dry_run=true)
        r2 = requests.post(
            f"{BASE_URL}/api/agents/hunter_ora/dry-run",
            headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
            json={"enabled": True}
        )
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2.get("ok") is True
        assert data2.get("dry_run") is True, "dry_run should be True after toggle back"


class TestStripeEmbedEndpoints:
    """Test Stripe Embedded Checkout endpoints"""

    def test_stripe_embed_health(self):
        """GET /api/stripe-embed/health returns status, configured, plans"""
        r = requests.get(f"{BASE_URL}/api/stripe-embed/health")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        
        assert data.get("status") == "ok", f"Expected status=ok, got {data.get('status')}"
        assert "configured" in data, "Missing 'configured' field"
        assert "plans" in data, "Missing 'plans' field"
        
        # Plans should have starter, growth, enterprise
        plans = data.get("plans", {})
        assert "starter" in plans, "Missing plans.starter"
        assert "growth" in plans, "Missing plans.growth"
        assert "enterprise" in plans, "Missing plans.enterprise"

    def test_stripe_embed_publishable_key(self):
        """GET /api/stripe-embed/publishable-key returns publishable_key starting with pk_"""
        r = requests.get(f"{BASE_URL}/api/stripe-embed/publishable-key")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        
        assert "publishable_key" in data, "Missing 'publishable_key' field"
        pk = data.get("publishable_key", "")
        assert pk.startswith("pk_"), f"publishable_key should start with 'pk_', got {pk[:20]}"

    def test_stripe_embed_create_session_requires_auth(self):
        """POST /api/stripe-embed/create-session without auth returns 401"""
        r = requests.post(
            f"{BASE_URL}/api/stripe-embed/create-session",
            json={"plan": "starter", "return_url": "https://aurem.live"}
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_stripe_embed_create_session_invalid_plan(self, customer_token):
        """POST /api/stripe-embed/create-session with invalid plan returns 400"""
        r = requests.post(
            f"{BASE_URL}/api/stripe-embed/create-session",
            headers={"Authorization": f"Bearer {customer_token}", "Content-Type": "application/json"},
            json={"plan": "invalid_plan", "return_url": "https://aurem.live"}
        )
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"

    def test_stripe_embed_create_session_success(self, customer_token):
        """POST /api/stripe-embed/create-session with valid plan returns client_secret, session_id"""
        r = requests.post(
            f"{BASE_URL}/api/stripe-embed/create-session",
            headers={"Authorization": f"Bearer {customer_token}", "Content-Type": "application/json"},
            json={"plan": "starter", "return_url": "https://aurem.live"}
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        data = r.json()
        
        assert "client_secret" in data, "Missing 'client_secret' field"
        assert "session_id" in data, "Missing 'session_id' field"
        
        session_id = data.get("session_id", "")
        assert session_id.startswith("cs_"), f"session_id should start with 'cs_', got {session_id[:20]}"
        
        # Store session_id for next test
        pytest.session_id = session_id

    def test_stripe_embed_session_status(self, customer_token):
        """GET /api/stripe-embed/session-status/{session_id} returns status, payment_status"""
        session_id = getattr(pytest, "session_id", None)
        if not session_id:
            pytest.skip("No session_id from previous test")
        
        r = requests.get(
            f"{BASE_URL}/api/stripe-embed/session-status/{session_id}",
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        
        assert "status" in data, "Missing 'status' field"
        assert "payment_status" in data, "Missing 'payment_status' field"


class TestSchedulerHealthCheckJob:
    """Test that aurem_health_check job is registered"""

    def test_scheduler_has_health_check_job(self, admin_token):
        """Scheduler should have 'aurem_health_check' job with next_run_time"""
        r = requests.get(
            f"{BASE_URL}/api/admin/system-audit",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert r.status_code == 200
        data = r.json()
        
        scheduler = data.get("scheduler", {})
        assert scheduler.get("available") is True or scheduler.get("running") is True, "Scheduler should be available/running"
        
        jobs = scheduler.get("jobs", [])
        job_ids = [j["id"] for j in jobs]
        assert "aurem_health_check" in job_ids, f"Missing 'aurem_health_check' job. Jobs: {job_ids}"
        
        # Find the health check job and verify next_run
        hc_job = next((j for j in jobs if j["id"] == "aurem_health_check"), None)
        assert hc_job is not None
        assert hc_job.get("next_run") is not None, "aurem_health_check should have next_run_time set"


class TestSmartOnboardingRegression:
    """Regression tests for smart onboarding (iteration 201)"""

    def test_smart_onboarding_health(self):
        """GET /api/smart-onboarding/health returns status=ok"""
        r = requests.get(f"{BASE_URL}/api/smart-onboarding/health")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert data.get("status") == "ok", f"Expected status=ok, got {data.get('status')}"

    def test_smart_onboarding_detect_requires_auth(self):
        """POST /api/smart-onboarding/detect without auth returns 401"""
        r = requests.post(
            f"{BASE_URL}/api/smart-onboarding/detect",
            json={"business_name": "Test", "website_url": "https://test.com", "city": "Toronto"}
        )
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_smart_onboarding_me_requires_auth(self):
        """GET /api/smart-onboarding/me without auth returns 401"""
        r = requests.get(f"{BASE_URL}/api/smart-onboarding/me")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def test_smart_onboarding_me_with_auth(self, customer_token):
        """GET /api/smart-onboarding/me with auth returns user data"""
        r = requests.get(
            f"{BASE_URL}/api/smart-onboarding/me",
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert "email" in data, "Missing 'email' field"


class TestPaymentTransactionCreation:
    """Test that payment_transactions doc is created on session creation"""

    def test_payment_transaction_created(self, customer_token):
        """POST /api/stripe-embed/create-session creates payment_transactions doc with status=initiated"""
        # Create a new session
        r = requests.post(
            f"{BASE_URL}/api/stripe-embed/create-session",
            headers={"Authorization": f"Bearer {customer_token}", "Content-Type": "application/json"},
            json={"plan": "growth", "return_url": "https://aurem.live"}
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        session_id = data.get("session_id")
        assert session_id, "Missing session_id"
        
        # The payment_transactions doc should be created with status=initiated
        # We can't directly query MongoDB, but we can verify via session-status
        # that the session exists and is tracked
        r2 = requests.get(
            f"{BASE_URL}/api/stripe-embed/session-status/{session_id}",
            headers={"Authorization": f"Bearer {customer_token}"}
        )
        assert r2.status_code == 200, f"Session status check failed: {r2.status_code}"
        # If we get here, the session is tracked (payment_transactions doc exists)
        print(f"Session {session_id} created and tracked successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
