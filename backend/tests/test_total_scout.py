"""Tests for the Total-Scout multi-source discovery dispatcher (iter 322n)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

from services import total_scout as ts


# ─── Helpers ────────────────────────────────────────────────────────────
def _ll(name: str, source: str, *, phone: str = "", website: str = "", city: str = "Mississauga") -> Dict[str, Any]:
    return {
        "business_name": name,
        "phone": phone,
        "website": website,
        "email": "",
        "address": "",
        "city": city,
        "source": source,
    }


# ─── Dedup-key behaviour ────────────────────────────────────────────────
def test_dedup_key_prefers_phone():
    a = _ll("Foo HVAC", "yelp", phone="(905) 555-1212")
    b = _ll("foo  HVAC!!", "places", phone="9055551212")
    assert ts._dedup_key(a) == ts._dedup_key(b), "name+phone variants must collapse"


def test_dedup_key_falls_back_to_website():
    a = _ll("Foo HVAC", "tavily", website="https://www.foohvac.ca/about")
    b = _ll("foo HVAC", "places", website="http://foohvac.ca")
    assert ts._dedup_key(a) == ts._dedup_key(b)


def test_dedup_key_distinct_when_no_overlap():
    a = _ll("Foo HVAC", "yelp", phone="9055551212")
    b = _ll("Bar Plumbing", "yelp", phone="9055551313")
    assert ts._dedup_key(a) != ts._dedup_key(b)


# ─── Phone normalisation ───────────────────────────────────────────────
def test_norm_phone_e164():
    assert ts._norm_phone("(905) 555-1212") == "+19055551212"
    assert ts._norm_phone("1-905-555-1212") == "+19055551212"
    assert ts._norm_phone("9055551212") == "+19055551212"
    assert ts._norm_phone("") == ""
    assert ts._norm_phone("garbage") == ""


# ─── Orchestrator: source merging + chains ─────────────────────────────
@pytest.mark.asyncio
async def test_orchestrator_merges_overlapping_sources(monkeypatch):
    """Two sources return the same business — final result must be one
    lead with a `source_chain` listing both contributors and the first
    non-empty value for each field."""
    async def fake_yelp(_q, _l, _lim):
        return [_ll("Foo HVAC", "yelp_fusion", phone="9055551212")]

    async def fake_places(_q, _l, _lim):
        return [_ll("Foo HVAC", "google_places", phone="9055551212",
                    website="https://foohvac.ca")]

    async def empty(*_a, **_k):
        return []

    monkeypatch.setattr(ts, "_SOURCES", {
        "yelp": fake_yelp,
        "google_places": fake_places,
        "osm": empty,
        "yellowpages": empty,
        "tavily": empty,
        "duckduckgo": empty,
    })
    out = await ts.discover_leads_total_scout("hvac", "Mississauga", limit=10, db=None)
    assert out["success"] is True
    assert out["total"] == 1, "duplicates must collapse"
    lead = out["leads"][0]
    assert lead["phone"] == "9055551212"
    assert lead["website"] == "https://foohvac.ca"
    chain = lead.get("source_chain") or []
    assert "yelp_fusion" in chain and "google_places" in chain


@pytest.mark.asyncio
async def test_orchestrator_returns_distinct_leads(monkeypatch):
    async def fake_yelp(_q, _l, _lim):
        return [
            _ll("Foo HVAC", "yelp_fusion", phone="9055551212"),
            _ll("Bar Plumbing", "yelp_fusion", phone="9055551313"),
        ]

    async def empty(*_a, **_k):
        return []

    monkeypatch.setattr(ts, "_SOURCES", {
        "yelp": fake_yelp, "google_places": empty, "osm": empty,
        "yellowpages": empty, "tavily": empty, "duckduckgo": empty,
    })
    out = await ts.discover_leads_total_scout("hvac", "Mississauga", limit=10, db=None)
    assert out["total"] == 2
    names = sorted(L["business_name"] for L in out["leads"])
    assert names == ["Bar Plumbing", "Foo HVAC"]


@pytest.mark.asyncio
async def test_orchestrator_records_source_yields(monkeypatch):
    async def fake_yelp(_q, _l, _lim):
        return [_ll("A", "yelp_fusion", phone="9055551111"),
                _ll("B", "yelp_fusion", phone="9055552222")]

    async def fake_yp(_q, _l, _lim):
        return [_ll("C", "yellowpages_ca", phone="9055553333")]

    async def empty(*_a, **_k):
        return []

    monkeypatch.setattr(ts, "_SOURCES", {
        "yelp": fake_yelp, "google_places": empty, "osm": empty,
        "yellowpages": fake_yp, "tavily": empty, "duckduckgo": empty,
    })
    out = await ts.discover_leads_total_scout("hvac", "Mississauga", limit=10, db=None)
    yields = out["source_yields"]
    assert yields["yelp"] == 2
    assert yields["yellowpages"] == 1
    assert yields["google_places"] == 0
    assert "elapsed_ms" in out and out["elapsed_ms"] >= 0


@pytest.mark.asyncio
async def test_source_timeout_does_not_kill_dispatcher(monkeypatch):
    """A slow source must time out without bringing the others down."""
    async def slow(_q, _l, _lim):
        await asyncio.sleep(60)  # > SOURCE_TIMEOUT_S
        return []

    async def fast(_q, _l, _lim):
        return [_ll("Quick HVAC", "yelp_fusion", phone="9055554444")]

    async def empty(*_a, **_k):
        return []

    monkeypatch.setattr(ts, "SOURCE_TIMEOUT_S", 0.2)
    monkeypatch.setattr(ts, "_SOURCES", {
        "yelp": fast, "google_places": slow, "osm": empty,
        "yellowpages": empty, "tavily": empty, "duckduckgo": empty,
    })
    out = await ts.discover_leads_total_scout("hvac", "Mississauga", limit=5, db=None)
    assert out["total"] == 1
    assert out["errors"].get("google_places") == "timeout"


# ─── Source-stats aggregation ──────────────────────────────────────────
class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def limit(self, _n):
        return self

    def __aiter__(self):
        self._iter = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class _FakeColl:
    def __init__(self, docs):
        self._docs = docs

    def find(self, _q, _proj):
        return _FakeCursor(self._docs)


class _FakeDB:
    def __init__(self, docs):
        self.scout_source_runs = _FakeColl(docs)


@pytest.mark.asyncio
async def test_source_stats_rollup():
    docs = [
        {"source_yields": {"yelp": 5, "google_places": 1}, "total_after_dedup": 5, "elapsed_ms": 1200},
        {"source_yields": {"yelp": 3, "yellowpages": 4}, "total_after_dedup": 6, "elapsed_ms": 1800},
        {"source_yields": {"osm": 2}, "total_after_dedup": 2, "elapsed_ms": 600},
    ]
    out = await ts.get_source_stats(_FakeDB(docs), days=7)
    assert out["runs"] == 3
    assert out["total_leads"] == 13
    by = {row["source"]: row["leads"] for row in out["by_source"]}
    assert by["yelp"] == 8
    assert by["yellowpages"] == 4
    assert by["osm"] == 2
    assert by["google_places"] == 1
    # Sorted descending by leads
    sources_in_order = [r["source"] for r in out["by_source"]]
    assert sources_in_order[0] == "yelp"
    # Share percentages sum close to 100
    assert abs(sum(r["share_pct"] for r in out["by_source"]) - 100.0) < 0.5
    assert out["avg_elapsed_ms"] == int((1200 + 1800 + 600) / 3)


@pytest.mark.asyncio
async def test_source_stats_empty_when_no_docs():
    out = await ts.get_source_stats(_FakeDB([]), days=7)
    assert out["runs"] == 0
    assert out["total_leads"] == 0
    assert out["by_source"] == []


@pytest.mark.asyncio
async def test_source_stats_returns_zero_with_no_db():
    out = await ts.get_source_stats(db=None, days=7)
    assert out["runs"] == 0
    assert out["by_source"] == []


# ─── Back-compat alias ─────────────────────────────────────────────────
# ─── Sovereign-Gold tier tagging ───────────────────────────────────────
def test_classify_tier_thresholds():
    assert ts.classify_tier([]) == "bronze"
    assert ts.classify_tier(["yelp_fusion"]) == "bronze"
    assert ts.classify_tier(["yelp_fusion", "google_places"]) == "silver"
    assert ts.classify_tier(["yelp_fusion", "google_places", "osm_overpass"]) == "gold"
    assert ts.classify_tier(["a", "b", "c", "d", "e"]) == "gold"


def test_classify_tier_dedupes_duplicates():
    """Same source repeated must NOT inflate the tier."""
    assert ts.classify_tier(["yelp_fusion", "yelp_fusion", "yelp_fusion"]) == "bronze"
    assert ts.classify_tier(["yelp_fusion", "yelp_fusion", "google_places"]) == "silver"


def test_is_sovereign_gold():
    gold_lead = {"source_chain": ["yelp_fusion", "google_places", "osm_overpass"]}
    silver_lead = {"source_chain": ["yelp_fusion", "google_places"]}
    assert ts.is_sovereign_gold(gold_lead) is True
    assert ts.is_sovereign_gold(silver_lead) is False
    assert ts.is_sovereign_gold({}) is False


# ─── Forensic Miner niche-gating ───────────────────────────────────────
def test_looks_like_ecommerce_niche_positive():
    assert ts._looks_like_ecommerce_niche("skincare brands") is True
    assert ts._looks_like_ecommerce_niche("BEAUTY products Canada") is True
    assert ts._looks_like_ecommerce_niche("shopify dtc store") is True
    assert ts._looks_like_ecommerce_niche("petcare ecommerce") is True


def test_looks_like_ecommerce_niche_skips_local_trades():
    """Local-trade queries must NOT trigger Forensic Miner."""
    assert ts._looks_like_ecommerce_niche("HVAC Mississauga") is False
    assert ts._looks_like_ecommerce_niche("plumber Toronto") is False
    assert ts._looks_like_ecommerce_niche("electrician North York") is False
    assert ts._looks_like_ecommerce_niche("roofing contractor Ottawa") is False
    assert ts._looks_like_ecommerce_niche("dentist Mississauga") is False
    assert ts._looks_like_ecommerce_niche("") is False


@pytest.mark.asyncio
async def test_forensic_discover_returns_empty_for_local_trades():
    """The adapter must short-circuit on non-niche queries — no API call,
    no Tomba burn."""
    out = await ts._forensic_discover("HVAC", "Mississauga", limit=10)
    assert out == []


# ─── Tier counts in dispatcher output ─────────────────────────────────
@pytest.mark.asyncio
async def test_orchestrator_emits_tier_counts(monkeypatch):
    """Dispatcher must annotate each lead with `tier` AND surface a
    `tier_counts` rollup in the response."""
    async def fake_yelp(_q, _l, _lim):
        return [_ll("Foo HVAC", "yelp_fusion", phone="9055551212"),
                _ll("Bar Plumbing", "yelp_fusion", phone="9055551313")]

    async def fake_places(_q, _l, _lim):
        # Foo HVAC also seen by Places — bumps it to silver
        return [_ll("Foo HVAC", "google_places", phone="9055551212")]

    async def fake_osm(_q, _l, _lim):
        # Foo HVAC also seen by OSM — bumps it to gold
        return [_ll("Foo HVAC", "osm_overpass", phone="9055551212")]

    async def empty(*_a, **_k):
        return []

    monkeypatch.setattr(ts, "_SOURCES", {
        "yelp": fake_yelp, "google_places": fake_places, "osm": fake_osm,
        "yellowpages": empty, "tavily": empty, "duckduckgo": empty,
        "forensic": empty,
    })
    out = await ts.discover_leads_total_scout("hvac", "Mississauga", limit=10, db=None)
    assert out["total"] == 2
    by_name = {L["business_name"]: L for L in out["leads"]}
    assert by_name["Foo HVAC"]["tier"] == "gold"
    assert by_name["Bar Plumbing"]["tier"] == "bronze"
    assert out["tier_counts"]["gold"] == 1
    assert out["tier_counts"]["bronze"] == 1
    assert out["tier_counts"]["silver"] == 0


@pytest.mark.asyncio
async def test_google_places_leads_alias_calls_dispatcher(monkeypatch):
    """The legacy public name `google_places_leads` must keep working —
    it's used by existing callers."""
    captured = {}

    async def fake_dispatcher(query, location, *, limit, db=None, enabled=None):
        captured["q"] = query
        captured["loc"] = location
        captured["lim"] = limit
        return {"success": True, "leads": [], "total": 0,
                "source": "total_scout", "source_yields": {}}

    monkeypatch.setattr(ts, "discover_leads_total_scout", fake_dispatcher)
    out = await ts.google_places_leads("hvac", "Mississauga", limit=15)
    assert out["success"] is True
    assert captured == {"q": "hvac", "loc": "Mississauga", "lim": 15}
