"""
routers/aurem_rules_router.py — iter D-79.

User-facing CRUD for `.aurem-rules.md` (per-customer CTO agent rules).

  GET    /api/cto/rules           — read your own rules
  PUT    /api/cto/rules           — replace your own rules (body: {rules_md})
  DELETE /api/cto/rules           — wipe your own rules

Auth: any logged-in user can manage THEIR OWN rules. The user_id is
read from the JWT — no cross-account writes possible.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from services import aurem_rules

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cto", tags=["CTO Rules"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database
    aurem_rules.set_db(database)


async def _require_user(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="bearer_token_required")
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="jwt_secret_unset")
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1], secret, algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token_expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid_token")
    uid = payload.get("user_id") or payload.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="no_user_id_in_token")
    return {
        "user_id": uid,
        "email": payload.get("email") or "",
    }


class RulesIn(BaseModel):
    rules_md: str = Field(default="", max_length=128 * 1024)


@router.get("/rules")
async def read_rules(authorization: Optional[str] = Header(None)) -> dict:
    user = await _require_user(authorization)
    env = await aurem_rules.get_rules(user["user_id"])
    return {"ok": True, **env}


@router.put("/rules")
async def write_rules(
    body: RulesIn,
    authorization: Optional[str] = Header(None),
) -> dict:
    user = await _require_user(authorization)
    saved = await aurem_rules.set_rules(
        user["user_id"], body.rules_md,
        updated_by=user["email"] or user["user_id"],
    )
    return {"ok": True, **saved}


@router.delete("/rules")
async def delete_rules(authorization: Optional[str] = Header(None)) -> dict:
    user = await _require_user(authorization)
    removed = await aurem_rules.clear_rules(user["user_id"])
    return {"ok": True, "removed": removed}
