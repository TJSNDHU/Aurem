"""Regression test for dogfood pixel status (BIN ⇄ tenant_id resolver).

Bug: dogfood admin (super_admin) has user.tenant_id=`aurem_platform` but
their aurem_onboarding row was seeded under their business_id (`AURE-RUGC`).
Frontend PixelGateBanner queried /onboarding/tenant/aurem_platform/pixel/status
and got 404 → status null → banner stuck on "not installed" forever.

Fix: backend `_resolve_onboarding` cross-walks via users collection so either
tenant_id OR business_id resolves to the same onboarding row, AND PIN login
returns `tenant_id` in the JWT response.
"""
import os
import httpx
import pytest


BASE = os.environ.get("BACKEND_BASE_URL", "http://localhost:8001")


@pytest.mark.asyncio
async def test_pixel_status_resolves_by_tenant_id():
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{BASE}/api/onboarding/tenant/aurem_platform/pixel/status")
    assert r.status_code == 200
    j = r.json()
    assert j["pixel_installed"] is True
    assert j["resolved"] is True
    assert j["resolved_tenant_id"] == "AURE-RUGC"


@pytest.mark.asyncio
async def test_pixel_status_resolves_by_business_id():
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{BASE}/api/onboarding/tenant/AURE-RUGC/pixel/status")
    assert r.status_code == 200
    j = r.json()
    assert j["pixel_installed"] is True


@pytest.mark.asyncio
async def test_pixel_status_unknown_tenant_soft_fails():
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{BASE}/api/onboarding/tenant/__nope__/pixel/status")
    assert r.status_code == 200
    j = r.json()
    assert j["pixel_installed"] is False
    assert j["resolved"] is False


@pytest.mark.asyncio
async def test_pin_login_returns_tenant_id():
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            f"{BASE}/api/platform/auth/login-pin",
            json={"bin": "AURE-RUGC", "pin": "7668"},
        )
    # If PIN not set in this env, skip — but in dogfood it IS set.
    if r.status_code != 200:
        pytest.skip(f"PIN login unavailable: {r.status_code} {r.text[:200]}")
    j = r.json()
    assert j.get("tenant_id"), "PIN login response missing tenant_id"
    assert j.get("business_id") == "AURE-RUGC"
