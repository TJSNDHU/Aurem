"""
AUREM Privacy Mode Router — Phase 3 Sovereign Privacy
======================================================
$49/mo add-on that routes ALL LLM calls to the Canadian Sovereign Node
(sovereign.aurem.live / llama3.1). No data leaves Canadian soil.

Endpoints:
  GET   /api/customer/privacy      — my current privacy settings
  PATCH /api/customer/privacy      — toggle sovereign mode

Other services check via helper: `await is_sovereign_enabled(db, email)`.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
import jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/customer/privacy", tags=["Privacy / Sovereign"])
_db = None


def set_db(database):
    global _db
    _db = database


def _decode_jwt(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    secret = os.environ.get("JWT_SECRET")
    try:
        return jwt.decode(auth[7:], secret, algorithms=["HS256"])
    except Exception as e:
        raise HTTPException(401, f"invalid token: {e}")


async def _require_user(request: Request) -> dict:
    payload = _decode_jwt(request)
    email = (payload.get("email") or payload.get("sub") or "").lower()
    if not email:
        raise HTTPException(401, "no email in token")
    return {"email": email}


class PrivacyUpdate(BaseModel):
    sovereign_mode: Optional[bool] = None
    analytics_opt_in: Optional[bool] = None


async def is_sovereign_enabled(db, email: str) -> bool:
    """Exported helper — other services can check before LLM call."""
    if db is None or not email:
        return False
    doc = await db.customer_privacy.find_one({"email": email.lower()}, {"_id": 0})
    if not doc or not doc.get("sovereign_mode"):
        return False
    sub = await db.customer_subscriptions.find_one(
        {"email": email.lower(), "service_id": "sovereign_privacy", "status": "active"},
        {"_id": 0},
    )
    return bool(sub)


@router.get("")
async def get_privacy(user: dict = Depends(_require_user)):
    doc = await _db.customer_privacy.find_one({"email": user["email"]}, {"_id": 0})
    sub = await _db.customer_subscriptions.find_one(
        {"email": user["email"], "service_id": "sovereign_privacy", "status": "active"},
        {"_id": 0},
    )
    return {
        "sovereign_mode": bool(doc and doc.get("sovereign_mode")),
        "analytics_opt_in": bool(doc and doc.get("analytics_opt_in", True)),
        "sovereign_available": bool(sub),
        "sovereign_endpoint": os.environ.get("SOVEREIGN_NODE_URL", ""),
    }


@router.patch("")
async def update_privacy(body: PrivacyUpdate, user: dict = Depends(_require_user)):
    update = {"email": user["email"], "updated_at": datetime.now(timezone.utc).isoformat()}
    if body.sovereign_mode is not None:
        if body.sovereign_mode:
            sub = await _db.customer_subscriptions.find_one(
                {"email": user["email"], "service_id": "sovereign_privacy", "status": "active"},
                {"_id": 0},
            )
            if not sub:
                raise HTTPException(402, "Sovereign Privacy add-on required — subscribe at /my/website")
        update["sovereign_mode"] = body.sovereign_mode
    if body.analytics_opt_in is not None:
        update["analytics_opt_in"] = body.analytics_opt_in

    await _db.customer_privacy.update_one(
        {"email": user["email"]}, {"$set": update}, upsert=True,
    )
    return {"ok": True, **update}
