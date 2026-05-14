"""
Tenant Optimization Router — Gates 1 & 4
Endpoints for profiling tenants, monitoring optimization, and admin controls.
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/optimization", tags=["Tenant Optimization"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.tenant_profiling import set_db as set_prof_db
    from services.optimization_monitor import set_db as set_mon_db
    set_prof_db(database)
    set_mon_db(database)


async def _get_admin(authorization: str = Header(None)):
    """Require admin authentication."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    import jwt
    import os
    try:
        secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
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
# GATE 1: TENANT PROFILING
# ═══════════════════════════════════════

@router.post("/profile/{tenant_id}")
async def profile_tenant_endpoint(tenant_id: str, admin=Depends(_get_admin)):
    """Profile a specific tenant for optimization readiness (Gate 1)."""
    from services.tenant_profiling import profile_tenant
    profile = await profile_tenant(tenant_id)
    if "error" in profile:
        raise HTTPException(status_code=500, detail=profile["error"])
    return profile


@router.post("/profile-all")
async def profile_all_tenants_endpoint(admin=Depends(_get_admin)):
    """Profile all active tenants (batch)."""
    from services.tenant_profiling import profile_all_tenants
    return await profile_all_tenants()


@router.get("/profiles")
async def list_profiles(admin=Depends(_get_admin)):
    """List all tenant optimization profiles."""
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    profiles = await _db.tenant_optimization_profiles.find(
        {}, {"_id": 0}
    ).sort("risk_score", -1).to_list(500)
    return {"profiles": profiles, "total": len(profiles)}


@router.get("/profile/{tenant_id}")
async def get_profile(tenant_id: str, admin=Depends(_get_admin)):
    """Get optimization profile for a specific tenant."""
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    profile = await _db.tenant_optimization_profiles.find_one(
        {"tenant_id": tenant_id}, {"_id": 0}
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Run profiling first.")
    return profile


# ═══════════════════════════════════════
# GATE 4: MONITORING
# ═══════════════════════════════════════

@router.get("/metrics/{tenant_id}")
async def get_metrics(tenant_id: str, days: int = 30, admin=Depends(_get_admin)):
    """Get optimization metrics for a tenant."""
    from services.optimization_monitor import get_tenant_optimization_metrics
    return await get_tenant_optimization_metrics(tenant_id, window_days=days)


@router.get("/dashboard")
async def get_dashboard_summary(admin=Depends(_get_admin)):
    """Get aggregate optimization dashboard summary."""
    from services.optimization_monitor import get_optimization_dashboard_summary
    return await get_optimization_dashboard_summary()


@router.get("/report/{tenant_id}")
async def get_monthly_report(tenant_id: str, admin=Depends(_get_admin)):
    """Generate monthly optimization report for a tenant."""
    from services.optimization_monitor import generate_monthly_report
    return await generate_monthly_report(tenant_id)


@router.get("/health-check/{tenant_id}")
async def check_tenant_health(tenant_id: str, admin=Depends(_get_admin)):
    """Check if optimization should be rolled back for a tenant."""
    from services.optimization_monitor import check_rollback_needed
    return await check_rollback_needed(tenant_id)


# ═══════════════════════════════════════
# ADMIN CONTROLS
# ═══════════════════════════════════════

@router.post("/toggle/{tenant_id}")
async def toggle_optimization(tenant_id: str, data: dict, admin=Depends(_get_admin)):
    """Enable or disable optimization for a tenant."""
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    enabled = data.get("enabled", False)
    profile = await _db.tenant_optimization_profiles.find_one(
        {"tenant_id": tenant_id}, {"_id": 0}
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    update = {
        "optimization_enabled": enabled,
        "toggled_at": datetime.now(timezone.utc).isoformat(),
        "toggled_by": admin.get("email", "admin"),
    }

    if enabled:
        update["optimization_stage"] = "monitoring"
        update["optimization_started_at"] = datetime.now(timezone.utc).isoformat()
    else:
        update["optimization_stage"] = "paused"

    await _db.tenant_optimization_profiles.update_one(
        {"tenant_id": tenant_id}, {"$set": update}
    )

    action = "enabled" if enabled else "paused"
    logger.info(f"[ADMIN] Optimization {action} for {tenant_id} by {admin.get('email')}")
    return {"success": True, "tenant_id": tenant_id, "optimization_enabled": enabled}


@router.post("/rollback/{tenant_id}")
async def force_rollback(tenant_id: str, admin=Depends(_get_admin)):
    """Force immediate rollback for a tenant."""
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    await _db.tenant_optimization_profiles.update_one(
        {"tenant_id": tenant_id},
        {"$set": {
            "optimization_enabled": False,
            "optimization_stage": "rolled_back",
            "rollback_at": datetime.now(timezone.utc).isoformat(),
            "rollback_by": admin.get("email", "admin"),
            "rollback_reasons": ["Manual rollback by admin"],
        }}
    )

    logger.warning(f"[ADMIN] Manual rollback for {tenant_id} by {admin.get('email')}")
    return {"success": True, "tenant_id": tenant_id, "stage": "rolled_back"}


@router.post("/advance-stage/{tenant_id}")
async def advance_stage(tenant_id: str, admin=Depends(_get_admin)):
    """Advance a tenant to the next optimization stage (admin override)."""
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    STAGE_ORDER = [
        "profiled", "shadow", "10%", "25%", "50%", "100%", "monitoring"
    ]

    profile = await _db.tenant_optimization_profiles.find_one(
        {"tenant_id": tenant_id}, {"_id": 0}
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    current = profile.get("optimization_stage", "profiled")
    if current in STAGE_ORDER:
        idx = STAGE_ORDER.index(current)
        if idx < len(STAGE_ORDER) - 1:
            next_stage = STAGE_ORDER[idx + 1]
        else:
            return {"success": True, "tenant_id": tenant_id, "stage": current, "message": "Already at final stage"}
    else:
        next_stage = "profiled"

    await _db.tenant_optimization_profiles.update_one(
        {"tenant_id": tenant_id},
        {"$set": {
            "optimization_stage": next_stage,
            "stage_advanced_at": datetime.now(timezone.utc).isoformat(),
            "stage_advanced_by": admin.get("email", "admin"),
        }}
    )

    logger.info(f"[ADMIN] Advanced {tenant_id}: {current} -> {next_stage}")
    return {"success": True, "tenant_id": tenant_id, "previous_stage": current, "new_stage": next_stage}
