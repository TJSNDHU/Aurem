"""
Dark Scout Router — API endpoints for AUREM's Intelligence Layer 3.
Manual investigation triggers, history, and OODA loop integration.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/admin/dark-scout", tags=["Dark Scout"])
logger = logging.getLogger(__name__)

_db = None


def set_db(db):
    global _db
    _db = db


def _verify_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        import jwt
        secret = os.environ.get("JWT_SECRET")
        if not secret:
            raise HTTPException(500, "JWT not configured")
        payload = jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
        # Bug-fix #39 — require an admin claim, not just a valid JWT.
        from utils.admin_guard import is_admin_email
        if not (payload.get("is_admin") or payload.get("is_super_admin")
                or payload.get("role") in ("admin", "super_admin")
                or is_admin_email(payload.get("email"))):
            raise HTTPException(403, "Admin access required")
        return payload
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid token")


# ══════════════════════════════════════════════
# Investigation Trigger
# ══════════════════════════════════════════════

class InvestigationRequest(BaseModel):
    query: str
    preset: str = "brand_monitor"
    max_results: int = 15


@router.post("/investigate")
async def start_investigation(body: InvestigationRequest, request: Request):
    """Trigger a Dark Scout investigation manually."""
    _verify_admin(request)

    from services.dark_scout_service import run_investigation
    result = await run_investigation(
        query=body.query,
        tenant_id="polaris-built-001",
        preset=body.preset,
        max_results=body.max_results,
    )
    return {
        "investigation_id": result.get("investigation_id"),
        "status": result.get("status"),
        "risk_level": result.get("risk_level"),
        "search_results": result.get("search_results"),
        "filtered_results": result.get("filtered_results"),
        "scraped_pages": result.get("scraped_pages"),
        "analysis_preview": (result.get("analysis") or "")[:500],
    }


# ══════════════════════════════════════════════
# Investigation History
# ══════════════════════════════════════════════

@router.get("/investigations")
async def list_investigations(
    request: Request,
    page: int = 1,
    limit: int = 20,
    risk_level: Optional[str] = None,
):
    """List past investigations with pagination."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    query = {}
    if risk_level:
        query["risk_level"] = risk_level.upper()

    total = await _db.dark_scout_investigations.count_documents(query)
    skip = (page - 1) * limit
    docs = await _db.dark_scout_investigations.find(query, {"_id": 0}).sort("started_at", -1).skip(skip).limit(limit).to_list(limit)

    return {"investigations": docs, "total": total, "page": page}


@router.get("/investigations/{investigation_id}")
async def get_investigation(investigation_id: str, request: Request):
    """Get full investigation report."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    doc = await _db.dark_scout_investigations.find_one(
        {"investigation_id": investigation_id}, {"_id": 0}
    )
    if not doc:
        raise HTTPException(404, "Investigation not found")
    return doc


# ══════════════════════════════════════════════
# Quick Brand Monitor
# ══════════════════════════════════════════════

@router.get("/quick-scan")
async def quick_brand_scan(request: Request, brand: str = "Aurem"):
    """Quick brand mention scan — no LLM analysis, just search + count."""
    _verify_admin(request)

    from services.dark_scout_service import search_surface
    results = await search_surface(f'"{brand}" data breach OR leak OR credentials', max_results=20)

    return {
        "brand": brand,
        "mentions_found": len(results),
        "results": [{"title": r.get("title", ""), "link": r.get("link", ""), "source": r.get("source", "")} for r in results[:10]],
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════
# Status / Health
# ══════════════════════════════════════════════

@router.get("/status")
async def dark_scout_status(request: Request):
    """Dark Scout system status."""
    _verify_admin(request)
    if _db is None:
        raise HTTPException(500, "DB not initialized")

    total = await _db.dark_scout_investigations.count_documents({})
    recent = await _db.dark_scout_investigations.find(
        {}, {"_id": 0, "risk_level": 1, "status": 1}
    ).sort("started_at", -1).limit(10).to_list(10)

    risk_counts = {}
    for r in recent:
        rl = r.get("risk_level", "UNKNOWN")
        risk_counts[rl] = risk_counts.get(rl, 0) + 1

    # Check Camofox availability
    camofox_ok = False
    try:
        from services.camofox_client import check_health
        camofox_ok = await check_health()
    except Exception:
        pass

    # Check Tor availability (for future Legion deployment)
    tor_available = False

    llm_key = os.environ.get("EMERGENT_LLM_KEY")

    return {
        "operational": True,
        "total_investigations": total,
        "risk_distribution": risk_counts,
        "scraping_engine": "camofox" if camofox_ok else "httpx_fallback",
        "tor_available": tor_available,
        "llm_available": bool(llm_key),
        "dark_web_enabled": tor_available,
    }


# ══════════════════════════════════════════════
# Presets (for frontend dropdown)
# ══════════════════════════════════════════════

@router.get("/presets")
async def list_presets(request: Request):
    _verify_admin(request)
    return {
        "presets": [
            {"id": "brand_monitor", "name": "Brand Monitor", "description": "Monitor brand mentions, impersonation, reputation threats"},
            {"id": "competitor_intel", "name": "Competitor Intelligence", "description": "Track competitor pricing, products, strategy signals"},
            {"id": "breach_detection", "name": "Breach Detection", "description": "Detect leaked credentials, PII, internal documents"},
            {"id": "threat_landscape", "name": "Threat Landscape", "description": "Scan for active threats targeting your industry/geography"},
        ]
    }
