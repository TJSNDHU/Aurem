"""
Auto-Heal Monitor for reroots.ca
Self-healing system that monitors and automatically fixes common issues:
- Backend health
- Frontend serving
- Redis connection
- MongoDB connection
- Scheduler jobs
- Emergent credits / response time monitoring

Runs every 5 minutes via background task.
Logs all actions to MongoDB auto_heal_log collection.
Sends WhatsApp alerts to admin for critical issues.
"""

import os
import subprocess
import logging
import asyncio
import httpx
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

# MongoDB client
_db = None

# Admin phone for alerts (Tj's number)
ADMIN_WHATSAPP = os.environ.get("ADMIN_WHATSAPP", "+14168869408")

# Backend URL - use localhost since we're running on the same server
BACKEND_URL = "http://localhost:8001"
FRONTEND_URL = "http://localhost:3000"

# External URL for response time monitoring (Emergent credits proxy)
EXTERNAL_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://reroots.ca")

# Expected scheduler job names (the 7 background tasks we start)
EXPECTED_SCHEDULERS = [
    "daily_digest_scheduler",
    "abandoned_cart_scheduler",
    "operational_alerts_scheduler",
    "day21_review_scheduler",
    "whatsapp_crm_scheduler",
    "birthday_bonus_scheduler",
    "auto_heal_scheduler",
]

# Response time thresholds (in seconds)
RESPONSE_TIME_WARNING = 5.0  # Warn if > 5 seconds
RESPONSE_TIME_CRITICAL = 10.0  # Critical if > 10 seconds

logger = logging.getLogger(__name__)


def set_db(database):
    """Set database reference for auto_heal module"""
    global _db
    _db = database


async def send_alert_whatsapp(message: str) -> bool:
    """Send WhatsApp alert to admin via Twilio service"""
    try:
        from services.twilio_service import send_whatsapp_message
        result = await send_whatsapp_message(ADMIN_WHATSAPP, message)
        return result.get("success", False)
    except Exception as e:
        logger.error(f"[AUTO_HEAL] Failed to send WhatsApp alert: {e}")
        return False


async def log_auto_heal_action(
    check_name: str,
    issue_found: str,
    action_taken: str,
    resolved: bool
) -> None:
    """Log auto-heal action to MongoDB"""
    if _db is None:
        logger.warning("[AUTO_HEAL] Database not available for logging")
        return
    
    try:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "check_name": check_name,
            "issue_found": issue_found,
            "action_taken": action_taken,
            "resolved": resolved
        }
        await _db.auto_heal_log.insert_one(log_entry)
        logger.info(f"[AUTO_HEAL] Logged: {check_name} - {action_taken} - resolved={resolved}")
    except Exception as e:
        logger.error(f"[AUTO_HEAL] Failed to log action: {e}")


async def check_backend_health() -> Dict[str, Any]:
    """
    Check 1: Backend health check
    GET /api/health - if not {"status":"ok"}, restart FastAPI
    """
    check_name = "backend_health"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{BACKEND_URL}/api/health")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    return {"check": check_name, "status": "healthy", "action_taken": None}
            
            # Health check failed - attempt restart
            issue = f"Backend health check failed: status={response.status_code}"
            action = "Attempted supervisorctl restart of backend"
            
            try:
                # Use subprocess to restart via supervisor (no sudo in Emergent)
                result = subprocess.run(
                    ["supervisorctl", "restart", "backend"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                resolved = result.returncode == 0
                
                # Log and alert
                await log_auto_heal_action(check_name, issue, action, resolved)
                
                if not resolved:
                    await send_alert_whatsapp(f"Auto-heal: Backend restart attempted at {datetime.now(timezone.utc).strftime('%H:%M UTC')}")
                
                return {
                    "check": check_name,
                    "status": "fixed" if resolved else "attempted",
                    "issue": issue,
                    "action_taken": action,
                    "resolved": resolved
                }
            except Exception as restart_error:
                logger.error(f"[AUTO_HEAL] Backend restart failed: {restart_error}")
                await log_auto_heal_action(check_name, issue, f"Restart failed: {restart_error}", False)
                return {"check": check_name, "status": "attempted", "issue": issue, "error": str(restart_error)}
                
    except httpx.ConnectError:
        issue = "Backend connection refused - service may be down"
        action = "Attempted supervisorctl restart of backend"
        
        try:
            result = subprocess.run(
                ["supervisorctl", "restart", "backend"],
                capture_output=True,
                text=True,
                timeout=30
            )
            resolved = result.returncode == 0
            
            await log_auto_heal_action(check_name, issue, action, resolved)
            await send_alert_whatsapp(f"Auto-heal: Backend restart {'succeeded' if resolved else 'attempted'} at {datetime.now(timezone.utc).strftime('%H:%M UTC')}")
            
            return {"check": check_name, "status": "fixed" if resolved else "attempted", "issue": issue, "resolved": resolved}
        except Exception as e:
            await log_auto_heal_action(check_name, issue, f"Restart failed: {e}", False)
            return {"check": check_name, "status": "failed", "issue": issue, "error": str(e)}
            
    except Exception as e:
        logger.error(f"[AUTO_HEAL] Backend health check error: {e}")
        return {"check": check_name, "status": "error", "error": str(e)}


async def check_frontend_serving() -> Dict[str, Any]:
    """
    Check 2: Frontend serving
    GET / - if non-200, restart frontend via supervisor (no sudo needed in Emergent)
    """
    check_name = "frontend_serving"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(FRONTEND_URL)
            
            if response.status_code == 200:
                return {"check": check_name, "status": "healthy", "action_taken": None}
            
            # Frontend not serving properly
            issue = f"Frontend returned status {response.status_code}"
            action = "Attempted supervisorctl restart of frontend"
            
            try:
                # Use supervisorctl directly (no sudo in Emergent container)
                result = subprocess.run(
                    ["supervisorctl", "restart", "frontend"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                resolved = result.returncode == 0
                
                await log_auto_heal_action(check_name, issue, action, resolved)
                if not resolved:
                    await send_alert_whatsapp(f"Auto-heal: Frontend restart attempted at {datetime.now(timezone.utc).strftime('%H:%M UTC')}")
                
                return {"check": check_name, "status": "fixed" if resolved else "attempted", "issue": issue, "resolved": resolved}
            except Exception as e:
                await log_auto_heal_action(check_name, issue, f"Restart failed: {e}", False)
                return {"check": check_name, "status": "attempted", "issue": issue, "error": str(e)}
                
    except httpx.ConnectError:
        # Frontend may still be accessible via external URL even if localhost fails
        # Try checking external URL before attempting restart
        try:
            site_url = os.environ.get("SITE_URL", "https://reroots.ca")
            async with httpx.AsyncClient(timeout=10.0) as client:
                ext_response = await client.get(site_url)
                if ext_response.status_code == 200:
                    return {
                        "check": check_name, 
                        "status": "healthy", 
                        "note": "Serving via external URL (localhost unavailable)",
                        "action_taken": None
                    }
        except:
            pass
        
        # Actually down - attempt restart
        issue = "Frontend connection refused - service may be down"
        action = "Attempted supervisorctl restart of frontend"
        
        try:
            result = subprocess.run(
                ["supervisorctl", "restart", "frontend"],
                capture_output=True,
                text=True,
                timeout=30
            )
            resolved = result.returncode == 0
            
            await log_auto_heal_action(check_name, issue, action, resolved)
            await send_alert_whatsapp(f"Auto-heal: Frontend restart {'succeeded' if resolved else 'attempted'} at {datetime.now(timezone.utc).strftime('%H:%M UTC')}")
            
            return {"check": check_name, "status": "fixed" if resolved else "attempted", "issue": issue, "resolved": resolved}
        except Exception as e:
            await log_auto_heal_action(check_name, issue, f"Restart failed: {e}", False)
            return {"check": check_name, "status": "attempted", "issue": issue, "error": str(e)}
            
    except Exception as e:
        logger.error(f"[AUTO_HEAL] Frontend check error: {e}")
        return {"check": check_name, "status": "error", "error": str(e)}


async def check_redis_connection() -> Dict[str, Any]:
    """
    Check 3: Redis connection
    Ping Redis - if fails, log error and send WhatsApp alert
    (Redis Cloud is external, we cannot restart it)
    """
    check_name = "redis_connection"
    
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return {"check": check_name, "status": "skipped", "reason": "REDIS_URL not configured"}
    
    try:
        import redis.asyncio as aioredis
        
        redis_client = await aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5
        )
        
        # Ping Redis
        await redis_client.ping()
        await redis_client.close()
        
        return {"check": check_name, "status": "healthy", "action_taken": None}
        
    except Exception as e:
        issue = f"Redis connection failed: {e}"
        action = "Logged error and sent WhatsApp alert (Redis Cloud is external)"
        
        logger.error(f"[AUTO_HEAL] {issue}")
        await log_auto_heal_action(check_name, issue, action, False)
        
        # Send alert - we can't fix external Redis
        await send_alert_whatsapp(f"Auto-heal ALERT: Redis connection failed at {datetime.now(timezone.utc).strftime('%H:%M UTC')}. Error: {str(e)[:100]}")
        
        return {
            "check": check_name,
            "status": "alerted",
            "issue": issue,
            "action_taken": action,
            "resolved": False
        }


async def check_mongodb_connection() -> Dict[str, Any]:
    """
    Check 4: MongoDB connection
    Ping MongoDB - if fails, send WhatsApp alert immediately
    """
    check_name = "mongodb_connection"
    
    if _db is None:
        issue = "Database reference not set"
        await send_alert_whatsapp(f"Auto-heal CRITICAL: MongoDB database reference not available at {datetime.now(timezone.utc).strftime('%H:%M UTC')}")
        return {"check": check_name, "status": "failed", "issue": issue}
    
    try:
        # Ping MongoDB by running a simple command
        await _db.command("ping")
        
        return {"check": check_name, "status": "healthy", "action_taken": None}
        
    except Exception as e:
        issue = f"MongoDB connection failed: {e}"
        action = "Sent WhatsApp alert (MongoDB is external)"
        
        logger.error(f"[AUTO_HEAL] {issue}")
        await log_auto_heal_action(check_name, issue, action, False)
        
        # Send alert immediately - this is critical
        await send_alert_whatsapp(f"Auto-heal CRITICAL: MongoDB connection failed at {datetime.now(timezone.utc).strftime('%H:%M UTC')}. Error: {str(e)[:100]}")
        
        return {
            "check": check_name,
            "status": "alerted",
            "issue": issue,
            "action_taken": action,
            "resolved": False
        }


async def check_scheduler_jobs() -> Dict[str, Any]:
    """
    Check 5: Verify scheduler jobs are registered
    Check if all expected background tasks are running.
    If any are missing, we can't easily re-register them without a server restart,
    so we alert and potentially restart the backend.
    """
    check_name = "scheduler_jobs"
    
    # We check asyncio tasks to see if our schedulers are running
    # Note: This is a heuristic - we look for task names containing our scheduler names
    
    try:
        all_tasks = asyncio.all_tasks()
        running_schedulers = []
        
        for task in all_tasks:
            task_name = task.get_name() if hasattr(task, 'get_name') else str(task)
            coro_name = ""
            if hasattr(task, '_coro') and hasattr(task._coro, '__name__'):
                coro_name = task._coro.__name__
            
            # Check if this task is one of our schedulers
            for scheduler in EXPECTED_SCHEDULERS:
                if scheduler in task_name or scheduler in coro_name:
                    running_schedulers.append(scheduler)
                    break
        
        # Remove duplicates
        running_schedulers = list(set(running_schedulers))
        
        # Check for missing schedulers
        missing_schedulers = [s for s in EXPECTED_SCHEDULERS if s not in running_schedulers]
        
        if not missing_schedulers:
            return {
                "check": check_name,
                "status": "healthy",
                "running_schedulers": len(running_schedulers),
                "action_taken": None
            }
        
        # Some schedulers are missing
        issue = f"Missing schedulers: {', '.join(missing_schedulers)}"
        action = "Attempted backend restart to re-register schedulers"
        
        logger.warning(f"[AUTO_HEAL] {issue}")
        
        # Try to restart backend to re-register schedulers (no sudo in Emergent)
        try:
            result = subprocess.run(
                ["supervisorctl", "restart", "backend"],
                capture_output=True,
                text=True,
                timeout=30
            )
            resolved = result.returncode == 0
            
            await log_auto_heal_action(check_name, issue, action, resolved)
            if not resolved:
                await send_alert_whatsapp(f"Auto-heal: Missing schedulers - backend restart attempted at {datetime.now(timezone.utc).strftime('%H:%M UTC')}")
            
            return {
                "check": check_name,
                "status": "fixed" if resolved else "attempted",
                "issue": issue,
                "missing_schedulers": missing_schedulers,
                "action_taken": action,
                "resolved": resolved
            }
        except Exception as e:
            await log_auto_heal_action(check_name, issue, f"Restart failed: {e}", False)
            return {
                "check": check_name,
                "status": "attempted",
                "issue": issue,
                "missing_schedulers": missing_schedulers,
                "error": str(e)
            }
            
    except Exception as e:
        logger.error(f"[AUTO_HEAL] Scheduler check error: {e}")
        return {"check": check_name, "status": "error", "error": str(e)}


async def check_emergent_credits() -> Dict[str, Any]:
    """
    Check 6: Monitor response time as proxy for Emergent credits health.
    
    Uses localhost to avoid Cloudflare 520 errors on external URL.
    If localhost is healthy, the service is working.
    Only alerts on actual backend issues, not external routing issues.
    """
    check_name = "emergent_credits"
    
    try:
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Use localhost to check actual backend health (avoids Cloudflare issues)
            test_url = f"{BACKEND_URL}/api/health"
            
            try:
                response = await client.get(test_url)
                duration = time.time() - start_time
                
                if response.status_code == 200:
                    if duration > RESPONSE_TIME_CRITICAL:
                        # Critical - backend very slow
                        issue = f"Backend response time CRITICAL: {duration:.2f}s"
                        action = "Sent WhatsApp alert - check server resources"
                        
                        await log_auto_heal_action(check_name, issue, action, False)
                        await send_alert_whatsapp(
                            f"SLOW: Backend responding in {duration:.1f}s. "
                            f"Check server resources and Emergent credits."
                        )
                        
                        return {
                            "check": check_name,
                            "status": "warning",
                            "response_time_seconds": round(duration, 2),
                            "threshold": RESPONSE_TIME_CRITICAL,
                            "action_taken": action
                        }
                    
                    elif duration > RESPONSE_TIME_WARNING:
                        # Warning - backend slow but working
                        return {
                            "check": check_name,
                            "status": "healthy",
                            "response_time_seconds": round(duration, 2),
                            "note": "Response time elevated but acceptable",
                            "action_taken": None
                        }
                    
                    else:
                        # Healthy - response time normal
                        return {
                            "check": check_name,
                            "status": "healthy",
                            "response_time_seconds": round(duration, 2),
                            "action_taken": None
                        }
                
                else:
                    # Non-200 response from backend
                    issue = f"Backend health check returned status {response.status_code}"
                    action = "Sent WhatsApp alert"
                    
                    await log_auto_heal_action(check_name, issue, action, False)
                    await send_alert_whatsapp(
                        f"WARNING: Backend health check returned {response.status_code}. "
                        f"Check backend logs."
                    )
                    
                    return {
                        "check": check_name,
                        "status": "warning",
                        "http_status": response.status_code,
                        "action_taken": action
                    }
                    
            except httpx.TimeoutException:
                # Timeout - backend is down or very slow
                duration = time.time() - start_time
                issue = f"Backend health check timed out after {duration:.1f}s"
                action = "Sent CRITICAL WhatsApp alert"
                
                await log_auto_heal_action(check_name, issue, action, False)
                await send_alert_whatsapp(
                    "CRITICAL: Backend health check timed out. "
                    "Check server status and Emergent credits."
                )
                
                return {
                    "check": check_name,
                    "status": "critical",
                    "error": "timeout",
                    "response_time_seconds": round(duration, 2),
                    "action_taken": action
                }
                
    except Exception as e:
        # Complete failure to check - but don't spam alerts for connectivity issues
        logger.warning(f"[AUTO_HEAL] Credit check failed (may be transient): {e}")
        
        return {
            "check": check_name,
            "status": "skipped",
            "note": "Check skipped due to connectivity issue",
            "error": str(e)[:100],
            "action_taken": None
        }


# ═══════════════════════════════════════════════════════════════════
# CHECK 7: END-TO-END AI CHAT TEST
# ═══════════════════════════════════════════════════════════════════

async def check_ai_chat_working() -> Dict[str, Any]:
    """
    Check 7: End-to-end AI chat test.
    
    Tests the actual AI chat endpoint to catch real bugs that health checks miss.
    This would have caught the PyMongo boolean bug immediately.
    """
    check_name = "ai_chat"
    
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{BACKEND_URL}/api/ai/chat",
                json={"message": "health check ping", "session_id": "auto_heal_test"},
                headers={"X-Brand-Key": "reroots", "Content-Type": "application/json"}
            )
            
            data = response.json()
            
            if response.status_code == 200 and ("reply" in data or "response" in data):
                return {
                    "check": check_name,
                    "status": "healthy",
                    "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                    "action_taken": None
                }
            else:
                # AI chat is broken!
                issue = f"AI chat returned status {response.status_code}: {str(data)[:100]}"
                action = "Sent WhatsApp alert - AI chat is broken"
                
                await log_auto_heal_action(check_name, issue, action, False)
                await send_alert_whatsapp(
                    f"🚨 Reroots AI chat is BROKEN. Status: {response.status_code}. "
                    f"Response: {str(data)[:100]}"
                )
                
                return {
                    "check": check_name,
                    "status": "failed",
                    "http_status": response.status_code,
                    "response": str(data)[:200],
                    "action_taken": action
                }
                
    except httpx.TimeoutException:
        issue = "AI chat request timed out after 20s"
        action = "Sent WhatsApp alert - AI chat timeout"
        
        await log_auto_heal_action(check_name, issue, action, False)
        await send_alert_whatsapp(
            "🚨 Reroots AI chat is TIMING OUT. Requests taking >20s. "
            "Check LLM API and server resources."
        )
        
        return {
            "check": check_name,
            "status": "timeout",
            "error": "Request timed out after 20s",
            "action_taken": action
        }
        
    except Exception as e:
        issue = f"AI chat check failed: {str(e)[:100]}"
        action = "Sent WhatsApp alert - AI chat down"
        
        await log_auto_heal_action(check_name, issue, action, False)
        await send_alert_whatsapp(
            f"🚨 Reroots AI chat is DOWN. Error: {str(e)[:100]}"
        )
        
        return {
            "check": check_name,
            "status": "down",
            "error": str(e)[:200],
            "action_taken": action
        }


# ═══════════════════════════════════════════════════════════════════
# CHECK 8: ERROR LOG SCANNER
# ═══════════════════════════════════════════════════════════════════

async def check_error_logs() -> Dict[str, Any]:
    """
    Check 8: Scan error logs for recent issues.
    
    Checks both MongoDB error_logs collection and supervisor logs
    to catch exceptions that don't break health checks.
    """
    check_name = "error_logs"
    error_count = 0
    critical_count = 0
    recent_errors = []
    
    try:
        # Check MongoDB error_logs collection
        if _db is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
            
            cursor = _db.error_logs.find({
                "timestamp": {"$gte": cutoff.isoformat()},
                "level": {"$in": ["ERROR", "CRITICAL"]}
            }).sort("timestamp", -1).limit(20)
            
            recent_errors = await cursor.to_list(20)
            error_count = len(recent_errors)
            critical_count = len([e for e in recent_errors if e.get("level") == "CRITICAL"])
        
        # Also check supervisor logs for Python exceptions
        log_errors = 0
        try:
            log_path = "/var/log/supervisor/backend.err.log"
            with open(log_path, "r") as f:
                lines = f.readlines()
                recent = lines[-100:]  # Last 100 lines
                log_errors = len([
                    l for l in recent 
                    if "ERROR" in l or "Exception" in l or "Traceback" in l
                ])
        except Exception:
            pass  # Log file might not exist
        
        # Determine status
        if critical_count > 0:
            # Critical errors - immediate alert
            sample_error = recent_errors[0].get("message", "Unknown")[:100] if recent_errors else "Check logs"
            
            await send_alert_whatsapp(
                f"🚨 CRITICAL errors detected ({critical_count}): {sample_error}"
            )
            
            return {
                "check": check_name,
                "status": "critical",
                "db_errors": error_count,
                "critical_errors": critical_count,
                "log_errors": log_errors,
                "action_taken": "Sent WhatsApp alert for critical errors"
            }
        
        elif error_count > 5 or log_errors > 10:
            # Many errors - warning
            await send_alert_whatsapp(
                f"⚠️ {error_count} DB errors + {log_errors} log errors in last 15 min. "
                f"Check admin → Error Logs."
            )
            
            return {
                "check": check_name,
                "status": "warning",
                "db_errors": error_count,
                "log_errors": log_errors,
                "action_taken": "Sent WhatsApp warning"
            }
        
        else:
            # Healthy
            return {
                "check": check_name,
                "status": "healthy",
                "db_errors": error_count,
                "log_errors": log_errors,
                "action_taken": None
            }
            
    except Exception as e:
        logger.warning(f"[AUTO_HEAL] Error log check failed: {e}")
        return {
            "check": check_name,
            "status": "skipped",
            "error": str(e)[:100],
            "action_taken": None
        }


async def run_all_health_checks() -> Dict[str, Any]:
    """
    Run all health checks and return summary.
    This is the main function called by the scheduler.
    """
    start_time = datetime.now(timezone.utc)
    logger.info("[AUTO_HEAL] Starting health checks...")
    
    results = {
        "timestamp": start_time.isoformat(),
        "checks": {}
    }
    
    # Run checks sequentially to avoid overwhelming the system
    # Check 1: Backend health
    results["checks"]["backend"] = await check_backend_health()
    
    # Check 2: Frontend serving
    results["checks"]["frontend"] = await check_frontend_serving()
    
    # Check 3: Redis connection
    results["checks"]["redis"] = await check_redis_connection()
    
    # Check 4: MongoDB connection
    results["checks"]["mongodb"] = await check_mongodb_connection()
    
    # Check 5: Scheduler jobs
    results["checks"]["schedulers"] = await check_scheduler_jobs()
    
    # Check 6: Emergent credits / response time monitoring
    results["checks"]["emergent_credits"] = await check_emergent_credits()
    
    # Check 7: End-to-end AI chat test (catches real bugs)
    results["checks"]["ai_chat"] = await check_ai_chat_working()
    
    # Check 8: Error log scanner
    results["checks"]["error_logs"] = await check_error_logs()
    
    # Summary
    all_healthy = all(
        check.get("status") in ["healthy", "skipped"]
        for check in results["checks"].values()
    )
    
    actions_taken = [
        check for check in results["checks"].values()
        if check.get("action_taken")
    ]
    
    results["summary"] = {
        "all_healthy": all_healthy,
        "actions_taken_count": len(actions_taken),
        "duration_ms": int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
    }
    
    # Determine overall status
    if all_healthy:
        results["overall_status"] = "healthy"
        logger.info("[AUTO_HEAL] All health checks passed")
    else:
        results["overall_status"] = "degraded"
        logger.warning(f"[AUTO_HEAL] Health checks complete - {len(actions_taken)} actions taken")
    
    # Save run to MongoDB for audit tracking
    if _db is not None:
        try:
            await _db.auto_heal_runs.insert_one({
                "timestamp": results["timestamp"],
                "overall_status": results["overall_status"],
                "checks_passed": sum(1 for c in results["checks"].values() if c.get("status") in ["healthy", "skipped"]),
                "issues_found": len(actions_taken),
                "summary": results["summary"]
            })
        except Exception as e:
            logger.warning(f"[AUTO_HEAL] Failed to save run: {e}")
    
    return results


async def auto_heal_scheduler():
    """
    Background task that runs health checks every 5 minutes.
    This is started from server.py startup event.
    
    Note: Runs every 5 minutes (was 10) for faster detection of credit issues.
    """
    logger.info("[AUTO_HEAL] Auto-heal scheduler started (runs every 5 minutes)")
    
    # Wait 60 seconds after startup to let everything initialize
    await asyncio.sleep(60)
    
    while True:
        try:
            # Run all health checks
            results = await run_all_health_checks()
            
            # Log summary if any issues found
            if not results["summary"]["all_healthy"]:
                logger.warning(f"[AUTO_HEAL] Issues found: {results}")
            
            # Wait 5 minutes before next check (was 10 minutes)
            await asyncio.sleep(300)  # 5 minutes = 300 seconds
            
        except Exception as e:
            logger.error(f"[AUTO_HEAL] Scheduler error: {e}")
            # Wait 2 minutes on error before retrying
            await asyncio.sleep(120)


# API endpoint for manual trigger (add to routes if needed)
async def get_auto_heal_logs(limit: int = 50) -> list:
    """Get recent auto-heal logs from MongoDB"""
    if _db is None:
        return []
    
    try:
        logs = await _db.auto_heal_log.find(
            {},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        return logs
    except Exception as e:
        logger.error(f"[AUTO_HEAL] Failed to get logs: {e}")
        return []
