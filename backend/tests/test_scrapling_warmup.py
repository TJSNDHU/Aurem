"""
iter 282al-23 — Tests for services.scrapling_warmup
====================================================
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def limit(self, _n):
        return self

    async def to_list(self, length=None):
        return self._rows


def _mk_db(webclaw_rows=None, lead_rows=None):
    db = MagicMock()

    webclaw_coll = MagicMock()
    webclaw_coll.find = MagicMock(return_value=_Cursor(webclaw_rows or []))
    db.webclaw_usage = webclaw_coll

    lead_coll = MagicMock()
    lead_coll.find = MagicMock(return_value=_Cursor(lead_rows or []))
    db.campaign_leads = lead_coll

    log_coll = MagicMock()
    log_coll.insert_one = AsyncMock(return_value=None)
    log_coll.create_index = AsyncMock(return_value=None)
    db.scrapling_warmup_log = log_coll
    return db


# ─────────── domain helper ───────────
def test_domain_of_strips_scheme_and_path():
    from services.scrapling_warmup import _domain_of
    assert _domain_of("https://Example.CA/foo/bar") == "example.ca"
    assert _domain_of("http://www.x.com") == "www.x.com"
    assert _domain_of("") == ""
    assert _domain_of(None) == ""  # type: ignore[arg-type]


# ─────────── get_top_domains ───────────
@pytest.mark.asyncio
async def test_get_top_domains_dedupes_and_orders():
    from services.scrapling_warmup import get_top_domains
    db = _mk_db(
        webclaw_rows=[
            {"url": "https://a.ca/x"}, {"url": "https://a.ca/y"},
            {"url": "https://b.ca"},
        ],
        lead_rows=[
            {"website": "https://b.ca", "created_at": datetime.now(timezone.utc)},
            {"website": "https://c.ca", "created_at": datetime.now(timezone.utc)},
        ],
    )
    domains = await get_top_domains(db, limit=10)
    assert "a.ca" in domains
    assert "b.ca" in domains
    assert "c.ca" in domains
    # a.ca counted 2x, b.ca counted 2x → before c.ca
    assert domains[0] in ("a.ca", "b.ca")


@pytest.mark.asyncio
async def test_get_top_domains_handles_no_db():
    from services.scrapling_warmup import get_top_domains
    out = await get_top_domains(None, limit=5)
    assert out == []


@pytest.mark.asyncio
async def test_get_top_domains_handles_empty_collections():
    from services.scrapling_warmup import get_top_domains
    db = _mk_db()
    assert await get_top_domains(db, limit=10) == []


# ─────────── _warm_one ───────────
@pytest.mark.asyncio
async def test_warm_one_success(monkeypatch):
    from services import scrapling_warmup as sw
    import services.scrapling_client as sc

    async def _fake_fetch(url, use_stealth=False, timeout=15000):
        return {"status": "success", "fetcher": "AsyncFetcher",
                "content": "x" * 500}

    monkeypatch.setattr(sc, "scrapling_fetch", _fake_fetch)
    out = await sw._warm_one("example.com")
    assert out["ok"] is True
    assert out["fetcher"] == "AsyncFetcher"
    assert out["bytes"] == 500


@pytest.mark.asyncio
async def test_warm_one_failure(monkeypatch):
    from services import scrapling_warmup as sw
    import services.scrapling_client as sc

    async def _bad_fetch(url, use_stealth=False, timeout=15000):
        raise RuntimeError("network down")

    monkeypatch.setattr(sc, "scrapling_fetch", _bad_fetch)
    out = await sw._warm_one("example.com")
    assert out["ok"] is False
    assert "network down" in out.get("error", "")


# ─────────── run_scrapling_warmup ───────────
@pytest.mark.asyncio
async def test_run_warmup_no_domains_returns_no_domains():
    from services.scrapling_warmup import run_scrapling_warmup
    db = _mk_db()
    out = await run_scrapling_warmup(db, max_domains=5, concurrency=2)
    assert out["ok"] is False
    assert out["reason"] == "no_domains"
    assert out["warmed"] == 0


@pytest.mark.asyncio
async def test_run_warmup_full_flow_logs_to_db(monkeypatch):
    from services import scrapling_warmup as sw
    import services.scrapling_client as sc

    async def _fake_fetch(url, use_stealth=False, timeout=15000):
        return {"status": "success", "fetcher": "AsyncFetcher", "content": "ok"}

    monkeypatch.setattr(sc, "scrapling_fetch", _fake_fetch)

    db = _mk_db(webclaw_rows=[
        {"url": "https://a.ca"},
        {"url": "https://b.ca"},
    ])
    out = await sw.run_scrapling_warmup(db, max_domains=10, concurrency=2)
    assert out["ok"] is True
    assert out["warmed"] == 2
    assert out["considered"] == 2
    assert out["fetcher_breakdown"].get("AsyncFetcher") == 2
    db.scrapling_warmup_log.insert_one.assert_awaited_once()


# ─────────── ensure_warmup_indexes ───────────
@pytest.mark.asyncio
async def test_ensure_warmup_indexes_creates_ttl():
    from services.scrapling_warmup import ensure_warmup_indexes
    db = _mk_db()
    await ensure_warmup_indexes(db)
    db.scrapling_warmup_log.create_index.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_warmup_indexes_handles_no_db():
    from services.scrapling_warmup import ensure_warmup_indexes
    # Should not raise
    await ensure_warmup_indexes(None)
