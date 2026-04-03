"""
AUREM Admin Control - Global Sync & Status
Company: Polaris Built Inc.

Provides:
- System health indicator
- Last sync timestamp  
- Active missions count
- Circuit breaker status per channel
- Global SYNC button functionality
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/aurem/admin", tags=["aurem-admin"])

# MongoDB reference
_db = None

def set_db(database):
    global _db
    _db = database


# Track last sync
_last_sync: datetime = None


@router.get("/status")
async def get_admin_status():
    """Get global admin status for status bar"""
    from utils.aurem_bug_engine import get_bug_engine
    
    engine = get_bug_engine()
    
    # Get active missions count
    active_missions = 0
    if _db is not None:
        active_missions = await _db.aurem_missions.count_documents({
            "status": {"$in": ["initializing", "running"]}
        })
    
    # Get circuit breaker status
    circuit_breakers = {
        "email": _check_circuit_breaker("email", engine),
        "whatsapp": _check_circuit_breaker("whatsapp", engine),
        "voice": _check_circuit_breaker("voice", engine),
        "llm": _check_circuit_breaker("llm", engine),
    }
    
    # Determine overall health
    system_healthy = (
        engine.consecutive_failures < 2 and
        all(cb["status"] == "open" for cb in circuit_breakers.values())
    )
    
    return {
        "system_healthy": system_healthy,
        "last_sync": _last_sync.isoformat() if _last_sync else None,
        "last_scan": engine.last_scan.isoformat() if engine.last_scan else None,
        "active_missions": active_missions,
        "consecutive_failures": engine.consecutive_failures,
        "circuit_breakers": circuit_breakers,
    }


def _check_circuit_breaker(channel: str, engine) -> Dict:
    """Check if circuit breaker is tripped"""
    if channel in engine.circuit_breakers:
        until = engine.circuit_breakers[channel]
        if datetime.now(timezone.utc) < until:
            return {
                "status": "tripped",
                "until": until.isoformat(),
                "remaining_minutes": int((until - datetime.now(timezone.utc)).seconds / 60)
            }
    return {"status": "open"}


@router.post("/sync")
async def global_sync():
    """
    Global sync button functionality:
    1. Clear deduplication cache
    2. Re-index MongoDB collections
    3. Reset cooled-down circuit breakers
    4. Run immediate bug scan
    5. Return sync status
    """
    global _last_sync
    import time
    start = time.time()
    
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actions": [],
    }
    
    # 1. Clear deduplication cache (in-memory)
    try:
        from utils.aurem_rate_limiter import clear_rate_limits
        clear_rate_limits()
        results["actions"].append({"action": "clear_rate_limits", "success": True})
    except Exception as e:
        results["actions"].append({"action": "clear_rate_limits", "success": False, "error": str(e)})
    
    # 2. Re-index MongoDB collections
    if _db is not None:
        try:
            # Ensure indexes on key collections
            await _db.aurem_missions.create_index("mission_id")
            await _db.aurem_missions.create_index("status")
            await _db.aurem_missions.create_index("platform_user_id")
            await _db.aurem_bug_history.create_index("timestamp")
            results["actions"].append({"action": "reindex_db", "success": True})
        except Exception as e:
            results["actions"].append({"action": "reindex_db", "success": False, "error": str(e)})
    
    # 3. Reset cooled-down circuit breakers
    try:
        from utils.aurem_bug_engine import get_bug_engine
        engine = get_bug_engine()
        
        now = datetime.now(timezone.utc)
        reset_breakers = []
        
        for channel, until in list(engine.circuit_breakers.items()):
            if now >= until:
                del engine.circuit_breakers[channel]
                reset_breakers.append(channel)
        
        results["actions"].append({
            "action": "reset_circuit_breakers",
            "success": True,
            "reset": reset_breakers
        })
    except Exception as e:
        results["actions"].append({"action": "reset_circuit_breakers", "success": False, "error": str(e)})
    
    # 4. Run immediate bug scan
    try:
        from utils.aurem_bug_engine import scheduled_bug_scan
        scan_result = await scheduled_bug_scan()
        results["actions"].append({
            "action": "bug_scan",
            "success": True,
            "errors_found": len(scan_result.get("errors_found", [])),
            "auto_fixed": len(scan_result.get("auto_fixed", [])),
            "system_healthy": scan_result.get("system_healthy_after", False),
        })
    except Exception as e:
        results["actions"].append({"action": "bug_scan", "success": False, "error": str(e)})
    
    # Record sync time
    _last_sync = datetime.now(timezone.utc)
    results["sync_duration_ms"] = int((time.time() - start) * 1000)
    results["success"] = all(a.get("success", False) for a in results["actions"])
    
    logger.info(f"[AUREM ADMIN] Global sync completed in {results['sync_duration_ms']}ms")
    
    return results


@router.get("/dashboard-data")
async def get_dashboard_data():
    """Get all data needed for admin dashboard"""
    from utils.aurem_bug_engine import get_bug_engine
    
    engine = get_bug_engine()
    
    data = {
        "status": await get_admin_status(),
        "bug_engine": {
            "last_scan": engine.last_scan.isoformat() if engine.last_scan else None,
            "consecutive_failures": engine.consecutive_failures,
        },
    }
    
    if _db is not None:
        # Recent missions
        missions = await _db.aurem_missions.find(
            {},
            {"_id": 0, "mission_id": 1, "industry_target": 1, "status": 1, "phase": 1, "created_at": 1}
        ).sort("created_at", -1).limit(10).to_list(10)
        data["recent_missions"] = missions
        
        # Bug history summary
        from datetime import timedelta
        since = datetime.now(timezone.utc) - timedelta(days=7)
        bug_stats = await _db.aurem_bug_history.aggregate([
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {
                "_id": None,
                "total_scans": {"$sum": 1},
                "healthy_scans": {"$sum": {"$cond": ["$system_healthy_after", 1, 0]}},
            }}
        ]).to_list(1)
        data["bug_stats"] = bug_stats[0] if bug_stats else {"total_scans": 0, "healthy_scans": 0}
    
    return data
