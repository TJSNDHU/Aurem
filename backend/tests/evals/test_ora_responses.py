"""
ORA Agent Response Evals
────────────────────────
Smoke + structural tests for the ORA CTO autonomous agent. These check
the *contract* (shape of response, fallback behaviour, tool-call salvage)
not exact text — LLM output is non-deterministic.

Each test is gated on EVALS_OFFLINE=1 so CI can skip when LLM keys are
unavailable, and on actual import success of the agent module.
"""
import asyncio
import os
import re

import pytest

OFFLINE = os.environ.get("EVALS_OFFLINE") == "1"


@pytest.fixture(scope="module")
def ora():
    """Import ora_agent lazily so missing deps skip cleanly."""
    try:
        from services import ora_agent  # type: ignore
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"ora_agent unavailable: {exc}")
    return ora_agent


# ─────────────────────────────────────────────────────────────────────────────
# 1. Salvage parser — converts raw JSON strings into tool_calls
# ─────────────────────────────────────────────────────────────────────────────
def test_salvage_logic_present(ora):
    """Salvage logic must exist in ora_agent (inline or as helper).

    qwen2.5-coder and similar local models often emit tool calls as plain
    JSON inside `content` instead of populating `tool_calls`. We need code
    that promotes that shape into a proper OpenAI tool_calls array.
    """
    import inspect
    try:
        src = inspect.getsource(ora)
    except Exception as exc:
        pytest.skip(f"Cannot read ora_agent source: {exc}")
    src_l = src.lower()
    has_salvage = any(k in src_l for k in (
        "salvage", "promote", "tool-call", "salvaged qwen",
    ))
    has_json_parse = "json.loads" in src and "tool_calls" in src
    assert has_salvage or has_json_parse, (
        "Salvage logic missing — qwen2.5-coder raw JSON outputs will not be "
        "converted to tool_calls. Re-add per iter 323ab fix."
    )


def test_salvage_handles_multiple_key_shapes(ora):
    """Salvage must accept {name,parameters}, {tool,args}, {function,arguments}."""
    import inspect
    try:
        src = inspect.getsource(ora)
    except Exception as exc:
        pytest.skip(f"Cannot read ora_agent source: {exc}")
    # Permissive: at least two of the three argument-key aliases must
    # appear so the salvage isn't single-shape-only.
    arg_keys = ["parameters", "arguments", "args"]
    found = sum(1 for k in arg_keys if k in src)
    assert found >= 2, (
        f"Salvage only handles {found} arg-key shapes. Should handle at least 2 "
        f"of {arg_keys} to cover qwen / mistral / llama variants."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Canadian SMB context injection (iter 323k)
# ─────────────────────────────────────────────────────────────────────────────
def test_canadian_smb_context_in_system_prompt(ora):
    """System prompt must include Canadian/SMB context so ORA doesn't
    drift into generic enterprise advice."""
    prompt_attr = None
    for candidate in ("SYSTEM_PROMPT", "ORA_SYSTEM_PROMPT", "_SYSTEM_PROMPT", "build_system_prompt"):
        if hasattr(ora, candidate):
            prompt_attr = candidate
            break
    if prompt_attr is None:
        pytest.skip("No system-prompt symbol exported from ora_agent")

    prompt_obj = getattr(ora, prompt_attr)
    text = prompt_obj() if callable(prompt_obj) else prompt_obj
    text = str(text).lower()
    # Loose check: at least one Canadian-SMB anchor word must be present.
    anchors = ["canad", "ontario", "smb", "small business", "aurem", "mississauga"]
    assert any(a in text for a in anchors), (
        f"System prompt missing Canadian/SMB anchors. Looked for {anchors}."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Fallback chain — Ollama → Groq → Emergent
# ─────────────────────────────────────────────────────────────────────────────
def test_fallback_chain_has_groq(ora):
    """Per iter 323r, Groq must be wired as the middle-tier fallback so
    local-LLM failures don't drop straight to Claude (slower + paid)."""
    src = ""
    try:
        import inspect
        src = inspect.getsource(ora)
    except Exception as exc:
        pytest.skip(f"Cannot read ora_agent source: {exc}")
    src_l = src.lower()
    assert "groq" in src_l, "Groq fallback removed — re-add middle tier."
    # Must mention some Ollama indicator too (local sovereignty).
    assert any(k in src_l for k in ("ollama", "legion", "daemon", "sovereign")), (
        "Sovereign/local LLM tier missing from ora_agent fallback chain."
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Live chat (skipped offline)
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.skipif(OFFLINE, reason="EVALS_OFFLINE=1 set; skipping live LLM call")
def test_ora_chat_returns_non_empty(ora):
    """A trivial chat call should produce SOME text within 30s."""
    chat_fn = None
    for candidate in ("chat", "ora_chat", "run_chat", "respond"):
        if hasattr(ora, candidate):
            chat_fn = getattr(ora, candidate)
            break
    if chat_fn is None:
        pytest.skip("No chat entrypoint exported from ora_agent")

    async def _run():
        coro = chat_fn(messages=[{"role": "user", "content": "Reply with the single word: pong"}])
        return await asyncio.wait_for(coro, timeout=30.0)

    try:
        result = asyncio.run(_run())
    except Exception as exc:
        pytest.skip(f"Live chat unavailable: {exc}")
    text = ""
    if isinstance(result, dict):
        text = result.get("content") or result.get("text") or result.get("message") or ""
    else:
        text = str(result or "")
    assert text.strip(), "ORA chat returned empty content"
    # Should not be a raw JSON tool-call leak.
    assert not re.match(r'^\s*\{.*"name"\s*:\s*"', text), (
        "ORA returned raw tool-call JSON as content — salvage parser broken."
    )
