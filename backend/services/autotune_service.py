"""
AutoTune Service — Context-Adaptive LLM Parameters for AUREM
=============================================================

Ported from G0DM0D3's AutoTune architecture. Classifies conversation
context and selects optimal LLM sampling parameters.

Context Types:
  - ANALYTICAL: Pipeline data, deal analysis, metrics (low temp)
  - STRATEGIC: Forecasting, planning, optimization (medium temp)
  - CREATIVE: Outreach drafting, email writing, communication (high temp)
  - CONVERSATIONAL: General chat, questions, status checks (balanced)
  - CHAOTIC: Brainstorming, wild ideas, exploration (max temp)

EMA Feedback Loop:
  - Thumbs up/down adjusts parameter profiles via Exponential Moving Average
  - Stored in MongoDB `ema_feedback` collection
  - Converges within ~20 ratings per context type

Source: G0DM0D3 PAPER.md Sections 3.2-3.3
"""

import re
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


def get_db():
    return _db


# ═══════════════════════════════════════════════════
# CONTEXT DETECTION (20 regex patterns, 5 types)
# ═══════════════════════════════════════════════════

CONTEXT_PATTERNS = {
    "ANALYTICAL": [
        re.compile(r"\b(pipeline|deal|revenue|metric|data|report|status|health)\b", re.I),
        re.compile(r"\b(analyze|analysis|compare|statistics|trend|breakdown)\b", re.I),
        re.compile(r"\b(how many|what is the|show me|calculate|count)\b", re.I),
        re.compile(r"\b(at risk|at-risk|conversion|win rate|score|grade)\b", re.I),
    ],
    "STRATEGIC": [
        re.compile(r"\b(forecast|predict|plan|strategy|optimize|roadmap)\b", re.I),
        re.compile(r"\b(next quarter|next month|next year|projection|growth)\b", re.I),
        re.compile(r"\b(improve|increase|reduce|minimize|maximize|scale)\b", re.I),
        re.compile(r"\b(decision|prioritize|allocate|invest|budget)\b", re.I),
    ],
    "CREATIVE": [
        re.compile(r"\b(write|draft|compose|create|design|craft)\b", re.I),
        re.compile(r"\b(email|outreach|message|proposal|pitch|presentation)\b", re.I),
        re.compile(r"\b(campaign|content|copy|headline|subject line|hook)\b", re.I),
        re.compile(r"\b(brainstorm|idea|concept|approach|angle|narrative)\b", re.I),
    ],
    "CONVERSATIONAL": [
        re.compile(r"\b(hey|hi|hello|what can you|tell me about|how are)\b", re.I),
        re.compile(r"\b(thanks|thank you|help|explain|what is|who is)\b", re.I),
        re.compile(r"^.{0,40}$"),  # Short messages
    ],
    "CHAOTIC": [
        re.compile(r"\b(chaos|random|wild|crazy|experiment|unconventional)\b", re.I),
        re.compile(r"\b(disrupt|radical|moonshot|impossible|insane)\b", re.I),
        re.compile(r"[!]{3,}|[?]{3,}|[.]{4,}", re.I),
    ],
}

# Weights: current message 3x, each history message 1x
CURRENT_WEIGHT = 3
HISTORY_WEIGHT = 1
HISTORY_WINDOW = 4


def classify_context(
    message: str,
    conversation_history: Optional[List[Dict]] = None,
) -> Dict:
    """
    Classify the conversational context for parameter selection.

    Returns:
        {
            "context": "ANALYTICAL" | "STRATEGIC" | ... ,
            "confidence": float (0-1),
            "scores": {context: score},
            "matched_patterns": [str],
        }
    """
    scores = {}
    matched = []

    for ctx, patterns in CONTEXT_PATTERNS.items():
        score = 0
        for p in patterns:
            if p.search(message):
                score += CURRENT_WEIGHT
                matched.append(f"{ctx}:{p.pattern[:30]}")

        # Check history
        if conversation_history:
            recent = conversation_history[-HISTORY_WINDOW:]
            for msg in recent:
                content = msg.get("content", "")
                for p in patterns:
                    if p.search(content):
                        score += HISTORY_WEIGHT

        scores[ctx] = score

    total = sum(scores.values())
    if total == 0:
        return {
            "context": "CONVERSATIONAL",
            "confidence": 0.5,
            "scores": scores,
            "matched_patterns": [],
        }

    best_ctx = max(scores, key=scores.get)
    confidence = scores[best_ctx] / total

    return {
        "context": best_ctx,
        "confidence": round(confidence, 3),
        "scores": scores,
        "matched_patterns": matched,
    }


# ═══════════════════════════════════════════════════
# PARAMETER PROFILES
# ═══════════════════════════════════════════════════

# (temperature, top_p, top_k, frequency_penalty, presence_penalty, repetition_penalty)
PARAMETER_PROFILES = {
    "ANALYTICAL":     {"temperature": 0.15, "top_p": 0.80, "top_k": 25, "frequency_penalty": 0.20, "presence_penalty": 0.00, "repetition_penalty": 1.05},
    "STRATEGIC":      {"temperature": 0.40, "top_p": 0.88, "top_k": 40, "frequency_penalty": 0.20, "presence_penalty": 0.15, "repetition_penalty": 1.08},
    "CREATIVE":       {"temperature": 1.15, "top_p": 0.95, "top_k": 85, "frequency_penalty": 0.50, "presence_penalty": 0.70, "repetition_penalty": 1.20},
    "CONVERSATIONAL": {"temperature": 0.75, "top_p": 0.90, "top_k": 50, "frequency_penalty": 0.10, "presence_penalty": 0.10, "repetition_penalty": 1.00},
    "CHAOTIC":        {"temperature": 1.70, "top_p": 0.99, "top_k": 100, "frequency_penalty": 0.80, "presence_penalty": 0.90, "repetition_penalty": 1.30},
    "BALANCED":       {"temperature": 0.70, "top_p": 0.90, "top_k": 50, "frequency_penalty": 0.15, "presence_penalty": 0.10, "repetition_penalty": 1.05},
}

PARAM_BOUNDS = {
    "temperature":       (0.0, 2.0),
    "top_p":             (0.0, 1.0),
    "top_k":             (1, 100),
    "frequency_penalty": (-2.0, 2.0),
    "presence_penalty":  (-2.0, 2.0),
    "repetition_penalty": (0.0, 2.0),
}


def _clamp(params: Dict) -> Dict:
    """Clamp parameters to valid API ranges."""
    clamped = {}
    for key, val in params.items():
        if key in PARAM_BOUNDS:
            lo, hi = PARAM_BOUNDS[key]
            clamped[key] = max(lo, min(hi, val))
        else:
            clamped[key] = val
    return clamped


def _blend(profile_a: Dict, profile_b: Dict, weight_b: float) -> Dict:
    """Linear interpolation between two parameter profiles."""
    blended = {}
    for key in profile_a:
        a = profile_a[key]
        b = profile_b.get(key, a)
        blended[key] = a * (1 - weight_b) + b * weight_b
    return blended


def compute_params(
    context: str,
    confidence: float,
    conversation_length: int = 0,
) -> Dict:
    """
    Compute optimal LLM parameters for the detected context.

    Low confidence → blend with BALANCED profile.
    Long conversations → boost repetition penalty.
    """
    profile = PARAMETER_PROFILES.get(context, PARAMETER_PROFILES["CONVERSATIONAL"])
    balanced = PARAMETER_PROFILES["BALANCED"]

    # Low confidence: blend toward balanced
    if confidence < 0.6:
        profile = _blend(profile, balanced, 1 - confidence)

    # Long conversation: boost repetition penalty
    if conversation_length > 10:
        boost = min((conversation_length - 10) * 0.01, 0.15)
        profile = {**profile}
        profile["repetition_penalty"] = profile.get("repetition_penalty", 1.0) + boost
        profile["frequency_penalty"] = profile.get("frequency_penalty", 0.1) + 0.5 * boost

    return _clamp(profile)


# ═══════════════════════════════════════════════════
# EMA FEEDBACK LOOP
# ═══════════════════════════════════════════════════

EMA_ALPHA = 0.3
MIN_SAMPLES = 3
MAX_WEIGHT = 0.5
SAMPLES_FOR_MAX = 20


async def record_feedback(
    context: str,
    rating: int,
    params_used: Dict,
    response_text: str = "",
) -> Dict:
    """
    Record thumbs up (+1) or down (-1) feedback for EMA learning.

    Stored in MongoDB `ema_feedback` collection.
    """
    db = get_db()
    if db is None:
        return {"error": "Database not initialized"}

    record = {
        "context": context,
        "rating": rating,
        "params": params_used,
        "response_length": len(response_text),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await db.ema_feedback.insert_one(record)

    # Update running EMA averages
    await _update_ema(context, rating, params_used)

    count = await db.ema_feedback.count_documents({"context": context})
    return {"recorded": True, "context": context, "total_ratings": count}


async def _update_ema(context: str, rating: int, params: Dict):
    """Update EMA running average for positive/negative ratings."""
    db = get_db()
    if db is None:
        return

    field = "positive_ema" if rating > 0 else "negative_ema"

    existing = await db.ema_profiles.find_one(
        {"context": context}, {"_id": 0}
    )

    if not existing:
        existing = {
            "context": context,
            "positive_ema": PARAMETER_PROFILES.get(context, PARAMETER_PROFILES["CONVERSATIONAL"]).copy(),
            "negative_ema": PARAMETER_PROFILES.get(context, PARAMETER_PROFILES["CONVERSATIONAL"]).copy(),
            "sample_count": 0,
        }

    current_ema = existing.get(field, {})
    new_ema = {}
    for key in params:
        if key in PARAM_BOUNDS:
            old = current_ema.get(key, params[key])
            new_ema[key] = EMA_ALPHA * params[key] + (1 - EMA_ALPHA) * old

    await db.ema_profiles.update_one(
        {"context": context},
        {
            "$set": {field: new_ema},
            "$inc": {"sample_count": 1},
        },
        upsert=True,
    )


async def get_learned_adjustments(context: str) -> Optional[Dict]:
    """
    Get EMA-learned parameter adjustments for a context type.

    Returns None if insufficient samples (< MIN_SAMPLES).
    """
    db = get_db()
    if db is None:
        return None

    profile = await db.ema_profiles.find_one(
        {"context": context}, {"_id": 0}
    )

    if not profile or profile.get("sample_count", 0) < MIN_SAMPLES:
        return None

    base = PARAMETER_PROFILES.get(context, PARAMETER_PROFILES["CONVERSATIONAL"])
    pos_ema = profile.get("positive_ema", base)
    neg_ema = profile.get("negative_ema", base)

    # Adjustment: move toward positive, away from negative
    adjustments = {}
    for key in base:
        pos_delta = pos_ema.get(key, base[key]) - base[key]
        neg_delta = neg_ema.get(key, base[key]) - base[key]
        adjustments[key] = 0.5 * pos_delta - 0.5 * neg_delta

    # Weight by sample count (caps at 50%)
    count = profile.get("sample_count", 0)
    weight = min(count / SAMPLES_FOR_MAX * MAX_WEIGHT, MAX_WEIGHT)

    return {"adjustments": adjustments, "weight": weight, "samples": count}


async def compute_autotune_params(
    message: str,
    conversation_history: Optional[List[Dict]] = None,
    conversation_length: int = 0,
) -> Dict:
    """
    Full AutoTune pipeline:
    1. Classify context
    2. Select base parameters
    3. Apply EMA-learned adjustments
    4. Clamp to bounds

    Returns:
        {
            "context": str,
            "confidence": float,
            "params": dict,
            "learned_applied": bool,
        }
    """
    classification = classify_context(message, conversation_history)
    ctx = classification["context"]
    conf = classification["confidence"]

    params = compute_params(ctx, conf, conversation_length)

    # Apply EMA adjustments if available
    learned_applied = False
    learned = await get_learned_adjustments(ctx)
    if learned:
        weight = learned["weight"]
        for key, adj in learned["adjustments"].items():
            if key in params:
                params[key] = params[key] + weight * adj
        params = _clamp(params)
        learned_applied = True

    return {
        "context": ctx,
        "confidence": conf,
        "params": params,
        "learned_applied": learned_applied,
        "scores": classification["scores"],
    }
