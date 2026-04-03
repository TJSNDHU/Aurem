"""
AUREM Code Reviewer Agent
Reviews code for quality, security, and maintainability
Inspired by ECC's code-reviewer agent
"""

from typing import Dict, Any, List
import re
from pathlib import Path
import logging

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AUREMCodeReviewer(BaseAgent):
    """
    Agent that reviews code changes for AUREM projects
    
    Capabilities:
    1. FastAPI code review (async patterns, dependency injection)
    2. React code review (hooks, component patterns, Shadcn UI)
    3. MongoDB anti-pattern detection
    4. Security review (API keys, auth, OWASP)
    5. Code quality metrics (complexity, duplication)
    """
    
    def __init__(self):
        super().__init__(
            name="aurem-code-reviewer",
            description="Reviews code for quality, security, and AUREM best practices"
        )
        self.backend_root = Path("/app/backend")
        self.frontend_root = Path("/app/frontend")
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute code review
        
        Context parameters:
        - file_path: str (file to review)
        - code_type: "python" | "javascript" | "auto"
        - review_type: "full" | "security" | "style" | "performance"
        - standards: list (e.g., ["pep8", "owasp", "aurem"])
        
        Returns:
        - success: bool
        - issues: list (code issues found)
        - suggestions: list (improvement suggestions)
        - score: int (0-100, code quality score)
        """
        file_path = context.get("file_path")
        review_type = context.get("review_type", "full")
        code_type = context.get("code_type", "auto")
        
        if not file_path:
            return {
                "success": False,
                "message": "file_path is required"
            }
        
        # Read file
        try:
            with open(file_path, 'r') as f:
                code_content = f.read()
        except FileNotFoundError:
            return {
                "success": False,
                "message": f"File not found: {file_path}"
            }
        
        # Auto-detect code type
        if code_type == "auto":
            if file_path.endswith(".py"):
                code_type = "python"
            elif file_path.endswith((".js", ".jsx", ".ts", ".tsx")):
                code_type = "javascript"
            else:
                return {
                    "success": False,
                    "message": "Could not auto-detect code type"
                }
        
        # Run appropriate review
        if code_type == "python":
            result = await self._review_python(code_content, file_path, review_type)
        elif code_type == "javascript":
            result = await self._review_javascript(code_content, file_path, review_type)
        else:
            return {
                "success": False,
                "message": f"Unsupported code type: {code_type}"
            }
        
        # Calculate overall score
        result["score"] = self._calculate_score(result)
        result["success"] = True
        
        return result
    
    async def _review_python(self, code: str, file_path: str, review_type: str) -> Dict[str, Any]:
        """Review Python code"""
        issues = []
        suggestions = []
        
        # 1. AUREM-specific patterns
        issues.extend(self._check_mongodb_patterns(code))
        issues.extend(self._check_fastapi_patterns(code))
        issues.extend(self._check_env_usage(code))
        
        # 2. Security checks
        if review_type in ["full", "security"]:
            issues.extend(self._check_security_python(code))
        
        # 3. Code quality
        if review_type in ["full", "style"]:
            issues.extend(self._check_python_style(code))
        
        # 4. Performance
        if review_type in ["full", "performance"]:
            suggestions.extend(self._check_python_performance(code))
        
        # 5. Specific checks for server.py (43K lines monster!)
        if "server.py" in file_path:
            issues.append({
                "severity": "warning",
                "type": "tech_debt",
                "message": "server.py is 43K+ lines - consider breaking into modules",
                "suggestion": "Use refactor-agent to split into: routers/, services/, models/"
            })
        
        return {
            "file_path": file_path,
            "code_type": "python",
            "review_type": review_type,
            "issues": issues,
            "suggestions": suggestions,
            "total_issues": len(issues),
            "critical_issues": len([i for i in issues if i["severity"] == "critical"]),
            "warnings": len([i for i in issues if i["severity"] == "warning"])
        }
    
    async def _review_javascript(self, code: str, file_path: str, review_type: str) -> Dict[str, Any]:
        """Review JavaScript/React code"""
        issues = []
        suggestions = []
        
        # 1. React-specific patterns
        issues.extend(self._check_react_patterns(code))
        issues.extend(self._check_shadcn_usage(code))
        
        # 2. Security checks
        if review_type in ["full", "security"]:
            issues.extend(self._check_security_javascript(code))
        
        # 3. Code quality
        if review_type in ["full", "style"]:
            issues.extend(self._check_javascript_style(code))
        
        return {
            "file_path": file_path,
            "code_type": "javascript",
            "review_type": review_type,
            "issues": issues,
            "suggestions": suggestions,
            "total_issues": len(issues),
            "critical_issues": len([i for i in issues if i["severity"] == "critical"]),
            "warnings": len([i for i in issues if i["severity"] == "warning"])
        }
    
    def _check_mongodb_patterns(self, code: str) -> List[Dict]:
        """Check for MongoDB anti-patterns"""
        issues = []
        
        # Anti-pattern: if not self.db (should be: if self.db is None)
        if re.search(r'if not self\.db:', code):
            issues.append({
                "severity": "error",
                "type": "mongodb_antipattern",
                "message": "Use 'if self.db is None:' instead of 'if not self.db:'",
                "line": self._find_line_number(code, r'if not self\.db:'),
                "suggestion": "MongoDB databases are falsy when empty, causing bugs"
            })
        
        # Missing _id exclusion
        if re.search(r'\.find\([^)]+\)(?!\s*,\s*\{[^}]*"_id":\s*0)', code):
            if 'projection' not in code and '"_id": 0' not in code:
                issues.append({
                    "severity": "warning",
                    "type": "mongodb_serialization",
                    "message": "Consider excluding _id from query results",
                    "suggestion": 'Add projection: {"_id": 0} to prevent ObjectId serialization issues'
                })
        
        return issues
    
    def _check_fastapi_patterns(self, code: str) -> List[Dict]:
        """Check FastAPI best practices"""
        issues = []
        
        # Missing async/await
        if "@router." in code and "async def" not in code:
            issues.append({
                "severity": "warning",
                "type": "fastapi_pattern",
                "message": "FastAPI routes should use async def for better performance",
                "suggestion": "Change 'def' to 'async def' and use 'await' for DB calls"
            })
        
        # Missing response_model
        if re.search(r'@router\.(get|post|put|delete)\(', code):
            if "response_model" not in code and "List[" not in code:
                issues.append({
                    "severity": "info",
                    "type": "fastapi_docs",
                    "message": "Consider adding response_model for better API docs",
                    "suggestion": "@router.get('/endpoint', response_model=YourModel)"
                })
        
        return issues
    
    def _check_env_usage(self, code: str) -> List[Dict]:
        """Check environment variable usage"""
        issues = []
        
        # Hardcoded URLs
        hardcoded_patterns = [
            (r'https?://localhost:\d+', 'Hardcoded localhost URL'),
            (r'mongodb://localhost', 'Hardcoded MongoDB URL'),
            (r'sk-[A-Za-z0-9]{32,}', 'Hardcoded API key detected!'),
            (r'AKIA[0-9A-Z]{16}', 'Hardcoded AWS key detected!')
        ]
        
        for pattern, message in hardcoded_patterns:
            if re.search(pattern, code):
                issues.append({
                    "severity": "critical",
                    "type": "security_hardcoded",
                    "message": message,
                    "suggestion": "Use environment variables: os.environ.get('VAR_NAME')"
                })
        
        return issues
    
    def _check_security_python(self, code: str) -> List[Dict]:
        """Security checks for Python"""
        issues = []
        
        # SQL injection (even though we use MongoDB)
        if "execute(" in code and "%" in code:
            issues.append({
                "severity": "critical",
                "type": "security_injection",
                "message": "Potential SQL injection vulnerability",
                "suggestion": "Use parameterized queries"
            })
        
        # Unsafe eval/exec
        if re.search(r'\b(eval|exec)\(', code):
            issues.append({
                "severity": "critical",
                "type": "security_code_execution",
                "message": "Unsafe eval/exec usage detected",
                "suggestion": "Never use eval/exec with user input"
            })
        
        # Missing input validation
        if "request.get(" in code or "request.post(" in code:
            if ".get(" not in code:  # Simple heuristic
                issues.append({
                    "severity": "warning",
                    "type": "security_validation",
                    "message": "Consider adding input validation",
                    "suggestion": "Use Pydantic models for request validation"
                })
        
        return issues
    
    def _check_python_style(self, code: str) -> List[Dict]:
        """Python style checks (simplified PEP 8)"""
        issues = []
        
        # Long lines (>120 chars)
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                issues.append({
                    "severity": "info",
                    "type": "style_line_length",
                    "message": f"Line {i} exceeds 120 characters ({len(line)} chars)",
                    "line": i
                })
        
        # Missing docstrings for functions
        if re.search(r'def [a-zA-Z_][a-zA-Z0-9_]*\([^)]*\):\s*(?!""")', code):
            issues.append({
                "severity": "info",
                "type": "style_docstring",
                "message": "Some functions missing docstrings",
                "suggestion": "Add docstrings for better documentation"
            })
        
        return issues
    
    def _check_python_performance(self, code: str) -> List[Dict]:
        """Performance suggestions for Python"""
        suggestions = []
        
        # Inefficient list comprehension
        if ".append(" in code and "for " in code:
            if "[" not in code or "]" not in code:
                suggestions.append({
                    "type": "performance_list_comp",
                    "message": "Consider using list comprehension instead of append in loop",
                    "example": "items = [process(x) for x in data]"
                })
        
        return suggestions
    
    def _check_react_patterns(self, code: str) -> List[Dict]:
        """Check React best practices"""
        issues = []
        
        # Missing key in list items
        if ".map(" in code and "return <" in code:
            if "key=" not in code:
                issues.append({
                    "severity": "warning",
                    "type": "react_key",
                    "message": "Missing 'key' prop in list items",
                    "suggestion": "Add unique key: key={item.id}"
                })
        
        # Inline arrow functions in JSX
        if re.search(r'onClick=\{.*=>', code):
            issues.append({
                "severity": "info",
                "type": "react_performance",
                "message": "Inline arrow functions in JSX cause re-renders",
                "suggestion": "Use useCallback or define function outside render"
            })
        
        return issues
    
    def _check_shadcn_usage(self, code: str) -> List[Dict]:
        """Check Shadcn UI component usage"""
        issues = []
        
        # Not using Shadcn components
        if "className=" in code and "cn(" not in code:
            issues.append({
                "severity": "info",
                "type": "shadcn_usage",
                "message": "Consider using cn() utility for className merging",
                "suggestion": "import { cn } from '@/lib/utils'"
            })
        
        return issues
    
    def _check_security_javascript(self, code: str) -> List[Dict]:
        """Security checks for JavaScript"""
        issues = []
        
        # Hardcoded API keys
        if re.search(r'(api[_-]?key|token)\s*[:=]\s*["\'][^"\']+["\']', code, re.IGNORECASE):
            issues.append({
                "severity": "critical",
                "type": "security_hardcoded",
                "message": "Potential hardcoded API key/token",
                "suggestion": "Use environment variables: process.env.REACT_APP_KEY"
            })
        
        # dangerouslySetInnerHTML
        if "dangerouslySetInnerHTML" in code:
            issues.append({
                "severity": "warning",
                "type": "security_xss",
                "message": "dangerouslySetInnerHTML can lead to XSS attacks",
                "suggestion": "Sanitize HTML or use safe alternatives"
            })
        
        return issues
    
    def _check_javascript_style(self, code: str) -> List[Dict]:
        """JavaScript style checks"""
        issues = []
        
        # var instead of const/let
        if re.search(r'\bvar\s+', code):
            issues.append({
                "severity": "warning",
                "type": "style_var",
                "message": "Use 'const' or 'let' instead of 'var'",
                "suggestion": "Modern JavaScript best practice"
            })
        
        # console.log in production
        if "console.log(" in code:
            issues.append({
                "severity": "info",
                "type": "style_console",
                "message": "Remove console.log before production",
                "suggestion": "Use proper logging library"
            })
        
        return issues
    
    def _calculate_score(self, result: Dict) -> int:
        """Calculate code quality score (0-100)"""
        critical = result["critical_issues"]
        warnings = result["warnings"]
        total = result["total_issues"]
        
        if total == 0:
            return 100
        
        # Weighted scoring
        score = 100
        score -= critical * 15  # -15 per critical
        score -= warnings * 5   # -5 per warning
        score -= (total - critical - warnings) * 2  # -2 per info
        
        return max(0, min(100, score))
    
    def _find_line_number(self, code: str, pattern: str) -> int:
        """Find line number of pattern match"""
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            if re.search(pattern, line):
                return i
        return 0
