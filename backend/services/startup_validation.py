"""
AUREM Startup Validation
Ensures critical services are available before server starts
Prevents broken deployments
"""

import os
import logging
from typing import Dict, List, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class StartupValidator:
    """
    Validates critical services and configuration on startup
    Server refuses to start if validation fails
    """
    
    def __init__(self, db=None):
        self.db = db
        self.errors = []
        self.warnings = []
        self.checks = []
    
    async def validate_all(self) -> Dict[str, Any]:
        """
        Run all validation checks
        
        Returns:
            dict with success status, errors, warnings
        """
        logger.info("[STARTUP] Running validation checks...")
        
        # Critical checks (must pass)
        await self._check_mongodb()
        await self._check_environment_variables()
        await self._check_filesystem()
        
        # Warning checks (can fail but log warning)
        await self._check_optional_services()
        await self._check_api_keys()
        
        success = len(self.errors) == 0
        
        if success:
            logger.info(f"[STARTUP] ✅ All validation checks passed ({len(self.checks)} checks)")
        else:
            logger.error(f"[STARTUP] ❌ Validation failed with {len(self.errors)} errors")
            for error in self.errors:
                logger.error(f"  - {error}")
        
        if self.warnings:
            logger.warning(f"[STARTUP] ⚠️  {len(self.warnings)} warnings:")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")
        
        return {
            "success": success,
            "errors": self.errors,
            "warnings": self.warnings,
            "checks": self.checks,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def _check_mongodb(self):
        """Check MongoDB connection"""
        check_name = "MongoDB Connection"
        try:
            # IMPORTANT: Use `is None` instead of `not db` to avoid PyMongo NotImplementedError
            if self.db is None:
                self.errors.append(f"{check_name}: Database not initialized")
                return
            
            # Ping database
            await self.db.command('ping')
            
            # Check collections exist
            collections = await self.db.list_collection_names()
            
            self.checks.append({
                "name": check_name,
                "status": "pass",
                "collections": len(collections)
            })
            
        except Exception as e:
            self.errors.append(f"{check_name}: {str(e)}")
            self.checks.append({
                "name": check_name,
                "status": "fail",
                "error": str(e)
            })
    
    async def _check_environment_variables(self):
        """Check required environment variables"""
        check_name = "Environment Variables"
        
        # Critical variables
        critical_vars = [
            "JWT_SECRET",
            "MONGO_URL",
        ]
        
        # Important but not critical
        important_vars = [
            "EMERGENT_LLM_KEY",
        ]
        
        missing_critical = []
        missing_important = []
        
        for var in critical_vars:
            if not os.environ.get(var):
                missing_critical.append(var)
        
        for var in important_vars:
            if not os.environ.get(var):
                missing_important.append(var)
        
        if missing_critical:
            self.errors.append(f"{check_name}: Missing critical vars: {', '.join(missing_critical)}")
            self.checks.append({
                "name": check_name,
                "status": "fail",
                "missing_critical": missing_critical
            })
        else:
            self.checks.append({
                "name": check_name,
                "status": "pass",
                "vars_checked": len(critical_vars)
            })
        
        if missing_important:
            self.warnings.append(f"Missing important env vars: {', '.join(missing_important)}")
    
    async def _check_filesystem(self):
        """Check filesystem permissions"""
        check_name = "Filesystem"
        
        try:
            # Check if we can write to logs
            test_paths = [
                "/var/log/supervisor",
                "/app/backend",
            ]
            
            writable = []
            for path in test_paths:
                if os.path.exists(path) and os.access(path, os.W_OK):
                    writable.append(path)
            
            self.checks.append({
                "name": check_name,
                "status": "pass",
                "writable_paths": len(writable)
            })
            
        except Exception as e:
            self.warnings.append(f"{check_name}: {str(e)}")
    
    async def _check_optional_services(self):
        """Check optional services availability"""
        check_name = "Optional Services"
        
        services = []
        
        # Check Redis (optional) — use shared pool so we don't leak a client
        try:
            from utils.redis_pool import get_sync_redis
            if os.environ.get("REDIS_URL"):
                r = get_sync_redis()
                if r is not None:
                    r.ping()
                    services.append("redis")
        except Exception:
            pass
        
        self.checks.append({
            "name": check_name,
            "status": "pass",
            "available": services
        })
    
    async def _check_api_keys(self):
        """Check API key configuration"""
        check_name = "API Keys"
        
        configured_keys = []
        missing_keys = []
        
        api_keys = {
            "EMERGENT_LLM_KEY": "AI Chat",
            "STRIPE_API_KEY": "Payments",
            "EMERGENT_LLM_KEY": "Voice AI + LLM",
        }
        
        for key, service in api_keys.items():
            if os.environ.get(key):
                configured_keys.append(service)
            else:
                missing_keys.append(service)
        
        if missing_keys:
            self.warnings.append(f"Missing API keys for: {', '.join(missing_keys)}")
        
        self.checks.append({
            "name": check_name,
            "status": "pass",
            "configured": configured_keys,
            "missing": missing_keys
        })


async def run_startup_validation(db=None) -> bool:
    """
    Run startup validation
    
    Returns:
        bool: True if validation passed, False otherwise
    """
    validator = StartupValidator(db)
    result = await validator.validate_all()
    
    # Send notification if failed (if possible)
    if not result["success"]:
        try:
            await _send_failure_notification(result)
        except Exception as e:
            logger.error(f"Failed to send startup failure notification: {e}")
    
    return result["success"]


async def _send_failure_notification(result: Dict[str, Any]):
    """Send notification about startup failure.

    iter 322ar — was a TODO. Now writes a `founder_notifications` row +
    sends an email to FOUNDER_EMAIL via Resend (best-effort, never raises)."""
    logger.error("[STARTUP] ❌ CRITICAL: Server startup validation failed")
    logger.error(f"[STARTUP] Errors: {result.get('errors')}")
    try:
        import motor.motor_asyncio
        from datetime import datetime, timezone
        url = os.environ.get("MONGO_URL", "")
        dbn = os.environ.get("DB_NAME", "aurem_db")
        if url:
            db = motor.motor_asyncio.AsyncIOMotorClient(url)[dbn]
            await db.founder_notifications.insert_one({
                "type": "startup_validation_failed",
                "severity": "critical",
                "errors": result.get("errors", []),
                "warnings": result.get("warnings", []),
                "ts": datetime.now(timezone.utc),
                "read": False,
            })
    except Exception as e:
        logger.warning(f"[STARTUP] founder_notifications write failed: {e}")
    # Best-effort email to founder via Resend
    try:
        import resend
        api_key = os.environ.get("RESEND_API_KEY", "")
        to_addr = os.environ.get("FOUNDER_EMAIL", "")
        if api_key and to_addr:
            resend.api_key = api_key
            errs = "<br>".join(f"• {e}" for e in result.get("errors", [])[:10]) or "(no errors listed)"
            resend.Emails.send({
                "from": os.environ.get("RESEND_FROM_EMAIL", "ORA <ora@aurem.live>"),
                "to": [to_addr],
                "subject": "AUREM ❌ Startup validation FAILED",
                "html": (
                    "<h2 style=\"color:#EF4444\">Startup validation failed</h2>"
                    f"<p>Errors:</p><div style=\"font-family:monospace\">{errs}</div>"
                    "<p style=\"color:#6A6070;font-size:12px\">AUREM Sovereign · Polaris Built Inc.</p>"
                ),
            })
    except Exception as e:
        logger.warning(f"[STARTUP] founder email send failed: {e}")
