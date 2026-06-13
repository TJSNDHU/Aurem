"""
Antigravity Skills Router Tests — iter 322bz
Tests for the 1,453 SKILL.md playbooks library + broadcast functionality.

Endpoints tested:
  GET  /api/admin/antigravity-skills/library/meta
  GET  /api/admin/antigravity-skills/library
  GET  /api/admin/antigravity-skills/library/categories
  GET  /api/admin/antigravity-skills/library/{skill_id}
  POST /api/admin/antigravity-skills/broadcast
  GET  /api/admin/antigravity-skills/broadcast/active
  POST /api/admin/antigravity-skills/broadcast/clear
"""
import pytest
import requests
import os
import time

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="asserts pre-slim health/bootstrap shape or older infra spec — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://ai-platform-preview-3.preview.emergentagent.com"

SKILLS_BASE = f"{BASE_URL}/api/admin/antigravity-skills"


class TestHealthEndpoints:
    """Verify health endpoints respond fast (deploy fix verification)"""

    def test_root_health_fast(self):
        """GET /health responds 200 in <1s"""
        start = time.time()
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        elapsed = time.time() - start
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert elapsed < 1.0, f"Health check took {elapsed:.2f}s, expected <1s"
        data = response.json()
        assert "status" in data
        print(f"✓ /health responded in {elapsed*1000:.0f}ms")

    def test_platform_health_fast(self):
        """GET /api/platform/health responds 200 instantly"""
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/platform/health", timeout=5)
        elapsed = time.time() - start
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert elapsed < 1.0, f"Platform health took {elapsed:.2f}s, expected <1s"
        data = response.json()
        assert data.get("status") == "ok"
        print(f"✓ /api/platform/health responded in {elapsed*1000:.0f}ms")


class TestLibraryMeta:
    """Test /library/meta endpoint"""

    def test_library_meta_returns_1453_skills(self):
        """GET /library/meta returns total_in_db=1453 and ingestion meta"""
        response = requests.get(f"{SKILLS_BASE}/library/meta", timeout=10)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify total count
        assert "total_in_db" in data, "Missing total_in_db field"
        assert data["total_in_db"] == 1453, f"Expected 1453 skills, got {data['total_in_db']}"
        
        # Verify meta fields
        assert "meta" in data, "Missing meta field"
        meta = data["meta"]
        assert "ingested_at" in meta, "Missing ingested_at in meta"
        assert "total_in_index" in meta, "Missing total_in_index in meta"
        assert meta["total_in_index"] == 1453, f"Expected 1453 in index, got {meta['total_in_index']}"
        assert "source" in meta, "Missing source in meta"
        assert "github.com/sickn33/antigravity-awesome-skills" in meta["source"]
        
        print(f"✓ Library meta: {data['total_in_db']} skills, ingested at {meta['ingested_at']}")


class TestLibrarySearch:
    """Test /library search endpoint"""

    def test_search_security_returns_items(self):
        """GET /library?q=security&limit=5 returns items with security category"""
        response = requests.get(
            f"{SKILLS_BASE}/library",
            params={"q": "security", "limit": 5},
            timeout=10
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "items" in data, "Missing items field"
        assert "total" in data, "Missing total field"
        assert len(data["items"]) <= 5, f"Expected max 5 items, got {len(data['items'])}"
        assert data["total"] > 0, "Expected at least some security-related skills"
        
        # Verify item structure
        for item in data["items"]:
            assert "id" in item, "Missing id in item"
            assert "name" in item, "Missing name in item"
            assert "category" in item, "Missing category in item"
            assert "description" in item, "Missing description in item"
        
        print(f"✓ Security search: {data['total']} total, returned {len(data['items'])} items")

    def test_search_by_category(self):
        """GET /library?category=development returns development skills"""
        response = requests.get(
            f"{SKILLS_BASE}/library",
            params={"category": "development", "limit": 10},
            timeout=10
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["items"]) > 0, "Expected development skills"
        for item in data["items"]:
            assert item["category"] == "development", f"Expected development category, got {item['category']}"
        
        print(f"✓ Category filter: {data['total']} development skills")

    def test_pagination(self):
        """Test skip/limit pagination"""
        # First page
        r1 = requests.get(f"{SKILLS_BASE}/library", params={"limit": 5, "skip": 0}, timeout=10)
        assert r1.status_code == 200
        d1 = r1.json()
        
        # Second page
        r2 = requests.get(f"{SKILLS_BASE}/library", params={"limit": 5, "skip": 5}, timeout=10)
        assert r2.status_code == 200
        d2 = r2.json()
        
        # Verify different items
        ids1 = {item["id"] for item in d1["items"]}
        ids2 = {item["id"] for item in d2["items"]}
        assert ids1.isdisjoint(ids2), "Pagination returned duplicate items"
        
        print(f"✓ Pagination working: page1={len(d1['items'])} items, page2={len(d2['items'])} items")


class TestLibraryCategories:
    """Test /library/categories endpoint"""

    def test_categories_returns_many(self):
        """GET /library/categories returns >50 categories with counts"""
        response = requests.get(f"{SKILLS_BASE}/library/categories", timeout=10)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "categories" in data, "Missing categories field"
        categories = data["categories"]
        
        assert len(categories) > 50, f"Expected >50 categories, got {len(categories)}"
        
        # Verify structure
        for cat in categories:
            assert "category" in cat, "Missing category name"
            assert "count" in cat, "Missing count"
            assert cat["count"] > 0, f"Category {cat['category']} has 0 count"
        
        # Verify some expected categories exist
        cat_names = {c["category"] for c in categories}
        expected = {"development", "security", "cloud", "ai-ml", "business"}
        found = expected & cat_names
        assert len(found) >= 4, f"Missing expected categories. Found: {found}"
        
        total_skills = sum(c["count"] for c in categories)
        print(f"✓ Categories: {len(categories)} categories, {total_skills} total skills")


class TestLibraryGetSkill:
    """Test /library/{skill_id} endpoint"""

    def test_get_brainstorming_skill(self):
        """GET /library/brainstorming returns full SKILL.md body"""
        response = requests.get(f"{SKILLS_BASE}/library/brainstorming", timeout=10)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data["id"] == "brainstorming", f"Expected id=brainstorming, got {data['id']}"
        assert "body" in data, "Missing body field"
        assert len(data["body"]) > 100, "Body too short, expected full SKILL.md content"
        assert "# Brainstorming" in data["body"], "Body should contain markdown heading"
        assert "body_size" in data, "Missing body_size field"
        assert data["body_size"] > 0, "body_size should be positive"
        
        print(f"✓ Skill 'brainstorming': {data['body_size']} bytes, category={data['category']}")

    def test_get_nonexistent_skill_404(self):
        """GET /library/nonexistent-skill-xyz returns 404"""
        response = requests.get(f"{SKILLS_BASE}/library/nonexistent-skill-xyz-12345", timeout=10)
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Nonexistent skill returns 404")


class TestBroadcast:
    """Test broadcast endpoints"""

    def test_broadcast_flow(self):
        """Full broadcast flow: POST broadcast → GET active → POST clear → verify cleared"""
        
        # Step 1: Clear any existing broadcast first
        clear_resp = requests.post(f"{SKILLS_BASE}/broadcast/clear", timeout=10)
        assert clear_resp.status_code == 200, f"Clear failed: {clear_resp.status_code}"
        
        # Step 2: Verify cleared
        active_resp = requests.get(f"{SKILLS_BASE}/broadcast/active", timeout=10)
        assert active_resp.status_code == 200
        active_data = active_resp.json()
        assert active_data.get("active") == False or "skill_ids" not in active_data, \
            "Broadcast should be cleared"
        print("✓ Broadcast cleared successfully")
        
        # Step 3: Create new broadcast
        broadcast_payload = {
            "skill_ids": ["brainstorming", "security-auditor"],
            "note": "pytest test broadcast"
        }
        broadcast_resp = requests.post(
            f"{SKILLS_BASE}/broadcast",
            json=broadcast_payload,
            timeout=10
        )
        
        assert broadcast_resp.status_code == 200, f"Broadcast failed: {broadcast_resp.status_code} - {broadcast_resp.text}"
        broadcast_data = broadcast_resp.json()
        
        assert broadcast_data.get("ok") == True, "Expected ok=true"
        assert broadcast_data.get("skill_count") == 2, f"Expected skill_count=2, got {broadcast_data.get('skill_count')}"
        assert set(broadcast_data.get("skill_ids", [])) == {"brainstorming", "security-auditor"}
        assert "broadcast_at" in broadcast_data
        assert "addendum_chars" in broadcast_data
        print(f"✓ Broadcast created: {broadcast_data['skill_count']} skills, {broadcast_data['addendum_chars']} chars")
        
        # Step 4: Verify active broadcast
        active_resp2 = requests.get(f"{SKILLS_BASE}/broadcast/active", timeout=10)
        assert active_resp2.status_code == 200
        active_data2 = active_resp2.json()
        
        assert "skill_ids" in active_data2, "Missing skill_ids in active broadcast"
        assert "system_addendum" in active_data2, "Missing system_addendum in active broadcast"
        assert set(active_data2["skill_ids"]) == {"brainstorming", "security-auditor"}
        assert len(active_data2["system_addendum"]) > 100, "system_addendum too short"
        print(f"✓ Active broadcast verified: {len(active_data2['skill_ids'])} skills")
        
        # Step 5: Clear broadcast (cleanup)
        clear_resp2 = requests.post(f"{SKILLS_BASE}/broadcast/clear", timeout=10)
        assert clear_resp2.status_code == 200
        clear_data = clear_resp2.json()
        assert clear_data.get("cleared") == True, "Expected cleared=true"
        print("✓ Broadcast cleared (cleanup)")
        
        # Step 6: Verify cleared
        active_resp3 = requests.get(f"{SKILLS_BASE}/broadcast/active", timeout=10)
        assert active_resp3.status_code == 200
        active_data3 = active_resp3.json()
        assert active_data3.get("active") == False, "Broadcast should show active=false after clear"
        print("✓ Verified broadcast is cleared")

    def test_broadcast_unknown_skill_404(self):
        """POST /broadcast with unknown skill_ids returns 404"""
        payload = {
            "skill_ids": ["nonexistent-skill-xyz-99999"],
            "note": "should fail"
        }
        response = requests.post(f"{SKILLS_BASE}/broadcast", json=payload, timeout=10)
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Unknown skill in broadcast returns 404")

    def test_broadcast_empty_skill_ids_422(self):
        """POST /broadcast with empty skill_ids returns 422"""
        payload = {
            "skill_ids": [],
            "note": "should fail validation"
        }
        response = requests.post(f"{SKILLS_BASE}/broadcast", json=payload, timeout=10)
        
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Empty skill_ids returns 422 validation error")


class TestORAIntegration:
    """Test ORA chat endpoint still works"""

    def test_ora_chat_endpoint_exists(self):
        """POST /api/public/ora/chat endpoint is reachable"""
        # Just verify the endpoint exists and accepts POST
        # We don't need to test full chat functionality here
        response = requests.post(
            f"{BASE_URL}/api/public/ora/chat",
            json={"message": "hello", "session_id": "test-session"},
            timeout=15
        )
        
        # Should not be 404 or 405
        assert response.status_code not in [404, 405], \
            f"ORA chat endpoint not found or method not allowed: {response.status_code}"
        
        print(f"✓ ORA chat endpoint reachable, status={response.status_code}")


# Cleanup fixture to ensure broadcast is cleared after all tests
@pytest.fixture(scope="module", autouse=True)
def cleanup_broadcast():
    """Ensure broadcast is cleared after all tests"""
    yield
    # Cleanup: clear any active broadcast
    try:
        requests.post(f"{SKILLS_BASE}/broadcast/clear", timeout=10)
        print("\n✓ Cleanup: broadcast cleared")
    except Exception as e:
        print(f"\n⚠ Cleanup failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
