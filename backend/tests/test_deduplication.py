"""Lead dedup + DNC tests — iter 282al-6.

All Mongo work runs inside a single per-test event loop to avoid the
"future belongs to a different loop" Motor footgun.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from services.lead_dedup import (
    MAX_CONTACTS_PER_PHONE,
    SAME_BUSINESS_THRESHOLD,
    add_to_dnc,
    can_contact_lead,
    ensure_dedup_indexes,
    extract_domain,
    find_existing_site,
    fuzzy_match,
    is_duplicate_lead,
    is_in_dnc,
    process_stop_reply,
    reject_duplicate,
)


# ─────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────
def _run(coro):
    """Single fresh event loop per test → no cross-loop Motor errors."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _fresh_db():
    """Return (db, drop_fn). Caller must invoke drop_fn() at the end."""
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_url)
    name = f"aurem_test_dedup_{uuid.uuid4().hex[:8]}"
    db = client[name]
    return db, client, name


# ─────────────────────────────────────────────────────────────────────
# fuzzy_match — pure-python, no Mongo
# ─────────────────────────────────────────────────────────────────────
def test_fuzzy_identical():
    assert fuzzy_match("Mike's Plumbing", "mike's plumbing") == 1.0


def test_fuzzy_name_match_blocks():
    score = fuzzy_match("mike's plumbing co", "mikes plumbing company")
    assert score >= SAME_BUSINESS_THRESHOLD


def test_fuzzy_name_with_inc_suffix():
    score = fuzzy_match("Acme Plumbing Inc.", "Acme Plumbing")
    assert score >= SAME_BUSINESS_THRESHOLD


def test_fuzzy_different_business_passes():
    score = fuzzy_match("mike's plumbing", "toronto hvac solutions")
    assert score < SAME_BUSINESS_THRESHOLD


def test_fuzzy_empty_inputs():
    assert fuzzy_match("", "anything") == 0.0
    assert fuzzy_match("foo", "") == 0.0


def test_extract_domain():
    assert extract_domain("https://www.acme.ca/about") == "acme.ca"
    assert extract_domain("acme.ca") == "acme.ca"
    assert extract_domain("") == ""


# ─────────────────────────────────────────────────────────────────────
# is_duplicate_lead
# ─────────────────────────────────────────────────────────────────────
def test_same_phone_rejected():
    db, client, name = _fresh_db()

    async def _go():
        try:
            await db.campaign_leads.insert_one({
                "lead_id": "seed-1", "business_name": "Seed Co",
                "phone": "+1 (416) 555-0100",
                "phone_normalized": "14165550100",
                "city": "Toronto",
            })
            return await is_duplicate_lead(db, {
                "phone": "+14165550100",
                "business_name": "Different Co",
                "city": "Mississauga",
            })
        finally:
            await client.drop_database(name)

    is_dup, reason = _run(_go())
    assert is_dup is True
    assert reason == "phone_match"


def test_same_domain_rejected():
    db, client, name = _fresh_db()

    async def _go():
        try:
            await db.campaign_leads.insert_one({
                "lead_id": "seed-2", "business_name": "Seed Co",
                "website_domain": "acmeplumbing.ca", "city": "Toronto",
            })
            return await is_duplicate_lead(db, {
                "business_name": "Acme Plumbing Inc",
                "website": "https://www.acmeplumbing.ca/services",
                "city": "Mississauga",
            })
        finally:
            await client.drop_database(name)

    is_dup, reason = _run(_go())
    assert is_dup is True
    assert reason == "domain_match"


def test_fuzzy_name_city_blocks():
    db, client, name = _fresh_db()

    async def _go():
        try:
            await db.campaign_leads.insert_one({
                "lead_id": "seed-3", "business_name": "Mike's Plumbing Co",
                "city": "Mississauga",
            })
            return await is_duplicate_lead(db, {
                "business_name": "Mikes Plumbing Company",
                "city": "Mississauga",
            })
        finally:
            await client.drop_database(name)

    is_dup, reason = _run(_go())
    assert is_dup is True
    assert reason == "fuzzy_name_city"


def test_unique_lead_passes():
    db, client, name = _fresh_db()

    async def _go():
        try:
            return await is_duplicate_lead(db, {
                "phone": "+14165559999", "business_name": "Brand New Co",
                "city": "Mississauga",
            })
        finally:
            await client.drop_database(name)

    is_dup, reason = _run(_go())
    assert is_dup is False
    assert reason == ""


def test_dnc_phone_treated_as_duplicate():
    db, client, name = _fresh_db()

    async def _go():
        try:
            await add_to_dnc(db, phone="+14165550900", reason="stop_reply")
            return await is_duplicate_lead(db, {
                "phone": "+14165550900", "business_name": "Anything",
                "city": "Toronto",
            })
        finally:
            await client.drop_database(name)

    is_dup, reason = _run(_go())
    assert is_dup is True
    assert reason == "dnc_phone"


# ─────────────────────────────────────────────────────────────────────
# can_contact_lead
# ─────────────────────────────────────────────────────────────────────
def test_outreach_blocked_after_max_contacts():
    db, client, name = _fresh_db()

    async def _go():
        try:
            for i in range(MAX_CONTACTS_PER_PHONE):
                await db.outreach_history.insert_one({
                    "phone_normalized": "14165550111",
                    "lead_id": f"prior-{i}",
                    "dispatched_at": datetime.now(timezone.utc),
                })
            allowed, reason = await can_contact_lead(db, {
                "phone": "+14165550111", "lead_id": "lead-new",
                "business_name": "Some Co", "city": "Toronto",
            })
            in_dnc = await is_in_dnc(db, phone="+14165550111")
            return allowed, reason, in_dnc
        finally:
            await client.drop_database(name)

    allowed, reason, in_dnc = _run(_go())
    assert allowed is False
    assert reason == "max_contacts"
    assert in_dnc is True


def test_outreach_blocked_within_cooldown():
    db, client, name = _fresh_db()

    async def _go():
        try:
            await db.outreach_history.insert_one({
                "lead_id": "cool-1", "phone_normalized": "14165550222",
                "dispatched_at": datetime.now(timezone.utc),
            })
            return await can_contact_lead(db, {
                "lead_id": "cool-1", "phone": "+14165550222",
                "business_name": "Cool Co", "city": "Toronto",
            })
        finally:
            await client.drop_database(name)

    allowed, reason = _run(_go())
    assert allowed is False
    assert "cooldown" in reason


def test_outreach_passes_for_fresh_lead():
    db, client, name = _fresh_db()

    async def _go():
        try:
            return await can_contact_lead(db, {
                "lead_id": "fresh-1", "phone": "+14165550333",
                "business_name": "Fresh Co", "city": "Toronto",
            })
        finally:
            await client.drop_database(name)

    allowed, reason = _run(_go())
    assert allowed is True
    assert reason == "ok"


def test_dnc_blocks_outreach():
    db, client, name = _fresh_db()

    async def _go():
        try:
            await add_to_dnc(db, phone="+14165550444", reason="manual")
            return await can_contact_lead(db, {
                "lead_id": "dnc-1", "phone": "+14165550444",
                "business_name": "Test Co", "city": "Toronto",
            })
        finally:
            await client.drop_database(name)

    allowed, reason = _run(_go())
    assert allowed is False
    assert reason == "dnc_phone"


# ─────────────────────────────────────────────────────────────────────
# DNC
# ─────────────────────────────────────────────────────────────────────
def test_stop_reply_adds_to_dnc():
    db, client, name = _fresh_db()

    async def _go():
        try:
            await process_stop_reply(db, phone="+14165550555")
            return await is_in_dnc(db, phone="+14165550555")
        finally:
            await client.drop_database(name)

    assert _run(_go()) is True


def test_dnc_email_works():
    db, client, name = _fresh_db()

    async def _go():
        try:
            await add_to_dnc(db, email="optout@example.com", reason="manual")
            return await is_in_dnc(db, email="optout@example.com")
        finally:
            await client.drop_database(name)

    assert _run(_go()) is True


# ─────────────────────────────────────────────────────────────────────
# find_existing_site
# ─────────────────────────────────────────────────────────────────────
def test_site_not_rebuilt_if_exists():
    db, client, name = _fresh_db()

    async def _go():
        try:
            await db.auto_built_sites.insert_one({
                "site_id": "site-001", "lead_id": "lead-A",
                "business_name": "Seed Co",
                "phone_normalized": "14165550666",
                "preview_url": "https://aurem.live/preview/site-001",
                "slug": "abc",
                "status": "rendered",
                "ts": datetime.now(timezone.utc),
            })
            return await find_existing_site(db, {
                "phone": "+14165550666", "business_name": "Different Name",
                "city": "Toronto",
            })
        finally:
            await client.drop_database(name)

    found = _run(_go())
    assert found is not None
    assert found["site_id"] == "site-001"


def test_find_existing_site_no_match():
    db, client, name = _fresh_db()

    async def _go():
        try:
            return await find_existing_site(db, {
                "phone": "+14165559876", "business_name": "Ghost Co",
                "city": "Nowhere",
            })
        finally:
            await client.drop_database(name)

    assert _run(_go()) is None


# ─────────────────────────────────────────────────────────────────────
# ensure_dedup_indexes
# ─────────────────────────────────────────────────────────────────────
def test_ensure_dedup_indexes_creates():
    db, client, name = _fresh_db()

    async def _go():
        try:
            await ensure_dedup_indexes(db)
            return await db.campaign_leads.index_information()
        finally:
            await client.drop_database(name)

    info = _run(_go())
    assert "phone_norm" in info
    assert "website_domain" in info


# ─────────────────────────────────────────────────────────────────────
# reject_duplicate logging
# ─────────────────────────────────────────────────────────────────────
def test_reject_duplicate_logs_to_scout_rejected():
    db, client, name = _fresh_db()

    async def _go():
        try:
            await reject_duplicate(db, {
                "business_name": "Dup Co", "city": "Toronto",
                "phone": "+14165550777",
            }, "phone_match")
            return await db.scout_rejected.count_documents(
                {"reason": "phone_match"},
            )
        finally:
            await client.drop_database(name)

    assert _run(_go()) == 1
