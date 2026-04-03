#!/usr/bin/env python3
"""
AUREM Platform Backend API Testing
Tests all AUREM-specific endpoints with admin credentials
"""

import requests
import sys
import json
from datetime import datetime

class AuremAPITester:
    def __init__(self, base_url="https://live-support-3.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        # Using credentials from review request
        self.admin_email = "teji.ss1986@gmail.com"
        self.admin_password = "Admin123"

    def log(self, message):
        """Log test messages with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if headers:
            test_headers.update(headers)
        
        if self.token and 'Authorization' not in test_headers:
            test_headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        self.log(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ PASSED - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict) and len(str(response_data)) < 500:
                        self.log(f"   Response: {response_data}")
                except:
                    self.log(f"   Response: {response.text[:200]}...")
            else:
                self.log(f"❌ FAILED - Expected {expected_status}, got {response.status_code}")
                self.log(f"   Response: {response.text[:300]}")

            return success, response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text

        except requests.exceptions.Timeout:
            self.log(f"❌ FAILED - Request timeout")
            return False, {}
        except requests.exceptions.ConnectionError:
            self.log(f"❌ FAILED - Connection error")
            return False, {}
        except Exception as e:
            self.log(f"❌ FAILED - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test basic health endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET",
            "api/health",
            200
        )
        return success

    def test_aurem_login(self):
        """Test AUREM login with admin credentials"""
        success, response = self.run_test(
            "AUREM Login",
            "POST",
            "api/aurem/auth/login",
            200,
            data={
                "email": self.admin_email,
                "password": self.admin_password
            }
        )
        
        if success and isinstance(response, dict) and 'token' in response:
            self.token = response['token']
            self.log(f"   ✅ Token obtained: {self.token[:30]}...")
            self.log(f"   ✅ User: {response.get('full_name', 'Unknown')}")
            self.log(f"   ✅ Tier: {response.get('tier', 'Unknown')}")
            return True
        else:
            self.log(f"   ❌ No token in response: {response}")
            return False

    def test_aurem_profile(self):
        """Test getting AUREM user profile"""
        if not self.token:
            self.log("❌ Skipping profile test - no token")
            return False
            
        success, response = self.run_test(
            "AUREM User Profile",
            "GET",
            "api/aurem/auth/me",
            200
        )
        
        if success and isinstance(response, dict):
            self.log(f"   ✅ Profile loaded for: {response.get('full_name', 'Unknown')}")
            self.log(f"   ✅ Company: {response.get('company_name', 'Unknown')}")
            self.log(f"   ✅ Tier: {response.get('tier', 'Unknown')}")
            return True
        return success

    def test_aurem_chat(self):
        """Test AUREM AI chat functionality"""
        if not self.token:
            self.log("❌ Skipping chat test - no token")
            return False
            
        success, response = self.run_test(
            "AUREM AI Chat",
            "POST",
            "api/aurem/chat",
            200,
            data={
                "message": "Hello AUREM, tell me about your capabilities",
                "session_id": "test-session-123"
            }
        )
        
        if success and isinstance(response, dict):
            self.log(f"   ✅ Chat response received: {response.get('response', '')[:100]}...")
            self.log(f"   ✅ Session ID: {response.get('session_id', 'Unknown')}")
            if 'intent' in response:
                self.log(f"   ✅ Intent detected: {response['intent']}")
            return True
        return success

    def test_aurem_metrics(self):
        """Test AUREM platform metrics"""
        if not self.token:
            self.log("❌ Skipping metrics test - no token")
            return False
            
        success, response = self.run_test(
            "AUREM Platform Metrics",
            "GET",
            "api/aurem/metrics",
            200
        )
        
        if success and isinstance(response, dict):
            self.log(f"   ✅ Queries today: {response.get('queries_today', 'Unknown')}")
            self.log(f"   ✅ Uptime: {response.get('uptime', 'Unknown')}%")
            self.log(f"   ✅ Avg response time: {response.get('avg_response_time', 'Unknown')}s")
            self.log(f"   ✅ Active brands: {response.get('active_brands', 'Unknown')}")
            return True
        return success

    def test_aurem_agents_status(self):
        """Test AUREM agent swarm status"""
        if not self.token:
            self.log("❌ Skipping agents test - no token")
            return False
            
        success, response = self.run_test(
            "AUREM Agent Swarm Status",
            "GET",
            "api/aurem/agents/status",
            200
        )
        
        if success and isinstance(response, dict) and 'agents' in response:
            agents = response['agents']
            self.log(f"   ✅ Found {len(agents)} agents")
            for agent in agents:
                self.log(f"   ✅ {agent.get('name', 'Unknown')}: {agent.get('status', 'Unknown')}")
            return True
        return success

    def test_aurem_chat_history(self):
        """Test AUREM chat history"""
        if not self.token:
            self.log("❌ Skipping chat history test - no token")
            return False
            
        success, response = self.run_test(
            "AUREM Chat History",
            "GET",
            "api/aurem/chat/history?limit=5",
            200
        )
        
        if success and isinstance(response, dict):
            messages = response.get('messages', [])
            self.log(f"   ✅ Found {len(messages)} chat messages")
            return True
        return success

    def test_aurem_automations(self):
        """Test AUREM automations list"""
        if not self.token:
            self.log("❌ Skipping automations test - no token")
            return False
            
        success, response = self.run_test(
            "AUREM Automations List",
            "GET",
            "api/aurem/automations",
            200
        )
        
        if success and isinstance(response, dict):
            automations = response.get('automations', [])
            self.log(f"   ✅ Found {len(automations)} automations")
            return True
        return success

    def test_aurem_activity_feed(self):
        """Test AUREM activity feed"""
        if not self.token:
            self.log("❌ Skipping activity feed test - no token")
            return False
            
        success, response = self.run_test(
            "AUREM Activity Feed",
            "GET",
            "api/aurem/activity/feed?limit=5",
            200
        )
        
        if success and isinstance(response, dict):
            activities = response.get('activities', [])
            self.log(f"   ✅ Found {len(activities)} activities")
            for activity in activities[:3]:  # Show first 3
                self.log(f"   ✅ {activity.get('action', 'Unknown action')} - {activity.get('time', 'Unknown time')}")
            return True
        return success

    def test_aurem_voice_config(self):
        """Test AUREM voice configuration"""
        if not self.token:
            self.log("❌ Skipping voice config test - no token")
            return False
            
        success, response = self.run_test(
            "AUREM Voice Config",
            "GET",
            "api/aurem/voice/config",
            200
        )
        
        if success and isinstance(response, dict):
            self.log(f"   ✅ Voice config loaded: {list(response.keys())}")
            return True
        return success

    def test_invalid_endpoints(self):
        """Test some invalid endpoints to ensure proper error handling"""
        self.log("\n🔍 Testing error handling...")
        
        # Test 404
        success, _ = self.run_test(
            "404 Error Handling",
            "GET",
            "api/aurem/nonexistent",
            404
        )
        
        # Test unauthorized access
        old_token = self.token
        self.token = None
        success2, _ = self.run_test(
            "Unauthorized Access",
            "GET",
            "api/aurem/auth/me",
            401
        )
        self.token = old_token
        
        return success and success2

def main():
    """Run all AUREM platform tests"""
    print("🚀 AUREM Platform Backend API Testing")
    print("=" * 50)
    
    tester = AuremAPITester()
    
    # AUREM-specific API tests
    tests = [
        ("Health Check", tester.test_health_check),
        ("AUREM Login", tester.test_aurem_login),
        ("AUREM Profile", tester.test_aurem_profile),
        ("AUREM AI Chat", tester.test_aurem_chat),
        ("AUREM Metrics", tester.test_aurem_metrics),
        ("AUREM Agent Status", tester.test_aurem_agents_status),
        ("AUREM Chat History", tester.test_aurem_chat_history),
        ("AUREM Automations", tester.test_aurem_automations),
        ("AUREM Activity Feed", tester.test_aurem_activity_feed),
        ("AUREM Voice Config", tester.test_aurem_voice_config),
        ("Error Handling", tester.test_invalid_endpoints),
    ]
    
    print(f"\n🧪 Running {len(tests)} test suites...\n")
    
    for test_name, test_func in tests:
        try:
            test_func()
        except Exception as e:
            tester.log(f"❌ {test_name} failed with exception: {e}")
        print()  # Add spacing between tests
    
    # Final results
    print("=" * 50)
    print(f"📊 FINAL RESULTS:")
    print(f"   Tests Run: {tester.tests_run}")
    print(f"   Tests Passed: {tester.tests_passed}")
    print(f"   Success Rate: {(tester.tests_passed/tester.tests_run*100):.1f}%")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())