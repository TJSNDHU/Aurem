"""
AUREM Ghost Mode + GEO Router — Phase G
==========================================
API endpoints for:
- Ghost Mode toggle and configuration
- Morning Brief retrieval
- Manual ghost cycle trigger
- GEO Score calculation (instant)
- Live AI Check (on-demand)
- GEO History
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional
import jwt

from services.ghost_worker import (
    get_ghost_config, toggle_ghost_mode, run_ghost_cycle,
    get_morning_brief, get_ghost_history,
)
from services.geo_engine import (
    calculate_geo_score, live_ai_check, get_geo_history,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Ghost Mode + GEO"])

from config import JWT_SECRET

_db = None

def set_db(db):
    global _db
    _db = db
    from services.ghost_worker import set_db as set_ghost_db
    from services.geo_engine import set_db as set_geo_db
    set_ghost_db(db)
    set_geo_db(db)

async def _get_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        return jwt.decode(auth.split(" ")[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


# ═══════════════════════════════════════════════════════════════
# GHOST MODE
# ═══════════════════════════════════════════════════════════════

@router.get("/api/ghost/config")
async def get_config(request: Request):
    """Get Ghost Mode configuration for current tenant."""
    user = await _get_user(request)
    tenant_id = user.get("tenant_id", user.get("user_id"))
    config = await get_ghost_config(tenant_id)
    return config


class GhostToggleRequest(BaseModel):
    enabled: bool
    auto_reminders: Optional[bool] = None
    auto_seo: Optional[bool] = None
    auto_recovery: Optional[bool] = None
    auto_inventory_alerts: Optional[bool] = None
    floor_discount_pct: Optional[float] = None
    morning_brief_enabled: Optional[bool] = None

@router.post("/api/ghost/toggle")
async def toggle(body: GhostToggleRequest, request: Request):
    """Toggle Ghost Mode on/off with optional config."""
    user = await _get_user(request)
    tenant_id = user.get("tenant_id", user.get("user_id"))
    options = {}
    if body.auto_reminders is not None:
        options["ghost_auto_reminders"] = body.auto_reminders
    if body.auto_seo is not None:
        options["ghost_auto_seo"] = body.auto_seo
    if body.auto_recovery is not None:
        options["ghost_auto_recovery"] = body.auto_recovery
    if body.auto_inventory_alerts is not None:
        options["ghost_auto_inventory"] = body.auto_inventory_alerts
    if body.floor_discount_pct is not None:
        options["ghost_floor_discount"] = body.floor_discount_pct
    if body.morning_brief_enabled is not None:
        options["ghost_morning_brief"] = body.morning_brief_enabled

    result = await toggle_ghost_mode(tenant_id, body.enabled, options if options else None)
    return {"success": True, **result}


@router.post("/api/ghost/run-cycle")
async def trigger_cycle(request: Request):
    """Manually trigger a Ghost Mode cycle (for testing/demo)."""
    user = await _get_user(request)
    tenant_id = user.get("tenant_id", user.get("user_id"))
    brief = await run_ghost_cycle(tenant_id)
    return brief


@router.get("/api/ghost/morning-brief")
async def morning_brief(request: Request):
    """Get the Morning Brief for the current tenant."""
    user = await _get_user(request)
    tenant_id = user.get("tenant_id", user.get("user_id"))
    brief = await get_morning_brief(tenant_id)
    if not brief:
        return {"available": False, "message": "No brief available. Enable Ghost Mode and run a cycle first."}
    return {"available": True, "brief": brief}


@router.get("/api/ghost/history")
async def ghost_history(request: Request, limit: int = 20):
    """Get Ghost Mode action history."""
    user = await _get_user(request)
    tenant_id = user.get("tenant_id", user.get("user_id"))
    history = await get_ghost_history(tenant_id, limit)
    return {"history": history, "total": len(history)}


# ═══════════════════════════════════════════════════════════════
# GEO (Generative Engine Optimization)
# ═══════════════════════════════════════════════════════════════

@router.get("/api/geo/score")
async def geo_score(request: Request):
    """Calculate the GEO Index (instant, no LLM call)."""
    user = await _get_user(request)
    tenant_id = user.get("tenant_id", user.get("user_id"))
    return await calculate_geo_score(tenant_id)


class LiveAICheckRequest(BaseModel):
    query: Optional[str] = None
    brand_name: Optional[str] = None

@router.post("/api/geo/live-check")
async def geo_live_check(body: LiveAICheckRequest, request: Request):
    """Live AI Check — Query GPT-4o to verify brand visibility."""
    user = await _get_user(request)
    tenant_id = user.get("tenant_id", user.get("user_id"))
    result = await live_ai_check(tenant_id, body.query, body.brand_name)
    return result


@router.get("/api/geo/history")
async def geo_check_history(request: Request, limit: int = 10):
    """Get history of Live AI Checks."""
    user = await _get_user(request)
    tenant_id = user.get("tenant_id", user.get("user_id"))
    checks = await get_geo_history(tenant_id, limit)
    return {"checks": checks, "total": len(checks)}


print("[STARTUP] Ghost Mode + GEO Router loaded (Phase G)", flush=True)
