"""
Iteration 167 Backend Tests — News Monitor, Voice Config, Competitor Templates
================================================================================
Tests for:
1. News Auto-Monitor with APScheduler (2h cycle, DDG search with rate limit fallback)
2. ORA voice config changes: TTS_VOICE=nova, CHUNK_WORDS=8
3. Competitor campaign templates (AUREM vs traditional agency, no competitor names)
"""

import pytest
import requests
import os
import re

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Auth failed: {response.status_code} - {response.text[:200]}")


@pytest.fixture
def auth_headers(auth_token):
    """Headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ═══════════════════════════════════════════════════════════════════
# NEWS MONITOR TESTS
# ═══════════════════════════════════════════════════════════════════

class TestNewsMonitorEndpoints:
    """Test news monitoring endpoints."""

    def test_get_monitor_topics(self, auth_headers):
        """GET /api/news/topics — returns 5 configured monitoring topics."""
        response = requests.get(f"{BASE_URL}/api/news/topics", headers=auth_headers, timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "topics" in data, "Response should contain 'topics' key"
        topics = data["topics"]
        assert isinstance(topics, list), "Topics should be a list"
        assert len(topics) == 5, f"Expected 5 topics, got {len(topics)}"
        
        # Verify expected topics
        expected_keywords = ["SEO", "website", "Canada", "developer", "business"]
        for topic in topics:
            assert isinstance(topic, str), "Each topic should be a string"
            assert len(topic) > 5, "Topic should have meaningful content"
        
        print(f"✓ GET /api/news/topics returned {len(topics)} topics: {topics}")

    def test_get_news_alerts(self, auth_headers):
        """GET /api/news/alerts — returns news alerts list (may be empty if DDG rate limited)."""
        response = requests.get(f"{BASE_URL}/api/news/alerts", headers=auth_headers, timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "alerts" in data, "Response should contain 'alerts' key"
        assert "total" in data, "Response should contain 'total' key"
        assert isinstance(data["alerts"], list), "Alerts should be a list"
        assert isinstance(data["total"], int), "Total should be an integer"
        
        print(f"✓ GET /api/news/alerts returned {data['total']} alerts")

    def test_get_news_leads(self, auth_headers):
        """GET /api/news/leads — returns lead-matched articles."""
        response = requests.get(f"{BASE_URL}/api/news/leads", headers=auth_headers, timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "leads" in data, "Response should contain 'leads' key"
        assert "total" in data, "Response should contain 'total' key"
        assert isinstance(data["leads"], list), "Leads should be a list"
        
        print(f"✓ GET /api/news/leads returned {data['total']} lead matches")

    def test_manual_news_fetch(self, auth_headers):
        """POST /api/news/fetch — triggers manual news fetch, returns new_articles + lead_matches count."""
        response = requests.post(f"{BASE_URL}/api/news/fetch", headers=auth_headers, timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # DDG may be rate limited, so we just check the response structure
        assert "new_articles" in data, "Response should contain 'new_articles' key"
        assert "lead_matches" in data, "Response should contain 'lead_matches' key"
        assert "timestamp" in data, "Response should contain 'timestamp' key"
        
        assert isinstance(data["new_articles"], int), "new_articles should be an integer"
        assert isinstance(data["lead_matches"], int), "lead_matches should be an integer"
        assert data["new_articles"] >= 0, "new_articles should be non-negative"
        assert data["lead_matches"] >= 0, "lead_matches should be non-negative"
        
        print(f"✓ POST /api/news/fetch returned: {data['new_articles']} new articles, {data['lead_matches']} lead matches")
        print(f"  Note: DDG may be rate limited — 0 articles is expected behavior")

    def test_news_endpoints_require_auth(self):
        """News endpoints should require authentication."""
        endpoints = [
            ("GET", "/api/news/alerts"),
            ("GET", "/api/news/leads"),
            ("POST", "/api/news/fetch"),
        ]
        
        for method, endpoint in endpoints:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            else:
                response = requests.post(f"{BASE_URL}{endpoint}", timeout=10)
            
            assert response.status_code == 401, f"{method} {endpoint} should require auth, got {response.status_code}"
        
        print("✓ News endpoints correctly require authentication")


# ═══════════════════════════════════════════════════════════════════
# CODE VERIFICATION TESTS (Direct file inspection)
# ═══════════════════════════════════════════════════════════════════

class TestCodeVerification:
    """Verify code changes by reading files directly."""

    def test_news_monitor_scheduler_registered(self):
        """Verify _news_monitor_scheduler is registered in startup_init.py."""
        startup_path = "/app/backend/services/startup_init.py"
        
        with open(startup_path, "r") as f:
            content = f.read()
        
        # Check for _news_monitor_scheduler function definition
        assert "_news_monitor_scheduler" in content, "startup_init.py should contain _news_monitor_scheduler"
        assert "async def _news_monitor_scheduler" in content, "_news_monitor_scheduler should be an async function"
        
        # Check it's started in start_all_background_schedulers
        assert 'news_monitor_scheduler' in content, "news_monitor_scheduler should be registered"
        assert '_safe_task(_news_monitor_scheduler(db), "news_monitor_scheduler")' in content, \
            "_news_monitor_scheduler should be started with _safe_task"
        
        # Check 2-hour interval
        assert "INTERVAL_HOURS = 2" in content, "News monitor should have 2-hour interval"
        
        print("✓ _news_monitor_scheduler is registered in startup_init.py with 2h cycle")

    def test_tts_voice_is_nova(self):
        """Verify TTS_VOICE is 'nova' in v2v_stream_engine.py."""
        v2v_path = "/app/backend/routers/v2v_stream_engine.py"
        
        with open(v2v_path, "r") as f:
            content = f.read()
        
        # Check TTS_VOICE = "nova"
        assert 'TTS_VOICE = "nova"' in content, f"TTS_VOICE should be 'nova', not 'alloy'"
        
        # Verify it's not alloy
        lines = content.split("\n")
        for line in lines:
            if line.strip().startswith("TTS_VOICE ="):
                assert '"nova"' in line, f"TTS_VOICE line should be 'nova': {line}"
                assert '"alloy"' not in line, f"TTS_VOICE should not be 'alloy': {line}"
                break
        
        print("✓ TTS_VOICE is 'nova' in v2v_stream_engine.py")

    def test_chunk_words_is_8(self):
        """Verify CHUNK_WORDS is 8 in ora_stream_router.py."""
        ora_path = "/app/backend/routers/ora_stream_router.py"
        
        with open(ora_path, "r") as f:
            content = f.read()
        
        # Check CHUNK_WORDS = 8
        assert "CHUNK_WORDS = 8" in content, f"CHUNK_WORDS should be 8, not 5"
        
        # Verify it's not 5
        lines = content.split("\n")
        for line in lines:
            if line.strip().startswith("CHUNK_WORDS ="):
                assert "= 8" in line, f"CHUNK_WORDS should be 8: {line}"
                assert "= 5" not in line, f"CHUNK_WORDS should not be 5: {line}"
                break
        
        print("✓ CHUNK_WORDS is 8 in ora_stream_router.py")


# ═══════════════════════════════════════════════════════════════════
# COMPETITOR TEMPLATES TESTS
# ═══════════════════════════════════════════════════════════════════

class TestCompetitorTemplates:
    """Test competitor comparison campaign templates."""

    def test_get_competitor_templates_endpoint(self, auth_headers):
        """GET /api/campaign/competitor-templates — returns whatsapp/email/sms/voice template keys."""
        response = requests.get(f"{BASE_URL}/api/campaign/competitor-templates", headers=auth_headers, timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "templates" in data, "Response should contain 'templates' key"
        assert "positioning" in data, "Response should contain 'positioning' key"
        
        templates = data["templates"]
        assert "whatsapp" in templates, "Templates should include 'whatsapp'"
        assert "email" in templates, "Templates should include 'email'"
        assert "sms" in templates, "Templates should include 'sms'"
        assert "voice" in templates, "Templates should include 'voice'"
        
        print(f"✓ GET /api/campaign/competitor-templates returned all channel keys")
        print(f"  WhatsApp: {templates['whatsapp']}")
        print(f"  Email: {len(templates['email'])} subject lines")
        print(f"  SMS: {templates['sms']}")
        print(f"  Voice: {templates['voice']}")

    def test_whatsapp_has_three_variants(self):
        """COMPETITOR_TEMPLATES has 3 WhatsApp variants: switch_pitch, post_demo, price_compare."""
        campaign_path = "/app/backend/routers/campaign_router.py"
        
        with open(campaign_path, "r") as f:
            content = f.read()
        
        # Check for the three WhatsApp variants
        assert '"switch_pitch"' in content, "WhatsApp should have 'switch_pitch' template"
        assert '"post_demo"' in content, "WhatsApp should have 'post_demo' template"
        assert '"price_compare"' in content, "WhatsApp should have 'price_compare' template"
        
        # Verify they're in the whatsapp section
        assert '"whatsapp": {' in content, "COMPETITOR_TEMPLATES should have 'whatsapp' section"
        
        print("✓ COMPETITOR_TEMPLATES has 3 WhatsApp variants: switch_pitch, post_demo, price_compare")

    def test_email_has_comparison_table(self):
        """COMPETITOR_TEMPLATES email has comparison HTML table (Agency vs AUREM)."""
        campaign_path = "/app/backend/routers/campaign_router.py"
        
        with open(campaign_path, "r") as f:
            content = f.read()
        
        # Check for comparison table elements
        assert "Traditional Agency vs AUREM" in content, "Email should have 'Traditional Agency vs AUREM' heading"
        assert "Typical Agency" in content, "Email should have 'Typical Agency' column"
        assert "<table" in content, "Email should contain HTML table"
        assert "Site scanning" in content, "Table should compare site scanning"
        assert "Fix deployment" in content, "Table should compare fix deployment"
        assert "Quarterly" in content, "Table should mention quarterly (agency)"
        assert "Every day" in content, "Table should mention every day (AUREM)"
        assert "$500-2,000" in content, "Table should show agency pricing"
        assert "$97" in content, "Table should show AUREM pricing"
        
        print("✓ COMPETITOR_TEMPLATES email has comparison HTML table (Agency vs AUREM)")

    def test_voice_has_switch_script(self):
        """COMPETITOR_TEMPLATES voice has switch_script for outbound calls."""
        campaign_path = "/app/backend/routers/campaign_router.py"
        
        with open(campaign_path, "r") as f:
            content = f.read()
        
        # Check for voice switch_script
        assert '"voice": {' in content, "COMPETITOR_TEMPLATES should have 'voice' section"
        assert '"switch_script"' in content, "Voice should have 'switch_script' template"
        assert "O R A from AUREM" in content, "Voice script should mention ORA from AUREM"
        assert "Press 1 for yes" in content, "Voice script should have keypress options"
        assert "press 2 to opt out" in content, "Voice script should have opt-out option"
        
        print("✓ COMPETITOR_TEMPLATES voice has switch_script for outbound calls")

    def test_no_competitor_names_in_templates(self):
        """No competitor names mentioned in any template (no OTTO, no specific agency names)."""
        campaign_path = "/app/backend/routers/campaign_router.py"
        
        with open(campaign_path, "r") as f:
            content = f.read()
        
        # Extract COMPETITOR_TEMPLATES section
        start_idx = content.find("COMPETITOR_TEMPLATES = {")
        end_idx = content.find("\n\n\n@router.get", start_idx)
        if end_idx == -1:
            end_idx = content.find("\n@router.get(\"/competitor-templates\")", start_idx)
        
        templates_section = content[start_idx:end_idx] if end_idx > start_idx else content[start_idx:start_idx+5000]
        
        # List of competitor names that should NOT appear (as whole words)
        # Using word boundary regex to avoid false positives like "bottom" matching "otto"
        forbidden_patterns = [
            r"\bOTTO\b", r"\bOtto\b",
            r"\bWix\b", r"\bWIX\b",
            r"\bSquarespace\b", r"\bSQUARESPACE\b",
            r"\bGoDaddy\b", r"\bGODADDY\b", r"\bGodaddy\b",
            r"\bWeebly\b", r"\bWEEBLY\b",
            r"\bDuda\b", r"\bDUDA\b",
            r"\bWebflow\b", r"\bWEBFLOW\b",
        ]
        
        for pattern in forbidden_patterns:
            match = re.search(pattern, templates_section)
            if match:
                assert False, f"Competitor name '{match.group()}' found in COMPETITOR_TEMPLATES"
        
        # Also check for generic agency names that might be specific
        assert "Agency X" not in templates_section, "Should not mention 'Agency X'"
        assert "Company Y" not in templates_section, "Should not mention 'Company Y'"
        
        print("✓ No competitor names mentioned in COMPETITOR_TEMPLATES (AUREM vs traditional agency only)")

    def test_competitor_templates_endpoint_requires_auth(self):
        """Competitor templates endpoint should require authentication."""
        response = requests.get(f"{BASE_URL}/api/campaign/competitor-templates", timeout=10)
        assert response.status_code == 401, f"Should require auth, got {response.status_code}"
        
        print("✓ /api/campaign/competitor-templates correctly requires authentication")


# ═══════════════════════════════════════════════════════════════════
# VOICE HEALTH CHECK TEST
# ═══════════════════════════════════════════════════════════════════

class TestVoiceHealthCheck:
    """Test voice engine health endpoint to verify config."""

    def test_voice_health_shows_nova(self):
        """GET /api/voice/health — should show tts_voice as 'nova'."""
        response = requests.get(f"{BASE_URL}/api/voice/health", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "ok", "Voice health should be ok"
        assert data.get("tts_voice") == "nova", f"TTS voice should be 'nova', got {data.get('tts_voice')}"
        
        print(f"✓ GET /api/voice/health shows tts_voice='nova'")
        print(f"  Service: {data.get('service')}")
        print(f"  TTS Model: {data.get('tts_model')}")
        print(f"  LLM Model: {data.get('llm_model')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
