"""
tests/test_public_api_d59.py — iter D-59 Part B

Covers AUREM Public API:
  • Key issuance + secret-only-once invariant
  • Hash-only at-rest storage (no raw secret persisted)
  • Validation (good / bad / revoked / wrong-scope)
  • Daily rate-limit enforcement + reset on new day
  • Usage logging
  • Admin router endpoint registration
  • Public router endpoint registration + /health anonymous
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


# ── Minimal async Mongo stub ────────────────────────────────────────

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
                return dict(r)
        return None

    def find(self, q, p=None):
        rows = [dict(r) for r in self._rows if self._match(r, q)]
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
            async def to_list(s, n=None): return s._rs[: n or len(s._rs)]
        return _C(rows)

    async def update_one(self, q, upd, upsert=False):
        for r in self._rows:
            if self._match(r, q):
                for k, v in (upd.get("$set") or {}).items():
                    r[k] = v
                for k, v in (upd.get("$inc") or {}).items():
                    r[k] = int(r.get(k, 0)) + int(v)
                class _R:
                    modified_count = 1
                    matched_count = 1
                    upserted_id = None
                return _R()
        if upsert:
            doc = dict(q)
            doc.update(upd.get("$set") or {})
            for k, v in (upd.get("$inc") or {}).items():
                doc[k] = int(v)
            self._rows.append(doc)
            class _R:
                modified_count = 0
                matched_count = 0
                upserted_id = "x"
            return _R()
        class _R:
            modified_count = 0
            matched_count = 0
            upserted_id = None
        return _R()

    async def count_documents(self, q):
        return sum(1 for r in self._rows if self._match(r, q))

    def aggregate(self, pipe):
        rows = [dict(r) for r in self._rows]
        for stage in pipe:
            if "$match" in stage:
                rows = [r for r in rows if self._match(r, stage["$match"])]
            elif "$group" in stage:
                key_expr = stage["$group"]["_id"]
                groups: dict = {}
                for r in rows:
                    k = r.get(key_expr.lstrip("$"), None) if isinstance(key_expr, str) else None
                    g = groups.setdefault(k, {"_id": k})
                    for fld, agg in stage["$group"].items():
                        if fld == "_id": continue
                        if "$sum" in agg:
                            v = agg["$sum"]
                            g[fld] = g.get(fld, 0) + (1 if v == 1 else int(v))
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
            if isinstance(v, dict):
                if "$gte" in v and (r.get(k) is None or r.get(k) < v["$gte"]):
                    return False
                if "$ne" in v and r.get(k) == v["$ne"]:
                    return False
                if "$exists" in v:
                    has = k in r
                    if has != v["$exists"]: return False
            else:
                if r.get(k) != v: return False
        return True


class _DB:
    def __init__(self):
        self.aurem_api_keys  = _Coll()
        self.aurem_api_usage = _Coll()


# ── ISSUANCE ─────────────────────────────────────────────────────────

def test_issue_returns_raw_secret_once():
    from services import aurem_public_api as svc
    db = _DB(); svc.set_db(db)
    out = asyncio.run(svc.issue_key(
        name="founder primary", owner_email="founder@aurem.live",
    ))
    assert out["ok"]
    assert out["secret"].startswith("aurem_sk_live_")
    assert len(out["secret"]) > 30
    # Stored row should never contain the cleartext secret
    stored = db.aurem_api_keys._rows[0]
    assert "key_hash" in stored
    assert stored.get("key_hash") != out["secret"]
    assert out["secret"] not in str(stored)


def test_issue_stores_only_prefix_and_hash():
    from services import aurem_public_api as svc
    db = _DB(); svc.set_db(db)
    out = asyncio.run(svc.issue_key(
        name="t", owner_email="t@x.com",
    ))
    stored = db.aurem_api_keys._rows[0]
    assert stored["key_prefix"].startswith("aurem_sk_live_")
    assert len(stored["key_prefix"]) == 20      # exactly first 20 chars
    assert stored["key_prefix"] in out["secret"]


def test_issue_assigns_default_scopes_and_limits():
    from services import aurem_public_api as svc
    db = _DB(); svc.set_db(db)
    out = asyncio.run(svc.issue_key(name="x", owner_email="x@x.com"))
    k = out["key"]
    assert "ora_chat" in k["scopes"]
    assert "cto_chat" in k["scopes"]
    assert "leads_read" in k["scopes"]
    assert k["rate_limit_per_day"] == 5000


# ── VALIDATION ───────────────────────────────────────────────────────

def test_validate_valid_key_returns_row():
    from services import aurem_public_api as svc
    db = _DB(); svc.set_db(db)
    out = asyncio.run(svc.issue_key(name="t", owner_email="t@x.com"))
    secret = out["secret"]
    row = asyncio.run(svc.validate_key(secret, scope="ora_chat"))
    assert row is not None
    assert row["key_id"] == out["key"]["key_id"]


def test_validate_garbage_returns_none():
    from services import aurem_public_api as svc
    db = _DB(); svc.set_db(db)
    assert asyncio.run(svc.validate_key("garbage", "ora_chat")) is None
    assert asyncio.run(svc.validate_key("", "ora_chat")) is None
    assert asyncio.run(svc.validate_key("aurem_sk_live_x", "ora_chat")) is None


def test_validate_revoked_key_returns_none():
    from services import aurem_public_api as svc
    db = _DB(); svc.set_db(db)
    out = asyncio.run(svc.issue_key(name="t", owner_email="t@x.com"))
    asyncio.run(svc.revoke(out["key"]["key_id"]))
    assert asyncio.run(svc.validate_key(out["secret"], "ora_chat")) is None


def test_validate_wrong_scope_returns_none():
    from services import aurem_public_api as svc
    db = _DB(); svc.set_db(db)
    out = asyncio.run(svc.issue_key(
        name="t", owner_email="t@x.com", scopes=["leads_read"],
    ))
    assert asyncio.run(svc.validate_key(out["secret"], "ora_chat")) is None
    assert asyncio.run(svc.validate_key(out["secret"], "leads_read")) is not None


# ── RATE LIMIT ───────────────────────────────────────────────────────

def test_rate_limit_blocks_after_quota():
    from services import aurem_public_api as svc
    db = _DB(); svc.set_db(db)
    out = asyncio.run(svc.issue_key(
        name="t", owner_email="t@x.com", rate_per_day=2,
    ))
    kid = out["key"]["key_id"]
    today = datetime.now(timezone.utc).date().isoformat()
    # Mark the key as "fully used" today
    db.aurem_api_keys._rows[0]["usage_day"]   = today
    db.aurem_api_keys._rows[0]["usage_today"] = 2
    allowed, reason = asyncio.run(svc.check_rate_limit(kid))
    assert not allowed
    assert reason == "daily_quota_exceeded"


def test_rate_limit_resets_on_new_day():
    from services import aurem_public_api as svc
    db = _DB(); svc.set_db(db)
    out = asyncio.run(svc.issue_key(
        name="t", owner_email="t@x.com", rate_per_day=2,
    ))
    kid = out["key"]["key_id"]
    # Pretend yesterday was exhausted
    db.aurem_api_keys._rows[0]["usage_day"]   = "2000-01-01"
    db.aurem_api_keys._rows[0]["usage_today"] = 999
    allowed, _ = asyncio.run(svc.check_rate_limit(kid))
    assert allowed
    # Counter should have been reset
    assert db.aurem_api_keys._rows[0]["usage_today"] == 0


# ── USAGE ────────────────────────────────────────────────────────────

def test_record_usage_increments_counters_and_logs():
    from services import aurem_public_api as svc
    db = _DB(); svc.set_db(db)
    out = asyncio.run(svc.issue_key(name="t", owner_email="t@x.com"))
    kid = out["key"]["key_id"]
    asyncio.run(svc.record_usage(kid, "/ora/chat", 200, 123))
    asyncio.run(svc.record_usage(kid, "/ora/chat", 200, 89))
    assert db.aurem_api_keys._rows[0]["usage_total"] == 2
    assert db.aurem_api_keys._rows[0]["usage_today"] == 2
    assert len(db.aurem_api_usage._rows) == 2


# ── ROUTER WIRING ────────────────────────────────────────────────────

def test_public_router_paths_registered():
    from routers import public_api_router as mod
    paths = {r.path for r in mod.router.routes}
    for p in ("/api/v1/public/health",
                "/api/v1/public/ora/chat",
                "/api/v1/public/cto/chat",
                "/api/v1/public/leads/lookup"):
        assert p in paths, f"missing {p}"


def test_admin_router_paths_registered():
    from routers import admin_api_keys_router as mod
    paths = {r.path for r in mod.router.routes}
    for p in ("/api/admin/public-api-keys",
                "/api/admin/public-api-keys/issue",
                "/api/admin/public-api-keys/{key_id}/revoke",
                "/api/admin/public-api-keys/{key_id}/usage"):
        assert p in paths, f"missing {p}"


def test_admin_router_wired_in_registry():
    """Defence-in-depth: assert the registry import block exists."""
    p = os.path.join(ROOT, "routers", "registry.py")
    with open(p, "r", encoding="utf-8") as f:
        src = f.read()
    assert "admin_api_keys_router" in src
    assert "public_api_router" in src


# ── FRONTEND WIRING ─────────────────────────────────────────────────

FRONTEND = os.path.normpath(
    os.path.join(ROOT, "..", "frontend", "src")
)


def test_admin_api_keys_page_present():
    p = os.path.join(FRONTEND, "platform", "AdminApiKeysPage.jsx")
    assert os.path.exists(p), "AdminApiKeysPage.jsx not created yet"
    with open(p, "r", encoding="utf-8") as f:
        src = f.read()
    assert "/api/admin/public-api-keys" in src
    assert 'data-testid="admin-api-keys-page"' in src
    assert 'data-testid="api-key-issue-btn"' in src


def test_app_route_and_sidebar_wired():
    with open(os.path.join(FRONTEND, "App.js"), "r", encoding="utf-8") as f:
        app_src = f.read()
    with open(os.path.join(FRONTEND, "platform", "AdminShell.jsx"),
                "r", encoding="utf-8") as f:
        shell_src = f.read()
    assert "AdminApiKeysPage" in app_src
    assert "/admin/api-keys" in app_src
    assert "/admin/api-keys" in shell_src
    assert "API Keys" in shell_src
