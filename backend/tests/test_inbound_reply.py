"""Inbound reply handler tests — iter 282al-9."""
from __future__ import annotations

import asyncio
import os
import uuid

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

# Force fallback path for compose_warm_reply (clear LLM/Resend keys
# even if .env had them — these tests must not call external services).
os.environ["EMERGENT_LLM_KEY"] = ""
os.environ["RESEND_API_KEY"] = ""

from services.inbound_reply_handler import (  # noqa: E402
    classify_intent,
    compose_warm_reply,
    ensure_inbound_indexes,
    handle_inbound_reply,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _fresh_db_async():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    name = f"aurem_test_inbound_{uuid.uuid4().hex[:8]}"
    motor_client = AsyncIOMotorClient(mongo_url)
    return motor_client[name], motor_client, name


# ── classify_intent ──────────────────────────────────────────────────
def test_classify_positive():
    assert classify_intent("OMG that's so nice. how do i proceed") == "positive"
    assert classify_intent("Yes please") == "positive"
    assert classify_intent("Looks great, sign me up") == "positive"
    assert classify_intent("ok") == "positive"


def test_classify_question():
    assert classify_intent("How much does this cost?") == "question"
    assert classify_intent("what does it cost") == "question"


def test_classify_opt_out():
    assert classify_intent("STOP emailing me") == "opt_out"
    assert classify_intent("unsubscribe please") == "opt_out"
    assert classify_intent("not interested") == "opt_out"


def test_classify_negative():
    assert classify_intent("This is a scam") == "negative"
    assert classify_intent("I'll report you for CASL violation") == "negative"


def test_classify_unknown():
    assert classify_intent("") == "unknown"
    assert classify_intent("xyzzy random gibberish") == "unknown"


# ── compose_warm_reply (fallback path) ───────────────────────────────
def test_compose_warm_reply_includes_canadian_footer():
    lead = {"business_name": "Mike's Plumbing",
             "city": "Mississauga", "category": "plumber"}
    res = _run(compose_warm_reply(lead, "OMG how do i proceed",
                                    "https://aurem.live/api/sites/abc"))
    body = res["body"].lower()
    assert "mississauga" in body
    assert "stop" in body
    assert "aurem" in body
    assert "abc" in body  # site URL should be referenced
    assert res["fallback_used"] is True


def test_compose_warm_reply_no_site_url():
    lead = {"business_name": "X", "city": "Toronto", "category": "plumber"}
    res = _run(compose_warm_reply(lead, "yes interested"))
    assert "stop" in res["body"].lower()
    assert "aurem" in res["body"].lower()


# ── handle_inbound_reply — opt_out path ──────────────────────────────
def test_handle_opt_out_adds_to_dnc():
    db, client, name = _fresh_db_async()

    async def _go():
        try:
            # Seed lead + outreach history so dedup actually works
            await db.campaign_leads.insert_one({
                "lead_id": "lead-opt", "business_id": "AUR-FNDR-001",
                "email": "stop@example.com",
                "business_name": "Test", "city": "Toronto",
            })
            res = await handle_inbound_reply(db, {
                "from": "stop@example.com", "subject": "STOP",
                "text": "STOP emailing me",
            })
            in_dnc = await db.dnc_list.find_one(
                {"email": "stop@example.com"}, projection={"_id": 0},
            )
            return res, in_dnc
        finally:
            await client.drop_database(name)

    res, dnc = _run(_go())
    assert res["intent"] == "opt_out"
    assert res["auto_replied"] is False
    assert res["action"] == "added_to_dnc"
    assert dnc is not None


# ── handle_inbound_reply — positive (no RESEND key → no send) ───────
def test_handle_positive_records_intent():
    db, client, name = _fresh_db_async()

    async def _go():
        try:
            await db.campaign_leads.insert_one({
                "lead_id": "lead-yes", "business_id": "AUR-FNDR-001",
                "email": "happy@example.com",
                "business_name": "Mike Plumbing", "city": "Mississauga",
                "category": "plumber",
            })
            await db.auto_built_sites.insert_one({
                "site_id": "s1", "lead_id": "lead-yes",
                "slug": "mike-plumbing-abc",
                "publish_status": "partial",
                "ts": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc),
            })
            res = await handle_inbound_reply(db, {
                "from": "happy@example.com", "subject": "Re: preview",
                "text": "OMG that's so nice. how do i proceed",
            })
            row = await db.inbound_replies.find_one(
                {"from": "happy@example.com"}, projection={"_id": 0},
            )
            return res, row
        finally:
            await client.drop_database(name)

    res, row = _run(_go())
    assert res["intent"] == "positive"
    assert res["matched_lead"] is True
    # Site URL falls back to /api/sites/{slug}
    assert res.get("site_url", "").endswith("mike-plumbing-abc")
    # No RESEND_API_KEY → auto_replied False with reason
    assert res["auto_replied"] is False
    assert row is not None
    assert row["intent"] == "positive"


def test_handle_negative_flagged():
    db, client, name = _fresh_db_async()

    async def _go():
        try:
            res = await handle_inbound_reply(db, {
                "from": "angry@example.com", "subject": "scam",
                "text": "this is a scam, I'll sue you",
            })
            alert = await db.sentinel_alerts.find_one(
                {"kind": "negative_inbound_reply"}, projection={"_id": 0},
            )
            return res, alert
        finally:
            await client.drop_database(name)

    res, alert = _run(_go())
    assert res["intent"] == "negative"
    assert res["action"] == "flagged_for_human"
    assert alert is not None


# ── ensure_inbound_indexes ──────────────────────────────────────────
def test_ensure_inbound_indexes_creates():
    db, client, name = _fresh_db_async()

    async def _go():
        try:
            await ensure_inbound_indexes(db)
            return await db.inbound_replies.index_information()
        finally:
            await client.drop_database(name)

    info = _run(_go())
    assert "received_at_ttl" in info
    assert "from_received" in info
    assert "intent_received" in info


# ── webhook E2E (FastAPI) ────────────────────────────────────────────
def test_webhook_endpoint_e2e():
    """Round-trip POST /api/email/inbound."""
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from routers.inbound_email_router import (
        router as inbound_router, set_db,
    )

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    name = f"aurem_test_inbound_{uuid.uuid4().hex[:8]}"
    sync_client = MongoClient(mongo_url)
    sync_client[name].campaign_leads.insert_one({
        "business_id": "AUR-FNDR-001",
        "lead_id": "lead-e2e", "email": "vet@example.com",
        "business_name": "Brampton Vet", "city": "Brampton",
        "category": "veterinarian",
    })

    app = FastAPI()
    app.include_router(inbound_router)

    async def _go():
        motor_client = AsyncIOMotorClient(mongo_url)
        set_db(motor_client[name])
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport,
                                 base_url="http://test") as ac:
            r = await ac.get("/api/email/inbound/health")
            assert r.status_code == 200
            assert r.json()["ok"] is True

            r = await ac.post("/api/email/inbound", json={
                "from": "Vet User <vet@example.com>",
                "to": "ora@aurem.live",
                "subject": "Re: free preview",
                "text": "OMG that's so nice. how do i proceed",
            })
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["intent"] == "positive"
            assert data["matched_lead"] is True

            # Bad payload
            r = await ac.post("/api/email/inbound", json={"text": "no from"})
            assert r.status_code == 400
        motor_client.close()

    _run(_go())
    sync_client.drop_database(name)
    sync_client.close()
    set_db(None)
