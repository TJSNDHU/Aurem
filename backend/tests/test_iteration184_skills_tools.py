"""
Iteration 184 - AUREM Skills & Tools Testing
=============================================
Tests for 4 new skills wired into AUREM:
1. UI UX Pro Max — design intelligence (161 rules, 67 styles, 161 palettes)
2. Superpowers — TDD, debugging, verification patterns
3. LightRAG — graph+vector hybrid RAG (graceful without LLM key)
4. n8n-MCP — 400+ integrations (graceful without n8n instance)

Endpoints tested:
- POST /api/skills/design/recommend
- POST /api/skills/design/search
- GET /api/skills/superpowers
- GET /api/skills/superpowers/{name}
- POST /api/skills/lightrag/insert
- POST /api/skills/lightrag/query
- GET /api/skills/lightrag/stats
- GET /api/skills/n8n/status
- GET /api/skills/n8n/workflows
- GET /api/skills/inventory
- Auth guards (401 without token)
- Regression: /api/self-audit/run, /api/self-audit/usage, /api/docs/generate
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TEST_EMAIL = "teji.ss1986@gmail.com"
TEST_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for testing."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("token") or data.get("access_token")
    pytest.skip(f"Auth failed: {response.status_code} - {response.text[:200]}")


@pytest.fixture
def auth_headers(auth_token):
    """Headers with auth token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestDesignIntelligence:
    """Tests for UI UX Pro Max design intelligence endpoints."""

    def test_design_recommend_beauty_spa(self, auth_headers):
        """POST /api/skills/design/recommend - beauty spa product type."""
        response = requests.post(
            f"{BASE_URL}/api/skills/design/recommend",
            headers=auth_headers,
            json={"product_type": "beauty spa", "business_name": "Glow Spa"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:200]}"
        data = response.json()
        
        # Validate response structure
        assert "reasoning" in data, "Missing reasoning in response"
        assert "colors" in data, "Missing colors in response"
        assert "style" in data, "Missing style in response"
        assert "typography" in data, "Missing typography in response"
        assert "anti_patterns" in data, "Missing anti_patterns in response"
        assert "checklist" in data, "Missing checklist in response"
        
        # Validate reasoning has product match
        reasoning = data["reasoning"]
        assert "product_type" in reasoning
        # Should match Beauty/Spa/Wellness or similar
        assert "error" not in reasoning or reasoning.get("error") != "not_found"
        
        # Validate colors structure
        colors = data["colors"]
        assert "primary" in colors or "error" in colors
        
        print(f"Design recommend for 'beauty spa': product_type={reasoning.get('product_type')}, style={reasoning.get('primary_style')}")

    def test_design_recommend_saas(self, auth_headers):
        """POST /api/skills/design/recommend - SaaS product type."""
        response = requests.post(
            f"{BASE_URL}/api/skills/design/recommend",
            headers=auth_headers,
            json={"product_type": "saas", "business_name": "CloudApp"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "reasoning" in data
        assert "colors" in data
        print(f"Design recommend for 'saas': product_type={data['reasoning'].get('product_type')}")

    def test_design_recommend_fintech(self, auth_headers):
        """POST /api/skills/design/recommend - fintech product type."""
        response = requests.post(
            f"{BASE_URL}/api/skills/design/recommend",
            headers=auth_headers,
            json={"product_type": "fintech", "business_name": "PayFlow"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "reasoning" in data
        print(f"Design recommend for 'fintech': product_type={data['reasoning'].get('product_type')}")

    def test_design_recommend_restaurant(self, auth_headers):
        """POST /api/skills/design/recommend - restaurant product type."""
        response = requests.post(
            f"{BASE_URL}/api/skills/design/recommend",
            headers=auth_headers,
            json={"product_type": "restaurant", "business_name": "Bistro 42"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "reasoning" in data
        print(f"Design recommend for 'restaurant': product_type={data['reasoning'].get('product_type')}")

    def test_design_search_style(self, auth_headers):
        """POST /api/skills/design/search - search styles."""
        response = requests.post(
            f"{BASE_URL}/api/skills/design/search",
            headers=auth_headers,
            json={"query": "minimalist", "domain": "style", "limit": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "domain" in data
        assert data["domain"] == "style"
        print(f"Style search for 'minimalist': {len(data['results'])} results")

    def test_design_search_typography(self, auth_headers):
        """POST /api/skills/design/search - search typography."""
        response = requests.post(
            f"{BASE_URL}/api/skills/design/search",
            headers=auth_headers,
            json={"query": "modern", "domain": "typography", "limit": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["domain"] == "typography"
        print(f"Typography search for 'modern': {len(data['results'])} results")

    def test_design_search_colors(self, auth_headers):
        """POST /api/skills/design/search - search colors."""
        response = requests.post(
            f"{BASE_URL}/api/skills/design/search",
            headers=auth_headers,
            json={"query": "healthcare", "domain": "colors", "limit": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["domain"] == "colors"
        print(f"Colors search for 'healthcare': returned {type(data['results'])}")


class TestSuperpowersSkills:
    """Tests for Superpowers skill patterns (TDD, debugging, verification)."""

    def test_list_all_skills(self, auth_headers):
        """GET /api/skills/superpowers - list all skill patterns."""
        response = requests.get(
            f"{BASE_URL}/api/skills/superpowers",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "skills" in data
        skills = data["skills"]
        
        # Should have 5 skills: tdd, systematic_debugging, verification_before_completion, brainstorming, writing_plans
        expected_skills = ["tdd", "systematic_debugging", "verification_before_completion", "brainstorming", "writing_plans"]
        for skill in expected_skills:
            assert skill in skills, f"Missing skill: {skill}"
        
        print(f"Superpowers skills: {list(skills.keys())}")

    def test_get_tdd_skill(self, auth_headers):
        """GET /api/skills/superpowers/tdd - get TDD skill details."""
        response = requests.get(
            f"{BASE_URL}/api/skills/superpowers/tdd",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Validate TDD skill structure
        assert "name" in data
        assert data["name"] == "Test-Driven Development"
        assert "process" in data
        assert "rules" in data
        assert len(data["process"]) >= 5, "TDD should have at least 5 process steps"
        assert len(data["rules"]) >= 3, "TDD should have at least 3 rules"
        
        print(f"TDD skill: {len(data['process'])} steps, {len(data['rules'])} rules")

    def test_get_systematic_debugging_skill(self, auth_headers):
        """GET /api/skills/superpowers/systematic_debugging - get debugging skill."""
        response = requests.get(
            f"{BASE_URL}/api/skills/superpowers/systematic_debugging",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "name" in data
        assert data["name"] == "Systematic Debugging"
        assert "process" in data
        assert "rules" in data
        
        # Check for OBSERVE, HYPOTHESIZE, TEST, FIX phases
        process_text = " ".join(data["process"])
        assert "OBSERVE" in process_text or "observe" in process_text.lower()
        
        print(f"Debugging skill: {len(data['process'])} phases, {len(data['rules'])} rules")

    def test_get_verification_skill(self, auth_headers):
        """GET /api/skills/superpowers/verification_before_completion - get verification skill."""
        response = requests.get(
            f"{BASE_URL}/api/skills/superpowers/verification_before_completion",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "name" in data
        assert "Verification" in data["name"]
        assert "process" in data
        
        print(f"Verification skill: {len(data['process'])} steps")

    def test_get_unknown_skill_404(self, auth_headers):
        """GET /api/skills/superpowers/unknown_skill - should return 404."""
        response = requests.get(
            f"{BASE_URL}/api/skills/superpowers/unknown_skill_xyz",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404 for unknown skill, got {response.status_code}"


class TestLightRAG:
    """Tests for LightRAG graph+vector hybrid RAG (graceful without LLM key)."""

    def test_lightrag_stats(self, auth_headers):
        """GET /api/skills/lightrag/stats - get LightRAG status."""
        response = requests.get(
            f"{BASE_URL}/api/skills/lightrag/stats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return status (either active or not_initialized)
        assert "status" in data
        # Without LLM key, should be not_initialized
        if data["status"] == "not_initialized":
            assert "reason" in data
            print(f"LightRAG status: not_initialized (expected - no LLM key)")
        else:
            print(f"LightRAG status: {data['status']}")

    def test_lightrag_insert_graceful(self, auth_headers):
        """POST /api/skills/lightrag/insert - graceful without LLM key."""
        response = requests.post(
            f"{BASE_URL}/api/skills/lightrag/insert",
            headers=auth_headers,
            json={"text": "Test knowledge for AUREM platform", "metadata": {"source": "test"}}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Without LLM key, should return inserted=false with reason
        assert "inserted" in data
        if not data["inserted"]:
            assert "reason" in data
            assert data["reason"] == "lightrag_not_available"
            print(f"LightRAG insert: graceful degradation - {data['reason']}")
        else:
            print(f"LightRAG insert: success - {data.get('engine')}")

    def test_lightrag_query_fallback(self, auth_headers):
        """POST /api/skills/lightrag/query - falls back to Memobase."""
        response = requests.post(
            f"{BASE_URL}/api/skills/lightrag/query",
            headers=auth_headers,
            json={"query": "What is AUREM?", "mode": "hybrid"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have answer and mode
        assert "answer" in data
        assert "mode" in data
        
        # Without LLM key, should fallback to memobase
        if data.get("engine") == "memobase":
            print(f"LightRAG query: fallback to Memobase")
        elif data.get("mode") == "fallback_failed":
            print(f"LightRAG query: fallback failed (no Memobase)")
        else:
            print(f"LightRAG query: {data.get('engine')} mode={data.get('mode')}")


class TestN8NConnector:
    """Tests for n8n workflow connector (graceful without n8n instance)."""

    def test_n8n_status_not_configured(self, auth_headers):
        """GET /api/skills/n8n/status - returns not configured."""
        response = requests.get(
            f"{BASE_URL}/api/skills/n8n/status",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Without N8N_API_URL, should return connected=false
        assert "connected" in data
        if not data["connected"]:
            assert "reason" in data
            print(f"n8n status: not configured - {data['reason']}")
        else:
            print(f"n8n status: connected to {data.get('url')}")

    def test_n8n_workflows_empty(self, auth_headers):
        """GET /api/skills/n8n/workflows - returns empty list when not configured."""
        response = requests.get(
            f"{BASE_URL}/api/skills/n8n/workflows",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "workflows" in data
        assert "count" in data
        # Without n8n configured, should be empty
        if data["count"] == 0:
            print(f"n8n workflows: empty (not configured)")
        else:
            print(f"n8n workflows: {data['count']} workflows")


class TestSkillsInventory:
    """Tests for skills inventory endpoint."""

    def test_skills_inventory(self, auth_headers):
        """GET /api/skills/inventory - lists all installed skills + service statuses."""
        response = requests.get(
            f"{BASE_URL}/api/skills/inventory",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Validate structure
        assert "installed_skills" in data
        assert "services" in data
        assert "total_skills" in data
        
        # Check installed skills
        installed = data["installed_skills"]
        skill_names = [s["name"] for s in installed]
        print(f"Installed skills: {skill_names}")
        
        # Check services status
        services = data["services"]
        assert "design_intelligence" in services
        assert "superpowers" in services
        assert "lightrag" in services
        assert "n8n" in services
        
        # Design intelligence should be active
        assert services["design_intelligence"]["status"] == "active"
        # Superpowers should be active
        assert services["superpowers"]["status"] == "active"
        
        print(f"Services: design={services['design_intelligence']['status']}, superpowers={services['superpowers']['status']}")
        print(f"LightRAG: {services['lightrag'].get('status')}, n8n: {services['n8n'].get('connected')}")


class TestAuthGuards:
    """Tests for auth guards - all endpoints should return 401 without token."""

    def test_design_recommend_no_auth(self):
        """POST /api/skills/design/recommend without auth - should return 401."""
        response = requests.post(
            f"{BASE_URL}/api/skills/design/recommend",
            json={"product_type": "saas"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    def test_design_search_no_auth(self):
        """POST /api/skills/design/search without auth - should return 401."""
        response = requests.post(
            f"{BASE_URL}/api/skills/design/search",
            json={"query": "modern"}
        )
        assert response.status_code == 401

    def test_superpowers_no_auth(self):
        """GET /api/skills/superpowers without auth - should return 401."""
        response = requests.get(f"{BASE_URL}/api/skills/superpowers")
        assert response.status_code == 401

    def test_superpowers_skill_no_auth(self):
        """GET /api/skills/superpowers/tdd without auth - should return 401."""
        response = requests.get(f"{BASE_URL}/api/skills/superpowers/tdd")
        assert response.status_code == 401

    def test_lightrag_stats_no_auth(self):
        """GET /api/skills/lightrag/stats without auth - should return 401."""
        response = requests.get(f"{BASE_URL}/api/skills/lightrag/stats")
        assert response.status_code == 401

    def test_lightrag_insert_no_auth(self):
        """POST /api/skills/lightrag/insert without auth - should return 401."""
        response = requests.post(
            f"{BASE_URL}/api/skills/lightrag/insert",
            json={"text": "test"}
        )
        assert response.status_code == 401

    def test_lightrag_query_no_auth(self):
        """POST /api/skills/lightrag/query without auth - should return 401."""
        response = requests.post(
            f"{BASE_URL}/api/skills/lightrag/query",
            json={"query": "test"}
        )
        assert response.status_code == 401

    def test_n8n_status_no_auth(self):
        """GET /api/skills/n8n/status without auth - should return 401."""
        response = requests.get(f"{BASE_URL}/api/skills/n8n/status")
        assert response.status_code == 401

    def test_n8n_workflows_no_auth(self):
        """GET /api/skills/n8n/workflows without auth - should return 401."""
        response = requests.get(f"{BASE_URL}/api/skills/n8n/workflows")
        assert response.status_code == 401

    def test_inventory_no_auth(self):
        """GET /api/skills/inventory without auth - should return 401."""
        response = requests.get(f"{BASE_URL}/api/skills/inventory")
        assert response.status_code == 401


class TestRegressionExistingEndpoints:
    """Regression tests for existing endpoints that should still work."""

    def test_self_audit_run(self, auth_headers):
        """POST /api/self-audit/run - regression test."""
        response = requests.post(
            f"{BASE_URL}/api/self-audit/run",
            headers=auth_headers,
            json={"auto_fix": False, "scope": "quick"}
        )
        assert response.status_code == 200, f"Self-audit run failed: {response.status_code}"
        data = response.json()
        assert "status" in data or "issues" in data or "summary" in data
        print(f"Self-audit run: {response.status_code} OK")

    def test_self_audit_usage(self, auth_headers):
        """GET /api/self-audit/usage - regression test."""
        response = requests.get(
            f"{BASE_URL}/api/self-audit/usage",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Self-audit usage failed: {response.status_code}"
        data = response.json()
        assert "plan" in data
        assert "used" in data or "fixes_used" in data
        print(f"Self-audit usage: plan={data.get('plan')}")

    def test_docs_generate(self, auth_headers):
        """POST /api/docs/generate - regression test."""
        response = requests.post(
            f"{BASE_URL}/api/docs/generate",
            headers=auth_headers,
            json={
                "title": "Test API Documentation",
                "sections": [
                    {"heading": "Overview", "content": "This is a test document."},
                    {"heading": "Endpoints", "content": "List of API endpoints."}
                ],
                "format": "docx",
                "doc_type": "custom"
            }
        )
        # May return 200 with doc_id or error
        assert response.status_code == 200, f"Docs generate failed: {response.status_code} - {response.text[:200]}"
        print(f"Docs generate: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
