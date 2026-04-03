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
            if not self.db:
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
            "REACT_APP_BACKEND_URL",
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
        
        # Check Redis (optional)
        try:
            import redis
            redis_url = os.environ.get("REDIS_URL")
            if redis_url:
                r = redis.from_url(redis_url)
                r.ping()
                services.append("redis")
        except:
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
            "VAPI_API_KEY": "Voice AI",
            "OMNIDIMENSION_API_KEY": "OmniDimension",
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
    """Send notification about startup failure"""
    # TODO: Integrate with WhatsApp/Email when configured
    logger.error(f"[STARTUP] ❌ CRITICAL: Server startup validation failed")
    logger.error(f"[STARTUP] Errors: {result['errors']}")
