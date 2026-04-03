"""
Brand Guard Service
═══════════════════════════════════════════════════════════════════
Filters AI responses to protect brand integrity.
- Removes competitor brand mentions
- Validates response compliance
═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

import re
import logging
from typing import Tuple, List

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brands_config import get_brand_config, BrandConfig

logger = logging.getLogger(__name__)


def brand_guard(response: str, brand_key: str) -> Tuple[str, bool]:
    """
    Scan and sanitize AI response for brand compliance.
    
    Args:
        response: Raw AI response text
        brand_key: Brand identifier
    
    Returns:
        Tuple of (sanitized_response, was_modified)
    """
    config = get_brand_config(brand_key)
    if not config:
        return response, False
    
    original = response
    modified = response
    
    # Filter competitor brand mentions
    modified = _filter_competitor_mentions(modified, config.competitor_brands)
    
    # Filter model disclosure attempts
    modified = _filter_model_disclosure(modified)
    
    was_modified = modified != original
    
    if was_modified:
        logger.info(f"Brand guard modified response for {brand_key}")
    
    return modified, was_modified


def _filter_competitor_mentions(text: str, competitors: List[str]) -> str:
    """Replace competitor brand names with 'other brands'."""
    
    for competitor in competitors:
        # Case-insensitive replacement
        pattern = re.compile(re.escape(competitor), re.IGNORECASE)
        text = pattern.sub("other brands", text)
    
    return text


def _filter_model_disclosure(text: str) -> str:
    """
    Filter any accidental model self-disclosure.
    Replace mentions of underlying AI models.
    """
    
    model_patterns = [
        (r"\b(I am|I'm)\s+(Claude|GPT|ChatGPT|OpenAI|Anthropic|Google|Gemini)\b", "I am a proprietary skincare advisor"),
        (r"\b(powered by|built on|using)\s+(Claude|GPT|ChatGPT|OpenAI|Anthropic|Gemini)\b", "developed by our team"),
        (r"\bClaude\s*(3|4|Sonnet|Opus|Haiku)?\b", "our AI system"),
        (r"\bGPT-?(3|4|4o|5)?\b", "our AI system"),
        (r"\bChatGPT\b", "our AI system"),
        (r"\bAnthropic\b", "our company"),
        (r"\bOpenAI\b", "our company"),
    ]
    
    for pattern, replacement in model_patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text


def validate_response_compliance(response: str, brand_key: str) -> List[str]:
    """
    Check response for compliance issues without modifying.
    Returns list of warnings.
    """
    warnings = []
    config = get_brand_config(brand_key)
    
    if not config:
        return ["Unknown brand key"]
    
    response_lower = response.lower()
    
    # Check for competitor mentions
    for competitor in config.competitor_brands:
        if competitor.lower() in response_lower:
            warnings.append(f"Competitor mention: {competitor}")
    
    # Check for model disclosure
    model_keywords = ["claude", "gpt", "chatgpt", "openai", "anthropic", "gemini"]
    for keyword in model_keywords:
        if keyword in response_lower:
            warnings.append(f"Model disclosure: {keyword}")
    
    # Check for medical claims
    medical_phrases = [
        "will cure", "will treat", "diagnose", "prescription",
        "medical advice", "consult a doctor", "see a dermatologist"
    ]
    for phrase in medical_phrases:
        if phrase in response_lower:
            warnings.append(f"Potential medical claim: {phrase}")
    
    return warnings
