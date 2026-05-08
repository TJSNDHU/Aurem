"""
iter 282al-15 — Tests for services/website_repair_service.py

Covers:
  - calculate_site_score: thin content + no phone + full
  - extract_issues: flags missing phone, services, form, mobile
  - get_cta_type thresholds
  - audit_existing_site returns error without website
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock

from services.website_repair_service import (
    calculate_site_score, extract_issues, get_cta_type,
    audit_existing_site,
)


# ─────────── calculate_site_score ───────────
def test_score_low_thin_content():
    scan = {"content": "Hi", "contacts": {}, "brand": {}}
    assert calculate_site_score(scan) < 60


def test_score_full_site_is_high():
    scan = {
        "content": "x" * 500,
        "contacts": {
            "phone": "416-555-0100",
            "services": ["plumbing", "drain cleaning"],
        },
        "brand": {"logo_url": "https://example.ca/l.png"},
        "mobile": {"viewport": True, "responsive": True},
    }
    assert calculate_site_score(scan) >= 80


def test_score_floors_at_5():
    scan = {"content": "", "contacts": {}, "brand": {}, "mobile": {}}
    assert calculate_site_score(scan) >= 5
    assert calculate_site_score(scan) <= 50


# ─────────── extract_issues ───────────
def test_extract_issues_no_phone_flagged():
    scan = {"contacts": {}, "content": "x" * 300, "mobile": {"viewport": True}}
    issues = extract_issues(scan, {"business_name": "ACME"})
    assert any("phone" in i["title"].lower() for i in issues)


def test_extract_issues_no_services_flagged():
    scan = {
        "contacts": {"phone": "416-555-0100"},
        "content": "x" * 300,
        "mobile": {"viewport": True},
    }
    issues = extract_issues(scan, {})
    assert any("service" in i["title"].lower() for i in issues)


def test_extract_issues_missing_mobile_is_critical():
    scan = {
        "contacts": {"phone": "416-555-0100", "services": ["x"]},
        "content": "x" * 300,
        "brand": {"logo_url": "l"},
    }
    issues = extract_issues(scan, {})
    mobile = [i for i in issues if "mobile" in i["title"].lower()]
    assert mobile, "mobile issue should be present"
    assert mobile[0]["priority"] == "critical"


# ─────────── get_cta_type ───────────
def test_cta_repair_for_low_score():
    assert get_cta_type(45) == "repair"


def test_cta_tuneup_for_mid_score():
    assert get_cta_type(70) == "tuneup"


def test_cta_widget_for_high_score():
    assert get_cta_type(85) == "widget"


def test_cta_generic_for_none_or_zero():
    # iter 282al-18 — align with router behaviour: no audit yet = "generic"
    assert get_cta_type(None) == "generic"  # type: ignore[arg-type]
    assert get_cta_type(0) == "generic"


# ─────────── audit_existing_site ───────────
@pytest.mark.asyncio
async def test_audit_returns_error_without_website():
    out = await audit_existing_site(MagicMock(), {"business_name": "ACME"})
    assert out.get("error") == "no_website"


@pytest.mark.asyncio
async def test_audit_persists_and_returns_full_doc(monkeypatch):
    # Stub scan_website to return a controlled payload
    async def _fake_scan(url, db):
        return {
            "content": "x" * 100,  # thin → score hit
            "contacts": {},
            "brand": {},
            "mobile": {},
        }

    import services.webclaw_client as wc
    monkeypatch.setattr(wc, "scan_website", _fake_scan, raising=False)

    mock_db = MagicMock()
    mock_db.site_audits.insert_one = AsyncMock(return_value=None)

    out = await audit_existing_site(
        mock_db,
        {"_id": "lead_1", "business_name": "ACME", "website": "https://acme.ca"},
    )
    assert "overall_score" in out
    assert out["overall_score"] <= 60
    assert out["website_url"] == "https://acme.ca"
    assert out["cta_type"] == "repair"
    assert isinstance(out["issues"], list) and len(out["issues"]) > 0
    mock_db.site_audits.insert_one.assert_awaited_once()
