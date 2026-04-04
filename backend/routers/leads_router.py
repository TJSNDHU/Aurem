"""
Leads Router
API endpoints for lead management and dashboard

Endpoints:
- GET  /api/leads - List all leads for tenant
- GET  /api/leads/{lead_id} - Get lead details
- POST /api/leads/{lead_id}/status - Update lead status
- GET  /api/leads/stats - Get lead statistics
- POST /api/leads/test-capture - Test lead capture (development only)
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/leads", tags=["Leads"])

# MongoDB connection (will be set by server.py)
db = None


def set_db(database):
    global db
    db = database


class LeadStatusUpdate(BaseModel):
    status: str  # new, contacted, converted, lost


class TestLeadCaptureRequest(BaseModel):
    """For testing lead capture in development"""
    tenant_id: str = "test_tenant"
    conversation_id: str = "test_conv_123"
    user_message: str
    conversation_history: Optional[List[Dict]] = None


@router.get("")
async def get_leads(
    status: Optional[str] = None,
    limit: int = 50,
    tenant_id: str = "aurem_platform"  # TODO: Get from TenantContext
):
    """
    Get leads for current tenant
    
    Query params:
        status: Filter by status (new, contacted, converted, lost)
        limit: Max number of leads (default: 50)
    
    Returns:
        List of lead objects
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        from services.lead_capture_service import get_lead_capture_service
        
        lead_service = get_lead_capture_service(db)
        leads = await lead_service.get_leads(
            tenant_id=tenant_id,
            status=status,
            limit=limit
        )
        
        return {
            "success": True,
            "count": len(leads),
            "leads": leads
        }
    
    except Exception as e:
        logger.error(f"[LeadsRouter] Error getting leads: {e}")
        raise HTTPException(500, str(e))


@router.get("/stats")
async def get_lead_stats(
    period: str = "today",  # today, week, month, all
    tenant_id: str = "aurem_platform"  # TODO: Get from TenantContext
):
    """
    Get lead statistics for dashboard
    
    Query params:
        period: Time period (today, week, month, all)
    
    Returns:
        {
            "total_leads": int,
            "new_leads": int,
            "converted": int,
            "total_value": float,
            "conversion_rate": float
        }
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        from services.lead_capture_service import get_lead_capture_service
        
        lead_service = get_lead_capture_service(db)
        stats = await lead_service.get_lead_stats(
            tenant_id=tenant_id,
            period=period
        )
        
        return {
            "success": True,
            "period": period,
            "stats": stats
        }
    
    except Exception as e:
        logger.error(f"[LeadsRouter] Error getting stats: {e}")
        raise HTTPException(500, str(e))


@router.get("/{lead_id}")
async def get_lead_details(
    lead_id: str,
    tenant_id: str = "aurem_platform"  # TODO: Get from TenantContext
):
    """
    Get detailed information about a specific lead
    
    Returns:
        Full lead object with conversation transcript
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        lead = await db.leads.find_one(
            {"lead_id": lead_id, "tenant_id": tenant_id},
            {"_id": 0}
        )
        
        if not lead:
            raise HTTPException(404, f"Lead not found: {lead_id}")
        
        return {
            "success": True,
            "lead": lead
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LeadsRouter] Error getting lead {lead_id}: {e}")
        raise HTTPException(500, str(e))


@router.post("/{lead_id}/status")
async def update_lead_status(
    lead_id: str,
    request: LeadStatusUpdate,
    tenant_id: str = "aurem_platform"  # TODO: Get from TenantContext
):
    """
    Update lead status
    
    Body:
        {
            "status": "contacted" | "converted" | "lost"
        }
    
    Returns:
        Updated lead object
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Validate status
        valid_statuses = ["new", "contacted", "converted", "lost"]
        if request.status not in valid_statuses:
            raise HTTPException(400, f"Invalid status. Must be one of: {valid_statuses}")
        
        # Update lead
        result = await db.leads.update_one(
            {"lead_id": lead_id, "tenant_id": tenant_id},
            {
                "$set": {
                    "status": request.status,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(404, f"Lead not found: {lead_id}")
        
        # Get updated lead
        lead = await db.leads.find_one(
            {"lead_id": lead_id},
            {"_id": 0}
        )
        
        logger.info(f"[LeadsRouter] Updated lead {lead_id} status to {request.status}")
        
        return {
            "success": True,
            "lead": lead
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LeadsRouter] Error updating lead {lead_id}: {e}")
        raise HTTPException(500, str(e))


@router.post("/test-capture")
async def test_lead_capture(request: TestLeadCaptureRequest):
    """
    Test lead capture functionality (development only)
    
    Body:
        {
            "tenant_id": "test_tenant",
            "conversation_id": "test_conv_123",
            "user_message": "I want to book an appointment tomorrow",
            "conversation_history": [...]  # optional
        }
    
    Returns:
        Lead capture result
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        from services.lead_capture_service import get_lead_capture_service
        from services.aurem_hooks.lead_capture_hook import get_lead_capture_hook
        
        # Build conversation history
        conversation = request.conversation_history or []
        conversation.append({
            "role": "user",
            "content": request.user_message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Execute lead capture hook
        hook = get_lead_capture_hook(db)
        result = await hook.execute(
            tenant_id=request.tenant_id,
            conversation_id=request.conversation_id,
            conversation_history=conversation,
            latest_user_message=request.user_message,
            latest_ai_response="I'd be happy to help you book an appointment!",
            metadata={"source": "test"}
        )
        
        return {
            "success": True,
            "result": result
        }
    
    except Exception as e:
        logger.error(f"[LeadsRouter] Test capture error: {e}")
        raise HTTPException(500, str(e))
