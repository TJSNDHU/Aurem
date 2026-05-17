"""
/app/backend/routers/founder_saves_router.py
Unified audit endpoint for founder-level commit/governance insight.
"""
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/founder-saves", tags=["founder-saves"])
security = HTTPBearer()

_db: Optional[AsyncIOMotorDatabase] = None

def set_db(database: AsyncIOMotorDatabase):
    global _db
    _db = database

async def get_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    secret = os.environ.get("JWT_SECRET") or ""
    if not secret:
        logger.error("JWT_SECRET not configured")
        raise HTTPException(status_code=500, detail="Server config error")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    email = (payload.get("email") or payload.get("sub") or "").lower()
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")
    # iter 322ey — fast path: trust the is_admin claim if present (auth router
    # already verified at login time); otherwise do a DB lookup.
    if payload.get("is_admin") or payload.get("is_super_admin"):
        return {"email": email, "is_admin": True}
    user = await _db.users.find_one(
        {"email": email},
        {"_id": 0, "is_admin": 1, "is_super_admin": 1, "role": 1},
    )
    if not user or not (
        user.get("is_admin") or user.get("is_super_admin")
        or user.get("role") in ("admin", "super_admin")
    ):
        raise HTTPException(status_code=403, detail="Admin access required")
    return {"email": email, "is_admin": True}

@router.get("/_/health")
async def health():
    return {"status": "ok", "service": "founder-saves"}

@router.get("/summary")
async def get_summary(user=Depends(get_admin_user)):
    # iter 322ey — audit collections store ts/decided_at as ISO STRINGS
    # (see services/ora_tools.py and git_gate_router.py). Use string
    # comparison so $gte works.
    now = datetime.now(timezone.utc)
    cutoff_iso = (now - timedelta(hours=24)).isoformat()

    commits_approved_24h = await _db.ora_commit_proposals.count_documents({
        "status": "approved",
        "decided_at": {"$gte": cutoff_iso}
    })
    commits_pending = await _db.ora_commit_proposals.count_documents({"status": "pending"})
    council_overrides_24h = await _db.ora_governance_overrides.count_documents({
        "ts": {"$gte": cutoff_iso}
    })
    tool_invocations_24h = await _db.ora_tool_invocations.count_documents({
        "ts": {"$gte": cutoff_iso}
    })
    tool_failures_24h = await _db.ora_tool_invocations.count_documents({
        "ts": {"$gte": cutoff_iso},
        "result.ok": False
    })

    last_save_doc = await _db.ora_commit_proposals.find_one(
        {"status": "approved"},
        sort=[("decided_at", -1)],
        projection={"decided_at": 1, "_id": 0}
    )
    # decided_at is already an ISO string — pass through verbatim
    last_save_ts = (last_save_doc or {}).get("decided_at")

    return {
        "commits_approved_24h": commits_approved_24h,
        "commits_pending": commits_pending,
        "council_overrides_24h": council_overrides_24h,
        "tool_invocations_24h": tool_invocations_24h,
        "tool_failures_24h": tool_failures_24h,
        "last_save_ts": last_save_ts
    }

@router.get("/timeline")
async def get_timeline(
    limit: int = 50,
    kind: Literal["all", "commit", "override", "tool_fail"] = "all",
    user=Depends(get_admin_user)
):
    timeline = []
    
    if kind in ("all", "commit"):
        cursor = _db.ora_commit_proposals.find(
            {"status": {"$in": ["approved", "rejected"]}},
            projection={"_id": 1, "commit_sha": 1, "commit_message": 1, "status": 1, "decided_at": 1, "decided_by": 1}
        ).sort("decided_at", -1).limit(limit if kind == "commit" else limit * 2)
        async for doc in cursor:
            timeline.append({
                "kind": "commit",
                "ts": doc.get("decided_at"),
                "actor": doc.get("decided_by"),
                "summary": f"{doc['status']}: {doc.get('commit_message', '')[:60]}",
                "ref_id": doc.get("commit_sha") or str(doc["_id"]),
                "ref_collection": "ora_commit_proposals"
            })
    
    if kind in ("all", "override"):
        cursor = _db.ora_governance_overrides.find(
            {},
            projection={"_id": 1, "reason": 1, "ts": 1, "actor": 1}
        ).sort("ts", -1).limit(limit if kind == "override" else limit * 2)
        async for doc in cursor:
            timeline.append({
                "kind": "override",
                "ts": doc.get("ts"),
                "actor": doc.get("actor"),
                "summary": doc.get("reason", "")[:80],
                "ref_id": str(doc["_id"]),
                "ref_collection": "ora_governance_overrides"
            })
    
    if kind in ("all", "tool_fail"):
        cursor = _db.ora_tool_invocations.find(
            {"result.ok": False},
            projection={"_id": 1, "tool": 1, "result": 1, "ts": 1, "actor": 1}
        ).sort("ts", -1).limit(limit if kind == "tool_fail" else limit * 2)
        async for doc in cursor:
            error_msg = doc.get("result", {}).get("error", "unknown")
            timeline.append({
                "kind": "tool_fail",
                "ts": doc.get("ts"),
                "actor": doc.get("actor"),
                "summary": f"{doc.get('tool', 'unknown')} failed: {error_msg[:60]}",
                "ref_id": str(doc["_id"]),
                "ref_collection": "ora_tool_invocations"
            })
    
    # iter 322ey — ts is stored as an ISO STRING; lexicographic compare
    # works for ISO-8601 sort so we keep strings throughout. _id stays
    # because we need a fallback ref when commit_sha is absent.
    timeline.sort(key=lambda x: x["ts"] or "", reverse=True)
    timeline = timeline[:limit]

    # Final shape — ensure ts is a string (already is, but defensive)
    for item in timeline:
        if item["ts"] and not isinstance(item["ts"], str):
            try:
                item["ts"] = item["ts"].isoformat()
            except Exception:
                item["ts"] = str(item["ts"])

    return timeline