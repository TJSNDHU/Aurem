"""
ora_prose_filter.py — iter 323q

Stop Slop post-processor for ORA's final assistant replies.

Inspired by the Stop Slop skill (Hardik Pandya): scrub AI-tells from prose
so the founder doesn't get LLM-shaped output for production-facing work.

Applied AFTER the tool loop finishes, BEFORE the reply is persisted to
history or shipped to the chat UI. Idempotent — running twice changes
nothing on the second pass.

The cleaner is intentionally conservative: it only removes high-confidence
AI-tells. We do NOT try to rewrite or paraphrase — that's the LLM's job.

Heuristics applied (in order):
  1. Strip throat-clearing openers ("Great question!", "Certainly!", etc.)
  2. Replace em-dashes used as dramatic pauses with periods or commas
  3. Drop hedge-stack phrases ("It's worth noting that…")
  4. Collapse filler affirmations on their own line ("Absolutely!", "Sure!")
  5. Compress repeated blank lines (max 2 consecutive)
  6. Strip jargon ONLY when it's a standalone whole word (no false positives)

Coverage: ASCII + Unicode em-dash + smart quotes.
"""
from __future__ import annotations

import re
from typing import Tuple

# ── 1. Throat-clearing openers (line- or paragraph-leading) ──────────
_OPENER_PATTERNS = [
    r"^(?:Great|Excellent|Perfect|Wonderful|Fantastic)\s+question[!.]?\s*",
    r"^Certainly[!.]?\s*",
    r"^Of\s+course[!.]?\s*",
    r"^Absolutely[!.]?\s*",
    r"^Definitely[!.]?\s*",
    r"^Sure(?:\s+thing)?[!.]?\s*",
    r"^I'd\s+be\s+happy\s+to\s+",
    r"^I\s+understand[!.]?\s*",
    r"^Let\s+me\s+help\s+you\s+with\s+that[!.]?\s*",
    r"^Happy\s+to\s+help[!.]?\s*",
]
_OPENER_RE = re.compile("|".join(f"(?:{p})" for p in _OPENER_PATTERNS),
                        re.IGNORECASE | re.MULTILINE)

# ── 2. Hedge stacks ──────────────────────────────────────────────────
_HEDGE_PATTERNS = [
    r"It['']s\s+(?:worth|important)\s+(?:to\s+note|noting|to\s+mention|mentioning)\s+that\s+",
    r"It\s+should\s+be\s+noted\s+that\s+",
    r"Please\s+(?:note|be\s+aware)\s+that\s+",
    r"As\s+(?:an?\s+AI|a\s+language\s+model)[,.\s]+",
    r"As\s+previously\s+(?:mentioned|stated)\s*,?\s*",
]
_HEDGE_RE = re.compile("|".join(f"(?:{p})" for p in _HEDGE_PATTERNS),
                       re.IGNORECASE)

# ── 3. Standalone filler affirmation lines ───────────────────────────
_STANDALONE_FILLER = re.compile(
    r"^\s*(?:Absolutely|Definitely|Certainly|Of\s+course|Sure)[!.]?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# ── 4. Em-dash dramatic pauses ───────────────────────────────────────
# Pattern: word + (spaces around) em-dash + word. Replace with comma+space.
# Don't touch em-dashes inside code fences (handled separately).
_EM_DASH_DRAMATIC = re.compile(r"(\w)\s*[—–]\s*(\w)")

# ── 5. Repeated blank lines ──────────────────────────────────────────
_TRIPLE_BLANK = re.compile(r"\n{3,}")

# ── 6. Jargon as whole-word matches (case-insensitive) ───────────────
# Conservative list — only universal buzzwords. NOT used for code-comment
# style words like "leverage", since founder explicitly uses those.
_JARGON_WHOLE = re.compile(
    r"\b(?:synergize|synergistic|holistic\s+approach|paradigm\s+shift|"
    r"low-hanging\s+fruit|move\s+the\s+needle|circle\s+back|"
    r"at\s+the\s+end\s+of\s+the\s+day)\b",
    re.IGNORECASE,
)


def _split_code_fences(text: str) -> list[tuple[bool, str]]:
    """Split text into [(is_code, chunk), ...] respecting ``` fences.

    We must NEVER touch code blocks — em-dashes in code or shell commands
    are syntactically meaningful.
    """
    parts: list[tuple[bool, str]] = []
    buf = []
    inside = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            if buf:
                parts.append((inside, "\n".join(buf)))
                buf = []
            inside = not inside
            buf.append(line)
            if not inside:
                parts.append((True, "\n".join(buf)))
                buf = []
        else:
            buf.append(line)
    if buf:
        parts.append((inside, "\n".join(buf)))
    return parts


def clean_prose(text: str) -> Tuple[str, dict]:
    """Apply the Stop Slop pass. Returns (cleaned_text, stats_dict).

    `stats` is suitable for logging: e.g. {"openers": 1, "hedges": 2}.
    A no-op on already-clean prose returns the same string + zero counts.
    """
    if not isinstance(text, str) or not text.strip():
        return text or "", {"applied": False}

    stats = {
        "openers_removed":   0,
        "hedges_removed":    0,
        "standalone_filler": 0,
        "em_dashes":         0,
        "jargon":            0,
        "applied":           True,
    }

    cleaned_parts: list[str] = []
    for is_code, chunk in _split_code_fences(text):
        if is_code:
            cleaned_parts.append(chunk)
            continue

        # Throat-clearing
        n_open = len(_OPENER_RE.findall(chunk))
        if n_open:
            chunk = _OPENER_RE.sub("", chunk)
            stats["openers_removed"] += n_open

        # Hedges
        n_hedge = len(_HEDGE_RE.findall(chunk))
        if n_hedge:
            chunk = _HEDGE_RE.sub("", chunk)
            stats["hedges_removed"] += n_hedge

        # Standalone filler lines
        n_filler = len(_STANDALONE_FILLER.findall(chunk))
        if n_filler:
            chunk = _STANDALONE_FILLER.sub("", chunk)
            stats["standalone_filler"] += n_filler

        # Em-dashes as dramatic pauses
        n_em = len(_EM_DASH_DRAMATIC.findall(chunk))
        if n_em:
            chunk = _EM_DASH_DRAMATIC.sub(r"\1, \2", chunk)
            stats["em_dashes"] += n_em

        # Jargon
        n_jargon = len(_JARGON_WHOLE.findall(chunk))
        if n_jargon:
            chunk = _JARGON_WHOLE.sub("", chunk)
            stats["jargon"] += n_jargon

        cleaned_parts.append(chunk)

    cleaned = "\n".join(cleaned_parts)
    cleaned = _TRIPLE_BLANK.sub("\n\n", cleaned).strip()

    return cleaned, stats


__all__ = ["clean_prose"]
