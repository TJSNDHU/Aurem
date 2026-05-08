"""Industry slang tests — iter 282al-6."""
from __future__ import annotations

from services.industry_slang import INDUSTRY_SLANG, get_industry_context


def test_plumber_direct_match():
    assert get_industry_context("plumber") is INDUSTRY_SLANG["plumber"]


def test_hvac_fuzzy():
    r = get_industry_context("air conditioning repair")
    assert r is INDUSTRY_SLANG["hvac"]
    r = get_industry_context("furnace install")
    assert r is INDUSTRY_SLANG["hvac"]


def test_skincare_clinic_matches():
    r = get_industry_context("skin care clinic")
    assert r is INDUSTRY_SLANG["skincare_clinic"]
    r = get_industry_context("med spa")
    assert r is INDUSTRY_SLANG["skincare_clinic"]
    r = get_industry_context("aesthetic clinic")
    assert r is INDUSTRY_SLANG["skincare_clinic"]


def test_pdrn_in_skincare_services():
    services = INDUSTRY_SLANG["skincare_clinic"]["services"]
    assert any("PDRN" in s for s in services)
    assert any("biostimulator" in s for s in services)


def test_skincare_credibility_note_present():
    note = INDUSTRY_SLANG["skincare_clinic"].get("credibility_note", "")
    assert "PDRN" in note
    assert "biostimulator" in note
    # Reroots is NOT named directly — only industry credibility implied
    assert "Reroots" not in note


def test_auto_body_matches():
    r = get_industry_context("auto body shop")
    assert r is INDUSTRY_SLANG["auto_body"]
    r = get_industry_context("collision repair")
    assert r is INDUSTRY_SLANG["auto_body"]


def test_landscaper_fuzzy():
    assert get_industry_context("lawn care") is INDUSTRY_SLANG["landscaper"]
    assert get_industry_context("snow removal") is INDUSTRY_SLANG["landscaper"]


def test_dental_fuzzy():
    assert get_industry_context("orthodontist") is INDUSTRY_SLANG["dental"]
    assert get_industry_context("dental clinic") is INDUSTRY_SLANG["dental"]


def test_unknown_returns_general():
    assert get_industry_context("pottery studio") is INDUSTRY_SLANG["general"]
    assert get_industry_context("") is INDUSTRY_SLANG["general"]


def test_every_industry_has_required_keys():
    """Defensive — composer prompt builder reads these keys."""
    required = ("pain_points", "services", "urgency_hook", "search_terms")
    for industry, slang in INDUSTRY_SLANG.items():
        for k in required:
            assert k in slang, f"{industry} missing {k}"
        assert slang["pain_points"], f"{industry} pain_points empty"
        assert slang["urgency_hook"], f"{industry} urgency_hook empty"


def test_composer_user_prompt_includes_industry_block():
    """Regression — `_build_user_prompt` must inject INDUSTRY CONTEXT."""
    from services.outreach_composer import _build_user_prompt
    prompt = _build_user_prompt(
        lead={"business_name": "Mike's Plumbing", "city": "Mississauga",
              "province": "ON", "category": "plumber",
              "yelp_rating": 4.3, "review_count": 28, "has_website": False},
        channel="sms", step=1, site_change_context=None,
        scan_content=None,
    )
    assert "INDUSTRY CONTEXT" in prompt
    assert "industry insider" in prompt.lower()


def test_composer_skincare_credibility_injected():
    from services.outreach_composer import _build_user_prompt
    prompt = _build_user_prompt(
        lead={"business_name": "X Clinic", "city": "Toronto",
              "province": "ON", "category": "skincare_clinic",
              "yelp_rating": 4.6, "review_count": 80, "has_website": True},
        channel="email", step=1, site_change_context=None,
        scan_content=None,
    )
    assert "Insider credibility" in prompt
    assert "PDRN" in prompt
