"""
AUREM Sentiment Service — Phase C Extracted Module

Decoupled from the 40k-line monolith via Operation Clean-Cut.
Implements the JSON-LD SentimentAnalysisEvent contract
and Safety Buffer for zero-downtime migration.

Communication Contract: sentiment_jsonld_schema_and_directive.md
Safety Protocol: safety_buffer_and_execution_auth.md
"""

from services.sentiment_service.analyzer import (
    SentimentAnalyzer,
    get_sentiment_analyzer,
    analyze_message_sentiment,
)
from services.sentiment_service.schema import SentimentAnalysisEvent
from services.sentiment_service.safety_buffer import safety_buffer_check

__all__ = [
    "SentimentAnalyzer",
    "get_sentiment_analyzer",
    "analyze_message_sentiment",
    "SentimentAnalysisEvent",
    "safety_buffer_check",
]
