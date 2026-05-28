"""
tests/test_cto_learning_d53.py — iter D-53

Self-learning system tests. Pure offline — stubbed motor collections.
Covers:
  • record_outcome rejects unverified self-reports (403)
  • record_outcome accepts code/github/deploy GREEN + user thumbs-up
  • find_similar ranks by success_rate desc then n desc
  • confidence_for surfaces the best approach
  • weekly_self_review aggregates last-7-day rows and upserts the report
  • Router endpoints are registered
  • Sunday 02:00 UTC scheduler stub wired in registry.py
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ──────────────────────────────────────────────────────────────────
# Stubs
# ──────────────────────────────────────────────────────────────────

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

    async def update_one(self, q, upd, upsert=False):
        for r in self._rows:
            if self._match(r, q):
                r.update(upd.get("$set", {}))
                return type("R", (), {"matched_count": 1,
                                       "modified_count": 1,
                                       "upserted_id": None})
        if upsert:
            doc = {**q, **upd.get("$set", {})}
            self._rows.append(doc)
            return type("R", (), {"matched_count": 0, "modified_count": 0,
                                    "upserted_id": doc.get("_id", "x")})
        return type("R", (), {"matched_count": 0, "modified_count": 0,
                                "upserted_id": None})

    async def distinct(self, key):
        return list({r.get(key) for r in self._rows if r.get(key)})

    def aggregate(self, pipe):
        rows = [dict(r) for r in self._rows]
        for stage in pipe:
            if "$match" in stage:
                rows = [r for r in rows if self._match(r, stage["$match"])]
            elif "$group" in stage:
                rows = self._group(rows, stage["$group"])
            elif "$sort" in stage:
                for k, d in reversed(list(stage["$sort"].items())):
                    rows.sort(key=lambda r, kk=k: r.get(kk, 0),
                               reverse=(d == -1))
            elif "$limit" in stage:
                rows = rows[: stage["$limit"]]
            elif "$project" in stage:
                rows = [self._project(r, stage["$project"]) for r in rows]

        class _C:
            def __init__(s, rs): s._rs = rs; s._i = 0
            def __aiter__(s): return s
            async def __anext__(s):
                if s._i >= len(s._rs):
                    raise StopAsyncIteration
                r = s._rs[s._i]; s._i += 1
                return r
        return _C(rows)

    def _match(self, r, q):
        for k, v in q.items():
            if isinstance(v, dict) and "$gte" in v:
                if r.get(k, "") < v["$gte"]:
                    return False
            elif isinstance(v, dict) and "$in" in v:
                if r.get(k) not in v["$in"]:
                    return False
            else:
                if r.get(k) != v:
                    return False
        return True

    def _group(self, rows, spec):
        groups: dict = {}
        key_spec = spec["_id"]
        for r in rows:
            if isinstance(key_spec, dict):
                key = tuple((kk, r.get(vv.lstrip("$")))
                             for kk, vv in key_spec.items())
            else:
                key = r.get(key_spec.lstrip("$"))
            g = groups.setdefault(key, {"_id": (
                {kk: r.get(vv.lstrip("$"))
                  for kk, vv in key_spec.items()}
                if isinstance(key_spec, dict)
                else r.get(key_spec.lstrip("$"))
            )})
            for fld, op in spec.items():
                if fld == "_id":
                    continue
                if "$sum" in op:
                    val = op["$sum"]
                    if isinstance(val, dict) and "$cond" in val:
                        cond = val["$cond"]
                        c, t, f = cond
                        if isinstance(c, dict) and "$eq" in c:
                            lhs, rhs = c["$eq"]
                            ok = r.get(lhs.lstrip("$")) == rhs
                            g[fld] = g.get(fld, 0) + (t if ok else f)
                        else:
                            g[fld] = g.get(fld, 0)
                    else:
                        g[fld] = g.get(fld, 0) + (val if isinstance(val, int)
                                                    else 1)
                elif "$max" in op:
                    cur = g.get(fld, "")
                    val = r.get(op["$max"].lstrip("$"), "")
                    g[fld] = val if val > cur else cur
                elif "$last" in op:
                    fld_path = op["$last"].lstrip("$")
                    # support metadata.error_text
                    parts = fld_path.split(".")
                    val = r
                    for p in parts:
                        val = (val or {}).get(p)
                    g[fld] = val
        return list(groups.values())

    def _project(self, r, spec):
        def _eval(expr, row):
            # Recursive evaluation of nested $cond/$divide/etc.
            if isinstance(expr, str) and expr.startswith("$"):
                return row.get(expr.lstrip("$"), 0)
            if isinstance(expr, dict):
                if "$cond" in expr:
                    c, t, f = expr["$cond"]
                    return _eval(t, row) if _eval(c, row) else _eval(f, row)
                if "$gt" in expr:
                    a, b = expr["$gt"]
                    return _eval(a, row) > _eval(b, row)
                if "$eq" in expr:
                    a, b = expr["$eq"]
                    return _eval(a, row) == _eval(b, row)
                if "$divide" in expr:
                    a, b = expr["$divide"]
                    bv = _eval(b, row); av = _eval(a, row)
                    return (av / bv) if bv else 0
            return expr

        out = {}
        for k, v in spec.items():
            if v == 0:
                continue
            if v == 1:
                out[k] = r.get(k)
            elif isinstance(v, str) and v.startswith("$"):
                out[k] = r.get(v.lstrip("$"))
            elif isinstance(v, dict):
                out[k] = _eval(v, r)
        return out


class _DB:
    def __init__(self):
        self.cto_learnings       = _Coll()
        self.cto_weekly_reports  = _Coll()


# ──────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────

def test_record_rejects_unverified():
    from services import cto_learning as svc
    svc.set_db(_DB())
    with pytest.raises(ValueError) as ei:
        asyncio.run(svc.record_outcome(
            task_type="mobile_fix", approach="add CSS class",
            result="success", verified_by="cto_self_report",
            actor="x"))
    assert "unverified" in str(ei.value)


def test_record_accepts_all_verify_layers():
    from services import cto_learning as svc
    db = _DB(); svc.set_db(db)
    for vb in ("code_green", "github_green", "deploy_green",
                "user_thumbs_up"):
        out = asyncio.run(svc.record_outcome(
            task_type="t1", approach="a1", result="success",
            verified_by=vb, actor="x"))
        assert out["verified_by"] == vb
    assert len(db.cto_learnings._rows) == 4


def test_find_similar_ranks_by_success_rate():
    from services import cto_learning as svc
    db = _DB(); svc.set_db(db)
    # Two approaches for same task_type — approach A has 3/3 success,
    # approach B has 1/4 success. A must rank above B.
    for _ in range(3):
        asyncio.run(svc.record_outcome(
            task_type="mobile_fix", approach="add CSS class",
            result="success", verified_by="github_green", actor="x"))
    asyncio.run(svc.record_outcome(
        task_type="mobile_fix", approach="inline style hack",
        result="success", verified_by="github_green", actor="x"))
    for _ in range(3):
        asyncio.run(svc.record_outcome(
            task_type="mobile_fix", approach="inline style hack",
            result="failure", verified_by="github_green", actor="x"))

    rows = asyncio.run(svc.find_similar("mobile_fix"))
    assert rows[0]["approach"]    == "add CSS class"
    assert rows[0]["success_rate"] == 1.0
    assert rows[1]["approach"]    == "inline style hack"
    assert rows[1]["success_rate"] < 0.5


def test_confidence_for_surfaces_best():
    from services import cto_learning as svc
    db = _DB(); svc.set_db(db)
    for _ in range(5):
        asyncio.run(svc.record_outcome(
            task_type="auth_bug", approach="bcrypt rotate",
            result="success", verified_by="deploy_green", actor="x"))
    out = asyncio.run(svc.confidence_for("auth_bug"))
    assert out["n"] == 5
    assert out["success_rate"]  == 1.0
    assert out["best_approach"] == "bcrypt rotate"


def test_confidence_returns_zero_for_unknown_task():
    from services import cto_learning as svc
    svc.set_db(_DB())
    out = asyncio.run(svc.confidence_for("never_seen_task"))
    assert out["n"] == 0
    assert out["success_rate"] == 0.0


def test_weekly_review_aggregates_and_upserts():
    from services import cto_learning as svc
    db = _DB(); svc.set_db(db)
    # Seed two successes + one failure within last 7d
    for r in ("success", "success"):
        asyncio.run(svc.record_outcome(
            task_type="api_endpoint", approach="fastapi router",
            result=r, verified_by="deploy_green", actor="x"))
    asyncio.run(svc.record_outcome(
        task_type="api_endpoint", approach="raw asgi",
        result="failure", verified_by="deploy_green", actor="x",
        metadata={"error_text": "404 not found"}))

    report = asyncio.run(svc.weekly_self_review())
    assert report["learnings_added"] == 3
    assert abs(report["success_rate"] - (2 / 3)) < 0.01
    # Top patterns has the successful approach
    assert any(p["approach"] == "fastapi router"
                for p in report["top_patterns"])
    # Failed patterns carries the error
    assert any(p["last_error"] == "404 not found"
                for p in report["failed_patterns"])

    # Idempotent — second run replaces, doesn't duplicate
    asyncio.run(svc.weekly_self_review())
    assert len(db.cto_weekly_reports._rows) == 1


def test_router_endpoints_registered():
    from routers import cto_learning_router as mod
    paths = {r.path for r in mod.router.routes}
    assert "/api/developers/cto/learning/record"             in paths
    assert "/api/developers/cto/learning/similar"            in paths
    assert "/api/developers/cto/learning/confidence"         in paths
    assert "/api/developers/cto/learning/stats"              in paths
    assert "/api/developers/cto/learning/weekly-report"      in paths
    assert "/api/developers/cto/learning/weekly-report/run-now" in paths


def test_record_endpoint_rejects_self_report():
    """403 must surface to the chat — no silent learning."""
    from routers import cto_learning_router as mod
    db = _DB(); mod.set_db(db)

    async def _fake_admin(_a): return "admin@aurem.live"
    mod._require_admin = _fake_admin

    body = mod.RecordBody(task_type="xx", approach="yy", result="success",
                            verified_by="cto_says_so", metadata={})
    with pytest.raises(Exception) as ei:
        asyncio.run(mod.record(body, authorization="Bearer x"))
    # FastAPI's HTTPException(403, …) — string form has status_code
    assert "403" in str(ei.value) or "unverified" in str(ei.value)


def test_sunday_cron_wired_in_registry():
    """The Sunday 02:00 UTC cron is wired in registry.py."""
    path = os.path.join(ROOT, "routers", "registry.py")
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    assert "cto_learning_weekly_review"            in src
    # Match the cron wiring with relaxed whitespace.
    assert re.search(r'day_of_week\s*=\s*"sun"', src) is not None
    assert re.search(r'hour\s*=\s*2,\s*minute\s*=\s*0', src) is not None
