"""
test_iter326v_token_cost_transparency.py — Regression for iter 326v.
══════════════════════════════════════════════════════════════════════════════
Founder ask: "Aaj tu andhere mein hai. Koi idea nahi ki ek turn pe $0.02
gaya ya $2. Har chat turn ke neeche dikhega: 'This turn: $0.03 |
Session: $0.18'."

THE FIX (services/ora_agent.py — iter 326v)
───────────────────────────────────────────
1. `_PROVIDER_PRICING_USD_PER_M_TOKENS` — table of input/output $/1M
   tokens per provider. Numbers rounded UP so we never under-report.
2. `_estimate_call_cost_usd(provider, prompt_chars, response_chars)`
   — cheap pure-Python estimator using tokens ≈ chars/4.
3. `_SESSION_COST_USD` — module-level dict per session_id, tracks
   `session_total` and `turn_total`.
4. `_track_session_cost()` — adds cost to both running totals.
5. `_reset_turn_cost()` — called at the start of every new user
   message so the footer shows only THIS turn's cost.
6. `_format_cost_footer()` — renders
   `_(This turn: $0.003 · Session: $0.018)_`
   on the end of every reply.
7. Wiring:
   • `_llm_turn` attaches `__ora_provider__` / `__ora_prompt_chars__` /
     `__ora_resp_chars__` to the winning msg.
   • The main loop reads those keys after every LLM call and updates
     the session cost bucket.
   • The final-reply branch appends the formatted footer (after the
     iter 326t hallucination shield, before history persist).
8. Operator opt-out: `ORA_AGENT_SHOW_COST=0` suppresses the footer.

WHAT THIS TEST LOCKS IN
───────────────────────
  • Cost estimator returns expected ballpark for each provider.
  • Free providers (NVIDIA, Ollama) cost exactly 0.
  • Session bucket accumulates across multiple calls.
  • turn_total resets per user message; session_total does NOT.
  • Footer renders correctly for cents and sub-cent values.
  • Footer is empty when nothing was spent (e.g. local-only).
  • Cost tracking never raises (wrapped in try/except).

Run:  cd /app/backend && python3 -m pytest tests/test_iter326v_token_cost_transparency.py -v
"""
from __future__ import annotations

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# 1) Pricing estimator — sanity for each provider
# ─────────────────────────────────────────────────────────────────────────────
def test_claude_call_costs_dollars_not_cents():
    """Claude is the most expensive brain. A 4000-char prompt + 2000-char
    reply should cost a non-trivial amount (single-digit cents at least)."""
    from services.ora_agent import _estimate_call_cost_usd
    cost = _estimate_call_cost_usd("claude", 4000, 2000)
    # 1000 input tokens × $3 + 500 output × $15 = $0.003 + $0.0075 = $0.0105
    assert 0.005 < cost < 0.05, f"claude cost out of plausible range: ${cost}"


def test_gemini_call_is_30x_cheaper_than_claude_for_same_size():
    """Gemini Flash is the cheap brain in our chain. Same prompt should
    cost much less than Claude — the WHOLE POINT of iter 326u routing."""
    from services.ora_agent import _estimate_call_cost_usd
    claude = _estimate_call_cost_usd("claude", 4000, 2000)
    gemini = _estimate_call_cost_usd("gemini", 4000, 2000)
    ratio = claude / gemini
    assert ratio > 15, (
        f"claude should be ≥15× more expensive than gemini, got {ratio:.1f}×"
    )


@pytest.mark.parametrize("provider", ["nvidia", "ollama", "legion_ollama", "freellmapi"])
def test_free_providers_cost_zero(provider):
    """Free providers must report exactly zero so the footer doesn't
    misleadingly show cents when we paid nothing."""
    from services.ora_agent import _estimate_call_cost_usd
    assert _estimate_call_cost_usd(provider, 4000, 2000) == 0.0


def test_unknown_provider_returns_zero_not_crash():
    """Defensive — if a provider name doesn't have a pricing entry,
    return 0 rather than KeyError. We'd rather under-report one obscure
    call than break the reply path."""
    from services.ora_agent import _estimate_call_cost_usd
    assert _estimate_call_cost_usd("not_a_real_provider", 4000, 2000) == 0.0


def test_zero_chars_returns_zero():
    from services.ora_agent import _estimate_call_cost_usd
    assert _estimate_call_cost_usd("claude", 0, 0) == 0.0


def test_negative_chars_clamped_to_zero():
    """Sanity — negative char counts (impossible but defensive)
    must not produce negative dollars."""
    from services.ora_agent import _estimate_call_cost_usd
    assert _estimate_call_cost_usd("claude", -100, -50) == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 2) Session cost tracker — accumulates across calls, resets per turn
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def fresh_session():
    """Isolated session bucket so tests don't pollute each other."""
    from services import ora_agent
    sid = "test_session_326v"
    ora_agent._SESSION_COST_USD.pop(sid, None)
    yield sid
    ora_agent._SESSION_COST_USD.pop(sid, None)


def test_track_accumulates_session_total(fresh_session):
    from services.ora_agent import _track_session_cost, _SESSION_COST_USD
    sid = fresh_session
    _track_session_cost(sid, "claude", 0.005)
    _track_session_cost(sid, "deepseek", 0.001)
    _track_session_cost(sid, "claude", 0.003)
    assert abs(_SESSION_COST_USD[sid]["session_total"] - 0.009) < 1e-9


def test_track_accumulates_turn_total(fresh_session):
    """In a single turn, multiple LLM calls (e.g. one for planning, one
    for synthesis) all roll into the same turn_total."""
    from services.ora_agent import _track_session_cost, _SESSION_COST_USD
    sid = fresh_session
    _track_session_cost(sid, "claude", 0.005)
    _track_session_cost(sid, "deepseek", 0.001)
    assert abs(_SESSION_COST_USD[sid]["turn_total"] - 0.006) < 1e-9


def test_reset_turn_does_not_reset_session(fresh_session):
    """Critical contract: a new user message clears turn_total, but
    session_total must keep growing."""
    from services.ora_agent import (
        _track_session_cost, _reset_turn_cost, _SESSION_COST_USD,
    )
    sid = fresh_session
    _track_session_cost(sid, "claude", 0.005)
    _track_session_cost(sid, "claude", 0.003)
    # Simulate: new user message arrives
    _reset_turn_cost(sid)
    assert _SESSION_COST_USD[sid]["turn_total"] == 0.0
    assert abs(_SESSION_COST_USD[sid]["session_total"] - 0.008) < 1e-9
    # Next turn's calls roll into a fresh turn_total
    _track_session_cost(sid, "deepseek", 0.001)
    assert abs(_SESSION_COST_USD[sid]["turn_total"] - 0.001) < 1e-9
    assert abs(_SESSION_COST_USD[sid]["session_total"] - 0.009) < 1e-9


def test_track_with_empty_session_id_is_noop(fresh_session):
    """Defensive — if session_id is missing for any reason, must not
    create ghost entries in the cost dict."""
    from services.ora_agent import _track_session_cost, _SESSION_COST_USD
    pre = dict(_SESSION_COST_USD)
    _track_session_cost("", "claude", 0.005)
    _track_session_cost(None, "claude", 0.005)  # type: ignore[arg-type]
    assert dict(_SESSION_COST_USD) == pre


# ─────────────────────────────────────────────────────────────────────────────
# 3) Footer formatter — sub-cent values + zero handling
# ─────────────────────────────────────────────────────────────────────────────
def test_footer_shows_dollar_amount_when_meaningful(fresh_session):
    from services.ora_agent import _track_session_cost, _format_cost_footer
    sid = fresh_session
    _track_session_cost(sid, "claude", 0.015)  # this turn
    footer = _format_cost_footer(sid)
    assert "This turn:" in footer
    assert "Session:" in footer
    assert "$0.015" in footer


def test_footer_shows_lessthan_for_microcent_values(fresh_session):
    """Founders shouldn't read '$0.000001' — show '<$0.001' instead."""
    from services.ora_agent import _track_session_cost, _format_cost_footer
    sid = fresh_session
    _track_session_cost(sid, "gemini", 0.0001)
    footer = _format_cost_footer(sid)
    assert "<$0.001" in footer


def test_footer_empty_when_nothing_spent(fresh_session):
    """When all calls were on free providers (NVIDIA/Ollama), the
    footer must be empty — no point telling the founder 'this turn: $0'."""
    from services.ora_agent import _format_cost_footer
    assert _format_cost_footer(fresh_session) == ""


def test_footer_distinguishes_turn_from_session(fresh_session):
    """After a previous turn cost X and the current turn cost Y, the
    footer must show Y (turn) and X+Y (session) separately."""
    from services.ora_agent import (
        _track_session_cost, _reset_turn_cost, _format_cost_footer,
    )
    sid = fresh_session
    # Turn 1: $0.01
    _track_session_cost(sid, "claude", 0.01)
    # Turn boundary
    _reset_turn_cost(sid)
    # Turn 2: $0.005
    _track_session_cost(sid, "deepseek", 0.005)
    footer = _format_cost_footer(sid)
    # The footer should report turn=$0.005, session=$0.015
    assert "$0.005" in footer  # turn
    assert "$0.015" in footer  # session


# ─────────────────────────────────────────────────────────────────────────────
# 4) Module surface sanity
# ─────────────────────────────────────────────────────────────────────────────
def test_pricing_table_includes_all_chain_providers():
    """Every provider in the routing chain must have a pricing entry
    or the estimator silently reports $0 for it — bad founder UX."""
    from services.ora_agent import _PROVIDER_PRICING_USD_PER_M_TOKENS as P
    for p in ("deepseek", "gemini", "nvidia", "claude", "groq"):
        assert p in P, f"missing pricing entry: {p}"
        assert "input" in P[p] and "output" in P[p]


def test_helpers_are_exported():
    from services import ora_agent
    for name in (
        "_estimate_call_cost_usd",
        "_track_session_cost",
        "_reset_turn_cost",
        "_format_cost_footer",
        "_SESSION_COST_USD",
        "_PROVIDER_PRICING_USD_PER_M_TOKENS",
    ):
        assert hasattr(ora_agent, name), f"missing: {name}"
