"""
tests/test_non_tech_no_code_d40b.py — iter D-40b

Regression tests for the founder-reported bug: AUREM CTO dumped Python
pseudo-code (`def distill_idea(...)`, `patterns = {...}`) when asked
the META question "how do you reply to a non-tech customer?".

We test two layers:
  1. The output-guard helper directly (deterministic, no LLM call).
  2. classify_intent + is_non_technical return the expected buckets
     for the founder's actual prompt.
"""
from __future__ import annotations

import os
import sys

# Allow running this file from /app/backend with `pytest tests/...`.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.aurem_cto_intent import classify_intent, is_non_technical
from services.aurem_cto_output_guard import strip_illustrative_code


# ──────────────────────────────────────────────────────────────────
# Intent / non-tech classification on the founder's actual message
# ──────────────────────────────────────────────────────────────────

FOUNDER_META_QUESTION = (
    "how you reply to any non tech customer who share you idea and "
    "ask to suggest batter and customer want to build something .... "
    "what do background and how you reply to that non tech background "
    "customer ???"
)


def test_founder_meta_question_is_a_question():
    """`how you reply...` must classify as 'question' (introspective),
    NOT as 'build' — otherwise the LLM uses the full build scaffold."""
    assert classify_intent(FOUNDER_META_QUESTION) == "question"


def test_founder_meta_question_flagged_non_tech():
    """The phrase mentions 'non tech customer' and 'customer want to
    build' — must be flagged so the NON-TECH suffix is appended."""
    assert is_non_technical(FOUNDER_META_QUESTION) is True


# ──────────────────────────────────────────────────────────────────
# Output guard — the actual deterministic safety net
# ──────────────────────────────────────────────────────────────────

# The actual reply the founder pasted in (excerpt sufficient for the
# test). It contains 3 illustrative Python blocks that must all be
# stripped when the intent is non-build.
ROBOTIC_REPLY = """\
Here's my approach for non-technical customers:
### 1. Simplify the Idea (30 sec)
```python
def distill_idea(raw_input):
    return {
        "problem": extract_problem_statement(raw_input),
        "audience": identify_target_users(raw_input),
        "value": articulate_unique_value(raw_input)
    }
```
### 2. Map to Patterns (60 sec)
```python
patterns = {
    "social": ["feed", "profiles", "messaging"],
    "marketplace": ["listings", "reviews", "payments"],
}
```
### 3. Suggest Next Steps
```python
def suggest_steps(customer_type):
    if customer_type == "founder":
        return ["MVP scope", "Tech stack", "Hiring"]
```
### Example Response Flow:
1. Understand: "Let me make sure I get this right..."
2. Frame: "This reminds me of..."
"""


def test_guard_strips_python_blocks_for_question_intent():
    """Question intent → all illustrative Python blocks must go."""
    cleaned = strip_illustrative_code(
        ROBOTIC_REPLY, intent="question", non_technical=True,
    )
    assert "```python" not in cleaned
    assert "def distill_idea" not in cleaned
    assert "patterns = {" not in cleaned
    assert "def suggest_steps" not in cleaned
    # Surrounding prose must survive.
    assert "Simplify the Idea" in cleaned
    assert "Example Response Flow" in cleaned


def test_guard_strips_for_conversational_intent_too():
    cleaned = strip_illustrative_code(
        ROBOTIC_REPLY, intent="conversational",
    )
    assert "def distill_idea" not in cleaned


def test_guard_strips_when_non_tech_even_if_intent_build():
    """Non-tech customer ALWAYS gets prose — even if intent==build."""
    cleaned = strip_illustrative_code(
        ROBOTIC_REPLY, intent="build", non_technical=True,
    )
    assert "def distill_idea" not in cleaned


def test_guard_leaves_build_intent_untouched_for_tech_dev():
    """For a build turn from a tech dev, code blocks ARE legitimate.
    They must survive intact."""
    cleaned = strip_illustrative_code(
        ROBOTIC_REPLY, intent="build", non_technical=False,
    )
    assert "def distill_idea" in cleaned
    assert "```python" in cleaned


def test_guard_handles_empty_reply():
    assert strip_illustrative_code("", intent="question") == ""
    assert strip_illustrative_code(None, intent="question") is None  # type: ignore[arg-type]


def test_guard_preserves_real_config_fences():
    """A JSON/yaml/text fence in a non-build reply is NOT pseudo-code
    and should survive (we only strip Python/JS-ish code)."""
    reply = (
        "Your config should look like this:\n"
        "```json\n{\"port\": 8001, \"host\": \"0.0.0.0\"}\n```\n"
        "That's it."
    )
    cleaned = strip_illustrative_code(reply, intent="question")
    assert "\"port\": 8001" in cleaned
    assert "```json" in cleaned


def test_guard_idempotent():
    once = strip_illustrative_code(
        ROBOTIC_REPLY, intent="question", non_technical=True,
    )
    twice = strip_illustrative_code(
        once, intent="question", non_technical=True,
    )
    assert once == twice
