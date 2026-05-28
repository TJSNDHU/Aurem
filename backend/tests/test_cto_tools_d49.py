"""
tests/test_cto_tools_d49.py — iter D-49

Verifies the real-execution tool surface added at
`/api/developers/cto/tools/*`:

  • whitelist: SECURITY_ALERT_SLACK_WEBHOOK + SECURITY_ALERT_EMAIL
    are now founder-saveable via /api/developers/settings/secrets.
  • import-leads: validates email, dedupes by email/phone, channel-gates
    properly.
  • db-stats: returns campaign_leads breakdown + sent-today + customers.
  • run-scout / run-blast: import paths resolve (no live network).

Pure offline test — DB is stubbed in-memory.
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ──────────────────────────────────────────────────────────────────
# Stubs
# ──────────────────────────────────────────────────────────────────

class _Coll:
    def __init__(self):
        self._rows = []

    async def insert_one(self, doc):
        self._rows.append(dict(doc))
        return type("R", (), {"inserted_id": "x"})

    async def find_one(self, q, p=None):
        for r in self._rows:
            ok = True
            for k, v in q.items():
                if k == "$or":
                    if not any(all(r.get(kk) == vv for kk, vv in cond.items())
                                for cond in v):
                        ok = False
                        break
                elif r.get(k) != v:
                    ok = False
                    break
            if ok:
                return dict(r)
        return None

    async def count_documents(self, q):
        cnt = 0
        for r in self._rows:
            if self._match(r, q):
                cnt += 1
        return cnt

    def _match(self, r, q):
        for k, v in q.items():
            if k == "$or":
                if not any(self._match(r, cond) for cond in v):
                    return False
            elif k == "status" and isinstance(v, dict) and "$in" in v:
                if r.get("status") not in v["$in"]:
                    return False
            elif isinstance(v, dict) and "$exists" in v:
                exists = k in r
                if v["$exists"] != exists:
                    return False
            elif isinstance(v, dict) and "$gte" in v:
                rv = r.get(k)
                if rv is None or rv < v["$gte"]:
                    return False
            else:
                if r.get(k) != v:
                    return False
        return True


class _DB:
    def __init__(self):
        self.campaign_leads   = _Coll()
        self.cto_tool_runs    = _Coll()
        self.sent_emails      = _Coll()
        self.aurem_customers  = _Coll()
        self.auto_blast_config = _Coll()


# ──────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────

def test_whitelist_includes_alert_sinks():
    """D-49: founder can save SECURITY_ALERT_* secrets via UI."""
    from routers.platform_secrets_router import _ALLOWED_SECRETS
    assert "SECURITY_ALERT_SLACK_WEBHOOK" in _ALLOWED_SECRETS
    assert "SECURITY_ALERT_EMAIL"          in _ALLOWED_SECRETS


def test_cto_tools_router_registered():
    """Router file exists and exposes the four documented endpoints."""
    from routers import cto_tools_router as mod
    routes = {r.path for r in mod.router.routes}
    assert "/api/developers/cto/tools/run-scout"   in routes
    assert "/api/developers/cto/tools/import-leads" in routes
    assert "/api/developers/cto/tools/run-blast"   in routes
    assert "/api/developers/cto/tools/db-stats"    in routes


def test_import_leads_inserts_dedupes_and_skips_invalid():
    from routers import cto_tools_router as mod
    db = _DB()
    mod.set_db(db)

    body = mod.ImportLeadsBody(leads=[
        # valid
        mod.LeadIn(business_name="Acme Spa", email="hi@acme.com",
                    phone="+14165550199", city="Toronto"),
        # dup of #1 by email
        mod.LeadIn(business_name="Acme Spa Dup", email="hi@acme.com",
                    phone="+14165550100"),
        # no contact at all → invalid
        mod.LeadIn(business_name="No Contact", email="", phone=""),
        # bad email format → email blanked, phone kept (still valid lead)
        mod.LeadIn(business_name="Phone Only", email="not-an-email",
                    phone="+14165550111"),
    ])

    # bypass admin check by stubbing _require_admin
    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    out = asyncio.run(mod.import_leads(body, authorization="Bearer x"))
    assert out["inserted"]        == 2, out
    assert out["skipped_dup"]     == 1, out
    assert out["skipped_invalid"] == 1, out

    # channel-gating wired
    saved = db.campaign_leads._rows[0]
    assert saved["verification"]["channel_gating"]["email"] is True
    assert saved["verification"]["channel_gating"]["sms"]   is True
    # bad-email lead: only sms gated
    bad = [r for r in db.campaign_leads._rows
            if r["business_name"] == "Phone Only"][0]
    assert bad["verification"]["channel_gating"]["email"] is False
    assert bad["verification"]["channel_gating"]["sms"]   is True


def test_db_stats_returns_live_counts():
    from routers import cto_tools_router as mod
    db = _DB()
    mod.set_db(db)

    # seed
    asyncio.run(db.campaign_leads.insert_one({"status": "new"}))
    asyncio.run(db.campaign_leads.insert_one({"status": "emailed",
                                                 "last_blast_at": "x"}))
    asyncio.run(db.campaign_leads.insert_one({"status": "queued"}))

    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    out = asyncio.run(mod.db_stats(authorization="Bearer x"))
    assert out["ok"] is True
    assert out["campaign_leads"]["total"]   == 3
    # fresh = status in {new, queued} AND no last_blast_at
    assert out["campaign_leads"]["fresh"]   == 2
    assert out["campaign_leads"]["emailed"] == 1


def test_run_scout_payload_shape():
    """Body validation: city / category required, count clamped 1..50."""
    from routers import cto_tools_router as mod
    # valid
    mod.ScoutBody(city="Toronto", category="spa", count=10, country="ca")
    # bad country
    with pytest.raises(Exception):
        mod.ScoutBody(city="Toronto", category="spa", count=10, country="uk")
    # bad count
    with pytest.raises(Exception):
        mod.ScoutBody(city="T", category="spa", count=99)


def test_audit_writes_to_cto_tool_runs():
    from routers import cto_tools_router as mod
    db = _DB()
    mod.set_db(db)
    asyncio.run(mod._audit("run_scout", "admin@aurem.live",
                            {"city": "Toronto"}, {"inserted": 5}))
    assert len(db.cto_tool_runs._rows) == 1
    row = db.cto_tool_runs._rows[0]
    assert row["tool"]   == "run_scout"
    assert row["actor"]  == "admin@aurem.live"
    assert row["result"] == {"inserted": 5}
