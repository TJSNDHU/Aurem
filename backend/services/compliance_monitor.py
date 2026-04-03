"""
Health Canada Compliance Monitor
═══════════════════════════════════════════════════════════════════
Scans content for Health Canada cosmetic claim violations and 
Competition Act issues before publishing.

CRITICAL violations block content. WARNING issues allow but flag.
═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

import os
import re
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# SEVERITY LEVELS
# ═══════════════════════════════════════════════════════════════════

class Severity(str, Enum):
    CRITICAL = "CRITICAL"  # Blocks publishing - illegal claims
    WARNING = "WARNING"    # Allows but flags - brand voice issues
    PASS = "PASS"          # No issues found


# ═══════════════════════════════════════════════════════════════════
# BANNED PHRASES - CRITICAL (Block Publishing)
# ═══════════════════════════════════════════════════════════════════
# Health Canada prohibits cosmetic claims that imply drug-like effects

BANNED_PHRASES = [
    # Drug-like claims
    "cures",
    "treats",
    "heals",
    "eliminates disease",
    "kills bacteria",
    "kills acne",
    "kills germs",
    "antibacterial",
    "antimicrobial",
    
    # Regulatory claims
    "fda approved",
    "health canada approved",
    "clinically proven to cure",
    "prescription strength",
    "medical grade",
    "pharmaceutical grade",
    
    # Absolute guarantees
    "guaranteed results",
    "permanent results",
    "100% effective",
    "completely eliminates",
    "total removal",
    
    # Disease treatment claims
    "eczema treatment",
    "eczema cure",
    "rosacea cure",
    "rosacea treatment", 
    "psoriasis treatment",
    "psoriasis cure",
    "dermatitis treatment",
    "acne treatment",
    "acne cure",
    
    # Other violations
    "prevents cancer",
    "prevents disease",
    "boosts immunity",
    "detoxifies",
    "detox",
    
    # Business rule violations - PERMANENTLY REMOVED PROMOTIONS
    "founder's launch subsidy",
    "founders launch subsidy",
    "50% founder",
    "founder discount",
    "launch subsidy",
]

# Regex patterns for CRITICAL issues
BANNED_PATTERNS = [
    r"\b100\s*%\s*(effective|guaranteed|cure|results)\b",
    r"\bcompletely\s+(eliminates?|removes?|cures?)\b",
    r"\bpermanently\s+(removes?|eliminates?)\b",
    r"\bmedically\s+proven\b",
    r"\bclinically\s+proven\s+to\s+(cure|treat|heal)\b",
]


# ═══════════════════════════════════════════════════════════════════
# BRAND VOICE FIXES - WARNING (Allow but Flag)
# ═══════════════════════════════════════════════════════════════════
# These aren't illegal but should use approved brand language

BRAND_VOICE_REPLACEMENTS = {
    # Anti-aging terminology
    "anti-aging": "age recovery",
    "anti-ageing": "age recovery", 
    "antiaging": "age recovery",
    "antiageing": "age recovery",
    
    # Skin tone terminology
    "whitening": "brightening",
    "skin whitening": "skin brightening",
    "bleaching": "brightening",
    "lightening": "brightening",
    
    # Wrinkle claims
    "eliminates wrinkles": "visibly reduces the appearance of fine lines",
    "removes wrinkles": "visibly reduces the appearance of fine lines",
    "erases wrinkles": "visibly reduces the appearance of fine lines",
    "gets rid of wrinkles": "visibly reduces the appearance of fine lines",
    
    # Other softening
    "removes dark spots": "visibly reduces the appearance of dark spots",
    "eliminates dark spots": "helps fade the appearance of dark spots",
    "stops aging": "supports skin's natural renewal process",
    "reverses aging": "supports age recovery",
    "fights aging": "supports age recovery",
}


# ═══════════════════════════════════════════════════════════════════
# COMPLIANCE SCANNER
# ═══════════════════════════════════════════════════════════════════

class ComplianceMonitor:
    """
    Scans content for Health Canada compliance issues.
    
    Usage:
        monitor = ComplianceMonitor(db)
        result = await monitor.scan_content(text, content_type="instagram")
        if result["blocked"]:
            # Don't allow publishing
    """
    
    def __init__(self, db=None):
        self.db = db
        self.collection_name = "compliance_scans"
    
    def _check_banned_phrases(self, text: str) -> List[Dict[str, Any]]:
        """Check for CRITICAL banned phrases."""
        issues = []
        text_lower = text.lower()
        
        for phrase in BANNED_PHRASES:
            if phrase.lower() in text_lower:
                # Find the actual occurrence for context
                pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                matches = pattern.finditer(text)
                for match in matches:
                    # Get surrounding context (50 chars each side)
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end]
                    
                    issues.append({
                        "type": "banned_phrase",
                        "severity": Severity.CRITICAL,
                        "phrase": phrase,
                        "context": f"...{context}...",
                        "position": match.start(),
                        "reason": f"Health Canada prohibits cosmetic claims using '{phrase}'"
                    })
        
        return issues
    
    def _check_banned_patterns(self, text: str) -> List[Dict[str, Any]]:
        """Check for CRITICAL banned regex patterns."""
        issues = []
        
        for pattern in BANNED_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end]
                
                issues.append({
                    "type": "banned_pattern",
                    "severity": Severity.CRITICAL,
                    "phrase": match.group(),
                    "context": f"...{context}...",
                    "position": match.start(),
                    "reason": "This claim pattern violates Health Canada cosmetic regulations"
                })
        
        return issues
    
    def _check_brand_voice(self, text: str) -> List[Dict[str, Any]]:
        """Check for WARNING brand voice issues."""
        issues = []
        text_lower = text.lower()
        
        for bad_phrase, good_phrase in BRAND_VOICE_REPLACEMENTS.items():
            if bad_phrase.lower() in text_lower:
                pattern = re.compile(re.escape(bad_phrase), re.IGNORECASE)
                matches = pattern.finditer(text)
                for match in matches:
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 30)
                    context = text[start:end]
                    
                    issues.append({
                        "type": "brand_voice",
                        "severity": Severity.WARNING,
                        "phrase": bad_phrase,
                        "suggested": good_phrase,
                        "context": f"...{context}...",
                        "position": match.start(),
                        "reason": f"Brand voice: consider using '{good_phrase}' instead of '{bad_phrase}'"
                    })
        
        return issues
    
    async def scan_content(
        self,
        content: str,
        content_type: str = "general",
        content_id: Optional[str] = None,
        save_scan: bool = True
    ) -> Dict[str, Any]:
        """
        Scan content for compliance issues.
        
        Args:
            content: Text content to scan
            content_type: Type of content (instagram, email, website, etc.)
            content_id: Optional ID to track this content
            save_scan: Whether to save scan results to database
            
        Returns:
            {
                "compliant": bool,
                "severity": "CRITICAL" | "WARNING" | "PASS",
                "issues": [...],
                "blocked": bool,
                "scan_id": str,
                "scanned_at": datetime
            }
        """
        if not content or not content.strip():
            return {
                "compliant": True,
                "severity": Severity.PASS,
                "issues": [],
                "blocked": False,
                "message": "No content to scan"
            }
        
        all_issues = []
        
        # Check banned phrases (CRITICAL)
        all_issues.extend(self._check_banned_phrases(content))
        
        # Check banned patterns (CRITICAL)
        all_issues.extend(self._check_banned_patterns(content))
        
        # Check brand voice (WARNING)
        all_issues.extend(self._check_brand_voice(content))
        
        # Determine overall severity
        has_critical = any(i["severity"] == Severity.CRITICAL for i in all_issues)
        has_warning = any(i["severity"] == Severity.WARNING for i in all_issues)
        
        if has_critical:
            severity = Severity.CRITICAL
            blocked = True
            compliant = False
        elif has_warning:
            severity = Severity.WARNING
            blocked = False
            compliant = True  # Compliant but with suggestions
        else:
            severity = Severity.PASS
            blocked = False
            compliant = True
        
        result = {
            "compliant": compliant,
            "severity": severity,
            "issues": all_issues,
            "blocked": blocked,
            "issue_count": len(all_issues),
            "critical_count": sum(1 for i in all_issues if i["severity"] == Severity.CRITICAL),
            "warning_count": sum(1 for i in all_issues if i["severity"] == Severity.WARNING),
            "content_type": content_type,
            "content_preview": content[:200] + "..." if len(content) > 200 else content,
            "scanned_at": datetime.now(timezone.utc)
        }
        
        # Save scan to database
        if save_scan and self.db is not None:
            scan_doc = {
                **result,
                "content_id": content_id,
                "content_hash": hash(content),
                "severity": str(severity),
                "issues": [
                    {**i, "severity": str(i["severity"])} for i in all_issues
                ]
            }
            insert_result = await self.db[self.collection_name].insert_one(scan_doc)
            result["scan_id"] = str(insert_result.inserted_id)
        
        logger.info(
            f"[COMPLIANCE] Scan complete: {severity} - "
            f"{result['critical_count']} critical, {result['warning_count']} warnings"
        )
        
        return result
    
    async def scan_before_publish(
        self,
        content: str,
        content_type: str = "general",
        content_id: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Scan content before publishing. Returns (can_publish, scan_result).
        
        Usage:
            can_publish, result = await monitor.scan_before_publish(text)
            if not can_publish:
                return {"error": "Content blocked", "issues": result["issues"]}
        """
        result = await self.scan_content(content, content_type, content_id)
        can_publish = not result["blocked"]
        return can_publish, result
    
    async def deep_scan_with_ai(
        self,
        content: str,
        content_type: str = "general"
    ) -> Dict[str, Any]:
        """
        Use Claude AI for deep compliance analysis.
        Catches nuanced violations the regex scanner might miss.
        """
        # First run the basic scan
        basic_result = await self.scan_content(content, content_type, save_scan=False)
        
        # Then do AI deep scan
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            
            api_key = os.environ.get("EMERGENT_LLM_KEY", "")
            if not api_key:
                logger.warning("[COMPLIANCE] No EMERGENT_LLM_KEY, skipping AI deep scan")
                return basic_result
            
            chat = LlmChat(
                api_key=api_key,
                system_message="""You are a Health Canada cosmetic compliance expert.
                
Analyze the provided content for:
1. Health Canada cosmetic claim violations (claims that imply drug-like effects)
2. Competition Act issues (false/misleading advertising)
3. Natural Health Products Regulations violations

Return a JSON object with:
{
    "ai_issues": [
        {
            "severity": "CRITICAL" or "WARNING",
            "phrase": "the problematic text",
            "reason": "why this is a violation",
            "regulation": "which regulation it violates"
        }
    ],
    "overall_assessment": "brief summary"
}

Be strict but fair. Only flag actual compliance issues, not general writing suggestions."""
            )
            chat.with_model("anthropic", "claude-sonnet-4-20250514")
            
            prompt = f"""Analyze this {content_type} content for Health Canada compliance:

---
{content}
---

Return ONLY valid JSON, no other text."""
            
            response = await chat.send_message(UserMessage(text=prompt))
            
            # Parse AI response
            import json
            try:
                # Extract JSON from response
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    ai_result = json.loads(json_match.group())
                    ai_issues = ai_result.get("ai_issues", [])
                    
                    # Merge AI issues with basic scan
                    for issue in ai_issues:
                        # Avoid duplicates
                        if not any(
                            existing["phrase"].lower() == issue.get("phrase", "").lower()
                            for existing in basic_result["issues"]
                        ):
                            basic_result["issues"].append({
                                "type": "ai_detected",
                                "severity": Severity.CRITICAL if issue.get("severity") == "CRITICAL" else Severity.WARNING,
                                "phrase": issue.get("phrase", ""),
                                "reason": issue.get("reason", ""),
                                "regulation": issue.get("regulation", ""),
                                "context": ""
                            })
                    
                    # Update counts
                    basic_result["ai_assessment"] = ai_result.get("overall_assessment", "")
                    basic_result["critical_count"] = sum(
                        1 for i in basic_result["issues"] 
                        if i["severity"] == Severity.CRITICAL or i["severity"] == "CRITICAL"
                    )
                    basic_result["warning_count"] = sum(
                        1 for i in basic_result["issues"] 
                        if i["severity"] == Severity.WARNING or i["severity"] == "WARNING"
                    )
                    
                    # Update blocked status if AI found critical issues
                    if basic_result["critical_count"] > 0:
                        basic_result["blocked"] = True
                        basic_result["compliant"] = False
                        basic_result["severity"] = Severity.CRITICAL
                    
            except json.JSONDecodeError:
                logger.warning("[COMPLIANCE] Could not parse AI response as JSON")
                basic_result["ai_assessment"] = response
                
        except Exception as e:
            logger.error(f"[COMPLIANCE] AI deep scan failed: {e}")
            basic_result["ai_error"] = str(e)
        
        return basic_result
    
    async def get_scan_history(
        self,
        limit: int = 50,
        severity_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent compliance scan history."""
        if self.db is None:
            return []
        
        query = {}
        if severity_filter:
            query["severity"] = severity_filter
        
        cursor = self.db[self.collection_name].find(
            query,
            {"_id": 0, "content_hash": 0}
        ).sort("scanned_at", -1).limit(limit)
        
        return await cursor.to_list(limit)
    
    async def get_compliance_stats(self) -> Dict[str, Any]:
        """Get compliance scanning statistics."""
        if self.db is None:
            return {}
        
        pipeline = [
            {
                "$group": {
                    "_id": "$severity",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        results = await self.db[self.collection_name].aggregate(pipeline).to_list(10)
        
        stats = {
            "total_scans": 0,
            "critical": 0,
            "warning": 0,
            "pass": 0
        }
        
        for r in results:
            severity = r["_id"]
            count = r["count"]
            stats["total_scans"] += count
            if severity == "CRITICAL":
                stats["critical"] = count
            elif severity == "WARNING":
                stats["warning"] = count
            elif severity == "PASS":
                stats["pass"] = count
        
        if stats["total_scans"] > 0:
            stats["compliance_rate"] = round(
                (stats["pass"] / stats["total_scans"]) * 100, 1
            )
        else:
            stats["compliance_rate"] = 100.0
        
        return stats


# ═══════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════

_compliance_monitor = None

def get_compliance_monitor(db=None):
    """Get or create compliance monitor instance."""
    global _compliance_monitor
    if _compliance_monitor is None or db is not None:
        _compliance_monitor = ComplianceMonitor(db)
    return _compliance_monitor
