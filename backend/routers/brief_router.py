"""
Brief Router — Morning Brief API Endpoints
/api/brief/* — today, history, generate, settings, preview
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Header, Body

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/brief", tags=["Morning Brief"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.morning_brief import set_db as set_mb_db
    set_mb_db(database)


async def _get_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    import jwt
    try:
        secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
        payload = jwt.decode(authorization[7:], secret, algorithms=["HS256"])
        user_id = payload.get("user_id", "")
        email = payload.get("email", "")
        if _db is not None:
            # Try user_id first, then email
            user = None
            if user_id:
                user = await _db.users.find_one({"id": user_id}, {"_id": 0})
            if not user and email:
                user = await _db.users.find_one({"email": email}, {"_id": 0})
            if user:
                return user
        # Return payload as fallback user if DB lookup fails
        return {"id": user_id or email, "email": email, "role": payload.get("role", "admin"), "tenant_id": "polaris-built-001"}
    except Exception:
        pass
    raise HTTPException(status_code=401, detail="Invalid token")


def _tenant_id(user):
    """Get tenant_id from user — admin sees all."""
    is_admin = user.get("is_admin") or user.get("is_super_admin") or user.get("role") == "admin"
    return None if is_admin else user.get("tenant_id", user.get("id"))


# ═══════════════════════════════════════
# TODAY'S BRIEF
# ═══════════════════════════════════════

@router.get("/today")
async def get_today(user=Depends(_get_user)):
    """Get today's morning brief. Generates one if not yet created."""
    from services.morning_brief import get_today_brief, run_morning_brief
    tid = _tenant_id(user)
    brief = await get_today_brief(tid)
    if not brief:
        brief = await run_morning_brief(tid)
    return brief


# ═══════════════════════════════════════
# HISTORY
# ═══════════════════════════════════════

@router.get("/history")
async def get_history(limit: int = 30, user=Depends(_get_user)):
    """Get last N morning briefs."""
    from services.morning_brief import get_brief_history
    briefs = await get_brief_history(_tenant_id(user), limit)
    return {"briefs": briefs, "total": len(briefs)}


# ═══════════════════════════════════════
# GENERATE ON DEMAND
# ═══════════════════════════════════════

@router.post("/generate")
async def generate_now(user=Depends(_get_user)):
    """Generate a morning brief right now (on-demand)."""
    from services.morning_brief import run_morning_brief
    tid = _tenant_id(user)
    brief = await run_morning_brief(tid)
    return brief


# ═══════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════

@router.get("/settings")
async def get_settings(user=Depends(_get_user)):
    """Get brief delivery settings."""
    from services.morning_brief import get_brief_settings
    tid = _tenant_id(user)
    return await get_brief_settings(tid or "default")


@router.put("/settings")
async def update_settings(body: dict = Body(...), user=Depends(_get_user)):
    """Update brief delivery settings."""
    from services.morning_brief import update_brief_settings
    tid = _tenant_id(user) or "default"
    return await update_brief_settings(tid, body)


# ═══════════════════════════════════════
# PREVIEW
# ═══════════════════════════════════════

@router.get("/preview")
async def preview_brief(user=Depends(_get_user)):
    """Generate a preview brief with current data (not saved)."""
    from services.morning_brief import scan_overnight, auto_act, generate_brief
    tid = _tenant_id(user)
    scan = await scan_overnight(tid)
    auto_actions = await auto_act(scan, tid)
    brief = await generate_brief(scan, auto_actions, tid)
    # Delete from DB (preview only)
    if _db is not None:
        await _db.morning_briefs.delete_one({"brief_id": brief.get("brief_id")})
    return brief
