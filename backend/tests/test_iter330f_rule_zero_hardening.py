"""
iter 330f — Rule Zero hardening (closes 3 holes from 330e audit)
================================================================

Three hardening passes on top of iter 330e:

(a) Two hard-coded halt strings inside the ORA tool loop were in
    Hindi/Urdu mixed with English, violating Rule Zero. Rewritten
    to plain English:
      • "founder se discuss kar lo"
            → "I need your input before continuing."
      • "Yeh code ki galti nahi, environment issue lag raha hai."
            → "This looks like an environment issue, not a code
               problem."

(b) `clean_prose()` now also strips raw JSON blocks and fenced
    code blocks before the rest of the AI-tell pipeline runs.
    Inline backtick references (e.g. `tool_name`) are left
    untouched. Stripped blocks are replaced with the placeholder
    "[details available on request]".

(c) The prose filter is now applied on EVERY assistant-role
    history append via a central `_assistant_append()` helper —
    not only on the LLM's final turn. That covers the 5 other
    sites:
      • prompt-injection block reply
      • intent fast-path reply
      • wall-clock budget halt message
      • consecutive-fail halt message
      • transient-fail halt message
"""
from __future__ import annotations

from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
AGENT_SRC  = (BACKEND / "services" / "ora_agent.py").read_text()
PROSE_SRC  = (BACKEND / "services" / "ora_prose_filter.py").read_text()


# ─────────────────────────────────────────────────────────
# (a) Plain-English halt strings
# ─────────────────────────────────────────────────────────

def test_halt_messages_use_plain_english():
    # Old Hindi copy must be gone
    assert "founder se discuss kar lo" not in AGENT_SRC
    assert "Yeh code ki galti nahi" not in AGENT_SRC
    assert "lag raha hai" not in AGENT_SRC
    # New English copy must be present
    assert "I need your input before continuing." in AGENT_SRC
    assert "This looks like an environment issue, not a code problem." in AGENT_SRC


def test_iter_330f_marker_present_in_agent():
    assert "330f" in AGENT_SRC


# ─────────────────────────────────────────────────────────
# (b) clean_prose() strips JSON / fenced blocks
# ─────────────────────────────────────────────────────────

def test_prose_filter_strips_fenced_code_block():
    from services.ora_prose_filter import clean_prose
    sample = (
        "Here's the proof for the wire-up:\n"
        "```json\n"
        "{\n"
        '  "path": "/app/backend/routers/aurem_vanguard_router.py",\n'
        '  "bytes_written": 251\n'
        "}\n"
        "```\n"
        "All good."
    )
    cleaned, stats = clean_prose(sample)
    assert "bytes_written" not in cleaned
    assert "[details available on request]" in cleaned
    assert stats["fenced_stripped"] >= 1


def test_prose_filter_strips_standalone_json_block():
    from services.ora_prose_filter import clean_prose
    sample = (
        "Proof:\n"
        "{\n"
        '  "path": "/app/backend/routers/aurem_vanguard_router.py",\n'
        '  "bytes_written": 251,\n'
        '  "created_at": "2026-05-23T15:44:38.920232+00:00",\n'
        '  "was_overwrite": false\n'
        "}\n"
        "Done."
    )
    cleaned, stats = clean_prose(sample)
    assert "bytes_written" not in cleaned
    assert "was_overwrite" not in cleaned
    assert "[details available on request]" in cleaned
    assert stats["json_stripped"] >= 1


def test_prose_filter_preserves_inline_backtick_refs():
    """Legit short references like `tool_name` or `/api/health` must
    survive the strip pass."""
    from services.ora_prose_filter import clean_prose
    sample = (
        "I called the `create_file` tool against "
        "`/app/backend/tests/test_x.py` and it succeeded."
    )
    cleaned, _ = clean_prose(sample)
    assert "`create_file`" in cleaned
    assert "`/app/backend/tests/test_x.py`" in cleaned


def test_prose_filter_idempotent_after_strip():
    """Running the filter twice on already-stripped text changes nothing."""
    from services.ora_prose_filter import clean_prose
    sample = (
        "Proof:\n"
        "{\n  \"a\": 1,\n  \"b\": 2\n}\n"
        "All good."
    )
    once, _ = clean_prose(sample)
    twice, stats2 = clean_prose(once)
    assert once == twice
    assert stats2["json_stripped"] == 0
    assert stats2["fenced_stripped"] == 0


def test_prose_filter_handles_empty_and_plain_text():
    from services.ora_prose_filter import clean_prose
    empty, _ = clean_prose("")
    assert empty == ""
    plain, _ = clean_prose("Daily hunt finished. 12 leads queued.")
    assert plain == "Daily hunt finished. 12 leads queued."


def test_iter_330f_marker_in_prose_filter():
    assert "330f" in PROSE_SRC


# ─────────────────────────────────────────────────────────
# (c) Prose filter applied on EVERY assistant append
# ─────────────────────────────────────────────────────────

def test_central_assistant_append_helper_exists():
    """The helper that runs prose filter + history.append must exist."""
    assert "def _assistant_append" in AGENT_SRC
    # The helper itself must call clean_prose
    idx = AGENT_SRC.index("def _assistant_append")
    body = AGENT_SRC[idx: idx + 1500]
    assert "from services.ora_prose_filter import clean_prose" in body
    assert "clean_prose(content)" in body


def test_no_raw_assistant_history_append_outside_helper():
    """Only ONE site in the file may do a direct
    `history.append({"role": "assistant", ...})` — the helper itself.
    Every other site MUST route through `_assistant_append(...)` so
    the prose filter runs on EVERY founder-visible turn, not just
    the final LLM reply."""
    import re
    matches = re.findall(
        r'history\.append\(\{"role":\s*"assistant"',
        AGENT_SRC,
    )
    assert len(matches) == 1, (
        f"Expected exactly 1 raw assistant append (inside the helper), "
        f"found {len(matches)}. Every other site must call "
        f"_assistant_append() instead."
    )


def test_all_known_assistant_sites_use_helper():
    """Spot-check each of the 5 non-helper assistant-emit sites that
    Rule Zero must guard."""
    # 1. Prompt-injection block reply
    assert "_assistant_append(history, _PI_BLOCK_REPLY)" in AGENT_SRC
    # 2. Fast-path intent reply
    assert "fast_reply = _assistant_append(history, fast_reply)" in AGENT_SRC
    # 3. Wall-clock halt
    assert "wall_msg = _assistant_append(history, wall_msg)" in AGENT_SRC
    # 4 + 5. Both halt sites for fail/transient
    assert AGENT_SRC.count("stop_msg = _assistant_append(history, stop_msg)") >= 2


def test_final_turn_still_runs_filter():
    """The LLM final turn went from inline `clean_prose(content)`
    to `content = _assistant_append(history, content)`. Either pattern
    is fine, but the final turn MUST still get filtered."""
    assert "content = _assistant_append(history, content)" in AGENT_SRC


# ─────────────────────────────────────────────────────────
# End-to-end proof — Rule Zero leak scenario from the audit
# ─────────────────────────────────────────────────────────

def test_e2e_proof_json_leak_from_audit_now_clean():
    """The exact leak pattern the founder saw in the cockpit screenshot:
    a 'Proof:' header followed by a verbatim tool-result JSON block.
    After 330f, that block becomes the neutral placeholder."""
    from services.ora_prose_filter import clean_prose
    leak_sample = (
        "Proof:\n"
        "\n"
        "{\n"
        '  "path": "/app/backend/routers/aurem_vanguard_router.py",\n'
        '  "bytes_written": 251,\n'
        '  "created_at": "2026-05-23T15:44:38.920232+00:00",\n'
        '  "was_overwrite": false\n'
        "}\n"
        "\n"
        "Wired in 251 bytes."
    )
    cleaned, stats = clean_prose(leak_sample)
    # Verbatim JSON keys/values must be gone
    assert "bytes_written" not in cleaned
    assert "was_overwrite" not in cleaned
    assert "/app/backend/routers/aurem_vanguard_router.py" not in cleaned
    # Placeholder must be present
    assert "[details available on request]" in cleaned
    # Surrounding prose must survive
    assert "Proof:" in cleaned
    assert "Wired in 251 bytes." in cleaned
    # Stats reflect at least one block stripped
    assert stats["json_stripped"] >= 1
