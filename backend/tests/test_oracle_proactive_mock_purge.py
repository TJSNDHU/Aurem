"""
Step 3 of P0 mock purge — oracle_proactive.py auto-scout fill must:
  • Import discover_real_leads_via_apollo (the real function)
  • NEVER import generate_simulated_leads (deleted in Step 2 cleanup)
  • Record campaigns with data_source="apollo" (never "simulated")
  • Await the async Apollo call
  • Skip the cycle on apollo_rate_limit_pause without throwing
  • Skip the cycle when Apollo returns 0 (no fabrication)
"""
from __future__ import annotations

import asyncio
import importlib
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _read(p): 
    with open(p, "r", encoding="utf-8") as f: return f.read()


def _reload():
    for m in ("services.oracle_proactive", "services.proximity_blast",
                "services.apollo_discovery"):
        if m in sys.modules: del sys.modules[m]
    return importlib.import_module("services.oracle_proactive")


# ── Source invariants ───────────────────────────────────────────

def test_no_simulated_imports_left():
    src = _read(os.path.join(ROOT, "services", "oracle_proactive.py"))
    assert "generate_simulated_leads" not in src, (
        "oracle_proactive must not reference the removed alias"
    )
    assert "discover_real_leads_via_apollo" in src


def test_no_simulated_data_source_strings():
    src = _read(os.path.join(ROOT, "services", "oracle_proactive.py"))
    assert '"data_source": "simulated"' not in src
    assert '"data_source": "apollo"' in src


def test_apollo_call_is_awaited():
    src = _read(os.path.join(ROOT, "services", "oracle_proactive.py"))
    assert "await discover_real_leads_via_apollo(" in src


# ── Runtime behaviour ──────────────────────────────────────────

class _Coll:
    def __init__(self):
        self._rows = []
    async def find_one(self, q, p=None):
        return None
    async def insert_one(self, doc):
        self._rows.append(dict(doc))
        class _R: inserted_id="x"
        return _R()
    async def insert_many(self, docs):
        self._rows.extend(dict(d) for d in docs)
        class _R: inserted_ids=["x"]*len(docs)
        return _R()
    async def count_documents(self, q): return 0
    def find(self, q=None, p=None):
        rows = list(self._rows)
        class _C:
            def __init__(s, rs): s._rs = rs
            def sort(s, *a, **kw): return s
            def limit(s, n): s._rs = s._rs[:n]; return s
            def __aiter__(s): s._i=0; return s
            async def __anext__(s):
                if s._i >= len(s._rs): raise StopAsyncIteration
                r = s._rs[s._i]; s._i += 1; return r
            async def to_list(s, n=None): return s._rs[:n or len(s._rs)]
        return _C(rows)


class _DB:
    def __init__(self):
        self.proximity_campaigns = _Coll()
        self.proximity_config    = _Coll()
        self.envoy_outreach      = _Coll()
        # oracle_proactive expects a couple more collections at top-level
        self.aurem_workspaces    = _Coll()
        self.lead_pipeline       = _Coll()


def test_skips_when_apollo_returns_empty(monkeypatch):
    op = _reload()
    db = _DB()
    monkeypatch.setattr(op, "_get_db", lambda: db)
    import services.proximity_blast as pb
    async def _empty(*a, **kw): return []
    monkeypatch.setattr(pb, "discover_real_leads_via_apollo", _empty)
    result = asyncio.run(op._trigger_background_scout("tenant_x"))
    assert result is False
    # No tasks queued
    assert len(db.envoy_outreach._rows) == 0


def test_queues_real_leads_on_success(monkeypatch):
    op = _reload()
    db = _DB()
    monkeypatch.setattr(op, "_get_db", lambda: db)
    import services.proximity_blast as pb
    async def _real(*a, **kw):
        return [
            {"lead_id": "L1", "business_name": "Mississauga Dental",
              "phone": "+14165550100", "email": "",
              "business_type": "dental", "distance_km": None,
              "website": "https://md.ca"},
            {"lead_id": "L2", "business_name": "Toronto Spa",
              "phone": "+14165550200", "email": "",
              "business_type": "med spa", "distance_km": None,
              "website": ""},
        ]
    monkeypatch.setattr(pb, "discover_real_leads_via_apollo", _real)
    result = asyncio.run(op._trigger_background_scout("tenant_x"))
    assert result is True
    assert len(db.envoy_outreach._rows) == 2
    assert db.envoy_outreach._rows[0]["business_name"] == "Mississauga Dental"
    assert db.envoy_outreach._rows[0]["source"] == "apollo_discovery"
    # Campaign record must be tagged apollo
    assert len(db.proximity_campaigns._rows) == 1
    assert db.proximity_campaigns._rows[0]["data_source"] == "apollo"


def test_handles_rate_limit_pause_without_crashing(monkeypatch):
    op = _reload()
    db = _DB()
    monkeypatch.setattr(op, "_get_db", lambda: db)
    import services.proximity_blast as pb
    async def _paused(*a, **kw):
        raise RuntimeError("apollo_rate_limit_pause")
    monkeypatch.setattr(pb, "discover_real_leads_via_apollo", _paused)
    result = asyncio.run(op._trigger_background_scout("tenant_x"))
    assert result is False
    assert len(db.envoy_outreach._rows) == 0


def test_script_does_not_have_blank_owner(monkeypatch):
    """Apollo doesn't return owner_name. The outreach script must not
    say 'Hi ,' with a blank — must address the business directly."""
    op = _reload()
    db = _DB()
    monkeypatch.setattr(op, "_get_db", lambda: db)
    import services.proximity_blast as pb
    async def _real(*a, **kw):
        return [{
            "lead_id": "L1", "business_name": "Real Biz",
            "phone": "+14165550100", "email": "",
            "business_type": "dental", "distance_km": None,
        }]
    monkeypatch.setattr(pb, "discover_real_leads_via_apollo", _real)
    asyncio.run(op._trigger_background_scout("tenant_x"))
    script = db.envoy_outreach._rows[0]["script"]
    assert "Hi ," not in script
    assert "Real Biz" in script
