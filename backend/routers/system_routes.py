"""
AUREM System Status & Sync API
Global health checks, sync operations, and system introspection
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Dict, Any, List
from datetime import datetime, timezone
import logging
import os

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
    """Require a valid JWT with admin role. Returns the decoded payload."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        import jwt
        payload = jwt.decode(
            authorization.split(" ", 1)[1],
            os.environ.get("JWT_SECRET", ""),
            algorithms=["HS256"],
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    role = (payload.get("role") or "").lower()
    is_admin = bool(payload.get("is_admin") or payload.get("is_super_admin"))
    if role not in ("admin", "super_admin") and not is_admin:
        raise HTTPException(status_code=403, detail="Admin role required")
    return payload


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
    
    # TTS/Voice status
    elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY", "")
    tts_status = "active"
    if not elevenlabs_key:
        tts_status = "missing_key"
    elif len(elevenlabs_key) < 10:
        tts_status = "invalid_key"

    # Camofox anti-detection browser status
    camofox_available = False
    try:
        from services.camofox_client import is_camofox_available
        camofox_available = await is_camofox_available()
    except Exception:
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
            },
            "voice_tts": {
                "elevenlabs": tts_status,
                "fallback": "web_speech_api",
                "warning": "ElevenLabs key expired or missing — using browser TTS fallback" if tts_status != "active" else None
            },
            "camofox": {
                "available": camofox_available,
                "description": "Anti-detection browser for Scout"
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
    """Return circuit breaker state + real historical traffic.

    The in-memory CircuitBreaker only counts requests routed through
    `protected_call()`. Most direct LLM / Twilio / WHAPI calls bypass it,
    so the raw stats show 0 even when the platform is under heavy load.
    We enrich the payload with lifetime counts from real collections so the
    admin dashboard always reflects actual production traffic.
    """
    from services.circuit_breaker import get_all_status
    status = get_all_status()

    # ── lifetime aggregates from real collections ─────────────────────
    try:
        from server import db
        if db is not None:
            # Map each circuit breaker name → collections / event_types / from_agents
            # that actually record traffic for that upstream service.
            sources = {
                "anthropic":   {"api_usage": {"provider": "anthropic"}, "a2a": None},
                "openai":      {"api_usage": {"provider": "openai"},    "a2a": None},
                "emergent_llm":{"api_usage": {"provider": "emergent"},  "a2a": None},
                "aurem_voice": {"a2a": {"from_agent": {"$in": ["voice_ora", "closer_ora"]}}, "api_usage": {"provider": "voice"}},
                "twilio":      {"api_usage": {"provider": "twilio"}},
                "elevenlabs":  {"api_usage": {"provider": "elevenlabs"}},
                "whatsapp":    {"api_usage": {"provider": {"$in": ["whapi", "whatsapp", "twilio_whatsapp"]}}},
                "gmail":       {"api_usage": {"provider": "gmail"}},
                "firebase":    {"api_usage": {"provider": "firebase"}},
                "stripe":      {"api_usage": {"provider": "stripe"}},
                "shopify":     {"api_usage": {"provider": "shopify"}},
            }
            for name, src in sources.items():
                if name not in status["breakers"]:
                    continue
                calls = failures = 0
                if "api_usage" in src:
                    q = src["api_usage"]
                    try:
                        calls += await db.api_usage_log.count_documents(q)
                        failures += await db.api_usage_log.count_documents({**q, "status": {"$in": ["error", "failed", "timeout"]}})
                    except Exception:
                        pass
                if "a2a" in src and src["a2a"]:
                    try:
                        calls += await db.a2a_events.count_documents(src["a2a"])
                    except Exception:
                        pass
                # Only overwrite zeros — preserve live-failure stats when breakers actually tripped.
                bs = status["breakers"][name].get("stats", {})
                if (bs.get("total_calls", 0) == 0) and calls > 0:
                    bs["total_calls"] = calls
                    bs["total_failures"] = failures
                    bs["failure_rate"] = round((failures / calls * 100) if calls > 0 else 0, 2)
                    bs["source"] = "lifetime_audit"
                    status["breakers"][name]["stats"] = bs

            # Overall platform traffic summary so the top strip always shows something.
            total_events = await db.a2a_events.estimated_document_count()
            total_api = 0
            try:
                total_api = await db.api_usage_log.estimated_document_count()
            except Exception:
                pass
            status["traffic_summary"] = {
                "a2a_events_lifetime": total_events,
                "api_usage_lifetime": total_api,
            }
    except Exception as e:
        status["enrichment_error"] = str(e)[:200]

    return status


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



@router.get("/modules")
async def get_module_health(user=Depends(get_current_user)):
    """
    Show which extracted modules loaded successfully.
    Useful for on-call debugging when a specific feature stops working.
    """
    modules = {}

    # Phase 1 extractions
    _phase1 = [
        ("services.cron_schedulers", "Cron Schedulers", ["daily_stock_alert_scheduler", "weekly_revenue_summary_scheduler", "cnf_reminder_scheduler"]),
        ("services.milestone_system", "Milestone System", ["profile_tenant", "check_referral_fraud", "verify_referral_for_milestone"]),
        ("routers.server_misc_routes", "Server Misc Routes", ["router", "push_sse_event"]),
    ]
    # Phase 2 extractions
    _phase2 = [
        ("routers.registry", "Router Registry", ["register_all_routers"]),
        ("services.startup_init", "Startup Init", ["init_all_service_dbs", "start_all_background_schedulers"]),
        ("middleware.cache_headers", "Cache Headers Middleware", ["CacheHeadersMiddleware"]),
    ]
    # Core services
    _core = [
        ("services.semantic_cache", "Semantic Cache", ["SemanticCache"]),
        ("services.openrouter_client", "OpenRouter Client", ["call_openrouter"]),
        ("services.ora_live_context", "ORA Live Context", ["get_live_context"]),
        ("services.tenant_profiling", "Tenant Profiling (Gate 1)", ["profile_tenant"]),
        ("services.optimization_monitor", "Optimization Monitor (Gate 4)", ["get_tenant_optimization_metrics"]),
    ]
    # Key routers
    _routers = [
        ("routers.aurem_chat", "AUREM Chat", ["router"]),
        ("routers.sentinel_router", "Sentinel", ["router", "start_sentinel"]),
        ("routers.tenant_optimization_router", "Tenant Optimization", ["router"]),
        ("routers.brain_router", "Brain Orchestrator", ["router"]),
        ("routers.ooda_loop_router", "OODA Loop", ["router"]),
        ("routers.biometric_secure", "Biometric Auth", ["router"]),
    ]

    all_checks = [
        ("phase1_extractions", _phase1),
        ("phase2_extractions", _phase2),
        ("core_services", _core),
        ("key_routers", _routers),
    ]

    total = 0
    loaded = 0

    for section_name, checks in all_checks:
        section = {}
        for module_path, label, expected_attrs in checks:
            total += 1
            try:
                mod = __import__(module_path, fromlist=expected_attrs)
                missing = [a for a in expected_attrs if not hasattr(mod, a)]
                if missing:
                    section[label] = {"status": "partial", "module": module_path, "missing": missing}
                else:
                    section[label] = {"status": "loaded", "module": module_path}
                    loaded += 1
            except ImportError as e:
                section[label] = {"status": "missing", "module": module_path, "error": str(e)}
            except Exception as e:
                section[label] = {"status": "error", "module": module_path, "error": str(e)}
        modules[section_name] = section

    return {
        "modules": modules,
        "summary": {
            "total": total,
            "loaded": loaded,
            "missing": total - loaded,
            "health": "healthy" if loaded == total else ("degraded" if loaded > total * 0.7 else "critical"),
        },
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


print("[STARTUP] System Status & Sync Routes loaded")
