"""Tests for services.lead_sort — Section 4 of growth-engine upgrade."""
import asyncio
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services import lead_sort as ls

# Disable expensive net checks in tests by default
os.environ["SORT_TWILIO_LOOKUP"] = "false"
os.environ["SORT_MX_LOOKUP"] = "false"


# ── pure helpers ──────────────────────────────────────────────────────

def test_e164_normaliser():
    assert ls._to_e164("416-555-1234") == "+14165551234"
    assert ls._to_e164("4165551234") == "+14165551234"
    assert ls._to_e164("+14165551234") == "+14165551234"
    assert ls._to_e164("garbage") == ""
    assert ls._to_e164("") == ""


def test_email_validate_syntax():
    res = asyncio.run(ls._validate_email("good@biz.ca"))
    assert res["syntax_ok"] is True
    assert res["mx_ok"] is True  # MX disabled → trust syntax
    res = asyncio.run(ls._validate_email("bad-email"))
    assert res["syntax_ok"] is False
    res = asyncio.run(ls._validate_email(None))
    assert res["present"] is False


def test_phone_validate_no_lookup():
    # SORT_TWILIO_LOOKUP=false → trust E.164 syntax
    res = asyncio.run(ls._validate_phone("416-555-1234"))
    assert res["valid"] is True
    assert res["e164"] == "+14165551234"
    res = asyncio.run(ls._validate_phone("12345"))
    assert res["e164"] == ""
    assert res["valid"] is False


# ── classification ────────────────────────────────────────────────────

def test_classify_has_website():
    v = {
        "email": {"syntax_ok": True, "mx_ok": True, "present": True},
        "phone": {"valid": True, "e164": "+14165551234", "is_landline": False, "present": True},
        "website": {"present": True, "ok": True, "is_facebook": False, "reason": ""},
    }
    queue, reasons = ls._classify_queue({}, v)
    assert queue == "has_website"
    assert reasons == []


def test_classify_no_website_when_thin():
    v = {
        "email": {"syntax_ok": True, "mx_ok": True, "present": True},
        "phone": {"valid": True, "e164": "+14165551234", "is_landline": False, "present": True},
        "website": {"present": True, "ok": False, "is_facebook": False, "reason": "thin_content_120b"},
    }
    queue, reasons = ls._classify_queue({}, v)
    assert queue == "no_website"


def test_classify_facebook():
    v = {
        "email": {"syntax_ok": True, "mx_ok": True, "present": True},
        "phone": {"valid": True, "e164": "+14165551234", "is_landline": False, "present": True},
        "website": {"present": True, "ok": False, "is_facebook": True, "reason": "facebook_only"},
    }
    queue, reasons = ls._classify_queue({}, v)
    assert queue == "facebook"


def test_classify_rejected_no_contact():
    v = {
        "email": {"syntax_ok": False, "mx_ok": False, "present": False},
        "phone": {"valid": False, "e164": "", "is_landline": False, "present": False},
        "website": {"present": True, "ok": True, "is_facebook": False, "reason": ""},
    }
    queue, reasons = ls._classify_queue({}, v)
    assert queue == "rejected"
    assert "no_contact_channel" in reasons


def test_classify_landline_flagged_email_only():
    lead = {}
    v = {
        "email": {"syntax_ok": True, "mx_ok": True, "present": True},
        "phone": {"valid": True, "e164": "+14165551234", "type": "landline",
                  "is_landline": True, "present": True},
        "website": {"present": True, "ok": True, "is_facebook": False, "reason": ""},
    }
    queue, _ = ls._classify_queue(lead, v)
    assert queue == "has_website"
    assert lead["sort_email_only"] is True  # blast must use email channel


# ── full flow ─────────────────────────────────────────────────────────

def test_sort_leads_full_flow():
    leads = [
        # has_website
        {"name": "A HVAC", "score": 9, "phone": "416-555-1100",
         "email": "a@hvac.ca", "website": "https://example.com"},
        # facebook only
        {"name": "FB Plumber", "score": 8, "phone": "416-555-1200",
         "email": "p@x.ca", "website": "https://facebook.com/plumberx"},
        # no website (no website at all)
        {"name": "NoWeb Roofer", "score": 7, "phone": "416-555-1300",
         "email": "r@x.ca", "website": ""},
        # rejected — no contact channel & no website
        {"name": "Ghost Co", "score": 6, "phone": "", "email": "", "website": ""},
    ]
    # Stub website fetch so test never hits network
    import services.lead_sort as mod

    async def _fake_validate_website(lead):
        url = (lead.get("website") or "").strip()
        if not url:
            return {"present": False, "url": "", "is_facebook": False,
                    "ok": False, "reason": "missing"}
        if "facebook.com" in url:
            return {"present": True, "url": url, "is_facebook": True,
                    "ok": False, "reason": "facebook_only"}
        return {"present": True, "url": url, "is_facebook": False,
                "ok": True, "status": 200, "content_len": 5000, "reason": ""}
    mod._validate_website = _fake_validate_website

    out = asyncio.run(ls.sort_leads(leads, db=None))
    assert len(out["has_website"]) == 1
    assert out["has_website"][0]["name"] == "A HVAC"
    assert len(out["facebook"]) == 1
    assert len(out["no_website"]) == 1
    assert len(out["rejected"]) == 1
    # Each lead got the audit fields
    for L in leads:
        assert "sort_queue" in L
        assert "sort_validation" in L
        assert "sort_at" in L


def test_sort_within_queue_score_desc():
    leads = [
        {"name": "Low", "score": 4, "phone": "416-555-2200", "email": "l@x.ca",
         "website": "https://example.com"},
        {"name": "Hi",  "score": 9, "phone": "416-555-2201", "email": "h@x.ca",
         "website": "https://example.com"},
        {"name": "Mid", "score": 7, "phone": "416-555-2202", "email": "m@x.ca",
         "website": "https://example.com"},
    ]
    import services.lead_sort as mod
    async def _ok_web(lead):
        return {"present": True, "url": lead.get("website",""), "is_facebook": False,
                "ok": True, "status": 200, "content_len": 5000, "reason": ""}
    mod._validate_website = _ok_web

    out = asyncio.run(ls.sort_leads(leads, db=None))
    scores = [L["score"] for L in out["has_website"]]
    assert scores == sorted(scores, reverse=True)
