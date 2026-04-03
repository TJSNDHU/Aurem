"""
AUREM Daily Digest API Routes
Centralized notification engine
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/digest", tags=["Daily Digest"])

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
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class RecordEventRequest(BaseModel):
    event_type: str
    title: str
    description: str
    business_id: str
    priority: str = "medium"  # critical, high, medium, low
    metadata: Dict[str, Any] = {}
    action_required: bool = False
    action_url: Optional[str] = None


class GenerateDigestRequest(BaseModel):
    business_id: str
    hours: int = 24


class SendDigestRequest(BaseModel):
    business_id: str
    channel: str = "whatsapp"  # whatsapp, email, dashboard
    recipient: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/record-event")
async def record_event(request: RecordEventRequest, user = Depends(get_current_user)):
    """
    Record event for digest aggregation
    
    All system events should flow through here:
    - Cart abandonments
    - New leads
    - System errors
    - Revenue milestones
    - Customer feedback
    """
    from services.daily_digest import get_digest_engine, EventPriority
    
    engine = get_digest_engine(db)
    
    try:
        priority = EventPriority(request.priority)
    except ValueError:
        priority = EventPriority.MEDIUM
    
    event_id = await engine.record_event(
        event_type=request.event_type,
        title=request.title,
        description=request.description,
        business_id=request.business_id,
        priority=priority,
        metadata=request.metadata,
        action_required=request.action_required,
        action_url=request.action_url
    )
    
    return {
        "event_id": event_id,
        "recorded": True,
        "priority": request.priority
    }


@router.post("/generate")
async def generate_digest(request: GenerateDigestRequest, user = Depends(get_current_user)):
    """
    Generate daily digest for a business
    
    This is the "orchestrator" - aggregates all events and creates
    one intelligent summary instead of spam.
    """
    from services.daily_digest import get_digest_engine
    
    engine = get_digest_engine(db)
    
    start_time = datetime.now(timezone.utc) - timedelta(hours=request.hours)
    end_time = datetime.now(timezone.utc)
    
    digest = await engine.generate_daily_digest(
        business_id=request.business_id,
        start_time=start_time,
        end_time=end_time
    )
    
    return digest


@router.post("/send")
async def send_digest(request: SendDigestRequest, user = Depends(get_current_user)):
    """
    Generate and send digest via specified channel
    
    Channels: whatsapp, email, dashboard
    """
    from services.daily_digest import get_digest_engine
    
    engine = get_digest_engine(db)
    
    result = await engine.send_digest(
        business_id=request.business_id,
        channel=request.channel,
        recipient=request.recipient
    )
    
    return result


@router.get("/events/{business_id}")
async def get_events(
    business_id: str,
    hours: int = 24,
    priority: str = None,
    user = Depends(get_current_user)
):
    """Get recent events for a business"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not available")
    
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    query = {
        "business_id": business_id,
        "timestamp": {"$gte": start_time}
    }
    
    if priority:
        query["priority"] = priority
    
    events = await db.aurem_digest_events.find(
        query,
        {"_id": 0}
    ).sort("timestamp", -1).to_list(100)
    
    return {
        "business_id": business_id,
        "period_hours": hours,
        "count": len(events),
        "events": events
    }


@router.get("/stats/{business_id}")
async def get_digest_stats(
    business_id: str,
    days: int = 7,
    user = Depends(get_current_user)
):
    """Get digest statistics for a business"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not available")
    
    start_time = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Count events by priority
    pipeline = [
        {
            "$match": {
                "business_id": business_id,
                "timestamp": {"$gte": start_time}
            }
        },
        {
            "$group": {
                "_id": "$priority",
                "count": {"$sum": 1}
            }
        }
    ]
    
    results = await db.aurem_digest_events.aggregate(pipeline).to_list(10)
    
    stats = {
        "business_id": business_id,
        "period_days": days,
        "total_events": sum(r["count"] for r in results),
        "by_priority": {r["_id"]: r["count"] for r in results},
        "avg_per_day": 0
    }
    
    if days > 0:
        stats["avg_per_day"] = round(stats["total_events"] / days, 1)
    
    return stats


@router.delete("/events/{business_id}")
async def clear_events(
    business_id: str,
    older_than_days: int = 30,
    user = Depends(get_current_user)
):
    """Clear old events for a business"""
    if not db:
        raise HTTPException(status_code=500, detail="Database not available")
    
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    
    result = await db.aurem_digest_events.delete_many({
        "business_id": business_id,
        "timestamp": {"$lt": cutoff_time}
    })
    
    return {
        "business_id": business_id,
        "deleted_count": result.deleted_count,
        "older_than_days": older_than_days
    }


print("[STARTUP] Daily Digest Routes loaded")
