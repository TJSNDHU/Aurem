"""
Panic Button Settings Router
API endpoints for configuring panic button per tenant

Endpoints:
- GET  /api/panic/settings - Get current panic configuration
- POST /api/panic/settings - Update panic configuration
- GET  /api/panic/events - List panic events
- GET  /api/panic/events/{event_id} - Get specific panic event
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/panic", tags=["Panic Button"])

# MongoDB connection
db = None

def set_db(database):
    global db
    db = database


class PanicConfig(BaseModel):
    """Panic button configuration"""
    enabled: bool = True
    alert_phone: Optional[str] = None
    alert_email: Optional[EmailStr] = None
    sensitivity_threshold: float = -0.7  # -1.0 to 1.0
    custom_keywords: List[str] = []
    auto_pause_ai: bool = True
    alert_channels: List[str] = ["email"]  # ["email", "sms", "webhook"]
    webhook_url: Optional[str] = None


@router.get("/settings")
async def get_panic_settings(
    tenant_id: str = "aurem_platform"  # TODO: Get from JWT
):
    """
    Get current panic button configuration for tenant
    
    Returns:
        {
            "success": true,
            "config": PanicConfig
        }
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        tenant = await db.users.find_one(
            {"tenant_id": tenant_id},
            {"_id": 0, "panic_config": 1}
        )
        
        if not tenant:
            raise HTTPException(404, "Tenant not found")
        
        config = tenant.get("panic_config", {})
        
        # Merge with defaults
        default_config = PanicConfig().dict()
        merged_config = {**default_config, **config}
        
        return {
            "success": True,
            "config": merged_config
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PanicSettings] Error getting settings: {e}")
        raise HTTPException(500, str(e))


@router.post("/settings")
async def update_panic_settings(
    config: PanicConfig,
    tenant_id: str = "aurem_platform"  # TODO: Get from JWT
):
    """
    Update panic button configuration
    
    Body: PanicConfig
    
    Returns:
        {
            "success": true,
            "config": PanicConfig
        }
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Validate threshold
        if not -1.0 <= config.sensitivity_threshold <= 1.0:
            raise HTTPException(400, "Sensitivity threshold must be between -1.0 and 1.0")
        
        # Validate alert channels
        valid_channels = ["email", "sms", "webhook"]
        for channel in config.alert_channels:
            if channel not in valid_channels:
                raise HTTPException(400, f"Invalid alert channel: {channel}")
        
        # Update tenant config
        result = await db.users.update_one(
            {"tenant_id": tenant_id},
            {"$set": {
                "panic_config": config.dict(),
                "panic_config_updated_at": datetime.now(timezone.utc)
            }}
        )
        
        if result.matched_count == 0:
            raise HTTPException(404, "Tenant not found")
        
        logger.info(f"[PanicSettings] Updated config for {tenant_id}")
        
        return {
            "success": True,
            "config": config.dict()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PanicSettings] Error updating settings: {e}")
        raise HTTPException(500, str(e))


@router.get("/events")
async def get_panic_events(
    status: Optional[str] = None,  # triggered, human_controlling, resolved
    limit: int = 50,
    tenant_id: str = "aurem_platform"  # TODO: Get from JWT
):
    """
    Get list of panic events for tenant
    
    Query params:
        status: Filter by status
        limit: Max events to return
    
    Returns:
        {
            "success": true,
            "count": int,
            "events": [PanicEvent]
        }
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        query = {"tenant_id": tenant_id}
        
        if status:
            query["status"] = status
        
        events = await db.panic_events.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)
        
        # Convert datetime to ISO strings
        for event in events:
            if "created_at" in event and isinstance(event["created_at"], datetime):
                event["created_at"] = event["created_at"].isoformat()
            if "alerted_at" in event and isinstance(event["alerted_at"], datetime):
                event["alerted_at"] = event["alerted_at"].isoformat()
            if "taken_over_at" in event and isinstance(event["taken_over_at"], datetime):
                event["taken_over_at"] = event["taken_over_at"].isoformat()
            if "resolved_at" in event and isinstance(event["resolved_at"], datetime):
                event["resolved_at"] = event["resolved_at"].isoformat()
        
        return {
            "success": True,
            "count": len(events),
            "events": events
        }
    
    except Exception as e:
        logger.error(f"[PanicSettings] Error getting events: {e}")
        raise HTTPException(500, str(e))


@router.get("/events/{event_id}")
async def get_panic_event(
    event_id: str,
    tenant_id: str = "aurem_platform"  # TODO: Get from JWT
):
    """
    Get specific panic event details
    
    Returns:
        {
            "success": true,
            "event": PanicEvent
        }
    """
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        event = await db.panic_events.find_one(
            {"event_id": event_id, "tenant_id": tenant_id},
            {"_id": 0}
        )
        
        if not event:
            raise HTTPException(404, "Panic event not found")
        
        # Convert datetime to ISO strings
        if "created_at" in event and isinstance(event["created_at"], datetime):
            event["created_at"] = event["created_at"].isoformat()
        if "alerted_at" in event and isinstance(event["alerted_at"], datetime):
            event["alerted_at"] = event["alerted_at"].isoformat()
        if "taken_over_at" in event and isinstance(event["taken_over_at"], datetime):
            event["taken_over_at"] = event["taken_over_at"].isoformat()
        if "resolved_at" in event and isinstance(event["resolved_at"], datetime):
            event["resolved_at"] = event["resolved_at"].isoformat()
        
        return {
            "success": True,
            "event": event
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PanicSettings] Error getting event {event_id}: {e}")
        raise HTTPException(500, str(e))
