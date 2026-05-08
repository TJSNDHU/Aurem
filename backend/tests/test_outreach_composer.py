"""
Outreach Composer tests — iter 282ai (Prompt 6).

When EMERGENT_LLM_KEY is present we hit the real Claude Sonnet 4.5 endpoint
via emergentintegrations. When the key is missing (or the LLM times out at
test time) the composer falls back to the hardcoded table and we validate
only the fallback contract.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.outreach_composer import compose_outreach_sync  # noqa: E402

MOCK_LEAD = {
    "business_name": "Test Plumbing Co",
    "city": "Mississauga",
    "province": "ON",
    "category": "plumber",
    "yelp_rating": 4.2,
    "review_count": 35,
    "has_website": False,
    "lead_id": "test-123",
}

_LLM_ON = bool(os.environ.get("EMERGENT_LLM_KEY", "").strip())


def test_compose_returns_required_fields():
    result = compose_outreach_sync(MOCK_LEAD, "sms", 1)
    for k in ("body", "channel", "fallback_used", "composed_at",
               "subject", "tone_used", "model"):
        assert k in result, f"missing key: {k}"
    assert result["channel"] == "sms"


def test_sms_body_under_160_chars():
    result = compose_outreach_sync(MOCK_LEAD, "sms", 1)
    assert len(result["body"]) <= 160, \
        f"SMS body {len(result['body'])}>160 chars: {result['body']!r}"


def test_email_has_subject():
    result = compose_outreach_sync(MOCK_LEAD, "email", 1)
    assert result.get("subject") is not None
    assert result.get("body")


def test_fallback_fires_on_bad_lead():
    # Composer should never raise — even with totally empty lead dict.
    result = compose_outreach_sync({}, "sms", 1)
    assert result["body"] is not None
    assert len(result["body"]) > 0


def test_step3_is_different_from_step1():
    if not _LLM_ON:
        pytest.skip("EMERGENT_LLM_KEY not set — fallback bodies are identical per channel, test is LLM-only")
    r1 = compose_outreach_sync(MOCK_LEAD, "email", 1)
    r3 = compose_outreach_sync(MOCK_LEAD, "email", 3)
    # LLM non-determinism makes EXACT inequality likely but not guaranteed.
    # We check at least one of {subject, body} differs, OR both are non-fallback.
    if r1["fallback_used"] or r3["fallback_used"]:
        pytest.skip("one or both composed via fallback — cannot compare LLM outputs")
    assert (r1["body"] != r3["body"]) or (r1.get("subject") != r3.get("subject")), \
        "step 1 and step 3 produced identical outputs — prompt differentiation failed"
