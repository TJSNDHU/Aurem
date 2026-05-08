"""
Self-Healing AI Router
API endpoints for autonomous system monitoring and repair
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from services.self_healing_ai import get_self_healing_ai

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai/self-healing", tags=["Self-Healing AI"])


class AILearningRequest(BaseModel):
    """AI learning from external source"""
    ai_source: str  # "gpt-4o", "claude", "gemini"
    problem: str
    solution: str
    success_rate: float
    context: str


class SystemHealthResponse(BaseModel):
    """System health status"""
    status: str  # "healthy", "degraded", "critical"
    issues_detected: int
    auto_repairs_applied: int
    monitoring_active: bool
    last_check: datetime


@router.get("/health")
async def get_system_health():
    """
    Get overall system health status
    
    Returns:
    {
        "status": "healthy",
        "issues_detected": 0,
        "auto_repairs_applied": 2,
        "monitoring_active": true,
        "last_check": "2026-04-03T21:30:00Z"
    }
    """
    ai = get_self_healing_ai()
    
    try:
        issues = await ai.detect_issues()
        
        # Determine status
        critical_count = sum(1 for issue in issues if issue["severity"] == "critical")
        high_count = sum(1 for issue in issues if issue["severity"] == "high")
        
        if critical_count > 0:
            status = "critical"
        elif high_count > 0:
            status = "degraded"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "issues_detected": len(issues),
            "auto_repairs_applied": len(ai.repair_history),
            "monitoring_active": ai.monitoring_active,
            "last_check": datetime.now().isoformat(),
            "issues": issues
        }
        
    except Exception as e:
        logger.error(f"[Self-Healing] Health check error: {e}")
        raise HTTPException(500, f"Health check failed: {str(e)}")


@router.post("/scan")
async def scan_for_issues():
    """
    Manually trigger system scan for issues
    
    Returns list of detected issues
    """
    ai = get_self_healing_ai()
    
    try:
        issues = await ai.detect_issues()
        
        return {
            "success": True,
            "issues_found": len(issues),
            "issues": issues,
            "scan_time": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"[Self-Healing] Scan error: {e}")
        raise HTTPException(500, f"Scan failed: {str(e)}")


@router.post("/repair")
async def auto_repair_issues():
    """
    Manually trigger auto-repair for all detected issues
    
    Returns:
    {
        "issues_fixed": 3,
        "issues_remaining": 1,
        "repairs": [...]
    }
    """
    ai = get_self_healing_ai()
    
    try:
        # Detect issues
        issues = await ai.detect_issues()
        
        repairs = []
        fixed_count = 0
        
        # Attempt to fix each issue
        for issue in issues:
            if issue.get("auto_fixable"):
                repair_result = await ai.auto_repair(issue)
                repairs.append({
                    "issue": issue["description"],
                    "result": repair_result
                })
                
                if repair_result["success"]:
                    fixed_count += 1
        
        return {
            "success": True,
            "issues_fixed": fixed_count,
            "issues_remaining": len(issues) - fixed_count,
            "repairs": repairs
        }
        
    except Exception as e:
        logger.error(f"[Self-Healing] Repair error: {e}")
        raise HTTPException(500, f"Repair failed: {str(e)}")


@router.post("/learn")
async def learn_from_ai(request: AILearningRequest):
    """
    Teach the AI from external AI source
    
    Request:
    {
        "ai_source": "gpt-4o",
        "problem": "Database connection timeout",
        "solution": "Increase connection pool size to 50",
        "success_rate": 0.95,
        "context": "When MongoDB connections > 40"
    }
    """
    ai = get_self_healing_ai()
    
    try:
        knowledge = {
            "problem": request.problem,
            "solution": request.solution,
            "success_rate": request.success_rate,
            "context": request.context
        }
        
        success = await ai.learn_from_other_ai(request.ai_source, knowledge)
        
        if success:
            return {
                "success": True,
                "message": f"Learned from {request.ai_source}",
                "knowledge_id": "learned"
            }
        else:
            raise HTTPException(500, "Failed to store learning")
            
    except Exception as e:
        logger.error(f"[Self-Healing] Learning error: {e}")
        raise HTTPException(500, f"Learning failed: {str(e)}")


@router.get("/knowledge")
async def query_knowledge(problem: str):
    """
    Query AI knowledge base for solutions
    
    Args:
        problem: Description of the problem
    
    Returns matching solution from learned knowledge
    """
    ai = get_self_healing_ai()
    
    try:
        knowledge = await ai.query_ai_knowledge(problem)
        
        if knowledge:
            return {
                "found": True,
                "solution": knowledge["solution"],
                "context": knowledge["context"],
                "success_rate": knowledge["success_rate"]
            }
        else:
            return {
                "found": False,
                "message": "No matching knowledge found"
            }
            
    except Exception as e:
        logger.error(f"[Self-Healing] Knowledge query error: {e}")
        raise HTTPException(500, f"Query failed: {str(e)}")


@router.post("/optimize")
async def optimize_system():
    """
    Trigger system-wide optimization
    
    Returns:
    {
        "optimizations_applied": ["Database indexes", "Code optimization"],
        "performance_gain": "~15-20%",
        "learned_from": ["gpt-4o", "claude"]
    }
    """
    ai = get_self_healing_ai()
    
    try:
        result = await ai.optimize_system()
        
        return {
            "success": True,
            **result
        }
        
    except Exception as e:
        logger.error(f"[Self-Healing] Optimization error: {e}")
        raise HTTPException(500, f"Optimization failed: {str(e)}")


@router.post("/monitoring/start")
async def start_monitoring(interval_seconds: int = 300):
    """
    Start background monitoring
    
    Args:
        interval_seconds: Check interval (default: 300s = 5 min)
    """
    ai = get_self_healing_ai()
    
    if ai.monitoring_active:
        return {
            "success": False,
            "message": "Monitoring already active"
        }
    
    # Start monitoring in background
    import asyncio
    asyncio.create_task(ai.start_monitoring(interval_seconds))
    
    return {
        "success": True,
        "message": f"Monitoring started (interval: {interval_seconds}s)",
        "interval": interval_seconds
    }


@router.post("/monitoring/stop")
async def stop_monitoring():
    """Stop background monitoring"""
    ai = get_self_healing_ai()
    ai.stop_monitoring()
    
    return {
        "success": True,
        "message": "Monitoring stopped"
    }


@router.get("/repairs/history")
async def get_repair_history(limit: int = 50):
    """
    Get history of auto-repairs
    
    Returns recent repair actions
    """
    ai = get_self_healing_ai()
    
    return {
        "repairs": ai.repair_history[-limit:],
        "total_repairs": len(ai.repair_history)
    }
