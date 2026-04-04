"""
Panic Alert Service
Sends immediate alerts to business owners when panic button triggers

Supports multiple channels:
- Email (via existing email_notification_service)
- SMS (via Twilio)
- Webhook (Slack/Discord - optional)

Universal templates that work for any industry.
"""

import logging
import os
from typing import Dict, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class PanicAlertService:
    """Handles panic button alerts across multiple channels"""
    
    def __init__(self, db=None):
        self.db = db
    
    async def send_panic_alert(
        self,
        tenant_id: str,
        panic_event: Dict,
        alert_channels: Optional[List[str]] = None
    ) -> Dict:
        """
        Send panic alert through configured channels
        
        Args:
            tenant_id: Tenant identifier
            panic_event: Panic event data
                {
                    "event_id": str,
                    "conversation_id": str,
                    "customer": {"name": str, "phone": str, "email": str},
                    "trigger_reason": str,
                    "sentiment_score": float,
                    "detected_keywords": List[str],
                    "last_message": str
                }
            alert_channels: List of channels ["email", "sms", "webhook"]
        
        Returns:
            {
                "success": bool,
                "channels_sent": List[str],
                "channels_failed": List[str],
                "details": Dict
            }
        """
        if not self.db:
            logger.error("[PanicAlert] Database not initialized")
            return {"success": False, "error": "Database not initialized"}
        
        try:
            # Get tenant configuration
            tenant_config = await self._get_tenant_config(tenant_id)
            
            if not tenant_config:
                logger.warning(f"[PanicAlert] No config found for tenant {tenant_id}")
                return {"success": False, "error": "Tenant config not found"}
            
            # Determine which channels to use
            if alert_channels is None:
                alert_channels = tenant_config.get("panic_config", {}).get("alert_channels", ["email"])
            
            results = {
                "success": True,
                "channels_sent": [],
                "channels_failed": [],
                "details": {}
            }
            
            # Send email alert
            if "email" in alert_channels:
                email_result = await self._send_email_alert(tenant_config, panic_event)
                if email_result["success"]:
                    results["channels_sent"].append("email")
                else:
                    results["channels_failed"].append("email")
                results["details"]["email"] = email_result
            
            # Send SMS alert
            if "sms" in alert_channels:
                sms_result = await self._send_sms_alert(tenant_config, panic_event)
                if sms_result["success"]:
                    results["channels_sent"].append("sms")
                else:
                    results["channels_failed"].append("sms")
                results["details"]["sms"] = sms_result
            
            # Send webhook alert (optional)
            if "webhook" in alert_channels:
                webhook_result = await self._send_webhook_alert(tenant_config, panic_event)
                if webhook_result["success"]:
                    results["channels_sent"].append("webhook")
                else:
                    results["channels_failed"].append("webhook")
                results["details"]["webhook"] = webhook_result
            
            # Overall success if at least one channel worked
            results["success"] = len(results["channels_sent"]) > 0
            
            logger.info(f"[PanicAlert] Sent alerts for {panic_event['event_id']}: {results['channels_sent']}")
            
            return results
        
        except Exception as e:
            logger.error(f"[PanicAlert] Error sending alerts: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_tenant_config(self, tenant_id: str) -> Optional[Dict]:
        """Get tenant configuration from database"""
        try:
            tenant = await self.db.users.find_one(
                {"tenant_id": tenant_id},
                {"_id": 0}
            )
            return tenant
        except Exception as e:
            logger.error(f"[PanicAlert] Error fetching tenant config: {e}")
            return None
    
    async def _send_email_alert(self, tenant_config: Dict, panic_event: Dict) -> Dict:
        """Send email alert to business owner"""
        try:
            from services.email_notification_service import send_panic_alert_email
            
            # Get alert email from config
            alert_email = (
                tenant_config.get("panic_config", {}).get("alert_email") or
                tenant_config.get("email")
            )
            
            if not alert_email:
                logger.warning("[PanicAlert] No alert email configured")
                return {"success": False, "reason": "No email configured"}
            
            # Prepare email data
            email_data = {
                "business_name": tenant_config.get("company_name", "Business"),
                "customer_name": panic_event["customer"].get("name", "Unknown"),
                "customer_phone": panic_event["customer"].get("phone", "N/A"),
                "customer_email": panic_event["customer"].get("email", "N/A"),
                "trigger_reason": panic_event["trigger_reason"],
                "sentiment_score": panic_event.get("sentiment_score", 0.0),
                "detected_keywords": panic_event.get("detected_keywords", []),
                "last_message": panic_event["last_message"],
                "conversation_id": panic_event["conversation_id"],
                "event_id": panic_event["event_id"],
                "dashboard_link": f"{os.getenv('REACT_APP_BACKEND_URL', '')}/dashboard?convo={panic_event['conversation_id']}"
            }
            
            success = await send_panic_alert_email(alert_email, email_data)
            
            return {
                "success": success,
                "recipient": alert_email,
                "sent_at": datetime.now(timezone.utc).isoformat()
            }
        
        except Exception as e:
            logger.error(f"[PanicAlert] Email send error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _send_sms_alert(self, tenant_config: Dict, panic_event: Dict) -> Dict:
        """Send SMS alert via Twilio"""
        try:
            from services.twilio_service import send_sms, get_twilio_client
            
            # Check if Twilio is configured
            client = get_twilio_client()
            if not client:
                logger.warning("[PanicAlert] Twilio not configured, skipping SMS")
                return {"success": False, "reason": "Twilio not configured"}
            
            # Get alert phone from config
            alert_phone = tenant_config.get("panic_config", {}).get("alert_phone")
            
            if not alert_phone:
                logger.warning("[PanicAlert] No alert phone configured")
                return {"success": False, "reason": "No phone configured"}
            
            # Create SMS message
            customer_name = panic_event["customer"].get("name", "Unknown")
            trigger = panic_event.get("trigger_reason", "panic")
            last_msg = panic_event["last_message"][:50] + "..." if len(panic_event["last_message"]) > 50 else panic_event["last_message"]
            
            message = f"""🚨 AUREM Alert

Customer: {customer_name}
Issue: {trigger}
Last Message: "{last_msg}"

View & Take Over: {os.getenv('REACT_APP_BACKEND_URL', '')}/dashboard?convo={panic_event['conversation_id']}"""
            
            # Send SMS
            result = await send_sms(
                to_number=alert_phone,
                message=message
            )
            
            return {
                "success": result.get("success", False),
                "recipient": alert_phone,
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "message_sid": result.get("sid")
            }
        
        except Exception as e:
            logger.error(f"[PanicAlert] SMS send error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _send_webhook_alert(self, tenant_config: Dict, panic_event: Dict) -> Dict:
        """Send webhook alert (Slack/Discord)"""
        try:
            import httpx
            
            webhook_url = tenant_config.get("panic_config", {}).get("webhook_url")
            
            if not webhook_url:
                return {"success": False, "reason": "No webhook URL configured"}
            
            # Create webhook payload (Slack format)
            payload = {
                "text": f"🚨 AUREM Panic Alert",
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🚨 Customer Needs Immediate Attention"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Customer:*\n{panic_event['customer'].get('name', 'Unknown')}"},
                            {"type": "mrkdwn", "text": f"*Trigger:*\n{panic_event['trigger_reason']}"},
                            {"type": "mrkdwn", "text": f"*Sentiment:*\n{panic_event.get('sentiment_score', 0.0):.2f}"},
                            {"type": "mrkdwn", "text": f"*Keywords:*\n{', '.join(panic_event.get('detected_keywords', [])[:3])}"}
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Last Message:*\n> {panic_event['last_message'][:150]}"
                        }
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {"type": "plain_text", "text": "Take Over Conversation"},
                                "url": f"{os.getenv('REACT_APP_BACKEND_URL', '')}/dashboard?convo={panic_event['conversation_id']}",
                                "style": "danger"
                            }
                        ]
                    }
                ]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(webhook_url, json=payload, timeout=10.0)
            
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "sent_at": datetime.now(timezone.utc).isoformat()
            }
        
        except Exception as e:
            logger.error(f"[PanicAlert] Webhook send error: {e}")
            return {"success": False, "error": str(e)}


# Singleton instance
_panic_alert_service = None


def get_panic_alert_service(db=None) -> PanicAlertService:
    """Get or create panic alert service instance"""
    global _panic_alert_service
    if _panic_alert_service is None or db is not None:
        _panic_alert_service = PanicAlertService(db)
    return _panic_alert_service
