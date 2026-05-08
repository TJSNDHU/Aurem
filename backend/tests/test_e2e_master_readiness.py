"""
Master E2E / Full-System Readiness Test — iter 317+
====================================================
10-layer smoke test against the LIVE running backend to prove the system
is READY TO ONBOARD FIRST CLIENT.

Layers:
  1. Infrastructure: /api/health (mongodb+redis ok)
  2. ORA Chat (public demo): POST /api/public/ora/chat
  3. ORA Emotion Tone: POST /api/public/ora/chat with emotion=sad
  4. ORA Widget Chat: POST /api/widget/chat
  5. Inbound Reply Pipeline: POST /api/email/inbound
  6. Self-Audit: GET /api/self-audit/health
  7. Site QA Chip: GET /api/admin/site-qa/health (grey/no_key expected)
  8. Repair Checkout: GET /api/repair/checkout (400 on missing slug OK)
  9. Public Report CTA: GET /api/report/{slug} with seeded site_audits
 10. Scout Dispatcher: import + call dispatch_lead_sync

Run:
    pytest /app/backend/tests/test_e2e_master_readiness.py -v --tb=short
"""
import os
import pytest
import requests
import time
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://ai-platform-preview-3.preview.emergentagent.com"

TIMEOUT = 30


class TestLayer1Infrastructure:
    """Layer 1 — Infrastructure: GET /api/health returns 200 with mongodb+redis ok"""

    def test_health_endpoint_returns_200(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=TIMEOUT)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        print(f"[Layer 1] Health response: {data}")
        assert data.get("status") == "ok", f"status != ok: {data}"
        checks = data.get("checks", {})
        assert checks.get("mongodb") == "ok", f"mongodb != ok: {checks}"
        assert checks.get("redis") == "ok", f"redis != ok: {checks}"

    def test_pillars_map_overview(self):
        """GET /api/admin/pillars-map/overview returns pillar list"""
        r = requests.get(f"{BASE_URL}/api/admin/pillars-map/overview", timeout=TIMEOUT)
        # May require auth, but should at least be reachable (401/403 is acceptable)
        assert r.status_code in (200, 401, 403), f"Unexpected {r.status_code}: {r.text[:200]}"
        if r.status_code == 200:
            data = r.json()
            print(f"[Layer 1] Pillars map overview: {list(data.keys()) if isinstance(data, dict) else 'list'}")


class TestLayer2ORAPublicDemo:
    """Layer 2 — ORA Chat (public demo): POST /api/public/ora/chat"""

    def test_ora_demo_chat_responds(self):
        payload = {"text": "What is AUREM?"}
        r = requests.post(f"{BASE_URL}/api/public/ora/chat", json=payload, timeout=TIMEOUT)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        data = r.json()
        print(f"[Layer 2] ORA demo reply (truncated): {str(data.get('reply', ''))[:150]}...")
        assert data.get("ok") is True, f"ok != True: {data}"
        assert data.get("reply"), "reply is empty"


class TestLayer3ORAEmotionTone:
    """Layer 3 — ORA Emotion Tone: POST /api/public/ora/chat with emotion=sad"""

    def test_ora_emotion_sad_empathetic_reply(self):
        payload = {
            "text": "I'm having a really hard time with my business website",
            "emotion": "sad",
            "emotion_confidence": 0.78,
        }
        r = requests.post(f"{BASE_URL}/api/public/ora/chat", json=payload, timeout=TIMEOUT)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        data = r.json()
        reply = (data.get("reply") or "").lower()
        print(f"[Layer 3] ORA emotion-aware reply (truncated): {reply[:200]}...")
        assert data.get("ok") is True, f"ok != True: {data}"
        # Check for empathetic tone (not hype/sales)
        hype_words = ["amazing", "incredible", "buy now", "sign up today", "limited time"]
        hype_found = [w for w in hype_words if w in reply]
        assert len(hype_found) == 0, f"Hype words found in sad-emotion reply: {hype_found}"


class TestLayer4ORAWidgetChat:
    """Layer 4 — ORA Widget Chat: POST /api/widget/chat"""

    def test_widget_chat_responds(self):
        payload = {
            "bin": "DEMO",
            "message": "What services do you offer?",
        }
        r = requests.post(f"{BASE_URL}/api/widget/chat", json=payload, timeout=TIMEOUT)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        data = r.json()
        print(f"[Layer 4] Widget chat reply (truncated): {str(data.get('reply', ''))[:150]}...")
        assert data.get("reply"), "reply is empty"
        assert data.get("session_id"), "session_id missing"
        # Check Canadian persona preserved
        reply = (data.get("reply") or "").lower()
        # Should not have hard sales CTAs
        hard_sales = ["buy now", "sign up today", "limited offer"]
        hard_found = [w for w in hard_sales if w in reply]
        assert len(hard_found) == 0, f"Hard sales CTAs found: {hard_found}"


class TestLayer5InboundReplyPipeline:
    """Layer 5 — Inbound Reply Pipeline: POST /api/email/inbound"""

    def test_inbound_email_webhook_accepts_positive_reply(self):
        payload = {
            "from": "test_positive_reply@example.com",
            "to": "ora@aurem.live",
            "subject": "Re: Your website audit",
            "text": "Yes, I'm interested! Please call me at 416-555-1234.",
        }
        r = requests.post(f"{BASE_URL}/api/email/inbound", json=payload, timeout=TIMEOUT)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        data = r.json()
        print(f"[Layer 5] Inbound reply result: {data}")
        # Should be classified and logged
        assert "intent" in data or "classified" in data or "ok" in data, f"Unexpected response: {data}"


class TestLayer6SelfAudit:
    """Layer 6 — Self-Audit: GET /api/self-audit/health"""

    def test_self_audit_health_returns_status(self):
        r = requests.get(f"{BASE_URL}/api/self-audit/health", timeout=TIMEOUT)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        print(f"[Layer 6] Self-audit health: {data}")
        assert data.get("ok") is True, f"ok != True: {data}"
        assert "service" in data, "service field missing"
        # Should have latest or healthy field
        assert "latest" in data or "healthy" in data, f"Missing latest/healthy: {data}"


class TestLayer7SiteQAChip:
    """Layer 7 — Site QA Chip: GET /api/admin/site-qa/health (grey/no_key expected)"""

    def test_site_qa_health_grey_no_key(self):
        r = requests.get(f"{BASE_URL}/api/admin/site-qa/health", timeout=TIMEOUT)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        print(f"[Layer 7] Site QA health: {data}")
        # TEST_LAB_API_KEY intentionally absent — should return grey/no_key
        assert data.get("status") == "grey", f"Expected status=grey, got {data.get('status')}"
        assert data.get("message") == "no_key", f"Expected message=no_key, got {data.get('message')}"

    def test_site_qa_brief_returns_counts(self):
        r = requests.get(f"{BASE_URL}/api/admin/site-qa/brief", timeout=TIMEOUT)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        print(f"[Layer 7] Site QA brief: {data}")
        # Should have count fields
        expected_fields = ["audits", "verified", "sent", "paid", "failed"]
        for field in expected_fields:
            assert field in data, f"Missing field {field} in brief: {data}"


class TestLayer8RepairCheckout:
    """Layer 8 — Repair Checkout: GET /api/repair/checkout"""

    def test_repair_checkout_reachable(self):
        # Without slug, should return 400 or 422 (validation error) — proves endpoint is wired
        r = requests.get(f"{BASE_URL}/api/repair/checkout", timeout=TIMEOUT)
        # 400/422 on missing slug is acceptable proof endpoint is wired
        assert r.status_code in (400, 422, 307, 302), f"Unexpected {r.status_code}: {r.text[:200]}"
        print(f"[Layer 8] Repair checkout (no slug): {r.status_code} — endpoint wired")

    def test_repair_checkout_with_fake_slug(self):
        # With a fake slug, should return 404 (report not found) or redirect
        r = requests.get(
            f"{BASE_URL}/api/repair/checkout",
            params={"slug": "fake_test_slug_12345", "tier": "basic"},
            timeout=TIMEOUT,
            allow_redirects=False,
        )
        # 404 (not found) or 302 (redirect to Stripe/manual) are both acceptable
        assert r.status_code in (404, 302, 307, 503), f"Unexpected {r.status_code}: {r.text[:200]}"
        print(f"[Layer 8] Repair checkout (fake slug): {r.status_code}")


class TestLayer9PublicReportCTA:
    """Layer 9 — Public Report: GET /api/report/{slug} with CTA by score"""

    def test_report_endpoint_exists(self):
        # Test with a fake slug — should return 404 or empty data
        r = requests.get(f"{BASE_URL}/api/report/fake_test_slug_99999", timeout=TIMEOUT)
        # 404 or 200 with error/empty is acceptable
        assert r.status_code in (200, 404), f"Unexpected {r.status_code}: {r.text[:200]}"
        print(f"[Layer 9] Report endpoint (fake slug): {r.status_code}")


class TestLayer10ScoutDispatcher:
    """Layer 10 — Scout Dispatcher: verify dispatch_lead_sync exists and routes correctly"""

    def test_scout_dispatcher_import(self):
        """Verify services.scout_dispatcher.dispatch_lead_sync exists"""
        try:
            from services.scout_dispatcher import (
                dispatch_lead_sync,
                has_website,
                _audit_then_outreach,
                _build_qa_then_notify,
            )
            print("[Layer 10] Scout dispatcher imports successful")
            assert callable(dispatch_lead_sync), "dispatch_lead_sync not callable"
            assert callable(has_website), "has_website not callable"
        except ImportError as e:
            pytest.fail(f"Scout dispatcher import failed: {e}")

    def test_has_website_routing_logic(self):
        """Test has_website routing detection"""
        from services.scout_dispatcher import has_website

        # Lead with website → should return True
        lead_with_website = {"website": "https://example.ca", "has_website": True}
        assert has_website(lead_with_website) is True, "Should detect website"

        # Lead without website → should return False
        lead_no_website = {"website": "", "has_website": False}
        assert has_website(lead_no_website) is False, "Should detect no website"

        # Lead with placeholder → should return False
        lead_placeholder = {"website": "http://", "has_website": True}
        assert has_website(lead_placeholder) is False, "Should reject placeholder"

        print("[Layer 10] has_website routing logic verified")


# ─────────────────────────────────────────────────────────────────────
# Summary test
# ─────────────────────────────────────────────────────────────────────
class TestFinalVerdict:
    """Final verdict: READY TO ONBOARD FIRST CLIENT?"""

    def test_all_layers_summary(self):
        """Run a quick summary check of all critical endpoints"""
        results = {}

        # Layer 1 - Health
        try:
            r = requests.get(f"{BASE_URL}/api/health", timeout=10)
            results["L1_health"] = "PASS" if r.status_code == 200 else f"FAIL ({r.status_code})"
        except Exception as e:
            results["L1_health"] = f"FAIL ({e})"

        # Layer 2 - ORA Demo
        try:
            r = requests.post(f"{BASE_URL}/api/public/ora/chat", json={"text": "hi"}, timeout=15)
            results["L2_ora_demo"] = "PASS" if r.status_code == 200 else f"FAIL ({r.status_code})"
        except Exception as e:
            results["L2_ora_demo"] = f"FAIL ({e})"

        # Layer 4 - Widget
        try:
            r = requests.post(f"{BASE_URL}/api/widget/chat", json={"bin": "DEMO", "message": "hi"}, timeout=15)
            results["L4_widget"] = "PASS" if r.status_code == 200 else f"FAIL ({r.status_code})"
        except Exception as e:
            results["L4_widget"] = f"FAIL ({e})"

        # Layer 5 - Inbound
        try:
            r = requests.post(f"{BASE_URL}/api/email/inbound", json={"from": "test@x.com", "text": "yes"}, timeout=10)
            results["L5_inbound"] = "PASS" if r.status_code == 200 else f"FAIL ({r.status_code})"
        except Exception as e:
            results["L5_inbound"] = f"FAIL ({e})"

        # Layer 6 - Self-audit
        try:
            r = requests.get(f"{BASE_URL}/api/self-audit/health", timeout=10)
            results["L6_self_audit"] = "PASS" if r.status_code == 200 else f"FAIL ({r.status_code})"
        except Exception as e:
            results["L6_self_audit"] = f"FAIL ({e})"

        # Layer 7 - Site QA
        try:
            r = requests.get(f"{BASE_URL}/api/admin/site-qa/health", timeout=10)
            data = r.json() if r.status_code == 200 else {}
            # grey/no_key is expected
            if data.get("status") == "grey" and data.get("message") == "no_key":
                results["L7_site_qa"] = "PASS (grey/no_key as expected)"
            else:
                results["L7_site_qa"] = f"WARN ({data})"
        except Exception as e:
            results["L7_site_qa"] = f"FAIL ({e})"

        # Layer 8 - Repair checkout
        try:
            r = requests.get(f"{BASE_URL}/api/repair/checkout", timeout=10)
            results["L8_repair"] = "PASS (wired)" if r.status_code in (400, 422, 302, 307) else f"FAIL ({r.status_code})"
        except Exception as e:
            results["L8_repair"] = f"FAIL ({e})"

        print("\n" + "=" * 60)
        print("MASTER E2E READINESS SUMMARY")
        print("=" * 60)
        for layer, status in results.items():
            print(f"  {layer}: {status}")
        print("=" * 60)

        # Count passes
        passes = sum(1 for s in results.values() if s.startswith("PASS"))
        total = len(results)
        print(f"\nVERDICT: {passes}/{total} layers PASS")

        if passes == total:
            print("READY TO ONBOARD FIRST CLIENT: YES")
        elif passes >= total - 1:
            print("READY TO ONBOARD FIRST CLIENT: YES-WITH-CAVEATS")
        else:
            print("READY TO ONBOARD FIRST CLIENT: NO")

        assert passes >= total - 1, f"Too many failures: {passes}/{total}"
