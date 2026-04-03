"""
AUREM Security Scanner Agent
Comprehensive security audit for AUREM SaaS platform
Inspired by ECC's security-reviewer agent
"""

from typing import Dict, Any, List
import re
from pathlib import Path
import logging

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AUREMSecurityScanner(BaseAgent):
    """
    Agent that performs security audits on AUREM codebase
    
    Capabilities:
    1. OWASP Top 10 checks
    2. SaaS-specific security (auth, subscriptions, payments)
    3. API security (rate limiting, auth, CORS)
    4. MongoDB security (injection, auth)
    5. Frontend security (XSS, CSRF, secrets exposure)
    """
    
    def __init__(self):
        super().__init__(
            name="aurem-security-scanner",
            description="Comprehensive security audit for AUREM SaaS platform"
        )
        self.backend_root = Path("/app/backend")
        self.frontend_root = Path("/app/frontend")
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute security scan
        
        Context parameters:
        - scan_type: "full" | "auth" | "payment" | "api" | "frontend"
        - target: "backend" | "frontend" | "both"
        - severity_threshold: "critical" | "high" | "medium" | "low"
        
        Returns:
        - success: bool
        - vulnerabilities: list (security issues found)
        - risk_score: int (0-100, higher = more risky)
        - recommendations: list (security improvements)
        """
        scan_type = context.get("scan_type", "full")
        target = context.get("target", "both")
        
        vulnerabilities = []
        recommendations = []
        
        # Backend security scans
        if target in ["backend", "both"]:
            if scan_type in ["full", "auth"]:
                vulnerabilities.extend(await self._scan_auth_security())
            
            if scan_type in ["full", "payment"]:
                vulnerabilities.extend(await self._scan_payment_security())
            
            if scan_type in ["full", "api"]:
                vulnerabilities.extend(await self._scan_api_security())
            
            if scan_type == "full":
                vulnerabilities.extend(await self._scan_owasp_backend())
        
        # Frontend security scans
        if target in ["frontend", "both"]:
            if scan_type == "full":
                vulnerabilities.extend(await self._scan_frontend_security())
        
        # Generate recommendations
        recommendations = self._generate_recommendations(vulnerabilities)
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(vulnerabilities)
        
        return {
            "success": True,
            "scan_type": scan_type,
            "target": target,
            "vulnerabilities": vulnerabilities,
            "total_vulnerabilities": len(vulnerabilities),
            "critical": len([v for v in vulnerabilities if v["severity"] == "critical"]),
            "high": len([v for v in vulnerabilities if v["severity"] == "high"]),
            "medium": len([v for v in vulnerabilities if v["severity"] == "medium"]),
            "low": len([v for v in vulnerabilities if v["severity"] == "low"]),
            "risk_score": risk_score,
            "risk_level": self._get_risk_level(risk_score),
            "recommendations": recommendations
        }
    
    async def _scan_auth_security(self) -> List[Dict]:
        """Scan authentication & authorization security"""
        vulnerabilities = []
        
        # Check if JWT secret is properly configured
        env_file = self.backend_root / ".env"
        
        if env_file.exists():
            with open(env_file, 'r') as f:
                env_content = f.read()
            
            # JWT secret check
            if "JWT_SECRET_KEY" not in env_content:
                vulnerabilities.append({
                    "severity": "critical",
                    "category": "authentication",
                    "title": "Missing JWT Secret Key",
                    "description": "JWT_SECRET_KEY not found in .env file",
                    "impact": "Authentication tokens may be insecure or not working",
                    "remediation": "Add JWT_SECRET_KEY to .env with a strong random value",
                    "cwe": "CWE-798: Use of Hard-coded Credentials"
                })
            elif re.search(r'JWT_SECRET_KEY\s*=\s*["\']?(changeme|secret|test)', env_content, re.IGNORECASE):
                vulnerabilities.append({
                    "severity": "critical",
                    "category": "authentication",
                    "title": "Weak JWT Secret Key",
                    "description": "JWT_SECRET_KEY appears to use a weak/default value",
                    "impact": "Attackers can forge authentication tokens",
                    "remediation": "Use a strong random secret (32+ characters)",
                    "cwe": "CWE-521: Weak Password Requirements"
                })
        
        # Check for bcrypt usage in password hashing
        auth_files = list(self.backend_root.glob("**/auth*.py"))
        
        for auth_file in auth_files:
            with open(auth_file, 'r') as f:
                code = f.read()
            
            # Password hashing check
            if "password" in code.lower() and "bcrypt" not in code and "hash" in code:
                vulnerabilities.append({
                    "severity": "high",
                    "category": "authentication",
                    "title": "Insecure Password Hashing",
                    "description": f"Password hashing in {auth_file.name} may not use bcrypt",
                    "impact": "User passwords vulnerable to cracking",
                    "remediation": "Use bcrypt for password hashing",
                    "file": str(auth_file),
                    "cwe": "CWE-916: Use of Password Hash With Insufficient Computational Effort"
                })
            
            # Session management
            if "session" in code.lower() and "httponly" not in code.lower():
                vulnerabilities.append({
                    "severity": "medium",
                    "category": "authentication",
                    "title": "Missing HttpOnly Flag on Sessions",
                    "description": "Session cookies should have HttpOnly flag",
                    "impact": "XSS attacks can steal session tokens",
                    "remediation": "Set HttpOnly=True on session cookies",
                    "file": str(auth_file),
                    "cwe": "CWE-1004: Sensitive Cookie Without 'HttpOnly' Flag"
                })
        
        return vulnerabilities
    
    async def _scan_payment_security(self) -> List[Dict]:
        """Scan payment/subscription security"""
        vulnerabilities = []
        
        # Check Stripe integration
        stripe_files = list(self.backend_root.glob("**/*subscription*.py")) + \
                       list(self.backend_root.glob("**/*payment*.py"))
        
        for file in stripe_files:
            with open(file, 'r') as f:
                code = f.read()
            
            # Hardcoded Stripe keys
            if re.search(r'sk_test_[A-Za-z0-9]{24,}', code):
                vulnerabilities.append({
                    "severity": "critical",
                    "category": "payment",
                    "title": "Hardcoded Stripe Secret Key",
                    "description": f"Stripe secret key found in {file.name}",
                    "impact": "API keys exposed in code, potential unauthorized charges",
                    "remediation": "Move Stripe keys to environment variables",
                    "file": str(file),
                    "cwe": "CWE-798: Use of Hard-coded Credentials"
                })
            
            # Amount validation
            if "amount" in code and "int(" in code:
                if "validate" not in code and "check" not in code:
                    vulnerabilities.append({
                        "severity": "high",
                        "category": "payment",
                        "title": "Missing Payment Amount Validation",
                        "description": "Payment amounts should be validated server-side",
                        "impact": "Users could manipulate payment amounts",
                        "remediation": "Add server-side validation for all payment amounts",
                        "file": str(file),
                        "cwe": "CWE-20: Improper Input Validation"
                    })
            
            # Webhook signature verification
            if "webhook" in code.lower():
                if "verify" not in code.lower() and "signature" not in code.lower():
                    vulnerabilities.append({
                        "severity": "high",
                        "category": "payment",
                        "title": "Missing Webhook Signature Verification",
                        "description": "Stripe webhooks should verify signatures",
                        "impact": "Attackers can send fake webhook events",
                        "remediation": "Verify webhook signatures using stripe.Webhook.construct_event()",
                        "file": str(file),
                        "cwe": "CWE-345: Insufficient Verification of Data Authenticity"
                    })
        
        return vulnerabilities
    
    async def _scan_api_security(self) -> List[Dict]:
        """Scan API security"""
        vulnerabilities = []
        
        # Check CORS configuration
        server_file = self.backend_root / "server.py"
        
        if server_file.exists():
            with open(server_file, 'r') as f:
                code = f.read()
            
            # Overly permissive CORS
            if re.search(r'allow_origins\s*=\s*\[\s*["\']?\*["\']?\s*\]', code):
                vulnerabilities.append({
                    "severity": "high",
                    "category": "api",
                    "title": "Overly Permissive CORS Policy",
                    "description": "CORS allows all origins (*)",
                    "impact": "Any website can make requests to your API",
                    "remediation": "Restrict CORS to specific trusted domains",
                    "file": "server.py",
                    "cwe": "CWE-942: Overly Permissive Cross-domain Whitelist"
                })
            
            # Rate limiting
            if "RateLimiter" not in code and "rate_limit" not in code:
                vulnerabilities.append({
                    "severity": "medium",
                    "category": "api",
                    "title": "Missing Rate Limiting",
                    "description": "API endpoints lack rate limiting",
                    "impact": "Vulnerable to DoS attacks and brute force",
                    "remediation": "Implement rate limiting on all API endpoints",
                    "file": "server.py",
                    "cwe": "CWE-770: Allocation of Resources Without Limits"
                })
        
        # Check API routers for auth
        router_files = list(self.backend_root.glob("routers/*.py"))
        
        for router_file in router_files:
            with open(router_file, 'r') as f:
                code = f.read()
            
            # Public endpoints without auth
            if "@router.post" in code or "@router.put" in code or "@router.delete" in code:
                if "Depends(" not in code and "auth" not in code.lower():
                    # Check if it's intentionally public
                    if "public" not in router_file.name and "webhook" not in router_file.name:
                        vulnerabilities.append({
                            "severity": "medium",
                            "category": "api",
                            "title": "Potentially Unprotected API Endpoint",
                            "description": f"{router_file.name} has POST/PUT/DELETE without auth dependency",
                            "impact": "Unauthorized users may access sensitive operations",
                            "remediation": "Add auth dependency: Depends(get_current_user)",
                            "file": str(router_file),
                            "cwe": "CWE-306: Missing Authentication for Critical Function"
                        })
        
        return vulnerabilities
    
    async def _scan_owasp_backend(self) -> List[Dict]:
        """Scan for OWASP Top 10 vulnerabilities"""
        vulnerabilities = []
        
        # A01:2021 – Broken Access Control
        # Check for direct object references
        router_files = list(self.backend_root.glob("routers/*.py"))
        
        for router_file in router_files:
            with open(router_file, 'r') as f:
                code = f.read()
            
            # User ID in path without ownership check
            if re.search(r'@router\.(get|put|delete)\(["\'].*\{user_id\}', code):
                if "current_user" not in code:
                    vulnerabilities.append({
                        "severity": "high",
                        "category": "access_control",
                        "title": "Potential IDOR Vulnerability",
                        "description": "User ID in path without ownership verification",
                        "impact": "Users may access/modify other users' data",
                        "remediation": "Verify current_user.id == user_id before operations",
                        "file": str(router_file),
                        "cwe": "CWE-639: Insecure Direct Object Reference"
                    })
        
        # A03:2021 – Injection
        # Check for NoSQL injection
        service_files = list(self.backend_root.glob("services/*.py"))
        
        for service_file in service_files:
            with open(service_file, 'r') as f:
                code = f.read()
            
            # Direct string concatenation in queries
            if ".find({" in code or ".update({" in code:
                if "f\"" in code or "f'" in code:
                    vulnerabilities.append({
                        "severity": "high",
                        "category": "injection",
                        "title": "Potential NoSQL Injection",
                        "description": "String formatting in MongoDB queries",
                        "impact": "Attackers may manipulate database queries",
                        "remediation": "Use parameterized queries, validate input",
                        "file": str(service_file),
                        "cwe": "CWE-943: Improper Neutralization of Special Elements in Data Query Logic"
                    })
        
        return vulnerabilities
    
    async def _scan_frontend_security(self) -> List[Dict]:
        """Scan frontend security"""
        vulnerabilities = []
        
        # Check for exposed secrets in frontend
        env_file = self.frontend_root / ".env"
        
        if env_file.exists():
            with open(env_file, 'r') as f:
                env_content = f.read()
            
            # Secret keys in frontend env
            if re.search(r'(SECRET|PRIVATE|PASSWORD)', env_content, re.IGNORECASE):
                # Exclude REACT_APP_BACKEND_URL which is ok
                if "REACT_APP_BACKEND_URL" not in env_content:
                    vulnerabilities.append({
                        "severity": "critical",
                        "category": "frontend",
                        "title": "Secrets in Frontend Environment",
                        "description": "Secret keys found in frontend .env",
                        "impact": "Secrets exposed to users in browser",
                        "remediation": "Move secrets to backend, use backend proxy",
                        "file": "frontend/.env",
                        "cwe": "CWE-540: Information Exposure Through Source Code"
                    })
        
        # Check React components
        component_files = list(self.frontend_root.glob("src/**/*.jsx")) + \
                         list(self.frontend_root.glob("src/**/*.tsx"))
        
        for component_file in component_files[:10]:  # Sample first 10
            try:
                with open(component_file, 'r') as f:
                    code = f.read()
                
                # Hardcoded API keys
                if re.search(r'(api[_-]?key|token)\s*[:=]\s*["\'][A-Za-z0-9]{20,}["\']', code, re.IGNORECASE):
                    vulnerabilities.append({
                        "severity": "critical",
                        "category": "frontend",
                        "title": "Hardcoded API Key in Component",
                        "description": f"API key found in {component_file.name}",
                        "impact": "API keys exposed in browser source",
                        "remediation": "Use environment variables: process.env.REACT_APP_KEY",
                        "file": str(component_file),
                        "cwe": "CWE-798: Use of Hard-coded Credentials"
                    })
            except Exception:
                pass  # Skip unreadable files
        
        return vulnerabilities
    
    def _generate_recommendations(self, vulnerabilities: List[Dict]) -> List[Dict]:
        """Generate security recommendations based on findings"""
        recommendations = []
        
        # Group by category
        categories = set(v["category"] for v in vulnerabilities)
        
        for category in categories:
            count = len([v for v in vulnerabilities if v["category"] == category])
            
            if category == "authentication":
                recommendations.append({
                    "priority": "high",
                    "category": category,
                    "title": "Strengthen Authentication",
                    "actions": [
                        "Use strong JWT secrets (32+ random characters)",
                        "Implement password hashing with bcrypt",
                        "Add 2FA for admin accounts",
                        "Implement session timeout and renewal"
                    ],
                    "issues_found": count
                })
            
            elif category == "payment":
                recommendations.append({
                    "priority": "critical",
                    "category": category,
                    "title": "Secure Payment Processing",
                    "actions": [
                        "Never store Stripe keys in code",
                        "Verify webhook signatures",
                        "Validate all amounts server-side",
                        "Implement PCI DSS compliance"
                    ],
                    "issues_found": count
                })
            
            elif category == "api":
                recommendations.append({
                    "priority": "high",
                    "category": category,
                    "title": "API Security Hardening",
                    "actions": [
                        "Implement rate limiting (100 req/min)",
                        "Restrict CORS to trusted domains",
                        "Add authentication to all non-public endpoints",
                        "Enable API versioning"
                    ],
                    "issues_found": count
                })
        
        # General recommendations
        recommendations.append({
            "priority": "medium",
            "category": "general",
            "title": "Security Best Practices",
            "actions": [
                "Run security scans before every deployment",
                "Keep dependencies updated (npm audit, pip-audit)",
                "Enable HTTPS in production",
                "Implement security headers (CSP, HSTS, X-Frame-Options)",
                "Regular penetration testing"
            ]
        })
        
        return recommendations
    
    def _calculate_risk_score(self, vulnerabilities: List[Dict]) -> int:
        """Calculate overall risk score (0-100, higher = more risky)"""
        if not vulnerabilities:
            return 0
        
        score = 0
        
        for vuln in vulnerabilities:
            severity = vuln["severity"]
            
            if severity == "critical":
                score += 25
            elif severity == "high":
                score += 15
            elif severity == "medium":
                score += 7
            elif severity == "low":
                score += 3
        
        return min(100, score)
    
    def _get_risk_level(self, score: int) -> str:
        """Convert risk score to level"""
        if score >= 75:
            return "CRITICAL"
        elif score >= 50:
            return "HIGH"
        elif score >= 25:
            return "MEDIUM"
        else:
            return "LOW"
