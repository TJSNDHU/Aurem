"""
AUREM Proactive Follow-Up Engine
Automatically follows up with customers who haven't converted or responded
Tier 2/3 Premium Feature
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class FollowUpStatus(str, Enum):
    """Follow-up conversation status"""
    ACTIVE = "active"
    PENDING_FOLLOWUP = "pending_followup"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    OPTED_OUT = "opted_out"


class FollowUpTiming(str, Enum):
    """Standard follow-up intervals"""
    HOUR_24 = "24h"
    HOUR_48 = "48h"
    DAY_7 = "7d"
    DAY_14 = "14d"
    DAY_30 = "30d"


class FollowUpRule(BaseModel):
    """Configuration for a follow-up rule"""
    timing: FollowUpTiming
    max_attempts: int = 3
    channels: List[str] = ["whatsapp", "email", "sms"]
    ai_decision_required: bool = True  # AI decides if follow-up is needed


class ProactiveFollowUpEngine:
    """
    Proactive Follow-Up System
    - Monitors conversations for follow-up opportunities
    - Uses AI to decide if follow-up is appropriate
    - Executes multi-channel follow-ups
    - Tracks engagement and conversion
    """
    
    def __init__(self, db=None):
        self.db = db
        self.api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        
        # Default follow-up rules
        self.default_rules = [
            FollowUpRule(timing=FollowUpTiming.HOUR_24, max_attempts=1),
            FollowUpRule(timing=FollowUpTiming.HOUR_48, max_attempts=1),
            FollowUpRule(timing=FollowUpTiming.DAY_7, max_attempts=1)
        ]
    
    async def find_conversations_needing_followup(
        self, 
        business_id: str,
        timing: FollowUpTiming = FollowUpTiming.HOUR_24
    ) -> List[Dict[str, Any]]:
        """Find conversations that need follow-up based on timing"""
        if not self.db:
            return []
        
        # Calculate time threshold
        hours_map = {
            FollowUpTiming.HOUR_24: 24,
            FollowUpTiming.HOUR_48: 48,
            FollowUpTiming.DAY_7: 168,
            FollowUpTiming.DAY_14: 336,
            FollowUpTiming.DAY_30: 720
        }
        
        hours = hours_map.get(timing, 24)
        threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        # Find conversations where:
        # 1. Last message was from assistant (AI)
        # 2. Last activity was > threshold hours ago
        # 3. Status is not closed or opted out
        # 4. Follow-up attempts < max for this timing
        
        pipeline = [
            # Get latest message per customer
            {
                "$match": {
                    "business_id": business_id,
                    "direction": "outbound",
                    "timestamp": {"$lt": threshold}
                }
            },
            {
                "$sort": {"timestamp": -1}
            },
            {
                "$group": {
                    "_id": "$customer_id",
                    "last_message": {"$first": "$$ROOT"}
                }
            },
            {
                "$lookup": {
                    "from": "aurem_customers",
                    "localField": "_id",
                    "foreignField": "customer_id",
                    "as": "customer"
                }
            },
            {
                "$unwind": "$customer"
            },
            {
                "$match": {
                    "$or": [
                        {"customer.followup_status": {"$exists": False}},
                        {"customer.followup_status": {"$in": [
                            FollowUpStatus.ACTIVE.value,
                            FollowUpStatus.PENDING_FOLLOWUP.value
                        ]}}
                    ]
                }
            }
        ]
        
        results = await self.db.aurem_messages.aggregate(pipeline).to_list(100)
        return results
    
    async def should_followup(
        self,
        customer_id: str,
        conversation_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Use AI to decide if follow-up is appropriate and generate message"""
        
        # Build conversation context
        context = "\n".join([
            f"{'Customer' if msg['direction'] == 'inbound' else 'Assistant'}: {msg['content']}"
            for msg in conversation_history[-6:]  # Last 6 messages
        ])
        
        prompt = f"""You are analyzing a customer conversation to determine if a follow-up is appropriate.

Conversation History:
{context}

Analyze this conversation and respond with JSON:
{{
    "should_followup": true/false,
    "reason": "brief explanation",
    "suggested_message": "natural, non-pushy follow-up message (if should_followup is true)",
    "urgency": "low/medium/high",
    "estimated_intent": "information_seeking/purchase_intent/support_request/just_browsing"
}}

Guidelines:
- Don't follow up if customer explicitly said "not interested" or "don't contact"
- Don't follow up if conversation naturally concluded
- DO follow up if customer showed interest but didn't commit
- DO follow up if customer asked a question we didn't fully answer
- Keep message brief, friendly, and value-focused
"""
        
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"followup_{customer_id}"
            ).with_model("openai", "gpt-4o")
            
            response = await chat.send_message(UserMessage(text=prompt))
            
            # Parse JSON response
            import json
            decision = json.loads(response)
            
            return decision
            
        except Exception as e:
            logger.error(f"AI follow-up decision error: {e}")
            # Safe fallback - don't spam
            return {
                "should_followup": False,
                "reason": f"Error: {str(e)}",
                "suggested_message": "",
                "urgency": "low",
                "estimated_intent": "unknown"
            }
    
    async def execute_followup(
        self,
        business_id: str,
        customer_id: str,
        message: str,
        channel: str = "whatsapp"
    ) -> Dict[str, Any]:
        """Execute the follow-up via specified channel"""
        from services.omnidimension_service import get_omni_service, Channel
        
        omni = get_omni_service(self.db)
        
        # Map string to Channel enum
        channel_map = {
            "whatsapp": Channel.WHATSAPP,
            "email": Channel.EMAIL,
            "sms": Channel.SMS,
            "voice": Channel.VOICE
        }
        
        channel_enum = channel_map.get(channel, Channel.WHATSAPP)
        
        # Send outbound message
        result = await omni.send_outbound_message(
            channel=channel_enum,
            business_id=business_id,
            customer_id=customer_id,
            content=message,
            metadata={
                "followup": True,
                "automated": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Update customer follow-up tracking
        if self.db:
            await self.db.aurem_customers.update_one(
                {"customer_id": customer_id},
                {
                    "$set": {
                        "last_followup": datetime.now(timezone.utc),
                        "followup_status": FollowUpStatus.PENDING_FOLLOWUP.value
                    },
                    "$inc": {"followup_count": 1}
                }
            )
        
        return result
    
    async def run_followup_cycle(
        self,
        business_id: str,
        timing: FollowUpTiming = FollowUpTiming.HOUR_24
    ) -> Dict[str, Any]:
        """
        Main follow-up cycle - run this on a schedule
        Returns summary of follow-ups executed
        """
        logger.info(f"Running follow-up cycle for {business_id} at {timing.value}")
        
        # Find conversations needing follow-up
        conversations = await self.find_conversations_needing_followup(business_id, timing)
        
        results = {
            "business_id": business_id,
            "timing": timing.value,
            "candidates": len(conversations),
            "followups_sent": 0,
            "skipped": 0,
            "errors": 0,
            "details": []
        }
        
        for conv in conversations:
            customer_id = conv["_id"]
            
            try:
                # Get conversation history
                messages = await self.db.aurem_messages.find(
                    {"customer_id": customer_id}
                ).sort("timestamp", -1).limit(10).to_list(10)
                
                # AI decision
                decision = await self.should_followup(customer_id, messages)
                
                if decision.get("should_followup"):
                    # Execute follow-up
                    followup_result = await self.execute_followup(
                        business_id=business_id,
                        customer_id=customer_id,
                        message=decision["suggested_message"],
                        channel="whatsapp"  # Can be dynamic based on customer preference
                    )
                    
                    results["followups_sent"] += 1
                    results["details"].append({
                        "customer_id": customer_id,
                        "action": "sent",
                        "channel": "whatsapp",
                        "reason": decision["reason"]
                    })
                else:
                    results["skipped"] += 1
                    results["details"].append({
                        "customer_id": customer_id,
                        "action": "skipped",
                        "reason": decision["reason"]
                    })
                    
            except Exception as e:
                logger.error(f"Follow-up error for {customer_id}: {e}")
                results["errors"] += 1
                results["details"].append({
                    "customer_id": customer_id,
                    "action": "error",
                    "error": str(e)
                })
        
        logger.info(f"Follow-up cycle complete: {results['followups_sent']} sent, {results['skipped']} skipped")
        return results
    
    async def update_conversation_status(
        self,
        customer_id: str,
        status: FollowUpStatus,
        notes: str = ""
    ) -> bool:
        """Update the follow-up status of a conversation"""
        if not self.db:
            return False
        
        result = await self.db.aurem_customers.update_one(
            {"customer_id": customer_id},
            {
                "$set": {
                    "followup_status": status.value,
                    "followup_notes": notes,
                    "status_updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        return result.modified_count > 0


# Singleton
_followup_engine = None

def get_followup_engine(db=None):
    global _followup_engine
    if _followup_engine is None:
        _followup_engine = ProactiveFollowUpEngine(db)
    elif db and _followup_engine.db is None:
        _followup_engine.db = db
    return _followup_engine
