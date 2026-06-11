"""
D-81b — Customer Activation Onboarding (BIN-scoped).

Proves:
  1. POST /api/onboarding/business-profile rejects unauthenticated calls.
  2. POST requires BIN (business_id) on the JWT.
  3. POST validates body (business_url, industry, target_country whitelist).
  4. POST writes a BIN-scoped row to customer_business_profile.
  5. Two synthetic BINs cannot read each other's profile via GET.
  6. Re-POST is idempotent (upsert, no duplicates) and is_new flips to false.
  7. The wizard checklist also marks "business_profile" complete.

All real HTTP, real Mongo, real JWT — no mocks.
"""
from __future__ import annotations

import os
import uuid

import httpx
import jwt
import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

API_BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "aurem_db")


def _token(*, user_id: str, business_id: str | None, email: str = "d81b@aurem.live") -> str:
    claims = {"user_id": user_id, "sub": user_id, "email": email, "role": "customer"}
    if business_id:
        claims["business_id"] = business_id
        claims["bin"] = business_id
    return jwt.encode(claims, os.environ["JWT_SECRET"], algorithm="HS256")


@pytest_asyncio.fixture
async def db():
    cli = AsyncIOMotorClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest_asyncio.fixture
async def cleanup_bins(db):
    bins_used: list[str] = []
    yield bins_used
    if bins_used:
        await db.customer_business_profile.delete_many({"business_id": {"$in": bins_used}})
        await db.onboarding.delete_many({"user_id": {"$regex": "^d81b-"}})
        await db.audit_trail.delete_many({"business_id": {"$in": bins_used}})


def _valid_body() -> dict:
    return {
        "business_name": "Royal Premier Homes",
        "business_url": "https://royalpremierhomes.com",
        "industry": "real_estate",
        "target_city": "Toronto",
        "target_country": "CA",
    }


# ── 1. Auth gates ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_post_requires_bearer():
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"{API_BASE}/api/onboarding/business-profile", json=_valid_body())
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_post_requires_business_id_claim():
    tok = _token(user_id="d81b-no-bin", business_id=None)
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{API_BASE}/api/onboarding/business-profile",
            headers={"Authorization": f"Bearer {tok}"},
            json=_valid_body(),
        )
    assert r.status_code == 403
    assert "business_id" in r.text.lower() or "bin" in r.text.lower()


# ── 2. Body validation ───────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("patch", [
    {"business_url": ""},
    {"business_url": "not-a-url"},
    {"industry": "spaceship-repair"},
    {"target_country": "ZZ"},
    {"business_name": ""},
    {"target_city": ""},
])
async def test_post_validates_body(patch, cleanup_bins):
    bin_id = f"AUR-D81B-{uuid.uuid4().hex[:6].upper()}"
    cleanup_bins.append(bin_id)
    tok = _token(user_id=f"d81b-{uuid.uuid4().hex[:8]}", business_id=bin_id)
    body = _valid_body()
    body.update(patch)
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(
            f"{API_BASE}/api/onboarding/business-profile",
            headers={"Authorization": f"Bearer {tok}"},
            json=body,
        )
    assert r.status_code == 400, f"expected 400 for {patch}, got {r.status_code}: {r.text}"


# ── 3. Happy-path write + idempotency + audit + checklist ────────────

@pytest.mark.asyncio
async def test_post_writes_bin_scoped_profile_and_fires_audit(db, cleanup_bins):
    bin_id = f"AUR-D81B-{uuid.uuid4().hex[:6].upper()}"
    user_id = f"d81b-{uuid.uuid4().hex[:8]}"
    cleanup_bins.append(bin_id)
    tok = _token(user_id=user_id, business_id=bin_id, email="founder@d81b.test")

    async with httpx.AsyncClient(timeout=10) as c:
        r1 = await c.post(
            f"{API_BASE}/api/onboarding/business-profile",
            headers={"Authorization": f"Bearer {tok}"},
            json=_valid_body(),
        )
    assert r1.status_code == 200, r1.text
    j1 = r1.json()
    assert j1["ok"] is True
    assert j1["business_id"] == bin_id
    assert j1["is_new"] is True
    assert j1["redirect_to"] == "/dashboard"

    # DB scoped correctly
    doc = await db.customer_business_profile.find_one({"business_id": bin_id})
    assert doc is not None
    assert doc["business_url"] == "https://royalpremierhomes.com"
    assert doc["industry"] == "real_estate"
    assert doc["target_city"] == "Toronto"
    assert doc["target_country"] == "CA"
    assert doc["user_id"] == user_id

    # Wizard checklist updated
    wiz = await db.onboarding.find_one({"user_id": user_id})
    assert wiz is not None
    assert "business_profile" in (wiz.get("completed_steps") or [])

    # Audit trail row landed
    audit_n = await db.audit_trail.count_documents({
        "business_id": bin_id,
        "event": "onboarding.business_profile.saved",
    })
    assert audit_n >= 1

    # Re-POST is idempotent — no duplicate row, is_new=False second time
    async with httpx.AsyncClient(timeout=10) as c:
        r2 = await c.post(
            f"{API_BASE}/api/onboarding/business-profile",
            headers={"Authorization": f"Bearer {tok}"},
            json={**_valid_body(), "target_city": "Mississauga"},
        )
    assert r2.status_code == 200
    assert r2.json()["is_new"] is False
    n = await db.customer_business_profile.count_documents({"business_id": bin_id})
    assert n == 1
    doc2 = await db.customer_business_profile.find_one({"business_id": bin_id})
    assert doc2["target_city"] == "Mississauga"  # update applied


# ── 4. GET round-trip and cross-BIN isolation ────────────────────────

@pytest.mark.asyncio
async def test_get_returns_exists_false_when_missing(cleanup_bins):
    bin_id = f"AUR-D81B-{uuid.uuid4().hex[:6].upper()}"
    cleanup_bins.append(bin_id)
    tok = _token(user_id=f"d81b-{uuid.uuid4().hex[:8]}", business_id=bin_id)
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"{API_BASE}/api/onboarding/business-profile",
            headers={"Authorization": f"Bearer {tok}"},
        )
    assert r.status_code == 200
    j = r.json()
    assert j["exists"] is False
    assert j["business_id"] == bin_id


@pytest.mark.asyncio
async def test_cross_bin_isolation_two_synthetic_customers(cleanup_bins):
    """The headline D-81b acceptance test:
    Two distinct BINs each save their own profile. BIN A's JWT MUST NOT
    be able to read BIN B's row — and vice-versa.
    """
    bin_a = f"AUR-D81B-{uuid.uuid4().hex[:6].upper()}"
    bin_b = f"AUR-D81B-{uuid.uuid4().hex[:6].upper()}"
    cleanup_bins.extend([bin_a, bin_b])
    tok_a = _token(user_id=f"d81b-{uuid.uuid4().hex[:8]}", business_id=bin_a, email="a@d81b.test")
    tok_b = _token(user_id=f"d81b-{uuid.uuid4().hex[:8]}", business_id=bin_b, email="b@d81b.test")

    body_a = {**_valid_body(), "business_name": "Tenant A LLC", "business_url": "https://tenant-a.com", "target_city": "Toronto"}
    body_b = {**_valid_body(), "business_name": "Tenant B LLC", "business_url": "https://tenant-b.com", "target_city": "Vancouver"}

    async with httpx.AsyncClient(timeout=10) as c:
        ra = await c.post(f"{API_BASE}/api/onboarding/business-profile",
                          headers={"Authorization": f"Bearer {tok_a}"}, json=body_a)
        rb = await c.post(f"{API_BASE}/api/onboarding/business-profile",
                          headers={"Authorization": f"Bearer {tok_b}"}, json=body_b)
        assert ra.status_code == 200 and rb.status_code == 200

        # A reads — sees only A's row, never B's
        ga = await c.get(f"{API_BASE}/api/onboarding/business-profile",
                         headers={"Authorization": f"Bearer {tok_a}"})
        gb = await c.get(f"{API_BASE}/api/onboarding/business-profile",
                         headers={"Authorization": f"Bearer {tok_b}"})

    pa, pb = ga.json()["profile"], gb.json()["profile"]
    assert pa["business_id"] == bin_a
    assert pa["business_name"] == "Tenant A LLC"
    assert pa["target_city"] == "Toronto"

    assert pb["business_id"] == bin_b
    assert pb["business_name"] == "Tenant B LLC"
    assert pb["target_city"] == "Vancouver"

    # The cross-leak guard: A's response must not contain B's identifiers
    assert "Tenant B" not in ga.text
    assert bin_b not in ga.text
    assert "Tenant A" not in gb.text
    assert bin_a not in gb.text
