"""
AUREM API Key Management System
Proprietary sk_aurem_ key system for secure LLM proxy

Features:
- Generate/validate sk_aurem_ API keys with SCOPES
- Track usage per key for billing
- Proxy requests to Emergent LLM (server-to-server)
- Rate limiting integration
- Usage analytics for billing

Scopes:
- chat:read - Can use LLM chat completions
- chat:write - Can send messages via channels
- actions:calendar - Can book/cancel appointments
- actions:payments - Can create invoices/payment links
- actions:email - Can send emails
- actions:whatsapp - Can send WhatsApp messages
- admin:keys - Can manage API keys
"""

import secrets
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class KeyStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    RATE_LIMITED = "rate_limited"


class KeyScope(str, Enum):
    """Permission scopes for AUREM API keys"""
    # Chat/LLM
    CHAT_READ = "chat:read"
    CHAT_WRITE = "chat:write"
    
    # Actions
    ACTIONS_CALENDAR = "actions:calendar"
    ACTIONS_PAYMENTS = "actions:payments"
    ACTIONS_EMAIL = "actions:email"
    ACTIONS_WHATSAPP = "actions:whatsapp"
    
    # Admin
    ADMIN_KEYS = "admin:keys"
    ADMIN_BILLING = "admin:billing"


# Predefined scope bundles
SCOPE_BUNDLES = {
    "read_only": [KeyScope.CHAT_READ.value],
    "standard": [
        KeyScope.CHAT_READ.value,
        KeyScope.CHAT_WRITE.value,
        KeyScope.ACTIONS_EMAIL.value
    ],
    "full_access": [
        KeyScope.CHAT_READ.value,
        KeyScope.CHAT_WRITE.value,
        KeyScope.ACTIONS_CALENDAR.value,
        KeyScope.ACTIONS_PAYMENTS.value,
        KeyScope.ACTIONS_EMAIL.value,
        KeyScope.ACTIONS_WHATSAPP.value
    ],
    "admin": [
        KeyScope.CHAT_READ.value,
        KeyScope.CHAT_WRITE.value,
        KeyScope.ACTIONS_CALENDAR.value,
        KeyScope.ACTIONS_PAYMENTS.value,
        KeyScope.ACTIONS_EMAIL.value,
        KeyScope.ACTIONS_WHATSAPP.value,
        KeyScope.ADMIN_KEYS.value,
        KeyScope.ADMIN_BILLING.value
    ]
}


class AuremKeyService:
    """
    AUREM API Key Management
    
    Key Format: sk_aurem_{environment}_{random_hex}
    Example: sk_aurem_live_a1b2c3d4e5f6g7h8
    """
    
    COLLECTION = "aurem_api_keys"
    USAGE_COLLECTION = "aurem_key_usage"
    PREFIX_LIVE = "sk_aurem_live_"
    PREFIX_TEST = "sk_aurem_test_"
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.keys_collection = db[self.COLLECTION]
        self.usage_collection = db[self.USAGE_COLLECTION]
    
    async def ensure_indexes(self):
        """Create database indexes"""
        await self.keys_collection.create_index("key_hash", unique=True)
        await self.keys_collection.create_index("business_id")
        await self.keys_collection.create_index("status")
        await self.usage_collection.create_index([("key_id", 1), ("timestamp", -1)])
        await self.usage_collection.create_index([("business_id", 1), ("billing_period", 1)])
    
    def _hash_key(self, api_key: str) -> str:
        """Hash API key for secure storage (never store raw keys)"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    def _generate_key(self, is_test: bool = False) -> str:
        """Generate a new AUREM API key"""
        prefix = self.PREFIX_TEST if is_test else self.PREFIX_LIVE
        random_part = secrets.token_hex(16)
        return f"{prefix}{random_part}"
    
    async def create_key(
        self,
        business_id: str,
        name: str = "Default API Key",
        is_test: bool = False,
        rate_limit: int = 1000,  # requests per day
        scope_bundle: str = "standard",  # read_only, standard, full_access, admin
        custom_scopes: Optional[List[str]] = None,  # Override bundle with custom scopes
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create a new AUREM API key for a business.
        
        Returns the full key ONLY ONCE - store it securely!
        
        Scope bundles:
        - read_only: chat:read only
        - standard: chat:read, chat:write, actions:email
        - full_access: All action scopes (calendar, payments, email, whatsapp)
        - admin: Full access + admin:keys, admin:billing
        """
        api_key = self._generate_key(is_test)
        key_hash = self._hash_key(api_key)
        key_id = f"key_{secrets.token_hex(8)}"
        
        # Determine scopes - custom overrides bundle
        if custom_scopes:
            scopes = custom_scopes
        else:
            scopes = SCOPE_BUNDLES.get(scope_bundle, SCOPE_BUNDLES["standard"])
        
        key_doc = {
            "key_id": key_id,
            "key_hash": key_hash,
            "key_prefix": api_key[:20] + "...",  # Store prefix for identification
            "business_id": business_id,
            "name": name,
            "is_test": is_test,
            "scopes": scopes,
            "scope_bundle": scope_bundle if not custom_scopes else "custom",
            "status": KeyStatus.ACTIVE.value,
            "rate_limit_daily": rate_limit,
            "usage_today": 0,
            "usage_total": 0,
            "created_at": datetime.now(timezone.utc),
            "last_used_at": None,
            "metadata": metadata or {}
        }
        
        await self.keys_collection.insert_one(key_doc)
        
        logger.info(f"[AuremKeys] Created key {key_id} for business {business_id} with scopes: {scopes}")
        
        # Return full key only once
        return {
            "key_id": key_id,
            "api_key": api_key,  # ONLY returned at creation time
            "key_prefix": key_doc["key_prefix"],
            "name": name,
            "is_test": is_test,
            "scopes": scopes,
            "scope_bundle": key_doc["scope_bundle"],
            "rate_limit_daily": rate_limit,
            "message": "Store this key securely - it will not be shown again!"
        }
    
    async def validate_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Validate an AUREM API key.
        
        Returns key info if valid, None if invalid.
        """
        if not api_key:
            return None
        
        # Check prefix
        if not (api_key.startswith(self.PREFIX_LIVE) or api_key.startswith(self.PREFIX_TEST)):
            logger.warning("[AuremKeys] Invalid key prefix")
            return None
        
        key_hash = self._hash_key(api_key)
        
        key_doc = await self.keys_collection.find_one(
            {"key_hash": key_hash},
            {"_id": 0, "key_hash": 0}
        )
        
        if not key_doc:
            logger.warning("[AuremKeys] Key not found")
            return None
        
        if key_doc["status"] != KeyStatus.ACTIVE.value:
            logger.warning(f"[AuremKeys] Key {key_doc['key_id']} is {key_doc['status']}")
            return None
        
        # Check rate limit
        if key_doc["usage_today"] >= key_doc["rate_limit_daily"]:
            logger.warning(f"[AuremKeys] Key {key_doc['key_id']} rate limited")
            return None
        
        return key_doc
    
    async def record_usage(
        self,
        key_id: str,
        business_id: str,
        operation: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        model: str = "gpt-4o-mini",
        latency_ms: int = 0,
        success: bool = True,
        metadata: Optional[Dict] = None
    ):
        """Record API key usage for billing"""
        now = datetime.now(timezone.utc)
        billing_period = now.strftime("%Y-%m")  # Monthly billing
        
        # Usage record
        usage_doc = {
            "key_id": key_id,
            "business_id": business_id,
            "operation": operation,
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "tokens_total": tokens_in + tokens_out,
            "latency_ms": latency_ms,
            "success": success,
            "billing_period": billing_period,
            "timestamp": now,
            "metadata": metadata or {}
        }
        
        await self.usage_collection.insert_one(usage_doc)
        
        # Update key counters
        await self.keys_collection.update_one(
            {"key_id": key_id},
            {
                "$inc": {"usage_today": 1, "usage_total": 1},
                "$set": {"last_used_at": now}
            }
        )
        
        # Also track in Redis rate limiter
        try:
            from services.aurem_commercial import get_rate_limiter
            limiter = await get_rate_limiter()
            await limiter.check_limit(business_id, "llm_calls", "pro")
        except Exception:
            pass  # Redis may not be available
    
    async def get_usage_stats(
        self,
        business_id: str,
        billing_period: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get usage statistics for billing"""
        if not billing_period:
            billing_period = datetime.now(timezone.utc).strftime("%Y-%m")
        
        pipeline = [
            {"$match": {"business_id": business_id, "billing_period": billing_period}},
            {"$group": {
                "_id": "$model",
                "total_requests": {"$sum": 1},
                "total_tokens_in": {"$sum": "$tokens_in"},
                "total_tokens_out": {"$sum": "$tokens_out"},
                "successful_requests": {"$sum": {"$cond": ["$success", 1, 0]}},
                "avg_latency_ms": {"$avg": "$latency_ms"}
            }}
        ]
        
        results = await self.usage_collection.aggregate(pipeline).to_list(100)
        
        total_tokens = sum(r.get("total_tokens_in", 0) + r.get("total_tokens_out", 0) for r in results)
        total_requests = sum(r.get("total_requests", 0) for r in results)
        
        return {
            "business_id": business_id,
            "billing_period": billing_period,
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "by_model": results,
            "estimated_cost_usd": self._estimate_cost(results)
        }
    
    def _estimate_cost(self, usage_by_model: List[Dict]) -> float:
        """Estimate cost based on token usage"""
        # Pricing per 1M tokens (approximate)
        pricing = {
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4-turbo": {"input": 10.00, "output": 30.00},
            "claude-3-sonnet": {"input": 3.00, "output": 15.00}
        }
        
        total = 0.0
        for model_usage in usage_by_model:
            model = model_usage.get("_id", "gpt-4o-mini")
            prices = pricing.get(model, pricing["gpt-4o-mini"])
            
            tokens_in = model_usage.get("total_tokens_in", 0)
            tokens_out = model_usage.get("total_tokens_out", 0)
            
            total += (tokens_in / 1_000_000) * prices["input"]
            total += (tokens_out / 1_000_000) * prices["output"]
        
        return round(total, 4)
    
    async def list_keys(self, business_id: str) -> List[Dict[str, Any]]:
        """List all API keys for a business (without hashes)"""
        keys = await self.keys_collection.find(
            {"business_id": business_id},
            {"_id": 0, "key_hash": 0}
        ).to_list(100)
        
        return keys
    
    async def revoke_key(self, key_id: str, business_id: str) -> bool:
        """Revoke an API key"""
        result = await self.keys_collection.update_one(
            {"key_id": key_id, "business_id": business_id},
            {"$set": {"status": KeyStatus.REVOKED.value, "revoked_at": datetime.now(timezone.utc)}}
        )
        
        if result.modified_count > 0:
            logger.info(f"[AuremKeys] Revoked key {key_id}")
            return True
        return False
    
    async def reset_daily_usage(self):
        """Reset daily usage counters (call via scheduler)"""
        await self.keys_collection.update_many(
            {},
            {"$set": {"usage_today": 0}}
        )
        logger.info("[AuremKeys] Reset daily usage counters")


# Singleton
_key_service: Optional[AuremKeyService] = None

def get_aurem_key_service(db: AsyncIOMotorDatabase) -> AuremKeyService:
    global _key_service
    if _key_service is None:
        _key_service = AuremKeyService(db)
    return _key_service
