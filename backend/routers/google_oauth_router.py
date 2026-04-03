"""
AUREM Commercial Platform - Google OAuth Router
Handles OAuth 2.0 flow for connecting Gmail accounts

Endpoints:
- GET /api/oauth/gmail/authorize - Start OAuth flow
- GET /api/oauth/gmail/callback - Handle OAuth callback
- GET /api/oauth/gmail/status/{business_id} - Check connection status
- DELETE /api/oauth/gmail/disconnect/{business_id} - Disconnect Gmail
"""

import os
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import warnings

router = APIRouter(prefix="/api/oauth/gmail", tags=["AUREM Gmail OAuth"])

logger = logging.getLogger(__name__)

# Database reference
_db = None

# OAuth configuration
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

# Redirect URI will be set dynamically based on request
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "")

# Gmail scopes
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.labels",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
]

# State storage (temporary - should be Redis in production)
_oauth_states = {}


def set_db(db):
    """Set database reference"""
    global _db
    _db = db


def get_db():
    """Get database reference"""
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


def _get_flow(redirect_uri: str) -> Flow:
    """Create OAuth flow with client config"""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            400, 
            "Gmail integration not configured. Please add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to environment."
        )
    
    return Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=GMAIL_SCOPES,
        redirect_uri=redirect_uri
    )


# ==================== MODELS ====================

class OAuthStatusResponse(BaseModel):
    business_id: str
    connected: bool
    email: Optional[str] = None
    scopes: list = []
    connected_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    status: str = "disconnected"


# ==================== ENDPOINTS ====================

@router.get("/authorize")
async def start_oauth(
    request: Request,
    business_id: str = Query(..., description="Business workspace ID"),
    redirect_url: Optional[str] = Query(None, description="URL to redirect after OAuth")
):
    """
    Start the Gmail OAuth flow.
    
    Args:
        business_id: The business workspace to connect Gmail to
        redirect_url: Where to redirect after successful connection (frontend URL)
        
    Returns:
        Redirect to Google OAuth consent screen
    """
    from services.aurem_commercial import get_workspace_service
    
    db = get_db()
    workspace_service = get_workspace_service(db)
    
    # Verify business exists
    workspace = await workspace_service.get_workspace(business_id)
    if not workspace:
        raise HTTPException(404, "Business workspace not found")
    
    # Build redirect URI
    scheme = request.headers.get("x-forwarded-proto", "https")
    host = request.headers.get("host", "")
    
    # Use BASE_URL if available (production), otherwise construct from request
    if BASE_URL:
        callback_uri = f"{BASE_URL}/api/oauth/gmail/callback"
    else:
        callback_uri = f"{scheme}://{host}/api/oauth/gmail/callback"
    
    logger.info(f"[OAuth] Starting flow for {business_id}, callback: {callback_uri}")
    
    # Create flow
    flow = _get_flow(callback_uri)
    
    # Generate state with business_id and redirect encoded
    state = secrets.token_urlsafe(32)
    
    # Store state mapping (with 10 min expiry)
    _oauth_states[state] = {
        "business_id": business_id,
        "redirect_url": redirect_url or "/aurem-ai",
        "created_at": datetime.now(timezone.utc),
        "callback_uri": callback_uri
    }
    
    # Clean up old states
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    expired = [k for k, v in _oauth_states.items() if v["created_at"] < cutoff]
    for k in expired:
        del _oauth_states[k]
    
    # Generate authorization URL
    authorization_url, _ = flow.authorization_url(
        access_type='offline',  # Required for refresh token
        prompt='consent',       # Always show consent to get refresh token
        state=state,
        include_granted_scopes='true'
    )
    
    return RedirectResponse(authorization_url)


@router.get("/callback")
async def oauth_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    error: Optional[str] = Query(None)
):
    """
    Handle OAuth callback from Google.
    
    Args:
        code: Authorization code from Google
        state: State parameter for CSRF protection
        error: Error message if authorization failed
        
    Returns:
        Redirect to frontend with success/error status
    """
    from services.aurem_commercial import get_token_vault, IntegrationProvider
    from services.aurem_commercial import get_audit_logger, AuditAction
    
    # Handle error
    if error:
        logger.error(f"[OAuth] Google returned error: {error}")
        return RedirectResponse(f"/aurem-ai?gmail_error={error}")
    
    # Verify state
    if state not in _oauth_states:
        logger.error("[OAuth] Invalid state token")
        return RedirectResponse("/aurem-ai?gmail_error=invalid_state")
    
    state_data = _oauth_states.pop(state)
    business_id = state_data["business_id"]
    redirect_url = state_data["redirect_url"]
    callback_uri = state_data["callback_uri"]
    
    db = get_db()
    token_vault = get_token_vault(db)
    audit_logger = get_audit_logger(db)
    ip_address = request.client.host if request.client else None
    
    try:
        # Create flow with same redirect URI
        flow = _get_flow(callback_uri)
        
        # Exchange code for tokens
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # Ignore scope order warnings
            flow.fetch_token(code=code)
        
        creds = flow.credentials
        
        # Get user info
        from googleapiclient.discovery import build
        
        oauth2_service = build('oauth2', 'v2', credentials=creds)
        user_info = oauth2_service.userinfo().get().execute()
        
        gmail_email = user_info.get("email")
        
        # Calculate expiry
        expires_at = None
        if creds.expiry:
            expires_at = creds.expiry
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        # Store credentials in vault
        await token_vault.store_integration(
            business_id=business_id,
            provider=IntegrationProvider.GOOGLE,
            credentials={
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET
            },
            metadata={
                "email": gmail_email,
                "name": user_info.get("name"),
                "picture": user_info.get("picture")
            },
            scopes=list(creds.scopes) if creds.scopes else GMAIL_SCOPES,
            expires_at=expires_at,
            ip_address=ip_address
        )
        
        # Audit log
        await audit_logger.log(
            action=AuditAction.INTEGRATION_CONNECTED,
            business_id=business_id,
            actor_type="user",
            resource_type="gmail",
            details={
                "email": gmail_email,
                "has_refresh_token": bool(creds.refresh_token)
            },
            ip_address=ip_address,
            success=True
        )
        
        logger.info(f"[OAuth] Gmail connected for {business_id}: {gmail_email}")
        
        # Redirect to frontend with success
        return RedirectResponse(f"{redirect_url}?gmail_connected=true&email={gmail_email}")
        
    except Exception as e:
        logger.error(f"[OAuth] Token exchange failed: {e}")
        
        await audit_logger.log(
            action=AuditAction.INTEGRATION_ERROR,
            business_id=business_id,
            actor_type="user",
            resource_type="gmail",
            details={"error": str(e)},
            ip_address=ip_address,
            success=False,
            error_message=str(e)
        )
        
        return RedirectResponse(f"{redirect_url}?gmail_error=token_exchange_failed")


@router.get("/status/{business_id}", response_model=OAuthStatusResponse)
async def get_gmail_status(business_id: str, request: Request):
    """
    Check Gmail connection status for a business.
    
    Args:
        business_id: The business workspace ID
        
    Returns:
        Connection status including email and expiry info
    """
    from services.aurem_commercial import get_token_vault, IntegrationProvider
    
    db = get_db()
    token_vault = get_token_vault(db)
    ip_address = request.client.host if request.client else None
    
    # Get integration without decrypting credentials (just metadata)
    integrations = await token_vault.get_all_integrations(business_id)
    
    gmail_integration = None
    for integration in integrations:
        if integration.get("provider") == IntegrationProvider.GOOGLE.value:
            gmail_integration = integration
            break
    
    if not gmail_integration:
        return OAuthStatusResponse(
            business_id=business_id,
            connected=False,
            status="disconnected"
        )
    
    return OAuthStatusResponse(
        business_id=business_id,
        connected=gmail_integration.get("status") == "active",
        email=gmail_integration.get("metadata", {}).get("email"),
        scopes=gmail_integration.get("scopes", []),
        connected_at=gmail_integration.get("connected_at"),
        expires_at=gmail_integration.get("expires_at"),
        status=gmail_integration.get("status", "unknown")
    )


@router.delete("/disconnect/{business_id}")
async def disconnect_gmail(business_id: str, request: Request):
    """
    Disconnect Gmail from a business workspace.
    
    Args:
        business_id: The business workspace ID
        
    Returns:
        Success status
    """
    from services.aurem_commercial import get_token_vault, IntegrationProvider
    
    db = get_db()
    token_vault = get_token_vault(db)
    ip_address = request.client.host if request.client else None
    
    success = await token_vault.revoke_integration(
        business_id=business_id,
        provider=IntegrationProvider.GOOGLE,
        ip_address=ip_address,
        reason="user_requested"
    )
    
    if not success:
        raise HTTPException(404, "Gmail not connected")
    
    logger.info(f"[OAuth] Gmail disconnected for {business_id}")
    
    return {"success": True, "message": "Gmail disconnected successfully"}


@router.get("/health")
async def health_check():
    """Health check for Gmail OAuth service"""
    configured = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
    
    return {
        "status": "healthy" if configured else "not_configured",
        "google_oauth_configured": configured,
        "message": "Gmail OAuth ready" if configured else "Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET"
    }
