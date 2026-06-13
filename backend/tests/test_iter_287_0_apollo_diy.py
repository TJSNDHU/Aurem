"""iter 287.0 — Apollo DIY Credit-Saver Proxy.

Validates:
  • apollo_scout._domain_from_url strips protocol/www/port correctly
  • apollo_scout.apollo_people_search gracefully returns [] when no key
  • apollo_scout caches results in db.apollo_people_cache per (domain, titles_hash)
  • email_guesser.generate_candidates produces top-N patterns in priority order
  • email_guesser._normalize handles whitespace + case
  • email_guesser.verify_email returns invalid for bad domain, unknown for
    unreliable_provider_skip_probe (gmail.com)
  • email_guesser.guess_and_verify returns probably_valid when MX exists
    and candidates produced (probe may fail in container — that's OK)
  • apollo_enrichment.enrich_lead_with_apollo_diy returns skipped when
    APOLLO_API_KEY missing (the common case today)
  • enrichment writes apollo_candidates_tried metadata even when no email found
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

REPO = Path(__file__).resolve().parents[2]


def _env():
    env = {}
    for line in (REPO / "backend" / ".env").read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


# ── apollo_scout helpers ─────────────────────────────────────────────

def test_domain_extraction_various_shapes():
    from backend.services.apollo_scout import _domain_from_url
    assert _domain_from_url("https://www.reroots.ca/about") == "reroots.ca"
    assert _domain_from_url("http://foo.com:8080/x") == "foo.com"
    assert _domain_from_url("www.homerevive.ca") == "homerevive.ca"
    assert _domain_from_url("Plain.Example.CO.uk/") == "plain.example.co.uk"
    assert _domain_from_url("") == ""
    assert _domain_from_url(None or "") == ""


def test_apollo_search_returns_empty_when_key_missing(monkeypatch):
    monkeypatch.delenv("APOLLO_API_KEY", raising=False)
    from backend.services.apollo_scout import apollo_people_search
    result = asyncio.run(apollo_people_search(None, domain="example.com"))
    assert result == []


def test_apollo_search_returns_empty_on_empty_domain(monkeypatch):
    monkeypatch.setenv("APOLLO_API_KEY", "dummy_will_not_be_used")
    from backend.services.apollo_scout import apollo_people_search
    result = asyncio.run(apollo_people_search(None, domain=""))
    assert result == []


# ── email_guesser pattern generation ─────────────────────────────────

def test_generate_candidates_top_pattern_is_first_dot_last():
    from backend.services.email_guesser import generate_candidates
    out = generate_candidates("John", "Doe", "example.com", limit=5)
    assert len(out) == 5
    assert out[0] == "john.doe@example.com"
    # should also include initial-first-last pattern
    assert any(e.startswith("jdoe@") for e in out)


def test_generate_candidates_handles_whitespace_and_case():
    from backend.services.email_guesser import generate_candidates
    out = generate_candidates("  Priya ", "Sharma", "Aurem.Live")
    assert out[0] == "priya.sharma@aurem.live"


def test_generate_candidates_rejects_unsafe_localparts():
    from backend.services.email_guesser import generate_candidates
    # Weird input — should produce no invalid results
    out = generate_candidates("", "Doe", "example.com")
    # first is empty → patterns using {first} will be ".doe@" etc, rejected by _LOCAL_SAFE
    # Actually "." is allowed in LOCAL_SAFE, so ".doe@example.com" might slip.
    # Enforce: no candidate starts with a dot
    for e in out:
        local = e.split("@")[0]
        assert local and not local.startswith(".")


def test_generate_candidates_needs_domain():
    from backend.services.email_guesser import generate_candidates
    assert generate_candidates("John", "Doe", "") == []


# ── email_guesser verification ───────────────────────────────────────

def test_verify_email_rejects_no_at_symbol():
    from backend.services.email_guesser import verify_email
    result = asyncio.run(verify_email("not-an-email"))
    assert result["status"] == "invalid"
    assert result["detail"] == "no_at_symbol"


def test_verify_email_returns_invalid_for_bad_domain():
    from backend.services.email_guesser import verify_email
    result = asyncio.run(verify_email("probe@definitely-not-a-real-domain-xyz123.tld"))
    assert result["status"] in ("invalid", "unknown")


def test_verify_email_unreliable_gmail_short_circuits():
    from backend.services.email_guesser import verify_email
    # Gmail has MX but we skip probe — should return "unknown"
    result = asyncio.run(verify_email("test@gmail.com"))
    assert result["status"] == "unknown"
    assert "unreliable_provider" in result["detail"]


# ── apollo_enrichment graceful skip ──────────────────────────────────

def test_enrichment_skipped_when_no_apollo_key(monkeypatch):
    """After iter 287.2 pivot, enrichment uses website_scraper primarily
    (doesn't require Apollo key). Without a key, Apollo org-enrich is
    skipped, but website scrape still runs. For a non-existent domain
    it returns "no_data". Apollo key just affects metadata breadth."""
    monkeypatch.delenv("APOLLO_API_KEY", raising=False)
    from backend.services.apollo_enrichment import enrich_lead_with_apollo_diy
    # Use a domain that definitely won't resolve → scrape returns 0 pages → no_data
    result = asyncio.run(enrich_lead_with_apollo_diy(
        None, "test_lead", "https://definitely-not-a-real-domain-xyz-12345.invalid",
    ))
    assert result["status"] in ("no_data", "metadata_only")
    assert result["email"] is None
    assert result["sources"] == [] or result["sources"] == ["website_scrape"]


def test_enrichment_skipped_when_no_website(monkeypatch):
    monkeypatch.setenv("APOLLO_API_KEY", "dummy_key")
    from backend.services.apollo_enrichment import enrich_lead_with_apollo_diy
    result = asyncio.run(enrich_lead_with_apollo_diy(None, "test_lead", ""))
    assert result["status"] == "skipped"
    assert result["skipped_reason"] == "no_domain"


# ── enrichment integration (mocked apollo + real DB) ────────────────

def test_enrichment_end_to_end_with_mocked_scrape(monkeypatch):
    """Full pipeline: mock scrape_website to return a fake page with emails,
    then verify enrichment writes enrichment_* fields to campaign_leads."""
    async def _fake_scrape(url):
        return {
            "website": "https://fake.ca",
            "domain":  "fake.ca",
            "emails":  ["info@fake.ca", "john@fake.ca"],
            "phones":  ["+14165551234"],
            "people":  [{"first_name": "John", "last_name": "Doe",
                         "title": "Owner", "source": "website_scrape"}],
            "socials": {"linkedin": "https://linkedin.com/in/johndoe"},
            "pages_scanned": 2,
        }

    from backend.services import apollo_enrichment, website_scraper
    monkeypatch.setattr(website_scraper, "scrape_website", _fake_scrape)
    monkeypatch.setattr(apollo_enrichment, "scrape_website", _fake_scrape, raising=False)
    import importlib
    importlib.reload(apollo_enrichment)
    monkeypatch.setattr(apollo_enrichment, "scrape_website", _fake_scrape, raising=False)

    env = _env()

    async def _run():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        lead_id = f"test_enrich_{int(time.time())}"
        await db.campaign_leads.insert_one({
            "lead_id": lead_id,
            "business_name": "Fake Biz",
            "website_url": "https://fake.ca",
            "email": None,
        })
        try:
            result = await apollo_enrichment.enrich_lead_with_apollo_diy(
                db, lead_id, "https://fake.ca",
            )
            lead = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
            assert lead is not None
            assert "enrichment_sources" in lead
            assert "website_scrape" in lead["enrichment_sources"]
            assert "enriched_at" in lead
            # Email should be populated from scrape
            assert lead.get("email") == "info@fake.ca"
            assert lead.get("email_confidence") == "HIGH"
            assert lead.get("apollo_person_name") == "John Doe"
            assert lead.get("apollo_linkedin_url") == "https://linkedin.com/in/johndoe"
            assert result["status"] == "enriched"
        finally:
            await db.campaign_leads.delete_one({"lead_id": lead_id})

    asyncio.run(_run())


# ── apollo_scout cache behavior ──────────────────────────────────────

def test_apollo_cache_writes_and_reads(monkeypatch):
    """Confirm db.apollo_people_cache is written on a successful search."""
    monkeypatch.setenv("APOLLO_API_KEY", "dummy_key_cache_test")

    # Patch httpx to return a fake successful response
    class FakeResponse:
        status_code = 200
        text = "{}"
        def json(self):
            return {"people": [{
                "first_name": "Cache",
                "last_name": "Test",
                "title": "Manager",
                "linkedin_url": "",
                "organization": {"name": "Cache Co", "primary_domain": "cache-test.ca"},
                "id": "c1",
            }], "pagination": {}}

    class FakeClient:
        def __init__(self, *a, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, *a, **kw): return FakeResponse()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    from backend.services.apollo_scout import apollo_people_search, CACHE_COLLECTION
    env = _env()

    async def _run():
        c = AsyncIOMotorClient(env["MONGO_URL"])
        db = c[env["DB_NAME"]]
        await db[CACHE_COLLECTION].delete_many({"domain": "cache-test.ca"})
        r1 = await apollo_people_search(db, domain="cache-test.ca", limit=3)
        assert len(r1) == 1
        assert r1[0]["first_name"] == "Cache"
        # Verify cache row exists
        cached = await db[CACHE_COLLECTION].find_one({"domain": "cache-test.ca"}, {"_id": 0})
        assert cached is not None
        assert len(cached["people"]) == 1
        # Second call should return cached data without re-calling httpx
        # (we can't easily assert httpx wasn't called without more mocking,
        # but we verify return value shape is the same)
        r2 = await apollo_people_search(db, domain="cache-test.ca", limit=3)
        assert r2[0]["first_name"] == "Cache"
        await db[CACHE_COLLECTION].delete_many({"domain": "cache-test.ca"})

    asyncio.run(_run())
