"""
Base Agent Class
All AUREM agents inherit from this
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all AUREM agents
    Follows ECC agent pattern
    """
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.execution_count = 0
        self.success_count = 0
        self.failure_count = 0
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent task
        
        Args:
            context: Task context with parameters
        
        Returns:
            Result dictionary with:
            - success: bool
            - data: Any (agent-specific output)
            - message: str
            - execution_time: float
        """
        pass
    
    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wrapper around execute with tracking
        """
        start_time = datetime.now(timezone.utc)
        self.execution_count += 1
        
        try:
            result = await self.execute(context)
            
            if result.get("success"):
                self.success_count += 1
            else:
                self.failure_count += 1
            
            end_time = datetime.now(timezone.utc)
            execution_time = (end_time - start_time).total_seconds()
            
            result["execution_time"] = execution_time
            result["agent"] = self.name
            result["timestamp"] = end_time.isoformat()
            
            logger.info(
                f"[Agent:{self.name}] Executed in {execution_time:.2f}s | "
                f"Success: {result.get('success')} | "
                f"Stats: {self.success_count}✅ {self.failure_count}❌"
            )
            
            return result
            
        except Exception as e:
            self.failure_count += 1
            logger.error(f"[Agent:{self.name}] Error: {e}")
            
            return {
                "success": False,
                "agent": self.name,
                "error": str(e),
                "message": f"Agent execution failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent execution statistics"""
        success_rate = (
            (self.success_count / self.execution_count * 100)
            if self.execution_count > 0
            else 0
        )
        
        return {
            "name": self.name,
            "description": self.description,
            "executions": self.execution_count,
            "success": self.success_count,
            "failure": self.failure_count,
            "success_rate": round(success_rate, 2)
        }
