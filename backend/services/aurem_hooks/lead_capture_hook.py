"""
Lead Capture Hook
Automatically detects and captures leads from AI conversations

Trigger: After every AI agent response
Action: Check for lead intent, extract data, save to database, notify owner
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class LeadCaptureHook:
    """
    Hook that runs after AI responses to detect and capture leads
    """
    
    def __init__(self, db):
        """
        Initialize Lead Capture Hook
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.enabled = True
        logger.info("[LeadCaptureHook] Initialized")
    
    async def execute(
        self,
        tenant_id: str,
        conversation_id: str,
        conversation_history: list,
        latest_user_message: str,
        latest_ai_response: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Execute lead capture hook
        
        Args:
            tenant_id: Tenant ID (for multi-tenancy)
            conversation_id: ID of the conversation
            conversation_history: Full conversation history
            latest_user_message: Most recent user message
            latest_ai_response: AI's response
            metadata: Additional context
        
        Returns:
            {
                "lead_captured": bool,
                "lead_id": str or None,
                "confidence": float,
                "notifications_sent": List[str]
            }
        """
        if not self.enabled:
            return {"lead_captured": False, "reason": "Hook disabled"}
        
        try:
            # Import service (lazy import to avoid circular dependencies)
            from services.lead_capture_service import get_lead_capture_service
            
            lead_service = get_lead_capture_service(self.db)
            
            # Detect lead intent in latest message
            intent_data = lead_service.detect_lead_intent(
                message=latest_user_message,
                conversation_history=conversation_history
            )
            
            logger.info(
                f"[LeadCaptureHook] Intent detection: is_lead={intent_data['is_lead']}, "
                f"confidence={intent_data['confidence']}, signals={intent_data['signals']}"
            )
            
            # If not a lead, skip
            if not intent_data["is_lead"]:
                return {
                    "lead_captured": False,
                    "reason": "No lead intent detected",
                    "confidence": intent_data["confidence"]
                }
            
            # Check if we already captured a lead for this conversation
            existing_lead = await self.db.leads.find_one(
                {"conversation_id": conversation_id, "tenant_id": tenant_id},
                {"_id": 0}
            )
            
            if existing_lead:
                logger.info(f"[LeadCaptureHook] Lead already exists for conversation {conversation_id}")
                return {
                    "lead_captured": False,
                    "reason": "Lead already exists for this conversation",
                    "existing_lead_id": existing_lead.get("lead_id")
                }
            
            # Create lead
            lead = await lead_service.create_lead(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                conversation=conversation_history,
                intent_data=intent_data,
                source="ai_chat"
            )
            
            logger.info(f"[LeadCaptureHook] ✓ Lead captured: {lead['lead_id']}")
            
            # Send notifications
            notifications_sent = await self._send_notifications(
                tenant_id=tenant_id,
                lead=lead
            )
            
            # Update lead with notification status
            await self.db.leads.update_one(
                {"lead_id": lead["lead_id"]},
                {"$set": {"notifications_sent": notifications_sent}}
            )
            
            return {
                "lead_captured": True,
                "lead_id": lead["lead_id"],
                "confidence": intent_data["confidence"],
                "intent_type": intent_data["intent_type"],
                "notifications_sent": notifications_sent
            }
        
        except Exception as e:
            logger.error(f"[LeadCaptureHook] Error executing hook: {e}")
            return {
                "lead_captured": False,
                "error": str(e)
            }
    
    async def _send_notifications(self, tenant_id: str, lead: Dict) -> list:
        """
        Send notifications to business owner about new lead
        
        Args:
            tenant_id: Tenant ID
            lead: Lead document
        
        Returns:
            List of notification channels that succeeded
        """
        notifications_sent = []
        
        try:
            # Get tenant settings to find owner's contact info
            tenant = await self.db.tenants.find_one(
                {"tenant_id": tenant_id},
                {"_id": 0}
            )
            
            if not tenant:
                logger.warning(f"[LeadCaptureHook] Tenant not found: {tenant_id}")
                return notifications_sent
            
            # Email notification
            email_sent = await self._send_email_notification(tenant, lead)
            if email_sent:
                notifications_sent.append("email")
            
            # SMS notification (optional - requires Twilio)
            # sms_sent = await self._send_sms_notification(tenant, lead)
            # if sms_sent:
            #     notifications_sent.append("sms")
            
            logger.info(f"[LeadCaptureHook] Notifications sent: {notifications_sent}")
            
        except Exception as e:
            logger.error(f"[LeadCaptureHook] Error sending notifications: {e}")
        
        return notifications_sent
    
    async def _send_email_notification(self, tenant: Dict, lead: Dict) -> bool:
        """
        Send email notification to business owner
        
        Args:
            tenant: Tenant document
            lead: Lead document
        
        Returns:
            Success boolean
        """
        try:
            # Get owner's email from tenant settings
            owner_email = tenant.get("metadata", {}).get("owner_email")
            
            if not owner_email:
                # Fallback: use first admin user's email
                owner_email = tenant.get("admin_email") or "admin@aurem.ai"
            
            # Import email service
            from services.email_notification_service import send_lead_notification_email
            
            # Prepare email data
            lead_name = lead.get("customer", {}).get("name", "Unknown")
            lead_phone = lead.get("customer", {}).get("phone", "Not provided")
            lead_email = lead.get("customer", {}).get("email", "Not provided")
            intent_type = lead.get("interest", {}).get("intent_type", "general inquiry")
            value_estimate = lead.get("value_estimate", 0)
            
            # Send email
            success = await send_lead_notification_email(
                to_email=owner_email,
                lead_data={
                    "lead_id": lead["lead_id"],
                    "name": lead_name,
                    "phone": lead_phone,
                    "email": lead_email,
                    "intent_type": intent_type,
                    "value_estimate": value_estimate,
                    "captured_at": lead["captured_at"].strftime("%Y-%m-%d %H:%M:%S UTC")
                }
            )
            
            if success:
                logger.info(f"[LeadCaptureHook] ✓ Email sent to {owner_email}")
            
            return success
        
        except Exception as e:
            logger.error(f"[LeadCaptureHook] Email notification error: {e}")
            return False


# Global instance
_lead_capture_hook = None


def get_lead_capture_hook(db):
    """Get singleton LeadCaptureHook instance"""
    global _lead_capture_hook
    
    if _lead_capture_hook is None:
        _lead_capture_hook = LeadCaptureHook(db)
    
    return _lead_capture_hook
