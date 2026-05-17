"""
db_audit_router.py — Admin REST surface for the 5-layer DB hygiene scan.

Endpoints:
  GET  /api/admin/db-audit/scan       — run full scan, return JSON
  GET  /api/admin/db-audit/scan/text  — same, return ORA-formatted text + proofs

Used by:
  • /admin/audit-live frontend widget
  • /admin/db-drift cron (future)
  • Direct curl by founder during incident response

Admin-only via _require_admin_claims (matches customer_audit_router pattern).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import jwt
from fastapi import APIRouter, Header, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/db-audit", tags=["Admin · DB Audit"])

_db = None
_jwt_secret = os.environ.get("JWT_SECRET") or ""
_jwt_algo = "HS256"


def set_db(db) -> None:
    global _db
    _db = db


async def _require_admin(authorization: Optional[str]) -> dict:
    if _db is None:
        raise HTTPException(503, "DB not initialised")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1].strip(),
            _jwt_secret, algorithms=[_jwt_algo],
        )
    except Exception:
        raise HTTPException(401, "Invalid token")
    email = (payload.get("email") or payload.get("sub") or "").lower()
    user = await _db.users.find_one(
        {"email": email},
        {"_id": 0, "is_admin": 1, "is_super_admin": 1, "role": 1},
    )
    if not user or not (user.get("is_admin") or user.get("is_super_admin")
                          or user.get("role") in ("admin", "super_admin")):
        raise HTTPException(403, "Admin access required")
    return {"email": email}


@router.get("/scan")
async def scan_json(
    full_grep: bool = False,
    max_empties: int = 30,
    authorization: Optional[str] = Header(None),
):
    """Return the full structured scan as JSON. Set `full_grep=true` for
    nightly cron runs (slower, classifies every empty collection)."""
    await _require_admin(authorization)
    from services.db_audit_scanner import scan_db_audit, gather_proofs
    scan = await scan_db_audit(_db, max_empties=max_empties, full_grep=full_grep)
    proofs = await gather_proofs(_db)
    return {"scan": scan, "proofs": proofs}


@router.get("/scan/text", response_class=None)
async def scan_text(authorization: Optional[str] = Header(None)):
    """Return the ORA-formatted text block (for piping straight into chat
    or copy-pasting into incident reports). Includes the mandatory
    3-proof footer."""
    from fastapi.responses import PlainTextResponse
    await _require_admin(authorization)
    from services.db_audit_scanner import (
        scan_db_audit, gather_proofs, format_for_ora,
    )
    scan = await scan_db_audit(_db, max_empties=30, full_grep=False)
    proofs = await gather_proofs(_db)
    return PlainTextResponse(format_for_ora(scan, proofs))
