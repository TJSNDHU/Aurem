"""
OmniBridge Router - Phase 8.4
OmniDimension Integration Endpoints

Endpoints:
- POST /api/brain/omnidim-callback    - Post-call webhook (Summary, Sentiment, Transcript)
- POST /api/brain/omnidim-lead        - Social lead capture (DM automation)
- POST /api/omnidim/dispatch          - Dispatch outbound call
- POST /api/omnidim/dispatch-smart    - Smart dispatch with agent mapping
- GET  /api/omnidim/status            - Integration status
- GET  /api/omnidim/logs              - Call logs from OmniDim
- GET  /api/omnidim/businesses        - List registered businesses
- POST /api/omnidim/businesses        - Add new business
- POST /api/a2a/handoff               - Execute A2A handoff
- GET  /api/a2a/history               - Get A2A handoff history
"""

import logging
import json
import hmac
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Header, Query, Request, BackgroundTasks
from pydantic import BaseModel, Field

from services.aurem_commercial.omnidim_service import (
    OmniDimConfig,
    CallResult,
    SocialLead,
    CallContext,
    omnidim_client,
    customer_hydrator,
    scout_lead_processor,
    briefing_dispatcher,
    set_dependencies
)
from services.aurem_commercial.mapping_service import (
    get_mapping_service,
    set_mapping_db,
    BusinessMappingService
)
from services.aurem_commercial.a2a_handoff_service import (
    get_a2a_service,
    set_a2a_handoff_db,
    HandoffType,
    HandoffPriority
)

router = APIRouter(tags=["OmniBridge - OmniDimension Integration"])

logger = logging.getLogger(__name__)

_db = None


def set_db(db):
    """Set database dependency."""
    global _db
    _db = db
    set_dependencies(db=db)
    set_mapping_db(db)
    set_a2a_handoff_db(db)


def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


def require_omnidim_enabled():
    """
    Fix 5: OmniDim Readiness Gate
    
    Dependency that checks if OmniDim is properly configured.
    Returns 503 with clear message if not configured.
    """
    if not OmniDimConfig.is_enabled():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "OmniDimension not configured",
                "message": "OMNIDIM_API_KEY or OMNIDIM_AGENT_ID environment variables are not set",
                "mode": "scaffold",
                "action": "Set OMNIDIM_API_KEY and OMNIDIM_AGENT_ID in backend/.env"
            }
        )


# ==================== REQUEST MODELS ====================

class OmniDimCallbackPayload(BaseModel):
    """
    Standard payload from OmniDimension post-call webhook.
    
    Matches OmniDim's webhook schema:
    https://omnidim.io/docs/agent#post-call-actions
    """
    call_id: str = Field(..., description="Unique call identifier")
    agent_id: int = Field(..., description="OmniDim agent ID")
    status: str = Field(..., description="Call status: completed, failed, busy, no-answer")
    duration: int = Field(0, description="Call duration in seconds")
    
    # Customer info
    to_number: str = Field(..., description="Called phone number")
    from_number: Optional[str] = Field(None, description="Caller ID used")
    
    # Content
    transcript: str = Field("", description="Full conversation transcript")
    summary: str = Field("", description="AI-generated call summary")
    
    # Sentiment analysis
    sentiment: str = Field("neutral", description="Overall sentiment: positive, neutral, negative")
    sentiment_score: float = Field(0.0, description="Sentiment score -1.0 to 1.0")
    
    # Extracted data
    extracted_variables: Dict[str, Any] = Field(default_factory=dict, description="LLM-extracted variables")
    
    # Web search (if enabled)
    web_search_results: Optional[List[Dict]] = Field(None, description="Real-time web search data")
    
    # Recording
    recording_url: Optional[str] = Field(None, description="Call recording URL")
    
    # Context passed during dispatch
    call_context: Optional[Dict[str, Any]] = Field(None, description="Original call context")
    
    # Metadata
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SocialLeadPayload(BaseModel):
    """
    Payload from OmniDimension DM automation.
    
    Captured when a lead messages via Instagram/Facebook/WhatsApp.
    """
    lead_id: str = Field(..., description="Unique lead identifier")
    source: str = Field(..., description="Lead source: dm_instagram, dm_facebook, dm_whatsapp")
    platform: str = Field(..., description="Platform name")
    
    # Customer info
    customer_name: str = Field(..., description="Customer display name")
    customer_handle: str = Field(..., description="Social handle or username")
    customer_profile_url: Optional[str] = Field(None, description="Profile URL if available")
    
    # Message
    message: str = Field(..., description="Original DM message")
    message_id: Optional[str] = Field(None, description="Platform message ID")
    
    # Pre-analyzed by OmniDim (optional)
    intent: Optional[str] = Field(None, description="Detected intent")
    sentiment: Optional[str] = Field(None, description="Detected sentiment")
    
    # Contact info if provided
    contact_info: Optional[Dict[str, Any]] = Field(None, description="Phone, email if captured")
    
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DispatchCallRequest(BaseModel):
    """Request to dispatch an outbound call."""
    to_number: str = Field(..., description="Phone number with country code (e.g., +14165551234)")
    customer_name: str = Field("Customer", description="Customer name for context")
    
    # Task context (from Morning Brief)
    task_id: Optional[str] = Field(None, description="Associated task ID")
    task_title: Optional[str] = Field(None, description="Task description")
    priority: str = Field("normal", description="Priority: urgent, high, normal, low")
    
    # Business context
    business_id: str = Field("default", description="Business identifier")
    
    # Additional context
    notes: Optional[str] = Field(None, description="Additional notes for the agent")
    customer_tier: str = Field("standard", description="Customer tier: vip, premium, standard")
    
    # Agent override
    agent_id: Optional[int] = Field(None, description="Override default OmniDim agent")


# ==================== WEBHOOK SIGNATURE VERIFICATION ====================

def verify_webhook_signature(
    payload: bytes,
    signature: Optional[str],
    secret: str
) -> bool:
    """
    Verify OmniDimension webhook signature.
    
    OmniDim uses HMAC-SHA256 for webhook signatures.
    """
    if not secret:
        # Webhook secret not configured - skip verification
        return True
    
    if not signature:
        return False
    
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # Compare with timing-safe function
    return hmac.compare_digest(f"sha256={expected}", signature)


# ==================== P0 TASK 1: POST-CALL WEBHOOK ====================

@router.post("/api/brain/omnidim-callback")
async def handle_post_call_webhook(
    payload: OmniDimCallbackPayload,
    background_tasks: BackgroundTasks,
    request: Request,
    x_omnidim_signature: Optional[str] = Header(None, alias="X-OmniDim-Signature")
):
    """
    P0 Task 1: Post-Call Webhook Listener
    
    Receives call completion data from OmniDimension and:
    1. Validates webhook signature
    2. Parses Summary, Sentiment, Transcript
    3. Hydrates customer record in Redis memory
    4. Logs to Brain Debugger for observability
    
    OmniDim sends this webhook when:
    - Call completes (answered and ended)
    - Call fails (busy, no-answer, error)
    """
    # Verify signature if configured
    if OmniDimConfig.WEBHOOK_SECRET:
        body = await request.body()
        if not verify_webhook_signature(body, x_omnidim_signature, OmniDimConfig.WEBHOOK_SECRET):
            logger.warning(f"[OmniBridge] Invalid webhook signature for call {payload.call_id}")
            raise HTTPException(401, "Invalid webhook signature")
    
    logger.info(
        f"[OmniBridge] Post-call webhook received: "
        f"call_id={payload.call_id}, status={payload.status}, "
        f"duration={payload.duration}s, sentiment={payload.sentiment}"
    )
    
    # Convert to internal CallResult
    call_result = CallResult(
        call_id=payload.call_id,
        status=payload.status,
        duration_seconds=payload.duration,
        transcript=payload.transcript,
        summary=payload.summary,
        sentiment=payload.sentiment,
        sentiment_score=payload.sentiment_score,
        customer_phone=payload.to_number,
        agent_id=payload.agent_id,
        extracted_variables=payload.extracted_variables,
        web_search_results=payload.web_search_results,
        recording_url=payload.recording_url,
        timestamp=payload.timestamp
    )
    
    # Get business_id from call context or resolve via mapping
    business_id = "default"
    if payload.call_context:
        business_id = payload.call_context.get("business_id", "default")
    
    # Route to correct Unified Inbox based on agent_id
    mapping_service = get_mapping_service(_db)
    routing_result = await mapping_service.route_callback_to_inbox(
        agent_id=str(payload.agent_id),
        call_data={
            "call_id": payload.call_id,
            "to_number": payload.to_number,
            "summary": payload.summary,
            "transcript": payload.transcript,
            "sentiment": payload.sentiment,
            "sentiment_score": payload.sentiment_score,
            "duration": payload.duration,
            "call_context": payload.call_context
        }
    )
    
    # Use routed business_id if available
    if routing_result.get("routed"):
        business_id = routing_result.get("business_id", business_id)
    
    # Hydrate customer record in background
    background_tasks.add_task(
        hydrate_customer_async,
        call_result,
        business_id
    )
    
    # Log to Brain Debugger (store in MongoDB)
    db = get_db()
    debugger_entry = {
        "type": "omnidim_call",
        "call_id": payload.call_id,
        "status": payload.status,
        "duration": payload.duration,
        "summary": payload.summary,
        "sentiment": payload.sentiment,
        "sentiment_score": payload.sentiment_score,
        "transcript_preview": payload.transcript[:500] if payload.transcript else "",
        "extracted_variables": payload.extracted_variables,
        "web_search_results": payload.web_search_results,
        "business_id": business_id,
        "routed_to_inbox": routing_result.get("inbox_channel"),
        "customer_phone_masked": f"{payload.to_number[:6]}***",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        await db["brain_debugger_logs"].insert_one(debugger_entry.copy())
    except Exception as e:
        logger.error(f"[OmniBridge] Failed to log to Brain Debugger: {e}")
    
    return {
        "status": "received",
        "call_id": payload.call_id,
        "hydration_queued": True,
        "brain_debugger_logged": True,
        "routed_to_business": business_id,
        "inbox_channel": routing_result.get("inbox_channel"),
        "received_at": datetime.now(timezone.utc).isoformat()
    }


async def hydrate_customer_async(call_result: CallResult, business_id: str):
    """Background task to hydrate customer record."""
    try:
        result = await customer_hydrator.hydrate_from_call(call_result, business_id)
        logger.info(f"[OmniBridge] Customer hydration complete: {result.get('customer_key')}")
    except Exception as e:
        logger.error(f"[OmniBridge] Customer hydration failed: {e}")


# ==================== P0 TASK 2: MORNING BRIEF CALL DISPATCH ====================

@router.post("/api/omnidim/dispatch")
async def dispatch_outbound_call(
    request: DispatchCallRequest,
    background_tasks: BackgroundTasks
):
    """
    P0 Task 2: Morning Brief 'Call' Action
    
    One-click trigger to launch OmniDimension outbound call.
    
    Used by:
    - Morning Brief dashboard for high-priority task follow-ups
    - Unified Inbox for quick customer callbacks
    - Automated VIP escalation workflows
    
    Returns:
    - call_id: Unique identifier for tracking
    - status: queued (call will be initiated async)
    """
    # Build call context
    context = CallContext(
        customer_name=request.customer_name,
        customer_phone=request.to_number,
        task_id=request.task_id,
        task_title=request.task_title,
        priority=request.priority,
        business_id=request.business_id,
        morning_brief_tone="professional" if request.priority != "urgent" else "urgent",
        customer_tier=request.customer_tier,
        notes=request.notes
    )
    
    # Dispatch via OmniDim client
    result = await omnidim_client.dispatch_call(
        to_number=request.to_number,
        context=context,
        agent_id=request.agent_id
    )
    
    # Log dispatch attempt
    db = get_db()
    dispatch_log = {
        "type": "call_dispatch",
        "to_number_masked": f"{request.to_number[:6]}***",
        "task_id": request.task_id,
        "priority": request.priority,
        "business_id": request.business_id,
        "result": result,
        "dispatched_at": datetime.now(timezone.utc).isoformat()
    }
    
    background_tasks.add_task(
        log_dispatch_async,
        db,
        dispatch_log
    )
    
    if result.get("success"):
        return {
            "status": "dispatched",
            "call_id": result.get("call_id"),
            "to_number": request.to_number,
            "task_id": request.task_id,
            "source": result.get("source", "omnidim"),
            "dispatched_at": datetime.now(timezone.utc).isoformat()
        }
    else:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Call dispatch failed",
                "reason": result.get("error"),
                "source": result.get("source")
            }
        )


async def log_dispatch_async(db, log_entry: Dict):
    """Background task to log dispatch attempt."""
    try:
        await db["omnidim_dispatch_logs"].insert_one(log_entry)
    except Exception as e:
        logger.error(f"[OmniBridge] Failed to log dispatch: {e}")


@router.post("/api/omnidim/dispatch-for-task")
async def dispatch_for_morning_brief_task(
    task_id: str,
    customer_phone: str,
    business_id: str = Query("default")
):
    """
    Dispatch call specifically for a Morning Brief task.
    
    Looks up task details and dispatches with full context.
    """
    db = get_db()
    
    # Find the task
    task = await db["aurem_tasks"].find_one(
        {"id": task_id, "business_id": business_id},
        {"_id": 0}
    )
    
    if not task:
        raise HTTPException(404, f"Task not found: {task_id}")
    
    # Use briefing dispatcher
    result = await briefing_dispatcher.dispatch_for_task(
        task=task,
        customer_phone=customer_phone,
        business_id=business_id
    )
    
    return result


# ==================== P0 TASK 3: SOCIAL LEAD SENSOR ====================

@router.post("/api/brain/omnidim-lead")
async def handle_social_lead_webhook(
    payload: SocialLeadPayload,
    background_tasks: BackgroundTasks,
    request: Request,
    x_omnidim_signature: Optional[str] = Header(None, alias="X-OmniDim-Signature")
):
    """
    P0 Task 3: Social-Lead Sensor
    
    Receives leads captured by OmniDimension DM automation.
    
    When a potential customer DMs via Instagram/Facebook/WhatsApp:
    1. OmniDim captures the message
    2. Sends to this webhook
    3. Scout Agent analyzes intent and sentiment
    4. Lead is flagged in Unified Inbox with priority
    5. Real-time notification pushed to dashboard
    
    This creates a seamless lead capture → qualification → follow-up pipeline.
    """
    # Verify signature
    if OmniDimConfig.WEBHOOK_SECRET:
        body = await request.body()
        if not verify_webhook_signature(body, x_omnidim_signature, OmniDimConfig.WEBHOOK_SECRET):
            logger.warning(f"[OmniBridge] Invalid webhook signature for lead {payload.lead_id}")
            raise HTTPException(401, "Invalid webhook signature")
    
    logger.info(
        f"[OmniBridge] Social lead received: "
        f"lead_id={payload.lead_id}, source={payload.source}, "
        f"customer={payload.customer_name}"
    )
    
    # Convert to internal SocialLead
    lead = SocialLead(
        lead_id=payload.lead_id,
        source=payload.source,
        platform=payload.platform,
        customer_name=payload.customer_name,
        customer_handle=payload.customer_handle,
        message=payload.message,
        intent=payload.intent,
        sentiment=payload.sentiment,
        contact_info=payload.contact_info,
        timestamp=payload.timestamp
    )
    
    # Process via Scout Lead Processor
    result = await scout_lead_processor.process_social_lead(
        lead=lead,
        business_id="default"  # Could be determined from OmniDim account
    )
    
    return {
        "status": "processed",
        "lead_id": payload.lead_id,
        "inbox_id": result.get("inbox_id"),
        "priority": result.get("priority"),
        "analysis": result.get("analysis"),
        "processed_at": datetime.now(timezone.utc).isoformat()
    }


# ==================== STATUS & MONITORING ENDPOINTS ====================

@router.get("/api/omnidim/status")
async def get_integration_status():
    """
    Get OmniDimension integration status.
    
    Shows configuration state and connectivity.
    """
    config_status = OmniDimConfig.get_status()
    
    # Test connectivity if configured
    connectivity = {"tested": False, "status": "not_configured"}
    
    if config_status["configured"]:
        try:
            agents = await omnidim_client.get_agents()
            connectivity = {
                "tested": True,
                "status": "connected",
                "agents_found": len(agents)
            }
        except Exception as e:
            connectivity = {
                "tested": True,
                "status": "error",
                "error": str(e)
            }
    
    return {
        "integration": "omnidimension",
        "phase": "8.4",
        "codename": "Omni-Bridge",
        "description": "The Muscle - Voice AI Sales Rep reporting to AUREM Manager",
        "configuration": config_status,
        "connectivity": connectivity,
        "mode": "live" if config_status.get("configured") else "scaffold",
        "scaffold_note": None if config_status.get("configured") else (
            "OmniDim not configured - operating in scaffold mode. "
            "Set OMNIDIM_API_KEY and OMNIDIM_AGENT_ID to enable live calls."
        ),
        "endpoints": {
            "post_call_webhook": "/api/brain/omnidim-callback",
            "social_lead_webhook": "/api/brain/omnidim-lead",
            "dispatch_call": "/api/omnidim/dispatch",
            "dispatch_for_task": "/api/omnidim/dispatch-for-task"
        },
        "pricing": {
            "starter": "$0.105/min",
            "growth": "$0.070/min",
            "enterprise": "$0.04/min (custom)"
        },
        "checked_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/api/omnidim/logs")
async def get_call_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status")
):
    """
    Get call logs from OmniDimension.
    
    Returns recent calls with status, duration, and summary.
    """
    logs = await omnidim_client.get_call_logs(
        page=page,
        page_size=page_size,
        status=status
    )
    
    return {
        "logs": logs.get("logs", []),
        "total": logs.get("total", 0),
        "page": page,
        "page_size": page_size,
        "source": logs.get("source", "omnidim")
    }


@router.get("/api/omnidim/dispatchable-tasks")
async def get_dispatchable_tasks(
    business_id: str = Query("default")
):
    """
    Get tasks from Morning Brief that can trigger calls.
    
    Filters high-priority and relevant category tasks.
    """
    from routers.morning_brief_router import fetch_pending_tasks
    
    # Fetch pending tasks
    tasks = await fetch_pending_tasks(business_id, limit=20)
    
    # Filter dispatchable
    dispatchable = await briefing_dispatcher.get_dispatchable_tasks(tasks)
    
    return {
        "total_tasks": len(tasks),
        "dispatchable_count": len(dispatchable),
        "dispatchable_tasks": dispatchable,
        "business_id": business_id
    }


# ==================== BRAIN DEBUGGER INTEGRATION ====================

@router.get("/api/brain/omnidim-activity")
async def get_omnidim_activity(
    business_id: str = Query("default"),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get OmniDimension activity for Brain Debugger.
    
    Shows recent calls and leads processed through OmniBridge.
    """
    db = get_db()
    
    # Get call logs
    call_logs = await db["brain_debugger_logs"].find(
        {"type": "omnidim_call", "business_id": business_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Get lead logs
    lead_logs = await db["unified_inbox"].find(
        {"type": "social_lead", "business_id": business_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Get dispatch logs
    dispatch_logs = await db["omnidim_dispatch_logs"].find(
        {"business_id": business_id},
        {"_id": 0}
    ).sort("dispatched_at", -1).limit(limit).to_list(limit)
    
    return {
        "calls": {
            "count": len(call_logs),
            "items": call_logs
        },
        "leads": {
            "count": len(lead_logs),
            "items": lead_logs
        },
        "dispatches": {
            "count": len(dispatch_logs),
            "items": dispatch_logs
        },
        "business_id": business_id,
        "retrieved_at": datetime.now(timezone.utc).isoformat()
    }


# ==================== BUSINESS MAPPING ENDPOINTS ====================

@router.get("/api/omnidim/businesses")
async def list_businesses():
    """
    List all registered businesses in the Traffic Controller.
    
    Shows which businesses are mapped to which OmniDim agents.
    """
    mapping_service = get_mapping_service(_db)
    businesses = mapping_service.lookup_table.list_businesses()
    
    return {
        "businesses": businesses,
        "count": len(businesses),
        "retrieved_at": datetime.now(timezone.utc).isoformat()
    }


class AddBusinessRequest(BaseModel):
    """Request to add a new business to AUREM."""
    business_id: str = Field(..., description="Unique business identifier")
    name: str = Field(..., description="Business display name")
    vertical: str = Field(..., description="Business vertical: skincare, automotive, finance, enterprise")
    agent_id: str = Field(..., description="OmniDimension Agent ID")
    agent_name: str = Field(..., description="Agent display name")
    phone_numbers: List[str] = Field(default=[], description="Associated phone numbers")


@router.post("/api/omnidim/businesses")
async def add_business(request: AddBusinessRequest):
    """
    Add a new business to AUREM Traffic Controller.
    
    Enables rapid onboarding: "Add new business in minutes."
    Once added, calls to/from the specified phone numbers
    will be routed to the correct OmniDim agent.
    """
    mapping_service = get_mapping_service(_db)
    
    result = await mapping_service.add_business(
        business_id=request.business_id,
        name=request.name,
        vertical=request.vertical,
        agent_id=request.agent_id,
        agent_name=request.agent_name,
        phone_numbers=request.phone_numbers
    )
    
    return result


@router.get("/api/omnidim/resolve-agent")
async def resolve_agent(
    business_id: Optional[str] = Query(None, description="Business ID"),
    phone_number: Optional[str] = Query(None, description="Phone number"),
    customer_id: Optional[str] = Query(None, description="Customer ID"),
    intent: Optional[str] = Query(None, description="Detected intent")
):
    """
    Resolve which OmniDim agent should handle a call.
    
    Uses the Traffic Controller logic:
    1. Business ID lookup
    2. Phone number mapping
    3. Customer association
    4. Intent-based routing
    """
    mapping_service = get_mapping_service(_db)
    
    result = await mapping_service.resolve_agent_for_call(
        business_id=business_id,
        phone_number=phone_number,
        customer_id=customer_id,
        intent=intent
    )
    
    return result


class SmartDispatchRequest(BaseModel):
    """Request for smart call dispatch with automatic agent routing."""
    to_number: str = Field(..., description="Phone number to call")
    customer_name: str = Field("Customer", description="Customer name")
    
    # Context for agent resolution
    business_id: Optional[str] = Field(None, description="Override business ID")
    customer_id: Optional[str] = Field(None, description="Customer ID for lookup")
    intent: Optional[str] = Field(None, description="Call intent for routing")
    customer_tier: str = Field("standard", description="Customer tier: vip, premium, standard")
    
    # Task context
    task_id: Optional[str] = Field(None, description="Associated task ID")
    task_title: Optional[str] = Field(None, description="Task description")
    
    # Additional context
    notes: Optional[str] = Field(None, description="Additional notes for agent")


@router.post("/api/omnidim/dispatch-smart")
async def smart_dispatch_call(
    request: SmartDispatchRequest,
    background_tasks: BackgroundTasks
):
    """
    Smart call dispatch with automatic agent routing.
    
    Uses the Traffic Controller to:
    1. Resolve the correct business from context
    2. Select the appropriate agent (VIP vs standard)
    3. Hydrate metadata for the call
    4. Dispatch to OmniDimension
    """
    mapping_service = get_mapping_service(_db)
    
    # Resolve agent
    agent_resolution = await mapping_service.resolve_agent_for_call(
        business_id=request.business_id,
        phone_number=request.to_number,
        customer_id=request.customer_id,
        intent=request.intent
    )
    
    if not agent_resolution.get("success"):
        raise HTTPException(400, agent_resolution.get("error", "Could not resolve agent"))
    
    # Build call context with hydration metadata
    context = CallContext(
        customer_name=request.customer_name,
        customer_phone=request.to_number,
        task_id=request.task_id,
        task_title=request.task_title,
        priority="high" if request.customer_tier == "vip" else "normal",
        business_id=agent_resolution["business"]["id"],
        morning_brief_tone="professional",
        customer_tier=request.customer_tier,
        notes=request.notes
    )
    
    # Dispatch with resolved agent
    result = await omnidim_client.dispatch_call(
        to_number=request.to_number,
        context=context,
        agent_id=int(agent_resolution["agent_id"]) if agent_resolution["agent_id"].isdigit() else None
    )
    
    # Log dispatch
    db = get_db()
    dispatch_log = {
        "type": "smart_dispatch",
        "to_number_masked": f"{request.to_number[:6]}***",
        "business_id": agent_resolution["business"]["id"],
        "agent_id": agent_resolution["agent_id"],
        "agent_name": agent_resolution["agent_name"],
        "customer_tier": request.customer_tier,
        "result": result,
        "dispatched_at": datetime.now(timezone.utc).isoformat()
    }
    
    background_tasks.add_task(log_dispatch_async, db, dispatch_log)
    
    return {
        "status": "dispatched" if result.get("success") else "failed",
        "call_id": result.get("call_id"),
        "agent": {
            "id": agent_resolution["agent_id"],
            "name": agent_resolution["agent_name"],
            "persona": agent_resolution["agent_persona"]
        },
        "business": agent_resolution["business"],
        "hydration_metadata": agent_resolution["hydration_metadata"],
        "dispatched_at": datetime.now(timezone.utc).isoformat()
    }


# ==================== A2A HANDOFF ENDPOINTS ====================

class A2AHandoffRequest(BaseModel):
    """Request to execute an A2A handoff."""
    from_agent: str = Field(..., description="Source agent ID")
    to_agent: str = Field(..., description="Target agent ID")
    task_type: str = Field(..., description="Task type: payment, booking, email, etc.")
    params: Dict[str, Any] = Field(default={}, description="Task parameters")
    
    # Handoff config
    handoff_type: str = Field("delegate", description="Handoff type: delegate, transfer, consult")
    priority: str = Field("normal", description="Priority: critical, high, normal, low")
    
    # Context
    context: Dict[str, Any] = Field(default={}, description="Additional context")
    customer_info: Dict[str, Any] = Field(default={}, description="Customer information")
    
    # Business context
    from_business_id: str = Field("", description="Source business ID")
    to_business_id: str = Field("", description="Target business ID")


@router.post("/api/a2a/handoff")
async def execute_a2a_handoff(request: A2AHandoffRequest):
    """
    Execute an Agent-to-Agent handoff.
    
    Enables agents to delegate tasks to specialists:
    - Sales Agent needs payment → Delegates to Finance Agent
    - Support call becomes sales → Transfers to Sales Agent
    - Auto Agent needs pricing → Consults Finance Agent
    
    Handoff Types:
    - DELEGATE: "Do this for me" (async, returns result)
    - TRANSFER: "Take over" (sync, full context handoff)
    - CONSULT: "Advise me" (sync, returns recommendation)
    """
    a2a_service = get_a2a_service(_db)
    
    # Map string to enum
    try:
        handoff_type = HandoffType(request.handoff_type)
    except ValueError:
        handoff_type = HandoffType.DELEGATE
    
    try:
        priority = HandoffPriority(request.priority)
    except ValueError:
        priority = HandoffPriority.NORMAL
    
    # Create and execute handoff
    handoff_request = await a2a_service.create_handoff(
        from_agent=request.from_agent,
        to_agent=request.to_agent,
        task=f"{request.handoff_type}: {request.task_type}",
        task_type=request.task_type,
        params=request.params,
        handoff_type=handoff_type,
        priority=priority,
        context=request.context,
        customer_info=request.customer_info,
        from_business_id=request.from_business_id,
        to_business_id=request.to_business_id
    )
    
    result = await a2a_service.execute_handoff(handoff_request)
    
    return {
        "handoff_id": result.request_id,
        "status": result.status.value,
        "success": result.success,
        "from_agent": result.from_agent,
        "to_agent": result.to_agent,
        "result": result.result,
        "error": result.error,
        "execution_time_ms": result.execution_time_ms,
        "completed_at": result.completed_at
    }


@router.get("/api/a2a/history")
async def get_a2a_history(
    business_id: Optional[str] = Query(None, description="Filter by business"),
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get A2A handoff history.
    
    Shows which agents have delegated tasks to each other.
    """
    a2a_service = get_a2a_service(_db)
    
    history = await a2a_service.get_handoff_history(
        business_id=business_id,
        agent_id=agent_id,
        limit=limit
    )
    
    return {
        "handoffs": history,
        "count": len(history),
        "retrieved_at": datetime.now(timezone.utc).isoformat()
    }


@router.post("/api/a2a/delegate/{task_type}")
async def quick_delegate(
    task_type: str,
    from_agent: str = Query(..., description="Source agent"),
    to_agent: str = Query(..., description="Target agent"),
    amount: Optional[float] = Query(None, description="Amount (for payment tasks)"),
    description: Optional[str] = Query(None, description="Description"),
    customer_email: Optional[str] = Query(None, description="Customer email")
):
    """
    Quick delegation endpoint for common tasks.
    
    Example:
    POST /api/a2a/delegate/create_payment_link?from_agent=skincare&to_agent=finance&amount=299
    """
    a2a_service = get_a2a_service(_db)
    
    params = {}
    if amount:
        params["amount"] = amount
    if description:
        params["description"] = description
    if customer_email:
        params["customer_email"] = customer_email
    
    result = await a2a_service.delegate(
        from_agent=from_agent,
        to_agent=to_agent,
        task_type=task_type,
        params=params
    )
    
    return {
        "handoff_id": result.request_id,
        "success": result.success,
        "result": result.result,
        "error": result.error
    }


# ==================== UNIFIED INBOX ROUTING ====================

@router.get("/api/omnidim/inbox/{business_id}")
async def get_business_inbox(
    business_id: str,
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, description="Filter by status")
):
    """
    Get Unified Inbox entries for a specific business.
    
    Shows calls and leads routed to this business's dashboard.
    """
    db = get_db()
    
    query = {"business_id": business_id}
    if status:
        query["status"] = status
    
    # Get inbox entries (calls + leads)
    entries = await db["unified_inbox"].find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Get counts by type
    call_count = sum(1 for e in entries if e.get("type") == "voice_call")
    lead_count = sum(1 for e in entries if e.get("type") == "social_lead")
    
    # Get mapping service for business info
    mapping_service = get_mapping_service(_db)
    business_config = mapping_service.lookup_table.get_business(business_id)
    
    return {
        "business": {
            "id": business_id,
            "name": business_config.name if business_config else business_id,
            "channel": business_config.unified_inbox_channel if business_config else f"inbox:{business_id}"
        },
        "entries": entries,
        "counts": {
            "total": len(entries),
            "calls": call_count,
            "leads": lead_count
        },
        "retrieved_at": datetime.now(timezone.utc).isoformat()
    }
