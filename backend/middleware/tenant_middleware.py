"""
Multi-Tenancy Middleware
Automatically extracts tenant_id from JWT and sets TenantContext
"""

import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import jwt
import os

from services.multi_tenancy_service import TenantContext

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET", "aurem-platform-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract tenant_id from JWT and set TenantContext
    
    This runs on EVERY request before the endpoint handler
    """
    
    async def dispatch(self, request: Request, call_next):
        # Clear previous tenant context
        TenantContext.clear_tenant()
        
        try:
            # Extract JWT token from Authorization header
            auth_header = request.headers.get("Authorization", "")
            
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                
                try:
                    # Decode JWT
                    payload = jwt.decode(
                        token, 
                        JWT_SECRET, 
                        algorithms=[JWT_ALGORITHM],
                        options={"verify_exp": False}  # Allow expired tokens for tenant extraction
                    )
                    
                    # Extract tenant_id (multiple fallback strategies)
                    tenant_id = None
                    
                    # Strategy 1: Explicit tenant_id in JWT
                    if "tenant_id" in payload:
                        tenant_id = payload["tenant_id"]
                    
                    # Strategy 2: Company_id in JWT
                    elif "company_id" in payload:
                        tenant_id = payload["company_id"]
                    
                    # Strategy 3: Derive from user_id (for admin)
                    elif payload.get("user_id") == "admin":
                        tenant_id = "aurem_platform"
                    
                    # Strategy 4: Derive from email domain
                    elif "email" in payload:
                        email = payload["email"]
                        # Use email domain as tenant_id
                        domain = email.split("@")[1] if "@" in email else "default"
                        tenant_id = f"tenant_{domain.replace('.', '_')}"
                    
                    # Strategy 5: Default tenant for unknown cases
                    else:
                        tenant_id = "default_tenant"
                    
                    # Set tenant context for this request
                    TenantContext.set_tenant(tenant_id)
                    
                    logger.debug(f"[TenantMiddleware] Set tenant: {tenant_id}")
                
                except jwt.InvalidTokenError as e:
                    logger.warning(f"[TenantMiddleware] Invalid JWT: {e}")
                    # Don't fail the request - let auth middleware handle it
                    pass
        
        except Exception as e:
            logger.error(f"[TenantMiddleware] Error: {e}")
            # Don't fail requests on middleware errors
            pass
        
        # Process request
        response = await call_next(request)
        
        # Clear tenant context after request
        TenantContext.clear_tenant()
        
        return response
