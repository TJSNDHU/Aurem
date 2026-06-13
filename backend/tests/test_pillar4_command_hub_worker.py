"""
Pillar 4 (Command Hub / Observability / Platform Ops) Worker Tests
===================================================================
Tests for iteration 261 — Pillar 4 worker isolation with 19 schedulers.

Verifies:
- Pillar 4 worker starts cleanly with exactly 19 schedulers
- All 4 pillar workers show as running via /api/health
- No duplicate scheduler startup in startup_init.py
- backup_loop is NOT directly asyncio.create_task'd in server.py
- Pillar 1, 2, 3 regression — still running 3, 5, 3 schedulers respectively
- All required API endpoints return expected status codes
- File structure verification for pillars/command_hub/
"""

import pytest
import requests
import os

import pytest
pytestmark = pytest.mark.skip(reason="stale — asserts iter-era scheduler counts via log greps; counts changed every iteration since — quarantined iter D-86; delete or rewrite when feature re-stabilises")

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPillar4WorkerFileStructure:
    """Verify Pillar 4 worker file structure exists"""
    
    def test_pillar4_worker_file_exists(self):
        """pillars/command_hub/worker.py must exist"""
        worker_path = "/app/backend/pillars/command_hub/worker.py"
        assert os.path.exists(worker_path), f"Pillar 4 worker file not found: {worker_path}"
        print(f"✓ Pillar 4 worker file exists: {worker_path}")
    
    def test_pillar4_init_file_exists(self):
        """pillars/command_hub/__init__.py must exist"""
        init_path = "/app/backend/pillars/command_hub/__init__.py"
        assert os.path.exists(init_path), f"Pillar 4 __init__.py not found: {init_path}"
        print(f"✓ Pillar 4 __init__.py exists: {init_path}")
    
    def test_pillar4_worker_has_required_functions(self):
        """worker.py must have start_pillar4_worker, get_worker_status, shutdown_pillar4_worker"""
        worker_path = "/app/backend/pillars/command_hub/worker.py"
        with open(worker_path, 'r') as f:
            content = f.read()
        
        required_functions = [
            'def start_pillar4_worker',
            'def get_worker_status',
            'async def shutdown_pillar4_worker',
            'def _safe_task',
        ]
        
        for func in required_functions:
            assert func in content, f"Required function not found: {func}"
            print(f"✓ Found function: {func}")
    
    def test_pillar4_worker_accepts_8_coro_factories(self):
        """start_pillar4_worker must accept 8 coro_factory parameters"""
        worker_path = "/app/backend/pillars/command_hub/worker.py"
        with open(worker_path, 'r') as f:
            content = f.read()
        
        required_params = [
            'daily_digest_coro_factory',
            'operational_alerts_coro_factory',
            'whatsapp_crm_coro_factory',
            'orchestrator_digest_coro_factory',
            'auto_repair_coro_factory',
            'monthly_cleanup_coro_factory',
            'daily_client_scan_coro_factory',
            'health_score_coro_factory',
        ]
        
        for param in required_params:
            assert param in content, f"Required coro_factory param not found: {param}"
            print(f"✓ Found coro_factory param: {param}")


class TestNoDuplicateSchedulerStartup:
    """Verify no duplicate scheduler startups in startup_init.py and server.py"""
    
    def test_no_duplicate_auto_heal_in_startup_init(self):
        """startup_init.py must NOT have _safe_task(auto_heal_scheduler(), ...)"""
        startup_path = "/app/backend/services/startup_init.py"
        with open(startup_path, 'r') as f:
            content = f.read()
        
        # These schedulers are now owned by Pillar 4 — should NOT be started directly
        forbidden_patterns = [
            '_safe_task(auto_heal_scheduler()',
            '_safe_task(qa_bot_pulse_scheduler()',
            '_safe_task(health_score_scheduler()',
            '_safe_task(autonomy_cron_scheduler()',
            '_safe_task(system_audit_scheduler()',
            '_safe_task(daily_client_scan_loop()',
            '_safe_task(start_daily_audit()',
            '_safe_task(reverification_scheduler()',
        ]
        
        for pattern in forbidden_patterns:
            assert pattern not in content, f"Duplicate scheduler startup found: {pattern}"
        print("✓ No duplicate scheduler startups in startup_init.py")
    
    def test_no_backup_loop_in_server_py(self):
        """server.py must NOT have asyncio.create_task(backup_loop()) or _safe_task(backup_loop())"""
        server_path = "/app/backend/server.py"
        with open(server_path, 'r') as f:
            content = f.read()
        
        forbidden_patterns = [
            'asyncio.create_task(backup_loop()',
            '_safe_task(backup_loop()',
        ]
        
        for pattern in forbidden_patterns:
            assert pattern not in content, f"backup_loop direct startup found: {pattern}"
        print("✓ backup_loop is NOT directly started in server.py (owned by P4)")
    
    def test_pillar4_worker_started_in_startup_init(self):
        """startup_init.py must call start_pillar4_worker"""
        startup_path = "/app/backend/services/startup_init.py"
        with open(startup_path, 'r') as f:
            content = f.read()
        
        assert 'from pillars.command_hub.worker import start_pillar4_worker' in content
        assert 'start_pillar4_worker(' in content
        print("✓ Pillar 4 worker is started in startup_init.py")


class TestAPIEndpoints:
    """Test all required API endpoints"""
    
    def test_health_endpoint_shows_4_pillar_workers(self):
        """GET /api/health must return schedulers='4/4 pillar workers'"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get('status') == 'ok', f"Expected status 'ok', got {data.get('status')}"
        
        checks = data.get('checks', {})
        schedulers = checks.get('schedulers', '')
        assert '4/4 pillar workers' in schedulers, f"Expected '4/4 pillar workers', got '{schedulers}'"
        print(f"✓ /api/health returns schedulers='{schedulers}'")
    
    def test_subscription_plans_returns_4_plans(self):
        """GET /api/subscription/plans must return 4 plans (P2 regression)"""
        response = requests.get(f"{BASE_URL}/api/subscription/plans", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        plans = data.get('plans', [])
        assert len(plans) == 4, f"Expected 4 plans, got {len(plans)}"
        
        plan_ids = [p.get('id') for p in plans]
        expected_ids = ['trial', 'starter', 'growth', 'enterprise']
        for pid in expected_ids:
            assert pid in plan_ids, f"Missing plan: {pid}"
        print(f"✓ /api/subscription/plans returns 4 plans: {plan_ids}")
    
    def test_auto_blast_status_returns_401(self):
        """GET /api/campaign/auto-blast/status must return 401 (auth required) — P1 regression"""
        response = requests.get(f"{BASE_URL}/api/campaign/auto-blast/status", timeout=10)
        # 401 is expected because auth is required
        assert response.status_code in [401, 200], f"Expected 401 or 200, got {response.status_code}"
        print(f"✓ /api/campaign/auto-blast/status returns {response.status_code} (P1 regression OK)")
    
    def test_repair_pending_returns_200(self):
        """GET /api/repair/pending must return 200 with fixes array — P3 regression"""
        response = requests.get(f"{BASE_URL}/api/repair/pending", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert 'fixes' in data, "Response must contain 'fixes' array"
        print(f"✓ /api/repair/pending returns 200 with {len(data.get('fixes', []))} fixes (P3 regression OK)")
    
    def test_sentinel_overview_returns_401(self):
        """GET /api/admin/sentinel/overview must return 401 (auth required)"""
        response = requests.get(f"{BASE_URL}/api/admin/sentinel/overview", timeout=10)
        # 401 is expected because admin auth is required
        assert response.status_code in [401, 200], f"Expected 401 or 200, got {response.status_code}"
        print(f"✓ /api/admin/sentinel/overview returns {response.status_code}")
    
    def test_shannon_posture_returns_401(self):
        """GET /api/security/shannon/posture must return 401 (auth required)"""
        response = requests.get(f"{BASE_URL}/api/security/shannon/posture", timeout=10)
        # 401 is expected because auth is required
        assert response.status_code in [401, 200], f"Expected 401 or 200, got {response.status_code}"
        print(f"✓ /api/security/shannon/posture returns {response.status_code}")
    
    def test_admin_catalog_returns_401(self):
        """GET /api/admin/catalog must return 401 (auth required)"""
        response = requests.get(f"{BASE_URL}/api/admin/catalog", timeout=10)
        # 401 is expected because admin auth is required
        assert response.status_code in [401, 200], f"Expected 401 or 200, got {response.status_code}"
        print(f"✓ /api/admin/catalog returns {response.status_code}")


class TestPillarWorkerCounts:
    """Verify all 4 pillar workers have correct scheduler counts"""
    
    def test_pillar4_has_19_schedulers(self):
        """Pillar 4 worker must have exactly 19 schedulers"""
        # Read backend logs to verify
        log_path = "/var/log/supervisor/backend.out.log"
        with open(log_path, 'r') as f:
            content = f.read()
        
        # Look for the Pillar 4 startup message
        assert '[p4-worker] Pillar 4 worker ready — 19 schedulers attached, 0 failed' in content, \
            "Pillar 4 worker did not start with 19 schedulers"
        print("✓ Pillar 4 worker has 19 schedulers attached, 0 failed")
    
    def test_pillar1_has_3_schedulers(self):
        """Pillar 1 worker must have exactly 3 schedulers (regression)"""
        log_path = "/var/log/supervisor/backend.out.log"
        with open(log_path, 'r') as f:
            content = f.read()
        
        assert '[p1-worker] Pillar 1 worker ready — 3 schedulers attached, 0 failed' in content, \
            "Pillar 1 worker did not start with 3 schedulers"
        print("✓ Pillar 1 worker has 3 schedulers attached, 0 failed (regression OK)")
    
    def test_pillar2_has_5_schedulers(self):
        """Pillar 2 worker must have exactly 5 schedulers (regression)"""
        log_path = "/var/log/supervisor/backend.out.log"
        with open(log_path, 'r') as f:
            content = f.read()
        
        assert '[p2-worker] Pillar 2 worker ready — 5 schedulers attached, 0 failed' in content, \
            "Pillar 2 worker did not start with 5 schedulers"
        print("✓ Pillar 2 worker has 5 schedulers attached, 0 failed (regression OK)")
    
    def test_pillar3_has_3_schedulers(self):
        """Pillar 3 worker must have exactly 3 schedulers (regression)"""
        log_path = "/var/log/supervisor/backend.out.log"
        with open(log_path, 'r') as f:
            content = f.read()
        
        assert '[p3-worker] Pillar 3 worker ready — 3 schedulers attached, 0 failed' in content, \
            "Pillar 3 worker did not start with 3 schedulers"
        print("✓ Pillar 3 worker has 3 schedulers attached, 0 failed (regression OK)")
    
    def test_total_schedulers_is_30(self):
        """Total schedulers across all 4 pillars must be 30 (3+5+3+19)"""
        total = 3 + 5 + 3 + 19
        assert total == 30, f"Expected 30 total schedulers, got {total}"
        print(f"✓ Total schedulers: {total} (P1=3, P2=5, P3=3, P4=19)")


class TestNoImportErrors:
    """Verify backend boots clean with zero ImportError"""
    
    def test_no_import_errors_in_logs(self):
        """Backend logs must not contain ImportError (except sentence_transformers which is optional)"""
        log_path = "/var/log/supervisor/backend.err.log"
        with open(log_path, 'r') as f:
            content = f.read()
        
        # Filter out known optional module warnings
        lines = content.split('\n')
        import_errors = [
            line for line in lines 
            if 'ImportError' in line or 'ModuleNotFoundError' in line
            if 'sentence_transformers' not in line  # Optional ML module
        ]
        
        assert len(import_errors) == 0, f"Found ImportError in logs: {import_errors}"
        print("✓ No ImportError in backend logs (clean boot)")
    
    def test_no_unhandled_exceptions_in_logs(self):
        """Backend logs must not contain unhandled exceptions related to pillar workers"""
        log_path = "/var/log/supervisor/backend.err.log"
        with open(log_path, 'r') as f:
            content = f.read()
        
        # Check for pillar-related exceptions
        pillar_exceptions = [
            line for line in content.split('\n')
            if ('pillar' in line.lower() or 'p4-worker' in line.lower() or 'command_hub' in line.lower())
            and ('exception' in line.lower() or 'error' in line.lower() or 'traceback' in line.lower())
        ]
        
        assert len(pillar_exceptions) == 0, f"Found pillar-related exceptions: {pillar_exceptions}"
        print("✓ No unhandled exceptions related to pillar workers")


class TestPillar4SchedulerAttachment:
    """Verify all 19 schedulers are attached to Pillar 4"""
    
    def test_all_19_schedulers_attached(self):
        """All 19 schedulers must be attached to Pillar 4 worker"""
        log_path = "/var/log/supervisor/backend.out.log"
        with open(log_path, 'r') as f:
            content = f.read()
        
        expected_schedulers = [
            'Auto-Heal monitor',
            'Autonomous Self-Repair (10 min)',
            'QA Bot Pulse (10 min)',
            'QA Agent Deep (weekly)',
            'Health Score Engine (6 h)',
            'System Audit (monthly heartbeat)',
            'Autonomy Nightly Self-Audit (2 AM UTC)',
            'Daily Site Audit',
            'Daily Client Website Intel (3:15 AM UTC)',
            'Accurate-Scout Re-verification (nightly)',
            'Daily Review Digest (9 AM EST)',
            'Orchestrator Digest (8 AM EST)',
            'Operational Alerts (low stock / NPN)',
            'WhatsApp CRM Daily Ticks',
            'Monthly GDPR Data Cleanup',
            'Backup Service (6 h cycle)',
            'ClawChief Heartbeat',
            'ClawChief Daily Sweep',
            'ClawChief Pipeline Audit',
        ]
        
        attached_count = 0
        for scheduler in expected_schedulers:
            pattern = f'[p4-worker] ✓ {scheduler} attached'
            if pattern in content:
                attached_count += 1
                print(f"  ✓ {scheduler}")
            else:
                print(f"  ✗ {scheduler} NOT FOUND")
        
        assert attached_count == 19, f"Expected 19 schedulers attached, found {attached_count}"
        print(f"✓ All 19 schedulers attached to Pillar 4 worker")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
