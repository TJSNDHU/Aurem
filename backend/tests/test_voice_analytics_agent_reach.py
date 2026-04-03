"""
Test Voice Analytics Dashboard and Agent-Reach Social Intelligence
Phase 8.2 Features:
- Voice Analytics endpoint with ROI metrics
- Agent-Reach zero-API social intelligence tools
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ═══════════════════════════════════════════════════════════════════════════════
# VOICE ANALYTICS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestVoiceAnalytics:
    """Voice Analytics Dashboard API tests"""
    
    def test_voice_analytics_endpoint_returns_200(self):
        """GET /api/aurem-voice/{business_id}/analytics should return 200"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/test_business/analytics")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Voice analytics endpoint returns 200")
    
    def test_voice_analytics_summary_structure(self):
        """Analytics should include summary with totalCalls, avgDuration, actionRate, vipCalls"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/test_business/analytics")
        assert response.status_code == 200
        data = response.json()
        
        assert "summary" in data, "Response missing 'summary' field"
        summary = data["summary"]
        
        # Check required summary fields
        required_fields = ["totalCalls", "avgDuration", "actionRate", "vipCalls"]
        for field in required_fields:
            assert field in summary, f"Summary missing '{field}' field"
        
        # Validate data types
        assert isinstance(summary["totalCalls"], int), "totalCalls should be int"
        assert isinstance(summary["avgDuration"], (int, float)), "avgDuration should be numeric"
        assert isinstance(summary["actionRate"], (int, float)), "actionRate should be numeric"
        assert isinstance(summary["vipCalls"], int), "vipCalls should be int"
        
        print(f"PASS: Summary structure valid - totalCalls={summary['totalCalls']}, avgDuration={summary['avgDuration']}, actionRate={summary['actionRate']}, vipCalls={summary['vipCalls']}")
    
    def test_voice_analytics_tier_breakdown(self):
        """Analytics should include tierBreakdown array with Standard/Premium/VIP/Enterprise"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/test_business/analytics")
        assert response.status_code == 200
        data = response.json()
        
        assert "tierBreakdown" in data, "Response missing 'tierBreakdown' field"
        tier_breakdown = data["tierBreakdown"]
        
        assert isinstance(tier_breakdown, list), "tierBreakdown should be a list"
        assert len(tier_breakdown) >= 4, f"Expected at least 4 tiers, got {len(tier_breakdown)}"
        
        # Check tier labels
        tier_labels = [t.get("label") for t in tier_breakdown]
        expected_tiers = ["Standard", "Premium", "VIP", "Enterprise"]
        for tier in expected_tiers:
            assert tier in tier_labels, f"Missing tier: {tier}"
        
        # Check tier structure
        for tier in tier_breakdown:
            assert "label" in tier, "Tier missing 'label'"
            assert "value" in tier, "Tier missing 'value'"
            assert "color" in tier, "Tier missing 'color'"
        
        print(f"PASS: Tier breakdown valid - {tier_labels}")
    
    def test_voice_analytics_persona_stats(self):
        """Analytics should include personaStats with avgDuration for each persona"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/test_business/analytics")
        assert response.status_code == 200
        data = response.json()
        
        assert "personaStats" in data, "Response missing 'personaStats' field"
        persona_stats = data["personaStats"]
        
        assert isinstance(persona_stats, list), "personaStats should be a list"
        assert len(persona_stats) >= 1, "Expected at least 1 persona stat"
        
        # Check persona structure
        for persona in persona_stats:
            assert "name" in persona, "Persona missing 'name'"
            assert "avgDuration" in persona, "Persona missing 'avgDuration'"
            assert "color" in persona, "Persona missing 'color'"
            assert isinstance(persona["avgDuration"], (int, float)), "avgDuration should be numeric"
        
        print(f"PASS: Persona stats valid - {len(persona_stats)} personas")
    
    def test_voice_analytics_cost_savings(self):
        """Analytics should include costSavings with totalSaved and savingsPercent"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/test_business/analytics")
        assert response.status_code == 200
        data = response.json()
        
        assert "costSavings" in data, "Response missing 'costSavings' field"
        cost_savings = data["costSavings"]
        
        # Check required cost savings fields
        required_fields = ["totalSaved", "savingsPercent", "aiCostPerCall", "humanCostPerCall"]
        for field in required_fields:
            assert field in cost_savings, f"costSavings missing '{field}' field"
        
        # Validate values
        assert cost_savings["totalSaved"] >= 0, "totalSaved should be non-negative"
        assert cost_savings["savingsPercent"] >= 0, "savingsPercent should be non-negative"
        assert cost_savings["aiCostPerCall"] == 0.45, f"Expected AI cost $0.45, got {cost_savings['aiCostPerCall']}"
        assert cost_savings["humanCostPerCall"] == 15.00, f"Expected human cost $15.00, got {cost_savings['humanCostPerCall']}"
        
        print(f"PASS: Cost savings valid - totalSaved=${cost_savings['totalSaved']}, savingsPercent={cost_savings['savingsPercent']}%")
    
    def test_voice_analytics_time_range_parameter(self):
        """Analytics should accept time range parameter (24h, 7d, 30d)"""
        for time_range in ["24h", "7d", "30d"]:
            response = requests.get(f"{BASE_URL}/api/aurem-voice/test_business/analytics?range={time_range}")
            assert response.status_code == 200, f"Failed for range={time_range}"
            data = response.json()
            assert data.get("timeRange") == time_range, f"Expected timeRange={time_range}, got {data.get('timeRange')}"
        
        print("PASS: Time range parameter works for 24h, 7d, 30d")
    
    def test_voice_analytics_daily_volume(self):
        """Analytics should include dailyVolume array for sparkline chart"""
        response = requests.get(f"{BASE_URL}/api/aurem-voice/test_business/analytics")
        assert response.status_code == 200
        data = response.json()
        
        assert "dailyVolume" in data, "Response missing 'dailyVolume' field"
        daily_volume = data["dailyVolume"]
        
        assert isinstance(daily_volume, list), "dailyVolume should be a list"
        assert len(daily_volume) >= 7, f"Expected at least 7 days of data, got {len(daily_volume)}"
        
        # All values should be numeric
        for val in daily_volume:
            assert isinstance(val, (int, float)), "dailyVolume values should be numeric"
        
        print(f"PASS: Daily volume valid - {len(daily_volume)} data points")


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT-REACH TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAgentReachHealth:
    """Agent-Reach health and configuration tests"""
    
    def test_reach_health_endpoint(self):
        """GET /api/reach/health should return healthy status"""
        response = requests.get(f"{BASE_URL}/api/reach/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "healthy", f"Expected status=healthy, got {data.get('status')}"
        assert data.get("service") == "aurem-agent-reach", f"Expected service=aurem-agent-reach"
        
        print("PASS: Agent-Reach health endpoint returns healthy")
    
    def test_reach_health_zero_api_philosophy(self):
        """Health endpoint should include zero-api philosophy"""
        response = requests.get(f"{BASE_URL}/api/reach/health")
        assert response.status_code == 200
        data = response.json()
        
        assert "philosophy" in data, "Response missing 'philosophy' field"
        assert data["philosophy"] == "zero-api-social-intelligence", f"Expected zero-api-social-intelligence, got {data['philosophy']}"
        
        print("PASS: Zero-API philosophy confirmed")
    
    def test_reach_health_tools_status(self):
        """Health endpoint should show tool availability status"""
        response = requests.get(f"{BASE_URL}/api/reach/health")
        assert response.status_code == 200
        data = response.json()
        
        assert "tools" in data, "Response missing 'tools' field"
        tools = data["tools"]
        
        expected_tools = ["twitter_search", "reddit_search", "youtube_transcript", "web_reader"]
        for tool in expected_tools:
            assert tool in tools, f"Missing tool: {tool}"
            assert "status" in tools[tool], f"Tool {tool} missing 'status'"
        
        print(f"PASS: All 4 tools present in health check")


class TestAgentReachTools:
    """Agent-Reach tools endpoint tests"""
    
    def test_reach_tools_endpoint(self):
        """GET /api/reach/tools should return 4 tools"""
        response = requests.get(f"{BASE_URL}/api/reach/tools")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "tools" in data, "Response missing 'tools' field"
        assert "total" in data, "Response missing 'total' field"
        
        tools = data["tools"]
        assert len(tools) == 4, f"Expected 4 tools, got {len(tools)}"
        
        print(f"PASS: Tools endpoint returns {len(tools)} tools")
    
    def test_reach_tools_structure(self):
        """Each tool should have name, description, available, cost, parameters"""
        response = requests.get(f"{BASE_URL}/api/reach/tools")
        assert response.status_code == 200
        data = response.json()
        
        for tool in data["tools"]:
            assert "name" in tool, "Tool missing 'name'"
            assert "description" in tool, "Tool missing 'description'"
            assert "available" in tool, "Tool missing 'available'"
            assert "cost" in tool, "Tool missing 'cost'"
            assert "parameters" in tool, "Tool missing 'parameters'"
            
            # Verify zero cost
            assert "$0" in tool["cost"], f"Expected $0 cost, got {tool['cost']}"
        
        print("PASS: All tools have correct structure with $0 cost")
    
    def test_reach_tools_names(self):
        """Tools should include twitter, reddit, youtube, web"""
        response = requests.get(f"{BASE_URL}/api/reach/tools")
        assert response.status_code == 200
        data = response.json()
        
        tool_names = [t["name"] for t in data["tools"]]
        expected_names = ["search_twitter", "search_reddit", "get_youtube_transcript", "read_webpage"]
        
        for name in expected_names:
            assert name in tool_names, f"Missing tool: {name}"
        
        print(f"PASS: All expected tools present: {tool_names}")


class TestAgentReachTwitter:
    """Twitter search endpoint tests"""
    
    def test_twitter_search_endpoint(self):
        """POST /api/reach/twitter should search and return tweets"""
        response = requests.post(
            f"{BASE_URL}/api/reach/twitter",
            json={"query": "PDRN skincare", "limit": 5}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data.get('success')}"
        assert data.get("tool") == "twitter_search", f"Expected tool=twitter_search"
        
        print("PASS: Twitter search endpoint works")
    
    def test_twitter_search_zero_cost(self):
        """Twitter search should have $0 cost"""
        response = requests.post(
            f"{BASE_URL}/api/reach/twitter",
            json={"query": "test query"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("cost") == 0.0, f"Expected cost=0.0, got {data.get('cost')}"
        
        print("PASS: Twitter search has $0 cost")
    
    def test_twitter_search_returns_data(self):
        """Twitter search should return tweets data"""
        response = requests.post(
            f"{BASE_URL}/api/reach/twitter",
            json={"query": "skincare reviews", "limit": 3}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data, "Response missing 'data' field"
        assert "tweets" in data["data"], "Data missing 'tweets' field"
        assert "count" in data["data"], "Data missing 'count' field"
        
        print(f"PASS: Twitter search returns {data['data']['count']} tweets")


class TestAgentReachReddit:
    """Reddit search endpoint tests"""
    
    def test_reddit_search_endpoint(self):
        """POST /api/reach/reddit should search and return threads"""
        response = requests.post(
            f"{BASE_URL}/api/reach/reddit",
            json={"query": "best mechanic Toronto", "limit": 5}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True"
        assert data.get("tool") == "reddit_search", f"Expected tool=reddit_search"
        
        print("PASS: Reddit search endpoint works")
    
    def test_reddit_search_zero_cost(self):
        """Reddit search should have $0 cost"""
        response = requests.post(
            f"{BASE_URL}/api/reach/reddit",
            json={"query": "test query"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("cost") == 0.0, f"Expected cost=0.0, got {data.get('cost')}"
        
        print("PASS: Reddit search has $0 cost")
    
    def test_reddit_search_returns_threads(self):
        """Reddit search should return threads data"""
        response = requests.post(
            f"{BASE_URL}/api/reach/reddit",
            json={"query": "skincare routine", "limit": 3}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data, "Response missing 'data' field"
        assert "threads" in data["data"], "Data missing 'threads' field"
        assert "count" in data["data"], "Data missing 'count' field"
        
        print(f"PASS: Reddit search returns {data['data']['count']} threads")


class TestAgentReachWeb:
    """Web reader endpoint tests"""
    
    def test_web_reader_endpoint(self):
        """POST /api/reach/web should read webpage and return markdown"""
        response = requests.post(
            f"{BASE_URL}/api/reach/web",
            json={"url": "https://example.com"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True"
        assert data.get("tool") == "web_reader", f"Expected tool=web_reader"
        
        print("PASS: Web reader endpoint works")
    
    def test_web_reader_zero_cost(self):
        """Web reader should have $0 cost"""
        response = requests.post(
            f"{BASE_URL}/api/reach/web",
            json={"url": "https://example.com"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("cost") == 0.0, f"Expected cost=0.0, got {data.get('cost')}"
        
        print("PASS: Web reader has $0 cost")
    
    def test_web_reader_returns_content(self):
        """Web reader should return markdown content"""
        response = requests.post(
            f"{BASE_URL}/api/reach/web",
            json={"url": "https://example.com"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data, "Response missing 'data' field"
        assert "content" in data["data"], "Data missing 'content' field"
        assert "format" in data["data"], "Data missing 'format' field"
        assert data["data"]["format"] == "markdown", f"Expected format=markdown"
        
        print("PASS: Web reader returns markdown content")


class TestAgentReachSkillDefinitions:
    """Skill definitions endpoint tests"""
    
    def test_skill_definitions_endpoint(self):
        """GET /api/reach/skill-definitions should return SKILL.md compatible format"""
        response = requests.get(f"{BASE_URL}/api/reach/skill-definitions")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "skill_md" in data, "Response missing 'skill_md' field"
        assert "tool_definitions" in data, "Response missing 'tool_definitions' field"
        assert "format" in data, "Response missing 'format' field"
        
        print("PASS: Skill definitions endpoint works")
    
    def test_skill_definitions_format(self):
        """Skill definitions should be in openai_function_calling format"""
        response = requests.get(f"{BASE_URL}/api/reach/skill-definitions")
        assert response.status_code == 200
        data = response.json()
        
        assert data["format"] == "openai_function_calling", f"Expected openai_function_calling format"
        
        # Check tool definitions structure
        tool_defs = data["tool_definitions"]
        assert len(tool_defs) == 4, f"Expected 4 tool definitions, got {len(tool_defs)}"
        
        for tool_def in tool_defs:
            assert "type" in tool_def, "Tool definition missing 'type'"
            assert "function" in tool_def, "Tool definition missing 'function'"
            assert tool_def["type"] == "function", "Tool type should be 'function'"
        
        print("PASS: Skill definitions in correct format")
    
    def test_skill_md_content(self):
        """Skill MD should contain all tool commands"""
        response = requests.get(f"{BASE_URL}/api/reach/skill-definitions")
        assert response.status_code == 200
        data = response.json()
        
        skill_md = data["skill_md"]
        
        # Check for tool commands in markdown
        expected_commands = ["search_twitter", "search_reddit", "get_youtube_transcript", "read_webpage"]
        for cmd in expected_commands:
            assert cmd in skill_md, f"Skill MD missing command: {cmd}"
        
        # Check for zero cost mention
        assert "$0" in skill_md, "Skill MD should mention $0 cost"
        
        print("PASS: Skill MD contains all tool commands")


# ═══════════════════════════════════════════════════════════════════════════════
# RUN TESTS
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
