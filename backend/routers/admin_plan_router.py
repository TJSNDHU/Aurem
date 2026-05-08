"""
AUREM AI Platform — Proprietary Software
Copyright (c) 2026 Polaris Built Inc.

Tenant Plan Router — tenant-facing plan/usage endpoints.
"""
import logging
import os
from fastapi import APIRouter, Depends, Header, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plan", tags=["Tenant Plan"])

db = None


def set_db(database):
    global db
    db = database


async def _get_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        import jwt as pyjwt
        from server import JWT_SECRET, JWT_ALGORITHM
        token = authorization.replace("Bearer ", "")
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id or not db:
            raise HTTPException(status_code=401, detail="Unauthorized")
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/my-usage")
async def my_usage(user=Depends(_get_user)):
    """Get current user's plan usage summary for sidebar widget."""
    from services.plan_enforcement import get_usage_summary
    tenant_id = user.get("tenant_id", "aurem_platform")
    return await get_usage_summary(tenant_id)


@router.get("/my-plan")
async def my_plan(user=Depends(_get_user)):
    """Get current user's plan details."""
    from services.plan_enforcement import get_tenant_plan
    tenant_id = user.get("tenant_id", "aurem_platform")
    plan = await get_tenant_plan(tenant_id)
    plan.pop("_id", None)
    return plan


@router.get("/available")
async def available_plans():
    """Public: List all active plans for pricing page."""
    if db is None:
        from services.plan_enforcement import PLAN_TIERS
        plans = [{"tier": k, **v, "active": True} for k, v in PLAN_TIERS.items()]
        return {"plans": plans}
    plans = await db.subscription_plans.find(
        {"active": True}, {"_id": 0}
    ).sort("price_monthly", 1).to_list(10)
    return {"plans": plans}


@router.get("/check-feature/{feature}")
async def check_feature(feature: str, user=Depends(_get_user)):
    """Check if a feature is available on the user's plan."""
    from services.plan_enforcement import check_feature_access
    tenant_id = user.get("tenant_id", "aurem_platform")
    return await check_feature_access(tenant_id, feature)
