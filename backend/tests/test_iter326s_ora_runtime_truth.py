"""
test_iter326s_ora_runtime_truth.py — Regression for iter 326s.
══════════════════════════════════════════════════════════════════════════════
Founder report (verbatim chat with ORA on aurem.live):
  ORA: "Aapka AUREM Windows par hai, lekin grep_codebase tool
        Linux/Unix-based systems ke liye design kiya gaya hai."
  Founder: "but mujha yaad aya hmm to window pe chla rha hain sbb
            to aura linex kyo show kr rha hai" ("but I remembered —
            we're not running on Windows, why is it showing Linux?")

ROOT CAUSE
──────────
ORA's system prompt did not pin down the runtime environment. When a
tool call failed for an unrelated reason (bad args, missing file, etc),
the LLM filled the explanation gap by INVENTING that AUREM runs on
Windows. Pure hallucination — AUREM is a Linux Kubernetes deployment.
This was the same failure mode as the fake campaign numbers and the
leaked tool-call JSON: when ORA doesn't know something, it makes
something up instead of saying "I don't know".

THE FIX (iter 326s)
──────────────────
Added a "RULE ONE — RUNTIME TRUTH" block at the very top of ORA's
system prompt that locks in non-negotiable facts:
  • OS is Linux (NOT Windows, NOT macOS)
  • Shell tools (bash, grep, sed, awk, curl, ls) ARE available
  • The founder's laptop OS is irrelevant — tools run on the backend
  • Tool errors must NEVER be blamed on the OS

This sits ABOVE the language rule (Rule Zero) because it's a knowledge
truth that protects against hallucination in any language.

Run:  cd /app/backend && python3 -m pytest tests/test_iter326s_ora_runtime_truth.py -v
"""
from __future__ import annotations


def test_runtime_truth_block_locks_in_linux():
    from services.ora_agent import SYSTEM_PROMPT

    assert "RULE ONE — RUNTIME TRUTH" in SYSTEM_PROMPT
    assert "OS:           Linux" in SYSTEM_PROMPT
    # The negative assertion is more important than the positive — we
    # MUST explicitly say "not Windows" and "not macOS" so the model
    # can never invent that excuse again.
    assert "AUREM is NOT on Windows" in SYSTEM_PROMPT
    assert "AUREM is NOT on macOS" in SYSTEM_PROMPT


def test_runtime_truth_lists_available_shell_tools():
    """The model needs to know its OWN tool surface so it stops
    second-guessing whether `grep` works. Listing the available shell
    tools removes the ambiguity it was filling with fabrication."""
    from services.ora_agent import SYSTEM_PROMPT

    must_mention = [
        "bash", "grep", "sed", "awk", "find", "curl", "ls", "cat",
    ]
    for tool in must_mention:
        assert tool in SYSTEM_PROMPT, (
            f"shell tool `{tool}` should be listed in RULE ONE so ORA "
            f"never invents 'this is a Linux tool that won't work here'"
        )


def test_runtime_truth_forbids_blaming_the_os():
    """When a tool fails, ORA must read the actual error — not blame
    the OS. This is what crashed the founder's confidence on the live
    site. Lock the directive in."""
    from services.ora_agent import SYSTEM_PROMPT

    # The hallucinated reply pattern that must never recur
    assert (
        "NEVER reply" in SYSTEM_PROMPT
        and "Linux tool" in SYSTEM_PROMPT
        and "Windows" in SYSTEM_PROMPT
    )
    # The constructive replacement instructions
    assert "Read the actual stderr" in SYSTEM_PROMPT
    assert "Quote the actual error" in SYSTEM_PROMPT
    assert "never blame the OS" in SYSTEM_PROMPT or "Never blame the OS" in SYSTEM_PROMPT


def test_rule_one_precedes_rule_zero():
    """Rule One (RUNTIME TRUTH) must appear ABOVE Rule Zero (VOICE) in
    the prompt. Knowledge truth ranks higher than language style — if
    the model has to drop one rule under pressure, it should drop the
    style instruction, not the platform truth."""
    from services.ora_agent import SYSTEM_PROMPT

    pos_one = SYSTEM_PROMPT.find("RULE ONE — RUNTIME TRUTH")
    pos_zero = SYSTEM_PROMPT.find("RULE ZERO — FOUNDER VOICE")
    assert pos_one > -1 and pos_zero > -1
    assert pos_one < pos_zero, (
        "RULE ONE (RUNTIME TRUTH) must come BEFORE RULE ZERO (VOICE) "
        "so platform knowledge is harder to drop than style."
    )


def test_prompt_still_imports_cleanly():
    """Sanity — after the edit the module must still import without
    syntax errors (catches accidental truncation / unclosed strings)."""
    import importlib
    import services.ora_agent
    importlib.reload(services.ora_agent)
    assert hasattr(services.ora_agent, "SYSTEM_PROMPT")
    assert len(services.ora_agent.SYSTEM_PROMPT) > 3000
