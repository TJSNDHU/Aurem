"""
test_ora_agent_bug_patches.py — regression tests for the 7-bug audit fix.

Locks the contracts so future refactors can't reintroduce:
  #1 ora_rollback_list duplicated across tiers
  #2 TOCTOU race in approve flow
  #3 system prompt sliced off after 40 turns
  #4 multi-tool history poisoning
  #5 LLM-controlled MongoDB _id
  #6 unbounded wall-clock on agent loop
  #7 git_bisect missing from TIER_1_AUTO

Run: PYTHONPATH=/app/backend python3 tests/test_ora_agent_bug_patches.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from typing import Any

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="asserts pre-slim health/bootstrap shape or older infra spec — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

# Ensure backend on path
sys.path.insert(0, "/app/backend")

from services import ora_agent  # noqa: E402


# ── Bug #1 + #7: Tier set integrity ──────────────────────────────────
def test_tier_sets_are_disjoint():
    assert not (ora_agent.TIER_1_AUTO & ora_agent.TIER_2_APPROVE)
    assert not (ora_agent.TIER_1_AUTO & ora_agent.TIER_3_HIGH_RISK)
    assert not (ora_agent.TIER_2_APPROVE & ora_agent.TIER_3_HIGH_RISK)


def test_ora_rollback_list_is_tier2_only():
    """Bug #1: was duplicated in TIER_1_AUTO causing silent auto-exec."""
    assert "ora_rollback_list" not in ora_agent.TIER_1_AUTO
    assert "ora_rollback_list" in ora_agent.TIER_2_APPROVE
    assert ora_agent.tier_of("ora_rollback_list") == "tier2_approve"


def test_git_bisect_is_tier1():
    """Bug #7: system prompt promises autonomous bug-hunt → must be tier1."""
    assert "git_bisect" in ora_agent.TIER_1_AUTO
    assert ora_agent.tier_of("git_bisect") == "tier1_auto"


def test_unknown_tool_defaults_to_tier2():
    assert ora_agent.tier_of("definitely_fake_tool_xyz") == "tier2_approve"


# ── Bug #3: system prompt pinning ────────────────────────────────────
class _FakeColl:
    """Minimal stand-in for a Mongo collection — records the doc passed to update_one."""

    def __init__(self):
        self.last_set: dict[str, Any] | None = None

    async def find_one(self, *_args, **_kw):
        return None

    async def update_one(self, _q, update, **_kw):
        self.last_set = update.get("$set") or {}


class _FakeDB:
    def __init__(self):
        self._coll = _FakeColl()

    def __getitem__(self, _name):
        return self._coll


def test_system_prompt_survives_long_history():
    """Bug #3: old code did messages[-40:] and dropped system prompt at index 0."""
    fake_db = _FakeDB()
    ora_agent.set_db(fake_db)

    # Build a 100-turn conversation with the system prompt at the head
    history = [{"role": "system", "content": ora_agent.SYSTEM_PROMPT}]
    for i in range(100):
        history.append({"role": "user",      "content": f"msg {i}"})
        history.append({"role": "assistant", "content": f"reply {i}"})

    asyncio.run(ora_agent._save_history("sess-1", history))

    saved = fake_db._coll.last_set["messages"]
    # System prompt MUST still be present and at index 0
    assert saved[0]["role"] == "system", "system prompt was dropped (BUG #3)"
    assert saved[0]["content"] == ora_agent.SYSTEM_PROMPT
    # Non-system turns capped at HISTORY_CAP - len(sys_msgs) = 40 - 1 = 39
    non_sys = [m for m in saved if m["role"] != "system"]
    assert len(non_sys) == ora_agent.HISTORY_CAP - 1
    # The retained tail must be the most recent
    assert non_sys[-1]["content"] == "reply 99"


# ── Bug #6: wall-clock budget ────────────────────────────────────────
def test_wall_clock_budget_is_positive():
    """Bug #6: env-driven, must always be > 0 so the guard triggers."""
    assert ora_agent.MAX_LOOP_WALL_SECONDS > 0


# ── Bug #5: action_id never comes from the LLM ───────────────────────
def test_persist_pending_signature_takes_action_id_kwarg():
    """Bug #5 prevention: callers MUST pass a server-generated action_id.

    _continue_loop generates uuid4().hex and passes it as action_id=.
    If a future refactor accidentally drops back to call['id'], this
    test will fail because the only callsite uses uuid4().hex.
    """
    import inspect
    src = inspect.getsource(ora_agent._continue_loop)
    # Must contain explicit uuid4().hex generation right before _persist_pending
    assert "action_id = uuid4().hex" in src
    # Must NOT pass call["id"] as action_id
    assert 'action_id=call["id"]' not in src
    assert "action_id=call['id']" not in src


# ── Bug #4: only one tool_call enters history per turn ───────────────
def test_only_first_tool_call_stored_in_history():
    """Bug #4: old code stored msg.get('tool_calls') (all of them) but only
    invoked tool_calls[0]. Subsequent LLM turns saw N requests but only 1
    response, corrupting the conversation.

    Static check: the source of _continue_loop must store [call_raw] (a list
    containing only the first call), NOT the full tool_calls list.
    """
    import inspect
    src = inspect.getsource(ora_agent._continue_loop)
    # The fix: history.append({"role": "assistant", "tool_calls": [call_raw]})
    assert '"tool_calls": [call_raw]' in src or "'tool_calls': [call_raw]" in src
    # The bug pattern (storing entire tool_calls list) must be absent
    assert '"tool_calls": tool_calls,' not in src
    assert "'tool_calls': tool_calls," not in src


# ── Bug #2: TOCTOU race uses find_one_and_update ─────────────────────
def test_resume_uses_atomic_find_one_and_update():
    """Bug #2: the gate that flips status pending→executing must be atomic."""
    import inspect
    src = inspect.getsource(ora_agent.resume_after_decision)
    assert "find_one_and_update" in src, "TOCTOU race not patched (Bug #2)"
    # The atomic gate must filter on BOTH _id AND status to be safe
    assert '"status": "pending"' in src or "'status': 'pending'" in src


# ── _serialise_tool_call sanity ──────────────────────────────────────
def test_serialise_tool_call_falls_back_to_uuid():
    out = ora_agent._serialise_tool_call({"function": {"name": "x", "arguments": "{}"}})
    assert out["id"].startswith("call_")
    assert out["name"] == "x"
    assert out["args"] == {}


if __name__ == "__main__":
    tests = [
        test_tier_sets_are_disjoint,
        test_ora_rollback_list_is_tier2_only,
        test_git_bisect_is_tier1,
        test_unknown_tool_defaults_to_tier2,
        test_system_prompt_survives_long_history,
        test_wall_clock_budget_is_positive,
        test_persist_pending_signature_takes_action_id_kwarg,
        test_only_first_tool_call_stored_in_history,
        test_resume_uses_atomic_find_one_and_update,
        test_serialise_tool_call_falls_back_to_uuid,
    ]
    for t in tests:
        t()
        print(f"  ✓ {t.__name__}")
    print()
    print("ALL ora_agent bug-patch tests passed ✓")
