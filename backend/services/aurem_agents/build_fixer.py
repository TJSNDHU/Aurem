"""
AUREM Build Fixer Agent
Detects and fixes build errors in AUREM codebase
Inspired by ECC's build-error-resolver agent
"""

from typing import Dict, Any
import re
import asyncio
from pathlib import Path
import logging

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AUREMBuildFixer(BaseAgent):
    """
    Agent that detects and fixes common build errors
    
    Capabilities:
    1. Detect missing imports
    2. Detect missing singleton patterns
    3. Fix import paths
    4. Auto-generate missing functions
    5. Verify fixes with Python import test
    """
    
    def __init__(self):
        super().__init__(
            name="aurem-build-fixer",
            description="Detects and auto-fixes build errors in AUREM codebase"
        )
        self.backend_root = Path("/app/backend")
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute build fix
        
        Context parameters:
        - error_type: "import_error" | "syntax_error" | "module_not_found"
        - error_message: str (error details)
        - file_path: str (optional, file with error)
        - auto_fix: bool (default: True)
        
        Returns:
        - success: bool
        - fix_applied: bool
        - fix_description: str
        - verification: dict (import test results)
        """
        error_type = context.get("error_type")
        error_message = context.get("error_message", "")
        auto_fix = context.get("auto_fix", True)
        
        logger.info(f"[BuildFixer] Analyzing error: {error_type}")
        
        # Detect error pattern
        if "cannot import name" in error_message.lower():
            return await self._fix_import_error(error_message, auto_fix)
        elif "no module named" in error_message.lower():
            return await self._fix_module_error(error_message, auto_fix)
        elif "syntaxerror" in error_message.lower():
            return await self._fix_syntax_error(error_message, auto_fix)
        else:
            return {
                "success": False,
                "fix_applied": False,
                "message": f"Unknown error type: {error_type}"
            }
    
    async def _fix_import_error(self, error_message: str, auto_fix: bool) -> Dict[str, Any]:
        """
        Fix import errors like:
        'cannot import name get_connector_ecosystem from services.connector_ecosystem'
        """
        # Extract missing function name
        match = re.search(r"cannot import name '?(\w+)'? from '?([\w.]+)'?", error_message, re.IGNORECASE)
        
        if not match:
            return {
                "success": False,
                "fix_applied": False,
                "message": "Could not parse import error"
            }
        
        function_name = match.group(1)
        module_path = match.group(2)
        
        logger.info(f"[BuildFixer] Missing: {function_name} in {module_path}")
        
        # Convert module path to file path
        file_path = self.backend_root / module_path.replace(".", "/") / ".py"
        if not file_path.exists():
            # Try without __init__.py
            file_path = self.backend_root / f"{module_path.replace('.', '/')}.py"
        
        if not file_path.exists():
            return {
                "success": False,
                "fix_applied": False,
                "message": f"File not found: {file_path}"
            }
        
        # Check if it's a singleton pattern issue
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Detect if class exists but getter function missing
        class_pattern = re.search(r"class (\w+Ecosystem|\w+Service).*?:", content)
        
        if class_pattern and auto_fix:
            class_name = class_pattern.group(1)
            
            # Check if singleton already exists
            if f"def {function_name}" in content:
                return {
                    "success": True,
                    "fix_applied": False,
                    "message": f"Function {function_name} already exists"
                }
            
            # Generate singleton pattern
            singleton_code = f"""
# Global instance (singleton pattern)
_{class_name.lower().replace('ecosystem', '').replace('service', '')}_instance = {class_name}()


def {function_name}() -> {class_name}:
    \"\"\"Get global {class_name.lower()} instance\"\"\"
    return _{class_name.lower().replace('ecosystem', '').replace('service', '')}_instance


def set_{class_name.lower()}_db(db):
    \"\"\"Set database for {class_name.lower()}\"\"\"
    _{class_name.lower().replace('ecosystem', '').replace('service', '')}_instance.set_db(db)
"""
            
            # Append to file
            with open(file_path, 'a') as f:
                f.write(singleton_code)
            
            # Verify fix
            verification = await self._verify_import(module_path, function_name)
            
            return {
                "success": verification["success"],
                "fix_applied": True,
                "fix_description": f"Added singleton pattern for {class_name}",
                "function_added": function_name,
                "class_name": class_name,
                "file_path": str(file_path),
                "verification": verification
            }
        
        return {
            "success": False,
            "fix_applied": False,
            "message": "Could not auto-fix import error"
        }
    
    async def _fix_module_error(self, error_message: str, auto_fix: bool) -> Dict[str, Any]:
        """Fix 'No module named X' errors"""
        match = re.search(r"No module named '?([\w.]+)'?", error_message, re.IGNORECASE)
        
        if not match:
            return {
                "success": False,
                "fix_applied": False,
                "message": "Could not parse module error"
            }
        
        module_name = match.group(1)
        
        # Check if it's a missing __init__.py
        module_path = self.backend_root / module_name.replace(".", "/")
        
        if module_path.exists() and module_path.is_dir():
            init_file = module_path / "__init__.py"
            
            if not init_file.exists() and auto_fix:
                # Create __init__.py
                init_file.touch()
                
                return {
                    "success": True,
                    "fix_applied": True,
                    "fix_description": f"Created missing __init__.py in {module_path}",
                    "file_created": str(init_file)
                }
        
        return {
            "success": False,
            "fix_applied": False,
            "message": f"Could not auto-fix module error for {module_name}"
        }
    
    async def _fix_syntax_error(self, error_message: str, auto_fix: bool) -> Dict[str, Any]:
        """Fix syntax errors"""
        # This is complex and risky, so we only suggest fixes
        return {
            "success": False,
            "fix_applied": False,
            "message": "Syntax errors require manual review",
            "suggestion": "Run: python3 -m py_compile <file_path>"
        }
    
    async def _verify_import(self, module_path: str, function_name: str) -> Dict[str, Any]:
        """
        Verify import works by running Python import test
        """
        try:
            # Run import test
            test_code = f"import sys; sys.path.insert(0, '/app/backend'); from {module_path} import {function_name}; print('✅ Import successful')"
            
            process = await asyncio.create_subprocess_shell(
                f'python3 -c "{test_code}"',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            success = process.returncode == 0 and b"Import successful" in stdout
            
            return {
                "success": success,
                "return_code": process.returncode,
                "stdout": stdout.decode(),
                "stderr": stderr.decode() if stderr else None
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def diagnose_404_error(self, endpoint: str) -> Dict[str, Any]:
        """
        Diagnose why an API endpoint is returning 404
        
        Args:
            endpoint: API endpoint path (e.g., "/api/connectors/platforms")
        
        Returns:
            Diagnosis with fix suggestions
        """
        # Find router file for this endpoint
        endpoint_parts = endpoint.strip("/").split("/")
        
        if len(endpoint_parts) < 2:
            return {
                "success": False,
                "message": "Invalid endpoint format"
            }
        
        router_name = f"{endpoint_parts[1]}_router"  # e.g., "connectors" → "connector_router"
        router_file = self.backend_root / "routers" / f"{router_name}.py"
        
        if not router_file.exists():
            return {
                "success": False,
                "message": f"Router file not found: {router_file}",
                "suggestion": f"Create {router_file} with FastAPI router"
            }
        
        # Check if router is imported in server.py
        server_file = self.backend_root / "server.py"
        
        with open(server_file, 'r') as f:
            server_content = f.read()
        
        if router_name not in server_content:
            return {
                "success": False,
                "message": f"Router {router_name} not imported in server.py",
                "suggestion": f"Add: from routers.{router_name} import router as {router_name}"
            }
        
        # Check if router has import errors
        try:
            test_code = f"import sys; sys.path.insert(0, '/app/backend'); from routers import {router_name}"
            
            process = await asyncio.create_subprocess_shell(
                f'python3 -c "{test_code}"',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                # Import error detected!
                error_message = stderr.decode()
                
                # Try to auto-fix
                fix_result = await self.execute({
                    "error_type": "import_error",
                    "error_message": error_message,
                    "auto_fix": True
                })
                
                return {
                    "success": True,
                    "diagnosis": "Import error detected in router",
                    "error_message": error_message,
                    "fix_result": fix_result
                }
            
            return {
                "success": True,
                "diagnosis": "Router imports successfully",
                "message": "404 may be due to server not restarted or route prefix mismatch"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
