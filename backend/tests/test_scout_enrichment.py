"""Tests for services.scout_enrichment — Section 3 of growth-engine upgrade."""
import asyncio
import os
import sys
import pytest
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services import scout_enrichment as se


# ── pure helpers ──────────────────────────────────────────────────────

def test_e164_normaliser():
    assert se._to_e164("416-555-1234") == "+14165551234"
    assert se._to_e164("4165551234") == "+14165551234"
    assert se._to_e164("+1 (416) 555-1234") == "+14165551234"
    assert se._to_e164("14165551234") == "+14165551234"
    assert se._to_e164("") == ""
    assert se._to_e164(None) == ""
    assert se._to_e164("garbage") == ""


def test_valid_mobile_ca_rejects_toll_free():
    assert se._is_valid_mobile_ca("+18005551234") is False  # 800
    assert se._is_valid_mobile_ca("+18885551234") is False  # 888
    assert se._is_valid_mobile_ca("+14165551234") is True   # GTA mobile-eligible
    assert se._is_valid_mobile_ca("+16475551234") is True
    assert se._is_valid_mobile_ca("") is False
    assert se._is_valid_mobile_ca("+44123456789") is False  # UK


def test_classify_industry_hvac():
    assert se._classify_industry({"category": "HVAC Repair"}) == "hvac"
    assert se._classify_industry({"name": "Joe's Heating & Cooling"}) == "hvac"
    assert se._classify_industry({"types": ["furnace_service"]}) == "hvac"


def test_classify_industry_plumbing():
    assert se._classify_industry({"category": "Plumber"}) == "plumbing"
    assert se._classify_industry({"name": "AAA Drain Service"}) == "plumbing"


def test_classify_industry_outside_trades():
    assert se._classify_industry({"category": "Coffee Shop"}) == ""
    assert se._classify_industry({}) == ""


def test_dead_check():
    assert se._is_dead({"status": "PERMANENTLY_CLOSED"}) is True
    assert se._is_dead({"business_status": "permanently closed"}) is True
    assert se._is_dead({"name": "Joe — Out of Business"}) is True
    assert se._is_dead({"status": "OPERATIONAL"}) is False
    assert se._is_dead({}) is False


def test_score_no_website_plus_3():
    s = se._score_lead({"website": "", "review_count": 0}, is_dnc=False, phone_e164="")
    # baseline 5 + 3 (no website) = 8
    assert s == 8


def test_score_reviews_in_band():
    s = se._score_lead({"website": "x", "review_count": 50}, is_dnc=False, phone_e164="")
    # 5 + 0 (has website) + 2 (10-100 reviews) = 7
    assert s == 7


def test_score_too_many_reviews_minus_2():
    s = se._score_lead({"website": "x", "review_count": 800}, is_dnc=False, phone_e164="")
    # 5 + 0 - 2 = 3
    assert s == 3


def test_score_dnc_minus_3():
    s = se._score_lead({"website": "x"}, is_dnc=True, phone_e164="+14165551234")
    # 5 + 2 (mobile CA) - 3 (dnc) = 4
    assert s == 4


def test_score_clamp_to_one_to_ten():
    # Tons of negatives stack
    s = se._score_lead(
        {"website": "x", "review_count": 9999},
        is_dnc=True, phone_e164=""
    )
    assert 1 <= s <= 10


def test_score_valid_email_plus_1():
    s = se._score_lead(
        {"website": "x", "email": "owner@biz.ca"},
        is_dnc=False, phone_e164="",
    )
    # 5 + 0 + 1 = 6
    assert s == 6


def test_score_invalid_email_no_bonus():
    s = se._score_lead(
        {"website": "x", "email": "not-an-email"},
        is_dnc=False, phone_e164="",
    )
    assert s == 5


def test_score_young_business_plus_2():
    s = se._score_lead(
        {"website": "x", "founded_year": datetime.now(timezone.utc).year - 1},
        is_dnc=False, phone_e164="",
    )
    # 5 + 0 + 2 (young) = 7
    assert s == 7


def test_name_postal_key():
    assert se._name_postal_key({"name": "Joe's Plumbing", "postal_code": "M5V 2T6"}) == "joesplumbing|M5V2T6"
    assert se._name_postal_key({"name": "X", "postal_code": ""}) == ""


# ── full flow ─────────────────────────────────────────────────────────

class _FakeCursor:
    def __init__(self, rows):
        self.rows = rows
    def __aiter__(self):
        async def gen():
            for r in self.rows:
                yield r
        return gen()


class _FakeColl:
    def __init__(self, rows=None):
        self.rows = rows or []
    def find(self, *a, **kw):
        return _FakeCursor(self.rows)
    async def create_index(self, *a, **kw):
        return None


class _FakeDB:
    def __init__(self):
        self.campaign_leads = _FakeColl([])
        self.dnc_list = _FakeColl([])


def test_enrich_and_filter_full_flow():
    db = _FakeDB()
    leads = [
        {"name": "Closed Co", "phone": "416-111-2222", "status": "PERMANENTLY_CLOSED"},
        {"name": "Joe HVAC", "phone": "416-555-0001", "category": "HVAC", "review_count": 25, "website": ""},
        {"name": "Big Plumbing", "phone": "416-555-0002", "category": "Plumber", "review_count": 800, "website": "x"},
    ]
    out = asyncio.run(se.enrich_and_filter_leads(leads, db=db))
    # Closed dropped
    assert len(out) == 2
    # HVAC ranks above Plumbing per priority
    assert out[0]["industry"] == "hvac"
    assert out[1]["industry"] == "plumbing"
    # HVAC score (no website + 25 reviews + mobile) > Plumbing
    assert out[0]["score"] > out[1]["score"]
    # All scored
    for L in out:
        assert 1 <= L["score"] <= 10
        assert "scored_at" in L


def test_enrich_handles_no_db():
    leads = [{"name": "X HVAC", "phone": "4165551234", "category": "hvac", "review_count": 50}]
    out = asyncio.run(se.enrich_and_filter_leads(leads, db=None))
    assert len(out) == 1
    assert out[0]["score"] >= 5


def test_annotate_dedup_fields():
    lead = {"name": "Joe Plumbing", "phone": "416-555-0001", "postal_code": "M5V 2T6"}
    out = se.annotate_dedup_fields(lead)
    assert out["phone_e164"] == "+14165550001"
    assert out["dedup_name_postal"] == "joeplumbing|M5V2T6"


def test_industry_priority_order():
    db = _FakeDB()
    leads = [
        {"name": "Pest Co",  "phone": "416-555-1110", "category": "Pest Control"},
        {"name": "HVAC Co",  "phone": "416-555-2220", "category": "HVAC"},
        {"name": "Floor Co", "phone": "416-555-3330", "category": "Flooring"},
    ]
    out = asyncio.run(se.enrich_and_filter_leads(leads, db=db))
    industries = [L["industry"] for L in out]
    # HVAC (10) > Flooring (3) > Pest Control (1)
    assert industries == ["hvac", "flooring", "pest control"]
