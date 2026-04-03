"""
Agent Harness Router
API endpoints for AUREM agent system
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging

from services.aurem_agents import AUREMAgentHarness, get_agent_harness

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dev/agents", tags=["AUREM Agent Harness"])


class AgentTaskRequest(BaseModel):
    """Request to execute an agent"""
    agent_name: Optional[str] = None  # If None, auto-detect
    context: Dict[str, Any]


class DiagnoseRequest(BaseModel):
    """Request to diagnose an issue"""
    problem: str
    endpoint: Optional[str] = None
    error_message: Optional[str] = None


@router.get("/")
async def list_agents():
    """
    List all available agents with statistics
    
    Returns:
    {
        "total_agents": 1,
        "agents": [
            {
                "name": "aurem-build-fixer",
                "description": "...",
                "executions": 5,
                "success": 4,
                "failure": 1,
                "success_rate": 80.0
            }
        ]
    }
    """
    harness = get_agent_harness()
    return harness.list_agents()


@router.get("/{agent_name}/stats")
async def get_agent_stats(agent_name: str):
    """
    Get statistics for specific agent
    
    Example: GET /api/dev/agents/build-fixer/stats
    """
    harness = get_agent_harness()
    stats = harness.get_agent_stats(agent_name)
    
    if not stats:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")
    
    return stats


@router.post("/execute")
async def execute_agent(request: AgentTaskRequest):
    """
    Execute a specific agent or auto-detect
    
    Examples:
    
    1. Explicit agent:
    {
        "agent_name": "build-fixer",
        "context": {
            "error_type": "import_error",
            "error_message": "cannot import name 'get_connector_ecosystem'",
            "auto_fix": true
        }
    }
    
    2. Auto-detect:
    {
        "context": {
            "problem": "API endpoint returning 404 error"
        }
    }
    """
    harness = get_agent_harness()
    
    try:
        if request.agent_name:
            # Explicit agent
            result = await harness.delegate(request.agent_name, request.context)
        else:
            # Auto-detect
            result = await harness.auto_detect(request.context)
        
        return result
        
    except Exception as e:
        logger.error(f"[AgentHarness] Error executing agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/diagnose-404")
async def diagnose_404(request: DiagnoseRequest):
    """
    Diagnose why an API endpoint is returning 404
    
    Example:
    {
        "problem": "Connector API returning 404",
        "endpoint": "/api/connectors/platforms",
        "error_message": "Not Found"
    }
    
    Returns:
    {
        "success": true,
        "diagnosis": "Import error detected in router",
        "fix_result": {
            "success": true,
            "fix_applied": true,
            "fix_description": "Added singleton pattern for ConnectorEcosystem"
        }
    }
    """
    if not request.endpoint:
        raise HTTPException(status_code=400, detail="endpoint is required")
    
    # Use build-fixer agent to diagnose
    harness = get_agent_harness()
    build_fixer = harness.agents.get("build-fixer")
    
    if not build_fixer:
        raise HTTPException(status_code=500, detail="Build fixer agent not available")
    
    try:
        result = await build_fixer.diagnose_404_error(request.endpoint)
        return result
        
    except Exception as e:
        logger.error(f"[Diagnose404] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fix-build-error")
async def fix_build_error(
    error_type: str,
    error_message: str,
    auto_fix: bool = True
):
    """
    Quick endpoint to fix build errors
    
    Example:
    POST /api/dev/agents/fix-build-error
    ?error_type=import_error
    &error_message=cannot import name 'get_connector_ecosystem'
    &auto_fix=true
    
    Returns:
    {
        "success": true,
        "fix_applied": true,
        "fix_description": "Added singleton pattern for ConnectorEcosystem",
        "verification": {...}
    }
    """
    harness = get_agent_harness()
    
    result = await harness.delegate("build-fixer", {
        "error_type": error_type,
        "error_message": error_message,
        "auto_fix": auto_fix
    })
    
    return result
