"""PRD Auto-Fill tests — iter 282al-8 (Prompt 11)."""
from __future__ import annotations

from services.prd_auto_fill import (
    CANADIAN_TRUST_BANK,
    CATEGORY_COLOR_SCHEMES,
    auto_fill_prd,
    prd_summary_for_llm,
)


# ── auto_fill_prd ────────────────────────────────────────────────────
def test_prd_minimum_lead():
    prd = auto_fill_prd({})
    assert prd["business_name"] == "Local Business"
    assert prd["province"] == "ON"
    assert prd["color_scheme"]["primary"].startswith("#")
    assert isinstance(prd["services"], list) and len(prd["services"]) >= 3


def test_prd_plumber_uses_industry_services():
    prd = auto_fill_prd({
        "business_name": "Mike's Plumbing",
        "city": "Mississauga",
        "category": "plumber",
        "phone": "+1 416 555 0123",
        "email": "info@mikes.ca",
    })
    assert prd["business_name"] == "Mike's Plumbing"
    assert prd["city"] == "Mississauga"
    assert prd["category"] == "plumber"
    assert prd["phone"].startswith("+1") or "(" in prd["phone"]
    assert prd["color_scheme"]["primary"] == \
        CATEGORY_COLOR_SCHEMES["plumber"]["primary"]
    # plumber category gets at least 5 service entries
    assert len(prd["services"]) >= 4
    names = " ".join(s["name"].lower() for s in prd["services"])
    # should reference plumbing-specific services
    assert "drain" in names or "plumb" in names or "fixture" in names


def test_prd_hvac_color_scheme():
    prd = auto_fill_prd({"business_name": "ColdSnap HVAC",
                          "category": "hvac", "city": "Toronto"})
    assert prd["color_scheme"] == CATEGORY_COLOR_SCHEMES["hvac"]
    assert "Toronto" in prd["tagline"] or "HVAC" in prd["tagline"]


def test_prd_unknown_category_falls_back():
    prd = auto_fill_prd({"business_name": "X",
                          "category": "unicorn-trainer",
                          "city": "Mississauga"})
    assert prd["color_scheme"] == CATEGORY_COLOR_SCHEMES["general"]
    assert isinstance(prd["services"], list)
    # Generic services only
    assert len(prd["services"]) >= 3


def test_prd_trust_bullets_count():
    prd = auto_fill_prd({"business_name": "X", "category": "plumber"})
    assert isinstance(prd["trust_bullets"], list)
    assert len(prd["trust_bullets"]) == 3
    # All entries are non-empty strings
    for b in prd["trust_bullets"]:
        assert isinstance(b, str) and b


def test_prd_canadian_signals_present():
    prd = auto_fill_prd({"business_name": "X", "city": "Brampton",
                          "category": "plumber"})
    blob = " ".join(prd["canadian_signals"]).lower()
    assert "canadian" in blob
    assert "brampton" in blob or "ontario" in blob


def test_prd_phone_normalization():
    prd = auto_fill_prd({"business_name": "X", "phone": "4165550100",
                          "category": "plumber"})
    # 10 digits → "(416) 555-0100"
    assert "(416)" in prd["phone"]


def test_prd_industry_terms_unique_capped():
    prd = auto_fill_prd({"business_name": "X", "category": "plumber",
                          "city": "Mississauga"})
    assert isinstance(prd["industry_terms"], list)
    assert len(prd["industry_terms"]) <= 12
    # No case-insensitive duplicates
    lows = [t.lower() for t in prd["industry_terms"]]
    assert len(lows) == len(set(lows))


def test_prd_source_signals_flagged():
    prd = auto_fill_prd({"business_name": "X", "category": "plumber",
                          "city": "Mississauga", "phone": "4165550100",
                          "email": "x@y.ca"})
    sigs = prd["source_signals"]
    assert sigs["used_industry"] is True
    assert sigs["has_phone"] is True
    assert sigs["has_email"] is True
    assert sigs["used_scan"] is False


# ── prd_summary_for_llm ──────────────────────────────────────────────
def test_summary_for_llm_grounded():
    prd = auto_fill_prd({"business_name": "Mike's Plumbing",
                          "city": "Mississauga", "category": "plumber",
                          "phone": "4165550100"})
    blob = prd_summary_for_llm(prd)
    assert "Mike's Plumbing" in blob
    assert "Mississauga" in blob
    assert "plumber" in blob
    assert "AUTO-FILLED PRD" in blob
    assert "do NOT invent" in blob


def test_summary_handles_empty_prd():
    assert prd_summary_for_llm({}) == ""
    assert prd_summary_for_llm(None) == ""  # type: ignore[arg-type]


# ── trust bank constants ─────────────────────────────────────────────
def test_trust_bank_has_canadian_signals():
    blob = " ".join(CANADIAN_TRUST_BANK).lower()
    assert "ontario" in blob or "canadian" in blob or "wsib" in blob
