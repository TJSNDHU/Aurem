"""
PostAgentExecute Hook
Runs after agent execution - logs outputs for AI-to-AI learning
"""

from typing import Dict, Any
import logging
from datetime import datetime, timezone

from .base_hook import BaseHook, HookResult

logger = logging.getLogger(__name__)


class PostAgentExecuteHook(BaseHook):
    """
    Post-agent-execute hook
    
    Actions:
    - Log agent execution details
    - Index agent outputs in Vector DB for learning
    - Track agent performance patterns
    - Enable AI-to-AI learning (agents learn from each other)
    - Support self-healing (learn from Build Fixer patterns)
    """
    
    def __init__(self):
        super().__init__(
            name="post-agent-execute",
            description="Logs agent outputs for AI-to-AI learning",
            hook_type="post"
        )
        
        self.enable_learning = True
        self.min_output_length = 20
    
    async def execute(self, context: Dict[str, Any]) -> HookResult:
        """
        Execute post-agent-execute actions
        
        Context:
        {
            "agent_name": "build-fixer",
            "input": {...},
            "output": {...},
            "success": true,
            "execution_time": 2.5,
            "error": null
        }
        """
        agent_name = context.get("agent_name", "")
        input_data = context.get("input", {})
        output_data = context.get("output", {})
        success = context.get("success", False)
        execution_time = context.get("execution_time", 0)
        error = context.get("error")
        
        actions_taken = []
        warnings = []
        
        # Log execution
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent_name,
            "success": success,
            "execution_time": execution_time
        }
        
        logger.info(f"[PostAgentExecute] {agent_name}: {log_entry}")
        actions_taken.append(f"✅ Logged execution of {agent_name}")
        
        # Index in Vector DB for AI-to-AI learning
        if self.enable_learning and success:
            try:
                from services.vector_search import get_vector_search
                
                vector_service = get_vector_search()
                
                # Build learning text
                learning_text = self._build_learning_text(
                    agent_name, input_data, output_data, error
                )
                
                if learning_text and len(learning_text) >= self.min_output_length:
                    # Extract task and solution from learning text
                    task_summary = str(input_data)[:200] if input_data else "No input"
                    solution_summary = str(output_data)[:200] if output_data else "No output"
                    
                    # Use the existing index_agent_memory method
                    success_indexed = await vector_service.index_agent_memory(
                        agent_name=agent_name,
                        task=task_summary,
                        solution=solution_summary,
                        success=success,
                        metadata={
                            "execution_time": execution_time,
                            "source": "agent_execution_hook"
                        }
                    )
                    
                    if success_indexed:
                        actions_taken.append(
                            "🧠 Indexed agent output in Vector DB for learning"
                        )
                        
                        logger.info(
                            f"[PostAgentExecute] Indexed {agent_name} output "
                            f"for AI-to-AI learning"
                        )
                    else:
                        warnings.append("⚠️ Agent memory indexing returned False")
                
            except Exception as e:
                logger.error(f"[PostAgentExecute] Vector indexing failed: {e}")
                warnings.append(f"Learning indexing failed: {str(e)[:100]}")
        
        # Track performance patterns
        if success:
            actions_taken.append(
                f"📊 Performance: {execution_time:.2f}s for {agent_name}"
            )
        else:
            warnings.append(f"⚠️ Agent {agent_name} execution failed")
        
        return HookResult(
            success=True,
            message=f"Post-agent actions completed for {agent_name}",
            should_proceed=True,
            warnings=warnings,
            data={
                "agent": agent_name,
                "success": success,
                "execution_time": execution_time,
                "actions_taken": actions_taken,
                "learned": self.enable_learning and success
            }
        )
    
    def _build_learning_text(self, agent_name: str, input_data: Dict, output_data: Dict, error: Any) -> str:
        """
        Build learning text from agent execution
        
        Format: "Agent [name] received [input summary] and produced [output summary]"
        """
        parts = [f"Agent {agent_name} execution:"]
        
        # Input summary
        if isinstance(input_data, dict):
            # Extract key input fields
            input_summary = ", ".join([
                f"{k}={v}" for k, v in list(input_data.items())[:3]
                if isinstance(v, (str, int, float, bool))
            ])
            if input_summary:
                parts.append(f"Input: {input_summary}")
        
        # Output summary
        if isinstance(output_data, dict):
            # Try to get meaningful output
            output_text = (
                output_data.get("result", "") or
                output_data.get("message", "") or
                output_data.get("summary", "") or
                str(output_data)[:200]
            )
            if output_text:
                parts.append(f"Output: {output_text}")
        
        # Error (if any)
        if error:
            parts.append(f"Error: {str(error)[:100]}")
        
        return " | ".join(parts)
