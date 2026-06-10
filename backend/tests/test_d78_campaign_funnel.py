"""
D-78 Campaign Command Funnel — E2E backend tests.

Proves every metric in `routers/campaign_funnel_router.py` reflects
REAL Mongo state. Inserts synthetic leads with known outreach
history, queries the API end-to-end (real HTTP + real JWT + real
DB), asserts on the returned counts, cleans up.

Run:
    pytest backend/tests/test_d78_campaign_funnel.py -v
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

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

CAMPAIGN_ID = f"d78_test_{uuid.uuid4().hex[:8]}"


def _admin_token() -> str:
    secret = os.environ["JWT_SECRET"]
    return jwt.encode(
        {"user_id": "d78-tests", "email": "d78@aurem.live",
         "is_admin": True, "is_super_admin": True, "role": "super_admin"},
        secret, algorithm="HS256",
    )


def _customer_token() -> str:
    secret = os.environ["JWT_SECRET"]
    return jwt.encode(
        {"user_id": "d78-customer", "email": "customer@example.com",
         "is_admin": False, "role": "customer"},
        secret, algorithm="HS256",
    )


@pytest_asyncio.fixture
async def db():
    cli = AsyncIOMotorClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest_asyncio.fixture
async def synthetic_campaign(db):
    """Seed:
       - 3 leads in CAMPAIGN_ID
         - lead A: 2 emails, 1 sms, 1 report_view, status='emailed'
         - lead B: 1 whatsapp, 1 call, 1 sample_view, status='contacted'
                   (conversion!)
         - lead C: 1 email, status='emailed', email matches an
                   inbound_replies row (reply!)
       - 1 inbound_reply matching lead C's email
       Returns the lead IDs so the test can assert specific counts."""
    lead_ids = [f"d78_lead_{uuid.uuid4().hex[:6]}" for _ in range(3)]
    lead_c_email = f"d78_replier_{uuid.uuid4().hex[:6]}@example.com"
    now = datetime.now(timezone.utc)

    leads_to_insert = [
        {
            "lead_id": lead_ids[0],
            "campaign_id": CAMPAIGN_ID,
            "email": f"d78_a_{uuid.uuid4().hex[:6]}@example.com",
            "phone": "+15140001111",
            "status": "emailed",
            "created_at": now,
            "outreach_history": [
                {"channel": "email", "type": "email", "timestamp": now,
                 "status": "ok"},
                {"channel": "email", "type": "email", "timestamp": now,
                 "status": "ok"},
                {"channel": "sms", "type": "sms", "timestamp": now,
                 "status": "ok"},
                {"channel": "report_view", "type": "report_view",
                 "timestamp": now},
            ],
        },
        {
            "lead_id": lead_ids[1],
            "campaign_id": CAMPAIGN_ID,
            "email": f"d78_b_{uuid.uuid4().hex[:6]}@example.com",
            "phone": "+15140002222",
            "status": "contacted",
            "created_at": now,
            "outreach_history": [
                {"channel": "whatsapp", "type": "whatsapp",
                 "timestamp": now, "status": "ok"},
                {"channel": "call", "type": "call", "timestamp": now,
                 "status": "completed"},
                {"channel": "sample_view", "type": "sample_view",
                 "timestamp": now},
            ],
        },
        {
            "lead_id": lead_ids[2],
            "campaign_id": CAMPAIGN_ID,
            "email": lead_c_email,
            "phone": "+15140003333",
            "status": "emailed",
            "created_at": now,
            "outreach_history": [
                {"channel": "email", "type": "email", "timestamp": now,
                 "status": "ok"},
            ],
        },
    ]
    await db.campaign_leads.insert_many(leads_to_insert)

    reply_id = f"d78_reply_{uuid.uuid4().hex[:8]}"
    await db.inbound_replies.insert_one({
        "message_id": reply_id,
        "from": lead_c_email,
        "to": "ora@aurem.live",
        "subject": "Re: free preview",
        "text": "interested",
        "intent": "positive",
        "received_at": now,
    })

    yield {"lead_ids": lead_ids, "reply_email": lead_c_email,
           "reply_id": reply_id}

    # Cleanup
    await db.campaign_leads.delete_many({"campaign_id": CAMPAIGN_ID})
    await db.inbound_replies.delete_one({"message_id": reply_id})


# ── Auth ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_funnel_requires_bearer():
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.get(f"{API_BASE}/api/admin/campaigns/funnel")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_funnel_requires_admin_role():
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.get(
            f"{API_BASE}/api/admin/campaigns/funnel",
            headers={"Authorization": f"Bearer {_customer_token()}"},
        )
    assert r.status_code == 403


# ── List ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_funnels_returns_synthetic_campaign(synthetic_campaign):
    """Live HTTP — synthetic campaign appears in the list with the
    counts we planted."""
    async with httpx.AsyncClient(timeout=15) as cli:
        r = await cli.get(
            f"{API_BASE}/api/admin/campaigns/funnel?limit=100",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    found = next(
        (c for c in body["campaigns"] if c["campaign_id"] == CAMPAIGN_ID),
        None,
    )
    assert found is not None, f"campaign {CAMPAIGN_ID} missing from list"

    # Hard-counts — must match the fixture exactly
    assert found["leads_total"] == 3
    assert found["touches"]["total"] == 6  # 3 email + 1 sms + 1 whatsapp + 1 call
    assert found["touches"]["by_channel"] == {
        "email": 3, "sms": 1, "whatsapp": 1, "call": 1,
    }
    assert found["opens"]["total"] == 2
    assert found["opens"]["by_channel"] == {
        "report_view": 1, "sample_view": 1,
    }
    assert found["replies"]["total"] == 1
    # Conversions: status='contacted' = 1
    assert found["conversions"]["by_lead_status"] == 1
    assert found["conversions"]["total"] == 1


# ── Drill-down ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_one_funnel_drilldown(synthetic_campaign):
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.get(
            f"{API_BASE}/api/admin/campaigns/funnel/{CAMPAIGN_ID}",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    f = body["funnel"]
    assert f["campaign_id"] == CAMPAIGN_ID
    assert f["leads_total"] == 3
    assert f["touches"]["total"] == 6
    # Source lineage exposed for honesty
    assert "campaign_leads.outreach_history" in f["touches"]["source_collection"]


@pytest.mark.asyncio
async def test_unattributed_sentinel():
    """`__unattributed__` resolves to campaign_id=None bucket."""
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.get(
            f"{API_BASE}/api/admin/campaigns/funnel/__unattributed__",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["funnel"]["campaign_id"] == "(unattributed)"
    assert body["funnel"]["is_unattributed"] is True


# ── Timeline ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_timeline_returns_zero_filled_series(synthetic_campaign):
    """14-day window must return exactly 14 buckets (zero-filled)."""
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.get(
            f"{API_BASE}/api/admin/campaigns/funnel/{CAMPAIGN_ID}/timeline?days=14",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["days"] == 14
    assert len(body["series"]) == 14
    # Last bucket is today and should include our synthetic touches.
    today = body["series"][-1]
    assert today["total"] >= 6, (
        f"today's bucket {today} missing the 6 synthetic touches"
    )


# ── Rates ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_calculations(synthetic_campaign):
    async with httpx.AsyncClient(timeout=10) as cli:
        r = await cli.get(
            f"{API_BASE}/api/admin/campaigns/funnel/{CAMPAIGN_ID}",
            headers={"Authorization": f"Bearer {_admin_token()}"},
        )
    f = r.json()["funnel"]
    # open_rate = opens(2) / touches(6) * 100 ≈ 33.33%
    assert f["rates_pct"]["open_rate"] == pytest.approx(33.33, abs=0.5)
    # reply_rate = replies(1) / touches(6) * 100 ≈ 16.67%
    assert f["rates_pct"]["reply_rate"] == pytest.approx(16.67, abs=0.5)
    # conversion_rate = conversions(1) / leads(3) * 100 ≈ 33.33%
    assert f["rates_pct"]["conversion_rate"] == pytest.approx(33.33, abs=0.5)


@pytest.mark.asyncio
async def test_rates_safe_division_when_zero_touches(db):
    """Empty campaign must NOT crash on division by zero — return None
    rates honestly so the UI can render "—" instead of NaN."""
    empty_cid = f"d78_empty_{uuid.uuid4().hex[:6]}"
    await db.campaign_leads.insert_one({
        "lead_id": f"d78_empty_lead_{uuid.uuid4().hex[:6]}",
        "campaign_id": empty_cid,
        "status": "new",
        "outreach_history": [],
    })
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.get(
                f"{API_BASE}/api/admin/campaigns/funnel/{empty_cid}",
                headers={"Authorization": f"Bearer {_admin_token()}"},
            )
        assert r.status_code == 200
        f = r.json()["funnel"]
        assert f["touches"]["total"] == 0
        assert f["rates_pct"]["open_rate"] is None
        assert f["rates_pct"]["reply_rate"] is None
    finally:
        await db.campaign_leads.delete_many({"campaign_id": empty_cid})
