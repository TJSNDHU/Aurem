"""Tests for Sovereign Truth directive + Data-Anchor (iter 322m Day 3+4)."""
import pytest

from services import ora_council as oc


# ─── Day 3: Sovereign Truth directive embedded in role prompts ─────────
def test_sovereign_truth_prefix_present():
    out = oc._wrap_with_sovereign_truth("You are AUREM's Dev Agent.")
    assert "SOVEREIGN TRUTH PROTOCOL" in out
    assert "INSUFFICIENT_DATA" in out
    # Original role prompt must still be there
    assert "You are AUREM's Dev Agent." in out


def test_sovereign_truth_idempotent():
    """Wrapping twice must not duplicate the directive."""
    once = oc._wrap_with_sovereign_truth("base prompt")
    twice = oc._wrap_with_sovereign_truth(once)
    assert once == twice
    # Only one occurrence of the marker
    assert once.count("SOVEREIGN TRUTH PROTOCOL") == 1


def test_load_skill_prompt_for_unknown_agent_still_wraps():
    """Even fallback prompt for an unknown agent gets wrapped."""
    out = oc._load_skill_prompt("nonexistent_agent_xyz")
    assert "SOVEREIGN TRUTH PROTOCOL" in out


def test_load_skill_prompt_for_dev_wraps_builtin():
    out = oc._load_skill_prompt("dev")
    assert "SOVEREIGN TRUTH PROTOCOL" in out
    assert "AUREM's Dev Agent" in out


# ─── Day 4: Data-Anchor in convene_council ────────────────────────────
@pytest.mark.asyncio
async def test_convene_council_refuses_system_call_without_evidence():
    out = await oc.convene_council(
        "do something",
        context={"source": "latency_guardian"},  # NO evidence
        db=None,
    )
    assert out["ok"] is True
    assert out["data_anchor"] == "refused_no_evidence"
    assert "INSUFFICIENT_DATA" in out["final_response"]
    assert out["winner"] is None


@pytest.mark.asyncio
async def test_convene_council_refuses_when_evidence_is_empty_dict():
    out = await oc.convene_council(
        "do something",
        context={"source": "sovereign_watchdog", "evidence": {}},
        db=None,
    )
    assert out["data_anchor"] == "refused_no_evidence"


@pytest.mark.asyncio
async def test_convene_council_refuses_when_evidence_is_empty_list():
    out = await oc.convene_council(
        "x",
        context={"source": "council_rotation_worker", "evidence": []},
        db=None,
    )
    assert out["data_anchor"] == "refused_no_evidence"


@pytest.mark.asyncio
async def test_convene_council_passes_when_evidence_present(monkeypatch):
    """When evidence IS present, the data-anchor does NOT short-circuit;
    the call falls through to normal agent dispatch (which we mock to
    return no agents, simulating LLM unavailability — the result should
    still be `ok=False` from the no-drafts path, not the data_anchor path)."""
    async def no_agents(*_a, **_k):
        return []
    monkeypatch.setattr(oc, "get_relevant_agents", no_agents)
    out = await oc.convene_council(
        "real ask",
        context={"source": "latency_guardian",
                 "evidence": {"endpoint": "x", "latency_ms": 800}},
        db=None,
    )
    # Should NOT carry the data_anchor refusal flag
    assert out.get("data_anchor") is None
    # Falls into the no-drafts path (ok=False), not the refusal path
    assert out["ok"] is False


@pytest.mark.asyncio
async def test_convene_council_does_not_apply_anchor_to_customer_callers():
    """A customer-facing caller (no `source` field, or source not in the
    SYSTEM list) is unaffected — for back-compat with existing chat flow."""
    async def no_agents(*_a, **_k):
        return []
    import unittest.mock as _m
    with _m.patch.object(oc, "get_relevant_agents", side_effect=no_agents):
        out = await oc.convene_council(
            "What's the weather?",
            context={"source": "customer_chat"},  # NOT a system source
            db=None,
        )
    # Customer call falls to no-drafts path, NOT the refusal path
    assert out.get("data_anchor") is None
