"""
Multi-Tenant Provisioning Router — Client Integration Endpoints
================================================================
Per-client connection wizard: Email SMTP + WhatsApp QR + Activation Links
"""

import logging
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["Client Integrations"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.provisioning_service import set_db as set_prov_db
    set_prov_db(database)


async def _get_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        import jwt
        import os
        token = authorization.replace("Bearer ", "")
        return jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


class EmailConfigRequest(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str
    smtp_pass: str
    smtp_secure: bool = True
    from_name: str = ""
    from_email: str = ""


class ProvisionRequest(BaseModel):
    tenant_id: str
    email: str
    company_name: str = ""


# ═══ ADMIN: Provision new client ═══

@router.post("/provision")
async def provision_client(req: ProvisionRequest, authorization: str = Header(None)):
    """Admin: Create a new integration profile for a client."""
    from utils.require_auth import require_admin
    await require_admin(authorization=authorization)
    from services.provisioning_service import provision_client
    result = await provision_client(req.tenant_id, req.email, req.company_name)
    return result


# ═══ CLIENT: Get own integration status ═══

@router.get("/status/{tenant_id}")
async def get_integration_status(tenant_id: str, authorization: str = Header(None)):
    """Get a client's integration profile (email/WhatsApp status). Tenant-scoped."""
    user = await _get_user(authorization)
    from utils.require_auth import enforce_tenant_match
    enforce_tenant_match(user, tenant_id)
    from services.provisioning_service import get_client_integrations
    profile = await get_client_integrations(tenant_id)
    if not profile:
        return {"status": "not_provisioned", "message": "No integration profile found. Contact admin to set up your account."}
    # Redact sensitive fields
    safe = {**profile}
    if safe.get("email_config", {}).get("smtp_pass"):
        safe["email_config"]["smtp_pass"] = "****"
    return safe


# ═══ CLIENT: Configure Email ═══

@router.post("/email/configure/{tenant_id}")
async def configure_email(tenant_id: str, config: EmailConfigRequest, authorization: str = Header(None)):
    """Client: Set up SMTP email integration.

    Bug-fix 102 — was allowing any authenticated user to overwrite ANY
    tenant's SMTP creds (mail-server hijack via URL path tenant_id).
    Now enforces caller tenant_id == path tenant_id unless admin.
    """
    user = await _get_user(authorization)
    from utils.require_auth import enforce_tenant_match
    enforce_tenant_match(user, tenant_id)
    from services.provisioning_service import update_email_config
    result = await update_email_config(tenant_id, config.model_dump())
    return result


@router.post("/email/test/{tenant_id}")
async def test_email(tenant_id: str, authorization: str = Header(None)):
    """Client: Test SMTP connection. Bug-fix 102 — tenant-scoped."""
    user = await _get_user(authorization)
    from utils.require_auth import enforce_tenant_match
    enforce_tenant_match(user, tenant_id)
    from services.provisioning_service import test_email_connection
    return await test_email_connection(tenant_id)


# ═══ CLIENT: WhatsApp Setup ═══

@router.post("/whatsapp/init/{tenant_id}")
async def init_whatsapp(tenant_id: str, authorization: str = Header(None)):
    """Client: Initialize a WhatsApp QR session. Bug-fix 102 — tenant-scoped."""
    user = await _get_user(authorization)
    from utils.require_auth import enforce_tenant_match
    enforce_tenant_match(user, tenant_id)
    from services.provisioning_service import init_whatsapp_session
    return await init_whatsapp_session(tenant_id)


# ═══ ACTIVATION LINK ═══

@router.get("/activate/{token}")
async def activate_via_link(token: str):
    """
    Public endpoint: Client clicks their activation link.
    Returns their profile info so the frontend can show the wizard.
    """
    from services.provisioning_service import get_by_activation_token
    profile = await get_by_activation_token(token)
    if not profile:
        raise HTTPException(status_code=404, detail="Invalid or expired activation link")

    from datetime import datetime, timezone
    expires = profile.get("activation_expires", "")
    if expires and datetime.fromisoformat(expires) < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Activation link has expired")

    return {
        "tenant_id": profile["tenant_id"],
        "instance_id": profile["instance_id"],
        "company_name": profile.get("company_name", ""),
        "email_configured": profile.get("email_config", {}).get("verified", False),
        "whatsapp_connected": profile.get("whatsapp_config", {}).get("connected", False),
        "status": profile.get("status", "pending_activation"),
    }


# ═══ ADMIN: List all client integrations ═══

@router.get("/all")
async def list_all_integrations(authorization: str = Header(None)):
    """Admin: List all client integration profiles."""
    from utils.require_auth import require_admin
    await require_admin(authorization=authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not connected")

    profiles = await _db.user_integrations.find(
        {}, {"_id": 0, "email_config.smtp_pass": 0}
    ).to_list(length=100)
    return {"profiles": profiles, "total": len(profiles)}
