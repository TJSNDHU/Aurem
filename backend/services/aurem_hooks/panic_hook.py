"""
Panic Hook - The Emergency Brake for AI Conversations
Monitors sentiment in real-time and triggers human intervention when needed

This hook executes AFTER every AI response to check if human help is needed.
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timezone
import uuid

logger = logging.getLogger(__name__)


class PanicHook:
    """
    Monitors conversation sentiment and triggers panic alerts
    
    Executes after each AI response to:
    1. Analyze customer sentiment
    2. Detect panic triggers
    3. Send alerts to business owner
    4. Pause AI responses (lockdown mode)
    """
    
    def __init__(self, db=None):
        self.db = db
        self.hook_name = "panic_button"
    
    async def execute(
        self,
        tenant_id: str,
        conversation_id: str,
        conversation_history: List[Dict],
        latest_user_message: str,
        latest_ai_response: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Execute panic detection after AI response
        
        Args:
            tenant_id: Tenant identifier
            conversation_id: Conversation ID
            conversation_history: Full conversation so far
            latest_user_message: Most recent customer message
            latest_ai_response: AI's response (just generated)
            metadata: Additional context (customer info, etc.)
        
        Returns:
            {
                "panic_triggered": bool,
                "event_id": str | None,
                "sentiment_score": float,
                "action_taken": str
            }
        """
        if self.db is None:
            logger.error("[PanicHook] Database not initialized")
            return {"panic_triggered": False, "error": "Database not initialized"}
        
        try:
            # Get tenant panic configuration
            tenant_config = await self._get_tenant_config(tenant_id)
            
            if not tenant_config:
                logger.warning(f"[PanicHook] Tenant not found: {tenant_id}")
                return {"panic_triggered": False, "error": "Tenant not found"}
            
            panic_config = tenant_config.get("panic_config", {})
            
            # Check if panic button is enabled (default: yes)
            if not panic_config.get("enabled", True):
                return {"panic_triggered": False, "reason": "Panic button disabled"}
            
            # Analyze sentiment of latest user message
            from services.sentiment_analyzer import analyze_message_sentiment
            
            sentiment_result = await analyze_message_sentiment(
                message=latest_user_message,
                conversation_history=conversation_history,
                custom_keywords=panic_config.get("custom_keywords", [])
            )
            
            logger.info(f"[PanicHook] Sentiment for {conversation_id}: {sentiment_result['sentiment_label']} ({sentiment_result['sentiment_score']:.2f})")
            
            # Check if panic threshold crossed
            threshold = panic_config.get("sensitivity_threshold", -0.7)
            is_panic = sentiment_result["is_panic"] and sentiment_result["sentiment_score"] < threshold
            
            # Also trigger if explicit human request detected
            if sentiment_result["needs_human"]:
                is_panic = True
            
            if not is_panic:
                # No panic - all good
                return {
                    "panic_triggered": False,
                    "sentiment_score": sentiment_result["sentiment_score"],
                    "sentiment_label": sentiment_result["sentiment_label"]
                }
            
            # PANIC TRIGGERED - Create event and send alerts
            event_id = f"panic_{uuid.uuid4().hex[:12]}"
            
            # Extract customer info from metadata OR get from lead database
            customer_info = metadata.get("customer", {}) if metadata else {}
            
            # Try to get lead data for this conversation
            try:
                from services.enhanced_lead_capture import get_lead_by_conversation
                lead_data = await get_lead_by_conversation(self.db, conversation_id)
                
                if lead_data:
                    # Use lead data for customer info
                    if not customer_info.get("name"):
                        customer_info["name"] = lead_data.get("name", "Unknown")
                    if not customer_info.get("email"):
                        customer_info["email"] = lead_data.get("email", "N/A")
                    if not customer_info.get("phone"):
                        customer_info["phone"] = lead_data.get("phone", "N/A")
            except Exception as e:
                logger.warning(f"[PanicHook] Could not fetch lead data: {e}")
            
            panic_event = {
                "event_id": event_id,
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "customer": {
                    "name": customer_info.get("name", "Unknown"),
                    "phone": customer_info.get("phone", "N/A"),
                    "email": customer_info.get("email", "N/A")
                },
                "trigger_reason": ", ".join(sentiment_result["panic_triggers"]),
                "sentiment_score": sentiment_result["sentiment_score"],
                "sentiment_label": sentiment_result["sentiment_label"],
                "emotion": sentiment_result["emotion"],
                "detected_keywords": sentiment_result["detected_keywords"],
                "detected_language": sentiment_result.get("detected_language", "en"),
                "original_message": latest_user_message,
                "english_translation": sentiment_result.get("english_translation", latest_user_message),
                "last_message": latest_user_message,
                "conversation_history": conversation_history[-5:],  # Last 5 messages
                "status": "triggered",
                "created_at": datetime.now(timezone.utc),
                "alerted_at": None,
                "taken_over_at": None,
                "resolved_at": None,
                "auto_pause_enabled": panic_config.get("auto_pause_ai", True)
            }
            
            # Save panic event to database
            await self.db.panic_events.insert_one(panic_event)
            
            logger.warning(f"[PanicHook] 🚨 PANIC TRIGGERED: {event_id} for conversation {conversation_id}")
            
            # Send alerts to business owner
            from services.panic_alert_service import get_panic_alert_service
            
            alert_service = get_panic_alert_service(self.db)
            alert_result = await alert_service.send_panic_alert(
                tenant_id=tenant_id,
                panic_event=panic_event,
                alert_channels=panic_config.get("alert_channels", ["email"])
            )
            
            # Update event with alert timestamp
            if alert_result["success"]:
                await self.db.panic_events.update_one(
                    {"event_id": event_id},
                    {"$set": {
                        "alerted_at": datetime.now(timezone.utc),
                        "alert_channels_sent": alert_result["channels_sent"]
                    }}
                )
            
            # Mark conversation as "needs_human_intervention"
            await self.db.conversations.update_one(
                {"conversation_id": conversation_id},
                {"$set": {
                    "needs_human_intervention": True,
                    "ai_paused": panic_config.get("auto_pause_ai", True),
                    "panic_event_id": event_id,
                    "paused_at": datetime.now(timezone.utc)
                }},
                upsert=True
            )
            
            logger.info(f"[PanicHook] ✓ Alerts sent via {alert_result['channels_sent']}")
            
            return {
                "panic_triggered": True,
                "event_id": event_id,
                "sentiment_score": sentiment_result["sentiment_score"],
                "sentiment_label": sentiment_result["sentiment_label"],
                "emotion": sentiment_result["emotion"],
                "detected_keywords": sentiment_result["detected_keywords"],
                "action_taken": "alerts_sent_ai_paused" if panic_config.get("auto_pause_ai") else "alerts_sent",
                "alert_channels": alert_result["channels_sent"]
            }
        
        except Exception as e:
            logger.error(f"[PanicHook] Execution error: {e}", exc_info=True)
            return {"panic_triggered": False, "error": str(e)}
    
    async def _get_tenant_config(self, tenant_id: str) -> Optional[Dict]:
        """Get tenant configuration from database"""
        try:
            tenant = await self.db.users.find_one(
                {"tenant_id": tenant_id},
                {"_id": 0}
            )
            return tenant
        except Exception as e:
            logger.error(f"[PanicHook] Error fetching tenant: {e}")
            return None
    
    async def get_final_ai_message_before_pause(self, customer_name: str = "there") -> str:
        """
        Generate the final soothing message AI sends before pausing
        
        Args:
            customer_name: Customer's name (if known)
        
        Returns:
            Final AI message string
        """
        return (
            f"I understand this is important to you. "
            f"I'm connecting you with our team right now so they can "
            f"assist you personally. They'll be with you shortly!"
        )


# Singleton instance
_panic_hook = None


def get_panic_hook(db=None) -> PanicHook:
    """Get or create panic hook instance"""
    global _panic_hook
    if _panic_hook is None or db is not None:
        _panic_hook = PanicHook(db)
    return _panic_hook
