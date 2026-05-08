"""
AUREM Business Mapping Service
"The Traffic Controller" - Routes calls to the right Agent based on Business ID

Phase 8.4: Multi-Tenant Agent Mapping

Architecture:
┌─────────────────────────────────────────────────────────────────────┐
│                    AUREM TRAFFIC CONTROLLER                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Incoming Call/Lead                                                │
│         │                                                           │
│         ▼                                                           │
│   ┌─────────────┐     ┌─────────────────────────────────────┐      │
│   │  Business   │────▶│      AGENT LOOKUP TABLE             │      │
│   │  ID Check   │     │  ─────────────────────────────────  │      │
│   └─────────────┘     │  reroots    → Agent_Skincare_VIP    │      │
│                       │  tj_auto    → Agent_Auto_Advisor    │      │
│                       │  polaris    → Agent_Enterprise      │      │
│                       └─────────────────────────────────────┘      │
│                                    │                                │
│                                    ▼                                │
│                       ┌─────────────────────┐                      │
│                       │  DISPATCH CALL      │                      │
│                       │  + Hydrated Metadata│                      │
│                       └─────────────────────┘                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

Features:
- Business-to-Agent mapping with fallbacks
- Phone number to Business ID resolution
- Metadata hydration for call context
- A2A handoff coordination
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


# ==================== BUSINESS CONFIGURATION ====================

class AgentPersona(str, Enum):
    """Agent personas for different business contexts."""
    SKINCARE_VIP = "skincare_vip"
    SKINCARE_STANDARD = "skincare_standard"
    AUTO_ADVISOR = "auto_advisor"
    AUTO_SERVICE = "auto_service"
    FINANCE = "finance"
    SUPPORT = "support"
    ENTERPRISE = "enterprise"
    DEFAULT = "default"


class BusinessVertical(str, Enum):
    """Business verticals supported by AUREM."""
    SKINCARE = "skincare"
    AUTOMOTIVE = "automotive"
    FINANCE = "finance"
    ENTERPRISE = "enterprise"


@dataclass
class AgentConfig:
    """Configuration for an OmniDimension agent."""
    agent_id: str
    persona: AgentPersona
    name: str
    description: str
    voice_id: Optional[str] = None
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    welcome_message: str = "Hello! How can I assist you today?"
    knowledge_base_ids: List[str] = field(default_factory=list)
    can_transfer_to: List[str] = field(default_factory=list)
    web_search_enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BusinessConfig:
    """Configuration for a business entity."""
    business_id: str
    name: str
    vertical: BusinessVertical
    primary_agent: AgentConfig
    secondary_agents: List[AgentConfig] = field(default_factory=list)
    phone_numbers: List[str] = field(default_factory=list)
    unified_inbox_channel: str = ""
    timezone: str = "America/Toronto"
    vip_threshold: float = 1000.0  # Lifetime value for VIP status
    
    def __post_init__(self):
        if not self.unified_inbox_channel:
            self.unified_inbox_channel = f"inbox:{self.business_id}"


# ==================== AGENT LOOKUP TABLE ====================

class AgentLookupTable:
    """
    Central registry for Business-to-Agent mappings.
    
    This is the "Traffic Controller" that ensures the right
    AI expert handles each conversation.
    """
    
    def __init__(self):
        self._businesses: Dict[str, BusinessConfig] = {}
        self._phone_to_business: Dict[str, str] = {}
        self._agent_to_business: Dict[str, str] = {}
        self._initialize_default_mappings()
    
    def _initialize_default_mappings(self):
        """Initialize default business configurations."""
        
        # ==================== REROOTS SKINCARE ====================
        skincare_vip_agent = AgentConfig(
            agent_id=os.environ.get("OMNIDIM_AGENT_SKINCARE_VIP", "agent_skincare_vip"),
            persona=AgentPersona.SKINCARE_VIP,
            name="Luxe Sales Scientist",
            description="Premium skincare consultant for VIP clients",
            voice_id="rachel",  # ElevenLabs premium voice
            model="gpt-4o",  # Premium model for VIP
            temperature=0.6,
            welcome_message=(
                "Good day! This is your personal skincare consultant from ReRoots. "
                "I'm delighted to assist you with our PDRN treatments and premium skincare solutions."
            ),
            knowledge_base_ids=["kb_pdrn", "kb_skincare_products", "kb_treatments"],
            can_transfer_to=["finance", "support"],
            web_search_enabled=True
        )
        
        skincare_standard_agent = AgentConfig(
            agent_id=os.environ.get("OMNIDIM_AGENT_SKINCARE_STD", "agent_skincare_std"),
            persona=AgentPersona.SKINCARE_STANDARD,
            name="Skincare Advisor",
            description="General skincare consultation",
            voice_id="alloy",
            model="gpt-4o-mini",
            temperature=0.7,
            welcome_message="Hello! Welcome to ReRoots. How can I help with your skincare needs today?",
            knowledge_base_ids=["kb_pdrn", "kb_skincare_products"],
            can_transfer_to=["skincare_vip", "support"]
        )
        
        reroots_config = BusinessConfig(
            business_id="reroots",
            name="ReRoots Skincare",
            vertical=BusinessVertical.SKINCARE,
            primary_agent=skincare_vip_agent,
            secondary_agents=[skincare_standard_agent],
            phone_numbers=[
                os.environ.get("REROOTS_PHONE_1", "+14165550001"),
                os.environ.get("REROOTS_PHONE_2", "+14165550002")
            ],
            timezone="America/Toronto",
            vip_threshold=500.0
        )
        
        # ==================== TJ AUTO CLINIC ====================
        auto_advisor_agent = AgentConfig(
            agent_id=os.environ.get("OMNIDIM_AGENT_AUTO_ADVISOR", "agent_auto_advisor"),
            persona=AgentPersona.AUTO_ADVISOR,
            name="Auto Advisor",
            description="Automotive service and repair consultant",
            voice_id="adam",  # Professional male voice
            model="gpt-4o-mini",
            temperature=0.7,
            welcome_message=(
                "Hello! This is TJ Auto Clinic. I'm your automotive advisor. "
                "How can I help with your vehicle today?"
            ),
            knowledge_base_ids=["kb_gmc_chevy", "kb_auto_services", "kb_parts_catalog"],
            can_transfer_to=["finance", "support"],
            web_search_enabled=True
        )
        
        auto_service_agent = AgentConfig(
            agent_id=os.environ.get("OMNIDIM_AGENT_AUTO_SERVICE", "agent_auto_service"),
            persona=AgentPersona.AUTO_SERVICE,
            name="Service Scheduler",
            description="Appointment scheduling and service status",
            voice_id="alloy",
            model="gpt-4o-mini",
            temperature=0.5,
            welcome_message="Hi! I can help you schedule service or check on your vehicle's status.",
            knowledge_base_ids=["kb_auto_services"],
            can_transfer_to=["auto_advisor"]
        )
        
        tj_auto_config = BusinessConfig(
            business_id="tj_auto",
            name="TJ Auto Clinic",
            vertical=BusinessVertical.AUTOMOTIVE,
            primary_agent=auto_advisor_agent,
            secondary_agents=[auto_service_agent],
            phone_numbers=[
                os.environ.get("TJAUTO_PHONE_1", "+14165550101"),
                os.environ.get("TJAUTO_PHONE_2", "+14165550102")
            ],
            timezone="America/Toronto",
            vip_threshold=2000.0
        )
        
        # ==================== SHARED FINANCE AGENT ====================
        finance_agent = AgentConfig(
            agent_id=os.environ.get("OMNIDIM_AGENT_FINANCE", "agent_finance"),
            persona=AgentPersona.FINANCE,
            name="Finance Agent",
            description="Payment processing and invoicing",
            voice_id="nova",
            model="gpt-4o-mini",
            temperature=0.4,
            welcome_message="I can help you with payments, invoices, and billing inquiries.",
            knowledge_base_ids=["kb_billing", "kb_payments"],
            can_transfer_to=[]  # Finance doesn't transfer
        )
        
        finance_config = BusinessConfig(
            business_id="finance",
            name="Finance Services",
            vertical=BusinessVertical.FINANCE,
            primary_agent=finance_agent,
            phone_numbers=[]  # Shared agent, no dedicated phone
        )
        
        # ==================== ENTERPRISE DEFAULT ====================
        enterprise_agent = AgentConfig(
            agent_id=os.environ.get("OMNIDIM_AGENT_ENTERPRISE", "agent_enterprise"),
            persona=AgentPersona.ENTERPRISE,
            name="Enterprise Assistant",
            description="General business inquiries",
            voice_id="alloy",
            model="gpt-4o-mini",
            temperature=0.7,
            welcome_message="Hello! Welcome to Polaris Built. How can I assist you?",
            can_transfer_to=["skincare_vip", "auto_advisor", "finance"]
        )
        
        enterprise_config = BusinessConfig(
            business_id="polaris",
            name="Polaris Built Inc.",
            vertical=BusinessVertical.ENTERPRISE,
            primary_agent=enterprise_agent,
            phone_numbers=[
                os.environ.get("POLARIS_PHONE", "+14165559999")
            ]
        )
        
        # Register all businesses
        for config in [reroots_config, tj_auto_config, finance_config, enterprise_config]:
            self.register_business(config)
    
    def register_business(self, config: BusinessConfig):
        """Register a business configuration."""
        self._businesses[config.business_id] = config
        
        # Map phone numbers to business
        for phone in config.phone_numbers:
            normalized = self._normalize_phone(phone)
            self._phone_to_business[normalized] = config.business_id
        
        # Map agents to business
        self._agent_to_business[config.primary_agent.agent_id] = config.business_id
        for agent in config.secondary_agents:
            self._agent_to_business[agent.agent_id] = config.business_id
        
        logger.info(f"[Mapping] Registered business: {config.business_id} with agent {config.primary_agent.name}")
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number for lookup."""
        return "".join(c for c in phone if c.isdigit() or c == "+")
    
    def get_business(self, business_id: str) -> Optional[BusinessConfig]:
        """Get business configuration by ID."""
        return self._businesses.get(business_id)
    
    def get_business_by_phone(self, phone: str) -> Optional[BusinessConfig]:
        """Get business configuration by phone number."""
        normalized = self._normalize_phone(phone)
        business_id = self._phone_to_business.get(normalized)
        if business_id:
            return self._businesses.get(business_id)
        return None
    
    def get_business_by_agent(self, agent_id: str) -> Optional[BusinessConfig]:
        """Get business configuration by OmniDim agent ID."""
        business_id = self._agent_to_business.get(agent_id)
        if business_id:
            return self._businesses.get(business_id)
        return None
    
    def get_agent_for_business(
        self,
        business_id: str,
        customer_tier: str = "standard",
        intent: Optional[str] = None
    ) -> Optional[AgentConfig]:
        """
        Get the appropriate agent for a business context.
        
        Selection logic:
        1. VIP customers get premium agents
        2. Specific intents may route to specialized agents
        3. Default to primary agent
        """
        config = self._businesses.get(business_id)
        if not config:
            # Fall back to enterprise
            config = self._businesses.get("polaris")
        
        if not config:
            return None
        
        # VIP customers get primary (premium) agent
        if customer_tier == "vip":
            return config.primary_agent
        
        # Check for intent-specific routing
        if intent:
            intent_lower = intent.lower()
            
            # Finance intents go to finance agent
            if any(w in intent_lower for w in ["payment", "invoice", "billing", "price"]):
                finance_config = self._businesses.get("finance")
                if finance_config:
                    return finance_config.primary_agent
            
            # Support intents may have dedicated agent
            if any(w in intent_lower for w in ["support", "help", "issue", "problem"]):
                for agent in config.secondary_agents:
                    if agent.persona == AgentPersona.SUPPORT:
                        return agent
        
        # Default: primary agent for standard, secondary for others
        if customer_tier == "standard" and config.secondary_agents:
            return config.secondary_agents[0]
        
        return config.primary_agent
    
    def list_businesses(self) -> List[Dict[str, Any]]:
        """List all registered businesses."""
        return [
            {
                "business_id": config.business_id,
                "name": config.name,
                "vertical": config.vertical.value,
                "primary_agent": config.primary_agent.name,
                "phone_numbers": config.phone_numbers
            }
            for config in self._businesses.values()
        ]


# ==================== MAPPING SERVICE ====================

class BusinessMappingService:
    """
    The Traffic Controller Service.
    
    Orchestrates agent selection and metadata hydration
    for OmniDimension calls.
    """
    
    def __init__(self, db=None):
        self.db = db
        self.lookup_table = AgentLookupTable()
    
    async def resolve_agent_for_call(
        self,
        business_id: Optional[str] = None,
        phone_number: Optional[str] = None,
        customer_id: Optional[str] = None,
        intent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resolve the correct OmniDim agent for an outbound call.
        
        Resolution order:
        1. Explicit business_id
        2. Phone number lookup
        3. Customer's associated business
        4. Default to enterprise
        
        Returns agent config with hydration metadata.
        """
        business_config = None
        customer_tier = "standard"
        
        # Resolution chain
        if business_id:
            business_config = self.lookup_table.get_business(business_id)
        
        if not business_config and phone_number:
            business_config = self.lookup_table.get_business_by_phone(phone_number)
        
        if not business_config and customer_id and self.db:
            # Look up customer's associated business
            customer = await self.db["customers"].find_one(
                {"customer_id": customer_id},
                {"_id": 0, "business_id": 1, "tier": 1}
            )
            if customer:
                business_config = self.lookup_table.get_business(
                    customer.get("business_id", "polaris")
                )
                customer_tier = customer.get("tier", "standard")
        
        # Fallback to enterprise
        if not business_config:
            business_config = self.lookup_table.get_business("polaris")
        
        if not business_config:
            return {"error": "No business configuration found", "success": False}
        
        # Get appropriate agent
        agent = self.lookup_table.get_agent_for_business(
            business_config.business_id,
            customer_tier=customer_tier,
            intent=intent
        )
        
        if not agent:
            return {"error": "No agent configuration found", "success": False}
        
        # Build hydration metadata
        metadata = {
            "business_id": business_config.business_id,
            "business_name": business_config.name,
            "vertical": business_config.vertical.value,
            "unified_inbox_channel": business_config.unified_inbox_channel,
            "customer_tier": customer_tier,
            "resolved_at": datetime.now(timezone.utc).isoformat()
        }
        
        return {
            "success": True,
            "agent_id": agent.agent_id,
            "agent_name": agent.name,
            "agent_persona": agent.persona.value,
            "agent_config": agent.to_dict(),
            "business": {
                "id": business_config.business_id,
                "name": business_config.name,
                "vertical": business_config.vertical.value
            },
            "hydration_metadata": metadata
        }
    
    async def route_callback_to_inbox(
        self,
        agent_id: str,
        call_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Route a post-call webhook to the correct Unified Inbox.
        
        Uses agent_id to determine business, then routes
        transcript and summary to the appropriate dashboard.
        """
        # Get business from agent
        business_config = self.lookup_table.get_business_by_agent(agent_id)
        
        # Check call_context for business_id override
        call_context = call_data.get("call_context") or {}
        if call_context.get("business_id"):
            override_config = self.lookup_table.get_business(call_context["business_id"])
            if override_config:
                business_config = override_config
        
        if not business_config:
            # Default to enterprise
            business_config = self.lookup_table.get_business("polaris")
        
        if not business_config:
            return {
                "routed": False,
                "error": "Could not determine business for routing"
            }
        
        # Build inbox entry
        inbox_entry = {
            "type": "voice_call",
            "source": "omnidim",
            "business_id": business_config.business_id,
            "channel": business_config.unified_inbox_channel,
            "call_id": call_data.get("call_id"),
            "customer_phone": call_data.get("to_number"),
            "summary": call_data.get("summary"),
            "transcript": call_data.get("transcript"),
            "sentiment": call_data.get("sentiment"),
            "sentiment_score": call_data.get("sentiment_score"),
            "duration": call_data.get("duration"),
            "agent_id": agent_id,
            "agent_name": self._get_agent_name(agent_id),
            "status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Store in database
        if self.db is not None:
            try:
                await self.db["unified_inbox"].insert_one(inbox_entry.copy())
                logger.info(
                    f"[Mapping] Routed call {call_data.get('call_id')} "
                    f"to inbox:{business_config.business_id}"
                )
            except Exception as e:
                logger.error(f"[Mapping] Failed to store inbox entry: {e}")
        
        return {
            "routed": True,
            "business_id": business_config.business_id,
            "business_name": business_config.name,
            "inbox_channel": business_config.unified_inbox_channel,
            "inbox_entry_id": inbox_entry.get("call_id")
        }
    
    def _get_agent_name(self, agent_id: str) -> str:
        """Get agent name from ID."""
        business = self.lookup_table.get_business_by_agent(agent_id)
        if business:
            if business.primary_agent.agent_id == agent_id:
                return business.primary_agent.name
            for agent in business.secondary_agents:
                if agent.agent_id == agent_id:
                    return agent.name
        return "Unknown Agent"
    
    def get_unified_inbox_channel(self, business_id: str) -> str:
        """Get the Unified Inbox WebSocket channel for a business."""
        config = self.lookup_table.get_business(business_id)
        if config:
            return config.unified_inbox_channel
        return "inbox:default"
    
    async def add_business(
        self,
        business_id: str,
        name: str,
        vertical: str,
        agent_id: str,
        agent_name: str,
        phone_numbers: List[str] = None
    ) -> Dict[str, Any]:
        """
        Dynamically add a new business to AUREM.
        
        This enables rapid onboarding: "Add new business in minutes."
        """
        try:
            vertical_enum = BusinessVertical(vertical.lower())
        except ValueError:
            vertical_enum = BusinessVertical.ENTERPRISE
        
        agent_config = AgentConfig(
            agent_id=agent_id,
            persona=AgentPersona.DEFAULT,
            name=agent_name,
            description=f"AI assistant for {name}"
        )
        
        business_config = BusinessConfig(
            business_id=business_id,
            name=name,
            vertical=vertical_enum,
            primary_agent=agent_config,
            phone_numbers=phone_numbers or []
        )
        
        self.lookup_table.register_business(business_config)
        
        # Persist to database
        if self.db is not None:
            await self.db["aurem_businesses"].update_one(
                {"business_id": business_id},
                {"$set": {
                    "business_id": business_id,
                    "name": name,
                    "vertical": vertical,
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "phone_numbers": phone_numbers or [],
                    "created_at": datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
        
        return {
            "success": True,
            "business_id": business_id,
            "message": f"Business '{name}' added to AUREM Traffic Controller"
        }


# ==================== SINGLETON ====================

_mapping_service: Optional[BusinessMappingService] = None


def get_mapping_service(db=None) -> BusinessMappingService:
    """Get or create the Business Mapping Service singleton."""
    global _mapping_service
    if _mapping_service is None:
        _mapping_service = BusinessMappingService(db)
    elif db is not None and _mapping_service.db is None:
        _mapping_service.db = db
    return _mapping_service


def set_mapping_db(db):
    """Set database for the mapping service."""
    service = get_mapping_service(db)
    service.db = db
