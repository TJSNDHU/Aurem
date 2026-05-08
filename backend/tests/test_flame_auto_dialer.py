"""
Flame Auto-Dialer regression tests
----------------------------------
Covers the gate logic & script generation. Does NOT place real Twilio calls.
Uses plain asyncio.run so no pytest-asyncio required.
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.flame_auto_dialer import try_auto_dial, _build_pitch_script, _resolve_alert_phone  # noqa: E402


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    async def find_one(self, q, projection=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items()):
                return d
        return None

    async def insert_one(self, doc):
        self.docs.append(doc)

    async def update_one(self, q, update, upsert=False):
        pass


class FakeDB:
    def __init__(self):
        self.campaign_leads = FakeCollection()
        self.aurem_live_viewers = FakeCollection()
        self.aurem_websites = FakeCollection()
        self.tenant_settings = FakeCollection()
        self.flame_auto_dials = FakeCollection()
        self.voice_calls = FakeCollection()


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_script_personalization():
    lead = {"contact_name": "Tejinder Singh", "business_name": "TJ Auto Clinic", "website_url": "https://tj.example"}
    viewer = {"duration_seconds": 180, "business_name": "TJ Auto Clinic"}
    script = _build_pitch_script(lead, viewer)
    assert "Tejinder" in script
    assert "TJ Auto Clinic" in script
    assert "3 minutes" in script
    assert "O R A" in script


def test_below_tier_skips():
    db = FakeDB()
    viewer = {"session_id": "s1", "flame_score": 45, "flame_tier": "HOT"}
    result = _run(try_auto_dial(db, viewer))
    assert result["status"] == "below_tier"


def test_blocked_gate_when_accurate_scout_says_no():
    db = FakeDB()
    db.campaign_leads.docs.append({
        "lead_id": "l1", "phone": "+16135551234", "business_name": "GatedCo",
        "verification": {"channel_gating": {"call": False}}, "dnc": False,
    })
    viewer = {"session_id": "s2", "flame_score": 150, "flame_tier": "INFERNO", "slug": "gated"}
    result = _run(try_auto_dial(db, viewer, lead_id="l1"))
    assert result["status"] == "blocked_gate"


def test_blocked_dnc():
    db = FakeDB()
    db.campaign_leads.docs.append({
        "lead_id": "l2", "phone": "+16135551234", "business_name": "DNCCo",
        "verification": {"channel_gating": {"call": True}}, "dnc": True,
    })
    viewer = {"session_id": "s3", "flame_score": 150, "flame_tier": "INFERNO"}
    result = _run(try_auto_dial(db, viewer, lead_id="l2"))
    assert result["status"] == "blocked_dnc"


def test_no_phone_on_file():
    db = FakeDB()
    db.campaign_leads.docs.append({
        "lead_id": "l3", "business_name": "NoPhoneCo",
        "verification": {"channel_gating": {"call": True}}, "dnc": False, "phone": "",
    })
    viewer = {"session_id": "s4", "flame_score": 150, "flame_tier": "INFERNO"}
    result = _run(try_auto_dial(db, viewer, lead_id="l3"))
    assert result["status"] == "no_phone"


def test_tenant_phone_override():
    db = FakeDB()
    db.tenant_settings.docs.append({"tenant_id": "tenant-x", "flame_alert_phone": "+19998887777"})
    phone = _run(_resolve_alert_phone(db, "tenant-x"))
    assert phone == "+19998887777"


def test_tenant_phone_fallback():
    db = FakeDB()
    phone = _run(_resolve_alert_phone(db, "missing-tenant"))
    assert phone.startswith("+")


if __name__ == "__main__":
    test_script_personalization()
    test_below_tier_skips()
    test_blocked_gate_when_accurate_scout_says_no()
    test_blocked_dnc()
    test_no_phone_on_file()
    test_tenant_phone_override()
    test_tenant_phone_fallback()
    print("All tests passed")
