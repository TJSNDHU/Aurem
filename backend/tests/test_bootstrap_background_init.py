"""
Test suite for iter 264 - Bootstrap Background Init + Image Cleanup extraction
Tests the extraction of background_init.py (114 LOC) and image_cleanup.py (146 LOC) from server.py

Features tested:
1. Bootstrap module imports (background_init, image_cleanup)
2. run_background_init function signature (5 params)
3. DEFAULT_IMAGES has 5 keys
4. Backwards-compat re-exports from server.py
5. No duplicate definitions in server.py
6. No inline background_init async function in server.py
7. Background init ran successfully (admin user, blog indexes, subscription plans)
8. Health endpoint returns 4/4 pillar workers
9. Security headers present
10. Login flow works
11. Cross-pillar regression tests
"""

import pytest
import requests
import os
import inspect

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBootstrapModuleImports:
    """Test bootstrap module imports work correctly"""
    
    def test_run_background_init_import(self):
        """run_background_init can be imported from bootstrap.background_init"""
        from bootstrap.background_init import run_background_init
        assert callable(run_background_init)
        print("✓ run_background_init imported successfully")
    
    def test_cleanup_broken_images_import(self):
        """cleanup_broken_images can be imported from bootstrap.image_cleanup"""
        from bootstrap.image_cleanup import cleanup_broken_images
        assert callable(cleanup_broken_images)
        print("✓ cleanup_broken_images imported successfully")
    
    def test_default_images_import(self):
        """DEFAULT_IMAGES can be imported from bootstrap.image_cleanup"""
        from bootstrap.image_cleanup import DEFAULT_IMAGES
        assert isinstance(DEFAULT_IMAGES, dict)
        print("✓ DEFAULT_IMAGES imported successfully")
    
    def test_default_images_has_5_keys(self):
        """DEFAULT_IMAGES has exactly 5 keys: product, hero, science, category, section"""
        from bootstrap.image_cleanup import DEFAULT_IMAGES
        expected_keys = {'product', 'hero', 'science', 'category', 'section'}
        assert set(DEFAULT_IMAGES.keys()) == expected_keys
        print(f"✓ DEFAULT_IMAGES has correct 5 keys: {list(DEFAULT_IMAGES.keys())}")
    
    def test_run_background_init_signature(self):
        """run_background_init accepts 5 params: db, create_indexes_fn, setup_database_indexes_fn, seed_business_system_data_fn, start_crypto_tasks_fn"""
        from bootstrap.background_init import run_background_init
        sig = inspect.signature(run_background_init)
        params = list(sig.parameters.keys())
        expected = ['db', 'create_indexes_fn', 'setup_database_indexes_fn', 'seed_business_system_data_fn', 'start_crypto_tasks_fn']
        assert params == expected, f"Expected {expected}, got {params}"
        print(f"✓ run_background_init has correct 5 parameters: {params}")


class TestBackwardsCompatReExports:
    """Test backwards-compat re-exports from server.py"""
    
    def test_cleanup_broken_images_reexport(self):
        """cleanup_broken_images is re-exported from server.py"""
        from server import cleanup_broken_images
        assert callable(cleanup_broken_images)
        print("✓ cleanup_broken_images re-exported from server.py")
    
    def test_default_images_reexport(self):
        """DEFAULT_IMAGES is re-exported from server.py"""
        from server import DEFAULT_IMAGES
        assert isinstance(DEFAULT_IMAGES, dict)
        assert len(DEFAULT_IMAGES) == 5
        print("✓ DEFAULT_IMAGES re-exported from server.py")


class TestServerCodeQuality:
    """Test server.py code quality after extraction"""
    
    def test_no_duplicate_cleanup_broken_images(self):
        """No duplicate definition of cleanup_broken_images in server.py"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        # Should only have import, not definition
        assert 'def cleanup_broken_images' not in content
        assert 'from bootstrap.image_cleanup import cleanup_broken_images' in content
        print("✓ No duplicate cleanup_broken_images definition in server.py")
    
    def test_no_duplicate_default_images(self):
        """No duplicate definition of DEFAULT_IMAGES in server.py"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        # Should only have import, not definition
        assert 'DEFAULT_IMAGES = {' not in content
        assert 'from bootstrap.image_cleanup import' in content and 'DEFAULT_IMAGES' in content
        print("✓ No duplicate DEFAULT_IMAGES definition in server.py")
    
    def test_no_inline_background_init(self):
        """No inline background_init async function in server.py"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        # Should not have inline definition
        assert 'async def background_init(' not in content
        assert 'async def _background_init(' not in content
        # Should have import
        assert 'from bootstrap.background_init import run_background_init' in content
        print("✓ No inline background_init function in server.py")
    
    def test_run_background_init_called_via_create_task(self):
        """run_background_init is called via asyncio.create_task in startup_event"""
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        # Should have create_task call
        assert 'asyncio.create_task' in content
        assert '_run_bg_init(' in content or 'run_background_init(' in content
        print("✓ run_background_init called via asyncio.create_task")
    
    def test_server_loc_reduced(self):
        """server.py LOC reduced from 1618 to ~1434"""
        with open('/app/backend/server.py', 'r') as f:
            lines = len(f.readlines())
        assert lines < 1500, f"server.py has {lines} lines, expected < 1500"
        print(f"✓ server.py reduced to {lines} LOC")


class TestBackgroundInitRan:
    """Test that background_init ran successfully on startup"""
    
    def test_admin_user_exists(self):
        """Admin user teji.ss1986@gmail.com exists with is_admin=true"""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import load_dotenv
        
        load_dotenv('/app/backend/.env')
        mongo_url = os.environ.get('MONGO_URL')
        db_name = os.environ.get('DB_NAME', 'aurem_db')
        
        async def check():
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            admin = await db.users.find_one({'email': 'teji.ss1986@gmail.com'})
            client.close()
            return admin
        
        admin = asyncio.run(check())
        assert admin is not None, "Admin user not found"
        assert admin.get('is_admin') == True, "Admin user is_admin not True"
        print(f"✓ Admin user exists: {admin.get('email')}, is_admin={admin.get('is_admin')}")
    
    def test_blog_posts_indexes(self):
        """blog_posts has 4 indexes: slug (unique), status, category, published_at"""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import load_dotenv
        
        load_dotenv('/app/backend/.env')
        mongo_url = os.environ.get('MONGO_URL')
        db_name = os.environ.get('DB_NAME', 'aurem_db')
        
        async def check():
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            indexes = await db.blog_posts.index_information()
            client.close()
            return indexes
        
        indexes = asyncio.run(check())
        expected = ['slug', 'status', 'category', 'published_at']
        found = [k for k in indexes.keys() if any(e in k for e in expected)]
        assert len(found) >= 4, f"Expected 4 blog indexes, found {len(found)}: {found}"
        print(f"✓ blog_posts has {len(found)} expected indexes: {found}")
    
    def test_subscription_plans_seeded(self):
        """subscription_plans has >= 4 plans seeded"""
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import load_dotenv
        
        load_dotenv('/app/backend/.env')
        mongo_url = os.environ.get('MONGO_URL')
        db_name = os.environ.get('DB_NAME', 'aurem_db')
        
        async def check():
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            count = await db.subscription_plans.count_documents({})
            client.close()
            return count
        
        count = asyncio.run(check())
        assert count >= 4, f"Expected >= 4 subscription plans, found {count}"
        print(f"✓ subscription_plans has {count} plans seeded")


class TestHealthEndpoint:
    """Test /api/health endpoint"""
    
    def test_health_returns_200(self):
        """GET /api/health returns 200"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        print("✓ /api/health returns 200")
    
    def test_health_status_ok(self):
        """GET /api/health returns status=ok"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        data = response.json()
        assert data.get('status') == 'ok'
        print("✓ /api/health status=ok")
    
    def test_health_mongodb_ok(self):
        """GET /api/health returns mongodb=ok"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        data = response.json()
        assert data.get('checks', {}).get('mongodb') == 'ok'
        print("✓ /api/health mongodb=ok")
    
    def test_health_redis_ok(self):
        """GET /api/health returns redis=ok"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        data = response.json()
        assert data.get('checks', {}).get('redis') == 'ok'
        print("✓ /api/health redis=ok")
    
    def test_health_4_pillar_workers(self):
        """GET /api/health returns schedulers='4/4 pillar workers'"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        data = response.json()
        schedulers = data.get('checks', {}).get('schedulers', '')
        assert '4/4 pillar workers' in schedulers
        print(f"✓ /api/health schedulers={schedulers}")
    
    def test_health_response_ms_under_100(self):
        """GET /api/health response_ms < 100"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        data = response.json()
        response_ms = data.get('response_ms', 999)
        assert response_ms < 100, f"response_ms={response_ms}, expected < 100"
        print(f"✓ /api/health response_ms={response_ms}")


class TestSecurityHeaders:
    """Test security headers are present"""
    
    def test_hsts_header(self):
        """HSTS header present"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert 'Strict-Transport-Security' in response.headers
        print("✓ HSTS header present")
    
    def test_x_frame_options(self):
        """X-Frame-Options header present"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert 'X-Frame-Options' in response.headers
        print("✓ X-Frame-Options header present")
    
    def test_x_content_type_options(self):
        """X-Content-Type-Options header present"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert 'X-Content-Type-Options' in response.headers
        print("✓ X-Content-Type-Options header present")
    
    def test_referrer_policy(self):
        """Referrer-Policy header present"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert 'Referrer-Policy' in response.headers
        print("✓ Referrer-Policy header present")
    
    def test_permissions_policy(self):
        """Permissions-Policy header present"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert 'Permissions-Policy' in response.headers
        print("✓ Permissions-Policy header present")


class TestLoginFlow:
    """Test login flow works"""
    
    def test_login_success(self):
        """POST /api/auth/login with admin credentials returns JWT token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "teji.ss1986@gmail.com", "password": "<REDACTED>"},
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert 'token' in data
        assert len(data['token']) > 50
        print(f"✓ Login successful, token received")
    
    def test_login_returns_user(self):
        """POST /api/auth/login returns user object with email"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "teji.ss1986@gmail.com", "password": "<REDACTED>"},
            timeout=10
        )
        data = response.json()
        assert 'user' in data
        assert data['user'].get('email') == 'teji.ss1986@gmail.com'
        print(f"✓ Login returns user: {data['user'].get('email')}")


class TestCrossPillarRegression:
    """Test cross-pillar regression"""
    
    def test_pillar1_auto_blast_status(self):
        """P1: /api/campaign/auto-blast/status returns 200 or 401"""
        response = requests.get(f"{BASE_URL}/api/campaign/auto-blast/status", timeout=10)
        assert response.status_code in [200, 401]
        print(f"✓ P1 auto-blast status: {response.status_code}")
    
    def test_pillar2_subscription_plans(self):
        """P2: /api/subscription/plans returns 200"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans", timeout=10)
        assert response.status_code == 200
        print("✓ P2 subscription plans: 200")
    
    def test_pillar3_repair_pending(self):
        """P3: /api/repair/pending returns 200"""
        response = requests.get(f"{BASE_URL}/api/repair/pending", timeout=10)
        assert response.status_code == 200
        print("✓ P3 repair pending: 200")
    
    def test_platform_health(self):
        """Platform health: /api/platform/health returns 200"""
        response = requests.get(f"{BASE_URL}/api/platform/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'ok'
        print("✓ Platform health: 200, status=ok")


class TestBootstrapModuleLOC:
    """Test bootstrap module line counts"""
    
    def test_background_init_loc(self):
        """background_init.py is ~114 LOC"""
        with open('/app/backend/bootstrap/background_init.py', 'r') as f:
            lines = len(f.readlines())
        assert 100 <= lines <= 130, f"background_init.py has {lines} lines, expected ~114"
        print(f"✓ background_init.py: {lines} LOC")
    
    def test_image_cleanup_loc(self):
        """image_cleanup.py is ~146 LOC"""
        with open('/app/backend/bootstrap/image_cleanup.py', 'r') as f:
            lines = len(f.readlines())
        assert 130 <= lines <= 160, f"image_cleanup.py has {lines} lines, expected ~146"
        print(f"✓ image_cleanup.py: {lines} LOC")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
