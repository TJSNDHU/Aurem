"""
AUREM Subscription & API Control System — SINGLE SOURCE OF TRUTH (iter 322w)
═══════════════════════════════════════════════════════════════════════════
Master entry point: `get_plan_state(business_id)`
ALL plan/service/usage checks across the codebase MUST route through this
function. The legacy `plan_enforcement.py` and `usage_metering_service.py`
remain as thin shims delegating here so existing imports keep working.

Single source for plan definitions: `aurem_config.plans.PLANS`.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from enum import Enum
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────
# iter 322w — MASTER plan-state function (the only one routes should call)
# ─────────────────────────────────────────────────────────────────────────
async def get_plan_state(business_id: str, db=None) -> Dict[str, Any]:
    """Single source of truth for a tenant's plan posture.

    Args:
      business_id: BIN identifier (e.g., AURE-XXXX).
      db: optional Motor handle. If None, resolves from server.db.

    Returns:
      {
        "business_id":       <str>,
        "plan":              "trial" | "starter" | "growth" | "pro" | "enterprise",
        "services_unlocked": [<service_id>, ...]    # "*" = all (lifetime/admin)
        "trial_ends_at":     ISO datetime str | None,
        "is_expired":        bool,
        "subscription_status": "active" | "trialing" | "expired" | "lifetime_active" | ...,
        "usage": {
          "actions_used":    <int>     # current month service_usage_log count
          "actions_limit":   <int>     # plan-level ceiling (sum of caps),
                                       # or float('inf') for lifetime
        },
      }

    Idempotent — pure read. Computes `is_expired=True` when:
      - plan == "trial" AND trial_ends_at < now AND not lifetime_free
      - subscription_status == "expired"
    """
    if db is None:
        try:
            from server import db as _server_db
            db = _server_db
        except Exception:
            db = None
    if db is None:
        return _empty_state(business_id, reason="db_unavailable")

    # Lookup tenant. We accept either business_id or platform_user_id.
    user = await db.platform_users.find_one(
        {"business_id": business_id}, {"_id": 0}
    )
    if not user:
        # Tolerant fallback — many old rows use email as the primary key.
        user = await db.platform_users.find_one(
            {"$or": [{"user_id": business_id}, {"email": business_id}]},
            {"_id": 0},
        )
    if not user:
        return _empty_state(business_id, reason="tenant_not_found")

    plan_id = (user.get("plan") or "trial").lower()
    services_unlocked = list(user.get("services_unlocked") or [])
    trial_ends_at = user.get("trial_ends_at")
    sub_status = user.get("subscription_status") or "trialing"
    # iter 322w — lifetime detection: explicit flag OR wildcard services
    # OR subscription_status='lifetime_active'.
    lifetime_free = (
        bool(user.get("lifetime_free"))
        or "*" in services_unlocked
        or sub_status == "lifetime_active"
    )

    # Expiry computation — trial gate.
    is_expired = False
    now = datetime.now(timezone.utc)
    if not lifetime_free:
        if plan_id == "trial" and trial_ends_at:
            ttl = trial_ends_at
            if isinstance(ttl, str):
                try:
                    ttl = datetime.fromisoformat(ttl.replace("Z", "+00:00"))
                except Exception:
                    ttl = None
            if isinstance(ttl, datetime):
                if ttl.tzinfo is None:
                    ttl = ttl.replace(tzinfo=timezone.utc)
                if ttl < now:
                    is_expired = True
        if sub_status == "expired":
            is_expired = True

    # If expired and not lifetime — drop unlocked services to []
    if is_expired:
        services_unlocked = []

    # Usage roll-up — count this month's service_usage_log rows.
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    actions_used = 0
    try:
        actions_used = await db.service_usage_log.count_documents({
            "business_id": business_id,
            "ts": {"$gte": month_start.isoformat()},
        })
    except Exception:
        actions_used = 0

    # Limit aggregation from the SSOT.
    if lifetime_free:
        actions_limit = float("inf")
    else:
        try:
            from aurem_config.plans import PLANS as _PLANS
            plan_def = _PLANS.get(plan_id) or _PLANS.get("trial") or {}
            limits = plan_def.get("limits") or {}
            # Use ai_calls_limit as the "actions" ceiling — it's the most
            # generic counter and what the rate-limit middleware checks.
            actions_limit = int(limits.get("ai_calls_limit") or 0)
        except Exception:
            actions_limit = 0

    return {
        "business_id": business_id,
        "plan": plan_id,
        "services_unlocked": services_unlocked,
        "trial_ends_at": (
            trial_ends_at.isoformat()
            if isinstance(trial_ends_at, datetime)
            else trial_ends_at
        ),
        "is_expired": is_expired,
        "subscription_status": "expired" if is_expired else sub_status,
        "usage": {
            "actions_used": actions_used,
            "actions_limit": actions_limit,
        },
    }


def _empty_state(business_id: str, reason: str) -> Dict[str, Any]:
    return {
        "business_id": business_id,
        "plan": "trial",
        "services_unlocked": [],
        "trial_ends_at": None,
        "is_expired": True,
        "subscription_status": "expired",
        "usage": {"actions_used": 0, "actions_limit": 0},
        "_reason": reason,
    }


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
    elif db is not None and _subscription_manager.db is None:
        _subscription_manager.db = db
    return _subscription_manager



# ─────────────────────────────────────────────────────────────────────────
# iter 322w — Legacy compatibility aliases
# These exist ONLY so old `from services.plan_enforcement import X` callers
# can swap to `from services.subscription_manager import X` without further
# code changes. New code MUST call `get_plan_state(business_id)` directly.
# ─────────────────────────────────────────────────────────────────────────
_db_module_handle = None


def set_db(database):
    """Compat with plan_enforcement.set_db(db). Used by registry boot."""
    global _db_module_handle
    _db_module_handle = database


def _resolve_db():
    if _db_module_handle is not None:
        return _db_module_handle
    try:
        from server import db as _server_db
        return _server_db
    except Exception:
        return None


async def get_tenant_plan(tenant_id: str) -> dict:
    """Compat shim. Returns a dict shaped like the legacy plan-tier doc.
    Delegates to `get_plan_state` for plan + services + limits."""
    state = await get_plan_state(tenant_id, db=_resolve_db())
    plan_id = state["plan"]
    try:
        from aurem_config.plans import PLANS as _PLANS
        plan_def = _PLANS.get(plan_id) or _PLANS.get("trial") or {}
    except Exception:
        plan_def = {}
    return {
        "tier": plan_id,
        "name": plan_def.get("name", plan_id.title()),
        "price_cad": plan_def.get("price_cad", 0),
        "features": {s: True for s in state["services_unlocked"]},
        "limits": {
            "actions_per_month": state["usage"]["actions_limit"],
            **(plan_def.get("limits") or {}),
        },
    }


async def check_action_limit(tenant_id: str) -> dict:
    """Compat. Returns {allowed, actions_used, actions_limit, tier, ...}"""
    state = await get_plan_state(tenant_id, db=_resolve_db())
    if state["is_expired"]:
        return {
            "allowed": False, "reason": "trial_expired",
            "actions_used": state["usage"]["actions_used"],
            "actions_limit": state["usage"]["actions_limit"],
            "tier": state["plan"],
            "message": "Your trial has ended. Pick a plan at aurem.live/pricing",
        }
    used = state["usage"]["actions_used"]
    cap = state["usage"]["actions_limit"]
    if cap == float("inf") or cap == -1:
        return {"allowed": True, "actions_used": used,
                "actions_limit": "unlimited", "tier": state["plan"]}
    if used >= cap:
        return {
            "allowed": False, "reason": "monthly_action_limit",
            "actions_used": used, "actions_limit": cap,
            "tier": state["plan"],
            "message": (f"Monthly limit reached ({used}/{cap} actions). "
                        "Upgrade at aurem.live/pricing"),
        }
    pct = round(used / max(cap, 1) * 100)
    return {"allowed": True, "actions_used": used, "actions_limit": cap,
            "usage_pct": pct, "tier": state["plan"]}


async def check_pipeline_limit(tenant_id: str) -> dict:
    """Compat. Pipeline limit is plan-specific; we approximate via daily
    activity in agent_actions for this BIN."""
    state = await get_plan_state(tenant_id, db=_resolve_db())
    if state["is_expired"]:
        return {"allowed": False, "reason": "trial_expired",
                "message": "Your trial has ended."}
    db = _resolve_db()
    if db is None:
        return {"allowed": True, "runs_today": 0, "daily_limit": 0}
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    runs = await db.agent_actions.count_documents({
        "business_id": tenant_id, "ts": {"$gte": today_start},
    })
    # Trial = 1 daily, others = unlimited via SSOT plan limits
    daily_limit = 1 if state["plan"] == "trial" else -1
    if daily_limit == -1:
        return {"allowed": True, "runs_today": runs, "daily_limit": "unlimited"}
    if runs >= daily_limit:
        return {"allowed": False, "reason": "daily_pipeline_limit",
                "runs_today": runs, "daily_limit": daily_limit,
                "message": f"Daily pipeline limit reached ({runs}/{daily_limit})"}
    return {"allowed": True, "runs_today": runs, "daily_limit": daily_limit}


async def check_feature_access(tenant_id: str, feature: str) -> dict:
    """Compat. Maps `feature` to a service_id; returns gate result."""
    state = await get_plan_state(tenant_id, db=_resolve_db())
    if state["is_expired"]:
        return {"allowed": False, "reason": "trial_expired",
                "feature": feature, "tier": state["plan"]}
    unlocked = state["services_unlocked"]
    if "*" in unlocked or feature in unlocked:
        return {"allowed": True, "feature": feature, "value": True}
    return {"allowed": False, "reason": "feature_not_in_plan",
            "feature": feature, "tier": state["plan"],
            "message": (f"'{feature}' is not on the {state['plan']} plan. "
                        "Upgrade at aurem.live/pricing")}


async def get_usage_summary(tenant_id: str) -> dict:
    """Compat. Returns plan + usage rollup for sidebar widget."""
    state = await get_plan_state(tenant_id, db=_resolve_db())
    plan = await get_tenant_plan(tenant_id)
    return {
        "tier": state["plan"],
        "plan_name": plan.get("name"),
        "is_expired": state["is_expired"],
        "usage": state["usage"],
        "services_unlocked": state["services_unlocked"],
    }


async def get_usage(tenant_id: str) -> dict:
    """Compat. Returns just the usage portion."""
    state = await get_plan_state(tenant_id, db=_resolve_db())
    return {
        "actions_used": state["usage"]["actions_used"],
        "actions_limit": state["usage"]["actions_limit"],
    }


async def increment_usage(tenant_id: str, field: str, amount: int = 1):
    """Compat. Records a usage event. Real counter lives in
    `service_usage_log` (gated by `@require_service`); this preserves the
    legacy mutator surface for callers that hand-roll usage tracking."""
    db = _resolve_db()
    if db is None:
        return
    try:
        await db.service_usage_log.insert_one({
            "ts": datetime.now(timezone.utc).isoformat(),
            "business_id": tenant_id,
            "service": field,
            "count": amount,
            "path": "legacy_increment_usage",
        })
    except Exception as e:
        logger.debug(f"[subscription_manager.increment_usage] failed: {e}")


async def seed_plans():
    """No-op shim. Plans are SSOT-defined in `aurem_config.plans.PLANS`
    and read on every call — no DB seeding required. Kept so the legacy
    boot-time call from registry.py doesn't crash."""
    return {"ok": True, "note": "plans seeded via aurem_config.plans SSOT"}


# iter 322w — Re-export PLAN_TIERS from the SSOT so callers migrating
# off `plan_enforcement.PLAN_TIERS` can land here.
try:
    from aurem_config.plans import PLANS as _SSOT_PLANS
    PLAN_TIERS = {
        plan_id: {
            "tier": plan_id,
            "name": p.get("name", plan_id.title()),
            "price_cad": p.get("price_cad", 0),
            "limits": p.get("limits", {}),
            "services": p.get("services", []),
        }
        for plan_id, p in _SSOT_PLANS.items()
    }
except Exception:
    PLAN_TIERS = {}
