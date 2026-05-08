"""
Database Optimization Router — Health Reports & Manual Triggers
================================================================
Endpoints for viewing DB health, triggering cold storage archival,
and running full optimization sweeps.
"""

import logging
from fastapi import APIRouter, Header, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/db", tags=["Database Optimization"])

_db = None

def set_db(database):
    global _db
    _db = database


async def _verify_admin(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")
    try:
        import jwt, os
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/health")
async def db_health_report(authorization: str = Header(None)):
    """Get comprehensive DB health report with bloat analysis."""
    await _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    from services.db_optimizer import get_db_health_report
    return await get_db_health_report(_db)


@router.post("/optimize")
async def run_optimization(authorization: str = Header(None)):
    """Run full optimization: archive cold data, create indexes, drop empties."""
    await _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    from services.db_optimizer import run_full_optimization
    results = await run_full_optimization(_db)
    return {"status": "complete", **results}


@router.post("/archive")
async def archive_old_data(days: int = 7, authorization: str = Header(None)):
    """Archive data older than N days to cold storage collections."""
    await _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    from services.db_optimizer import archive_cold_data
    archived = await archive_cold_data(_db, days_threshold=days)
    return {"status": "complete", "documents_archived": archived, "threshold_days": days}


@router.post("/index")
async def create_indexes(authorization: str = Header(None)):
    """Create compound indexes for hot query patterns."""
    await _verify_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    from services.db_optimizer import create_compound_indexes
    count = await create_compound_indexes(_db)
    return {"status": "complete", "indexes_created": count}
