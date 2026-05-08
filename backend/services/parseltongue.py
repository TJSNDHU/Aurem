"""
Parseltongue — Adversarial Input Perturbation Engine for AUREM
==============================================================

Ported from G0DM0D3's Parseltongue framework (PAPER.md Section 3.4).
Used by the Security Reviewer for red-team testing of agent prompts.

6 Transformation Techniques:
  1. LEETSPEAK  — Replace chars with visually similar ASCII (a→@, e→3)
  2. UNICODE    — Replace with Unicode homoglyphs (a→а [Cyrillic])
  3. ZWJ        — Insert zero-width Unicode chars between letters
  4. MIXEDCASE  — Disrupt casing patterns
  5. PHONETIC   — Replace with phonetically equivalent spellings
  6. RANDOM     — Randomly pick one of the above per word

3 Intensity Levels:
  - LIGHT:  1 char per trigger word
  - MEDIUM: half the chars
  - HEAVY:  all chars

Trigger detection uses word-boundary regex matching.
Longest triggers are processed first to prevent partial-match corruption.

Source: G0DM0D3 PAPER.md Section 3.4, Table 10
"""

import re
import random
import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════
# TRIGGER WORDS (36 default, 7 categories)
# ═══════════════════════════════════════════════════

TRIGGERS: Dict[str, List[str]] = {
    "action_verbs": ["hack", "exploit", "bypass", "inject", "override", "execute"],
    "security_terms": ["password", "credential", "token", "secret", "key", "certificate"],
    "sensitive_topics": ["weapon", "drug", "bomb", "attack", "kill", "steal"],
    "system_terms": ["sudo", "root", "admin", "shell", "kernel", "daemon"],
    "social_engineering": ["pretend", "roleplay", "ignore", "forget", "disregard", "override"],
    "content_flags": ["nsfw", "explicit", "illegal", "harmful", "dangerous", "malicious"],
    "ai_specific": ["jailbreak", "prompt", "system", "instruction", "alignment", "safety"],
}

ALL_TRIGGERS: Set[str] = set()
for words in TRIGGERS.values():
    ALL_TRIGGERS.update(words)


# ═══════════════════════════════════════════════════
# CHARACTER MAPS
# ═══════════════════════════════════════════════════

LEET_MAP = {
    "a": ["@", "4"], "b": ["8", "|3"], "c": ["(", "{"],
    "d": ["|)", "|>"], "e": ["3", "&"], "f": ["|=", "ph"],
    "g": ["6", "9"], "h": ["#", "|-|"], "i": ["1", "!"],
    "j": ["]", "_|"], "k": ["|<", "|{"], "l": ["|", "1"],
    "m": ["|V|", "/\\/\\"], "n": ["|\\|", "/\\/"],
    "o": ["0", "()"], "p": ["|>", "|*"], "q": ["9", "0,"],
    "r": ["|2", "12"], "s": ["5", "$"], "t": ["7", "+"],
    "u": ["|_|", "(_)"], "v": ["\\/", "|/"], "w": ["\\/\\/", "vv"],
    "x": ["><", "}{"], "y": ["'/", "`/"], "z": ["2", "7_"],
}

UNICODE_HOMOGLYPHS = {
    "a": "\u0430",  # Cyrillic а
    "c": "\u0441",  # Cyrillic с
    "d": "\u0501",  # Cyrillic ԁ
    "e": "\u0435",  # Cyrillic е
    "h": "\u04BB",  # Cyrillic һ
    "i": "\u0456",  # Cyrillic і
    "j": "\u0458",  # Cyrillic ј
    "k": "\u043A",  # Cyrillic к
    "l": "\u04CF",  # Cyrillic ӏ
    "m": "\u043C",  # Cyrillic м
    "n": "\u0578",  # Armenian ո
    "o": "\u043E",  # Cyrillic о
    "p": "\u0440",  # Cyrillic р
    "q": "\u0566",  # Armenian զ
    "r": "\u0433",  # Cyrillic г
    "s": "\u0455",  # Cyrillic ѕ
    "t": "\u03C4",  # Greek τ
    "u": "\u057D",  # Armenian ս
    "v": "\u0475",  # Cyrillic ѵ
    "w": "\u0461",  # Cyrillic ѡ
    "x": "\u0445",  # Cyrillic х
    "y": "\u0443",  # Cyrillic у
    "z": "\u0290",  # Latin ʐ
}

ZW_CHARS = [
    "\u200B",  # Zero-width space
    "\u200C",  # Zero-width non-joiner
    "\u200D",  # Zero-width joiner
    "\uFEFF",  # Zero-width no-break space
]

PHONETIC_RULES = [
    (re.compile(r"ck"), "k"),
    (re.compile(r"ph"), "f"),
    (re.compile(r"qu"), "kw"),
    (re.compile(r"x"), "ks"),
    (re.compile(r"c(?=[eiy])"), "s"),
    (re.compile(r"c"), "k"),
]


# ═══════════════════════════════════════════════════
# TRIGGER DETECTION
# ═══════════════════════════════════════════════════

def detect_triggers(
    text: str,
    custom_triggers: Optional[Set[str]] = None,
) -> List[Dict]:
    """
    Detect trigger words in text using word-boundary regex.

    Returns list of {word, position, category} sorted by length (longest first).
    """
    triggers = ALL_TRIGGERS | (custom_triggers or set())
    found = []

    for word in triggers:
        pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        for match in pattern.finditer(text):
            category = "custom"
            for cat, words in TRIGGERS.items():
                if word.lower() in [w.lower() for w in words]:
                    category = cat
                    break
            found.append({
                "word": match.group(),
                "position": match.start(),
                "category": category,
            })

    # Sort by length descending (longest first to prevent partial-match corruption)
    found.sort(key=lambda x: -len(x["word"]))
    return found


# ═══════════════════════════════════════════════════
# TRANSFORMATION TECHNIQUES
# ═══════════════════════════════════════════════════

def _chars_to_transform(word: str, intensity: str) -> int:
    """How many characters to transform based on intensity."""
    if intensity == "light":
        return 1
    elif intensity == "medium":
        return max(1, (len(word) + 1) // 2)
    else:  # heavy
        return len(word)


def apply_leetspeak(word: str, intensity: str = "medium") -> str:
    count = _chars_to_transform(word, intensity)
    chars = list(word)
    step = max(1, len(chars) // count)
    transformed = 0

    for i in range(0, len(chars), step):
        if transformed >= count:
            break
        c = chars[i].lower()
        if c in LEET_MAP:
            chars[i] = random.choice(LEET_MAP[c])
            transformed += 1

    return "".join(chars)


def apply_unicode(word: str, intensity: str = "medium") -> str:
    count = _chars_to_transform(word, intensity)
    chars = list(word)
    step = max(1, len(chars) // count)
    transformed = 0

    for i in range(0, len(chars), step):
        if transformed >= count:
            break
        c = chars[i].lower()
        if c in UNICODE_HOMOGLYPHS:
            chars[i] = UNICODE_HOMOGLYPHS[c]
            transformed += 1

    return "".join(chars)


def apply_zwj(word: str, intensity: str = "medium") -> str:
    count = _chars_to_transform(word, intensity)
    chars = list(word)
    result = []
    inserted = 0

    for i, c in enumerate(chars):
        result.append(c)
        if inserted < count and i < len(chars) - 1:
            result.append(random.choice(ZW_CHARS))
            inserted += 1

    return "".join(result)


def apply_mixedcase(word: str, intensity: str = "medium") -> str:
    count = _chars_to_transform(word, intensity)
    chars = list(word)
    indices = random.sample(range(len(chars)), min(count, len(chars)))

    for i in indices:
        chars[i] = chars[i].upper() if chars[i].islower() else chars[i].lower()

    return "".join(chars)


def apply_phonetic(word: str, intensity: str = "medium") -> str:
    result = word
    for pattern, replacement in PHONETIC_RULES:
        result = pattern.sub(replacement, result)
    return result


TECHNIQUES = {
    "leetspeak": apply_leetspeak,
    "unicode": apply_unicode,
    "zwj": apply_zwj,
    "mixedcase": apply_mixedcase,
    "phonetic": apply_phonetic,
}


def apply_random(word: str, intensity: str = "medium") -> str:
    technique = random.choice(list(TECHNIQUES.values()))
    return technique(word, intensity)


TECHNIQUES["random"] = apply_random


# ═══════════════════════════════════════════════════
# MAIN TRANSFORM FUNCTION
# ═══════════════════════════════════════════════════

def transform(
    text: str,
    technique: str = "leetspeak",
    intensity: str = "medium",
    custom_triggers: Optional[Set[str]] = None,
) -> Dict:
    """
    Transform trigger words in text using the specified technique.

    Args:
        text: Input text to perturb
        technique: One of "leetspeak", "unicode", "zwj", "mixedcase", "phonetic", "random"
        intensity: "light", "medium", or "heavy"
        custom_triggers: Additional trigger words to detect

    Returns:
        {
            "original": str,
            "transformed": str,
            "triggers_found": list,
            "triggers_transformed": int,
            "technique": str,
            "intensity": str,
        }
    """
    triggers = detect_triggers(text, custom_triggers)

    if not triggers:
        return {
            "original": text,
            "transformed": text,
            "triggers_found": [],
            "triggers_transformed": 0,
            "technique": technique,
            "intensity": intensity,
        }

    transform_fn = TECHNIQUES.get(technique, apply_leetspeak)
    result = text
    offset = 0

    # Process triggers (sorted longest-first)
    processed_positions = set()
    transformed_count = 0

    for trigger in triggers:
        pos = trigger["position"]
        if pos in processed_positions:
            continue

        word = trigger["word"]
        new_word = transform_fn(word, intensity)

        # Replace in text (accounting for offset from previous replacements)
        adj_pos = pos + offset
        result = result[:adj_pos] + new_word + result[adj_pos + len(word):]
        offset += len(new_word) - len(word)

        processed_positions.add(pos)
        transformed_count += 1

    return {
        "original": text,
        "transformed": result,
        "triggers_found": triggers,
        "triggers_transformed": transformed_count,
        "technique": technique,
        "intensity": intensity,
    }


# ═══════════════════════════════════════════════════
# ADVERSARIAL TEST SUITE (for Security Reviewer)
# ═══════════════════════════════════════════════════

def run_adversarial_suite(
    text: str,
    custom_triggers: Optional[Set[str]] = None,
) -> Dict:
    """
    Run all 6 techniques at all 3 intensities against the input text.

    Returns a comprehensive adversarial report showing how the text
    transforms under each combination. Used by Security Reviewer for
    red-team testing of agent prompts and system inputs.
    """
    triggers = detect_triggers(text, custom_triggers)

    if not triggers:
        return {
            "input": text,
            "triggers_found": 0,
            "verdict": "CLEAN",
            "detail": "No trigger words detected",
            "variants": {},
        }

    variants = {}
    for technique_name in TECHNIQUES:
        variants[technique_name] = {}
        for intensity in ["light", "medium", "heavy"]:
            result = transform(text, technique_name, intensity, custom_triggers)
            variants[technique_name][intensity] = {
                "output": result["transformed"],
                "transforms": result["triggers_transformed"],
            }

    return {
        "input": text,
        "triggers_found": len(triggers),
        "trigger_words": [t["word"] for t in triggers],
        "trigger_categories": list(set(t["category"] for t in triggers)),
        "verdict": "SENSITIVE",
        "total_variants": len(TECHNIQUES) * 3,
        "variants": variants,
    }
