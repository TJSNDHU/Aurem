"""
AUREM Multi-Business Agent System
Supports multiple businesses with dedicated agent configurations
"""

import os
import uuid
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# BUSINESS DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

class BusinessType(str, Enum):
    """Supported business types"""
    SKINCARE = "skincare"
    AUTOMOTIVE = "automotive"
    ECOMMERCE = "ecommerce"
    SAAS = "saas"
    AGENCY = "agency"
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    RETAIL = "retail"
    CUSTOM = "custom"


class BusinessConfig(BaseModel):
    """Configuration for a business"""
    business_id: str
    name: str
    type: BusinessType
    description: str = ""
    industry_keywords: List[str] = []
    tone: str = "professional"  # professional, friendly, casual, formal
    target_audience: str = ""
    products_services: List[str] = []
    unique_selling_points: List[str] = []
    competitors: List[str] = []
    knowledge_base_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True


# Pre-configured businesses
BUSINESSES: Dict[str, BusinessConfig] = {
    "ABC-001": BusinessConfig(
        business_id="ABC-001",
        name="ABC Skincare",
        type=BusinessType.SKINCARE,
        description="Premium biotech skincare brand specializing in PDRN technology",
        industry_keywords=["skincare", "beauty", "PDRN", "biotech", "anti-aging", "serum", "cream"],
        tone="professional",
        target_audience="Health-conscious consumers aged 25-55 seeking premium skincare",
        products_services=["PDRN Serums", "Anti-aging Creams", "Bio-Scan Analysis", "Skincare Consultation"],
        unique_selling_points=["PDRN Technology", "Made in Canada", "Cruelty-Free", "Biotech Innovation"],
        competitors=["SkinCeuticals", "La Mer", "Drunk Elephant"]
    ),
    "ABC-002": BusinessConfig(
        business_id="ABC-002",
        name="ABC Auto",
        type=BusinessType.AUTOMOTIVE,
        description="Premium automotive repair and maintenance services",
        industry_keywords=["auto repair", "car service", "mechanic", "oil change", "brake service", "tire"],
        tone="friendly",
        target_audience="Vehicle owners seeking reliable, honest auto repair services",
        products_services=["Oil Changes", "Brake Service", "Tire Service", "Engine Diagnostics", "AC Repair"],
        unique_selling_points=["Certified Technicians", "Transparent Pricing", "Same-Day Service", "Warranty"],
        competitors=["Jiffy Lube", "Midas", "Pep Boys"]
    ),
    "ABC-003": BusinessConfig(
        business_id="ABC-003",
        name="ABC Tech",
        type=BusinessType.SAAS,
        description="AI-powered business automation platform",
        industry_keywords=["AI", "automation", "SaaS", "business intelligence", "CRM", "workflow"],
        tone="professional",
        target_audience="SMBs and enterprises looking to automate operations",
        products_services=["AI Automation", "CRM Integration", "Analytics Dashboard", "Multi-Agent System"],
        unique_selling_points=["OODA Loop AI", "Multi-Agent Architecture", "Real-time Analytics"],
        competitors=["Salesforce", "HubSpot", "Zapier"]
    )
}


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

class AgentRole(str, Enum):
    """Agent roles in OODA loop"""
    SCOUT = "scout"       # OBSERVE
    ARCHITECT = "architect"  # ORIENT
    ENVOY = "envoy"       # DECIDE
    CLOSER = "closer"     # ACT
    ORCHESTRATOR = "orchestrator"  # COORDINATE


class AgentConfig(BaseModel):
    """Configuration for an AI agent"""
    agent_id: str
    name: str
    role: AgentRole
    business_id: str
    description: str = ""
    capabilities: List[str] = []
    system_prompt: str = ""
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 2000
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Agent templates by role
AGENT_TEMPLATES: Dict[AgentRole, Dict[str, Any]] = {
    AgentRole.SCOUT: {
        "name_prefix": "XYZ Scout",
        "description": "Observes and gathers market intelligence, identifies leads and opportunities",
        "capabilities": ["web_scraping", "market_research", "competitor_analysis", "lead_discovery", "trend_detection"],
        "system_prompt_template": """You are {agent_name}, a Scout Agent for {business_name}.

Your role is OBSERVE in the OODA loop. You:
- Scan the market for opportunities and leads
- Monitor competitor activities
- Identify trends relevant to {business_type}
- Gather intelligence about potential customers
- Track industry news and developments

Business Context:
{business_description}

Target Audience: {target_audience}

Key Products/Services: {products_services}

Always provide actionable intelligence that can be used by the Architect and Envoy agents."""
    },
    AgentRole.ARCHITECT: {
        "name_prefix": "XYZ Architect",
        "description": "Designs strategies and automation pipelines based on Scout intelligence",
        "capabilities": ["automation_design", "workflow_creation", "llm_routing", "strategy_planning", "pipeline_building"],
        "system_prompt_template": """You are {agent_name}, an Architect Agent for {business_name}.

Your role is ORIENT in the OODA loop. You:
- Design automation strategies based on Scout intelligence
- Build workflow pipelines for customer engagement
- Create response templates optimized for {business_type}
- Route requests to appropriate channels
- Optimize conversion funnels

Business Context:
{business_description}

USPs: {unique_selling_points}

Create strategies that leverage our unique advantages while addressing customer needs."""
    },
    AgentRole.ENVOY: {
        "name_prefix": "XYZ Envoy",
        "description": "Makes decisions on lead routing, prioritization, and engagement strategies",
        "capabilities": ["intent_classification", "lead_scoring", "decision_routing", "priority_ranking", "sentiment_analysis"],
        "system_prompt_template": """You are {agent_name}, an Envoy Agent for {business_name}.

Your role is DECIDE in the OODA loop. You:
- Classify customer intents and needs
- Score and prioritize leads
- Decide optimal engagement channels (email, WhatsApp, voice, chat)
- Route conversations to appropriate responses
- Determine urgency and escalation needs

Business Context:
{business_description}

Products/Services: {products_services}

Make decisions that maximize conversion while providing excellent customer experience."""
    },
    AgentRole.CLOSER: {
        "name_prefix": "XYZ Closer",
        "description": "Executes outreach and closes deals via voice, email, WhatsApp",
        "capabilities": ["voice_calls", "whatsapp_messaging", "email_outreach", "deal_closing", "appointment_booking"],
        "system_prompt_template": """You are {agent_name}, a Closer Agent for {business_name}.

Your role is ACT in the OODA loop. You:
- Execute outreach campaigns via voice, email, WhatsApp
- Handle customer conversations professionally
- Book appointments and consultations
- Close sales and process orders
- Follow up with prospects

Business Context:
{business_description}

Tone: {tone}
Target Audience: {target_audience}

Communicate in a {tone} manner while driving conversions. Always represent {business_name} professionally."""
    },
    AgentRole.ORCHESTRATOR: {
        "name_prefix": "XYZ Orchestrator",
        "description": "Coordinates all agents and manages the overall OODA cycle",
        "capabilities": ["agent_coordination", "task_distribution", "system_monitoring", "error_recovery", "performance_optimization"],
        "system_prompt_template": """You are {agent_name}, the Orchestrator for {business_name}.

Your role is to COORDINATE the entire OODA loop:
- Monitor and coordinate Scout, Architect, Envoy, and Closer agents
- Distribute tasks based on priority and agent availability
- Ensure smooth handoffs between agents
- Monitor system health and performance
- Handle errors and edge cases

Business: {business_name}
Type: {business_type}

Ensure all agents work in harmony to achieve business goals."""
    }
}


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class AgentManager:
    """Manages multi-business agent configurations"""
    
    def __init__(self, db=None):
        self.db = db
        self.businesses = BUSINESSES.copy()
        self.agents: Dict[str, AgentConfig] = {}
        self._initialize_default_agents()
    
    def _initialize_default_agents(self):
        """Create default agents for each business"""
        for business_id, business in self.businesses.items():
            for role in AgentRole:
                agent = self._create_agent_for_business(business, role)
                self.agents[agent.agent_id] = agent
    
    def _create_agent_for_business(self, business: BusinessConfig, role: AgentRole) -> AgentConfig:
        """Create an agent for a specific business and role"""
        template = AGENT_TEMPLATES[role]
        
        agent_id = f"{business.business_id}-{role.value.upper()}"
        agent_name = f"{template['name_prefix']} ({business.name})"
        
        # Build system prompt from template
        system_prompt = template["system_prompt_template"].format(
            agent_name=agent_name,
            business_name=business.name,
            business_type=business.type.value,
            business_description=business.description,
            target_audience=business.target_audience,
            products_services=", ".join(business.products_services),
            unique_selling_points=", ".join(business.unique_selling_points),
            tone=business.tone
        )
        
        return AgentConfig(
            agent_id=agent_id,
            name=agent_name,
            role=role,
            business_id=business.business_id,
            description=template["description"],
            capabilities=template["capabilities"],
            system_prompt=system_prompt
        )
    
    def get_business(self, business_id: str) -> Optional[BusinessConfig]:
        """Get business configuration"""
        return self.businesses.get(business_id)
    
    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        """Get agent configuration"""
        return self.agents.get(agent_id)
    
    def get_agents_for_business(self, business_id: str) -> List[AgentConfig]:
        """Get all agents for a business"""
        return [a for a in self.agents.values() if a.business_id == business_id]
    
    def get_agent_by_role(self, business_id: str, role: AgentRole) -> Optional[AgentConfig]:
        """Get specific agent by business and role"""
        agent_id = f"{business_id}-{role.value.upper()}"
        return self.agents.get(agent_id)
    
    def add_business(self, config: BusinessConfig) -> BusinessConfig:
        """Add a new business"""
        self.businesses[config.business_id] = config
        
        # Create agents for the business
        for role in AgentRole:
            agent = self._create_agent_for_business(config, role)
            self.agents[agent.agent_id] = agent
        
        return config
    
    def update_business(self, business_id: str, updates: Dict[str, Any]) -> Optional[BusinessConfig]:
        """Update business configuration"""
        if business_id not in self.businesses:
            return None
        
        business = self.businesses[business_id]
        for key, value in updates.items():
            if hasattr(business, key):
                setattr(business, key, value)
        
        # Regenerate agent prompts with updated business info
        for role in AgentRole:
            agent = self._create_agent_for_business(business, role)
            self.agents[agent.agent_id] = agent
        
        return business
    
    def list_businesses(self) -> List[BusinessConfig]:
        """List all businesses"""
        return list(self.businesses.values())
    
    def list_agents(self, business_id: str = None) -> List[AgentConfig]:
        """List agents, optionally filtered by business"""
        if business_id:
            return self.get_agents_for_business(business_id)
        return list(self.agents.values())
    
    async def save_to_db(self):
        """Persist configurations to database"""
        if not self.db:
            return
        
        # Save businesses
        for business in self.businesses.values():
            await self.db.aurem_businesses.update_one(
                {"business_id": business.business_id},
                {"$set": business.dict()},
                upsert=True
            )
        
        # Save agents
        for agent in self.agents.values():
            await self.db.aurem_agents.update_one(
                {"agent_id": agent.agent_id},
                {"$set": agent.dict()},
                upsert=True
            )
    
    async def load_from_db(self):
        """Load configurations from database"""
        if not self.db:
            return
        
        # Load businesses
        async for doc in self.db.aurem_businesses.find({"is_active": True}):
            doc.pop("_id", None)
            business = BusinessConfig(**doc)
            self.businesses[business.business_id] = business
        
        # Load agents
        async for doc in self.db.aurem_agents.find({"is_active": True}):
            doc.pop("_id", None)
            agent = AgentConfig(**doc)
            self.agents[agent.agent_id] = agent


# ═══════════════════════════════════════════════════════════════════════════════
# BUSINESS-AWARE AI SERVICE
# ═══════════════════════════════════════════════════════════════════════════════

class BusinessAwareAI:
    """AI service that adapts to different businesses"""
    
    def __init__(self, db=None):
        self.db = db
        self.manager = AgentManager(db)
        self.api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    
    async def chat_with_context(
        self, 
        message: str, 
        business_id: str,
        agent_role: AgentRole = None,
        session_id: str = None
    ) -> Dict[str, Any]:
        """Chat with business-specific context"""
        from services.aurem_ai_service import get_aurem_service
        
        business = self.manager.get_business(business_id)
        if not business:
            return {"error": f"Business {business_id} not found"}
        
        # Get appropriate agent
        if agent_role:
            agent = self.manager.get_agent_by_role(business_id, agent_role)
        else:
            # Default to Envoy for general chat
            agent = self.manager.get_agent_by_role(business_id, AgentRole.ENVOY)
        
        if not agent:
            return {"error": "No agent available"}
        
        # Use the agent's system prompt
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            chat = LlmChat(
                api_key=self.api_key,
                session_id=session_id or str(uuid.uuid4()),
                system_message=agent.system_prompt
            ).with_model("openai", agent.model)
            
            response = await chat.send_message(UserMessage(text=message))
            
            return {
                "response": response,
                "business_id": business_id,
                "business_name": business.name,
                "agent_id": agent.agent_id,
                "agent_name": agent.name,
                "agent_role": agent.role.value,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Business chat error: {e}")
            return {
                "response": f"I'm {agent.name} for {business.name}. How can I assist you today?",
                "error": str(e),
                "business_id": business_id,
                "agent_id": agent.agent_id
            }
    
    def get_business_summary(self, business_id: str) -> Dict[str, Any]:
        """Get summary of business and its agents"""
        business = self.manager.get_business(business_id)
        if not business:
            return {"error": "Business not found"}
        
        agents = self.manager.get_agents_for_business(business_id)
        
        return {
            "business": business.dict(),
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "name": a.name,
                    "role": a.role.value,
                    "capabilities": a.capabilities,
                    "is_active": a.is_active
                }
                for a in agents
            ],
            "agent_count": len(agents)
        }


# Singleton instance
_agent_manager = None
_business_ai = None

def get_agent_manager(db=None) -> AgentManager:
    global _agent_manager
    if _agent_manager is None:
        _agent_manager = AgentManager(db)
    elif db and _agent_manager.db is None:
        _agent_manager.db = db
    return _agent_manager

def get_business_ai(db=None) -> BusinessAwareAI:
    global _business_ai
    if _business_ai is None:
        _business_ai = BusinessAwareAI(db)
    elif db and _business_ai.db is None:
        _business_ai.db = db
    return _business_ai
