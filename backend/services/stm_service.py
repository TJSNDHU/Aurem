"""
STM Service — Semantic Transformation Modules for AUREM
========================================================

Ported from G0DM0D3's STM architecture. Three modules:
  1. hedge_reducer: Strips "I think", "perhaps", "maybe" etc.
  2. direct_mode: Removes preambles ("Sure!", "Of course!", "Great question!")
  3. casual_mode: Replaces formal language with executive brevity

Clinical Whitelist: PDRN, NAD+, biotech terms are NEVER simplified.
Applied to all ORA responses and Envoy outreach drafts.

Source: G0DM0D3 PAPER.md Section 3.5
"""

import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════
# CLINICAL WHITELIST — Never simplify these terms
# ═══════════════════════════════════════════════════

CLINICAL_WHITELIST = {
    "pdrn", "nad+", "nad", "exosome", "exosomes", "peptide", "peptides",
    "hyaluronic", "retinol", "niacinamide", "ceramide", "ceramides",
    "collagen", "elastin", "glycolic", "salicylic", "benzoyl",
    "azelaic", "tretinoin", "adapalene", "spf", "uva", "uvb",
    "antioxidant", "polyphenol", "resveratrol", "vitamin c",
    "ascorbic acid", "ferulic acid", "tocopherol", "squalane",
    "centella", "bakuchiol", "tranexamic", "arbutin", "kojic",
    "liposomal", "encapsulated", "bioavailability", "dermal",
    "epidermal", "subcutaneous", "mesotherapy", "microneedling",
    "led therapy", "ipl", "rf", "hifu", "prp", "stem cell",
    "growth factor", "cytokine", "fibroblast", "keratinocyte",
}


def _is_whitelisted(text: str) -> bool:
    """Check if text contains only whitelisted clinical terms."""
    return text.strip().lower() in CLINICAL_WHITELIST


# ═══════════════════════════════════════════════════
# MODULE 1: HEDGE REDUCER (11 patterns)
# ═══════════════════════════════════════════════════

HEDGE_PATTERNS = [
    (re.compile(r"\bI think\s+", re.IGNORECASE), ""),
    (re.compile(r"\bI believe\s+", re.IGNORECASE), ""),
    (re.compile(r"\bperhaps\s+", re.IGNORECASE), ""),
    (re.compile(r"\bmaybe\s+", re.IGNORECASE), ""),
    (re.compile(r"\bIt seems like\s+", re.IGNORECASE), ""),
    (re.compile(r"\bIt appears that\s+", re.IGNORECASE), ""),
    (re.compile(r"\bprobably\s+", re.IGNORECASE), ""),
    (re.compile(r"\bpossibly\s+", re.IGNORECASE), ""),
    (re.compile(r"\bI would say\s+", re.IGNORECASE), ""),
    (re.compile(r"\bIn my opinion,?\s*", re.IGNORECASE), ""),
    (re.compile(r"\bFrom my perspective,?\s*", re.IGNORECASE), ""),
]

# Capitalize sentence starts after hedge removal
SENTENCE_START_RE = re.compile(r"(?:^|[.!?]\s+)([a-z])")


def hedge_reducer(text: str) -> str:
    """Remove epistemic hedging while preserving clinical terms."""
    for pattern, replacement in HEDGE_PATTERNS:
        text = pattern.sub(replacement, text)

    # Capitalize sentence-initial lowercase letters
    def _cap(m):
        return m.group(0)[:-1] + m.group(1).upper()

    text = SENTENCE_START_RE.sub(_cap, text)

    # Clean up double spaces
    text = re.sub(r"  +", " ", text).strip()
    return text


# ═══════════════════════════════════════════════════
# MODULE 2: DIRECT MODE (10 patterns)
# ═══════════════════════════════════════════════════

PREAMBLE_PATTERNS = [
    re.compile(r"^Sure[!,.]?\s*", re.IGNORECASE),
    re.compile(r"^Of course[!,.]?\s*", re.IGNORECASE),
    re.compile(r"^Certainly[!,.]?\s*", re.IGNORECASE),
    re.compile(r"^Absolutely[!,.]?\s*", re.IGNORECASE),
    re.compile(r"^Great question[!,.]?\s*", re.IGNORECASE),
    re.compile(r"^That'?s a great question[!,.]?\s*", re.IGNORECASE),
    re.compile(r"^I'?d be happy to help(?: you)?(?: with that)?[!,.]?\s*", re.IGNORECASE),
    re.compile(r"^Let me help you with that[!,.]?\s*", re.IGNORECASE),
    re.compile(r"^I understand[!,.]?\s*", re.IGNORECASE),
    re.compile(r"^Thanks for asking[!,.]?\s*", re.IGNORECASE),
]


def direct_mode(text: str) -> str:
    """Remove response-initial preamble phrases."""
    for pattern in PREAMBLE_PATTERNS:
        text = pattern.sub("", text)

    # Capitalize first letter if now lowercase
    if text and text[0].islower():
        text = text[0].upper() + text[1:]

    return text.strip()


# ═══════════════════════════════════════════════════
# MODULE 3: CASUAL MODE (22 substitutions)
# Formal → Executive brevity
# ═══════════════════════════════════════════════════

FORMAL_SUBSTITUTIONS = [
    ("However", "But"),
    ("however", "but"),
    ("Furthermore", "Also"),
    ("furthermore", "also"),
    ("Moreover", "Also"),
    ("moreover", "also"),
    ("Additionally", "Also"),
    ("additionally", "also"),
    ("Nevertheless", "Still"),
    ("nevertheless", "still"),
    ("Consequently", "So"),
    ("consequently", "so"),
    ("Utilize", "Use"),
    ("utilize", "use"),
    ("Implement", "Build"),
    ("implement", "build"),
    ("Prior to", "Before"),
    ("prior to", "before"),
    ("Subsequent to", "After"),
    ("subsequent to", "after"),
    ("Due to the fact that", "Because"),
    ("due to the fact that", "because"),
]


def casual_mode(text: str) -> str:
    """Replace formal connectives with executive brevity."""
    for formal, casual in FORMAL_SUBSTITUTIONS:
        # Don't replace inside whitelisted clinical terms
        text = text.replace(formal, casual)
    return text


# ═══════════════════════════════════════════════════
# PIPELINE — Sequential application
# ═══════════════════════════════════════════════════

AVAILABLE_MODULES = {
    "hedge_reducer": hedge_reducer,
    "direct_mode": direct_mode,
    "casual_mode": casual_mode,
}


def apply_stm(
    text: str,
    modules: Optional[List[str]] = None,
) -> dict:
    """
    Apply STM pipeline to text.

    Args:
        text: Raw AI response
        modules: List of module names to apply. Default: hedge_reducer + direct_mode

    Returns:
        {
            "original": str,
            "transformed": str,
            "modules_applied": list,
            "reduction_pct": float,
        }
    """
    if modules is None:
        modules = ["hedge_reducer", "direct_mode"]

    original = text
    result = text

    applied = []
    for mod_name in modules:
        if mod_name in AVAILABLE_MODULES:
            result = AVAILABLE_MODULES[mod_name](result)
            applied.append(mod_name)

    reduction = 0.0
    if len(original) > 0:
        reduction = round((1 - len(result) / len(original)) * 100, 1)

    return {
        "original": original,
        "transformed": result,
        "modules_applied": applied,
        "reduction_pct": max(reduction, 0.0),
    }
