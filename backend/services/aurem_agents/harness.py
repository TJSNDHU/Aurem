"""
AUREM Agent Harness
Central coordinator for all AUREM agents
Inspired by ECC's agent orchestration system
"""

from typing import Dict, Any, Optional
import logging

from .build_fixer import AUREMBuildFixer
from .code_reviewer import AUREMCodeReviewer
from .security_scanner import AUREMSecurityScanner
from .feature_planner import AUREMFeaturePlanner

logger = logging.getLogger(__name__)


class AUREMAgentHarness:
    """
    Central agent coordinator for AUREM
    
    Manages:
    - Agent registration
    - Task delegation
    - Agent execution tracking
    - Statistics & monitoring
    """
    
    def __init__(self):
        self.agents = {
            "build-fixer": AUREMBuildFixer(),
            "code-reviewer": AUREMCodeReviewer(),
            "security-scanner": AUREMSecurityScanner(),
            "planner": AUREMFeaturePlanner(),
            # Future agents:
            # "tdd-guide": AUREMTDDGuide(),
            # "mongo-optimizer": AUREMMongoOptimizer(),
            # "refactor-agent": AUREMRefactorAgent(),
            # "doc-sync": AUREMDocSync(),
            # "e2e-runner": AUREME2ERunner(),
            # "architect": AUREMArchitect()
        }
        
        logger.info(f"[AgentHarness] Initialized with {len(self.agents)} agents")
    
    async def delegate(self, agent_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delegate task to specific agent
        
        Args:
            agent_name: Agent identifier (e.g., "build-fixer")
            context: Task context/parameters
        
        Returns:
            Agent execution result
        """
        agent = self.agents.get(agent_name)
        
        if not agent:
            available_agents = list(self.agents.keys())
            return {
                "success": False,
                "error": f"Unknown agent: {agent_name}",
                "available_agents": available_agents
            }
        
        logger.info(f"[AgentHarness] Delegating to {agent_name}")
        
        result = await agent.run(context)
        
        return result
    
    async def auto_detect(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Automatically detect which agent to use based on context
        
        Args:
            context: Problem description
        
        Returns:
            Agent execution result
        """
        problem = context.get("problem", "").lower()
        feature_description = context.get("feature_description", "").lower()
        
        # Simple pattern matching for now
        # In future, use LLM to classify problem type
        
        # Build errors
        if any(keyword in problem for keyword in ["404", "import error", "build error", "cannot import", "module not found"]):
            return await self.delegate("build-fixer", context)
        
        # Security scans
        elif any(keyword in problem for keyword in ["security", "vulnerability", "owasp", "audit", "penetration"]):
            return await self.delegate("security-scanner", context)
        
        # Code review
        elif any(keyword in problem for keyword in ["review", "code quality", "refactor", "improve code"]):
            return await self.delegate("code-reviewer", context)
        
        # Feature planning
        elif any(keyword in feature_description for keyword in ["plan", "design", "architect", "new feature"]) or \
             "feature_description" in context:
            return await self.delegate("planner", context)
        
        # Add more patterns as agents are implemented
        # elif "test" in problem or "tdd" in problem:
        #     return await self.delegate("tdd-guide", context)
        # elif "mongo" in problem or "database" in problem:
        #     return await self.delegate("mongo-optimizer", context)
        
        return {
            "success": False,
            "message": "Could not auto-detect appropriate agent",
            "suggestion": "Please specify agent_name explicitly",
            "available_agents": list(self.agents.keys())
        }
    
    def list_agents(self) -> Dict[str, Any]:
        """List all available agents with stats"""
        agents_info = []
        
        for name, agent in self.agents.items():
            agents_info.append(agent.get_stats())
        
        return {
            "total_agents": len(self.agents),
            "agents": agents_info
        }
    
    def get_agent_stats(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get statistics for specific agent"""
        agent = self.agents.get(agent_name)
        
        if not agent:
            return None
        
        return agent.get_stats()


# Global harness instance
_harness = AUREMAgentHarness()


def get_agent_harness() -> AUREMAgentHarness:
    """Get global agent harness instance"""
    return _harness
