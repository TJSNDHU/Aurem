"""
iter 327b — RULE ZERO reinforcement
====================================

Founder directive (verbatim):
  "ORA still uses jargon even after Rule Zero. Add concrete
  'say X — not Y' examples at the TOP of the rule so the LLM
  hits them first."

Added inside SYSTEM_PROMPT::RULE ZERO:
  - 4 explicit X/Y pairs taken from real ORA replies the founder
    saw recently (council/PBKDF2, shell_exec gated, deepseek 401,
    Stripe usage record).
  - A "WHEN A TOOL FAILS, NEVER SAY" block with the most common
    raw-error phrases ORA was pasting into chat + plain-English
    replacements.
  - A "3-LINE STANDARD" rule capping most replies at 3 lines.

Test surface: source-level only (we don't unit-test live LLM
output — too flaky). We verify the system prompt has all the new
clauses present, in the right position (before LANGUAGE / REPLY
SHAPE) so they're the first thing the LLM brain sees inside RULE
ZERO.
"""
from __future__ import annotations

from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def _read_prompt() -> str:
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    return src[src.index('SYSTEM_PROMPT = """'):]


# ─────────────────────────────────────────────
# Concrete examples present
# ─────────────────────────────────────────────

def test_say_x_not_y_block_exists():
    p = _read_prompt()
    assert 'CONCRETE "SAY X — NOT Y" EXAMPLES' in p
    assert "iter 327b" in p


def test_council_pbkdf2_example_present():
    p = _read_prompt()
    # ✗ shape
    assert "Invoked council_consult with roles" in p
    assert "PBKDF2" in p or "PBKDF2-HMAC-SHA256" in p
    # ✓ shape
    assert "your API keys are now stored safely" in p
    assert "can't read them" in p


def test_shell_exec_gated_example_present():
    p = _read_prompt()
    assert "shell_exec gated" in p
    assert "no secrets were leaked" in p


def test_deepseek_401_example_present():
    p = _read_prompt()
    assert "deepseek 401" in p
    assert "expired login" in p
    assert "OpenRouter key" in p


def test_stripe_usage_record_example_present():
    p = _read_prompt()
    assert "SubscriptionItem.create_usage_record" in p
    assert "Stripe didn't accept your usage update" in p
    assert "Telegram" in p


# ─────────────────────────────────────────────
# Tool-failure replacement block
# ─────────────────────────────────────────────

def test_tool_failure_replacement_block_present():
    p = _read_prompt()
    assert "WHEN A TOOL FAILS, NEVER SAY" in p
    # Banned raw phrases
    for banned in (
        'Tool X failed with error Y',
        "council_consult returned 0 peers",
        "MongoDB ServerSelectionTimeoutError",
        "HTTP 502 from upstream",
        "Pydantic validation error",
    ):
        assert banned in p, f"missing banned phrase: {banned}"
    # Plain-English replacements
    assert "Something went wrong with the email tool" in p
    assert "The database paused for a moment" in p


# ─────────────────────────────────────────────
# 3-line standard
# ─────────────────────────────────────────────

def test_three_line_standard_present():
    p = _read_prompt()
    assert "THE 3-LINE STANDARD" in p
    assert "Line 1 — what you did" in p
    assert "Line 2 — anything broken" in p
    assert "Line 3 — what they should do next" in p


# ─────────────────────────────────────────────
# Position — examples appear BEFORE the LANGUAGE block
# so the LLM hits them first inside RULE ZERO
# ─────────────────────────────────────────────

def test_examples_appear_before_language_block():
    p = _read_prompt()
    examples_idx = p.index('CONCRETE "SAY X — NOT Y" EXAMPLES')
    language_idx = p.index("LANGUAGE\n  •")
    assert examples_idx < language_idx, \
        "concrete examples must appear before the LANGUAGE block"


def test_examples_inside_rule_zero_not_after():
    p = _read_prompt()
    rule_zero_idx = p.index("RULE ZERO — FOUNDER VOICE")
    internal_rules_idx = p.index("INTERNAL OPERATING RULES")
    examples_idx = p.index('CONCRETE "SAY X — NOT Y" EXAMPLES')
    assert rule_zero_idx < examples_idx < internal_rules_idx, \
        "examples must live INSIDE the RULE ZERO block"
