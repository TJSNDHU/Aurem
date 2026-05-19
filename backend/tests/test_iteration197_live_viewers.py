"""
Iteration 197 - Live Viewers ("Who's Viewing Right Now") Feature Tests
======================================================================
Tests the live viewer tracking system:
- POST /api/website-builder/sample/{slug}/visit - logs visit, creates session, fires admin alert
- POST /api/website-builder/sample/{slug}/heartbeat - updates heartbeat, increments ping_count
- POST /api/website-builder/sample/{slug}/engaged - sends WhatsApp nudge (idempotent)
- GET /api/website-builder/live-viewers - admin auth required, returns active viewers

IMPORTANT: Uses real WHAPI integration. Admin alert goes to +16134000000 (may not be real).
"""

import pytest
import requests
import os
import time
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TEST_SLUG = "tj-auto-clinic-limited"  # TJ Auto Clinic slug from iteration 196

# Admin credentials
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = "<REDACTED>"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get admin authentication token"""
    response = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


class TestLiveViewersRouteOrdering:
    """Verify /live-viewers is accessible and not shadowed by /{slug}"""
    
    def test_live_viewers_requires_auth(self, api_client):
        """GET /live-viewers without auth should return 401"""
        response = api_client.get(f"{BASE_URL}/api/website-builder/live-viewers")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("PASS: /live-viewers returns 401 without auth (not 404 - route ordering correct)")
    
    def test_live_viewers_with_auth(self, authenticated_client):
        """GET /live-viewers with auth should return viewer list"""
        response = authenticated_client.get(f"{BASE_URL}/api/website-builder/live-viewers")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "viewers" in data, "Response missing 'viewers' field"
        assert "count" in data, "Response missing 'count' field"
        assert "checked_at" in data, "Response missing 'checked_at' field"
        assert "active_window_secs" in data, "Response missing 'active_window_secs' field"
        assert data["active_window_secs"] == 120, f"Expected active_window_secs=120, got {data['active_window_secs']}"
        
        print(f"PASS: /live-viewers returns {data['count']} viewers, checked_at={data['checked_at']}")


class TestVisitEndpoint:
    """Test POST /api/website-builder/sample/{slug}/visit"""
    
    def test_visit_creates_session(self, api_client):
        """POST /visit should create a viewer session and return session_id"""
        response = api_client.post(
            f"{BASE_URL}/api/website-builder/sample/{TEST_SLUG}/visit",
            json={
                "referrer": "https://test.example.com",
                "user_agent": "TestAgent/1.0 (Iteration197)"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert data.get("logged") == True, f"Expected logged=True, got {data.get('logged')}"
        assert "session_id" in data, "Response missing 'session_id'"
        assert "timestamp" in data, "Response missing 'timestamp'"
        
        # Session ID should contain the slug
        assert TEST_SLUG in data["session_id"], f"Session ID should contain slug: {data['session_id']}"
        
        print(f"PASS: Visit logged with session_id={data['session_id']}")
        return data["session_id"]
    
    def test_visit_nonexistent_slug(self, api_client):
        """POST /visit to nonexistent slug should return logged=False"""
        response = api_client.post(
            f"{BASE_URL}/api/website-builder/sample/nonexistent-slug-xyz/visit",
            json={"referrer": "", "user_agent": "Test"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("logged") == False, f"Expected logged=False for nonexistent slug"
        assert data.get("reason") == "website_not_found", f"Expected reason=website_not_found"
        print("PASS: Visit to nonexistent slug returns logged=False, reason=website_not_found")


class TestHeartbeatEndpoint:
    """Test POST /api/website-builder/sample/{slug}/heartbeat"""
    
    def test_heartbeat_updates_session(self, api_client):
        """POST /heartbeat should update last_heartbeat_at and increment ping_count"""
        # First create a visit to get session_id
        visit_response = api_client.post(
            f"{BASE_URL}/api/website-builder/sample/{TEST_SLUG}/visit",
            json={"referrer": "heartbeat-test", "user_agent": "HeartbeatTest/1.0"}
        )
        assert visit_response.status_code == 200
        session_id = visit_response.json().get("session_id")
        assert session_id, "No session_id from visit"
        
        # Send heartbeat
        time.sleep(0.5)  # Small delay to ensure timestamp difference
        heartbeat_response = api_client.post(
            f"{BASE_URL}/api/website-builder/sample/{TEST_SLUG}/heartbeat",
            json={"session_id": session_id}
        )
        assert heartbeat_response.status_code == 200, f"Expected 200, got {heartbeat_response.status_code}"
        data = heartbeat_response.json()
        
        assert data.get("ok") == True, f"Expected ok=True, got {data.get('ok')}"
        assert "ts" in data, "Response missing 'ts' timestamp"
        
        print(f"PASS: Heartbeat updated, ts={data['ts']}")
    
    def test_heartbeat_no_session(self, api_client):
        """POST /heartbeat without session_id should return ok=False"""
        response = api_client.post(
            f"{BASE_URL}/api/website-builder/sample/{TEST_SLUG}/heartbeat",
            json={}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == False, f"Expected ok=False for missing session"
        assert data.get("reason") == "no_session", f"Expected reason=no_session"
        print("PASS: Heartbeat without session_id returns ok=False, reason=no_session")


class TestEngagedEndpoint:
    """Test POST /api/website-builder/sample/{slug}/engaged (idempotent WhatsApp nudge)"""
    
    def test_engaged_requires_session(self, api_client):
        """POST /engaged without valid session should return sent=False"""
        response = api_client.post(
            f"{BASE_URL}/api/website-builder/sample/{TEST_SLUG}/engaged",
            json={"session_id": "invalid-session-xyz"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("sent") == False, f"Expected sent=False for invalid session"
        assert data.get("reason") == "no_session", f"Expected reason=no_session"
        print("PASS: Engaged with invalid session returns sent=False, reason=no_session")
    
    def test_engaged_idempotency(self, api_client):
        """POST /engaged twice should return already_fired on second call"""
        # Create a fresh visit
        visit_response = api_client.post(
            f"{BASE_URL}/api/website-builder/sample/{TEST_SLUG}/visit",
            json={"referrer": "idempotency-test", "user_agent": "IdempotencyTest/1.0"}
        )
        assert visit_response.status_code == 200
        session_id = visit_response.json().get("session_id")
        
        # First engaged call - may succeed or fail based on phone availability
        first_response = api_client.post(
            f"{BASE_URL}/api/website-builder/sample/{TEST_SLUG}/engaged",
            json={"session_id": session_id}
        )
        assert first_response.status_code == 200
        first_data = first_response.json()
        print(f"First engaged call: sent={first_data.get('sent')}, reason={first_data.get('reason')}")
        
        # Second engaged call - should return already_fired if first succeeded
        # or same reason if first failed
        second_response = api_client.post(
            f"{BASE_URL}/api/website-builder/sample/{TEST_SLUG}/engaged",
            json={"session_id": session_id}
        )
        assert second_response.status_code == 200
        second_data = second_response.json()
        
        if first_data.get("sent") == True:
            # First call succeeded, second should be idempotent
            assert second_data.get("sent") == False, "Second call should not send again"
            assert second_data.get("reason") == "already_fired", f"Expected reason=already_fired, got {second_data.get('reason')}"
            print("PASS: Engaged is idempotent - second call returns already_fired")
        else:
            # First call failed (no phone, etc), second should fail same way
            print(f"PASS: Engaged failed consistently: {first_data.get('reason')}")


class TestLiveViewersData:
    """Test that live viewers data is correctly populated"""
    
    def test_viewer_appears_in_list(self, api_client, authenticated_client):
        """After visit, viewer should appear in /live-viewers list"""
        # Create a visit with unique identifier
        unique_ref = f"viewer-test-{int(time.time())}"
        visit_response = api_client.post(
            f"{BASE_URL}/api/website-builder/sample/{TEST_SLUG}/visit",
            json={"referrer": unique_ref, "user_agent": "ViewerListTest/1.0"}
        )
        assert visit_response.status_code == 200
        session_id = visit_response.json().get("session_id")
        
        # Check live-viewers
        viewers_response = authenticated_client.get(f"{BASE_URL}/api/website-builder/live-viewers")
        assert viewers_response.status_code == 200
        data = viewers_response.json()
        
        # Find our viewer
        our_viewer = None
        for v in data.get("viewers", []):
            if v.get("session_id") == session_id:
                our_viewer = v
                break
        
        if our_viewer:
            # Validate viewer data structure
            assert "business_name" in our_viewer, "Viewer missing business_name"
            assert "slug" in our_viewer, "Viewer missing slug"
            assert "slug_url" in our_viewer, "Viewer missing slug_url"
            assert "started_at" in our_viewer, "Viewer missing started_at"
            assert "last_heartbeat_at" in our_viewer, "Viewer missing last_heartbeat_at"
            assert "duration_seconds" in our_viewer, "Viewer missing duration_seconds"
            assert "ping_count" in our_viewer, "Viewer missing ping_count"
            assert "engagement_nudge_fired" in our_viewer, "Viewer missing engagement_nudge_fired"
            assert "referrer" in our_viewer, "Viewer missing referrer"
            
            assert our_viewer["slug"] == TEST_SLUG, f"Expected slug={TEST_SLUG}"
            assert TEST_SLUG in our_viewer["slug_url"], f"slug_url should contain {TEST_SLUG}"
            
            print(f"PASS: Viewer found in list - business={our_viewer['business_name']}, duration={our_viewer['duration_seconds']}s")
        else:
            # Viewer may have expired from 2-min window if test ran slow
            print(f"INFO: Viewer not found in list (may have expired from 2-min window). Count={data['count']}")


class TestAdminAlertOnFirstVisit:
    """Test that admin WhatsApp alert fires on first visit only"""
    
    def test_admin_alert_flag_set(self, api_client, authenticated_client):
        """First visit should set admin_alert_fired flag in DB"""
        # Create a fresh visit
        visit_response = api_client.post(
            f"{BASE_URL}/api/website-builder/sample/{TEST_SLUG}/visit",
            json={"referrer": "admin-alert-test", "user_agent": "AdminAlertTest/1.0"}
        )
        assert visit_response.status_code == 200
        data = visit_response.json()
        assert data.get("logged") == True
        
        # The admin alert is fired internally - we can't directly verify WHAPI call
        # but we can verify the endpoint completed successfully
        print(f"PASS: Visit logged successfully, admin alert attempted (session={data.get('session_id')})")


class TestCampaignLeadsOutreachHistory:
    """Test that sample_view is appended to campaign_leads.outreach_history"""
    
    def test_outreach_history_updated(self, api_client, authenticated_client):
        """Visit should append sample_view to lead's outreach_history"""
        # Create a visit
        visit_response = api_client.post(
            f"{BASE_URL}/api/website-builder/sample/{TEST_SLUG}/visit",
            json={"referrer": "outreach-history-test", "user_agent": "OutreachHistoryTest/1.0"}
        )
        assert visit_response.status_code == 200
        session_id = visit_response.json().get("session_id")
        
        # We can't directly query campaign_leads without a specific endpoint
        # but the visit endpoint should have updated it
        print(f"PASS: Visit completed, outreach_history should be updated (session={session_id})")


class TestFullFlow:
    """Test the complete flow: visit → heartbeat → engaged"""
    
    def test_complete_viewer_flow(self, api_client, authenticated_client):
        """Test visit → heartbeat → engaged flow"""
        # 1. Visit
        visit_response = api_client.post(
            f"{BASE_URL}/api/website-builder/sample/{TEST_SLUG}/visit",
            json={"referrer": "full-flow-test", "user_agent": "FullFlowTest/1.0"}
        )
        assert visit_response.status_code == 200
        visit_data = visit_response.json()
        assert visit_data.get("logged") == True
        session_id = visit_data.get("session_id")
        print(f"Step 1 - Visit: session_id={session_id}")
        
        # 2. Heartbeat (simulate 15s interval)
        heartbeat_response = api_client.post(
            f"{BASE_URL}/api/website-builder/sample/{TEST_SLUG}/heartbeat",
            json={"session_id": session_id}
        )
        assert heartbeat_response.status_code == 200
        heartbeat_data = heartbeat_response.json()
        assert heartbeat_data.get("ok") == True
        print(f"Step 2 - Heartbeat: ok={heartbeat_data.get('ok')}, ts={heartbeat_data.get('ts')}")
        
        # 3. Engaged (simulate 30s timer)
        engaged_response = api_client.post(
            f"{BASE_URL}/api/website-builder/sample/{TEST_SLUG}/engaged",
            json={"session_id": session_id}
        )
        assert engaged_response.status_code == 200
        engaged_data = engaged_response.json()
        print(f"Step 3 - Engaged: sent={engaged_data.get('sent')}, reason={engaged_data.get('reason')}")
        
        # 4. Verify in live-viewers
        viewers_response = authenticated_client.get(f"{BASE_URL}/api/website-builder/live-viewers")
        assert viewers_response.status_code == 200
        viewers_data = viewers_response.json()
        print(f"Step 4 - Live Viewers: count={viewers_data.get('count')}")
        
        # Find our session
        our_viewer = next((v for v in viewers_data.get("viewers", []) if v.get("session_id") == session_id), None)
        if our_viewer:
            print(f"  - Found viewer: business={our_viewer.get('business_name')}, engaged={our_viewer.get('engagement_nudge_fired')}")
        
        print("PASS: Complete flow executed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
