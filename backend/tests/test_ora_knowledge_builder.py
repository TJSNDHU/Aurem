"""
iter 282al-23 — Tests for services.ora_knowledge_builder
========================================================
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


# ───────────── Fake Mongo cursor helper ─────────────
class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self, length=None):
        return self._rows


def _mk_db(collections):
    """Build a MagicMock db where each collection returns the given rows
    on `.find(...).to_list(...)`."""
    db = MagicMock()
    for name, rows in collections.items():
        coll = MagicMock()
        coll.find = MagicMock(return_value=_Cursor(rows))
        coll.insert_one = AsyncMock(return_value=None)
        setattr(db, name, coll)
    db.knowledge_builds.insert_one = AsyncMock(return_value=None)
    return db


# ───────────── Section builders ─────────────
@pytest.mark.asyncio
async def test_outreach_patterns_returns_block_when_replies_exist():
    from services.ora_knowledge_builder import _build_outreach_patterns
    db = _mk_db({"outreach_history": [
        {"channel": "email", "step": 1, "industry": "plumber",
         "city": "Mississauga", "reply_received": True,
         "body": "hi mike — noticed your site has no booking form"},
        {"channel": "email", "step": 1, "industry": "plumber",
         "city": "Toronto", "reply_received": False, "body": "hello"},
        {"channel": "sms", "step": 2, "industry": "hvac",
         "city": "Brampton", "reply_received": True, "body": "hey hvac"},
    ]})
    out = await _build_outreach_patterns(db, datetime.now(timezone.utc))
    assert "TOP PERFORMING" in out
    assert "plumber" in out.lower() or "hvac" in out.lower()
    assert "Reply rate" in out


@pytest.mark.asyncio
async def test_outreach_patterns_returns_empty_when_no_replies():
    from services.ora_knowledge_builder import _build_outreach_patterns
    db = _mk_db({"outreach_history": [
        {"channel": "email", "reply_received": False, "body": "x"},
    ]})
    out = await _build_outreach_patterns(db, datetime.now(timezone.utc))
    assert out == ""


@pytest.mark.asyncio
async def test_casl_patterns_block():
    from services.ora_knowledge_builder import _build_casl_patterns
    db = _mk_db({"casl_scores": [
        {"channel": "email", "passed": True},
        {"channel": "email", "passed": False, "reason": "missing_stop"},
        {"channel": "sms",   "passed": False, "reason": "missing_stop"},
    ]})
    out = await _build_casl_patterns(db, datetime.now(timezone.utc))
    assert "CASL PATTERNS" in out
    assert "missing_stop" in out


@pytest.mark.asyncio
async def test_market_patterns_block():
    from services.ora_knowledge_builder import _build_market_patterns
    db = _mk_db({"campaign_leads": [
        {"category": "plumber", "city": "mississauga", "website": ""},
        {"category": "plumber", "city": "toronto",     "website": "https://x.ca"},
        {"category": "hvac",    "city": "mississauga", "website": ""},
    ]})
    out = await _build_market_patterns(db, datetime.now(timezone.utc))
    assert "CANADIAN MARKET PATTERNS" in out
    assert "plumber" in out.lower()
    assert "Mississauga" in out  # title-cased


@pytest.mark.asyncio
async def test_site_score_patterns_block():
    from services.ora_knowledge_builder import _build_site_score_patterns
    db = _mk_db({"site_audits": [
        {"overall_score": 40, "issues": [{"title": "No mobile menu"},
                                          {"title": "Slow LCP"}]},
        {"overall_score": 60, "issues": [{"title": "No mobile menu"}]},
    ]})
    out = await _build_site_score_patterns(db, datetime.now(timezone.utc))
    assert "SITE-SCORE PATTERNS" in out
    assert "No mobile menu" in out


@pytest.mark.asyncio
async def test_timing_patterns_block():
    from services.ora_knowledge_builder import _build_timing_patterns
    db = _mk_db({"outreach_history": [
        {"sent_at": datetime(2026, 1, 5, 14, 0, tzinfo=timezone.utc),
         "reply_received": True, "channel": "email"},
        {"sent_at": datetime(2026, 1, 6, 14, 30, tzinfo=timezone.utc),
         "reply_received": True, "channel": "email"},
        {"sent_at": datetime(2026, 1, 6, 22, 0, tzinfo=timezone.utc),
         "reply_received": False, "channel": "email"},
    ]})
    out = await _build_timing_patterns(db, datetime.now(timezone.utc))
    assert "TIMING PATTERNS" in out
    assert "14:00" in out


# ───────────── Public entry point ─────────────
@pytest.mark.asyncio
async def test_build_snapshot_writes_file_and_logs(tmp_path, monkeypatch):
    from services import ora_knowledge_builder as kb

    # Redirect snapshot file to tmp
    fake_dir = tmp_path / "ora_skills"
    fake_dir.mkdir()
    monkeypatch.setattr(kb, "_SKILLS_DIR", fake_dir, raising=True)
    monkeypatch.setattr(kb, "_SNAPSHOT_FILE",
                        fake_dir / "ora_knowledge_snapshot.md", raising=True)

    db = _mk_db({
        "outreach_history": [
            {"channel": "email", "industry": "plumber",
             "reply_received": True, "body": "hi mike booking form"},
        ],
        "casl_scores":     [{"channel": "email", "passed": True}],
        "campaign_leads":  [{"category": "plumber", "city": "mississauga", "website": ""}],
        "site_audits":     [{"overall_score": 50, "issues": [{"title": "X"}]}],
    })

    out = await kb.build_knowledge_snapshot(db)
    assert out["ok"] is True
    assert "outreach" in out["sections_built"]
    snap_path = fake_dir / "ora_knowledge_snapshot.md"
    assert snap_path.exists()
    content = snap_path.read_text(encoding="utf-8")
    assert "ORA Knowledge Snapshot" in content
    assert "TOP PERFORMING" in content
    db.knowledge_builds.insert_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_build_snapshot_no_db_short_circuits():
    from services.ora_knowledge_builder import build_knowledge_snapshot
    out = await build_knowledge_snapshot(None)
    assert out["ok"] is False
    assert out["reason"] == "no_db"


@pytest.mark.asyncio
async def test_build_snapshot_no_data_returns_no_data(tmp_path, monkeypatch):
    from services import ora_knowledge_builder as kb
    fake_dir = tmp_path / "ora_skills"
    fake_dir.mkdir()
    monkeypatch.setattr(kb, "_SKILLS_DIR", fake_dir, raising=True)
    monkeypatch.setattr(kb, "_SNAPSHOT_FILE",
                        fake_dir / "ora_knowledge_snapshot.md", raising=True)

    db = _mk_db({
        "outreach_history": [], "casl_scores": [],
        "campaign_leads": [],   "site_audits": [],
    })
    out = await kb.build_knowledge_snapshot(db)
    assert out["ok"] is False
    assert out["reason"] == "no_data"
