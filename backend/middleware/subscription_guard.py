"""
AUREM Subscription Guard Middleware
Gates API access based on subscription tier
"""

from fastapi import Request, HTTPException
from typing import Callable
import logging

logger = logging.getLogger(__name__)


class SubscriptionGuard:
    """
    Middleware to enforce subscription-based access control
    
    Usage:
        @app.middleware("http")
        async def subscription_guard_middleware(request: Request, call_next):
            guard = SubscriptionGuard(db)
            return await guard.process_request(request, call_next)
    """
    
    def __init__(self, db=None):
        self.db = db
        
        # Define which endpoints require which features
        self.endpoint_features = {
            "/api/premium/followup": "followup_engine",
            "/api/premium/handoff": "whatsapp",
            "/api/premium/multimodal": "multimodal",
            "/api/aurem/voice": "voice",
            "/api/business": "whatsapp",  # Basic
        }
        
        # Endpoints that are always free
        self.free_endpoints = [
            "/api/platform/auth",
            "/api/subscription",
            "/api/system/health",
            "/docs",
            "/openapi.json",
            "/",
            "/platform"
        ]
    
    async def process_request(self, request: Request, call_next: Callable):
        """Process incoming request and check subscription"""
        
        # Skip guard for free endpoints
        if any(request.url.path.startswith(endpoint) for endpoint in self.free_endpoints):
            return await call_next(request)
        
        # Skip guard for OPTIONS requests (CORS)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Get user from request (simplified - should decode JWT)
        user_id = self._get_user_from_request(request)
        
        if not user_id:
            # No user ID - proceed (will be caught by auth middleware)
            return await call_next(request)
        
        # Check subscription access
        allowed = await self._check_access(user_id, request.url.path)
        
        if not allowed["allowed"]:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Subscription required",
                    "message": allowed["reason"],
                    "upgrade_to": allowed.get("upgrade_to"),
                    "current_tier": allowed.get("tier")
                }
            )
        
        # Check usage limits for certain operations
        if request.method in ["POST", "PUT", "DELETE"]:
            limit_ok = await self._check_limits(user_id, request.url.path)
            
            if not limit_ok["allowed"]:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Usage limit reached",
                        "message": limit_ok["reason"],
                        "current": limit_ok.get("current"),
                        "limit": limit_ok.get("limit"),
                        "upgrade_required": True
                    }
                )
        
        # Proceed with request
        response = await call_next(request)
        
        # Increment usage counter after successful request
        if response.status_code < 400:
            await self._increment_usage(user_id, request.url.path)
        
        return response
    
    def _get_user_from_request(self, request: Request) -> str:
        """Extract user ID from request"""
        # Get from Authorization header (simplified)
        auth_header = request.headers.get("authorization", "")
        
        if auth_header.startswith("Bearer "):
            # TODO: Decode JWT and get real user_id
            # For now, return dummy user
            return "admin"
        
        return None
    
    async def _check_access(self, user_id: str, path: str) -> dict:
        """Check if user has access to this endpoint"""
        from services.subscription_manager import get_subscription_manager, FeatureAccess
        
        manager = get_subscription_manager(self.db)
        
        # Determine required feature for this endpoint
        required_feature = None
        for endpoint_prefix, feature in self.endpoint_features.items():
            if path.startswith(endpoint_prefix):
                required_feature = feature
                break
        
        if not required_feature:
            # No specific feature required
            return {"allowed": True}
        
        # Check feature access
        try:
            feature_enum = FeatureAccess(required_feature)
            access = await manager.check_feature_access(user_id, feature_enum)
            return access
        except:
            return {"allowed": True}  # Fail open for unknown features
    
    async def _check_limits(self, user_id: str, path: str) -> dict:
        """Check usage limits"""
        from services.subscription_manager import get_subscription_manager
        
        manager = get_subscription_manager(self.db)
        
        # Determine resource being used
        resource = "api_calls"
        
        if "/followup" in path:
            resource = "followups"
        elif "/voice" in path:
            resource = "voice_minutes"
        elif any(x in path for x in ["/whatsapp", "/email", "/sms"]):
            resource = "messages"
        
        limit_check = await manager.check_usage_limit(user_id, resource)
        return limit_check
    
    async def _increment_usage(self, user_id: str, path: str):
        """Increment usage counter"""
        from services.subscription_manager import get_subscription_manager
        
        manager = get_subscription_manager(self.db)
        
        # Determine resource
        resource = "api_calls"
        amount = 1
        
        if "/followup/run" in path:
            resource = "followups"
        elif "/voice/call" in path:
            resource = "voice_minutes"
            amount = 1  # Will be updated based on call duration
        elif any(x in path for x in ["/whatsapp", "/email", "/sms"]):
            resource = "messages"
        
        await manager.increment_usage(user_id, resource, amount)


def create_subscription_guard(db):
    """Factory function to create subscription guard"""
    return SubscriptionGuard(db)
