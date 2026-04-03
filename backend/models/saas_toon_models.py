"""
AUREM SaaS Models - TOON Format
Token-Oriented Object Notation for efficient data storage

All subscription, service, and usage data uses TOON encoding
to minimize database size and LLM token usage.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class SubscriptionTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class ServiceCategory(str, Enum):
    LLM = "llm"  # Language models
    VOICE = "voice"  # TTS/STT
    IMAGE = "image"  # Image generation
    VIDEO = "video"  # Video generation/processing
    AUTOMATION = "automation"  # n8n, workflows
    INTELLIGENCE = "intelligence"  # Agent-Reach, competitive analysis
    COMMUNICATION = "communication"  # Email, SMS, WhatsApp
    PAYMENTS = "payments"  # Stripe, PayPal
    ANALYTICS = "analytics"  # Tracking, monitoring


class ServiceStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    NO_KEYS = "no_keys"  # Service available but no API keys added
    SUSPENDED = "suspended"  # Admin manually suspended


# ═══════════════════════════════════════════════════════════════════════════════
# TOON DATA MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class ServiceDefinition(BaseModel):
    """
    TOON Format for Third-Party Service Registry
    
    Example TOON:
    Service[gpt-4o]:
      cat: llm
      provider: OpenAI
      status: active
      cost_per_1k_tokens: 0.005
      features: {chat, completion, vision}
    """
    service_id: str  # Unique ID: gpt-4o, voxtral-tts, stripe-payments
    name: str  # Display name: "GPT-4o", "Voxtral TTS"
    category: ServiceCategory
    provider: str  # OpenAI, Mistral, Stripe, etc.
    
    # Pricing (per unit)
    cost_per_1k_tokens: Optional[float] = None  # For LLMs
    cost_per_minute: Optional[float] = None  # For voice
    cost_per_image: Optional[float] = None  # For image gen
    cost_per_api_call: Optional[float] = None  # For other services
    
    # Features this service provides
    features: List[str] = []  # ["chat", "completion", "vision"]
    
    # API Key requirements
    requires_api_key: bool = True
    api_key_field_name: str = "api_key"  # ENV var name or config key
    additional_config: Dict[str, Any] = {}  # Extra config needed
    
    # Which tiers have access to this service
    available_in_tiers: List[SubscriptionTier] = [
        SubscriptionTier.STARTER,
        SubscriptionTier.PROFESSIONAL,
        SubscriptionTier.ENTERPRISE
    ]
    
    # Documentation
    docs_url: Optional[str] = None
    setup_instructions: Optional[str] = None


class SubscriptionPlanTOON(BaseModel):
    """
    TOON Format for Subscription Plans
    
    Example TOON:
    Plan[starter]:
      name: Starter
      price_monthly: 99
      limits: {tokens: 50000, formulas: 20, content: 50}
      features: {ai_chat: T, voice_tts: openai, multi_agent: F}
    """
    plan_id: str  # free, starter, professional, enterprise
    tier: SubscriptionTier
    name: str
    tagline: str
    
    # Pricing
    price_monthly: float
    price_annual: float  # With 20% discount
    currency: str = "usd"
    
    # Stripe IDs
    stripe_price_id_monthly: Optional[str] = None
    stripe_price_id_annual: Optional[str] = None
    
    # Usage Limits (TOON compressed)
    limits: Dict[str, int] = {
        "ai_tokens": 50000,
        "formulas": 20,
        "content_pieces": 50,
        "workflows": 5,
        "videos": 0
    }
    
    # Feature Access (TOON compressed)
    features: Dict[str, Any] = {
        "ai_chat": True,
        "voice_tts": "openai",  # browser|openai|voxtral
        "voice_to_voice": False,
        "multi_agent": False,
        "crew_ai": [],
        "video_upscaling": False,
        "competitive_intelligence": False,
        "api_access": False,
        "white_label": False,
        "priority_support": False
    }
    
    # Services included in this tier (references ServiceDefinition.service_id)
    included_services: List[str] = []  # ["gpt-4o-mini", "openai-tts", "stripe-payments"]
    
    # Marketing
    features_list: List[str] = []
    is_popular: bool = False
    active: bool = True


class UserSubscriptionTOON(BaseModel):
    """
    TOON Format for User Subscription
    
    Example TOON:
    Subscription[sub_xxxxx]:
      user_id: user_12345
      tier: professional
      status: active
      amount: 399
      usage: {tokens_used: 15000, tokens_limit: 200000, formulas_count: 5}
      services: Service[3]{id, status, tokens_used}: gpt-4o, active, 15000; voxtral-tts, active, 0; stripe, active, 0
    """
    subscription_id: str
    user_id: str
    tier: SubscriptionTier
    status: SubscriptionStatus
    
    # Billing
    amount: float
    currency: str = "usd"
    billing_cycle: str = "monthly"  # monthly|annual
    
    # Stripe
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    
    # Dates
    current_period_start: datetime
    current_period_end: datetime
    trial_ends_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    
    # Usage Tracking (TOON compressed)
    usage: Dict[str, int] = {
        "ai_tokens_used": 0,
        "ai_tokens_limit": 50000,
        "formulas_count": 0,
        "formulas_limit": 20,
        "content_generated": 0,
        "content_limit": 50,
        "workflows_count": 0,
        "workflows_limit": 5
    }
    
    # Custom Features (for custom tier)
    custom_features: List[Dict[str, Any]] = []
    
    # Active Services (TOON compressed)
    # Each service tracks: service_id, status, tokens_used, cost_this_period
    active_services: List[Dict[str, Any]] = []
    
    # Metadata
    created_at: datetime
    updated_at: datetime


class ServiceUsageLogTOON(BaseModel):
    """
    TOON Format for Service Usage Logs
    
    Example TOON:
    UsageLog[log_xxxxx]:
      user_id: user_12345
      service_id: gpt-4o
      tokens: 1500
      cost: 0.0075
      endpoint: /api/aurem/chat
      timestamp: 2026-01-15T10:30:00Z
    """
    log_id: str
    user_id: str
    subscription_id: str
    service_id: str  # References ServiceDefinition
    
    # Usage metrics (varies by service type)
    tokens_used: Optional[int] = None  # For LLMs
    minutes_used: Optional[float] = None  # For voice
    images_generated: Optional[int] = None  # For image gen
    api_calls: Optional[int] = None  # For other services
    
    # Cost
    cost_usd: float  # Calculated cost for this usage
    
    # Context
    endpoint: Optional[str] = None  # Which API endpoint was called
    metadata: Dict[str, Any] = {}  # Additional context
    
    # Timestamp
    timestamp: datetime


class APIKeyRecord(BaseModel):
    """
    Admin-managed API keys for third-party services
    
    TOON Format:
    APIKey[key_xxxxx]:
      service_id: gpt-4o
      key_preview: sk-proj-...ABC
      added_by: admin_user_123
      status: active
      total_spend: 45.67
      last_used: 2026-01-15T10:30:00Z
    """
    key_id: str
    service_id: str  # References ServiceDefinition
    
    # Encrypted API key (never stored in plain text)
    encrypted_key: str
    key_preview: str  # First 8 and last 4 chars: "sk-proj-...ABC"
    
    # Metadata
    added_by: str  # Admin user who added this key
    added_at: datetime
    status: ServiceStatus
    
    # Usage tracking
    total_calls: int = 0
    total_spend_usd: float = 0.0
    last_used: Optional[datetime] = None
    
    # Limits (optional - can set spend limits per key)
    monthly_spend_limit: Optional[float] = None
    daily_call_limit: Optional[int] = None
    
    # Notes
    notes: Optional[str] = None  # Admin notes about this key


class TokenRechargeRecord(BaseModel):
    """
    Track token/credit purchases from third-party providers
    
    TOON Format:
    Recharge[rech_xxxxx]:
      service_id: openai-credits
      amount_usd: 100.00
      tokens_added: 20000000
      purchased_by: admin_user_123
      purchase_date: 2026-01-15T10:30:00Z
    """
    recharge_id: str
    service_id: str  # Which service was recharged
    
    # Purchase details
    amount_usd: float
    tokens_added: Optional[int] = None  # For token-based services
    credits_added: Optional[float] = None  # For credit-based services
    
    # Who made the purchase
    purchased_by: str  # Admin user
    purchase_date: datetime
    
    # Payment method
    payment_method: str  # "stripe", "paypal", "manual"
    payment_reference: Optional[str] = None  # Transaction ID
    
    # Notes
    notes: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# TOON ENCODER EXTENSIONS FOR SAAS DATA
# ═══════════════════════════════════════════════════════════════════════════════

class SaaSToonEncoder:
    """
    Specialized TOON encoder for SaaS subscription data
    Extends the base TOON encoder with subscription-specific formats
    """
    
    @staticmethod
    def encode_subscription(sub: UserSubscriptionTOON) -> str:
        """
        Encode subscription in TOON format
        
        Output:
        Subscription[sub_xxxxx]:
          user_id: user_12345
          tier: professional
          status: active
          amount: 399
          usage: {tokens_used: 15000, tokens_limit: 200000}
          services: Service[3]{id, status, tokens}: gpt-4o, active, 15000; ...
        """
        lines = [f"Subscription[{sub.subscription_id}]:"]
        lines.append(f"  user_id: {sub.user_id}")
        lines.append(f"  tier: {sub.tier.value}")
        lines.append(f"  status: {sub.status.value}")
        lines.append(f"  amount: {sub.amount}")
        lines.append(f"  period_end: {sub.current_period_end.isoformat()}")
        
        # Usage (compressed)
        usage_str = ", ".join([f"{k}: {v}" for k, v in sub.usage.items()])
        lines.append(f"  usage: {{{usage_str}}}")
        
        # Active services (tabular)
        if sub.active_services:
            svc_count = len(sub.active_services)
            svc_header = f"  services: Service[{svc_count}]{{id, status, tokens}}"
            svc_rows = []
            for svc in sub.active_services:
                svc_rows.append(f"{svc.get('service_id', 'N/A')}, {svc.get('status', 'N/A')}, {svc.get('tokens_used', 0)}")
            lines.append(f"{svc_header}: {'; '.join(svc_rows)}")
        
        return "\n".join(lines)
    
    @staticmethod
    def encode_service_usage(logs: List[ServiceUsageLogTOON]) -> str:
        """
        Encode service usage logs in TOON tabular format
        
        Output:
        UsageLog[150]{user_id, service_id, tokens, cost, timestamp}:
          user_12345, gpt-4o, 1500, 0.0075, 2026-01-15T10:30:00Z
          user_12345, voxtral-tts, 0, 0, 2026-01-15T10:31:00Z
          ...
        """
        if not logs:
            return "UsageLog[0]:"
        
        header = f"UsageLog[{len(logs)}]{{user_id, service_id, tokens, cost, timestamp}}"
        
        rows = []
        for log in logs:
            rows.append(
                f"{log.user_id}, {log.service_id}, {log.tokens_used or 0}, {log.cost_usd:.4f}, {log.timestamp.isoformat()}"
            )
        
        return f"{header}:\n  " + "\n  ".join(rows)
    
    @staticmethod
    def encode_api_keys(keys: List[APIKeyRecord]) -> str:
        """
        Encode API keys in TOON tabular format
        
        Output:
        APIKey[5]{service_id, preview, status, total_spend, last_used}:
          gpt-4o, sk-proj-...ABC, active, 45.67, 2026-01-15T10:30:00Z
          voxtral-tts, sk-mist-...XYZ, active, 12.34, 2026-01-14T15:20:00Z
          ...
        """
        if not keys:
            return "APIKey[0]:"
        
        header = f"APIKey[{len(keys)}]{{service_id, preview, status, total_spend, last_used}}"
        
        rows = []
        for key in keys:
            last_used = key.last_used.isoformat() if key.last_used else "never"
            rows.append(
                f"{key.service_id}, {key.key_preview}, {key.status.value}, {key.total_spend_usd:.2f}, {last_used}"
            )
        
        return f"{header}:\n  " + "\n  ".join(rows)
    
    @staticmethod
    def encode_service_registry(services: List[ServiceDefinition]) -> str:
        """
        Encode service registry in TOON tabular format
        
        Output:
        Service[15]{id, cat, provider, cost_1k_tokens, tiers}:
          gpt-4o, llm, OpenAI, 0.005, [starter|pro|ent]
          voxtral-tts, voice, Mistral, 0, [pro|ent]
          ...
        """
        if not services:
            return "Service[0]:"
        
        header = f"Service[{len(services)}]{{id, cat, provider, cost, tiers}}"
        
        rows = []
        for svc in services:
            cost = svc.cost_per_1k_tokens or svc.cost_per_minute or svc.cost_per_image or 0
            tiers = "|".join([t.value[:3] for t in svc.available_in_tiers])  # Abbreviated
            rows.append(
                f"{svc.service_id}, {svc.category.value}, {svc.provider}, {cost}, [{tiers}]"
            )
        
        return f"{header}:\n  " + "\n  ".join(rows)
