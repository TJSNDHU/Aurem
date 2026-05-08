"""
WhatsApp Hybrid Integration Router
====================================
Endpoints for connecting Meta Cloud API (primary) or WHAPI (fallback)
per tenant. Credentials stored in DB (user_integrations), never in .env.

Endpoints:
  POST /api/integrations/{tenant_id}/whatsapp/connect-meta
  POST /api/integrations/{tenant_id}/whatsapp/connect-whapi
  GET  /api/integrations/{tenant_id}/whatsapp/status
  POST /api/integrations/{tenant_id}/whatsapp/send-test
  POST /api/integrations/{tenant_id}/whatsapp/disconnect
"""

import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/integrations", tags=["WhatsApp Hybrid"])
logger = logging.getLogger(__name__)

_db = None

def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


async def _auth(authorization: str):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    try:
        import jwt
        payload = jwt.decode(
            authorization.replace("Bearer ", ""),
            os.getenv("JWT_SECRET"), algorithms=["HS256"]
        )
        return payload
    except Exception:
        raise HTTPException(401, "Invalid token")


# ═══════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════

class MetaConnectRequest(BaseModel):
    phone_number_id: str
    waba_id: str
    access_token: str

class WhapiConnectRequest(BaseModel):
    whapi_token: str

class SendTestRequest(BaseModel):
    to: str
    message: str = "AUREM WhatsApp Test Message"


# ═══════════════════════════════════════════════════════════
# Connect Meta Cloud API
# ═══════════════════════════════════════════════════════════

@router.post("/{tenant_id}/whatsapp/connect-meta")
async def connect_meta(tenant_id: str, body: MetaConnectRequest, authorization: str = Header(None)):
    """
    Connect Meta Cloud API (permanent — never expires).
    Validates credentials against Meta's API before saving.
    """
    await _auth(authorization)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not available")

    from services.whatsapp_engine import WhatsAppEngine
    engine = WhatsAppEngine(db)

    # Validate credentials
    verify = await engine.verify_meta_credentials(
        body.phone_number_id, body.waba_id, body.access_token
    )
    if not verify["valid"]:
        raise HTTPException(400, f"Meta credential validation failed: {verify.get('error', 'Unknown error')}")

    now = datetime.now(timezone.utc).isoformat()

    # Update whatsapp_config in user_integrations
    await db.user_integrations.update_one(
        {"tenant_id": tenant_id},
        {"$set": {
            "whatsapp_config.whatsapp_mode": "meta_cloud",
            "whatsapp_config.meta_phone_number_id": body.phone_number_id,
            "whatsapp_config.meta_waba_id": body.waba_id,
            "whatsapp_config.meta_access_token": body.access_token,
            "whatsapp_config.whatsapp_connected": True,
            "whatsapp_config.whatsapp_connected_at": now,
            "whatsapp_config.phone_number": verify.get("phone_display_name", ""),
            "whatsapp_config.provider": "meta_cloud",
        }},
        upsert=True,
    )

    logger.info(f"[WhatsApp] Meta Cloud connected for tenant {tenant_id}")

    return {
        "success": True,
        "mode": "meta_cloud",
        "phone_display_name": verify.get("phone_display_name", ""),
        "connected_at": now,
        "message": "Meta Cloud API connected — permanent, never expires.",
    }


# ═══════════════════════════════════════════════════════════
# Connect WHAPI (Quick Start / Fallback)
# ═══════════════════════════════════════════════════════════

@router.post("/{tenant_id}/whatsapp/connect-whapi")
async def connect_whapi(tenant_id: str, body: WhapiConnectRequest, authorization: str = Header(None)):
    """
    Connect WHAPI (session-based — may expire on phone restart).
    Validates token before saving.
    """
    await _auth(authorization)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not available")

    from services.whatsapp_engine import WhatsAppEngine
    engine = WhatsAppEngine(db)

    # Validate token
    verify = await engine.verify_whapi_token(body.whapi_token)
    if not verify["valid"]:
        raise HTTPException(400, f"WHAPI token validation failed: {verify.get('error', 'Unknown error')}")

    now = datetime.now(timezone.utc).isoformat()

    await db.user_integrations.update_one(
        {"tenant_id": tenant_id},
        {"$set": {
            "whatsapp_config.whatsapp_mode": "whapi",
            "whatsapp_config.whapi_token": body.whapi_token,
            "whatsapp_config.whatsapp_connected": True,
            "whatsapp_config.whatsapp_connected_at": now,
            "whatsapp_config.phone_number": verify.get("phone", ""),
            "whatsapp_config.provider": "whapi",
        }},
        upsert=True,
    )

    logger.info(f"[WhatsApp] WHAPI connected for tenant {tenant_id}")

    return {
        "success": True,
        "mode": "whapi",
        "phone": verify.get("phone", ""),
        "name": verify.get("name", ""),
        "connected_at": now,
        "message": "WHAPI connected — session-based. May expire if phone restarts.",
    }


# ═══════════════════════════════════════════════════════════
# Status
# ═══════════════════════════════════════════════════════════

@router.get("/{tenant_id}/whatsapp/status")
async def whatsapp_status(tenant_id: str, authorization: str = Header(None)):
    """Get WhatsApp connection status for a tenant."""
    await _auth(authorization)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not available")

    from services.whatsapp_engine import WhatsAppEngine
    engine = WhatsAppEngine(db)
    return await engine.get_status(tenant_id)


# ═══════════════════════════════════════════════════════════
# Send Test Message
# ═══════════════════════════════════════════════════════════

@router.post("/{tenant_id}/whatsapp/send-test")
async def send_test_message(tenant_id: str, body: SendTestRequest, authorization: str = Header(None)):
    """Send a test WhatsApp message via the hybrid engine."""
    await _auth(authorization)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not available")

    from services.whatsapp_engine import WhatsAppEngine
    engine = WhatsAppEngine(db)
    result = await engine.send_message(tenant_id, body.to, body.message)
    return result


# ═══════════════════════════════════════════════════════════
# Disconnect
# ═══════════════════════════════════════════════════════════

@router.post("/{tenant_id}/whatsapp/disconnect")
async def disconnect_whatsapp(tenant_id: str, authorization: str = Header(None)):
    """Disconnect WhatsApp for a tenant."""
    await _auth(authorization)
    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not available")

    await db.user_integrations.update_one(
        {"tenant_id": tenant_id},
        {"$set": {
            "whatsapp_config.whatsapp_mode": "not_connected",
            "whatsapp_config.whatsapp_connected": False,
            "whatsapp_config.meta_phone_number_id": "",
            "whatsapp_config.meta_waba_id": "",
            "whatsapp_config.meta_access_token": "",
            "whatsapp_config.whapi_token": "",
        }}
    )

    return {"success": True, "message": "WhatsApp disconnected"}
