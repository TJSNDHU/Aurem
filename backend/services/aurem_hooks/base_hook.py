"""
AUREM Hooks System
Event-driven automation workflows
Inspired by ECC's hooks architecture
"""

from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timezone
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class HookResult:
    """Result from hook execution"""
    
    def __init__(
        self,
        success: bool,
        message: str = "",
        data: Optional[Dict[str, Any]] = None,
        should_proceed: bool = True,
        warnings: Optional[List[str]] = None
    ):
        self.success = success
        self.message = message
        self.data = data or {}
        self.should_proceed = should_proceed  # Can block action if False
        self.warnings = warnings or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "should_proceed": self.should_proceed,
            "warnings": self.warnings
        }


class BaseHook(ABC):
    """
    Base class for all hooks
    
    Hooks are event-driven workflows that run automatically:
    - Pre hooks: Run before an action (can block if needed)
    - Post hooks: Run after an action (for logging, notifications)
    """
    
    def __init__(self, name: str, description: str, hook_type: str):
        self.name = name
        self.description = description
        self.hook_type = hook_type  # "pre" or "post"
        self.enabled = True
        self.execution_count = 0
        self.last_execution = None
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> HookResult:
        """
        Execute hook
        
        Args:
            context: Event context (file path, API endpoint, etc.)
        
        Returns:
            HookResult with success status and optional blocking
        """
        pass
    
    async def run(self, context: Dict[str, Any]) -> HookResult:
        """Run hook with tracking"""
        if not self.enabled:
            return HookResult(
                success=True,
                message=f"Hook {self.name} is disabled",
                should_proceed=True
            )
        
        start_time = datetime.now(timezone.utc)
        self.execution_count += 1
        
        try:
            result = await self.execute(context)
            
            self.last_execution = datetime.now(timezone.utc)
            execution_time = (self.last_execution - start_time).total_seconds()
            
            logger.info(
                f"[Hook:{self.name}] Executed in {execution_time:.2f}s | "
                f"Proceed: {result.should_proceed}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"[Hook:{self.name}] Error: {e}")
            
            # On error, allow proceeding by default (fail-safe)
            return HookResult(
                success=False,
                message=f"Hook execution failed: {str(e)}",
                should_proceed=True,
                warnings=[str(e)]
            )
    
    def enable(self):
        """Enable hook"""
        self.enabled = True
        logger.info(f"[Hook:{self.name}] Enabled")
    
    def disable(self):
        """Disable hook"""
        self.enabled = False
        logger.info(f"[Hook:{self.name}] Disabled")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get hook statistics"""
        return {
            "name": self.name,
            "description": self.description,
            "type": self.hook_type,
            "enabled": self.enabled,
            "executions": self.execution_count,
            "last_execution": self.last_execution.isoformat() if self.last_execution else None
        }
