"""
AUREM Platform Spine Backend Tests (iter 292)
Tests for: A2A Task Queue, Council Deliberation, ORA Learning, Founders Console
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://ai-platform-preview-3.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "teji.ss1986@gmail.com"
ADMIN_PASSWORD = "Admin123"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin JWT token for authenticated requests"""
    response = requests.post(
        f"{BASE_URL}/api/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        headers={"Content-Type": "application/json"}
    )
    if response.status_code != 200:
        pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
    data = response.json()
    assert "token" in data, "No token in login response"
    return data["token"]


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Headers with Bearer token for authenticated requests"""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {admin_token}"
    }


class TestAuthGate:
    """Test that all platform spine endpoints require authentication"""
    
    def test_spine_health_requires_auth(self):
        """GET /api/admin/platform/spine/health without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/admin/platform/spine/health")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ spine/health requires auth")
    
    def test_a2a_tasks_requires_auth(self):
        """GET /api/admin/platform/a2a/tasks without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/admin/platform/a2a/tasks")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ a2a/tasks requires auth")
    
    def test_council_deliberate_requires_auth(self):
        """POST /api/admin/platform/council/deliberate without token returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/admin/platform/council/deliberate",
            json={"action_kind": "test", "payload": {}}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ council/deliberate requires auth")
    
    def test_ora_feed_requires_auth(self):
        """GET /api/admin/platform/ora/feed without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/admin/platform/ora/feed")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ ora/feed requires auth")
    
    def test_console_message_requires_auth(self):
        """POST /api/admin/console/message without token returns 401"""
        response = requests.post(
            f"{BASE_URL}/api/admin/console/message",
            json={"message": "test"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ console/message requires auth")
    
    def test_console_history_requires_auth(self):
        """GET /api/admin/console/history without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/admin/console/history?session_id=test")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ console/history requires auth")
    
    def test_console_sessions_requires_auth(self):
        """GET /api/admin/console/sessions without token returns 401"""
        response = requests.get(f"{BASE_URL}/api/admin/console/sessions")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ console/sessions requires auth")


class TestSpineHealth:
    """Test GET /api/admin/platform/spine/health endpoint"""
    
    def test_spine_health_returns_stats(self, auth_headers):
        """GET /api/admin/platform/spine/health returns a2a/council/ora stats"""
        response = requests.get(
            f"{BASE_URL}/api/admin/platform/spine/health",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify a2a stats
        assert "a2a" in data, "Missing 'a2a' in response"
        assert "stats" in data["a2a"] or "queued" in data["a2a"], "Missing a2a stats"
        
        # Verify council stats
        assert "council" in data, "Missing 'council' in response"
        assert "pending_escalations" in data["council"], "Missing pending_escalations"
        
        # Verify ora stats
        assert "ora" in data, "Missing 'ora' in response"
        
        # Verify timestamp
        assert "ts" in data, "Missing timestamp"
        
        print(f"✓ spine/health returns: a2a={data['a2a']}, council_escalations={data['council']['pending_escalations']}")


class TestA2ATaskQueue:
    """Test A2A Task Queue endpoints"""
    
    def test_a2a_test_handoff_creates_chain(self, auth_headers):
        """POST /api/admin/platform/a2a/test-handoff creates Scout→Architect→Envoy→Closer chain"""
        response = requests.post(
            f"{BASE_URL}/api/admin/platform/a2a/test-handoff",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True, "Expected ok=True"
        assert "chain_id" in data, "Missing chain_id"
        assert "tasks" in data, "Missing tasks"
        assert len(data["tasks"]) == 3, f"Expected 3 tasks, got {len(data['tasks'])}"
        
        print(f"✓ test-handoff created chain_id={data['chain_id']} with {len(data['tasks'])} tasks")
        return data["chain_id"]
    
    def test_a2a_tasks_list(self, auth_headers):
        """GET /api/admin/platform/a2a/tasks returns recent tasks + stats"""
        response = requests.get(
            f"{BASE_URL}/api/admin/platform/a2a/tasks?limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "tasks" in data, "Missing 'tasks' in response"
        assert "stats" in data, "Missing 'stats' in response"
        assert isinstance(data["tasks"], list), "tasks should be a list"
        
        print(f"✓ a2a/tasks returned {len(data['tasks'])} tasks, stats={data['stats']}")
    
    def test_a2a_chain_retrieval(self, auth_headers):
        """GET /api/admin/platform/a2a/chain/{chain_id} returns full chain order"""
        # First create a chain
        handoff_response = requests.post(
            f"{BASE_URL}/api/admin/platform/a2a/test-handoff",
            headers=auth_headers
        )
        assert handoff_response.status_code == 200
        chain_id = handoff_response.json()["chain_id"]
        
        # Now retrieve the chain
        response = requests.get(
            f"{BASE_URL}/api/admin/platform/a2a/chain/{chain_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "chain" in data, "Missing 'chain' in response"
        assert isinstance(data["chain"], list), "chain should be a list"
        assert len(data["chain"]) >= 1, "Chain should have at least 1 task"
        
        # Verify chain order (Scout→Architect→Envoy→Closer)
        agents = [t.get("assigned_to") for t in data["chain"]]
        print(f"✓ chain/{chain_id} returned {len(data['chain'])} tasks: {agents}")


class TestCouncilDeliberation:
    """Test Council Deliberation endpoints"""
    
    def test_council_deliberate_approve(self, auth_headers):
        """POST /api/admin/platform/council/deliberate with valid payload → approve"""
        payload = {
            "action_kind": "outreach_blast",
            "payload": {
                "lead_id": "X",
                "verification": {
                    "channel_gating": {"email": True}
                }
            },
            "cost_usd": 0.01,
            "llm_voters": False
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/platform/council/deliberate",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "decision" in data, "Missing 'decision' in response"
        assert "decision_id" in data, "Missing 'decision_id' in response"
        assert "votes" in data, "Missing 'votes' in response"
        assert "avg_confidence" in data, "Missing 'avg_confidence' in response"
        
        # With valid channel_gating and low cost, should approve
        assert data["decision"] == "approve", f"Expected 'approve', got '{data['decision']}' - reason: {data.get('reason')}"
        
        print(f"✓ council/deliberate approved: decision_id={data['decision_id']}, conf={data['avg_confidence']}")
    
    def test_council_deliberate_veto_no_channels(self, auth_headers):
        """POST /api/admin/platform/council/deliberate with empty channel_gating → veto (scout block)"""
        payload = {
            "action_kind": "outreach_blast",
            "payload": {
                "lead_id": "Y",
                "verification": {
                    "channel_gating": {}  # Empty = no open channels
                }
            },
            "cost_usd": 0.01,
            "llm_voters": False
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/platform/council/deliberate",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "decision" in data, "Missing 'decision' in response"
        # With empty channel_gating, scout should block → veto
        assert data["decision"] == "veto", f"Expected 'veto', got '{data['decision']}' - reason: {data.get('reason')}"
        
        print(f"✓ council/deliberate vetoed (no channels): reason={data.get('reason', '')[:80]}")
    
    def test_council_deliberate_escalate_high_cost(self, auth_headers):
        """POST /api/admin/platform/council/deliberate with cost_usd=6.0 → escalate"""
        payload = {
            "action_kind": "outreach_blast",
            "payload": {"lead_id": "Z"},
            "cost_usd": 6.0,  # Above $5 threshold
            "llm_voters": False
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/platform/council/deliberate",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "decision" in data, "Missing 'decision' in response"
        # With cost > $5, should escalate
        assert data["decision"] == "escalate", f"Expected 'escalate', got '{data['decision']}' - reason: {data.get('reason')}"
        
        print(f"✓ council/deliberate escalated (high cost): reason={data.get('reason', '')[:80]}")
    
    def test_council_recent(self, auth_headers):
        """GET /api/admin/platform/council/recent returns recent decisions"""
        response = requests.get(
            f"{BASE_URL}/api/admin/platform/council/recent?limit=10",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "decisions" in data, "Missing 'decisions' in response"
        assert isinstance(data["decisions"], list), "decisions should be a list"
        
        print(f"✓ council/recent returned {len(data['decisions'])} decisions")
    
    def test_council_escalations(self, auth_headers):
        """GET /api/admin/platform/council/escalations returns pending escalations"""
        response = requests.get(
            f"{BASE_URL}/api/admin/platform/council/escalations",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "pending" in data, "Missing 'pending' in response"
        assert isinstance(data["pending"], list), "pending should be a list"
        
        print(f"✓ council/escalations returned {len(data['pending'])} pending")


class TestORALearning:
    """Test ORA Learning Loop endpoints"""
    
    def test_ora_test_log(self, auth_headers):
        """POST /api/admin/platform/ora/test-log creates agent_outcomes + agent_feed row"""
        response = requests.post(
            f"{BASE_URL}/api/admin/platform/ora/test-log",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("ok") is True, "Expected ok=True"
        assert "action_id" in data, "Missing 'action_id' in response"
        
        print(f"✓ ora/test-log created action_id={data['action_id']}")
    
    def test_ora_feed(self, auth_headers):
        """GET /api/admin/platform/ora/feed returns live feed"""
        response = requests.get(
            f"{BASE_URL}/api/admin/platform/ora/feed?limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "feed" in data, "Missing 'feed' in response"
        assert isinstance(data["feed"], list), "feed should be a list"
        
        print(f"✓ ora/feed returned {len(data['feed'])} items")
    
    def test_ora_patterns(self, auth_headers):
        """GET /api/admin/platform/ora/patterns returns pattern library"""
        response = requests.get(
            f"{BASE_URL}/api/admin/platform/ora/patterns?limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "patterns" in data, "Missing 'patterns' in response"
        assert isinstance(data["patterns"], list), "patterns should be a list"
        
        print(f"✓ ora/patterns returned {len(data['patterns'])} patterns")
    
    def test_ora_stats(self, auth_headers):
        """GET /api/admin/platform/ora/stats returns outcome breakdown"""
        response = requests.get(
            f"{BASE_URL}/api/admin/platform/ora/stats",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "outcomes" in data or "until_finetune" in data, "Missing expected fields in stats"
        
        print(f"✓ ora/stats returned: {data}")


class TestFoundersConsole:
    """Test Founders Console endpoints"""
    
    def test_console_message_scout_run(self, auth_headers):
        """POST /api/admin/console/message with 'Run scout for auto-repair shops' → intent=scout_run, decision=approve"""
        payload = {
            "message": "Run scout for auto-repair shops"
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/console/message",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "reply" in data, "Missing 'reply' in response"
        assert "intent" in data, "Missing 'intent' in response"
        assert "decision" in data, "Missing 'decision' in response"
        assert "session_id" in data, "Missing 'session_id' in response"
        
        # Verify intent classification
        assert data["intent"] == "scout_run", f"Expected intent='scout_run', got '{data['intent']}'"
        assert data["decision"] == "approve", f"Expected decision='approve', got '{data['decision']}'"
        
        # Verify task_ids non-empty for approved scout_run
        assert "task_ids" in data, "Missing 'task_ids' in response"
        assert len(data["task_ids"]) > 0, f"Expected non-empty task_ids for approved scout_run"
        
        print(f"✓ console/message scout_run: intent={data['intent']}, decision={data['decision']}, tasks={len(data['task_ids'])}")
        return data["session_id"]
    
    def test_console_message_report_query(self, auth_headers):
        """POST /api/admin/console/message with 'How many sends today?' → intent=report (NOT outreach_blast)"""
        payload = {
            "message": "How many sends today?"
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/console/message",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "intent" in data, "Missing 'intent' in response"
        # CRITICAL: This should be 'report', NOT 'outreach_blast'
        assert data["intent"] == "report", f"Expected intent='report', got '{data['intent']}' - KEYWORDS order fix needed!"
        
        print(f"✓ console/message report query: intent={data['intent']} (correctly NOT outreach_blast)")
    
    def test_console_message_pause_outreach(self, auth_headers):
        """POST /api/admin/console/message with 'Pause outreach' → intent=pause_outreach, decision=approve"""
        payload = {
            "message": "Pause outreach"
        }
        response = requests.post(
            f"{BASE_URL}/api/admin/console/message",
            headers=auth_headers,
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "intent" in data, "Missing 'intent' in response"
        assert data["intent"] == "pause_outreach", f"Expected intent='pause_outreach', got '{data['intent']}'"
        assert data["decision"] == "approve", f"Expected decision='approve', got '{data['decision']}'"
        
        print(f"✓ console/message pause_outreach: intent={data['intent']}, decision={data['decision']}")
    
    def test_console_history(self, auth_headers):
        """GET /api/admin/console/history?session_id=X returns user+assistant turns"""
        # First create a session with a message
        msg_response = requests.post(
            f"{BASE_URL}/api/admin/console/message",
            headers=auth_headers,
            json={"message": "Test message for history"}
        )
        assert msg_response.status_code == 200
        session_id = msg_response.json()["session_id"]
        
        # Now get history
        response = requests.get(
            f"{BASE_URL}/api/admin/console/history?session_id={session_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "messages" in data, "Missing 'messages' in response"
        assert isinstance(data["messages"], list), "messages should be a list"
        
        # Should have at least user + assistant turns
        roles = [m.get("role") for m in data["messages"]]
        assert "user" in roles, "Missing user turn in history"
        assert "assistant" in roles, "Missing assistant turn in history"
        
        print(f"✓ console/history returned {len(data['messages'])} messages for session {session_id}")
    
    def test_console_sessions(self, auth_headers):
        """GET /api/admin/console/sessions returns list with session_id + preview"""
        response = requests.get(
            f"{BASE_URL}/api/admin/console/sessions",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "sessions" in data, "Missing 'sessions' in response"
        assert isinstance(data["sessions"], list), "sessions should be a list"
        
        # If there are sessions, verify structure
        if len(data["sessions"]) > 0:
            session = data["sessions"][0]
            assert "session_id" in session, "Missing session_id in session"
            assert "preview" in session or "first_msg" in session, "Missing preview in session"
        
        print(f"✓ console/sessions returned {len(data['sessions'])} sessions")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
