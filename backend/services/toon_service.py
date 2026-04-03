"""
AUREM TOON Service
Core service for TOON-based data handling across the entire system

This service:
1. Auto-converts all MongoDB queries to TOON
2. Provides TOON encoders for all data types
3. Handles TOON parsing from frontend
4. Manages TOON caching for performance
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from utils.toon_encoder import ToonEncoder, ReRootsToonEncoder, json_to_toon
from models.saas_toon_models import (
    SaaSToonEncoder,
    ServiceDefinition,
    SubscriptionPlanTOON,
    UserSubscriptionTOON,
    ServiceUsageLogTOON,
    APIKeyRecord,
    SubscriptionTier,
    ServiceCategory,
    ServiceStatus
)

logger = logging.getLogger(__name__)


class AuremToonService:
    """
    Central TOON service for all AUREM data operations
    Converts MongoDB documents to TOON format automatically
    """
    
    def __init__(self, db=None):
        self.db = db
        self.base_encoder = ToonEncoder()
        self.reroots_encoder = ReRootsToonEncoder()
        self.saas_encoder = SaaSToonEncoder()
        
    def set_db(self, db):
        """Set database reference"""
        self.db = db
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # SUBSCRIPTION DATA (TOON FORMAT)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def get_subscription_plans_toon(self) -> str:
        """
        Get all subscription plans in TOON format
        
        Returns:
        Plan[4]{id, name, price_m, price_y, limits, features}:
          free, Free Forever, 0, 0, {tokens:5k,formulas:3}, {ai_chat:T,voice:browser}
          starter, Starter, 99, 950, {tokens:50k,formulas:20}, {ai_chat:T,voice:openai}
          professional, Professional, 399, 3830, {tokens:200k,formulas:50}, {ai_chat:T,voice:openai,multi_agent:T}
          enterprise, Enterprise, 999, 9590, {tokens:unlimited}, {ai_chat:T,voice:voxtral,all:T}
        """
        if self.db is None:
            return "Plan[0]:"
        
        plans = await self.db.subscription_plans.find(
            {"active": True},
            {"_id": 0}
        ).to_list(100)
        
        if not plans:
            return "Plan[0]:"
        
        # TOON tabular format
        header = f"Plan[{len(plans)}]{{id, name, price_m, price_y, limits, features}}"
        
        rows = []
        for plan in plans:
            plan_id = plan.get('plan_id', plan.get('tier', 'unknown'))
            name = plan.get('name', 'Unknown')
            price_m = plan.get('price_monthly', 0)
            price_y = plan.get('price_annual', 0)
            
            # Compress limits
            limits = plan.get('limits', {})
            limits_str = ",".join([f"{k.split('_')[0]}:{v}" for k, v in limits.items()])
            
            # Compress features
            features = plan.get('features', {})
            features_str = ",".join([f"{k}:{v}" if isinstance(v, bool) else f"{k}:{v}" for k, v in list(features.items())[:5]])
            
            rows.append(f"{plan_id}, {name}, {price_m}, {price_y}, {{{limits_str}}}, {{{features_str}}}")
        
        return f"{header}:\n  " + "\n  ".join(rows)
    
    async def get_user_subscription_toon(self, user_id: str) -> str:
        """
        Get user's current subscription in TOON format
        
        Returns:
        Subscription[sub_xxxxx]:
          user_id: user_12345
          tier: professional
          status: active
          amount: 399
          period_end: 2026-02-01
          usage: {tokens_used:15000, tokens_limit:200000, formulas:5/50}
          services: Service[3]{id, status, tokens}: gpt-4o, active, 15000; voxtral, active, 0; stripe, active, 0
        """
        if self.db is None:
            return f"Subscription: user {user_id} not found"
        
        sub = await self.db.subscriptions.find_one(
            {"user_id": user_id, "status": {"$in": ["active", "trialing"]}},
            {"_id": 0}
        )
        
        if not sub:
            # Return free tier default
            return f"Subscription[free]:\n  user_id: {user_id}\n  tier: free\n  status: active\n  amount: 0"
        
        # Use SaaS TOON encoder
        lines = [f"Subscription[{sub.get('id', sub.get('subscription_id', 'unknown'))}]:"]
        lines.append(f"  user_id: {user_id}")
        lines.append(f"  tier: {sub.get('tier', 'free')}")
        lines.append(f"  status: {sub.get('status', 'active')}")
        lines.append(f"  amount: {sub.get('amount', 0)}")
        lines.append(f"  period_end: {sub.get('current_period_end', 'N/A')}")
        
        # Usage (compressed)
        usage = sub.get('usage', {})
        usage_parts = []
        for key, val in usage.items():
            if 'used' in key or 'count' in key:
                limit_key = key.replace('_used', '_limit').replace('_count', '_limit')
                limit = usage.get(limit_key, 'unlimited')
                resource = key.split('_')[0]
                usage_parts.append(f"{resource}:{val}/{limit}")
        lines.append(f"  usage: {{{', '.join(usage_parts)}}}")
        
        # Active services (tabular)
        active_services = sub.get('active_services', [])
        if active_services:
            svc_count = len(active_services)
            svc_rows = []
            for svc in active_services:
                svc_rows.append(f"{svc.get('service_id', 'N/A')}, {svc.get('status', 'N/A')}, {svc.get('tokens_used', 0)}")
            lines.append(f"  services: Service[{svc_count}]{{id, status, tokens}}: {'; '.join(svc_rows)}")
        
        return "\n".join(lines)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # SERVICE REGISTRY (TOON FORMAT)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def get_service_registry_toon(self) -> str:
        """
        Get all available third-party services in TOON format
        
        Returns:
        Service[15]{id, cat, provider, cost, status, tiers}:
          gpt-4o, llm, OpenAI, 0.005/1k, active, [starter|pro|ent]
          gpt-4o-mini, llm, OpenAI, 0.00015/1k, active, [free|starter|pro|ent]
          voxtral-tts, voice, Mistral, 0.002/min, active, [pro|ent]
          openai-tts, voice, OpenAI, 0.015/1k, active, [starter|pro|ent]
          stripe-payments, payments, Stripe, 0.029/txn, active, [all]
          ...
        """
        if self.db is None:
            return "Service[0]:"
        
        services = await self.db.service_registry.find(
            {},
            {"_id": 0}
        ).to_list(100)
        
        if not services:
            # Return default service registry
            return self._get_default_service_registry_toon()
        
        header = f"Service[{len(services)}]{{id, cat, provider, cost, status, tiers}}"
        
        rows = []
        for svc in services:
            service_id = svc.get('service_id', 'unknown')
            category = svc.get('category', 'unknown')
            provider = svc.get('provider', 'Unknown')
            
            # Format cost
            cost = svc.get('cost_per_1k_tokens') or svc.get('cost_per_minute') or svc.get('cost_per_api_call') or 0
            cost_unit = '/1k' if 'tokens' in str(svc.get('cost_per_1k_tokens', '')) else '/min' if svc.get('cost_per_minute') else '/call'
            cost_str = f"{cost}{cost_unit}"
            
            status = svc.get('status', 'no_keys')
            
            # Tiers (abbreviated)
            tiers = svc.get('available_in_tiers', [])
            tiers_str = "|".join([t[:3] for t in tiers]) if tiers else "all"
            
            rows.append(f"{service_id}, {category}, {provider}, {cost_str}, {status}, [{tiers_str}]")
        
        return f"{header}:\n  " + "\n  ".join(rows)
    
    def _get_default_service_registry_toon(self) -> str:
        """Default service registry (when DB is empty)"""
        services = [
            # LLM Services
            "gpt-4o, llm, OpenAI, 0.005/1k, no_keys, [sta|pro|ent]",
            "gpt-4o-mini, llm, OpenAI, 0.00015/1k, no_keys, [free|sta|pro|ent]",
            "claude-sonnet-4, llm, Anthropic, 0.003/1k, no_keys, [pro|ent]",
            "gemini-2.5-flash, llm, Google, 0.0002/1k, no_keys, [sta|pro|ent]",
            
            # Voice Services
            "openai-tts, voice, OpenAI, 0.015/1k, no_keys, [sta|pro|ent]",
            "openai-whisper, voice, OpenAI, 0.006/min, no_keys, [sta|pro|ent]",
            "voxtral-tts, voice, Mistral, 0.002/min, no_keys, [pro|ent]",
            "elevenlabs-tts, voice, ElevenLabs, 0.18/1k, no_keys, [ent]",
            
            # Image Services
            "gpt-image-1, image, OpenAI, 0.04/img, no_keys, [pro|ent]",
            "nano-banana, image, Gemini, 0.02/img, no_keys, [pro|ent]",
            
            # Video Services
            "sora-2, video, OpenAI, 0.08/sec, no_keys, [ent]",
            
            # Automation
            "n8n-cloud, automation, n8n, 0/free, no_keys, [sta|pro|ent]",
            
            # Communication
            "resend-email, communication, Resend, 0.0001/email, no_keys, [sta|pro|ent]",
            "twilio-sms, communication, Twilio, 0.0079/sms, no_keys, [pro|ent]",
            
            # Payments
            "stripe-payments, payments, Stripe, 0.029/txn, no_keys, [all]"
        ]
        
        header = f"Service[{len(services)}]{{id, cat, provider, cost, status, tiers}}"
        return f"{header}:\n  " + "\n  ".join(services)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # API KEYS MANAGEMENT (TOON FORMAT)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def get_api_keys_toon(self, admin_id: Optional[str] = None) -> str:
        """
        Get all API keys in TOON format (for admin panel)
        
        Returns:
        APIKey[5]{service, preview, status, calls, spend, last_used}:
          gpt-4o, sk-proj-...ABC, active, 15000, 45.67, 2026-01-15T10:30
          voxtral-tts, sk-mist-...XYZ, active, 500, 12.34, 2026-01-14T15:20
          stripe, sk_live_...789, active, 89, 125.50, 2026-01-15T09:15
          ...
        """
        if self.db is None:
            return "APIKey[0]:"
        
        keys = await self.db.api_keys_registry.find(
            {},
            {"_id": 0, "encrypted_key": 0}  # Never return actual keys
        ).to_list(100)
        
        if not keys:
            return "APIKey[0]:"
        
        header = f"APIKey[{len(keys)}]{{service, preview, status, calls, spend, last_used}}"
        
        rows = []
        for key in keys:
            service_id = key.get('service_id', 'unknown')
            preview = key.get('key_preview', '***')
            status = key.get('status', 'unknown')
            calls = key.get('total_calls', 0)
            spend = key.get('total_spend_usd', 0.0)
            last_used = key.get('last_used', 'never')
            if isinstance(last_used, datetime):
                last_used = last_used.strftime('%Y-%m-%dT%H:%M')
            
            rows.append(f"{service_id}, {preview}, {status}, {calls}, {spend:.2f}, {last_used}")
        
        return f"{header}:\n  " + "\n  ".join(rows)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # USAGE ANALYTICS (TOON FORMAT)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def get_usage_analytics_toon(
        self,
        user_id: Optional[str] = None,
        service_id: Optional[str] = None,
        limit: int = 100
    ) -> str:
        """
        Get usage logs in TOON format
        
        Returns:
        UsageLog[150]{user, service, tokens, cost, endpoint, time}:
          user_123, gpt-4o, 1500, 0.0075, /api/aurem/chat, 2026-01-15T10:30
          user_123, voxtral-tts, 0, 0.0020, /api/voice/tts, 2026-01-15T10:31
          user_456, gpt-4o-mini, 500, 0.0001, /api/aurem/chat, 2026-01-15T10:32
          ...
        """
        if self.db is None:
            return "UsageLog[0]:"
        
        # Build query
        query = {}
        if user_id:
            query['user_id'] = user_id
        if service_id:
            query['service_id'] = service_id
        
        logs = await self.db.usage_logs.find(
            query,
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        if not logs:
            return "UsageLog[0]:"
        
        header = f"UsageLog[{len(logs)}]{{user, service, tokens, cost, endpoint, time}}"
        
        rows = []
        for log in logs:
            user = log.get('user_id', 'unknown')[:12]  # Truncate for display
            service = log.get('service_id', 'unknown')
            tokens = log.get('tokens_used', 0)
            cost = log.get('cost_usd', 0.0)
            endpoint = log.get('endpoint', 'N/A')
            timestamp = log.get('timestamp', datetime.now(timezone.utc))
            if isinstance(timestamp, datetime):
                timestamp = timestamp.strftime('%Y-%m-%dT%H:%M')
            
            rows.append(f"{user}, {service}, {tokens}, {cost:.4f}, {endpoint}, {timestamp}")
        
        return f"{header}:\n  " + "\n  ".join(rows)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # ADMIN DASHBOARD (TOON FORMAT)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def get_admin_dashboard_toon(self) -> str:
        """
        Get complete admin dashboard data in TOON format
        
        Returns comprehensive TOON document with:
        - Active subscriptions count
        - MRR/ARR
        - Service statuses
        - Top users by usage
        - Recent activity
        """
        if self.db is None:
            return "AdminDashboard: Database not connected"
        
        lines = ["AdminDashboard:"]
        
        # 1. Subscription metrics
        total_subs = await self.db.subscriptions.count_documents({"status": "active"})
        
        # Calculate MRR
        pipeline = [
            {"$match": {"status": "active"}},
            {"$group": {"_id": None, "total_mrr": {"$sum": "$amount"}}}
        ]
        mrr_result = await self.db.subscriptions.aggregate(pipeline).to_list(1)
        mrr = mrr_result[0]['total_mrr'] if mrr_result else 0
        arr = mrr * 12
        
        lines.append(f"  metrics:")
        lines.append(f"    total_active_subscriptions: {total_subs}")
        lines.append(f"    mrr: ${mrr:.2f}")
        lines.append(f"    arr: ${arr:.2f}")
        
        # 2. Subscription breakdown by tier
        tier_counts = await self.db.subscriptions.aggregate([
            {"$match": {"status": "active"}},
            {"$group": {"_id": "$tier", "count": {"$sum": 1}}}
        ]).to_list(10)
        
        if tier_counts:
            lines.append(f"  tiers:")
            for tier in tier_counts:
                lines.append(f"    {tier['_id']}: {tier['count']}")
        
        # 3. Service statuses
        services = await self.db.api_keys_registry.aggregate([
            {"$group": {
                "_id": "$service_id",
                "status": {"$first": "$status"},
                "total_spend": {"$sum": "$total_spend_usd"}
            }}
        ]).to_list(100)
        
        if services:
            lines.append(f"  services: Service[{len(services)}]{{id, status, spend}}: " + 
                        "; ".join([f"{s['_id']}, {s['status']}, {s['total_spend']:.2f}" for s in services[:5]]))
        
        # 4. Top users by usage
        top_users = await self.db.usage_logs.aggregate([
            {"$group": {
                "_id": "$user_id",
                "total_tokens": {"$sum": "$tokens_used"},
                "total_cost": {"$sum": "$cost_usd"}
            }},
            {"$sort": {"total_cost": -1}},
            {"$limit": 5}
        ]).to_list(5)
        
        if top_users:
            lines.append(f"  top_users: User[{len(top_users)}]{{id, tokens, cost}}: " +
                        "; ".join([f"{u['_id'][:12]}, {u['total_tokens']}, {u['total_cost']:.2f}" for u in top_users]))
        
        return "\n".join(lines)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # GENERIC TOON CONVERSION
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def to_toon(self, data: Any, data_type: Optional[str] = None) -> str:
        """
        Generic TOON conversion for any data
        
        Args:
            data: Any JSON-compatible data
            data_type: Optional type hint (formula, products, inventory, customer, order, subscription, etc.)
        
        Returns:
            TOON-formatted string
        """
        if data_type == 'subscription':
            return self.saas_encoder.encode_subscription(data)
        elif data_type == 'service_usage':
            return self.saas_encoder.encode_service_usage(data)
        elif data_type == 'api_keys':
            return self.saas_encoder.encode_api_keys(data)
        elif data_type in ['formula', 'products', 'inventory', 'customer', 'order']:
            return json_to_toon(data, data_type)
        else:
            return self.base_encoder.encode(data)


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_toon_service = AuremToonService()

def get_toon_service() -> AuremToonService:
    """Get global TOON service instance"""
    return _toon_service

def set_toon_service_db(db):
    """Set database for TOON service"""
    _toon_service.set_db(db)
