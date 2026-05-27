"""
services/aurem_cto_output_guard.py — iter D-40b

Defense-in-depth: strip "illustrative pseudo-code" out of AUREM CTO
replies whose intent is NOT a build/fix request.

Why this exists
---------------
The founder caught AUREM CTO replying to a meta-question ("how do you
reply to a non-tech customer?") with Python pseudo-code (`def
distill_idea(raw_input): ...`, `patterns = {...}` dictionaries). The
system prompt already forbids this, but the free-tier LLMs (deepseek,
llama) occasionally slip back into pseudo-code as "illustration".

This module is the deterministic safety net. It runs AFTER the LLM
reply lands and BEFORE the reply is returned to the chat UI:

  - For intents in {question, conversational, strategic, unknown,
    diagnostic} we treat code blocks as illustrative and strip them.
  - For intent == "build" we leave the reply untouched — those code
    blocks are intentional, for the dev's actual project.
  - When non_technical=True we strip regardless of intent: a non-tech
    customer never gets pseudo-code, period.

Public API
----------
    strip_illustrative_code(reply: str, *, intent: str,
                            non_technical: bool = False) -> str
"""
from __future__ import annotations

import re

# Intents where code blocks are *probably* illustrative (i.e. not for
# the dev's project) and should be stripped.
_NON_BUILD_INTENTS = {
    "question", "conversational", "strategic", "unknown", "diagnostic",
}

# Fenced code blocks of any language.  Captures the language tag in
# group(1) and the body in group(2). Non-greedy so multiple blocks in
# one reply each match individually.
_FENCE_RE = re.compile(
    r"```([A-Za-z0-9_+\-]*)\s*\n(.*?)```",
    re.DOTALL,
)

# Inline "pseudo-code-ish" patterns we want to flag inside fenced blocks
# (def, lambda, if/else, dict literal, function call signature).
_PSEUDO_HINT_RE = re.compile(
    r"^\s*(def\s+\w+\s*\(|class\s+\w+|"
    r"if\s+\w.+?:\s*$|elif\s+\w.+?:\s*$|else\s*:|"
    r"for\s+\w+\s+in\s+|while\s+|"
    r"return\s+|"
    r"\w+\s*=\s*\{|"           # dict literal assignment
    r"\w+\s*=\s*\[|"           # list literal assignment
    r"\w+\s*=\s*lambda)",
    re.M,
)


def _looks_like_pseudo_code(body: str, lang: str) -> bool:
    """Returns True when the fenced block looks like illustrative
    pseudo-code (Python/JS-ish syntax) rather than a real config file
    or a quoted chunk of natural language."""
    if lang.lower() in {"python", "py", "javascript", "js", "ts",
                         "typescript", "jsx", "tsx"}:
        return True
    # No language tag — sniff the body.
    return bool(_PSEUDO_HINT_RE.search(body))


def strip_illustrative_code(
    reply: str,
    *,
    intent: str,
    non_technical: bool = False,
) -> str:
    """Remove illustrative code fences from a non-build reply.

    Build replies are returned untouched. For non-build replies (or
    when non_technical=True), every fenced block that looks like
    pseudo-code is replaced with a short prose breadcrumb so the
    surrounding sentences still make sense.

    Idempotent and side-effect free.
    """
    if not reply:
        return reply
    if intent == "build" and not non_technical:
        return reply
    if intent not in _NON_BUILD_INTENTS and not non_technical:
        return reply

    def _repl(m: re.Match) -> str:
        lang = (m.group(1) or "").strip()
        body = m.group(2) or ""
        if not _looks_like_pseudo_code(body, lang):
            # Looks like a config snippet, JSON example, etc. — keep
            # it. We only strip Python/JS-style illustrative code.
            return m.group(0)
        # Replace with a single neutral line so paragraph flow survives.
        return "(skipped a pseudo-code block — see plain explanation above)"

    cleaned = _FENCE_RE.sub(_repl, reply)
    # Tidy duplicate blank lines that fence removal can leave behind.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned
