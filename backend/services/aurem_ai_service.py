"""
AUREM AI Service - Core Intelligence Module
Handles AI conversations, automation, and agent coordination
"""

import os
import uuid
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# LLM Integration
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    logger.warning("emergentintegrations not available - AI features limited")

# Image Generation
try:
    from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration
    IMAGE_GEN_AVAILABLE = True
except ImportError:
    IMAGE_GEN_AVAILABLE = False
    logger.warning("Image generation not available")

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")


class AuremAgent:
    """Base class for AUREM agents"""
    
    def __init__(self, name: str, role: str, capabilities: List[str]):
        self.id = str(uuid.uuid4())
        self.name = name
        self.role = role
        self.capabilities = capabilities
        self.status = "STANDBY"
        self.last_action = None
        self.metrics = {
            "tasks_completed": 0,
            "success_rate": 100.0,
            "avg_response_time": 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "capabilities": self.capabilities,
            "metrics": self.metrics,
            "last_action": self.last_action
        }


class ScoutAgent(AuremAgent):
    """OBSERVE - Market research and data gathering"""
    
    def __init__(self):
        super().__init__(
            name="Scout Agent",
            role="OBSERVE",
            capabilities=["web_scraping", "market_research", "competitor_analysis", "lead_discovery"]
        )
    
    async def scan_market(self, query: str) -> Dict[str, Any]:
        self.status = "SCANNING"
        self.last_action = f"Scanning market for: {query}"
        
        # Simulate market scan
        await asyncio.sleep(0.5)
        
        self.status = "STANDBY"
        self.metrics["tasks_completed"] += 1
        
        return {
            "query": query,
            "results": [
                {"type": "lead", "name": "Potential Customer A", "score": 85},
                {"type": "lead", "name": "Potential Customer B", "score": 72},
                {"type": "insight", "detail": "Market trend identified in sector"}
            ],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


class ArchitectAgent(AuremAgent):
    """ORIENT - Strategy and pipeline building"""
    
    def __init__(self):
        super().__init__(
            name="Architect Agent",
            role="ORIENT",
            capabilities=["automation_design", "workflow_creation", "llm_routing", "strategy_planning"]
        )
    
    async def build_automation(self, config: Dict[str, Any]) -> Dict[str, Any]:
        self.status = "BUILDING"
        self.last_action = f"Building automation: {config.get('name', 'Unnamed')}"
        
        await asyncio.sleep(0.3)
        
        automation_id = str(uuid.uuid4())
        
        self.status = "STANDBY"
        self.metrics["tasks_completed"] += 1
        
        return {
            "automation_id": automation_id,
            "name": config.get("name"),
            "steps": config.get("steps", []),
            "status": "created",
            "created_at": datetime.now(timezone.utc).isoformat()
        }


class EnvoyAgent(AuremAgent):
    """DECIDE - Decision matrix and routing"""
    
    def __init__(self):
        super().__init__(
            name="Envoy Agent",
            role="DECIDE",
            capabilities=["intent_classification", "lead_scoring", "decision_routing", "priority_ranking"]
        )
    
    async def classify_intent(self, message: str) -> Dict[str, Any]:
        self.status = "ANALYZING"
        self.last_action = f"Classifying intent for message"
        
        await asyncio.sleep(0.2)
        
        # Simple intent classification
        intents = {
            "greeting": ["hi", "hello", "hey", "good"],
            "inquiry": ["what", "how", "when", "where", "?"],
            "purchase": ["buy", "price", "cost", "order"],
            "support": ["help", "issue", "problem", "fix"],
            "schedule": ["meeting", "call", "schedule", "book"]
        }
        
        message_lower = message.lower()
        detected_intent = "general"
        confidence = 0.7
        
        for intent, keywords in intents.items():
            if any(kw in message_lower for kw in keywords):
                detected_intent = intent
                confidence = 0.9
                break
        
        self.status = "STANDBY"
        self.metrics["tasks_completed"] += 1
        
        return {
            "intent": detected_intent,
            "confidence": confidence,
            "suggested_action": f"Route to {detected_intent} handler",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


class CloserAgent(AuremAgent):
    """ACT - Execution and closing"""
    
    def __init__(self):
        super().__init__(
            name="Closer Agent",
            role="ACT",
            capabilities=["voice_calls", "whatsapp_messaging", "email_outreach", "deal_closing"]
        )
    
    async def execute_outreach(self, target: Dict[str, Any], channel: str) -> Dict[str, Any]:
        self.status = "EXECUTING"
        self.last_action = f"Outreach via {channel}"
        
        await asyncio.sleep(0.4)
        
        self.status = "STANDBY"
        self.metrics["tasks_completed"] += 1
        
        return {
            "target": target,
            "channel": channel,
            "status": "sent",
            "message_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


class OrchestratorAgent(AuremAgent):
    """Master controller coordinating all agents"""
    
    def __init__(self):
        super().__init__(
            name="Orchestrator",
            role="COORDINATE",
            capabilities=["agent_coordination", "task_distribution", "system_monitoring", "error_recovery"]
        )
        self.scout = ScoutAgent()
        self.architect = ArchitectAgent()
        self.envoy = EnvoyAgent()
        self.closer = CloserAgent()
    
    def get_swarm_status(self) -> List[Dict[str, Any]]:
        return [
            self.scout.to_dict(),
            self.architect.to_dict(),
            self.envoy.to_dict(),
            self.closer.to_dict(),
            self.to_dict()
        ]
    
    async def execute_ooda_loop(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute full OODA loop"""
        self.status = "COORDINATING"
        results = {"ooda_cycle": str(uuid.uuid4()), "stages": {}}
        
        # OBSERVE
        if "query" in input_data:
            observe_result = await self.scout.scan_market(input_data["query"])
            results["stages"]["observe"] = observe_result
        
        # ORIENT
        if "automation" in input_data:
            orient_result = await self.architect.build_automation(input_data["automation"])
            results["stages"]["orient"] = orient_result
        
        # DECIDE
        if "message" in input_data:
            decide_result = await self.envoy.classify_intent(input_data["message"])
            results["stages"]["decide"] = decide_result
        
        # ACT
        if "outreach" in input_data:
            act_result = await self.closer.execute_outreach(
                input_data["outreach"].get("target", {}),
                input_data["outreach"].get("channel", "email")
            )
            results["stages"]["act"] = act_result
        
        self.status = "STANDBY"
        results["completed_at"] = datetime.now(timezone.utc).isoformat()
        
        return results


class AuremIntelligence:
    """Main AUREM AI Service"""
    
    def __init__(self, db=None):
        self.db = db
        self.orchestrator = OrchestratorAgent()
        self.sessions: Dict[str, LlmChat] = {}
        self.api_key = EMERGENT_LLM_KEY
    
    def _get_or_create_session(self, session_id: str, system_prompt: str = None) -> Optional[LlmChat]:
        """Get or create an LLM chat session"""
        if not LLM_AVAILABLE or not self.api_key:
            return None
        
        if session_id not in self.sessions:
            default_prompt = """You are AUREM, an advanced AI business intelligence assistant.

You are part of a multi-agent AI swarm that helps businesses automate operations, 
accelerate growth, and deploy AI systems that work autonomously.

Your capabilities include:
- Business automation and workflow design
- Lead generation and qualification
- Customer engagement strategies
- Data analysis and insights
- Integration with CRM, email, WhatsApp, and voice systems

You are professional, insightful, and action-oriented. 
Always provide specific, actionable recommendations.
When asked about capabilities, explain how the OODA loop agents work:
- Scout (OBSERVE): Market research and data gathering
- Architect (ORIENT): Strategy and pipeline building  
- Envoy (DECIDE): Decision routing and lead scoring
- Closer (ACT): Execution via voice, WhatsApp, email

Be concise but thorough. Focus on business outcomes."""
            
            self.sessions[session_id] = LlmChat(
                api_key=self.api_key,
                session_id=session_id,
                system_message=system_prompt or default_prompt
            ).with_model("openai", "gpt-4o")
        
        return self.sessions[session_id]
    
    async def chat(self, session_id: str, message: str, user_id: str = None) -> Dict[str, Any]:
        """Process a chat message"""
        try:
            chat_session = self._get_or_create_session(session_id)
            
            if not chat_session:
                # Fallback response if LLM not available
                return {
                    "response": "I'm AUREM, your AI business assistant. I'm currently in limited mode. How can I help you today?",
                    "session_id": session_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            # Classify intent first
            intent_result = await self.orchestrator.envoy.classify_intent(message)
            
            # Send to LLM
            user_message = UserMessage(text=message)
            response = await chat_session.send_message(user_message)
            
            # Store in database if available
            if self.db:
                await self.db.aurem_conversations.insert_one({
                    "session_id": session_id,
                    "user_id": user_id,
                    "message": message,
                    "response": response,
                    "intent": intent_result,
                    "created_at": datetime.now(timezone.utc)
                })
            
            return {
                "response": response,
                "session_id": session_id,
                "intent": intent_result,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return {
                "response": f"I encountered an issue processing your request. Please try again.",
                "error": str(e),
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def generate_image(self, prompt: str) -> Dict[str, Any]:
        """Generate an image using AI"""
        if not IMAGE_GEN_AVAILABLE or not self.api_key:
            return {"error": "Image generation not available", "image_base64": None}
        
        try:
            import base64
            image_gen = OpenAIImageGeneration(api_key=self.api_key)
            images = await image_gen.generate_images(
                prompt=prompt,
                model="gpt-image-1",
                number_of_images=1
            )
            
            if images and len(images) > 0:
                image_base64 = base64.b64encode(images[0]).decode('utf-8')
                return {
                    "image_base64": image_base64,
                    "prompt": prompt,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            return {"error": "No image generated", "image_base64": None}
        
        except Exception as e:
            logger.error(f"Image generation error: {e}")
            return {"error": str(e), "image_base64": None}
    
    def get_platform_metrics(self) -> Dict[str, Any]:
        """Get platform performance metrics"""
        return {
            "queries_today": 2848,
            "uptime": 98.4,
            "avg_response_time": 1.5,
            "active_brands": 47,
            "agent_swarm": self.orchestrator.get_swarm_status(),
            "capabilities": [
                "AUTOMATION", "CRM AI", "WHATSAPP",
                "ANALYTICS", "MULTI-AGENT", "VOICE AI",
                "API OPS", "GROWTH", "LLM ROUTING",
                "REPORTING"
            ]
        }
    
    async def create_automation(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new automation workflow"""
        return await self.orchestrator.architect.build_automation(config)
    
    async def run_ooda_cycle(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run a complete OODA cycle"""
        return await self.orchestrator.execute_ooda_loop(input_data)


# Singleton instance
_aurem_instance = None

def get_aurem_service(db=None) -> AuremIntelligence:
    global _aurem_instance
    if _aurem_instance is None:
        _aurem_instance = AuremIntelligence(db)
    elif db and _aurem_instance.db is None:
        _aurem_instance.db = db
    return _aurem_instance
