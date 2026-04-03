"""
AUREM Automated Outreach Scheduler
Connects GitHub Leads → WhatsApp/Email/Voice Actions
Growth OS Action Layer
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class OutreachChannel(str, Enum):
    """Outreach channels"""
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    VOICE = "voice"
    SMS = "sms"


class OutreachType(str, Enum):
    """Types of outreach"""
    CART_RECOVERY = "cart_recovery"           # Abandoned cart
    ONBOARDING = "onboarding"                 # New user welcome
    FEATURE_ADOPTION = "feature_adoption"     # SaaS feature push
    APPOINTMENT_BOOKING = "appointment_booking"  # Service scheduling
    DISCOUNT_OFFER = "discount_offer"         # Promotional
    FEEDBACK_REQUEST = "feedback_request"     # Post-purchase
    REACTIVATION = "reactivation"             # Dormant users
    UPGRADE_PROMPT = "upgrade_prompt"         # Upsell


class OutreachCampaign(BaseModel):
    """Outreach campaign"""
    campaign_id: str
    business_id: str
    name: str
    outreach_type: OutreachType
    channels: List[OutreachChannel]
    target_lead_score: int = 50
    
    # Timing
    trigger_delay_hours: int = 2  # Wait 2h after lead creation
    max_attempts: int = 3
    retry_delay_hours: int = 24
    
    # Content
    message_template: str
    personalization_fields: List[str] = []
    
    # Status
    status: str = "active"
    created_at: datetime
    leads_targeted: int = 0
    leads_contacted: int = 0
    conversion_rate: float = 0.0


class OutreachScheduler:
    """
    Automated Outreach Scheduler
    
    The "Action" layer of Growth OS:
    - GitHub extracts leads
    - Scheduler triggers campaigns
    - Multi-channel delivery (WhatsApp, Email, Voice)
    - Tracks conversions
    """
    
    def __init__(self, db=None):
        self.db = db
        self.api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    
    async def create_campaign(
        self,
        business_id: str,
        name: str,
        outreach_type: OutreachType,
        channels: List[OutreachChannel],
        message_template: str,
        target_lead_score: int = 50
    ) -> OutreachCampaign:
        """Create automated outreach campaign"""
        from uuid import uuid4
        
        campaign = OutreachCampaign(
            campaign_id=str(uuid4()),
            business_id=business_id,
            name=name,
            outreach_type=outreach_type,
            channels=channels,
            message_template=message_template,
            target_lead_score=target_lead_score,
            created_at=datetime.now(timezone.utc)
        )
        
        if self.db is not None:
            await self.db.aurem_outreach_campaigns.insert_one(campaign.dict())
        
        logger.info(f"Created campaign: {name} for business {business_id}")
        return campaign
    
    async def run_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """
        Execute outreach campaign
        
        Flow:
        1. Get high-score leads
        2. Filter by campaign criteria
        3. Generate personalized messages (AI)
        4. Send via appropriate channels
        5. Track conversions
        """
        campaign = await self._get_campaign(campaign_id)
        if not campaign:
            return {"error": "Campaign not found"}
        
        # Check subscription limits
        from services.subscription_manager import get_subscription_manager, FeatureAccess
        
        sub_manager = get_subscription_manager(self.db)
        
        # Check if business has access to required channels
        for channel in campaign.channels:
            feature = self._channel_to_feature(channel)
            access = await sub_manager.check_feature_access(
                campaign.business_id,  # Assuming business_id = user_id for now
                feature
            )
            
            if not access["allowed"]:
                logger.warning(f"Campaign {campaign_id}: No access to {channel.value}")
                continue
        
        # Get leads
        from services.github_data_miner import get_github_miner
        
        miner = get_github_miner(self.db)
        leads = await miner.get_business_leads(
            business_id=campaign.business_id,
            min_score=campaign.target_lead_score
        )
        
        results = {
            "campaign_id": campaign_id,
            "leads_found": len(leads),
            "messages_sent": 0,
            "channels_used": {},
            "errors": []
        }
        
        for lead in leads[:50]:  # Process first 50 leads
            # Generate personalized message
            message = await self._personalize_message(
                template=campaign.message_template,
                lead=lead,
                outreach_type=campaign.outreach_type
            )
            
            # Send via appropriate channels
            for channel in campaign.channels:
                try:
                    sent = await self._send_outreach(
                        channel=channel,
                        business_id=campaign.business_id,
                        lead=lead,
                        message=message
                    )
                    
                    if sent:
                        results["messages_sent"] += 1
                        results["channels_used"][channel.value] = results["channels_used"].get(channel.value, 0) + 1
                        
                        # Check usage limit
                        limit_ok = await sub_manager.check_usage_limit(
                            campaign.business_id,
                            "messages"
                        )
                        
                        if not limit_ok["allowed"]:
                            logger.warning(f"Campaign {campaign_id}: Usage limit reached")
                            break
                        
                except Exception as e:
                    logger.error(f"Outreach error: {e}")
                    results["errors"].append(str(e))
        
        # Update campaign stats
        if self.db is not None:
            await self.db.aurem_outreach_campaigns.update_one(
                {"campaign_id": campaign_id},
                {
                    "$inc": {
                        "leads_targeted": len(leads),
                        "leads_contacted": results["messages_sent"]
                    }
                }
            )
        
        # Record event for daily digest
        from services.daily_digest import get_digest_engine, EventPriority
        digest = get_digest_engine(self.db)
        
        await digest.record_event(
            event_type="outreach_campaign",
            title=f"Campaign '{campaign.name}' Executed",
            description=f"{results['messages_sent']} messages sent to {len(leads)} leads",
            business_id=campaign.business_id,
            priority=EventPriority.MEDIUM,
            metadata=results
        )
        
        return results
    
    def _channel_to_feature(self, channel: OutreachChannel) -> str:
        """Map channel to subscription feature"""
        from services.subscription_manager import FeatureAccess
        
        channel_map = {
            OutreachChannel.WHATSAPP: FeatureAccess.WHATSAPP,
            OutreachChannel.EMAIL: FeatureAccess.EMAIL,
            OutreachChannel.VOICE: FeatureAccess.VOICE,
            OutreachChannel.SMS: FeatureAccess.WHATSAPP
        }
        
        return channel_map.get(channel, FeatureAccess.WHATSAPP)
    
    async def _personalize_message(
        self,
        template: str,
        lead: Dict[str, Any],
        outreach_type: OutreachType
    ) -> str:
        """
        Generate personalized message using AI
        
        Template: "Hi {name}, we noticed you left items in your cart..."
        Output: "Hi John, we noticed you left items in your cart. Here's 10% off!"
        """
        # Simple template replacement
        message = template
        
        replacements = {
            "{name}": lead.get("name", "there"),
            "{email}": lead.get("email", ""),
            "{phone}": lead.get("phone", ""),
            "{business_name}": "Our Business"
        }
        
        for key, value in replacements.items():
            message = message.replace(key, value)
        
        # Use AI to enhance message (optional)
        if self.api_key and len(message) < 100:
            enhanced = await self._enhance_with_ai(message, lead, outreach_type)
            if enhanced:
                message = enhanced
        
        return message
    
    async def _enhance_with_ai(
        self,
        message: str,
        lead: Dict[str, Any],
        outreach_type: OutreachType
    ) -> Optional[str]:
        """Use AI to enhance message"""
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            prompt = f"""Enhance this outreach message to be more engaging and personalized:

Original: {message}

Lead context: {lead.get('name', 'Customer')} - Score: {lead.get('lead_score', 0)}
Outreach type: {outreach_type.value}

Make it:
1. Brief (under 160 chars for SMS)
2. Personalized
3. Action-oriented
4. Non-pushy

Return only the enhanced message, nothing else."""

            chat = LlmChat(
                api_key=self.api_key,
                session_id="outreach"
            ).with_model("openai", "gpt-4o-mini")
            
            enhanced = await chat.send_message(UserMessage(text=prompt))
            return enhanced.strip()
            
        except Exception as e:
            logger.error(f"AI enhancement error: {e}")
            return None
    
    async def _send_outreach(
        self,
        channel: OutreachChannel,
        business_id: str,
        lead: Dict[str, Any],
        message: str
    ) -> bool:
        """Send outreach via specified channel"""
        from services.omnidimension_service import get_omni_service, Channel as OmniChannel
        
        omni = get_omni_service(self.db)
        
        # Map to OmniChannel
        channel_map = {
            OutreachChannel.WHATSAPP: OmniChannel.WHATSAPP,
            OutreachChannel.EMAIL: OmniChannel.EMAIL,
            OutreachChannel.SMS: OmniChannel.SMS,
            OutreachChannel.VOICE: OmniChannel.VOICE
        }
        
        omni_channel = channel_map.get(channel, OmniChannel.WHATSAPP)
        
        try:
            result = await omni.send_outbound_message(
                channel=omni_channel,
                business_id=business_id,
                customer_id=lead.get("customer_id"),
                content=message,
                metadata={
                    "outreach": True,
                    "lead_score": lead.get("lead_score"),
                    "automated": True
                }
            )
            
            return result.get("sent", False)
            
        except Exception as e:
            logger.error(f"Send error ({channel.value}): {e}")
            return False
    
    async def _get_campaign(self, campaign_id: str) -> Optional[OutreachCampaign]:
        """Get campaign"""
        if self.db is None:
            return None
        
        campaign_doc = await self.db.aurem_outreach_campaigns.find_one(
            {"campaign_id": campaign_id},
            {"_id": 0}
        )
        
        if campaign_doc:
            return OutreachCampaign(**campaign_doc)
        
        return None
    
    async def schedule_appointment_booking(
        self,
        business_id: str,
        lead_id: str,
        service_type: str,
        available_slots: List[str]
    ) -> Dict[str, Any]:
        """
        Schedule appointment booking outreach
        
        For SERVICE businesses:
        - Sends available time slots
        - Handles booking confirmation
        - Integrates with Google Calendar/Calendly
        """
        # TODO: Integrate with Google Calendar API
        
        return {
            "appointment_link": "https://calendly.com/business/30min",
            "slots_offered": available_slots,
            "booking_status": "pending"
        }


# Singleton
_outreach_scheduler = None

def get_outreach_scheduler(db=None):
    global _outreach_scheduler
    if _outreach_scheduler is None:
        _outreach_scheduler = OutreachScheduler(db)
    elif db and _outreach_scheduler.db is None:
        _outreach_scheduler.db = db
    return _outreach_scheduler
