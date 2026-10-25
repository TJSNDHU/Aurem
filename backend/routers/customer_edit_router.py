"""
Customer Edit Portal — router (iter 311)
=========================================
POST /api/edit/request-access  body: {business_email, site_slug}
GET  /api/edit/verify?token=
POST /api/edit/save             body: {token, changes}
POST /api/edit/upload-image     multipart: token, kind=hero|logo, file
GET  /api/edit/site/{slug}      preview/public site fetch (no auth)
"""
from __future__ import annotations

import base64
import logging
import os
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Header, Query, UploadFile, File, Form
from pydantic import BaseModel
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/edit", tags=["Customer Edit Portal"])

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db is None:
        try:
            import server
            _db = getattr(server, "db", None)
        except Exception:
            pass
    return _db


# ── Models ────────────────────────────────────────────────────────────────
class RequestAccessBody(BaseModel):
    business_email: str
    site_slug: str


class SaveBody(BaseModel):
    token: str
    changes: Dict[str, Any]


# ── Endpoints ─────────────────────────────────────────────────────────────
@router.post("/request-access")
async def request_access(body: RequestAccessBody):
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.customer_edit import request_access as svc
    return await svc(db, body.business_email, body.site_slug)


@router.get("/verify")
async def verify(token: str = Query(...)):
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.customer_edit import verify_token
    out = await verify_token(db, token)
    if not out:
        raise HTTPException(401, "invalid or expired token")
    return out


@router.post("/nps")
async def submit_nps(body: Dict[str, Any]):
    """2-tap customer NPS — body: {token, score}"""
    db = _get_db()
    if db is None:
        raise HTTPException(503,"db unavailable")
    token = (body or {}).get("token", "")
    try:
        score = int((body or {}).get("score", 0))
    except Exception:
        raise HTTPException(400,"score must be int 1..5")
    if not token:
        raise HTTPException(400,"token required")
    if not (1 <= score <= 5):
        raise HTTPException(400,"score must be 1..5")
    from services.nps_service import submit_nps as svc
    out = await svc(db,
                      source=(body.get("source") or "edit_portal"))
                      )
                      )
                      )
                      )
                      )
                      )
                      )
                      )
                      )
                      )
                      )
                      )
                      )
                      )
                      )