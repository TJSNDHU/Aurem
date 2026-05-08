"""CASL compliance regression — iter 282ak (Prompt 8, Task D).

Asserts every composer output path (LLM-hit + fallback) remains CASL-compliant.
Skipped test paths: LinkedIn hashtag requirement is only checked when the
LLM path actually fires (fallbacks ship a baked-in hashtag pair for
LinkedIn so the test is still meaningful in offline mode).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.outreach_composer import (  # noqa: E402
    FALLBACK_MESSAGES, compose_outreach_sync,
)

OPT_OUT_PHRASES = [
    "reply stop", "text stop", "opt out",
    "unsubscribe", "opt-out", "txt stop",
    "stop to opt",
]

MOCK_LEAD = {
    "business_name": "Test Plumbing Co",
    "city":          "Mississauga",
    "province":      "ON",
    "category":      "plumber",
    "yelp_rating":   4.2,
    "review_count":  35,
    "has_website":   False,
    "lead_id":       "casl-test-001",
}


def has_opt_out(body: str) -> bool:
    return any(p in (body or "").lower() for p in OPT_OUT_PHRASES)


def test_email_has_opt_out():
    r = compose_outreach_sync(MOCK_LEAD, "email", 1)
    assert has_opt_out(r["body"]), f"CASL FAIL email: {r['body']!r}"


def test_sms_has_opt_out():
    r = compose_outreach_sync(MOCK_LEAD, "sms", 1)
    assert has_opt_out(r["body"]), f"CASL FAIL sms: {r['body']!r}"


def test_sms_under_160_chars():
    r = compose_outreach_sync(MOCK_LEAD, "sms", 1)
    assert len(r["body"]) <= 160, f"SMS {len(r['body'])}>160: {r['body']!r}"


def test_whatsapp_b2b_context():
    r = compose_outreach_sync(MOCK_LEAD, "whatsapp", 1)
    body = (r["body"] or "").lower()
    is_b2b = "test plumbing" in body or "local" in body
    assert is_b2b or has_opt_out(r["body"])


def test_linkedin_has_hashtags():
    r = compose_outreach_sync(MOCK_LEAD, "linkedin", 1)
    assert "#" in r["body"], f"LinkedIn missing hashtags: {r['body']!r}"


def test_fallback_email_casl_compliant():
    assert has_opt_out(FALLBACK_MESSAGES["email"]["body"])


def test_fallback_sms_casl_compliant():
    assert has_opt_out(FALLBACK_MESSAGES["sms"]["body"])


def test_fallback_linkedin_has_hashtag():
    assert "#" in FALLBACK_MESSAGES["linkedin"]["body"]
