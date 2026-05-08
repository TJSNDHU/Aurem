"""
iter 282al-20 — Tests for services.ora_council
"""
from __future__ import annotations

import sys
import types
from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import AsyncMock, MagicMock


# ───────────────────────── routing ─────────────────────────
@pytest.mark.asyncio
async def test_relevant_agents_outreach():
    from services.ora_council import get_relevant_agents
    agents = await get_relevant_agents("write email to plumber", {})
    assert "envoy" in agents
    assert "casl" in agents
    assert len(agents) <= 3


@pytest.mark.asyncio
async def test_relevant_agents_code():
    from services.ora_council import get_relevant_agents
    agents = await get_relevant_agents("fix bug in scout_agent.py", {})
    assert "dev" in agents
    assert len(agents) <= 3


@pytest.mark.asyncio
async def test_relevant_agents_pricing():
    from services.ora_council import get_relevant_agents
    agents = await get_relevant_agents("should we charge $97 or $197 monthly", {})
    assert "pricing" in agents


@pytest.mark.asyncio
async def test_relevant_agents_seo_and_reddit():
    from services.ora_council import get_relevant_agents
    agents = await get_relevant_agents("who mentions us without linking — find unlinked mentions", {})
    assert "seo" in agents


@pytest.mark.asyncio
async def test_relevant_agents_default_envoy():
    from services.ora_council import get_relevant_agents
    agents = await get_relevant_agents("aurora alpine zebra wave", {})
    assert agents == ["envoy"]


@pytest.mark.asyncio
async def test_relevant_agents_max_three():
    from services.ora_council import get_relevant_agents
    agents = await get_relevant_agents(
        "write email about pricing for new lead with audit and casl compliance",
        {},
    )
    assert len(agents) <= 3


# ───────────────────────── scoring ─────────────────────────
def test_score_response_casl_safe():
    from services.ora_council import score_response
    score = score_response(
        "envoy",
        "Hi Mike, noticed your site at Mike's Plumbing has no contact form. "
        "Worth a quick look? We've helped 12 trades shops in Brampton this "
        "year add booking via SMS in under a week. Reply STOP to opt out.",
        "write email to mike's plumbing",
        {"business_name": "Mike's Plumbing"},
    )
    assert score >= 30


def test_score_response_hard_sell_penalized():
    from services.ora_council import score_response
    score = score_response(
        "envoy",
        "Buy now! Act now! Limited time! 100% free guaranteed!",
        "x",
        {},
    )
    assert score < 25


def test_score_response_empty_is_zero():
    from services.ora_council import score_response
    assert score_response("envoy", "", "q", {}) == 0


def test_score_response_caps_at_50():
    from services.ora_council import score_response
    long = ("Hi ACME, " + ("noticed your audit. " * 20) +
            "Reply STOP to opt out. — AUREM Inc, Toronto.").strip() + "?"
    s = score_response("envoy", long, "q", {"business_name": "ACME"})
    assert 0 <= s <= 50


# ───────────────────────── complexity gate ─────────────────────────
def test_simple_query_skips_council():
    from services.ora_council import is_complex_query
    assert is_complex_query("hi") is False
    assert is_complex_query("thanks") is False
    assert is_complex_query("ok") is False
    assert is_complex_query("") is False


def test_complex_query_uses_council():
    from services.ora_council import is_complex_query
    assert is_complex_query(
        "write a follow-up email for this plumber"
    ) is True
    assert is_complex_query(
        "should we charge $197 one-time or $297 monthly for repair"
    ) is True


# ───────────────────────── council end-to-end ─────────────────────────
@pytest.mark.asyncio
async def test_council_logs_to_db_on_success(monkeypatch):
    """convene_council persists to db.council_sessions on success."""
    import services.ora_council as oc

    async def _fake_agent_respond(agent, msg, ctx, db):
        return {
            "agent":      agent,
            "response":   f"Hi ACME, noticed your site. Reply STOP to opt out. ({agent})?",
            "confidence": 8,
        }

    async def _fake_reform(winning, msg, agent):
        return f"[ORA] {winning}"

    monkeypatch.setattr(oc, "agent_respond", _fake_agent_respond)
    monkeypatch.setattr(oc, "ora_reformulate", _fake_reform)

    db = MagicMock()
    db.council_sessions.insert_one = AsyncMock(return_value=None)

    out = await oc.convene_council(
        "write email to ACME plumber about audit",
        {"business_name": "ACME"}, db,
    )

    assert out["ok"] is True
    assert out["final_response"].startswith("[ORA]")
    assert out["winner"] in oc.COUNCIL_AGENTS
    assert "envoy" in out["agents_consulted"]
    db.council_sessions.insert_one.assert_awaited_once()
    inserted = db.council_sessions.insert_one.await_args.args[0]
    assert "winner" in inserted
    assert "agents_consulted" in inserted
    assert "ts" in inserted


@pytest.mark.asyncio
async def test_council_returns_safely_when_all_agents_fail(monkeypatch):
    """When every agent returns empty, council reports ok=False so the
    caller can fall back to skill_router."""
    import services.ora_council as oc

    async def _fake_agent_respond(agent, msg, ctx, db):
        return {"agent": agent, "response": "", "confidence": 0}

    monkeypatch.setattr(oc, "agent_respond", _fake_agent_respond)

    out = await oc.convene_council("write email to ACME", {}, MagicMock())
    assert out["ok"] is False
    assert out["final_response"] == ""


# ───────────────────────── roster integrity ─────────────────────────
def test_all_council_agents_have_skill_or_builtin():
    from services.ora_council import COUNCIL_AGENTS, _BUILTIN_PROMPTS, _load_skill_prompt
    # No agent should ever return an empty system prompt
    for agent in COUNCIL_AGENTS:
        prompt = _load_skill_prompt(agent)
        assert prompt
        assert agent in _BUILTIN_PROMPTS or len(prompt) > 100


# ───────────────────────── learning cycle ─────────────────────────
@pytest.mark.asyncio
async def test_council_learning_cycle_appends_log(monkeypatch, tmp_path):
    import services.ora_council as oc

    # Patch _SKILLS_DIR to a tmp dir so we don't touch the real log
    monkeypatch.setattr(oc, "_SKILLS_DIR", tmp_path, raising=False)

    db = MagicMock()
    rows = [
        {"winner": "envoy",  "winner_score": 35, "agents_consulted": ["envoy", "casl"]},
        {"winner": "envoy",  "winner_score": 40, "agents_consulted": ["envoy", "casl"]},
        {"winner": "dev",    "winner_score": 30, "agents_consulted": ["dev", "qa"]},
    ]

    class _Cursor:
        def __init__(self, r): self._r = r
        def sort(self, *_, **__): return self
        async def to_list(self, length=None): return self._r

    db.council_sessions.find = MagicMock(return_value=_Cursor(rows))

    out = await oc.council_learning_cycle(db)
    assert out["appended"] is True
    assert (tmp_path / "council_routing_log.md").exists()
    text = (tmp_path / "council_routing_log.md").read_text()
    assert "envoy: 2 wins" in text or "envoy" in text
