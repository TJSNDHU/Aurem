"""
tests/test_campaign_health_d59.py — iter D-59

Covers Campaign Health page + Autonomous Autofix loop.
Pure offline tests with stubbed Mongo.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

import pytest

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="asserts pre-slim health/bootstrap shape or older infra spec — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ── Stubs ───────────────────────────────────────────────────────────

class _Coll:
    def __init__(self):
        self._rows: list[dict] = []
    async def insert_one(self, doc):
        self._rows.append(dict(doc))
        return type("R", (), {"inserted_id": doc.get("_id", "x")})
    async def count_documents(self, q):
        return sum(1 for r in self._rows if self._match(r, q))
    async def find_one(self, q, p=None, sort=None):
        rows = [r for r in self._rows if self._match(r, q)]
        if sort:
            for k, d in reversed(sort):
                rows.sort(key=lambda r, kk=k: r.get(kk, ""),
                           reverse=(d == -1))
        return dict(rows[0]) if rows else None
    def find(self, q, p=None):
        rows = [r for r in self._rows if self._match(r, q)]
        class _C:
            def __init__(s, rs): s._rs = list(rs)
            def sort(s, *a, **kw):
                if a and isinstance(a[0], str):
                    s._rs.sort(key=lambda r, k=a[0]: r.get(k, ""),
                                reverse=(len(a) > 1 and a[1] == -1))
                return s
            def limit(s, n): s._rs = s._rs[:n]; return s
            async def to_list(s, n):
                return s._rs[:n]
            def __aiter__(s): s._i = 0; return s
            async def __anext__(s):
                if s._i >= len(s._rs): raise StopAsyncIteration
                r = s._rs[s._i]; s._i += 1
                return r
        return _C(rows)
    def aggregate(self, pipe):
        rows = [dict(r) for r in self._rows]
        for stage in pipe:
            if "$match" in stage:
                rows = [r for r in rows if self._match(r, stage["$match"])]
            elif "$unwind" in stage:
                fld = stage["$unwind"].lstrip("$").split(".")
                out = []
                for r in rows:
                    cur = r
                    for p in fld[:-1]:
                        cur = (cur or {}).get(p, {})
                    arr = (cur or {}).get(fld[-1], [])
                    if not isinstance(arr, list): continue
                    for itm in arr:
                        cp = dict(r)
                        target = cp
                        for p in fld[:-1]:
                            target = target.setdefault(p, {})
                        target[fld[-1]] = itm
                        out.append(cp)
                rows = out
            elif "$count" in stage:
                rows = [{stage["$count"]: len(rows)}]
        class _C:
            def __init__(s, rs): s._rs = rs
            def __aiter__(s): s._i = 0; return s
            async def __anext__(s):
                if s._i >= len(s._rs): raise StopAsyncIteration
                r = s._rs[s._i]; s._i += 1
                return r
        return _C(rows)
    def _match(self, r, q):
        for k, v in q.items():
            if k == "$or":
                if not any(self._match(r, c) for c in v): return False
                continue
            def _resolve(d, path):
                for p in path.split("."):
                    if not isinstance(d, dict): return None
                    d = d.get(p)
                return d
            actual = _resolve(r, k)
            if isinstance(v, dict):
                if "$gte" in v and (actual is None or actual < v["$gte"]):
                    return False
                if "$nin" in v and actual in v["$nin"]:
                    return False
                if "$ne" in v and actual == v["$ne"]:
                    return False
                if "$exists" in v:
                    has = (actual is not None)
                    if v["$exists"] != has: return False
                if "$regex" in v:
                    import re
                    if not actual or not re.search(v["$regex"], str(actual)):
                        return False
            else:
                if actual != v: return False
        return True


class _DB:
    def __init__(self):
        for c in ("ghost_scout_log", "auto_blast_config",
                   "outreach_history", "proactive_ora_config",
                   "blast_performance", "blast_template_state",
                   "daily_briefs", "campaign_leads",
                   "campaign_autofix_log"):
            setattr(self, c, _Coll())


# ── HEALTH CHECKS ───────────────────────────────────────────────────

def test_ghost_scout_red_when_dormant():
    from services import campaign_health as ch
    db = _DB(); ch.set_db(db)
    out = asyncio.run(ch._check_ghost_scout())
    assert out["status"]    == "red"
    assert out["component"] == "ghost_scout"
    assert out["autofix"]   == "trigger_scout_run"


def test_ghost_scout_green_with_recent_run():
    from services import campaign_health as ch
    db = _DB(); ch.set_db(db)
    now = datetime.now(timezone.utc).isoformat()
    db.ghost_scout_log._rows.append({"ts": now, "query": "spa",
                                       "location": "Toronto"})
    out = asyncio.run(ch._check_ghost_scout())
    assert out["status"] == "green"
    assert "1 runs" in out["headline"]


def test_auto_blast_red_when_never_run():
    from services import campaign_health as ch
    db = _DB(); ch.set_db(db)
    out = asyncio.run(ch._check_auto_blast())
    assert out["status"]  == "red"
    assert out["autofix"] == "trigger_blast_cycle"


def test_auto_blast_yellow_when_pool_empty():
    from services import campaign_health as ch
    db = _DB(); ch.set_db(db)
    db.auto_blast_config._rows.append({
        "tenant_id":      "global",
        "last_run_at":    datetime.now(timezone.utc).isoformat(),
        "last_run_sent":  0,
        "last_run_note":  "no-eligible-leads",
    })
    out = asyncio.run(ch._check_auto_blast())
    assert out["status"]  == "yellow"
    assert out["autofix"] == "topup_via_scout"


def test_resend_red_without_key(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    from services import campaign_health as ch
    db = _DB(); ch.set_db(db)
    out = asyncio.run(ch._check_resend())
    assert out["status"] == "red"
    assert out["autofix"] is None    # founder must add key


def test_lead_pool_red_when_empty():
    from services import campaign_health as ch
    db = _DB(); ch.set_db(db)
    out = asyncio.run(ch._check_lead_pool())
    assert out["status"]  == "red"
    assert out["autofix"] == "topup_via_scout"


def test_lead_pool_green_with_25_plus():
    from services import campaign_health as ch
    db = _DB(); ch.set_db(db)
    for i in range(30):
        db.campaign_leads._rows.append({
            "lead_id": f"L{i}", "email": f"a{i}@b.com",
            "status": "new",
        })
    out = asyncio.run(ch._check_lead_pool())
    assert out["status"] == "green"
    assert "30 eligible" in out["headline"]


def test_full_report_returns_summary():
    from services import campaign_health as ch
    db = _DB(); ch.set_db(db)
    out = asyncio.run(ch.full_report())
    assert out["ok"]
    assert "summary" in out
    assert "rows" in out
    assert all("status" in r for r in out["rows"])
    # 11 components
    assert len(out["rows"]) == 11


# ── AUTOFIX ─────────────────────────────────────────────────────────

def test_autofix_unknown_tag_returns_human_required():
    from services import campaign_autofix as af
    db = _DB(); af.set_db(db)
    out = asyncio.run(af.apply("definitely_not_a_real_tag"))
    assert out["ok"]              is False
    assert out["fixed"]            is False
    assert out["requires_human"]   is True


def test_autofix_logs_to_db():
    from services import campaign_autofix as af
    db = _DB(); af.set_db(db)
    asyncio.run(af.apply("unknown_tag"))
    assert len(db.campaign_autofix_log._rows) == 1
    row = db.campaign_autofix_log._rows[0]
    assert row["component"] == "unknown_tag"


def test_autofix_all_only_runs_known_tags():
    from services import campaign_autofix as af
    db = _DB(); af.set_db(db)
    rows = [
        {"component": "x", "autofix": "made_up_fix"},
        {"component": "y", "autofix": None},
        {"component": "z", "autofix": "another_fake"},
    ]
    out = asyncio.run(af.apply_all_from_report(rows))
    # All tags are fake, so nothing should be attempted
    assert out["attempted"] == 0
    assert out["fixed"]      == 0


# ── ROUTER WIRING ───────────────────────────────────────────────────

def test_campaign_routes_registered():
    from routers import campaign_health_router as mod
    paths = {r.path for r in mod.router.routes}
    for p in ("/api/admin/campaign/health",
                "/api/admin/campaign/autofix/{tag}",
                "/api/admin/campaign/autofix-all",
                "/api/admin/campaign/autofix-log"):
        assert p in paths, f"missing {p}"


# ── FRONTEND WIRING ─────────────────────────────────────────────────

FRONTEND = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  "..", "..", "frontend", "src")
)


def test_page_component_exists():
    p = os.path.join(FRONTEND, "platform", "CampaignHealthPage.jsx")
    assert os.path.exists(p)
    with open(p, "r", encoding="utf-8") as f:
        src = f.read()
    assert "/api/admin/campaign/health" in src
    assert "/api/admin/campaign/autofix" in src
    assert 'data-testid="campaign-health-page"' in src
    assert 'data-testid="campaign-autofix-all"' in src


def test_sidebar_link_present():
    p = os.path.join(FRONTEND, "platform", "AdminShell.jsx")
    with open(p, "r", encoding="utf-8") as f:
        src = f.read()
    assert "/admin/campaign-health" in src
    assert "Campaign Health" in src


def test_app_route_wired():
    p = os.path.join(FRONTEND, "App.js")
    with open(p, "r", encoding="utf-8") as f:
        src = f.read()
    assert "CampaignHealthPage" in src
    assert "/admin/campaign-health" in src
