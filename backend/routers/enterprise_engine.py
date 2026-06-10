"""
Phase F: Enterprise Features Engine
Team management, audit trail, white-labeling, data export
"""
import os
import logging
import uuid
import json
import csv
import io
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
import jwt
import bcrypt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enterprise", tags=["Enterprise Features"])

from config import JWT_SECRET
JWT_ALGORITHM = "HS256"

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db

async def _get_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        payload = jwt.decode(auth.split(" ")[1], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        raise HTTPException(401, "Invalid token")

async def _require_admin(request: Request):
    user = await _get_user(request)
    if not user.get("is_admin"):
        raise HTTPException(403, "Admin access required")
    return user

async def _log_activity(db, tenant_id: str, user_id: str, action: str, resource: str, details: dict = None):
    """Write an audit log entry"""
    await db.audit_trail.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "user_id": user_id,
        "action": action,
        "resource": resource,
        "details": details or {},
        "ip_address": "",
        "created_at": datetime.now(timezone.utc).isoformat()
    })


# ═══════════════════════════════════════════════════════════════════════
# TEAM MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════

ROLES = {
    "owner": {"level": 100, "label": "Owner", "desc": "Full access, billing, team management"},
    "admin": {"level": 80, "label": "Admin", "desc": "All features except billing and owner transfer"},
    "manager": {"level": 60, "label": "Manager", "desc": "CRM, pipeline, campaigns, analytics"},
    "agent": {"level": 40, "label": "Agent", "desc": "Voice calls, chat, customer handling"},
    "viewer": {"level": 20, "label": "Viewer", "desc": "Read-only access to dashboards"},
}

class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = "agent"
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""

class UpdateMemberRoleRequest(BaseModel):
    role: str

@router.get("/roles")
async def list_roles(request: Request):
    """Available team roles"""
    await _get_user(request)
    return {"roles": [{"id": k, **v} for k, v in ROLES.items()]}

@router.get("/team")
async def list_team(request: Request):
    """List all team members"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    members = await db.team_members.find(
        {"tenant_id": tenant_id}, {"_id": 0, "password_hash": 0}
    ).sort("created_at", 1).to_list(200)

    # Add the owner as first entry
    owner = await db.users.find_one({"id": tenant_id}, {"_id": 0, "password": 0})
    owner_entry = {
        "id": tenant_id,
        "email": owner.get("email", "") if owner else "",
        "first_name": owner.get("first_name", "") if owner else "",
        "last_name": owner.get("last_name", "") if owner else "",
        "role": "owner",
        "status": "active",
        "created_at": owner.get("created_at", "") if owner else "",
        "is_owner": True
    }

    return {"members": [owner_entry] + members, "total": len(members) + 1}

@router.post("/team/invite")
async def invite_member(body: InviteMemberRequest, request: Request):
    """Invite a new team member"""
    user = await _require_admin(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    if body.role not in ROLES or body.role == "owner":
        raise HTTPException(400, f"Invalid role: {body.role}")

    existing = await db.team_members.find_one({"tenant_id": tenant_id, "email": body.email})
    if existing:
        raise HTTPException(409, "Member with this email already exists")

    temp_password = str(uuid.uuid4())[:12]
    member = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "email": body.email,
        "first_name": body.first_name or "",
        "last_name": body.last_name or "",
        "role": body.role,
        "role_id": body.role,
        "status": "invited",
        "password_hash": bcrypt.hashpw(temp_password.encode(), bcrypt.gensalt()).decode(),
        "invited_by": user.get("user_id"),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.team_members.insert_one(member)
    await _log_activity(db, tenant_id, user.get("user_id"), "team.invite", "team_members", {"email": body.email, "role": body.role})

    return {
        "success": True,
        "member_id": member["id"],
        "email": body.email,
        "role": body.role,
        "temp_password": temp_password,
        "message": f"Invited {body.email} as {body.role}"
    }

@router.put("/team/{member_id}/role")
async def update_member_role(member_id: str, body: UpdateMemberRoleRequest, request: Request):
    """Change a team member's role"""
    user = await _require_admin(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    if body.role not in ROLES or body.role == "owner":
        raise HTTPException(400, f"Invalid role: {body.role}")

    result = await db.team_members.update_one(
        {"id": member_id, "tenant_id": tenant_id},
        {"$set": {"role": body.role, "role_id": body.role, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(404, "Member not found")

    await _log_activity(db, tenant_id, user.get("user_id"), "team.role_change", "team_members", {"member_id": member_id, "new_role": body.role})
    return {"success": True, "message": f"Role updated to {body.role}"}

@router.delete("/team/{member_id}")
async def remove_member(member_id: str, request: Request):
    """Remove a team member"""
    user = await _require_admin(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    if member_id == tenant_id:
        raise HTTPException(400, "Cannot remove the account owner")

    result = await db.team_members.delete_one({"id": member_id, "tenant_id": tenant_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Member not found")

    await _log_activity(db, tenant_id, user.get("user_id"), "team.remove", "team_members", {"member_id": member_id})
    return {"success": True, "message": "Member removed"}

@router.put("/team/{member_id}/activate")
async def activate_member(member_id: str, request: Request):
    """Activate an invited member"""
    user = await _require_admin(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    result = await db.team_members.update_one(
        {"id": member_id, "tenant_id": tenant_id},
        {"$set": {"status": "active", "activated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.modified_count == 0:
        raise HTTPException(404, "Member not found")
    return {"success": True}


# ═══════════════════════════════════════════════════════════════════════
# AUDIT TRAIL
# ═══════════════════════════════════════════════════════════════════════
# iter D-76 dedupe — /audit moved fully to routers/enterprise_router.py
# (newer unified_audit-backed implementation). Both this file and
# enterprise_router declare a router under /api/enterprise, producing a
# duplicate (GET, /api/enterprise/audit). The unified-audit version is
# the more mature handler (supports event filtering, CSV export).


# ═══════════════════════════════════════════════════════════════════════
# WHITE-LABEL SETTINGS
# ═══════════════════════════════════════════════════════════════════════

class WhiteLabelSettings(BaseModel):
    brand_name: Optional[str] = None
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    primary_color: Optional[str] = None
    accent_color: Optional[str] = None
    custom_domain: Optional[str] = None
    support_email: Optional[str] = None
    footer_text: Optional[str] = None

@router.get("/whitelabel")
async def get_whitelabel(request: Request):
    """Get current white-label settings"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    settings = await db.whitelabel_settings.find_one({"tenant_id": tenant_id}, {"_id": 0})
    return settings or {
        "tenant_id": tenant_id,
        "brand_name": "AUREM",
        "primary_color": "#2D7A4A",
        "accent_color": "#D4AF37",
        "footer_text": "Powered by AUREM AI"
    }

@router.put("/whitelabel")
async def update_whitelabel(body: WhiteLabelSettings, request: Request):
    """Update white-label settings"""
    user = await _require_admin(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    update_data = {k: v for k, v in body.dict().items() if v is not None}
    update_data["tenant_id"] = tenant_id
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.whitelabel_settings.update_one(
        {"tenant_id": tenant_id}, {"$set": update_data}, upsert=True
    )
    await _log_activity(db, tenant_id, user.get("user_id"), "whitelabel.update", "whitelabel_settings", update_data)
    return {"success": True, "message": "White-label settings updated"}


# ═══════════════════════════════════════════════════════════════════════
# DATA EXPORT
# ═══════════════════════════════════════════════════════════════════════

@router.get("/export/{resource}")
async def export_data(resource: str, request: Request, format: str = Query("json", regex="^(json|csv)$")):
    """Export data as JSON or CSV (team, audit, invoices, usage)"""
    user = await _require_admin(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    collection_map = {
        "team": ("team_members", {"tenant_id": tenant_id}),
        "audit": ("audit_trail", {"tenant_id": tenant_id}),
        "invoices": ("invoices", {"tenant_id": tenant_id}),
        "usage": ("usage_events", {"tenant_id": tenant_id}),
        "payments": ("payments", {"tenant_id": tenant_id}),
    }

    if resource not in collection_map:
        raise HTTPException(400, f"Invalid resource. Choose from: {', '.join(collection_map.keys())}")

    col_name, query = collection_map[resource]
    docs = await db[col_name].find(query, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(10000)

    await _log_activity(db, tenant_id, user.get("user_id"), "data.export", resource, {"format": format, "count": len(docs)})

    if format == "csv" and docs:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=docs[0].keys())
        writer.writeheader()
        for doc in docs:
            row = {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in doc.items()}
            writer.writerow(row)
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={resource}_export.csv"}
        )

    return {"resource": resource, "count": len(docs), "data": docs}


# ═══════════════════════════════════════════════════════════════════════
# ENTERPRISE DASHBOARD SUMMARY
# ═══════════════════════════════════════════════════════════════════════

@router.get("/summary")
async def enterprise_summary(request: Request):
    """Quick summary of enterprise features status"""
    user = await _get_user(request)
    db = get_db()
    tenant_id = user.get("tenant_id", user.get("user_id"))

    team_count = await db.team_members.count_documents({"tenant_id": tenant_id})
    audit_count = await db.audit_trail.count_documents({"tenant_id": tenant_id})
    wl = await db.whitelabel_settings.find_one({"tenant_id": tenant_id})

    return {
        "team_members": team_count + 1,
        "audit_entries": audit_count,
        "whitelabel_configured": wl is not None,
        "data_export_available": True,
        "sso_enabled": False
    }

print("[STARTUP] Enterprise Features Engine loaded (Phase F: Team, Audit, White-Label, Export)", flush=True)
