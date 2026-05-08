"""
Memory Tiers Router — Three-Tier Memory + Plan Persistence + ASK_USER Switch
Exposes memory stats, episodic queries, execution plans, and the ASK_USER master toggle.
"""

import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Header, Body
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["Memory"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.memory_tiers import set_db as set_mt_db
    set_mt_db(database)


async def _get_admin(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    import jwt
    try:
        secret = os.environ.get("JWT_SECRET", "")
        payload = jwt.decode(authorization[7:], secret, algorithms=["HS256"])
        user_id = payload.get("user_id")
        if _db is not None and user_id:
            user = await _db.users.find_one({"id": user_id}, {"_id": 0})
            if user and (user.get("is_admin") or user.get("is_super_admin") or user.get("role") == "admin"):
                return user
    except Exception:
        pass
    raise HTTPException(status_code=403, detail="Admin access required")


# ═══════════════════════════════════════
# MEMORY STATS
# ═══════════════════════════════════════

@router.get("/stats")
async def get_memory_stats(tenant_id: Optional[str] = None, admin=Depends(_get_admin)):
    from services.memory_tiers import get_memory_stats
    stats = await get_memory_stats(tenant_id)
    return {"status": "ok", **stats}


@router.get("/episodes")
async def get_episodes(
    tenant_id: Optional[str] = None,
    action_type: Optional[str] = None,
    outcome: Optional[str] = None,
    limit: int = 20,
    admin=Depends(_get_admin),
):
    from services.memory_tiers import query_episodes
    # Admin UI lists every tenant's episodes by default — only filter when explicitly requested.
    episodes = await query_episodes(tenant_id, action_type=action_type, outcome=outcome, limit=limit)
    return {"status": "ok", "episodes": episodes, "count": len(episodes)}


@router.get("/episodes/patterns")
async def get_patterns(
    tenant_id: Optional[str] = None,
    action_type: Optional[str] = None,
    admin=Depends(_get_admin),
):
    from services.memory_tiers import get_success_patterns
    patterns = await get_success_patterns(tenant_id, action_type=action_type)
    return {"status": "ok", **patterns}


@router.get("/working")
async def get_working(tenant_id: Optional[str] = None, admin=Depends(_get_admin)):
    from services.memory_tiers import get_working_memory
    wm = await get_working_memory(tenant_id)
    return {"status": "ok", "working_memory": wm}


# ═══════════════════════════════════════
# EXECUTION PLANS
# ═══════════════════════════════════════

@router.get("/plans/recent")
async def get_recent_plans(
    tenant_id: Optional[str] = None,
    limit: int = 10,
    admin=Depends(_get_admin),
):
    from services.memory_tiers import get_recent_plans
    # Admin UI defaults to cross-tenant view.
    plans = await get_recent_plans(tenant_id, limit=limit)
    return {"status": "ok", "plans": plans, "count": len(plans)}


@router.get("/plans/{pipeline_run_id}")
async def get_plan(pipeline_run_id: str, admin=Depends(_get_admin)):
    from services.memory_tiers import get_execution_plan
    plan = await get_execution_plan(pipeline_run_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"status": "ok", "plan": plan}


@router.get("/promotions")
async def get_promotions_api(
    tenant_id: Optional[str] = None,
    limit: int = 20,
    admin=Depends(_get_admin),
):
    from services.memory_tiers import get_promotions
    promotions = await get_promotions(tenant_id, limit=limit)
    return {"status": "ok", "promotions": promotions, "count": len(promotions)}


@router.get("/learning-velocity")
async def learning_velocity_api(
    tenant_id: Optional[str] = None,
    admin=Depends(_get_admin),
):
    from services.memory_tiers import get_learning_velocity
    velocity = await get_learning_velocity(tenant_id)
    return {"status": "ok", **velocity}


@router.get("/loop-stats")
async def get_loop_stats(
    tenant_id: Optional[str] = None,
    admin=Depends(_get_admin),
):
    from services.memory_tiers import get_memory_loop_stats
    stats = await get_memory_loop_stats(tenant_id)
    return {"status": "ok", **stats}


# ═══════════════════════════════════════
# ASK_USER MASTER SWITCH
# ═══════════════════════════════════════

@router.get("/ask-user")
async def get_ask_user_mode(admin=Depends(_get_admin)):
    env_val = os.environ.get("ASK_USER", "true").lower()
    db_override = None
    if _db is not None:
        doc = await _db.system_config.find_one({"key": "ask_user_mode"}, {"_id": 0})
        if doc:
            db_override = doc.get("value")
    mode = db_override if db_override is not None else (env_val == "true")
    return {
        "status": "ok",
        "ask_user": mode,
        "source": "database" if db_override is not None else "env",
        "label": "SUPERVISED" if mode else "AUTONOMOUS",
    }


@router.put("/ask-user")
async def set_ask_user_mode(body: dict = Body(...), admin=Depends(_get_admin)):
    enabled = body.get("enabled")
    if enabled is None:
        raise HTTPException(status_code=400, detail="'enabled' field required (true/false)")
    if _db is not None:
        await _db.system_config.update_one(
            {"key": "ask_user_mode"},
            {"$set": {
                "key": "ask_user_mode",
                "value": bool(enabled),
                "updated_by": admin.get("email", "admin"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
    mode = bool(enabled)
    label = "SUPERVISED" if mode else "AUTONOMOUS"
    logger.info(f"[ASK_USER] Mode set to {label} by {admin.get('email')}")
    return {"status": "ok", "ask_user": mode, "label": label}
