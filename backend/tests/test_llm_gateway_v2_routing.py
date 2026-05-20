"""Regression tests for services.llm_gateway_v2 routing.

Tests:
- DeepSeek/Kimi present in non-sensitive task chains
- Sensitive tasks NEVER include China-origin providers
- _chain_for() always returns a non-empty chain
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services import llm_gateway_v2 as gw


SENSITIVE = list(gw.SENSITIVE_TASKS)
CHEAP_KEYWORDS = ("deepseek", "kimi", "moonshot", "qwen", "glm", "zai-org", "minimax")


def test_sensitive_tasks_never_route_to_china_models():
    for task in SENSITIVE:
        chain = gw._chain_for(task)
        for provider, model in chain:
            ml = model.lower()
            for kw in CHEAP_KEYWORDS:
                assert kw not in ml, (
                    f"Sensitive task {task!r} leaked Chinese-origin model: "
                    f"{provider}/{model}"
                )


def test_non_sensitive_paid_tasks_have_cheap_middle_tier():
    """Code-fix, ora_brain etc. should try a cheap middle-tier (DeepSeek/Kimi)
    before falling through to paid Claude."""
    for task in ("code_fix", "ora_brain", "repair_diagnose", "learning_digest"):
        chain = gw._chain_for(task)
        has_cheap = any(
            any(kw in m.lower() for kw in CHEAP_KEYWORDS)
            for _, m in chain
        )
        assert has_cheap, (
            f"Task {task!r} chain missing cheap middle tier — only contains: {chain}"
        )


def test_default_chain_when_task_missing():
    chain = gw._chain_for("totally_unknown_task_xyz")
    assert chain == [gw.DEFAULT]


def test_redact_keeps_safe_providers():
    raw = [
        ("groq", "llama-3.3-70b-versatile"),
        ("openrouter", "deepseek/deepseek-chat-v3.1"),
        ("anthropic", "claude-sonnet-4-5-20250929"),
    ]
    safe = gw._redact_sensitive_providers("auth_token_decision", raw)
    assert ("openrouter", "deepseek/deepseek-chat-v3.1") not in safe
    # Groq + Claude both safe
    assert ("groq", "llama-3.3-70b-versatile") in safe
    assert ("anthropic", "claude-sonnet-4-5-20250929") in safe


def test_redact_leaves_non_sensitive_chain_unchanged():
    raw = [
        ("openrouter", "deepseek/deepseek-chat-v3.1"),
        ("anthropic", "claude-sonnet-4-5-20250929"),
    ]
    same = gw._redact_sensitive_providers("code_fix", raw)
    assert same == raw
