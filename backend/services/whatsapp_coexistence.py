"""
AUREM WhatsApp Coexistence & Human Handoff System
Allows business owners to take over conversations from AI
Tier 1 Critical Feature
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ConversationMode(str, Enum):
    """Conversation handling mode"""
    AI_MODE = "ai_mode"           # Fully automated
    HUMAN_MODE = "human_mode"     # Human took over
    HYBRID_MODE = "hybrid_mode"   # Both can respond
    PAUSED = "paused"             # Waiting for human decision


class HandoffReason(str, Enum):
    """Reason for human handoff"""
    HUMAN_REPLY = "human_reply"           # Human sent a message
    COMPLEX_QUERY = "complex_query"       # AI escalated
    CUSTOMER_REQUEST = "customer_request" # Customer asked for human
    HIGH_VALUE = "high_value"             # High-value opportunity
    NEGATIVE_SENTIMENT = "negative_sentiment"  # Customer unhappy


class ConversationState(BaseModel):
    """State tracking for a conversation"""
    customer_id: str
    business_id: str
    mode: ConversationMode = ConversationMode.AI_MODE
    last_human_activity: Optional[datetime] = None
    last_ai_activity: Optional[datetime] = None
    handoff_reason: Optional[HandoffReason] = None
    assigned_human: Optional[str] = None  # User ID of human handling
    notes: str = ""
    auto_resume_at: Optional[datetime] = None  # When to auto-resume AI


class CoexistenceManager:
    """
    WhatsApp Coexistence & Handoff Manager
    
    Features:
    - Detects when human enters conversation
    - Pauses AI when human is active
    - Auto-resumes AI after human inactivity
    - Supports hybrid mode (both can respond)
    - Tracks handoff reasons and context
    """
    
    def __init__(self, db=None):
        self.db = db
        self.human_inactivity_threshold = timedelta(hours=2)  # Resume AI after 2h
        self.handoff_cooldown = timedelta(minutes=5)  # Don't flip-flop too quickly
    
    async def detect_human_activity(
        self,
        business_id: str,
        sender_id: str,
        message_content: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Detect if this message is from a human (not customer, not AI)
        
        Indicators:
        - Message from business phone number
        - Metadata indicates manual send
        - Sender ID matches business owner/staff
        """
        if not metadata:
            metadata = {}
        
        # Check if explicitly marked as human
        if metadata.get("source") == "human":
            return True
        
        # Check if sender is a staff member
        if self.db is not None:
            staff = await self.db.aurem_staff.find_one({
                "business_id": business_id,
                "phone": sender_id
            })
            if staff:
                return True
        
        # Check for business phone number match
        if self.db is not None:
            business = await self.db.aurem_businesses.find_one({
                "business_id": business_id
            })
            if business and business.get("phone") == sender_id:
                return True
        
        return False
    
    async def get_conversation_state(
        self,
        customer_id: str
    ) -> ConversationState:
        """Get current conversation state"""
        if self.db is None:
            # Default state
            return ConversationState(
                customer_id=customer_id,
                business_id="unknown",
                mode=ConversationMode.AI_MODE
            )
        
        state_doc = await self.db.aurem_conversation_states.find_one({
            "customer_id": customer_id
        })
        
        if state_doc:
            state_doc.pop("_id", None)
            return ConversationState(**state_doc)
        
        # Create new state
        state = ConversationState(
            customer_id=customer_id,
            business_id="unknown"
        )
        await self.db.aurem_conversation_states.insert_one(state.dict())
        return state
    
    async def update_conversation_state(
        self,
        customer_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """Update conversation state"""
        if self.db is None:
            return False
        
        result = await self.db.aurem_conversation_states.update_one(
            {"customer_id": customer_id},
            {"$set": {
                **updates,
                "updated_at": datetime.now(timezone.utc)
            }},
            upsert=True
        )
        
        return result.modified_count > 0 or result.upserted_id is not None
    
    async def handle_human_takeover(
        self,
        customer_id: str,
        business_id: str,
        human_id: str,
        reason: HandoffReason = HandoffReason.HUMAN_REPLY
    ) -> Dict[str, Any]:
        """
        Handle human taking over the conversation
        - Pause AI
        - Log handoff
        - Set auto-resume timer
        """
        logger.info(f"Human takeover: {customer_id} by {human_id}, reason: {reason.value}")
        
        # Update state
        await self.update_conversation_state(
            customer_id=customer_id,
            updates={
                "mode": ConversationMode.HUMAN_MODE.value,
                "last_human_activity": datetime.now(timezone.utc),
                "handoff_reason": reason.value,
                "assigned_human": human_id,
                "auto_resume_at": datetime.now(timezone.utc) + self.human_inactivity_threshold
            }
        )
        
        # Log event
        if self.db is not None:
            await self.db.aurem_handoff_log.insert_one({
                "customer_id": customer_id,
                "business_id": business_id,
                "event": "human_takeover",
                "human_id": human_id,
                "reason": reason.value,
                "timestamp": datetime.now(timezone.utc)
            })
        
        return {
            "status": "human_mode",
            "message": "AI paused - human is handling this conversation",
            "auto_resume_in_hours": self.human_inactivity_threshold.total_seconds() / 3600
        }
    
    async def should_ai_respond(
        self,
        customer_id: str,
        business_id: str
    ) -> Dict[str, Any]:
        """
        Check if AI should respond to this customer message
        
        Returns:
        - should_respond: bool
        - reason: str
        - mode: ConversationMode
        """
        state = await self.get_conversation_state(customer_id)
        
        # AI mode - always respond
        if state.mode == ConversationMode.AI_MODE:
            return {
                "should_respond": True,
                "reason": "AI mode active",
                "mode": state.mode.value
            }
        
        # Human mode - check if human is still active
        if state.mode == ConversationMode.HUMAN_MODE:
            # Check auto-resume timer
            if state.auto_resume_at and datetime.now(timezone.utc) > state.auto_resume_at:
                # Human inactive for too long - resume AI
                await self.resume_ai_mode(customer_id, "human_inactivity_timeout")
                return {
                    "should_respond": True,
                    "reason": "Auto-resumed after human inactivity",
                    "mode": ConversationMode.AI_MODE.value
                }
            
            return {
                "should_respond": False,
                "reason": f"Human ({state.assigned_human}) is handling this conversation",
                "mode": state.mode.value,
                "assigned_to": state.assigned_human
            }
        
        # Hybrid mode - AI can respond but flag human
        if state.mode == ConversationMode.HYBRID_MODE:
            return {
                "should_respond": True,
                "reason": "Hybrid mode - AI responds with human oversight",
                "mode": state.mode.value,
                "notify_human": True
            }
        
        # Paused - don't respond
        if state.mode == ConversationMode.PAUSED:
            return {
                "should_respond": False,
                "reason": "Conversation paused",
                "mode": state.mode.value
            }
        
        # Default fallback
        return {
            "should_respond": True,
            "reason": "Default AI mode",
            "mode": ConversationMode.AI_MODE.value
        }
    
    async def resume_ai_mode(
        self,
        customer_id: str,
        reason: str = "manual"
    ) -> Dict[str, Any]:
        """Resume AI mode after human handoff"""
        logger.info(f"Resuming AI mode for {customer_id}, reason: {reason}")
        
        await self.update_conversation_state(
            customer_id=customer_id,
            updates={
                "mode": ConversationMode.AI_MODE.value,
                "handoff_reason": None,
                "assigned_human": None,
                "auto_resume_at": None
            }
        )
        
        return {
            "status": "ai_mode_resumed",
            "reason": reason
        }
    
    async def escalate_to_human(
        self,
        customer_id: str,
        business_id: str,
        reason: HandoffReason,
        ai_context: str = ""
    ) -> Dict[str, Any]:
        """
        AI-initiated escalation to human
        - Sets conversation to paused
        - Notifies available humans
        - Provides context
        """
        logger.info(f"AI escalating {customer_id} to human, reason: {reason.value}")
        
        await self.update_conversation_state(
            customer_id=customer_id,
            updates={
                "mode": ConversationMode.PAUSED.value,
                "handoff_reason": reason.value,
                "notes": ai_context
            }
        )
        
        # Log escalation
        if self.db is not None:
            await self.db.aurem_handoff_log.insert_one({
                "customer_id": customer_id,
                "business_id": business_id,
                "event": "ai_escalation",
                "reason": reason.value,
                "context": ai_context,
                "timestamp": datetime.now(timezone.utc)
            })
        
        # TODO: Notify humans (WhatsApp, email, dashboard notification)
        
        return {
            "status": "escalated",
            "reason": reason.value,
            "context": ai_context,
            "message": "Conversation paused - awaiting human assignment"
        }
    
    async def get_active_human_conversations(
        self,
        business_id: str,
        human_id: str = None
    ) -> List[Dict[str, Any]]:
        """Get list of conversations currently in human mode"""
        if self.db is None:
            return []
        
        query = {
            "business_id": business_id,
            "mode": ConversationMode.HUMAN_MODE.value
        }
        
        if human_id:
            query["assigned_human"] = human_id
        
        conversations = await self.db.aurem_conversation_states.find(query).to_list(100)
        
        return [{**c, "_id": None} for c in conversations]


# Singleton
_coexistence_manager = None

def get_coexistence_manager(db=None):
    global _coexistence_manager
    if _coexistence_manager is None:
        _coexistence_manager = CoexistenceManager(db)
    elif db is not None and _coexistence_manager.db is None:
        _coexistence_manager.db = db
    return _coexistence_manager
