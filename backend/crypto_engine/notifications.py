"""
PWA Push Notifications (Web Push)
"""
import json
import logging
from typing import Dict, Optional
from pywebpush import webpush, WebPushException
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# VAPID keys for web push (generate with: npx web-push generate-vapid-keys)
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_EMAIL = os.environ.get("VAPID_EMAIL", "admin@cryptosignal.app")


class PushNotificationService:
    def __init__(self):
        self.subscriptions: Dict[str, dict] = {}  # user_id -> subscription info
        
    def save_subscription(self, user_id: str, subscription: dict):
        """Save a push subscription"""
        self.subscriptions[user_id] = subscription
        logger.info(f"[Push] Saved subscription for user {user_id}")
        
    def remove_subscription(self, user_id: str):
        """Remove a push subscription"""
        if user_id in self.subscriptions:
            del self.subscriptions[user_id]
            logger.info(f"[Push] Removed subscription for user {user_id}")
            
    async def send_notification(self, user_id: str, title: str, body: str, data: dict = None) -> bool:
        """Send a push notification to a user"""
        subscription = self.subscriptions.get(user_id)
        if not subscription:
            logger.warning(f"[Push] No subscription for user {user_id}")
            return False
            
        if not VAPID_PUBLIC_KEY or not VAPID_PRIVATE_KEY:
            logger.warning("[Push] VAPID keys not configured")
            return False
            
        try:
            payload = json.dumps({
                "title": title,
                "body": body,
                "icon": "/logo192.png",
                "badge": "/badge.png",
                "data": data or {},
                "requireInteraction": True,
                "vibrate": [200, 100, 200]
            })
            
            webpush(
                subscription_info=subscription,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={
                    "sub": f"mailto:{VAPID_EMAIL}"
                }
            )
            
            logger.info(f"[Push] Sent notification to user {user_id}: {title}")
            return True
            
        except WebPushException as e:
            logger.error(f"[Push] WebPush error: {e}")
            if e.response and e.response.status_code == 410:
                # Subscription expired, remove it
                self.remove_subscription(user_id)
            return False
        except Exception as e:
            logger.error(f"[Push] Error sending notification: {e}")
            return False
            
    async def broadcast_signal(self, title: str, body: str, data: dict = None):
        """Send notification to all subscribers"""
        for user_id in list(self.subscriptions.keys()):
            await self.send_notification(user_id, title, body, data)


# Global instance
push_service = PushNotificationService()
