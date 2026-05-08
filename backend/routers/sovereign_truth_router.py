"""
iter 282al-26 — Sovereign Truth toggle endpoints (founder-only).

Endpoints:
  GET  /api/founder/sovereign-truth/state   — read current toggle state
  POST /api/founder/sovereign-truth/toggle  — set {on: bool}

Both require a valid JWT whose email (or mapped admin_users.email) is on
the founder allowlist. Non-founders get 403.
"""
from __future__ import annotations

import os
from typing import Optional

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from services.sovereign_truth import (
    get_founder_prefs, is_founder, set_founder_prefs,
)

router = APIRouter(tags=["Sovereign Truth"])
_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _decode_jwt(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing token")
    token = authorization.split(" ", 1)[1].strip()
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        raise HTTPException(500, "jwt secret unset")
    try:
        return jwt.decode(
            token, secret, algorithms=["HS256"],
            options={"verify_exp": False},
        )
    except Exception:
        raise HTTPException(401, "invalid token")


async def _require_founder(authorization: Optional[str]) -> dict:
    payload = _decode_jwt(authorization)
    uid = payload.get("user_id") or payload.get("email")
    email = payload.get("email") or (
        uid if isinstance(uid, str) and "@" in uid else None
    )
    # iter 282al-32 — Some auth paths (phone login, biometric, OAuth refresh)
    # mint JWTs with only `user_id` and no `email`. Resolve the email from
    # the users collection so founder detection still works.
    if not email and uid and _db is not None:
        try:
            u = await _db.users.find_one({"id": uid}, {"_id": 0, "email": 1})
            if u and u.get("email"):
                email = u["email"]
        except Exception:
            pass
    ok = await is_founder(uid, email, _db)
    if not ok:
        raise HTTPException(403, "founder only")
    payload["_founder_key"] = (email or uid or "").lower()
    return payload


@router.get("/api/founder/sovereign-truth/state")
async def read_state(authorization: Optional[str] = Header(None)) -> dict:
    payload = await _require_founder(authorization)
    prefs = await get_founder_prefs(_db, payload["_founder_key"])
    return {
        "ok": True,
        "sovereign_truth": bool(prefs.get("sovereign_truth")),
        "founder": payload["_founder_key"],
    }


class ToggleBody(BaseModel):
    on: bool


@router.post("/api/founder/sovereign-truth/toggle")
async def toggle(
    body: ToggleBody,
    authorization: Optional[str] = Header(None),
) -> dict:
    payload = await _require_founder(authorization)
    res = await set_founder_prefs(
        _db, payload["_founder_key"], sovereign_truth=bool(body.on),
    )
    return {
        "ok": res.get("ok", False),
        "sovereign_truth": bool(body.on),
        "founder": payload["_founder_key"],
    }
