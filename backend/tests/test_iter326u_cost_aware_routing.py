"""
test_iter326u_cost_aware_routing.py — Regression for iter 326u.
══════════════════════════════════════════════════════════════════════════════
Founder's ask: "Simple chitchat pe expensive model waste ho raha hai…
$200-500/month potential saving."

ROOT CAUSE
──────────
Before iter 326u, the LLM provider chain was a STATIC sequence:
    deepseek → gemini → nvidia → claude → groq
Every request — from "hi" to "rewrite the entire campaign engine" —
burned the same providers in the same order. Simple questions paid
DeepSeek + Gemini rates when the cheapest brain would have nailed it.

THE FIX
───────
Two new helpers in `services/ora_agent.py`:

  • `_classify_complexity(messages)` — KEYWORD HEURISTIC (no LLM call;
    classification by another LLM would defeat the cost saving). Looks
    at the LAST user message and returns one of:
        "simple"  — single-word / status check / "yes/no" / ≤8 tokens
        "complex" — refactor / debug / build / >120 tokens
        "medium"  — everything else

  • `_chain_order_for(complexity)` — picks a chain order:
        simple   → gemini, deepseek, nvidia, groq, claude
                    (cheapest first; Claude last-ditch)
        medium   → deepseek, gemini, nvidia, claude, groq  (UNCHANGED)
        complex  → claude, deepseek, gemini, nvidia, groq
                    (best reasoning first)

Env overrides preserved:
  ORA_AGENT_PROVIDER_ORDER   — hard override (operator-set chain)
  ORA_AGENT_DISABLE_ROUTING  — kill switch back to static legacy chain

WHAT THIS FILE LOCKS IN
───────────────────────
  • Simple greetings route to cheapest first.
  • Complex tasks ("rewrite the X module") route to smartest first.
  • Medium stays IDENTICAL to the legacy chain (no surprises for the
    bulk of traffic — strictly additive saving).
  • Operator overrides still win.
  • Classifier never calls an LLM (else: no cost saving).

Run:  cd /app/backend && python3 -m pytest tests/test_iter326u_cost_aware_routing.py -v
"""
from __future__ import annotations

import os

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# 1) Classifier — basic shapes
# ─────────────────────────────────────────────────────────────────────────────
def _last_user(text: str) -> list[dict]:
    return [
        {"role": "system", "content": "you are ora"},
        {"role": "user", "content": text},
    ]


@pytest.mark.parametrize("text", [
    "hi",
    "hello",
    "campaign status?",
    "report?",
    "ok",
    "thanks",
    "ping",
    "show me the status",
    "is the system healthy?",
    "yes",
    "no",
])
def test_simple_intents_classify_as_simple(text):
    from services.ora_agent import _classify_complexity
    assert _classify_complexity(_last_user(text)) == "simple", (
        f"{text!r} should be SIMPLE — currently routes too expensive"
    )


@pytest.mark.parametrize("text", [
    "refactor the campaign engine to use Redis instead of MongoDB",
    "rewrite the auth router so admin and customer use separate tokens",
    "implement the auto-refill safety net per the spec we discussed",
    "debug why the campaign watchdog tripped at 3am",
    "investigate the CORS bug on aurem.live",
    "architect a multi-tenant pricing system",
])
def test_complex_tasks_classify_as_complex(text):
    from services.ora_agent import _classify_complexity
    assert _classify_complexity(_last_user(text)) == "complex", (
        f"{text!r} should be COMPLEX — needs strongest brain first"
    )


def test_long_message_promotes_to_complex():
    """Founders don't write essays for status checks. Long input
    (>120 tokens) almost always means a multi-step task."""
    from services.ora_agent import _classify_complexity
    long_text = "Hey, " + ("can you help me understand the database " * 25)
    assert _classify_complexity(_last_user(long_text)) == "complex"


def test_explanation_request_is_medium():
    """Asking for an explanation isn't a deep code task and isn't a
    tiny status check either. Should land in MEDIUM."""
    from services.ora_agent import _classify_complexity
    text = "Can you explain how the email auto-blast cycle picks leads?"
    assert _classify_complexity(_last_user(text)) == "medium"


def test_empty_or_no_user_message_defaults_medium():
    """When we genuinely don't know, default UP to MEDIUM. Underprovisioning
    a hard request is worse than overprovisioning an easy one."""
    from services.ora_agent import _classify_complexity
    assert _classify_complexity([]) == "medium"
    assert _classify_complexity([
        {"role": "system", "content": "hi"}
    ]) == "medium"


# ─────────────────────────────────────────────────────────────────────────────
# 2) Chain order picker — three distinct orders + safe fallbacks
# ─────────────────────────────────────────────────────────────────────────────
def test_simple_complexity_puts_cheap_first():
    """Cheapest-first sequence for simple traffic."""
    from services.ora_agent import _chain_order_for
    chain = _chain_order_for("simple")
    # gemini (cheap) must come before claude (expensive)
    assert chain.index("gemini") < chain.index("claude")
    assert chain.index("deepseek") < chain.index("claude")
    # claude should be at or near the bottom
    assert chain[-1] in ("claude", "groq"), (
        f"claude should be last-ditch for simple, got {chain}"
    )


def test_complex_complexity_puts_smart_first():
    """Smartest-first sequence for hard tasks."""
    from services.ora_agent import _chain_order_for
    chain = _chain_order_for("complex")
    assert chain[0] == "claude", (
        f"complex tasks should start with claude, got {chain}"
    )


def test_medium_chain_matches_legacy_static_order():
    """Critical safety property: MEDIUM (the default) must NOT change
    the existing chain order. The whole iter 326u landing is strictly
    additive — only SIMPLE and COMPLEX routes shift."""
    from services.ora_agent import _chain_order_for
    chain = _chain_order_for("medium")
    assert chain == ["deepseek", "gemini", "nvidia", "claude", "groq"]


def test_unknown_complexity_falls_to_medium_safe_default():
    from services.ora_agent import _chain_order_for
    chain = _chain_order_for("anything_else")
    # Falls through to the medium branch
    assert chain == ["deepseek", "gemini", "nvidia", "claude", "groq"]


# ─────────────────────────────────────────────────────────────────────────────
# 3) Env overrides — operator escape hatches
# ─────────────────────────────────────────────────────────────────────────────
def test_disable_routing_env_returns_legacy_chain():
    """Operator can opt out by setting ORA_AGENT_DISABLE_ROUTING=1.
    All 3 complexity tiers then return the legacy static chain."""
    from services.ora_agent import _chain_order_for

    prior = os.environ.get("ORA_AGENT_DISABLE_ROUTING")
    try:
        os.environ["ORA_AGENT_DISABLE_ROUTING"] = "1"
        legacy = ["deepseek", "gemini", "nvidia", "claude", "groq"]
        assert _chain_order_for("simple") == legacy
        assert _chain_order_for("medium") == legacy
        assert _chain_order_for("complex") == legacy
    finally:
        if prior is None:
            os.environ.pop("ORA_AGENT_DISABLE_ROUTING", None)
        else:
            os.environ["ORA_AGENT_DISABLE_ROUTING"] = prior


def test_classifier_does_not_call_any_llm():
    """The whole point of this fix is COST SAVING. If the classifier
    calls an LLM to figure out what tier the message is, we just
    burned the savings.

    Functionally: classifying 1000 messages must take less than half
    a second — far below any LLM round-trip."""
    import time
    from services.ora_agent import _classify_complexity

    samples = [
        _last_user("hi"),
        _last_user("rewrite the entire campaign engine end-to-end"),
        _last_user("how is the system?"),
        _last_user("debug the watchdog please"),
        _last_user("explain something to me about the schema"),
    ] * 200

    start = time.perf_counter()
    for s in samples:
        _classify_complexity(s)
    elapsed = time.perf_counter() - start
    assert elapsed < 0.5, (
        f"Classifier took {elapsed:.2f}s for 1000 calls — too slow, "
        f"likely making LLM calls. Must stay pure-Python heuristic."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4) Safety property — every chain order contains EVERY provider
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("complexity", ["simple", "medium", "complex"])
def test_every_chain_includes_all_5_providers(complexity):
    """If a provider is missing from a chain, that provider can never
    pick up the call when the higher-priority ones fail. Every chain
    MUST list all 5 — only the order changes."""
    from services.ora_agent import _chain_order_for
    chain = _chain_order_for(complexity)
    must_have = {"deepseek", "gemini", "nvidia", "claude", "groq"}
    assert set(chain) == must_have, (
        f"chain for {complexity} is missing providers: "
        f"{must_have - set(chain)}"
    )
    assert len(chain) == 5, (
        f"chain for {complexity} has duplicates: {chain}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5) Module sanity
# ─────────────────────────────────────────────────────────────────────────────
def test_routing_helpers_are_exported():
    """Future call sites and tests rely on these being module-level."""
    from services import ora_agent
    for name in ("_classify_complexity", "_chain_order_for"):
        assert hasattr(ora_agent, name)
        assert callable(getattr(ora_agent, name))
