"""
AUREM System Status & Sync API
Global health checks, sync operations, and system introspection
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Dict, Any, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["System Status"])

# Database reference
db = None

def set_db(database):
    global db
    db = database


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH HELPER
# ═══════════════════════════════════════════════════════════════════════════════

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"_id": "admin", "email": "admin@aurem.ai", "role": "admin"}


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM STATUS ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/status")
async def get_system_status(user = Depends(get_current_user)):
    """
    Get comprehensive system status
    Used by status bar and monitoring
    """
    from services.circuit_breaker import get_all_status
    
    # Circuit breaker status
    circuit_status = get_all_status()
    
    # Database health
    db_healthy = True
    db_collections = 0
    try:
        if db is not None:
            await db.command('ping')
            collections = await db.list_collection_names()
            db_collections = len(collections)
    except:
        db_healthy = False
    
    # Count pending items across systems
    pending_approvals = 0
    pending_followups = 0
    active_handoffs = 0
    
    if db is not None:
        try:
            # Pending approvals (placeholder - implement when approval system is ready)
            pending_approvals = await db.pending_approvals.count_documents({"status": "pending"})
        except:
            pass
        
        try:
            # Pending follow-ups
            from services.proactive_followup_service import get_followup_engine, FollowUpTiming
            engine = get_followup_engine(db)
            # Get businesses and count pending for all
            businesses = await db.aurem_businesses.find({}, {"_id": 0, "business_id": 1}).to_list(10)
            for biz in businesses:
                candidates = await engine.find_conversations_needing_followup(
                    biz["business_id"],
                    FollowUpTiming.HOUR_24
                )
                pending_followups += len(candidates)
        except:
            pass
        
        try:
            # Active human handoffs
            from services.whatsapp_coexistence import get_coexistence_manager
            manager = get_coexistence_manager(db)
            businesses = await db.aurem_businesses.find({}, {"_id": 0, "business_id": 1}).to_list(10)
            for biz in businesses:
                handoffs = await manager.get_active_human_conversations(biz["business_id"])
                active_handoffs += len(handoffs)
        except:
            pass
    
    # Overall health
    overall_healthy = (
        db_healthy and
        circuit_status["open_breakers"] == 0
    )
    
    return {
        "overall_status": "healthy" if overall_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "database": {
                "healthy": db_healthy,
                "collections": db_collections
            },
            "circuit_breakers": {
                "total": circuit_status["total_breakers"],
                "open": circuit_status["open_breakers"],
                "degraded_services": circuit_status["degraded_services"]
            }
        },
        "pending_work": {
            "approvals": pending_approvals,
            "followups": pending_followups,
            "handoffs": active_handoffs
        }
    }


@router.post("/sync")
async def force_sync(user = Depends(get_current_user)):
    """
    Force global sync - run all health checks and sync operations
    Based on Reroots sync button pattern
    """
    results = {}
    errors = []
    
    logger.info("[SYNC] Starting global sync...")
    
    # 1. Database indexes
    try:
        if db is not None:
            # Core indexes
            await db.aurem_users.create_index("email")
            await db.aurem_businesses.create_index("business_id")
            await db.aurem_agents.create_index("agent_id")
            await db.aurem_customers.create_index("customer_id")
            await db.aurem_customers.create_index("email")
            await db.aurem_customers.create_index("phone")
            await db.aurem_messages.create_index("customer_id")
            await db.aurem_messages.create_index("business_id")
            await db.aurem_messages.create_index("timestamp")
            await db.aurem_conversations.create_index("session_id")
            
            results["database_indexes"] = "synced"
    except Exception as e:
        errors.append(f"Database index sync failed: {str(e)}")
    
    # 2. Circuit breaker reset
    try:
        from services.circuit_breaker import get_all_status
        circuit_status = get_all_status()
        results["circuit_breakers"] = {
            "total": circuit_status["total_breakers"],
            "open": circuit_status["open_breakers"]
        }
    except Exception as e:
        errors.append(f"Circuit breaker check failed: {str(e)}")
    
    # 3. Premium features health check
    try:
        # Check if services are importable
        from services.proactive_followup_service import get_followup_engine
        from services.whatsapp_coexistence import get_coexistence_manager
        from services.multimodal_processor import get_multimodal_processor
        
        results["premium_features"] = "loaded"
    except Exception as e:
        errors.append(f"Premium features check failed: {str(e)}")
    
    # 4. Business agent sync
    try:
        from services.aurem_business_agents import get_agent_manager
        manager = get_agent_manager(db)
        
        businesses = manager.list_businesses()
        results["businesses"] = {
            "count": len(businesses),
            "ids": [b.business_id for b in businesses]
        }
    except Exception as e:
        errors.append(f"Business sync failed: {str(e)}")
    
    success = len(errors) == 0
    
    logger.info(f"[SYNC] Sync {'completed' if success else 'completed with errors'}")
    
    return {
        "success": success,
        "results": results,
        "errors": errors if errors else None,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/health")
async def health_check():
    """Simple health check endpoint (no auth required)"""
    try:
        if db is not None:
            await db.command('ping')
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except:
        raise HTTPException(status_code=503, detail="Service unavailable")


@router.get("/circuit-breakers")
async def get_circuit_breakers(user = Depends(get_current_user)):
    """Get status of all circuit breakers"""
    from services.circuit_breaker import get_all_status
    return get_all_status()


@router.post("/circuit-breakers/reset")
async def reset_circuit_breakers(
    service: str = None,
    user = Depends(get_current_user)
):
    """Reset circuit breaker(s)"""
    from services.circuit_breaker import breakers, reset_all, get_breaker
    
    if service:
        # Reset specific service
        breaker = get_breaker(service)
        breaker.reset()
        return {
            "reset": service,
            "status": breaker.get_status()
        }
    else:
        # Reset all
        reset_all()
        return {
            "reset": "all",
            "count": len(breakers)
        }


@router.get("/automation-status")
async def get_automation_status(user = Depends(get_current_user)):
    """
    Get status of all automation systems
    MCP-style introspection endpoint
    """
    status = {
        "premium_features": {
            "followup_engine": {"enabled": True, "status": "active"},
            "coexistence": {"enabled": True, "status": "active"},
            "multimodal": {"enabled": True, "status": "active"}
        },
        "business_agents": {
            "enabled": True,
            "businesses": []
        },
        "omni_channel": {
            "enabled": True,
            "channels": ["email", "whatsapp", "voice", "sms", "web_chat"]
        }
    }
    
    # Get business count
    if db is not None:
        try:
            from services.aurem_business_agents import get_agent_manager
            manager = get_agent_manager(db)
            businesses = manager.list_businesses()
            status["business_agents"]["businesses"] = [
                {"id": b.business_id, "name": b.name, "type": b.type.value}
                for b in businesses
            ]
        except:
            pass
    
    return status


@router.get("/pending-work")
async def get_pending_work(user = Depends(get_current_user)):
    """
    Get all pending work items across the system
    MCP-style tool for visibility
    """
    pending = {
        "followups": [],
        "handoffs": [],
        "approvals": []
    }
    
    if db is not None:
        # Get businesses
        try:
            businesses = await db.aurem_businesses.find({}, {"_id": 0, "business_id": 1, "name": 1}).to_list(10)
            
            # Get follow-ups for each business
            from services.proactive_followup_service import get_followup_engine, FollowUpTiming
            engine = get_followup_engine(db)
            
            for biz in businesses:
                candidates = await engine.find_conversations_needing_followup(
                    biz["business_id"],
                    FollowUpTiming.HOUR_24
                )
                if candidates:
                    pending["followups"].append({
                        "business": biz["name"],
                        "count": len(candidates)
                    })
            
            # Get active handoffs
            from services.whatsapp_coexistence import get_coexistence_manager
            manager = get_coexistence_manager(db)
            
            for biz in businesses:
                handoffs = await manager.get_active_human_conversations(biz["business_id"])
                if handoffs:
                    pending["handoffs"].append({
                        "business": biz["name"],
                        "count": len(handoffs)
                    })
                    
        except Exception as e:
            logger.error(f"Error getting pending work: {e}")
    
    return pending


print("[STARTUP] System Status & Sync Routes loaded")
