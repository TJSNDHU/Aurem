"""
iter 282al-26 — Tests for services.sovereign_truth (founder anti-sycophancy)
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, length=None):
        return self._rows


def _mk_db(**collections):
    db = MagicMock()
    for name, rows in collections.items():
        coll = MagicMock()
        coll.find = MagicMock(return_value=_Cursor(rows))
        setattr(db, name, coll)
    # Always-present admin_users
    if not hasattr(db, "admin_users") or isinstance(db.admin_users, type(None)):
        db.admin_users = MagicMock()
    return db


# ─────────────── is_founder ───────────────
@pytest.mark.asyncio
async def test_is_founder_by_email_allowlist():
    from services.sovereign_truth import is_founder
    assert await is_founder(None, "teji.ss1986@gmail.com", None) is True
    assert await is_founder(None, "TEJI.ss1986@gmail.com", None) is True
    assert await is_founder(None, "random@example.com", None) is False


@pytest.mark.asyncio
async def test_is_founder_by_db_role():
    from services.sovereign_truth import is_founder
    db = MagicMock()
    db.admin_users.find_one = AsyncMock(return_value={
        "email": "other@example.com", "role": "founder",
    })
    assert await is_founder("uid-1", None, db) is True


@pytest.mark.asyncio
async def test_is_founder_no_db_no_email_returns_false():
    from services.sovereign_truth import is_founder
    assert await is_founder("uid-x", None, None) is False


# ─────────────── prefs ───────────────
@pytest.mark.asyncio
async def test_get_founder_prefs_defaults_off():
    from services.sovereign_truth import get_founder_prefs
    db = MagicMock()
    db.admin_users.find_one = AsyncMock(return_value=None)
    out = await get_founder_prefs(db, "teji.ss1986@gmail.com")
    assert out["sovereign_truth"] is False


@pytest.mark.asyncio
async def test_get_founder_prefs_reads_stored_value():
    from services.sovereign_truth import get_founder_prefs
    db = MagicMock()
    db.admin_users.find_one = AsyncMock(return_value={
        "founder_prefs": {"sovereign_truth": True},
    })
    out = await get_founder_prefs(db, "teji.ss1986@gmail.com")
    assert out["sovereign_truth"] is True


@pytest.mark.asyncio
async def test_set_founder_prefs_upserts_bool():
    from services.sovereign_truth import set_founder_prefs
    db = MagicMock()
    db.admin_users.update_one = AsyncMock(return_value=None)
    res = await set_founder_prefs(db, "teji.ss1986@gmail.com", sovereign_truth=True)
    assert res["ok"] is True
    db.admin_users.update_one.assert_awaited_once()
    _q, upd = db.admin_users.update_one.call_args[0]
    kwargs = db.admin_users.update_one.call_args.kwargs
    assert upd["$set"]["founder_prefs.sovereign_truth"] is True
    assert kwargs.get("upsert") is True
    # Email filter path when identity looks like an email
    assert _q == {"email": "teji.ss1986@gmail.com"}


# ─────────────── Strategy intent detector ───────────────
def test_is_strategy_intent_canonical_intents():
    from services.sovereign_truth import is_strategy_intent
    for intent in ("outreach", "close", "casl", "followup", "strategy"):
        assert is_strategy_intent(intent, "") is True


def test_is_strategy_intent_by_language_only():
    from services.sovereign_truth import is_strategy_intent
    assert is_strategy_intent("general", "should I launch this new product?")
    assert is_strategy_intent("general", "approve this email blast")
    assert is_strategy_intent("general", "worth it to hire a BDR now?")
    assert is_strategy_intent("general", "pricing for the new plan")


def test_is_strategy_intent_skips_factual_questions():
    from services.sovereign_truth import is_strategy_intent
    assert is_strategy_intent("general", "what is the capital of France?") is False
    assert is_strategy_intent("scan", "audit this website") is False
    assert is_strategy_intent("greeting", "hi") is False


# ─────────────── Truth block — no data = harmless ───────────────
@pytest.mark.asyncio
async def test_truth_block_no_data_returns_aligns_message():
    from services.sovereign_truth import build_truth_block
    db = _mk_db(
        outreach_history=[], casl_scores=[], site_audits=[],
    )
    block = await build_truth_block(db, "should I launch?", "strategy", {})
    assert "--- SOVEREIGN TRUTH ---" in block
    assert "aligns" in block.lower()
    assert "no objective friction" in block.lower()


@pytest.mark.asyncio
async def test_truth_block_no_db_returns_empty():
    from services.sovereign_truth import build_truth_block
    assert await build_truth_block(None, "x", "outreach", {}) == ""


# ─────────────── Truth block — real data critique ───────────────
@pytest.mark.asyncio
async def test_truth_block_flags_low_reply_rate():
    from services.sovereign_truth import build_truth_block
    # 5 replies / 100 sends = 5% — below 10% threshold for outreach
    rows = [{"reply_received": i < 5} for i in range(100)]
    db = _mk_db(
        outreach_history=rows, casl_scores=[], site_audits=[],
    )
    block = await build_truth_block(db, "write outreach", "outreach", {})
    assert "reply rate" in block.lower()
    assert "5.0%" in block
    # Not small-sample (n=100 > 20)
    assert "small sample" not in block.lower()


@pytest.mark.asyncio
async def test_truth_block_prefixes_small_sample_when_below_20():
    from services.sovereign_truth import build_truth_block
    rows = [{"reply_received": False} for _ in range(10)]
    db = _mk_db(
        outreach_history=rows, casl_scores=[], site_audits=[],
    )
    block = await build_truth_block(db, "outreach email", "outreach", {})
    assert "small sample" in block.lower()


@pytest.mark.asyncio
async def test_truth_block_flags_casl_fail_rate():
    from services.sovereign_truth import build_truth_block
    # 70 pass / 100 total = 70% — below 90% threshold
    rows = [{"passed": i < 70} for i in range(100)]
    db = _mk_db(
        outreach_history=[], casl_scores=rows, site_audits=[],
    )
    block = await build_truth_block(db, "should I send this?", "close", {})
    assert "CASL" in block
    assert "70.0%" in block


@pytest.mark.asyncio
async def test_truth_block_includes_path_forward_when_critique_exists():
    from services.sovereign_truth import build_truth_block
    rows = [{"passed": False} for _ in range(30)]
    db = _mk_db(
        outreach_history=[], casl_scores=rows, site_audits=[],
    )
    block = await build_truth_block(db, "approve this", "close", {})
    assert "next move" in block.lower()


# ─────────────── augment_response ───────────────
def test_augment_response_appends_when_not_present():
    from services.sovereign_truth import augment_response
    out = augment_response("Hi Mike, here is the plan.", "\n\n--- SOVEREIGN TRUTH ---\nX\n")
    assert out.endswith("--- SOVEREIGN TRUTH ---\nX\n")


def test_augment_response_idempotent_when_already_present():
    from services.sovereign_truth import augment_response
    original = "Plan.\n\n--- SOVEREIGN TRUTH ---\nX"
    out = augment_response(original, "\n\n--- SOVEREIGN TRUTH ---\nY\n")
    assert out == original


def test_augment_response_empty_truth_block_returns_original():
    from services.sovereign_truth import augment_response
    assert augment_response("hello", "") == "hello"
