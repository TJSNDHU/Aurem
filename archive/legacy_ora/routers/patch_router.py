"""
AUREM Patch API Router
========================
Endpoints for the pixel to fetch patches, report status,
and for admins to manage patch deployments.
"""
from fastapi import APIRouter, HTTPException, Request, Query
from datetime import datetime, timezone
from typing import Optional

router = APIRouter(prefix="/api/pixel", tags=["Live Patches"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.patch_deployer import set_db as set_deployer_db
    set_deployer_db(database)


@router.get("/patches")
async def get_patches_for_pixel(key: str = Query(..., description="API key from the tracking pixel")):
    """Pixel calls this on load to get any pending patches to apply."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Not ready")

    # Kill Switch check — if live patches disabled, return empty
    from services.kill_switch import is_live_patches_disabled
    if is_live_patches_disabled():
        return {"patches": [], "version": "2.0.0", "count": 0, "kill_switch": True}

    # Resolve API key → business_id
    key_doc = await _db["api_keys"].find_one({"key": key, "is_active": True}, {"_id": 0})
    if not key_doc:
        return {"patches": [], "version": "1.0.0"}

    business_id = key_doc.get("business_id", "")

    from services.patch_deployer import get_active_patches
    patches = await get_active_patches(business_id)

    # Format for pixel consumption
    pixel_patches = []
    for p in patches:
        pixel_patches.append({
            "id": p.get("patch_id", ""),
            "type": p.get("type", ""),
            "code": p.get("code", ""),
            "tags": p.get("tags", []),
            "json_ld": p.get("json_ld"),
            "description": p.get("description", ""),
            "rollout_pct": p.get("rollout_pct", 100),
        })

    # HMAC sign all patches for integrity verification
    from services.hmac_signing import sign_patches, get_public_verification_key, set_db as set_hmac_db
    set_hmac_db(_db)
    signed_patches = await sign_patches(pixel_patches, business_id)
    verify_token = await get_public_verification_key(business_id)

    return {
        "patches": signed_patches,
        "version": "3.0.0",
        "count": len(signed_patches),
        "verify_token": verify_token,
        "hmac": True,
    }


@router.post("/patches/report")
async def report_patch_status(request: Request):
    """Pixel reports whether a patch was applied successfully or failed."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Not ready")

    body = await request.json()
    patch_id = body.get("patch_id", "")
    success = body.get("success", True)
    error_msg = body.get("error", "")

    if not patch_id:
        raise HTTPException(status_code=400, detail="patch_id required")

    from services.patch_deployer import report_patch_applied
    await report_patch_applied(patch_id, success)

    # Log failures for debugging
    if not success:
        await _db["patch_errors"].insert_one({
            "patch_id": patch_id,
            "error": error_msg,
            "user_agent": request.headers.get("user-agent", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return {"status": "ok"}


# ─── Admin Endpoints ───────────────────────────────────────────

@router.get("/patches/admin")
async def admin_list_patches(business_id: Optional[str] = None, status: Optional[str] = None):
    """Admin: List all patches, optionally filtered."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Not ready")

    query = {}
    if business_id:
        query["business_id"] = business_id
    if status:
        query["status"] = status

    cursor = _db["live_patches"].find(query, {"_id": 0}).sort("created_at", -1).limit(100)
    patches = await cursor.to_list(100)
    return {"count": len(patches), "patches": patches}


@router.post("/patches/rollback")
async def admin_rollback_batch(request: Request):
    """Admin: Rollback all patches in a batch."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Not ready")

    body = await request.json()
    batch_id = body.get("batch_id", "")
    if not batch_id:
        raise HTTPException(status_code=400, detail="batch_id required")

    from services.patch_deployer import rollback_batch
    result = await rollback_batch(batch_id)
    return result


@router.post("/patches/promote")
async def admin_promote_batch(request: Request):
    """Admin: Promote a batch to a higher rollout percentage (canary deploy)."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Not ready")

    body = await request.json()
    batch_id = body.get("batch_id", "")
    new_pct = body.get("rollout_pct", 100)

    if not batch_id:
        raise HTTPException(status_code=400, detail="batch_id required")
    if not (1 <= new_pct <= 100):
        raise HTTPException(status_code=400, detail="rollout_pct must be 1-100")

    from services.patch_deployer import canary_promote
    result = await canary_promote(batch_id, new_pct)
    return result
