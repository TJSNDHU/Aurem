"""
iter 332b D-6 — Dev portal admin bypass + DevDashboard purchases wiring.

Covers two production bugs discovered during the founder's frontend review:

1.  Platform admins could NOT access `/developers/me` with their existing
    admin JWT — the fallback path tried `from utils.auth import _decode_token`,
    a symbol that doesn't exist, so the import silently raised ImportError
    and admin tokens were rejected with `invalid_or_expired_token`.

2.  /developers/dashboard rendered blank because the JSX referenced
    `purchases.length` without ever declaring the `purchases` state, so
    every authed dashboard load crashed at render. Backend `me/purchases`
    endpoint is fine; the frontend simply never called it.

Tests here focus on the BACKEND admin bypass + source-level wiring of
the frontend fix (since DevDashboard.jsx is a React file).
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid

import jwt
import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.developer_portal_core import set_db as _set_dev_db
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    _set_dev_db(database)
    yield database
    await database.developer_accounts.delete_many(
        {"email": {"$regex": "^pytest_d6_"}}
    )
    client.close()


def _mint_admin_token(email: str) -> str:
    """Mint a platform admin JWT exactly the way utils.auth.create_token does."""
    from config import JWT_SECRET, JWT_ALGORITHM
    payload = {
        "user_id": f"admin_{uuid.uuid4().hex[:8]}",
        "is_admin": True,
        "is_super_admin": True,
        "email": email,
        "exp": int(time.time()) + 60 * 60,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ───────────────────────────── admin bypass ──────────────────────────────

@pytest.mark.asyncio
async def test_admin_token_resolves_to_dev_account(db):
    """A valid platform-admin JWT must auto-provision an internal_admin
    developer row and return it from _current_dev — no bounce to signup."""
    from routers.developer_portal_router import _current_dev
    email = f"pytest_d6_{uuid.uuid4().hex[:8]}@aurem.local"
    tok   = _mint_admin_token(email)

    acc = await _current_dev(f"Bearer {tok}")
    assert acc is not None
    assert acc["email"] == email.lower()
    assert acc["plan"] == "internal_admin"
    assert acc["admin_full_access"] is True
    assert acc["tokens_remaining"] >= 1_000_000


@pytest.mark.asyncio
async def test_admin_token_is_idempotent(db):
    """Calling _current_dev twice with the same admin token must not
    duplicate the developer row — it should locate the existing one."""
    from routers.developer_portal_router import _current_dev
    email = f"pytest_d6_{uuid.uuid4().hex[:8]}@aurem.local"
    tok   = _mint_admin_token(email)

    a1 = await _current_dev(f"Bearer {tok}")
    a2 = await _current_dev(f"Bearer {tok}")
    assert a1["user_id"] == a2["user_id"]

    n = await db.developer_accounts.count_documents({"email": email.lower()})
    assert n == 1


@pytest.mark.asyncio
async def test_bogus_token_still_rejected(db):
    """Garbage tokens must NOT bypass the dev portal."""
    from fastapi import HTTPException
    from routers.developer_portal_router import _current_dev
    with pytest.raises(HTTPException) as ei:
        await _current_dev("Bearer not.a.real.jwt")
    assert ei.value.status_code == 401


@pytest.mark.asyncio
async def test_non_admin_token_rejected(db):
    """A valid JWT but without is_admin=True must NOT auto-provision."""
    from config import JWT_SECRET, JWT_ALGORITHM
    from fastapi import HTTPException
    from routers.developer_portal_router import _current_dev
    tok = jwt.encode(
        {"user_id": "u1", "is_admin": False,
         "email": "regular@aurem.local",
         "exp": int(time.time()) + 60},
        JWT_SECRET, algorithm=JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as ei:
        await _current_dev(f"Bearer {tok}")
    assert ei.value.status_code == 401


@pytest.mark.asyncio
async def test_missing_bearer_header(db):
    from fastapi import HTTPException
    from routers.developer_portal_router import _current_dev
    with pytest.raises(HTTPException) as ei:
        await _current_dev(None)
    assert ei.value.status_code == 401


@pytest.mark.asyncio
async def test_decode_token_no_longer_imported_from_utils_auth():
    """Regression guard — the broken import has been removed from code paths."""
    import ast
    src = open("/app/backend/routers/developer_portal_router.py").read()
    tree = ast.parse(src)
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "utils.auth":
            for n in node.names:
                if n.name == "_decode_token":
                    bad.append(node.lineno)
    assert not bad, (
        f"Broken legacy import on line(s) {bad}; admin bypass would silently fail."
    )
    # And the replacement is in place.
    assert "_jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])" in src


# ───────────────────────── frontend dashboard wiring ─────────────────────

def test_dev_dashboard_declares_purchases_state():
    """DevDashboard.jsx must declare a `purchases` state variable AND
    fetch from /api/developers/me/purchases — otherwise it crashes
    silently on every authed dashboard render."""
    src = open(
        "/app/frontend/src/platform/developers/DevDashboard.jsx"
    ).read()
    assert "const [purchases, setPurchases]" in src, (
        "purchases state not declared — dashboard will crash on render."
    )
    assert "/api/developers/me/purchases" in src, (
        "Purchases endpoint not called — recent-purchases strip will be empty."
    )


def test_homepage_signin_has_smart_redirect():
    """Top-right Log In must short-circuit to the right dashboard
    when the visitor is already authenticated (admin / dev / customer)."""
    src = open("/app/frontend/src/platform/AuremHomepage.jsx").read()
    assert "handleSignIn" in src
    assert "/admin/mission-control" in src
    assert "/developers/dashboard" in src
    assert "data-testid=\"nav-link-login\"" in src
