"""
Usage Metering Service
Tracks resource usage and enforces plan limits
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class ResourceType(str, Enum):
    """Types of resources to meter"""
    API_CALL = "api_call"
    LLM_TOKEN = "llm_token"
    VECTOR_EMBEDDING = "vector_embedding"
    CONNECTOR_CALL = "connector_call"
    AGENT_EXECUTION = "agent_execution"
    HOOK_TRIGGER = "hook_trigger"
    STORAGE_MB = "storage_mb"


# Plan limits configuration
PLAN_LIMITS = {
    "free": {
        ResourceType.API_CALL: 1000,           # 1K API calls/month
        ResourceType.LLM_TOKEN: 100000,        # 100K tokens/month
        ResourceType.VECTOR_EMBEDDING: 5000,   # 5K embeddings/month
        ResourceType.CONNECTOR_CALL: 100,      # 100 connector calls/month
        ResourceType.AGENT_EXECUTION: 50,      # 50 agent runs/month
        ResourceType.HOOK_TRIGGER: 500,        # 500 hook triggers/month
        ResourceType.STORAGE_MB: 100,          # 100 MB storage
    },
    "starter": {
        ResourceType.API_CALL: 10000,          # 10K/month
        ResourceType.LLM_TOKEN: 1000000,       # 1M tokens/month
        ResourceType.VECTOR_EMBEDDING: 50000,  # 50K embeddings/month
        ResourceType.CONNECTOR_CALL: 1000,     # 1K connector calls/month
        ResourceType.AGENT_EXECUTION: 500,     # 500 agent runs/month
        ResourceType.HOOK_TRIGGER: 5000,       # 5K hook triggers/month
        ResourceType.STORAGE_MB: 1000,         # 1 GB storage
    },
    "professional": {
        ResourceType.API_CALL: 100000,         # 100K/month
        ResourceType.LLM_TOKEN: 10000000,      # 10M tokens/month
        ResourceType.VECTOR_EMBEDDING: 500000, # 500K embeddings/month
        ResourceType.CONNECTOR_CALL: 10000,    # 10K connector calls/month
        ResourceType.AGENT_EXECUTION: 5000,    # 5K agent runs/month
        ResourceType.HOOK_TRIGGER: 50000,      # 50K hook triggers/month
        ResourceType.STORAGE_MB: 10000,        # 10 GB storage
    },
    "enterprise": {
        ResourceType.API_CALL: -1,             # Unlimited
        ResourceType.LLM_TOKEN: -1,            # Unlimited
        ResourceType.VECTOR_EMBEDDING: -1,     # Unlimited
        ResourceType.CONNECTOR_CALL: -1,       # Unlimited
        ResourceType.AGENT_EXECUTION: -1,      # Unlimited
        ResourceType.HOOK_TRIGGER: -1,         # Unlimited
        ResourceType.STORAGE_MB: -1,           # Unlimited
    }
}


class UsageMeteringService:
    """
    Tracks and enforces resource usage limits
    
    CRITICAL: Call record_usage() for EVERY billable operation
    CRITICAL: Call check_quota() BEFORE expensive operations
    """
    
    def __init__(self, db):
        self.db = db
        logger.info("[UsageMetering] Service initialized")
    
    async def record_usage(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        amount: int = 1,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Record resource usage
        
        CRITICAL: Call this for EVERY billable operation
        
        Args:
            tenant_id: Tenant/company ID
            resource_type: Type of resource consumed
            amount: Quantity consumed (default: 1)
            metadata: Additional context (endpoint, agent_name, etc.)
        
        Returns:
            Success boolean
        """
        try:
            # Get current month period
            now = datetime.now(timezone.utc)
            period = now.strftime("%Y-%m")
            
            # Update usage counter
            await self.db.usage_tracking.update_one(
                {
                    "tenant_id": tenant_id,
                    "period": period,
                    "resource_type": resource_type.value
                },
                {
                    "$inc": {"usage_count": amount},
                    "$setOnInsert": {
                        "created_at": now
                    },
                    "$set": {
                        "updated_at": now
                    },
                    "$push": {
                        "events": {
                            "$each": [{
                                "timestamp": now,
                                "amount": amount,
                                "metadata": metadata or {}
                            }],
                            "$slice": -100  # Keep last 100 events
                        }
                    }
                },
                upsert=True
            )
            
            logger.debug(
                f"[UsageMetering] Recorded {amount} {resource_type.value} "
                f"for tenant {tenant_id}"
            )
            
            return True
        
        except Exception as e:
            logger.error(f"[UsageMetering] Error recording usage: {e}")
            return False
    
    async def check_quota(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        requested_amount: int = 1
    ) -> Dict[str, Any]:
        """
        Check if tenant has quota remaining
        
        CRITICAL: Call this BEFORE expensive operations
        
        Args:
            tenant_id: Tenant/company ID
            resource_type: Type of resource to check
            requested_amount: Amount about to be consumed
        
        Returns:
            {
                "allowed": bool,
                "current_usage": int,
                "limit": int,
                "remaining": int,
                "message": str
            }
        """
        try:
            # Get tenant plan
            tenant = await self.db.tenants.find_one(
                {"tenant_id": tenant_id},
                {"_id": 0}
            )
            
            if not tenant:
                return {
                    "allowed": False,
                    "message": "Tenant not found"
                }
            
            plan_tier = tenant.get("plan_tier", "free")
            
            # Get plan limit
            limit = PLAN_LIMITS.get(plan_tier, {}).get(resource_type, 0)
            
            # Unlimited for enterprise
            if limit == -1:
                return {
                    "allowed": True,
                    "current_usage": 0,
                    "limit": -1,
                    "remaining": -1,
                    "message": "Unlimited"
                }
            
            # Get current usage
            now = datetime.now(timezone.utc)
            period = now.strftime("%Y-%m")
            
            usage_record = await self.db.usage_tracking.find_one(
                {
                    "tenant_id": tenant_id,
                    "period": period,
                    "resource_type": resource_type.value
                },
                {"_id": 0}
            )
            
            current_usage = usage_record.get("usage_count", 0) if usage_record else 0
            remaining = limit - current_usage
            
            # Check if quota exceeded
            if current_usage + requested_amount > limit:
                return {
                    "allowed": False,
                    "current_usage": current_usage,
                    "limit": limit,
                    "remaining": max(0, remaining),
                    "message": (
                        f"Quota exceeded. {current_usage}/{limit} {resource_type.value} used. "
                        f"Upgrade plan to continue."
                    )
                }
            
            return {
                "allowed": True,
                "current_usage": current_usage,
                "limit": limit,
                "remaining": remaining,
                "message": "OK"
            }
        
        except Exception as e:
            logger.error(f"[UsageMetering] Error checking quota: {e}")
            return {
                "allowed": False,
                "message": f"Error: {str(e)}"
            }
    
    async def get_usage_stats(
        self,
        tenant_id: str,
        period: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive usage statistics for a tenant
        
        Args:
            tenant_id: Tenant/company ID
            period: Month period (YYYY-MM), defaults to current month
        
        Returns:
            Usage stats across all resource types
        """
        try:
            if not period:
                period = datetime.now(timezone.utc).strftime("%Y-%m")
            
            # Get tenant plan
            tenant = await self.db.tenants.find_one(
                {"tenant_id": tenant_id},
                {"_id": 0}
            )
            
            if not tenant:
                return {"error": "Tenant not found"}
            
            plan_tier = tenant.get("plan_tier", "free")
            limits = PLAN_LIMITS.get(plan_tier, {})
            
            # Get all usage records for period
            usage_records = await self.db.usage_tracking.find(
                {
                    "tenant_id": tenant_id,
                    "period": period
                },
                {"_id": 0}
            ).to_list(100)
            
            # Build stats
            stats = {
                "tenant_id": tenant_id,
                "plan_tier": plan_tier,
                "period": period,
                "resources": {}
            }
            
            for resource_type in ResourceType:
                # Find usage record for this resource
                usage_record = next(
                    (r for r in usage_records if r.get("resource_type") == resource_type.value),
                    None
                )
                
                current_usage = usage_record.get("usage_count", 0) if usage_record else 0
                limit = limits.get(resource_type, 0)
                
                stats["resources"][resource_type.value] = {
                    "current": current_usage,
                    "limit": limit,
                    "remaining": limit - current_usage if limit != -1 else -1,
                    "percentage": (current_usage / limit * 100) if limit > 0 else 0,
                    "unlimited": limit == -1
                }
            
            return stats
        
        except Exception as e:
            logger.error(f"[UsageMetering] Error getting usage stats: {e}")
            return {"error": str(e)}
    
    async def reset_monthly_usage(self, tenant_id: str) -> bool:
        """
        Reset usage for new billing period
        
        Called automatically on month rollover
        """
        try:
            # Archive current month to history
            current_period = datetime.now(timezone.utc).strftime("%Y-%m")
            
            usage_records = await self.db.usage_tracking.find(
                {
                    "tenant_id": tenant_id,
                    "period": current_period
                },
                {"_id": 0}
            ).to_list(100)
            
            if usage_records:
                # Archive to history collection
                await self.db.usage_history.insert_many(usage_records)
                
                # Delete current records (they'll be recreated on next use)
                await self.db.usage_tracking.delete_many({
                    "tenant_id": tenant_id,
                    "period": current_period
                })
            
            logger.info(f"[UsageMetering] Reset usage for tenant {tenant_id}")
            return True
        
        except Exception as e:
            logger.error(f"[UsageMetering] Error resetting usage: {e}")
            return False
    
    async def get_overage_cost(
        self,
        tenant_id: str,
        resource_type: ResourceType,
        overage_amount: int
    ) -> Dict[str, Any]:
        """
        Calculate overage charges
        
        For plans that allow overage with additional charges
        """
        # Overage pricing (per unit beyond limit)
        OVERAGE_PRICING = {
            ResourceType.API_CALL: 0.001,         # $0.001 per call
            ResourceType.LLM_TOKEN: 0.00001,      # $0.00001 per token
            ResourceType.VECTOR_EMBEDDING: 0.0001, # $0.0001 per embedding
            ResourceType.CONNECTOR_CALL: 0.01,    # $0.01 per call
            ResourceType.AGENT_EXECUTION: 0.10,   # $0.10 per execution
            ResourceType.HOOK_TRIGGER: 0.001,     # $0.001 per trigger
            ResourceType.STORAGE_MB: 0.05,        # $0.05 per MB
        }
        
        unit_price = OVERAGE_PRICING.get(resource_type, 0)
        total_cost = overage_amount * unit_price
        
        return {
            "resource_type": resource_type.value,
            "overage_amount": overage_amount,
            "unit_price": unit_price,
            "total_cost": total_cost,
            "currency": "USD"
        }


# Singleton instance
_usage_metering_service = None


def get_usage_metering_service(db):
    """Get singleton UsageMeteringService instance"""
    global _usage_metering_service
    
    if _usage_metering_service is None:
        _usage_metering_service = UsageMeteringService(db)
    
    return _usage_metering_service
