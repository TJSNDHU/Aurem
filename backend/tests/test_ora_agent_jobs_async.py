"""Tests for ora_agent_jobs (async-polling fix for Cloudflare 524 + token-cap).

The legacy POST /api/ora/agent/run executed the full tool-loop inline,
which routinely exceeded 100 s on multi-step queries — Cloudflare Free
plan kills any single request taking longer than that with a 524.

The fix splits the slow path into two short requests:
    POST /run-async      → enqueue, return job_id in <100 ms
    GET  /status/<id>    → poll until status=done; each call <50 ms

These tests verify the queue's correctness and idempotency at the
collection level — no actual Ollama call needed.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from services import ora_agent_jobs


# ── Mongo stub (in-memory, just enough to exercise the worker) ───────
class _MockColl:
    def __init__(self):
        self.docs: dict[str, dict] = {}

    async def insert_one(self, doc):
        self.docs[doc["_id"]] = dict(doc)

        class _R:
            inserted_id = doc["_id"]
        return _R()

    async def find_one(self, query, projection=None, sort=None):
        # Tiny match engine for the queries this module actually issues.
        def matches(d):
            for k, v in query.items():
                if isinstance(v, dict):
                    continue
                if d.get(k) != v:
                    return False
            return True

        matched = [d for d in self.docs.values() if matches(d)]
        if sort:
            field, direction = sort[0]
            matched.sort(key=lambda d: d.get(field) or datetime.min.replace(tzinfo=timezone.utc),
                         reverse=(direction == -1))
        if not matched:
            return None
        out = dict(matched[0])
        if projection:
            wanted = {k for k, v in projection.items() if v == 1}
            if wanted:
                # always keep keys with v==1, drop keys with v==0
                drop = {k for k, v in projection.items() if v == 0}
                if drop:
                    return {k: v for k, v in out.items() if k not in drop}
                return {k: out.get(k) for k in wanted if k in out}
        return out

    async def update_one(self, query, update):
        target_id = query.get("_id")
        if target_id and target_id in self.docs:
            doc = self.docs[target_id]
            ok = all(
                doc.get(k) == v
                for k, v in query.items()
                if not isinstance(v, dict) and k != "_id"
            )
            if not ok:
                class _R:
                    modified_count = 0
                return _R()
            for k, v in update.get("$set", {}).items():
                doc[k] = v

            class _R:
                modified_count = 1
            return _R()

        class _R:
            modified_count = 0
        return _R()

    async def count_documents(self, _q):
        return len(self.docs)

    async def create_index(self, *_a, **_kw):
        return None


class _MockDb:
    def __init__(self):
        self._coll = _MockColl()

    def __getitem__(self, _name):
        return self._coll


# ── Tests ────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_enqueue_returns_job_id_fast():
    db = _MockDb()
    ora_agent_jobs.set_db(db)
    out = await ora_agent_jobs.enqueue(
        session_id="s1", text="hello", founder_email="x@y"
    )
    assert out["ok"] is True
    assert isinstance(out["job_id"], str) and len(out["job_id"]) >= 16
    assert out["status"] == "pending"


@pytest.mark.asyncio
async def test_get_status_only_returns_result_when_done():
    db = _MockDb()
    ora_agent_jobs.set_db(db)
    res = await ora_agent_jobs.enqueue(
        session_id="s2", text="hi", founder_email="x@y"
    )
    jid = res["job_id"]

    # Pending → no heavy payload yet (saves bytes per poll)
    s1 = await ora_agent_jobs.get_status(jid, "x@y")
    assert s1["status"] == "pending"
    assert s1["result"] is None
    assert s1["error"] is None

    # Manually flip to "done" and stuff a result.
    db._coll.docs[jid]["status"] = "done"
    db._coll.docs[jid]["result"] = {"ok": True, "reply": "hello back"}

    s2 = await ora_agent_jobs.get_status(jid, "x@y")
    assert s2["status"] == "done"
    assert s2["result"]["reply"] == "hello back"


@pytest.mark.asyncio
async def test_get_status_404_for_wrong_owner():
    db = _MockDb()
    ora_agent_jobs.set_db(db)
    res = await ora_agent_jobs.enqueue(
        session_id="s3", text="x", founder_email="owner@a"
    )
    out = await ora_agent_jobs.get_status(res["job_id"], "intruder@b")
    assert out["ok"] is False
    assert out["error"] == "not_found"


@pytest.mark.asyncio
async def test_worker_claims_pending_atomically(monkeypatch):
    """Verifies the worker flips a pending job to running, then done,
    after delegating to ora_agent.run_turn (stubbed)."""
    db = _MockDb()
    ora_agent_jobs.set_db(db)
    res = await ora_agent_jobs.enqueue(
        session_id="s4", text="ping", founder_email="x@y"
    )
    jid = res["job_id"]

    fake_turn_result = {"ok": True, "reply": "pong", "tool_calls": 1}

    async def _fake_run_turn(session_id, text, founder_email):
        # Mid-execution the doc must already be "running"
        assert db._coll.docs[jid]["status"] == "running"
        return fake_turn_result

    import services.ora_agent as oa
    monkeypatch.setattr(oa, "run_turn", _fake_run_turn)

    doc = await db._coll.find_one({"status": "pending"})
    await ora_agent_jobs._run_one_job(doc)

    final = db._coll.docs[jid]
    assert final["status"] == "done"
    assert final["result"] == fake_turn_result
    assert final["finished_at"] is not None


@pytest.mark.asyncio
async def test_worker_records_timeout(monkeypatch):
    """Verifies a long-running ora_agent.run_turn gets killed at
    _JOB_TIMEOUT_S and the failure is captured atomically."""
    db = _MockDb()
    ora_agent_jobs.set_db(db)
    res = await ora_agent_jobs.enqueue(
        session_id="s5", text="forever", founder_email="x@y"
    )
    jid = res["job_id"]

    monkeypatch.setattr(ora_agent_jobs, "_JOB_TIMEOUT_S", 0.05)

    async def _hang(session_id, text, founder_email):
        await asyncio.sleep(1.0)
        return {"ok": True}

    import services.ora_agent as oa
    monkeypatch.setattr(oa, "run_turn", _hang)

    doc = await db._coll.find_one({"status": "pending"})
    await ora_agent_jobs._run_one_job(doc)

    final = db._coll.docs[jid]
    assert final["status"] == "failed"
    assert final["error"].startswith("timeout_after_")


@pytest.mark.asyncio
async def test_worker_records_exception(monkeypatch):
    db = _MockDb()
    ora_agent_jobs.set_db(db)
    res = await ora_agent_jobs.enqueue(
        session_id="s6", text="boom", founder_email="x@y"
    )
    jid = res["job_id"]

    async def _boom(*_a, **_kw):
        raise RuntimeError("simulated crash")

    import services.ora_agent as oa
    monkeypatch.setattr(oa, "run_turn", _boom)

    doc = await db._coll.find_one({"status": "pending"})
    await ora_agent_jobs._run_one_job(doc)

    final = db._coll.docs[jid]
    assert final["status"] == "failed"
    assert "simulated crash" in final["error"]


@pytest.mark.asyncio
async def test_double_claim_prevented(monkeypatch):
    """Two concurrent workers must not both run the same job."""
    db = _MockDb()
    ora_agent_jobs.set_db(db)
    res = await ora_agent_jobs.enqueue(
        session_id="s7", text="race", founder_email="x@y"
    )
    jid = res["job_id"]

    calls = []

    async def _ok(*_a, **_kw):
        calls.append(1)
        return {"ok": True, "reply": "done"}

    import services.ora_agent as oa
    monkeypatch.setattr(oa, "run_turn", _ok)

    doc1 = await db._coll.find_one({"status": "pending"})
    # second "worker" sees the same doc snapshot
    doc2 = dict(doc1)

    await asyncio.gather(
        ora_agent_jobs._run_one_job(doc1),
        ora_agent_jobs._run_one_job(doc2),
    )

    assert len(calls) == 1, "run_turn must be called exactly once"
    assert db._coll.docs[jid]["status"] == "done"


@pytest.mark.asyncio
async def test_get_status_handles_missing_db():
    ora_agent_jobs.set_db(None)
    out = await ora_agent_jobs.get_status("doesntmatter", "x@y")
    assert out["ok"] is False
    assert out["error"] == "db_not_ready"
