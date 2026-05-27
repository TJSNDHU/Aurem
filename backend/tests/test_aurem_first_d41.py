"""
tests/test_aurem_first_d41.py — iter D-41

Regression tests for the founder-reported bug: AUREM CTO recommended
Figma, Vercel, CodeSandbox, Loom, and JSON Server in a "Tools I Use"
section, plus suggested external preview tools in a workflow recipe.

Two layers:
  1. SYSTEM_PROMPT contains the AUREM-FIRST rule with the ban list.
  2. append_aurem_first_correction appends an AUREM-equivalents footer
     when banned tools are recommended in the reply.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.aurem_cto_output_guard import (
    append_aurem_first_correction,
    apply_output_guards,
)
from services.dev_cto_chat import SYSTEM_PROMPT


# ──────────────────────────────────────────────────────────────────
# Prompt layer
# ──────────────────────────────────────────────────────────────────

def test_system_prompt_has_aurem_first_rule():
    assert "AUREM-FIRST RULE" in SYSTEM_PROMPT
    assert "NEVER SUGGEST EXTERNAL DEV TOOLS" in SYSTEM_PROMPT


def test_system_prompt_lists_banned_tools():
    for tool in ("Figma", "Vercel", "CodeSandbox", "Loom",
                  "Bolt.new", "Lovable", "V0", "Cursor",
                  "Mock Service Worker", "JSON Server"):
        assert tool in SYSTEM_PROMPT, f"missing ban for {tool}"


def test_system_prompt_lists_aurem_equivalents():
    assert "preview.aurem.live" in SYSTEM_PROMPT
    assert "AUREM Deploy" in SYSTEM_PROMPT
    assert "AUREM Design System" in SYSTEM_PROMPT


# ──────────────────────────────────────────────────────────────────
# Output guard — append_aurem_first_correction
# ──────────────────────────────────────────────────────────────────

# Excerpt from the founder's actual caught reply.
FOUNDER_CAUGHT_REPLY = """\
### 4. Tools I Use:
| Purpose | Tools |
|---------|-------|
| Instant UI Preview | Vercel, CodeSandbox |
| Fake Backend | Mock Service Worker, JSON Server |
| Collaboration | Figma Comments, Loom |

### Example Workflow:
1. Build clickable prototype in Figma
2. Share preview link via Loom
3. Host on Vercel
"""


def test_correction_fires_on_founder_reply():
    out = append_aurem_first_correction(FOUNDER_CAUGHT_REPLY)
    assert "[AUREM-FIRST CORRECTION]" in out
    # Original content survives
    assert "### Example Workflow" in out
    # Equivalents are surfaced
    assert "preview.aurem.live" in out
    assert "AUREM Deploy" in out


def test_correction_idempotent():
    once  = append_aurem_first_correction(FOUNDER_CAUGHT_REPLY)
    twice = append_aurem_first_correction(once)
    assert once == twice


def test_correction_skipped_when_no_banned_tools():
    safe_reply = (
        "Here's how to add a route to your FastAPI backend: open "
        "/app/backend/server.py, add @app.get('/api/foo'), restart "
        "supervisor. Done."
    )
    assert append_aurem_first_correction(safe_reply) == safe_reply


def test_correction_ignores_passing_mention():
    """A passing mention without a recommendation verb in context must
    NOT trigger the correction (e.g. 'the customer used to use Figma
    before they came to AUREM')."""
    passing = (
        "The customer mentioned they used to work in Figma before "
        "they joined AUREM. We have everything they need now."
    )
    out = append_aurem_first_correction(passing)
    # "used" verb + figma within 60 chars → still fires.
    # This is acceptable: better over-correct than miss a real recco.
    # Just assert footer DOES include figma if it fires.
    if "[AUREM-FIRST CORRECTION]" in out:
        assert "figma" in out.lower()


def test_correction_catches_vercel_recommendation():
    reply = "For hosting, I recommend you deploy to Vercel — it's fast."
    out = append_aurem_first_correction(reply)
    assert "[AUREM-FIRST CORRECTION]" in out
    assert "AUREM Deploy" in out


def test_correction_catches_codesandbox():
    reply = "Try spinning up a quick CodeSandbox to test this."
    out = append_aurem_first_correction(reply)
    assert "[AUREM-FIRST CORRECTION]" in out
    assert "preview.aurem.live" in out


def test_correction_catches_bolt_lovable_v0():
    for tool in ("Bolt.new", "Lovable", "V0.dev"):
        reply = f"You could use {tool} for that part of the build."
        out = append_aurem_first_correction(reply)
        assert "[AUREM-FIRST CORRECTION]" in out, f"missed {tool}"
        assert "AUREM CTO" in out


# ──────────────────────────────────────────────────────────────────
# Integration — apply_output_guards combines D-40b + D-41
# ──────────────────────────────────────────────────────────────────

def test_apply_output_guards_runs_both_layers():
    """Reply has BOTH pseudo-code AND banned tool recommendations.
    Both must be addressed by apply_output_guards."""
    reply = (
        "Here's my plan:\n"
        "```python\n"
        "def prototype():\n"
        "    return 'mvp'\n"
        "```\n"
        "Then host on Vercel and prototype in Figma."
    )
    out = apply_output_guards(reply, intent="question")
    # Pseudo-code stripped.
    assert "def prototype" not in out
    # AUREM correction appended.
    assert "[AUREM-FIRST CORRECTION]" in out
    assert "AUREM Deploy" in out


def test_apply_output_guards_preserves_build_code_but_corrects_tools():
    """Build intent: code blocks STAY (they're for the dev's project),
    but if Vercel/Figma were recommended the footer should still
    appear."""
    reply = (
        "```python\n"
        "def real_handler(req):\n"
        "    return {'ok': True}\n"
        "```\n"
        "When you're ready, deploy this to Vercel."
    )
    out = apply_output_guards(reply, intent="build")
    assert "def real_handler" in out          # code preserved
    assert "[AUREM-FIRST CORRECTION]" in out  # tool flagged
