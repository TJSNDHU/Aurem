"""
iter 325z — ORA-CTO chat "primary brain unreachable" + UI online/offline
blink dual root-cause fixes.

User's 2026-05-21 16:43 prod screenshot showed:
  • **Bhai ORA chat ka primary brain (DeepSeek V3.1) abhi reach nahi
    ho raha,** but tension nahi:
    Campaign Engine: ON ... zero_sent_streak (streak=143)

Diagnosis (verified live on preview):
  1. DeepSeek IS reachable (curl HTTPS 200, 358 OpenRouter models)
  2. The "unreachable" message comes from ora_agent.py:1336 which fires
     only when `_llm_turn(messages)` returns None — meaning EVERY
     provider in the chain failed.
  3. Why all failed: OpenRouter Novita has a 30-40s cold-start tax on
     the first request per pod. Old `_DEEPSEEK_WAIT_FOR=25s` killed
     the warm-up call → fell to Claude → old `_CLAUDE_WAIT_FOR=15s`
     was also too tight → Anthropic streaming got cut → Ollama CB-open
     → Groq quota-limited → return None → degrade message.

Route-level fixes:
  • `_DEEPSEEK_WAIT_FOR` 25s → 45s (matches Novita cold-start)
  • `_DEEPSEEK_HTTPX_TIMEOUT` 22s → 42s (keeps inner<outer rule)
  • `_CLAUDE_WAIT_FOR` 15s → 30s (fallback gets a real shot)
  • One automatic retry on DeepSeek timeout (cold-start is a 1-burst)
  • Startup `warm_deepseek()` ping so the founder's first query is hot
    (pod boot → <2s ORA replies instead of 35s)

Online/offline blink (parallel fix):
  • `useLuxeDashboardData` + `useLiveApi` now use HYSTERESIS: success
    DECREMENTS failStreak instead of resetting to 0. Old reset-to-0
    behaviour flapped online↔degraded every 30 s when prod hovered
    ~50/50 success rate (sub-pod restarts, edge wobble). New rule
    requires 3 consecutive successes to clear and 3 consecutive
    failures to escalate.

These tests lock both fixes in place.
"""
import os
import sys
import pytest

sys.path.insert(0, "/app/backend")


# ─── DeepSeek timeout + retry ─────────────────────────────────────────

def test_deepseek_wait_for_at_least_45s():
    from services import ora_agent
    assert ora_agent._DEEPSEEK_WAIT_FOR >= 45.0, (
        f"primary provider needs cold-start headroom; got "
        f"{ora_agent._DEEPSEEK_WAIT_FOR}"
    )


def test_deepseek_httpx_timeout_under_wait_for():
    from services import ora_agent
    assert ora_agent._DEEPSEEK_HTTPX_TIMEOUT < ora_agent._DEEPSEEK_WAIT_FOR, (
        "inner httpx timeout must be < outer asyncio.wait_for so cancellation "
        "never races a mid-flight request"
    )


def test_claude_fallback_has_real_chance():
    from services import ora_agent
    assert ora_agent._CLAUDE_WAIT_FOR >= 25.0, (
        f"fallback can't help if its budget is shorter than primary's "
        f"cold-start; got {ora_agent._CLAUDE_WAIT_FOR}"
    )


def test_deepseek_retry_branch_present():
    """The provider chain must retry DeepSeek ONCE on cold-start timeout."""
    src = open("/app/backend/services/ora_agent.py", encoding="utf-8").read()
    assert "deepseek attempt 1 timed out" in src
    assert "for attempt in (1, 2):" in src


def test_warm_deepseek_helper_exists():
    """The warmup helper must be importable and async."""
    import inspect
    from services import ora_agent
    assert hasattr(ora_agent, "warm_deepseek")
    assert inspect.iscoroutinefunction(ora_agent.warm_deepseek)


def test_warm_deepseek_wired_into_server_startup():
    """server.py must schedule warm_deepseek() during the startup event."""
    src = open("/app/backend/server.py", encoding="utf-8").read()
    assert "from services.ora_agent import warm_deepseek" in src
    assert "asyncio.create_task(warm_deepseek())" in src


# ─── Online/offline blink hysteresis ──────────────────────────────────

def test_dashboard_data_uses_hysteresis():
    src = open("/app/frontend/src/platform/luxe/useLuxeDashboardData.js",
               encoding="utf-8").read()
    assert "Math.max(failStreak.current - 1, 0)" in src, (
        "success must DECREMENT failStreak (hysteresis), not reset to 0"
    )
    assert "iter 325u/325z" in src or "iter 325z" in src


def test_useliveapi_uses_hysteresis():
    src = open("/app/frontend/src/hooks/useAuthFetch.js",
               encoding="utf-8").read()
    assert "Math.max(failStreak.current - 1, 0)" in src
    assert "iter 325z" in src
