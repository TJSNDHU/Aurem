"""Tests for FollowUp ORA engine (iter 322p)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest

from services import followup_ora_engine as foe


def _iso_ago(days: float = 0, hours: float = 0) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(days=days, hours=hours)
    ).isoformat()


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
                    if "$lt" in v and not (str(d.get(k, "")) < v["$lt"]):
                        ok = False
                        break
                    if "$nin" in v and d.get(k) in v["$nin"]:
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
                # apply $push
                if "$push" in u:
                    for k, v in u["$push"].items():
                        d.setdefault(k, []).append(v)
                if "$set" in u:
                    d.update(u["$set"])
                self.updates.append({"q": q, "u": u})
                return type("R", (), {"matched_count": 1})()
        self.updates.append({"q": q, "u": u})
        return type("R", (), {"matched_count": 0})()

    async def insert_one(self, doc):
        self.inserts.append(doc)
        self.docs.append(doc)


class _FakeDB:
    def __init__(self):
        self.campaign_leads = _FakeColl()
        self.agent_ledger_entries = _FakeColl()


# ─── Tests ─────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_no_db_safe():
    out = await foe.run_followup_tick(db=None)
    assert out["ok"] is False
    assert out["reason"] == "no_db"


@pytest.mark.asyncio
async def test_silent_lead_gets_followup_attempt():
    db = _FakeDB()
    db.campaign_leads.docs.append({
        "lead_id": "lead-1",
        "business_name": "Foo HVAC",
        "status": "outreach_sent",
        "updated_at": _iso_ago(days=5),
        "outreach_history": [
            {"type": "envoy_send", "ts": _iso_ago(days=5)},
        ],
    })
    out = await foe.run_followup_tick(db)
    assert out["ok"] is True
    assert out["leads_scanned"] == 1
    assert out["attempts"] == 1
    # Lead history should now include a `followup_attempt` row
    lead = db.campaign_leads.docs[0]
    types = [h.get("type") for h in lead.get("outreach_history", [])]
    assert "followup_attempt" in types
    # Ledger heartbeat must be recorded so wedge-detector sees agent alive
    pings = [d for d in db.agent_ledger_entries.inserts
             if d.get("agent_id") == "followup_ora"]
    assert len(pings) == 1


@pytest.mark.asyncio
async def test_terminal_status_skipped():
    db = _FakeDB()
    db.campaign_leads.docs.append({
        "lead_id": "lead-1",
        "status": "responded",
        "updated_at": _iso_ago(days=5),
        "outreach_history": [{"type": "envoy_send", "ts": _iso_ago(days=5)}],
    })
    out = await foe.run_followup_tick(db)
    # Terminal-status leads must not be picked up by the find query
    assert out["leads_scanned"] == 0
    assert out["attempts"] == 0


@pytest.mark.asyncio
async def test_recent_followup_in_cooldown():
    db = _FakeDB()
    db.campaign_leads.docs.append({
        "lead_id": "lead-1",
        "status": "outreach_sent",
        "updated_at": _iso_ago(days=5),
        "outreach_history": [
            {"type": "envoy_send", "ts": _iso_ago(days=5)},
            {"type": "followup_attempt", "ts": _iso_ago(hours=2)},  # 2h ago
        ],
    })
    out = await foe.run_followup_tick(db)
    assert out["leads_scanned"] == 1
    assert out["attempts"] == 0
    assert out["skipped_in_cooldown"] == 1


@pytest.mark.asyncio
async def test_dry_run_default_no_live_send():
    """By default `FOLLOWUP_LIVE_SENDING` is False — channel == intent_only."""
    db = _FakeDB()
    db.campaign_leads.docs.append({
        "lead_id": "lead-1",
        "status": "outreach_sent",
        "updated_at": _iso_ago(days=5),
        "outreach_history": [{"type": "envoy_send", "ts": _iso_ago(days=5)}],
    })
    await foe.run_followup_tick(db)
    lead = db.campaign_leads.docs[0]
    last = lead["outreach_history"][-1]
    assert last["type"] == "followup_attempt"
    assert last["channel"] == "intent_only"
