"""
AUREM Premium Features API Routes
- Proactive Follow-Up Management
- Human Handoff/Coexistence Control
- Multi-Modal Processing Status
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/premium", tags=["Premium Features"])

# Database reference
db = None

def set_db(database):
    global db
    db = database


# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class FollowUpRequest(BaseModel):
    business_id: str
    timing: str = "24h"  # 24h, 48h, 7d, 14d, 30d


class HandoffRequest(BaseModel):
    customer_id: str
    business_id: str
    human_id: str
    reason: str = "human_reply"


class ResumeAIRequest(BaseModel):
    customer_id: str
    reason: str = "manual"


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH HELPER
# ═══════════════════════════════════════════════════════════════════════════════

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"_id": "admin", "email": "admin@aurem.ai", "role": "admin"}


# ═══════════════════════════════════════════════════════════════════════════════
# PROACTIVE FOLLOW-UP ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/followup/run")
async def run_followup_cycle(request: FollowUpRequest, user = Depends(get_current_user)):
    """
    Run proactive follow-up cycle for a business
    Tier 2/3 Feature
    """
    from services.proactive_followup_service import get_followup_engine, FollowUpTiming
    
    engine = get_followup_engine(db)
    
    try:
        timing = FollowUpTiming(request.timing)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid timing: {request.timing}")
    
    result = await engine.run_followup_cycle(
        business_id=request.business_id,
        timing=timing
    )
    
    return result


@router.get("/followup/candidates/{business_id}")
async def get_followup_candidates(
    business_id: str,
    timing: str = "24h",
    user = Depends(get_current_user)
):
    """Get list of conversations needing follow-up"""
    from services.proactive_followup_service import get_followup_engine, FollowUpTiming
    
    engine = get_followup_engine(db)
    
    try:
        timing_enum = FollowUpTiming(timing)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid timing: {timing}")
    
    candidates = await engine.find_conversations_needing_followup(business_id, timing_enum)
    
    return {
        "business_id": business_id,
        "timing": timing,
        "count": len(candidates),
        "conversations": candidates
    }


@router.put("/followup/status/{customer_id}")
async def update_followup_status(
    customer_id: str,
    status: str,
    notes: str = "",
    user = Depends(get_current_user)
):
    """Update follow-up status for a conversation"""
    from services.proactive_followup_service import get_followup_engine, FollowUpStatus
    
    engine = get_followup_engine(db)
    
    try:
        status_enum = FollowUpStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    success = await engine.update_conversation_status(customer_id, status_enum, notes)
    
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    return {
        "customer_id": customer_id,
        "status": status,
        "updated": True
    }


# ═══════════════════════════════════════════════════════════════════════════════
# WHATSAPP COEXISTENCE / HANDOFF ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/handoff/takeover")
async def human_takeover(request: HandoffRequest, user = Depends(get_current_user)):
    """
    Human takes over conversation from AI
    Tier 1 Critical Feature
    """
    from services.whatsapp_coexistence import get_coexistence_manager, HandoffReason
    
    manager = get_coexistence_manager(db)
    
    try:
        reason = HandoffReason(request.reason)
    except ValueError:
        reason = HandoffReason.HUMAN_REPLY
    
    result = await manager.handle_human_takeover(
        customer_id=request.customer_id,
        business_id=request.business_id,
        human_id=request.human_id,
        reason=reason
    )
    
    return result


@router.post("/handoff/resume-ai")
async def resume_ai(request: ResumeAIRequest, user = Depends(get_current_user)):
    """Resume AI mode after human handoff"""
    from services.whatsapp_coexistence import get_coexistence_manager
    
    manager = get_coexistence_manager(db)
    result = await manager.resume_ai_mode(request.customer_id, request.reason)
    
    return result


@router.get("/handoff/state/{customer_id}")
async def get_conversation_state(customer_id: str, user = Depends(get_current_user)):
    """Get current conversation handoff state"""
    from services.whatsapp_coexistence import get_coexistence_manager
    
    manager = get_coexistence_manager(db)
    state = await manager.get_conversation_state(customer_id)
    
    return state.dict()


@router.get("/handoff/active/{business_id}")
async def get_active_human_conversations(
    business_id: str,
    human_id: str = None,
    user = Depends(get_current_user)
):
    """Get all conversations currently in human mode"""
    from services.whatsapp_coexistence import get_coexistence_manager
    
    manager = get_coexistence_manager(db)
    conversations = await manager.get_active_human_conversations(business_id, human_id)
    
    return {
        "business_id": business_id,
        "human_id": human_id,
        "count": len(conversations),
        "conversations": conversations
    }


@router.post("/handoff/escalate")
async def escalate_to_human(
    customer_id: str,
    business_id: str,
    reason: str,
    context: str = "",
    user = Depends(get_current_user)
):
    """AI escalates conversation to human"""
    from services.whatsapp_coexistence import get_coexistence_manager, HandoffReason
    
    manager = get_coexistence_manager(db)
    
    try:
        reason_enum = HandoffReason(reason)
    except ValueError:
        reason_enum = HandoffReason.COMPLEX_QUERY
    
    result = await manager.escalate_to_human(
        customer_id=customer_id,
        business_id=business_id,
        reason=reason_enum,
        ai_context=context
    )
    
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-MODAL PROCESSING STATUS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/multimodal/status")
async def get_multimodal_status(user = Depends(get_current_user)):
    """Get multi-modal processing capabilities status"""
    from services.multimodal_processor import get_multimodal_processor
    
    processor = get_multimodal_processor()
    
    return {
        "enabled": True,
        "supported_types": ["text", "audio", "image", "video", "document"],
        "audio_transcription": "openai-whisper",
        "image_analysis": "gpt-4o-vision",
        "max_image_size_mb": processor.max_image_size / (1024 * 1024),
        "max_audio_duration_seconds": processor.max_audio_duration,
        "tier": "Premium Tier 3"
    }


@router.post("/multimodal/process")
async def process_multimodal_message(
    message_data: Dict[str, Any],
    user = Depends(get_current_user)
):
    """Process a multi-modal message (testing endpoint)"""
    from services.multimodal_processor import get_multimodal_processor
    
    processor = get_multimodal_processor()
    result = await processor.process_message(message_data)
    
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# PREMIUM FEATURES DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard/{business_id}")
async def get_premium_dashboard(business_id: str, user = Depends(get_current_user)):
    """Get overview of all premium features for a business"""
    from services.proactive_followup_service import get_followup_engine
    from services.whatsapp_coexistence import get_coexistence_manager
    
    # Follow-up stats
    followup_engine = get_followup_engine(db)
    pending_24h = await followup_engine.find_conversations_needing_followup(
        business_id,
        timing="24h"
    )
    
    # Handoff stats
    coexistence = get_coexistence_manager(db)
    active_human = await coexistence.get_active_human_conversations(business_id)
    
    # Multi-modal stats (from last 7 days)
    multimodal_stats = {
        "audio_processed": 0,
        "images_analyzed": 0,
        "total_multimodal": 0
    }
    
    if db is not None:
        # Count messages with multimodal metadata
        audio_count = await db.aurem_messages.count_documents({
            "business_id": business_id,
            "metadata.original_type": "audio"
        })
        image_count = await db.aurem_messages.count_documents({
            "business_id": business_id,
            "metadata.original_type": "image"
        })
        multimodal_stats = {
            "audio_processed": audio_count,
            "images_analyzed": image_count,
            "total_multimodal": audio_count + image_count
        }
    
    return {
        "business_id": business_id,
        "premium_features": {
            "proactive_followup": {
                "enabled": True,
                "pending_24h": len(pending_24h),
                "tier": "2/3"
            },
            "human_coexistence": {
                "enabled": True,
                "active_handoffs": len(active_human),
                "tier": "1"
            },
            "multimodal_processing": {
                "enabled": True,
                "stats": multimodal_stats,
                "tier": "3"
            }
        },
        "timestamp": datetime.now().isoformat()
    }


print("[STARTUP] Premium Features Routes loaded")
