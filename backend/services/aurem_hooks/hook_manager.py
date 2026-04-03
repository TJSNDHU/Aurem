"""
Hook Manager
Orchestrates all hooks in the AUREM system
"""

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timezone

from .base_hook import BaseHook, HookResult
from .pre_file_edit import PreFileEditHook
from .post_file_edit import PostFileEditHook
from .pre_api_call import PreAPICallHook
from .post_api_call import PostAPICallHook
from .pre_deploy import PreDeployHook
from .post_deploy import PostDeployHook
from .post_connector_fetch import PostConnectorFetchHook
from .post_agent_execute import PostAgentExecuteHook

logger = logging.getLogger(__name__)


class HookManager:
    """
    Central manager for all AUREM hooks
    
    Provides:
    - Hook registration
    - Hook execution
    - Hook lifecycle management (enable/disable)
    - Statistics tracking
    """
    
    def __init__(self):
        self.hooks: Dict[str, BaseHook] = {}
        self._initialized = False
        
        logger.info("[HookManager] Initializing...")
    
    def initialize(self):
        """Initialize all hooks"""
        if self._initialized:
            return
        
        # Register all 8 hooks
        self._register_hook(PreFileEditHook())
        self._register_hook(PostFileEditHook())
        self._register_hook(PreAPICallHook())
        self._register_hook(PostAPICallHook())
        self._register_hook(PreDeployHook())
        self._register_hook(PostDeployHook())
        self._register_hook(PostConnectorFetchHook())
        self._register_hook(PostAgentExecuteHook())
        
        self._initialized = True
        
        logger.info(
            f"[HookManager] Initialized with {len(self.hooks)} hooks: "
            f"{', '.join(self.hooks.keys())}"
        )
    
    def _register_hook(self, hook: BaseHook):
        """Register a hook"""
        self.hooks[hook.name] = hook
        logger.info(f"[HookManager] Registered hook: {hook.name}")
    
    async def trigger(self, hook_name: str, context: Dict[str, Any]) -> HookResult:
        """
        Trigger a specific hook
        
        Args:
            hook_name: Name of hook to trigger (e.g., "pre-file-edit")
            context: Context data for the hook
        
        Returns:
            HookResult with execution status
        """
        if not self._initialized:
            self.initialize()
        
        hook = self.hooks.get(hook_name)
        
        if not hook:
            logger.warning(f"[HookManager] Hook not found: {hook_name}")
            return HookResult(
                success=False,
                message=f"Hook '{hook_name}' not found",
                should_proceed=True
            )
        
        logger.info(f"[HookManager] Triggering hook: {hook_name}")
        result = await hook.run(context)
        
        return result
    
    async def trigger_event(self, event_name: str, context: Dict[str, Any]) -> List[HookResult]:
        """
        Trigger all hooks for an event
        
        Example events:
        - "file.edit" -> triggers pre-file-edit AND post-file-edit
        - "api.call" -> triggers pre-api-call AND post-api-call
        - "deploy" -> triggers pre-deploy AND post-deploy
        
        Args:
            event_name: Event name (e.g., "file.edit")
            context: Context data
        
        Returns:
            List of HookResults
        """
        if not self._initialized:
            self.initialize()
        
        # Map events to hooks
        event_hooks_map = {
            "file.edit": ["pre-file-edit", "post-file-edit"],
            "api.call": ["pre-api-call", "post-api-call"],
            "deploy": ["pre-deploy", "post-deploy"],
            "connector.fetch": ["post-connector-fetch"],
            "agent.execute": ["post-agent-execute"]
        }
        
        hook_names = event_hooks_map.get(event_name, [])
        
        if not hook_names:
            logger.warning(f"[HookManager] No hooks for event: {event_name}")
            return []
        
        results = []
        for hook_name in hook_names:
            result = await self.trigger(hook_name, context)
            results.append(result)
            
            # If pre-hook blocks, stop execution
            if "pre-" in hook_name and not result.should_proceed:
                logger.warning(
                    f"[HookManager] Hook {hook_name} blocked action. "
                    f"Reason: {result.message}"
                )
                break
        
        return results
    
    def enable_hook(self, hook_name: str) -> bool:
        """Enable a hook"""
        if not self._initialized:
            self.initialize()
        
        hook = self.hooks.get(hook_name)
        if hook:
            hook.enable()
            return True
        return False
    
    def disable_hook(self, hook_name: str) -> bool:
        """Disable a hook"""
        if not self._initialized:
            self.initialize()
        
        hook = self.hooks.get(hook_name)
        if hook:
            hook.disable()
            return True
        return False
    
    def list_hooks(self) -> List[Dict[str, Any]]:
        """List all hooks with stats"""
        if not self._initialized:
            self.initialize()
        
        return [hook.get_stats() for hook in self.hooks.values()]
    
    def get_hook_stats(self, hook_name: str) -> Optional[Dict[str, Any]]:
        """Get stats for specific hook"""
        if not self._initialized:
            self.initialize()
        
        hook = self.hooks.get(hook_name)
        if hook:
            return hook.get_stats()
        return None


# Singleton instance
_hook_manager = None


def get_hook_manager() -> HookManager:
    """Get singleton HookManager instance"""
    global _hook_manager
    
    if _hook_manager is None:
        _hook_manager = HookManager()
        _hook_manager.initialize()
    
    return _hook_manager
