"""
Skills API Router
API endpoints for AUREM Skills Library
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging

from services.aurem_skills import get_skills_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dev/skills", tags=["AUREM Skills Library"])


class SkillExecutionRequest(BaseModel):
    """Request to execute a skill"""
    skill_name: str
    context: Dict[str, Any]


@router.get("/")
async def list_skills():
    """List all available skills"""
    manager = get_skills_manager()
    return manager.list_skills()


@router.get("/{skill_name}")
async def get_skill_info(skill_name: str):
    """Get information about a specific skill"""
    manager = get_skills_manager()
    info = manager.get_skill_info(skill_name)
    
    if not info:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")
    
    return info


@router.post("/execute")
async def execute_skill(request: SkillExecutionRequest):
    """Execute a specific skill"""
    manager = get_skills_manager()
    
    try:
        result = await manager.execute_skill(request.skill_name, request.context)
        return result
        
    except Exception as e:
        logger.error(f"[SkillsAPI] Error executing skill: {e}")
        raise HTTPException(status_code=500, detail=str(e))
