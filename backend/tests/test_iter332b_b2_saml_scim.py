"""
iter 332b Batch B — SAML SSO + SCIM provisioning (Steps 2 + 3)
================================================================

Step 2: SAML config storage + discovery + metadata XML
Step 3: SCIM token lifecycle + protocol endpoints (List / Create / Get / Delete)

Real SAML AuthnResponse parsing + python3-saml dependency wiring lands
in a follow-up slice; this tests the foundation that ship today.
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
    from services.organizations import set_db as _o
    from services.saml_sso import set_db as _s
    from services.scim_provisioning import set_db as _sc
    _o(database); _s(database); _sc(database)
    yield database
    # cleanup
    await database.organizations.delete_many({"name": {"$regex": "^pytest_"}})
    await database.organization_members.delete_many({"user_id": {"$regex": "^pytest_"}})
    await database.saml_configs.delete_many({"org_id": {"$regex": "^pytest_org_"}})
    await database.scim_tokens.delete_many({"org_id": {"$regex": "^pytest_org_"}})
    await database.saml_logins.delete_many({"org_id": {"$regex": "^pytest_org_"}})
    await database.users.delete_many({"id": {"$regex": "^pytest_u_|^scim_"}})
    client.close()


# ═══════════════════════════════════════════════════════════════════
# SAML config CRUD
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_saml_upsert_persists_and_derives_sp_urls(db):
    from services.organizations import create_organization
    from services.saml_sso import upsert_saml_config, get_saml_config
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    org = await create_organization(name="pytest_SAMLco", created_by=uid)
    r = await upsert_saml_config(org["org"]["org_id"], {
        "idp_provider": "okta",
        "idp_entity_id": "http://www.okta.com/exk123",
        "idp_sso_url":   "https://acme.okta.com/app/abc/sso/saml",
        "idp_cert":      "-----BEGIN CERTIFICATE-----\nMIIabc\n-----END CERTIFICATE-----",
    })
    assert r["ok"] is True
    cfg = await get_saml_config(org["org"]["org_id"])
    assert cfg["idp_provider"] == "okta"
    assert cfg["sp_entity_id"].endswith(f"/saml/{org['org']['slug']}/metadata")
    assert cfg["acs_url"].endswith(f"/api/saml/{org['org']['org_id']}/acs")
    assert "givenName" in str(cfg["attribute_map"]).lower() \
            or "FirstName" in str(cfg["attribute_map"])


@pytest.mark.asyncio
async def test_saml_invalid_provider_rejected(db):
    from services.organizations import create_organization
    from services.saml_sso import upsert_saml_config
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    org = await create_organization(name="pytest_BadIdP", created_by=uid)
    r = await upsert_saml_config(org["org"]["org_id"],
                                   {"idp_provider": "facebook"})
    assert r["ok"] is False
    assert r["error"] == "invalid_provider"


@pytest.mark.asyncio
async def test_saml_invalid_org_rejected(db):
    from services.saml_sso import upsert_saml_config
    r = await upsert_saml_config("does-not-exist-x", {"idp_provider": "okta"})
    assert r["ok"] is False
    assert r["error"] == "org_not_found"


@pytest.mark.asyncio
async def test_saml_discover_by_email_domain(db):
    from services.organizations import create_organization, update_organization
    from services.saml_sso import upsert_saml_config, discover_org_by_email
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    org = await create_organization(
        name="pytest_DiscoCo", created_by=uid, domain="discoco.example",
    )
    # Activate SAML
    await upsert_saml_config(org["org"]["org_id"], {
        "idp_provider": "azure_ad",
        "idp_sso_url": "https://login.microsoftonline.com/x/saml",
        "idp_cert": "-----BEGIN CERTIFICATE-----\nMIIab\n-----END CERTIFICATE-----",
        "status": "active",
    })
    found = await discover_org_by_email("user@discoco.example")
    assert found is not None
    assert found["org"]["org_id"] == org["org"]["org_id"]
    assert found["saml"]["idp_provider"] == "azure_ad"


@pytest.mark.asyncio
async def test_saml_discover_returns_none_for_unknown_domain(db):
    from services.saml_sso import discover_org_by_email
    found = await discover_org_by_email("nobody@unknown-domain.example")
    assert found is None


@pytest.mark.asyncio
async def test_saml_login_record_persists(db):
    from services.organizations import create_organization
    from services.saml_sso import record_saml_login
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    org = await create_organization(name="pytest_RecLog", created_by=uid)
    await record_saml_login(
        org["org"]["org_id"], email="user@pytest.example",
        name_id="user@pytest.example", success=True,
    )
    row = await db.saml_logins.find_one(
        {"org_id": org["org"]["org_id"]}, {"_id": 0},
    )
    assert row is not None
    assert row["email"] == "user@pytest.example"


# ═══════════════════════════════════════════════════════════════════
# SCIM token lifecycle
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_scim_token_issue_validate_revoke(db):
    from services.organizations import create_organization
    from services.scim_provisioning import (
        issue_scim_token, validate_scim_token, revoke_scim_token,
    )
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    org = await create_organization(name="pytest_SCIMco", created_by=uid)
    r = await issue_scim_token(org["org"]["org_id"], "Okta integration",
                                 created_by=uid)
    assert r["ok"] is True
    assert r["token"].startswith("scim_")
    # Validate
    row = await validate_scim_token(org["org"]["org_id"], r["token"])
    assert row is not None
    assert row["name"] == "Okta integration"
    # Wrong token rejected
    bad = await validate_scim_token(org["org"]["org_id"], "scim_wrong")
    assert bad is None
    # Revoke
    rev = await revoke_scim_token(org["org"]["org_id"], r["token_id"])
    assert rev["ok"] is True
    # Validate post-revoke fails
    after = await validate_scim_token(org["org"]["org_id"], r["token"])
    assert after is None


@pytest.mark.asyncio
async def test_scim_token_list_excludes_hash(db):
    from services.organizations import create_organization
    from services.scim_provisioning import issue_scim_token, list_scim_tokens
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    org = await create_organization(name="pytest_ListTok", created_by=uid)
    await issue_scim_token(org["org"]["org_id"], "Azure", created_by=uid)
    rows = await list_scim_tokens(org["org"]["org_id"])
    assert len(rows) == 1
    assert "token_hash" not in rows[0]
    assert rows[0]["token_preview"].endswith("…")


@pytest.mark.asyncio
async def test_scim_provision_creates_user_and_org_membership(db):
    from services.organizations import (
        create_organization, get_user_role,
    )
    from services.scim_provisioning import provision_user
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    org = await create_organization(name="pytest_ProvCo", created_by=uid)
    scim_body = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "userName": "new.user@pytest.example",
        "emails": [{"value": "new.user@pytest.example", "primary": True}],
        "name": {"givenName": "New", "familyName": "User"},
        "active": True,
    }
    r = await provision_user(org["org"]["org_id"], scim_body, "tok_xyz")
    assert r["ok"] is True
    assert r["created"] is True
    new_uid = r["user"]["id"]
    role = await get_user_role(org["org"]["org_id"], new_uid)
    assert role == "member"


@pytest.mark.asyncio
async def test_scim_provision_existing_email_reuses_user(db):
    from services.organizations import create_organization
    from services.scim_provisioning import provision_user
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    org = await create_organization(name="pytest_ReuseUser", created_by=uid)
    # Pre-create the user
    pre_id = "pytest_u_pre_" + uuid.uuid4().hex[:6]
    await db.users.insert_one({
        "id": pre_id, "email": "shared@pytest.example",
        "first_name": "Old", "last_name": "Name",
    })
    scim_body = {
        "userName": "shared@pytest.example",
        "emails": [{"value": "shared@pytest.example"}],
        "name": {"givenName": "X", "familyName": "Y"},
    }
    r = await provision_user(org["org"]["org_id"], scim_body, "tok")
    assert r["ok"] is True
    assert r["created"] is False
    assert r["user"]["id"] == pre_id


@pytest.mark.asyncio
async def test_scim_provision_rejects_missing_email(db):
    from services.organizations import create_organization
    from services.scim_provisioning import provision_user
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    org = await create_organization(name="pytest_NoEmail", created_by=uid)
    r = await provision_user(org["org"]["org_id"], {"name": {"givenName": "X"}}, "tok")
    assert r["ok"] is False
    assert r["error"] == "email_required"


@pytest.mark.asyncio
async def test_scim_user_envelope_shape(db):
    from services.scim_provisioning import scim_user_from_aurem
    u = {
        "id": "scim_u_abc", "email": "x@pytest.example",
        "first_name": "X", "last_name": "Y",
        "active": True, "org_role": "admin",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    env = scim_user_from_aurem(u, "org_xyz")
    assert env["schemas"][0].lower().endswith("core:2.0:user")
    assert env["userName"] == "x@pytest.example"
    assert env["emails"][0]["primary"] is True
    ext = env["urn:ietf:params:scim:schemas:extension:aurem:1.0:User"]
    assert ext["org_id"] == "org_xyz"
    assert ext["role"] == "admin"


@pytest.mark.asyncio
async def test_scim_deactivate_user(db):
    from services.organizations import (
        create_organization, get_user_role,
    )
    from services.scim_provisioning import provision_user, deactivate_user
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    org = await create_organization(name="pytest_Deact", created_by=uid)
    r = await provision_user(org["org"]["org_id"], {
        "userName": "deact@pytest.example",
        "emails": [{"value": "deact@pytest.example", "primary": True}],
    }, "tok")
    new_uid = r["user"]["id"]
    assert await get_user_role(org["org"]["org_id"], new_uid) == "member"
    deact = await deactivate_user(org["org"]["org_id"], new_uid)
    assert deact["ok"] is True
    assert await get_user_role(org["org"]["org_id"], new_uid) is None
    row = await db.users.find_one({"id": new_uid}, {"_id": 0})
    assert row["active"] is False


# ═══════════════════════════════════════════════════════════════════
# Source-level wiring sanity
# ═══════════════════════════════════════════════════════════════════

def test_saml_router_paths_registered():
    from routers.saml_router import router
    paths = {r.path for r in router.routes}
    assert "/api/saml/{org_id}/config" in paths
    assert "/api/saml/{org_id}/metadata" in paths
    assert "/api/saml/discover" in paths
    assert "/api/saml/{org_id}/acs" in paths


def test_scim_router_paths_registered():
    from routers.scim_router import admin_router, protocol_router
    admin_paths = {r.path for r in admin_router.routes}
    proto_paths = {r.path for r in protocol_router.routes}
    assert "/api/scim/{org_id}/tokens" in admin_paths
    assert "/api/scim/{org_id}/tokens/{token_id}" in admin_paths
    assert "/scim/v2/{org_id}/Users" in proto_paths
    assert "/scim/v2/{org_id}/Users/{user_id}" in proto_paths


def test_registry_wires_saml_scim():
    from pathlib import Path
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "saml_router" in src
    assert "scim_router" in src
