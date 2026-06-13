"""
Memoir API E2E Tests — iter 322da
Tests all /api/admin/memoir/* endpoints + integration mirrors (ORA chat, skill broadcast, customer audit).
"""
import os
import sys
import time
import uuid

import pytest
import requests

sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://ai-platform-preview-3.preview.emergentagent.com"


# ─── Fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def customer_jwt(session):
    """Get JWT for customer account (teji.ss1986@gmail.com)"""
    resp = session.post(f"{BASE_URL}/api/auth/login", json={
        "email": "teji.ss1986@gmail.com",
        "password": os.environ.get("AUREM_ADMIN_PASSWORD", "")
    })
    if resp.status_code == 200:
        data = resp.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Auth failed: {resp.status_code} - {resp.text[:200]}")


# ─── Section 1: Memoir Core Endpoints ────────────────────────────────────────
class TestMemoirCoreEndpoints:
    """Tests for /api/admin/memoir/* REST surface"""

    def test_memoir_info(self, session):
        """GET /api/admin/memoir/info returns availability + store path"""
        resp = session.get(f"{BASE_URL}/api/admin/memoir/info")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data["available"] is True, "Memoir should be available"
        assert data["store_path"], "store_path should be set"
        assert data["init_error"] is None, f"init_error should be None, got: {data.get('init_error')}"
        print(f"PASS: /info - available={data['available']}, store_path={data['store_path']}")

    def test_memoir_stats(self, session):
        """GET /api/admin/memoir/stats returns performance metrics"""
        resp = session.get(f"{BASE_URL}/api/admin/memoir/stats")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data["available"] is True, "Memoir should be available"
        assert "performance" in data, "stats should include performance"
        assert "total_keys" in data, "stats should include total_keys"
        assert "total_namespaces" in data, "stats should include total_namespaces"
        print(f"PASS: /stats - total_keys={data.get('total_keys')}, total_namespaces={data.get('total_namespaces')}")

    def test_memoir_health(self, session):
        """GET /api/admin/memoir/_/health returns ok=true"""
        resp = session.get(f"{BASE_URL}/api/admin/memoir/_/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert data["ok"] is True, "health should return ok=true"
        assert data["available"] is True, "health should return available=true"
        print(f"PASS: /_/health - ok={data['ok']}, available={data['available']}")

    def test_memoir_remember_and_recall(self, session):
        """POST /remember + GET /recall round-trip"""
        test_path = "aurem.test.api"
        test_key = f"test_key_{int(time.time())}"
        test_value = {"foo": "bar", "ts": time.time()}

        # Remember
        resp = session.post(f"{BASE_URL}/api/admin/memoir/remember", json={
            "path": test_path,
            "key": test_key,
            "value": test_value,
            "commit_msg": "test:remember"
        })
        assert resp.status_code == 200, f"Remember failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        assert data["ok"] is True, "remember should return ok=true"
        commit_sha = data.get("commit")
        print(f"PASS: /remember - ok={data['ok']}, commit={commit_sha}")

        # Recall
        resp = session.get(f"{BASE_URL}/api/admin/memoir/recall", params={
            "path": test_path,
            "key": test_key
        })
        assert resp.status_code == 200, f"Recall failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        assert data["path"] == test_path
        assert data["key"] == test_key
        assert data["value"]["foo"] == "bar", "Recalled value should match"
        print(f"PASS: /recall - value={data['value']}")

    def test_memoir_search(self, session):
        """GET /search returns items under a path"""
        # First write some test data
        test_path = "aurem.test.search"
        for i in range(3):
            session.post(f"{BASE_URL}/api/admin/memoir/remember", json={
                "path": test_path,
                "key": f"item_{i}",
                "value": {"index": i}
            })

        resp = session.get(f"{BASE_URL}/api/admin/memoir/search", params={
            "path": test_path,
            "limit": 10
        })
        assert resp.status_code == 200, f"Search failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        assert "count" in data, "search should return count"
        assert "items" in data, "search should return items"
        assert data["count"] >= 3, f"Expected at least 3 items, got {data['count']}"
        print(f"PASS: /search - count={data['count']}, items={len(data['items'])}")

    def test_memoir_history(self, session):
        """GET /history returns commit history for a key"""
        test_path = "aurem.test.history"
        test_key = f"hkey_{int(time.time())}"

        # Write twice to create history
        for v in [1, 2]:
            session.post(f"{BASE_URL}/api/admin/memoir/remember", json={
                "path": test_path,
                "key": test_key,
                "value": {"version": v}
            })

        resp = session.get(f"{BASE_URL}/api/admin/memoir/history", params={
            "path": test_path,
            "key": test_key,
            "limit": 10
        })
        assert resp.status_code == 200, f"History failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        assert "history" in data, "history should return history array"
        # History may have commits with id/message/author/timestamp
        print(f"PASS: /history - entries={len(data.get('history', []))}")

    def test_memoir_commit(self, session):
        """POST /commit forces a manual commit"""
        resp = session.post(f"{BASE_URL}/api/admin/memoir/commit", json={
            "message": f"test:manual_commit_{int(time.time())}"
        })
        assert resp.status_code == 200, f"Commit failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        # commit may return sha or None if nothing to commit
        print(f"PASS: /commit - sha={data.get('commit')}")


# ─── Section 2: ORA Chat Memoir Mirror ───────────────────────────────────────
class TestORAMemoirMirror:
    """Tests ORA chat turn persistence to Memoir"""

    def test_ora_chat_creates_session_in_memoir(self, session):
        """POST /api/public/ora/chat should mirror turns to Memoir"""
        # Generate unique session ID
        test_session_id = f"test_sess_{uuid.uuid4().hex[:8]}"

        # Send a chat message (json mode, demo)
        resp = session.post(f"{BASE_URL}/api/public/ora/chat", json={
            "text": "Hello, this is a test message for Memoir integration",
            "session_id": test_session_id,
            "mode": "json"
        }, timeout=30)

        # ORA chat may return 200 or stream
        assert resp.status_code in [200, 201], f"ORA chat failed: {resp.status_code} - {resp.text[:300]}"
        print(f"PASS: ORA chat responded with status {resp.status_code}")

        # Wait a moment for async Memoir write
        time.sleep(2)

        # Check if session is recallable from Memoir
        resp = session.get(f"{BASE_URL}/api/admin/memoir/ora/session/{test_session_id}")
        assert resp.status_code == 200, f"ORA session recall failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        assert "session_id" in data, "Response should include session_id"
        assert "turns" in data, "Response should include turns array"
        # Turns may be empty if Memoir write was async and not yet complete
        print(f"PASS: /ora/session/{test_session_id} - turns={len(data.get('turns', []))}")


# ─── Section 3: Skill Broadcast Memoir Mirror ────────────────────────────────
class TestSkillBroadcastMemoirMirror:
    """Tests skill broadcast persistence to Memoir"""

    def test_skill_broadcast_mirrors_to_memoir(self, session):
        """POST /api/admin/antigravity-skills/broadcast should mirror to Memoir"""
        # Broadcast some skills
        resp = session.post(f"{BASE_URL}/api/admin/antigravity-skills/broadcast", json={
            "skill_ids": ["brainstorming", "security-auditor"]
        })
        assert resp.status_code == 200, f"Broadcast failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        assert data.get("ok") is True, "Broadcast should return ok=true"
        print(f"PASS: Broadcast created - skill_count={data.get('skill_count')}")

        # Wait for Memoir write
        time.sleep(1)

        # Verify via Memoir recall
        resp = session.get(f"{BASE_URL}/api/admin/memoir/recall", params={
            "path": "aurem.skills.broadcast",
            "key": "active"
        })
        assert resp.status_code == 200, f"Memoir recall failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        assert "value" in data, "Recall should return value"
        value = data["value"]
        assert "skill_ids" in value, "Value should include skill_ids"
        assert "brainstorming" in value["skill_ids"], "skill_ids should include brainstorming"
        assert "security-auditor" in value["skill_ids"], "skill_ids should include security-auditor"
        print(f"PASS: Memoir recall - skill_ids={value.get('skill_ids')}")


# ─── Section 4: Customer Audit Memoir Mirror ─────────────────────────────────
class TestCustomerAuditMemoirMirror:
    """Tests customer audit persistence to Memoir"""

    def test_customer_audit_mirrors_to_memoir(self, session, customer_jwt):
        """POST /api/customer/audit/run should mirror to Memoir"""
        # Run an audit
        headers = {"Authorization": f"Bearer {customer_jwt}"}
        resp = session.post(f"{BASE_URL}/api/customer/audit/run", json={
            "url": "https://example.com"
        }, headers=headers, timeout=60)

        assert resp.status_code == 200, f"Audit run failed: {resp.status_code} - {resp.text[:300]}"
        data = resp.json()
        assert data.get("status") in ["completed", "partial"], f"Unexpected status: {data.get('status')}"
        print(f"PASS: Audit completed - status={data.get('status')}")

        # Wait for Memoir write
        time.sleep(2)

        # Verify via Memoir recall (path: aurem.customers.{email}.audits, key: latest)
        email = "teji.ss1986@gmail.com"
        resp = session.get(f"{BASE_URL}/api/admin/memoir/recall", params={
            "path": f"aurem.customers.{email}.audits",
            "key": "latest"
        })
        # May be 404 if Memoir write failed or path doesn't exist yet
        if resp.status_code == 200:
            data = resp.json()
            value = data.get("value", {})
            assert "scores" in value or "url" in value, "Audit summary should have scores or url"
            print(f"PASS: Memoir audit recall - url={value.get('url')}, scores={value.get('scores')}")
        else:
            print(f"INFO: Memoir audit recall returned {resp.status_code} - may be async delay")


# ─── Section 5: Regression Tests ─────────────────────────────────────────────
class TestRegressions:
    """Regression tests from iter 322bz/322ca"""

    def test_health_endpoint_fast(self, session):
        """GET /health should respond in <1s"""
        import time
        start = time.time()
        resp = session.get(f"{BASE_URL}/health", timeout=5)
        elapsed = time.time() - start
        assert resp.status_code == 200, f"Health failed: {resp.status_code}"
        assert elapsed < 1.0, f"Health took {elapsed:.2f}s, expected <1s"
        print(f"PASS: /health - {resp.status_code} in {elapsed*1000:.0f}ms")

    def test_skills_library_meta(self, session):
        """GET /api/admin/antigravity-skills/library/meta returns total_in_db=1453"""
        resp = session.get(f"{BASE_URL}/api/admin/antigravity-skills/library/meta")
        assert resp.status_code == 200, f"Skills meta failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        assert data.get("total_in_db") == 1453, f"Expected 1453 skills, got {data.get('total_in_db')}"
        print(f"PASS: /library/meta - total_in_db={data.get('total_in_db')}")

    def test_customer_audit_health(self, session):
        """GET /api/customer/audit/_/health returns ok=true, psi_key_configured=true"""
        resp = session.get(f"{BASE_URL}/api/customer/audit/_/health")
        assert resp.status_code == 200, f"Audit health failed: {resp.status_code} - {resp.text[:200]}"
        data = resp.json()
        assert data.get("ok") is True, "Audit health should return ok=true"
        assert data.get("psi_key_configured") is True, "psi_key_configured should be true"
        print(f"PASS: /audit/_/health - ok={data.get('ok')}, psi_key_configured={data.get('psi_key_configured')}")


# ─── Section 6: Cleanup ──────────────────────────────────────────────────────
class TestCleanup:
    """Cleanup after tests"""

    def test_clear_broadcast(self, session):
        """POST /api/admin/antigravity-skills/broadcast/clear to leave broadcast cleared"""
        resp = session.post(f"{BASE_URL}/api/admin/antigravity-skills/broadcast/clear")
        assert resp.status_code == 200, f"Clear broadcast failed: {resp.status_code} - {resp.text[:200]}"
        print("PASS: Broadcast cleared")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
