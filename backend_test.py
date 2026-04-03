#!/usr/bin/env python3
"""
AUREM Platform Backend API Testing
Tests all platform endpoints with admin credentials
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
        self.admin_email = "admin@aurem.live"
        self.admin_password = "AuremAdmin2024!"

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

    def test_admin_login(self):
        """Test admin login with AUREM credentials"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "api/platform/auth/login",
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

    def test_user_profile(self):
        """Test getting user profile with token"""
        if not self.token:
            self.log("❌ Skipping profile test - no token")
            return False
            
        success, response = self.run_test(
            "User Profile (/me)",
            "GET",
            "api/platform/me",
            200
        )
        
        if success and isinstance(response, dict):
            self.log(f"   ✅ Profile loaded for: {response.get('full_name', 'Unknown')}")
            self.log(f"   ✅ Company: {response.get('company_name', 'Unknown')}")
            self.log(f"   ✅ Tier: {response.get('tier', 'Unknown')}")
            return True
        return success

    def test_platform_tiers(self):
        """Test getting platform tiers (public endpoint)"""
        success, response = self.run_test(
            "Platform Tiers",
            "GET",
            "api/platform/tiers",
            200
        )
        
        if success and isinstance(response, dict) and 'tiers' in response:
            tiers = response['tiers']
            self.log(f"   ✅ Found {len(tiers)} tiers: {list(tiers.keys())}")
            return True
        return success

    def test_crew_templates(self):
        """Test getting crew templates (public endpoint)"""
        success, response = self.run_test(
            "Crew Templates",
            "GET",
            "api/platform/templates",
            200
        )
        
        if success and isinstance(response, dict) and 'templates' in response:
            templates = response['templates']
            self.log(f"   ✅ Found {len(templates)} templates: {list(templates.keys())[:3]}...")
            return True
        return success

    def test_tools_status(self):
        """Test getting tools status (authenticated)"""
        if not self.token:
            self.log("❌ Skipping tools status test - no token")
            return False
            
        success, response = self.run_test(
            "Tools Status",
            "GET",
            "api/platform/tools/status",
            200
        )
        
        if success and isinstance(response, dict) and 'tools' in response:
            tools = response['tools']
            self.log(f"   ✅ Found {len(tools)} tools: {list(tools.keys())}")
            return True
        return success

    def test_executions_history(self):
        """Test getting execution history (authenticated)"""
        if not self.token:
            self.log("❌ Skipping executions test - no token")
            return False
            
        success, response = self.run_test(
            "Execution History",
            "GET",
            "api/platform/crews/executions?limit=5",
            200
        )
        
        if success and isinstance(response, dict) and 'executions' in response:
            executions = response['executions']
            self.log(f"   ✅ Found {len(executions)} executions")
            return True
        return success

    def test_analytics(self):
        """Test getting analytics (authenticated)"""
        if not self.token:
            self.log("❌ Skipping analytics test - no token")
            return False
            
        success, response = self.run_test(
            "Analytics",
            "GET",
            "api/platform/analytics?days=7",
            200
        )
        
        if success and isinstance(response, dict):
            self.log(f"   ✅ Analytics loaded for {response.get('period_days', 0)} days")
            return True
        return success

    def test_invalid_endpoints(self):
        """Test some invalid endpoints to ensure proper error handling"""
        self.log("\n🔍 Testing error handling...")
        
        # Test 404
        success, _ = self.run_test(
            "404 Error Handling",
            "GET",
            "api/platform/nonexistent",
            404
        )
        
        # Test unauthorized access
        old_token = self.token
        self.token = None
        success2, _ = self.run_test(
            "Unauthorized Access",
            "GET",
            "api/platform/me",
            401
        )
        self.token = old_token
        
        return success and success2

def main():
    """Run all AUREM platform tests"""
    print("🚀 AUREM Platform Backend API Testing")
    print("=" * 50)
    
    tester = AuremAPITester()
    
    # Core API tests
    tests = [
        ("Health Check", tester.test_health_check),
        ("Admin Login", tester.test_admin_login),
        ("User Profile", tester.test_user_profile),
        ("Platform Tiers", tester.test_platform_tiers),
        ("Crew Templates", tester.test_crew_templates),
        ("Tools Status", tester.test_tools_status),
        ("Execution History", tester.test_executions_history),
        ("Analytics", tester.test_analytics),
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