"""Tests for Council Verdict Auto-Apply executor (iter 322p)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

from services import council_verdict_executor as cve


# ─── Fakes ─────────────────────────────────────────────────────────────
class _FakeColl:
    def __init__(self, docs: List[Dict[str, Any]] | None = None):
        self.docs: List[Dict[str, Any]] = list(docs or [])
        self.inserts: List[Dict[str, Any]] = []
        self.updates: List[Dict[str, Any]] = []

    def find(self, q, proj=None):
        items = []
        for d in self.docs:
            ok = True
            for k, v in q.items():
                if isinstance(v, dict):
                    if "$ne" in v and d.get(k) == v["$ne"]:
                        ok = False
                        break
                    if "$exists" in v and (k in d) != v["$exists"]:
                        ok = False
                        break
                elif d.get(k) != v:
                    ok = False
                    break
            if ok:
                items.append(d)

        class _Cursor:
            def __init__(self, items):
                self._items = items
                self._n = None

            def limit(self, n):
                self._n = n
                return self

            def __aiter__(self):
                self._iter = iter(
                    self._items[: self._n] if self._n else self._items
                )
                return self

            async def __anext__(self):
                try:
                    return next(self._iter)
                except StopIteration:
                    raise StopAsyncIteration

        return _Cursor(items)

    async def update_one(self, q, u):
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items()):
                if "$set" in u:
                    d.update(u["$set"])
                self.updates.append({"q": q, "u": u})
                return type("R", (), {"matched_count": 1})()
        self.updates.append({"q": q, "u": u})
        return type("R", (), {"matched_count": 0})()

    async def update_many(self, q, u):
        n = 0
        for d in self.docs:
            ok = True
            for k, v in q.items():
                if isinstance(v, dict):
                    if "$ne" in v and d.get(k) == v["$ne"]:
                        ok = False
                        break
                elif d.get(k) != v:
                    ok = False
                    break
            if ok:
                if "$set" in u:
                    d.update(u["$set"])
                n += 1
        return type("R", (), {"modified_count": n})()

    async def insert_one(self, doc):
        self.inserts.append(doc)
        self.docs.append(doc)


class _FakeDB:
    def __init__(self):
        self.learnings = _FakeColl()
        self.agent_ledger_entries = _FakeColl()
        self.agent_a2a_signals = _FakeColl()


# ─── Tests ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_no_db_safe():
    out = await cve.run_verdict_executor_tick(db=None)
    assert out["ok"] is False


@pytest.mark.asyncio
async def test_no_promoted_with_fix_returns_zero():
    db = _FakeDB()
    out = await cve.run_verdict_executor_tick(db)
    assert out["considered"] == 0
    assert out["applied"] == 0


@pytest.mark.asyncio
async def test_ping_agent_action_runs_and_marks_applied(monkeypatch):
    monkeypatch.setattr(cve, "COUNCIL_VERDICT_DRY_RUN", False)
    db = _FakeDB()
    db.learnings.docs.append({
        "learning_id": "L1",
        "subject": "scout_ora",
        "recommended_fix": {"action": "ping_agent",
                             "params": {"reason": "post_wedge"}},
    })
    out = await cve.run_verdict_executor_tick(db)
    assert out["considered"] == 1
    assert out["applied"] == 1
    # ledger heartbeat written for scout_ora
    pings = [d for d in db.agent_ledger_entries.inserts
             if d.get("agent_id") == "scout_ora" and d.get("kind") == "verdict_ping"]
    assert len(pings) == 1
    # Learning marked applied
    L = db.learnings.docs[0]
    assert L["applied"] is True
    assert L["applied_action"] == "ping_agent"
    assert L["applied_result"]["ok"] is True


@pytest.mark.asyncio
async def test_dry_run_does_not_write_ledger(monkeypatch):
    monkeypatch.setattr(cve, "COUNCIL_VERDICT_DRY_RUN", True)
    db = _FakeDB()
    db.learnings.docs.append({
        "learning_id": "L1",
        "subject": "scout_ora",
        "recommended_fix": {"action": "ping_agent", "params": {}},
    })
    out = await cve.run_verdict_executor_tick(db)
    assert out["dry_run"] is True
    assert out["applied"] == 1
    # No real ledger row written
    assert db.agent_ledger_entries.inserts == []
    L = db.learnings.docs[0]
    assert L["applied"] is True
    assert L["applied_result"].get("dry_run") is True


@pytest.mark.asyncio
async def test_unknown_action_rejected():
    db = _FakeDB()
    db.learnings.docs.append({
        "learning_id": "L1",
        "subject": "scout_ora",
        "recommended_fix": {"action": "rm_rf_/", "params": {}},
    })
    out = await cve.run_verdict_executor_tick(db)
    assert out["considered"] == 1
    assert out["applied"] == 0
    assert out["rejected"][0]["reason"].startswith("action_not_allowed:")
    # Learning is NOT marked applied — refused at the gate
    assert "applied" not in db.learnings.docs[0]


@pytest.mark.asyncio
async def test_already_applied_learning_skipped():
    db = _FakeDB()
    db.learnings.docs.append({
        "learning_id": "L1",
        "subject": "scout_ora",
        "applied": True,
        "recommended_fix": {"action": "ping_agent", "params": {}},
    })
    out = await cve.run_verdict_executor_tick(db)
    # find filter excludes applied=True rows
    assert out["considered"] == 0


@pytest.mark.asyncio
async def test_broadcast_a2a_kind_must_have_verdict_prefix(monkeypatch):
    monkeypatch.setattr(cve, "COUNCIL_VERDICT_DRY_RUN", False)
    db = _FakeDB()
    db.learnings.docs.append({
        "learning_id": "L1",
        "subject": "scout_ora",
        "recommended_fix": {
            "action": "broadcast_a2a",
            "params": {"kind": "wedge_recovered"},  # not verdict_*
        },
    })
    out = await cve.run_verdict_executor_tick(db)
    # action runs, but the handler returns ok=False because prefix wrong
    assert out["considered"] == 1
    L = db.learnings.docs[0]
    assert L["applied_result"]["ok"] is False
    # Marked applied (true) but with a non-ok result so it doesn't keep
    # being retried — the audit trail captures the failure.
    assert L["applied"] is True


@pytest.mark.asyncio
async def test_broadcast_a2a_writes_signal(monkeypatch):
    monkeypatch.setattr(cve, "COUNCIL_VERDICT_DRY_RUN", False)
    db = _FakeDB()
    db.learnings.docs.append({
        "learning_id": "L1",
        "subject": "scout_ora",
        "recommended_fix": {
            "action": "broadcast_a2a",
            "params": {"kind": "verdict_re_attest", "payload": {"reason": "wedge"}},
        },
    })
    out = await cve.run_verdict_executor_tick(db)
    assert out["applied"] == 1
    sigs = [s for s in db.agent_a2a_signals.inserts
            if s.get("kind") == "verdict_re_attest"]
    assert len(sigs) == 1
    assert sigs[0]["from"] == "council_verdict_executor"
    assert sigs[0]["to"] == "scout_ora"
