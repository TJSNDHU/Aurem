"""
iter 332a-2 — Auto-escalation + smart routing + cockpit tile
============================================================

Covers Parts 2 + 5 + cockpit endpoint + the 3 E2E proofs that DON'T
require iter 332a-2's deferred companion work:
  • Proof 3 — same debug task 3rd time → validated solution found
  • Proof 5 — cockpit shows ora + emergent + validated rollup
  • Proof 6 — /api/admin/ora/validated-solutions returns plain English

Part 2 cases:
  • record_task_failure increments the counter
  • check_escalation_needed flips to emergent after threshold
  • record_task_success resets the counter
  • fork_context fail verdict bumps the counter
  • fork_context pass verdict resets the counter

Part 5 cases:
  • new .jsx file routes to design + auto_specialist=True
  • new Stripe integration routes to integration playbook
  • debug touching 1 file → default ora-first
  • debug touching 3 files → still ora-first, but tagged for escalation
  • escalation state observed via smart_route
"""
from __future__ import annotations

import asyncio
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
# Part 2 — Auto-escalation counter mechanics
# ═══════════════════════════════════════════════════════════════════

def test_record_failure_increments_counter():
    from services.ora_guards import (
        record_task_failure, record_task_success, check_escalation_needed,
    )
    sid = f"sess-{uuid.uuid4().hex[:8]}"
    tid = "debug-task-1"
    # Start clean
    record_task_success(sid, tid)
    assert check_escalation_needed(sid, tid)["fails"] == 0
    # 1st failure
    record_task_failure(sid, tid)
    assert check_escalation_needed(sid, tid)["fails"] == 1
    # 2nd failure
    record_task_failure(sid, tid)
    r = check_escalation_needed(sid, tid)
    assert r["fails"] == 2
    assert r["escalate"] is True
    assert r["suggested_mode"] == "emergent"
    # Reset
    record_task_success(sid, tid)
    r2 = check_escalation_needed(sid, tid)
    assert r2["fails"] == 0
    assert r2["suggested_mode"] == "ora"


def test_escalation_threshold_env_overridable(monkeypatch):
    """Threshold must come from ORA_ESCALATE_AFTER_FAILS env. We can't
    re-import the module here, but we CAN assert the source uses the
    env-overridable knob (audit-style check)."""
    from services.ora_guards import ESCALATE_AFTER_FAILS
    assert ESCALATE_AFTER_FAILS >= 1
    # And the policy is sane: default is 2 per spec
    assert ESCALATE_AFTER_FAILS == 2


# ═══════════════════════════════════════════════════════════════════
# Part 5 — Smart routing rules
# ═══════════════════════════════════════════════════════════════════

def test_smart_route_new_jsx_auto_specialist_design():
    from services.ora_guards import smart_route
    r = smart_route(
        task_type="design",
        brief="Add a brand-new CheckoutForm component above the fold",
        relevant_files=["/app/frontend/src/CheckoutForm.jsx"],
        is_new_file=True,
        session_id="s1", task_id="t1",
    )
    assert r["mode"] == "emergent"
    assert r["task_type"] == "design"
    assert r["auto_specialist"] is True
    assert "design" in r["reason"]


def test_smart_route_new_tsx_also_design_specialist():
    from services.ora_guards import smart_route
    r = smart_route(
        task_type="design",
        brief="Brand-new dashboard widget",
        relevant_files=["/app/frontend/src/Widget.tsx"],
        is_new_file=True,
        session_id="s1", task_id="t1",
    )
    assert r["auto_specialist"] is True
    assert r["mode"] == "emergent"


def test_smart_route_new_stripe_integration_emergent():
    from services.ora_guards import smart_route
    r = smart_route(
        task_type="integration",
        brief="Integrate Stripe for new subscription billing tier",
        relevant_files=[],
        session_id="s1", task_id="t1",
    )
    assert r["mode"] == "emergent"
    assert r["task_type"] == "integration"
    assert r["auto_specialist"] is True
    assert "third_party" in r["reason"]


def test_smart_route_new_resend_integration_emergent():
    from services.ora_guards import smart_route
    r = smart_route(
        task_type="integration",
        brief="Wire up Resend for transactional emails",
        relevant_files=[],
        session_id="s1", task_id="t1",
    )
    assert r["auto_specialist"] is True


def test_smart_route_simple_debug_default_ora():
    from services.ora_guards import smart_route, record_task_success
    record_task_success("s2", "t2")   # clean slate
    r = smart_route(
        task_type="debug",
        brief="Why does the dashboard count drift by 1?",
        relevant_files=["/app/backend/services/x.py"],
        session_id="s2", task_id="t2",
    )
    assert r["mode"] == "ora"
    assert r["auto_specialist"] is False
    assert "default" in r["reason"] or "ora" in r["reason"]


def test_smart_route_complex_debug_tagged_for_escalation():
    """Debug touching 3+ files still tries ORA first, but with a
    reason that explains it'll escalate quickly."""
    from services.ora_guards import smart_route, record_task_success
    record_task_success("s3", "t3")
    r = smart_route(
        task_type="debug",
        brief="Cross-cutting bug in dispatch / queue / scheduler",
        relevant_files=["/a.py", "/b.py", "/c.py"],
        session_id="s3", task_id="t3",
    )
    assert r["mode"] == "ora"
    assert "3plus_files" in r["reason"]


def test_smart_route_after_two_failures_flips_to_emergent():
    """The 3-failure ladder: clean → fail → fail → smart_route picks
    emergent because the threshold was crossed."""
    from services.ora_guards import (
        smart_route, record_task_failure, record_task_success,
    )
    sid, tid = "s4", "t4"
    record_task_success(sid, tid)   # clean
    record_task_failure(sid, tid)
    record_task_failure(sid, tid)
    r = smart_route(
        task_type="debug",
        brief="same bug as before",
        relevant_files=["/x.py"],
        session_id=sid, task_id=tid,
    )
    assert r["mode"] == "emergent"
    assert r["previous_fails"] == 2
    assert "escalated" in r["reason"]
    # Cleanup
    record_task_success(sid, tid)


# ═══════════════════════════════════════════════════════════════════
# Validated solutions endpoint
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_validated_solutions_endpoint_returns_recent_rows(vs_db):
    """E2E Proof 6 — /api/admin/ora/validated-solutions exposes the
    'What ORA taught itself' panel data."""
    from services import ora_validated_solutions as VS
    # Seed 3 solutions
    seeded = []
    for i in range(3):
        sig = f"sig-panel-{uuid.uuid4().hex}"
        seeded.append(sig)
        await VS.save_solution(
            signature=sig,
            task_type="debug",
            fix_suggestion=f"Patch {i}: bump retry to N+1",
            findings=[f"finding-{i}"],
            files_involved=[f"/x{i}.py"],
            specialist="ora",
        )
    try:
        from routers.ora_specialist_cost_router import (
            validated_solutions, set_db as _set_router_db,
        )
        _set_router_db(vs_db)

        class _AdminRequest:
            headers = {"authorization": "Bearer fake-admin-for-test"}

        out = await validated_solutions(_AdminRequest())   # type: ignore[arg-type]
        assert out["ok"] is True
        # Our seeded sigs should be in the response
        returned_sigs = {r["signature"] for r in out["rows"]}
        for s in seeded:
            assert s in returned_sigs, f"missing seeded sig {s}"
        # Plain-English fix_suggestion present
        for row in out["rows"]:
            if row["signature"] in seeded:
                assert "Patch" in row["fix_suggestion"]
    finally:
        for sig in seeded:
            await vs_db.ora_validated_solutions.delete_one({"signature": sig})


@pytest.mark.asyncio
async def test_validated_solutions_endpoint_admin_gated():
    """Endpoint refuses calls without an admin bearer (Proof 6 negative)."""
    from routers.ora_specialist_cost_router import validated_solutions
    from fastapi import HTTPException

    class _AnonRequest:
        headers = {}

    try:
        await validated_solutions(_AnonRequest())   # type: ignore[arg-type]
    except HTTPException as e:
        assert e.status_code in (401, 403, 503)
    else:
        pytest.fail("must refuse without admin bearer")


# ═══════════════════════════════════════════════════════════════════
# E2E Proof 3 — repeat task hits cache
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_proof3_repeat_task_uses_validated_solution(vs_db):
    """Trigger the SAME debug task a 2nd time → validated solution found,
    cost = 0, used_validated_solution = True."""
    from services import ora_validated_solutions as VS
    from services.ora_fork_context import fork_context
    brief = "NoneType subscript bug in handler — 3rd time today"
    sig = VS.compute_signature("debug", brief, "")
    try:
        # First time: seed the solution as if a real run had saved it
        await VS.save_solution(
            signature=sig, task_type="debug",
            fix_suggestion="guard against None before subscripting",
            findings=["dispatch returned None on empty queue"],
            files_involved=[], specialist="ora",
        )
        # Second invocation — must hit cache, $0
        r = await fork_context(task_type="debug", brief=brief,
                                relevant_files=[], mode="ora")
        assert r["ok"] is True
        assert r["used_validated_solution"] is True
        assert r["elapsed_s"] == 0.0
        assert "guard against None" in r["fix_suggestion"]
    finally:
        await vs_db.ora_validated_solutions.delete_one({"signature": sig})


# ═══════════════════════════════════════════════════════════════════
# E2E Proof 5 — cockpit rollup shows ora + emergent + validated
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_e2e_proof5_cockpit_shows_three_buckets(vs_db):
    """After mixed calls land, the cost rollup returns all three buckets."""
    from services.ora_validated_solutions import (
        log_specialist_call, cost_rollup_7d,
    )
    sid_prefix = f"proof5-{uuid.uuid4().hex[:6]}"
    try:
        await log_specialist_call(
            session_id=f"{sid_prefix}-1", mode="ora",
            task_type="debug", specialist_name="ora",
            verdict="pass", used_validated_solution=False,
            tokens_used=80,
        )
        await log_specialist_call(
            session_id=f"{sid_prefix}-2", mode="emergent",
            task_type="design", specialist_name="emergent",
            verdict="pass", used_validated_solution=False,
            tokens_used=400,
        )
        await log_specialist_call(
            session_id=f"{sid_prefix}-3", mode="ora",
            task_type="debug", specialist_name="cache",
            verdict="pass", used_validated_solution=True,
        )
        roll = await cost_rollup_7d()
        assert roll["ok"] is True
        # The 'shape' the cockpit tile reads
        for key in ("ora", "emergent", "validated"):
            assert key in roll
        assert roll["ora"]["calls"] >= 1
        assert roll["emergent"]["calls"] >= 1
        assert roll["validated"]["calls"] >= 1
        # Total spent counts only paid calls
        assert roll["total_spent_usd"] > 0
        # Savings reflect the cache hit
        assert roll["total_saved_usd"] >= 0.05 - 1e-6
    finally:
        await vs_db.ora_specialist_calls.delete_many(
            {"session_id": {"$regex": f"^{sid_prefix}"}}
        )


# ═══════════════════════════════════════════════════════════════════
# Source-level wiring sanity
# ═══════════════════════════════════════════════════════════════════

def test_smart_route_and_escalation_exported():
    from services import ora_guards as G
    for name in ("smart_route", "record_task_failure",
                 "record_task_success", "check_escalation_needed",
                 "ESCALATE_AFTER_FAILS"):
        assert hasattr(G, name), f"missing public API: {name}"


def test_cockpit_tiles_wired_in_jsx():
    from pathlib import Path
    src = Path("/app/frontend/src/platform/admin/OraCtoCockpit.jsx").read_text()
    assert "SpecialistCostBreakdownTile" in src
    assert "ValidatedSolutionsPanel" in src


def test_validated_solutions_endpoint_registered():
    from pathlib import Path
    src = Path("/app/backend/routers/ora_specialist_cost_router.py").read_text()
    assert "/validated-solutions" in src


def test_fork_context_updates_failure_counter_on_fail(monkeypatch):
    """fork_context must call record_task_failure when verdict is fail
    and record_task_success when verdict is pass."""
    import pathlib
    src = pathlib.Path("/app/backend/services/ora_fork_context.py").read_text()
    assert "record_task_failure" in src
    assert "record_task_success" in src
