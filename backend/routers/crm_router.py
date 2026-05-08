"""
AUREM CRM Connect Router
Handles CRM connections, contact sync, and deal pipeline management
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/crm", tags=["AUREM CRM"])
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


class CRMConnectRequest(BaseModel):
    provider: str
    api_key: str
    instance_url: Optional[str] = None


@router.get("/connections")
async def get_connections(request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    connections = []
    cursor = db.crm_connections.find(
        {"user_id": user_id},
        {"_id": 0}
    )
    async for conn in cursor:
        connections.append(conn)

    # Compute stats
    contact_count = await db.crm_contacts.count_documents({"user_id": user_id})
    deal_count = await db.crm_deals.count_documents({"user_id": user_id, "status": "active"})

    # Calculate synced today from contacts created today
    from datetime import datetime, timezone
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()
    synced_today = await db.crm_contacts.count_documents({
        "user_id": user_id,
        "last_activity": {"$gte": today_start}
    })

    return {
        "connections": connections,
        "stats": {
            "total_contacts": contact_count,
            "synced_today": synced_today,
            "active_deals": deal_count,
            "sync_health": 100 if connections else 0
        }
    }


@router.post("/connect")
async def connect_crm(data: CRMConnectRequest, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    # Check if already connected
    existing = await db.crm_connections.find_one(
        {"user_id": user_id, "provider": data.provider}
    )
    if existing:
        raise HTTPException(400, f"{data.provider} is already connected")

    connection = {
        "user_id": user_id,
        "provider": data.provider,
        "instance_url": data.instance_url,
        "status": "connected",
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "last_sync": None
    }
    await db.crm_connections.insert_one(connection)

    return {"success": True, "provider": data.provider, "status": "connected"}


@router.delete("/disconnect/{provider}")
async def disconnect_crm(provider: str, request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    result = await db.crm_connections.delete_one(
        {"user_id": user_id, "provider": provider}
    )

    if result.deleted_count == 0:
        raise HTTPException(404, "Connection not found")

    return {"success": True, "provider": provider}


@router.get("/contacts/recent")
async def get_recent_contacts(request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    contacts = []
    cursor = db.crm_contacts.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(20)
    async for contact in cursor:
        contacts.append(contact)

    return {"contacts": contacts}



@router.post("/sync/{provider}")
async def sync_crm(provider: str, request: Request):
    """Trigger a sync for a connected CRM provider"""
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    connection = await db.crm_connections.find_one(
        {"user_id": user_id, "crm_type": provider},
        {"_id": 0}
    )
    if not connection:
        # Try by provider field
        connection = await db.crm_connections.find_one(
            {"user_id": user_id, "provider": provider},
            {"_id": 0}
        )
    if not connection:
        raise HTTPException(404, f"No connection found for {provider}")

    # Update last_sync timestamp
    await db.crm_connections.update_one(
        {"user_id": user_id, "crm_type": provider},
        {"$set": {"last_sync": datetime.now(timezone.utc).isoformat()}}
    )
    await db.crm_connections.update_one(
        {"user_id": user_id, "provider": provider},
        {"$set": {"last_sync": datetime.now(timezone.utc).isoformat()}}
    )

    return {
        "success": True,
        "provider": provider,
        "contacts_synced": connection.get("contacts_synced", 0),
        "last_sync": datetime.now(timezone.utc).isoformat()
    }
