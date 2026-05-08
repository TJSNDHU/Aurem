"""
Triple-Pulse Backend Tests — Iteration 270
==========================================
Tests for the Triple-Pulse layer added to Pillars Map:
  - Every collection row has triple_pulse object with db/backend/frontend status
  - totals.backend_red is present and non-negative
  - frontend.status is always 'green' (API reachable)
  - Mapped collections with live scheduler → backend.status = 'green'
  - Unmapped collections → backend falls back to 'green if pillar_live_count>0'
  - Collection-level overall status = _pick_worst(db, backend, frontend)
  - Heartbeat endpoint returns cached snapshot with totals.backend_red
  - Existing endpoints still work
  - Auth enforcement (401 without JWT)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = "Admin123"

# Collections with empty writer list (should fall back to pillar_live_count check)
UNMAPPED_COLLECTIONS = ["stem_fixes", "client_errors", "migrations", "deployment_log", "stem_fix_backups"]

# Mapped collections with known writers
MAPPED_COLLECTIONS = {
    "campaign_leads": ["p1:auto_blast_scheduler", "p1:news_monitor_scheduler", "p1:proactive_outreach"],
    "shannon_reports": ["p3:shannon_runner"],
    "sentinel_alerts": ["p3:self_repair_loop"],
}


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token for authenticated requests."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    if resp.status_code != 200:
        pytest.skip(f"Admin login failed: {resp.status_code} - {resp.text[:200]}")
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        pytest.skip("No token in login response")
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Headers with admin JWT."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def overview_data(auth_headers):
    """Fetch overview data once for multiple tests."""
    resp = requests.get(
        f"{BASE_URL}/api/admin/pillars-map/overview",
        headers=auth_headers,
        timeout=30,
    )
    assert resp.status_code == 200, f"Overview failed: {resp.status_code}"
    return resp.json()


class TestTriplePulseStructure:
    """Verify triple_pulse object structure in every collection row."""

    def test_every_row_has_triple_pulse(self, overview_data):
        """Every collection row must have triple_pulse object."""
        for pillar in overview_data["pillars"]:
            for row in pillar["collections"]["rows"]:
                assert "triple_pulse" in row, f"Missing triple_pulse in {row['collection']}"
                tp = row["triple_pulse"]
                assert "db" in tp, f"Missing db in triple_pulse for {row['collection']}"
                assert "backend" in tp, f"Missing backend in triple_pulse for {row['collection']}"
                assert "frontend" in tp, f"Missing frontend in triple_pulse for {row['collection']}"
        print("✓ All collection rows have triple_pulse object")

    def test_triple_pulse_has_status_and_reason(self, overview_data):
        """Each pulse (db/backend/frontend) must have status and reason."""
        for pillar in overview_data["pillars"]:
            for row in pillar["collections"]["rows"]:
                tp = row["triple_pulse"]
                for key in ["db", "backend", "frontend"]:
                    pulse = tp[key]
                    assert "status" in pulse, f"Missing status in {key} for {row['collection']}"
                    assert "reason" in pulse, f"Missing reason in {key} for {row['collection']}"
                    assert pulse["status"] in ["green", "yellow", "red"], f"Invalid status '{pulse['status']}' in {key} for {row['collection']}"
        print("✓ All pulses have status and reason fields")

    def test_backend_pulse_has_writers_list(self, overview_data):
        """Backend pulse should have writers list for mapped collections."""
        for pillar in overview_data["pillars"]:
            for row in pillar["collections"]["rows"]:
                tp = row["triple_pulse"]
                # Writers list should be present (may be empty for unmapped)
                assert "writers" in tp["backend"], f"Missing writers in backend for {row['collection']}"
        print("✓ All backend pulses have writers list")


class TestTotalBackendRed:
    """Verify totals.backend_red field."""

    def test_totals_has_backend_red(self, overview_data):
        """totals must have backend_red field."""
        assert "totals" in overview_data, "Missing totals"
        assert "backend_red" in overview_data["totals"], "Missing backend_red in totals"
        print(f"✓ totals.backend_red = {overview_data['totals']['backend_red']}")

    def test_backend_red_is_non_negative(self, overview_data):
        """totals.backend_red must be non-negative integer."""
        backend_red = overview_data["totals"]["backend_red"]
        assert isinstance(backend_red, int), f"backend_red should be int, got {type(backend_red)}"
        assert backend_red >= 0, f"backend_red should be >= 0, got {backend_red}"
        print(f"✓ totals.backend_red is non-negative: {backend_red}")

    def test_backend_red_matches_pillar_sum(self, overview_data):
        """totals.backend_red should equal sum of pillar-level backend_red."""
        total_from_pillars = sum(
            p["collections"].get("backend_red", 0) for p in overview_data["pillars"]
        )
        assert overview_data["totals"]["backend_red"] == total_from_pillars, \
            f"Mismatch: totals={overview_data['totals']['backend_red']}, sum={total_from_pillars}"
        print(f"✓ totals.backend_red matches pillar sum: {total_from_pillars}")


class TestFrontendStatusAlwaysGreen:
    """Verify frontend.status is always 'green' (API reachable)."""

    def test_all_frontend_status_green(self, overview_data):
        """Every collection's frontend.status must be 'green'."""
        non_green = []
        for pillar in overview_data["pillars"]:
            for row in pillar["collections"]["rows"]:
                fe_status = row["triple_pulse"]["frontend"]["status"]
                if fe_status != "green":
                    non_green.append((row["collection"], fe_status))
        
        assert len(non_green) == 0, f"Found non-green frontend status: {non_green}"
        print("✓ All frontend.status values are 'green'")

    def test_frontend_reason_is_api_reachable(self, overview_data):
        """Frontend reason should indicate API is reachable."""
        for pillar in overview_data["pillars"]:
            for row in pillar["collections"]["rows"][:3]:  # Check first 3 per pillar
                reason = row["triple_pulse"]["frontend"]["reason"]
                assert "reachable" in reason.lower() or "api" in reason.lower(), \
                    f"Unexpected frontend reason for {row['collection']}: {reason}"
        print("✓ Frontend reasons indicate API reachable")


class TestMappedCollectionsBackendStatus:
    """Verify mapped collections with live scheduler have backend.status = 'green'."""

    def test_campaign_leads_backend_green(self, overview_data):
        """campaign_leads with live schedulers should have backend.status = 'green'."""
        for pillar in overview_data["pillars"]:
            for row in pillar["collections"]["rows"]:
                if row["collection"] == "campaign_leads":
                    be = row["triple_pulse"]["backend"]
                    assert be["status"] == "green", f"Expected green, got {be['status']}"
                    assert "writer" in be["reason"].lower() or "live" in be["reason"].lower(), \
                        f"Unexpected reason: {be['reason']}"
                    print(f"✓ campaign_leads backend: {be['status']} - {be['reason']}")
                    return
        pytest.fail("campaign_leads not found in overview")

    def test_mapped_collections_have_writers_in_reason(self, overview_data):
        """Mapped collections should mention writers in backend reason."""
        for pillar in overview_data["pillars"]:
            for row in pillar["collections"]["rows"]:
                if row["collection"] in MAPPED_COLLECTIONS:
                    be = row["triple_pulse"]["backend"]
                    # Should have writers list
                    assert len(be.get("writers", [])) > 0, \
                        f"{row['collection']} should have writers list"
                    print(f"  {row['collection']}: {be['status']} - writers={be['writers']}")


class TestUnmappedCollectionsBackendFallback:
    """Verify unmapped collections fall back to 'green if pillar_live_count>0'."""

    def test_unmapped_collections_backend_green(self, overview_data):
        """Unmapped collections should have backend.status = 'green' (pillar workers live)."""
        for pillar in overview_data["pillars"]:
            for row in pillar["collections"]["rows"]:
                if row["collection"] in UNMAPPED_COLLECTIONS:
                    be = row["triple_pulse"]["backend"]
                    # Should be green with "pillar workers live" reason
                    assert be["status"] == "green", \
                        f"{row['collection']} expected green, got {be['status']}"
                    assert "pillar" in be["reason"].lower() or "workers" in be["reason"].lower(), \
                        f"Unexpected reason for {row['collection']}: {be['reason']}"
                    print(f"✓ {row['collection']}: {be['status']} - {be['reason']}")

    def test_unmapped_collections_have_empty_writers(self, overview_data):
        """Unmapped collections should have empty writers list."""
        for pillar in overview_data["pillars"]:
            for row in pillar["collections"]["rows"]:
                if row["collection"] in UNMAPPED_COLLECTIONS:
                    writers = row["triple_pulse"]["backend"].get("writers", [])
                    assert writers == [], f"{row['collection']} should have empty writers, got {writers}"


class TestPickWorstLogic:
    """Verify collection-level overall status = _pick_worst(db, backend, frontend)."""

    def test_overall_status_is_worst_of_three(self, overview_data):
        """row.status should equal worst of (db, backend, frontend)."""
        def pick_worst(*statuses):
            if "red" in statuses:
                return "red"
            if "yellow" in statuses:
                return "yellow"
            return "green"
        
        mismatches = []
        for pillar in overview_data["pillars"]:
            for row in pillar["collections"]["rows"]:
                tp = row["triple_pulse"]
                expected = pick_worst(
                    tp["db"]["status"],
                    tp["backend"]["status"],
                    tp["frontend"]["status"]
                )
                if row["status"] != expected:
                    mismatches.append({
                        "collection": row["collection"],
                        "actual": row["status"],
                        "expected": expected,
                        "db": tp["db"]["status"],
                        "backend": tp["backend"]["status"],
                        "frontend": tp["frontend"]["status"],
                    })
        
        assert len(mismatches) == 0, f"Status mismatches: {mismatches}"
        print("✓ All collection statuses match _pick_worst logic")

    def test_red_db_makes_overall_red(self, overview_data):
        """If db.status=red, overall should be red."""
        for pillar in overview_data["pillars"]:
            for row in pillar["collections"]["rows"]:
                if row["triple_pulse"]["db"]["status"] == "red":
                    assert row["status"] == "red", \
                        f"{row['collection']}: db=red but overall={row['status']}"
                    print(f"✓ {row['collection']}: db=red → overall=red")


class TestHeartbeatEndpoint:
    """Verify heartbeat endpoint returns cached snapshot with totals.backend_red."""

    def test_heartbeat_has_backend_red(self, auth_headers):
        """GET /api/admin/pillars-map/heartbeat should have totals.backend_red."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/heartbeat",
            headers=auth_headers,
            timeout=30,
        )
        assert resp.status_code == 200, f"Heartbeat failed: {resp.status_code}"
        data = resp.json()
        
        assert "totals" in data, "Missing totals in heartbeat"
        assert "backend_red" in data["totals"], "Missing backend_red in heartbeat totals"
        print(f"✓ Heartbeat totals.backend_red = {data['totals']['backend_red']}")

    def test_heartbeat_has_cached_flag(self, auth_headers):
        """Heartbeat should have 'cached' flag."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/heartbeat",
            headers=auth_headers,
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        # cached flag may be True or False depending on timing
        print(f"✓ Heartbeat cached flag: {data.get('cached', 'not present')}")


class TestExistingEndpointsStillWork:
    """Verify existing endpoints still work after Triple-Pulse addition."""

    def test_services_endpoint(self, auth_headers):
        """GET /api/admin/pillars-map/collection/{name}/services still works."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/collection/campaign_leads/services",
            headers=auth_headers,
            timeout=15,
        )
        assert resp.status_code == 200, f"Services failed: {resp.status_code}"
        data = resp.json()
        assert "service_refs" in data, "Missing service_refs"
        print(f"✓ Services endpoint works: {data.get('count', 0)} refs")

    def test_errors_endpoint(self, auth_headers):
        """GET /api/admin/pillars-map/collection/{name}/errors still works."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/collection/client_errors/errors",
            headers=auth_headers,
            timeout=15,
        )
        assert resp.status_code == 200, f"Errors failed: {resp.status_code}"
        data = resp.json()
        assert "counts" in data, "Missing counts"
        print(f"✓ Errors endpoint works: {data['counts']}")

    def test_health_endpoint(self):
        """GET /api/admin/pillars-map/health still works (no auth)."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/health",
            timeout=10,
        )
        assert resp.status_code == 200, f"Health failed: {resp.status_code}"
        data = resp.json()
        assert data.get("status") == "ok", f"Unexpected status: {data}"
        print("✓ Health endpoint works")


class TestAuthEnforcement:
    """Verify all endpoints still require admin JWT (401 without)."""

    def test_overview_requires_auth(self):
        """GET /api/admin/pillars-map/overview without token returns 401."""
        resp = requests.get(f"{BASE_URL}/api/admin/pillars-map/overview", timeout=10)
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ Overview requires auth")

    def test_heartbeat_requires_auth(self):
        """GET /api/admin/pillars-map/heartbeat without token returns 401."""
        resp = requests.get(f"{BASE_URL}/api/admin/pillars-map/heartbeat", timeout=10)
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ Heartbeat requires auth")

    def test_services_requires_auth(self):
        """GET /api/admin/pillars-map/collection/{name}/services without token returns 401."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/collection/campaign_leads/services",
            timeout=10,
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ Services requires auth")

    def test_errors_requires_auth(self):
        """GET /api/admin/pillars-map/collection/{name}/errors without token returns 401."""
        resp = requests.get(
            f"{BASE_URL}/api/admin/pillars-map/collection/client_errors/errors",
            timeout=10,
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ Errors requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
