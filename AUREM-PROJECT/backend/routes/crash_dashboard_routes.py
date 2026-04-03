"""
Crash Dashboard Routes for Reroots Admin Panel
Provides endpoints for monitoring system health, crashes, and rate limits.
"""

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/crash-dashboard", tags=["crash-dashboard"])

# Database reference
_db = None


def set_db(database):
    """Set database reference"""
    global _db
    _db = database


@router.get("/status")
async def get_crash_dashboard_status():
    """
    Get complete crash dashboard status including:
    - Circuit breaker state
    - Recent crashes
    - Response time stats
    - Rate limit violations
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Get circuit breaker status
        from services.crash_protection import db_circuit_breaker
        circuit_breaker_status = db_circuit_breaker.get_status()
        
        # Get recent crashes (last 24 hours)
        cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_crashes = await _db.crash_log.find(
            {"timestamp": {"$gte": cutoff_24h.isoformat()}},
            {"_id": 0}
        ).sort("timestamp", -1).limit(20).to_list(20)
        
        # Get crash count by hour (last 24 hours)
        crash_count_24h = await _db.crash_log.count_documents({
            "timestamp": {"$gte": cutoff_24h.isoformat()}
        })
        
        # Get rate limit violations (last 24 hours)
        rate_limit_violations = await _db.suspicious_activity_log.find(
            {
                "timestamp": {"$gte": cutoff_24h.isoformat()},
                "activity_type": {"$in": ["rate_limit_exceeded", "duplicate_spam"]}
            },
            {"_id": 0}
        ).sort("timestamp", -1).limit(20).to_list(20)
        
        violation_count = await _db.suspicious_activity_log.count_documents({
            "timestamp": {"$gte": cutoff_24h.isoformat()},
            "activity_type": {"$in": ["rate_limit_exceeded", "duplicate_spam"]}
        })
        
        # Get auto-heal logs (last 24 hours)
        auto_heal_logs = await _db.auto_heal_log.find(
            {"timestamp": {"$gte": cutoff_24h.isoformat()}},
            {"_id": 0}
        ).sort("timestamp", -1).limit(20).to_list(20)
        
        auto_heal_actions = await _db.auto_heal_log.count_documents({
            "timestamp": {"$gte": cutoff_24h.isoformat()},
            "resolved": False
        })
        
        # Overall health score (0-100)
        health_score = 100
        if circuit_breaker_status["state"] == "OPEN":
            health_score -= 50
        elif circuit_breaker_status["state"] == "HALF_OPEN":
            health_score -= 25
        
        health_score -= min(crash_count_24h * 5, 30)  # Max -30 for crashes
        health_score -= min(violation_count * 2, 20)  # Max -20 for violations
        health_score = max(0, health_score)
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health_score": health_score,
            "circuit_breaker": circuit_breaker_status,
            "crashes": {
                "count_24h": crash_count_24h,
                "recent": recent_crashes
            },
            "rate_limits": {
                "violations_24h": violation_count,
                "recent": rate_limit_violations
            },
            "auto_heal": {
                "unresolved_24h": auto_heal_actions,
                "recent": auto_heal_logs
            }
        }
        
    except Exception as e:
        logger.error(f"[CRASH_DASHBOARD] Failed to get status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/response-times")
async def get_response_time_history():
    """
    Get response time history from auto-heal checks.
    Returns data for charting response time trends.
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        # Get emergent_credits checks from last 24 hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        
        logs = await _db.auto_heal_log.find(
            {
                "check_name": "emergent_credits",
                "timestamp": {"$gte": cutoff.isoformat()}
            },
            {"_id": 0, "timestamp": 1, "issue_found": 1, "action_taken": 1}
        ).sort("timestamp", -1).limit(288).to_list(288)  # 5 min intervals = 288 per day
        
        # Also get the check results if stored
        health_checks = await _db.auto_heal_log.find(
            {
                "timestamp": {"$gte": cutoff.isoformat()}
            },
            {"_id": 0}
        ).sort("timestamp", -1).limit(100).to_list(100)
        
        return {
            "period": "24h",
            "interval": "5m",
            "data_points": len(logs),
            "history": logs,
            "all_checks": health_checks
        }
        
    except Exception as e:
        logger.error(f"[CRASH_DASHBOARD] Failed to get response times: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/crashes")
async def get_crash_details(limit: int = 50):
    """Get detailed crash logs."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        crashes = await _db.crash_log.find(
            {},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        # Group by error type
        by_type = {}
        for crash in crashes:
            error_type = crash.get("type", "Unknown")
            if error_type not in by_type:
                by_type[error_type] = 0
            by_type[error_type] += 1
        
        return {
            "total": len(crashes),
            "by_type": by_type,
            "crashes": crashes
        }
        
    except Exception as e:
        logger.error(f"[CRASH_DASHBOARD] Failed to get crashes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rate-limits")
async def get_rate_limit_details(limit: int = 50):
    """Get detailed rate limit violation logs."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        violations = await _db.suspicious_activity_log.find(
            {},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        # Group by activity type
        by_type = {}
        for v in violations:
            activity_type = v.get("activity_type", "Unknown")
            if activity_type not in by_type:
                by_type[activity_type] = 0
            by_type[activity_type] += 1
        
        # Count blocked IPs
        blocked_ips = await _db.ai_rate_limits.count_documents({
            "type": "block",
            "blocked": True,
            "blocked_until": {"$gt": datetime.now(timezone.utc).isoformat()}
        })
        
        return {
            "total": len(violations),
            "by_type": by_type,
            "currently_blocked_ips": blocked_ips,
            "violations": violations
        }
        
    except Exception as e:
        logger.error(f"[CRASH_DASHBOARD] Failed to get rate limits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker():
    """Manually reset the circuit breaker to CLOSED state."""
    try:
        from services.crash_protection import db_circuit_breaker
        
        db_circuit_breaker.state = "CLOSED"
        db_circuit_breaker.failures = 0
        db_circuit_breaker.last_failure_time = 0
        
        logger.info("[CRASH_DASHBOARD] Circuit breaker manually reset to CLOSED")
        
        return {
            "success": True,
            "message": "Circuit breaker reset to CLOSED state",
            "new_status": db_circuit_breaker.get_status()
        }
        
    except Exception as e:
        logger.error(f"[CRASH_DASHBOARD] Failed to reset circuit breaker: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/crashes/clear")
async def clear_old_crashes(days: int = 7):
    """Clear crash logs older than specified days."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        result = await _db.crash_log.delete_many({
            "timestamp": {"$lt": cutoff.isoformat()}
        })
        
        logger.info(f"[CRASH_DASHBOARD] Cleared {result.deleted_count} crash logs older than {days} days")
        
        return {
            "success": True,
            "deleted": result.deleted_count,
            "cutoff": cutoff.isoformat()
        }
        
    except Exception as e:
        logger.error(f"[CRASH_DASHBOARD] Failed to clear crashes: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ==================== ALL 8 CIRCUIT BREAKERS ENDPOINTS ====================

@router.get("/circuit-breakers")
async def get_all_circuit_breakers():
    """
    Get status of all 8 circuit breakers.
    
    Breakers:
    1. database - MongoDB connection
    2. email - Resend/SendGrid
    3. whatsapp - Twilio WhatsApp
    4. voice - Vapi/OmniDim voice
    5. llm - OpenRouter LLM
    6. redis - Redis cache (NEW)
    7. flagship - FlagShip courier (NEW)
    8. omnidim - OmniDimension webhook (NEW)
    """
    try:
        from services.circuit_breaker_service import circuit_registry
        
        all_status = circuit_registry.get_all_status()
        open_breakers = circuit_registry.get_open_breakers()
        
        # Calculate health
        total = len(all_status)
        open_count = len(open_breakers)
        health_percent = int(((total - open_count) / total) * 100) if total > 0 else 100
        
        return {
            "total_breakers": total,
            "open_count": open_count,
            "health_percent": health_percent,
            "open_breakers": open_breakers,
            "breakers": all_status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except ImportError:
        # Fallback to legacy single breaker
        from services.crash_protection import db_circuit_breaker
        return {
            "total_breakers": 1,
            "open_count": 1 if db_circuit_breaker.state == "OPEN" else 0,
            "health_percent": 0 if db_circuit_breaker.state == "OPEN" else 100,
            "breakers": {"database": db_circuit_breaker.get_status()},
            "note": "Using legacy single circuit breaker"
        }
    except Exception as e:
        logger.error(f"[CRASH_DASHBOARD] Failed to get circuit breakers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/circuit-breakers/{breaker_name}/reset")
async def reset_specific_breaker(breaker_name: str):
    """Reset a specific circuit breaker by name."""
    try:
        from services.circuit_breaker_service import circuit_registry
        
        if circuit_registry.reset(breaker_name):
            return {
                "success": True,
                "message": f"Circuit breaker '{breaker_name}' reset to CLOSED",
                "new_status": circuit_registry.get(breaker_name).get_status()
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Circuit breaker '{breaker_name}' not found"
            )
            
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="New circuit breaker service not available"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CRASH_DASHBOARD] Failed to reset breaker: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/circuit-breakers/reset-all")
async def reset_all_breakers():
    """Reset all circuit breakers to CLOSED state."""
    try:
        from services.circuit_breaker_service import circuit_registry
        
        circuit_registry.reset_all()
        
        return {
            "success": True,
            "message": "All circuit breakers reset to CLOSED",
            "new_status": circuit_registry.get_all_status()
        }
        
    except ImportError:
        # Fallback to legacy
        from services.crash_protection import db_circuit_breaker
        db_circuit_breaker.state = "CLOSED"
        db_circuit_breaker.failures = 0
        return {
            "success": True,
            "message": "Legacy circuit breaker reset",
            "new_status": db_circuit_breaker.get_status()
        }
    except Exception as e:
        logger.error(f"[CRASH_DASHBOARD] Failed to reset all breakers: {e}")
        raise HTTPException(status_code=500, detail=str(e))
