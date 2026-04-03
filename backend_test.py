#!/usr/bin/env python3
"""
AUREM Platform Backend API Testing
Tests all critical AUREM platform endpoints and functionality
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class AuremAPITester:
    def __init__(self, base_url: str = "https://live-support-3.preview.emergentagent.com"):
        self.base_url = base_url.rstrip('/')
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
        # Test credentials from platform auth router
        self.admin_email = "admin@aurem.live"
        self.admin_password = "AuremAdmin2024!"
        
        print(f"🎯 AUREM Platform API Testing")
        print(f"📡 Base URL: {self.base_url}")
        print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Optional[Dict] = None, headers: Optional[Dict] = None) -> tuple[bool, Dict]:
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Default headers
        test_headers = {'Content-Type': 'application/json'}
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Test {self.tests_run}: {name}")
        print(f"   {method} {endpoint}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")

            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                print(f"   ✅ PASS - Status: {response.status_code}")
                
                # Try to parse JSON response
                try:
                    response_data = response.json()
                except:
                    response_data = {"raw_response": response.text[:200]}
                    
            else:
                print(f"   ❌ FAIL - Expected {expected_status}, got {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   📄 Response: {json.dumps(response_data, indent=2)[:300]}")
                except:
                    print(f"   📄 Raw Response: {response.text[:200]}")
                response_data = {}

            # Store test result
            self.test_results.append({
                "name": name,
                "method": method,
                "endpoint": endpoint,
                "expected_status": expected_status,
                "actual_status": response.status_code,
                "success": success,
                "response_preview": str(response_data)[:100] if response_data else ""
            })

            return success, response_data

        except requests.exceptions.Timeout:
            print(f"   ⏰ TIMEOUT - Request took longer than 10 seconds")
            self.test_results.append({
                "name": name,
                "method": method,
                "endpoint": endpoint,
                "expected_status": expected_status,
                "actual_status": "TIMEOUT",
                "success": False,
                "error": "Request timeout"
            })
            return False, {}
            
        except requests.exceptions.ConnectionError:
            print(f"   🔌 CONNECTION ERROR - Could not connect to {url}")
            self.test_results.append({
                "name": name,
                "method": method,
                "endpoint": endpoint,
                "expected_status": expected_status,
                "actual_status": "CONNECTION_ERROR",
                "success": False,
                "error": "Connection failed"
            })
            return False, {}
            
        except Exception as e:
            print(f"   💥 ERROR - {str(e)}")
            self.test_results.append({
                "name": name,
                "method": method,
                "endpoint": endpoint,
                "expected_status": expected_status,
                "actual_status": "ERROR",
                "success": False,
                "error": str(e)
            })
            return False, {}

    def test_health_endpoints(self):
        """Test basic health and connectivity"""
        print("\n🏥 HEALTH CHECK TESTS")
        print("-" * 30)
        
        # Root health
        self.run_test("Root Health Check", "GET", "/", 200)
        
        # API health
        self.run_test("API Health Check", "GET", "/api/health", 200)
        
        # Ready check
        self.run_test("Ready Check", "GET", "/ready", 200)

    def test_platform_endpoints(self):
        """Test AUREM platform specific endpoints"""
        print("\n🎯 AUREM PLATFORM TESTS")
        print("-" * 30)
        
        # Platform tiers
        self.run_test("Platform Tiers", "GET", "/api/platform/tiers", 200)
        
        # AUREM system info
        self.run_test("AUREM System Info", "GET", "/api/aurem/system", 200)

    def test_auth_endpoints(self):
        """Test authentication endpoints"""
        print("\n🔐 AUTHENTICATION TESTS")
        print("-" * 30)
        
        # Test platform auth registration (should work or give validation error)
        test_user_data = {
            "email": f"test_{datetime.now().strftime('%H%M%S')}@aurem.test",
            "password": "TestPass123!",
            "company_name": "Test Company",
            "full_name": "Test User"
        }
        
        success, response = self.run_test(
            "Platform Registration", 
            "POST", 
            "/api/platform/auth/register", 
            200,  # Expecting success or validation error
            data=test_user_data
        )
        
        # Test platform auth login with admin credentials
        admin_login_data = {
            "email": self.admin_email,
            "password": self.admin_password
        }
        
        success, response = self.run_test(
            "Platform Admin Login", 
            "POST", 
            "/api/platform/auth/login", 
            200,
            data=admin_login_data
        )
        
        if success and 'token' in response:
            self.token = response['token']
            print(f"   🎫 Token acquired for subsequent tests")
        
        # Test AUREM auth endpoints
        aurem_login_data = {
            "email": self.admin_email,
            "password": self.admin_password
        }
        
        self.run_test(
            "AUREM Auth Login", 
            "POST", 
            "/api/aurem/auth/login", 
            200,
            data=aurem_login_data
        )

    def test_protected_endpoints(self):
        """Test endpoints that require authentication"""
        if not self.token:
            print("\n⚠️  SKIPPING PROTECTED TESTS - No auth token available")
            return
            
        print("\n🛡️  PROTECTED ENDPOINT TESTS")
        print("-" * 30)
        
        # Test auth/me endpoint
        self.run_test("Auth Me", "GET", "/api/aurem/auth/me", 200)
        
        # Test platform dashboard data
        self.run_test("Platform Dashboard", "GET", "/api/platform/dashboard", 200)

    def test_aurem_services(self):
        """Test AUREM specific service endpoints"""
        print("\n🤖 AUREM SERVICE TESTS")
        print("-" * 30)
        
        # Test AUREM platform endpoints (these should exist)
        self.run_test("AUREM Platform Health", "GET", "/api/aurem-platform/health", 200)
        
        # Test morning brief endpoints
        self.run_test("AUREM Morning Brief", "GET", "/api/aurem/morning-brief", 200)
        
        # Test architecture endpoint
        self.run_test("AUREM Architecture", "GET", "/api/aurem/architecture", 200)

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        
        print(f"✅ Tests Passed: {self.tests_passed}")
        print(f"❌ Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"📈 Success Rate: {success_rate:.1f}%")
        print(f"⏱️  Total Tests: {self.tests_run}")
        
        if self.tests_passed < self.tests_run:
            print(f"\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    print(f"   • {result['name']} - {result.get('error', 'Status mismatch')}")
        
        print(f"\n🏁 Testing completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return success_rate >= 70  # Consider 70%+ success rate as acceptable

def main():
    """Main test execution"""
    tester = AuremAPITester()
    
    try:
        # Run all test suites
        tester.test_health_endpoints()
        tester.test_platform_endpoints()
        tester.test_auth_endpoints()
        tester.test_protected_endpoints()
        tester.test_aurem_services()
        
        # Print summary and determine exit code
        success = tester.print_summary()
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Testing interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 CRITICAL ERROR: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())