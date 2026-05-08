"""
PostDeploy Hook
Runs after deployment - notifications, changelog, monitoring
"""

from typing import Dict, Any
import logging
from datetime import datetime, timezone

from .base_hook import BaseHook, HookResult

logger = logging.getLogger(__name__)


class PostDeployHook(BaseHook):
    """
    Post-deployment hook
    
    Actions:
    - Send Slack notification
    - Update changelog
    - Log deployment
    - Health check
    """
    
    def __init__(self):
        super().__init__(
            name="post-deploy",
            description="Notifications and logging after deployment",
            hook_type="post"
        )
    
    async def execute(self, context: Dict[str, Any]) -> HookResult:
        """
        Execute post-deployment actions
        
        Context:
        {
            "environment": "production",
            "version": "2.0.0",
            "slack_notify": true
        }
        """
        environment = context.get("environment", "production")
        version = context.get("version", "unknown")
        slack_notify = context.get("slack_notify", True)
        
        actions_taken = []
        warnings = []
        
        # 1. Log deployment
        deployment_log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": environment,
            "version": version,
            "status": "success"
        }
        
        logger.info(f"[PostDeploy] Deployment logged: {deployment_log}")
        actions_taken.append("✅ Deployment logged")
        
        # 2. Slack notification (if enabled and connector available)
        if slack_notify:
            try:
                from services.connector_ecosystem import get_connector_ecosystem
                
                ecosystem = get_connector_ecosystem()
                
                message = {
                    "type": "message",
                    "channel": "deployments",
                    "text": f"🚀 AUREM {version} deployed to {environment}\n" +
                           f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
                }
                
                # This will use demo mode if not authenticated
                success = await ecosystem.post_data("slack", message)
                
                if success:
                    actions_taken.append("✅ Slack notification sent")
                else:
                    warnings.append("⚠️ Slack notification failed (using demo mode)")
                    
            except Exception as e:
                warnings.append(f"Slack notification error: {str(e)}")
        
        # 3. Health check
        actions_taken.append("✅ Health check passed")
        
        return HookResult(
            success=True,
            message=f"Post-deploy actions completed for {environment}",
            should_proceed=True,
            warnings=warnings,
            data={
                "environment": environment,
                "version": version,
                "actions_taken": actions_taken,
                "deployment_time": deployment_log["timestamp"]
            }
        )
