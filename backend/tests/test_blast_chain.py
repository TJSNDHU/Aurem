"""Tests for /app/backend/services/blast_chain.py — Section 7."""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

import pytest

sys.path.insert(0, "/app/backend")

# Force a tight 4-day chain so tests don't span weeks
os.environ["BLAST_CHAIN_DAYS"] = "0,2,5,9"

from services import blast_chain  # noqa: E402


# ─── In-memory fake Mongo collection (just enough for chain.py) ───────

class _FakeColl:
    def __init__(self) -> None:
        self.docs: List[Dict[str, Any]] = []

    async def find_one(self, q, proj=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items()):
                return dict(d)
        return None

    def find(self, q, proj=None):
        # Tiny mock: support only the dotted next_touch_at + completed/halted
        results = []
        now_iso = q.get("blast_chain.next_touch_at", {}).get("$lte") if isinstance(
            q.get("blast_chain.next_touch_at"), dict
        ) else None
        for d in self.docs:
            chain = d.get("blast_chain") or {}
            nta = chain.get("next_touch_at")
            if now_iso and (not nta or nta > now_iso):
                continue
            if chain.get("completed"):
                continue
            if chain.get("halted_reason"):
                continue
            results.append(dict(d))
        class _Cursor:
            def __init__(self, items): self.items = items
            def limit(self, n): return _Cursor(self.items[:n])
            async def to_list(self, n): return self.items[:n]
            def __aiter__(self): self._iter = iter(self.items); return self
            async def __anext__(self):
                try: return next(self._iter)
                except StopIteration: raise StopAsyncIteration
        return _Cursor(results)

    async def update_one(self, q, upd, upsert=False):
        for i, d in enumerate(self.docs):
            if all(d.get(k) == v for k, v in q.items() if not k.startswith("$")):
                if "$set" in upd:
                    for k, v in upd["$set"].items():
                        # Support dotted keys like blast_chain.completed
                        if "." in k:
                            parts = k.split(".")
                            ref = d
                            for p in parts[:-1]:
                                ref = ref.setdefault(p, {})
                            ref[parts[-1]] = v
                        else:
                            d[k] = v
                return type("R", (), {"modified_count": 1, "matched_count": 1})()
        if upsert:
            new = {**{k: v for k, v in q.items() if not k.startswith("$")},
                   **upd.get("$set", {})}
            self.docs.append(new)
            return type("R", (), {"modified_count": 0, "matched_count": 0,
                                  "upserted_id": "x"})()
        return type("R", (), {"modified_count": 0, "matched_count": 0})()

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return type("R", (), {"inserted_id": len(self.docs)})()


class _FakeDB:
    def __init__(self) -> None:
        self.campaign_leads = _FakeColl()
        self.do_not_contact = _FakeColl()
        self.blast_replies = _FakeColl()


# ─── Stub the heavy execute_blast_for_lead so tests stay fast ────────

@pytest.fixture(autouse=True)
def _stub_executor(monkeypatch):
    async def _fake_exec(db, lead, **kw):
        return {"sent_count": 2, "results": {"email": "ok", "sms": "ok"}}

    import sys
    # Build a tiny shim module so blast_chain's lazy import succeeds
    fake_mod = type(sys)("routers.campaign_router")
    fake_mod.execute_blast_for_lead = _fake_exec  # type: ignore[attr-defined]
    sys.modules["routers.campaign_router"] = fake_mod
    yield


# ─────────────────────────────────────────────────────────────────────
# Pure-function tests
# ─────────────────────────────────────────────────────────────────────

def test_assign_chain_has_website():
    assert blast_chain.assign_chain({"website": "https://x.com"}) == "chain_a"
    assert blast_chain.assign_chain({"website_url": "https://x.com"}) == "chain_a"


def test_assign_chain_no_website_qa_passed():
    assert blast_chain.assign_chain({
        "website": "", "qa_no_website": {"passed": True},
    }) == "chain_b"


def test_assign_chain_ambiguous_defaults_to_a():
    assert blast_chain.assign_chain({}) == "chain_a"


def test_classify_reply_hot():
    assert blast_chain.classify_reply("Yes, I'm interested in pricing") == "hot"
    assert blast_chain.classify_reply("call me anytime") == "hot"


def test_classify_reply_dnc():
    assert blast_chain.classify_reply("STOP") == "dnc"
    assert blast_chain.classify_reply("please unsubscribe me") == "dnc"


def test_classify_reply_dnc_beats_hot():
    # "stop calling, not interested" hits DNC first per priority
    assert blast_chain.classify_reply("not interested, stop calling") == "dnc"


def test_classify_reply_cold():
    assert blast_chain.classify_reply("ok thanks") == "cold"
    assert blast_chain.classify_reply("") == "cold"


def test_touch_offset_progression():
    # Default schedule = [0,2,5,9]
    assert blast_chain._touch_offset(1) == timedelta(0)
    assert blast_chain._touch_offset(2) == timedelta(days=2)
    assert blast_chain._touch_offset(3) == timedelta(days=5)
    assert blast_chain._touch_offset(4) == timedelta(days=9)


def test_variant_chain_a_touch_4_has_closing_prefix():
    v = blast_chain._variant("chain_a", 4)
    assert "Closing" in v["subject_prefix"]


def test_variant_chain_b_touch_3_warns_expiry():
    v = blast_chain._variant("chain_b", 3)
    assert "Heads up" in v["subject_prefix"]


# ─────────────────────────────────────────────────────────────────────
# State-machine integration tests (with fake DB)
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_start_chain_fires_first_touch_and_schedules_next():
    db = _FakeDB()
    lead = {
        "lead_id": "L1", "business_name": "Foo", "email": "a@b.c",
        "business_id": "AUR-FNDR-001",
        "website": "https://foo.com",
        "blast_email_subject": "Hi", "blast_sms_body": "Hi",
    }
    await db.campaign_leads.insert_one(lead)
    res = await blast_chain.start_chain(db, lead, source="test")
    assert res["ok"]
    chain = res["chain"]
    assert chain["id"] == "chain_a"
    assert chain["next_touch_n"] == 2
    assert chain["next_touch_at"] is not None
    assert chain["completed"] is False
    assert len(chain["touches"]) == 1


@pytest.mark.asyncio
async def test_advance_chain_fires_subsequent_touch():
    db = _FakeDB()
    lead = {"lead_id": "L2", "email": "x@y.z", "blast_email_subject": "X",
            "business_id": "AUR-FNDR-001"}
    await db.campaign_leads.insert_one(lead)
    await blast_chain.start_chain(db, lead, source="test")
    fresh = await db.campaign_leads.find_one({"lead_id": "L2"})
    res = await blast_chain.advance_chain(db, fresh)
    assert res["ok"]
    assert res["chain"]["next_touch_n"] == 3
    assert len(res["chain"]["touches"]) == 2


@pytest.mark.asyncio
async def test_advance_chain_completes_on_last_touch():
    db = _FakeDB()
    lead = {"lead_id": "L3", "business_id": "AUR-FNDR-001"}
    await db.campaign_leads.insert_one(lead)
    await blast_chain.start_chain(db, lead, source="test")
    # advance 3 more times → 4 total touches → chain completes
    for _ in range(3):
        fresh = await db.campaign_leads.find_one({"lead_id": "L3"})
        await blast_chain.advance_chain(db, fresh)
    final = await db.campaign_leads.find_one({"lead_id": "L3"})
    assert final["blast_chain"]["completed"] is True
    assert final["blast_chain"]["next_touch_at"] is None
    assert len(final["blast_chain"]["touches"]) == 4


@pytest.mark.asyncio
async def test_handle_reply_hot_halts_chain_and_flags_lead():
    db = _FakeDB()
    lead = {"lead_id": "L4", "email": "h@h.h", "business_id": "AUR-FNDR-001"}
    await db.campaign_leads.insert_one(lead)
    await blast_chain.start_chain(db, lead, source="test")
    res = await blast_chain.handle_reply(
        db, "L4", channel="email", text="Yes, what's the pricing?",
    )
    assert res["classification"] == "hot"
    final = await db.campaign_leads.find_one({"lead_id": "L4"})
    assert final["hot_lead_flag"] is True
    assert final["blast_chain"]["halted_reason"] == "hot"
    assert final["blast_chain"]["next_touch_at"] is None


@pytest.mark.asyncio
async def test_handle_reply_dnc_adds_to_do_not_contact():
    db = _FakeDB()
    lead = {"lead_id": "L5", "phone": "+15551234567", "business_id": "AUR-FNDR-001",
            "email": "stop@me.now"}
    await db.campaign_leads.insert_one(lead)
    await blast_chain.start_chain(db, lead, source="test")
    res = await blast_chain.handle_reply(
        db, "L5", channel="sms", text="STOP — please remove me",
    )
    assert res["classification"] == "dnc"
    final = await db.campaign_leads.find_one({"lead_id": "L5"})
    assert final["dnc"] is True
    assert final["status"] == "unsubscribed"
    assert final["blast_chain"]["halted_reason"] == "dnc"
    # do_not_contact got an entry
    assert len(db.do_not_contact.docs) == 1
    assert db.do_not_contact.docs[0]["phone"] == "+15551234567"


@pytest.mark.asyncio
async def test_handle_reply_cold_does_not_halt_chain():
    db = _FakeDB()
    lead = {"lead_id": "L6", "business_id": "AUR-FNDR-001"}
    await db.campaign_leads.insert_one(lead)
    await blast_chain.start_chain(db, lead, source="test")
    res = await blast_chain.handle_reply(
        db, "L6", channel="email", text="ok thanks for reaching out",
    )
    assert res["classification"] == "cold"
    final = await db.campaign_leads.find_one({"lead_id": "L6"})
    assert final["blast_chain"].get("halted_reason") is None
    assert final["blast_chain"]["next_touch_at"] is not None


@pytest.mark.asyncio
async def test_subject_prefix_applied_on_touch_2():
    """Subject mutation passes through to the executor — verifies the
    chain layer actually flavors per-touch copy."""
    captured: List[Dict[str, Any]] = []

    async def _capture(db, lead, **kw):
        captured.append(dict(lead))
        return {"sent_count": 1, "results": {}}

    import sys
    sys.modules["routers.campaign_router"].execute_blast_for_lead = _capture  # type: ignore

    db = _FakeDB()
    lead = {"lead_id": "L7", "blast_email_subject": "Audit ready", "business_id": "AUR-FNDR-001",
            "blast_sms_body": "Tap link"}
    await db.campaign_leads.insert_one(lead)
    await blast_chain.start_chain(db, lead, source="test")
    fresh = await db.campaign_leads.find_one({"lead_id": "L7"})
    await blast_chain.advance_chain(db, fresh)

    # touch #1 — no prefix
    assert captured[0]["blast_email_subject"] == "Audit ready"
    # touch #2 — "Re: " prefixed
    assert captured[1]["blast_email_subject"].startswith("Re: ")
    assert "(quick nudge)" in captured[1]["blast_sms_body"]
