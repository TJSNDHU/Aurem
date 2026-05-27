"""
test_self_awareness_d39.py — iter D-39

Asserts the AUREM CTO base prompt now teaches the LLM:
  - what it actually is (specific architecture, not generic "I'm a senior engineer")
  - to never fabricate stats
  - to mirror the user's language
  - to use plain sentences when asked introspective questions

Asserts the intent classifier now routes introspective phrasing
("how do you work", "tum kaise kaam karte ho", "your workflow")
to the `question` bucket — even when keywords like "plan" or "workflow"
would otherwise hit the build bucket.
"""
from __future__ import annotations

import sys
sys.path.insert(0, "/app/backend")

import pytest


# ── 1. Base SYSTEM_PROMPT carries the new self-awareness block ───────

def test_base_prompt_includes_architecture_block():
    from services.dev_cto_chat import SYSTEM_PROMPT
    # Collapse whitespace so multi-line word breaks (e.g. "AUREM Design\n
    # System") still match the needle list.
    flat = " ".join(SYSTEM_PROMPT.split())
    needles = (
        "WHAT YOU ACTUALLY ARE",
        "intent classification",
        "AUREM Design System",
        "codebase indexer",
        "Tavily",
        "deploy to a customer-owned server",
        "dry-run",
        "rollback",
        "75",                # pytest count phrasing
        "token wallet",
        "1,000-token signup grant",
    )
    for n in needles:
        assert n in flat, f"base prompt missing '{n}'"


def test_base_prompt_forbids_fabrication():
    from services.dev_cto_chat import SYSTEM_PROMPT
    # Explicit "never invent stats" line must be there.
    assert "NEVER fabricate" in SYSTEM_PROMPT
    assert "185 bugs" in SYSTEM_PROMPT,  \
        "explicit example of the fabricated stat is missing — must be in the prompt as a negative example"
    assert "I don't have that number" in SYSTEM_PROMPT


def test_base_prompt_includes_language_mirroring():
    from services.dev_cto_chat import SYSTEM_PROMPT
    assert "LANGUAGE MIRRORING" in SYSTEM_PROMPT
    assert "Hinglish" in SYSTEM_PROMPT
    # The "scan in English" log-friendly trailer must be required.
    assert "(en:" in SYSTEM_PROMPT


def test_base_prompt_blocks_python_pseudo_code_for_introspection():
    from services.dev_cto_chat import SYSTEM_PROMPT
    assert "use plain sentences"  in SYSTEM_PROMPT.lower() \
        or "plain sentences"      in SYSTEM_PROMPT.lower()
    # Pseudo-code is only for actual code generation
    assert "Code blocks are only for code you're producing" in SYSTEM_PROMPT


# ── 2. Intent classifier routes introspection to `question` ──────────

@pytest.mark.parametrize("text", [
    # English
    "how do you work?",
    "explain your workflow",
    "what are your capabilities",
    "what can't you do",
    "describe your architecture",
    "can you show me your working flow how you think best way to complete tasks",
    # Hinglish / Hindi (matches the founder's actual phrasing)
    "tum kaise kaam karte ho",
    "aap kaise sochte ho",
    "tum kya kar sakte ho",
])
def test_introspection_routes_to_question(text):
    from services.aurem_cto_intent import classify_intent
    got = classify_intent(text)
    assert got == "question", \
        f"introspective '{text}' classified as {got}, expected 'question'"


# ── 3. Question prompt branch forbids fabricated stats ───────────────

def test_question_branch_warns_against_invented_stats():
    from services.aurem_cto_intent import system_prompt_for
    p = system_prompt_for("question")
    assert "NEVER invent statistics" in p
    # The suffix references the base prompt's "WHAT YOU ACTUALLY ARE"
    # block; just confirm the cross-reference token is present.
    assert "WHAT YOU" in p and "ACTUALLY ARE" in p
    assert "Python pseudo-code"      in p
