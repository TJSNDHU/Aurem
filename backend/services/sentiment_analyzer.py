"""
Sentiment Analyzer Service
AI-powered emotion detection for conversation monitoring

Uses GPT-4o to analyze customer sentiment in real-time and detect:
- Negative emotions (frustration, anger, disappointment)
- Explicit requests for human assistance
- Escalation language (refund, cancel, complaint)

Universal system that works for ANY industry.
"""

import logging
import os
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Emergent LLM Key (GPT-4o)
EMERGENT_LLM_KEY = os.getenv("EMERGENT_LLM_KEY", "sk-emergent-0D2C22421Cb5436270")

# Universal panic keywords (work across all industries)
UNIVERSAL_PANIC_KEYWORDS = [
    # Explicit human requests
    "human", "real person", "speak to someone", "talk to manager", 
    "speak to owner", "actual person", "representative",
    
    # Frustration indicators
    "frustrated", "frustrating", "annoyed", "annoying", "upset",
    "angry", "mad", "terrible", "horrible", "awful", "worst",
    
    # Escalation language
    "refund", "money back", "cancel", "unsubscribe", "complaint",
    "lawyer", "attorney", "sue", "legal action", "report",
    "review", "bad review", "1 star", "scam", "fraud", "fake",
    
    # Problem indicators
    "not working", "doesn't work", "broken", "error", "bug",
    "wrong", "incorrect", "mistake", "problem", "issue"
]


class SentimentAnalyzer:
    """Analyzes conversation sentiment using AI"""
    
    def __init__(self):
        self.openai_client = None
        self._init_openai()
    
    def _init_openai(self):
        """Initialize OpenAI client with Emergent LLM key"""
        try:
            # Use emergentintegrations for Emergent LLM Key
            from emergentintegrations.llm.chat import LlmChat
            # Create a client instance with required parameters
            self.openai_client = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id="sentiment_analyzer",
                system_message="You are a sentiment analysis expert. Respond only with valid JSON."
            )
            self.using_emergent = True
            logger.info("[SentimentAnalyzer] Initialized with Emergent LLM Key (emergentintegrations)")
        except ImportError:
            logger.warning("[SentimentAnalyzer] emergentintegrations not available, using fallback")
            self.openai_client = None
            self.using_emergent = False
        except Exception as e:
            logger.error(f"[SentimentAnalyzer] Init error: {e}")
            self.openai_client = None
            self.using_emergent = False
    
    async def analyze_message(
        self, 
        message: str, 
        conversation_history: Optional[List[Dict]] = None,
        custom_keywords: Optional[List[str]] = None
    ) -> Dict:
        """
        Analyze a single message for sentiment and panic triggers
        
        Args:
            message: The customer's message
            conversation_history: Previous messages for context
            custom_keywords: Tenant-specific panic keywords
        
        Returns:
            {
                "sentiment_score": float,  # -1.0 to 1.0
                "sentiment_label": str,    # "positive", "neutral", "concerned", "panic"
                "emotion": str,            # "happy", "neutral", "frustrated", "angry"
                "is_panic": bool,
                "panic_triggers": List[str],  # Why it triggered
                "detected_keywords": List[str],
                "needs_human": bool,
                "confidence": float
            }
        """
        if not self.openai_client:
            logger.warning("[SentimentAnalyzer] OpenAI not available, using fallback")
            return self._fallback_analysis(message, custom_keywords)
        
        try:
            # Quick keyword check first (faster than API call)
            keyword_check = self._check_keywords(message, custom_keywords)
            
            # If obvious panic keywords, skip expensive AI call
            if keyword_check["is_panic"] and keyword_check["confidence"] > 0.9:
                return keyword_check
            
            # AI-powered sentiment analysis
            ai_result = await self._analyze_with_gpt4o(message, conversation_history)
            
            # Merge AI analysis with keyword detection
            final_result = {
                **ai_result,
                "detected_keywords": keyword_check["detected_keywords"],
            }
            
            # Override if keywords found (keywords are high confidence)
            if keyword_check["detected_keywords"]:
                final_result["is_panic"] = True
                final_result["panic_triggers"].extend(keyword_check["panic_triggers"])
            
            return final_result
        
        except Exception as e:
            logger.error(f"[SentimentAnalyzer] Analysis error: {e}")
            return self._fallback_analysis(message, custom_keywords)
    
    async def _analyze_with_gpt4o(
        self, 
        message: str, 
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:
        """Use GPT-4o to analyze sentiment with language detection"""
        
        # Build context from conversation history
        context = ""
        if conversation_history:
            recent = conversation_history[-3:]  # Last 3 messages
            context = "\n".join([
                f"{msg.get('role', 'user')}: {msg.get('content', '')}" 
                for msg in recent
            ])
        
        prompt = f"""You are a multilingual sentiment analysis expert. Analyze the following customer message and classify the emotion.

Context (recent conversation):
{context if context else "No prior context"}

Current Customer Message:
"{message}"

Analyze and respond with JSON:
{{
  "sentiment_score": <float between -1.0 (very negative) and 1.0 (very positive)>,
  "emotion": "<happy|satisfied|neutral|concerned|frustrated|angry>",
  "needs_human": <true if customer explicitly or implicitly wants human help>,
  "detected_language": "<ISO 639-1 code: en, fr, es, zh, de, etc.>",
  "english_translation": "<English translation if not English, otherwise same as original>",
  "reasoning": "<brief explanation>"
}}

CRITICAL: 
- Detect the language of the customer message
- If not English, provide accurate English translation
- Sentiment analysis works regardless of language
- Focus on emotional tone, not just words

Respond ONLY with valid JSON, no other text."""

        try:
            # Use emergentintegrations LlmChat if available
            if hasattr(self, 'using_emergent') and self.using_emergent:
                from emergentintegrations.llm.chat import UserMessage
                response = await self.openai_client.with_model(
                    provider="openai",
                    model="gpt-4o"
                ).send_message(user_message=UserMessage(text=prompt))
                
                # Extract JSON from response (may be wrapped in markdown code blocks)
                import json
                import re
                
                # Remove markdown code blocks if present
                response_clean = response.strip()
                if response_clean.startswith('```'):
                    # Extract content between ```json and ``` or ``` and ```
                    match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response_clean, re.DOTALL)
                    if match:
                        response_clean = match.group(1)
                    else:
                        # Fallback: remove first and last line
                        lines = response_clean.split('\n')
                        response_clean = '\n'.join(lines[1:-1])
                
                result = json.loads(response_clean)
            else:
                # Fallback to standard OpenAI (if configured)
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a sentiment analysis expert. Respond only with valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=200
                )
                import json
                result = json.loads(response.choices[0].message.content)
            
            # Map to our format
            sentiment_score = result.get("sentiment_score", 0.0)
            emotion = result.get("emotion", "neutral")
            needs_human = result.get("needs_human", False)
            detected_language = result.get("detected_language", "en")
            english_translation = result.get("english_translation", message)
            
            # Determine panic state
            is_panic = sentiment_score < -0.7 or needs_human
            
            # Determine label
            if sentiment_score >= 0.3:
                label = "positive"
            elif sentiment_score >= -0.3:
                label = "neutral"
            elif sentiment_score >= -0.7:
                label = "concerned"
            else:
                label = "panic"
            
            panic_triggers = []
            if sentiment_score < -0.7:
                panic_triggers.append(f"negative_sentiment ({sentiment_score:.2f})")
            if needs_human:
                panic_triggers.append("explicit_human_request")
            
            return {
                "sentiment_score": sentiment_score,
                "sentiment_label": label,
                "emotion": emotion,
                "is_panic": is_panic,
                "panic_triggers": panic_triggers,
                "detected_keywords": [],
                "needs_human": needs_human,
                "confidence": 0.85,
                "reasoning": result.get("reasoning", ""),
                "detected_language": detected_language,
                "english_translation": english_translation
            }
        
        except Exception as e:
            logger.error(f"[SentimentAnalyzer] GPT-4o error: {e}")
            raise
    
    def _check_keywords(
        self, 
        message: str, 
        custom_keywords: Optional[List[str]] = None
    ) -> Dict:
        """Fast keyword-based panic detection with basic language detection"""
        
        message_lower = message.lower()
        
        # Basic language detection (simple heuristic)
        detected_language = "en"  # Default to English
        
        # French indicators
        if any(word in message_lower for word in ["je", "vous", "suis", "très", "merci"]):
            detected_language = "fr"
        # Spanish indicators
        elif any(word in message_lower for word in ["estoy", "muy", "por favor", "gracias"]):
            detected_language = "es"
        # German indicators
        elif any(word in message_lower for word in ["ich", "bin", "sehr", "danke"]):
            detected_language = "de"
        
        # Combine universal and custom keywords
        all_keywords = UNIVERSAL_PANIC_KEYWORDS.copy()
        if custom_keywords:
            all_keywords.extend([k.lower() for k in custom_keywords])
        
        # Check for matches
        detected = []
        for keyword in all_keywords:
            if keyword in message_lower:
                detected.append(keyword)
        
        # Determine panic state
        is_panic = len(detected) > 0
        
        # High confidence if explicit human request
        human_keywords = ["human", "real person", "speak to someone", "manager", "owner"]
        has_human_request = any(k in detected for k in human_keywords)
        
        confidence = 0.95 if has_human_request else (0.7 if detected else 0.0)
        
        panic_triggers = []
        if detected:
            panic_triggers.append(f"keywords: {', '.join(detected[:3])}")
        
        return {
            "sentiment_score": -0.8 if is_panic else 0.0,
            "sentiment_label": "panic" if is_panic else "neutral",
            "emotion": "frustrated" if is_panic else "neutral",
            "is_panic": is_panic,
            "panic_triggers": panic_triggers,
            "detected_keywords": detected,
            "needs_human": has_human_request,
            "confidence": confidence,
            "detected_language": detected_language,
            "english_translation": message  # Fallback doesn't translate
        }
    
    def _fallback_analysis(
        self, 
        message: str, 
        custom_keywords: Optional[List[str]] = None
    ) -> Dict:
        """Fallback keyword-only analysis when AI unavailable"""
        logger.info("[SentimentAnalyzer] Using fallback keyword analysis")
        return self._check_keywords(message, custom_keywords)


# Singleton instance
_sentiment_analyzer = None


def get_sentiment_analyzer() -> SentimentAnalyzer:
    """Get or create sentiment analyzer instance"""
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = SentimentAnalyzer()
    return _sentiment_analyzer


# Convenience function
async def analyze_message_sentiment(
    message: str,
    conversation_history: Optional[List[Dict]] = None,
    custom_keywords: Optional[List[str]] = None
) -> Dict:
    """
    Analyze message sentiment (convenience wrapper)
    
    Returns:
        Sentiment analysis result dict
    """
    analyzer = get_sentiment_analyzer()
    return await analyzer.analyze_message(message, conversation_history, custom_keywords)
