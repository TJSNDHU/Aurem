"""
AUREM Subscription & API Control System
Tiered access control for the Growth OS
Revenue Layer
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SubscriptionTier(str, Enum):
    """Subscription tiers"""
    FREE = "free"              # Trial - Limited
    BASIC = "basic"            # WhatsApp only
    PRO = "pro"                # WhatsApp + Email + Follow-up
    ENTERPRISE = "enterprise"  # Full Voice + GitHub Auto-Repair
    CUSTOM = "custom"          # Admin override


class FeatureAccess(str, Enum):
    """Features that can be gated"""
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    VOICE = "voice"
    FOLLOWUP_ENGINE = "followup_engine"
    MULTIMODAL = "multimodal"
    GITHUB_LISTENER = "github_listener"
    AUTO_REPAIR = "auto_repair"
    DAILY_DIGEST = "daily_digest"
    CIRCUIT_BREAKERS = "circuit_breakers"
    PREMIUM_SUPPORT = "premium_support"


class PlanLimits(BaseModel):
    """Usage limits per plan"""
    max_messages_per_month: int
    max_voice_minutes_per_month: int
    max_businesses: int
    max_agents: int
    max_followups_per_day: int
    rate_limit_per_minute: int


class Subscription(BaseModel):
    """Subscription record"""
    subscription_id: str
    user_id: str
    tier: SubscriptionTier
    status: str = "active"  # active, expired, cancelled, suspended
    features: List[FeatureAccess] = []
    limits: PlanLimits
    
    # Billing
    start_date: datetime
    end_date: Optional[datetime] = None
    auto_renew: bool = True
    
    # Usage tracking
    current_usage: Dict[str, int] = {
        "messages": 0,
        "voice_minutes": 0,
        "followups": 0,
        "api_calls": 0
    }
    
    # Admin overrides
    admin_notes: str = ""
    free_access_granted: bool = False
    custom_limits: Optional[Dict[str, Any]] = None


class SubscriptionManager:
    """
    Subscription & API Control Manager
    
    - Tiered access control
    - Usage tracking and limits
    - Plan upgrades/downgrades
    - Admin overrides
    - Expiry notifications
    """
    
    def __init__(self, db=None):
        self.db = db
        
        # Define tier features
        self.tier_features = {
            SubscriptionTier.FREE: [
                FeatureAccess.WHATSAPP,
                FeatureAccess.DAILY_DIGEST
            ],
            SubscriptionTier.BASIC: [
                FeatureAccess.WHATSAPP,
                FeatureAccess.DAILY_DIGEST,
                FeatureAccess.CIRCUIT_BREAKERS
            ],
            SubscriptionTier.PRO: [
                FeatureAccess.WHATSAPP,
                FeatureAccess.EMAIL,
                FeatureAccess.FOLLOWUP_ENGINE,
                FeatureAccess.MULTIMODAL,
                FeatureAccess.DAILY_DIGEST,
                FeatureAccess.CIRCUIT_BREAKERS
            ],
            SubscriptionTier.ENTERPRISE: [
                # All features
                FeatureAccess.WHATSAPP,
                FeatureAccess.EMAIL,
                FeatureAccess.VOICE,
                FeatureAccess.FOLLOWUP_ENGINE,
                FeatureAccess.MULTIMODAL,
                FeatureAccess.GITHUB_LISTENER,
                FeatureAccess.AUTO_REPAIR,
                FeatureAccess.DAILY_DIGEST,
                FeatureAccess.CIRCUIT_BREAKERS,
                FeatureAccess.PREMIUM_SUPPORT
            ]
        }
        
        # Define tier limits
        self.tier_limits = {
            SubscriptionTier.FREE: PlanLimits(
                max_messages_per_month=100,
                max_voice_minutes_per_month=0,
                max_businesses=1,
                max_agents=3,
                max_followups_per_day=5,
                rate_limit_per_minute=10
            ),
            SubscriptionTier.BASIC: PlanLimits(
                max_messages_per_month=1000,
                max_voice_minutes_per_month=0,
                max_businesses=1,
                max_agents=5,
                max_followups_per_day=20,
                rate_limit_per_minute=30
            ),
            SubscriptionTier.PRO: PlanLimits(
                max_messages_per_month=5000,
                max_voice_minutes_per_month=100,
                max_businesses=3,
                max_agents=15,
                max_followups_per_day=100,
                rate_limit_per_minute=60
            ),
            SubscriptionTier.ENTERPRISE: PlanLimits(
                max_messages_per_month=50000,
                max_voice_minutes_per_month=1000,
                max_businesses=10,
                max_agents=50,
                max_followups_per_day=1000,
                rate_limit_per_minute=120
            )
        }
    
    async def get_subscription(self, user_id: str) -> Optional[Subscription]:
        """Get user's current subscription"""
        if self.db is None:
            return None
        
        sub_doc = await self.db.aurem_subscriptions.find_one(
            {"user_id": user_id, "status": "active"},
            {"_id": 0}
        )
        
        if sub_doc:
            return Subscription(**sub_doc)
        
        return None
    
    async def create_subscription(
        self,
        user_id: str,
        tier: SubscriptionTier,
        duration_days: int = 30
    ) -> Subscription:
        """Create new subscription"""
        from uuid import uuid4
        
        subscription = Subscription(
            subscription_id=str(uuid4()),
            user_id=user_id,
            tier=tier,
            status="active",
            features=self.tier_features.get(tier, []),
            limits=self.tier_limits.get(tier),
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc) + timedelta(days=duration_days)
        )
        
        if self.db is not None:
            await self.db.aurem_subscriptions.insert_one(subscription.dict())
        
        logger.info(f"Created {tier.value} subscription for user {user_id}")
        return subscription
    
    async def check_feature_access(
        self,
        user_id: str,
        feature: FeatureAccess
    ) -> Dict[str, Any]:
        """
        Check if user has access to a feature
        
        Returns:
            {
                "allowed": bool,
                "reason": str,
                "tier": str
            }
        """
        subscription = await self.get_subscription(user_id)
        
        if not subscription:
            return {
                "allowed": False,
                "reason": "No active subscription",
                "tier": None
            }
        
        # Admin override
        if subscription.free_access_granted:
            return {
                "allowed": True,
                "reason": "Admin granted free access",
                "tier": subscription.tier.value
            }
        
        # Check if expired
        if subscription.end_date and datetime.now(timezone.utc) > subscription.end_date:
            return {
                "allowed": False,
                "reason": "Subscription expired",
                "tier": subscription.tier.value
            }
        
        # Check feature access
        if feature in subscription.features:
            return {
                "allowed": True,
                "reason": "Feature included in plan",
                "tier": subscription.tier.value
            }
        
        return {
            "allowed": False,
            "reason": f"Feature requires {self._get_required_tier(feature)} or higher",
            "tier": subscription.tier.value
        }
    
    def _get_required_tier(self, feature: FeatureAccess) -> str:
        """Get minimum tier required for a feature"""
        for tier, features in self.tier_features.items():
            if feature in features:
                return tier.value
        return "enterprise"
    
    async def check_usage_limit(
        self,
        user_id: str,
        resource: str
    ) -> Dict[str, Any]:
        """
        Check if user has reached usage limits
        
        resource: messages, voice_minutes, followups, etc.
        """
        subscription = await self.get_subscription(user_id)
        
        if not subscription:
            return {
                "allowed": False,
                "reason": "No active subscription",
                "current": 0,
                "limit": 0
            }
        
        # Admin override
        if subscription.free_access_granted:
            return {
                "allowed": True,
                "reason": "Unlimited (admin grant)",
                "current": subscription.current_usage.get(resource, 0),
                "limit": -1
            }
        
        # Get current usage
        current = subscription.current_usage.get(resource, 0)
        
        # Get limit
        limit_map = {
            "messages": subscription.limits.max_messages_per_month,
            "voice_minutes": subscription.limits.max_voice_minutes_per_month,
            "followups": subscription.limits.max_followups_per_day,
            "businesses": subscription.limits.max_businesses
        }
        
        limit = limit_map.get(resource, 0)
        
        if current >= limit:
            return {
                "allowed": False,
                "reason": f"Monthly limit reached ({current}/{limit})",
                "current": current,
                "limit": limit,
                "upgrade_required": True
            }
        
        return {
            "allowed": True,
            "reason": "Within limits",
            "current": current,
            "limit": limit,
            "remaining": limit - current
        }
    
    async def increment_usage(
        self,
        user_id: str,
        resource: str,
        amount: int = 1
    ) -> bool:
        """Increment usage counter"""
        if self.db is None:
            return False
        
        result = await self.db.aurem_subscriptions.update_one(
            {"user_id": user_id, "status": "active"},
            {"$inc": {f"current_usage.{resource}": amount}}
        )
        
        return result.modified_count > 0
    
    async def upgrade_subscription(
        self,
        user_id: str,
        new_tier: SubscriptionTier
    ) -> Dict[str, Any]:
        """Upgrade user's subscription"""
        subscription = await self.get_subscription(user_id)
        
        if not subscription:
            return {"success": False, "error": "No active subscription"}
        
        # Update subscription
        if self.db is not None:
            await self.db.aurem_subscriptions.update_one(
                {"subscription_id": subscription.subscription_id},
                {
                    "$set": {
                        "tier": new_tier.value,
                        "features": [f.value for f in self.tier_features[new_tier]],
                        "limits": self.tier_limits[new_tier].dict()
                    }
                }
            )
        
        logger.info(f"Upgraded user {user_id} from {subscription.tier.value} to {new_tier.value}")
        
        return {
            "success": True,
            "old_tier": subscription.tier.value,
            "new_tier": new_tier.value,
            "new_features": [f.value for f in self.tier_features[new_tier]]
        }
    
    async def grant_free_access(
        self,
        user_id: str,
        admin_notes: str = ""
    ) -> Dict[str, Any]:
        """Admin grants free unlimited access"""
        if self.db is None:
            return {"success": False, "error": "Database not available"}
        
        result = await self.db.aurem_subscriptions.update_one(
            {"user_id": user_id, "status": "active"},
            {
                "$set": {
                    "free_access_granted": True,
                    "admin_notes": admin_notes,
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        logger.info(f"Admin granted free access to user {user_id}")
        
        return {
            "success": result.modified_count > 0,
            "message": "Free unlimited access granted"
        }
    
    async def check_expiry_soon(
        self,
        days_threshold: int = 7
    ) -> List[Dict[str, Any]]:
        """Find subscriptions expiring soon"""
        if self.db is None:
            return []
        
        threshold_date = datetime.now(timezone.utc) + timedelta(days=days_threshold)
        
        expiring = await self.db.aurem_subscriptions.find({
            "status": "active",
            "end_date": {
                "$lte": threshold_date,
                "$gte": datetime.now(timezone.utc)
            },
            "free_access_granted": {"$ne": True}
        }, {"_id": 0}).to_list(100)
        
        return expiring
    
    async def send_expiry_notifications(self):
        """Send notifications for expiring subscriptions"""
        expiring = await self.check_expiry_soon(7)
        
        for sub in expiring:
            days_left = (sub["end_date"] - datetime.now(timezone.utc)).days
            
            # Record event for daily digest
            from services.daily_digest import get_digest_engine, EventPriority
            digest = get_digest_engine(self.db)
            
            await digest.record_event(
                event_type="subscription_expiring",
                title=f"Subscription Expiring in {days_left} Days",
                description=f"User {sub['user_id']} - {sub['tier']} plan",
                business_id="admin",
                priority=EventPriority.HIGH,
                action_required=True,
                action_url=f"/admin/subscriptions/{sub['user_id']}"
            )
        
        logger.info(f"Processed {len(expiring)} expiring subscriptions")
        return len(expiring)


# Singleton
_subscription_manager = None

def get_subscription_manager(db=None):
    global _subscription_manager
    if _subscription_manager is None:
        _subscription_manager = SubscriptionManager(db)
    elif db and _subscription_manager.db is None:
        _subscription_manager.db = db
    return _subscription_manager
