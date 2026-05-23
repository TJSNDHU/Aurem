"""
iter 332b Batch A-2 — Enterprise Admin UI backend coverage
============================================================

Covers the THREE admin surfaces the new frontend pages talk to:
  • /api/enterprise/branding GET / PUT + public read
  • /api/enterprise/domain POST + /domain/verify POST
  • /api/enterprise/keys GET / POST / POST .../rotate / DELETE

Plus source-level wiring sanity for the 4 frontend admin routes.
"""
from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def db():
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    yield database
    # housekeeping — pytest tenants only
    await database.enterprise_branding.delete_many({"tenant_id": {"$regex": "^pytest_"}})
    await database.enterprise_domains.delete_many({"tenant_id": {"$regex": "^pytest_"}})
    await database.enterprise_api_keys.delete_many({"name": {"$regex": "^pytest_"}})
    client.close()


class _AuthedReq:
    """Stand-in admin request: bypasses ensure_admin via headers."""
    def __init__(self):
        self.client = None
        self.headers = {"authorization": "Bearer test-admin-token"}


# ═════════════════════════════════════════════════════════════════
# Branding endpoints
# ═════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_branding_put_persists_and_get_reads_back(db):
    from routers.enterprise_router import (
        get_branding, set_branding, BrandingBody, set_db as _set_db,
    )
    _set_db(db)
    tenant = f"pytest_brand_{uuid.uuid4().hex[:6]}"

    body = BrandingBody(
        tenant_id=tenant,
        logo_url="https://cdn.example.com/logo.svg",
        primary_color="#FF6B00",
        company_name="Pytest Co",
    )
    r = await set_branding(body, _AuthedReq())
    assert r["ok"] is True
    assert r["branding"]["logo_url"] == "https://cdn.example.com/logo.svg"
    assert r["branding"]["company_name"] == "Pytest Co"

    g = await get_branding(_AuthedReq(), tenant_id=tenant)
    assert g["branding"]["tenant_id"] == tenant
    assert g["branding"]["primary_color"] == "#FF6B00"


@pytest.mark.asyncio
async def test_branding_put_audit_row_written(db):
    from routers.enterprise_router import (
        set_branding, BrandingBody, set_db as _set_db,
    )
    from services.unified_audit import set_db as _ua_set
    _set_db(db)
    _ua_set(db)
    tenant = f"pytest_audit_{uuid.uuid4().hex[:6]}"

    await set_branding(
        BrandingBody(tenant_id=tenant, company_name="AuditCo",
                     logo_url="", primary_color="#000000"),
        _AuthedReq(),
    )
    audit = await db.unified_audit_log.find_one(
        {"action": "branding_updated", "resource": f"tenant:{tenant}"},
        {"_id": 0},
    )
    assert audit is not None
    assert audit["extra"]["company_name"] == "AuditCo"
    await db.unified_audit_log.delete_one({"event_id": audit["event_id"]})


@pytest.mark.asyncio
async def test_branding_public_returns_no_auth(db):
    from routers.enterprise_router import (
        get_branding_public, set_branding, BrandingBody, set_db as _set_db,
    )
    _set_db(db)
    tenant = f"pytest_pub_{uuid.uuid4().hex[:6]}"
    await set_branding(
        BrandingBody(tenant_id=tenant, company_name="PubCo",
                     logo_url="", primary_color="#fff"),
        _AuthedReq(),
    )
    j = await get_branding_public(tenant)
    assert j["ok"] is True
    assert j["branding"]["company_name"] == "PubCo"


# ═════════════════════════════════════════════════════════════════
# Domain wizard
# ═════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_domain_register_returns_cname(db):
    from routers.enterprise_router import (
        register_custom_domain, DomainBody, set_db as _set_db,
    )
    _set_db(db)
    tenant = f"pytest_dom_{uuid.uuid4().hex[:6]}"
    r = await register_custom_domain(
        DomainBody(tenant_id=tenant, domain="customer.example.com"),
        _AuthedReq(),
    )
    assert r["ok"] is True
    assert r["domain"] == "customer.example.com"
    assert r["cname_target"] == "aurem.live"
    assert "CNAME" in r["instructions"]


@pytest.mark.asyncio
async def test_domain_register_rejects_invalid_chars(db):
    from routers.enterprise_router import (
        register_custom_domain, DomainBody, set_db as _set_db,
    )
    from fastapi import HTTPException
    _set_db(db)
    with pytest.raises(HTTPException) as exc:
        await register_custom_domain(
            DomainBody(tenant_id="pytest_inv", domain="bad domain!.com"),
            _AuthedReq(),
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_domain_register_persists_pending_row(db):
    from routers.enterprise_router import (
        register_custom_domain, DomainBody, set_db as _set_db,
    )
    _set_db(db)
    tenant = f"pytest_dompers_{uuid.uuid4().hex[:6]}"
    await register_custom_domain(
        DomainBody(tenant_id=tenant, domain="lab.example.com"),
        _AuthedReq(),
    )
    row = await db.enterprise_domains.find_one(
        {"tenant_id": tenant, "domain": "lab.example.com"}, {"_id": 0},
    )
    assert row is not None
    assert row["status"] == "pending_verification"
    assert row["cname_target"] == "aurem.live"


@pytest.mark.asyncio
async def test_domain_verify_returns_struct_when_dns_fails(db):
    """Unresolvable test domain → verified=False, status=pending_verification."""
    from routers.enterprise_router import (
        verify_custom_domain, DomainBody, set_db as _set_db,
    )
    _set_db(db)
    tenant = f"pytest_domver_{uuid.uuid4().hex[:6]}"
    r = await verify_custom_domain(
        DomainBody(tenant_id=tenant,
                   domain=f"nope-{uuid.uuid4().hex[:6]}.invalid"),
        _AuthedReq(),
    )
    assert r["ok"] is True
    assert r["verified"] is False
    assert r["status"] == "pending_verification"
    assert "detail" in r


# ═════════════════════════════════════════════════════════════════
# API Key CRUD
# ═════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_apikey_create_returns_key_once(db):
    from routers.enterprise_router import (
        create_api_key, ApiKeyCreateBody, set_db as _set_db,
    )
    _set_db(db)
    body = ApiKeyCreateBody(
        name=f"pytest_key_{uuid.uuid4().hex[:6]}", scope="read",
    )
    r = await create_api_key(body, _AuthedReq())
    assert r["ok"] is True
    assert r["key"].startswith("aurem_")
    assert r["key_id"]
    assert "only time" in r["warning"].lower()
    # cleanup
    await db.enterprise_api_keys.delete_one({"key_id": r["key_id"]})


@pytest.mark.asyncio
async def test_apikey_list_never_exposes_full_key(db):
    from routers.enterprise_router import (
        create_api_key, list_api_keys, ApiKeyCreateBody, set_db as _set_db,
    )
    _set_db(db)
    body = ApiKeyCreateBody(
        name=f"pytest_listcheck_{uuid.uuid4().hex[:6]}", scope="read",
    )
    created = await create_api_key(body, _AuthedReq())
    listed = await list_api_keys(_AuthedReq())
    assert listed["ok"] is True
    target = [r for r in listed["rows"] if r.get("key_id") == created["key_id"]]
    assert len(target) == 1
    # full key MUST NOT be in the list response (only preview)
    assert "key" not in target[0]
    assert target[0]["key_preview"].endswith("…")
    await db.enterprise_api_keys.delete_one({"key_id": created["key_id"]})


@pytest.mark.asyncio
async def test_apikey_rotate_changes_key(db):
    from routers.enterprise_router import (
        create_api_key, rotate_api_key, ApiKeyCreateBody, set_db as _set_db,
    )
    _set_db(db)
    created = await create_api_key(
        ApiKeyCreateBody(name=f"pytest_rotate_{uuid.uuid4().hex[:6]}",
                         scope="read"),
        _AuthedReq(),
    )
    rotated = await rotate_api_key(created["key_id"], _AuthedReq())
    assert rotated["ok"] is True
    assert rotated["key"] != created["key"]
    assert rotated["key"].startswith("aurem_")
    # DB row reflects the new key
    row = await db.enterprise_api_keys.find_one(
        {"key_id": created["key_id"]}, {"_id": 0},
    )
    assert row["key"] == rotated["key"]
    assert "rotated_at" in row
    await db.enterprise_api_keys.delete_one({"key_id": created["key_id"]})


@pytest.mark.asyncio
async def test_apikey_rotate_404_when_missing(db):
    from routers.enterprise_router import (
        rotate_api_key, set_db as _set_db,
    )
    from fastapi import HTTPException
    _set_db(db)
    with pytest.raises(HTTPException) as exc:
        await rotate_api_key("does-not-exist-" + uuid.uuid4().hex[:6],
                              _AuthedReq())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_apikey_revoke_flips_active_flag(db):
    from routers.enterprise_router import (
        create_api_key, revoke_api_key, ApiKeyCreateBody, set_db as _set_db,
    )
    _set_db(db)
    created = await create_api_key(
        ApiKeyCreateBody(name=f"pytest_rev_{uuid.uuid4().hex[:6]}",
                         scope="read"),
        _AuthedReq(),
    )
    r = await revoke_api_key(created["key_id"], _AuthedReq())
    assert r["ok"] is True
    assert r["revoked"] is True
    row = await db.enterprise_api_keys.find_one(
        {"key_id": created["key_id"]}, {"_id": 0},
    )
    assert row["active"] is False
    assert "revoked_at" in row
    await db.enterprise_api_keys.delete_one({"key_id": created["key_id"]})


@pytest.mark.asyncio
async def test_apikey_revoke_404_when_already_revoked(db):
    from routers.enterprise_router import (
        create_api_key, revoke_api_key, ApiKeyCreateBody, set_db as _set_db,
    )
    from fastapi import HTTPException
    _set_db(db)
    created = await create_api_key(
        ApiKeyCreateBody(name=f"pytest_dblrev_{uuid.uuid4().hex[:6]}",
                         scope="read"),
        _AuthedReq(),
    )
    await revoke_api_key(created["key_id"], _AuthedReq())
    with pytest.raises(HTTPException) as exc:
        await revoke_api_key(created["key_id"], _AuthedReq())
    assert exc.value.status_code == 404
    await db.enterprise_api_keys.delete_one({"key_id": created["key_id"]})


@pytest.mark.asyncio
async def test_apikey_audit_rows_written(db):
    from routers.enterprise_router import (
        create_api_key, rotate_api_key, revoke_api_key,
        ApiKeyCreateBody, set_db as _set_db,
    )
    from services.unified_audit import set_db as _ua_set
    _set_db(db); _ua_set(db)
    key_name = f"pytest_audkey_{uuid.uuid4().hex[:6]}"
    created = await create_api_key(
        ApiKeyCreateBody(name=key_name, scope="write"), _AuthedReq(),
    )
    await rotate_api_key(created["key_id"], _AuthedReq())
    await revoke_api_key(created["key_id"], _AuthedReq())
    actions = await db.unified_audit_log.find(
        {"extra.key_id": created["key_id"]}, {"_id": 0},
    ).to_list(length=10)
    seen = {a["action"] for a in actions}
    assert "api_key_created" in seen
    assert "api_key_rotated" in seen
    assert "api_key_revoked" in seen
    # cleanup audit + key
    await db.unified_audit_log.delete_many(
        {"extra.key_id": created["key_id"]},
    )
    await db.enterprise_api_keys.delete_one({"key_id": created["key_id"]})


# ═════════════════════════════════════════════════════════════════
# Source-level wiring sanity
# ═════════════════════════════════════════════════════════════════

def test_app_js_wires_4_admin_routes():
    from pathlib import Path
    src = Path("/app/frontend/src/App.js").read_text()
    assert "/enterprise/admin" in src
    assert "/enterprise/admin/branding" in src
    assert "/enterprise/admin/domain" in src
    assert "/enterprise/admin/keys" in src
    assert "EnterpriseAdminOverview" in src
    assert "EnterpriseBranding" in src
    assert "EnterpriseDomain" in src
    assert "EnterpriseApiKeys" in src


def test_enterprise_admin_shell_uses_admin_headers():
    """Shell should NOT require dev_jwt; backend 401 drives UX."""
    from pathlib import Path
    src = Path(
        "/app/frontend/src/platform/enterprise/EnterpriseAdminShell.jsx",
    ).read_text()
    assert "platform_token" in src
    assert "aurem_admin_token" in src
    # requireAuth flag should be removed so admins without dev_jwt still see the page
    assert "<DeveloperShell requireAuth>" not in src
