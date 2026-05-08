"""
AUREM Sentiment Analyzer — Extracted Service Core

AI-powered emotion detection for conversation monitoring.
Uses GPT-4o via Emergent LLM Key for real-time analysis.

Phase C: Decoupled from monolith, communicates via JSON-LD
SentimentAnalysisEvent schema.
"""

import logging
import os
import json
import re
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

EMERGENT_LLM_KEY = os.getenv("EMERGENT_LLM_KEY")

# Universal panic keywords (industry-agnostic)
UNIVERSAL_PANIC_KEYWORDS = [
    "human", "real person", "speak to someone", "talk to manager",
    "speak to owner", "actual person", "representative",
    "frustrated", "frustrating", "annoyed", "annoying", "upset",
    "angry", "mad", "terrible", "horrible", "awful", "worst",
    "refund", "money back", "cancel", "unsubscribe", "complaint",
    "lawyer", "attorney", "sue", "legal action", "report",
    "review", "bad review", "1 star", "scam", "fraud", "fake",
    "not working", "doesn't work", "broken", "error", "bug",
    "wrong", "incorrect", "mistake", "problem", "issue",
]

HUMAN_REQUEST_KEYWORDS = [
    "human", "real person", "speak to someone", "manager", "owner",
]


class SentimentAnalyzer:
    """Analyzes conversation sentiment using AI with keyword fallback."""

    def __init__(self):
        self.openai_client = None
        self.using_emergent = False
        self._init_llm()

    def _init_llm(self):
        try:
            from emergentintegrations.llm.chat import LlmChat
            key = EMERGENT_LLM_KEY
            if not key:
                logger.warning("[SentimentAnalyzer] No EMERGENT_LLM_KEY set")
                return
            self.openai_client = LlmChat(
                api_key=key,
                session_id="sentiment_analyzer",
                system_message="You are a sentiment analysis expert. Respond only with valid JSON.",
            )
            self.using_emergent = True
            logger.info("[SentimentAnalyzer] Initialized with Emergent LLM Key")
        except ImportError:
            logger.warning("[SentimentAnalyzer] emergentintegrations not available")
        except Exception as e:
            logger.error(f"[SentimentAnalyzer] Init error: {e}")

    async def analyze_message(
        self,
        message: str,
        conversation_history: Optional[List[Dict]] = None,
        custom_keywords: Optional[List[str]] = None,
    ) -> Dict:
        """
        Analyze a message for sentiment and panic triggers.

        Returns legacy flat dict for backward compatibility.
        Wrap with SentimentAnalysisEvent.from_raw_result() for JSON-LD.
        """
        if not self.openai_client:
            return self._check_keywords(message, custom_keywords)

        try:
            keyword_check = self._check_keywords(message, custom_keywords)
            if keyword_check["is_panic"] and keyword_check["confidence"] > 0.9:
                return keyword_check

            ai_result = await self._analyze_with_llm(message, conversation_history)
            final_result = {**ai_result, "detected_keywords": keyword_check["detected_keywords"]}

            if keyword_check["detected_keywords"]:
                final_result["is_panic"] = True
                final_result["panic_triggers"].extend(keyword_check["panic_triggers"])

            return final_result
        except Exception as e:
            logger.error(f"[SentimentAnalyzer] Analysis error: {e}")
            return self._check_keywords(message, custom_keywords)

    async def _analyze_with_llm(
        self,
        message: str,
        conversation_history: Optional[List[Dict]] = None,
    ) -> Dict:
        context = ""
        if conversation_history:
            recent = conversation_history[-3:]
            context = "\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')}" for m in recent
            )

        prompt = f"""Analyze the following customer message for sentiment.

Context (recent conversation):
{context or "No prior context"}

Current Customer Message:
"{message}"

Respond with JSON:
{{
  "sentiment_score": <float -1.0 to 1.0>,
  "emotion": "<happy|satisfied|neutral|concerned|frustrated|angry>",
  "needs_human": <true if customer wants human help>,
  "detected_language": "<ISO 639-1 code>",
  "english_translation": "<translation if not English>",
  "reasoning": "<brief explanation>"
}}

Respond ONLY with valid JSON."""

        try:
            from emergentintegrations.llm.chat import UserMessage

            response = await self.openai_client.with_model(
                provider="openai", model="gpt-4o"
            ).send_message(user_message=UserMessage(text=prompt))

            response_clean = response.strip()
            if response_clean.startswith("```"):
                match = re.search(r"```(?:json)?\s*\n(.*?)\n```", response_clean, re.DOTALL)
                if match:
                    response_clean = match.group(1)
                else:
                    lines = response_clean.split("\n")
                    response_clean = "\n".join(lines[1:-1])

            result = json.loads(response_clean)

            score = result.get("sentiment_score", 0.0)
            emotion = result.get("emotion", "neutral")
            needs_human = result.get("needs_human", False)
            is_panic = score < -0.7 or needs_human

            if score >= 0.3:
                label = "positive"
            elif score >= -0.3:
                label = "neutral"
            elif score >= -0.7:
                label = "concerned"
            else:
                label = "panic"

            panic_triggers = []
            if score < -0.7:
                panic_triggers.append(f"negative_sentiment ({score:.2f})")
            if needs_human:
                panic_triggers.append("explicit_human_request")

            return {
                "sentiment_score": score,
                "sentiment_label": label,
                "emotion": emotion,
                "is_panic": is_panic,
                "panic_triggers": panic_triggers,
                "detected_keywords": [],
                "needs_human": needs_human,
                "confidence": 0.85,
                "reasoning": result.get("reasoning", ""),
                "detected_language": result.get("detected_language", "en"),
                "english_translation": result.get("english_translation", message),
            }
        except Exception as e:
            logger.error(f"[SentimentAnalyzer] LLM error: {e}")
            raise

    def _check_keywords(
        self,
        message: str,
        custom_keywords: Optional[List[str]] = None,
    ) -> Dict:
        message_lower = message.lower()

        detected_language = "en"
        if any(w in message_lower for w in ["je", "vous", "suis", "très", "merci"]):
            detected_language = "fr"
        elif any(w in message_lower for w in ["estoy", "muy", "por favor", "gracias"]):
            detected_language = "es"
        elif any(w in message_lower for w in ["ich", "bin", "sehr", "danke"]):
            detected_language = "de"

        all_keywords = UNIVERSAL_PANIC_KEYWORDS.copy()
        if custom_keywords:
            all_keywords.extend(k.lower() for k in custom_keywords)

        detected = [kw for kw in all_keywords if kw in message_lower]
        is_panic = len(detected) > 0
        has_human_request = any(k in detected for k in HUMAN_REQUEST_KEYWORDS)
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
            "english_translation": message,
        }


# Singleton
_sentiment_analyzer: Optional[SentimentAnalyzer] = None


def get_sentiment_analyzer() -> SentimentAnalyzer:
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = SentimentAnalyzer()
    return _sentiment_analyzer


async def analyze_message_sentiment(
    message: str,
    conversation_history: Optional[List[Dict]] = None,
    custom_keywords: Optional[List[str]] = None,
) -> Dict:
    """Convenience wrapper — backward compatible with all callers."""
    analyzer = get_sentiment_analyzer()
    return await analyzer.analyze_message(message, conversation_history, custom_keywords)
