"""
iter 332b Batch B — Organization entity (Step 1)
==================================================

Covers the foundation: create, read, update, member CRUD, invites,
role changes, last-owner guards, slug uniqueness, org switcher.

SAML SSO + SCIM provisioning land in Step 2 + Step 3 (separate test files).
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
    # Wire the service to this DB
    from services.organizations import set_db as _set
    _set(database)
    yield database
    # cleanup pytest rows
    await database.organizations.delete_many({"name": {"$regex": "^pytest_"}})
    await database.organization_members.delete_many(
        {"user_id": {"$regex": "^pytest_"}},
    )
    await database.organization_invites.delete_many(
        {"email": {"$regex": "@pytest\\.example$"}},
    )
    client.close()


# ═══════════════════════════════════════════════════════════════════
# Slug helper
# ═══════════════════════════════════════════════════════════════════

def test_slugify_lowercases_and_strips_special_chars():
    from services.organizations import slugify
    assert slugify("Acme Corp") == "acme-corp"
    assert slugify("Café  &  Spa!!!") == "caf-spa"
    assert slugify("---trim---") == "trim"
    assert slugify("") == ""
    assert len(slugify("x" * 200)) <= 60


# ═══════════════════════════════════════════════════════════════════
# Create + read
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_org_makes_creator_owner(db):
    from services.organizations import (
        create_organization, get_user_role, list_user_organizations,
    )
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name=f"pytest_Org_{uuid.uuid4().hex[:4]}",
                                    created_by=uid, plan="growth")
    assert r["ok"] is True
    assert r["org"]["org_id"]
    assert r["org"]["plan"] == "growth"
    role = await get_user_role(r["org"]["org_id"], uid)
    assert role == "owner"
    orgs = await list_user_organizations(uid)
    assert len(orgs) == 1
    assert orgs[0]["role"] == "owner"


@pytest.mark.asyncio
async def test_create_org_rejects_invalid_plan(db):
    from services.organizations import create_organization
    r = await create_organization(
        name="pytest_Co", created_by="pytest_u_x", plan="bogus",
    )
    assert r["ok"] is False
    assert r["error"] == "invalid_plan"


@pytest.mark.asyncio
async def test_create_org_unique_slug_auto_increments(db):
    from services.organizations import create_organization
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    a = await create_organization(name="pytest_Same Slug", created_by=uid)
    b = await create_organization(name="pytest_Same Slug", created_by=uid)
    assert a["org"]["slug"] != b["org"]["slug"]
    assert b["org"]["slug"].endswith("-2")


@pytest.mark.asyncio
async def test_get_org_by_id_and_slug(db):
    from services.organizations import (
        create_organization, get_organization, get_organization_by_slug,
    )
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_Lookup", created_by=uid)
    org = await get_organization(r["org"]["org_id"])
    assert org is not None
    assert org["name"] == "pytest_Lookup"
    by_slug = await get_organization_by_slug(r["org"]["slug"])
    assert by_slug["org_id"] == r["org"]["org_id"]


# ═══════════════════════════════════════════════════════════════════
# Update
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_update_org_owner_can_edit(db):
    from services.organizations import create_organization, update_organization
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_Edit", created_by=uid)
    up = await update_organization(
        r["org"]["org_id"], {"name": "pytest_Edited", "plan": "pro"}, uid,
    )
    assert up["ok"] is True
    assert up["org"]["name"] == "pytest_Edited"
    assert up["org"]["plan"] == "pro"


@pytest.mark.asyncio
async def test_update_org_non_member_blocked(db):
    from services.organizations import create_organization, update_organization
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    other = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_Blocked", created_by=uid)
    up = await update_organization(
        r["org"]["org_id"], {"name": "should_fail"}, other,
    )
    assert up["ok"] is False
    assert up["error"] == "permission_denied"


@pytest.mark.asyncio
async def test_update_org_member_role_cant_edit(db):
    from services.organizations import (
        create_organization, add_member, update_organization,
    )
    uid = f"pytest_u_{uuid.uuid4().hex[:6]}"
    other = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_RoleEdit", created_by=uid)
    await add_member(r["org"]["org_id"], other, role="member")
    up = await update_organization(
        r["org"]["org_id"], {"name": "should_fail"}, other,
    )
    assert up["ok"] is False
    assert up["error"] == "permission_denied"


# ═══════════════════════════════════════════════════════════════════
# Membership: add / remove / role change
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_add_member_then_list_includes_role(db):
    from services.organizations import (
        create_organization, add_member, list_user_organizations,
    )
    owner = f"pytest_u_{uuid.uuid4().hex[:6]}"
    new = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_Add", created_by=owner)
    add = await add_member(r["org"]["org_id"], new, role="admin",
                             invited_by=owner)
    assert add["ok"] is True
    orgs = await list_user_organizations(new)
    assert len(orgs) == 1
    assert orgs[0]["role"] == "admin"


@pytest.mark.asyncio
async def test_add_member_invalid_role_rejected(db):
    from services.organizations import create_organization, add_member
    owner = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_BadRole", created_by=owner)
    add = await add_member(r["org"]["org_id"], "pytest_u_x", role="god")
    assert add["ok"] is False
    assert add["error"] == "invalid_role"


@pytest.mark.asyncio
async def test_remove_member_self_allowed(db):
    from services.organizations import (
        create_organization, add_member, remove_member, get_user_role,
    )
    owner = f"pytest_u_{uuid.uuid4().hex[:6]}"
    member = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_SelfLeave", created_by=owner)
    await add_member(r["org"]["org_id"], member, role="member")
    rm = await remove_member(r["org"]["org_id"], member, member)
    assert rm["ok"] is True
    assert await get_user_role(r["org"]["org_id"], member) is None


@pytest.mark.asyncio
async def test_remove_last_owner_blocked(db):
    from services.organizations import create_organization, remove_member
    owner = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_LastOwner", created_by=owner)
    rm = await remove_member(r["org"]["org_id"], owner, owner)
    assert rm["ok"] is False
    assert rm["error"] == "last_owner_cannot_be_removed"


@pytest.mark.asyncio
async def test_member_cant_remove_owner(db):
    from services.organizations import (
        create_organization, add_member, remove_member,
    )
    owner = f"pytest_u_{uuid.uuid4().hex[:6]}"
    member = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_NoCoup", created_by=owner)
    await add_member(r["org"]["org_id"], member, role="member")
    rm = await remove_member(r["org"]["org_id"], owner, member)
    assert rm["ok"] is False
    assert rm["error"] == "permission_denied"


@pytest.mark.asyncio
async def test_admin_cant_remove_owner_even_with_perms(db):
    from services.organizations import (
        create_organization, add_member, remove_member,
    )
    owner = f"pytest_u_{uuid.uuid4().hex[:6]}"
    admin = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_AdminBlock", created_by=owner)
    await add_member(r["org"]["org_id"], admin, role="admin")
    rm = await remove_member(r["org"]["org_id"], owner, admin)
    assert rm["ok"] is False
    assert rm["error"] == "only_owner_can_remove_owner"


@pytest.mark.asyncio
async def test_change_role_owner_can_promote(db):
    from services.organizations import (
        create_organization, add_member, change_member_role, get_user_role,
    )
    owner = f"pytest_u_{uuid.uuid4().hex[:6]}"
    member = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_Promote", created_by=owner)
    await add_member(r["org"]["org_id"], member, role="member")
    chg = await change_member_role(r["org"]["org_id"], member, "admin", owner)
    assert chg["ok"] is True
    assert await get_user_role(r["org"]["org_id"], member) == "admin"


@pytest.mark.asyncio
async def test_change_role_non_owner_blocked(db):
    from services.organizations import (
        create_organization, add_member, change_member_role,
    )
    owner = f"pytest_u_{uuid.uuid4().hex[:6]}"
    admin = f"pytest_u_{uuid.uuid4().hex[:6]}"
    target = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_AdminPromote", created_by=owner)
    await add_member(r["org"]["org_id"], admin, role="admin")
    await add_member(r["org"]["org_id"], target, role="member")
    chg = await change_member_role(r["org"]["org_id"], target, "admin", admin)
    assert chg["ok"] is False
    assert chg["error"] == "owner_required"


@pytest.mark.asyncio
async def test_demote_last_owner_blocked(db):
    from services.organizations import create_organization, change_member_role
    owner = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_DemoteOwn", created_by=owner)
    chg = await change_member_role(r["org"]["org_id"], owner, "admin", owner)
    assert chg["ok"] is False
    assert chg["error"] == "last_owner_cannot_be_demoted"


# ═══════════════════════════════════════════════════════════════════
# Invites
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_invite_then_accept_flow(db):
    from services.organizations import (
        create_organization, create_invite, accept_invite, get_user_role,
    )
    owner = f"pytest_u_{uuid.uuid4().hex[:6]}"
    accepter = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_Inv", created_by=owner)
    inv = await create_invite(r["org"]["org_id"],
                                "invited@pytest.example", role="member",
                                invited_by=owner)
    assert inv["ok"] is True
    assert inv["token"]
    acc = await accept_invite(inv["token"], accepter)
    assert acc["ok"] is True
    role = await get_user_role(r["org"]["org_id"], accepter)
    assert role == "member"


@pytest.mark.asyncio
async def test_invite_invalid_email_rejected(db):
    from services.organizations import create_organization, create_invite
    owner = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_BadEmail", created_by=owner)
    inv = await create_invite(r["org"]["org_id"], "no-at-sign",
                                role="member", invited_by=owner)
    assert inv["ok"] is False
    assert inv["error"] == "invalid_email"


@pytest.mark.asyncio
async def test_accept_invite_twice_rejected(db):
    from services.organizations import (
        create_organization, create_invite, accept_invite,
    )
    owner = f"pytest_u_{uuid.uuid4().hex[:6]}"
    accepter1 = f"pytest_u_{uuid.uuid4().hex[:6]}"
    accepter2 = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_OneShot", created_by=owner)
    inv = await create_invite(r["org"]["org_id"],
                                "oneshot@pytest.example", role="member",
                                invited_by=owner)
    a1 = await accept_invite(inv["token"], accepter1)
    a2 = await accept_invite(inv["token"], accepter2)
    assert a1["ok"] is True
    assert a2["ok"] is False
    assert a2["error"] == "invite_already_used"


@pytest.mark.asyncio
async def test_accept_invite_expired(db):
    from services.organizations import create_organization, accept_invite
    from datetime import datetime, timedelta, timezone
    owner = f"pytest_u_{uuid.uuid4().hex[:6]}"
    accepter = f"pytest_u_{uuid.uuid4().hex[:6]}"
    r = await create_organization(name="pytest_ExpInv", created_by=owner)
    # Hand-insert an expired invite (no helper to do it cleanly)
    await db.organization_invites.insert_one({
        "invite_id":  uuid.uuid4().hex,
        "org_id":     r["org"]["org_id"],
        "email":      "expired@pytest.example",
        "role":       "member",
        "token":      "expired_token_pytest_" + uuid.uuid4().hex[:8],
        "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "status":     "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    row = await db.organization_invites.find_one(
        {"email": "expired@pytest.example"}, {"_id": 0},
    )
    acc = await accept_invite(row["token"], accepter)
    assert acc["ok"] is False
    assert acc["error"] == "invite_expired"


# ═══════════════════════════════════════════════════════════════════
# Org switcher
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_switch_org_persists_current_org_id(db):
    from services.organizations import (
        create_organization, set_current_org,
    )
    owner = f"pytest_u_{uuid.uuid4().hex[:6]}"
    # Pre-create the user row so set_current_org has somewhere to write.
    await db.users.insert_one({"id": owner, "email": f"{owner}@pytest.example"})
    r = await create_organization(name="pytest_Switch", created_by=owner)
    sw = await set_current_org(owner, r["org"]["org_id"])
    assert sw["ok"] is True
    assert sw["current_org_id"] == r["org"]["org_id"]
    u = await db.users.find_one({"id": owner}, {"_id": 0})
    assert u["current_org_id"] == r["org"]["org_id"]
    assert u["current_org_role"] == "owner"
    # cleanup
    await db.users.delete_one({"id": owner})


@pytest.mark.asyncio
async def test_switch_org_non_member_blocked(db):
    from services.organizations import (
        create_organization, set_current_org,
    )
    owner = f"pytest_u_{uuid.uuid4().hex[:6]}"
    outsider = f"pytest_u_{uuid.uuid4().hex[:6]}"
    await db.users.insert_one({"id": outsider, "email": f"{outsider}@pytest.example"})
    r = await create_organization(name="pytest_NoSwitch", created_by=owner)
    sw = await set_current_org(outsider, r["org"]["org_id"])
    assert sw["ok"] is False
    assert sw["error"] == "not_a_member"
    await db.users.delete_one({"id": outsider})


# ═══════════════════════════════════════════════════════════════════
# Source-level wiring sanity
# ═══════════════════════════════════════════════════════════════════

def test_router_module_imports_cleanly():
    from routers.organizations_router import router, set_db
    assert router is not None
    assert callable(set_db)
    # All 11 endpoints registered
    paths = {r.path for r in router.routes}
    assert "/api/orgs" in paths
    assert "/api/orgs/me" in paths
    assert "/api/orgs/{org_id}" in paths
    assert "/api/orgs/{org_id}/members" in paths
    assert "/api/orgs/{org_id}/invites" in paths
    assert "/api/orgs/invites/accept" in paths
    assert "/api/orgs/switch" in paths


def test_registry_wires_orgs_router():
    from pathlib import Path
    src = Path("/app/backend/routers/registry.py").read_text()
    assert "organizations_router" in src
