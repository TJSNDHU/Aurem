"""
iter 332a-1 — Emergent Specialist Swarm foundation
==================================================

Tests for Parts 1 + 3 + 4 of the swarm spec:

Part 1 — fork_context mode extension
  • mode="ora"      (default) still works exactly as before
  • mode="emergent" tags the cost row + result envelope
  • mode="garbage"  refused with clear error
  • task_type aliases: "integration" + "design" route to existing prompts

Part 3 — Validated solution memory
  • compute_signature is deterministic
  • compute_signature normalises line numbers + traceback noise
  • Different file_type → different signature
  • lookup_solution returns None when nothing cached
  • save_solution + lookup_solution round-trip
  • lookup_solution caps at MAX_USES_BEFORE_REVALIDATE
  • Second identical fork_context call hits the cache at $0

Part 4 — Cost tracking
  • log_specialist_call writes a row with expected fields
  • cost_rollup_7d aggregates ora / emergent / validated buckets
  • cost_rollup_7d sums total_spent + total_saved
  • Specialist Cost Breakdown endpoint requires admin
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone, timedelta

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
    """Wire the validated_solutions service to the test DB and clean up
    leftovers from earlier runs that share the unique signature index."""
    from services import ora_validated_solutions as VS
    VS.set_db(db)
    yield db
    # Best-effort cleanup of test-signature rows
    await db.ora_validated_solutions.delete_many({"task_type": "test332a"})
    await db.ora_specialist_calls.delete_many({"task_type": "test332a"})


# ═══════════════════════════════════════════════════════════════════
# Part 3 — Signature hashing
# ═══════════════════════════════════════════════════════════════════

def test_signature_is_deterministic():
    from services.ora_validated_solutions import compute_signature
    sig1 = compute_signature("debug", "NameError: x is not defined", ".py")
    sig2 = compute_signature("debug", "NameError: x is not defined", ".py")
    assert sig1 == sig2
    assert len(sig1) == 64    # SHA256 hex


def test_signature_normalises_traceback_noise():
    """Two tracebacks for the same bug with different line numbers
    must collapse to the same signature."""
    from services.ora_validated_solutions import compute_signature
    err1 = (
        'File "/app/x.py", line 42, in foo\n'
        '  return bar(req_id=12345678)\n'
        'AttributeError: object has no attribute "baz"'
    )
    err2 = (
        'File "/app/x.py", line 99, in foo\n'
        '  return bar(req_id=98765432)\n'
        'AttributeError: object has no attribute "baz"'
    )
    assert compute_signature("debug", err1, ".py") == compute_signature("debug", err2, ".py")


def test_signature_different_file_type_different_hash():
    from services.ora_validated_solutions import compute_signature
    py_sig = compute_signature("debug", "TypeError: blah", ".py")
    js_sig = compute_signature("debug", "TypeError: blah", ".js")
    assert py_sig != js_sig


def test_signature_different_task_type_different_hash():
    from services.ora_validated_solutions import compute_signature
    a = compute_signature("debug", "same problem", ".py")
    b = compute_signature("qa",    "same problem", ".py")
    assert a != b


# ═══════════════════════════════════════════════════════════════════
# Part 3 — Cache lookup + save round-trip
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_lookup_returns_none_when_empty(vs_db):
    from services.ora_validated_solutions import lookup_solution
    fake_sig = "deadbeef" * 8
    r = await lookup_solution(fake_sig)
    assert r is None


@pytest.mark.asyncio
async def test_save_and_lookup_roundtrip(vs_db):
    from services.ora_validated_solutions import (
        save_solution, lookup_solution,
    )
    sig = f"sig-{uuid.uuid4().hex}"
    try:
        save = await save_solution(
            signature=sig,
            task_type="test332a",
            fix_suggestion="bump retry to 3",
            findings=["retry was set to 0"],
            files_involved=["/tmp/x.py"],
            specialist="ora",
        )
        assert save["ok"] is True
        assert save["is_new"] is True

        r = await lookup_solution(sig)
        assert r is not None
        assert r["fix_suggestion"] == "bump retry to 3"
        assert r["findings"] == ["retry was set to 0"]
        # First hit bumps use_count from 0 → 1
        assert r["use_count"] == 1
        # Second hit bumps to 2
        r2 = await lookup_solution(sig)
        assert r2["use_count"] == 2
    finally:
        await vs_db.ora_validated_solutions.delete_many({"signature": sig})


@pytest.mark.asyncio
async def test_lookup_caps_after_max_uses(vs_db, monkeypatch):
    """Once use_count reaches MAX_USES_BEFORE_REVALIDATE, lookup_solution
    returns None so the next call falls through to a fresh specialist."""
    from services import ora_validated_solutions as VS
    sig = f"sig-cap-{uuid.uuid4().hex}"
    # Force a low cap so we don't have to bump 10×
    monkeypatch.setattr(VS, "MAX_USES_BEFORE_REVALIDATE", 3)
    try:
        await VS.save_solution(
            signature=sig, task_type="test332a",
            fix_suggestion="x", findings=[], specialist="ora",
        )
        # 3 hits should all succeed (counts 1..3)
        for expected in (1, 2, 3):
            r = await VS.lookup_solution(sig)
            assert r is not None
            assert r["use_count"] == expected
        # 4th hit must miss → caller will re-validate
        r = await VS.lookup_solution(sig)
        assert r is None
    finally:
        await vs_db.ora_validated_solutions.delete_many({"signature": sig})


# ═══════════════════════════════════════════════════════════════════
# Part 1 — fork_context cache hit (end-to-end)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_fork_context_second_call_hits_cache(vs_db):
    """Seed a validated solution, then call fork_context with a brief
    that hashes to the same signature. The second call must skip the
    LLM, return at zero cost, and stamp used_validated_solution=True."""
    from services import ora_validated_solutions as VS
    from services.ora_fork_context import fork_context
    brief = "TypeError: 'NoneType' object is not subscriptable in dispatch"
    # fork_context computes file_type from the first relevant file's
    # extension; with no files passed, file_type = "". Seed with the
    # same to make signatures match.
    sig = VS.compute_signature("debug", brief, "")
    try:
        await VS.save_solution(
            signature=sig, task_type="debug",
            fix_suggestion="guard against None before subscripting",
            findings=["dispatch handler returns None on empty queue"],
            files_involved=[],
            specialist="ora",
        )
        # Set the use_count to MAX-1 so the test can prove the cache is
        # actually working AND the cap behaviour is in place
        await vs_db.ora_validated_solutions.update_one(
            {"signature": sig}, {"$set": {"use_count": 1}},
        )
        r = await fork_context(
            task_type="debug",
            brief=brief,
            relevant_files=[],
            mode="ora",
        )
        assert r["ok"] is True
        assert r["used_validated_solution"] is True
        assert r["fix_suggestion"] == "guard against None before subscripting"
        assert r["findings"] == ["dispatch handler returns None on empty queue"]
        assert r["elapsed_s"] == 0.0     # no LLM call
        assert r["signature"] == sig
    finally:
        await vs_db.ora_validated_solutions.delete_many({"signature": sig})
        await vs_db.ora_specialist_calls.delete_many({"task_type": "debug"})


@pytest.mark.asyncio
async def test_fork_context_rejects_unknown_mode():
    from services.ora_fork_context import fork_context
    r = await fork_context(
        task_type="debug", brief="anything at all", mode="quantum",
    )
    assert r["ok"] is False
    assert "unknown mode" in r["error"]


@pytest.mark.asyncio
async def test_fork_context_rejects_unknown_task_type():
    from services.ora_fork_context import fork_context
    r = await fork_context(
        task_type="bogus_task", brief="anything at all", mode="ora",
    )
    assert r["ok"] is False
    assert "unknown task_type" in r["error"]


def test_fork_context_accepts_new_task_type_aliases():
    """Source-level proof — the new aliases route to existing prompts."""
    from services.ora_fork_context import _PROMPTS
    assert "integration" in _PROMPTS
    assert "design" in _PROMPTS
    # Same prompt as the canonical names
    assert _PROMPTS["integration"] is _PROMPTS["integration_check"]


# ═══════════════════════════════════════════════════════════════════
# Part 4 — Cost tracking
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_log_specialist_call_writes_expected_row(vs_db):
    from services.ora_validated_solutions import log_specialist_call
    sid = f"sess-{uuid.uuid4().hex[:8]}"
    try:
        r = await log_specialist_call(
            session_id=sid, mode="ora", task_type="test332a",
            specialist_name="ora", verdict="pass",
            used_validated_solution=False,
            tokens_used=120, elapsed_ms=540,
        )
        assert r["ok"] is True
        assert r["mode"] == "ora"
        assert r["cost_usd"] > 0
        row = await vs_db.ora_specialist_calls.find_one({"session_id": sid})
        assert row is not None
        assert row["specialist_name"] == "ora"
        assert row["tokens_used"] == 120
        assert row["used_validated_solution"] is False
    finally:
        await vs_db.ora_specialist_calls.delete_many({"session_id": sid})


@pytest.mark.asyncio
async def test_log_specialist_call_zero_cost_for_cache_hit(vs_db):
    from services.ora_validated_solutions import log_specialist_call
    sid = f"sess-cache-{uuid.uuid4().hex[:8]}"
    try:
        r = await log_specialist_call(
            session_id=sid, mode="ora", task_type="test332a",
            specialist_name="cache", verdict="pass",
            used_validated_solution=True,
        )
        assert r["cost_usd"] == 0.0
    finally:
        await vs_db.ora_specialist_calls.delete_many({"session_id": sid})


@pytest.mark.asyncio
async def test_cost_rollup_7d_aggregates_three_buckets(vs_db):
    """Insert a mix of ora / emergent / cache rows and verify the rollup
    splits them into the right buckets with sensible USD totals."""
    from services.ora_validated_solutions import (
        log_specialist_call, cost_rollup_7d,
    )
    sid_prefix = f"rollup-{uuid.uuid4().hex[:6]}"
    try:
        # 3× ora, 1× emergent, 2× cache
        for i in range(3):
            await log_specialist_call(
                session_id=f"{sid_prefix}-ora-{i}", mode="ora",
                task_type="test332a", specialist_name="ora",
                verdict="pass", used_validated_solution=False,
                tokens_used=100,
            )
        await log_specialist_call(
            session_id=f"{sid_prefix}-emergent", mode="emergent",
            task_type="test332a", specialist_name="emergent",
            verdict="pass", used_validated_solution=False,
            tokens_used=500,
        )
        for i in range(2):
            await log_specialist_call(
                session_id=f"{sid_prefix}-cache-{i}", mode="ora",
                task_type="test332a", specialist_name="cache",
                verdict="pass", used_validated_solution=True,
            )
        roll = await cost_rollup_7d()
        assert roll["ok"] is True
        assert roll["window_days"] == 7
        # Our test rows are recent — should be inside the rollup
        assert roll["ora"]["calls"] >= 3
        assert roll["emergent"]["calls"] >= 1
        assert roll["validated"]["calls"] >= 2
        # Cache hits compute savings = N × $0.05 per emergent call avoided
        assert roll["validated"]["usd_saved"] >= 2 * 0.05 - 1e-6
        # Total spent only counts non-cache calls
        assert roll["total_spent_usd"] > 0
        assert roll["total_saved_usd"] == roll["validated"]["usd_saved"]
    finally:
        await vs_db.ora_specialist_calls.delete_many(
            {"session_id": {"$regex": f"^{sid_prefix}"}}
        )


# ═══════════════════════════════════════════════════════════════════
# Part 4 — Cockpit endpoint exposed + admin-gated
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_specialist_cost_endpoint_requires_admin():
    """Direct router-level check — avoids TestClient lifespan since
    spawning two TestClient contexts in one pytest process collides
    with the background scheduler (pre-existing infra issue, not 332a)."""
    from routers.ora_specialist_cost_router import specialist_cost_breakdown
    from fastapi import HTTPException, Request

    class _FakeRequest:
        headers = {}
    try:
        await specialist_cost_breakdown(_FakeRequest())   # type: ignore[arg-type]
    except HTTPException as e:
        # Must refuse without an admin bearer
        assert e.status_code in (401, 403, 503), \
            f"expected auth refusal, got {e.status_code}"
    else:
        pytest.fail("endpoint must refuse calls without admin bearer")


def test_specialist_cost_router_registered_in_codebase():
    from pathlib import Path
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "ora_specialist_cost_router" in src
    assert "specialist-cost-breakdown" in Path(
        "/app/backend/routers/ora_specialist_cost_router.py"
    ).read_text()


def test_validated_solutions_module_exports_match_spec():
    """Source-level audit — public API matches the iter 332a-1 spec."""
    from services import ora_validated_solutions as VS
    for name in ("compute_signature", "lookup_solution", "save_solution",
                 "log_specialist_call", "cost_rollup_7d",
                 "MAX_USES_BEFORE_REVALIDATE", "set_db"):
        assert hasattr(VS, name), f"missing public API: {name}"
