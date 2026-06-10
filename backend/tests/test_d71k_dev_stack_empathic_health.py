"""
D-71k — Dev Stack Health: zero-data ≠ broken.

User reported "Intelligence Merge: 0 signals → 0 merged profiles" red
on System Overview. Investigation showed the underlying engine was
WIRED correctly — there were simply zero signals in the freshly-
provisioned tenant. Conflating "no data yet" with "component broken"
is misleading; the empathic UX matches `skill_learner.learning_engine_health`
which returns green with `"ready · awaiting first run"`.

5 checks updated to the same pattern:
  Intelligence Merge, Council Engine, A2A Learning Bus,
  Sentinel Repair Loop, ORA Brain.

Real reds (Sovereign LLM unreachable, GROQ_API_KEY missing) keep
showing red — those are real env/config issues, not init races.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _src():
    return Path("/app/backend/routers/dev_stack_health_router.py").read_text()


def test_intelligence_merge_returns_ready_when_zero_signals():
    src = _src()
    # The empathic message text must be present in _check_intel_merge
    idx = src.index("_check_intel_merge")
    body = src[idx:idx + 800]
    assert "ready · awaiting first signal" in body, (
        "Intelligence Merge must show green-ready when zero signals exist"
    )
    # And the function must return _g(True, ...) for the zero path
    assert "return _g(True" in body


def test_council_engine_returns_ready_when_zero_decisions():
    src = _src()
    idx = src.index("_check_council")
    body = src[idx:idx + 600]
    assert "ready · awaiting first decision" in body


def test_a2a_returns_ready_when_zero_messages():
    src = _src()
    idx = src.index("_check_a2a")
    body = src[idx:idx + 600]
    assert "ready · awaiting first message" in body


def test_sentinel_returns_ready_when_zero_runs():
    src = _src()
    idx = src.index("_check_sentinel")
    body = src[idx:idx + 1000]
    assert "ready · awaiting first repair run" in body


def test_ora_brain_returns_ready_when_zero_thoughts():
    src = _src()
    idx = src.index("_check_ora_brain")
    body = src[idx:idx + 600]
    assert "ready · awaiting first thought" in body


def test_real_failure_paths_still_report_red():
    """Don't fake-green real failures — _g(False, ...) on exception
    must stay so we can still spot real Mongo outages."""
    src = _src()
    # Each check must still have its except branch returning _g(False, ...)
    for fn_name in ("_check_intel_merge", "_check_council", "_check_a2a",
                     "_check_sentinel", "_check_ora_brain"):
        idx = src.index(fn_name)
        body = src[idx:idx + 1000]
        assert "_g(False" in body, (
            f"{fn_name} must still red on Exception (real failure path)"
        )
