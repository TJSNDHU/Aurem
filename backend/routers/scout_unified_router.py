"""
Unified Scout Router — merges Deep Scout (surface) and Dark Scout (OSINT)
into one API for the ORA Command Console ScoutDrawer.

Does NOT replace existing /api/deep-scout and /api/admin/dark-scout routes
(they stay alive for rollback safety). Console calls /api/scout/unified only.
"""

import logging
import os
from typing import Any, Dict

import jwt
from fastapi import APIRouter, Body, Depends, Header, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scout", tags=["ORA Scout (unified)"])

_db = None


def set_db(database):
    global _db
    _db = database


async def _get_admin(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        secret = os.environ.get("JWT_SECRET", "")
        payload = jwt.decode(authorization[7:], secret, algorithms=["HS256"])
        user_id = payload.get("user_id", "")
        email = payload.get("email", "")
        if _db is not None:
            user = None
            if user_id:
                user = await _db.users.find_one({"id": user_id}, {"_id": 0})
            if not user and email:
                user = await _db.users.find_one({"email": email}, {"_id": 0})
            if user and (user.get("is_admin") or user.get("role") == "admin"):
                return user
        if payload.get("role") == "admin":
            return {"id": user_id or email, "email": email, "role": "admin"}
    except Exception:
        pass
    raise HTTPException(403, "Admin access required")


@router.post("/unified")
async def unified_scout(body: Dict[str, Any] = Body(...), admin=Depends(_get_admin)):
    """Run a surface / OSINT / both research pass in one call."""
    query: str = (body.get("query") or "").strip()
    if not query:
        raise HTTPException(400, "'query' field required")

    depth: str = (body.get("depth") or "surface").lower()
    if depth not in {"surface", "osint", "both"}:
        raise HTTPException(400, "'depth' must be surface, osint, or both")

    max_results = int(body.get("max_results") or 15)
    max_steps = int(body.get("max_steps") or 3)

    result: Dict[str, Any] = {"query": query, "depth": depth}

    if depth in {"surface", "both"}:
        try:
            from services.deep_scout import deep_scout_search
            surface = await deep_scout_search("aurem_platform", query, max_steps)
            result["surface"] = surface or {}
        except Exception as e:
            logger.warning(f"[scout] surface failed: {e}")
            result["surface_error"] = str(e)[:200]

    if depth in {"osint", "both"}:
        try:
            from services.dark_scout_service import run_investigation
            osint = await run_investigation(
                query=query,
                tenant_id="polaris-built-001",
                preset="brand_monitor",
                max_results=max_results,
            )
            result["osint"] = {
                "investigation_id": osint.get("investigation_id"),
                "risk_level": osint.get("risk_level"),
                "search_results": osint.get("search_results"),
                "filtered_results": osint.get("filtered_results"),
                "analysis_preview": (osint.get("analysis") or "")[:1500],
            }
        except Exception as e:
            logger.warning(f"[scout] osint failed: {e}")
            result["osint_error"] = str(e)[:200]

    return {"status": "ok", **result}
