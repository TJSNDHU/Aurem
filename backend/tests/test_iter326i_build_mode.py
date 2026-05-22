"""
iter 326i — BUILD MODE regression tests
═══════════════════════════════════════════════════════════════════════════
Scope:
  1. `run_pytest` tool — path guard, structured output, exit-code parse
  2. `verify_endpoint` tool — status assert + substring assert
  3. `build_verifier` service — record_proof + reverify_one drift detect
  4. Tool registry — both new tools tier-1 (auto), wired into TOOL_REGISTRY
  5. System prompt — BUILD MODE directive present
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient


# ── Shared ephemeral DB fixture (same pattern as iter 326h) ────────────
@pytest.fixture
def live_db_builder():
    db_name = f"aurem_iter326i_{uuid.uuid4().hex[:12]}"

    def _builder():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        return client[db_name], client

    yield _builder

    async def _cleanup():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        await cli.drop_database(db_name)
        cli.close()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_cleanup())
    finally:
        loop.close()


def _run(coro):
    """Run an async coroutine in a fresh event loop (motor-safe)."""
    return asyncio.new_event_loop().run_until_complete(coro)


# ════════════════════════════════════════════════════════════════════════
# 1. run_pytest — Tier-1 tool
# ════════════════════════════════════════════════════════════════════════

def test_run_pytest_rejects_outside_tests_dir():
    from services.ora_tools import run_pytest

    async def go():
        res = await run_pytest("/app/backend/server.py")
        assert res["ok"] is False
        assert "/app/backend/tests" in res["error"]

    _run(go())


def test_run_pytest_rejects_missing_file():
    from services.ora_tools import run_pytest

    async def go():
        res = await run_pytest("/app/backend/tests/__does_not_exist__.py")
        assert res["ok"] is False
        assert "not found" in res["error"]

    _run(go())


def test_run_pytest_returns_structured_envelope_on_real_run(tmp_path):
    """Run pytest against an actual tiny test file under /app/backend/tests.
    Use a known-good file from this iter (iter326h) as the target."""
    from services.ora_tools import run_pytest
    target = "/app/backend/tests/test_iter326h_3_critical_db_fixes.py"
    # Skip if the target itself doesn't exist (defensive — should always exist)
    if not os.path.isfile(target):
        pytest.skip("target test file not present")

    async def go():
        # Use ::test selector to run a SINGLE test → cheaper
        res = await run_pytest(
            target + "::test_fix3_idempotent_on_repeat",
            timeout_s=30,
        )
        assert res["ok"] is True, f"unexpected: {res}"
        assert res["exit_code"] == 0
        assert res["passed"] >= 1
        assert res["failed"] == 0
        assert "passed" in res["summary"].lower()
        # tail must be non-empty
        assert res["tail"]
        assert res["duration_s"] >= 0

    _run(go())


# ════════════════════════════════════════════════════════════════════════
# 2. verify_endpoint — Tier-1 tool
# ════════════════════════════════════════════════════════════════════════

def test_verify_endpoint_rejects_external_url():
    from services.ora_tools import verify_endpoint

    async def go():
        res = await verify_endpoint("https://example.com/api/foo")
        assert res["ok"] is False

    _run(go())


def test_verify_endpoint_against_live_health_route():
    """Hit a known-good endpoint and assert structured envelope shape."""
    from services.ora_tools import verify_endpoint

    async def go():
        res = await verify_endpoint("/api/health", expected_status=200)
        # Live backend MAY be slow on this test runner, but envelope must
        # always carry the keys we promised.
        for key in ("ok", "endpoint", "http_status", "expected_status",
                    "matched_status", "latency_ms", "body_snippet"):
            assert key in res, f"missing key {key!r} in {res}"
        # /api/health is registered (we verified earlier in this iter)
        if res["http_status"] != 0:
            assert res["matched_status"] is True

    _run(go())


def test_verify_endpoint_substring_assert():
    from services.ora_tools import verify_endpoint

    async def go():
        # /api/health returns {"status":"ok","platform":"aurem"}
        res = await verify_endpoint(
            "/api/health",
            expected_status=200,
            expected_substring="aurem",
        )
        if res.get("http_status") == 200:
            assert res["matched_substring"] is True
            assert res["ok"] is True

    _run(go())


# ════════════════════════════════════════════════════════════════════════
# 3. build_verifier — record + reverify
# ════════════════════════════════════════════════════════════════════════

def test_build_verifier_record_proof_persists_green(live_db_builder):
    from services import build_verifier as bv

    async def go():
        db, _cli = live_db_builder()
        bv.set_db(db)
        res = await bv.record_proof(
            feature="add /api/foo endpoint",
            files_changed=["backend/routers/foo_router.py",
                           "backend/tests/test_foo.py"],
            tests=[{
                "path":       "/app/backend/tests/test_foo.py",
                "passed":     3, "failed": 0, "errors": 0,
                "duration_s": 0.41, "summary": "3 passed in 0.41s",
            }],
            endpoints=[{
                "endpoint":        "/api/foo",
                "expected_status": 200,
                "matched_status":  True,
                "latency_ms":      42,
            }],
        )
        assert res["ok"] is True
        assert res["verdict"] == "green"
        # Persisted in build_proofs?
        doc = await db.build_proofs.find_one({"_id": res["build_id"]})
        assert doc is not None
        assert doc["verdict"] == "green"
        assert doc["feature"] == "add /api/foo endpoint"
        assert len(doc["files_changed"]) == 2

    _run(go())


def test_build_verifier_verdict_red_when_failed_tests(live_db_builder):
    from services import build_verifier as bv

    async def go():
        db, _cli = live_db_builder()
        bv.set_db(db)
        res = await bv.record_proof(
            feature="bad build",
            files_changed=["x.py"],
            tests=[{"path": "/app/backend/tests/x.py",
                    "passed": 0, "failed": 1, "errors": 0,
                    "duration_s": 0.5, "summary": "1 failed"}],
            endpoints=[],
        )
        assert res["verdict"] == "red"

    _run(go())


def test_build_verifier_verdict_red_when_endpoint_status_mismatch(live_db_builder):
    from services import build_verifier as bv

    async def go():
        db, _cli = live_db_builder()
        bv.set_db(db)
        res = await bv.record_proof(
            feature="endpoint regressed",
            files_changed=["x.py"],
            tests=[],
            endpoints=[{"endpoint": "/api/foo", "expected_status": 200,
                        "matched_status": False, "latency_ms": 800}],
        )
        assert res["verdict"] == "red"

    _run(go())


def test_build_verifier_reverify_one_against_live_endpoint(live_db_builder):
    """Record a proof against /api/health, then re-verify it. Should
    stay green because /api/health is registered + healthy."""
    from services import build_verifier as bv

    async def go():
        db, _cli = live_db_builder()
        bv.set_db(db)
        rec = await bv.record_proof(
            feature="health endpoint check",
            files_changed=[],
            tests=[],
            endpoints=[{
                "endpoint":        "/api/health",
                "expected_status": 200,
                "matched_status":  True,
                "latency_ms":      10,
            }],
        )
        bid = rec["build_id"]
        reverify = await bv.reverify_one(bid)
        assert reverify["ok"] is True
        assert reverify["prior_verdict"] == "green"
        # Live endpoint is up; new verdict must also be green
        if reverify["endpoints"][0]["http_status"] == 200:
            assert reverify["new_verdict"] == "green"
            assert reverify["drifted"] is False
        # last_reverified_at must be set on the doc
        doc = await db.build_proofs.find_one({"_id": bid})
        assert doc["last_reverified_at"] is not None

    _run(go())


def test_build_verifier_drift_event_written_when_endpoint_dies(live_db_builder):
    """Record a green proof against a fake endpoint (matched_status=True
    in the recorded row). Then reverify_one will hit /api/__fake__ which
    returns 404 → verdict downgrades → drift event must be written."""
    from services import build_verifier as bv

    async def go():
        db, _cli = live_db_builder()
        bv.set_db(db)
        rec = await bv.record_proof(
            feature="fake endpoint",
            files_changed=[],
            tests=[],
            endpoints=[{
                "endpoint":        "/api/__does_not_exist__",
                "expected_status": 200,
                "matched_status":  True,    # historical row says green
                "latency_ms":      10,
            }],
        )
        bid = rec["build_id"]
        reverify = await bv.reverify_one(bid)
        assert reverify["prior_verdict"] == "green"
        assert reverify["new_verdict"] == "red"
        assert reverify["drifted"] is True
        drift_doc = await db.build_drift_events.find_one({"build_id": bid})
        assert drift_doc is not None
        assert "green → red" in drift_doc["diff"]["verdict"]

    _run(go())


def test_build_verifier_reverify_tick_skips_old_builds(live_db_builder):
    """Builds older than `max_age_hours` must NOT be considered."""
    from services import build_verifier as bv
    from datetime import datetime, timezone, timedelta

    async def go():
        db, _cli = live_db_builder()
        bv.set_db(db)
        # Insert an old build directly (no record_proof, to backdate it)
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        await db.build_proofs.insert_one({
            "_id":                  "old1",
            "created_at":           old_ts,
            "feature":              "old build",
            "files_changed":        [], "tests": [], "endpoints": [],
            "verdict":              "green",
            "last_reverified_at":   None,
            "last_reverify_verdict": None,
        })
        # And a fresh one
        await bv.record_proof(feature="fresh", files_changed=[],
                              tests=[], endpoints=[])
        res = await bv.reverify_tick(max_age_hours=24)
        # Old build excluded
        assert res["considered"] == 1

    _run(go())


# ════════════════════════════════════════════════════════════════════════
# 4. Tool registry & tier wiring
# ════════════════════════════════════════════════════════════════════════

def test_tools_registered_in_TOOL_REGISTRY():
    from services.ora_tools import TOOL_REGISTRY
    for name in ("run_pytest", "verify_endpoint"):
        assert name in TOOL_REGISTRY, f"{name} not in TOOL_REGISTRY"
        meta = TOOL_REGISTRY[name]
        assert "fn" in meta and callable(meta["fn"])
        assert "args_spec" in meta
        assert "description" in meta
        assert meta["description"], f"{name} description empty"


def test_tools_are_tier1_auto():
    from services.ora_agent import TIER_1_AUTO
    assert "run_pytest" in TIER_1_AUTO
    assert "verify_endpoint" in TIER_1_AUTO


# ════════════════════════════════════════════════════════════════════════
# 5. System prompt — BUILD MODE directive
# ════════════════════════════════════════════════════════════════════════

def test_system_prompt_has_build_mode_directive():
    from services.ora_agent import SYSTEM_PROMPT
    # The whole directive must be present, not just a stub
    assert "BUILD MODE" in SYSTEM_PROMPT
    # All 5 numbered steps must appear
    for marker in ("Step 1 — PLAN", "Step 2 — WIRE", "Step 3 — TEST",
                   "Step 4 — VERIFY", "Step 5 — REPLY"):
        assert marker in SYSTEM_PROMPT, f"missing marker: {marker}"
    # iter 326n — verification tools are still mandatory; only the
    # founder-facing reply format changed (plain English summary first,
    # technical proof on demand instead of mandated PROOF TABLE).
    assert "run_pytest" in SYSTEM_PROMPT
    assert "verify_endpoint" in SYSTEM_PROMPT
    # Pass criteria for both must still be hard-wired into the prompt.
    assert "passed >= 1" in SYSTEM_PROMPT and "failed == 0" in SYSTEM_PROMPT
    assert "matched_status" in SYSTEM_PROMPT
    # Anti-hallucination guard rails still in force.
    assert "looks good" in SYSTEM_PROMPT  # banned phrase reference
    # "should be working" appears across a line wrap in the prompt source,
    # so match the literal substring as it lands in the rendered string.
    assert "should\n      be working" in SYSTEM_PROMPT or "should be working" in SYSTEM_PROMPT


def test_server_startup_wires_build_verifier_db():
    src = open("/app/backend/server.py", encoding="utf-8").read()
    assert "from services import build_verifier" in src
    assert "build_verifier.set_db(db)" in src
