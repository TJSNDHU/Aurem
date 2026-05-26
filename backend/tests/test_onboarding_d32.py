"""
test_onboarding_d32.py — iter D-32

Covers:
  • Manifest-patch balanced-brace extractor handles nested {}
  • Progress / phase regex picks up plain `progress: 0.42` lines
  • Wallet debit returns ok=False when balance is too low (no decrement)
"""
import asyncio
import os
import pytest

from motor.motor_asyncio import AsyncIOMotorClient

from services.onboarding_wallet import (
    _extract_manifest_json,
    _PROGRESS_RE,
    _PHASE_RE,
    debit_for_chat_turn,
    apply_progress_from_reply,
)


def test_manifest_patch_balanced_braces():
    reply = """
hello there
MANIFEST_PATCH: {"title":"X","sections":[{"kind":"hero","text":"hi"},{"kind":"cta","text":"go"}]}
NEXT_STEPS: ["a","b","c"]
""".strip()
    p = _extract_manifest_json(reply)
    assert p is not None
    assert p["title"] == "X"
    assert len(p["sections"]) == 2
    assert p["sections"][1]["kind"] == "cta"


def test_manifest_patch_returns_none_on_garbage():
    assert _extract_manifest_json("no patch in here") is None
    # malformed JSON
    assert _extract_manifest_json("MANIFEST_PATCH: {bad json") is None


def test_progress_regex():
    m = _PROGRESS_RE.search("Some text\nprogress: 0.42\nmore text")
    assert m
    assert float(m.group(1)) == 0.42

    # Bounded — > 1.0 still matches the float but the caller validates
    m2 = _PROGRESS_RE.search("progress: 0.99")
    assert m2 and float(m2.group(1)) == 0.99


def test_phase_regex():
    m = _PHASE_RE.search("blah blah\nphase: building\netc")
    assert m
    assert m.group(1) == "building"


@pytest.mark.asyncio
async def test_debit_fails_when_balance_zero():
    """Drains the wallet for a synthetic user, hits debit_for_chat_turn,
    asserts ok=False + balance=0. Restores afterwards."""
    mc = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = mc["aurem_db"]
    from routers import onboarding_flow_router as onb
    onb._db = db
    test_uid = "test_d32_uid"
    await db.onboarding_token_wallets.delete_many({"user_id": test_uid})
    await db.onboarding_token_wallets.insert_one({
        "user_id": test_uid, "balance": 0,
        "lifetime_earned": 0, "lifetime_spent": 0, "ledger": [],
    })
    try:
        r = await debit_for_chat_turn(user_id=test_uid,
                                       project_id="test", model_tier="cheap")
        assert r["ok"] is False
        assert r["balance"] == 0
        assert r["cost"] == 1
        r2 = await debit_for_chat_turn(user_id=test_uid,
                                        project_id="test", model_tier="frontier")
        assert r2["ok"] is False
        assert r2["cost"] == 5
    finally:
        await db.onboarding_token_wallets.delete_many({"user_id": test_uid})


@pytest.mark.asyncio
async def test_apply_progress_no_markers_returns_none():
    mc = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = mc["aurem_db"]
    from routers import onboarding_flow_router as onb
    onb._db = db
    r = await apply_progress_from_reply(
        user_id="nobody", project_id="nope",
        reply_text="just a regular reply with no markers",
    )
    assert r is None
