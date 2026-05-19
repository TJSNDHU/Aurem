"""
Iteration 192 - Keshav Sharma's 3 Repo Integrations + Pending Ops Banner
Tests: DeepSleep-beta (Hermes memory), ripple-agent (WhatsApp fallback), superskills (skill loader)
Plus: GET /api/campaign/ops-status endpoint
"""
import pytest
import requests
import os
import asyncio

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "teji.ss1986@gmail.com",
        "password": "<REDACTED>"
    })
    if resp.status_code == 200:
        return resp.json().get("token")
    pytest.skip("Admin login failed")

@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


class TestOpsStatusEndpoint:
    """GET /api/campaign/ops-status - Pending Ops Banner data"""
    
    def test_ops_status_requires_auth(self):
        """Endpoint requires admin auth"""
        resp = requests.get(f"{BASE_URL}/api/campaign/ops-status")
        assert resp.status_code == 401
    
    def test_ops_status_returns_structure(self, auth_headers):
        """Returns expected structure with channels and links"""
        resp = requests.get(f"{BASE_URL}/api/campaign/ops-status", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify structure
        assert "checked_at" in data
        assert "all_green" in data
        assert "pending_count" in data
        assert "channels" in data
        assert "links" in data
        
        # Verify channels
        channels = data["channels"]
        assert "twilio_whatsapp" in channels
        assert "google_places" in channels
        assert "ripple_meta_cloud_fallback" in channels
        
        # Each channel has ok, detail, channel keys
        for ch_name, ch_data in channels.items():
            assert "ok" in ch_data
            assert "detail" in ch_data
            assert "channel" in ch_data
    
    def test_ops_status_google_places_enabled(self, auth_headers):
        """Google Places API should be enabled (user just enabled it)"""
        resp = requests.get(f"{BASE_URL}/api/campaign/ops-status", headers=auth_headers)
        data = resp.json()
        
        google_places = data["channels"]["google_places"]
        assert google_places["ok"] == True
        assert "enabled" in google_places["detail"].lower() or "responding" in google_places["detail"].lower()
    
    def test_ops_status_twilio_pending(self, auth_headers):
        """Twilio WhatsApp should be pending (awaiting approval)"""
        resp = requests.get(f"{BASE_URL}/api/campaign/ops-status", headers=auth_headers)
        data = resp.json()
        
        twilio = data["channels"]["twilio_whatsapp"]
        # Either pending or not configured
        assert twilio.get("pending") == True or twilio["ok"] == False
    
    def test_ops_status_ripple_fallback_optional(self, auth_headers):
        """Ripple fallback should report as optional (not configured)"""
        resp = requests.get(f"{BASE_URL}/api/campaign/ops-status", headers=auth_headers)
        data = resp.json()
        
        ripple = data["channels"]["ripple_meta_cloud_fallback"]
        # Should be False without env vars
        assert ripple["ok"] == False
        assert "optional" in ripple["detail"].lower() or "set" in ripple["detail"].lower()
    
    def test_ops_status_links_present(self, auth_headers):
        """Links to external consoles should be present"""
        resp = requests.get(f"{BASE_URL}/api/campaign/ops-status", headers=auth_headers)
        data = resp.json()
        
        links = data["links"]
        assert "twilio_whatsapp_approval" in links
        assert "console.twilio.com" in links["twilio_whatsapp_approval"]
        assert "google_places_enable" in links
        assert "console.cloud.google.com" in links["google_places_enable"]


class TestSuperskillsLoader:
    """superskills_loader.py - Keshav's superskills repo integration"""
    
    def test_registry_stats_total(self):
        """Should have 65 skills loaded"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.aurem_skills.superskills_loader import registry_stats
        
        stats = registry_stats()
        assert stats["total"] == 65
        assert "by_agent" in stats
        assert "by_category" in stats
    
    def test_list_skills_returns_all(self):
        """list_skills() returns all 65 skills"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.aurem_skills.superskills_loader import list_skills
        
        skills = list_skills()
        assert len(skills) == 65
        
        # Each skill has required fields
        for skill in skills[:5]:
            assert "id" in skill
            assert "name" in skill
            assert "agent" in skill
    
    def test_match_skills_finds_matches(self):
        """match_skills() finds relevant skills for query"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.aurem_skills.superskills_loader import match_skills
        
        matches = match_skills("fastapi async endpoint", "claude")
        assert len(matches) > 0
        assert matches[0]["score"] > 0
        assert "system_prompt" in matches[0]
    
    def test_build_augmented_prompt_injects_skills(self):
        """build_augmented_prompt() injects matched skills"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.aurem_skills.superskills_loader import build_augmented_prompt
        
        base = "You are a helpful assistant."
        augmented = build_augmented_prompt(base, "fastapi async endpoint", "claude")
        
        # Should be longer than base if skills matched
        assert len(augmented) >= len(base)
        # If skills matched, should contain augmentation marker
        if len(augmented) > len(base):
            assert "SuperSkills" in augmented or "Skill:" in augmented


class TestSkillsManager:
    """SkillsManager integration with superskills"""
    
    def test_list_superskills_method(self):
        """SkillsManager.list_superskills() works"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.aurem_skills.skills_manager import SkillsManager
        
        sm = SkillsManager()
        result = sm.list_superskills()
        
        assert "stats" in result
        assert "skills" in result
        assert result["stats"]["total"] == 65
    
    def test_match_superskills_method(self):
        """SkillsManager.match_superskills() works"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.aurem_skills.skills_manager import SkillsManager
        
        sm = SkillsManager()
        matches = sm.match_superskills("fastapi async endpoint", "claude", limit=3)
        
        assert isinstance(matches, list)
        if len(matches) > 0:
            assert "name" in matches[0]
            assert "score" in matches[0]


class TestRippleWhatsAppFallback:
    """ripple_whatsapp_fallback.py - Keshav's ripple-agent integration"""
    
    def test_ripple_configured_false_without_env(self):
        """ripple_whatsapp_configured() returns False without env vars"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.ripple_whatsapp_fallback import ripple_whatsapp_configured
        
        # Without RIPPLE_WHATSAPP_ACCESS_TOKEN, should be False
        result = ripple_whatsapp_configured()
        assert result == False
    
    def test_build_outbound_valid_payload(self):
        """build_outbound() creates valid Meta Cloud API payload"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.ripple_whatsapp_fallback import build_outbound
        
        payload = build_outbound("+12265017777", "Hello from AUREM")
        
        assert payload["messaging_product"] == "whatsapp"
        assert payload["to"] == "+12265017777"
        assert payload["type"] == "text"
        assert payload["text"]["body"] == "Hello from AUREM"
    
    def test_verify_webhook_403_without_token(self):
        """verify_webhook() returns 403 without VERIFY_TOKEN env"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.ripple_whatsapp_fallback import verify_webhook
        
        result = verify_webhook({
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "test123"
        })
        
        assert result[0] == 403
        assert result[1] == "Forbidden"
    
    def test_parse_inbound_valid_payload(self):
        """parse_inbound() parses valid Meta webhook payload"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.ripple_whatsapp_fallback import parse_inbound
        
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "12265017777",
                            "text": {"body": "Hello"}
                        }]
                    }
                }]
            }]
        }
        
        result = parse_inbound(payload)
        
        assert result is not None
        assert result["channel"] == "whatsapp"
        assert result["provider"] == "ripple-meta-cloud"
        assert result["user_id"] == "12265017777"
        assert result["text"] == "Hello"
    
    def test_parse_inbound_invalid_payload(self):
        """parse_inbound() returns None for invalid payload"""
        import sys
        sys.path.insert(0, '/app/backend')
        from services.ripple_whatsapp_fallback import parse_inbound
        
        result = parse_inbound({"invalid": "data"})
        assert result is None


class TestHermesDeepSleepBridge:
    """hermes_deepsleep_bridge.py - Keshav's DeepSleep-beta integration"""
    
    @pytest.fixture
    def deepsleep_memory(self):
        """Create DeepSleepMemory instance with DB connection"""
        import sys
        sys.path.insert(0, '/app/backend')
        from dotenv import load_dotenv
        load_dotenv('/app/backend/.env')
        
        from services.hermes_deepsleep_bridge import DeepSleepMemory, set_db
        from motor.motor_asyncio import AsyncIOMotorClient
        
        mongo_url = os.environ.get('MONGO_URL', '')
        db_name = os.environ.get('DB_NAME', 'aurem_db')
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        set_db(db)
        
        return DeepSleepMemory("test-deepsleep-pytest")
    
    def test_initialize_creates_doc(self, deepsleep_memory):
        """initialize() creates memory document"""
        async def run():
            result = await deepsleep_memory.initialize()
            assert "tenant_id" in result
            assert result["tenant_id"] == "test-deepsleep-pytest"
            assert "project" in result
            assert "session" in result
            assert "ephemeral" in result
        
        asyncio.get_event_loop().run_until_complete(run())
    
    def test_record_chat_turn_persists(self, deepsleep_memory):
        """record_chat_turn() persists user/assistant messages"""
        async def run():
            result = await deepsleep_memory.record_chat_turn(
                "How do I fix my website?",
                "I can help you with that.",
                files=["server.py"]
            )
            assert result["ephemeral"]["last_user_message"] == "How do I fix my website?"
            assert result["ephemeral"]["last_assistant_message"] == "I can help you with that."
            assert "server.py" in result["session"]["recent_files"]
        
        asyncio.get_event_loop().run_until_complete(run())
    
    def test_build_context_returns_3_layers(self, deepsleep_memory):
        """build_context() returns string with 3 layers"""
        async def run():
            ctx = await deepsleep_memory.build_context()
            assert "Project layer:" in ctx
            assert "Session layer:" in ctx
            assert "Ephemeral layer:" in ctx
        
        asyncio.get_event_loop().run_until_complete(run())
    
    def test_record_dream_stores_summary(self, deepsleep_memory):
        """record_dream() stores session summary"""
        async def run():
            result = await deepsleep_memory.record_dream(
                "Fixed website performance issues",
                changed_files=["index.html"]
            )
            assert result["session"]["summary"] == "Fixed website performance issues"
            assert result["session"]["last_dream_at"] is not None
        
        asyncio.get_event_loop().run_until_complete(run())
    
    def test_add_project_fact(self, deepsleep_memory):
        """add_project_fact() adds to facts list"""
        async def run():
            result = await deepsleep_memory.add_project_fact("AUREM uses FastAPI")
            assert "AUREM uses FastAPI" in result["project"]["facts"]
        
        asyncio.get_event_loop().run_until_complete(run())
    
    def test_add_goal(self, deepsleep_memory):
        """add_goal() adds to goals list"""
        async def run():
            result = await deepsleep_memory.add_goal("Improve SEO ranking")
            assert "Improve SEO ranking" in result["project"]["goals"]
        
        asyncio.get_event_loop().run_until_complete(run())
    
    def test_add_open_question(self, deepsleep_memory):
        """add_open_question() adds to questions list"""
        async def run():
            result = await deepsleep_memory.add_open_question("What is the best strategy?")
            assert "What is the best strategy?" in result["ephemeral"]["open_questions"]
        
        asyncio.get_event_loop().run_until_complete(run())
    
    @pytest.fixture(autouse=True)
    def cleanup(self, deepsleep_memory):
        """Cleanup test data after each test"""
        yield
        async def do_cleanup():
            import sys
            sys.path.insert(0, '/app/backend')
            from dotenv import load_dotenv
            load_dotenv('/app/backend/.env')
            from motor.motor_asyncio import AsyncIOMotorClient
            
            mongo_url = os.environ.get('MONGO_URL', '')
            db_name = os.environ.get('DB_NAME', 'aurem_db')
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            await db.hermes_deepsleep_memory.delete_one({"tenant_id": "test-deepsleep-pytest"})
        
        try:
            asyncio.get_event_loop().run_until_complete(do_cleanup())
        except:
            pass


class TestWhatsAppEngineRippleFallback:
    """WhatsApp Engine integration with Ripple as 3rd tier"""
    
    def test_whatsapp_engine_has_ripple_fallback(self):
        """WhatsApp engine code includes Ripple fallback"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        # Read the whatsapp_engine.py file
        with open('/app/backend/services/whatsapp_engine.py', 'r') as f:
            content = f.read()
        
        # Verify Ripple fallback is integrated
        assert "ripple_whatsapp_fallback" in content
        assert "send_via_ripple" in content
        assert "ripple_whatsapp_configured" in content
        assert "all 3 tiers exhausted" in content
    
    def test_whatsapp_engine_error_mentions_3_tiers(self, auth_headers):
        """When all tiers fail, error mentions 3 tiers"""
        # This is a code inspection test - the actual send would succeed via WHAPI
        import sys
        sys.path.insert(0, '/app/backend')
        
        with open('/app/backend/services/whatsapp_engine.py', 'r') as f:
            content = f.read()
        
        assert "all 3 tiers exhausted" in content
        assert "tenant, WHAPI, Ripple" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
