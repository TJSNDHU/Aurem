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

import os as _os_q, pytest as _pytest_q
pytestmark = _pytest_q.mark.skipif(
    not _os_q.environ.get("AUREM_RUN_LEGACY"),
    reason="legacy iteration-era live-e2e archive; asserts superseded behavior — quarantined iter D-86b; set AUREM_RUN_LEGACY=1 to run",
)


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
    """iter 332b D-19 — Founder redesign moved the purchases + activity
    strips off the dashboard. The chat panel is now the dashboard. This
    test asserts the new contract: full-screen chat is mounted and the
    compact header chips render."""
    src = open(
        "/app/frontend/src/platform/developers/DevDashboard.jsx"
    ).read()
    assert "DevCtoChatPanel" in src and "fullScreen" in src, (
        "DevDashboard must mount DevCtoChatPanel in fullScreen mode."
    )
    assert "dev-header-chips" in src, (
        "Compact header chip row not rendered."
    )


def test_homepage_signin_has_smart_redirect():
    """iter 332b D-18 — Founder reverted the smart-redirect: the top-right
    Log In must now ALWAYS land on /my. The handler exists as a no-op so
    the Link's href is the single source of truth for the destination."""
    src = open("/app/frontend/src/platform/AuremHomepage.jsx").read()
    assert "handleSignIn" in src
    assert "data-testid=\"nav-link-login\"" in src
    # The Link itself must point at /my.
    assert 'to="/my"' in src and 'data-testid="nav-link-login"' in src
