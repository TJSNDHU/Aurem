"""
AUREM Commercial Platform - Services Package
Multi-tenant SaaS infrastructure for AI-powered communication platform
"""

from .encryption_service import EncryptionService, get_encryption_service
from .audit_service import AuditLogger, AuditAction, get_audit_logger
from .token_vault import TokenVault, IntegrationProvider, IntegrationStatus, get_token_vault
from .workspace_service import (
    CustomerWorkspace, 
    SubscriptionPlan, 
    WorkspaceStatus,
    PLAN_LIMITS,
    get_workspace_service
)
from .consent_service import ConsentTracker, ConsentType, ConsentStatus, get_consent_tracker
from .billing_service import BillingService, PaymentStatus, get_billing_service
from .gmail_service import GmailService, get_gmail_service
from .redis_memory import AuremRedisMemory, get_aurem_memory
from .semantic_cache import AuremSemanticCache, get_semantic_cache
from .rate_limiter import AuremRateLimiter, get_rate_limiter, PLAN_LIMITS as RATE_PLAN_LIMITS
from .websocket_hub import AuremWebSocketHub, get_websocket_hub

from .action_engine import ActionEngine, get_action_engine
from .key_service import AuremKeyService, get_aurem_key_service, KeyStatus
from .llm_proxy import AuremLLMProxy, get_llm_proxy
from .brain_orchestrator import AuremBrainOrchestrator, get_brain_orchestrator, IntentType, BrainPhase
from .unified_inbox_service import UnifiedInboxService, get_unified_inbox_service, ChannelType, MessageStatus
from .whatsapp_service import WhatsAppService, get_whatsapp_service, WhatsAppConnectionStatus
from .voice_service import AuremVoiceService, get_voice_service, CallStatus, PersonaType, CustomerTier
from .date_parser import AuremDateParser, get_date_parser, parse_date, parse_date_for_tool, DateConfidence
from .agent_reach import AgentReachService, get_reach_service, ReachTool, REACH_TOOL_DEFINITIONS

__all__ = [
    # Encryption
    "EncryptionService",
    "get_encryption_service",
    
    # Audit
    "AuditLogger",
    "AuditAction", 
    "get_audit_logger",
    
    # Token Vault
    "TokenVault",
    "IntegrationProvider",
    "IntegrationStatus",
    "get_token_vault",
    
    # Workspace
    "CustomerWorkspace",
    "SubscriptionPlan",
    "WorkspaceStatus",
    "PLAN_LIMITS",
    "get_workspace_service",
    
    # Consent
    "ConsentTracker",
    "ConsentType",
    "ConsentStatus",
    "get_consent_tracker",
    
    # Billing
    "BillingService",
    "PaymentStatus",
    "get_billing_service",
    
    # Gmail
    "GmailService",
    "get_gmail_service",
    
    # Redis Memory
    "AuremRedisMemory",
    "get_aurem_memory",
    
    # Semantic Cache
    "AuremSemanticCache",
    "get_semantic_cache",
    
    # Rate Limiter
    "AuremRateLimiter",
    "get_rate_limiter",
    "RATE_PLAN_LIMITS",
    
    # WebSocket Hub
    "AuremWebSocketHub",
    "get_websocket_hub",
    
    # Action Engine
    "ActionEngine",
    "get_action_engine",
    
    # API Key Management
    "AuremKeyService",
    "get_aurem_key_service",
    "KeyStatus",
    
    # LLM Proxy
    "AuremLLMProxy",
    "get_llm_proxy",
    
    # Brain Orchestrator (Phase 4 - AI Brain)
    "AuremBrainOrchestrator",
    "get_brain_orchestrator",
    "IntentType",
    "BrainPhase",
    
    # Unified Inbox (Phase 7)
    "UnifiedInboxService",
    "get_unified_inbox_service",
    "ChannelType",
    "MessageStatus",
    
    # WhatsApp (Phase 5)
    "WhatsAppService",
    "get_whatsapp_service",
    "WhatsAppConnectionStatus",
    
    # Voice Module (Phase 8)
    "AuremVoiceService",
    "get_voice_service",
    "CallStatus",
    "PersonaType",
    "CustomerTier",
    
    # Date Parser (Universal Brain)
    "AuremDateParser",
    "get_date_parser",
    "parse_date",
    "parse_date_for_tool",
    "DateConfidence",
    
    # Agent-Reach (Zero-API Social Intelligence)
    "AgentReachService",
    "get_reach_service",
    "ReachTool",
    "REACH_TOOL_DEFINITIONS"
]
