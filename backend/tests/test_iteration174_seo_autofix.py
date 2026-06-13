"""
Test Suite: AUREM Pulse SEO Auto-Fix Endpoints (Iteration 174)
==============================================================
Tests the 5 new SEO fix endpoints + auto-fix-all master button:
1. POST /api/shopify/pulse/fix/meta-descriptions - AI meta description generation
2. POST /api/shopify/pulse/fix/page-titles - AI page title optimization
3. POST /api/shopify/pulse/fix/schema-markup - JSON-LD schema injection
4. POST /api/shopify/pulse/fix/h1-tags - H1 tag detection (crawls storefront)
5. POST /api/shopify/pulse/fix/auto-fix-all - Master button runs all 5 phases
6. POST /api/shopify/pulse/fix/alt-text - Existing alt-text fixer (regression)
7. POST /api/shopify/pulse/scan - Verify fix_available=True for missing_seo_meta
"""

import pytest
import requests
import os
import json

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")
TEST_SHOP = "aurem-dev.myshopify.com"


# Session-scoped auth token to avoid rate limiting
@pytest.fixture(scope="session")
def auth_token():
    """Get authentication token for admin user - session scoped with retry"""
    import time
    for attempt in range(3):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code == 200:
            data = response.json()
            assert "token" in data, "No token in login response"
            return data["token"]
        elif response.status_code == 429:
            print(f"Rate limited, waiting 5 seconds (attempt {attempt + 1}/3)")
            time.sleep(5)
        else:
            break
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("token")


class TestAuthAndSetup:
    """Authentication and basic setup tests"""
    
    def test_health_check(self):
        """Verify backend is running"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("PASS: Backend health check")
    
    def test_login_success(self, auth_token):
        """Verify login returns valid token"""
        assert auth_token is not None
        assert len(auth_token) > 20
        print(f"PASS: Login successful, token length: {len(auth_token)}")


class TestAuthGuards:
    """All fix endpoints require authentication (401 without token)"""
    
    def test_meta_descriptions_requires_auth(self):
        """POST /api/shopify/pulse/fix/meta-descriptions returns 401 without token"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/fix/meta-descriptions",
            json={"shop": TEST_SHOP}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: meta-descriptions requires auth (401)")
    
    def test_page_titles_requires_auth(self):
        """POST /api/shopify/pulse/fix/page-titles returns 401 without token"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/fix/page-titles",
            json={"shop": TEST_SHOP}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: page-titles requires auth (401)")
    
    def test_schema_markup_requires_auth(self):
        """POST /api/shopify/pulse/fix/schema-markup returns 401 without token"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/fix/schema-markup",
            json={"shop": TEST_SHOP}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: schema-markup requires auth (401)")
    
    def test_h1_tags_requires_auth(self):
        """POST /api/shopify/pulse/fix/h1-tags returns 401 without token"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/fix/h1-tags",
            json={"shop": TEST_SHOP}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: h1-tags requires auth (401)")
    
    def test_auto_fix_all_requires_auth(self):
        """POST /api/shopify/pulse/fix/auto-fix-all returns 401 without token"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/fix/auto-fix-all",
            json={"shop": TEST_SHOP}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: auto-fix-all requires auth (401)")
    
    def test_alt_text_requires_auth(self):
        """POST /api/shopify/pulse/fix/alt-text returns 401 without token"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/fix/alt-text",
            json={"shop": TEST_SHOP}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: alt-text requires auth (401)")
    
    def test_scan_requires_auth(self):
        """POST /api/shopify/pulse/scan returns 401 without token"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/scan",
            json={"shop": TEST_SHOP}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: scan requires auth (401)")


class TestScanEndpoint:
    """Test scan endpoint returns fix_available=True for missing_seo_meta"""
    
    def test_scan_returns_fix_available_for_seo_meta(self, auth_token):
        """POST /api/shopify/pulse/scan returns issues with fix_available=True for missing_seo_meta"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/scan",
            json={"shop": TEST_SHOP},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Scan failed: {response.text}"
        data = response.json()
        
        # Verify scan response structure
        assert "health_score" in data, "Missing health_score in scan response"
        assert "issues" in data, "Missing issues in scan response"
        
        # Check for missing_seo_meta issue with fix_available=True
        # In scaffold mode, this should be present
        issues = data.get("issues", [])
        print(f"Scan returned {len(issues)} issues")
        
        # Check if any issue has fix_available=True
        fix_available_issues = [i for i in issues if i.get("fix_available") == True]
        assert len(fix_available_issues) > 0, "No issues with fix_available=True found"
        
        # Log all issues for debugging
        for issue in issues:
            print(f"  - {issue.get('type')}: fix_available={issue.get('fix_available')}")
        
        print(f"PASS: Scan returns {len(fix_available_issues)} issues with fix_available=True")


def parse_sse_events(response_text):
    """Parse SSE events from response text"""
    events = []
    for line in response_text.split("\n"):
        if line.startswith("data: "):
            try:
                event_data = json.loads(line[6:])
                events.append(event_data)
            except json.JSONDecodeError:
                pass
    return events


class TestMetaDescriptionsFix:
    """Test POST /api/shopify/pulse/fix/meta-descriptions SSE stream"""
    
    def test_meta_descriptions_returns_sse_stream(self, auth_token):
        """POST /api/shopify/pulse/fix/meta-descriptions returns SSE stream with simulated fixes"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/fix/meta-descriptions",
            json={"shop": TEST_SHOP},
            headers={"Authorization": f"Bearer {auth_token}"},
            stream=True
        )
        assert response.status_code == 200, f"Request failed: {response.status_code}"
        assert "text/event-stream" in response.headers.get("content-type", ""), "Not SSE stream"
        
        # Collect all SSE events
        full_response = response.text
        events = parse_sse_events(full_response)
        
        assert len(events) > 0, "No SSE events received"
        
        # Check for fix events and complete event
        fix_events = [e for e in events if e.get("type") == "fix"]
        complete_events = [e for e in events if e.get("type") == "complete"]
        
        assert len(fix_events) > 0, "No fix events in SSE stream"
        assert len(complete_events) == 1, "Missing complete event"
        
        # Verify fix event structure
        for fix in fix_events:
            assert "product" in fix, "Fix event missing product"
            assert "meta_description" in fix, "Fix event missing meta_description"
            assert "status" in fix, "Fix event missing status"
            print(f"  Fix: {fix.get('product')} -> {fix.get('meta_description')[:50]}...")
        
        # Verify complete event
        complete = complete_events[0]
        assert "fixed" in complete, "Complete event missing fixed count"
        assert complete.get("fix_type") == "meta_descriptions", "Wrong fix_type"
        
        print(f"PASS: meta-descriptions SSE stream - {complete.get('fixed')} fixes, mode={complete.get('mode', 'live')}")


class TestPageTitlesFix:
    """Test POST /api/shopify/pulse/fix/page-titles SSE stream"""
    
    def test_page_titles_returns_sse_stream(self, auth_token):
        """POST /api/shopify/pulse/fix/page-titles returns SSE stream with simulated fixes"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/fix/page-titles",
            json={"shop": TEST_SHOP},
            headers={"Authorization": f"Bearer {auth_token}"},
            stream=True
        )
        assert response.status_code == 200, f"Request failed: {response.status_code}"
        assert "text/event-stream" in response.headers.get("content-type", ""), "Not SSE stream"
        
        events = parse_sse_events(response.text)
        assert len(events) > 0, "No SSE events received"
        
        fix_events = [e for e in events if e.get("type") == "fix"]
        complete_events = [e for e in events if e.get("type") == "complete"]
        
        assert len(fix_events) > 0, "No fix events in SSE stream"
        assert len(complete_events) == 1, "Missing complete event"
        
        # Verify fix event structure
        for fix in fix_events:
            assert "product" in fix, "Fix event missing product"
            assert "seo_title" in fix, "Fix event missing seo_title"
            assert "status" in fix, "Fix event missing status"
            print(f"  Fix: {fix.get('product')} -> {fix.get('seo_title')}")
        
        complete = complete_events[0]
        assert complete.get("fix_type") == "page_titles", "Wrong fix_type"
        
        print(f"PASS: page-titles SSE stream - {complete.get('fixed')} fixes")


class TestSchemaMarkupFix:
    """Test POST /api/shopify/pulse/fix/schema-markup SSE stream"""
    
    def test_schema_markup_returns_sse_stream(self, auth_token):
        """POST /api/shopify/pulse/fix/schema-markup returns SSE stream with simulated JSON-LD fixes"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/fix/schema-markup",
            json={"shop": TEST_SHOP},
            headers={"Authorization": f"Bearer {auth_token}"},
            stream=True
        )
        assert response.status_code == 200, f"Request failed: {response.status_code}"
        assert "text/event-stream" in response.headers.get("content-type", ""), "Not SSE stream"
        
        events = parse_sse_events(response.text)
        assert len(events) > 0, "No SSE events received"
        
        fix_events = [e for e in events if e.get("type") == "fix"]
        complete_events = [e for e in events if e.get("type") == "complete"]
        
        assert len(fix_events) > 0, "No fix events in SSE stream"
        assert len(complete_events) == 1, "Missing complete event"
        
        # Verify fix event structure
        for fix in fix_events:
            assert "product" in fix, "Fix event missing product"
            assert "schema_type" in fix, "Fix event missing schema_type"
            assert fix.get("schema_type") == "Product", "Schema type should be Product"
            print(f"  Fix: {fix.get('product')} -> schema_type={fix.get('schema_type')}")
        
        complete = complete_events[0]
        assert complete.get("fix_type") == "schema_markup", "Wrong fix_type"
        
        print(f"PASS: schema-markup SSE stream - {complete.get('fixed')} fixes")


class TestH1TagsFix:
    """Test POST /api/shopify/pulse/fix/h1-tags SSE stream (crawls real storefront)"""
    
    def test_h1_tags_crawls_storefront(self, auth_token):
        """POST /api/shopify/pulse/fix/h1-tags crawls storefront and detects H1 issues"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/fix/h1-tags",
            json={"shop": TEST_SHOP},
            headers={"Authorization": f"Bearer {auth_token}"},
            stream=True,
            timeout=60  # H1 scanner crawls real pages, may take time
        )
        assert response.status_code == 200, f"Request failed: {response.status_code}"
        assert "text/event-stream" in response.headers.get("content-type", ""), "Not SSE stream"
        
        events = parse_sse_events(response.text)
        assert len(events) > 0, "No SSE events received"
        
        # Check for start event
        start_events = [e for e in events if e.get("type") == "start"]
        assert len(start_events) == 1, "Missing start event"
        
        # Check for complete event
        complete_events = [e for e in events if e.get("type") == "complete"]
        assert len(complete_events) == 1, "Missing complete event"
        
        complete = complete_events[0]
        assert "checked" in complete, "Complete event missing checked count"
        assert "issues" in complete, "Complete event missing issues count"
        assert complete.get("fix_type") == "h1_tags", "Wrong fix_type"
        
        # Log all events for debugging
        for event in events:
            event_type = event.get("type")
            if event_type == "start":
                print(f"  Start: {event.get('message')}")
            elif event_type == "ok":
                print(f"  OK: {event.get('page')} - H1: {event.get('h1', 'N/A')[:40]}")
            elif event_type == "issue":
                print(f"  Issue: {event.get('page')} - {event.get('problem')}")
            elif event_type == "error":
                print(f"  Error: {event.get('page')} - {event.get('error')}")
            elif event_type == "complete":
                print(f"  Complete: checked={event.get('checked')}, issues={event.get('issues')}")
        
        print(f"PASS: h1-tags SSE stream - checked {complete.get('checked')} pages, found {complete.get('issues')} issues")


class TestAltTextFix:
    """Test POST /api/shopify/pulse/fix/alt-text SSE stream (regression test)"""
    
    def test_alt_text_returns_sse_stream(self, auth_token):
        """POST /api/shopify/pulse/fix/alt-text returns SSE stream with simulated fixes"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/fix/alt-text",
            json={"shop": TEST_SHOP},
            headers={"Authorization": f"Bearer {auth_token}"},
            stream=True
        )
        assert response.status_code == 200, f"Request failed: {response.status_code}"
        assert "text/event-stream" in response.headers.get("content-type", ""), "Not SSE stream"
        
        events = parse_sse_events(response.text)
        assert len(events) > 0, "No SSE events received"
        
        fix_events = [e for e in events if e.get("type") == "fix"]
        complete_events = [e for e in events if e.get("type") == "complete"]
        
        assert len(fix_events) > 0, "No fix events in SSE stream"
        assert len(complete_events) == 1, "Missing complete event"
        
        # Verify fix event structure
        for fix in fix_events:
            assert "product" in fix, "Fix event missing product"
            assert "alt_text" in fix, "Fix event missing alt_text"
            print(f"  Fix: {fix.get('product')} -> {fix.get('alt_text')[:50]}...")
        
        complete = complete_events[0]
        assert "fixed" in complete, "Complete event missing fixed count"
        
        print(f"PASS: alt-text SSE stream (regression) - {complete.get('fixed')} fixes")


class TestAutoFixAll:
    """Test POST /api/shopify/pulse/fix/auto-fix-all master button"""
    
    def test_auto_fix_all_runs_all_phases(self, auth_token):
        """POST /api/shopify/pulse/fix/auto-fix-all runs all 5 phases in sequence via SSE"""
        response = requests.post(
            f"{BASE_URL}/api/shopify/pulse/fix/auto-fix-all",
            json={"shop": TEST_SHOP},
            headers={"Authorization": f"Bearer {auth_token}"},
            stream=True,
            timeout=120  # Auto-fix-all runs all phases, may take time
        )
        assert response.status_code == 200, f"Request failed: {response.status_code}"
        assert "text/event-stream" in response.headers.get("content-type", ""), "Not SSE stream"
        
        events = parse_sse_events(response.text)
        assert len(events) > 0, "No SSE events received"
        
        # Check for master_start event with 5 phases
        master_start = [e for e in events if e.get("type") == "master_start"]
        assert len(master_start) == 1, "Missing master_start event"
        
        phases = master_start[0].get("phases", [])
        expected_phases = ["alt_text", "meta_descriptions", "page_titles", "schema_markup", "h1_tags"]
        assert phases == expected_phases, f"Expected phases {expected_phases}, got {phases}"
        print(f"  master_start: phases={phases}")
        
        # Check for phase events (running and done for each phase)
        phase_events = [e for e in events if e.get("type") == "phase"]
        
        # Each phase should have running and done status
        for phase_name in expected_phases:
            running = [e for e in phase_events if e.get("phase") == phase_name and e.get("status") == "running"]
            done = [e for e in phase_events if e.get("phase") == phase_name and e.get("status") == "done"]
            assert len(running) == 1, f"Missing running event for phase {phase_name}"
            assert len(done) == 1, f"Missing done event for phase {phase_name}"
            
            done_event = done[0]
            fixed = done_event.get("fixed", 0)
            errors = done_event.get("errors", 0)
            print(f"  Phase {phase_name}: fixed={fixed}, errors={errors}")
        
        # Check for master_complete event
        master_complete = [e for e in events if e.get("type") == "master_complete"]
        assert len(master_complete) == 1, "Missing master_complete event"
        
        complete = master_complete[0]
        assert "total_fixed" in complete, "master_complete missing total_fixed"
        assert "billing" in complete, "master_complete missing billing message"
        
        # Verify billing message mentions SEO fixes are free
        billing = complete.get("billing", "")
        assert "free" in billing.lower() or "FREE" in billing, "Billing should mention SEO fixes are free"
        
        total_fixed = complete.get("total_fixed", 0)
        total_errors = complete.get("total_errors", 0)
        
        print(f"  master_complete: total_fixed={total_fixed}, total_errors={total_errors}")
        print(f"  billing: {billing}")
        
        # In scaffold mode, expect 14 total fixes (5 alt + 3 meta + 3 titles + 3 schema + 0 h1)
        # But this may vary, so just check it's > 0
        assert total_fixed > 0, "Expected at least some fixes in scaffold mode"
        
        print(f"PASS: auto-fix-all SSE stream - {total_fixed} total fixes across 5 phases")


class TestSSEContentType:
    """Verify all fix endpoints return correct content-type"""
    
    def test_all_fix_endpoints_return_sse(self, auth_token):
        """All fix endpoints return content-type: text/event-stream"""
        endpoints = [
            "/api/shopify/pulse/fix/alt-text",
            "/api/shopify/pulse/fix/meta-descriptions",
            "/api/shopify/pulse/fix/page-titles",
            "/api/shopify/pulse/fix/schema-markup",
            "/api/shopify/pulse/fix/h1-tags",
            "/api/shopify/pulse/fix/auto-fix-all",
        ]
        
        for endpoint in endpoints:
            response = requests.post(
                f"{BASE_URL}{endpoint}",
                json={"shop": TEST_SHOP},
                headers={"Authorization": f"Bearer {auth_token}"},
                stream=True,
                timeout=60
            )
            assert response.status_code == 200, f"{endpoint} failed: {response.status_code}"
            content_type = response.headers.get("content-type", "")
            assert "text/event-stream" in content_type, f"{endpoint} not SSE: {content_type}"
            print(f"  {endpoint}: content-type={content_type}")
        
        print("PASS: All fix endpoints return text/event-stream")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
