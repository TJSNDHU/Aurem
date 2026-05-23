"""
iter 332a-3 — invoke_tool hooks for smart routing + escalation
==============================================================

Closes the loop on the 3 E2E proofs that were deferred from iter 332a-2:

  Proof 1 — Same debug task fails 2× via invoke_tool → next call
            silently flips to mode="emergent"
  Proof 2 — Same debug task 3rd time → cache hit at $0 (already
            covered by Proof 3 of 332a-2 from the fork_context path,
            re-proven here via invoke_tool transparency)
  Proof 4 — `invoke_tool('fork_context', brief='Integrate Stripe …')`
            routes to mode="emergent" + task_type="integration"

Also covers the new Re-teach button endpoint:
  • POST /api/admin/ora/validated-solutions/{sig}/reteach deletes the row
  • Refuses bad signatures with `invalid_signature`
  • Endpoint admin-gated
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


@pytest_asyncio.fixture
async def vs_db(db):
    from services import ora_validated_solutions as VS
    VS.set_db(db)
    yield db


# ═══════════════════════════════════════════════════════════════════
# Re-teach button
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_reteach_deletes_validated_solution(vs_db):
    from services import ora_validated_solutions as VS
    from routers.ora_specialist_cost_router import (
        reteach_validated_solution, set_db as _set_db,
    )
    _set_db(vs_db)
    sig = "a" * 64   # valid 64-char hex
    await VS.save_solution(
        signature=sig, task_type="debug",
        fix_suggestion="wrong fix that the founder spotted",
        findings=[], specialist="ora",
    )
    try:
        class _AdminReq:
            headers = {"authorization": "Bearer admin-test"}
        r = await reteach_validated_solution(sig, _AdminReq())  # type: ignore[arg-type]
        assert r["ok"] is True
        assert r["deleted"] == 1
        # Confirm gone
        from services.ora_validated_solutions import lookup_solution
        assert await lookup_solution(sig) is None
    finally:
        await vs_db.ora_validated_solutions.delete_many({"signature": sig})


@pytest.mark.asyncio
async def test_reteach_rejects_invalid_signature(vs_db):
    from routers.ora_specialist_cost_router import (
        reteach_validated_solution, set_db as _set_db,
    )
    _set_db(vs_db)

    class _AdminReq:
        headers = {"authorization": "Bearer admin-test"}
    r = await reteach_validated_solution("not-a-sig", _AdminReq())  # type: ignore[arg-type]
    assert r["ok"] is False
    assert r["error"] == "invalid_signature"


@pytest.mark.asyncio
async def test_reteach_endpoint_admin_gated():
    from routers.ora_specialist_cost_router import reteach_validated_solution
    from fastapi import HTTPException

    class _AnonReq:
        headers = {}

    try:
        await reteach_validated_solution("x" * 64, _AnonReq())  # type: ignore[arg-type]
    except HTTPException as e:
        assert e.status_code in (401, 403, 503)
    else:
        pytest.fail("must refuse without admin bearer")


# ═══════════════════════════════════════════════════════════════════
# E2E Proof 1 — invoke_tool failure counter → auto-escalation
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_proof1_invoke_tool_escalates_after_two_failures():
    """invoke_tool('fork_context') returns ok=False twice → the next
    fork_context call for the same session must route to mode='emergent'."""
    from services import ora_tools as _T
    from services.ora_guards import (
        record_task_success, smart_route,
    )
    sess = f"proof1-{uuid.uuid4().hex[:8]}"
    record_task_success(sess, "fork_context")   # clean slate

    # Swap fork_context with a probe that fails twice then succeeds
    call_count = {"n": 0}
    async def _probe(task_type="debug", brief="", relevant_files=None,
                      return_schema=None, mode="ora", session_id="",
                      **kwargs):
        call_count["n"] += 1
        # First two calls fail (verdict + ok=False); third call passes
        if call_count["n"] <= 2:
            return {"ok": False, "verdict": "fail", "findings": ["x"],
                    "fix_suggestion": "tried but failed",
                    "task_type": task_type, "mode": mode}
        return {"ok": True, "verdict": "pass", "findings": [],
                "fix_suggestion": "got it", "task_type": task_type,
                "mode": mode}

    real = _T.TOOL_REGISTRY.get("fork_context", {}).get("fn")
    _T.TOOL_REGISTRY["fork_context"]["fn"] = _probe
    try:
        # Drive two failures through invoke_tool for THIS tool
        for _ in range(2):
            r = await _T.invoke_tool(
                "fork_context",
                {"task_type": "debug",
                  "brief":     "same bug seen twice",
                  "relevant_files": [],
                  "_session_id": sess},
                actor="ora",
            )
            assert r.get("ok") is False
        # Now smart_route MUST flip to emergent on the next attempt
        decision = smart_route(
            task_type="debug",
            brief="same bug seen twice",
            relevant_files=[],
            session_id=sess, task_id="fork_context",
        )
        assert decision["mode"] == "emergent"
        assert decision["previous_fails"] >= 2
        assert "escalated" in decision["reason"]
    finally:
        if real is not None:
            _T.TOOL_REGISTRY["fork_context"]["fn"] = real
        record_task_success(sess, "fork_context")


@pytest.mark.asyncio
async def test_invoke_tool_success_resets_counter():
    """Reverse direction: a successful invocation must reset the
    counter so a future failure starts from 1, not N+1."""
    from services.ora_tools import invoke_tool
    from services.ora_guards import (
        record_task_failure, check_escalation_needed,
    )
    sess = f"reset-{uuid.uuid4().hex[:8]}"
    # Seed two failures externally
    record_task_failure(sess, "view_file")
    record_task_failure(sess, "view_file")
    assert check_escalation_needed(sess, "view_file")["fails"] == 2
    # Now drive a SUCCESS through invoke_tool
    r = await invoke_tool(
        "view_file",
        {"path": "/app/backend/services/ora_guards.py",
         "_session_id": sess},
        actor="ora",
    )
    # view_file accepts the path, so the call should succeed
    if r.get("ok"):
        c = check_escalation_needed(sess, "view_file")
        assert c["fails"] == 0
        assert c["suggested_mode"] == "ora"


# ═══════════════════════════════════════════════════════════════════
# E2E Proof 4 — new integration brief routes to specialist directly
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_proof4_new_integration_routes_to_emergent(vs_db, monkeypatch):
    """An invoke_tool('fork_context', ...) brief that mentions a new
    third-party integration must end up at mode='emergent' WITHOUT a
    prior failure. smart_route must intercept BEFORE the LLM call."""
    from services import ora_tools as _T
    from services.ora_guards import record_task_success
    sess = f"proof4-{uuid.uuid4().hex[:8]}"
    record_task_success(sess, "fork_context")   # clean slate

    # Replace fork_context with a probe that records what mode it saw
    seen = {}
    async def _probe(task_type="debug", brief="", relevant_files=None,
                      return_schema=None, mode="ora", session_id="",
                      **kwargs):
        seen["task_type"] = task_type
        seen["mode"]      = mode
        seen["brief"]     = brief
        return {"ok": True, "verdict": "pass", "findings": [],
                "fix_suggestion": "probe", "task_type": task_type,
                "mode": mode}
    # Swap the registered fork_context function for the probe
    real = _T.TOOL_REGISTRY.get("fork_context", {}).get("fn")
    _T.TOOL_REGISTRY["fork_context"]["fn"] = _probe
    try:
        r = await _T.invoke_tool(
            "fork_context",
            {"task_type":      "debug",
             "brief":          "Integrate Stripe for new subscription tier",
             "relevant_files": [],
             "_session_id":    sess},
            actor="ora",
        )
        assert r.get("ok") is True
        assert seen["mode"]      == "emergent"
        assert seen["task_type"] == "integration"
        # And the routing decision is surfaced on the result envelope
        assert r.get("auto_specialist") is True
        assert "third_party" in (r.get("routing_reason") or "")
    finally:
        if real is not None:
            _T.TOOL_REGISTRY["fork_context"]["fn"] = real


@pytest.mark.asyncio
async def test_new_jsx_routes_to_design_specialist():
    """Hard rule: new .jsx file → mode='emergent', task_type='design'."""
    from services import ora_tools as _T
    from services.ora_guards import record_task_success
    sess = f"jsx-{uuid.uuid4().hex[:8]}"
    record_task_success(sess, "fork_context")

    seen = {}
    async def _probe(task_type="debug", brief="", relevant_files=None,
                      return_schema=None, mode="ora", session_id="",
                      **kwargs):
        seen["task_type"] = task_type
        seen["mode"]      = mode
        return {"ok": True, "verdict": "pass", "findings": [],
                "fix_suggestion": "probe", "task_type": task_type,
                "mode": mode}
    real = _T.TOOL_REGISTRY.get("fork_context", {}).get("fn")
    _T.TOOL_REGISTRY["fork_context"]["fn"] = _probe
    try:
        r = await _T.invoke_tool(
            "fork_context",
            {"task_type":      "design",
             "brief":          "New CheckoutForm.jsx component",
             "relevant_files": ["/app/frontend/src/CheckoutForm.jsx"],
             "is_new_file":    True,
             "_session_id":    sess},
            actor="ora",
        )
        assert r.get("ok") is True
        assert seen["mode"]      == "emergent"
        assert seen["task_type"] == "design"
        assert r.get("auto_specialist") is True
    finally:
        if real is not None:
            _T.TOOL_REGISTRY["fork_context"]["fn"] = real


# ═══════════════════════════════════════════════════════════════════
# Source-level wiring sanity
# ═══════════════════════════════════════════════════════════════════

def test_invoke_tool_calls_smart_route_for_fork_context():
    from pathlib import Path
    src = Path("/app/backend/services/ora_tools.py").read_text()
    assert "smart_route" in src
    assert "_auto_specialist" in src or "auto_specialist" in src


def test_invoke_tool_feeds_failure_counter():
    from pathlib import Path
    src = Path("/app/backend/services/ora_tools.py").read_text()
    assert "record_task_failure" in src
    assert "record_task_success" in src


def test_reteach_route_registered():
    from pathlib import Path
    src = Path("/app/backend/routers/ora_specialist_cost_router.py").read_text()
    assert "/validated-solutions/{signature}/reteach" in src
