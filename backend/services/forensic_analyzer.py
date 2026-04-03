"""
ORA Forensic Analyzer
AI-Powered Root Cause Analysis using GPT-4o Vision

Capabilities:
- Screenshot analysis (UI errors, console logs, broken layouts)
- Error message extraction and classification
- Component identification
- API route detection
- Database query analysis
"""

import os
import logging
import base64
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ForensicAnalysisResult(BaseModel):
    """Result from forensic analysis"""
    analysis_id: str
    timestamp: datetime
    
    # Image Analysis
    image_description: str
    detected_error_type: str  # "runtime", "ui_broken", "api_failure", "database", "unknown"
    error_messages: List[str]
    affected_components: List[str]
    
    # Code Trace
    suspected_files: List[str]
    suspected_functions: List[str]
    api_routes_involved: List[str]
    
    # Root Cause
    root_cause_hypothesis: str
    confidence_score: float  # 0.0 to 1.0
    
    # Recommended Actions
    recommended_fixes: List[str]
    requires_database_change: bool
    estimated_complexity: str  # "simple", "medium", "complex"
    
    # Raw GPT Response
    raw_analysis: str


class ForensicAnalyzer:
    """
    AI-Powered Forensic Analysis Engine
    
    Uses GPT-4o Vision to analyze screenshots and error logs,
    then traces the issue back to source code.
    """
    
    def __init__(self, db=None):
        self.db = db
        self.api_key = os.environ.get("EMERGENT_LLM_KEY", "")
        
        if not self.api_key:
            logger.warning("[FORENSIC] EMERGENT_LLM_KEY not set - Vision analysis disabled")
    
    async def analyze_screenshot(
        self,
        image_base64: str,
        context: str = "",
        user_description: str = ""
    ) -> ForensicAnalysisResult:
        """
        Analyze screenshot using GPT-4o Vision
        
        Args:
            image_base64: Base64 encoded image (PNG/JPEG/WEBP)
            context: Optional context (e.g., "login flow", "checkout page")
            user_description: Optional user-provided description
            
        Returns:
            ForensicAnalysisResult with detailed analysis
        """
        from uuid import uuid4
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        
        analysis_id = str(uuid4())
        
        # Build analysis prompt
        prompt = self._build_vision_analysis_prompt(context, user_description)
        
        try:
            # Initialize GPT-4o Vision
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"forensic-{analysis_id}",
                system_message="You are ORA, an AI forensic engineer specializing in debugging web applications. Analyze images to identify bugs, errors, and root causes."
            ).with_model("openai", "gpt-5.1")
            
            # Create message with image
            image_content = ImageContent(image_base64=image_base64)
            message = UserMessage(
                text=prompt,
                file_contents=[image_content]
            )
            
            # Get analysis
            response = await chat.send_message(message)
            
            # Parse GPT response
            result = self._parse_vision_response(response, analysis_id)
            
            # Store analysis in database
            if self.db is not None:
                await self.db.aurem_forensic_analyses.insert_one(result.dict())
            
            logger.info(f"[FORENSIC] Analysis complete: {result.detected_error_type} (confidence: {result.confidence_score})")
            
            return result
            
        except Exception as e:
            logger.error(f"[FORENSIC] Analysis failed: {str(e)}")
            raise
    
    async def analyze_text_error(
        self,
        error_log: str,
        context: str = ""
    ) -> ForensicAnalysisResult:
        """
        Analyze text error logs without image
        
        Args:
            error_log: Error message or stack trace
            context: Optional context
            
        Returns:
            ForensicAnalysisResult
        """
        from uuid import uuid4
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        analysis_id = str(uuid4())
        
        prompt = f"""
Analyze this error log and provide forensic analysis:

Context: {context or 'Not provided'}

Error Log:
```
{error_log}
```

Provide analysis in this JSON format:
{{
  "error_type": "runtime|api_failure|database|syntax|unknown",
  "error_messages": ["list of error messages"],
  "affected_components": ["component names"],
  "suspected_files": ["/path/to/file.py"],
  "suspected_functions": ["function_name"],
  "api_routes_involved": ["/api/route"],
  "root_cause": "detailed hypothesis",
  "confidence": 0.0 to 1.0,
  "recommended_fixes": ["actionable steps"],
  "requires_db_change": true/false,
  "complexity": "simple|medium|complex"
}}
"""
        
        try:
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"forensic-text-{analysis_id}",
                system_message="You are ORA, an AI forensic engineer. Analyze error logs and identify root causes."
            ).with_model("openai", "gpt-5.1")
            
            response = await chat.send_message(UserMessage(text=prompt))
            
            # Parse response
            result = self._parse_text_response(response, analysis_id)
            
            # Store in DB
            if self.db is not None:
                await self.db.aurem_forensic_analyses.insert_one(result.dict())
            
            return result
            
        except Exception as e:
            logger.error(f"[FORENSIC] Text analysis failed: {str(e)}")
            raise
    
    def _build_vision_analysis_prompt(self, context: str, user_description: str) -> str:
        """Build comprehensive prompt for GPT-4o Vision"""
        return f"""
You are ORA, an AI Forensic Engineer analyzing a screenshot from the AUREM Business Operating System.

**Context:** {context or 'Not provided'}
**User Description:** {user_description or 'Not provided'}

**Your Task:**
Analyze this screenshot and identify any bugs, errors, or issues. Provide a detailed forensic analysis.

**Look for:**
1. Error messages (console errors, HTTP errors, exceptions)
2. Broken UI elements (missing data, misaligned components, white screens)
3. API failures (network errors, 404s, 500s)
4. Component rendering issues
5. Data flow problems

**Provide analysis in this JSON format:**
{{
  "image_description": "Brief description of what you see in the screenshot",
  "error_type": "runtime|ui_broken|api_failure|database|unknown",
  "error_messages": ["Extract any visible error messages"],
  "affected_components": ["Component names visible in the UI"],
  "suspected_files": ["/app/frontend/src/Component.jsx or /app/backend/routes/api.py"],
  "suspected_functions": ["Function names that might be involved"],
  "api_routes_involved": ["/api/route/path"],
  "root_cause": "Your hypothesis about the root cause",
  "confidence": 0.85,
  "recommended_fixes": ["Specific actionable steps to fix this"],
  "requires_db_change": false,
  "complexity": "simple|medium|complex"
}}

**Important:**
- Be specific with file paths (use /app/backend/ or /app/frontend/ prefix)
- Identify React component names if visible
- Extract exact error messages if present
- Consider full-stack implications (frontend → API → database)
"""
    
    def _parse_vision_response(self, response: str, analysis_id: str) -> ForensicAnalysisResult:
        """Parse GPT-4o Vision response into structured result"""
        import json
        
        # Try to extract JSON from response
        try:
            # Find JSON block
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "{" in response:
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
            else:
                raise ValueError("No JSON found in response")
            
            data = json.loads(json_str)
            
            return ForensicAnalysisResult(
                analysis_id=analysis_id,
                timestamp=datetime.now(timezone.utc),
                image_description=data.get("image_description", "N/A"),
                detected_error_type=data.get("error_type", "unknown"),
                error_messages=data.get("error_messages", []),
                affected_components=data.get("affected_components", []),
                suspected_files=data.get("suspected_files", []),
                suspected_functions=data.get("suspected_functions", []),
                api_routes_involved=data.get("api_routes_involved", []),
                root_cause_hypothesis=data.get("root_cause", "Unknown"),
                confidence_score=float(data.get("confidence", 0.5)),
                recommended_fixes=data.get("recommended_fixes", []),
                requires_database_change=data.get("requires_db_change", False),
                estimated_complexity=data.get("complexity", "medium"),
                raw_analysis=response
            )
            
        except Exception as e:
            logger.warning(f"[FORENSIC] Failed to parse JSON response: {e}")
            # Fallback: return basic result
            return ForensicAnalysisResult(
                analysis_id=analysis_id,
                timestamp=datetime.now(timezone.utc),
                image_description="Analysis completed but JSON parsing failed",
                detected_error_type="unknown",
                error_messages=[],
                affected_components=[],
                suspected_files=[],
                suspected_functions=[],
                api_routes_involved=[],
                root_cause_hypothesis=response[:500],
                confidence_score=0.3,
                recommended_fixes=[],
                requires_database_change=False,
                estimated_complexity="medium",
                raw_analysis=response
            )
    
    def _parse_text_response(self, response: str, analysis_id: str) -> ForensicAnalysisResult:
        """Parse text error analysis response"""
        # Similar parsing logic as vision response
        return self._parse_vision_response(response, analysis_id)


# Singleton
_forensic_analyzer = None

def get_forensic_analyzer(db=None):
    global _forensic_analyzer
    if _forensic_analyzer is None:
        _forensic_analyzer = ForensicAnalyzer(db)
    elif db and _forensic_analyzer.db is None:
        _forensic_analyzer.db = db
    return _forensic_analyzer
