"""
routers/organizations_router.py — iter 332b Batch B (Step 1)

Public surface for the Organization entity.

Endpoints (all under /api/orgs/*):
  POST   /                              — create org
  GET    /me                             — my orgs (with role attached)
  GET    /{org_id}                       — read org (member only)
  PATCH  /{org_id}                       — update (owner/admin only)
  GET    /{org_id}/members               — list members
  POST   /{org_id}/members               — add member directly (owner/admin)
  DELETE /{org_id}/members/{user_id}     — remove member
  PATCH  /{org_id}/members/{user_id}     — change role (owner only)
  POST   /{org_id}/invites               — create invite link
  POST   /invites/accept                 — accept invite by token
  POST   /switch                         — set current_org_id on user
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/orgs", tags=["organizations"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database
    try:
        from services.organizations import set_db as _orgs_set
        _orgs_set(database)
    except Exception as e:
        logger.warning(f"[orgs-router] orgs wiring failed: {e}")


async def _current_user(request: Request) -> dict:
    """Resolve the bearer-authenticated user. 401s on missing/invalid token."""
    try:
        from utils.auth import get_current_user
        user = await get_current_user(request)
    except Exception as e:
        logger.debug(f"[orgs] auth resolve failed: {e}")
        user = None
    if not user or not user.get("id"):
        raise HTTPException(401, "auth_required")
    return user


# ── Models ──────────────────────────────────────────────────────────

class OrgCreateBody(BaseModel):
    name:   str = Field(..., min_length=1, max_length=120)
    slug:   Optional[str] = Field(None, max_length=60)
    domain: Optional[str] = Field(None, max_length=120)
    plan:   str = Field("free", max_length=20)


class OrgPatchBody(BaseModel):
    name:     Optional[str] = Field(None, max_length=120)
    plan:     Optional[str] = Field(None, max_length=20)
    domain:   Optional[str] = Field(None, max_length=120)
    settings: Optional[dict] = None
    status:   Optional[str] = Field(None, max_length=20)


class MemberAddBody(BaseModel):
    user_id: str = Field(..., max_length=80)
    role:    str = Field("member", max_length=20)


class MemberRoleBody(BaseModel):
    role: str = Field(..., max_length=20)


class InviteBody(BaseModel):
    email: str = Field(..., max_length=160)
    role:  str = Field("member", max_length=20)


class AcceptInviteBody(BaseModel):
    token: str = Field(..., max_length=120)


class SwitchOrgBody(BaseModel):
    org_id: str = Field(..., max_length=80)


# ── Org CRUD ────────────────────────────────────────────────────────

@router.post("")
async def create_org_endpoint(body: OrgCreateBody,
                               request: Request) -> dict[str, Any]:
    user = await _current_user(request)
    from services.organizations import create_organization
    r = await create_organization(
        name=body.name, slug=body.slug, domain=body.domain,
        plan=body.plan, created_by=user["id"],
    )
    if not r.get("ok"):
        raise HTTPException(400, r.get("error", "create_failed"))
    # Audit
    try:
        from services.unified_audit import write_event
        await write_event(
            action="org_created", resource=f"org:{r['org']['org_id']}",
            result="ok", user_id=user["id"],
            org_id=r["org"]["org_id"],
            source_collection="organizations",
            extra={"slug": r["org"]["slug"], "plan": r["org"]["plan"]},
        )
    except Exception:
        pass
    return r


@router.get("/me")
async def list_my_orgs(request: Request) -> dict[str, Any]:
    user = await _current_user(request)
    from services.organizations import list_user_organizations
    orgs = await list_user_organizations(user["id"])
    return {"ok": True, "rows": orgs, "current_org_id": user.get("current_org_id")}


@router.get("/{org_id}")
async def get_org_endpoint(org_id: str, request: Request) -> dict[str, Any]:
    user = await _current_user(request)
    from services.organizations import get_organization, get_user_role
    role = await get_user_role(org_id, user["id"])
    if not role:
        raise HTTPException(403, "not_a_member")
    org = await get_organization(org_id)
    if not org:
        raise HTTPException(404, "org_not_found")
    return {"ok": True, "org": org, "role": role}


@router.patch("/{org_id}")
async def patch_org_endpoint(org_id: str, body: OrgPatchBody,
                              request: Request) -> dict[str, Any]:
    user = await _current_user(request)
    from services.organizations import update_organization
    updates = body.model_dump(exclude_none=True)
    r = await update_organization(org_id, updates, user["id"])
    if not r.get("ok"):
        code = 403 if r.get("error") in ("permission_denied",
                                          "owner_required_for_suspend") else 400
        raise HTTPException(code, r.get("error", "update_failed"))
    try:
        from services.unified_audit import write_event
        await write_event(
            action="org_updated", resource=f"org:{org_id}", result="ok",
            user_id=user["id"], org_id=org_id,
            source_collection="organizations",
            extra={"keys": list(updates.keys())},
        )
    except Exception:
        pass
    return r


# ── Membership ──────────────────────────────────────────────────────

@router.get("/{org_id}/members")
async def list_members_endpoint(org_id: str,
                                  request: Request) -> dict[str, Any]:
    user = await _current_user(request)
    from services.organizations import get_user_role, list_org_members
    role = await get_user_role(org_id, user["id"])
    if not role:
        raise HTTPException(403, "not_a_member")
    rows = await list_org_members(org_id)
    return {"ok": True, "rows": rows}


@router.post("/{org_id}/members")
async def add_member_endpoint(org_id: str, body: MemberAddBody,
                                request: Request) -> dict[str, Any]:
    user = await _current_user(request)
    from services.organizations import get_user_role, add_member
    role = await get_user_role(org_id, user["id"])
    if role not in ("owner", "admin"):
        raise HTTPException(403, "permission_denied")
    r = await add_member(org_id, body.user_id, body.role,
                          invited_by=user["id"])
    if not r.get("ok"):
        raise HTTPException(400, r.get("error", "add_failed"))
    return r


@router.delete("/{org_id}/members/{user_id}")
async def remove_member_endpoint(org_id: str, user_id: str,
                                   request: Request) -> dict[str, Any]:
    user = await _current_user(request)
    from services.organizations import remove_member
    r = await remove_member(org_id, user_id, user["id"])
    if not r.get("ok"):
        code = (403 if r["error"] in ("permission_denied",
                                       "only_owner_can_remove_owner")
                 else 409 if r["error"] == "last_owner_cannot_be_removed"
                 else 404)
        raise HTTPException(code, r["error"])
    return r


@router.patch("/{org_id}/members/{user_id}")
async def change_role_endpoint(org_id: str, user_id: str, body: MemberRoleBody,
                                 request: Request) -> dict[str, Any]:
    user = await _current_user(request)
    from services.organizations import change_member_role
    r = await change_member_role(org_id, user_id, body.role, user["id"])
    if not r.get("ok"):
        code = (403 if r["error"] == "owner_required"
                 else 409 if r["error"] == "last_owner_cannot_be_demoted"
                 else 404 if r["error"] == "member_not_found"
                 else 400)
        raise HTTPException(code, r["error"])
    return r


# ── Invites ─────────────────────────────────────────────────────────

@router.post("/{org_id}/invites")
async def create_invite_endpoint(org_id: str, body: InviteBody,
                                   request: Request) -> dict[str, Any]:
    user = await _current_user(request)
    from services.organizations import get_user_role, create_invite
    role = await get_user_role(org_id, user["id"])
    if role not in ("owner", "admin"):
        raise HTTPException(403, "permission_denied")
    r = await create_invite(org_id, body.email, body.role,
                              invited_by=user["id"])
    if not r.get("ok"):
        raise HTTPException(400, r.get("error", "invite_failed"))
    return r


@router.post("/invites/accept")
async def accept_invite_endpoint(body: AcceptInviteBody,
                                   request: Request) -> dict[str, Any]:
    user = await _current_user(request)
    from services.organizations import accept_invite
    r = await accept_invite(body.token, user["id"])
    if not r.get("ok"):
        code = (410 if r["error"] in ("invite_expired", "invite_already_used")
                 else 404)
        raise HTTPException(code, r["error"])
    return r


# ── Org switcher ───────────────────────────────────────────────────

@router.post("/switch")
async def switch_org_endpoint(body: SwitchOrgBody,
                                request: Request) -> dict[str, Any]:
    user = await _current_user(request)
    from services.organizations import set_current_org
    r = await set_current_org(user["id"], body.org_id)
    if not r.get("ok"):
        raise HTTPException(403, r.get("error", "switch_failed"))
    return r
