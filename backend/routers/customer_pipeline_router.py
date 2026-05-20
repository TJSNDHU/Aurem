"""
Customer Pipeline Router — exposes the recent scan-events feed that the
luxe dashboard polls every refresh.

Created (iter 325) to eliminate the recurring 404s on
`/api/customer/pipeline/scan-events?limit=30` seen in production logs.
The luxe dashboard's `useLuxeDashboardData.js` calls this on mount and
silently swallows the 404 via `safeGet`, so the UX never broke — but the
log noise was masking real errors.

Returns the most recent N scan records belonging to the authenticated
platform user. Source collection: `customer_scans` (written by the
scanner pipeline). If no scans exist yet, returns an empty list — the
frontend renders an empty-state card.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query

from config import JWT_SECRET

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/customer/pipeline", tags=["Customer Pipeline"])

_db = None


def set_db(db):
    global _db
    _db = db


def _decode_token(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing_bearer")
    token = authorization.split(" ", 1)[1].strip()
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"invalid_token: {e}")


@router.get("/scan-events")
async def scan_events(
    limit: int = Query(30, ge=1, le=100),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Recent scan events for the authenticated customer."""
    claims = _decode_token(authorization)
    user_id = claims.get("sub") or claims.get("user_id") or claims.get("email")
    if not user_id:
        raise HTTPException(status_code=401, detail="no_subject_in_token")

    if _db is None:
        return {"events": [], "total": 0, "note": "db-not-ready"}

    events: List[Dict[str, Any]] = []
    # Try the canonical collections in order — first hit wins. Newest first.
    for coll_name in ("customer_scans", "scan_history", "scans"):
        coll = _db[coll_name]
        cursor = coll.find(
            {"$or": [
                {"user_id": user_id},
                {"customer_email": claims.get("email")},
                {"email": claims.get("email")},
            ]},
            {"_id": 0},
        ).sort("created_at", -1).limit(limit)
        async for doc in cursor:
            # Normalise timestamps to ISO so the frontend doesn't choke.
            ts = doc.get("created_at") or doc.get("timestamp") or doc.get("ts")
            if isinstance(ts, datetime):
                doc["created_at"] = ts.astimezone(timezone.utc).isoformat()
            events.append(doc)
        if events:
            break

    return {"events": events, "total": len(events)}
