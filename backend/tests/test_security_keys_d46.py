"""
tests/test_security_keys_d46.py — iter D-46

Tests for the one-click security-key generation system + admin panel.

Coverage:
  - Triplet generation produces strong random secrets every call
  - generate-keys persists encrypted envelope, applies live to env,
    returns plaintext exactly once with the warning
  - Rotation: prior active row → status="rotated", fresh row inserted
  - status endpoint returns masked tails only (never plaintext)
  - Admin list aggregates by user, returns no plaintext
  - Admin history endpoint returns all rows for a user
  - Admin force-rotate inserts a new active row + marks old rotated
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ──────────────────────────────────────────────────────────────────
# Async in-memory MongoDB stub
# ──────────────────────────────────────────────────────────────────

class _Cursor:
    def __init__(self, rows):
        self._rows = list(rows)
    def sort(self, key, direction):
        self._rows.sort(key=lambda r: r.get(key) or "",
                         reverse=(direction < 0))
        return self
    async def to_list(self, length=None):
        return list(self._rows)


class _Coll:
    def __init__(self):
        self._rows = []
    def find(self, query=None, projection=None):
        q = query or {}
        out = [r for r in self._rows
               if all(r.get(k) == v for k, v in q.items())]
        return _Cursor(out)
    async def find_one(self, query, projection=None):
        for r in self._rows:
            if all(r.get(k) == v for k, v in query.items()):
                return dict(r)
        return None
    async def insert_one(self, doc):
        doc = dict(doc)
        doc.setdefault("_id", f"id_{len(self._rows)}")
        self._rows.append(doc)
        return type("R", (), {"inserted_id": doc["_id"]})
    async def update_many(self, query, update):
        n = 0
        for r in self._rows:
            if all(r.get(k) == v for k, v in query.items()):
                for k, v in (update.get("$set") or {}).items():
                    r[k] = v
                n += 1
        return type("R", (), {"matched_count": n})


class _DB:
    def __init__(self):
        self.customer_security_keys = _Coll()


@pytest.fixture
def db_stub(monkeypatch):
    from routers import security_keys_router as skr
    db = _DB()
    monkeypatch.setattr(skr, "_db", db)
    yield db


@pytest.fixture
def crypt_key(monkeypatch):
    monkeypatch.setenv("AUREM_ENCRYPTION_KEY",
                        "test-passphrase-d46-" + "x" * 32)
    # iter D-46 — pre-touch the env vars our generator mutates so
    # monkeypatch tracks them and restores the original values on
    # teardown (otherwise D-38's JWT test sees a rotated secret).
    monkeypatch.setenv("JWT_SECRET", os.environ.get("JWT_SECRET", ""))
    monkeypatch.setenv("CORS_ORIGINS", os.environ.get("CORS_ORIGINS", ""))
    from services import credential_crypto as cc
    cc._FERNET = None
    cc._INIT_TRIED = False
    yield


@pytest.fixture
def fake_request():
    class _C:
        host = "203.0.113.5"
    class _R:
        client = _C()
    return _R()


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def test_generate_triplet_is_random():
    from routers.security_keys_router import _generate_triplet
    a = _generate_triplet()
    b = _generate_triplet()
    assert a != b
    assert len(a["JWT_SECRET"])           >= 48
    assert len(a["AUREM_ENCRYPTION_KEY"]) >= 40
    assert a["CORS_ORIGINS"] == "https://aurem.live"


def test_tail4_helper():
    from routers.security_keys_router import _tail4
    assert _tail4("abcdefgh") == "efgh"
    assert _tail4("xy")       == "**"   # padded with *
    assert _tail4("")         == ""
    assert _tail4(None)       == ""


# ──────────────────────────────────────────────────────────────────
# Customer endpoint — generate
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_returns_plaintext_once(db_stub, crypt_key, fake_request,
                                                monkeypatch):
    for k in ("JWT_SECRET", "AUREM_ENCRYPTION_KEY", "CORS_ORIGINS"):
        monkeypatch.delenv(k, raising=False)
    from routers.security_keys_router import generate_security_keys, GenerateBody
    user = {"user_id": "u-test-1", "email": "founder@aurem.test",
            "tenant_id": "aurem"}
    out = await generate_security_keys(
        GenerateBody(rotate=True), fake_request, user=user,
    )
    assert out["ok"] is True
    pt = out["plaintext_once"]
    # All three keys present and strong
    assert pt["JWT_SECRET"]
    assert pt["AUREM_ENCRYPTION_KEY"]
    assert pt["CORS_ORIGINS"] == "https://aurem.live"
    # Live env applied
    assert os.environ.get("JWT_SECRET")           == pt["JWT_SECRET"]
    assert os.environ.get("AUREM_ENCRYPTION_KEY") == pt["AUREM_ENCRYPTION_KEY"]
    # Warning surfaces
    assert "shown ONCE" in out["warning"]
    # Summary contains tails + status, NO plaintext
    s = out["summary"]
    assert s["status"] == "active"
    assert s["ip_address"] == "203.0.113.5"
    for k in pt:
        meta = s["keys"][k]
        assert meta["set"] is True
        # The tail of the plaintext should appear in the summary tail.
        assert meta["key_tail"] == pt[k][-4:]
    # And nowhere in the summary string should the plaintext leak.
    flat = str(s)
    for k, v in pt.items():
        if len(v) > 8:
            assert v not in flat, f"plaintext {k} leaked into summary"


@pytest.mark.asyncio
async def test_rotate_marks_old_active_row(db_stub, crypt_key, fake_request):
    from routers.security_keys_router import generate_security_keys, GenerateBody
    user = {"user_id": "u-rot-1", "email": "x@y.z", "tenant_id": "t"}
    await generate_security_keys(GenerateBody(rotate=True), fake_request, user=user)
    await generate_security_keys(GenerateBody(rotate=True), fake_request, user=user)
    rows = db_stub.customer_security_keys._rows
    # Two rows for the same user.
    user_rows = [r for r in rows if r["user_id"] == "u-rot-1"]
    assert len(user_rows) == 2
    statuses = sorted(r["status"] for r in user_rows)
    assert statuses == ["active", "rotated"]


@pytest.mark.asyncio
async def test_status_returns_no_plaintext(db_stub, crypt_key, fake_request):
    from routers.security_keys_router import (
        generate_security_keys, my_keys_status, GenerateBody,
    )
    user = {"user_id": "u-stat-1", "email": "s@y.z", "tenant_id": "t"}
    out = await generate_security_keys(GenerateBody(), fake_request, user=user)
    plain = out["plaintext_once"]
    st = await my_keys_status(user=user)
    assert st["configured"] is True
    flat = str(st)
    for v in plain.values():
        if len(v) > 8:
            assert v not in flat


# ──────────────────────────────────────────────────────────────────
# Admin endpoints
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_list_aggregates_and_hides_plaintext(
    db_stub, crypt_key, fake_request,
):
    from routers.security_keys_router import (
        generate_security_keys, admin_list_security_keys, GenerateBody,
    )
    # Two distinct customers, customer A rotates once.
    await generate_security_keys(GenerateBody(),
        fake_request, user={"user_id": "u-A", "email": "a@x", "tenant_id": "t1"})
    out_A = await generate_security_keys(GenerateBody(),
        fake_request, user={"user_id": "u-A", "email": "a@x", "tenant_id": "t1"})
    await generate_security_keys(GenerateBody(),
        fake_request, user={"user_id": "u-B", "email": "b@x", "tenant_id": "t2"})

    res = await admin_list_security_keys()
    assert res["total"]   == 2
    assert res["active"]  == 2  # both customers have an active row
    user_ids = {r["user_id"] for r in res["items"]}
    assert user_ids == {"u-A", "u-B"}
    # No plaintext anywhere in the response.
    flat = str(res)
    for v in out_A["plaintext_once"].values():
        if len(v) > 8:
            assert v not in flat


@pytest.mark.asyncio
async def test_admin_history_returns_all_rows(db_stub, crypt_key, fake_request):
    from routers.security_keys_router import (
        generate_security_keys, admin_history, GenerateBody,
    )
    user = {"user_id": "u-hist-1", "email": "h@x", "tenant_id": "t"}
    for _ in range(3):
        await generate_security_keys(GenerateBody(rotate=True),
                                      fake_request, user=user)
    h = await admin_history("u-hist-1")
    assert h["user_id"] == "u-hist-1"
    assert len(h["items"]) == 3
    statuses = sorted(r["status"] for r in h["items"])
    assert statuses == ["active", "rotated", "rotated"]


@pytest.mark.asyncio
async def test_admin_force_rotate_inserts_new_active(
    db_stub, crypt_key, fake_request,
):
    from routers.security_keys_router import (
        generate_security_keys, admin_force_rotate,
        GenerateBody, AdminRotateBody,
    )
    user = {"user_id": "u-force-1", "email": "f@x", "tenant_id": "t"}
    await generate_security_keys(GenerateBody(), fake_request, user=user)
    out = await admin_force_rotate(
        "u-force-1", AdminRotateBody(reason="suspected leak"),
        request=fake_request,
    )
    assert out["ok"] is True
    rows = db_stub.customer_security_keys._rows
    user_rows = [r for r in rows if r["user_id"] == "u-force-1"]
    assert len(user_rows) == 2
    # Latest row marked rotated_by_admin
    active = next(r for r in user_rows if r["status"] == "active")
    assert active.get("rotated_by_admin") is True
    assert active.get("rotation_reason") == "suspected leak"


@pytest.mark.asyncio
async def test_admin_force_rotate_404_when_no_keys(db_stub, crypt_key, fake_request):
    from fastapi import HTTPException
    from routers.security_keys_router import (
        admin_force_rotate, AdminRotateBody,
    )
    with pytest.raises(HTTPException) as exc:
        await admin_force_rotate("u-never-existed",
                                  AdminRotateBody(), request=fake_request)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_generate_503_when_db_missing(crypt_key, fake_request, monkeypatch):
    from fastapi import HTTPException
    from routers import security_keys_router as skr
    monkeypatch.setattr(skr, "_db", None)
    from routers.security_keys_router import generate_security_keys, GenerateBody
    with pytest.raises(HTTPException) as exc:
        await generate_security_keys(
            GenerateBody(), fake_request,
            user={"user_id": "x", "email": "x@y"},
        )
    assert exc.value.status_code == 503
