"""
routers/scim_router.py — iter 332b Batch B (Step 3)

SCIM 2.0 admin surface (token CRUD) + actual SCIM protocol endpoints.

Admin endpoints (auth via platform admin):
  GET    /api/scim/{org_id}/tokens         — list tokens
  POST   /api/scim/{org_id}/tokens         — issue new token (shown once)
  DELETE /api/scim/{org_id}/tokens/{id}    — revoke

Protocol endpoints (auth via SCIM bearer token):
  GET    /scim/v2/{org_id}/Users
  POST   /scim/v2/{org_id}/Users
  GET    /scim/v2/{org_id}/Users/{user_id}
  DELETE /scim/v2/{org_id}/Users/{user_id}
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Admin surface
admin_router = APIRouter(prefix="/api/scim", tags=["scim-admin"])
# Protocol surface
protocol_router = APIRouter(prefix="/scim/v2", tags=["scim-protocol"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database
    try:
        from services.scim_provisioning import set_db as _s
        _s(database)
    except Exception as e:
        logger.warning(f"[scim] wiring failed: {e}")


async def _require_org_admin(request: Request, org_id: str) -> dict:
    try:
        from utils.auth import get_current_user
        user = await get_current_user(request)
    except Exception:
        user = None
    if not user or not user.get("id"):
        raise HTTPException(401, "auth_required")
    from services.organizations import get_user_role
    role = await get_user_role(org_id, user["id"])
    if role not in ("owner", "admin"):
        raise HTTPException(403, "permission_denied")
    return user


async def _require_scim_token(request: Request, org_id: str) -> dict:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "scim_token_required")
    token = auth[7:].strip()
    from services.scim_provisioning import validate_scim_token
    row = await validate_scim_token(org_id, token)
    if not row:
        raise HTTPException(401, "scim_token_invalid")
    return row


class TokenIssueBody(BaseModel):
    name:   str = Field(..., min_length=1, max_length=80)
    scopes: Optional[list[str]] = None


# ── Admin: token management ────────────────────────────────────────

@admin_router.get("/{org_id}/tokens")
async def list_tokens(org_id: str, request: Request) -> dict[str, Any]:
    await _require_org_admin(request, org_id)
    from services.scim_provisioning import list_scim_tokens
    rows = await list_scim_tokens(org_id)
    return {"ok": True, "rows": rows}


@admin_router.post("/{org_id}/tokens")
async def issue_token(org_id: str, body: TokenIssueBody,
                        request: Request) -> dict[str, Any]:
    user = await _require_org_admin(request, org_id)
    from services.scim_provisioning import issue_scim_token
    r = await issue_scim_token(org_id, body.name, body.scopes,
                                 created_by=user["id"])
    if not r.get("ok"):
        raise HTTPException(400, r.get("error", "issue_failed"))
    try:
        from services.unified_audit import write_event
        await write_event(
            action="scim_token_issued", resource=f"org:{org_id}",
            result="ok", user_id=user["id"], org_id=org_id,
            source_collection="scim_tokens",
            extra={"token_id": r["token_id"], "name": body.name},
        )
    except Exception:
        pass
    return r


@admin_router.delete("/{org_id}/tokens/{token_id}")
async def revoke_token(org_id: str, token_id: str,
                         request: Request) -> dict[str, Any]:
    user = await _require_org_admin(request, org_id)
    from services.scim_provisioning import revoke_scim_token
    r = await revoke_scim_token(org_id, token_id)
    if not r.get("ok"):
        raise HTTPException(404, r.get("error", "revoke_failed"))
    try:
        from services.unified_audit import write_event
        await write_event(
            action="scim_token_revoked", resource=f"org:{org_id}",
            result="ok", user_id=user["id"], org_id=org_id,
            source_collection="scim_tokens",
            extra={"token_id": token_id},
        )
    except Exception:
        pass
    return r


# ── Protocol: SCIM 2.0 endpoints ───────────────────────────────────

@protocol_router.get("/{org_id}/Users")
async def list_users(org_id: str, request: Request,
                       startIndex: int = 1, count: int = 50) -> dict[str, Any]:
    await _require_scim_token(request, org_id)
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    # All active members of this org
    members_cur = _db.organization_members.find(
        {"org_id": org_id, "status": "active"}, {"_id": 0},
    )
    members = await members_cur.to_list(length=2000)
    user_ids = [m["user_id"] for m in members]
    users_cur = _db.users.find({"id": {"$in": user_ids}}, {"_id": 0})
    users = await users_cur.to_list(length=2000)
    role_by_uid = {m["user_id"]: m["role"] for m in members}
    from services.scim_provisioning import scim_user_from_aurem
    page = users[startIndex - 1: startIndex - 1 + count]
    resources = []
    for u in page:
        u["org_role"] = role_by_uid.get(u["id"], "member")
        resources.append(scim_user_from_aurem(u, org_id))
    return {
        "schemas":      ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": len(users),
        "startIndex":   startIndex,
        "itemsPerPage": len(resources),
        "Resources":    resources,
    }


@protocol_router.post("/{org_id}/Users")
async def create_user(org_id: str, request: Request) -> dict[str, Any]:
    token_row = await _require_scim_token(request, org_id)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "invalid_json")
    from services.scim_provisioning import provision_user
    r = await provision_user(org_id, body, token_row["token_id"])
    if not r.get("ok"):
        raise HTTPException(400, r.get("error", "provision_failed"))
    return r["user"]


@protocol_router.get("/{org_id}/Users/{user_id}")
async def get_user_endpoint(org_id: str, user_id: str,
                              request: Request) -> dict[str, Any]:
    await _require_scim_token(request, org_id)
    if _db is None:
        raise HTTPException(503, "db_not_ready")
    user = await _db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(404, "user_not_found")
    from services.organizations import get_user_role
    user["org_role"] = await get_user_role(org_id, user_id) or "member"
    from services.scim_provisioning import scim_user_from_aurem
    return scim_user_from_aurem(user, org_id)


@protocol_router.delete("/{org_id}/Users/{user_id}")
async def delete_user(org_id: str, user_id: str,
                        request: Request) -> dict[str, Any]:
    await _require_scim_token(request, org_id)
    from services.scim_provisioning import deactivate_user
    r = await deactivate_user(org_id, user_id)
    return r
