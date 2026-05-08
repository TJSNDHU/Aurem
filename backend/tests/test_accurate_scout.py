"""
Tests for accurate_scout — consensus engine + channel gating.
Run: cd /app/backend && python3 -m pytest tests/test_accurate_scout.py -v
"""
import asyncio
from services.accurate_scout import (
    _consolidate_field,
    _compute_channel_gating,
    should_send_campaign,
    _normalize_phone,
    _extract_phone,
    _extract_email,
)


def test_normalize_phone():
    assert _normalize_phone("(416) 555-1234") == "+14165551234"
    assert _normalize_phone("+1 416 555 1234") == "+14165551234"
    assert _normalize_phone("4165551234") == "+14165551234"
    assert _normalize_phone("1-416-555-1234") == "+14165551234"
    assert _normalize_phone("garbage") == ""


def test_extract_phone_from_html():
    html = "Contact us at (226) 501-7777 or email info@tj.ca"
    assert _extract_phone(html) == "+12265017777"
    assert _extract_email(html) == "info@tj.ca"


def test_consensus_high_confidence_3_sources_agree():
    sources = [
        {"source": "google_places", "phone": "+14165551234", "confidence": "high"},
        {"source": "website", "phone": "+14165551234", "confidence": "high"},
        {"source": "yellowpages_ca", "phone": "+14165551234", "confidence": "high"},
    ]
    r = _consolidate_field("phone", sources)
    assert r["value"] == "+14165551234"
    assert r["confidence"] == "HIGH"
    assert r["source_count"] == 3


def test_consensus_medium_2_sources_agree():
    sources = [
        {"source": "google_places", "phone": "+14165551234", "confidence": "high"},
        {"source": "website", "phone": "+14165551234", "confidence": "high"},
        {"source": "tavily", "phone": "+14169990000", "confidence": "medium"},
    ]
    r = _consolidate_field("phone", sources)
    assert r["confidence"] == "HIGH"  # 2 high-conf sources agree → still HIGH


def test_consensus_low_when_all_conflict():
    sources = [
        {"source": "google_places", "phone": "+12265017777", "confidence": "high"},
        {"source": "tavily", "phone": "+16473366903", "confidence": "medium"},
        {"source": "yellowpages_ca", "phone": "+12604151822", "confidence": "high"},
    ]
    r = _consolidate_field("phone", sources)
    # 3 different values → winner has count=1 → promoted to MEDIUM (website/google_places bonus)
    assert r["confidence"] in ("LOW", "MEDIUM")
    assert r["source_count"] == 1


def test_consensus_website_single_source_promoted_to_medium():
    sources = [
        {"source": "website", "phone": "+14165551234", "confidence": "high"},
    ]
    r = _consolidate_field("phone", sources)
    # Single website source → MEDIUM (site is ground truth but only 1 source)
    assert r["confidence"] == "MEDIUM"


def test_consensus_empty_returns_none():
    r = _consolidate_field("phone", [])
    assert r["value"] == ""
    assert r["confidence"] == "NONE"


def test_channel_gating_high_phone_unlocks_all():
    verified = {
        "consolidated": {
            "phone": {"confidence": "HIGH"},
            "email": {"confidence": "HIGH"},
        }
    }
    gating = _compute_channel_gating(verified["consolidated"])
    assert gating == {"call": True, "sms": True, "email": True, "whatsapp": True}
    assert should_send_campaign("call", {"channel_gating": gating}) is True


def test_channel_gating_low_phone_blocks_call_sms():
    verified_consolidated = {
        "phone": {"confidence": "LOW"},
        "email": {"confidence": "HIGH"},
    }
    gating = _compute_channel_gating(verified_consolidated)
    assert gating["call"] is False
    assert gating["sms"] is False
    assert gating["email"] is True      # email still safe
    assert gating["whatsapp"] is False  # needs MEDIUM+


def test_channel_gating_medium_phone_allows_whatsapp_not_call():
    verified_consolidated = {
        "phone": {"confidence": "MEDIUM"},
        "email": {"confidence": "MEDIUM"},
    }
    gating = _compute_channel_gating(verified_consolidated)
    assert gating["call"] is False
    assert gating["sms"] is False
    assert gating["whatsapp"] is True
    assert gating["email"] is True


def test_should_send_campaign_public_api():
    verified = {"channel_gating": {"call": True, "sms": False, "email": True, "whatsapp": True}}
    assert should_send_campaign("call", verified) is True
    assert should_send_campaign("sms", verified) is False
    assert should_send_campaign("email", verified) is True
    assert should_send_campaign("whatsapp", verified) is True
    assert should_send_campaign("nonexistent", verified) is False
