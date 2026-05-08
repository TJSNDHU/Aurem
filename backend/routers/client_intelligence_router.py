"""
AUREM — Client Website Intelligence API Routes.
Endpoints for scanning client websites, viewing results, triggering scans, and auto-fixes.
"""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger("aurem.client_intelligence")

router = APIRouter(prefix="/api/intelligence", tags=["Client Website Intelligence"])

db = None


def set_db(database):
    global db
    db = database


class ScanTriggerRequest(BaseModel):
    website_url: Optional[str] = None


# ────────── SCAN TRIGGER ──────────
@router.post("/scan/{tenant_id}")
async def trigger_scan(tenant_id: str, req: ScanTriggerRequest = None, authorization: str = Header(None)):
    """Trigger a manual scan for a specific tenant's website."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    tenant = await db.users.find_one(
        {"$or": [{"tenant_id": tenant_id}, {"id": tenant_id}]},
        {"_id": 0, "website_url": 1, "business_name": 1, "tenant_id": 1},
    )

    # Resolve URL with fallbacks: (1) request body, (2) tenant profile, (3) last saved scan
    url = (req.website_url if req and req.website_url else None) or (tenant or {}).get("website_url")
    if not url:
        last = await db.client_scan_results.find_one(
            {"tenant_id": tenant_id, "url": {"$exists": True, "$ne": ""}},
            {"_id": 0, "url": 1},
            sort=[("scanned_at", -1)],
        )
        if last and last.get("url"):
            url = last["url"]
    if not url:
        raise HTTPException(status_code=400, detail="No website URL found for this tenant. Provide website_url in request body.")

    from services.client_scanner_service import ClientScannerService
    scanner = ClientScannerService(db)
    result = await scanner.run_full_scan(
        tenant_id=tenant_id,
        website_url=url,
        triggered_by="manual",
    )

    # Run auto-fixes on fixable issues
    from services.auto_fix_engine import run_auto_fixes
    fixes = await run_auto_fixes(db, tenant_id, result.get("issues", []))
    result["auto_fixed"] = [f for f in fixes if f.get("fixed")]
    result["auto_fix_count"] = len(result["auto_fixed"])

    # Update the stored scan with auto-fix results
    scan_key = f"scan_{tenant_id}_{int(datetime.fromisoformat(result['scanned_at']).timestamp())}"
    await db.client_scan_results.update_one(
        {"_id": scan_key},
        {"$set": {"auto_fixed": result["auto_fixed"], "auto_fix_count": result["auto_fix_count"]}},
    )

    result.pop("_id", None)
    return result


# ────────── LATEST SCAN ──────────
@router.get("/latest/{tenant_id}")
async def get_latest_scan(tenant_id: str, authorization: str = Header(None)):
    """Get the most recent scan result for a tenant."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    scan = await db.client_scan_results.find_one(
        {"tenant_id": tenant_id, "status": "completed"},
        {"_id": 0},
        sort=[("scanned_at", -1)],
    )
    if not scan:
        return {"found": False, "message": "No scans found for this tenant."}
    return {"found": True, **scan}


# ────────── SCAN HISTORY ──────────
@router.get("/history/{tenant_id}")
async def get_scan_history(tenant_id: str, limit: int = 30, authorization: str = Header(None)):
    """Get scan history for a tenant (last N scans)."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    cursor = db.client_scan_results.find(
        {"tenant_id": tenant_id},
        {"_id": 0, "pagespeed_raw": 0, "issues": 0, "auto_fixed": 0},
    ).sort("scanned_at", -1).limit(limit)

    scans = await cursor.to_list(length=limit)
    return {"tenant_id": tenant_id, "count": len(scans), "scans": scans}


# ────────── ALL CLIENTS OVERVIEW (Admin) ──────────
@router.get("/all-clients")
async def get_all_clients_scores(authorization: str = Header(None)):
    """Admin: Get latest scan scores for all clients."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    pipeline = [
        {"$match": {"status": "completed"}},
        {"$sort": {"scanned_at": -1}},
        {"$group": {
            "_id": "$tenant_id",
            "latest_scan": {"$first": "$$ROOT"},
        }},
        {"$replaceRoot": {"newRoot": "$latest_scan"}},
        {"$project": {
            "_id": 0, "tenant_id": 1, "url": 1, "overall_score": 1,
            "scores": 1, "issues_count": 1, "critical_count": 1,
            "fixable_count": 1, "auto_fix_count": 1, "scanned_at": 1,
            "scan_duration_seconds": 1,
        }},
        {"$sort": {"overall_score": 1}},
    ]

    results = await db.client_scan_results.aggregate(pipeline).to_list(length=200)

    # Enrich with business names
    for r in results:
        tenant = await db.users.find_one(
            {"$or": [{"tenant_id": r.get("tenant_id")}, {"id": r.get("tenant_id")}]},
            {"_id": 0, "business_name": 1, "full_name": 1},
        )
        r["business_name"] = (tenant or {}).get("business_name", r.get("tenant_id", "Unknown"))

    return {"clients": results, "total": len(results)}


# ────────── AUTO-FIX TRIGGER ──────────
@router.post("/auto-fix/{tenant_id}")
async def trigger_auto_fix(tenant_id: str, authorization: str = Header(None)):
    """Run auto-fix on the latest scan issues for a tenant."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    scan = await db.client_scan_results.find_one(
        {"tenant_id": tenant_id, "status": "completed"},
        sort=[("scanned_at", -1)],
    )
    if not scan:
        raise HTTPException(status_code=404, detail="No scan results found")

    from services.auto_fix_engine import run_auto_fixes
    fixes = await run_auto_fixes(db, tenant_id, scan.get("issues", []))

    fixed = [f for f in fixes if f.get("fixed")]

    await db.client_scan_results.update_one(
        {"_id": scan["_id"]},
        {"$set": {"auto_fixed": fixed, "auto_fix_count": len(fixed)}},
    )

    return {"tenant_id": tenant_id, "fixes_applied": len(fixed), "fixes": fixed}


# ────────── PUBLIC SHAREABLE REPORT ──────────
@router.get("/report/{tenant_id}")
async def get_public_report(tenant_id: str):
    """Public endpoint — no auth. Returns scan data for shareable report page."""
    if db is None:
        raise HTTPException(status_code=503, detail="Service unavailable")

    scan = await db.client_scan_results.find_one(
        {"tenant_id": tenant_id, "status": "completed"},
        {"_id": 0},
        sort=[("scanned_at", -1)],
    )
    if not scan:
        raise HTTPException(status_code=404, detail="No report found")

    tenant = await db.users.find_one(
        {"$or": [{"tenant_id": tenant_id}, {"id": tenant_id}]},
        {"_id": 0, "business_name": 1, "industry": 1, "website_url": 1, "full_name": 1},
    )
    bname = (tenant or {}).get("business_name", tenant_id)
    industry = (tenant or {}).get("industry", "")

    # Get scan history for trend
    history = await db.client_scan_results.find(
        {"tenant_id": tenant_id, "status": "completed"},
        {"_id": 0, "overall_score": 1, "scanned_at": 1},
    ).sort("scanned_at", -1).limit(10).to_list(length=10)

    return {
        "business_name": bname,
        "industry": industry,
        "url": scan.get("url", ""),
        "overall_score": scan.get("overall_score", 0),
        "scores": scan.get("scores", {}),
        "pagespeed_raw": scan.get("pagespeed_raw", {}),
        "issues": scan.get("issues", []),
        "auto_fixed": scan.get("auto_fixed", []),
        "issues_count": scan.get("issues_count", 0),
        "fixable_count": scan.get("fixable_count", 0),
        "auto_fix_count": scan.get("auto_fix_count", 0),
        "scanned_at": scan.get("scanned_at", ""),
        "scan_duration_seconds": scan.get("scan_duration_seconds", 0),
        "history": history,
        "tenant_id": tenant_id,
    }
@router.get("/morning-summary")
async def get_morning_scan_summary(authorization: str = Header(None)):
    """Morning Brief integration: summary of overnight scan results."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()

    scans_today = await db.client_scan_results.find(
        {"scanned_at": {"$gte": today}, "status": "completed"},
        {"_id": 0, "tenant_id": 1, "url": 1, "overall_score": 1, "issues_count": 1, "auto_fix_count": 1},
    ).to_list(length=200)

    below_80 = [s for s in scans_today if s.get("overall_score", 100) < 80]
    total_fixes = sum(s.get("auto_fix_count", 0) for s in scans_today)

    return {
        "scanned_count": len(scans_today),
        "below_80_count": len(below_80),
        "below_80_clients": below_80,
        "total_auto_fixes": total_fixes,
        "summary": f"{len(scans_today)} client websites scanned. {len(below_80)} dropped below 80. {total_fixes} issues auto-fixed.",
    }
