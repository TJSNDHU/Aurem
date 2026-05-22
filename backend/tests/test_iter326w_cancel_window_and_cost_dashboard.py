"""
test_iter326w_cancel_window_and_cost_dashboard.py — iter 326w regression.
══════════════════════════════════════════════════════════════════════════════
Founder asks (Phase 1 close-out):
  1. "30-second cancel window lo" — Tier 2 actions should auto-execute
     after 30 s unless founder cancels. Tier 3 stays manual.
  2. "Daily spend dashboard — haan, banao" — show last 7 days of ORA
     chat cost so an overnight loop is caught before it burns $50.

WHAT THIS TEST LOCKS IN
───────────────────────
  • TIER2_AUTO_EXECUTE_SECONDS == 30
  • _persist_pending writes auto_execute_at for tier2, None for tier3
  • auto_execute_due_tier2 atomically claims overdue tier2 rows
  • auto_execute_due_tier2 never touches tier3 rows
  • _track_session_cost persists a row to db.ora_llm_costs when cost > 0
  • Cost rows carry session_id, provider, cost_usd, ts, day fields

Run:  cd /app/backend && python3 -m pytest \
        tests/test_iter326w_cancel_window_and_cost_dashboard.py -v
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# 1) Constants + persistence surface
# ─────────────────────────────────────────────────────────────────────────────
def test_tier2_window_constant_is_30s():
    from services.ora_agent import TIER2_AUTO_EXECUTE_SECONDS
    assert TIER2_AUTO_EXECUTE_SECONDS == 30


def test_auto_execute_due_tier2_is_exported():
    from services import ora_agent
    assert hasattr(ora_agent, "auto_execute_due_tier2")
    assert callable(ora_agent.auto_execute_due_tier2)


# ─────────────────────────────────────────────────────────────────────────────
# 2) _persist_pending writes auto_execute_at for tier2, None for tier3
# ─────────────────────────────────────────────────────────────────────────────
class _FakeColl:
    def __init__(self):
        self.docs: dict = {}

    async def insert_one(self, doc):
        key = doc.get("_id") or f"auto-{len(self.docs)}"
        self.docs[key] = doc
        return type("R", (), {"inserted_id": key})

    async def find_one_and_update(self, filt, update, **_kw):
        # Return the first matching doc, apply update, simulate "return_document=AFTER"
        for k, d in list(self.docs.items()):
            ok = True
            for fk, fv in filt.items():
                if isinstance(fv, dict):
                    # Handle $lte / $ne minimally
                    if "$lte" in fv and not (d.get(fk) and d[fk] <= fv["$lte"]):
                        ok = False; break
                    if "$ne" in fv and d.get(fk) == fv["$ne"]:
                        ok = False; break
                else:
                    if d.get(fk) != fv:
                        ok = False; break
            if ok:
                for sk, sv in (update.get("$set") or {}).items():
                    d[sk] = sv
                return d
        return None

    async def update_one(self, filt, update):
        for d in self.docs.values():
            if all(d.get(k) == v for k, v in filt.items()):
                for sk, sv in (update.get("$set") or {}).items():
                    d[sk] = sv
                return type("R", (), {"modified_count": 1})
        return type("R", (), {"modified_count": 0})


class _FakeDB:
    def __init__(self):
        self.ora_pending_actions = _FakeColl()
        self.ora_llm_costs       = _FakeColl()

    def __getitem__(self, name):
        return getattr(self, name)


@pytest.mark.asyncio
async def test_persist_pending_tier2_sets_auto_execute_at(monkeypatch):
    from services import ora_agent
    fake = _FakeDB()
    monkeypatch.setattr(ora_agent, "_db", fake)
    await ora_agent._persist_pending(
        action_id="t2-a",
        session_id="s1",
        tool="safe_edit",
        args={},
        tier="tier2_approve",
        founder_email="x@y.com",
        summary="edit a file",
    )
    doc = fake.ora_pending_actions.docs["t2-a"]
    assert doc["tier"] == "tier2_approve"
    assert doc["auto_execute_at"] is not None
    # 30 ± 2 s in the future
    gap = (doc["auto_execute_at"] - datetime.now(timezone.utc)).total_seconds()
    assert 25 < gap < 35, f"auto_execute_at not ~30s ahead: gap={gap}"


@pytest.mark.asyncio
async def test_persist_pending_tier3_does_NOT_set_auto_execute_at(monkeypatch):
    from services import ora_agent
    fake = _FakeDB()
    monkeypatch.setattr(ora_agent, "_db", fake)
    await ora_agent._persist_pending(
        action_id="t3-a",
        session_id="s1",
        tool="legion_exec",
        args={"cmd": "rm -rf"},
        tier="tier3_high_risk",
        founder_email="x@y.com",
        summary="dangerous",
    )
    doc = fake.ora_pending_actions.docs["t3-a"]
    assert doc["tier"] == "tier3_high_risk"
    assert doc["auto_execute_at"] is None, "tier3 must NEVER auto-execute"


# ─────────────────────────────────────────────────────────────────────────────
# 3) auto_execute_due_tier2 only claims tier2 rows whose window elapsed
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_auto_executor_skips_tier3_and_future_tier2(monkeypatch):
    from services import ora_agent
    fake = _FakeDB()
    monkeypatch.setattr(ora_agent, "_db", fake)
    # Stub resume_after_decision so we can count invocations
    invoked: list = []
    async def _fake_resume(session_id, *, action_id, approved, note, founder_email):
        invoked.append(action_id)
        return {"ok": True}
    monkeypatch.setattr(ora_agent, "resume_after_decision", _fake_resume)

    past = datetime.now(timezone.utc) - timedelta(seconds=60)
    future = datetime.now(timezone.utc) + timedelta(seconds=60)
    # Overdue tier2 — must execute
    fake.ora_pending_actions.docs["due-t2"] = {
        "_id": "due-t2", "session_id": "s1", "tier": "tier2_approve",
        "status": "pending", "auto_execute_at": past, "founder_email": "f@a.com",
    }
    # Tier3 with past auto_execute_at — must STILL not execute
    fake.ora_pending_actions.docs["t3"] = {
        "_id": "t3", "session_id": "s1", "tier": "tier3_high_risk",
        "status": "pending", "auto_execute_at": past, "founder_email": "f@a.com",
    }
    # Tier2 not yet due — must not execute
    fake.ora_pending_actions.docs["future-t2"] = {
        "_id": "future-t2", "session_id": "s1", "tier": "tier2_approve",
        "status": "pending", "auto_execute_at": future, "founder_email": "f@a.com",
    }
    # Tier2 with None auto_execute_at — must not execute
    fake.ora_pending_actions.docs["null-t2"] = {
        "_id": "null-t2", "session_id": "s1", "tier": "tier2_approve",
        "status": "pending", "auto_execute_at": None, "founder_email": "f@a.com",
    }

    result = await ora_agent.auto_execute_due_tier2()
    assert result["executed"] == 1
    assert invoked == ["due-t2"]


# ─────────────────────────────────────────────────────────────────────────────
# 4) Cost row is persisted on tracked spend
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_track_session_cost_writes_to_ora_llm_costs(monkeypatch):
    from services import ora_agent
    # Fresh session bucket
    sid = "spend-test"
    ora_agent._SESSION_COST_USD.pop(sid, None)
    fake = _FakeDB()
    monkeypatch.setattr(ora_agent, "_db", fake)
    ora_agent._track_session_cost(sid, "claude", 0.0125)
    # _track_session_cost schedules an asyncio task — give it a tick
    await asyncio.sleep(0.05)
    rows = list(fake.ora_llm_costs.docs.values())
    assert len(rows) == 1
    r = rows[0]
    assert r["session_id"] == sid
    assert r["provider"]   == "claude"
    assert abs(r["cost_usd"] - 0.0125) < 1e-6
    assert "ts" in r and "day" in r
    # day is YYYY-MM-DD
    assert len(r["day"]) == 10 and r["day"].count("-") == 2


@pytest.mark.asyncio
async def test_zero_cost_does_not_write_row(monkeypatch):
    """Free-provider calls (NVIDIA, Ollama) cost $0 — no need to flood
    the cost collection with zero rows."""
    from services import ora_agent
    sid = "zero-test"
    ora_agent._SESSION_COST_USD.pop(sid, None)
    fake = _FakeDB()
    monkeypatch.setattr(ora_agent, "_db", fake)
    ora_agent._track_session_cost(sid, "nvidia", 0.0)
    await asyncio.sleep(0.05)
    assert fake.ora_llm_costs.docs == {}
