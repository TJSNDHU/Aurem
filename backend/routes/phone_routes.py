"""
Global Phone Number Admin Routes
═══════════════════════════════════════════════════════════════════
Admin API endpoints for managing global phone numbers via Telnyx.

Features:
- Provision phone numbers in 13+ countries
- List all numbers with cost breakdown
- Release/delete numbers
- TeXML webhook for inbound calls

Requires TELNYX_API_KEY for real provisioning (mocks without it).
═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

import os
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Header, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/phone", tags=["Phone Management"])

# Database reference
_db = None


def set_db(database):
    """Set database reference from server.py startup."""
    global _db
    _db = database
    
    # Also set for phone manager
    from utils.phone_manager import set_db as set_phone_db
    set_phone_db(database)
    
    logger.info("Phone routes: Database reference set")


# ═══════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════

class ProvisionRequest(BaseModel):
    """Request to provision a new phone number."""
    country_code: str  # ISO 2-letter code: CA, US, GB, etc.
    tenant_id: str = "reroots"


class ReleaseRequest(BaseModel):
    """Request to release a phone number."""
    phone_number: str
    tenant_id: str = "reroots"


# ═══════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@router.get("/countries")
async def get_supported_countries():
    """
    Get list of supported countries for phone provisioning.
    
    Returns country codes, names, languages, and monthly costs.
    """
    from utils.phone_manager import get_supported_countries
    
    countries = get_supported_countries()
    
    return {
        "success": True,
        "count": len(countries),
        "countries": countries,
        "telnyx_configured": bool(os.environ.get("TELNYX_API_KEY"))
    }


@router.post("/provision")
async def provision_phone_number(
    request: Request,
    body: ProvisionRequest
):
    """
    Provision a new phone number in the specified country.
    
    When TELNYX_API_KEY is configured, provisions a real number.
    Without the key, returns a mock number for testing.
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    from utils.phone_manager import provision_number
    
    result = await provision_number(
        country_code=body.country_code,
        tenant_id=body.tenant_id
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Provisioning failed"))
    
    logger.info(f"[PHONE] Provisioned number in {body.country_code} for {body.tenant_id}")
    
    return result


@router.get("/numbers")
async def list_phone_numbers(
    request: Request,
    tenant_id: str = "reroots"
):
    """
    List all phone numbers for a tenant.
    
    Returns numbers grouped by country with cost breakdown.
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    from utils.phone_manager import list_numbers
    
    result = await list_numbers(tenant_id=tenant_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to list numbers"))
    
    return result


@router.delete("/release")
async def release_phone_number(
    request: Request,
    body: ReleaseRequest
):
    """
    Release/delete a phone number.
    
    Removes from both Telnyx and local database.
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    from utils.phone_manager import release_number
    
    result = await release_number(
        phone_number=body.phone_number,
        tenant_id=body.tenant_id
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Release failed"))
    
    logger.info(f"[PHONE] Released number {body.phone_number}")
    
    return result


# ═══════════════════════════════════════════════════════════════════
# TEXML WEBHOOK FOR INBOUND CALLS
# ═══════════════════════════════════════════════════════════════════

@router.post("/texml/inbound")
async def texml_inbound_webhook(request: Request):
    """
    TeXML webhook for inbound voice calls.
    
    Telnyx calls this when a call comes in to a provisioned number.
    Returns TeXML with language-aware greeting and WebSocket connection.
    """
    try:
        # Parse Telnyx webhook payload
        body = await request.json()
        
        # Extract caller info
        caller_number = body.get("data", {}).get("payload", {}).get("from", "")
        called_number = body.get("data", {}).get("payload", {}).get("to", "")
        call_control_id = body.get("data", {}).get("payload", {}).get("call_control_id", "")
        
        logger.info(f"[TEXML] Inbound call from {caller_number} to {called_number}")
        
        # Detect caller's country
        from utils.phone_manager import detect_country_from_number, generate_texml_response
        
        caller_country = detect_country_from_number(caller_number)
        
        # Build voice agent WebSocket URL
        host = request.headers.get("host", "localhost:8001")
        protocol = "wss" if "https" in str(request.url) else "ws"
        voice_ws_url = f"{protocol}://{host}/api/voice/ws/{call_control_id}?phone={caller_number}"
        
        # Generate TeXML response
        texml = generate_texml_response(
            caller_country=caller_country,
            voice_agent_ws_url=voice_ws_url,
            brand_name="Reroots"
        )
        
        return Response(content=texml, media_type="application/xml")
        
    except Exception as e:
        logger.error(f"[TEXML] Webhook error: {e}")
        
        # Return fallback English greeting
        fallback_texml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">Hello! I'm the Reroots AI assistant. How can I help you with your skincare today?</Say>
    <Hangup />
</Response>"""
        
        return Response(content=fallback_texml, media_type="application/xml")


@router.get("/health")
async def phone_health():
    """Health check for phone management service."""
    return {
        "status": "ok",
        "service": "phone-management",
        "telnyx_configured": bool(os.environ.get("TELNYX_API_KEY")),
        "mode": "live" if os.environ.get("TELNYX_API_KEY") else "mock"
    }
