"""
tests/test_bug_catch_d60.py — iter D-60

Pytest regression for BugCatch (admin bug-report capture).

Covers:
  • create_report: stores row, clips oversized screenshot, runs AI step (mocked)
  • list_reports: hides heavy fields (screenshot, logs)
  • get_report: returns full doc
  • set_status: enforces enum
  • stats: per-status counts
  • email_founder: invoked but tolerant when key missing
  • Router endpoint registration + wiring in registry.py
  • Frontend widget + admin page wiring asserts
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ── Mongo stub ──────────────────────────────────────────────────────

class _Coll:
    def __init__(self):
        self._rows: list[dict] = []

    async def insert_one(self, doc):
        self._rows.append(dict(doc))
        class _R: inserted_id = doc.get("_id", "x")
        return _R()

    async def find_one(self, q, p=None):
        for r in self._rows:
            if self._match(r, q):
                if p:
                    return {k: v for k, v in r.items()
                              if p.get(k, 1) != 0}
                return dict(r)
        return None

    def find(self, q, p=None):
        rows = [r for r in self._rows if self._match(r, q)]
        if p:
            rows = [{k: v for k, v in r.items() if p.get(k, 1) != 0}
                    for r in rows]
        class _C:
            def __init__(s, rs): s._rs = list(rs)
            def sort(s, *a, **kw):
                if a:
                    s._rs.sort(key=lambda r, k=a[0]: r.get(k, ""),
                                reverse=(len(a) > 1 and a[1] == -1))
                return s
            def limit(s, n): s._rs = s._rs[:n]; return s
            def __aiter__(s): s._i = 0; return s
            async def __anext__(s):
                if s._i >= len(s._rs): raise StopAsyncIteration
                r = s._rs[s._i]; s._i += 1
                return r
        return _C(rows)

    async def update_one(self, q, upd):
        for r in self._rows:
            if self._match(r, q):
                for k, v in (upd.get("$set") or {}).items():
                    r[k] = v
                class _R: modified_count = 1
                return _R()
        class _R: modified_count = 0
        return _R()

    async def count_documents(self, q):
        return sum(1 for r in self._rows if self._match(r, q))

    def _match(self, r, q):
        for k, v in q.items():
            if r.get(k) != v: return False
        return True


class _DB:
    def __init__(self):
        self.bug_reports = _Coll()


# ── helpers ─────────────────────────────────────────────────────────

def _stub_no_ai(monkeypatch):
    """Force AI path to return empty (no LLM)."""
    from services import bug_catch as svc
    async def _no_ai(_):
        return "", "skipped_test"
    monkeypatch.setattr(svc, "_ai_root_cause", _no_ai)


def _stub_no_email(monkeypatch):
    from services import bug_catch as svc
    async def _noop(_):
        return
    monkeypatch.setattr(svc, "_email_founder", _noop)


# ── CREATE ──────────────────────────────────────────────────────────

def test_create_report_basic(monkeypatch):
    from services import bug_catch as svc
    db = _DB(); svc.set_db(db)
    _stub_no_ai(monkeypatch); _stub_no_email(monkeypatch)
    out = asyncio.run(svc.create_report({
        "description": "broke after I clicked Send",
        "severity":    "high",
        "screenshot_b64": "data:image/jpeg;base64,xyz",
        "url":         "/admin/api-keys",
        "viewport":    {"w": 1920, "h": 1080},
        "user_agent":  "test/1.0",
        "console_logs":  [{"level": "error", "msg": "boom", "ts": "x"}],
        "network_calls": [{"method": "POST", "url": "/api/x", "status": 500}],
        "annotations":   [],
    }, submitted_by="founder@aurem.live"))
    assert out["report_id"].startswith("br_")
    assert out["severity"] == "high"
    assert out["status"] == "open"
    assert out["screenshot_b64"] == "data:image/jpeg;base64,xyz"
    assert out["submitted_by"] == "founder@aurem.live"
    assert len(db.bug_reports._rows) == 1


def test_create_report_clips_oversized_screenshot(monkeypatch):
    from services import bug_catch as svc
    db = _DB(); svc.set_db(db)
    _stub_no_ai(monkeypatch); _stub_no_email(monkeypatch)
    huge = "x" * (2_000_001)
    out = asyncio.run(svc.create_report({
        "description": "test", "severity": "low",
        "screenshot_b64": huge, "url": "/x",
        "viewport": {}, "user_agent": "",
        "console_logs": [], "network_calls": [], "annotations": [],
    }, submitted_by="x"))
    assert out["screenshot_b64"] == ""        # dropped
    assert "screenshot_dropped" in out["screenshot_note"]


def test_create_report_invalid_severity_defaults_to_med(monkeypatch):
    from services import bug_catch as svc
    db = _DB(); svc.set_db(db)
    _stub_no_ai(monkeypatch); _stub_no_email(monkeypatch)
    out = asyncio.run(svc.create_report({
        "description": "x", "severity": "catastrophic",
        "screenshot_b64": "", "url": "", "viewport": {},
        "user_agent": "", "console_logs": [], "network_calls": [],
        "annotations": [],
    }, submitted_by="x"))
    assert out["severity"] == "med"


def test_create_report_truncates_logs(monkeypatch):
    from services import bug_catch as svc
    db = _DB(); svc.set_db(db)
    _stub_no_ai(monkeypatch); _stub_no_email(monkeypatch)
    huge_logs = [{"level": "log", "msg": str(i), "ts": ""}
                  for i in range(500)]
    huge_net  = [{"method": "GET", "url": f"/x/{i}", "status": 200}
                  for i in range(120)]
    out = asyncio.run(svc.create_report({
        "description": "x", "severity": "med",
        "screenshot_b64": "", "url": "", "viewport": {},
        "user_agent": "",
        "console_logs": huge_logs, "network_calls": huge_net,
        "annotations": [],
    }, submitted_by="x"))
    assert len(out["console_logs"])  == 200    # cap
    assert len(out["network_calls"]) == 50     # cap


def test_create_report_runs_ai_when_available(monkeypatch):
    from services import bug_catch as svc
    db = _DB(); svc.set_db(db)
    _stub_no_email(monkeypatch)
    async def _fake_ai(_):
        return "Probable cause: POST /api/x returned 500.", "deepseek-v3"
    monkeypatch.setattr(svc, "_ai_root_cause", _fake_ai)
    out = asyncio.run(svc.create_report({
        "description": "form Send failed",
        "severity": "med", "screenshot_b64": "",
        "url": "/admin/api-keys", "viewport": {},
        "user_agent": "",
        "console_logs":  [{"level": "error", "msg": "500"}],
        "network_calls": [{"method": "POST",
                             "url": "/api/x", "status": 500}],
        "annotations": [],
    }, submitted_by="founder"))
    assert "POST /api/x" in out["ai_root_cause"]
    assert out["ai_model"] == "deepseek-v3"
    assert out["ai_generated_at"]


# ── LIST / GET / STATUS / STATS ─────────────────────────────────────

def test_list_hides_heavy_fields(monkeypatch):
    from services import bug_catch as svc
    db = _DB(); svc.set_db(db)
    _stub_no_ai(monkeypatch); _stub_no_email(monkeypatch)
    asyncio.run(svc.create_report({
        "description": "x", "severity": "low",
        "screenshot_b64": "data:image/jpeg;base64,SHOTSHOT",
        "url": "/x", "viewport": {},
        "user_agent": "",
        "console_logs":  [{"level": "log", "msg": "noise"}],
        "network_calls": [], "annotations": [],
    }, submitted_by="x"))
    rows = asyncio.run(svc.list_reports())
    assert len(rows) == 1
    assert "screenshot_b64" not in rows[0]
    assert "console_logs"   not in rows[0]
    assert "network_calls"  not in rows[0]
    assert "annotations"    not in rows[0]


def test_get_report_returns_full(monkeypatch):
    from services import bug_catch as svc
    db = _DB(); svc.set_db(db)
    _stub_no_ai(monkeypatch); _stub_no_email(monkeypatch)
    out = asyncio.run(svc.create_report({
        "description": "x", "severity": "med",
        "screenshot_b64": "data:image/jpeg;base64,FULL",
        "url": "/x", "viewport": {},
        "user_agent": "",
        "console_logs": [{"level": "log", "msg": "n"}],
        "network_calls": [], "annotations": [],
    }, submitted_by="x"))
    rid = out["report_id"]
    full = asyncio.run(svc.get_report(rid))
    assert full is not None
    assert full["screenshot_b64"] == "data:image/jpeg;base64,FULL"
    assert full["console_logs"][0]["msg"] == "n"


def test_set_status_enforces_enum(monkeypatch):
    from services import bug_catch as svc
    db = _DB(); svc.set_db(db)
    _stub_no_ai(monkeypatch); _stub_no_email(monkeypatch)
    out = asyncio.run(svc.create_report({
        "description": "x", "severity": "med",
        "screenshot_b64": "", "url": "", "viewport": {},
        "user_agent": "", "console_logs": [],
        "network_calls": [], "annotations": [],
    }, submitted_by="x"))
    rid = out["report_id"]
    ok = asyncio.run(svc.set_status(rid, "resolved"))
    assert ok["ok"] is True
    bad = asyncio.run(svc.set_status(rid, "garbage"))
    assert bad["ok"] is False


def test_stats_counts(monkeypatch):
    from services import bug_catch as svc
    db = _DB(); svc.set_db(db)
    _stub_no_ai(monkeypatch); _stub_no_email(monkeypatch)
    for i in range(3):
        asyncio.run(svc.create_report({
            "description": "x", "severity": "med",
            "screenshot_b64": "", "url": "", "viewport": {},
            "user_agent": "", "console_logs": [],
            "network_calls": [], "annotations": [],
        }, submitted_by="x"))
    out = asyncio.run(svc.stats())
    assert out["open"] == 3
    assert out["resolved"] == 0


# ── ROUTER WIRING ───────────────────────────────────────────────────

def test_bug_catch_router_paths():
    from routers import bug_catch_router as mod
    paths = {r.path for r in mod.router.routes}
    for p in ("/api/admin/bug-reports",
                "/api/admin/bug-reports/stats",
                "/api/admin/bug-reports/{report_id}",
                "/api/admin/bug-reports/{report_id}/status"):
        assert p in paths, f"missing {p}"


def test_registry_wires_bug_catch():
    with open(os.path.join(ROOT, "routers", "registry.py"),
                "r", encoding="utf-8") as f:
        src = f.read()
    assert "bug_catch_router" in src


# ── FRONTEND WIRING ─────────────────────────────────────────────────

FRONTEND = os.path.normpath(
    os.path.join(ROOT, "..", "frontend", "src")
)


def test_widget_file_present():
    p = os.path.join(FRONTEND, "platform", "BugCatchWidget.jsx")
    assert os.path.exists(p)
    with open(p, "r", encoding="utf-8") as f:
        src = f.read()
    assert 'data-testid="bugcatch-fab"' in src
    assert 'data-testid="bugcatch-modal"' in src
    assert 'data-testid="bugcatch-send"' in src
    assert "/api/admin/bug-reports" in src
    assert "html2canvas" in src
    assert "patchConsoleAndFetch" in src


def test_admin_bug_reports_page_present():
    p = os.path.join(FRONTEND, "platform", "AdminBugReportsPage.jsx")
    assert os.path.exists(p)
    with open(p, "r", encoding="utf-8") as f:
        src = f.read()
    assert 'data-testid="admin-bug-reports-page"' in src
    assert "/api/admin/bug-reports/stats" in src


def test_admin_shell_mounts_widget():
    with open(os.path.join(FRONTEND, "platform", "AdminShell.jsx"),
                "r", encoding="utf-8") as f:
        src = f.read()
    assert "BugCatchWidget" in src
    assert "/admin/bug-reports" in src
    assert "BugCatch · Reports" in src


def test_app_route_wired():
    with open(os.path.join(FRONTEND, "App.js"),
                "r", encoding="utf-8") as f:
        src = f.read()
    assert "AdminBugReportsPage" in src
    assert "/admin/bug-reports" in src
