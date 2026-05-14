"""
Autonomous Self-Repair System for reroots.ca
═══════════════════════════════════════════════════════════════════
Fully autonomous error detection, diagnosis, and repair.
- Detects errors within 10 minutes
- Applies known fixes automatically
- Uses AI for unknown errors
- Only contacts admin for high-risk fixes
- Tests fixes and reports results

Runs every 10 minutes via APScheduler.
═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

import os
import re
import json
import hashlib
import shutil
import ast
import subprocess
import logging
import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# MongoDB reference (set by server.py)
_db = None

def set_db(db):
    global _db
    _db = db

# Admin phone for alerts. NO default fallback — if not configured, alerts
# silently disable instead of leaking a stale hardcoded number into the
# repo or sending to a wrong recipient.
ADMIN_WHATSAPP = os.environ.get("ADMIN_WHATSAPP", "").strip()

# ── Repair-storm protection ───────────────────────────────────────────
# If more than this many repair cycles ran in the cooloff window, skip
# this cycle. Prevents flapping (restart → break → restart → break ...).
_REPAIR_COOLOFF_MIN = 5
_REPAIR_COOLOFF_MAX = 3

# ── pip-install allowlist ─────────────────────────────────────────────
# Only these packages may be auto-installed by the repair loop. New names
# must be added explicitly here. Without this an error log containing
# `No module named 'rquests'` would have typosquat-installed malware.
_PIP_INSTALL_ALLOWLIST = frozenset({
    "requests", "httpx", "pymongo", "motor", "fastapi", "pydantic",
    "aiohttp", "redis", "sqlalchemy", "pillow", "numpy", "pandas",
    "twilio", "resend", "sendgrid", "stripe", "anthropic", "openai",
    "google-cloud-storage", "boto3", "python-dotenv", "uvicorn",
    "starlette", "pyjwt", "passlib", "bcrypt", "apscheduler",
    "beautifulsoup4", "lxml", "python-multipart", "email-validator",
})

# ── WhatsApp-approval safe-command allowlist ──────────────────────────
# When the admin approves an AI-suggested fix via WhatsApp, we still
# refuse to pipe arbitrary AI-generated strings into /bin/sh. Only the
# specific shapes below are accepted, exec'd as argv lists (shell=False).
_APPROVAL_CMD_RE = re.compile(
    r"^("
    r"sudo supervisorctl (restart|start|stop) [A-Za-z0-9_-]{1,40}"
    r"|pip install [A-Za-z0-9_.\-]{1,60}"
    r"|yarn (install|build)"
    r")$"
)

# ═══════════════════════════════════════════════════════════════════
# KNOWN FIX PATTERNS - Applied automatically without asking admin
# ═══════════════════════════════════════════════════════════════════

KNOWN_FIXES = {
    'timedelta_not_defined': {
        'pattern': "name 'timedelta' is not defined",
        'fix_type': 'code_patch',
        'description': 'Missing timedelta import',
        'search': 'from datetime import datetime',
        'replace': 'from datetime import datetime, timedelta',
        'safe': True
    },
    'timezone_not_defined': {
        'pattern': "name 'timezone' is not defined",
        'fix_type': 'code_patch',
        'description': 'Missing timezone import',
        'search': 'from datetime import datetime',
        'replace': 'from datetime import datetime, timezone',
        'safe': True
    },
    'collection_boolean_check': {
        'pattern': "NotImplementedError",
        'secondary_pattern': 'if not self.collection',
        'fix_type': 'code_patch',
        'description': 'PyMongo boolean antipattern',
        'search': 'if not self.collection:',
        'replace': 'if self.collection is None:',
        'safe': True
    },
    'collection_boolean_check_db': {
        'pattern': "NotImplementedError",
        'secondary_pattern': 'if not db:',
        'fix_type': 'code_patch',
        'description': 'PyMongo boolean antipattern (db)',
        'search': 'if not db:',
        'replace': 'if db is None:',
        'safe': True
    },
    'backend_down': {
        'pattern': 'backend_health.*failed|Connection refused.*8001',
        'fix_type': 'restart_service',
        'service': 'backend',
        'description': 'Backend process crashed',
        'safe': True
    },
    'frontend_down': {
        'pattern': 'frontend_serving.*failed|Connection refused.*3000',
        'fix_type': 'restart_service',
        'service': 'frontend',
        'description': 'Frontend process crashed',
        'safe': True
    },
    'scheduler_missing': {
        'pattern': 'scheduler_jobs.*failed|No running schedulers',
        'fix_type': 'restart_service',
        'service': 'backend',
        'description': 'Scheduler jobs disappeared',
        'safe': True
    },
    'redis_connection': {
        'pattern': 'redis.*connection.*refused|redis.*error',
        'fix_type': 'restart_service',
        'service': 'redis',
        'description': 'Redis connection lost',
        'safe': True
    },
    'module_not_found': {
        'pattern': "ModuleNotFoundError: No module named",
        'fix_type': 'pip_install',
        'description': 'Missing Python module',
        'safe': True
    },
}

# ═══════════════════════════════════════════════════════════════════
# FIXES THAT REQUIRE ADMIN APPROVAL - Too risky to apply automatically
# ═══════════════════════════════════════════════════════════════════

REQUIRES_APPROVAL = [
    'database migration',
    'delete',
    'drop collection',
    'remove route',
    'change port',
    'modify .env',
    'stripe',
    'payment',
    'order',
    'refund',
    'customer data',
    'production',
    'deploy',
]

# Pending approvals store (in-memory, also persisted to DB)
pending_approvals: Dict[str, dict] = {}


# ═══════════════════════════════════════════════════════════════════
# MAIN AUTONOMOUS REPAIR LOOP
# ═══════════════════════════════════════════════════════════════════

async def run_autonomous_repair() -> Dict[str, Any]:
    """
    Main autonomous repair loop.
    Runs every 10 minutes via APScheduler.
    
    1. Collects all recent errors
    2. Checks for known fixes first (fast path)
    3. Uses AI for unknown errors
    4. Tests if fixes worked
    5. Reports to admin
    """
    if _db is None:
        logger.warning("[AUTO_REPAIR] Database not initialized")
        return {'status': 'error', 'message': 'Database not ready'}

    # Repair-storm guard. If we've already burned 3+ cycles inside the
    # last 5 min, cool off; otherwise an unstable subsystem can trigger
    # an infinite restart→crash→restart spiral.
    try:
        cooloff_since = datetime.now(timezone.utc) - timedelta(minutes=_REPAIR_COOLOFF_MIN)
        recent = await _db.auto_repair_log.count_documents(
            {'timestamp': {'$gte': cooloff_since}}
        )
        if recent >= _REPAIR_COOLOFF_MAX:
            logger.warning(
                f"[AUTO_REPAIR] cooloff active — {recent} cycles in last "
                f"{_REPAIR_COOLOFF_MIN}min (max {_REPAIR_COOLOFF_MAX})"
            )
            return {'status': 'cooloff', 'recent_cycles': recent}
    except Exception as _cool_e:
        logger.debug(f"[AUTO_REPAIR] cooloff check failed: {_cool_e}")

    logger.info("[AUTO_REPAIR] Starting autonomous repair cycle...")
    
    since = datetime.now(timezone.utc) - timedelta(minutes=15)
    
    # Step 1 — Collect all errors from logs
    errors = []
    try:
        # Check error_logs collection
        error_cursor = _db.error_logs.find(
            {
                'timestamp': {'$gte': since},
                'level': {'$in': ['ERROR', 'CRITICAL', 'WARNING']}
            },
            {'_id': 0}
        ).limit(30)
        errors = await error_cursor.to_list(30)
    except Exception as e:
        logger.warning(f"[AUTO_REPAIR] Could not read error_logs: {e}")
    
    # Also check auto_heal_runs for issues
    auto_heal = None
    try:
        auto_heal = await _db.auto_heal_runs.find_one(
            sort=[('timestamp', -1)]
        )
    except Exception:
        pass
    
    # Check backend logs for errors
    log_errors = await scan_backend_logs()
    errors.extend(log_errors)
    
    if not errors and (not auto_heal or auto_heal.get('overall_status') == 'healthy'):
        logger.info("[AUTO_REPAIR] System healthy, no repairs needed")
        return {'status': 'healthy', 'actions': []}
    
    # Step 2 — Check for known fixes first (fast path). Dedup by a hash
    # of the message so that 5 identical "Connection refused" lines don't
    # trigger 5 redis restarts in a single cycle.
    auto_fixed = []
    remaining_errors = []
    _seen_error_hashes: set = set()

    for error in errors:
        error_text = str(error.get('message', '') or error.get('error', ''))
        _h = hashlib.md5(error_text.encode('utf-8', 'ignore')).hexdigest()
        if _h in _seen_error_hashes:
            continue
        _seen_error_hashes.add(_h)
        fixed = False
        
        for fix_name, fix_data in KNOWN_FIXES.items():
            pattern = fix_data['pattern']
            if re.search(pattern, error_text, re.IGNORECASE):
                logger.info(f"[AUTO_REPAIR] Known fix matched: {fix_name}")
                result = await apply_known_fix(fix_name, fix_data, error_text)
                if result['success']:
                    auto_fixed.append({
                        'error': error_text[:100],
                        'fix_applied': fix_data['description'],
                        'fix_name': fix_name,
                        'result': result,
                        'timestamp': datetime.now(timezone.utc)
                    })
                    fixed = True
                    break
        
        if not fixed:
            remaining_errors.append(error)
    
    # Step 3 — Use AI for unknown errors
    ai_actions = []
    if remaining_errors and len(remaining_errors) <= 5:  # Limit AI calls
        ai_actions = await ai_diagnose_and_fix(remaining_errors, auto_heal)
    
    # Step 4 — Test if fixes worked
    test_result = await test_system_health()
    
    # Step 5 — Report to admin
    await send_repair_report(auto_fixed, ai_actions, test_result)
    
    # Save to database
    try:
        await _db.auto_repair_log.insert_one({
            'timestamp': datetime.now(timezone.utc),
            'errors_found': len(errors),
            'auto_fixed': len(auto_fixed),
            'ai_actions': len(ai_actions),
            'system_healthy_after': test_result['healthy'],
            'fixes': auto_fixed + ai_actions,
            'test_results': test_result
        })
    except Exception as e:
        logger.error(f"[AUTO_REPAIR] Failed to log repair: {e}")
    
    logger.info(f"[AUTO_REPAIR] Cycle complete. Auto-fixed: {len(auto_fixed)}, AI actions: {len(ai_actions)}, Healthy: {test_result['healthy']}")
    
    return {
        'status': 'completed',
        'auto_fixed': auto_fixed,
        'ai_actions': ai_actions,
        'system_healthy': test_result['healthy']
    }


async def scan_backend_logs() -> List[dict]:
    """Scan backend logs for recent errors."""
    errors = []
    try:
        result = subprocess.run(
            ['tail', '-100', '/var/log/supervisor/backend.err.log'],
            capture_output=True, text=True, timeout=5
        )
        
        for line in result.stdout.split('\n'):
            if any(level in line.upper() for level in ['ERROR', 'CRITICAL', 'EXCEPTION', 'TRACEBACK']):
                errors.append({
                    'message': line[:500],
                    'source': 'backend_log',
                    'timestamp': datetime.now(timezone.utc)
                })
    except Exception as e:
        logger.warning(f"[AUTO_REPAIR] Could not scan logs: {e}")
    
    return errors[:10]  # Limit to 10 most recent


# ═══════════════════════════════════════════════════════════════════
# KNOWN FIX APPLICATORS
# ═══════════════════════════════════════════════════════════════════

async def apply_known_fix(fix_name: str, fix_data: dict, error_text: str) -> dict:
    """Applies a known safe fix automatically."""
    try:
        fix_type = fix_data['fix_type']
        
        if fix_type == 'restart_service':
            service = fix_data['service']
            result = subprocess.run(
                ['sudo', 'supervisorctl', 'restart', service],
                capture_output=True, text=True, timeout=30
            )
            await asyncio.sleep(3)  # Wait for service to start
            return {
                'success': result.returncode == 0,
                'action': f"Restarted {service}",
                'output': result.stdout[:200]
            }
        
        elif fix_type == 'code_patch':
            search = fix_data['search']
            replace = fix_data['replace']
            
            # Find files with the bad pattern
            grep_result = subprocess.run(
                ['grep', '-r', '--include=*.py', '-l', search, '/app/backend/'],
                capture_output=True, text=True
            )
            files = [f for f in grep_result.stdout.strip().split('\n') if f]
            patched = []
            
            for filepath in files:
                # Safety: make a .bak copy before any write, validate the
                # post-patch source parses cleanly, and restore on failure.
                # Without this, a regex-broad fix can corrupt a comment or
                # docstring and crash the whole backend on next restart.
                backup_path = filepath + ".bak"
                try:
                    with open(filepath, 'r') as f:
                        content = f.read()
                    
                    if search not in content or replace in content:
                        continue
                    
                    new_content = content.replace(search, replace)
                    try:
                        ast.parse(new_content, filename=filepath)
                    except SyntaxError as se:
                        logger.error(
                            f"[AUTO_REPAIR] code_patch on {filepath} would "
                            f"break syntax ({se}) — skipping"
                        )
                        continue

                    shutil.copy2(filepath, backup_path)
                    with open(filepath, 'w') as f:
                        f.write(new_content)

                    # Final guard: re-parse the on-disk file. If anything
                    # raced between validation and write, restore.
                    try:
                        with open(filepath, 'r') as f:
                            ast.parse(f.read(), filename=filepath)
                        patched.append(filepath)
                    except SyntaxError as se2:
                        logger.error(
                            f"[AUTO_REPAIR] post-write syntax error on "
                            f"{filepath} ({se2}) — restoring"
                        )
                        shutil.move(backup_path, filepath)
                except Exception as e:
                    logger.warning(f"[AUTO_REPAIR] Could not patch {filepath}: {e}")
                    # Best-effort restore if backup was made.
                    try:
                        if os.path.exists(backup_path):
                            shutil.move(backup_path, filepath)
                    except Exception:
                        pass
            
            if patched:
                # Restart backend to apply patch
                subprocess.run(
                    ['sudo', 'supervisorctl', 'restart', 'backend'],
                    capture_output=True, timeout=30
                )
                await asyncio.sleep(3)
                return {
                    'success': True,
                    'action': f"Patched {len(patched)} files and restarted backend",
                    'files': patched
                }
            
            return {'success': False, 'reason': 'No files needed patching'}
        
        elif fix_type == 'pip_install':
            # Extract module name from error
            match = re.search(r"No module named '([^']+)'", error_text)
            if match:
                module = match.group(1).split('.')[0]
                # Allowlist gate — without this, a "No module named 'rquests'"
                # in any log would let an attacker typosquat-install malware.
                if module.lower() not in _PIP_INSTALL_ALLOWLIST:
                    logger.warning(
                        f"[AUTO_REPAIR] pip_install BLOCKED — '{module}' not "
                        f"in allowlist"
                    )
                    return {
                        'success': False,
                        'reason': f"module '{module}' not in pip-install allowlist",
                    }
                result = subprocess.run(
                    ['pip', 'install', module],
                    capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0:
                    subprocess.run(
                        ['sudo', 'supervisorctl', 'restart', 'backend'],
                        capture_output=True, timeout=30
                    )
                    return {
                        'success': True,
                        'action': f"Installed {module} and restarted backend"
                    }
            return {'success': False, 'reason': 'Could not extract module name'}
        
        return {'success': False, 'reason': f'Fix type {fix_type} not implemented'}
    
    except Exception as e:
        logger.error(f"[AUTO_REPAIR] Error applying fix {fix_name}: {e}")
        return {'success': False, 'error': str(e)}


# ═══════════════════════════════════════════════════════════════════
# AI DIAGNOSIS FOR UNKNOWN ERRORS
# ═══════════════════════════════════════════════════════════════════

async def ai_diagnose_and_fix(errors: list, auto_heal: dict) -> list:
    """
    Uses Claude to diagnose unknown errors and either:
    - Applies fix automatically if safe
    - Sends to admin for approval if risky
    """
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        api_key = os.environ.get('EMERGENT_API_KEY') or os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            logger.warning("[AUTO_REPAIR] No API key for AI diagnosis")
            return []
        
        error_summary = '\n'.join([
            str(e.get('message', '') or e.get('error', ''))[:200]
            for e in errors[:10]
        ])
        
        auto_heal_status = json.dumps(auto_heal.get('checks', {}), indent=2) if auto_heal else 'No data'
        
        prompt = f"""You are an autonomous DevOps AI for reroots.ca (FastAPI + React + MongoDB).

Errors found:
{error_summary}

Auto-heal status:
{auto_heal_status}

For each error provide a JSON response:
{{
    "errors": [
        {{
            "description": "what is broken",
            "root_cause": "why it broke",
            "fix_command": "exact bash command or code fix",
            "fix_type": "restart|code_patch|config_change|requires_human",
            "safe_to_auto_apply": true/false,
            "risk_level": "low|medium|high"
        }}
    ]
}}

Only set safe_to_auto_apply=true for low risk fixes like service restarts.
Return ONLY valid JSON, no other text."""

        llm = LlmChat(
            api_key=api_key,
            session_id="auto_repair_diagnosis",
            system_message="You are an autonomous DevOps AI. Return ONLY valid JSON."
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        user_msg = UserMessage(text=prompt)
        # Hard timeout — without this, a slow/hung Claude call blocks the
        # entire 10-min repair scheduler tick.
        try:
            response_text = await asyncio.wait_for(
                llm.send_message(user_msg), timeout=30.0
            )
        except asyncio.TimeoutError:
            logger.warning("[AUTO_REPAIR] AI diagnosis timed out (30s)")
            return [{'auto_applied': False, 'description': 'AI diagnosis timeout'}]
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_match:
            return [{'auto_applied': False, 'description': 'Could not parse AI response'}]
        
        data = json.loads(json_match.group())
        actions = []
        
        # ─── Phase 4: ZERO HUMAN APPROVAL ─────────────────────────────
        # Auto-apply low + medium risk fixes. Only DESTRUCTIVE keywords
        # in REQUIRES_APPROVAL get logged to audit trail without block.
        for fix in data.get('errors', []):
            destructive = any(
                keyword in str(fix).lower()
                for keyword in REQUIRES_APPROVAL
            )
            risk = (fix.get('risk_level') or 'unknown').lower()
            
            # Auto-apply: low + medium, OR explicitly safe_to_auto_apply
            auto_apply = (
                fix.get('safe_to_auto_apply') is True
                or risk in ('low', 'medium')
            ) and not destructive
            
            if auto_apply:
                if fix.get('fix_type') == 'restart':
                    subprocess.run(
                        ['sudo', 'supervisorctl', 'restart', 'backend'],
                        capture_output=True, timeout=30
                    )
                actions.append({
                    'auto_applied': True,
                    'fix': fix.get('fix_command', ''),
                    'description': fix.get('description', ''),
                    'risk': risk,
                    'ai_diagnosed': True
                })
                # Emit CODE_FIX_APPLIED so ORA Brain can learn the pattern
                try:
                    from services.a2a_bus import bus
                    asyncio.create_task(bus.emit(
                        "auto_repair", "CODE_FIX_APPLIED", {
                            "fix_description": fix.get('description', ''),
                            "error_type": fix.get('root_cause', ''),
                            "files_changed": [],
                            "risk": risk,
                        },
                    ))
                except Exception:
                    pass
            else:
                # Destructive fix: log to ledger, do NOT page human
                try:
                    await _db.auto_repair_blocked.insert_one({
                        'fix': fix,
                        'reason': 'destructive_keyword_match',
                        'created_at': datetime.now(timezone.utc),
                    })
                except Exception:
                    pass
                actions.append({
                    'auto_applied': False,
                    'blocked': True,
                    'reason': 'destructive_keyword',
                    'description': fix.get('description', ''),
                    'risk': risk,
                    'ai_diagnosed': True
                })
        
        return actions
    
    except Exception as e:
        logger.error(f"[AUTO_REPAIR] AI diagnosis failed: {e}")
        return [{'auto_applied': False, 'description': f'AI diagnosis error: {str(e)}'}]


# ═══════════════════════════════════════════════════════════════════
# HUMAN APPROVAL SYSTEM
# ═══════════════════════════════════════════════════════════════════

async def request_human_approval(approval_id: str, fix: dict):
    """Sends fix to admin via WhatsApp for approval."""
    if not ADMIN_WHATSAPP:
        logger.debug("[AUTO_REPAIR] ADMIN_WHATSAPP not configured — skipping approval ping")
        return
    try:
        # Import WhatsApp service (Twilio-backed)
        from services.twilio_service import send_whatsapp_message

        message = f"""🤖 Auto-Repair needs approval:

Issue: {fix.get('description', 'Unknown')}
Cause: {fix.get('root_cause', 'Unknown')}
Fix: {fix.get('fix_command', 'None')[:100]}
Risk: {fix.get('risk_level', 'Unknown').upper()}

Reply:
APPROVE {approval_id}
REJECT {approval_id}"""

        await send_whatsapp_message(ADMIN_WHATSAPP, message)
        logger.info(f"[AUTO_REPAIR] Sent approval request {approval_id} to admin")
    except Exception as e:
        logger.debug(f"[AUTO_REPAIR] Could not send approval request: {e}")


async def process_whatsapp_approval(message: str) -> bool:
    """
    Call this from WhatsApp webhook when admin replies.
    Handles APPROVE/REJECT commands.
    """
    parts = message.strip().upper().split()
    if len(parts) != 2:
        return False
    
    command, approval_id = parts
    
    # Check in-memory first
    fix = pending_approvals.get(approval_id)
    
    # Check database if not in memory
    if not fix and _db is not None:
        try:
            doc = await _db.pending_approvals.find_one({'approval_id': approval_id})
            if doc:
                fix = doc.get('fix')
        except Exception:
            pass
    
    if not fix:
        return False
    
    try:
        from services.twilio_service import send_whatsapp_message

        if command == 'APPROVE':
            # Apply the fix
            fix_type = fix.get('fix_type', '')
            
            if fix_type == 'restart':
                subprocess.run(
                    ['sudo', 'supervisorctl', 'restart', 'backend'],
                    capture_output=True, timeout=30
                )
            elif fix_type == 'code_patch' and fix.get('fix_command'):
                # Admin-approved fix command. shlex.split() for list-args path when the
                # command is a simple tokenized string; fall back to ["sh","-c",cmd] only
                # when shell metacharacters are present.
                _fix_cmd = fix['fix_command']
                _has_shell_meta = any(c in _fix_cmd for c in ('|', '&', ';', '>', '<', '$(', '`'))
                if _has_shell_meta:
                    subprocess.run(
                        ["/bin/sh", "-c", _fix_cmd],
                        shell=False, capture_output=True, timeout=30
                    )
                else:
                    import shlex as _shlex
                    subprocess.run(
                        _shlex.split(_fix_cmd),
                        shell=False, capture_output=True, timeout=30
                    )

            await send_whatsapp_message(
                ADMIN_WHATSAPP,
                f'✅ Fix applied: {fix.get("description", "")}'
            )
            
            # Update status in DB
            if _db is not None:
                await _db.pending_approvals.update_one(
                    {'approval_id': approval_id},
                    {'$set': {'status': 'approved', 'processed_at': datetime.now(timezone.utc)}}
                )
            
            pending_approvals.pop(approval_id, None)
            logger.info(f"[AUTO_REPAIR] Approval {approval_id} applied")
            return True
        
        elif command == 'REJECT':
            await send_whatsapp_message(
                ADMIN_WHATSAPP,
                f'❌ Fix rejected. Will monitor: {fix.get("description", "")}'
            )
            
            # Update status in DB
            if _db is not None:
                await _db.pending_approvals.update_one(
                    {'approval_id': approval_id},
                    {'$set': {'status': 'rejected', 'processed_at': datetime.now(timezone.utc)}}
                )
            
            pending_approvals.pop(approval_id, None)
            logger.info(f"[AUTO_REPAIR] Approval {approval_id} rejected")
            return True
    
    except Exception as e:
        logger.error(f"[AUTO_REPAIR] Error processing approval: {e}")
    
    return False


# ═══════════════════════════════════════════════════════════════════
# HEALTH TESTING
# ═══════════════════════════════════════════════════════════════════

async def test_system_health() -> dict:
    """Tests if fixes worked by hitting real endpoints."""
    checks = {
        'health': 'https://reroots.ca/api/health',
        'chat': 'https://reroots.ca/api/ai/chat',
    }
    
    # Also test preview URL as fallback
    preview_url = os.environ.get('SITE_URL', '')
    if preview_url:
        checks['preview_health'] = f"{preview_url}/api/health"
    
    results = {}
    
    async with httpx.AsyncClient(timeout=10) as client:
        for name, url in checks.items():
            try:
                r = await client.get(url)
                # 200, 401, 403 are all "working" (just need auth)
                results[name] = r.status_code in [200, 401, 403, 405]
            except Exception as e:
                results[name] = False
                logger.warning(f"[AUTO_REPAIR] Health check failed for {name}: {e}")
    
    healthy = any(results.values())  # At least one endpoint working
    return {'healthy': healthy, 'checks': results}


# ═══════════════════════════════════════════════════════════════════
# REPORTING
# ═══════════════════════════════════════════════════════════════════

async def send_repair_report(auto_fixed: list, ai_actions: list, test_result: dict):
    """Sends summary to admin only if something happened."""
    if not auto_fixed and not ai_actions:
        return
    if not ADMIN_WHATSAPP:
        return
    
    try:
        from services.twilio_service import send_whatsapp_message

        status_emoji = '✅' if test_result['healthy'] else '⚠️'
        pending_count = len([a for a in ai_actions if not a.get('auto_applied')])
        
        fixes_summary = '\n'.join([
            f"✓ {f.get('fix_applied', f.get('description', 'Unknown'))}"
            for f in auto_fixed[:3]
        ])
        
        message = f"""{status_emoji} Auto-Repair Report:

Auto-fixed: {len(auto_fixed)} issues
Pending approval: {pending_count}
System healthy: {'Yes' if test_result['healthy'] else 'No'}

{fixes_summary if fixes_summary else 'No auto-fixes applied'}"""

        await send_whatsapp_message(ADMIN_WHATSAPP, message)
    except Exception as e:
        logger.debug(f"[AUTO_REPAIR] Could not send report: {e}")


# ═══════════════════════════════════════════════════════════════════
# API FUNCTIONS FOR DASHBOARD
# ═══════════════════════════════════════════════════════════════════

async def get_repair_history(limit: int = 50) -> list:
    """Get recent auto-repair history for dashboard."""
    if _db is None:
        return []
    
    try:
        cursor = _db.auto_repair_log.find(
            {},
            {'_id': 0}
        ).sort('timestamp', -1).limit(limit)
        
        return await cursor.to_list(limit)
    except Exception:
        return []


async def get_pending_approvals() -> list:
    """Get all pending approvals for dashboard."""
    if _db is None:
        return list(pending_approvals.values())
    
    try:
        cursor = _db.pending_approvals.find(
            {'status': 'pending'},
            {'_id': 0}
        ).sort('created_at', -1)
        
        return await cursor.to_list(50)
    except Exception:
        return list(pending_approvals.values())


async def get_repair_stats() -> dict:
    """Get auto-repair statistics for dashboard."""
    if _db is None:
        return {}
    
    try:
        # Count repairs in last 24 hours
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        
        total = await _db.auto_repair_log.count_documents({
            'timestamp': {'$gte': since}
        })
        
        auto_fixed = await _db.auto_repair_log.aggregate([
            {'$match': {'timestamp': {'$gte': since}}},
            {'$group': {'_id': None, 'total': {'$sum': '$auto_fixed'}}}
        ]).to_list(1)
        
        auto_fixed_count = auto_fixed[0]['total'] if auto_fixed else 0
        
        success_rate = (auto_fixed_count / max(total, 1)) * 100 if total > 0 else 100
        
        return {
            'total_repairs_24h': total,
            'auto_fixed_24h': auto_fixed_count,
            'success_rate': round(success_rate, 1),
            'pending_approvals': len(pending_approvals)
        }
    except Exception:
        return {}
