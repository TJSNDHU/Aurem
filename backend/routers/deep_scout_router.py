"""
Deep Scout Router — API endpoints for multi-step iterative search
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Header, Body
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/deep-scout", tags=["Deep Scout"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.deep_scout import set_db as set_ds_db
    set_ds_db(database)


async def _get_admin(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    import jwt
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
        role = payload.get("role", "")
        if role == "admin":
            return {"id": user_id or email, "email": email, "role": "admin", "is_admin": True}
    except Exception:
        pass
    raise HTTPException(status_code=403, detail="Admin access required")


@router.post("/search")
async def deep_search_api(body: dict = Body(...), admin=Depends(_get_admin)):
    query = body.get("query", "")
    tenant_id = body.get("tenant_id", "aurem_platform")
    max_steps = body.get("max_steps", 3)
    if not query:
        raise HTTPException(status_code=400, detail="'query' field required")
    from services.deep_scout import deep_scout_search
    result = await deep_scout_search(tenant_id, query, max_steps)
    return {"status": "ok", **result}


@router.get("/stats")
async def deep_scout_stats_api(tenant_id: Optional[str] = None, admin=Depends(_get_admin)):
    from services.deep_scout import get_deep_scout_stats
    stats = await get_deep_scout_stats(tenant_id)
    return {"status": "ok", **stats}
