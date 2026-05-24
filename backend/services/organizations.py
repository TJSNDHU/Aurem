"""
services/organizations.py — iter 332b Batch B (Step 1)
========================================================

Organization entity = top-level container above users. Foundation for:
  • SAML 2.0 SSO (an SSO config is org-scoped)
  • SCIM 2.0 provisioning (a SCIM endpoint is org-scoped)
  • Enterprise billing (one Stripe customer per org)
  • Future RBAC user tiers (a user's role is org-scoped)

DB collections:
  • organizations            — top-level org rows
  • organization_members     — { org_id, user_id, role, status, joined_at }
  • organization_invites     — { org_id, email, role, token, expires_at }

Indexes (set up at first set_db() call):
  organizations.slug            UNIQUE
  organizations.org_id          UNIQUE
  organization_members.{org_id,user_id} UNIQUE COMPOUND
  organization_invites.token    UNIQUE
"""
from __future__ import annotations

import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_db = None
_indexes_built = False


def set_db(database) -> None:
    global _db, _indexes_built
    _db = database
    if not _indexes_built:
        # Schedule index builds on the running loop; idempotent.
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(_ensure_indexes())
            else:
                loop.run_until_complete(_ensure_indexes())
            _indexes_built = True
        except Exception as e:
            logger.debug(f"[orgs] index build deferred: {e}")


async def _ensure_indexes() -> None:
    if _db is None:
        return
    try:
        await _db.organizations.create_index("slug", unique=True)
        await _db.organizations.create_index("org_id", unique=True)
        await _db.organization_members.create_index(
            [("org_id", 1), ("user_id", 1)], unique=True,
        )
        await _db.organization_invites.create_index("token", unique=True)
        await _db.organization_invites.create_index("email")
    except Exception as e:
        logger.debug(f"[orgs] ensure_indexes warn: {e}")


# ── Helpers ─────────────────────────────────────────────────────────

_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def slugify(name: str) -> str:
    """Lowercase, hyphenated, [a-z0-9-] only, trimmed, 60-char cap."""
    s = (name or "").strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = _SLUG_RE.sub("", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:60]


VALID_ROLES = ("owner", "admin", "member", "viewer")
VALID_PLANS = ("free", "starter", "growth", "pro", "enterprise")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Org CRUD ────────────────────────────────────────────────────────

async def create_organization(
    name: str,
    created_by: str,
    plan: str = "free",
    slug: Optional[str] = None,
    domain: Optional[str] = None,
) -> dict:
    """Create a new organization with the creator as Owner.

    Returns {ok, org} on success or {ok:false, error} on conflict.
    """
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    if not name or not name.strip():
        return {"ok": False, "error": "name_required"}
    if plan not in VALID_PLANS:
        return {"ok": False, "error": "invalid_plan"}

    # Auto-slug from name if not provided; uniqueify on collision.
    base_slug = slug.strip().lower() if slug else slugify(name)
    if not base_slug:
        base_slug = f"org-{uuid.uuid4().hex[:8]}"
    final_slug = base_slug
    for n in range(2, 100):
        existing = await _db.organizations.find_one(
            {"slug": final_slug}, {"_id": 0, "slug": 1},
        )
        if not existing:
            break
        final_slug = f"{base_slug}-{n}"
    else:
        return {"ok": False, "error": "slug_collision"}

    org_id = uuid.uuid4().hex
    doc = {
        "org_id": org_id,
        "name": name.strip()[:120],
        "slug": final_slug,
        "domain": (domain or "").strip().lower()[:120] or None,
        "plan": plan,
        "status": "active",
        "settings": {},
        "created_by": created_by,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    await _db.organizations.insert_one(dict(doc))
    # Strip the _id Mongo just added to our local copy.
    doc.pop("_id", None)

    # Make the creator the owner.
    await _db.organization_members.insert_one({
        "org_id":     org_id,
        "user_id":    created_by,
        "role":       "owner",
        "status":     "active",
        "joined_at":  _now_iso(),
        "invited_by": created_by,
    })
    return {"ok": True, "org": doc}


async def get_organization(org_id: str) -> Optional[dict]:
    if _db is None:
        return None
    return await _db.organizations.find_one({"org_id": org_id}, {"_id": 0})


async def get_organization_by_slug(slug: str) -> Optional[dict]:
    if _db is None:
        return None
    return await _db.organizations.find_one({"slug": slug}, {"_id": 0})


async def update_organization(
    org_id: str,
    updates: dict,
    actor_user_id: str,
) -> dict:
    """Owner/admin can edit name, plan, domain, settings. Slug + org_id immutable."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    role = await get_user_role(org_id, actor_user_id)
    if role not in ("owner", "admin"):
        return {"ok": False, "error": "permission_denied", "role": role}

    allowed = {"name", "plan", "domain", "settings", "status"}
    patch = {}
    if "name" in updates and updates["name"]:
        patch["name"] = str(updates["name"]).strip()[:120]
    if "plan" in updates:
        if updates["plan"] not in VALID_PLANS:
            return {"ok": False, "error": "invalid_plan"}
        patch["plan"] = updates["plan"]
    if "domain" in updates:
        patch["domain"] = (str(updates["domain"] or "").strip().lower()[:120] or None)
    if "settings" in updates and isinstance(updates["settings"], dict):
        patch["settings"] = {k: v for k, v in updates["settings"].items()
                              if isinstance(k, str)}
    if "status" in updates and updates["status"] in ("active", "suspended", "trial"):
        # Only Owner can suspend.
        if updates["status"] == "suspended" and role != "owner":
            return {"ok": False, "error": "owner_required_for_suspend"}
        patch["status"] = updates["status"]
    if not patch:
        return {"ok": False, "error": "no_valid_fields"}

    patch["updated_at"] = _now_iso()
    r = await _db.organizations.find_one_and_update(
        {"org_id": org_id},
        {"$set": patch},
        projection={"_id": 0},
        return_document=True,
    )
    if not r:
        return {"ok": False, "error": "org_not_found"}
    return {"ok": True, "org": r}


# ── Membership ──────────────────────────────────────────────────────

async def get_user_role(org_id: str, user_id: str) -> Optional[str]:
    """Returns the user's role string in the org, or None if not a member."""
    if _db is None or not org_id or not user_id:
        return None
    row = await _db.organization_members.find_one(
        {"org_id": org_id, "user_id": user_id, "status": "active"},
        {"_id": 0, "role": 1},
    )
    return row.get("role") if row else None


async def list_user_organizations(user_id: str) -> list[dict]:
    """All active orgs the user belongs to, with their role attached."""
    if _db is None:
        return []
    cursor = _db.organization_members.find(
        {"user_id": user_id, "status": "active"}, {"_id": 0},
    )
    members = await cursor.to_list(length=200)
    if not members:
        return []
    org_ids = [m["org_id"] for m in members]
    orgs_cur = _db.organizations.find(
        {"org_id": {"$in": org_ids}}, {"_id": 0},
    )
    orgs = {o["org_id"]: o for o in await orgs_cur.to_list(length=200)}
    out = []
    for m in members:
        org = orgs.get(m["org_id"])
        if org:
            out.append({**org, "role": m["role"]})
    return out


async def list_org_members(org_id: str) -> list[dict]:
    if _db is None:
        return []
    cursor = _db.organization_members.find({"org_id": org_id}, {"_id": 0})
    return await cursor.to_list(length=500)


async def add_member(
    org_id: str,
    user_id: str,
    role: str = "member",
    invited_by: Optional[str] = None,
) -> dict:
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    if role not in VALID_ROLES:
        return {"ok": False, "error": "invalid_role"}
    existing = await _db.organization_members.find_one(
        {"org_id": org_id, "user_id": user_id}, {"_id": 0},
    )
    if existing:
        # Re-activate if previously removed; otherwise no-op success.
        if existing.get("status") == "active":
            return {"ok": True, "already_member": True, "role": existing["role"]}
        await _db.organization_members.update_one(
            {"org_id": org_id, "user_id": user_id},
            {"$set": {"status": "active", "role": role,
                       "joined_at": _now_iso()}},
        )
        return {"ok": True, "reactivated": True, "role": role}
    await _db.organization_members.insert_one({
        "org_id":     org_id,
        "user_id":    user_id,
        "role":       role,
        "status":     "active",
        "joined_at":  _now_iso(),
        "invited_by": invited_by,
    })
    return {"ok": True, "role": role}


async def remove_member(
    org_id: str,
    user_id: str,
    actor_user_id: str,
) -> dict:
    """Soft-remove (status='removed'). Owner can't be removed if they're the
    last owner."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    actor_role = await get_user_role(org_id, actor_user_id)
    target_row = await _db.organization_members.find_one(
        {"org_id": org_id, "user_id": user_id}, {"_id": 0},
    )
    if not target_row:
        return {"ok": False, "error": "member_not_found"}
    # Permission: actor must be owner/admin, OR removing themselves.
    is_self = actor_user_id == user_id
    if not is_self and actor_role not in ("owner", "admin"):
        return {"ok": False, "error": "permission_denied"}
    # Owner cannot be removed by admin.
    if target_row.get("role") == "owner" and actor_role != "owner":
        return {"ok": False, "error": "only_owner_can_remove_owner"}
    # Last-owner guard.
    if target_row.get("role") == "owner":
        other_owners = await _db.organization_members.count_documents({
            "org_id": org_id, "role": "owner", "status": "active",
            "user_id": {"$ne": user_id},
        })
        if other_owners == 0:
            return {"ok": False, "error": "last_owner_cannot_be_removed"}
    await _db.organization_members.update_one(
        {"org_id": org_id, "user_id": user_id},
        {"$set": {"status": "removed", "removed_at": _now_iso(),
                   "removed_by": actor_user_id}},
    )
    return {"ok": True, "removed": True}


async def change_member_role(
    org_id: str,
    user_id: str,
    new_role: str,
    actor_user_id: str,
) -> dict:
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    if new_role not in VALID_ROLES:
        return {"ok": False, "error": "invalid_role"}
    actor_role = await get_user_role(org_id, actor_user_id)
    if actor_role != "owner":
        return {"ok": False, "error": "owner_required"}
    target_row = await _db.organization_members.find_one(
        {"org_id": org_id, "user_id": user_id, "status": "active"},
        {"_id": 0},
    )
    if not target_row:
        return {"ok": False, "error": "member_not_found"}
    # Demoting the only owner is blocked.
    if target_row.get("role") == "owner" and new_role != "owner":
        other_owners = await _db.organization_members.count_documents({
            "org_id": org_id, "role": "owner", "status": "active",
            "user_id": {"$ne": user_id},
        })
        if other_owners == 0:
            return {"ok": False, "error": "last_owner_cannot_be_demoted"}
    await _db.organization_members.update_one(
        {"org_id": org_id, "user_id": user_id},
        {"$set": {"role": new_role, "role_changed_at": _now_iso()}},
    )
    return {"ok": True, "role": new_role}


# ── Invites ────────────────────────────────────────────────────────

async def create_invite(
    org_id: str,
    email: str,
    role: str = "member",
    invited_by: Optional[str] = None,
    ttl_days: int = 14,
) -> dict:
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    if "@" not in email:
        return {"ok": False, "error": "invalid_email"}
    if role not in VALID_ROLES:
        return {"ok": False, "error": "invalid_role"}
    token = secrets.token_urlsafe(24)
    doc = {
        "invite_id":  uuid.uuid4().hex,
        "org_id":     org_id,
        "email":      email.lower().strip(),
        "role":       role,
        "token":      token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat(),
        "status":     "pending",
        "created_at": _now_iso(),
        "invited_by": invited_by,
    }
    await _db.organization_invites.insert_one(dict(doc))
    doc.pop("_id", None)
    return {"ok": True, "invite": doc, "token": token}


async def accept_invite(token: str, user_id: str) -> dict:
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    inv = await _db.organization_invites.find_one({"token": token}, {"_id": 0})
    if not inv:
        return {"ok": False, "error": "invite_not_found"}
    if inv.get("status") != "pending":
        return {"ok": False, "error": "invite_already_used"}
    try:
        exp = datetime.fromisoformat(inv["expires_at"])
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            await _db.organization_invites.update_one(
                {"token": token}, {"$set": {"status": "expired"}},
            )
            return {"ok": False, "error": "invite_expired"}
    except Exception:
        pass
    # Add member.
    add = await add_member(inv["org_id"], user_id, inv["role"],
                            invited_by=inv.get("invited_by"))
    await _db.organization_invites.update_one(
        {"token": token},
        {"$set": {"status": "accepted",
                   "accepted_at": _now_iso(),
                   "accepted_by": user_id}},
    )
    return {"ok": True, "org_id": inv["org_id"], "role": inv["role"], "add": add}


# ── Org switcher (current_org_id on users) ──────────────────────────

async def set_current_org(user_id: str, org_id: str) -> dict:
    """User picks which org context they're working in. Persists to users."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    role = await get_user_role(org_id, user_id)
    if not role:
        return {"ok": False, "error": "not_a_member"}
    await _db.users.update_one(
        {"id": user_id},
        {"$set": {"current_org_id": org_id, "current_org_role": role,
                   "current_org_set_at": _now_iso()}},
    )
    return {"ok": True, "current_org_id": org_id, "role": role}
