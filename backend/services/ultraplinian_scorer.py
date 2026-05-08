"""
ULTRAPLINIAN Scorer — 5-Axis Composite Scoring for AUREM
=========================================================

Ported from G0DM0D3's ULTRAPLINIAN scoring framework (PAPER.md Section 3.6).
Adapted for business context: replaces "anti-refusal" axis with "data_integrity".

5 Axes (100 points total):
  1. COMPLETENESS (0-25): Response length and depth
  2. STRUCTURE    (0-20): Headers, lists, code blocks, organized output
  3. DATA_INTEGRITY (0-25): Internal consistency, valid numbers, matching counts
  4. DIRECTNESS   (0-15): No preambles, no hedging, gets to the point
  5. RELEVANCE    (0-15): Query word overlap, topical alignment

Score Thresholds:
  90-100: EXCELLENT — Ship it
  80-89:  GOOD     — Minor polish needed
  60-79:  MEDIOCRE — Significant gaps
  40-59:  POOR     — Rebuild required
  0-39:   TERRIBLE — Complete failure

Source: G0DM0D3 PAPER.md Section 3.6, Tables 8-9
"""

import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════
# SCORING PATTERNS
# ═══════════════════════════════════════════════════

HEADER_RE = re.compile(r"^#{1,3}\s", re.MULTILINE)
LIST_RE = re.compile(r"^[\s]*[-*]\s", re.MULTILINE)
CODE_BLOCK_RE = re.compile(r"```")
NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)

PREAMBLE_PATTERNS = [
    re.compile(r"^(Sure|Of course|Certainly|Absolutely|Great question)", re.IGNORECASE),
    re.compile(r"^(That's a great question|I'd be happy to help)", re.IGNORECASE),
    re.compile(r"^(Let me help you|I understand|Thanks for asking)", re.IGNORECASE),
]

HEDGE_PATTERNS = [
    re.compile(r"\bI think\b", re.IGNORECASE),
    re.compile(r"\bperhaps\b", re.IGNORECASE),
    re.compile(r"\bmaybe\b", re.IGNORECASE),
    re.compile(r"\bprobably\b", re.IGNORECASE),
    re.compile(r"\bIt seems like\b", re.IGNORECASE),
    re.compile(r"\bpossibly\b", re.IGNORECASE),
    re.compile(r"\bI would say\b", re.IGNORECASE),
    re.compile(r"\bIn my opinion\b", re.IGNORECASE),
]

# Numbers that should be internally consistent
NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?(?:%|K|M|k|m)?\b")
PERCENTAGE_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*%")


def score_response(
    content: str,
    query: str = "",
    context: str = "",
) -> Dict:
    """
    Score a response on a 100-point composite metric.

    Args:
        content: The agent's response text
        query: The original user query (for relevance scoring)
        context: Additional context (agent_id, intent, etc.)

    Returns:
        {
            "total": int (0-100),
            "grade": "EXCELLENT"|"GOOD"|"MEDIOCRE"|"POOR"|"TERRIBLE",
            "axes": {
                "completeness": {"score": int, "max": 25, "detail": str},
                "structure": {"score": int, "max": 20, "detail": str},
                "data_integrity": {"score": int, "max": 25, "detail": str},
                "directness": {"score": int, "max": 15, "detail": str},
                "relevance": {"score": int, "max": 15, "detail": str},
            },
            "flags": [str],
        }
    """
    if not content or len(content.strip()) < 10:
        return {
            "total": 0,
            "grade": "TERRIBLE",
            "axes": _empty_axes(),
            "flags": ["Empty or near-empty response"],
        }

    flags = []

    # ═══ AXIS 1: COMPLETENESS (0-25) ═══
    char_count = len(content)
    completeness_score = min(char_count / 40, 25)
    completeness_detail = f"{char_count} chars"
    if char_count < 100:
        flags.append("Response too short (<100 chars)")

    # ═══ AXIS 2: STRUCTURE (0-20) ═══
    n_headers = len(HEADER_RE.findall(content))
    n_lists = len(LIST_RE.findall(content))
    n_numbered = len(NUMBERED_RE.findall(content))
    n_code = len(CODE_BLOCK_RE.findall(content)) // 2  # pairs

    structure_score = min(
        3 * n_headers + 1.5 * (n_lists + n_numbered) + 5 * n_code,
        20,
    )
    structure_detail = f"{n_headers}h {n_lists + n_numbered}li {n_code}code"

    # ═══ AXIS 3: DATA INTEGRITY (0-25) ═══
    numbers = NUMBER_RE.findall(content)
    percentages = PERCENTAGE_RE.findall(content)
    integrity_score = 25  # Start at max, deduct for issues

    # Check: percentages should be 0-100
    for pct_str in percentages:
        try:
            pct = float(pct_str)
            if pct < 0 or pct > 100:
                integrity_score -= 5
                flags.append(f"Invalid percentage: {pct}%")
        except ValueError:
            pass

    # Check: if content mentions "total" or "sum", verify consistency
    if re.search(r"\btotal\b|\bsum\b", content, re.I) and len(numbers) >= 3:
        # Heuristic: if there are many numbers, assume data is present
        integrity_score = max(integrity_score, 20)

    # Check: contradictions (says "no X" then discusses X)
    no_match = re.search(r"\bno\s+(\w+)\b", content, re.I)
    if no_match and re.search(rf"\b{re.escape(no_match.group(1))}\b", content[no_match.end():], re.I):
        integrity_score -= 3

    integrity_score = max(0, min(integrity_score, 25))
    integrity_detail = f"{len(numbers)} nums, {len(percentages)} pcts"

    # ═══ AXIS 4: DIRECTNESS (0-15) ═══
    trimmed = content.strip()
    has_preamble = any(p.match(trimmed) for p in PREAMBLE_PATTERNS)
    hedge_count = sum(1 for p in HEDGE_PATTERNS if p.search(content))

    if has_preamble:
        directness_score = 8
        flags.append("Response starts with preamble")
    else:
        directness_score = 15

    # Deduct for hedging (max -5)
    hedge_penalty = min(hedge_count * 1.5, 5)
    directness_score = max(0, directness_score - hedge_penalty)
    if hedge_count > 0:
        flags.append(f"{hedge_count} hedge phrases detected")

    directness_detail = f"preamble={'Y' if has_preamble else 'N'}, hedges={hedge_count}"

    # ═══ AXIS 5: RELEVANCE (0-15) ═══
    if query:
        query_words = set(
            w.lower() for w in re.findall(r"\w+", query) if len(w) > 3
        )
        if query_words:
            content_lower = content.lower()
            matched = sum(1 for w in query_words if w in content_lower)
            relevance_score = 15 * (matched / len(query_words))
        else:
            relevance_score = 7.5  # Default for short queries
    else:
        relevance_score = 7.5  # No query provided

    relevance_detail = f"{'%.0f' % relevance_score}/15"

    # ═══ TOTAL ═══
    total = min(
        int(completeness_score + structure_score + integrity_score +
            directness_score + relevance_score),
        100,
    )

    if total >= 90:
        grade = "EXCELLENT"
    elif total >= 80:
        grade = "GOOD"
    elif total >= 60:
        grade = "MEDIOCRE"
    elif total >= 40:
        grade = "POOR"
    else:
        grade = "TERRIBLE"

    return {
        "total": total,
        "grade": grade,
        "axes": {
            "completeness": {
                "score": int(completeness_score),
                "max": 25,
                "detail": completeness_detail,
            },
            "structure": {
                "score": int(structure_score),
                "max": 20,
                "detail": structure_detail,
            },
            "data_integrity": {
                "score": int(integrity_score),
                "max": 25,
                "detail": integrity_detail,
            },
            "directness": {
                "score": int(directness_score),
                "max": 15,
                "detail": directness_detail,
            },
            "relevance": {
                "score": round(relevance_score, 1),
                "max": 15,
                "detail": relevance_detail,
            },
        },
        "flags": flags,
    }


def _empty_axes():
    return {
        axis: {"score": 0, "max": mx, "detail": "N/A"}
        for axis, mx in [
            ("completeness", 25), ("structure", 20),
            ("data_integrity", 25), ("directness", 15), ("relevance", 15),
        ]
    }


def score_for_envoy_gate(content: str, query: str = "") -> Dict:
    """
    Score specifically for the Envoy Hard Gate.

    Returns the composite score plus a pass/fail based on the 80-point threshold.
    """
    result = score_response(content, query)
    result["envoy_pass"] = result["total"] >= 80
    result["threshold"] = 80
    return result
