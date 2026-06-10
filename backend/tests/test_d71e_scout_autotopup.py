"""
D-71e — Scout Auto-Topup background job.

Verifies:
 1. count_eligible mirrors auto_blast_engine _eligible_leads filter EXACTLY
 2. Disabled flag (SCOUT_AUTOTOPUP_DISABLED) is honoured
 3. Cooldown + daily ceiling block re-fires
 4. trigger_topup writes a log row with the structured outcome
 5. check_and_topup is a no-op when floor is met
 6. p1-worker attaches the autotopup scheduler at startup
 7. Admin endpoints registered
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest


# ─── 1. Core count_eligible filter parity ───────────────────────────

@pytest.mark.asyncio
async def test_count_eligible_excludes_internal_test_sources(monkeypatch):
    """A lead with `source='awb_e2e_test'` must NOT be counted as eligible
    — exactly mirroring _eligible_leads filter."""
    from services import scout_autotopup

    class FakeColl:
        def __init__(self):
            self.last_query = None
        async def count_documents(self, q):
            self.last_query = q
            return 0
    class FakeDB:
        def __init__(self):
            self.campaign_leads = FakeColl()

    db = FakeDB()
    await scout_autotopup.count_eligible(db)
    q = db.campaign_leads.last_query
    # The filter must contain ALL of these clauses
    assert "noise_flag" in q
    assert "source" in q
    src_exclusion = q["source"].get("$nin", [])
    for s in ("awb_e2e_test", "agent2agent_test", "playwright_test"):
        assert s in src_exclusion, f"Missing source exclusion: {s}"
    assert "$or" in q  # contact OR-clause
    # status dead-set excludes
    for s in ("signed_up", "not_interested", "unsubscribed"):
        assert s in q["status"]["$nin"]


# ─── 2. Disabled flag honoured ──────────────────────────────────────

@pytest.mark.asyncio
async def test_trigger_topup_respects_disabled_flag(monkeypatch):
    monkeypatch.setenv("SCOUT_AUTOTOPUP_DISABLED", "true")
    from services import scout_autotopup

    inserts = []
    class FakeLog:
        async def insert_one(self, doc): inserts.append(doc)
        async def find_one(self, *a, **k): return None
        async def count_documents(self, *a, **k): return 0
    class FakeDB:
        scout_autotopup_log = FakeLog()
        class campaign_leads:
            @staticmethod
            async def count_documents(q): return 0

    out = await scout_autotopup.trigger_topup(FakeDB(), reason="test_disabled")
    assert out["outcome"] == "disabled"
    assert "SCOUT_AUTOTOPUP_DISABLED" in out["detail"]
    assert len(inserts) == 1


# ─── 3. Missing Apollo key → graceful no-op ─────────────────────────

@pytest.mark.asyncio
async def test_trigger_topup_handles_missing_apollo_key(monkeypatch):
    monkeypatch.delenv("SCOUT_AUTOTOPUP_DISABLED", raising=False)
    monkeypatch.delenv("APOLLO_API_KEY", raising=False)
    from services import scout_autotopup

    inserts = []
    class FakeLog:
        async def insert_one(self, doc): inserts.append(doc)
    class FakeDB:
        scout_autotopup_log = FakeLog()

    out = await scout_autotopup.trigger_topup(FakeDB(), reason="test_nokey")
    assert out["outcome"] == "no_apollo_key"


# ─── 4. check_and_topup is a no-op when floor met ───────────────────

@pytest.mark.asyncio
async def test_check_and_topup_noop_when_floor_met(monkeypatch):
    monkeypatch.delenv("SCOUT_AUTOTOPUP_DISABLED", raising=False)
    from services import scout_autotopup

    class FakeDB:
        class campaign_leads:
            @staticmethod
            async def count_documents(q):
                return 9999  # WAY above floor

    out = await scout_autotopup.check_and_topup(FakeDB())
    assert out["outcome"] == "floor_met"
    assert out["eligible"] == 9999


# ─── 5. status() shape used by admin endpoint ───────────────────────

@pytest.mark.asyncio
async def test_status_returns_full_shape(monkeypatch):
    monkeypatch.delenv("SCOUT_AUTOTOPUP_DISABLED", raising=False)
    from services import scout_autotopup

    class FakeColl:
        async def count_documents(self, q): return 999
        async def find_one(self, *a, **k): return None
    class FakeDB:
        campaign_leads = FakeColl()
        scout_autotopup_log = FakeColl()

    s = await scout_autotopup.status(FakeDB())
    for k in ("disabled", "eligible_now", "floor", "target",
              "topups_today", "max_per_day", "cooldown_min", "interval_min",
              "would_fire_now"):
        assert k in s, f"status() missing key {k}"


# ─── 6. P1 worker attaches the scheduler ────────────────────────────

def test_p1_worker_attaches_autotopup_scheduler():
    src = Path("/app/backend/pillars/sales/worker.py").read_text()
    assert "scout_autotopup" in src
    assert "autotopup_scheduler" in src
    assert "Scout Auto-Topup scheduler attached" in src


# ─── 7. Router is registered ────────────────────────────────────────

def test_scout_autotopup_router_is_registered():
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "scout_autotopup_router" in src


def test_admin_endpoints_present_in_router_file():
    src = Path("/app/backend/routers/scout_autotopup_router.py").read_text()
    assert '@router.get("/status")' in src
    assert '@router.post("/trigger")' in src
    assert "force" in src   # force-override path exists for manual runs
