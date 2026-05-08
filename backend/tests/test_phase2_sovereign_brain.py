"""Phase 2 tests — Sovereign + ORA Brain Observer + Council backlog."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

import pytest

sys.path.insert(0, "/app/backend")

from services import a2a_bus  # noqa: E402


class _FakeColl:
    def __init__(self):
        self.docs: List[Dict[str, Any]] = []

    async def insert_one(self, d):
        self.docs.append(dict(d))
        return type("R", (), {"inserted_id": len(self.docs)})()

    async def insert_many(self, docs):
        self.docs.extend([dict(d) for d in docs])
        return type("R", (), {"inserted_ids": list(range(len(docs)))})()

    async def find_one(self, q, proj=None, sort=None):
        rows = list(self.docs)
        if sort:
            for k, d in reversed(sort):
                rows.sort(key=lambda x: x.get(k) or datetime.min,
                          reverse=(d == -1))
        for d in rows:
            ok = True
            for k, v in q.items():
                if k.startswith("$") or isinstance(v, dict):
                    continue
                if d.get(k) != v:
                    ok = False
                    break
            if ok:
                return dict(d)
        return None

    def find(self, q, proj=None):
        results = []
        for d in self.docs:
            ok = True
            for k, v in q.items():
                if k.startswith("$"):
                    continue
                if isinstance(v, dict):
                    if "$lte" in v and d.get(k) is not None:
                        if d[k] > v["$lte"]:
                            ok = False
                            break
                    if "$gte" in v and d.get(k) is not None:
                        if d[k] < v["$gte"]:
                            ok = False
                            break
                    if "$in" in v and d.get(k) not in v["$in"]:
                        ok = False
                        break
                    continue
                if d.get(k) != v:
                    ok = False
                    break
            if ok:
                results.append(dict(d))

        class _Cursor:
            def __init__(self, items): self.items = items
            def limit(self, n): return _Cursor(self.items[:n])
            async def to_list(self, n): return self.items[:n]
        return _Cursor(results)

    async def update_one(self, q, upd, upsert=False):
        for d in self.docs:
            ok = True
            for k, v in q.items():
                if k.startswith("$"):
                    continue
                if isinstance(v, dict):
                    continue
                if d.get(k) != v:
                    ok = False
                    break
            if ok:
                if "$set" in upd:
                    d.update(upd["$set"])
                if "$inc" in upd:
                    for k, v in upd["$inc"].items():
                        d[k] = (d.get(k) or 0) + v
                if "$push" in upd:
                    for k, v in upd["$push"].items():
                        d.setdefault(k, []).append(v)
                if "$setOnInsert" in upd and not d.get("_inserted"):
                    pass  # only on insert
                return type("R", (), {"modified_count": 1})()
        if upsert:
            new = {**{k: v for k, v in q.items() if not k.startswith("$")}}
            if "$set" in upd:
                new.update(upd["$set"])
            if "$inc" in upd:
                for k, v in upd["$inc"].items():
                    new[k] = v
            if "$setOnInsert" in upd:
                new.update(upd["$setOnInsert"])
            if "$push" in upd:
                for k, v in upd["$push"].items():
                    new[k] = [v]
            self.docs.append(new)
            return type("R", (), {"modified_count": 0, "upserted_id": "u"})()
        return type("R", (), {"modified_count": 0})()

    async def update_many(self, q, upd):
        n = 0
        ids = q.get("id", {}).get("$in", []) if isinstance(q.get("id"), dict) else []
        for d in self.docs:
            if ids and d.get("id") in ids:
                if "$set" in upd:
                    d.update(upd["$set"])
                if "$push" in upd:
                    for k, v in upd["$push"].items():
                        d.setdefault(k, []).append(v)
                n += 1
        return type("R", (), {"modified_count": n})()

    async def count_documents(self, q):
        n = 0
        for d in self.docs:
            ok = True
            for k, v in q.items():
                if k.startswith("$"):
                    continue
                if isinstance(v, dict):
                    if "$gte" in v and (d.get(k) is None or d[k] < v["$gte"]):
                        ok = False; break
                    if "$lte" in v and (d.get(k) is None or d[k] > v["$lte"]):
                        ok = False; break
                    continue
                if d.get(k) != v:
                    ok = False; break
            if ok:
                n += 1
        return n


class _FakeDB:
    def __init__(self):
        self.learnings_pending_review = _FakeColl()
        self.learnings = _FakeColl()
        self.ora_brain_thoughts = _FakeColl()
        self.ora_knowledge = _FakeColl()
        self.ora_hot_log = _FakeColl()
        self.ora_wedge_log = _FakeColl()
        self.ora_health_alerts = _FakeColl()
        self.ora_deploy_log = _FakeColl()
        self.council_decisions_detailed = _FakeColl()
        self.agent_heartbeats = _FakeColl()
        self.agent_actions = _FakeColl()
        self.a2a_events = _FakeColl()
        self.a2a_error_log = _FakeColl()

    def __getitem__(self, name):
        # sovereign_memory uses db[COLLECTION_NAME] subscript style
        return getattr(self, name)


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    db = _FakeDB()
    fake_server = type(sys)("server")
    fake_server.db = db
    sys.modules["server"] = fake_server
    a2a_bus.bus._handlers.clear()
    a2a_bus.bus._tail.clear()
    a2a_bus.bus._db = db

    # Stub twilio so SMS doesn't hit the wire
    sent = {"sms": []}
    async def _fake_sms(to, body):
        sent["sms"].append({"to": to, "body": body})
    fake_tw = type(sys)("services.twilio_service")
    fake_tw.send_sms = _fake_sms  # type: ignore
    sys.modules["services.twilio_service"] = fake_tw
    yield db, sent


# ─── ORA Brain Observer tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_observer_subscribes_to_all_events(_stub):
    from services import ora_brain_observer
    ora_brain_observer.register_subscriptions()
    for ev in ora_brain_observer.OBSERVED_EVENTS:
        assert ev in a2a_bus.bus._handlers
        assert len(a2a_bus.bus._handlers[ev]) >= 1


@pytest.mark.asyncio
async def test_observer_persists_thought_for_each_event(_stub):
    db, _ = _stub
    from services import ora_brain_observer
    ora_brain_observer.register_subscriptions()
    await a2a_bus.bus.emit("envoy", "BLAST_SENT",
                           {"lead_id": "L1", "chain_id": "chain_a"})
    await asyncio.sleep(0.05)
    assert len(db.ora_brain_thoughts.docs) == 1
    t = db.ora_brain_thoughts.docs[0]
    assert t["event"] == "BLAST_SENT"
    assert t["payload"]["lead_id"] == "L1"


@pytest.mark.asyncio
async def test_observer_pauses_agent_after_5_rejections(_stub):
    db, sent = _stub
    from services import ora_brain_observer
    # Seed 5 rejections in last 24h for "envoy"
    now = datetime.now(timezone.utc)
    for i in range(5):
        await db.council_decisions_detailed.insert_one({
            "requesting_agent": "envoy",
            "verdict": "REJECTED",
            "ts": now - timedelta(hours=1),
        })
    ora_brain_observer.register_subscriptions()
    await a2a_bus.bus.emit("council", "COUNCIL_REJECTED",
                           {"agent": "envoy", "voter": "casl",
                            "reason": "DNC"})
    await asyncio.sleep(0.05)
    # Heartbeat row marked paused
    hb = await db.agent_heartbeats.find_one({"agent": "envoy"})
    assert hb is not None
    assert hb["status"] == "paused"
    assert hb["paused_reason"] == "high_rejection"
    # SMS dispatched
    assert len(sent["sms"]) == 1
    assert "envoy" in sent["sms"][0]["body"]


@pytest.mark.asyncio
async def test_observer_does_not_pause_below_threshold(_stub):
    db, sent = _stub
    from services import ora_brain_observer
    # Only 3 rejections — below threshold (5)
    now = datetime.now(timezone.utc)
    for i in range(3):
        await db.council_decisions_detailed.insert_one({
            "requesting_agent": "scout",
            "verdict": "REJECTED",
            "ts": now - timedelta(hours=1),
        })
    ora_brain_observer.register_subscriptions()
    await a2a_bus.bus.emit("council", "COUNCIL_REJECTED",
                           {"agent": "scout", "voter": "qa", "reason": "x"})
    await asyncio.sleep(0.05)
    hb = await db.agent_heartbeats.find_one({"agent": "scout"})
    assert hb is None  # not paused
    assert len(sent["sms"]) == 0


@pytest.mark.asyncio
async def test_observer_apply_learning_upserts_ora_knowledge(_stub):
    db, _ = _stub
    from services import ora_brain_observer
    ora_brain_observer.register_subscriptions()
    await a2a_bus.bus.emit("learning_bus", "LEARNING_PROMOTED", {
        "pattern": "hvac_yelp_score9_tuesday_email_converted",
        "kind": "lead_pattern",
        "confidence": 0.92,
    })
    await asyncio.sleep(0.05)
    row = await db.ora_knowledge.find_one(
        {"pattern": "hvac_yelp_score9_tuesday_email_converted"})
    assert row is not None
    assert row["confidence"] == 0.92
    assert row["active"] is True


@pytest.mark.asyncio
async def test_observer_log_code_fix(_stub):
    db, _ = _stub
    from services import ora_brain_observer
    ora_brain_observer.register_subscriptions()
    await a2a_bus.bus.emit("emergent", "CODE_FIX_APPLIED", {
        "fix_description": "Auth flow CORS fix",
        "error_type": "CORS_ERROR",
        "files_changed": ["server.py"],
    })
    await asyncio.sleep(0.05)
    rows = [d for d in db.ora_knowledge.docs if d.get("kind") == "code_fix"]
    assert len(rows) == 1
    assert rows[0]["confidence"] == 1.0
    assert rows[0]["source"] == "emergent"


@pytest.mark.asyncio
async def test_observer_health_fail_alerts_once_per_hour(_stub):
    db, sent = _stub
    from services import ora_brain_observer
    ora_brain_observer.register_subscriptions()
    # First failure → alert
    await a2a_bus.bus.emit("deploy", "HEALTH_FAILED", {"error": "503 timeout"})
    await asyncio.sleep(0.05)
    # Second failure right after → suppressed
    await a2a_bus.bus.emit("deploy", "HEALTH_FAILED", {"error": "503 timeout"})
    await asyncio.sleep(0.05)
    # Both logged but only 1 SMS
    assert len(db.ora_health_alerts.docs) == 2
    assert len(sent["sms"]) == 1


# ─── Sovereign learning emit test ────────────────────────────────────

@pytest.mark.asyncio
async def test_promote_emits_learning_promoted(_stub):
    db, _ = _stub
    from services import sovereign_memory
    received = []

    async def handler(payload):
        received.append(payload)

    a2a_bus.bus.subscribe("LEARNING_PROMOTED", handler)
    # Seed a pending learning with 2 distinct-role approve stamps
    await db.learnings_pending_review.insert_one({
        "id": "test_learning_1",
        "kind": "scout_pattern",
        "subject": "hvac_yelp",
        "status": "pending",
        "stamps": [
            {"role": "council_admin", "vote": "approve",
             "ts": "2026-05-06T00:00:00+00:00"},
            {"role": "auto_promoter", "vote": "approve",
             "ts": "2026-05-06T00:00:01+00:00"},
        ],
        "confidence": 0.85,
        "submitted_by": "test",
        "payload": {},
    })
    result = await sovereign_memory.promote_if_ready(db, "test_learning_1")
    await asyncio.sleep(0.05)
    assert result is not None
    # LEARNING_PROMOTED was emitted
    assert len(received) == 1
    assert received[0]["pattern"].startswith("scout_pattern_")
    assert received[0]["id"] == "test_learning_1"
    # Live row exists
    live = await db.learnings.find_one({"id": "test_learning_1"})
    assert live is not None
