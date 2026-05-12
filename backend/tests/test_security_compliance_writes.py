"""
iter 322ee — Regression proof for the two "looks broken but works" writes.

In the 322eb audit the `token_blocklist` and `dnc_list` collections came
back empty in production and were almost reported as broken features.
The code paths are actually correct — they just hadn't been triggered
by a real user yet. These tests lock that down so the next refactor
doesn't silently break either flow.

Run: pytest backend/tests/test_security_compliance_writes.py -v
"""
from __future__ import annotations

import asyncio
import os
import sys
import time

import pytest
import pytest_asyncio

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient


@pytest_asyncio.fixture
async def db():
    """Live Motor handle against the configured Mongo. We use the same
    target as the app (preview Mongo) — these tests insert one doc,
    assert, and clean up after themselves."""
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    handle = client[os.environ["DB_NAME"]]
    # jwt_blocklist resolves db from `server.db` — wire it once.
    import server
    server.db = handle
    yield handle
    client.close()


# ─── token_blocklist (security) ──────────────────────────────────────
@pytest.mark.asyncio
async def test_token_blocklist_write_and_lookup(db):
    """block_token() must insert into token_blocklist and is_blocked()
    must return True for the same JTI within the TTL window."""
    from shared.auth.jwt_blocklist import block_token, is_blocked

    jti = f"regression_{int(time.time() * 1000)}"
    before = await db.token_blocklist.count_documents({})
    ok = await block_token("dummy.jwt.token", jti, ttl_seconds=300)
    after = await db.token_blocklist.count_documents({})

    try:
        assert ok is True, "block_token() must return True on success"
        assert after == before + 1, "exactly one new blocklist row"
        assert await is_blocked(jti) is True, "freshly blocked JTI must lookup"

        # Verify the doc shape — has the fields the auth layer expects.
        doc = await db.token_blocklist.find_one({"jti": jti}, {"_id": 0})
        assert doc is not None
        assert doc["jti"] == jti
        assert "expires_at" in doc or "blocked_at" in doc, \
            "blocklist row needs timestamp metadata"
    finally:
        await db.token_blocklist.delete_one({"jti": jti})


# ─── dnc_list (CASL/TCPA compliance) ─────────────────────────────────
@pytest.mark.asyncio
async def test_dnc_list_stop_reply_writes(db):
    """process_stop_reply() must add the address to dnc_list and
    is_in_dnc() must report True for the same address."""
    from services.lead_dedup import process_stop_reply, is_in_dnc

    email = f"regression_{int(time.time() * 1000)}@test.example"
    before = await db.dnc_list.count_documents({})
    ok = await process_stop_reply(db, email=email)
    after = await db.dnc_list.count_documents({})

    try:
        assert ok is True, "process_stop_reply must succeed for a valid email"
        assert after == before + 1, "DNC must gain exactly one row"
        assert await is_in_dnc(db, email=email) is True, \
            "freshly opted-out address must read True"

        doc = await db.dnc_list.find_one({"email": email}, {"_id": 0})
        assert doc is not None
        assert doc["email"] == email
        assert doc.get("reason") == "stop_reply", \
            "DNC reason must be tagged so we can audit compliance later"
    finally:
        await db.dnc_list.delete_one({"email": email})


@pytest.mark.asyncio
async def test_dnc_list_phone_path(db):
    """process_stop_reply() must also handle phone-based opt-outs."""
    from services.lead_dedup import process_stop_reply, is_in_dnc

    phone = f"+1555{int(time.time()) % 10000000:07d}"
    before = await db.dnc_list.count_documents({})
    ok = await process_stop_reply(db, phone=phone)
    after = await db.dnc_list.count_documents({})

    try:
        assert ok is True
        assert after == before + 1
        assert await is_in_dnc(db, phone=phone) is True
    finally:
        # Match the normalized form the writer used.
        from services.lead_dedup import _norm_phone
        await db.dnc_list.delete_one({"phone": _norm_phone(phone)})
