"""Phase 0 foundation tests — agent_registry + council_deliberate."""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

sys.path.insert(0, "/app/backend")

from services import agent_registry  # noqa: E402
from services import council_deliberate  # noqa: E402


# ─── Fake DB for tests ───────────────────────────────────────────────

class _FakeColl:
    def __init__(self):
        self.docs: List[Dict[str, Any]] = []
        self.bulk_calls: List[List[Any]] = []

    async def insert_one(self, d):
        self.docs.append(dict(d))
        return type("R", (), {"inserted_id": 1})()

    async def insert_many(self, docs):
        self.docs.extend([dict(d) for d in docs])
        return type("R", (), {"inserted_ids": list(range(len(docs)))})()

    async def bulk_write(self, ops, ordered=True):
        self.bulk_calls.append(list(ops))
        return type("R", (), {"modified_count": len(ops)})()

    async def find_one(self, q, proj=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items()
                   if not k.startswith("$")):
                return dict(d)
        return None

    async def count_documents(self, q):
        return 0


class _FakeDB:
    def __init__(self):
        self.agent_heartbeats = _FakeColl()
        self.agent_actions = _FakeColl()
        self.ora_brain_thoughts = _FakeColl()
        self.council_decisions_detailed = _FakeColl()
        self.learnings_pending_review = _FakeColl()
        self.do_not_contact = _FakeColl()
        self.blast_log = _FakeColl()
        self.security_events = _FakeColl()
        self.llm_costs = _FakeColl()


@pytest.fixture(autouse=True)
def _stub_db(monkeypatch):
    db = _FakeDB()
    # Stub server.db for both modules
    fake_server = type(sys)("server")
    fake_server.db = db
    sys.modules["server"] = fake_server
    # Reset registry buffers
    agent_registry._hb_buffer.clear()
    agent_registry._action_buffer.clear()
    yield db


# ─── agent_registry tests ────────────────────────────────────────────

def test_agent_registry_has_20_agents():
    assert len(agent_registry.AGENT_REGISTRY) == 20


@pytest.mark.asyncio
async def test_heartbeat_buffers_then_bulk_writes(_stub_db):
    await agent_registry.heartbeat("scout")
    await agent_registry.heartbeat("hunter")
    await agent_registry.heartbeat("envoy")
    assert len(agent_registry._hb_buffer) == 3

    flushed = await agent_registry.flush_heartbeats()
    assert flushed == 3
    assert len(agent_registry._hb_buffer) == 0
    # Confirm bulk_write was used (not 3 separate updates)
    assert len(_stub_db.agent_heartbeats.bulk_calls) == 1
    assert len(_stub_db.agent_heartbeats.bulk_calls[0]) == 3


@pytest.mark.asyncio
async def test_log_action_buffers_below_threshold(_stub_db):
    for i in range(5):
        await agent_registry.log_action(
            "scout", "TICK", f"r{i}", success=True,
        )
    assert len(agent_registry._action_buffer) == 5
    # Below threshold → no flush yet
    assert len(_stub_db.agent_actions.docs) == 0


@pytest.mark.asyncio
async def test_log_action_auto_flushes_at_threshold(_stub_db):
    for i in range(20):
        await agent_registry.log_action("scout", "TICK", f"r{i}")
    # Threshold = 20 → auto-flush triggered
    await asyncio.sleep(0)
    # Buffer cleared, batch written
    assert len(agent_registry._action_buffer) == 0
    # insert_many called once with 20 docs
    assert len(_stub_db.agent_actions.docs) == 20
    # Mirror to ora_brain_thoughts
    assert len(_stub_db.ora_brain_thoughts.docs) == 20


@pytest.mark.asyncio
async def test_flush_actions_idempotent_when_empty(_stub_db):
    flushed = await agent_registry.flush_actions()
    assert flushed == 0


# ─── council_deliberate tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_deliberate_approves_clean_payload(_stub_db):
    """Lead with valid +1 phone, no DNC, no prior contacts → APPROVED."""
    payload = {
        "phone_e164": "+14165551234",
        "email": "test@example.com",
        "blast_email_subject": "Quick question about your auto shop",
        "score": 7,
    }
    result = await council_deliberate.deliberate(
        "outreach_blast", "envoy", payload,
        required=["casl", "qa"],
        advisory=["security", "pricing"],
    )
    assert result["verdict"] == "APPROVED"
    assert "casl" in result["votes"]
    assert "qa" in result["votes"]
    assert "pricing" in result["votes"]  # advisory ran
    assert result["confidence"] >= 0.75


@pytest.mark.asyncio
async def test_deliberate_rejects_non_canadian_phone(_stub_db):
    payload = {
        "phone_e164": "+447777000000",  # UK number
        "email": "x@y.z",
        "blast_email_subject": "Hi",
    }
    result = await council_deliberate.deliberate(
        "outreach_blast", "envoy", payload,
        required=["casl"], advisory=[],
    )
    assert result["verdict"] == "REJECTED"
    assert result["votes"]["casl"]["vote"] == "REJECT"
    assert "Canadian" in result["votes"]["casl"]["reason"]


@pytest.mark.asyncio
async def test_deliberate_rejects_spam_subject(_stub_db):
    payload = {
        "phone_e164": "+14165551234",
        "email": "x@y.z",
        "blast_email_subject": "FREE OFFER — CLICK NOW!",
    }
    result = await council_deliberate.deliberate(
        "outreach_blast", "envoy", payload,
        required=["casl", "qa"], advisory=[],
    )
    assert result["verdict"] == "REJECTED"
    assert result["votes"]["qa"]["vote"] == "REJECT"


@pytest.mark.asyncio
async def test_deliberate_rejects_dnc(_stub_db):
    # Pre-seed DNC
    await _stub_db.do_not_contact.insert_one({
        "phone": "+14165550000", "ts": datetime.now(timezone.utc),
    })
    payload = {
        "phone_e164": "+14165550000",
        "email": "y@z.x",
        "blast_email_subject": "Hi",
    }
    result = await council_deliberate.deliberate(
        "outreach_blast", "envoy", payload,
        required=["casl"], advisory=[],
    )
    assert result["verdict"] == "REJECTED"
    assert "DNC" in result["votes"]["casl"]["reason"]


@pytest.mark.asyncio
async def test_pricing_voter_recommends_growth_for_high_score(_stub_db):
    payload = {"phone_e164": "+14165551234", "email": "x@y.z",
               "blast_email_subject": "Hi", "score": 9}
    result = await council_deliberate.deliberate(
        "outreach_blast", "envoy", payload,
        required=["casl"], advisory=["pricing"],
    )
    assert result["verdict"] == "APPROVED"
    # Pricing mutated payload
    assert payload["recommended_plan"] == "growth"
    assert "$449" in payload["recommended_price"]


@pytest.mark.asyncio
async def test_voter_crash_failsafe_approves(_stub_db, monkeypatch):
    """Crashing voter → failsafe APPROVE, never blocks."""
    async def _crashy(action, payload):
        raise RuntimeError("simulated crash")

    monkeypatch.setitem(
        council_deliberate.VOTER_MODULES,
        "casl", ("services.casl_compliance", "_nonexistent_func"),
    )
    payload = {"phone_e164": "+14165551234"}
    result = await council_deliberate.deliberate(
        "outreach_blast", "envoy", payload,
        required=["casl"], advisory=[],
    )
    # Missing function → failsafe approve
    assert result["verdict"] == "APPROVED"


@pytest.mark.asyncio
async def test_council_persists_to_decisions_and_learnings(_stub_db):
    payload = {"phone_e164": "+14165551234",
               "email": "x@y.z",
               "blast_email_subject": "Hi",
               "score": 7}
    await council_deliberate.deliberate(
        "outreach_blast", "envoy", payload,
        required=["casl", "qa"], advisory=["pricing"],
    )
    assert len(_stub_db.council_decisions_detailed.docs) == 1
    assert len(_stub_db.learnings_pending_review.docs) == 1
    learning = _stub_db.learnings_pending_review.docs[0]
    assert learning["status"] == "pending"
    assert learning["kind"] == "council_pattern"
