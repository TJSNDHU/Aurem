"""Phase 1 T1 Pipeline tests — Closer + Followup + Referral + bus wiring."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

import pytest

sys.path.insert(0, "/app/backend")

# Reset bus state for tests
from services import a2a_bus  # noqa: E402


# ─── Fake DB ─────────────────────────────────────────────────────────

class _FakeColl:
    def __init__(self):
        self.docs: List[Dict[str, Any]] = []

    async def insert_one(self, d):
        self.docs.append(dict(d))
        return type("R", (), {"inserted_id": len(self.docs)})()

    async def insert_many(self, docs):
        self.docs.extend([dict(d) for d in docs])
        return type("R", (), {"inserted_ids": list(range(len(docs)))})()

    async def find_one(self, q, proj=None):
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
            def __aiter__(self):
                self._iter = iter(self.items)
                return self

            async def __anext__(self):
                try:
                    return next(self._iter)
                except StopIteration:
                    raise StopAsyncIteration
        return _Cursor(results)

    async def update_one(self, q, upd, upsert=False):
        for d in self.docs:
            ok = all(d.get(k) == v for k, v in q.items() if not k.startswith("$"))
            if ok:
                if "$set" in upd:
                    d.update(upd["$set"])
                return type("R", (), {"modified_count": 1})()
        return type("R", (), {"modified_count": 0})()

    async def update_many(self, q, upd):
        n = 0
        for d in self.docs:
            ids = q.get("_id", {}).get("$in", [])
            if d.get("_id") in ids:
                if "$set" in upd:
                    d.update(upd["$set"])
                n += 1
        return type("R", (), {"modified_count": n})()


class _FakeDB:
    def __init__(self):
        self.campaign_leads = _FakeColl()
        self.scheduled_followups = _FakeColl()
        self.scheduled_referrals = _FakeColl()
        self.scheduled_calls = _FakeColl()
        self.auto_call_log = _FakeColl()
        self.agent_heartbeats = _FakeColl()
        self.agent_actions = _FakeColl()
        self.ora_brain_thoughts = _FakeColl()
        self.council_decisions_detailed = _FakeColl()
        self.learnings_pending_review = _FakeColl()
        self.do_not_contact = _FakeColl()
        self.blast_log = _FakeColl()
        self.security_events = _FakeColl()
        self.a2a_events = _FakeColl()
        self.a2a_error_log = _FakeColl()
        self.llm_costs = _FakeColl()


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    db = _FakeDB()
    fake_server = type(sys)("server")
    fake_server.db = db
    sys.modules["server"] = fake_server

    # Bus singleton — clear handlers between tests
    a2a_bus.bus._handlers.clear()
    a2a_bus.bus._tail.clear()
    a2a_bus.bus._db = db

    # Stub Retell call so Closer doesn't hit real API
    async def _fake_retell(to_number, lead_context):
        return {"ok": True, "call_id": f"call_{to_number[-4:]}"}

    fake_voice = type(sys)("routers.voice_agent_router")
    fake_voice._retell_create_phone_call = _fake_retell  # type: ignore
    sys.modules["routers.voice_agent_router"] = fake_voice

    # Stub twilio sms for Referral
    async def _fake_sms(to, body):
        return {"ok": True, "sid": f"sms_{to[-4:]}"}

    fake_twilio = type(sys)("services.twilio_service")
    fake_twilio.send_sms = _fake_sms  # type: ignore
    sys.modules["services.twilio_service"] = fake_twilio

    yield db


# ─────────────────────────────────────────────────────────────────────
# A2A bus handler subscription tests
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bus_subscribe_invokes_handler_on_emit(_stub):
    received = []

    async def handler(payload):
        received.append(payload)

    a2a_bus.bus.subscribe("TEST_EVENT", handler)
    await a2a_bus.bus.emit("test", "TEST_EVENT", {"x": 1})
    # emit fires handlers as create_task → wait
    await asyncio.sleep(0.05)
    assert len(received) == 1
    assert received[0]["x"] == 1


@pytest.mark.asyncio
async def test_bus_handler_exception_does_not_block(_stub):
    received = []

    async def crashing(payload):
        raise RuntimeError("boom")

    async def healthy(payload):
        received.append(payload)

    a2a_bus.bus.subscribe("X", crashing)
    a2a_bus.bus.subscribe("X", healthy)
    await a2a_bus.bus.emit("test", "X", {"y": 2})
    await asyncio.sleep(0.05)
    # healthy handler still fired despite crashing one
    assert len(received) == 1
    # error logged
    assert len(_stub.a2a_error_log.docs) == 1


# ─────────────────────────────────────────────────────────────────────
# Closer ORA tests
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_closer_arms_call_for_hot_reply(_stub, monkeypatch):
    # Make sure council approves
    from services import council_deliberate

    async def _approve_all(action, agent, payload, **kw):
        return {"verdict": "APPROVED", "votes": {}, "confidence": 1.0}

    monkeypatch.setattr(council_deliberate, "deliberate", _approve_all)

    # Force time-window check to TRUE
    from services.agents import closer_ora as closer
    monkeypatch.setattr(closer, "_within_calling_window", lambda tz: True)

    # Seed lead
    await _stub.campaign_leads.insert_one({
        "lead_id": "L_HOT_1",
        "phone": "+14165550001",
        "business_name": "Test Auto",
        "owner_first_name": "Mike",
        "timezone": "America/Toronto",
    })

    res = await closer.arm({"lead_id": "L_HOT_1", "trigger": "hot_reply"})
    assert res["ok"] is True
    assert res["call_id"] == "call_0001"
    # Persisted
    log = await _stub.auto_call_log.find_one({"lead_id": "L_HOT_1"})
    assert log is not None
    assert log["trigger"] == "hot_reply"


@pytest.mark.asyncio
async def test_closer_idempotent_skips_second_call(_stub, monkeypatch):
    from services import council_deliberate
    monkeypatch.setattr(council_deliberate, "deliberate",
                        lambda *a, **k: asyncio.sleep(0, {"verdict": "APPROVED"}))

    from services.agents import closer_ora as closer
    monkeypatch.setattr(closer, "_within_calling_window", lambda tz: True)

    # Pre-seed the call log + lead
    await _stub.campaign_leads.insert_one({
        "lead_id": "L1", "phone": "+14165550002",
    })
    await _stub.auto_call_log.insert_one({
        "lead_id": "L1", "trigger": "hot_reply",
    })

    res = await closer.arm({"lead_id": "L1", "trigger": "hot_reply"})
    assert res["ok"] is True
    assert res.get("skipped") == "idempotency"


@pytest.mark.asyncio
async def test_closer_queues_when_outside_window(_stub, monkeypatch):
    from services import council_deliberate

    async def _approve(action, agent, payload, **kw):
        return {"verdict": "APPROVED", "votes": {}, "confidence": 1.0}

    monkeypatch.setattr(council_deliberate, "deliberate", _approve)

    from services.agents import closer_ora as closer
    monkeypatch.setattr(closer, "_within_calling_window", lambda tz: False)

    await _stub.campaign_leads.insert_one({
        "lead_id": "L_OOH",
        "phone": "+14165550003",
        "timezone": "America/Toronto",
    })
    res = await closer.arm({"lead_id": "L_OOH", "trigger": "no_reply_day5"})
    assert res["ok"] is True
    assert res["queued"] is True
    # scheduled_calls row exists
    sched = await _stub.scheduled_calls.find_one({"lead_id": "L_OOH"})
    assert sched is not None


@pytest.mark.asyncio
async def test_closer_skips_when_no_phone(_stub, monkeypatch):
    from services.agents import closer_ora as closer
    await _stub.campaign_leads.insert_one({"lead_id": "NO_PH"})
    res = await closer.arm({"lead_id": "NO_PH", "trigger": "hot_reply"})
    assert res["ok"] is False
    assert "no phone" in res["error"]


@pytest.mark.asyncio
async def test_closer_subscribes_to_hot_reply_and_no_reply_day5(_stub):
    from services.agents import closer_ora
    closer_ora.register_subscriptions()
    handlers_hot = a2a_bus.bus._handlers.get("HOT_REPLY", [])
    handlers_d5 = a2a_bus.bus._handlers.get("NO_REPLY_DAY5", [])
    assert closer_ora.arm in handlers_hot
    assert closer_ora.arm in handlers_d5


# ─────────────────────────────────────────────────────────────────────
# Followup ORA tests
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_followup_arms_three_days_in_one_insert(_stub):
    from services.agents import followup_ora
    res = await followup_ora.arm({"lead_id": "F1"})
    assert res["ok"] is True
    assert res["armed_days"] == [2, 5, 9]
    rows = _stub.scheduled_followups.docs
    assert len(rows) == 3
    days = sorted(r["scheduled_day"] for r in rows)
    assert days == [2, 5, 9]


@pytest.mark.asyncio
async def test_followup_tick_emits_no_reply_day_for_cold_leads(_stub):
    from services.agents import followup_ora
    received = []

    async def handler(payload):
        received.append(payload)

    a2a_bus.bus.subscribe("NO_REPLY_DAY2", handler)
    a2a_bus.bus.subscribe("NO_REPLY_DAY5", handler)

    # Seed: 2 followups due NOW for 2 different leads
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    await _stub.scheduled_followups.insert_one({
        "_id": "fu1", "lead_id": "COLD1", "scheduled_day": 2,
        "scheduled_for": past, "status": "pending",
    })
    await _stub.scheduled_followups.insert_one({
        "_id": "fu2", "lead_id": "HOT1", "scheduled_day": 5,
        "scheduled_for": past, "status": "pending",
    })

    # Lead 1 = cold (no engagement); Lead 2 = hot (skip)
    await _stub.campaign_leads.insert_one({
        "lead_id": "COLD1", "hot_lead_flag": False, "dnc": False,
    })
    await _stub.campaign_leads.insert_one({
        "lead_id": "HOT1", "hot_lead_flag": True,
    })

    res = await followup_ora.tick()
    await asyncio.sleep(0.05)
    assert res["ok"] is True
    assert res["checked"] == 2
    assert res["emitted"] == 1  # only COLD1 emitted; HOT1 skipped


@pytest.mark.asyncio
async def test_followup_subscribes_to_blast_sent(_stub):
    from services.agents import followup_ora
    followup_ora.register_subscriptions()
    handlers = a2a_bus.bus._handlers.get("BLAST_SENT", [])
    assert followup_ora.arm in handlers


# ─────────────────────────────────────────────────────────────────────
# Referral ORA tests
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_referral_arms_day_7_on_subscription(_stub):
    from services.agents import referral_ora
    res = await referral_ora.arm({
        "customer_id": "cus_abc",
        "email": "owner@example.com",
        "phone": "+14165550010",
        "business_name": "ACME HVAC Inc",
    })
    assert res["ok"] is True
    row = await _stub.scheduled_referrals.find_one({"customer_id": "cus_abc"})
    assert row is not None
    delta = (row["scheduled_for"] - datetime.now(timezone.utc))
    assert 6 <= delta.days <= 8  # ~7 days (timing-tolerant)


@pytest.mark.asyncio
async def test_referral_idempotent(_stub):
    from services.agents import referral_ora
    await referral_ora.arm({"customer_id": "cus_xyz", "phone": "+14165550011"})
    res2 = await referral_ora.arm({"customer_id": "cus_xyz", "phone": "+14165550011"})
    assert res2["ok"] is True
    assert res2.get("already_scheduled") is True
    # Still only one row
    assert len(_stub.scheduled_referrals.docs) == 1


@pytest.mark.asyncio
async def test_referral_subscribes_to_subscription_created(_stub):
    from services.agents import referral_ora
    referral_ora.register_subscriptions()
    handlers = a2a_bus.bus._handlers.get("SUBSCRIPTION_CREATED", [])
    assert referral_ora.arm in handlers
