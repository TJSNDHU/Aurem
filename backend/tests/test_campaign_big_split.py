"""
Test Campaign Router Big Split (iter 262)
Tests the 4-module split of the former 2,068 LOC monolithic campaign_router.py:
  - lead_crud.py (CRUD/stats/DNC/unsubscribe)
  - blast_service.py (per-lead dispatch + test endpoints + voice + webhook)
  - auto_blast.py (controls + daily sequence runners)
  - render_templates.py (competitor templates + seed-aurem + template preview)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ══════════════════════════════════════════════
# Module 1: Import Tests (backwards compatibility)
# ══════════════════════════════════════════════

class TestImports:
    """Verify all imports from routers/campaign_router.py work (backwards compat shim)"""
    
    def test_import_router_and_set_db(self):
        """Import router and set_db from shim"""
        from routers.campaign_router import router, set_db
        assert router is not None
        assert callable(set_db)
        print("✓ router and set_db imported OK")
    
    def test_import_scheduler_functions(self):
        """Import all 6 scheduler sequence functions"""
        from routers.campaign_router import (
            run_daily_scrape, run_website_scans,
            run_email_sequence, run_whatsapp_sequence,
            run_sms_sequence, run_voice_sequence,
        )
        assert callable(run_daily_scrape)
        assert callable(run_website_scans)
        assert callable(run_email_sequence)
        assert callable(run_whatsapp_sequence)
        assert callable(run_sms_sequence)
        assert callable(run_voice_sequence)
        print("✓ All 6 scheduler functions imported OK")
    
    def test_import_blast_functions(self):
        """Import blast_all_channels and execute_blast_for_lead"""
        from routers.campaign_router import blast_all_channels, execute_blast_for_lead
        assert callable(blast_all_channels)
        assert callable(execute_blast_for_lead)
        print("✓ blast_all_channels and execute_blast_for_lead imported OK")
    
    def test_route_count(self):
        """Verify combined router has all 31 routes"""
        from routers.campaign_router import router
        routes = [r for r in router.routes if hasattr(r, 'path')]
        assert len(routes) == 31, f"Expected 31 routes, got {len(routes)}"
        print(f"✓ Combined router has {len(routes)} routes")


# ══════════════════════════════════════════════
# Module 2: Public Endpoints (no auth required)
# ══════════════════════════════════════════════

class TestPublicEndpoints:
    """Test public endpoints that don't require authentication"""
    
    def test_unsubscribe_returns_200(self):
        """GET /api/campaign/unsubscribe?email=test@test.com returns 200"""
        resp = requests.get(f"{BASE_URL}/api/campaign/unsubscribe", params={"email": "test@test.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        print(f"✓ Unsubscribe endpoint returns 200: {data}")
    
    def test_whatsapp_webhook_returns_ok(self):
        """POST /api/campaign/whatsapp-webhook returns ok (public webhook)"""
        resp = requests.post(f"{BASE_URL}/api/campaign/whatsapp-webhook", json={"messages": []})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        print(f"✓ WhatsApp webhook returns ok: {data}")


# ══════════════════════════════════════════════
# Module 3: Auth-Gated Endpoints (return 401 without token)
# ══════════════════════════════════════════════

class TestAuthGatedEndpoints:
    """Test that auth-gated endpoints return 401 without token"""
    
    def test_auto_blast_status_returns_401(self):
        """GET /api/campaign/auto-blast/status returns 401"""
        resp = requests.get(f"{BASE_URL}/api/campaign/auto-blast/status")
        assert resp.status_code == 401
        print("✓ /auto-blast/status returns 401 (auth required)")
    
    def test_leads_returns_401(self):
        """GET /api/campaign/leads returns 401"""
        resp = requests.get(f"{BASE_URL}/api/campaign/leads")
        assert resp.status_code == 401
        print("✓ /leads returns 401 (auth required)")
    
    def test_stats_returns_401(self):
        """GET /api/campaign/stats returns 401"""
        resp = requests.get(f"{BASE_URL}/api/campaign/stats")
        assert resp.status_code == 401
        print("✓ /stats returns 401 (auth required)")
    
    def test_overview_returns_401(self):
        """GET /api/campaign/overview returns 401"""
        resp = requests.get(f"{BASE_URL}/api/campaign/overview")
        assert resp.status_code == 401
        print("✓ /overview returns 401 (auth required)")
    
    def test_competitor_templates_returns_401(self):
        """GET /api/campaign/competitor-templates returns 401"""
        resp = requests.get(f"{BASE_URL}/api/campaign/competitor-templates")
        assert resp.status_code == 401
        print("✓ /competitor-templates returns 401 (auth required)")
    
    def test_ops_status_returns_401(self):
        """GET /api/campaign/ops-status returns 401"""
        resp = requests.get(f"{BASE_URL}/api/campaign/ops-status")
        assert resp.status_code == 401
        print("✓ /ops-status returns 401 (auth required)")
    
    def test_do_not_contact_returns_401(self):
        """GET /api/campaign/do-not-contact returns 401"""
        resp = requests.get(f"{BASE_URL}/api/campaign/do-not-contact")
        assert resp.status_code == 401
        print("✓ /do-not-contact returns 401 (auth required)")
    
    def test_scrape_without_body_returns_error(self):
        """POST /api/campaign/scrape without body returns 401 or 422"""
        resp = requests.post(f"{BASE_URL}/api/campaign/scrape")
        # Should return 401 (auth) or 422 (validation) - route exists
        assert resp.status_code in (401, 422, 405)
        print(f"✓ /scrape returns {resp.status_code} (route exists)")


# ══════════════════════════════════════════════
# Module 4: Authenticated Flows
# ══════════════════════════════════════════════

class TestAuthenticatedFlows:
    """Test authenticated endpoints with admin token"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        """Get auth token for admin user"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "teji.ss1986@gmail.com",
            "password": "Admin123"
        })
        if resp.status_code != 200:
            pytest.skip(f"Auth failed: {resp.status_code} - {resp.text}")
        data = resp.json()
        self.token = data.get("token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        print(f"✓ Authenticated as admin")
    
    def test_leads_returns_list(self):
        """GET /api/campaign/leads returns lead list (lead_crud sub-router)"""
        resp = requests.get(f"{BASE_URL}/api/campaign/leads", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "leads" in data
        assert "total" in data
        print(f"✓ /leads returns {data.get('total', 0)} leads")
    
    def test_stats_returns_stats(self):
        """GET /api/campaign/stats returns stats (lead_crud)"""
        resp = requests.get(f"{BASE_URL}/api/campaign/stats", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "stats" in data or "campaign_status" in data
        print(f"✓ /stats returns: {data}")
    
    def test_overview_returns_summary(self):
        """GET /api/campaign/overview returns campaign + leads summary (lead_crud)"""
        resp = requests.get(f"{BASE_URL}/api/campaign/overview", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "leads_summary" in data or "campaign" in data
        print(f"✓ /overview returns summary")
    
    def test_competitor_templates_returns_keys(self):
        """GET /api/campaign/competitor-templates returns template keys (render_templates)"""
        resp = requests.get(f"{BASE_URL}/api/campaign/competitor-templates", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "templates" in data
        assert "whatsapp" in data["templates"]
        assert "email" in data["templates"]
        print(f"✓ /competitor-templates returns: {list(data['templates'].keys())}")
    
    def test_ops_status_returns_health(self):
        """GET /api/campaign/ops-status returns blocker health (auto_blast)"""
        resp = requests.get(f"{BASE_URL}/api/campaign/ops-status", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "channels" in data
        assert "all_green" in data
        print(f"✓ /ops-status returns: all_green={data.get('all_green')}")
    
    def test_auto_blast_status_returns_config(self):
        """GET /api/campaign/auto-blast/status returns config (auto_blast)"""
        resp = requests.get(f"{BASE_URL}/api/campaign/auto-blast/status", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
        assert "total_leads" in data
        print(f"✓ /auto-blast/status returns: enabled={data.get('enabled')}, total_leads={data.get('total_leads')}")
    
    def test_auto_blast_toggle(self):
        """POST /api/campaign/auto-blast/toggle with {enabled: true} works (auto_blast)"""
        # First get current state
        resp = requests.get(f"{BASE_URL}/api/campaign/auto-blast/status", headers=self.headers)
        current_enabled = resp.json().get("enabled", False)
        
        # Toggle to opposite
        resp = requests.post(
            f"{BASE_URL}/api/campaign/auto-blast/toggle",
            headers=self.headers,
            json={"enabled": not current_enabled}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        print(f"✓ /auto-blast/toggle works: enabled={data.get('enabled')}")
        
        # Toggle back to original
        requests.post(
            f"{BASE_URL}/api/campaign/auto-blast/toggle",
            headers=self.headers,
            json={"enabled": current_enabled}
        )
    
    def test_do_not_contact_returns_list(self):
        """GET /api/campaign/do-not-contact returns DNC list (lead_crud)"""
        resp = requests.get(f"{BASE_URL}/api/campaign/do-not-contact", headers=self.headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert "total" in data
        print(f"✓ /do-not-contact returns {data.get('total', 0)} entries")


# ══════════════════════════════════════════════
# Module 5: Health & Pillar Worker Regression
# ══════════════════════════════════════════════

class TestHealthAndPillarWorkers:
    """Test health endpoint and pillar worker status"""
    
    def test_health_returns_4_pillar_workers(self):
        """GET /api/health returns 200 with schedulers='4/4 pillar workers'"""
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        data = resp.json()
        # schedulers is nested inside checks
        schedulers = data.get("checks", {}).get("schedulers") or data.get("schedulers")
        assert schedulers == "4/4 pillar workers"
        print(f"✓ /api/health returns: schedulers={schedulers}")
    
    def test_pillar1_regression_auto_blast_status(self):
        """Pillar 1 regression: /api/campaign/auto-blast/status accessible"""
        resp = requests.get(f"{BASE_URL}/api/campaign/auto-blast/status")
        # Should return 401 (auth required) - not 500 or 404
        assert resp.status_code == 401
        print("✓ Pillar 1 regression OK: /auto-blast/status returns 401")
    
    def test_pillar2_regression_subscription_plans(self):
        """Pillar 2 regression: /api/subscription/plans accessible"""
        resp = requests.get(f"{BASE_URL}/api/subscription/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert "plans" in data
        print(f"✓ Pillar 2 regression OK: /subscription/plans returns {len(data.get('plans', []))} plans")
    
    def test_pillar3_regression_repair_pending(self):
        """Pillar 3 regression: /api/repair/pending accessible"""
        resp = requests.get(f"{BASE_URL}/api/repair/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert "fixes" in data or isinstance(data, list)
        print("✓ Pillar 3 regression OK: /repair/pending returns 200")


# ══════════════════════════════════════════════
# Module 6: Sub-Router File Structure
# ══════════════════════════════════════════════

class TestSubRouterFileStructure:
    """Verify the 4 sub-router files exist and have correct structure"""
    
    def test_lead_crud_exists(self):
        """lead_crud.py exists and has router"""
        from pillars.sales.routes.lead_crud import router
        routes = [r for r in router.routes if hasattr(r, 'path')]
        assert len(routes) > 0
        print(f"✓ lead_crud.py has {len(routes)} routes")
    
    def test_blast_service_exists(self):
        """blast_service.py exists and has router + execute_blast_for_lead"""
        from pillars.sales.routes.blast_service import router, execute_blast_for_lead
        routes = [r for r in router.routes if hasattr(r, 'path')]
        assert len(routes) > 0
        assert callable(execute_blast_for_lead)
        print(f"✓ blast_service.py has {len(routes)} routes + execute_blast_for_lead")
    
    def test_auto_blast_exists(self):
        """auto_blast.py exists and has router + 6 sequence runners"""
        from pillars.sales.routes.auto_blast import (
            router, run_daily_scrape, run_website_scans,
            run_email_sequence, run_whatsapp_sequence,
            run_sms_sequence, run_voice_sequence,
        )
        routes = [r for r in router.routes if hasattr(r, 'path')]
        assert len(routes) > 0
        print(f"✓ auto_blast.py has {len(routes)} routes + 6 sequence runners")
    
    def test_render_templates_exists(self):
        """render_templates.py exists and has router"""
        from pillars.sales.routes.render_templates import router
        routes = [r for r in router.routes if hasattr(r, 'path')]
        assert len(routes) > 0
        print(f"✓ render_templates.py has {len(routes)} routes")
    
    def test_shared_helpers_exist(self):
        """_shared.py exists and has helpers + templates"""
        from pillars.sales.routes._shared import (
            _get_db, _verify_admin, set_db,
            WHATSAPP_TEMPLATES, EMAIL_SUBJECTS, TARGET_CATEGORIES, COMPETITOR_TEMPLATES,
        )
        assert callable(_get_db)
        assert callable(_verify_admin)
        assert callable(set_db)
        assert isinstance(WHATSAPP_TEMPLATES, dict)
        assert isinstance(EMAIL_SUBJECTS, dict)
        assert isinstance(TARGET_CATEGORIES, list)
        assert isinstance(COMPETITOR_TEMPLATES, dict)
        print("✓ _shared.py has all helpers and templates")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
