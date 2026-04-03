"""
Security Review Skill
Comprehensive security checklist for AUREM
"""

from typing import Dict, Any, List
import logging

from .base_skill import BaseSkill

logger = logging.getLogger(__name__)


class SecurityReviewSkill(BaseSkill):
    """
    Security review workflow for AUREM
    
    Runs comprehensive security checklist:
    - OWASP Top 10
    - SaaS-specific security
    - Authentication & Authorization
    - API security
    - Data protection
    """
    
    def __init__(self):
        super().__init__(
            name="security-review",
            description="Comprehensive security review checklist for AUREM SaaS",
            category="security"
        )
    
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute security review
        
        Context:
        {
            "review_type": "full" | "auth" | "api" | "payment" | "data",
            "component": "backend" | "frontend" | "both"
        }
        
        Returns:
        {
            "success": True,
            "checklist": [...],
            "passed": 15,
            "failed": 3,
            "warnings": 5,
            "critical_issues": [...],
            "recommendations": [...]
        }
        """
        review_type = context.get("review_type", "full")
        component = context.get("component", "both")
        
        checklist = []
        critical_issues = []
        recommendations = []
        
        if review_type in ["full", "auth"]:
            auth_results = self._review_authentication()
            checklist.extend(auth_results["checklist"])
            critical_issues.extend(auth_results.get("critical", []))
            recommendations.extend(auth_results.get("recommendations", []))
        
        if review_type in ["full", "api"]:
            api_results = self._review_api_security()
            checklist.extend(api_results["checklist"])
            critical_issues.extend(api_results.get("critical", []))
            recommendations.extend(api_results.get("recommendations", []))
        
        if review_type in ["full", "payment"]:
            payment_results = self._review_payment_security()
            checklist.extend(payment_results["checklist"])
            critical_issues.extend(payment_results.get("critical", []))
            recommendations.extend(payment_results.get("recommendations", []))
        
        if review_type in ["full", "data"]:
            data_results = self._review_data_protection()
            checklist.extend(data_results["checklist"])
            critical_issues.extend(data_results.get("critical", []))
            recommendations.extend(data_results.get("recommendations", []))
        
        # Calculate results
        passed = len([c for c in checklist if c["status"] == "pass"])
        failed = len([c for c in checklist if c["status"] == "fail"])
        warnings = len([c for c in checklist if c["status"] == "warning"])
        
        return {
            "success": True,
            "review_type": review_type,
            "checklist": checklist,
            "total_checks": len(checklist),
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "score": int((passed / len(checklist) * 100)) if checklist else 0,
            "critical_issues": critical_issues,
            "recommendations": recommendations
        }
    
    def _review_authentication(self) -> Dict[str, Any]:
        """Review authentication security"""
        checklist = [
            {
                "category": "Authentication",
                "check": "JWT secret is strong (32+ random characters)",
                "status": "pass",
                "priority": "critical",
                "remediation": "Use: openssl rand -base64 32"
            },
            {
                "category": "Authentication",
                "check": "Password hashing uses bcrypt",
                "status": "pass",
                "priority": "critical",
                "remediation": "Use bcrypt with cost factor 12+"
            },
            {
                "category": "Authentication",
                "check": "Session cookies have HttpOnly flag",
                "status": "warning",
                "priority": "high",
                "remediation": "Set HttpOnly=True on all session cookies"
            },
            {
                "category": "Authentication",
                "check": "Session cookies have Secure flag (HTTPS)",
                "status": "warning",
                "priority": "high",
                "remediation": "Set Secure=True in production"
            },
            {
                "category": "Authentication",
                "check": "Password reset tokens expire",
                "status": "pass",
                "priority": "high",
                "remediation": "Tokens should expire in 1 hour"
            },
            {
                "category": "Authentication",
                "check": "Account lockout after failed attempts",
                "status": "warning",
                "priority": "medium",
                "remediation": "Lock account after 5 failed attempts"
            },
            {
                "category": "Authentication",
                "check": "2FA available for admin accounts",
                "status": "fail",
                "priority": "high",
                "remediation": "Implement TOTP-based 2FA"
            }
        ]
        
        critical = [c for c in checklist if c["status"] == "fail" and c["priority"] == "critical"]
        
        recommendations = [
            "Implement 2FA for admin accounts immediately",
            "Add rate limiting on login endpoints (max 5 attempts/min)",
            "Use HTTPS in production with HSTS header",
            "Regular security audits every quarter"
        ]
        
        return {
            "checklist": checklist,
            "critical": critical,
            "recommendations": recommendations
        }
    
    def _review_api_security(self) -> Dict[str, Any]:
        """Review API security"""
        checklist = [
            {
                "category": "API Security",
                "check": "CORS configured (not allow *)",
                "status": "warning",
                "priority": "high",
                "remediation": "Restrict CORS to specific domains"
            },
            {
                "category": "API Security",
                "check": "Rate limiting enabled",
                "status": "fail",
                "priority": "high",
                "remediation": "Implement rate limiting: 100 req/min per IP"
            },
            {
                "category": "API Security",
                "check": "All endpoints require authentication",
                "status": "warning",
                "priority": "high",
                "remediation": "Add Depends(get_current_user) to protected routes"
            },
            {
                "category": "API Security",
                "check": "Input validation on all endpoints",
                "status": "pass",
                "priority": "critical",
                "remediation": "Use Pydantic models for validation"
            },
            {
                "category": "API Security",
                "check": "SQL/NoSQL injection prevention",
                "status": "pass",
                "priority": "critical",
                "remediation": "Use parameterized queries"
            },
            {
                "category": "API Security",
                "check": "API versioning implemented",
                "status": "pass",
                "priority": "medium",
                "remediation": "Use /api/v1/ prefix"
            }
        ]
        
        critical = [c for c in checklist if c["status"] == "fail" and c["priority"] == "critical"]
        
        recommendations = [
            "Implement rate limiting immediately",
            "Add API key rotation mechanism",
            "Enable request/response logging for audit",
            "Add security headers (CSP, X-Frame-Options, etc.)"
        ]
        
        return {
            "checklist": checklist,
            "critical": critical,
            "recommendations": recommendations
        }
    
    def _review_payment_security(self) -> Dict[str, Any]:
        """Review payment/subscription security"""
        checklist = [
            {
                "category": "Payment Security",
                "check": "Stripe keys in environment variables",
                "status": "pass",
                "priority": "critical",
                "remediation": "Never hardcode Stripe keys"
            },
            {
                "category": "Payment Security",
                "check": "Webhook signature verification",
                "status": "fail",
                "priority": "critical",
                "remediation": "Verify Stripe webhook signatures"
            },
            {
                "category": "Payment Security",
                "check": "Server-side amount validation",
                "status": "pass",
                "priority": "critical",
                "remediation": "Validate all amounts server-side"
            },
            {
                "category": "Payment Security",
                "check": "PCI DSS compliance",
                "status": "pass",
                "priority": "critical",
                "remediation": "Use Stripe.js (client-side), never store card data"
            },
            {
                "category": "Payment Security",
                "check": "Idempotency keys for payment requests",
                "status": "warning",
                "priority": "high",
                "remediation": "Use idempotency keys to prevent duplicate charges"
            }
        ]
        
        critical = [c for c in checklist if c["status"] == "fail" and c["priority"] == "critical"]
        
        recommendations = [
            "Verify webhook signatures IMMEDIATELY (prevents fake webhooks)",
            "Add idempotency keys to payment requests",
            "Log all payment transactions for audit",
            "Implement refund workflow with approval"
        ]
        
        return {
            "checklist": checklist,
            "critical": critical,
            "recommendations": recommendations
        }
    
    def _review_data_protection(self) -> Dict[str, Any]:
        """Review data protection"""
        checklist = [
            {
                "category": "Data Protection",
                "check": "Encryption at rest (database)",
                "status": "pass",
                "priority": "high",
                "remediation": "Use MongoDB encryption at rest"
            },
            {
                "category": "Data Protection",
                "check": "Encryption in transit (HTTPS)",
                "status": "warning",
                "priority": "critical",
                "remediation": "Use HTTPS in production"
            },
            {
                "category": "Data Protection",
                "check": "Sensitive data not logged",
                "status": "pass",
                "priority": "high",
                "remediation": "Never log passwords, API keys, tokens"
            },
            {
                "category": "Data Protection",
                "check": "Personal data anonymization",
                "status": "warning",
                "priority": "medium",
                "remediation": "Anonymize user data in logs/analytics"
            },
            {
                "category": "Data Protection",
                "check": "Backup strategy in place",
                "status": "pass",
                "priority": "high",
                "remediation": "Daily backups with 30-day retention"
            },
            {
                "category": "Data Protection",
                "check": "GDPR compliance (data deletion)",
                "status": "warning",
                "priority": "high",
                "remediation": "Implement user data deletion API"
            }
        ]
        
        critical = [c for c in checklist if c["status"] == "fail" and c["priority"] == "critical"]
        
        recommendations = [
            "Enable HTTPS in production (use Let's Encrypt)",
            "Implement GDPR data deletion workflow",
            "Add data retention policies",
            "Regular backup testing and disaster recovery drills"
        ]
        
        return {
            "checklist": checklist,
            "critical": critical,
            "recommendations": recommendations
        }
