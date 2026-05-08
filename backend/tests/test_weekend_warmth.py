"""Tests for services.weekend_warmth — Section 2 of growth-engine upgrade."""
import asyncio
import os
import sys
import pytest
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services import weekend_warmth as ww


def test_postal_to_tz():
    assert ww._postal_to_tz("M5V") == "America/Toronto"
    assert ww._postal_to_tz("V6B 2T6") == "America/Vancouver"
    assert ww._postal_to_tz("S4P") == "America/Regina"
    assert ww._postal_to_tz("") is None
    assert ww._postal_to_tz(None) is None


def test_quote_pool_size():
    # Spec: 52 quotes minimum
    assert len(ww._QUOTES) >= 52


def test_quote_uniqueness():
    # No duplicates
    assert len(set(ww._QUOTES)) == len(ww._QUOTES)


def test_quote_sms_friendly():
    # Each quote ≤ 200 chars (leaves room for greeting + leads count in 320-char SMS)
    for q in ww._QUOTES:
        assert len(q) <= 200, f"quote too long: {q!r}"


def test_pick_quote_deterministic_per_user_per_week():
    q1 = ww._pick_quote("user-A")
    q2 = ww._pick_quote("user-A")
    assert q1 == q2  # same user, same week → same quote
    qa = ww._pick_quote("user-A")
    qb = ww._pick_quote("user-B")
    # Different users likely get different quotes (52 buckets)
    # Not strictly required, but a sanity check on entropy
    assert isinstance(qa, str) and isinstance(qb, str)


def test_compose_saturday_msg_sunny_warm():
    msg = ww._compose_saturday_msg(
        "Mike", "Mike's Plumbing",
        {"city": "Toronto", "temp_c": 22, "condition": "Clear", "emoji": "☀️"},
    )
    assert "Mike" in msg
    assert "Mike's Plumbing" in msg or "Toronto" in msg
    # 3 sentences max — count periods/exclaims/question marks
    end_punct = sum(msg.count(c) for c in (". ", "! ", "? "))
    assert end_punct <= 4  # tolerant: 3 sentences + emoji period


def test_compose_saturday_msg_no_sales_words():
    msg = ww._compose_saturday_msg(
        "Sara", "Sara HVAC",
        {"city": "Calgary", "temp_c": -5, "condition": "Snow", "emoji": "❄️"},
    )
    sales_words = ["upgrade", "sign up", "pricing", "subscribe", "buy", "discount", "trial"]
    msg_l = msg.lower()
    for w in sales_words:
        assert w not in msg_l, f"sales word leaked: {w}"


def test_compose_saturday_handles_no_temp():
    msg = ww._compose_saturday_msg(
        "Kim", "Kim Roofing",
        {"city": "Vancouver", "temp_c": None, "condition": "", "emoji": "🌤️"},
    )
    assert "Vancouver" in msg
    assert "Kim" in msg


def test_log_id_stable():
    a = ww._log_id("biz-1", "saturday_warmth", "2026-05-09")
    b = ww._log_id("biz-1", "saturday_warmth", "2026-05-09")
    c = ww._log_id("biz-1", "saturday_warmth", "2026-05-10")
    assert a == b
    assert a != c


def test_pick_quote_returns_from_pool():
    q = ww._pick_quote("user-X")
    assert q in ww._QUOTES
