"""
AUREM API Gateway Router
Handles gateway stats, webhook management, and request logging
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/gateway", tags=["AUREM Gateway"])
logger = logging.getLogger(__name__)

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


def _get_user_from_token(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = auth_header.split(" ", 1)[1]
    try:
        import jwt
        secret = os.environ.get("JWT_SECRET", "")
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(401, "Invalid token")


class WebhookCreate(BaseModel):
    url: str
    events: List[str] = []


@router.get("/stats")
async def get_gateway_stats(request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    from datetime import datetime, timezone
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    webhook_count = await db.webhooks.count_documents({"user_id": user_id})
    total_logs = await db.api_request_logs.count_documents({"timestamp": {"$gte": today_start}})
    error_logs = await db.api_request_logs.count_documents({"timestamp": {"$gte": today_start}, "status": {"$gte": 400}})

    # Compute average latency from real logs
    avg_latency = 0
    pipeline = [{"$match": {"timestamp": {"$gte": today_start}}}, {"$group": {"_id": None, "avg": {"$avg": "$latency_ms"}}}]
    async for doc in db.api_request_logs.aggregate(pipeline):
        avg_latency = round(doc.get("avg", 0), 1)

    error_rate = round((error_logs / total_logs * 100), 2) if total_logs > 0 else 0

    return {
        "total_requests_today": total_logs,
        "avg_latency_ms": avg_latency,
        "error_rate": error_rate,
        "active_webhooks": webhook_count,
        "uptime_percent": 100.0
    }


@router.get("/webhooks")
async def get_webhooks(request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    webhooks = []
    cursor = db.webhooks.find({"user_id": user_id}, {"_id": 0})
    async for wh in cursor:
        webhooks.append(wh)

    return {"webhooks": webhooks}


@router.post("/webhooks")
async def create_webhook(data: WebhookCreate, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    webhook = {
        "user_id": user_id,
        "url": data.url,
        "events": data.events,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.webhooks.insert_one(webhook)

    return {"success": True, "url": data.url}


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: str, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    result = await db.webhooks.delete_one(
        {"user_id": user_id, "url": webhook_id}
    )

    return {"success": True, "deleted": result.deleted_count > 0}


@router.get("/request-logs")
async def get_request_logs(request: Request, limit: int = 30):
    """Get recent API request logs for the live request log feed"""
    user_data = _get_user_from_token(request)
    db = get_db()

    logs = []
    cursor = db.api_request_logs.find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).limit(limit)
    async for log in cursor:
        logs.append(log)

    return {"logs": logs, "total": len(logs)}
