"""
test_d62_ora_dev_orphan_filter.py — iter D-62
=============================================
Locks in the orphan-proposal cleanup behaviour for ORA Dev Console.

Background
----------
The DB collection `ora_dev_actions` historically had legacy rows where
`proposal_id` was missing/None/"". Those rendered as `#??` cards in the
UI and any approve/reject action POST'd to `/api/admin/ora-dev/undefined/...`
which 404'd.

This test enforces three guarantees:

1. `GET /pending`  → never returns docs without a string `proposal_id`.
2. `GET /list`     → same filter applied.
3. `GET /stats`    → returns an `orphans` count separately so the founder
                     can see + clean them. Real status counts only include
                     proposals with a valid `proposal_id`.
4. `POST /cleanup-orphans` → deletes all orphan rows in one shot.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_pending_filters_orphans(monkeypatch):
    from routers import ora_dev_actions_router as r

    captured_query = {}

    class _FakeCursor:
        def __init__(self): self._docs = []
        def sort(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def __aiter__(self): return self
        async def __anext__(self): raise StopAsyncIteration

    class _FakeColl:
        def find(self, q): captured_query["q"] = q; return _FakeCursor()

    class _FakeDB:
        def __init__(self): self.ora_dev_actions = _FakeColl()

    monkeypatch.setattr(r, "_get_db", lambda: _FakeDB())
    monkeypatch.setattr(r, "verify_admin", lambda *a, **k: {"email": "x@y.z"})

    out = await r.list_pending(authorization="Bearer x")
    assert out["ok"] is True
    q = captured_query["q"]
    # Filter must reject docs whose proposal_id is missing/None/non-string.
    assert q.get("status") == "pending"
    pid_filter = q.get("proposal_id", {})
    assert pid_filter.get("$exists") is True
    assert pid_filter.get("$ne") is None
    assert pid_filter.get("$type") == "string"


@pytest.mark.asyncio
async def test_list_filters_orphans(monkeypatch):
    from routers import ora_dev_actions_router as r

    captured_query = {}

    class _FakeCursor:
        def sort(self, *a, **k): return self
        def limit(self, *a, **k): return self
        def __aiter__(self): return self
        async def __anext__(self): raise StopAsyncIteration

    class _FakeColl:
        def find(self, q): captured_query["q"] = q; return _FakeCursor()

    class _FakeDB:
        def __init__(self): self.ora_dev_actions = _FakeColl()

    monkeypatch.setattr(r, "_get_db", lambda: _FakeDB())
    monkeypatch.setattr(r, "verify_admin", lambda *a, **k: {"email": "x@y.z"})

    out = await r.list_actions(authorization="Bearer x", status=None, limit=10)
    assert out["ok"] is True
    pid_filter = captured_query["q"].get("proposal_id", {})
    assert pid_filter.get("$type") == "string"


@pytest.mark.asyncio
async def test_stats_reports_orphans_separately(monkeypatch):
    from routers import ora_dev_actions_router as r

    class _FakeAgg:
        def __aiter__(self): return self
        async def __anext__(self): raise StopAsyncIteration

    class _FakeColl:
        async def count_documents(self, q):
            # Verifies the orphan-count query shape.
            assert "$or" in q
            assert any("proposal_id" in clause for clause in q["$or"])
            return 7
        def aggregate(self, pipeline):
            # Verifies the stats aggregation excludes orphans.
            assert any(
                "$match" in stage and "proposal_id" in stage.get("$match", {})
                for stage in pipeline
            ), f"orphans must be filtered out of stats: {pipeline}"
            return _FakeAgg()

    class _FakeDB:
        def __init__(self): self.ora_dev_actions = _FakeColl()

    monkeypatch.setattr(r, "_get_db", lambda: _FakeDB())
    monkeypatch.setattr(r, "verify_admin", lambda *a, **k: {"email": "x@y.z"})

    out = await r.stats(authorization="Bearer x")
    assert out["ok"] is True
    assert out["orphans"] == 7
    # Every valid status must be present even if zero.
    for s in ("pending", "approved", "rejected", "applied", "rolled_back", "total"):
        assert s in out


@pytest.mark.asyncio
async def test_cleanup_orphans_deletes(monkeypatch):
    from routers import ora_dev_actions_router as r

    captured = {}

    class _Result:
        deleted_count = 11

    class _FakeColl:
        async def delete_many(self, q):
            captured["q"] = q
            return _Result()

    class _FakeDB:
        def __init__(self): self.ora_dev_actions = _FakeColl()

    monkeypatch.setattr(r, "_get_db", lambda: _FakeDB())
    monkeypatch.setattr(r, "verify_admin", lambda *a, **k: {"email": "x@y.z"})

    out = await r.cleanup_orphans(authorization="Bearer x")
    assert out["ok"] is True
    assert out["deleted"] == 11
    q = captured["q"]
    assert "$or" in q
    # Must include all three orphan-detection variants.
    or_clauses = [str(c) for c in q["$or"]]
    assert any("$exists" in c for c in or_clauses)
    assert any("None" in c or "null" in c.lower() for c in or_clauses)
    assert any("''" in c or '""' in c for c in or_clauses)
