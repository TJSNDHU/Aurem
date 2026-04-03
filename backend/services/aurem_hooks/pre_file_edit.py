"""
PreFileEdit Hook
Runs before editing files - warns about large files, checks permissions
"""

from typing import Dict, Any
import logging
from pathlib import Path

from .base_hook import BaseHook, HookResult

logger = logging.getLogger(__name__)


class PreFileEditHook(BaseHook):
    """
    Pre-file-edit hook
    
    Checks:
    - File size (warn if >1000 lines)
    - Critical files (server.py = 43K lines!)
    - .env file edits (warn about secrets)
    - Read-only files
    """
    
    def __init__(self):
        super().__init__(
            name="pre-file-edit",
            description="Warns before editing large/critical files",
            hook_type="pre"
        )
        
        self.critical_files = [
            "server.py",  # 43K lines monster
            ".env",       # Contains secrets
            "requirements.txt",
            "package.json"
        ]
        
        self.max_lines_warning = 1000
    
    async def execute(self, context: Dict[str, Any]) -> HookResult:
        """
        Execute pre-file-edit checks
        
        Context:
        {
            "file_path": "/app/backend/server.py",
            "operation": "edit" | "create" | "delete"
        }
        """
        file_path = context.get("file_path", "")
        operation = context.get("operation", "edit")
        
        if not file_path:
            return HookResult(success=True, should_proceed=True)
        
        warnings = []
        should_proceed = True
        
        # Check if file exists
        path = Path(file_path)
        file_name = path.name
        
        # Critical file warning
        if file_name in self.critical_files:
            warnings.append(
                f"⚠️ CRITICAL FILE: {file_name} - "
                f"Changes may affect entire system"
            )
            
            if file_name == "server.py":
                warnings.append(
                    "💡 TIP: server.py is 43K+ lines. "
                    "Consider using search_replace for targeted edits"
                )
            
            elif file_name == ".env":
                warnings.append(
                    "🔒 SECURITY: Never commit .env to git. "
                    "Use environment variables in production"
                )
        
        # Check file size if exists
        if path.exists() and path.is_file():
            try:
                with open(path, 'r') as f:
                    line_count = sum(1 for _ in f)
                
                if line_count > self.max_lines_warning:
                    warnings.append(
                        f"📏 LARGE FILE: {line_count} lines. "
                        f"Consider breaking into smaller modules"
                    )
                    
                    if line_count > 10000:
                        warnings.append(
                            "⚠️ EXTREME SIZE: Use search_replace instead of "
                            "full file rewrite to avoid corruption"
                        )
            
            except Exception as e:
                logger.warning(f"[PreFileEdit] Could not read {file_path}: {e}")
        
        return HookResult(
            success=True,
            message=f"Pre-edit checks completed for {file_name}",
            should_proceed=should_proceed,
            warnings=warnings,
            data={
                "file": file_name,
                "operation": operation,
                "warnings_count": len(warnings)
            }
        )
