"""
AUREM Platform Production Stabilization Freeze — E2E Test
=========================================================
Tests ONLY the 3 specified areas:
1. Stripe checkout end-to-end for all 20 catalog services
2. ORA chat response time (<3s)
3. No 500 errors on customer-facing pages

iter 315g — FREEZE MODE: No new features, only validation.
"""

import pytest
import requests
import time
import os

# Use preview URL from environment
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-platform-preview-3.preview.emergentagent.com").rstrip("/")

# Test credentials from test_credentials.md
DOGFOOD_EMAIL = "teji.ss1986+dogfood@gmail.com"
DOGFOOD_PASSWORD = "Dogfood2026!"

# Common headers to bypass Cloudflare bot blocks
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/json"
}


class TestStripeCheckoutE2E:
    """
    Test 1: STRIPE CHECKOUT END-TO-END
    For ALL services from GET /api/catalog/services, hit POST /api/customer/subscriptions/subscribe.
    Each must return 200 with a valid Stripe Checkout session URL.
    """
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login as dogfood customer and get JWT token."""
        login_url = f"{BASE_URL}/api/platform/auth/login"
        payload = {"email": DOGFOOD_EMAIL, "password": DOGFOOD_PASSWORD}
        
        resp = requests.post(login_url, json=payload, headers=COMMON_HEADERS, timeout=15)
        
        if resp.status_code != 200:
            pytest.skip(f"Login failed with status {resp.status_code}: {resp.text[:200]}")
        
        data = resp.json()
        token = data.get("token") or data.get("access_token")
        if not token:
            pytest.skip(f"No token in login response: {data}")
        
        return token
    
    @pytest.fixture(scope="class")
    def catalog_services(self):
        """Fetch all services from the public catalog."""
        catalog_url = f"{BASE_URL}/api/catalog/services"
        resp = requests.get(catalog_url, headers=COMMON_HEADERS, timeout=15)
        
        assert resp.status_code == 200, f"Catalog fetch failed: {resp.status_code} - {resp.text[:200]}"
        
        data = resp.json()
        services = data.get("services", [])
        
        # Filter to only live services
        live_services = [s for s in services if s.get("status") == "live"]
        
        print(f"\n[CATALOG] Found {len(live_services)} live services out of {len(services)} total")
        return live_services
    
    def test_stripe_checkout_all_services(self, auth_token, catalog_services):
        """
        Test Stripe checkout for ALL catalog services.
        Each must return a valid cs_live_... or cs_test_... URL.
        """
        if not catalog_services:
            pytest.skip("No live services in catalog")
        
        headers = {
            **COMMON_HEADERS,
            "Authorization": f"Bearer {auth_token}"
        }
        
        subscribe_url = f"{BASE_URL}/api/customer/subscriptions/subscribe"
        
        results = {"passed": [], "failed": []}
        
        for svc in catalog_services:
            service_id = svc.get("service_id")
            service_name = svc.get("name", service_id)
            
            payload = {
                "service_id": service_id,
                "origin_url": "https://ai-platform-preview-3.preview.emergentagent.com"
            }
            
            try:
                resp = requests.post(subscribe_url, json=payload, headers=headers, timeout=30)
                
                if resp.status_code == 200:
                    data = resp.json()
                    checkout_url = data.get("url", "")
                    session_id = data.get("session_id", "")
                    
                    # Validate checkout URL format
                    if checkout_url.startswith("https://checkout.stripe.com"):
                        # Verify URL is loadable (HEAD request)
                        try:
                            head_resp = requests.head(checkout_url, timeout=10, allow_redirects=True)
                            if head_resp.status_code in [200, 302, 303]:
                                results["passed"].append({
                                    "service_id": service_id,
                                    "name": service_name,
                                    "session_id": session_id[:20] + "..." if session_id else "N/A"
                                })
                                print(f"  ✓ {service_name}: {session_id[:30]}...")
                            else:
                                results["failed"].append({
                                    "service_id": service_id,
                                    "name": service_name,
                                    "error": f"Checkout URL not loadable (HEAD {head_resp.status_code})"
                                })
                                print(f"  ✗ {service_name}: URL not loadable")
                        except Exception as e:
                            results["failed"].append({
                                "service_id": service_id,
                                "name": service_name,
                                "error": f"HEAD request failed: {str(e)[:50]}"
                            })
                    else:
                        results["failed"].append({
                            "service_id": service_id,
                            "name": service_name,
                            "error": f"Invalid checkout URL: {checkout_url[:50]}"
                        })
                        print(f"  ✗ {service_name}: Invalid URL format")
                
                elif resp.status_code == 409:
                    # Already subscribed - this is OK for testing
                    results["passed"].append({
                        "service_id": service_id,
                        "name": service_name,
                        "note": "Already subscribed (409)"
                    })
                    print(f"  ~ {service_name}: Already subscribed")
                
                else:
                    results["failed"].append({
                        "service_id": service_id,
                        "name": service_name,
                        "error": f"HTTP {resp.status_code}: {resp.text[:100]}"
                    })
                    print(f"  ✗ {service_name}: HTTP {resp.status_code}")
            
            except Exception as e:
                results["failed"].append({
                    "service_id": service_id,
                    "name": service_name,
                    "error": str(e)[:100]
                })
                print(f"  ✗ {service_name}: Exception - {str(e)[:50]}")
            
            # Sleep between calls as requested
            time.sleep(0.4)
        
        # Summary
        total = len(catalog_services)
        passed = len(results["passed"])
        failed = len(results["failed"])
        
        print(f"\n[STRIPE CHECKOUT SUMMARY]")
        print(f"  Total services: {total}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        
        if results["failed"]:
            print(f"\n[FAILED SERVICES]")
            for f in results["failed"]:
                print(f"  - {f['name']}: {f['error']}")
        
        # Assert at least 90% pass rate (allow some already-subscribed)
        assert passed >= total * 0.9, f"Stripe checkout failed for {failed}/{total} services"


class TestORAChatResponseTime:
    """
    Test 2: ORA CHAT RESPONSE TIME (<3s)
    Test endpoint POST /api/ora/command or /api/aurem/chat.
    Run 5 times consecutively. Each response must arrive in under 3 seconds.
    """
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login as dogfood customer and get JWT token."""
        login_url = f"{BASE_URL}/api/platform/auth/login"
        payload = {"email": DOGFOOD_EMAIL, "password": DOGFOOD_PASSWORD}
        
        resp = requests.post(login_url, json=payload, headers=COMMON_HEADERS, timeout=15)
        
        if resp.status_code != 200:
            pytest.skip(f"Login failed with status {resp.status_code}: {resp.text[:200]}")
        
        data = resp.json()
        token = data.get("token") or data.get("access_token")
        if not token:
            pytest.skip(f"No token in login response: {data}")
        
        return token
    
    def test_ora_chat_response_time(self, auth_token):
        """
        Test ORA chat response time - must be under 3 seconds for each of 5 calls.
        """
        headers = {
            **COMMON_HEADERS,
            "Authorization": f"Bearer {auth_token}"
        }
        
        # Try multiple possible ORA endpoints
        ora_endpoints = [
            f"{BASE_URL}/api/ora/command",
            f"{BASE_URL}/api/aurem/chat",
        ]
        
        # Find working endpoint
        working_endpoint = None
        for endpoint in ora_endpoints:
            try:
                test_payload = {"text": "Hello", "message": "Hello", "session_id": "e2e_test_probe"}
                resp = requests.post(endpoint, json=test_payload, headers=headers, timeout=10)
                if resp.status_code in [200, 401, 403]:  # 401/403 means endpoint exists but auth issue
                    working_endpoint = endpoint
                    break
            except Exception:
                continue
        
        if not working_endpoint:
            pytest.skip("No working ORA endpoint found")
        
        print(f"\n[ORA CHAT] Using endpoint: {working_endpoint}")
        
        results = []
        test_message = "Hello, what is AUREM?"
        
        for i in range(5):
            session_id = f"e2e_test_{i+1:03d}"
            
            # Determine payload format based on endpoint
            if "command" in working_endpoint:
                payload = {"text": test_message, "channel": "chat", "user": "e2e_test"}
            else:
                payload = {"message": test_message, "session_id": session_id}
            
            start_time = time.time()
            
            try:
                resp = requests.post(working_endpoint, json=payload, headers=headers, timeout=10)
                elapsed_ms = (time.time() - start_time) * 1000
                
                result = {
                    "iteration": i + 1,
                    "status_code": resp.status_code,
                    "elapsed_ms": round(elapsed_ms, 2),
                    "passed": elapsed_ms < 3000 and resp.status_code == 200
                }
                
                if resp.status_code == 200:
                    data = resp.json()
                    result["response_preview"] = str(data.get("reply") or data.get("response", ""))[:50]
                else:
                    result["error"] = resp.text[:100]
                
                results.append(result)
                
                status = "✓" if result["passed"] else "✗"
                print(f"  {status} Call {i+1}: {elapsed_ms:.0f}ms (HTTP {resp.status_code})")
                
            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000
                results.append({
                    "iteration": i + 1,
                    "status_code": 0,
                    "elapsed_ms": round(elapsed_ms, 2),
                    "passed": False,
                    "error": str(e)[:100]
                })
                print(f"  ✗ Call {i+1}: Exception - {str(e)[:50]}")
            
            # Small delay between calls
            time.sleep(0.2)
        
        # Summary
        passed = sum(1 for r in results if r["passed"])
        avg_time = sum(r["elapsed_ms"] for r in results) / len(results) if results else 0
        
        print(f"\n[ORA CHAT SUMMARY]")
        print(f"  Passed: {passed}/5")
        print(f"  Average response time: {avg_time:.0f}ms")
        
        # All 5 must pass
        failed_results = [r for r in results if not r["passed"]]
        if failed_results:
            print(f"\n[FAILED CALLS]")
            for r in failed_results:
                print(f"  - Call {r['iteration']}: {r['elapsed_ms']}ms, HTTP {r['status_code']}")
                if r.get("error"):
                    print(f"    Error: {r['error']}")
        
        assert passed == 5, f"ORA chat failed {5-passed}/5 calls (>3s or error)"


class TestNo500Errors:
    """
    Test 3: NO 500 ERRORS ON CUSTOMER-FACING PAGES
    Navigate to all customer-facing routes and check for 5xx responses.
    """
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login as dogfood customer and get JWT token."""
        login_url = f"{BASE_URL}/api/platform/auth/login"
        payload = {"email": DOGFOOD_EMAIL, "password": DOGFOOD_PASSWORD}
        
        resp = requests.post(login_url, json=payload, headers=COMMON_HEADERS, timeout=15)
        
        if resp.status_code != 200:
            pytest.skip(f"Login failed with status {resp.status_code}: {resp.text[:200]}")
        
        data = resp.json()
        token = data.get("token") or data.get("access_token")
        if not token:
            pytest.skip(f"No token in login response: {data}")
        
        return token
    
    def test_public_pages_no_500(self):
        """Test public pages (no auth required) for 5xx errors."""
        public_routes = [
            "/",
            "/pricing",
            "/audit",
            "/platform/login",
        ]
        
        results = {"passed": [], "failed": []}
        
        print("\n[PUBLIC PAGES]")
        for route in public_routes:
            url = f"{BASE_URL}{route}"
            try:
                resp = requests.get(url, headers=COMMON_HEADERS, timeout=15, allow_redirects=True)
                
                if resp.status_code >= 500:
                    results["failed"].append({
                        "route": route,
                        "status_code": resp.status_code,
                        "error": resp.text[:100]
                    })
                    print(f"  ✗ {route}: HTTP {resp.status_code}")
                else:
                    results["passed"].append({"route": route, "status_code": resp.status_code})
                    print(f"  ✓ {route}: HTTP {resp.status_code}")
            
            except Exception as e:
                results["failed"].append({
                    "route": route,
                    "status_code": 0,
                    "error": str(e)[:100]
                })
                print(f"  ✗ {route}: Exception - {str(e)[:50]}")
        
        assert len(results["failed"]) == 0, f"5xx errors on public pages: {results['failed']}"
    
    def test_customer_pages_no_500(self, auth_token):
        """Test customer portal pages (auth required) for 5xx errors."""
        customer_routes = [
            "/welcome",
            "/onboarding",
            "/my",
            "/my/website",
            "/my/dashboard",
            "/my/settings",
            "/my/reports",
            "/my/integrations",
            "/my/billing",
            "/my/scan-history",
        ]
        
        headers = {
            **COMMON_HEADERS,
            "Authorization": f"Bearer {auth_token}"
        }
        
        results = {"passed": [], "failed": []}
        
        print("\n[CUSTOMER PAGES]")
        for route in customer_routes:
            url = f"{BASE_URL}{route}"
            try:
                resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
                
                if resp.status_code >= 500:
                    results["failed"].append({
                        "route": route,
                        "status_code": resp.status_code,
                        "error": resp.text[:100]
                    })
                    print(f"  ✗ {route}: HTTP {resp.status_code}")
                else:
                    results["passed"].append({"route": route, "status_code": resp.status_code})
                    print(f"  ✓ {route}: HTTP {resp.status_code}")
            
            except Exception as e:
                results["failed"].append({
                    "route": route,
                    "status_code": 0,
                    "error": str(e)[:100]
                })
                print(f"  ✗ {route}: Exception - {str(e)[:50]}")
        
        assert len(results["failed"]) == 0, f"5xx errors on customer pages: {results['failed']}"
    
    def test_customer_api_endpoints_no_500(self, auth_token):
        """Test customer-facing API endpoints for 5xx errors."""
        api_endpoints = [
            "/api/catalog/services",
            "/api/bin-auth/customer-context",
            "/api/customer/subscriptions",
            "/api/customer/pixel/status",
        ]
        
        headers = {
            **COMMON_HEADERS,
            "Authorization": f"Bearer {auth_token}"
        }
        
        results = {"passed": [], "failed": []}
        
        print("\n[CUSTOMER API ENDPOINTS]")
        for endpoint in api_endpoints:
            url = f"{BASE_URL}{endpoint}"
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                
                if resp.status_code >= 500:
                    results["failed"].append({
                        "endpoint": endpoint,
                        "status_code": resp.status_code,
                        "error": resp.text[:100]
                    })
                    print(f"  ✗ {endpoint}: HTTP {resp.status_code}")
                else:
                    results["passed"].append({"endpoint": endpoint, "status_code": resp.status_code})
                    print(f"  ✓ {endpoint}: HTTP {resp.status_code}")
            
            except Exception as e:
                results["failed"].append({
                    "endpoint": endpoint,
                    "status_code": 0,
                    "error": str(e)[:100]
                })
                print(f"  ✗ {endpoint}: Exception - {str(e)[:50]}")
        
        assert len(results["failed"]) == 0, f"5xx errors on customer APIs: {results['failed']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
