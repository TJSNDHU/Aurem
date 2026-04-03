"""
AUREM Skills Library
Reusable workflows for AUREM development
Inspired by ECC's 156 skills system
"""

from typing import Dict, Any, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class BaseSkill:
    """
    Base class for all AUREM skills
    
    Skills are reusable workflows that can be:
    - Invoked by agents
    - Called via API
    - Triggered by hooks
    - Used by developers
    """
    
    def __init__(self, name: str, description: str, category: str):
        self.name = name
        self.description = description
        self.category = category
        self.execution_count = 0
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute skill workflow
        
        Args:
            context: Skill-specific parameters
        
        Returns:
            Result with success status and output
        """
        raise NotImplementedError
    
    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper with tracking"""
        start_time = datetime.now(timezone.utc)
        self.execution_count += 1
        
        try:
            result = await self.execute(context)
            
            end_time = datetime.now(timezone.utc)
            execution_time = (end_time - start_time).total_seconds()
            
            result["execution_time"] = execution_time
            result["skill"] = self.name
            result["category"] = self.category
            result["timestamp"] = end_time.isoformat()
            
            logger.info(f"[Skill:{self.name}] Executed in {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"[Skill:{self.name}] Error: {e}")
            return {
                "success": False,
                "error": str(e),
                "skill": self.name,
                "category": self.category
            }
    
    def get_info(self) -> Dict[str, Any]:
        """Get skill information"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "executions": self.execution_count
        }
