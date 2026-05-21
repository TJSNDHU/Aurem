"""iter 325m — Brand purge migration regression tests.

Locks in:
  1. Pattern rewrites every casing variant of ReRoots/REROOTS/Reroots → AUREM.
  2. Non-string + non-matching fields are passthrough (zero false writes).
  3. Migration is idempotent: second run = 0 updates.
  4. Sweeps all user + tenant collections + fields the customer sidebar reads.
  5. Wired into server startup_event (so prod self-heals on next deploy).
"""
from __future__ import annotations

import asyncio
import inspect
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from services import brand_purge_migration as bpm


# ─────────────────────────────────────────────────────────────────
# 1. Regex / rewrite primitive
# ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("inp,expected", [
    ("ReRoots",                "AUREM"),
    ("REROOTS",                "AUREM"),
    ("Reroots",                "AUREM"),
    ("reroots",                "AUREM"),
    ("RerootS",                "AUREM"),
    ("ReRoots AI Platform",    "AUREM AI Platform"),
    ("REROOTS · AURE-ADMIN",   "AUREM · AURE-ADMIN"),
    ("Powered by ReRoots Inc", "Powered by AUREM Inc"),
    ("AUREM",                  "AUREM"),         # no-op
    ("My Business",            "My Business"),   # no-op
    ("",                       ""),              # empty
])
def test_rewrite_all_casing(inp, expected):
    new, changed = bpm._rewrite(inp)
    assert new == expected
    assert changed == (inp != expected)


def test_rewrite_non_string_passthrough():
    for v in [None, 42, ["ReRoots"], {"x": "ReRoots"}, True]:
        new, changed = bpm._rewrite(v)
        assert new is v
        assert changed is False


def test_rewrite_does_not_touch_glued_tokens():
    """RerootsCompany (no word boundary) should be left alone —
    rare and more likely a product name than stale brand."""
    new, changed = bpm._rewrite("RerootsCompanyLLC")
    assert new == "RerootsCompanyLLC"
    assert changed is False


# ─────────────────────────────────────────────────────────────────
# 2. End-to-end sweep against fake Mongo
# ─────────────────────────────────────────────────────────────────

class _FakeColl:
    def __init__(self, docs):
        self._docs = {d["_id"]: dict(d) for d in docs}
        self.update_calls = []

    def find(self, query, projection=None):
        # Naive: match any doc where any string field hits the brand regex
        matches = []
        for doc in self._docs.values():
            for k, v in doc.items():
                if isinstance(v, str) and bpm._BRAND_RE.search(v):
                    matches.append(doc)
                    break

        class _Cursor:
            def __init__(self, items):
                self._items = items
                self._i = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._i >= len(self._items):
                    raise StopAsyncIteration
                d = self._items[self._i]
                self._i += 1
                return d

        return _Cursor(matches)

    async def update_one(self, filter_, update):
        self.update_calls.append((filter_, update))
        _id = filter_["_id"]
        self._docs[_id].update(update["$set"])


class _FakeDB:
    def __init__(self, collections):
        self._cols = collections

    async def list_collection_names(self):
        return list(self._cols.keys())

    def __getitem__(self, name):
        return self._cols[name]


def test_full_sweep_rewrites_user_and_tenant_collections():
    users = _FakeColl([
        {"_id": "u1", "email": "a@x", "company_name": "REROOTS",
         "full_name": "ReRoots Admin", "business_id": "AURE-ADMIN"},
        {"_id": "u2", "email": "b@x", "company_name": "AUREM Inc",
         "full_name": "Already Clean"},  # no-op
    ])
    bins = _FakeColl([
        {"_id": "t1", "tenant_name": "ReRoots Platform",
         "display_name": "ReRoots"},
    ])
    db = _FakeDB({"users": users, "bins": bins})

    counts = asyncio.run(bpm.run_brand_purge(db))

    assert counts["users"] == 1     # only u1 had stale strings
    assert counts["bins"] == 1
    assert users._docs["u1"]["company_name"] == "AUREM"
    assert users._docs["u1"]["full_name"] == "AUREM Admin"
    assert users._docs["u2"]["company_name"] == "AUREM Inc"  # untouched
    assert bins._docs["t1"]["tenant_name"] == "AUREM Platform"
    assert bins._docs["t1"]["display_name"] == "AUREM"


def test_idempotent_second_run_is_zero():
    users = _FakeColl([
        {"_id": "u1", "company_name": "ReRoots"},
    ])
    db = _FakeDB({"users": users})

    first = asyncio.run(bpm.run_brand_purge(db))
    second = asyncio.run(bpm.run_brand_purge(db))

    assert first["users"] == 1
    assert second["users"] == 0
    assert users._docs["u1"]["company_name"] == "AUREM"


def test_missing_collection_is_skipped_gracefully():
    """Tenants collection absent → silent zero, not an error."""
    db = _FakeDB({})  # no collections at all
    counts = asyncio.run(bpm.run_brand_purge(db))
    assert all(v == 0 for v in counts.values())


def test_handles_none_db():
    assert asyncio.run(bpm.run_brand_purge(None)) == {}


# ─────────────────────────────────────────────────────────────────
# 3. Wired into server startup_event
# ─────────────────────────────────────────────────────────────────

def test_run_brand_purge_called_from_startup_event():
    """Locks in the wire-up — if anyone removes the call from
    server.py the prod self-heal stops working silently."""
    with open("/app/backend/server.py") as fh:
        src = fh.read()
    assert "from services.brand_purge_migration import run_brand_purge" in src
    assert "await run_brand_purge(db)" in src


def test_user_field_set_covers_sidebar_ribbon():
    """The customer sidebar (LuxeDashboardPreview.jsx:184) reads
    ``company_name || business_name || full_name``. The sweep MUST
    cover all three or the bug recurs silently."""
    assert "company_name" in bpm._USER_FIELDS
    assert "business_name" in bpm._USER_FIELDS
    assert "full_name" in bpm._USER_FIELDS
