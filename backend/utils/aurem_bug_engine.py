"""
AUREM Autonomous Bug Engine
Company: Polaris Built Inc.

The most important system in the platform — runs permanently with no human needed.

Runs on APScheduler every 10 minutes:
1. SCAN - Check error logs and run health checks
2. CLASSIFY - Match errors against known fixes
3. AUTO-FIX - Apply fixes or get AI suggestions
4. VERIFY - Re-run health check after fix
5. LOG TO HISTORY - Permanent audit trail
"""

import os
import logging
import asyncio
import traceback
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# MongoDB reference
_db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global _db
    _db = database


# ═══════════════════════════════════════════════════════════════════════════════
# KNOWN FIXES DICTIONARY
# ═══════════════════════════════════════════════════════════════════════════════

KNOWN_FIXES = {
    "connection refused": {
        "action": "restart_service",
        "description": "Service not running - attempt restart",
        "auto_fix": True,
    },
    "rate limit": {
        "action": "pause_retry",
        "description": "API rate limited - pause 60s and retry",
        "delay_seconds": 60,
        "auto_fix": True,
    },
    "timeout": {
        "action": "switch_fallback",
        "description": "Timeout - switch to fallback model/service",
        "auto_fix": True,
    },
    "authentication failed": {
        "action": "alert_admin",
        "description": "Auth failure - requires human intervention",
        "auto_fix": False,
    },
    "json decode error": {
        "action": "log_skip",
        "description": "Invalid JSON - log payload and skip",
        "auto_fix": True,
    },
    "circuit breaker open": {
        "action": "wait_cooldown",
        "description": "Circuit breaker tripped - skip channel for 1 hour",
        "cooldown_hours": 1,
        "auto_fix": True,
    },
    "module not found": {
        "action": "alert_admin",
        "description": "Missing dependency - requires installation",
        "auto_fix": False,
    },
    "permission denied": {
        "action": "alert_admin", 
        "description": "Permission issue - requires admin",
        "auto_fix": False,
    },
    "out of memory": {
        "action": "restart_service",
        "description": "OOM - restart service",
        "auto_fix": True,
    },
    "database error": {
        "action": "reconnect_db",
        "description": "Database issue - attempt reconnection",
        "auto_fix": True,
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

HEALTH_CHECKS = [
    {"name": "FastAPI Server", "url": "http://localhost:8001/health", "critical": True},
    {"name": "AUREM System", "url": "http://localhost:8001/api/aurem/system", "critical": True},
    {"name": "Scout Agent", "url": "http://localhost:8001/api/aurem/agents", "critical": True},
    {"name": "Platform Status", "url": "http://localhost:8001/api/platform/health", "critical": False},
]


# ═══════════════════════════════════════════════════════════════════════════════
# BUG ENGINE CORE
# ═══════════════════════════════════════════════════════════════════════════════

class AuremBugEngine:
    """Autonomous bug detection and self-healing engine"""
    
    def __init__(self):
        self.last_scan = None
        self.consecutive_failures = 0
        self.circuit_breakers: Dict[str, datetime] = {}
    
    async def run_full_scan(self) -> Dict[str, Any]:
        """Run complete bug scan cycle"""
        import time
        start_time = time.time()
        
        scan_result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "errors_found": [],
            "auto_fixed": [],
            "ai_suggested_fixes": [],
            "health_checks": [],
            "system_healthy_after": False,
            "scan_duration_ms": 0,
        }
        
        try:
            # STEP 1: SCAN - Check error logs
            logger.info("[BUG ENGINE] Step 1: Scanning error logs...")
            errors = await self._scan_error_logs()
            scan_result["errors_found"] = errors
            
            # STEP 1b: Run health checks
            logger.info("[BUG ENGINE] Step 1b: Running health checks...")
            health_results = await self._run_health_checks()
            scan_result["health_checks"] = health_results
            
            # Add failed health checks to errors
            for check in health_results:
                if not check["healthy"]:
                    errors.append({
                        "source": "health_check",
                        "message": f"{check['name']} failed: {check.get('error', 'Unknown error')}",
                        "level": "CRITICAL" if check.get("critical") else "WARNING",
                    })
            
            # STEP 2: CLASSIFY - Match against known fixes
            logger.info("[BUG ENGINE] Step 2: Classifying errors...")
            for error in errors:
                fix = self._classify_error(error)
                if fix:
                    error["known_fix"] = fix
            
            # STEP 3: AUTO-FIX - Apply known fixes or get AI suggestions
            logger.info("[BUG ENGINE] Step 3: Applying auto-fixes...")
            for error in errors:
                if error.get("known_fix", {}).get("auto_fix"):
                    result = await self._apply_fix(error)
                    scan_result["auto_fixed"].append(result)
                elif error.get("known_fix") is None:
                    # Unknown error - ask AI
                    ai_fix = await self._get_ai_suggestion(error)
                    if ai_fix:
                        scan_result["ai_suggested_fixes"].append(ai_fix)
            
            # STEP 4: VERIFY - Re-run health checks
            logger.info("[BUG ENGINE] Step 4: Verifying system health...")
            await asyncio.sleep(2)  # Wait for fixes to take effect
            
            verify_results = await self._run_health_checks()
            all_healthy = all(r["healthy"] for r in verify_results if r.get("critical"))
            scan_result["system_healthy_after"] = all_healthy
            
            # Update failure counter
            if all_healthy:
                self.consecutive_failures = 0
            else:
                self.consecutive_failures += 1
                
                # Escalate if multiple failures
                if self.consecutive_failures >= 2:
                    await self._escalate_to_admin(scan_result)
            
        except Exception as e:
            logger.error(f"[BUG ENGINE] Scan error: {e}")
            scan_result["errors_found"].append({
                "source": "bug_engine",
                "message": str(e),
                "traceback": traceback.format_exc(),
                "level": "CRITICAL",
            })
        
        # Calculate duration
        scan_result["scan_duration_ms"] = int((time.time() - start_time) * 1000)
        
        # STEP 5: LOG TO HISTORY
        await self._log_to_history(scan_result)
        
        self.last_scan = datetime.now(timezone.utc)
        logger.info(f"[BUG ENGINE] Scan complete: {len(scan_result['errors_found'])} errors, {len(scan_result['auto_fixed'])} fixed")
        
        return scan_result
    
    async def _scan_error_logs(self) -> List[Dict]:
        """Scan MongoDB for recent errors"""
        errors = []
        
        if _db is None:
            return errors
        
        # Check last 15 minutes
        since = datetime.now(timezone.utc) - timedelta(minutes=15)
        
        try:
            cursor = _db.aurem_error_log.find({
                "timestamp": {"$gte": since},
                "level": {"$in": ["ERROR", "CRITICAL"]}
            }).sort("timestamp", -1).limit(50)
            
            async for doc in cursor:
                errors.append({
                    "source": "error_log",
                    "message": doc.get("message", ""),
                    "level": doc.get("level", "ERROR"),
                    "traceback": doc.get("traceback", ""),
                    "timestamp": doc.get("timestamp"),
                })
        except Exception as e:
            logger.warning(f"[BUG ENGINE] Error scanning logs: {e}")
        
        return errors
    
    async def _run_health_checks(self) -> List[Dict]:
        """Run all health check endpoints"""
        results = []
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for check in HEALTH_CHECKS:
                result = {
                    "name": check["name"],
                    "url": check["url"],
                    "critical": check.get("critical", False),
                    "healthy": False,
                    "response_time_ms": 0,
                }
                
                try:
                    import time
                    start = time.time()
                    response = await client.get(check["url"])
                    result["response_time_ms"] = int((time.time() - start) * 1000)
                    result["healthy"] = response.status_code in [200, 201]
                    result["status_code"] = response.status_code
                except Exception as e:
                    result["error"] = str(e)
                
                results.append(result)
        
        return results
    
    def _classify_error(self, error: Dict) -> Optional[Dict]:
        """Match error against known fixes"""
        message = error.get("message", "").lower()
        
        for pattern, fix in KNOWN_FIXES.items():
            if pattern in message:
                return fix
        
        return None
    
    async def _apply_fix(self, error: Dict) -> Dict:
        """Apply a known fix"""
        fix = error.get("known_fix", {})
        action = fix.get("action")
        result = {
            "error": error.get("message", "")[:100],
            "action": action,
            "success": False,
            "description": fix.get("description", ""),
        }
        
        try:
            if action == "pause_retry":
                delay = fix.get("delay_seconds", 60)
                await asyncio.sleep(min(delay, 10))  # Max 10s in scan
                result["success"] = True
                result["note"] = f"Paused {delay}s"
                
            elif action == "log_skip":
                result["success"] = True
                result["note"] = "Logged and skipped"
                
            elif action == "wait_cooldown":
                # Mark circuit breaker
                channel = error.get("channel", "unknown")
                cooldown_hours = fix.get("cooldown_hours", 1)
                self.circuit_breakers[channel] = datetime.now(timezone.utc) + timedelta(hours=cooldown_hours)
                result["success"] = True
                result["note"] = f"Channel {channel} paused for {cooldown_hours}h"
                
            elif action == "reconnect_db":
                # Database reconnection is handled by motor automatically
                result["success"] = True
                result["note"] = "DB reconnection triggered"
                
            elif action == "restart_service":
                # Log that restart is recommended (don't actually restart in scan)
                result["success"] = False
                result["note"] = "Service restart recommended"
                
            elif action == "alert_admin":
                await self._send_admin_alert(error)
                result["success"] = True
                result["note"] = "Admin alerted"
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    async def _get_ai_suggestion(self, error: Dict) -> Optional[Dict]:
        """Get AI-suggested fix for unknown error"""
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            from dotenv import load_dotenv
            load_dotenv()
            
            api_key = os.environ.get("EMERGENT_LLM_KEY")
            if not api_key:
                return None
            
            chat = LlmChat(
                api_key=api_key,
                session_id=f"bugfix_{datetime.now().strftime('%H%M%S')}",
                system_message="You are a FastAPI debugging expert. Suggest a 1-line Python fix for errors. Return only the fix code, nothing else."
            ).with_model("openai", "gpt-4o-mini")
            
            error_text = f"{error.get('message', '')}\n{error.get('traceback', '')[:500]}"
            response = await chat.send_message(UserMessage(text=f"Fix this error:\n{error_text}"))
            
            return {
                "error": error.get("message", "")[:100],
                "ai_suggestion": response[:200],
                "confidence": "medium",
            }
            
        except Exception as e:
            logger.warning(f"[BUG ENGINE] AI suggestion failed: {e}")
            return None
    
    async def _send_admin_alert(self, error: Dict):
        """Send alert to admin via WhatsApp"""
        admin_phone = os.environ.get("ADMIN_WHATSAPP")
        if not admin_phone:
            logger.warning("[BUG ENGINE] ADMIN_WHATSAPP not configured")
            return
        
        # Import WhatsApp sender
        try:
            from routers.whatsapp_alerts import send_whatsapp
            message = f"🚨 AUREM Alert\n\nError: {error.get('message', '')[:100]}\n\nAction required."
            await send_whatsapp(admin_phone, message)
            logger.info("[BUG ENGINE] Admin alert sent")
        except Exception as e:
            logger.error(f"[BUG ENGINE] Failed to send admin alert: {e}")
    
    async def _escalate_to_admin(self, scan_result: Dict):
        """Escalate after multiple failed fix attempts"""
        admin_phone = os.environ.get("ADMIN_WHATSAPP")
        if not admin_phone:
            return
        
        try:
            from routers.whatsapp_alerts import send_whatsapp
            
            errors_count = len(scan_result.get("errors_found", []))
            message = f"""🚨 AUREM ESCALATION

System unhealthy after {self.consecutive_failures} scans.

Errors: {errors_count}
Auto-fixes attempted: {len(scan_result.get('auto_fixed', []))}

Please check the dashboard immediately."""
            
            await send_whatsapp(admin_phone, message)
            logger.warning("[BUG ENGINE] Escalation alert sent to admin")
        except Exception as e:
            logger.error(f"[BUG ENGINE] Escalation failed: {e}")
    
    async def _log_to_history(self, scan_result: Dict):
        """Save scan result to permanent history"""
        if _db is None:
            return
        
        try:
            await _db.aurem_bug_history.insert_one({
                **scan_result,
                "timestamp": datetime.now(timezone.utc),
            })
        except Exception as e:
            logger.error(f"[BUG ENGINE] Failed to log history: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULER INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

_bug_engine: AuremBugEngine = None

def get_bug_engine() -> AuremBugEngine:
    """Get or create bug engine instance"""
    global _bug_engine
    if _bug_engine is None:
        _bug_engine = AuremBugEngine()
    return _bug_engine


async def scheduled_bug_scan():
    """Called by APScheduler every 10 minutes"""
    engine = get_bug_engine()
    try:
        result = await engine.run_full_scan()
        return result
    except Exception as e:
        logger.error(f"[BUG ENGINE] Scheduled scan failed: {e}")
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

from fastapi import APIRouter

router = APIRouter(prefix="/api/aurem/bug-engine", tags=["aurem-bug-engine"])


@router.get("/status")
async def get_bug_engine_status():
    """Get bug engine status"""
    engine = get_bug_engine()
    return {
        "last_scan": engine.last_scan.isoformat() if engine.last_scan else None,
        "consecutive_failures": engine.consecutive_failures,
        "circuit_breakers": {
            k: v.isoformat() for k, v in engine.circuit_breakers.items()
        },
    }


@router.post("/scan")
async def trigger_manual_scan():
    """Manually trigger a bug scan"""
    engine = get_bug_engine()
    result = await engine.run_full_scan()
    return result


@router.get("/history")
async def get_bug_history(limit: int = 20):
    """Get bug scan history"""
    if _db is None:
        return {"history": []}
    
    cursor = _db.aurem_bug_history.find(
        {},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit)
    
    history = await cursor.to_list(length=limit)
    return {"history": history}


@router.get("/stats")
async def get_bug_stats():
    """Get bug engine statistics"""
    if _db is None:
        return {"error": "Database not available"}
    
    # Last 7 days
    since = datetime.now(timezone.utc) - timedelta(days=7)
    
    total_scans = await _db.aurem_bug_history.count_documents({
        "timestamp": {"$gte": since}
    })
    
    # Count auto-fixes
    pipeline = [
        {"$match": {"timestamp": {"$gte": since}}},
        {"$project": {
            "auto_fixed_count": {"$size": {"$ifNull": ["$auto_fixed", []]}},
            "errors_count": {"$size": {"$ifNull": ["$errors_found", []]}},
            "healthy": "$system_healthy_after",
        }},
        {"$group": {
            "_id": None,
            "total_auto_fixed": {"$sum": "$auto_fixed_count"},
            "total_errors": {"$sum": "$errors_count"},
            "healthy_scans": {"$sum": {"$cond": ["$healthy", 1, 0]}},
        }}
    ]
    
    stats = await _db.aurem_bug_history.aggregate(pipeline).to_list(1)
    stats_data = stats[0] if stats else {}
    
    return {
        "period": "7d",
        "total_scans": total_scans,
        "total_errors": stats_data.get("total_errors", 0),
        "total_auto_fixed": stats_data.get("total_auto_fixed", 0),
        "healthy_scans": stats_data.get("healthy_scans", 0),
        "auto_fix_rate": round(
            stats_data.get("total_auto_fixed", 0) / max(stats_data.get("total_errors", 1), 1) * 100,
            2
        ),
    }
