"""
iter 332b D-6 — System Overview public mirror wiring.

The /share/system-overview public page was added in iter 332b D-4
but the public router (get_public_router()) was never mounted by
routers/registry.py — only the admin `router` got included. This
made /api/public/system-overview/stats return 404 in preview AND
production. Added registry hook + test guard.
"""
from __future__ import annotations

import os
import pathlib

import httpx
import pytest


def _resolve_base() -> str:
    base = os.environ.get("REACT_APP_BACKEND_URL")
    if not base:
        # Fall back to whatever the frontend is configured to call —
        # local 8001 doesn't go through the auth-enforcing ingress.
        envf = pathlib.Path("/app/frontend/.env")
        if envf.exists():
            for line in envf.read_text().splitlines():
                if line.startswith("REACT_APP_BACKEND_URL="):
                    base = line.split("=", 1)[1].strip()
                    break
    return (base or "http://localhost:8001").rstrip("/")


BASE = _resolve_base()


@pytest.mark.asyncio
async def test_public_system_overview_stats_is_unauthenticated():
    """No bearer required + only public fields returned."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{BASE}/api/public/system-overview/stats")
    assert r.status_code == 200
    body = r.json()
    assert body.get("public") is True
    plat = body.get("platform", {})
    assert plat.get("name") == "AUREM"
    assert plat.get("owner")
    assert plat.get("iteration")
    assert plat.get("as_of")
    # Negative: no private counters leak.
    for forbidden in (
        "session_memories", "shannon_audits", "ora_calls", "audit_log",
        "developer_accounts", "payment_transactions",
    ):
        assert forbidden not in body, (
            f"Private field {forbidden!r} leaked into public mirror."
        )


@pytest.mark.asyncio
async def test_admin_system_overview_still_requires_auth():
    """The full /api/admin/system-overview/* path must reject anon."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{BASE}/api/admin/system-overview/stats")
    assert r.status_code in (401, 403), (
        f"Admin stats route is unprotected — got HTTP {r.status_code}."
    )


def test_registry_wires_public_router():
    """Source-level guard: registry must call get_public_router() on
    any router that exposes it (catches any future module that adds
    a public mirror but forgets to register it)."""
    src = open("/app/backend/routers/registry.py").read()
    assert "get_public_router" in src, (
        "Registry no longer calls get_public_router — public mirrors will 404."
    )


def test_public_router_does_not_use_admin_prefix():
    """Hard guard: the public router must not piggy-back on
    /api/admin/system-overview/ — that prefix is auth-gated."""
    src = open("/app/backend/routers/system_overview_router.py").read()
    # The router builder line for the public router must NOT pass the
    # admin prefix.
    assert "_PUBLIC_ROUTER = APIRouter(tags=" in src
    # The public path is /api/public/...
    assert "/api/public/system-overview/stats" in src
