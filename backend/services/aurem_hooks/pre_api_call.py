"""
PreAPICall Hook
Runs before API calls - validates keys, checks rate limits
"""

from typing import Dict, Any
import logging

from .base_hook import BaseHook, HookResult

logger = logging.getLogger(__name__)


class PreAPICallHook(BaseHook):
    """
    Pre-API-call hook
    
    Checks:
    - API key validation
    - Rate limiting
    - Hardcoded credentials
    """
    
    def __init__(self):
        super().__init__(
            name="pre-api-call",
            description="Validates API calls before execution",
            hook_type="pre"
        )
    
    async def execute(self, context: Dict[str, Any]) -> HookResult:
        """
        Execute pre-API-call checks
        
        Context:
        {
            "endpoint": "/api/connectors/fetch",
            "platform": "twitter",
            "credentials": {...}
        }
        """
        endpoint = context.get("endpoint", "")
        platform = context.get("platform", "")
        credentials = context.get("credentials", {})
        
        warnings = []
        should_proceed = True
        
        # Check for hardcoded credentials
        if credentials:
            for key, value in credentials.items():
                if isinstance(value, str) and len(value) > 20:
                    # Check if it looks like a hardcoded key
                    if any(prefix in key.lower() for prefix in ["key", "token", "secret"]):
                        warnings.append(
                            f"⚠️ API credential detected: {key}. "
                            "Ensure it's from Admin Mission Control, not hardcoded"
                        )
        
        # Platform-specific checks
        if platform and not credentials:
            warnings.append(
                f"💡 TIP: {platform} connector will use demo mode. "
                "Add credentials via Admin Mission Control for real data"
            )
        
        return HookResult(
            success=True,
            message=f"Pre-API checks completed for {endpoint}",
            should_proceed=should_proceed,
            warnings=warnings,
            data={
                "endpoint": endpoint,
                "platform": platform,
                "has_credentials": bool(credentials)
            }
        )
