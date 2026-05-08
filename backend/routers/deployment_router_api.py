"""
AUREM Deployment Router API
=============================
Admin endpoints for viewing deployment history, stats, and manual operations.
"""
from fastapi import APIRouter, HTTPException, Request
from typing import Optional

router = APIRouter(prefix="/api/deploy", tags=["Deployment Router"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.deployment_router import set_db as set_dr_db
    set_dr_db(database)


@router.get("/stats")
async def get_deploy_stats():
    """Get aggregate deployment statistics across all tenants."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Not ready")

    from services.deployment_router import get_deployment_stats
    return await get_deployment_stats()


@router.get("/history")
async def get_deploy_history(business_id: Optional[str] = None, limit: int = 20):
    """Get deployment history, optionally filtered by business_id."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Not ready")

    from services.deployment_router import get_deployment_history
    history = await get_deployment_history(business_id=business_id, limit=limit)
    return {"count": len(history), "history": history}


@router.post("/manual")
async def manual_deploy(request: Request):
    """Manually trigger a deployment for a specific business.
    Body: { business_id, tenant_id, batch_id }
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Not ready")

    body = await request.json()
    business_id = body.get("business_id", "")
    tenant_id = body.get("tenant_id", business_id)
    batch_id = body.get("batch_id", "")

    if not business_id or not batch_id:
        raise HTTPException(status_code=400, detail="business_id and batch_id required")

    # Get patches for this batch
    patches = await _db["live_patches"].find(
        {"batch_id": batch_id, "status": "active"}, {"_id": 0}
    ).to_list(50)

    if not patches:
        raise HTTPException(status_code=404, detail="No active patches found for this batch")

    from services.deployment_router import route_and_deploy
    result = await route_and_deploy(tenant_id, business_id, patches, batch_id)
    return result


@router.post("/preflight")
async def run_preflight(request: Request):
    """Run a pre-flight check for a tenant's platform connection.
    Body: { business_id, tenant_id }
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Not ready")

    body = await request.json()
    business_id = body.get("business_id", "")
    tenant_id = body.get("tenant_id", business_id)

    if not business_id:
        raise HTTPException(status_code=400, detail="business_id required")

    from services.deployment_router import DeploymentRouter
    dr = DeploymentRouter(tenant_id, business_id)
    await dr.load_connection()
    result = await dr.preflight_check()
    result["platform"] = dr.platform
    result["business_id"] = business_id
    return result


@router.get("/log/{deploy_id}")
async def get_deploy_log(deploy_id: str):
    """Get details of a specific deployment."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Not ready")

    log = await _db["deployment_log"].find_one({"deploy_id": deploy_id}, {"_id": 0})
    if not log:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return log
