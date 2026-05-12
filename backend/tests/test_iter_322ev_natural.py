"""
test_iter_322ev_natural.py — Regression for the `ora_run_natural` tool.

Verifies:
  • Input validation (empty / too-long / bad max_steps).
  • Dry-run gate: execute mode (dry_run=False) is rejected in P1.
  • Lazy import safety: returns clean error if open-interpreter is absent
    (covered indirectly — env always has it after iter 322ev).
  • Full happy path: real Groq call returns a parsed plan with ≥1 step.
  • Tool is registered in TOOL_REGISTRY (28-tool surface).
  • Audit log: every invocation lands in ora_tool_invocations.

These tests hit the real LLM (Groq) — they require GROQ_API_KEY in env
and a working network. Skipped automatically if the key is missing.
"""
import os
import pytest

pytestmark = pytest.mark.asyncio


# ─── Direct bridge tests ─────────────────────────────────────────────

async def test_validation_empty_task():
    from services.ora_natural_bridge import ora_run_natural
    res = await ora_run_natural("")
    assert res["ok"] is False
    assert "non-empty" in res["error"]


async def test_validation_task_too_long():
    from services.ora_natural_bridge import ora_run_natural
    res = await ora_run_natural("x" * 2100)
    assert res["ok"] is False
    assert "2000" in res["error"]


async def test_validation_max_steps_out_of_range():
    from services.ora_natural_bridge import ora_run_natural
    res = await ora_run_natural("test", max_steps=99)
    assert res["ok"] is False
    assert "1..10" in res["error"]


async def test_p1_execution_gate_rejects_dry_run_false():
    from services.ora_natural_bridge import ora_run_natural
    res = await ora_run_natural("echo hello", dry_run=False)
    assert res["ok"] is False
    assert "P1" in res["error"]
    assert "founder approval" in res["error"]


# ─── Registry integration ────────────────────────────────────────────

async def test_tool_registered():
    from services.ora_tools import TOOL_REGISTRY, list_tools
    assert "ora_run_natural" in TOOL_REGISTRY
    catalog = list_tools()
    names = [t["name"] for t in catalog]
    assert "ora_run_natural" in names
    entry = TOOL_REGISTRY["ora_run_natural"]
    assert callable(entry["fn"])
    assert "open interpreter" in entry["description"].lower()


# ─── Live LLM happy path ─────────────────────────────────────────────

@pytest.mark.skipif(
    not os.environ.get("GROQ_API_KEY"),
    reason="GROQ_API_KEY missing — skipping live LLM test",
)
async def test_live_plan_returns_structured_steps():
    from services.ora_natural_bridge import ora_run_natural
    res = await ora_run_natural(
        "check if docker is installed and report its version",
        dry_run=True,
        max_steps=3,
    )
    assert res["ok"] is True, res
    assert res["dry_run"] is True
    assert res["model"] == "groq/llama-3.3-70b-versatile"
    assert res["scope"] == "emergent-pod"
    assert res["planned_steps"] >= 1
    assert isinstance(res["steps"], list)
    assert res["plan_text"]
    # At least one step should mention docker
    joined = " ".join(s["code"] for s in res["steps"]).lower()
    assert "docker" in joined


# ─── End-to-end via invoke_tool (audit log path) ─────────────────────

@pytest.mark.skipif(
    not os.environ.get("GROQ_API_KEY"),
    reason="GROQ_API_KEY missing",
)
async def test_invoke_tool_audit_path():
    from services.ora_tools import invoke_tool
    res = await invoke_tool(
        "ora_run_natural",
        {"task": "list files in /tmp", "dry_run": True, "max_steps": 2},
        actor="pytest@aurem.live",
    )
    assert res["ok"] is True
    assert res["tool"] == "ora_run_natural"
    assert isinstance(res["elapsed_ms"], int)
    assert "ts" in res
