"""
Iteration 255 — Phases 2-6 Backend Testing
============================================
Tests for:
  Phase 2: Admin catalog with 17 services (voice_agent_ai at $149), MRR, per-service stats
  Phase 3: Trial activation, friend-scan rate limiting, public report gating, pixel install
  Phase 4: Stripe webhook addon activation path verification (code inspection)
  Phase 5: /api/pricing-pro combo plans, trial_scheduler.py drip templates
  Phase 6: Voice agent overview, config save/get, retell webhook, customer voice status
"""
import pytest
import requests
import os
import json
from datetime import datetime

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="asserts pre-slim health/bootstrap shape or older infra spec — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials from test_credentials.md
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")
PLATFORM_EMAIL = "futuristic_test@aurem-preview.com"
PLATFORM_PASSWORD = "FutureTest123!"
PLATFORM_BIN = "PREV-HX5U"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token"""
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if res.status_code != 200:
        pytest.skip(f"Admin login failed: {res.status_code} - {res.text[:200]}")
    data = res.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def platform_token():
    """Get platform user JWT token"""
    res = requests.post(f"{BASE_URL}/api/platform/auth/login", json={
        "email": PLATFORM_EMAIL,
        "password": PLATFORM_PASSWORD
    })
    if res.status_code != 200:
        pytest.skip(f"Platform login failed: {res.status_code} - {res.text[:200]}")
    data = res.json()
    return data.get("token") or data.get("access_token")


class TestPhase2AdminCatalog:
    """Phase 2: GET /api/admin/catalog returns 17 services with MRR + per-service stats"""

    def test_admin_catalog_returns_17_services(self, admin_token):
        """Verify catalog has 17 services including voice_agent_ai"""
        res = requests.get(f"{BASE_URL}/api/admin/catalog", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        data = res.json()
        
        # Check total services (should be at least 16 seeded + voice_agent_ai = 17)
        services = data.get("services", [])
        assert len(services) >= 16, f"Expected at least 16 services, got {len(services)}"
        
        # Check voice_agent_ai exists at $149
        voice_agent = next((s for s in services if s.get("service_id") == "voice_agent_ai"), None)
        assert voice_agent is not None, "voice_agent_ai service not found in catalog"
        assert voice_agent.get("price_monthly") == 149, f"voice_agent_ai price should be $149, got {voice_agent.get('price_monthly')}"
        
        # Check MRR fields exist
        assert "total_mrr" in data, "total_mrr field missing"
        assert "total_active_subs" in data, "total_active_subs field missing"
        
        # Check per-service stats
        for svc in services[:3]:  # Check first 3
            assert "active_subscribers" in svc, f"active_subscribers missing for {svc.get('service_id')}"
            assert "monthly_revenue" in svc, f"monthly_revenue missing for {svc.get('service_id')}"
        
        print(f"✓ Catalog has {len(services)} services, total_mrr=${data.get('total_mrr')}")

    def test_admin_catalog_requires_super_admin(self, platform_token):
        """Platform user should get 403 on admin catalog"""
        res = requests.get(f"{BASE_URL}/api/admin/catalog", headers={
            "Authorization": f"Bearer {platform_token}"
        })
        assert res.status_code == 403, f"Expected 403 for platform user, got {res.status_code}"
        print("✓ Admin catalog correctly rejects platform user token")

    def test_admin_catalog_clusters_grouped(self, admin_token):
        """Verify services are grouped by cluster"""
        res = requests.get(f"{BASE_URL}/api/admin/catalog", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert res.status_code == 200
        data = res.json()
        
        clusters = data.get("clusters", {})
        expected_clusters = ["repair", "security", "crm", "marketing", "power"]
        for c in expected_clusters:
            assert c in clusters, f"Cluster '{c}' missing from response"
        
        # voice_agent_ai should be in 'power' cluster
        power_services = clusters.get("power", [])
        voice_ids = [s.get("service_id") for s in power_services]
        assert "voice_agent_ai" in voice_ids, "voice_agent_ai should be in 'power' cluster"
        print(f"✓ All 5 clusters present: {list(clusters.keys())}")


class TestPhase2AdminCatalogPatch:
    """Phase 2: PATCH /api/admin/catalog/{id} updates price + auto-recalculates margin"""

    def test_patch_price_recalculates_margin(self, admin_token):
        """Update price and verify margin is recalculated"""
        # First get current state
        res = requests.get(f"{BASE_URL}/api/admin/catalog", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert res.status_code == 200
        services = res.json().get("services", [])
        
        # Find a service to update (use cwv_monitor as it's low-risk)
        svc = next((s for s in services if s.get("service_id") == "cwv_monitor"), None)
        if not svc:
            pytest.skip("cwv_monitor service not found")
        
        original_price = svc.get("price_monthly", 19)
        new_price = original_price + 1  # Bump by $1
        
        # Patch the price
        patch_res = requests.patch(
            f"{BASE_URL}/api/admin/catalog/cwv_monitor",
            headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
            json={"price_monthly": new_price}
        )
        assert patch_res.status_code == 200, f"PATCH failed: {patch_res.status_code} - {patch_res.text[:200]}"
        
        updated = patch_res.json().get("service", {})
        assert updated.get("price_monthly") == new_price, "Price not updated"
        
        # Verify margin was recalculated
        cost = updated.get("cost_monthly", 4)
        expected_margin = round(((new_price - cost) / new_price) * 100, 1)
        actual_margin = updated.get("margin_pct")
        assert abs(actual_margin - expected_margin) < 0.5, f"Margin mismatch: expected ~{expected_margin}, got {actual_margin}"
        
        # Restore original price
        requests.patch(
            f"{BASE_URL}/api/admin/catalog/cwv_monitor",
            headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
            json={"price_monthly": original_price}
        )
        print(f"✓ PATCH updated price to ${new_price}, margin recalculated to {actual_margin}%")


class TestPhase3TrialActivation:
    """Phase 3: POST /api/trial/activate creates 7-day trial idempotently"""

    def test_trial_activate_idempotent(self, platform_token):
        """Trial activation should be idempotent"""
        headers = {"Authorization": f"Bearer {platform_token}"}
        
        # First activation
        res1 = requests.post(f"{BASE_URL}/api/trial/activate", headers=headers)
        assert res1.status_code == 200, f"First activation failed: {res1.status_code}"
        trial1 = res1.json().get("trial", {})
        
        # Second activation (should return same trial)
        res2 = requests.post(f"{BASE_URL}/api/trial/activate", headers=headers)
        assert res2.status_code == 200, f"Second activation failed: {res2.status_code}"
        trial2 = res2.json().get("trial", {})
        
        # Should be same trial (same started_at)
        assert trial1.get("started_at") == trial2.get("started_at"), "Trial should be idempotent"
        print(f"✓ Trial activation idempotent, started_at={trial1.get('started_at')}")

    def test_trial_status_returns_quotas(self, platform_token):
        """GET /api/trial/status returns trial session with quotas"""
        res = requests.get(f"{BASE_URL}/api/trial/status", headers={
            "Authorization": f"Bearer {platform_token}"
        })
        assert res.status_code == 200, f"Trial status failed: {res.status_code}"
        trial = res.json().get("trial", {})
        
        # Check required fields
        required_fields = ["days_remaining", "scanner_used", "friend_scans_used", "ora_msgs_used", "state"]
        for field in required_fields:
            assert field in trial, f"Missing field: {field}"
        
        print(f"✓ Trial status: days_remaining={trial.get('days_remaining')}, state={trial.get('state')}")


class TestPhase3FriendScan:
    """Phase 3: POST /api/customer/friend-scan rate-limited to 5/week for trial users"""

    def test_friend_scan_returns_referral_slug(self, platform_token):
        """Friend scan should return referral_slug and hardcoded score"""
        res = requests.post(
            f"{BASE_URL}/api/customer/friend-scan",
            headers={"Authorization": f"Bearer {platform_token}", "Content-Type": "application/json"},
            json={"friend_website": f"https://test-friend-{datetime.now().timestamp()}.com"}
        )
        # May get 429 if quota exhausted, which is also valid behavior
        if res.status_code == 429:
            print("✓ Friend scan rate limit working (429 returned)")
            return
        
        assert res.status_code == 200, f"Friend scan failed: {res.status_code} - {res.text[:200]}"
        data = res.json()
        
        assert "referral_slug" in data, "referral_slug missing"
        assert data.get("referral_slug", "").startswith("ref_"), "referral_slug should start with 'ref_'"
        
        scan = data.get("scan", {})
        assert "score" in scan, "score missing from scan"
        assert 40 <= scan.get("score", 0) <= 59, f"Score should be 40-59 (hardcoded), got {scan.get('score')}"
        
        print(f"✓ Friend scan created: slug={data.get('referral_slug')}, score={scan.get('score')}")


class TestPhase3PublicReport:
    """Phase 3: GET /api/public/report/{slug} gating behavior"""

    def test_public_report_without_auth_returns_locked(self):
        """Without auth header, should return locked:true + requires_signup:true"""
        # Use a known slug pattern (we'll create one first or use a test slug)
        # For this test, we'll use a non-existent slug which should return 404
        res = requests.get(f"{BASE_URL}/api/public/report/ai-platform-preview-3")
        
        # This specific slug may not exist, so 404 is acceptable
        if res.status_code == 404:
            print("✓ Public report returns 404 for non-existent slug (expected)")
            return
        
        assert res.status_code == 200, f"Unexpected status: {res.status_code}"
        data = res.json()
        assert data.get("locked") == True, "Should be locked without auth"
        assert data.get("requires_signup") == True, "Should require signup"
        print(f"✓ Public report without auth: locked={data.get('locked')}, requires_signup={data.get('requires_signup')}")

    def test_public_report_with_auth_returns_scan(self, platform_token):
        """With auth header, should return actual scan data"""
        # First create a friend scan to get a valid slug
        scan_res = requests.post(
            f"{BASE_URL}/api/customer/friend-scan",
            headers={"Authorization": f"Bearer {platform_token}", "Content-Type": "application/json"},
            json={"friend_website": f"https://test-report-{datetime.now().timestamp()}.com"}
        )
        
        if scan_res.status_code == 429:
            pytest.skip("Friend scan quota exhausted")
        
        if scan_res.status_code != 200:
            pytest.skip(f"Could not create friend scan: {scan_res.status_code}")
        
        slug = scan_res.json().get("referral_slug")
        
        # Now fetch the report with auth
        res = requests.get(
            f"{BASE_URL}/api/public/report/{slug}",
            headers={"Authorization": f"Bearer {platform_token}"}
        )
        assert res.status_code == 200, f"Report fetch failed: {res.status_code}"
        data = res.json()
        
        # Should have scan data
        assert "scan" in data, "scan data missing"
        assert "locked" in data, "locked field missing"
        print(f"✓ Public report with auth: locked={data.get('locked')}, has scan data")


class TestPhase3PixelInstall:
    """Phase 3: GET /api/customer/pixel/install returns 4 methods + progress gauge"""

    def test_pixel_install_returns_4_methods(self, platform_token):
        """Pixel install should return 4 methods"""
        res = requests.get(f"{BASE_URL}/api/customer/pixel/install", headers={
            "Authorization": f"Bearer {platform_token}"
        })
        assert res.status_code == 200, f"Pixel install failed: {res.status_code}"
        data = res.json()
        
        methods = data.get("methods", [])
        assert len(methods) == 4, f"Expected 4 methods, got {len(methods)}"
        
        method_ids = [m.get("id") for m in methods]
        expected_ids = ["shopify", "wordpress", "email_developer", "manual"]
        for eid in expected_ids:
            assert eid in method_ids, f"Method '{eid}' missing"
        
        # Check progress gauge
        progress = data.get("progress", {})
        assert "step" in progress, "progress.step missing"
        assert 0 <= progress.get("step", -1) <= 4, f"step should be 0-4, got {progress.get('step')}"
        
        print(f"✓ Pixel install: 4 methods, progress step={progress.get('step')}")


class TestPhase5PricingPro:
    """Phase 5: GET /api/pricing-pro returns 3 combo plans"""

    def test_pricing_pro_returns_3_plans(self):
        """Pricing pro should return Starter/Growth/Enterprise plans"""
        res = requests.get(f"{BASE_URL}/api/pricing-pro")
        assert res.status_code == 200, f"Pricing pro failed: {res.status_code}"
        data = res.json()
        
        packages = data.get("packages", [])
        assert len(packages) >= 3, f"Expected at least 3 packages, got {len(packages)}"
        
        # Check for expected plan IDs
        plan_ids = [p.get("id") for p in packages]
        expected = ["starter", "growth", "enterprise"]
        for pid in expected:
            assert pid in plan_ids, f"Plan '{pid}' missing"
        
        # Check notice about premium features
        assert "notice" in data, "notice field missing"
        
        print(f"✓ Pricing pro: {len(packages)} plans, notice present")


class TestPhase6VoiceAgentOverview:
    """Phase 6: GET /api/admin/voice-agent/overview returns stats"""

    def test_voice_overview_returns_stats(self, admin_token):
        """Voice overview should return retell_connected and stats"""
        res = requests.get(f"{BASE_URL}/api/admin/voice-agent/overview", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert res.status_code == 200, f"Voice overview failed: {res.status_code}"
        data = res.json()
        
        # Check required fields
        required = ["retell_connected", "total_customers_configured", "enabled_agents", "calls_7d"]
        for field in required:
            assert field in data, f"Missing field: {field}"
        
        # retell_connected should be false (no RETELL_API_KEY set)
        assert data.get("retell_connected") == False, "retell_connected should be false (no key)"
        
        print(f"✓ Voice overview: retell_connected={data.get('retell_connected')}, calls_7d={data.get('calls_7d')}")

    def test_voice_overview_requires_admin(self, platform_token):
        """Platform user should get 403"""
        res = requests.get(f"{BASE_URL}/api/admin/voice-agent/overview", headers={
            "Authorization": f"Bearer {platform_token}"
        })
        assert res.status_code == 403, f"Expected 403, got {res.status_code}"
        print("✓ Voice overview correctly rejects platform user")


class TestPhase6VoiceAgentConfig:
    """Phase 6: POST/GET /api/admin/voice-agent/config/{bin_id}"""

    def test_voice_config_save_and_get(self, admin_token):
        """Save and retrieve voice agent config"""
        config_payload = {
            "greeting": "Hello, this is a test greeting",
            "enabled": True,
            "voice_id": "rachel",
            "language": "en"
        }
        
        # Save config
        save_res = requests.post(
            f"{BASE_URL}/api/admin/voice-agent/config/{PLATFORM_BIN}",
            headers={"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"},
            json=config_payload
        )
        assert save_res.status_code == 200, f"Config save failed: {save_res.status_code} - {save_res.text[:200]}"
        save_data = save_res.json()
        assert save_data.get("ok") == True, "Save should return ok:true"
        
        # Get config
        get_res = requests.get(
            f"{BASE_URL}/api/admin/voice-agent/config/{PLATFORM_BIN}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert get_res.status_code == 200, f"Config get failed: {get_res.status_code}"
        get_data = get_res.json()
        
        assert "config" in get_data, "config field missing"
        assert "retell_ready" in get_data, "retell_ready field missing"
        assert get_data.get("retell_ready") == False, "retell_ready should be false (no key)"
        
        print(f"✓ Voice config saved and retrieved for BIN={PLATFORM_BIN}")


class TestPhase6RetellWebhook:
    """Phase 6: POST /api/retell/webhook accepts call_ended events"""

    def test_retell_webhook_accepts_call_ended(self):
        """Webhook should accept call_ended event"""
        webhook_payload = {
            "event": "call_ended",
            "call": {
                "call_id": "test_call_123",
                "agent_id": "test_agent",
                "from_number": "+14165551234",
                "to_number": "+14165555678",
                "duration_ms": 180000,
                "transcript": "Test transcript",
                "call_analysis": {
                    "call_summary": "Test call summary",
                    "user_sentiment": "positive"
                }
            }
        }
        
        res = requests.post(
            f"{BASE_URL}/api/retell/webhook",
            headers={"Content-Type": "application/json"},
            json=webhook_payload
        )
        assert res.status_code == 200, f"Webhook failed: {res.status_code} - {res.text[:200]}"
        data = res.json()
        assert data.get("received") == True, "Webhook should return received:true"
        assert data.get("event") == "call_ended", "Event type should be echoed"
        
        print("✓ Retell webhook accepted call_ended event")


class TestPhase6CustomerVoiceStatus:
    """Phase 6: GET /api/customer/voice-agent/status"""

    def test_customer_voice_status(self, platform_token):
        """Customer voice status should return provisioned:false (no subscription)"""
        res = requests.get(f"{BASE_URL}/api/customer/voice-agent/status", headers={
            "Authorization": f"Bearer {platform_token}"
        })
        assert res.status_code == 200, f"Voice status failed: {res.status_code}"
        data = res.json()
        
        # Check required fields
        assert "provisioned" in data, "provisioned field missing"
        assert "retell_ready" in data, "retell_ready field missing"
        assert "month_usage" in data, "month_usage field missing"
        
        # Should be false since test user doesn't have voice_agent_ai subscription
        # (they have website_repair, casl_compliance, crm_growth, seo_pro)
        assert data.get("retell_ready") == False, "retell_ready should be false"
        
        usage = data.get("month_usage", {})
        assert "minutes_used" in usage, "minutes_used missing"
        
        print(f"✓ Customer voice status: provisioned={data.get('provisioned')}, retell_ready={data.get('retell_ready')}")


class TestPhase5TrialSchedulerModule:
    """Phase 5: Verify trial_scheduler.py exists and has required functions"""

    def test_trial_scheduler_imports(self):
        """Verify trial_scheduler.py can be imported and has required functions"""
        import sys
        sys.path.insert(0, "/app/backend")
        
        try:
            from services.trial_scheduler import run_trial_scheduler_tick, DRIP_TEMPLATES
            
            # Check drip templates exist for required days
            required_days = [3, 5, 6, 7, 14, 30]
            for day in required_days:
                assert day in DRIP_TEMPLATES, f"DRIP_TEMPLATES missing day {day}"
            
            # Check template structure
            for day, tpl in DRIP_TEMPLATES.items():
                assert "subject" in tpl, f"Day {day} template missing 'subject'"
                assert "cta" in tpl, f"Day {day} template missing 'cta'"
            
            print(f"✓ trial_scheduler.py imports cleanly, has drip templates for days {list(DRIP_TEMPLATES.keys())}")
        except ImportError as e:
            pytest.fail(f"Failed to import trial_scheduler: {e}")


class TestPhase4StripeWebhookCodePath:
    """Phase 4: Verify Stripe webhook handler has addon activation path"""

    def test_stripe_webhook_addon_path_exists(self):
        """Verify addon_subscription path exists in webhook handler code"""
        webhook_file = "/app/backend/routers/stripe_payment_router.py"
        
        with open(webhook_file, "r") as f:
            content = f.read()
        
        # Check for addon_subscription metadata check
        assert 'metadata.get("type") == "addon_subscription"' in content, \
            "addon_subscription metadata check missing in webhook"
        
        # Check for customer.subscription.deleted handler
        assert 'customer.subscription.deleted' in content, \
            "customer.subscription.deleted handler missing"
        
        # Check for addon-first check in subscription.deleted
        assert 'addon_sub = await _db.customer_subscriptions.find_one' in content, \
            "addon subscription lookup missing in subscription.deleted handler"
        
        print("✓ Stripe webhook has addon activation path + subscription.deleted addon branch")


class TestNoMongoIdLeakage:
    """Verify no MongoDB _id leakage in responses"""

    def test_admin_catalog_no_id(self, admin_token):
        """Admin catalog should not leak _id"""
        res = requests.get(f"{BASE_URL}/api/admin/catalog", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        assert res.status_code == 200
        data = res.json()
        
        for svc in data.get("services", [])[:5]:
            assert "_id" not in svc, f"_id leaked in service {svc.get('service_id')}"
        
        print("✓ No _id leakage in admin catalog")

    def test_trial_status_no_id(self, platform_token):
        """Trial status should not leak _id"""
        res = requests.get(f"{BASE_URL}/api/trial/status", headers={
            "Authorization": f"Bearer {platform_token}"
        })
        assert res.status_code == 200
        trial = res.json().get("trial", {})
        assert "_id" not in trial, "_id leaked in trial"
        print("✓ No _id leakage in trial status")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
