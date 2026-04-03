"""
AUREM Commercial Platform - API Router
Endpoints for multi-tenant workspace management

Endpoints:
- POST /api/aurem-platform/workspaces - Create workspace
- GET /api/aurem-platform/workspaces/{id} - Get workspace
- PUT /api/aurem-platform/workspaces/{id}/settings - Update settings
- GET /api/aurem-platform/workspaces/{id}/usage - Get usage
- POST /api/aurem-platform/workspaces/{id}/integrations - Store integration
- GET /api/aurem-platform/workspaces/{id}/integrations - List integrations
- DELETE /api/aurem-platform/workspaces/{id}/integrations/{provider} - Revoke
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

router = APIRouter(prefix="/api/aurem-platform", tags=["AUREM Platform"])

logger = logging.getLogger(__name__)

# Database reference (set by server.py)
_db = None


def set_db(db):
    """Set database reference"""
    global _db
    _db = db


def get_db():
    """Get database reference"""
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


# ==================== MODELS ====================

class CreateWorkspaceRequest(BaseModel):
    owner_email: EmailStr
    business_name: str = Field(..., min_length=2, max_length=100)
    business_type: Optional[str] = None
    timezone: str = "America/Toronto"


class UpdateSettingsRequest(BaseModel):
    ai_mode: Optional[str] = None  # auto, manual, supervised
    ai_personality: Optional[str] = None
    working_hours: Optional[Dict[str, Any]] = None
    auto_reply_delay_seconds: Optional[int] = None
    escalation_keywords: Optional[List[str]] = None
    language: Optional[str] = None


class UpdateAIContextRequest(BaseModel):
    business_description: Optional[str] = None
    services: Optional[List[str]] = None
    faq: Optional[List[Dict[str, str]]] = None
    tone: Optional[str] = None
    prohibited_topics: Optional[List[str]] = None
    custom_instructions: Optional[str] = None


class StoreIntegrationRequest(BaseModel):
    provider: str  # google, meta, shopify, etc.
    credentials: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    scopes: Optional[List[str]] = None
    expires_at: Optional[datetime] = None


class WorkspaceResponse(BaseModel):
    business_id: str
    business_name: str
    status: str
    plan: str
    created_at: datetime


class UsageResponse(BaseModel):
    business_id: str
    billing_period: str
    plan: str
    included_messages: int
    usage: Dict[str, int]
    quota_remaining: int
    quota_exceeded: bool
    overage_messages: int
    overage_cost: float


# ==================== ENDPOINTS ====================

@router.post("/workspaces", response_model=WorkspaceResponse)
async def create_workspace(request: CreateWorkspaceRequest, req: Request):
    """
    Create a new customer workspace.
    Starts with TRIAL plan (50 AI messages).
    """
    from services.aurem_commercial import (
        get_workspace_service,
        get_consent_tracker,
        SubscriptionPlan
    )
    
    db = get_db()
    workspace_service = get_workspace_service(db)
    consent_tracker = get_consent_tracker(db)
    
    # Check if email already has a workspace
    existing = await workspace_service.get_workspace_by_email(request.owner_email)
    if existing:
        raise HTTPException(400, "Email already has a workspace")
    
    # Get client IP
    ip_address = req.client.host if req.client else None
    user_agent = req.headers.get("user-agent")
    
    # Create workspace
    workspace = await workspace_service.create_workspace(
        owner_email=request.owner_email,
        business_name=request.business_name,
        business_type=request.business_type,
        timezone=request.timezone,
        plan=SubscriptionPlan.TRIAL,
        ip_address=ip_address
    )
    
    # Record signup consents
    await consent_tracker.record_business_signup_consent(
        business_id=workspace["business_id"],
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    return WorkspaceResponse(
        business_id=workspace["business_id"],
        business_name=workspace["business_name"],
        status=workspace["status"],
        plan=workspace["plan"],
        created_at=workspace["created_at"]
    )


@router.get("/workspaces/{business_id}")
async def get_workspace(business_id: str):
    """Get workspace details"""
    from services.aurem_commercial import get_workspace_service
    
    db = get_db()
    workspace_service = get_workspace_service(db)
    
    workspace = await workspace_service.get_workspace(business_id)
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    
    # Remove sensitive fields
    workspace.pop("_id", None)
    
    return workspace


@router.put("/workspaces/{business_id}/settings")
async def update_workspace_settings(
    business_id: str, 
    request: UpdateSettingsRequest,
    req: Request
):
    """Update workspace settings"""
    from services.aurem_commercial import get_workspace_service
    
    db = get_db()
    workspace_service = get_workspace_service(db)
    
    # Get current workspace
    workspace = await workspace_service.get_workspace(business_id)
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    
    # Merge with existing settings
    current_settings = workspace.get("settings", {})
    update_data = request.dict(exclude_none=True)
    
    for key, value in update_data.items():
        current_settings[key] = value
    
    success = await workspace_service.update_settings(
        business_id=business_id,
        settings=current_settings
    )
    
    if not success:
        raise HTTPException(500, "Failed to update settings")
    
    return {"success": True, "settings": current_settings}


@router.put("/workspaces/{business_id}/ai-context")
async def update_ai_context(
    business_id: str,
    request: UpdateAIContextRequest
):
    """Update AI context for the business"""
    from services.aurem_commercial import get_workspace_service
    
    db = get_db()
    workspace_service = get_workspace_service(db)
    
    workspace = await workspace_service.get_workspace(business_id)
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    
    # Merge with existing context
    current_context = workspace.get("ai_context", {})
    update_data = request.dict(exclude_none=True)
    
    for key, value in update_data.items():
        current_context[key] = value
    
    success = await workspace_service.update_ai_context(
        business_id=business_id,
        ai_context=current_context
    )
    
    if not success:
        raise HTTPException(500, "Failed to update AI context")
    
    return {"success": True, "ai_context": current_context}


@router.get("/workspaces/{business_id}/usage", response_model=UsageResponse)
async def get_workspace_usage(business_id: str):
    """Get current usage for billing period"""
    from services.aurem_commercial import get_workspace_service
    
    db = get_db()
    workspace_service = get_workspace_service(db)
    
    workspace = await workspace_service.get_workspace(business_id)
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    
    usage = await workspace_service.get_current_usage(business_id)
    
    return UsageResponse(
        business_id=usage["business_id"],
        billing_period=usage["billing_period"],
        plan=usage["plan"],
        included_messages=usage["included_messages"],
        usage=usage.get("usage", {}),
        quota_remaining=usage.get("quota_remaining", 0),
        quota_exceeded=usage.get("quota_exceeded", False),
        overage_messages=usage.get("overage_messages", 0),
        overage_cost=usage.get("overage_cost", 0.0)
    )


@router.get("/workspaces/{business_id}/quota-check")
async def check_quota(business_id: str):
    """Check if business can send more AI messages"""
    from services.aurem_commercial import get_workspace_service
    
    db = get_db()
    workspace_service = get_workspace_service(db)
    
    result = await workspace_service.check_quota(business_id)
    return result


@router.get("/workspaces/{business_id}/system-prompt")
async def get_system_prompt(business_id: str):
    """Get the AI system prompt for this business"""
    from services.aurem_commercial import get_workspace_service
    
    db = get_db()
    workspace_service = get_workspace_service(db)
    
    workspace = await workspace_service.get_workspace(business_id)
    if not workspace:
        raise HTTPException(404, "Workspace not found")
    
    prompt = workspace_service.build_system_prompt(workspace)
    
    return {
        "business_id": business_id,
        "business_name": workspace.get("business_name"),
        "system_prompt": prompt
    }


# ==================== INTEGRATIONS ====================

@router.post("/workspaces/{business_id}/integrations")
async def store_integration(
    business_id: str,
    request: StoreIntegrationRequest,
    req: Request
):
    """Store integration credentials (encrypted)"""
    from services.aurem_commercial import get_token_vault, IntegrationProvider
    
    db = get_db()
    token_vault = get_token_vault(db)
    
    # Validate provider
    try:
        provider = IntegrationProvider(request.provider)
    except ValueError:
        raise HTTPException(400, f"Invalid provider: {request.provider}")
    
    ip_address = req.client.host if req.client else None
    
    doc_id = await token_vault.store_integration(
        business_id=business_id,
        provider=provider,
        credentials=request.credentials,
        metadata=request.metadata,
        scopes=request.scopes,
        expires_at=request.expires_at,
        ip_address=ip_address
    )
    
    return {
        "success": True,
        "integration_id": doc_id,
        "provider": request.provider
    }


@router.get("/workspaces/{business_id}/integrations")
async def list_integrations(business_id: str):
    """List all integrations for a workspace (no credentials returned)"""
    from services.aurem_commercial import get_token_vault
    
    db = get_db()
    token_vault = get_token_vault(db)
    
    integrations = await token_vault.get_all_integrations(business_id)
    
    return {
        "business_id": business_id,
        "integrations": integrations
    }


@router.delete("/workspaces/{business_id}/integrations/{provider}")
async def revoke_integration(
    business_id: str,
    provider: str,
    req: Request
):
    """Revoke an integration"""
    from services.aurem_commercial import get_token_vault, IntegrationProvider
    
    db = get_db()
    token_vault = get_token_vault(db)
    
    try:
        provider_enum = IntegrationProvider(provider)
    except ValueError:
        raise HTTPException(400, f"Invalid provider: {provider}")
    
    ip_address = req.client.host if req.client else None
    
    success = await token_vault.revoke_integration(
        business_id=business_id,
        provider=provider_enum,
        ip_address=ip_address,
        reason="user_requested"
    )
    
    if not success:
        raise HTTPException(404, f"Integration not found: {provider}")
    
    return {"success": True, "provider": provider}


# ==================== AUDIT LOGS ====================

@router.get("/workspaces/{business_id}/audit-logs")
async def get_audit_logs(
    business_id: str,
    action: Optional[str] = None,
    limit: int = 50,
    skip: int = 0
):
    """Get audit logs for a workspace"""
    from services.aurem_commercial import get_audit_logger, AuditAction
    
    db = get_db()
    audit_logger = get_audit_logger(db)
    
    action_enum = None
    if action:
        try:
            action_enum = AuditAction(action)
        except ValueError:
            pass  # Ignore invalid action filter
    
    logs = await audit_logger.get_logs(
        business_id=business_id,
        action=action_enum,
        limit=limit,
        skip=skip
    )
    
    return {
        "business_id": business_id,
        "logs": logs,
        "count": len(logs)
    }


# ==================== CONSENT ====================

@router.get("/workspaces/{business_id}/consent-status")
async def get_consent_status(business_id: str):
    """Check consent status for a workspace"""
    from services.aurem_commercial import get_consent_tracker
    
    db = get_db()
    consent_tracker = get_consent_tracker(db)
    
    status = await consent_tracker.check_required_consents(business_id)
    return status


# ==================== HEALTH ====================

@router.get("/health")
async def health_check():
    """Health check for AUREM Platform services"""
    from services.aurem_commercial import get_encryption_service
    
    # Test encryption
    enc = get_encryption_service()
    test_value = "test_health_check"
    encrypted = enc.encrypt(test_value)
    decrypted = enc.decrypt(encrypted)
    encryption_ok = decrypted == test_value
    
    return {
        "status": "healthy" if encryption_ok else "degraded",
        "services": {
            "encryption": "ok" if encryption_ok else "error",
            "database": "ok" if _db is not None else "not_initialized"
        },
        "version": "1.0.0"
    }
