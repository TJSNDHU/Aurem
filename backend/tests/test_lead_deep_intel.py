"""Tests for `services.lead_deep_intel` (iter 322n on-demand enrichment)."""
from __future__ import annotations

from typing import Any, Dict

import pytest

from services import lead_deep_intel as ldi


# ─── Query-builder behaviour ───────────────────────────────────────────
def test_build_query_with_business_and_city():
    q = ldi._build_query({
        "business_name": "Foo HVAC",
        "city": "Mississauga, ON",
    })
    assert '"Foo HVAC"' in q
    assert "Mississauga" in q


def test_build_query_falls_back_to_website_when_no_name():
    q = ldi._build_query({"website": "https://foohvac.ca"})
    assert "foohvac.ca" in q


def test_build_query_safe_when_empty():
    q = ldi._build_query({})
    assert q == "unknown business"


# ─── enrich_lead — happy path + persist ────────────────────────────────
class _FakeUpdateColl:
    def __init__(self):
        self.upserts: list = []

    async def update_one(self, q, u, upsert=False):
        self.upserts.append({"q": q, "u": u, "upsert": upsert})


class _FakeFindColl:
    def __init__(self, doc):
        self._doc = doc

    async def find_one(self, _q, _proj):
        return self._doc


class _FakeDB:
    def __init__(self, *, intel_doc=None):
        self.lead_deep_intel = _FakeUpdateColl()
        if intel_doc is not None:
            self.lead_deep_intel = type("C", (), {})()
            self.lead_deep_intel.find_one = _FakeFindColl(intel_doc).find_one
            self.lead_deep_intel.update_one = _FakeUpdateColl().update_one


@pytest.mark.asyncio
async def test_enrich_lead_persists_dark_scout_output(monkeypatch):
    async def fake_run(*, query, tenant_id, preset, max_results):
        return {
            "status": "completed",
            "risk_level": "MEDIUM",
            "analysis": "Looks fine.",
            "scraped_pages": 4,
            "investigation_id": "inv-abc",
        }

    monkeypatch.setattr(
        "services.dark_scout_service.run_investigation", fake_run,
    )
    db = _FakeDB()
    out = await ldi.enrich_lead(
        db,
        lead_id="lead-1",
        lead={"business_name": "Foo HVAC", "city": "Mississauga"},
        preset="brand_monitor",
    )
    assert out["status"] == "completed"
    assert out["risk_level"] == "MEDIUM"
    assert out["source_count"] == 4
    assert out["investigation_id"] == "inv-abc"
    assert "elapsed_ms" in out
    assert len(db.lead_deep_intel.upserts) == 1
    upsert = db.lead_deep_intel.upserts[0]
    assert upsert["q"] == {"lead_id": "lead-1"}
    assert upsert["upsert"] is True


@pytest.mark.asyncio
async def test_enrich_lead_rejects_missing_lead_id():
    out = await ldi.enrich_lead(db=None, lead_id="", lead={"business_name": "x"})
    assert out["status"] == "failed"
    assert out["error"] == "lead_id_required"


@pytest.mark.asyncio
async def test_enrich_lead_normalises_unknown_preset(monkeypatch):
    captured: Dict[str, Any] = {}

    async def fake_run(*, query, tenant_id, preset, max_results):
        captured["preset"] = preset
        return {"status": "completed", "risk_level": "LOW",
                "analysis": "", "scraped_pages": 0}

    monkeypatch.setattr(
        "services.dark_scout_service.run_investigation", fake_run,
    )
    await ldi.enrich_lead(
        db=None, lead_id="lead-x",
        lead={"business_name": "Foo"}, preset="totally-fake-preset",
    )
    assert captured["preset"] == "brand_monitor"


@pytest.mark.asyncio
async def test_enrich_lead_handles_dark_scout_exception(monkeypatch):
    async def boom(**_kw):
        raise RuntimeError("camofox down")

    monkeypatch.setattr(
        "services.dark_scout_service.run_investigation", boom,
    )
    out = await ldi.enrich_lead(
        db=None, lead_id="lead-9",
        lead={"business_name": "Foo HVAC"}, preset="brand_monitor",
    )
    assert out["status"] == "failed"
    assert "camofox down" in out["error"]


@pytest.mark.asyncio
async def test_get_deep_intel_returns_none_when_db_missing():
    out = await ldi.get_deep_intel(db=None, lead_id="lead-1")
    assert out is None


@pytest.mark.asyncio
async def test_get_deep_intel_returns_persisted_doc():
    expected = {
        "lead_id": "lead-1",
        "risk_level": "HIGH",
        "analysis": "Found leaked credentials.",
    }

    class _DB:
        class lead_deep_intel:
            @staticmethod
            async def find_one(_q, _proj):
                return expected

    out = await ldi.get_deep_intel(_DB(), "lead-1")
    assert out == expected
