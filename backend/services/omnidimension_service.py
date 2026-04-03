"""
OmniDimension Multi-Channel Intelligence Service
Provides unified intelligence across all communication channels
"""

import os
import uuid
import json
import logging
import aiohttp
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Configuration
OMNIDIMENSION_API_KEY = os.environ.get("OMNIDIMENSION_API_KEY", "")
OMNIDIMENSION_BASE_URL = os.environ.get("OMNIDIMENSION_URL", "https://api.omnidimension.ai")


class Channel(str, Enum):
    """Communication channels"""
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    VOICE = "voice"
    SMS = "sms"
    WEB_CHAT = "web_chat"
    SOCIAL = "social"


class MessagePriority(str, Enum):
    """Message priority levels"""
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class CustomerProfile(BaseModel):
    """Unified customer profile across channels"""
    customer_id: str
    business_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    channels_active: List[Channel] = []
    total_interactions: int = 0
    last_interaction: Optional[datetime] = None
    sentiment_score: float = 0.0  # -1 to 1
    engagement_score: float = 0.0  # 0 to 100
    tags: List[str] = []
    notes: str = ""
    created_at: datetime = None
    updated_at: datetime = None


class ChannelMessage(BaseModel):
    """Message from any channel"""
    message_id: str
    channel: Channel
    business_id: str
    customer_id: Optional[str] = None
    direction: str  # inbound, outbound
    content: str
    content_type: str = "text"  # text, image, audio, video
    metadata: Dict[str, Any] = {}
    priority: MessagePriority = MessagePriority.NORMAL
    sentiment: Optional[float] = None
    intent: Optional[str] = None
    timestamp: datetime = None


class OmniDimensionService:
    """
    Multi-channel intelligence service
    Provides unified view and routing across all communication channels
    """
    
    def __init__(self, db=None):
        self.db = db
        self.api_key = OMNIDIMENSION_API_KEY
        self.base_url = OMNIDIMENSION_BASE_URL
        self.is_configured = bool(self.api_key)
        
        # In-memory cache for quick access
        self.customer_cache: Dict[str, CustomerProfile] = {}
        self.channel_stats: Dict[str, Dict] = {}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CUSTOMER INTELLIGENCE
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_or_create_customer(
        self, 
        business_id: str,
        identifier: str,
        channel: Channel,
        name: str = None
    ) -> CustomerProfile:
        """Get existing customer or create new profile"""
        
        # Check cache first
        cache_key = f"{business_id}:{identifier}"
        if cache_key in self.customer_cache:
            return self.customer_cache[cache_key]
        
        # Check database
        if self.db is not None:
            customer_doc = await self.db.aurem_customers.find_one({
                "business_id": business_id,
                "$or": [
                    {"email": identifier},
                    {"phone": identifier},
                    {"whatsapp": identifier}
                ]
            })
            
            if customer_doc:
                customer_doc.pop("_id", None)
                customer = CustomerProfile(**customer_doc)
                self.customer_cache[cache_key] = customer
                return customer
        
        # Create new customer
        customer = CustomerProfile(
            customer_id=str(uuid.uuid4()),
            business_id=business_id,
            name=name,
            channels_active=[channel],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Set identifier based on channel
        if channel == Channel.EMAIL:
            customer.email = identifier
        elif channel in [Channel.WHATSAPP, Channel.SMS, Channel.VOICE]:
            customer.phone = identifier
            if channel == Channel.WHATSAPP:
                customer.whatsapp = identifier
        
        # Save to database
        if self.db is not None:
            await self.db.aurem_customers.insert_one(customer.dict())
        
        self.customer_cache[cache_key] = customer
        return customer
    
    async def update_customer(
        self, 
        customer_id: str, 
        updates: Dict[str, Any]
    ) -> Optional[CustomerProfile]:
        """Update customer profile"""
        updates["updated_at"] = datetime.now(timezone.utc)
        
        if self.db is not None:
            result = await self.db.aurem_customers.find_one_and_update(
                {"customer_id": customer_id},
                {"$set": updates},
                return_document=True
            )
            
            if result:
                result.pop("_id", None)
                customer = CustomerProfile(**result)
                # Update cache
                for key, cached in self.customer_cache.items():
                    if cached.customer_id == customer_id:
                        self.customer_cache[key] = customer
                        break
                return customer
        
        return None
    
    async def get_customer_360(self, customer_id: str) -> Dict[str, Any]:
        """Get 360-degree view of customer across all channels"""
        if self.db is None:
            return {"error": "Database not configured"}
        
        # Get customer profile
        customer_doc = await self.db.aurem_customers.find_one({"customer_id": customer_id})
        if not customer_doc:
            return {"error": "Customer not found"}
        
        customer_doc.pop("_id", None)
        
        # Get interaction history
        interactions = await self.db.aurem_messages.find(
            {"customer_id": customer_id}
        ).sort("timestamp", -1).limit(50).to_list(50)
        
        # Get channel breakdown
        channel_breakdown = {}
        for channel in Channel:
            count = await self.db.aurem_messages.count_documents({
                "customer_id": customer_id,
                "channel": channel.value
            })
            if count > 0:
                channel_breakdown[channel.value] = count
        
        return {
            "profile": customer_doc,
            "interactions": [{**m, "_id": None} for m in interactions],
            "channel_breakdown": channel_breakdown,
            "total_interactions": sum(channel_breakdown.values())
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MESSAGE INTELLIGENCE
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def process_inbound_message(
        self,
        channel: Channel,
        business_id: str,
        sender_id: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process an inbound message from any channel with multi-modal and coexistence support"""
        from services.aurem_business_agents import get_business_ai, AgentRole
        from services.multimodal_processor import get_multimodal_processor
        from services.whatsapp_coexistence import get_coexistence_manager
        
        # Get or create customer
        customer = await self.get_or_create_customer(business_id, sender_id, channel)
        
        # Check if human is handling this conversation
        coexistence = get_coexistence_manager(self.db)
        should_respond = await coexistence.should_ai_respond(customer.customer_id, business_id)
        
        # Multi-modal processing
        processor = get_multimodal_processor()
        processed = await processor.process_message(
            message_data={
                "content": content,
                "type": metadata.get("type", "text") if metadata else "text",
                "media_url": metadata.get("media_url") if metadata else None,
                **(metadata if metadata else {})
            },
            context={"business_id": business_id, "customer_id": customer.customer_id}
        )
        
        # Use processed text for analysis
        text_content = processed.get("text", content)
        
        # Analyze message
        analysis = await self._analyze_message(text_content)
        
        # Create message record
        message = ChannelMessage(
            message_id=str(uuid.uuid4()),
            channel=channel,
            business_id=business_id,
            customer_id=customer.customer_id,
            direction="inbound",
            content=text_content,
            metadata={
                **(metadata or {}),
                "multimodal": processed if processed.get("processed") else None,
                "original_type": processed.get("type")
            },
            priority=self._determine_priority(analysis),
            sentiment=analysis.get("sentiment"),
            intent=analysis.get("intent"),
            timestamp=datetime.now(timezone.utc)
        )
        
        # Save message
        if self.db is not None:
            await self.db.aurem_messages.insert_one(message.dict())
        
        # Update customer stats
        await self.update_customer(customer.customer_id, {
            "total_interactions": customer.total_interactions + 1,
            "last_interaction": datetime.now(timezone.utc),
            "sentiment_score": analysis.get("sentiment", customer.sentiment_score)
        })
        
        # Determine if AI should respond
        ai_response_text = None
        agent_name = None
        
        if should_respond.get("should_respond"):
            # Get AI response using business-specific agent
            business_ai = get_business_ai(self.db)
            ai_response = await business_ai.chat_with_context(
                message=text_content,
                business_id=business_id,
                agent_role=AgentRole.ENVOY,
                session_id=customer.customer_id
            )
            ai_response_text = ai_response.get("response")
            agent_name = ai_response.get("agent_name")
        else:
            ai_response_text = None  # Human handling
        
        return {
            "message_id": message.message_id,
            "customer_id": customer.customer_id,
            "channel": channel.value,
            "analysis": analysis,
            "priority": message.priority.value,
            "ai_response": ai_response_text,
            "agent_used": agent_name,
            "suggested_action": self._get_suggested_action(analysis),
            "conversation_mode": should_respond.get("mode"),
            "ai_handling": should_respond.get("should_respond"),
            "multimodal_processed": processed.get("processed", False)
        }
    
    async def send_outbound_message(
        self,
        channel: Channel,
        business_id: str,
        customer_id: str,
        content: str,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Send an outbound message via any channel"""
        
        # Get customer
        if self.db is not None:
            customer_doc = await self.db.aurem_customers.find_one({"customer_id": customer_id})
            if not customer_doc:
                return {"error": "Customer not found"}
        
        # Create message record
        message = ChannelMessage(
            message_id=str(uuid.uuid4()),
            channel=channel,
            business_id=business_id,
            customer_id=customer_id,
            direction="outbound",
            content=content,
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc)
        )
        
        # Save message
        if self.db is not None:
            await self.db.aurem_messages.insert_one(message.dict())
        
        # Route to appropriate channel handler
        delivery_result = await self._deliver_message(channel, customer_doc, content, metadata)
        
        return {
            "message_id": message.message_id,
            "channel": channel.value,
            "status": delivery_result.get("status", "queued"),
            "delivery_details": delivery_result
        }
    
    async def _analyze_message(self, content: str) -> Dict[str, Any]:
        """Analyze message for intent, sentiment, etc."""
        # Basic analysis (can be enhanced with ML)
        content_lower = content.lower()
        
        # Intent detection
        intent = "general"
        if any(w in content_lower for w in ["buy", "purchase", "order", "price", "cost"]):
            intent = "purchase"
        elif any(w in content_lower for w in ["help", "support", "issue", "problem", "fix"]):
            intent = "support"
        elif any(w in content_lower for w in ["hi", "hello", "hey"]):
            intent = "greeting"
        elif any(w in content_lower for w in ["book", "appointment", "schedule", "call"]):
            intent = "booking"
        elif "?" in content:
            intent = "inquiry"
        
        # Sentiment (simplified)
        positive_words = ["great", "love", "excellent", "amazing", "thank", "good", "happy"]
        negative_words = ["bad", "terrible", "awful", "hate", "worst", "disappointed", "angry"]
        
        positive_count = sum(1 for w in positive_words if w in content_lower)
        negative_count = sum(1 for w in negative_words if w in content_lower)
        
        if positive_count > negative_count:
            sentiment = 0.5 + (positive_count * 0.1)
        elif negative_count > positive_count:
            sentiment = -0.5 - (negative_count * 0.1)
        else:
            sentiment = 0.0
        
        sentiment = max(-1, min(1, sentiment))
        
        return {
            "intent": intent,
            "sentiment": sentiment,
            "urgency": "high" if any(w in content_lower for w in ["urgent", "asap", "emergency", "now"]) else "normal",
            "language": "en",  # Could use langdetect
            "word_count": len(content.split())
        }
    
    def _determine_priority(self, analysis: Dict[str, Any]) -> MessagePriority:
        """Determine message priority based on analysis"""
        if analysis.get("urgency") == "high":
            return MessagePriority.URGENT
        if analysis.get("intent") == "purchase":
            return MessagePriority.HIGH
        if analysis.get("sentiment", 0) < -0.5:
            return MessagePriority.HIGH
        return MessagePriority.NORMAL
    
    def _get_suggested_action(self, analysis: Dict[str, Any]) -> str:
        """Get suggested action based on analysis"""
        intent = analysis.get("intent")
        actions = {
            "purchase": "Route to Closer agent for sales conversation",
            "support": "Create support ticket and route to Envoy",
            "booking": "Offer available time slots",
            "inquiry": "Provide relevant information",
            "greeting": "Respond with welcome message"
        }
        return actions.get(intent, "Route to Envoy for classification")
    
    async def _deliver_message(
        self, 
        channel: Channel, 
        customer: Dict, 
        content: str,
        metadata: Dict = None
    ) -> Dict[str, Any]:
        """Deliver message via appropriate channel"""
        # This would integrate with actual channel APIs
        # For now, return simulated result
        
        if channel == Channel.EMAIL:
            # Would integrate with SendGrid/Gmail
            return {"status": "sent", "provider": "email"}
        
        elif channel == Channel.WHATSAPP:
            # Would integrate with WhatsApp Business API
            return {"status": "queued", "provider": "whatsapp"}
        
        elif channel == Channel.VOICE:
            # Would integrate with Vapi
            return {"status": "scheduled", "provider": "vapi"}
        
        elif channel == Channel.SMS:
            # Would integrate with Twilio
            return {"status": "sent", "provider": "twilio"}
        
        return {"status": "pending", "provider": "unknown"}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ANALYTICS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_channel_analytics(self, business_id: str) -> Dict[str, Any]:
        """Get analytics across all channels"""
        if self.db is None:
            return self._get_mock_analytics()
        
        analytics = {}
        
        for channel in Channel:
            # Message counts
            inbound = await self.db.aurem_messages.count_documents({
                "business_id": business_id,
                "channel": channel.value,
                "direction": "inbound"
            })
            outbound = await self.db.aurem_messages.count_documents({
                "business_id": business_id,
                "channel": channel.value,
                "direction": "outbound"
            })
            
            analytics[channel.value] = {
                "inbound": inbound,
                "outbound": outbound,
                "total": inbound + outbound
            }
        
        # Calculate totals
        total_inbound = sum(c["inbound"] for c in analytics.values())
        total_outbound = sum(c["outbound"] for c in analytics.values())
        
        return {
            "business_id": business_id,
            "channels": analytics,
            "totals": {
                "inbound": total_inbound,
                "outbound": total_outbound,
                "total": total_inbound + total_outbound
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _get_mock_analytics(self) -> Dict[str, Any]:
        """Return mock analytics data"""
        return {
            "channels": {
                "email": {"inbound": 1247, "outbound": 892, "total": 2139},
                "whatsapp": {"inbound": 3456, "outbound": 2834, "total": 6290},
                "voice": {"inbound": 234, "outbound": 567, "total": 801},
                "web_chat": {"inbound": 1823, "outbound": 1654, "total": 3477},
                "sms": {"inbound": 456, "outbound": 234, "total": 690}
            },
            "totals": {
                "inbound": 7216,
                "outbound": 6181,
                "total": 13397
            }
        }


# Singleton
_omni_service = None

def get_omni_service(db=None) -> OmniDimensionService:
    global _omni_service
    if _omni_service is None:
        _omni_service = OmniDimensionService(db)
    elif db is not None and _omni_service.db is None:
        _omni_service.db = db
    return _omni_service
