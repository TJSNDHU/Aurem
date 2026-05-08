"""
ORA Code Tracer
Maps errors to source code files and lines

Scans local /app directory to find:
- File containing suspected function
- Line numbers of error-prone code
- Related imports and dependencies
"""

import os
import re
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CodeLocation(BaseModel):
    """Location in source code"""
    file_path: str
    line_number: Optional[int] = None
    function_name: Optional[str] = None
    code_snippet: Optional[str] = None
    context_lines: int = 5


class TraceResult(BaseModel):
    """Result from code tracing"""
    found: bool
    locations: List[CodeLocation]
    related_files: List[str]
    imports: List[str]


class CodeTracer:
    """
    Traces errors back to source code
    
    - Searches local /app directory
    - Finds files containing suspected functions
    - Extracts code snippets
    - Identifies related dependencies
    """
    
    def __init__(self):
        self.app_root = Path("/app")
        self.backend_root = self.app_root / "backend"
        self.frontend_root = self.app_root / "frontend" / "src"
    
    async def trace_error_to_code(
        self,
        suspected_files: List[str],
        suspected_functions: List[str],
        error_message: str = ""
    ) -> TraceResult:
        """
        Trace error to source code locations
        
        Args:
            suspected_files: List of file paths
            suspected_functions: List of function names
            error_message: Original error message
            
        Returns:
            TraceResult with code locations
        """
        locations = []
        related_files = []
        imports = []
        
        # Search suspected files
        for file_path in suspected_files:
            full_path = self._resolve_path(file_path)
            if full_path and full_path.exists():
                # Find functions in file
                file_locations = await self._search_file(
                    full_path,
                    suspected_functions,
                    error_message
                )
                locations.extend(file_locations)
                
                # Extract imports
                file_imports = self._extract_imports(full_path)
                imports.extend(file_imports)
        
        # If no files specified, search by function name
        if not suspected_files and suspected_functions:
            for func_name in suspected_functions:
                search_locations = await self._search_by_function_name(func_name)
                locations.extend(search_locations)
        
        # Find related files
        for location in locations:
            related = self._find_related_files(Path(location.file_path))
            related_files.extend(related)
        
        return TraceResult(
            found=len(locations) > 0,
            locations=locations,
            related_files=list(set(related_files)),
            imports=list(set(imports))
        )
    
    def _resolve_path(self, file_path: str) -> Optional[Path]:
        """Resolve relative path to absolute"""
        # Remove leading /app if present
        file_path = file_path.replace("/app/", "")
        
        # Try direct path
        full_path = self.app_root / file_path
        if full_path.exists():
            return full_path
        
        # Try backend
        if not file_path.startswith("backend"):
            backend_path = self.backend_root / file_path
            if backend_path.exists():
                return backend_path
        
        # Try frontend
        if not file_path.startswith("frontend"):
            frontend_path = self.frontend_root / file_path
            if frontend_path.exists():
                return frontend_path
        
        return None
    
    async def _search_file(
        self,
        file_path: Path,
        function_names: List[str],
        error_message: str
    ) -> List[CodeLocation]:
        """Search file for function definitions"""
        locations = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Search for functions
            for func_name in function_names:
                # Python: def function_name or async def function_name
                python_pattern = rf"^\s*(async\s+)?def\s+{re.escape(func_name)}\s*\("
                # JavaScript: function name or const name = or export function name
                js_pattern = rf"(function\s+{re.escape(func_name)}|const\s+{re.escape(func_name)}\s*=|export\s+.*{re.escape(func_name)})"
                
                for i, line in enumerate(lines):
                    if re.search(python_pattern, line) or re.search(js_pattern, line):
                        # Found function definition
                        snippet = self._extract_snippet(lines, i)
                        locations.append(CodeLocation(
                            file_path=str(file_path),
                            line_number=i + 1,
                            function_name=func_name,
                            code_snippet=snippet
                        ))
            
            # If no functions found, search for error message
            if not locations and error_message:
                for i, line in enumerate(lines):
                    if error_message.lower() in line.lower():
                        snippet = self._extract_snippet(lines, i)
                        locations.append(CodeLocation(
                            file_path=str(file_path),
                            line_number=i + 1,
                            code_snippet=snippet
                        ))
                        break
        
        except Exception as e:
            logger.error(f"[CODE_TRACER] Failed to read {file_path}: {e}")
        
        return locations
    
    async def _search_by_function_name(self, function_name: str) -> List[CodeLocation]:
        """Search entire codebase for function name"""
        locations = []
        
        # Search backend
        for py_file in self.backend_root.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            file_locations = await self._search_file(py_file, [function_name], "")
            locations.extend(file_locations)
        
        # Search frontend
        for js_file in self.frontend_root.rglob("*.jsx"):
            file_locations = await self._search_file(js_file, [function_name], "")
            locations.extend(file_locations)
        
        for js_file in self.frontend_root.rglob("*.js"):
            file_locations = await self._search_file(js_file, [function_name], "")
            locations.extend(file_locations)
        
        return locations
    
    def _extract_snippet(self, lines: List[str], line_index: int, context: int = 5) -> str:
        """Extract code snippet with context"""
        start = max(0, line_index - context)
        end = min(len(lines), line_index + context + 1)
        
        snippet_lines = []
        for i in range(start, end):
            marker = ">>>" if i == line_index else "   "
            snippet_lines.append(f"{marker} {i+1:4d} | {lines[i].rstrip()}")
        
        return "\n".join(snippet_lines)
    
    def _extract_imports(self, file_path: Path) -> List[str]:
        """Extract import statements from file"""
        imports = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Python imports
                    if line.startswith("import ") or line.startswith("from "):
                        imports.append(line)
                    # JavaScript imports
                    elif line.startswith("import "):
                        imports.append(line)
        except:
            pass
        
        return imports
    
    def _find_related_files(self, file_path: Path) -> List[str]:
        """Find files related to this file"""
        related = []
        
        # Same directory files
        if file_path.parent.exists():
            for sibling in file_path.parent.iterdir():
                if sibling.is_file() and sibling != file_path:
                    related.append(str(sibling))
        
        return related[:10]  # Limit to 10


# Singleton
_code_tracer = None

def get_code_tracer():
    global _code_tracer
    if _code_tracer is None:
        _code_tracer = CodeTracer()
    return _code_tracer
