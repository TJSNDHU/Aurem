"""
iter 282al-31 — Continuity fix: short replies ("yes", "option 1") now
route through ORA God-Mode brain when the prior ORA message asked a
question or presented options.

This is a router-behaviour regression test. It doesn't spin up the
actual FastAPI app; instead, it re-implements the gate logic and
exercises every branch.
"""
from __future__ import annotations

import re


# ─── Mirror the router's inline logic exactly ────────────────────────
_AFFIRM_WORDS = {
    "yes", "yeah", "yep", "y", "ok", "okay", "k",
    "sure", "sounds good", "go ahead", "please",
    "no", "nope", "n",
}
_OPTION_RE = re.compile(r"^(option\s*[0-9]+|[0-9]+|first|second|third|both|all)\b")

_ASK_MARKERS = ("?", "would you like", "can i show",
                "want me to", "should i", "option")


def _is_short_affirm(msg: str) -> bool:
    m = (msg or "").strip().lower()
    return m in _AFFIRM_WORDS or bool(_OPTION_RE.match(m))


def _last_ora_asked(text: str) -> bool:
    t = (text or "").lower()
    return any(marker in t for marker in _ASK_MARKERS)


def _should_force_brain(msg: str, last_ora_text: str) -> bool:
    return _is_short_affirm(msg) and _last_ora_asked(last_ora_text)


# ─── Tests ────────────────────────────────────────────────────────────
def test_short_affirm_detects_all_common_yes_variants():
    for m in ("yes", "Yes", "YEP", "yeah", "y", "ok", "OK",
              "sure", "sounds good", "go ahead"):
        assert _is_short_affirm(m), f"failed for {m!r}"


def test_short_affirm_detects_option_replies():
    for m in ("option 1", "Option 2", "option3",
              "1", "2", "first", "Both", "all"):
        assert _is_short_affirm(m), f"failed for {m!r}"


def test_short_affirm_rejects_actual_questions():
    for m in ("tell me about leads", "what is revenue today",
              "show me all the customers and their plans"):
        assert not _is_short_affirm(m), f"wrongly flagged {m!r}"


def test_last_ora_asked_detects_question_mark():
    assert _last_ora_asked("Would you like to see more?")
    assert _last_ora_asked("Any follow-up questions?")


def test_last_ora_asked_detects_offer_phrases():
    assert _last_ora_asked("Want me to pull conversion rates")
    assert _last_ora_asked("Can I show you the dashboard")
    assert _last_ora_asked("Should I scan the site now")
    assert _last_ora_asked("Option 1: recent signups. Option 2: ...")


def test_last_ora_asked_returns_false_for_statements():
    assert not _last_ora_asked("Your site score is 42 out of 100.")
    assert not _last_ora_asked("I've saved the changes.")


# ─── Full gate decision matrix ───────────────────────────────────────
def test_gate_yes_after_question_forces_brain():
    prior = "Would you like to see the snapshot?"
    assert _should_force_brain("yes", prior) is True


def test_gate_option_1_after_offer_forces_brain():
    prior = "Option 1: last 7 days. Option 2: last 30 days. Which one?"
    assert _should_force_brain("option 1", prior) is True


def test_gate_yes_without_prior_question_does_NOT_force():
    prior = "Your morning brief is ready."  # No "?" or offer
    assert _should_force_brain("yes", prior) is False


def test_gate_long_reply_after_question_does_NOT_force():
    """Long replies go through the normal intent pipeline anyway."""
    prior = "Would you like to see more?"
    msg = "tell me which leads signed up this week and show revenue"
    assert _should_force_brain(msg, prior) is False


def test_gate_empty_prior_is_safe():
    assert _should_force_brain("yes", "") is False
    assert _should_force_brain("yes", None) is False


def test_gate_empty_msg_is_safe():
    assert _should_force_brain("", "Would you like to see more?") is False
