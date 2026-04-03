"""
AUREM MCP Server
Model Context Protocol implementation for AUREM AI

Exposes AUREM services as MCP tools that any LLM can call:
- Get subscription data
- Check usage limits
- Query formulas
- Access service registry
- View analytics

Based on: FastMCP (Python SDK)
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import logging

try:
    from mcp.server.fastmcp import FastMCP
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logging.warning("[AUREM MCP] FastMCP not installed. Run: pip install mcp")

from services.toon_service import get_toon_service

logger = logging.getLogger(__name__)

# Initialize MCP server
if MCP_AVAILABLE:
    mcp = FastMCP("AUREM AI")
else:
    mcp = None


# ═══════════════════════════════════════════════════════════════════════════════
# MCP TOOLS - Expose AUREM data to LLMs
# ═══════════════════════════════════════════════════════════════════════════════

if MCP_AVAILABLE:
    
    @mcp.tool()
    async def get_subscription_plans() -> str:
        """
        Get all AUREM subscription plans
        
        Returns TOON-formatted data showing:
        - Plan names and prices
        - Feature limits
        - Available services
        """
        toon_service = get_toon_service()
        try:
            return await toon_service.get_subscription_plans_toon()
        except Exception as e:
            return f"Error: {str(e)}"
    
    
    @mcp.tool()
    async def get_user_subscription(user_id: str) -> str:
        """
        Get specific user's subscription details
        
        Args:
            user_id: User ID to look up
        
        Returns TOON-formatted data showing:
        - Current tier
        - Usage (tokens, formulas, content)
        - Active services
        - Billing period
        """
        toon_service = get_toon_service()
        try:
            return await toon_service.get_user_subscription_toon(user_id)
        except Exception as e:
            return f"Error: {str(e)}"
    
    
    @mcp.tool()
    async def get_service_registry() -> str:
        """
        Get all available third-party services
        
        Returns TOON-formatted data showing:
        - Service names and categories
        - Pricing per 1k tokens/minute/image
        - Status (active, no_keys, paused)
        - Available in which tiers
        """
        toon_service = get_toon_service()
        try:
            return await toon_service.get_service_registry_toon()
        except Exception as e:
            return f"Error: {str(e)}"
    
    
    @mcp.tool()
    async def get_usage_analytics(
        user_id: Optional[str] = None,
        service_id: Optional[str] = None,
        limit: int = 50
    ) -> str:
        """
        Get usage logs and analytics
        
        Args:
            user_id: Filter by user (optional)
            service_id: Filter by service (optional)
            limit: Max results (default 50)
        
        Returns TOON-formatted usage logs showing:
        - User, service, tokens used, cost
        - Endpoint called
        - Timestamp
        """
        toon_service = get_toon_service()
        try:
            return await toon_service.get_usage_analytics_toon(user_id, service_id, limit)
        except Exception as e:
            return f"Error: {str(e)}"
    
    
    @mcp.tool()
    async def check_usage_limit(user_id: str, resource_type: str) -> Dict[str, Any]:
        """
        Check if user can perform an action (rate limiting)
        
        Args:
            user_id: User ID to check
            resource_type: Type of resource (ai_tokens, formulas, content, workflows, videos)
        
        Returns:
            Dictionary with:
            - allowed: boolean
            - current: current usage
            - limit: max allowed
            - remaining: how many left
            - message: human-readable status
        """
        # This would integrate with subscription checking
        # For now, return mock data
        return {
            "allowed": True,
            "current": 15000,
            "limit": 50000,
            "remaining": 35000,
            "message": f"35,000 {resource_type} remaining"
        }
    
    
    @mcp.tool()
    async def get_admin_dashboard() -> str:
        """
        Get admin dashboard metrics
        
        Returns TOON-formatted dashboard showing:
        - Total active subscriptions
        - MRR/ARR
        - Service statuses
        - Top users by usage
        """
        toon_service = get_toon_service()
        try:
            return await toon_service.get_admin_dashboard_toon()
        except Exception as e:
            return f"Error: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════════
# MCP RESOURCES - Expose AUREM data as resources
# ═══════════════════════════════════════════════════════════════════════════════

if MCP_AVAILABLE:
    
    @mcp.resource("aurem://plans")
    async def plans_resource() -> str:
        """Resource: All subscription plans"""
        return await get_subscription_plans()
    
    
    @mcp.resource("aurem://services")
    async def services_resource() -> str:
        """Resource: Service registry"""
        return await get_service_registry()


# ═══════════════════════════════════════════════════════════════════════════════
# SERVER STARTUP
# ═══════════════════════════════════════════════════════════════════════════════

def start_mcp_server():
    """Start the MCP server (stdio mode)"""
    if not MCP_AVAILABLE:
        logger.error("[AUREM MCP] FastMCP not installed. Cannot start MCP server.")
        return
    
    logger.info("[AUREM MCP] Starting MCP server...")
    mcp.run()


if __name__ == "__main__":
    start_mcp_server()
