"""
AUREM Agent Harness
Central coordinator for all AUREM agents
Inspired by ECC's agent orchestration system
"""

from typing import Dict, Any, Optional
import logging

from .build_fixer import AUREMBuildFixer

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
            # Future agents will be added here:
            # "code-reviewer": AUREMCodeReviewer(),
            # "security-scanner": AUREMSecurityScanner(),
            # "planner": AUREMFeaturePlanner(),
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
        
        # Simple pattern matching for now
        # In future, use LLM to classify problem type
        
        if any(keyword in problem for keyword in ["404", "import error", "build error", "cannot import"]):
            return await self.delegate("build-fixer", context)
        
        # Add more patterns as agents are implemented
        # elif "security" in problem or "vulnerability" in problem:
        #     return await self.delegate("security-scanner", context)
        # elif "test" in problem or "tdd" in problem:
        #     return await self.delegate("tdd-guide", context)
        
        return {
            "success": False,
            "message": "Could not auto-detect appropriate agent",
            "suggestion": "Please specify agent_name explicitly"
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
