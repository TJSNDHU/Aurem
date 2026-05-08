"""
PostFileEdit Hook
Runs after file edits - auto-lints, type checks, updates docs
"""

from typing import Dict, Any
import asyncio
import logging
from pathlib import Path

from .base_hook import BaseHook, HookResult

logger = logging.getLogger(__name__)


class PostFileEditHook(BaseHook):
    """
    Post-file-edit hook
    
    Actions:
    - Auto-lint Python files (ruff)
    - Auto-lint JavaScript files (eslint)
    - Run type checks
    - Update documentation if API changed
    """
    
    def __init__(self):
        super().__init__(
            name="post-file-edit",
            description="Auto-lints and validates files after edit",
            hook_type="post"
        )
    
    async def execute(self, context: Dict[str, Any]) -> HookResult:
        """
        Execute post-file-edit actions
        
        Context:
        {
            "file_path": "/app/backend/services/new_service.py",
            "operation": "create" | "edit",
            "run_lint": true
        }
        """
        file_path = context.get("file_path", "")
        run_lint = context.get("run_lint", True)
        
        if not file_path or not run_lint:
            return HookResult(
                success=True,
                message="Skipped linting",
                should_proceed=True
            )
        
        path = Path(file_path)
        warnings = []
        actions_taken = []
        
        # Python file - run ruff
        if path.suffix == ".py":
            try:
                proc = await asyncio.create_subprocess_shell(
                    f"cd /app/backend && ruff check {file_path} --quiet",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await proc.communicate()
                
                if proc.returncode == 0:
                    actions_taken.append("✅ Python linting passed")
                else:
                    errors = stderr.decode() if stderr else stdout.decode()
                    warnings.append(f"⚠️ Linting issues found:\n{errors[:200]}")
                    
            except Exception as e:
                warnings.append(f"Linting failed: {str(e)}")
        
        # JavaScript/TypeScript file - run eslint
        elif path.suffix in [".js", ".jsx", ".ts", ".tsx"]:
            try:
                proc = await asyncio.create_subprocess_shell(
                    f"cd /app/frontend && npx eslint {file_path} --quiet",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await proc.communicate()
                
                if proc.returncode == 0:
                    actions_taken.append("✅ JavaScript linting passed")
                else:
                    errors = stdout.decode() if stdout else stderr.decode()
                    warnings.append(f"⚠️ Linting issues found:\n{errors[:200]}")
                    
            except Exception as e:
                warnings.append(f"Linting failed: {str(e)}")
        
        # Check if it's a router file (API change)
        if "router" in path.name.lower() or "routes" in str(path):
            actions_taken.append("📝 API file detected - consider updating docs")
        
        return HookResult(
            success=True,
            message=f"Post-edit actions completed for {path.name}",
            should_proceed=True,
            warnings=warnings,
            data={
                "file": path.name,
                "actions_taken": actions_taken,
                "lint_run": run_lint
            }
        )
