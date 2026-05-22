"""
test_iter326n_ora_voice_plain_english.py — Regression for iter 326n.
══════════════════════════════════════════════════════════════════════════════
The founder's request (verbatim): "I'm a non tech founder vibecoder so it
must be reply me in english human language. Fix in my system production."

Three system prompts were instructing ORA to reply in Hinglish (Hindi-
English mix). They all needed to switch to plain English, with explicit
language guards so the LLM is told once and reminded inside its rule list:

  1. services/ora_agent.py   SYSTEM_PROMPT
  2. services/ora_brain.py   _MODE_2_SYSTEM_PROMPT
  3. services/ora_proposal_bridge.py  _TRANSLATE_SYSTEM

This file locks in the change so a future agent can't quietly revert it
without the test failing.

Run:  cd /app/backend && python3 -m pytest tests/test_iter326n_ora_voice_plain_english.py -v
"""
from __future__ import annotations

import re


# ─────────────────────────────────────────────────────────────────────────────
# 1) ora_agent.py — main chat system prompt
# ─────────────────────────────────────────────────────────────────────────────
def test_ora_agent_main_prompt_speaks_plain_english_only():
    """The main ORA chat prompt must contain a 'Plain English ONLY' rule
    AND must NOT carry the older Hinglish-preferred language."""
    from services.ora_agent import SYSTEM_PROMPT

    # Forced opt-in language — the new rule.
    assert "Plain English ONLY" in SYSTEM_PROMPT, (
        "Rule Zero (plain English only) is missing from ora_agent SYSTEM_PROMPT"
    )
    assert "non-technical" in SYSTEM_PROMPT.lower() or "non tech" in SYSTEM_PROMPT.lower()

    # Forbidden carry-overs — these instructions used to push Hinglish.
    forbidden_substrings = [
        "founder prefers Hinglish",
        "plain Hindi/English mix",
        "occasionally Hinglish/Punjabi when",
        # The old Build-Mode rule explicitly said "in Hinglish"
        "Write 3-7 lines in Hinglish",
    ]
    for s in forbidden_substrings:
        assert s not in SYSTEM_PROMPT, (
            f"Old Hinglish instruction still present in SYSTEM_PROMPT: {s!r}"
        )


def test_ora_agent_prompt_includes_jargon_translation_table():
    """The translation table is the operational guarantee — without it
    the model just gets a vague 'plain English' instruction and slips
    back into engineer-speak. Lock the most important translations in."""
    from services.ora_agent import SYSTEM_PROMPT

    must_have_translations = [
        "your records",      # for "database / MongoDB"
        "publish to your live site",  # for "deploy / push"
        "doors to the database",      # for "connection pool"
        "the engine",        # for "backend"
        "the screen the user sees",   # for "frontend"
    ]
    for phrase in must_have_translations:
        assert phrase in SYSTEM_PROMPT, (
            f"Jargon-translation phrase missing from SYSTEM_PROMPT: {phrase!r}"
        )


def test_ora_agent_prompt_keeps_safety_first_for_distress():
    """The new prompt must STILL tell ORA to acknowledge a distressed
    founder as a human first, before any technical reply. This is a
    hard safety line we will not regress on."""
    from services.ora_agent import SYSTEM_PROMPT

    assert "9152987821" in SYSTEM_PROMPT, "iCall hotline missing from prompt"
    assert "1860-2662-345" in SYSTEM_PROMPT, "Vandrevala hotline missing from prompt"
    # Wording can be paraphrased, but the intent must be present.
    assert (
        "Code can wait" in SYSTEM_PROMPT
        or "Acknowledge them as a human" in SYSTEM_PROMPT
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2) ora_brain.py — Mode-2 engineering proposal prompt
# ─────────────────────────────────────────────────────────────────────────────
def test_ora_brain_mode2_prompt_speaks_plain_english_only():
    from services.ora_brain import _MODE_2_SYSTEM_PROMPT as P

    assert "PLAIN ENGLISH ONLY" in P or "Plain English regardless" in P
    assert "PLAIN ENGLISH SUMMARY" in P, (
        "Mode-2 must emit a plain-English summary section ABOVE the "
        "engineering detail — without that the founder sees raw TARGET "
        "FILE / SUGGESTED PATCH first and gives up."
    )


def test_ora_brain_mode2_prompt_drops_old_persona_signature():
    """The old prompt ended every complex answer with the Hinglish-
    flavoured signature 'Anything else, boss?'. With the voice change,
    that signature line is removed."""
    from services.ora_brain import _MODE_2_SYSTEM_PROMPT as P

    assert "Anything else, boss" not in P


# ─────────────────────────────────────────────────────────────────────────────
# 3) ora_proposal_bridge.py — Approve/Reject card translation layer
# ─────────────────────────────────────────────────────────────────────────────
def test_proposal_bridge_translates_to_plain_english():
    """The translation system prompt for proposal cards is what the
    founder reads in the [Approve] / [Reject] modal. It used to ask the
    LLM for Hinglish output. Confirm that's now plain English."""
    from services.ora_proposal_bridge import _TRANSLATE_SYSTEM

    # Must explicitly say plain English and explicitly forbid Hinglish.
    assert "plain English" in _TRANSLATE_SYSTEM
    assert (
        "NO Hinglish" in _TRANSLATE_SYSTEM
        or "No Hindi" in _TRANSLATE_SYSTEM
        or "no Hinglish" in _TRANSLATE_SYSTEM.lower()
    )

    # Old Hinglish example sentence must be gone.
    assert "Tera checkout page pe error" not in _TRANSLATE_SYSTEM
    # JSON schema field NAMES are unchanged (so call sites still work).
    for field in ("problem_found", "what_will_change",
                  "impact_if_approved", "risk_if_rejected"):
        assert field in _TRANSLATE_SYSTEM


def test_proposal_bridge_translation_fallback_in_english():
    """The hard-coded fallback (used when the LLM is unavailable) must
    also be in plain English, otherwise a degraded provider would still
    leak Hinglish into the founder's UI."""
    import inspect
    import services.ora_proposal_bridge as bridge

    src = inspect.getsource(bridge._translate_to_plain_language)
    # The fallback string itself.
    assert "Translation unavailable" in src
    # No Hinglish words leaking through the fallback.
    for hinglish_token in ["pe error", "raha hai", "kar do", "tera ", "tumhara"]:
        assert hinglish_token not in src, (
            f"Hinglish token leaked into fallback: {hinglish_token!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Cross-file invariant — none of the 3 prompts should be empty after edits
# (would silently disable the rules).
# ─────────────────────────────────────────────────────────────────────────────
def test_all_three_prompts_are_substantial():
    from services.ora_agent import SYSTEM_PROMPT as P1
    from services.ora_brain import _MODE_2_SYSTEM_PROMPT as P2
    from services.ora_proposal_bridge import _TRANSLATE_SYSTEM as P3

    # Sanity floors — these will only fail if someone accidentally
    # truncates the prompt during a future edit.
    assert len(P1) > 2000, f"ora_agent SYSTEM_PROMPT shrank to {len(P1)} chars"
    assert len(P2) > 600, f"ora_brain Mode-2 prompt shrank to {len(P2)} chars"
    assert len(P3) > 600, f"ora_proposal_bridge translate prompt shrank to {len(P3)} chars"
