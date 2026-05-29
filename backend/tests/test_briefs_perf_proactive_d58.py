"""
tests/test_briefs_perf_proactive_d58.py — iter D-58

Covers all three D-58 features end-to-end (offline / stubbed):
  1. Daily Brief — morning + evening text composition, persistence
  2. Template Performance — record_event, aggregation, weekly_rotate
     (promotes best, retires < 10 % open, never auto-retires founder-locked)
  3. Proactive ORA — config get/set, rate-limit, CASL compliance, each
     of R1/R2/R3/R4 runs only when enabled.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

import pytest

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
            def __aiter__(s): s._i = 0; return s
            async def __anext__(s):
                if s._i >= len(s._rs): raise StopAsyncIteration
                r = s._rs[s._i]; s._i += 1
                return r
            async def to_list(s, n):
                return s._rs[:n]
        return _C(rows)

    async def update_one(self, q, upd, upsert=False):
        for r in self._rows:
            if self._match(r, q):
                r.update(upd.get("$set", {}))
                return type("R", (), {"matched_count": 1,
                                       "modified_count": 1})
        if upsert:
            doc = {**q, **upd.get("$set", {})}
            self._rows.append(doc)
            return type("R", (), {"matched_count": 0, "modified_count": 0})
        return type("R", (), {"matched_count": 0, "modified_count": 0})

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
                    if not isinstance(arr, list):
                        continue
                    for itm in arr:
                        cp = dict(r)
                        # set nested key path → itm
                        target = cp
                        for p in fld[:-1]:
                            target = target.setdefault(p, {})
                        target[fld[-1]] = itm
                        out.append(cp)
                rows = out
            elif "$group" in stage:
                spec = stage["$group"]
                groups: dict = {}
                key_spec = spec["_id"]
                for r in rows:
                    def get_path(d, path):
                        for p in path.lstrip("$").split("."):
                            d = (d or {}).get(p) if isinstance(d, dict) else None
                            if d is None: return None
                        return d
                    if isinstance(key_spec, dict):
                        key = tuple((kk, get_path(r, vv))
                                     for kk, vv in key_spec.items())
                    else:
                        key = get_path(r, key_spec)
                    g = groups.setdefault(key, {"_id": (
                        {kk: get_path(r, vv) for kk, vv in key_spec.items()}
                        if isinstance(key_spec, dict)
                        else get_path(r, key_spec)
                    )})
                    for fld, op in spec.items():
                        if fld == "_id": continue
                        if "$sum" in op:
                            val = op["$sum"]
                            g[fld] = g.get(fld, 0) + (val if isinstance(val, int) else 1)
                rows = list(groups.values())

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
                if not any(self._match(r, cond) for cond in v):
                    return False
                continue
            # Nested field path support (e.g. "verification.channel_gating.email")
            def _resolve(doc, path):
                cur = doc
                for p in path.split("."):
                    if not isinstance(cur, dict):
                        return None
                    cur = cur.get(p)
                return cur
            actual = _resolve(r, k)
            if isinstance(v, dict):
                if "$gte" in v and (actual is None or actual < v["$gte"]):
                    return False
                if "$lte" in v and (actual is None or actual > v["$lte"]):
                    return False
                if "$in" in v and actual not in v["$in"]:
                    return False
                if "$nin" in v and actual in v["$nin"]:
                    return False
                if "$ne" in v and actual == v["$ne"]:
                    return False
                if "$exists" in v:
                    has = (actual is not None)
                    if v["$exists"] != has:
                        return False
                if "$regex" in v:
                    import re
                    if not actual or not re.search(v["$regex"], str(actual)):
                        return False
            else:
                if actual != v:
                    return False
        return True


class _DB:
    def __init__(self):
        self.campaign_leads        = _Coll()
        self.outreach_history      = _Coll()
        self.daily_briefs          = _Coll()
        self.blast_performance     = _Coll()
        self.blast_template_state  = _Coll()
        self.proactive_ora_config  = _Coll()
        self.auto_blast_config     = _Coll()
        self.cta_clicks            = _Coll()
        self.auto_websites         = _Coll()


# ── FEATURE 1 — Daily Brief ─────────────────────────────────────────

def test_morning_brief_text_includes_3_top_tasks():
    from services.daily_brief import _morning_text
    stats = {"new_leads": 12, "delivered_email": 0, "hot_window": 5,
              "hot_clicked": 2, "eligible_leads": 0}
    txt = _morning_text(stats)
    assert "Morning Brief" in txt
    assert "12 new leads" in txt
    # Top 3 tasks present (with numbering 1, 2, 3)
    assert "1." in txt and "2." in txt and "3." in txt


def test_evening_brief_includes_tomorrow_preview():
    from services.daily_brief import _evening_text
    stats = {"delivered_email": 3, "delivered_sms": 0, "hot_window": 1,
              "hot_clicked": 0, "last_blast_note": "ok",
              "last_blast_sent": 3, "eligible_leads": 20,
              "new_leads": 5}
    txt = _evening_text(stats)
    assert "Evening Wrap" in txt
    assert "Tomorrow" in txt
    assert "20 eligible" in txt


def test_brief_persists_to_db():
    from services import daily_brief as svc
    db = _DB()
    svc.set_db(db)
    # Stub the channel senders
    async def _fake(*a, **kw): return {"ok": True, "id": "fake-id"}
    svc._send_email     = _fake
    svc._send_whatsapp  = _fake

    out = asyncio.run(svc.send_morning_brief())
    assert out["ok"] is True
    assert out["kind"] == "morning"
    assert len(db.daily_briefs._rows) == 1
    saved = db.daily_briefs._rows[0]
    assert saved["kind"] == "morning"
    assert "stats" in saved


def test_brief_router_endpoints_registered():
    from routers import cto_brief_router as mod
    paths = {r.path for r in mod.router.routes}
    for p in ("/api/cto/brief/latest", "/api/cto/brief/run-now",
              "/api/cto/brief/list",
              "/api/cto/perf/templates", "/api/cto/perf/rotate-now",
              "/api/cto/perf/state",
              "/api/cto/proactive/config", "/api/cto/proactive/run-now"):
        assert p in paths, f"missing route {p}"


# ── FEATURE 2 — Template Performance ───────────────────────────────

def test_record_event_appends():
    from services import template_performance as tp
    db = _DB()
    tp.set_db(db)
    asyncio.run(tp.record_event("TPL_A", "sent", lead_id="L1"))
    asyncio.run(tp.record_event("TPL_A", "opened", lead_id="L1"))
    assert len(db.blast_performance._rows) == 2


def test_stats_for_computes_rates():
    from services import template_performance as tp
    db = _DB()
    tp.set_db(db)
    # 20 sent, 8 opened, 2 clicked for TPL_HIGH
    for _ in range(20):
        asyncio.run(tp.record_event("TPL_HIGH", "sent"))
    for _ in range(8):
        asyncio.run(tp.record_event("TPL_HIGH", "opened"))
    for _ in range(2):
        asyncio.run(tp.record_event("TPL_HIGH", "clicked"))
    # 20 sent, 1 opened (5 % — below 10 %)
    for _ in range(20):
        asyncio.run(tp.record_event("TPL_LOW", "sent"))
    asyncio.run(tp.record_event("TPL_LOW", "opened"))

    rows = asyncio.run(tp.stats_for(window_days=30))
    by_id = {r["template_id"]: r for r in rows}
    assert by_id["TPL_HIGH"]["open_rate"] == 0.4
    assert by_id["TPL_LOW"]["open_rate"]  == 0.05
    # ranked best first
    assert rows[0]["template_id"] == "TPL_HIGH"


def test_weekly_rotate_promotes_winner_and_retires_loser():
    from services import template_performance as tp
    db = _DB()
    tp.set_db(db)
    for _ in range(25):
        asyncio.run(tp.record_event("TPL_A", "sent"))
    for _ in range(12):
        asyncio.run(tp.record_event("TPL_A", "opened"))
    for _ in range(25):
        asyncio.run(tp.record_event("TPL_B", "sent"))
    asyncio.run(tp.record_event("TPL_B", "opened"))   # 4 %

    state = asyncio.run(tp.weekly_rotate())
    assert state["default_template"] == "TPL_A"
    assert "TPL_B" in state["retired"]


def test_weekly_rotate_never_retires_founder_locked():
    from services import template_performance as tp
    db = _DB()
    tp.set_db(db)
    # Founder-locked template performing badly
    db.blast_template_state._rows.append({
        "_id": "global", "founder_locked": ["TPL_FOUNDER"],
    })
    for _ in range(25):
        asyncio.run(tp.record_event("TPL_FOUNDER", "sent"))
    # zero opens → 0 %

    state = asyncio.run(tp.weekly_rotate())
    assert "TPL_FOUNDER" not in state["retired"]


# ── FEATURE 3 — Proactive ORA ───────────────────────────────────────

def test_config_default_all_rules_off():
    from services import proactive_ora as pa
    db = _DB()
    pa.set_db(db)
    cfg = asyncio.run(pa.get_config("global"))
    for rule in ("R1", "R2", "R3", "R4"):
        assert cfg["enabled_rules"][rule] is False


def test_set_rule_persists():
    from services import proactive_ora as pa
    db = _DB()
    pa.set_db(db)
    asyncio.run(pa.set_rule("global", "R1", True))
    cfg = asyncio.run(pa.get_config("global"))
    assert cfg["enabled_rules"]["R1"] is True
    assert cfg["enabled_rules"]["R2"] is False


def test_rate_limit_blocks_after_3_touches_per_week():
    from services import proactive_ora as pa
    db = _DB()
    pa.set_db(db)
    now = datetime.now(timezone.utc).isoformat()
    for i in range(3):
        db.outreach_history._rows.append({
            "ts":      now,
            "lead_id": "LEAD_X",
            "type":    "proactive_ora_R1",
            "result":  {"sent": [{"ok": True}]},
        })
    # 4th attempt → rate-limited
    lead = {"lead_id": "LEAD_X", "email": "x@e.com", "status": "emailed"}
    assert asyncio.run(pa._eligible(lead, "R1")) is False


def test_compliance_blocks_dnc_casl_unsub():
    from services import proactive_ora as pa
    db = _DB()
    pa.set_db(db)
    for bad in (
        {"lead_id": "L", "email": "a@b.com", "dnc": True},
        {"lead_id": "L", "email": "a@b.com", "casl_blocked": True},
        {"lead_id": "L", "email": "a@b.com", "status": "unsubscribed"},
    ):
        assert asyncio.run(pa._is_compliant(bad)) is False
    assert asyncio.run(pa._is_compliant(
        {"lead_id": "L", "email": "a@b.com", "status": "emailed"},
    )) is True


def test_run_all_skips_disabled_rules():
    from services import proactive_ora as pa
    db = _DB()
    pa.set_db(db)
    # All rules disabled by default
    out = asyncio.run(pa.run_all("global"))
    assert all(r.get("skipped") == "disabled" for r in out["ran"])


def test_r1_fires_when_enabled_and_eligible():
    from services import proactive_ora as pa
    db = _DB()
    pa.set_db(db)
    # Enable R1
    asyncio.run(pa.set_rule("global", "R1", True))
    # Insert one eligible lead (status="emailed", last_blast_at > 3d ago)
    old = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    db.campaign_leads._rows.append({
        "lead_id":       "L_FU",
        "email":         "test-followup@example.com",
        "business_name": "Test Spa",
        "status":        "emailed",
        "last_blast_at": old,
        "tenant_id":     "global",
    })
    # Stub the send fn → return True
    async def _fake_email(_l): return True
    pa._send_followup_email = _fake_email

    out = asyncio.run(pa.run_r1_no_reply_3d())
    assert out["actions"] == 1
    # outreach_history logged with rule R1
    assert any(r.get("type") == "proactive_ora_R1"
                for r in db.outreach_history._rows)


def test_r2_skips_when_no_phone():
    from services import proactive_ora as pa
    db = _DB()
    pa.set_db(db)
    db.campaign_leads._rows.append({
        "lead_id":            "L_NO_PHONE",
        "email":              "a@b.com",
        "phone":              "",
        "hot_lead_flag":      True,
        "hot_lead_reason":    "email_opened",
        "hot_lead_signal_at": datetime.now(timezone.utc).isoformat(),
        "status":             "emailed",
    })
    out = asyncio.run(pa.run_r2_opened_no_reply())
    assert out["actions"] == 0   # no phone → not eligible for WA
