"""Tests for the Sovereign Memory Guard (iter 322k — two-stamp learning gate)."""
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

from services import sovereign_memory as smg


# ─── Minimal in-memory Mongo stand-in (only what smg uses) ─────────────
class _Cursor:
    def __init__(self, items: List[Dict[str, Any]]):
        self.items = list(items)
    def sort(self, *_a, **_k): return self
    def limit(self, n):
        self.items = self.items[:n]; return self
    def __aiter__(self):
        async def gen():
            for d in self.items:
                yield d
        return gen()


class FakeColl:
    def __init__(self):
        self.docs: List[Dict[str, Any]] = []

    @staticmethod
    def _matches(doc: Dict[str, Any], q: Dict[str, Any]) -> bool:
        for k, v in q.items():
            if "." in k:
                head, tail = k.split(".", 1)
                arr = doc.get(head, []) or []
                if isinstance(v, dict) and "$ne" in v:
                    if any(
                        isinstance(item, dict) and item.get(tail) == v["$ne"]
                        for item in arr
                    ):
                        return False
                else:
                    if not any(
                        isinstance(item, dict) and item.get(tail) == v
                        for item in arr
                    ):
                        return False
            elif isinstance(v, dict):
                if "$ne" in v and doc.get(k) == v["$ne"]:
                    return False
                if "$gte" in v and doc.get(k, "") < v["$gte"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    async def insert_one(self, doc):
        self.docs.append(doc)

    async def find_one(self, q, proj=None, sort=None):
        items = [d for d in self.docs if self._matches(d, q)]
        if sort:
            key, direction = sort[0]
            items.sort(key=lambda d: d.get(key, ""), reverse=(direction == -1))
        return items[0] if items else None

    async def update_one(self, q, update):
        for d in self.docs:
            if self._matches(d, q):
                if "$set" in update:
                    d.update(update["$set"])
                if "$push" in update:
                    for k, v in update["$push"].items():
                        d.setdefault(k, []).append(v)
                if "$unset" in update:
                    for k in update["$unset"]:
                        d.pop(k, None)
                return type("R", (), {"modified_count": 1})()
        return type("R", (), {"modified_count": 0})()

    async def count_documents(self, q):
        return sum(1 for d in self.docs if self._matches(d, q))

    def find(self, q, proj=None):
        items = [d for d in self.docs if self._matches(d, q)]
        return _Cursor(items)


class FakeDB:
    def __init__(self):
        self._colls: Dict[str, FakeColl] = {}

    def __getitem__(self, name):
        return self._colls.setdefault(name, FakeColl())


# ─── Submission gate ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_submit_requires_evidence():
    db = FakeDB()
    with pytest.raises(ValueError, match="evidence_required"):
        await smg.submit_learning(
            db, agent_role="watchdog", kind="x", payload={}, evidence={},
        )


@pytest.mark.asyncio
async def test_submit_rejects_unknown_role():
    db = FakeDB()
    with pytest.raises(ValueError, match="unknown agent_role"):
        await smg.submit_learning(
            db, agent_role="not_a_real_role", kind="x",
            payload={}, evidence={"src": "test"},
        )


@pytest.mark.asyncio
async def test_submit_writes_pending_with_zero_stamps():
    db = FakeDB()
    lid = await smg.submit_learning(
        db, agent_role="watchdog", kind="redis_fix",
        payload={"recipe": "redis_pool_kick"},
        evidence={"line": "max number of clients reached"},
    )
    assert lid
    doc = await db[smg.PENDING].find_one({"id": lid})
    assert doc["status"] == "pending"
    assert doc["stamps"] == []
    assert doc["submitted_by"] == "watchdog"


# ─── Two-stamp gate ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_self_stamp_forbidden():
    db = FakeDB()
    lid = await smg.submit_learning(
        db, agent_role="watchdog", kind="x",
        payload={}, evidence={"e": 1},
    )
    res = await smg.review_learning(
        db, learning_id=lid, reviewer_role="watchdog",
        vote="approve", notes="self stamp",
    )
    assert res["ok"] is False
    assert res["error"] == "self_stamp_forbidden"


@pytest.mark.asyncio
async def test_one_stamp_does_not_promote():
    db = FakeDB()
    lid = await smg.submit_learning(
        db, agent_role="watchdog", kind="x",
        payload={}, evidence={"e": 1},
    )
    res = await smg.review_learning(
        db, learning_id=lid, reviewer_role="dev",
        vote="approve", notes="ok",
    )
    assert res["ok"] is True
    assert res["promoted"] is False
    assert await db[smg.LIVE].count_documents({}) == 0


@pytest.mark.asyncio
async def test_two_distinct_stamps_promote():
    db = FakeDB()
    lid = await smg.submit_learning(
        db, agent_role="watchdog", kind="redis_fix",
        payload={}, evidence={"e": 1},
    )
    await smg.review_learning(
        db, learning_id=lid, reviewer_role="dev",
        vote="approve", notes="aligns with logs",
    )
    res = await smg.review_learning(
        db, learning_id=lid, reviewer_role="security",
        vote="approve", notes="no risk surface",
    )
    assert res["ok"] is True
    assert res["promoted"] is True
    promoted = await db[smg.LIVE].find_one({"id": lid})
    assert promoted is not None
    assert {s["role"] for s in promoted["stamps"]} == {"dev", "security"}


@pytest.mark.asyncio
async def test_duplicate_stamp_blocked():
    db = FakeDB()
    lid = await smg.submit_learning(
        db, agent_role="watchdog", kind="x",
        payload={}, evidence={"e": 1},
    )
    await smg.review_learning(
        db, learning_id=lid, reviewer_role="dev", vote="approve",
    )
    res = await smg.review_learning(
        db, learning_id=lid, reviewer_role="dev", vote="approve",
    )
    assert res["ok"] is False
    assert res["error"] == "duplicate_stamp"


@pytest.mark.asyncio
async def test_reject_terminates_review():
    db = FakeDB()
    lid = await smg.submit_learning(
        db, agent_role="watchdog", kind="x",
        payload={}, evidence={"e": 1},
    )
    res = await smg.review_learning(
        db, learning_id=lid, reviewer_role="security",
        vote="reject", notes="risky",
    )
    assert res["ok"] is True
    assert res["rejected"] is True
    # Subsequent review should fail because status moved off pending
    res2 = await smg.review_learning(
        db, learning_id=lid, reviewer_role="dev", vote="approve",
    )
    assert res2["ok"] is False
    assert res2["error"] == "already_rejected"


# ─── Rotation ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_next_pending_excludes_submitter():
    db = FakeDB()
    lid_w = await smg.submit_learning(
        db, agent_role="watchdog", kind="x",
        payload={}, evidence={"e": 1},
    )
    # watchdog calls next_for_review → must NOT see its own submission
    item = await smg.next_pending_for_review(db, exclude_role="watchdog")
    assert item is None
    # dev calls → sees it
    item2 = await smg.next_pending_for_review(db, exclude_role="dev")
    assert item2 is not None
    assert item2["id"] == lid_w


@pytest.mark.asyncio
async def test_next_pending_excludes_already_stamped_role():
    db = FakeDB()
    lid = await smg.submit_learning(
        db, agent_role="watchdog", kind="x",
        payload={}, evidence={"e": 1},
    )
    await smg.review_learning(
        db, learning_id=lid, reviewer_role="dev", vote="approve",
    )
    # `dev` already stamped → should not see it again
    item = await smg.next_pending_for_review(db, exclude_role="dev")
    assert item is None
    # security still hasn't stamped → sees it
    item2 = await smg.next_pending_for_review(db, exclude_role="security")
    assert item2 is not None


@pytest.mark.asyncio
async def test_stats_and_promoted_reads():
    db = FakeDB()
    # 1 promoted, 1 pending
    lid_a = await smg.submit_learning(
        db, agent_role="watchdog", kind="redis_fix",
        payload={}, evidence={"e": 1},
    )
    await smg.review_learning(db, learning_id=lid_a, reviewer_role="dev", vote="approve")
    await smg.review_learning(db, learning_id=lid_a, reviewer_role="qa", vote="approve")

    await smg.submit_learning(
        db, agent_role="watchdog", kind="other",
        payload={}, evidence={"e": 2},
    )

    stats = await smg.get_memory_guard_stats(db)
    assert stats["pending_review"] == 1
    assert stats["promoted_total"] == 1

    promoted = await smg.get_promoted_learnings(db, kind="redis_fix")
    assert len(promoted) == 1
    assert promoted[0]["kind"] == "redis_fix"


# ─── Promotion idempotency ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_promote_if_ready_is_idempotent():
    db = FakeDB()
    lid = await smg.submit_learning(
        db, agent_role="watchdog", kind="x",
        payload={}, evidence={"e": 1},
    )
    await smg.review_learning(db, learning_id=lid, reviewer_role="dev", vote="approve")
    await smg.review_learning(db, learning_id=lid, reviewer_role="qa", vote="approve")
    # Second promote call should be a no-op
    out = await smg.promote_if_ready(db, lid)
    assert out is None
    # Live collection still has exactly one row
    assert await db[smg.LIVE].count_documents({}) == 1
