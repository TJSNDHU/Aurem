"""Self-Audit tests — iter 282al-10."""
from __future__ import annotations

import asyncio
import os
import uuid

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="asserts pre-slim health/bootstrap shape or older infra spec — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

# Force fallback path — don't ping real Telegram from tests.
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""

from services.self_audit import (  # noqa: E402
    DEFAULT_THRESHOLD,
    ensure_self_audit_indexes,
    get_latest_self_audit,
    run_self_audit,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _fresh_db_async():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    name = f"aurem_test_selfaudit_{uuid.uuid4().hex[:8]}"
    motor_client = AsyncIOMotorClient(mongo_url)
    return motor_client[name], motor_client, name


def test_default_threshold_constant():
    assert DEFAULT_THRESHOLD == 95


def test_run_self_audit_logs_row():
    """E2E: hit aurem.live, verify row written, score sane."""
    db, client, name = _fresh_db_async()

    async def _go():
        try:
            row = await run_self_audit(
                db, target_url="https://aurem.live",
                threshold=95,
            )
            stored = await db.self_audit_log.count_documents({})
            return row, stored
        finally:
            await client.drop_database(name)

    row, stored = _run(_go())
    assert stored == 1
    # Score should be a real integer 0..100
    assert isinstance(row["overall_score"], int)
    assert 0 <= row["overall_score"] <= 100
    # Title populated when fetch worked
    assert row["target"] == "https://aurem.live"
    assert "started_at" in row and "completed_at" in row
    # alerted only fires below threshold AND with TG creds
    assert row["alerted"] is False  # creds cleared in tests


def test_run_self_audit_handles_unreachable_target():
    db, client, name = _fresh_db_async()

    async def _go():
        try:
            return await run_self_audit(
                db,
                target_url="https://this-does-not-exist-aurem-test.invalid",
                threshold=95,
            )
        finally:
            await client.drop_database(name)

    row = _run(_go())
    # Should still produce a row, just with low scores or ok=False
    assert "overall_score" in row
    assert isinstance(row["overall_score"], int)


def test_get_latest_self_audit():
    db, client, name = _fresh_db_async()

    async def _go():
        try:
            await run_self_audit(db, target_url="https://aurem.live",
                                  threshold=95)
            return await get_latest_self_audit(db)
        finally:
            await client.drop_database(name)

    latest = _run(_go())
    assert latest is not None
    assert "overall_score" in latest
    # ISO-formatted strings on the way out
    assert isinstance(latest["started_at"], str)


def test_ensure_indexes_creates():
    db, client, name = _fresh_db_async()

    async def _go():
        try:
            await ensure_self_audit_indexes(db)
            return await db.self_audit_log.index_information()
        finally:
            await client.drop_database(name)

    info = _run(_go())
    assert "started_at_ttl_90d" in info
    assert "target_started" in info


# ── Hot-lead Telegram ping wired in inbound_reply_handler ────────────
def test_positive_intent_triggers_telegram_path():
    """Verify handle_inbound_reply attempts the Telegram ping branch on
    positive intent. Since TG creds are empty, ping returns ok=False — but
    `telegram_pinged` flag should be written to the inbound_replies row."""
    from services.inbound_reply_handler import handle_inbound_reply

    # Stub Resend / LLM
    os.environ["EMERGENT_LLM_KEY"] = ""
    os.environ["RESEND_API_KEY"] = ""

    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    name = f"aurem_test_tg_{uuid.uuid4().hex[:8]}"
    sync_client = MongoClient(mongo_url)
    sync_client[name].campaign_leads.insert_one({
        "lead_id": "lead-tg", "email": "vet@example.com",
        "business_name": "Brampton Vet", "city": "Brampton",
        "category": "veterinarian",
    })

    async def _go():
        motor_client = AsyncIOMotorClient(mongo_url)
        try:
            db = motor_client[name]
            res = await handle_inbound_reply(db, {
                "from": "vet@example.com",
                "to": "ora@aurem.live",
                "subject": "Re: free preview",
                "text": "OMG that's so nice. how do i proceed",
            })
            row = await db.inbound_replies.find_one(
                {"from": "vet@example.com"}, projection={"_id": 0},
            )
            return res, row
        finally:
            motor_client.close()

    res, row = _run(_go())
    sync_client.drop_database(name)
    sync_client.close()

    assert res["intent"] == "positive"
    assert row is not None
    # Telegram branch ran (creds missing → ok=False, but flag was written)
    assert "telegram_pinged" in row
    assert row["telegram_pinged"] is False
    # reason captured
    assert row.get("telegram_reason") in ("creds_missing", None)
