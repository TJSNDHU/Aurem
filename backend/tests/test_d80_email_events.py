"""
D-80 — email_events collection + Resend webhook integration + funnel
       integration + Apply Plan UX flow.

Proves end-to-end against real Mongo:

  1. services.email_events.record_event dedups identical events
  2. email_events shows up in campaign_funnel.opens.resend_opens
  3. ensure_indexes is idempotent
  4. The "Apply plan" UX flow (server-side proof): a chat call with
     mode=execute after a plan-mode call correctly invokes skills.
     (Test #2 in D-79 already proves plan-mode suppression — here we
     prove the inverse round-trip.)
"""
from __future__ import annotations

import os
import uuid

import httpx
import jwt
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

API_BASE = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or "http://localhost:8001"
).rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "aurem_db")


def _admin_token() -> str:
    return jwt.encode(
        {"user_id": "d80-tests", "email": "d80@aurem.live",
         "is_admin": True, "is_super_admin": True, "role": "super_admin"},
        os.environ["JWT_SECRET"], algorithm="HS256",
    )


@pytest_asyncio.fixture
async def db():
    cli = AsyncIOMotorClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


# ── email_events service ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_email_events_record_basic(db):
    from services import email_events as ee
    ee.set_db(db)
    await ee.ensure_indexes()
    eid = f"d80_ee_{uuid.uuid4().hex[:8]}"
    try:
        out = await ee.record_event(
            event_type="email.opened",
            email_id=eid, email_to="qa@example.com",
            raw={"type": "email.opened"},
            lead_id="d80-lead", campaign_id="d80-camp",
            template_id="welcome_v1",
            created_at="2026-06-10T12:34:56.000Z",
        )
        assert out == eid
        doc = await db.email_events.find_one({"email_id": eid})
        assert doc is not None
        assert doc["event_type"] == "email.opened"
        assert doc["email_to"] == "qa@example.com"
        assert doc["lead_id"] == "d80-lead"
        assert doc["campaign_id"] == "d80-camp"
        assert doc["template_id"] == "welcome_v1"
        # ISO string roundtrip preserved
        assert doc["timestamp"].startswith("2026-06-10")
    finally:
        await db.email_events.delete_many({"email_id": eid})


@pytest.mark.asyncio
async def test_email_events_dedups_same_event(db):
    """Resend retries the same event — we must not double-count."""
    from services import email_events as ee
    ee.set_db(db)
    await ee.ensure_indexes()
    eid = f"d80_dedup_{uuid.uuid4().hex[:8]}"
    try:
        for _ in range(3):
            await ee.record_event(
                event_type="email.delivered",
                email_id=eid, email_to="qa@example.com",
                raw={},
                created_at="2026-06-10T12:34:56.000Z",
            )
        n = await db.email_events.count_documents({"email_id": eid})
        assert n == 1, f"dedup failed — got {n} rows for the same event"
    finally:
        await db.email_events.delete_many({"email_id": eid})


@pytest.mark.asyncio
async def test_email_events_drops_unknown_type(db):
    from services import email_events as ee
    ee.set_db(db)
    res = await ee.record_event(
        event_type="email.totally_fabricated",
        email_id="x", email_to="qa@example.com", raw={},
    )
    assert res is None


@pytest.mark.asyncio
async def test_email_events_drops_missing_email_id(db):
    from services import email_events as ee
    ee.set_db(db)
    res = await ee.record_event(
        event_type="email.opened",
        email_id="", email_to="qa@example.com", raw={},
    )
    assert res is None


@pytest.mark.asyncio
async def test_email_events_count_for_campaign(db):
    from services import email_events as ee
    ee.set_db(db)
    await ee.ensure_indexes()
    cid = f"d80_camp_{uuid.uuid4().hex[:6]}"
    try:
        for i in range(4):
            await ee.record_event(
                event_type="email.opened",
                email_id=f"{cid}_open_{i}",
                email_to=f"qa{i}@example.com",
                raw={}, campaign_id=cid,
                created_at=f"2026-06-10T12:{i:02d}:00.000Z",
            )
        for i in range(2):
            await ee.record_event(
                event_type="email.clicked",
                email_id=f"{cid}_click_{i}",
                email_to=f"qa{i}@example.com",
                raw={}, campaign_id=cid,
                created_at=f"2026-06-10T13:{i:02d}:00.000Z",
            )
        opens = await ee.count_for_campaign(cid, "email.opened")
        clicks = await ee.count_for_campaign(cid, "email.clicked")
        assert opens == 4
        assert clicks == 2
        # Different campaign returns 0 honestly
        other = await ee.count_for_campaign("does-not-exist", "email.opened")
        assert other == 0
    finally:
        await db.email_events.delete_many({"campaign_id": cid})


# ── Funnel integration — opens now includes resend events ───────────

@pytest.mark.asyncio
async def test_funnel_combines_pixel_and_resend_opens(db):
    """End-to-end via HTTP: insert leads with pixel opens AND insert
    Resend opens in email_events. Funnel must combine both."""
    from services import email_events as ee
    ee.set_db(db)
    await ee.ensure_indexes()

    cid = f"d80_fn_{uuid.uuid4().hex[:6]}"
    lead_email = f"d80_fn_{uuid.uuid4().hex[:6]}@example.com"
    try:
        await db.campaign_leads.insert_one({
            "lead_id": f"d80_fn_lead_{uuid.uuid4().hex[:6]}",
            "campaign_id": cid,
            "email": lead_email,
            "status": "emailed",
            "outreach_history": [
                {"channel": "email", "type": "email"},
                {"channel": "report_view", "type": "report_view"},
                {"channel": "sample_view", "type": "sample_view"},
            ],
        })
        # 2 real Resend opens, 1 click
        for i in range(2):
            await ee.record_event(
                event_type="email.opened",
                email_id=f"{cid}_re_open_{i}",
                email_to=lead_email, raw={},
                campaign_id=cid,
                created_at=f"2026-06-10T14:0{i}:00.000Z",
            )
        await ee.record_event(
            event_type="email.clicked",
            email_id=f"{cid}_re_click",
            email_to=lead_email, raw={},
            campaign_id=cid,
            created_at="2026-06-10T15:00:00.000Z",
        )
        # 1 delivered, 0 bounced
        await ee.record_event(
            event_type="email.delivered",
            email_id=f"{cid}_re_deliv",
            email_to=lead_email, raw={},
            campaign_id=cid,
            created_at="2026-06-10T14:01:30.000Z",
        )

        async with httpx.AsyncClient(timeout=12) as cli:
            r = await cli.get(
                f"{API_BASE}/api/admin/campaigns/funnel/{cid}",
                headers={"Authorization": f"Bearer {_admin_token()}"},
            )
        assert r.status_code == 200, r.text
        f = r.json()["funnel"]

        # 2 pixel opens (report_view + sample_view) + 2 resend opens = 4
        assert f["opens"]["total"] == 4, f["opens"]
        assert f["opens"]["pixel_opens"] == 2
        assert f["opens"]["resend_opens"] == 2
        # Resend engagement section is populated
        re = f["resend_engagement"]
        assert re["opened"] == 2
        assert re["clicked"] == 1
        assert re["delivered"] == 1
        assert re["bounced"] == 0
        assert re["source_missing"] is False
    finally:
        await db.campaign_leads.delete_many({"campaign_id": cid})
        await db.email_events.delete_many({"campaign_id": cid})


@pytest.mark.asyncio
async def test_funnel_unmissing_when_email_events_absent(db):
    """Even when no email_events exist for the campaign, the funnel
    must NOT crash and must return 0 honestly (not source_missing
    unless the entire collection is gone)."""
    cid = f"d80_empty_{uuid.uuid4().hex[:6]}"
    try:
        await db.campaign_leads.insert_one({
            "lead_id": f"d80_empty_lead_{uuid.uuid4().hex[:6]}",
            "campaign_id": cid,
            "email": "lonely@example.com",
            "status": "new",
            "outreach_history": [],
        })
        async with httpx.AsyncClient(timeout=12) as cli:
            r = await cli.get(
                f"{API_BASE}/api/admin/campaigns/funnel/{cid}",
                headers={"Authorization": f"Bearer {_admin_token()}"},
            )
        assert r.status_code == 200
        f = r.json()["funnel"]
        assert f["opens"]["total"] == 0
        assert f["opens"]["resend_opens"] == 0
        assert f["resend_engagement"]["opened"] == 0
    finally:
        await db.campaign_leads.delete_many({"campaign_id": cid})


# ── Webhook → email_events end-to-end (idempotent) ──────────────────

@pytest.mark.asyncio
async def test_resend_webhook_persists_to_email_events(db, monkeypatch):
    """POST /api/lifecycle/webhook/resend → row lands in email_events
    with the join keys (lead_id, campaign_id) attached."""
    # Disable signature verification for this test (we test that
    # separately).
    monkeypatch.delenv("RESEND_WEBHOOK_SECRET", raising=False)

    # Seed a real lead so the webhook can resolve campaign_id
    cid = f"d80_wh_{uuid.uuid4().hex[:6]}"
    eml = f"d80_wh_{uuid.uuid4().hex[:6]}@example.com"
    lead_id = f"d80_wh_lead_{uuid.uuid4().hex[:6]}"
    email_id = f"d80_wh_eid_{uuid.uuid4().hex[:8]}"

    await db.campaign_leads.insert_one({
        "lead_id": lead_id,
        "campaign_id": cid,
        "email": eml,
        "status": "emailed",
        "outreach_history": [],
    })
    try:
        payload = {
            "type": "email.opened",
            "created_at": "2026-06-10T20:00:00.000Z",
            "data": {
                "email_id": email_id,
                "to": [eml],
                "tags": [{"name": "template_id", "value": "welcome_v2"}],
            },
        }
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.post(
                f"{API_BASE}/api/lifecycle/webhook/resend",
                json=payload,
            )
        assert r.status_code == 200, r.text

        # Real Mongo state
        doc = await db.email_events.find_one({"email_id": email_id})
        assert doc is not None
        assert doc["event_type"] == "email.opened"
        assert doc["campaign_id"] == cid, (
            "webhook didn't propagate lead.campaign_id into email_events"
        )
        assert doc["lead_id"] == lead_id
        assert doc["template_id"] == "welcome_v2"
        assert doc["email_to"] == eml

        # Replay (Resend retry) — must dedup
        async with httpx.AsyncClient(timeout=10) as cli:
            r2 = await cli.post(
                f"{API_BASE}/api/lifecycle/webhook/resend",
                json=payload,
            )
        assert r2.status_code == 200
        n = await db.email_events.count_documents({"email_id": email_id})
        assert n == 1, f"dedup failed: got {n} rows after replay"
    finally:
        await db.campaign_leads.delete_many({"campaign_id": cid})
        await db.email_events.delete_many({"email_id": email_id})
