"""
Enhanced Lead Capture Service (Gentle Concierge Mode)
LLM-powered contact extraction from natural conversation

Features:
- No upfront forms - data captured naturally
- Channel auto-capture (WhatsApp, Vapi, Email)
- Context-aware asking (only when customer wants something)
- Integration with Panic Button system
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timezone
import uuid

logger = logging.getLogger(__name__)


async def capture_lead_from_conversation(
    db,
    tenant_id: str,
    conversation_id: str,
    customer_message: str,
    channel: Optional[str] = None,
    channel_metadata: Optional[Dict] = None
) -> Dict:
    """
    Capture lead from natural conversation (Gentle Concierge mode)
    
    Args:
        db: MongoDB database
        tenant_id: Tenant ID
        conversation_id: Conversation ID
        customer_message: Customer's latest message
        channel: Source channel (whatsapp, vapi, email, web)
        channel_metadata: Channel data (from_number, caller_id, etc.)
    
    Returns:
        {
            "lead_captured": bool,
            "lead_id": str | None,
            "contact_data": Dict | None,
            "should_ask_contact": bool,
            "suggested_prompt": str | None
        }
    """
    if db is None:
        return {"lead_captured": False, "error": "Database not initialized"}
    
    try:
        from services.contact_extractor import get_contact_extractor
        
        extractor = get_contact_extractor()
        
        # Extract contact info
        extracted = await extractor.extract_from_message(
            message=customer_message,
            channel=channel,
            channel_metadata=channel_metadata
        )
        
        # Check if we should ask
        triggers = extractor.detect_ask_triggers(customer_message)
        
        # If contact info found, create/update lead
        if extracted["email"] or extracted["phone"]:
            lead_id = f"lead_{uuid.uuid4().hex[:12]}"
            
            # Check if lead already exists for this conversation
            existing = await db.leads.find_one(
                {"conversation_id": conversation_id},
                {"_id": 0}
            )
            
            if existing:
                # Update existing lead
                await db.leads.update_one(
                    {"conversation_id": conversation_id},
                    {"$set": {
                        "email": extracted["email"] or existing.get("email"),
                        "phone": extracted["phone"] or existing.get("phone"),
                        "channel_preference": extracted["channel_preference"] or existing.get("channel_preference"),
                        "updated_at": datetime.now(timezone.utc),
                        "extraction_method": extracted["extraction_method"]
                    }}
                )
                lead_id = existing["lead_id"]
                logger.info(f"[EnhancedLeadCapture] Updated lead: {lead_id}")
            else:
                # Create new lead
                lead_doc = {
                    "lead_id": lead_id,
                    "tenant_id": tenant_id,
                    "conversation_id": conversation_id,
                    "email": extracted["email"],
                    "phone": extracted["phone"],
                    "channel": channel,
                    "channel_preference": extracted["channel_preference"],
                    "extraction_method": extracted["extraction_method"],
                    "confidence": extracted["confidence"],
                    "status": "new",
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }
                
                await db.leads.insert_one(lead_doc)
                logger.info(f"[EnhancedLeadCapture] Created lead: {lead_id}")
                
                # Send notification to business owner
                await _send_lead_notification(db, tenant_id, lead_doc)
            
            return {
                "lead_captured": True,
                "lead_id": lead_id,
                "contact_data": {
                    "email": extracted["email"],
                    "phone": extracted["phone"],
                    "channel_preference": extracted["channel_preference"]
                },
                "should_ask_contact": False,
                "suggested_prompt": None
            }
        
        # If trigger but no contact, suggest asking
        if triggers["should_ask"]:
            suggested_prompt = _generate_ask_prompt(triggers["trigger_type"])
            
            return {
                "lead_captured": False,
                "lead_id": None,
                "contact_data": None,
                "should_ask_contact": True,
                "suggested_prompt": suggested_prompt,
                "trigger_context": triggers["context"]
            }
        
        # No lead captured, no trigger
        return {
            "lead_captured": False,
            "lead_id": None,
            "contact_data": None,
            "should_ask_contact": False,
            "suggested_prompt": None
        }
    
    except Exception as e:
        logger.error(f"[EnhancedLeadCapture] Error: {e}", exc_info=True)
        return {"lead_captured": False, "error": str(e)}


def _generate_ask_prompt(trigger_type: str) -> str:
    """Generate natural prompt to ask for contact info"""
    
    prompts = {
        "send_request": "I'd love to send that to you! What's the best email or number to use?",
        "booking": "Great! To confirm your booking, I'll need your contact information. What's the best email or phone number?",
        "pricing_request": "I can send you our pricing details. Where would you like me to send it - email or WhatsApp?",
        "follow_up": "I'll make sure to follow up with you. What's the best way to reach you?"
    }
    
    return prompts.get(trigger_type, "What's the best way to reach you - email or phone?")


async def _send_lead_notification(db, tenant_id: str, lead_data: Dict):
    """Send email notification to business owner about new lead"""
    try:
        # Get tenant config
        tenant = await db.users.find_one(
            {"tenant_id": tenant_id},
            {"_id": 0, "email": 1, "company_name": 1}
        )
        
        if not tenant:
            return
        
        # Send email notification
        from services.email_notification_service import send_email
        
        subject = f"🎯 New Lead Captured - {lead_data.get('email') or lead_data.get('phone')}"
        
        content = f"""
        New lead captured in AUREM!
        
        Lead ID: {lead_data['lead_id']}
        Email: {lead_data.get('email', 'N/A')}
        Phone: {lead_data.get('phone', 'N/A')}
        Channel: {lead_data.get('channel', 'N/A')}
        Preferred Contact: {lead_data.get('channel_preference', 'N/A')}
        
        View conversation: /leads/{lead_data['lead_id']}
        """
        
        await send_email(
            to_email=tenant["email"],
            subject=subject,
            content=content
        )
        
        logger.info(f"[EnhancedLeadCapture] Notification sent to {tenant['email']}")
    
    except Exception as e:
        logger.warning(f"[EnhancedLeadCapture] Notification error: {e}")


async def get_lead_by_conversation(db, conversation_id: str) -> Optional[Dict]:
    """Get lead data for a conversation"""
    if db is None:
        return None
    
    try:
        lead = await db.leads.find_one(
            {"conversation_id": conversation_id},
            {"_id": 0}
        )
        return lead
    except Exception as e:
        logger.error(f"[EnhancedLeadCapture] Error getting lead: {e}")
        return None
