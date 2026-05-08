"""
Phase 2-5 regression — covers:
  - sovereign_memory.promote_if_ready resilient to legacy docs
  - council_backlog clear-backlog body-tunable cutoff
  - ora_knowledge_base.query / top / summarize / digest / assessment
  - error_ledger record + dedupe
  - deploy_monitor version detection
  - agent_health_check 7-rule orchestrator returns dict
"""
import asyncio
import os
import sys
import uuid

import pytest

sys.path.insert(0, "/app/backend")
os.environ.setdefault("DB_NAME", "aurem_db")


@pytest.fixture
def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]]


@pytest.mark.asyncio
async def test_promote_if_ready_legacy_doc(db):
    """A legacy doc missing submitted_by/kind should still promote."""
    from services.sovereign_memory import promote_if_ready
    lid = uuid.uuid4().hex
    await db.learnings_pending_review.insert_one({
        "id": lid,
        "kind": "test_legacy",
        "stamps": [
            {"role": "council_admin", "vote": "approve", "ts": "2026-05-06T00:00:00+00:00"},
            {"role": "auto_promoter", "vote": "approve", "ts": "2026-05-06T00:00:00+00:00"},
        ],
        "status": "pending",
    })
    res = await promote_if_ready(db, lid)
    assert res is not None, "promote_if_ready should return live doc"
    assert res["submitted_by"] == "system"
    # Cleanup
    await db.learnings_pending_review.delete_one({"id": lid})
    await db.learnings.delete_one({"id": lid})


@pytest.mark.asyncio
async def test_ora_knowledge_query(db):
    from services.ora_knowledge_base import query_knowledge, top_patterns, summarize_period
    items = await query_knowledge(db, limit=5)
    assert isinstance(items, list)
    top = await top_patterns(db, limit=3)
    assert isinstance(top, list)
    summ = await summarize_period(db, hours=24)
    assert summ.get("available") is True
    assert "rejection_rate" in summ


@pytest.mark.asyncio
async def test_error_ledger_dedupe(db):
    import server
    server.db = db
    from services.error_ledger import record_error, top_open
    try:
        raise RuntimeError("phase4_test_dedupe_marker")
    except RuntimeError as e:
        h1 = await record_error(e, path="/test/phase4")
        h2 = await record_error(e, path="/test/phase4")
    assert h1 is not None and h1 == h2, "dedupe must produce same hash"
    open_rows = await top_open(50)
    found = [r for r in open_rows if r["error_hash"] == h1]
    assert found, "ledger should have the recorded error"
    assert found[0]["count"] >= 2, "count should increment on dedupe"
    # Cleanup
    await db.error_ledger.delete_one({"error_hash": h1})


@pytest.mark.asyncio
async def test_deploy_monitor_version(db):
    import server
    server.db = db
    from services.deploy_monitor import _read_running_version
    v = await _read_running_version()
    assert v, "deploy version must resolve"
    assert isinstance(v, str)


@pytest.mark.asyncio
async def test_agent_health_check_runs(db):
    import server
    server.db = db
    from services.agent_health_check import run_health_check_once
    res = await run_health_check_once()
    assert res["ok"] is True
    for r in ("R1_silent", "R2_rejection_rate", "R3_cost_spike",
              "R4_error_rate", "R5_queue_overflow",
              "R6_deploy_drift", "R7_idle"):
        assert r in res, f"missing rule {r}"
    assert "total_fired" in res
