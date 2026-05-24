"""
services/scim_provisioning.py — iter 332b Batch B (Step 3)

SCIM 2.0 provisioning endpoints + token storage.

Each Organization can enable SCIM. The IdP (Okta, Azure AD) calls the
SCIM endpoints with a long-lived bearer token to push user lifecycle
events: create / update / disable / delete.

Storage:
  db.scim_tokens  — { token_id, org_id, token_hash, name, scopes,
                       created_at, last_used_at, revoked_at }

SCIM protocol surface (registered in routers/scim_router.py):
  POST   /scim/v2/{org_id}/Users           — provision user
  GET    /scim/v2/{org_id}/Users/{user_id}
  PUT    /scim/v2/{org_id}/Users/{user_id} — replace
  PATCH  /scim/v2/{org_id}/Users/{user_id} — partial
  DELETE /scim/v2/{org_id}/Users/{user_id} — soft delete (active=false)
  GET    /scim/v2/{org_id}/Users           — list (paginated)

All SCIM endpoints authenticate via "Authorization: Bearer <scim_token>".
"""
from __future__ import annotations

import hashlib
import hmac as _hmac
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Token management ───────────────────────────────────────────────

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def issue_scim_token(
    org_id: str,
    name: str,
    scopes: Optional[list[str]] = None,
    created_by: Optional[str] = None,
) -> dict:
    """Mint a new SCIM token. Returns the FULL token ONCE; never recoverable."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    if not org_id:
        return {"ok": False, "error": "org_id_required"}
    token = "scim_" + secrets.token_urlsafe(32)
    token_id = uuid.uuid4().hex
    doc = {
        "token_id":   token_id,
        "org_id":     org_id,
        "name":       str(name or "SCIM token").strip()[:80],
        "token_hash": _hash_token(token),
        "token_preview": token[:14] + "…",
        "scopes":     scopes or ["users:read", "users:write"],
        "created_at": _now_iso(),
        "created_by": created_by,
        "last_used_at": None,
        "use_count":  0,
        "revoked_at": None,
    }
    await _db.scim_tokens.insert_one(dict(doc))
    doc.pop("_id", None)
    return {
        "ok":           True,
        "token_id":     token_id,
        "token":        token,
        "token_preview": doc["token_preview"],
        "warning":      "This is the only time the full token is shown — save it now.",
    }


async def validate_scim_token(org_id: str, token: str) -> Optional[dict]:
    """Returns the token row if valid + active + matches the org.
    Updates last_used_at. Constant-time compare on hash."""
    if _db is None or not token:
        return None
    th = _hash_token(token)
    row = await _db.scim_tokens.find_one(
        {"org_id": org_id, "token_hash": th, "revoked_at": None},
        {"_id": 0},
    )
    if not row:
        return None
    # Constant-time on the canonical hash (already done via $eq, but kept
    # explicit for code clarity).
    if not _hmac.compare_digest(row["token_hash"], th):
        return None
    try:
        await _db.scim_tokens.update_one(
            {"token_id": row["token_id"]},
            {"$set":  {"last_used_at": _now_iso()},
             "$inc":  {"use_count": 1}},
        )
    except Exception:
        pass
    return row


async def list_scim_tokens(org_id: str) -> list[dict]:
    if _db is None:
        return []
    cur = _db.scim_tokens.find(
        {"org_id": org_id}, {"_id": 0, "token_hash": 0},
    ).sort("created_at", -1)
    return await cur.to_list(length=100)


async def revoke_scim_token(org_id: str, token_id: str) -> dict:
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    r = await _db.scim_tokens.update_one(
        {"org_id": org_id, "token_id": token_id, "revoked_at": None},
        {"$set": {"revoked_at": _now_iso()}},
    )
    if r.matched_count == 0:
        return {"ok": False, "error": "token_not_found_or_revoked"}
    return {"ok": True, "revoked": True}


# ── User provisioning (SCIM data shape ↔ AUREM users) ──────────────

def scim_user_from_aurem(user: dict, org_id: str) -> dict:
    """Render an AUREM user row in SCIM 2.0 Core User envelope."""
    email = user.get("email", "")
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id":         user.get("id") or user.get("user_id") or "",
        "userName":   email,
        "active":     bool(user.get("active", True)),
        "name": {
            "givenName":  user.get("first_name", ""),
            "familyName": user.get("last_name", ""),
        },
        "emails": [{"value": email, "primary": True}],
        "meta": {
            "resourceType": "User",
            "created":      user.get("created_at"),
            "lastModified": user.get("updated_at"),
        },
        "urn:ietf:params:scim:schemas:extension:aurem:1.0:User": {
            "org_id": org_id,
            "role":   user.get("org_role", "member"),
        },
    }


async def provision_user(
    org_id: str,
    scim_body: dict,
    actor_token_id: str,
) -> dict:
    """SCIM POST /Users — create user in AUREM + add to org."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    emails = scim_body.get("emails") or []
    primary_email = next(
        (e["value"] for e in emails if e.get("primary")), None,
    ) or (emails[0]["value"] if emails else scim_body.get("userName"))
    if not primary_email or "@" not in str(primary_email):
        return {"ok": False, "error": "email_required"}
    primary_email = primary_email.lower().strip()

    name = scim_body.get("name") or {}
    given = name.get("givenName", "")
    family = name.get("familyName", "")
    active = scim_body.get("active", True)

    # Upsert user
    existing = await _db.users.find_one(
        {"email": primary_email}, {"_id": 0, "id": 1},
    )
    if existing:
        user_id = existing["id"]
    else:
        user_id = "scim_" + uuid.uuid4().hex
        await _db.users.insert_one({
            "id":            user_id,
            "email":         primary_email,
            "first_name":    given,
            "last_name":     family,
            "active":        active,
            "created_at":    _now_iso(),
            "updated_at":    _now_iso(),
            "provisioned_via": "scim",
            "scim_token_id":   actor_token_id,
        })

    # Add to org as member
    from services.organizations import add_member
    await add_member(org_id, user_id, role="member",
                      invited_by="scim_provisioner")
    user = await _db.users.find_one({"id": user_id}, {"_id": 0})
    user["org_role"] = "member"
    return {"ok": True, "user": scim_user_from_aurem(user, org_id),
             "created": not existing}


async def deactivate_user(
    org_id: str, user_id: str,
) -> dict:
    """SCIM DELETE / PATCH active=false — flips active=False on user
    AND removes them from the org (soft). SCIM provisioner is a trusted
    system actor and bypasses the org-role gate."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    await _db.users.update_one(
        {"id": user_id},
        {"$set": {"active": False, "deactivated_at": _now_iso(),
                   "deactivated_via": "scim"}},
    )
    # Direct membership flip — bypass remove_member's permission gate
    # because the SCIM provisioner has been authenticated via the
    # org-scoped SCIM token, which already proves write-scope authority.
    await _db.organization_members.update_one(
        {"org_id": org_id, "user_id": user_id},
        {"$set": {"status": "removed", "removed_at": _now_iso(),
                   "removed_by": "scim_provisioner"}},
    )
    return {"ok": True, "deactivated": True, "user_id": user_id}
