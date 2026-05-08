"""
AUREM Settings Router
Handles profile updates, password changes, notification preferences,
and Shadow-Saving form buffer persistence.
"""
import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/settings", tags=["AUREM Settings"])
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
    """Extract user from JWT token"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = auth_header.split(" ", 1)[1]
    try:
        import jwt
        secret = os.environ.get("JWT_SECRET", "")
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(401, "Invalid token")


# ═══════════════════════════════════════════════════════════════
# PHONE SELF-CLEANING
# ═══════════════════════════════════════════════════════════════

def clean_phone(raw: str) -> str:
    """Strip dashes/spaces/parens, ensure +country code. Returns cleaned phone or original."""
    if not raw:
        return raw
    digits = re.sub(r"[^\d+]", "", raw)
    if not digits:
        return raw
    # If starts with +, keep as-is
    if digits.startswith("+"):
        return digits
    # North American: 10 digits → +1
    if len(digits) == 10:
        return f"+1{digits}"
    # 11 digits starting with 1 → +1
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    # Otherwise prefix +
    if not digits.startswith("+"):
        return f"+{digits}"
    return digits


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    timezone: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class NotificationPreferences(BaseModel):
    email_alerts: Optional[bool] = None
    push_notifications: Optional[bool] = None
    weekly_digest: Optional[bool] = None
    security_alerts: Optional[bool] = None
    marketing: Optional[bool] = None
    deal_updates: Optional[bool] = None
    agent_reports: Optional[bool] = None


@router.put("/profile")
async def update_profile(profile: ProfileUpdate, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    update_fields = {k: v for k, v in profile.dict().items() if v is not None}

    # Self-cleaning phone
    if "phone" in update_fields and update_fields["phone"]:
        update_fields["phone"] = clean_phone(update_fields["phone"])

    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = await db.users.update_one(
        {"id": user_id},
        {"$set": update_fields}
    )

    # Clear any buffer for this user on successful save
    await db.temp_buffer.delete_many({"user_id": user_id, "form": "profile"})

    return {"success": True, "modified": result.modified_count > 0, "cleaned_phone": update_fields.get("phone")}


@router.put("/password")
async def change_password(data: PasswordChange, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    email_from_token = user_data.get("email")
    db = get_db()

    # Look up by id first, then fall back to email — avoids 404s when the
    # JWT carries an email-style sub but the user row was created without
    # an `id` field.
    user = await db.users.find_one(
        {"$or": [{"id": user_id}, {"email": user_id}, {"email": email_from_token}]},
        {"_id": 0, "password": 1, "password_hash": 1, "email": 1, "id": 1},
    )
    if not user:
        raise HTTPException(404, "User not found")

    import bcrypt
    stored_pw = user.get("password") or user.get("password_hash") or ""
    if isinstance(stored_pw, str):
        stored_pw = stored_pw.encode("utf-8")
    if not stored_pw:
        raise HTTPException(400, "No password set on this account")

    if not bcrypt.checkpw(data.current_password.encode("utf-8"), stored_pw):
        raise HTTPException(400, "Current password is incorrect")

    # Strength gate — block known-weak passwords cold.
    new_pw = data.new_password
    weak = {"admin", "admin123", "password", "password123", "12345678", "qwerty", "letmein"}
    if (
        len(new_pw) < 8
        or new_pw.lower() in weak
        or new_pw.lower() == (user.get("email") or "").split("@")[0].lower()
    ):
        raise HTTPException(
            400,
            "Password too weak — must be ≥ 8 chars and not a common/obvious value",
        )

    new_hash = bcrypt.hashpw(new_pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    now_iso = datetime.now(timezone.utc).isoformat()
    email = user.get("email")

    # Sync ALL three auth collections so admin + customer + legacy logins
    # all accept the new password (no more drift).
    await db.users.update_one(
        {"_id": {"$exists": True}, "email": email} if email else {"id": user.get("id")},
        {"$set": {
            "password": new_hash,
            "password_hash": new_hash,
            "updated_at": now_iso,
        }},
    )
    if email:
        await db.platform_users.update_one(
            {"email": email},
            {"$set": {"password_hash": new_hash, "updated_at": now_iso}},
        )
        await db.aurem_users.update_one(
            {"email": email},
            {"$set": {"password_hash": new_hash, "updated_at": now_iso}},
        )

    return {"success": True}


@router.put("/notifications")
async def update_notifications(prefs: NotificationPreferences, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    update_fields = {f"notification_prefs.{k}": v for k, v in prefs.dict().items() if v is not None}
    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.users.update_one(
        {"id": user_id},
        {"$set": update_fields}
    )

    return {"success": True}


@router.get("/profile")
async def get_profile(request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(404, "User not found")

    return user


# ═══════════════════════════════════════════════════════════════
# SHADOW-SAVING: Zero-Data-Loss Form Buffer
# ═══════════════════════════════════════════════════════════════

@router.post("/buffer")
async def save_buffer(request: Request):
    """Shadow-save form data to temp_buffer collection.
    Called on every keystroke / form change for zero-data-loss.
    Body: {form: 'profile'|'security'|'api-keys', data: {...}}
    """
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()
    body = await request.json()
    form_name = body.get("form", "unknown")
    form_data = body.get("data", {})

    await db.temp_buffer.update_one(
        {"user_id": user_id, "form": form_name},
        {
            "$set": {
                "data": form_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "$setOnInsert": {
                "user_id": user_id,
                "form": form_name,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        upsert=True,
    )
    return {"buffered": True}


@router.get("/buffer/{form_name}")
async def get_buffer(form_name: str, request: Request):
    """Retrieve buffered form data for recovery."""
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    doc = await db.temp_buffer.find_one(
        {"user_id": user_id, "form": form_name}, {"_id": 0}
    )
    if not doc:
        return {"buffered": False, "data": None}
    return {"buffered": True, "data": doc.get("data"), "updated_at": doc.get("updated_at")}



# ══════════════════════════════════════════════
# Sidebar Order Persistence
# ══════════════════════════════════════════════

@router.get("/sidebar-order")
async def get_sidebar_order(request: Request):
    """Get saved sidebar order for the current user."""
    user = _get_user_from_token(request)
    user_id = user.get("email", user.get("user_id", ""))
    db = get_db()
    doc = await db.user_preferences.find_one(
        {"user_id": user_id, "preference": "sidebar_order"}, {"_id": 0}
    )
    if not doc:
        return {"order": None}
    return {"order": doc.get("order")}


@router.post("/sidebar-order")
async def save_sidebar_order(request: Request):
    """Save sidebar order for the current user."""
    user = _get_user_from_token(request)
    user_id = user.get("email", user.get("user_id", ""))
    body = await request.json()
    order = body.get("order", {})
    db = get_db()
    await db.user_preferences.update_one(
        {"user_id": user_id, "preference": "sidebar_order"},
        {"$set": {
            "user_id": user_id,
            "preference": "sidebar_order",
            "order": order,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"success": True}
