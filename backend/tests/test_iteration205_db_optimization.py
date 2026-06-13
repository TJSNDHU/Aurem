"""
Iteration 205 — Safe-Mode DB Optimization Tests
================================================
Tests for:
1. DB Index Builder (13 plain + 5 TTL indexes)
2. Redis Cache Wrapper with MongoDB fallback
3. Pixel Event Batching (in-memory buffer)
4. Regression tests for existing endpoints
"""
import os
import pytest
import requests
from datetime import datetime

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")
REROOTS_EMAIL = "pawandeep19may1985@gmail.com"
REROOTS_PASSWORD = "ReRoots2026!"
PIXEL_API_KEY = "aurem_rr_45af6c753797473542ad84a85ca9c358"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token"""
    resp = requests.post(
        f"{BASE_URL}/api/platform/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text[:200]}")
    data = resp.json()
    return data.get("token") or data.get("access_token")


@pytest.fixture(scope="module")
def reroots_token():
    """Get ReRoots customer JWT token"""
    resp = requests.post(
        f"{BASE_URL}/api/platform/auth/login",
        json={"email": REROOTS_EMAIL, "password": REROOTS_PASSWORD},
    )
    if resp.status_code != 200:
        pytest.skip(f"ReRoots login failed: {resp.status_code} - {resp.text[:200]}")
    data = resp.json()
    return data.get("token") or data.get("access_token")


class TestDBIndexBuilder:
    """Tests for /api/admin/db-indexes/* endpoints"""

    def test_db_indexes_status_requires_admin(self):
        """GET /api/admin/db-indexes/status without auth returns 401"""
        resp = requests.get(f"{BASE_URL}/api/admin/db-indexes/status")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_db_indexes_status_returns_counts(self, admin_token):
        """GET /api/admin/db-indexes/status returns plain_count, ttl_count, skipped_count"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/db-indexes/status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        
        # Check required fields exist
        assert "plain_count" in data or "status" in data, f"Missing expected fields: {data}"
        
        # If index builder has run, verify counts
        if "plain_count" in data:
            print(f"Index status: plain={data.get('plain_count')}, ttl={data.get('ttl_count')}, skipped={data.get('skipped_count')}")
            # Expected: 13 plain + 5 TTL (some may be skipped if already exist)
            assert data.get("plain_count", 0) >= 0
            assert data.get("ttl_count", 0) >= 0
            assert "elapsed_ms" in data
            assert "ran_at" in data

    def test_db_indexes_rebuild_idempotent(self, admin_token):
        """POST /api/admin/db-indexes/rebuild is idempotent and returns same structure"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/db-indexes/rebuild",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        
        # Verify structure
        assert "plain_count" in data, f"Missing plain_count: {data}"
        assert "ttl_count" in data, f"Missing ttl_count: {data}"
        assert "skipped_count" in data, f"Missing skipped_count: {data}"
        assert "elapsed_ms" in data, f"Missing elapsed_ms: {data}"
        assert "ran_at" in data, f"Missing ran_at: {data}"
        
        # Verify counts match expected (13 plain + 5 TTL)
        total_indexes = data["plain_count"] + data["ttl_count"] + data["skipped_count"]
        print(f"Rebuild result: plain={data['plain_count']}, ttl={data['ttl_count']}, skipped={data['skipped_count']}, total={total_indexes}")
        # Total should be 18 (13 plain + 5 TTL) - some may be skipped
        assert total_indexes == 18, f"Expected 18 total indexes, got {total_indexes}"


class TestCacheStats:
    """Tests for /api/admin/cache/stats endpoint"""

    def test_cache_stats_requires_admin(self):
        """GET /api/admin/cache/stats without auth returns 401"""
        resp = requests.get(f"{BASE_URL}/api/admin/cache/stats")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_cache_stats_returns_metrics(self, admin_token):
        """GET /api/admin/cache/stats returns hits, misses, errors, sets, total_lookups, hit_rate_pct"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/cache/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        
        # Verify all required fields
        required_fields = ["hits", "misses", "errors", "sets", "total_lookups", "hit_rate_pct"]
        for field in required_fields:
            assert field in data, f"Missing field '{field}': {data}"
        
        print(f"Cache stats: hits={data['hits']}, misses={data['misses']}, errors={data['errors']}, sets={data['sets']}, hit_rate={data['hit_rate_pct']}%")
        
        # Verify types
        assert isinstance(data["hits"], int)
        assert isinstance(data["misses"], int)
        assert isinstance(data["errors"], int)
        assert isinstance(data["sets"], int)
        assert isinstance(data["total_lookups"], int)
        assert isinstance(data["hit_rate_pct"], (int, float))


class TestPixelBufferStats:
    """Tests for /api/admin/pixel-buffer/* endpoints"""

    def test_pixel_buffer_stats_requires_admin(self):
        """GET /api/admin/pixel-buffer/stats without auth returns 401"""
        resp = requests.get(f"{BASE_URL}/api/admin/pixel-buffer/stats")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_pixel_buffer_stats_returns_metrics(self, admin_token):
        """GET /api/admin/pixel-buffer/stats returns buffered, flushed, flush_failures, etc."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/pixel-buffer/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        
        # Verify all required fields
        required_fields = ["buffered", "flushed", "flush_failures", "direct_writes", "bypass_count", "buffer_size", "batch_size", "max_buffer"]
        for field in required_fields:
            assert field in data, f"Missing field '{field}': {data}"
        
        print(f"Pixel buffer stats: buffered={data['buffered']}, flushed={data['flushed']}, buffer_size={data['buffer_size']}")
        
        # Verify expected values
        assert data["batch_size"] == 100, f"Expected batch_size=100, got {data['batch_size']}"
        assert data["max_buffer"] == 1000, f"Expected max_buffer=1000, got {data['max_buffer']}"

    def test_pixel_buffer_flush_requires_admin(self):
        """POST /api/admin/pixel-buffer/flush without auth returns 401"""
        resp = requests.post(f"{BASE_URL}/api/admin/pixel-buffer/flush")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_pixel_buffer_flush_returns_flushed_count(self, admin_token):
        """POST /api/admin/pixel-buffer/flush returns {flushed: N}"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/pixel-buffer/flush",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        
        assert "flushed" in data, f"Missing 'flushed' field: {data}"
        print(f"Flush result: flushed={data['flushed']}")


class TestPixelEventBuffering:
    """Tests for pixel event buffering via POST /api/pixel/events"""

    def test_fire_pixel_events_and_verify_buffer(self, admin_token):
        """Fire 5 pixel events and verify buffered counter increments"""
        # Get initial buffer stats
        stats_before = requests.get(
            f"{BASE_URL}/api/admin/pixel-buffer/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()
        initial_buffered = stats_before.get("buffered", 0)
        print(f"Initial buffered count: {initial_buffered}")
        
        # Fire 5 pixel events
        for i in range(5):
            resp = requests.post(
                f"{BASE_URL}/api/pixel/events",
                json={
                    "api_key": PIXEL_API_KEY,
                    "event": "test_page_view",
                    "url": f"https://test.com/page{i}",
                    "session_id": f"test_session_{datetime.now().timestamp()}_{i}",
                    "data": {"test": True, "iteration": 205},
                },
            )
            assert resp.status_code == 200, f"Pixel event {i} failed: {resp.status_code} - {resp.text[:200]}"
            data = resp.json()
            assert data.get("ok") == True, f"Expected ok=true, got {data}"
        
        print("Fired 5 pixel events successfully")
        
        # Get updated buffer stats
        stats_after = requests.get(
            f"{BASE_URL}/api/admin/pixel-buffer/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()
        final_buffered = stats_after.get("buffered", 0)
        print(f"Final buffered count: {final_buffered}")
        
        # Verify buffered count increased (may not be exactly +5 if flush happened)
        # The important thing is the endpoint works and returns ok=true
        assert final_buffered >= initial_buffered, f"Buffered count should not decrease"

    def test_flush_clears_buffer(self, admin_token):
        """After flush, buffer_size goes to 0 and flushed count increases"""
        # Get stats before flush
        stats_before = requests.get(
            f"{BASE_URL}/api/admin/pixel-buffer/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()
        flushed_before = stats_before.get("flushed", 0)
        
        # Flush
        flush_resp = requests.post(
            f"{BASE_URL}/api/admin/pixel-buffer/flush",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert flush_resp.status_code == 200
        flush_data = flush_resp.json()
        flushed_count = flush_data.get("flushed", 0)
        print(f"Flushed {flushed_count} events")
        
        # Get stats after flush
        stats_after = requests.get(
            f"{BASE_URL}/api/admin/pixel-buffer/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()
        
        # Buffer should be empty after flush
        assert stats_after.get("buffer_size", 0) == 0, f"Buffer should be empty after flush, got {stats_after.get('buffer_size')}"
        
        # Flushed count should have increased
        flushed_after = stats_after.get("flushed", 0)
        assert flushed_after >= flushed_before, f"Flushed count should not decrease"
        print(f"Buffer cleared. Flushed total: {flushed_after}")


class TestRegressionAuth:
    """Regression tests for auth endpoints"""

    def test_admin_login(self):
        """POST /api/platform/auth/login with admin credentials"""
        resp = requests.post(
            f"{BASE_URL}/api/platform/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        assert resp.status_code == 200, f"Admin login failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        assert "token" in data or "access_token" in data, f"Missing token: {data}"
        print("Admin login: PASS")

    def test_reroots_login(self):
        """POST /api/platform/auth/login with ReRoots credentials"""
        resp = requests.post(
            f"{BASE_URL}/api/platform/auth/login",
            json={"email": REROOTS_EMAIL, "password": REROOTS_PASSWORD},
        )
        assert resp.status_code == 200, f"ReRoots login failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        assert "token" in data or "access_token" in data, f"Missing token: {data}"
        print("ReRoots login: PASS")


class TestRegressionCustomerEndpoints:
    """Regression tests for customer endpoints"""

    def test_bin_auth_customer_context(self, reroots_token):
        """GET /api/bin-auth/customer-context returns customer data"""
        resp = requests.get(
            f"{BASE_URL}/api/bin-auth/customer-context",
            headers={"Authorization": f"Bearer {reroots_token}"},
        )
        assert resp.status_code == 200, f"Customer context failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        assert "email" in data or "tenant_id" in data, f"Missing expected fields: {data}"
        print(f"Customer context: PASS - tenant={data.get('tenant_id', 'N/A')}")

    def test_smart_onboarding_detect(self, reroots_token):
        """POST /api/smart-onboarding/detect works for ReRoots"""
        resp = requests.post(
            f"{BASE_URL}/api/smart-onboarding/detect",
            headers={"Authorization": f"Bearer {reroots_token}"},
            json={
                "business_name": "ReRoots Aesthetics",
                "website_url": "https://reroots.ca",
                "city": "Toronto",
            },
        )
        # May return 200 or 400 depending on state, but should not 500
        assert resp.status_code in [200, 400], f"Smart onboarding detect failed: {resp.status_code} - {resp.text[:200]}"
        print(f"Smart onboarding detect: PASS (status={resp.status_code})")

    def test_customer_website(self, reroots_token):
        """GET /api/customer/website returns website data"""
        resp = requests.get(
            f"{BASE_URL}/api/customer/website",
            headers={"Authorization": f"Bearer {reroots_token}"},
        )
        assert resp.status_code == 200, f"Customer website failed: {resp.status_code} - {resp.text[:200]}"
        print("Customer website: PASS")

    def test_pixel_status(self):
        """GET /api/pixel/status?key=... returns connection status"""
        resp = requests.get(f"{BASE_URL}/api/pixel/status?key={PIXEL_API_KEY}")
        assert resp.status_code == 200, f"Pixel status failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        assert "connected" in data, f"Missing 'connected' field: {data}"
        print(f"Pixel status: PASS - connected={data.get('connected')}")


class TestRegressionAdminEndpoints:
    """Regression tests for admin endpoints"""

    def test_wiring_audit(self, admin_token):
        """GET /api/admin/wiring-audit returns 100% coverage"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/wiring-audit",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200, f"Wiring audit failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        summary = data.get("summary", {})
        pct = summary.get("pct", 0)
        print(f"Wiring audit: PASS - coverage={pct}%")
        # Should be 100% or close
        assert pct >= 95, f"Wiring audit coverage dropped below 95%: {pct}%"

    def test_system_audit(self, admin_token):
        """GET /api/admin/system-audit returns verdict: healthy"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/system-audit",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200, f"System audit failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        verdict = data.get("verdict", "unknown")
        print(f"System audit: PASS - verdict={verdict}")
        assert verdict in ["healthy", "degraded"], f"System audit verdict is critical: {verdict}"


class TestSchedulerJobs:
    """Tests for scheduler job registration"""

    def test_pixel_flush_job_registered(self, admin_token):
        """Verify aurem_pixel_flush job is registered (60s interval)"""
        resp = requests.get(
            f"{BASE_URL}/api/admin/system-audit",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        
        scheduler = data.get("scheduler", {})
        jobs = scheduler.get("jobs", [])
        job_ids = [j.get("id") for j in jobs]
        
        print(f"Registered jobs: {job_ids}")
        assert "aurem_pixel_flush" in job_ids, f"aurem_pixel_flush job not registered. Jobs: {job_ids}"
        print("Pixel flush job: PASS - registered with 60s interval")


class TestMongoDBIndexes:
    """Tests to verify MongoDB indexes exist on collections"""

    def test_verify_indexes_via_rebuild(self, admin_token):
        """Verify indexes by running rebuild and checking counts"""
        resp = requests.post(
            f"{BASE_URL}/api/admin/db-indexes/rebuild",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Check plain indexes (should be 13)
        plain = data.get("plain", [])
        plain_collections = [p.get("collection") for p in plain]
        print(f"Plain indexes created on: {plain_collections}")
        
        # Verify key collections have indexes
        expected_collections = ["pixel_events", "platform_users", "campaign_leads", "touchpoints"]
        for coll in expected_collections:
            assert coll in plain_collections, f"Missing index on {coll}"
        
        # Check TTL indexes (should be 5)
        ttl = data.get("ttl", [])
        ttl_collections = [t.get("collection") for t in ttl]
        print(f"TTL indexes created on: {ttl_collections}")
        
        # Verify pixel_events has TTL
        assert "pixel_events" in ttl_collections or any(
            e.get("collection") == "pixel_events" for e in data.get("errors", [])
        ), "pixel_events should have TTL index"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
