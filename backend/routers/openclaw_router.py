"""
OpenClaw Features Router — Persona, Tool Permissions, Heartbeat, Cost, White-Label
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Header, Body
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/openclaw", tags=["OpenClaw Features"])

_db = None


def set_db(database):
    global _db
    _db = database
    for mod_path, set_fn in [
        ("services.tenant_persona", "set_db"),
        ("services.tool_permissions", "set_db"),
        ("services.tenant_heartbeat", "set_db"),
        ("services.tenant_cost_tracker", "set_db"),
        ("services.white_label", "set_db"),
    ]:
        try:
            mod = __import__(mod_path, fromlist=[set_fn])
            getattr(mod, set_fn)(database)
        except Exception as e:
            logger.warning(f"[OPENCLAW] {mod_path} set_db: {e}")


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
            if user and (user.get("is_admin") or user.get("is_super_admin") or user.get("role") == "admin"):
                return user
        # Fallback: check role in JWT payload
        role = payload.get("role", "")
        if role == "admin":
            return {"id": user_id or email, "email": email, "role": "admin", "is_admin": True}
    except Exception:
        pass
    raise HTTPException(status_code=403, detail="Admin access required")


# ═══════════════════════════════════════
# 1. TENANT PERSONA (SOUL.md)
# ═══════════════════════════════════════

@router.get("/persona/{tenant_id}")
async def get_persona(tenant_id: str, admin=Depends(_get_admin)):
    from services.tenant_persona import get_persona
    return {"status": "ok", "persona": await get_persona(tenant_id)}


@router.put("/persona/{tenant_id}")
async def update_persona(tenant_id: str, body: dict = Body(...), admin=Depends(_get_admin)):
    from services.tenant_persona import set_persona
    result = await set_persona(tenant_id, body)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "ok", "persona": result}


@router.get("/personas")
async def list_personas(admin=Depends(_get_admin)):
    from services.tenant_persona import list_personas
    personas = await list_personas()
    return {"status": "ok", "personas": personas, "count": len(personas)}


@router.get("/persona/{tenant_id}/prompt")
async def get_persona_prompt(tenant_id: str, admin=Depends(_get_admin)):
    from services.tenant_persona import get_persona, build_system_prompt
    persona = await get_persona(tenant_id)
    prompt = build_system_prompt(persona)
    return {"status": "ok", "prompt": prompt, "persona": persona}


# ═══════════════════════════════════════
# 2. TOOL PERMISSIONS
# ═══════════════════════════════════════

@router.get("/permissions/{tenant_id}")
async def get_permissions(tenant_id: str, admin=Depends(_get_admin)):
    from services.tool_permissions import get_tenant_tier, get_tier_tools
    tier = await get_tenant_tier(tenant_id)
    tools = get_tier_tools(tier)
    return {"status": "ok", **tools}


@router.get("/permissions/{tenant_id}/check/{tool_name}")
async def check_permission(tenant_id: str, tool_name: str, admin=Depends(_get_admin)):
    from services.tool_permissions import check_permission
    result = await check_permission(tenant_id, tool_name)
    return {"status": "ok", **result}


@router.put("/permissions/{tenant_id}/tier")
async def update_tier(tenant_id: str, body: dict = Body(...), admin=Depends(_get_admin)):
    from services.tool_permissions import set_tenant_tier
    tier = body.get("tier")
    if not tier:
        raise HTTPException(status_code=400, detail="'tier' required")
    result = await set_tenant_tier(tenant_id, tier)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "ok", **result}


@router.get("/tiers")
async def list_tiers(admin=Depends(_get_admin)):
    from services.tool_permissions import get_tier_tools, TIER_TOOLS
    tiers = {}
    for tier_name in TIER_TOOLS:
        tiers[tier_name] = get_tier_tools(tier_name)
    return {"status": "ok", "tiers": tiers}


# ═══════════════════════════════════════
# 3. TENANT HEARTBEAT
# ═══════════════════════════════════════

@router.get("/heartbeat/{tenant_id}")
async def tenant_heartbeat(tenant_id: str, admin=Depends(_get_admin)):
    from services.tenant_heartbeat import run_tenant_heartbeat
    health = await run_tenant_heartbeat(tenant_id)
    return {"status": "ok", **health}


@router.post("/heartbeat/all")
async def all_heartbeats(admin=Depends(_get_admin)):
    from services.tenant_heartbeat import run_all_heartbeats
    result = await run_all_heartbeats()
    return {"status": "ok", **result}


@router.get("/health/all")
async def all_health(admin=Depends(_get_admin)):
    from services.tenant_heartbeat import get_all_health
    health = await get_all_health()
    return {"status": "ok", "tenants": health, "count": len(health)}


# ═══════════════════════════════════════
# 4. COST TRACKING
# ═══════════════════════════════════════

@router.get("/cost/{tenant_id}")
async def get_cost(tenant_id: str, month: Optional[str] = None, admin=Depends(_get_admin)):
    from services.tenant_cost_tracker import get_tenant_cost
    cost = await get_tenant_cost(tenant_id, month)
    return {"status": "ok", **cost}


@router.get("/costs")
async def all_costs(month: Optional[str] = None, admin=Depends(_get_admin)):
    from services.tenant_cost_tracker import get_all_costs
    costs = await get_all_costs(month)
    total_savings = sum(c.get("savings_usd", 0) for c in costs)
    return {"status": "ok", "costs": costs, "count": len(costs), "total_savings_usd": round(total_savings, 2)}


@router.get("/cost/{tenant_id}/report")
async def cost_report(tenant_id: str, month: Optional[str] = None, admin=Depends(_get_admin)):
    from services.tenant_cost_tracker import generate_monthly_report
    report = await generate_monthly_report(tenant_id, month)
    return {"status": "ok", **report}


# ═══════════════════════════════════════
# 5. WHITE-LABEL
# ═══════════════════════════════════════

@router.get("/branding/{tenant_id}")
async def get_branding(tenant_id: str, admin=Depends(_get_admin)):
    from services.white_label import get_branding
    config = await get_branding(tenant_id)
    return {"status": "ok", **config}


@router.put("/branding/{tenant_id}")
async def update_branding(tenant_id: str, body: dict = Body(...), admin=Depends(_get_admin)):
    from services.white_label import set_branding
    result = await set_branding(tenant_id, body)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "ok", **result}


@router.get("/branding/{tenant_id}/cname")
async def cname_instructions(tenant_id: str, admin=Depends(_get_admin)):
    from services.white_label import get_cname_instructions
    return {"status": "ok", **(await get_cname_instructions(tenant_id))}
