"""
PostAPICall Hook
Runs after API calls - logs usage, tracks analytics
"""

from typing import Dict, Any
import logging
from datetime import datetime, timezone

from .base_hook import BaseHook, HookResult

logger = logging.getLogger(__name__)


class PostAPICallHook(BaseHook):
    """
    Post-API-call hook
    
    Actions:
    - Log API usage
    - Track analytics
    - Auto-index in vector DB (if connector call)
    - Monitor rate limits
    """
    
    def __init__(self):
        super().__init__(
            name="post-api-call",
            description="Logs and tracks API usage after calls",
            hook_type="post"
        )
    
    async def execute(self, context: Dict[str, Any]) -> HookResult:
        """
        Execute post-API-call actions
        
        Context:
        {
            "endpoint": "/api/connectors/fetch",
            "platform": "reddit",
            "success": true,
            "results_count": 10,
            "execution_time": 1.5
        }
        """
        endpoint = context.get("endpoint", "")
        platform = context.get("platform", "")
        success = context.get("success", False)
        results_count = context.get("results_count", 0)
        execution_time = context.get("execution_time", 0)
        
        actions_taken = []
        
        # Log usage
        usage_log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "platform": platform,
            "success": success,
            "results": results_count,
            "time": execution_time
        }
        
        logger.info(f"[PostAPICall] Usage: {usage_log}")
        actions_taken.append("✅ API usage logged")
        
        # Track in analytics (simplified)
        if success and results_count > 0:
            actions_taken.append(f"📊 Analytics: {results_count} results from {platform}")
        
        return HookResult(
            success=True,
            message=f"Post-API actions completed for {endpoint}",
            should_proceed=True,
            data={
                "endpoint": endpoint,
                "platform": platform,
                "actions_taken": actions_taken,
                "usage_logged": True
            }
        )
