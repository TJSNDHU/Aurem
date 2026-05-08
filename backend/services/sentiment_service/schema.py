"""
JSON-LD SentimentAnalysisEvent Contract

Defines the canonical schema for all sentiment data flowing between
the extracted service and the rest of the AUREM platform.

Source: /app/memory/sentiment_jsonld_schema_and_directive.md
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime, timezone
import uuid


# Tone tag constants (Operation Clean-Cut Phase C)
TONE_CLINICAL_INQUIRY = "Clinical_Inquiry"
TONE_EFFICACY_CONCERN = "Efficacy_Concern"
TONE_LOGISTICS_UPDATE = "Logistics_Update"
TONE_AESTHETIC_FEEDBACK = "Aesthetic_Feedback"

# UI Pulse color constants
PULSE_COPPER_WIREFRAME = "#B8860B"
PULSE_ROSE_GOLD = "#B76E79"
PULSE_CALM_GREEN = "#2E8B57"
PULSE_NEUTRAL_SLATE = "#708090"


@dataclass
class CommunicationTrace:
    source: str = "cloud_gateway"
    content_hash: str = ""


@dataclass
class SentimentScore:
    polarity: float = 0.0
    subjectivity: float = 0.0
    confidence: float = 0.0
    tone_tags: List[str] = field(default_factory=list)


@dataclass
class UIEvent:
    pulse_color: str = PULSE_NEUTRAL_SLATE
    animation_style: str = "none"
    panic_hook_active: bool = False


@dataclass
class SentimentAnalysisEvent:
    """
    JSON-LD compliant SentimentAnalysisEvent.

    Maps to:
    {
      "@context": "https://schema.aurem.ai/",
      "@type": "SentimentAnalysisEvent",
      ...
    }
    """

    identifier: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    subject: CommunicationTrace = field(default_factory=CommunicationTrace)
    analysis: SentimentScore = field(default_factory=SentimentScore)
    aurem_gen_trigger: UIEvent = field(default_factory=UIEvent)

    # Extended fields for internal routing
    sentiment_label: str = "neutral"
    emotion: str = "neutral"
    is_panic: bool = False
    panic_triggers: List[str] = field(default_factory=list)
    detected_keywords: List[str] = field(default_factory=list)
    needs_human: bool = False
    detected_language: str = "en"
    english_translation: str = ""

    def to_jsonld(self) -> dict:
        """Serialize to JSON-LD format per the schema contract."""
        return {
            "@context": "https://schema.aurem.ai/",
            "@type": "SentimentAnalysisEvent",
            "identifier": self.identifier,
            "timestamp": self.timestamp,
            "subject": asdict(self.subject),
            "analysis": {
                "@type": "SentimentScore",
                **asdict(self.analysis),
            },
            "aurem_gen_trigger": {
                "@type": "UIEvent",
                **asdict(self.aurem_gen_trigger),
            },
        }

    def to_legacy_dict(self) -> dict:
        """
        Return the flat dict format expected by existing callers
        (panic_hook.py, tone_sync_service.py) — zero-breakage shim.
        """
        return {
            "sentiment_score": self.analysis.polarity,
            "sentiment_label": self.sentiment_label,
            "emotion": self.emotion,
            "is_panic": self.is_panic,
            "panic_triggers": self.panic_triggers,
            "detected_keywords": self.detected_keywords,
            "needs_human": self.needs_human,
            "confidence": self.analysis.confidence,
            "detected_language": self.detected_language,
            "english_translation": self.english_translation,
        }

    @classmethod
    def from_raw_result(cls, raw: dict) -> "SentimentAnalysisEvent":
        """Build from the old-style flat dict returned by the analyzer."""
        polarity = raw.get("sentiment_score", 0.0)

        # Determine UI pulse based on polarity
        if polarity < -0.9:
            pulse_color = PULSE_COPPER_WIREFRAME
            animation = "Copper_Wireframe_Pulse"
            panic_active = True
        elif polarity < -0.7:
            pulse_color = PULSE_ROSE_GOLD
            animation = "Rose_Gold_Pulse"
            panic_active = True
        elif polarity >= 0.3:
            pulse_color = PULSE_CALM_GREEN
            animation = "Calm_Glow"
            panic_active = False
        else:
            pulse_color = PULSE_NEUTRAL_SLATE
            animation = "none"
            panic_active = False

        # Classify tone tags
        tone_tags = []
        keywords = [k.lower() for k in raw.get("detected_keywords", [])]
        if any(k in keywords for k in ["clinical", "ingredient", "pdrn", "nad"]):
            tone_tags.append(TONE_CLINICAL_INQUIRY)
        if any(k in keywords for k in ["disappointed", "not working", "doesn't work"]):
            tone_tags.append(TONE_EFFICACY_CONCERN)
        if any(k in keywords for k in ["shipping", "tracking", "delivery"]):
            tone_tags.append(TONE_LOGISTICS_UPDATE)
        if raw.get("needs_human", False):
            tone_tags.append(TONE_EFFICACY_CONCERN)

        return cls(
            subject=CommunicationTrace(
                source=raw.get("source", "cloud_gateway"),
                content_hash=raw.get("content_hash", ""),
            ),
            analysis=SentimentScore(
                polarity=polarity,
                subjectivity=raw.get("subjectivity", 0.0),
                confidence=raw.get("confidence", 0.0),
                tone_tags=tone_tags,
            ),
            aurem_gen_trigger=UIEvent(
                pulse_color=pulse_color,
                animation_style=animation,
                panic_hook_active=panic_active,
            ),
            sentiment_label=raw.get("sentiment_label", "neutral"),
            emotion=raw.get("emotion", "neutral"),
            is_panic=raw.get("is_panic", False),
            panic_triggers=raw.get("panic_triggers", []),
            detected_keywords=raw.get("detected_keywords", []),
            needs_human=raw.get("needs_human", False),
            detected_language=raw.get("detected_language", "en"),
            english_translation=raw.get("english_translation", ""),
        )
