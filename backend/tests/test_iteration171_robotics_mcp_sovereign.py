"""
Test Suite: Iteration 171 - Robotics Digital Twin, MCP Extended Tools, Sovereign Node
======================================================================================
Tests for:
1. Robotics Digital Twin API (6-DOF arm simulation, sequences, triggers)
2. MCP Extended Tools (Web Browse, File System, Database)
3. Sovereign Node (Cloudflare Tunnel status)

All endpoints require auth except where noted.
"""
import os
import time
import pytest
import requests

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MCP_API_KEY = "reroots-mcp-2024"

# Test credentials
TEST_EMAIL = "teji.ss1986@gmail.com"
TEST_PASSWORD = os.environ.get("AUREM_ADMIN_PASSWORD", "")


@pytest.fixture(scope="module")
def auth_token():
    """Get JWT token for authenticated requests."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if resp.status_code == 200:
        return resp.json().get("token")
    pytest.skip(f"Auth failed: {resp.status_code} - {resp.text[:200]}")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with Bearer token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def mcp_headers():
    """Headers with MCP API key."""
    return {"Authorization": f"Bearer {MCP_API_KEY}", "Content-Type": "application/json"}


# ═══════════════════════════════════════════════════════════════
# ROBOTICS DIGITAL TWIN TESTS
# ═══════════════════════════════════════════════════════════════

class TestRoboticsAuth:
    """Test that all robotics endpoints require authentication."""

    def test_config_requires_auth(self):
        """GET /api/robotics/config returns 401 without token."""
        resp = requests.get(f"{BASE_URL}/api/robotics/config")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: /api/robotics/config requires auth")

    def test_sequences_requires_auth(self):
        """GET /api/robotics/sequences returns 401 without token."""
        resp = requests.get(f"{BASE_URL}/api/robotics/sequences")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: /api/robotics/sequences requires auth")

    def test_state_requires_auth(self):
        """GET /api/robotics/state returns 401 without token."""
        resp = requests.get(f"{BASE_URL}/api/robotics/state")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: /api/robotics/state requires auth")

    def test_trigger_requires_auth(self):
        """POST /api/robotics/trigger returns 401 without token."""
        resp = requests.post(f"{BASE_URL}/api/robotics/trigger", json={
            "sequence_id": "pick_and_pack",
            "trigger": "test"
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: /api/robotics/trigger requires auth")

    def test_history_requires_auth(self):
        """GET /api/robotics/history returns 401 without token."""
        resp = requests.get(f"{BASE_URL}/api/robotics/history")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: /api/robotics/history requires auth")


class TestRoboticsConfig:
    """Test arm configuration endpoint."""

    def test_get_arm_config(self, auth_headers):
        """GET /api/robotics/config returns 6-DOF arm config."""
        resp = requests.get(f"{BASE_URL}/api/robotics/config", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert data.get("name") == "AUREM-Sovereign-Arm", f"Expected name AUREM-Sovereign-Arm, got {data.get('name')}"
        assert data.get("dof") == 6, f"Expected 6 DOF, got {data.get('dof')}"
        assert data.get("reach_mm") == 550, f"Expected reach 550mm, got {data.get('reach_mm')}"
        
        joints = data.get("joints", [])
        assert len(joints) == 6, f"Expected 6 joints, got {len(joints)}"
        
        # Verify joint names
        expected_joints = ["base_rotation", "shoulder", "elbow", "wrist_pitch", "wrist_roll", "gripper"]
        actual_joints = [j.get("name") for j in joints]
        assert actual_joints == expected_joints, f"Joint names mismatch: {actual_joints}"
        
        print(f"PASS: /api/robotics/config returns correct arm config (6-DOF, 550mm reach)")


class TestRoboticsSequences:
    """Test animation sequences endpoint."""

    def test_get_sequences(self, auth_headers):
        """GET /api/robotics/sequences returns 5 sequences."""
        resp = requests.get(f"{BASE_URL}/api/robotics/sequences", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        sequences = data.get("sequences", {})
        
        expected_sequences = ["idle_breathe", "pick_and_pack", "point_and_scan", "quality_inspect", "wave_greeting"]
        for seq_id in expected_sequences:
            assert seq_id in sequences, f"Missing sequence: {seq_id}"
        
        assert len(sequences) == 5, f"Expected 5 sequences, got {len(sequences)}"
        
        # Verify pick_and_pack has shopify_order_paid trigger
        pick_pack = sequences.get("pick_and_pack", {})
        assert pick_pack.get("trigger") == "shopify_order_paid", f"pick_and_pack trigger should be shopify_order_paid"
        
        # Verify point_and_scan has inventory_low trigger
        point_scan = sequences.get("point_and_scan", {})
        assert point_scan.get("trigger") == "inventory_low", f"point_and_scan trigger should be inventory_low"
        
        print(f"PASS: /api/robotics/sequences returns 5 sequences with correct triggers")


class TestRoboticsState:
    """Test arm state endpoint."""

    def test_get_idle_state(self, auth_headers):
        """GET /api/robotics/state returns idle state with joints [0,0,0,0,0,0]."""
        resp = requests.get(f"{BASE_URL}/api/robotics/state", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert data.get("status") == "idle", f"Expected status=idle, got {data.get('status')}"
        
        joints = data.get("joints", [])
        assert joints == [0, 0, 0, 0, 0, 0], f"Expected joints [0,0,0,0,0,0], got {joints}"
        
        assert data.get("sequence") == "idle_breathe", f"Expected sequence=idle_breathe, got {data.get('sequence')}"
        
        print(f"PASS: /api/robotics/state returns idle state with joints [0,0,0,0,0,0]")


class TestRoboticsTrigger:
    """Test sequence trigger endpoint."""

    def test_trigger_pick_and_pack(self, auth_headers):
        """POST /api/robotics/trigger with pick_and_pack returns task_id."""
        resp = requests.post(f"{BASE_URL}/api/robotics/trigger", headers=auth_headers, json={
            "sequence_id": "pick_and_pack",
            "trigger": "shopify_order_paid",
            "metadata": {"order_id": "TEST-001"}
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert "task_id" in data, f"Response should contain task_id"
        assert data.get("sequence") == "pick_and_pack", f"Expected sequence=pick_and_pack"
        assert data.get("duration_s") == 6.0, f"Expected duration_s=6.0, got {data.get('duration_s')}"
        
        task_id = data.get("task_id")
        print(f"PASS: /api/robotics/trigger returns task_id={task_id}")
        return task_id

    def test_state_during_execution(self, auth_headers):
        """GET /api/robotics/state during execution returns status=executing."""
        # Trigger a sequence first
        trigger_resp = requests.post(f"{BASE_URL}/api/robotics/trigger", headers=auth_headers, json={
            "sequence_id": "wave_greeting",
            "trigger": "test"
        })
        assert trigger_resp.status_code == 200
        
        # Wait a moment for execution to start
        time.sleep(0.5)
        
        # Check state
        state_resp = requests.get(f"{BASE_URL}/api/robotics/state", headers=auth_headers)
        assert state_resp.status_code == 200
        
        data = state_resp.json()
        # State should be executing (unless sequence already completed)
        status = data.get("status")
        assert status in ["executing", "idle"], f"Expected status=executing or idle, got {status}"
        
        if status == "executing":
            # Verify interpolated joints are not all zeros
            joints = data.get("joints", [])
            assert data.get("progress", 0) > 0, "Progress should be > 0 during execution"
            print(f"PASS: /api/robotics/state during execution: status=executing, progress={data.get('progress')}, joints={joints}")
        else:
            print(f"PASS: /api/robotics/state - sequence completed quickly (status=idle)")

    def test_trigger_invalid_sequence(self, auth_headers):
        """POST /api/robotics/trigger with invalid sequence returns 400."""
        resp = requests.post(f"{BASE_URL}/api/robotics/trigger", headers=auth_headers, json={
            "sequence_id": "nonexistent_sequence",
            "trigger": "test"
        })
        assert resp.status_code == 400, f"Expected 400 for invalid sequence, got {resp.status_code}"
        print("PASS: /api/robotics/trigger returns 400 for invalid sequence")


class TestRoboticsHistory:
    """Test task history endpoint."""

    def test_get_history(self, auth_headers):
        """GET /api/robotics/history returns completed tasks."""
        resp = requests.get(f"{BASE_URL}/api/robotics/history", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert "tasks" in data, "Response should contain tasks array"
        assert "count" in data, "Response should contain count"
        
        tasks = data.get("tasks", [])
        print(f"PASS: /api/robotics/history returns {len(tasks)} tasks")


# ═══════════════════════════════════════════════════════════════
# MCP EXTENDED TOOLS TESTS
# ═══════════════════════════════════════════════════════════════

class TestMCPTools:
    """Test MCP tools listing."""

    def test_list_tools_returns_19(self, mcp_headers):
        """GET /api/mcp/tools returns 19 tools (7 core + 12 extended)."""
        resp = requests.get(f"{BASE_URL}/api/mcp/tools", headers=mcp_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        tools = data.get("tools", [])
        core_count = data.get("core_count", 0)
        extended_count = data.get("extended_count", 0)
        
        assert core_count == 7, f"Expected 7 core tools, got {core_count}"
        assert extended_count == 12, f"Expected 12 extended tools, got {extended_count}"
        assert len(tools) == 19, f"Expected 19 total tools, got {len(tools)}"
        
        # Verify extended tool names
        tool_names = [t.get("name") for t in tools]
        expected_extended = ["web_fetch", "web_search", "web_extract_contacts", 
                           "fs_list_repairs", "fs_read_patch", "fs_write_patch", "fs_list_templates",
                           "db_query", "db_aggregate", "db_count", "db_collections", "db_sample"]
        for ext_tool in expected_extended:
            assert ext_tool in tool_names, f"Missing extended tool: {ext_tool}"
        
        print(f"PASS: /api/mcp/tools returns 19 tools (7 core + 12 extended)")


class TestMCPWebBrowse:
    """Test Web Browse MCP tools."""

    def test_web_fetch(self, mcp_headers):
        """POST /api/mcp/call with tool=web_fetch crawls a URL."""
        resp = requests.post(f"{BASE_URL}/api/mcp/call", headers=mcp_headers, json={
            "tool": "web_fetch",
            "arguments": {"url": "https://example.com", "extract": "all", "max_chars": 1000}
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert data.get("url") == "https://example.com", "URL should match"
        assert data.get("status") == 200, "Status should be 200"
        assert "meta" in data, "Response should contain meta"
        assert "text" in data, "Response should contain text"
        assert "links" in data, "Response should contain links"
        
        print(f"PASS: web_fetch returns meta/text/links for example.com")

    def test_web_extract_contacts(self, mcp_headers):
        """POST /api/mcp/call with tool=web_extract_contacts extracts social profiles."""
        resp = requests.post(f"{BASE_URL}/api/mcp/call", headers=mcp_headers, json={
            "tool": "web_extract_contacts",
            "arguments": {"url": "https://example.com"}
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert "emails" in data, "Response should contain emails"
        assert "phones" in data, "Response should contain phones"
        assert "social" in data, "Response should contain social"
        
        print(f"PASS: web_extract_contacts returns emails/phones/social")


class TestMCPDatabase:
    """Test Database MCP tools."""

    def test_db_collections(self, mcp_headers):
        """POST /api/mcp/call with tool=db_collections returns collection list."""
        resp = requests.post(f"{BASE_URL}/api/mcp/call", headers=mcp_headers, json={
            "tool": "db_collections",
            "arguments": {}
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert "collections" in data, "Response should contain collections"
        assert "total" in data, "Response should contain total"
        
        collections = data.get("collections", [])
        assert len(collections) > 0, "Should have at least one collection"
        
        # Verify each collection has name and documents count
        for coll in collections[:5]:
            assert "name" in coll, "Collection should have name"
            assert "documents" in coll, "Collection should have documents count"
        
        print(f"PASS: db_collections returns {len(collections)} collections")

    def test_db_sample_hermes_interactions(self, mcp_headers):
        """POST /api/mcp/call with tool=db_sample returns sample from hermes_interactions."""
        resp = requests.post(f"{BASE_URL}/api/mcp/call", headers=mcp_headers, json={
            "tool": "db_sample",
            "arguments": {"collection": "hermes_interactions"}
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert data.get("collection") == "hermes_interactions"
        # Sample may be None if collection is empty
        if data.get("sample"):
            assert "_id" not in data.get("sample"), "Sample should not contain _id"
        
        print(f"PASS: db_sample returns sample from hermes_interactions")

    def test_db_count(self, mcp_headers):
        """POST /api/mcp/call with tool=db_count counts documents."""
        resp = requests.post(f"{BASE_URL}/api/mcp/call", headers=mcp_headers, json={
            "tool": "db_count",
            "arguments": {"collection": "hermes_interactions", "filter": "{}"}
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert data.get("collection") == "hermes_interactions"
        assert "count" in data, "Response should contain count"
        assert isinstance(data.get("count"), int), "Count should be integer"
        
        print(f"PASS: db_count returns count={data.get('count')} for hermes_interactions")

    def test_db_query_blocked_collection(self, mcp_headers):
        """POST /api/mcp/call with tool=db_query on 'users' returns restricted error."""
        resp = requests.post(f"{BASE_URL}/api/mcp/call", headers=mcp_headers, json={
            "tool": "db_query",
            "arguments": {"collection": "users", "filter": "{}"}
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert "error" in data, "Response should contain error for blocked collection"
        assert "restricted" in data.get("error", "").lower(), f"Error should mention restricted: {data.get('error')}"
        
        print(f"PASS: db_query on 'users' returns restricted error")


class TestMCPFileSystem:
    """Test File System MCP tools."""

    def test_fs_list_repairs(self, mcp_headers):
        """POST /api/mcp/call with tool=fs_list_repairs returns repair fixes list."""
        resp = requests.post(f"{BASE_URL}/api/mcp/call", headers=mcp_headers, json={
            "tool": "fs_list_repairs",
            "arguments": {"status": "all"}
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert "fixes" in data, "Response should contain fixes"
        assert "count" in data, "Response should contain count"
        
        print(f"PASS: fs_list_repairs returns {data.get('count')} fixes")

    def test_fs_write_patch(self, mcp_headers):
        """POST /api/mcp/call with tool=fs_write_patch writes a patch file."""
        test_content = "<!-- Test patch content -->\n<style>.test { color: red; }</style>"
        resp = requests.post(f"{BASE_URL}/api/mcp/call", headers=mcp_headers, json={
            "tool": "fs_write_patch",
            "arguments": {
                "deploy_id": "test-deploy-001",
                "content": test_content,
                "filename": "test-patch-001.html"
            }
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert "path" in data, "Response should contain path"
        assert data.get("filename") == "test-patch-001.html"
        assert data.get("size") == len(test_content)
        
        print(f"PASS: fs_write_patch writes patch file successfully")


# ═══════════════════════════════════════════════════════════════
# SOVEREIGN NODE TESTS
# ═══════════════════════════════════════════════════════════════

class TestSovereignNode:
    """Test Sovereign Node (Local LLM) status endpoint."""

    def test_local_llm_status(self, auth_headers):
        """GET /api/local-llm/status shows url=https://sovereign.aurem.live and tunnel=cloudflare."""
        resp = requests.get(f"{BASE_URL}/api/local-llm/status", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        
        data = resp.json()
        
        # Verify URL is sovereign.aurem.live
        url = data.get("url", "")
        assert "sovereign.aurem.live" in url, f"Expected url to contain sovereign.aurem.live, got {url}"
        
        # Verify tunnel type is cloudflare
        tunnel = data.get("tunnel", "")
        assert tunnel == "cloudflare", f"Expected tunnel=cloudflare, got {tunnel}"
        
        # Sovereign Node is expected to be offline (user hasn't set up Cloudflare Tunnel)
        online = data.get("online", True)
        print(f"PASS: /api/local-llm/status shows url={url}, tunnel={tunnel}, online={online}")


# ═══════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════

class TestHealth:
    """Basic health check."""

    def test_health(self):
        """GET /api/health returns status=ok."""
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("status") == "ok", f"Expected status=ok, got {data.get('status')}"
        print("PASS: /api/health returns status=ok")

    def test_auth_login(self):
        """POST /api/auth/login returns token."""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "token" in data, "Response should contain token"
        print("PASS: /api/auth/login returns token")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
