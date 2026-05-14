"""
Google OAuth Router — Emergent-managed Google Auth
===================================================
Uses Emergent Auth service for Google OAuth social login.
"""

import os
import uuid
import logging
import httpx
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth/google", tags=["Google OAuth"])

AUTH_SERVICE_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

_db = None


def set_db(database):
    global _db
    _db = database


class GoogleSessionRequest(BaseModel):
    session_id: str


@router.post("/callback")
async def google_auth_callback(body: GoogleSessionRequest, response: Response):
    """
    Exchange Emergent Google Auth session_id for user data + JWT.
    Frontend sends the session_id from URL fragment after Google redirect.
    """
    if _db is None:
        raise HTTPException(500, "Database not available")

    # Call Emergent Auth service to get user data
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                AUTH_SERVICE_URL,
                headers={"X-Session-ID": body.session_id}
            )

        if resp.status_code != 200:
            logger.error(f"[Google OAuth] Emergent auth error: {resp.status_code} {resp.text}")
            raise HTTPException(401, "Invalid Google session")

        google_data = resp.json()

    except httpx.HTTPError as e:
        logger.error(f"[Google OAuth] HTTP error: {e}")
        raise HTTPException(502, "Authentication service unavailable")

    email = google_data.get("email", "").lower().strip()
    name = google_data.get("name", "")
    picture = google_data.get("picture", "")

    if not email:
        raise HTTPException(400, "No email returned from Google")

    # Check if user exists
    existing_user = await _db.users.find_one({"email": email}, {"_id": 0})

    if existing_user:
        # Update existing user with Google data
        user_id = existing_user.get("id", existing_user.get("user_id", ""))
        await _db.users.update_one(
            {"email": email},
            {"$set": {
                "google_picture": picture,
                "google_name": name,
                "last_google_login": datetime.now(timezone.utc).isoformat(),
                "auth_provider": existing_user.get("auth_provider", "email"),
            }}
        )
        is_admin = existing_user.get("is_admin", False)
    else:
        # Create new user from Google data
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        name_parts = name.split(" ", 1)
        first_name = name_parts[0] if name_parts else name
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        await _db.users.insert_one({
            "id": user_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "google_picture": picture,
            "google_name": name,
            "auth_provider": "google",
            "email_verified": True,
            "is_admin": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        is_admin = False

    # Generate JWT token
    import jwt
    jwt_secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
    token_payload = {
        "user_id": user_id,
        "email": email,
        "is_admin": is_admin,
        "tenant_id": user_id,
        "exp": (datetime.now(timezone.utc) + timedelta(days=7)).timestamp(),
    }
    token = jwt.encode(token_payload, jwt_secret, algorithm="HS256")

    logger.info(f"[Google OAuth] User authenticated: {email} (id: {user_id})")

    return {
        "token": token,
        "user": {
            "id": user_id,
            "email": email,
            "first_name": existing_user.get("first_name", name.split(" ")[0]) if existing_user else name.split(" ")[0],
            "last_name": existing_user.get("last_name", "") if existing_user else (name.split(" ", 1)[1] if " " in name else ""),
            "is_admin": is_admin,
            "picture": picture,
        }
    }
