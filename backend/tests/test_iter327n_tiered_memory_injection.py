"""
iter 327n — Tiered memory injection into ORA's SYSTEM_PROMPT.

Founder mandate (verbatim, 2026-02-23):
  "Iter 327n — smart memory injection:
     TIER 1 — inject every conversation (8000 char cap):
       - dev_zero-hallucination-charter.md
       - dev_322ey-ora-mistakes-lessons.md  (was: ora-mistakes-lessons)
       - WATCHDOG_MODE.md
       - WORKING_POLICY.md
       - SYSTEM_MAP.md (first 1500 chars)
     TIER 2 — inject when task is relevant
     TIER 3 — search via existing tools"

What this iter delivers:
  1. services/ora_lessons_loader.py
       - build_lessons_block() — Tier-1, 8000-char cap, runs once at
         module import.
       - relevant_tier2_blocks(user_text) — keyword-gated, per turn.
       - Best-effort: missing files → skip + log, never raise.
  2. services/ora_agent.py
       - SYSTEM_PROMPT is extended at module load with the Tier-1
         block (so every conversation gets it).
       - process_message inserts a Tier-2 SYSTEM message right before
         the user turn when keywords match.
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────
# Tier-1 loader: builds the always-injected block
# ─────────────────────────────────────────────

def test_tier1_block_includes_all_five_sources():
    from services.ora_lessons_loader import build_lessons_block
    block = build_lessons_block()
    assert block, "tier-1 block is empty — files must exist on disk"
    # All five labels MUST be present.
    for label in (
        "ZERO-HALLUCINATION CHARTER",
        "ORA MISTAKES — DO NOT REPEAT",
        "WATCHDOG MODE",
        "WORKING POLICY",
        "SYSTEM MAP (summary)",
    ):
        assert label in block, f"missing {label} in tier-1"


def test_tier1_block_is_capped_at_8000_chars():
    from services.ora_lessons_loader import build_lessons_block, _TIER1_CAP_TOTAL
    block = build_lessons_block()
    assert len(block) <= _TIER1_CAP_TOTAL + 64, (
        f"tier-1 block {len(block)} > cap {_TIER1_CAP_TOTAL}"
    )


def test_tier1_block_starts_with_rule_book_header():
    """The LLM needs a clear marker so it knows where founder rules
    start vs. the generic system prompt."""
    from services.ora_lessons_loader import build_lessons_block
    block = build_lessons_block()
    assert "FOUNDER'S RULE BOOK" in block


def test_tier1_is_actually_appended_to_system_prompt():
    """End-to-end: the lessons block is concatenated onto
    SYSTEM_PROMPT at module import."""
    from services.ora_agent import SYSTEM_PROMPT
    assert "FOUNDER'S RULE BOOK" in SYSTEM_PROMPT
    # Sanity: at least one specific phrase from the loaded files.
    # We don't pin a single phrase because the source files may
    # evolve — instead check the structural marker is present.
    assert "ZERO-HALLUCINATION CHARTER" in SYSTEM_PROMPT
    assert "ORA MISTAKES — DO NOT REPEAT" in SYSTEM_PROMPT


def test_tier1_loader_never_raises_on_missing_file(tmp_path, monkeypatch):
    """If a tier-1 source is deleted in some weird deploy, the
    loader must skip it and still return a usable block."""
    from services import ora_lessons_loader as ll
    # Replace one entry with a non-existent path; reload by calling
    # the function — _read_capped returns None and we move on.
    orig = list(ll._TIER1_FILES)
    monkeypatch.setattr(
        ll, "_TIER1_FILES",
        [("FAKE", "/nope/does-not-exist.md", 2000)] + orig,
    )
    out = ll.build_lessons_block()
    assert "FAKE" not in out
    # Real files still loaded.
    assert "WATCHDOG MODE" in out


# ─────────────────────────────────────────────
# Tier-2 loader: keyword-gated per-turn injection
# ─────────────────────────────────────────────

def test_tier2_returns_empty_for_unrelated_text():
    from services.ora_lessons_loader import relevant_tier2_blocks
    assert relevant_tier2_blocks("what's the weather today") == ""
    assert relevant_tier2_blocks("") == ""


def test_tier2_fires_on_security_keywords():
    from services.ora_lessons_loader import relevant_tier2_blocks
    out = relevant_tier2_blocks("review the JWT auth flow")
    assert "SECURITY PATTERNS" in out


def test_tier2_fires_on_outreach_keywords_with_casl_label():
    from services.ora_lessons_loader import relevant_tier2_blocks
    out = relevant_tier2_blocks(
        "start a cold email blast campaign for new leads"
    )
    assert "CASL + OUTREACH RULES" in out


def test_tier2_fires_on_debug_keywords_with_architecture():
    from services.ora_lessons_loader import relevant_tier2_blocks
    out = relevant_tier2_blocks(
        "why does the campaign endpoint crash with a 500 error"
    )
    assert "ARCHITECTURE" in out


def test_tier2_does_not_double_inject_same_file_for_two_rules():
    """SECURITY PATTERNS matches both 'security' and 'casl' rules
    but the file should appear only once."""
    from services.ora_lessons_loader import relevant_tier2_blocks
    out = relevant_tier2_blocks("CASL security audit on outreach blast")
    # First match wins (SECURITY PATTERNS label, NOT CASL+OUTREACH label).
    assert out.count("=== SECURITY PATTERNS ===") == 1
    assert "=== CASL + OUTREACH RULES" not in out


def test_tier2_blocks_capped_per_file():
    from services.ora_lessons_loader import relevant_tier2_blocks, _TIER2_CAP_PER_FILE
    out = relevant_tier2_blocks("security audit")
    # Cap + header/footer overhead < cap + 200 chars.
    assert len(out) <= _TIER2_CAP_PER_FILE + 300


# ─────────────────────────────────────────────
# process_message integration (source-level)
# ─────────────────────────────────────────────

def test_process_message_calls_relevant_tier2_blocks():
    src = (BACKEND / "services" / "ora_agent.py").read_text()
    assert "from services.ora_lessons_loader import relevant_tier2_blocks" in src
    assert "history.insert(-1, {\"role\": \"system\", \"content\": _t2})" in src


def test_iter_marker_present():
    src_loader = (BACKEND / "services" / "ora_lessons_loader.py").read_text()
    src_agent  = (BACKEND / "services" / "ora_agent.py").read_text()
    assert "iter 327n" in src_loader
    assert "iter 327n" in src_agent
