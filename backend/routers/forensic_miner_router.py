"""
AUREM Forensic Miner Router
POST /api/forensic-miner/scan — discover stores + emails + health scores
GET  /api/forensic-miner/history — scan history
GET  /api/forensic-miner/niches — supported niche keywords
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/api/forensic-miner", tags=["Forensic Miner"])
logger = logging.getLogger(__name__)


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        import jwt
        return jwt.decode(authorization.replace("Bearer ", ""), os.getenv("JWT_SECRET"), algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def _tenant(p: dict) -> str:
    return p.get("tenant_id") or p.get("business_id") or "aurem_platform"


def _init():
    from services.forensic_miner_service import set_db
    try:
        import server
        if hasattr(server, "db"):
            set_db(server.db)
    except Exception:
        pass


class ScanRequest(BaseModel):
    niche: str = "beauty"
    limit: int = 10
    zone: str = "com"
    auto_outreach: bool = False


@router.post("/scan")
async def scan(req: ScanRequest, authorization: str = Header(None)):
    """
    Forensic Miner: discover stores by niche + find emails + health scan.
    Uses DomainsDB (free) + Tomba (free) + web scraping.
    """
    p = await _auth(authorization)
    _init()
    from services.forensic_miner_service import scan_niche
    result = await scan_niche(req.niche, min(req.limit, 50), req.zone, req.auto_outreach, _tenant(p))
    return result


@router.get("/history")
async def history(limit: int = 10, authorization: str = Header(None)):
    """Get scan history."""
    p = await _auth(authorization)
    _init()
    from services.forensic_miner_service import get_scan_history
    scans = await get_scan_history(_tenant(p), limit)
    return {"scans": scans, "count": len(scans)}


class OutreachRequest(BaseModel):
    domain: str
    email: str = ""
    phone: str = ""
    health_score: int = 0
    issues: List[str] = []
    scan_id: str = ""


@router.post("/queue-outreach")
async def queue_outreach(req: OutreachRequest, authorization: str = Header(None)):
    """Queue WhatsApp + Email outreach for a discovered lead."""
    p = await _auth(authorization)
    _init()
    from services.forensic_miner_service import _get_db
    db = _get_db()
    if not db:
        raise HTTPException(500, "Database not available")
    channels = ["email"]
    if req.phone:
        channels.append("whatsapp")
    doc = {
        "domain": req.domain,
        "email": req.email,
        "phone": req.phone,
        "health_score": req.health_score,
        "issues": req.issues,
        "scan_id": req.scan_id,
        "tenant_id": _tenant(p),
        "channels": channels,
        "status": "queued",
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    await db.forensic_miner_outreach_queue.insert_one(doc)
    return {"queued": True, "domain": req.domain, "channels": channels, "status": "queued"}


@router.get("/outreach-status")
async def outreach_status(authorization: str = Header(None)):
    """Get outreach queue status for current tenant."""
    p = await _auth(authorization)
    _init()
    from services.forensic_miner_service import _get_db
    db = _get_db()
    if not db:
        return {"queue": [], "count": 0}
    items = await db.forensic_miner_outreach_queue.find(
        {"tenant_id": _tenant(p)}, {"_id": 0}
    ).sort("created_at", -1).limit(50).to_list(50)
    return {"queue": items, "count": len(items)}


@router.get("/niches")
async def niches(authorization: str = Header(None)):
    """List supported niche keywords for scanning."""
    await _auth(authorization)
    from services.forensic_miner_service import NICHE_KEYWORDS
    return {"niches": {k: v for k, v in NICHE_KEYWORDS.items()}, "count": len(NICHE_KEYWORDS)}
