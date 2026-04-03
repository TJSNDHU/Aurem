"""
Hooks Router
FastAPI endpoints for the Automation Hooks System
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging

from services.aurem_hooks.hook_manager import get_hook_manager

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/hooks",
    tags=["Hooks"]
)


# Request Models
class TriggerHookRequest(BaseModel):
    hook_name: str = Field(..., description="Name of hook to trigger (e.g., 'pre-file-edit')")
    context: Dict[str, Any] = Field(default_factory=dict, description="Context data for hook")


class TriggerEventRequest(BaseModel):
    event_name: str = Field(..., description="Event name (e.g., 'file.edit', 'api.call')")
    context: Dict[str, Any] = Field(default_factory=dict, description="Context data")


class HookControlRequest(BaseModel):
    hook_name: str = Field(..., description="Name of hook to enable/disable")


# Endpoints
@router.get("/list")
async def list_hooks():
    """
    List all registered hooks with their stats
    
    Returns:
    {
        "success": true,
        "hooks": [
            {
                "name": "pre-file-edit",
                "description": "...",
                "type": "pre",
                "enabled": true,
                "executions": 42,
                "last_execution": "2024-04-03T..."
            },
            ...
        ]
    }
    """
    try:
        hook_manager = get_hook_manager()
        hooks = hook_manager.list_hooks()
        
        return {
            "success": True,
            "count": len(hooks),
            "hooks": hooks
        }
        
    except Exception as e:
        logger.error(f"[HooksRouter] List hooks failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/{hook_name}")
async def get_hook_stats(hook_name: str):
    """
    Get stats for a specific hook
    
    Path params:
        hook_name: Name of hook (e.g., "pre-file-edit")
    
    Returns:
    {
        "success": true,
        "stats": {
            "name": "pre-file-edit",
            "executions": 42,
            ...
        }
    }
    """
    try:
        hook_manager = get_hook_manager()
        stats = hook_manager.get_hook_stats(hook_name)
        
        if not stats:
            raise HTTPException(
                status_code=404,
                detail=f"Hook '{hook_name}' not found"
            )
        
        return {
            "success": True,
            "stats": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[HooksRouter] Get stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger")
async def trigger_hook(request: TriggerHookRequest):
    """
    Manually trigger a specific hook
    
    Body:
    {
        "hook_name": "post-connector-fetch",
        "context": {
            "platform": "reddit",
            "query": "test",
            "results": [...],
            "results_count": 5
        }
    }
    
    Returns:
    {
        "success": true,
        "result": {
            "success": true,
            "message": "...",
            "should_proceed": true,
            "warnings": [],
            "data": {...}
        }
    }
    """
    try:
        hook_manager = get_hook_manager()
        
        result = await hook_manager.trigger(
            hook_name=request.hook_name,
            context=request.context
        )
        
        return {
            "success": True,
            "result": result.to_dict()
        }
        
    except Exception as e:
        logger.error(f"[HooksRouter] Trigger hook failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger-event")
async def trigger_event(request: TriggerEventRequest):
    """
    Trigger all hooks for an event
    
    Body:
    {
        "event_name": "file.edit",
        "context": {
            "file_path": "/app/backend/test.py",
            "operation": "edit"
        }
    }
    
    Events:
    - "file.edit" -> pre-file-edit + post-file-edit
    - "api.call" -> pre-api-call + post-api-call
    - "deploy" -> pre-deploy + post-deploy
    - "connector.fetch" -> post-connector-fetch
    - "agent.execute" -> post-agent-execute
    
    Returns:
    {
        "success": true,
        "results": [
            {"success": true, "message": "..."},
            {"success": true, "message": "..."}
        ]
    }
    """
    try:
        hook_manager = get_hook_manager()
        
        results = await hook_manager.trigger_event(
            event_name=request.event_name,
            context=request.context
        )
        
        return {
            "success": True,
            "event": request.event_name,
            "hooks_triggered": len(results),
            "results": [r.to_dict() for r in results]
        }
        
    except Exception as e:
        logger.error(f"[HooksRouter] Trigger event failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enable")
async def enable_hook(request: HookControlRequest):
    """
    Enable a hook
    
    Body:
    {
        "hook_name": "pre-file-edit"
    }
    """
    try:
        hook_manager = get_hook_manager()
        
        success = hook_manager.enable_hook(request.hook_name)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Hook '{request.hook_name}' not found"
            )
        
        return {
            "success": True,
            "message": f"Hook '{request.hook_name}' enabled"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[HooksRouter] Enable hook failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable")
async def disable_hook(request: HookControlRequest):
    """
    Disable a hook
    
    Body:
    {
        "hook_name": "pre-file-edit"
    }
    """
    try:
        hook_manager = get_hook_manager()
        
        success = hook_manager.disable_hook(request.hook_name)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Hook '{request.hook_name}' not found"
            )
        
        return {
            "success": True,
            "message": f"Hook '{request.hook_name}' disabled"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[HooksRouter] Disable hook failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
