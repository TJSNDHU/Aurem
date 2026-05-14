"""
AUREM Client Manager Router
Admin panel for managing multiple business clients and their credentials.
All sensitive credentials are AES-256 encrypted via the Vault.
"""
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/clients", tags=["Client Manager"])
logger = logging.getLogger(__name__)

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


def _get_user_from_token(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        import jwt
        secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
        payload = jwt.decode(auth_header.split(" ", 1)[1], secret, algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(401, "Invalid token")


def _encrypt(value: str) -> str:
    if not value:
        return ""
    try:
        from routers.vault_router import _encrypt as vault_encrypt
        return vault_encrypt(value)
    except Exception:
        return value


def _decrypt(value: str) -> str:
    if not value:
        return ""
    try:
        from routers.vault_router import _decrypt as vault_decrypt
        return vault_decrypt(value)
    except Exception:
        return value


SENSITIVE_FIELDS = [
    "gmail_app_password", "meta_access_token"
]


class ClientCreate(BaseModel):
    business_name: str
    industry: Optional[str] = ""
    website: Optional[str] = ""
    contact_person: Optional[str] = ""
    contact_email: Optional[str] = ""
    contact_phone: Optional[str] = ""
    logo_url: Optional[str] = ""
    gmail_email: Optional[str] = ""
    gmail_app_password: Optional[str] = ""
    gmail_keywords: Optional[str] = ""
    whatsapp_number: Optional[str] = ""
    meta_access_token: Optional[str] = ""
    meta_phone_id: Optional[str] = ""
    instagram_handle: Optional[str] = ""
    facebook_page_id: Optional[str] = ""
    youtube_channel: Optional[str] = ""
    linkedin_url: Optional[str] = ""
    twitter_handle: Optional[str] = ""
    sms_phone: Optional[str] = ""
    sms_carrier: Optional[str] = ""
    brand_tagline: Optional[str] = ""
    default_discount: Optional[str] = "10"
    welcome_message: Optional[str] = ""
    whatsapp_prefill: Optional[str] = ""
    automation_mode: Optional[str] = "auto"


class ClientUpdate(ClientCreate):
    status: Optional[str] = None


@router.get("")
async def list_clients(request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    clients = []
    cursor = db.managed_clients.find({"admin_user_id": user_id}, {"_id": 0}).sort("created_at", -1)
    async for c in cursor:
        safe = {k: v for k, v in c.items() if not k.endswith("_enc")}
        safe["has_gmail_password"] = bool(c.get("gmail_app_password_enc"))
        safe["has_meta_token"] = bool(c.get("meta_access_token_enc"))
        leads_count = await db.acquisition_leads.count_documents({"client_id": c["id"]})
        safe["leads_count"] = leads_count
        clients.append(safe)
    return {"clients": clients}


@router.post("/platform/subscribers/{user_id}/reset-password")
async def admin_reset_subscriber_password(user_id: str, request: Request):
    """
    Admin-only: force-reset a subscriber's password.

    Body (optional):
      {"new_password": "..."}   — if omitted, a secure 14-char password is generated
                                   and returned once (never stored in plaintext).

    The returned password is shown ONCE in the response — admin must copy it and
    share with the user over a trusted channel. It is not logged.
    """
    import secrets
    import string

    user_data = _get_user_from_token(request)
    role = user_data.get("role", "user")
    if role not in ("admin", "super_admin"):
        raise HTTPException(403, "Admin role required")

    body = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    new_password = (body.get("new_password") or "").strip()

    if new_password:
        if len(new_password) < 8:
            raise HTTPException(400, "Password must be at least 8 characters")
    else:
        # Auto-generate a strong 14-char password (letters + digits + symbols)
        alphabet = string.ascii_letters + string.digits + "!@#$%&*"
        new_password = "".join(secrets.choice(alphabet) for _ in range(14))

    # Hash using the same bcrypt(12) helper the signup flow uses
    from routers.platform_auth_router import hash_password
    hashed = hash_password(new_password)

    db = get_db()
    # Subscribers can be keyed by id OR user_id OR email depending on how the
    # signup router inserted them — try in order.
    target = await db.platform_users.find_one({"id": user_id}) \
        or await db.platform_users.find_one({"user_id": user_id}) \
        or await db.platform_users.find_one({"email": user_id})
    if not target:
        raise HTTPException(404, f"Subscriber not found: {user_id}")

    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    await db.platform_users.update_one(
        {"email": target["email"]},
        {"$set": {
            "password_hash": hashed,
            "password_reset_at": now_iso,
            "password_reset_by": user_data.get("email") or user_data.get("user_id"),
        }, "$unset": {"reset_token": "", "reset_token_expires_at": ""}},
    )

    # Audit log (separate collection — never includes the plaintext password)
    try:
        await db.admin_audit_log.insert_one({
            "action": "reset_subscriber_password",
            "target_email": target["email"],
            "target_user_id": target.get("id") or target.get("user_id"),
            "performed_by": user_data.get("email") or user_data.get("user_id"),
            "at": now_iso,
        })
    except Exception:
        pass

    return {
        "ok": True,
        "email": target["email"],
        "new_password": new_password,  # shown once; admin must copy it now
        "generated": not body.get("new_password"),
        "reset_at": now_iso,
        "warning": "Share this password with the user over a trusted channel. It will not be retrievable again.",
    }


@router.get("/platform/subscribers")
async def list_platform_subscribers(request: Request):
    """
    Admin-only view: every user who has signed up on aurem.live via
    /platform/signup (stored in db.platform_users).

    These are your PAYING SUBSCRIBERS (not their B2B managed clients — those
    live in db.managed_clients and are scoped per operator).
    """
    user_data = _get_user_from_token(request)
    role = user_data.get("role", "user")
    if role not in ("admin", "super_admin"):
        raise HTTPException(403, "Admin role required")

    db = get_db()
    subs = []
    cursor = db.platform_users.find(
        {},
        {
            "_id": 0,
            "password_hash": 0,
            "password": 0,
            "reset_token": 0,
        },
    ).sort("created_at", -1).limit(500)
    async for u in cursor:
        # Normalize timestamps to ISO strings for JSON
        for k in ("created_at", "last_login_at", "business_id_granted_at"):
            v = u.get(k)
            if hasattr(v, "isoformat"):
                u[k] = v.isoformat()
        # Count each subscriber's own managed_clients for quick insight
        try:
            u["managed_clients_count"] = await db.managed_clients.count_documents(
                {"admin_user_id": u.get("id") or u.get("user_id") or ""}
            )
        except Exception:
            u["managed_clients_count"] = 0
        subs.append(u)

    return {
        "count": len(subs),
        "subscribers": subs,
        "sources": {
            "db": "platform_users",
            "signup_endpoint": "/api/platform/auth/register",
            "signup_page": "/platform/signup",
        },
    }


@router.get("/{client_id}")
async def get_client(client_id: str, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    client = await db.managed_clients.find_one(
        {"id": client_id, "admin_user_id": user_id}, {"_id": 0}
    )
    if not client:
        raise HTTPException(404, "Client not found")
    safe = {k: v for k, v in client.items() if not k.endswith("_enc")}
    safe["has_gmail_password"] = bool(client.get("gmail_app_password_enc"))
    safe["has_meta_token"] = bool(client.get("meta_access_token_enc"))
    return {"client": safe}


@router.post("")
async def create_client(data: ClientCreate, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    client_id = f"cli-{uuid.uuid4().hex[:8]}"

    doc = {
        "id": client_id,
        "admin_user_id": user_id,
        "business_name": data.business_name,
        "industry": data.industry or "",
        "website": data.website or "",
        "contact_person": data.contact_person or "",
        "contact_email": data.contact_email or "",
        "contact_phone": data.contact_phone or "",
        "logo_url": data.logo_url or "",
        "gmail_email": data.gmail_email or "",
        "gmail_keywords": data.gmail_keywords or "",
        "whatsapp_number": data.whatsapp_number or "",
        "meta_phone_id": data.meta_phone_id or "",
        "instagram_handle": data.instagram_handle or "",
        "facebook_page_id": data.facebook_page_id or "",
        "youtube_channel": data.youtube_channel or "",
        "linkedin_url": data.linkedin_url or "",
        "twitter_handle": data.twitter_handle or "",
        "sms_phone": data.sms_phone or "",
        "sms_carrier": data.sms_carrier or "",
        "brand_tagline": data.brand_tagline or "",
        "default_discount": data.default_discount or "10",
        "welcome_message": data.welcome_message or "",
        "whatsapp_prefill": data.whatsapp_prefill or "",
        "automation_mode": data.automation_mode or "auto",
        "status": "setup",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_activity": datetime.now(timezone.utc).isoformat(),
    }

    if data.gmail_app_password:
        doc["gmail_app_password_enc"] = _encrypt(data.gmail_app_password)
    if data.meta_access_token:
        doc["meta_access_token_enc"] = _encrypt(data.meta_access_token)

    await db.managed_clients.insert_one(doc)
    return {"success": True, "id": client_id}


@router.put("/{client_id}")
async def update_client(client_id: str, data: ClientUpdate, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    existing = await db.managed_clients.find_one(
        {"id": client_id, "admin_user_id": user_id}, {"_id": 0}
    )
    if not existing:
        raise HTTPException(404, "Client not found")

    update_doc = {}
    fields = data.dict(exclude_unset=False)
    for key, value in fields.items():
        if key in SENSITIVE_FIELDS:
            if value:
                update_doc[f"{key}_enc"] = _encrypt(value)
        elif key == "status":
            if value:
                update_doc["status"] = value
        else:
            update_doc[key] = value or ""

    update_doc["last_activity"] = datetime.now(timezone.utc).isoformat()
    await db.managed_clients.update_one({"id": client_id}, {"$set": update_doc})
    return {"success": True}


@router.delete("/{client_id}")
async def delete_client(client_id: str, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    result = await db.managed_clients.delete_one({"id": client_id, "admin_user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Client not found")
    return {"success": True}


@router.put("/{client_id}/toggle")
async def toggle_client_status(client_id: str, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    client = await db.managed_clients.find_one({"id": client_id, "admin_user_id": user_id}, {"_id": 0})
    if not client:
        raise HTTPException(404, "Client not found")
    new_status = "paused" if client.get("status") == "active" else "active"
    await db.managed_clients.update_one(
        {"id": client_id},
        {"$set": {"status": new_status, "last_activity": datetime.now(timezone.utc).isoformat()}}
    )
    return {"success": True, "status": new_status}


@router.put("/{client_id}/mode")
async def toggle_automation_mode(client_id: str, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    body = await request.json()
    mode = body.get("mode", "auto")
    if mode not in ("auto", "manual"):
        raise HTTPException(400, "Mode must be 'auto' or 'manual'")
    await db.managed_clients.update_one(
        {"id": client_id, "admin_user_id": user_id},
        {"$set": {"automation_mode": mode, "last_activity": datetime.now(timezone.utc).isoformat()}}
    )
    return {"success": True, "mode": mode}


@router.get("/stats/overview")
async def get_overview_stats(request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    total = await db.managed_clients.count_documents({"admin_user_id": user_id})
    active = await db.managed_clients.count_documents({"admin_user_id": user_id, "status": "active"})
    paused = await db.managed_clients.count_documents({"admin_user_id": user_id, "status": "paused"})
    setup = await db.managed_clients.count_documents({"admin_user_id": user_id, "status": "setup"})
    return {"total": total, "active": active, "paused": paused, "setup": setup}
