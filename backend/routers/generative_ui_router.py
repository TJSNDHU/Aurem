"""
Generative UI Router
API endpoints for dynamic component generation
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging

from services.generative_ui.component_generator import get_component_generator
from services.generative_ui.dashboard_service import get_dashboard_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/generative-ui",
    tags=["Generative UI"]
)

# MongoDB reference
_db = None


def set_db(database):
    global _db
    _db = database
    logger.info("[GenUI] Database set")


# Request Models
class ComponentRequest(BaseModel):
    component_type: str = Field(..., description="Type: line_chart, pie_chart, metric_card, data_table, form")
    data: Any = Field(..., description="Data to visualize")
    config: Optional[Dict] = Field(default=None, description="Optional configuration")


class DashboardRequest(BaseModel):
    components: List[Dict] = Field(..., description="List of component definitions")


# Endpoints

@router.get("/dashboards/subscription")
async def get_subscription_dashboard():
    """
    Generate subscription analytics dashboard
    
    Returns:
    - Total revenue (metric card)
    - Revenue trend (line chart)
    - Plan distribution (pie chart)
    - Recent subscriptions (table)
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        dashboard_service = get_dashboard_service(_db)
        dashboard = await dashboard_service.generate_subscription_dashboard()
        
        if not dashboard.get("success"):
            raise HTTPException(500, dashboard.get("error", "Dashboard generation failed"))
        
        return {
            "success": True,
            "dashboard": dashboard["dashboard"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GenUI] Subscription dashboard error: {e}")
        raise HTTPException(500, str(e))


@router.get("/dashboards/crypto-treasury")
async def get_crypto_treasury_dashboard():
    """
    Generate crypto treasury monitoring dashboard
    
    Returns:
    - Current profit (metric card)
    - Wallet balance (metric card)
    - Conversion history (line chart)
    - Recent transactions (table)
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        dashboard_service = get_dashboard_service(_db)
        dashboard = await dashboard_service.generate_crypto_treasury_dashboard()
        
        if not dashboard.get("success"):
            raise HTTPException(500, dashboard.get("error", "Dashboard generation failed"))
        
        return {
            "success": True,
            "dashboard": dashboard["dashboard"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GenUI] Crypto treasury dashboard error: {e}")
        raise HTTPException(500, str(e))


@router.get("/dashboards/hooks-performance")
async def get_hooks_performance_dashboard():
    """
    Generate hooks system performance dashboard
    
    Returns:
    - Total executions (metric card)
    - Active hooks (metric card)
    - Executions by hook (bar chart)
    - Hooks overview (table)
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        dashboard_service = get_dashboard_service(_db)
        dashboard = await dashboard_service.generate_hooks_performance_dashboard()
        
        if not dashboard.get("success"):
            raise HTTPException(500, dashboard.get("error", "Dashboard generation failed"))
        
        return {
            "success": True,
            "dashboard": dashboard["dashboard"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GenUI] Hooks performance dashboard error: {e}")
        raise HTTPException(500, str(e))


@router.get("/dashboards/agent-logs")
async def get_agent_logs_dashboard():
    """
    Generate agent execution logs dashboard
    
    Returns:
    - Total agents (metric card)
    - Recent executions (metric card)
    - Agent activity (bar chart)
    - Execution history (table)
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        dashboard_service = get_dashboard_service(_db)
        dashboard = await dashboard_service.generate_agent_logs_dashboard()
        
        if not dashboard.get("success"):
            raise HTTPException(500, dashboard.get("error", "Dashboard generation failed"))
        
        return {
            "success": True,
            "dashboard": dashboard["dashboard"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GenUI] Agent logs dashboard error: {e}")
        raise HTTPException(500, str(e))


@router.get("/dashboards/connector-stats")
async def get_connector_stats_dashboard():
    """
    Generate connector usage statistics dashboard
    
    Returns:
    - Total connectors (metric card)
    - API calls (metric card)
    - Usage by connector (pie chart)
    - Recent calls (table)
    """
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        dashboard_service = get_dashboard_service(_db)
        dashboard = await dashboard_service.generate_connector_stats_dashboard()
        
        if not dashboard.get("success"):
            raise HTTPException(500, dashboard.get("error", "Dashboard generation failed"))
        
        return {
            "success": True,
            "dashboard": dashboard["dashboard"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GenUI] Connector stats dashboard error: {e}")
        raise HTTPException(500, str(e))

        raise HTTPException(500, "Database not initialized")
    
    try:
        dashboard_service = get_dashboard_service(_db)
        dashboard = await dashboard_service.generate_crypto_treasury_dashboard()
        
        if not dashboard.get("success"):
            raise HTTPException(500, dashboard.get("error", "Dashboard generation failed"))
        
        return {
            "success": True,
            "dashboard": dashboard["dashboard"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GenUI] Crypto treasury dashboard error: {e}")
        raise HTTPException(500, str(e))


@router.post("/component/generate")
async def generate_component(request: ComponentRequest):
    """
    Generate a single UI component
    
    Example - Line Chart:
    {
        "component_type": "line_chart",
        "data": [
            {"month": "Jan", "revenue": 1000},
            {"month": "Feb", "revenue": 1500}
        ],
        "config": {
            "title": "Monthly Revenue",
            "xKey": "month",
            "yKey": "revenue",
            "color": "#10b981"
        }
    }
    
    Example - Metric Card:
    {
        "component_type": "metric_card",
        "data": {
            "value": "$12,345",
            "label": "Total Revenue",
            "change": "+15%",
            "trend": "up"
        },
        "config": {
            "color": "green"
        }
    }
    
    Example - Pie Chart:
    {
        "component_type": "pie_chart",
        "data": [
            {"name": "Free", "value": 100},
            {"name": "Starter", "value": 50}
        ],
        "config": {
            "title": "User Distribution"
        }
    }
    """
    try:
        generator = get_component_generator()
        
        result = generator.generate_component(
            component_type=request.component_type,
            data=request.data,
            config=request.config
        )
        
        if not result.get("success"):
            raise HTTPException(400, result.get("error", "Component generation failed"))
        
        return {
            "success": True,
            "component": result["spec"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GenUI] Component generation error: {e}")
        raise HTTPException(500, str(e))


@router.post("/dashboard/generate")
async def generate_custom_dashboard(request: DashboardRequest):
    """
    Generate a custom dashboard with multiple components
    
    Example:
    {
        "components": [
            {
                "type": "metric_card",
                "data": {"value": "$10,000", "label": "Revenue"},
                "config": {"color": "green"}
            },
            {
                "type": "line_chart",
                "data": [{"month": "Jan", "value": 100}],
                "config": {"title": "Trend"}
            }
        ]
    }
    """
    try:
        generator = get_component_generator()
        
        result = generator.generate_dashboard(request.components)
        
        if not result.get("success"):
            raise HTTPException(400, result.get("error", "Dashboard generation failed"))
        
        return {
            "success": True,
            "dashboard": result["dashboard"]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GenUI] Dashboard generation error: {e}")
        raise HTTPException(500, str(e))


@router.get("/component-types")
async def list_component_types():
    """
    List all available component types
    """
    return {
        "success": True,
        "component_types": [
            {
                "type": "line_chart",
                "description": "Line chart for trends over time",
                "data_format": "Array of {x, y} objects"
            },
            {
                "type": "bar_chart",
                "description": "Bar chart for comparisons",
                "data_format": "Array of {name, value} objects"
            },
            {
                "type": "pie_chart",
                "description": "Pie chart for distributions",
                "data_format": "Array of {name, value} objects"
            },
            {
                "type": "metric_card",
                "description": "Single metric with optional trend",
                "data_format": "{value, label, change, trend}"
            },
            {
                "type": "data_table",
                "description": "Interactive data table",
                "data_format": "Array of objects (columns auto-detected)"
            },
            {
                "type": "form",
                "description": "Dynamic form with validation",
                "data_format": "{fields: [{name, type, label}], submitLabel}"
            }
        ]
    }
