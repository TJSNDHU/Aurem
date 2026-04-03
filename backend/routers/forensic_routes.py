"""
ORA Forensic API Routes
AI-Powered Root Cause Analysis & Genetic Repair
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/forensic", tags=["Forensic Engineering"])

# Database reference
db = None

def set_db(database):
    global db
    db = database


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH HELPER
# ═══════════════════════════════════════════════════════════════════════════════

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"user_id": "admin", "email": "admin@aurem.ai", "role": "admin"}


# ═══════════════════════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class AnalyzeScreenshotRequest(BaseModel):
    image_base64: str
    context: Optional[str] = ""
    user_description: Optional[str] = ""


class AnalyzeTextRequest(BaseModel):
    error_log: str
    context: Optional[str] = ""


class RepairRequest(BaseModel):
    analysis_id: str
    auto_apply: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/analyze/screenshot")
async def analyze_screenshot(
    request: AnalyzeScreenshotRequest,
    user = Depends(get_current_user)
):
    """
    Analyze screenshot using GPT-4o Vision
    
    Upload a screenshot of an error and ORA will:
    - Identify the error type
    - Trace it to source code
    - Recommend fixes
    """
    from services.forensic_analyzer import get_forensic_analyzer
    from services.code_tracer import get_code_tracer
    
    analyzer = get_forensic_analyzer(db)
    tracer = get_code_tracer()
    
    # Analyze screenshot
    analysis = await analyzer.analyze_screenshot(
        image_base64=request.image_base64,
        context=request.context,
        user_description=request.user_description
    )
    
    # Trace to code
    trace = await tracer.trace_error_to_code(
        suspected_files=analysis.suspected_files,
        suspected_functions=analysis.suspected_functions,
        error_message=analysis.error_messages[0] if analysis.error_messages else ""
    )
    
    # Log to Daily Digest
    from services.daily_digest import get_digest_engine, EventPriority
    digest = get_digest_engine(db)
    await digest.record_event(
        event_type="forensic_analysis",
        title=f"ORA Forensic Analysis: {analysis.detected_error_type}",
        description=analysis.root_cause_hypothesis[:200],
        business_id="admin",
        priority=EventPriority.HIGH if analysis.confidence_score > 0.7 else EventPriority.MEDIUM,
        metadata={
            "analysis_id": analysis.analysis_id,
            "confidence": analysis.confidence_score
        }
    )
    
    return {
        "analysis_id": analysis.analysis_id,
        "analysis": analysis.dict(),
        "code_trace": trace.dict(),
        "ready_for_repair": trace.found
    }


@router.post("/analyze/text")
async def analyze_text_error(
    request: AnalyzeTextRequest,
    user = Depends(get_current_user)
):
    """
    Analyze text error log
    
    Paste error logs and ORA will analyze them
    """
    from services.forensic_analyzer import get_forensic_analyzer
    from services.code_tracer import get_code_tracer
    
    analyzer = get_forensic_analyzer(db)
    tracer = get_code_tracer()
    
    # Analyze text
    analysis = await analyzer.analyze_text_error(
        error_log=request.error_log,
        context=request.context
    )
    
    # Trace to code
    trace = await tracer.trace_error_to_code(
        suspected_files=analysis.suspected_files,
        suspected_functions=analysis.suspected_functions,
        error_message=analysis.error_messages[0] if analysis.error_messages else ""
    )
    
    return {
        "analysis_id": analysis.analysis_id,
        "analysis": analysis.dict(),
        "code_trace": trace.dict(),
        "ready_for_repair": trace.found
    }


@router.post("/repair")
async def repair_code(
    request: RepairRequest,
    user = Depends(get_current_user)
):
    """
    Apply genetic repair to code
    
    ORA will:
    - Refactor the code (not just patch)
    - Generate unit tests
    - Add "Never Again" compliance rule
    """
    from services.genetic_repair import get_genetic_repair_engine
    from services.code_tracer import get_code_tracer
    
    repair_engine = get_genetic_repair_engine(db)
    tracer = get_code_tracer()
    
    # Get analysis
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    
    analysis_doc = await db.aurem_forensic_analyses.find_one(
        {"analysis_id": request.analysis_id},
        {"_id": 0}
    )
    
    if not analysis_doc:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Get code location
    trace = await tracer.trace_error_to_code(
        suspected_files=analysis_doc["suspected_files"],
        suspected_functions=analysis_doc["suspected_functions"],
        error_message=analysis_doc["error_messages"][0] if analysis_doc["error_messages"] else ""
    )
    
    if not trace.found or not trace.locations:
        raise HTTPException(status_code=400, detail="Could not trace error to code")
    
    # Get first location
    location = trace.locations[0]
    
    # Apply repair
    repair = await repair_engine.repair_code(
        file_path=location.file_path,
        code_snippet=location.code_snippet or "",
        root_cause=analysis_doc["root_cause_hypothesis"],
        recommended_fixes=analysis_doc["recommended_fixes"]
    )
    
    # Log to Daily Digest
    from services.daily_digest import get_digest_engine, EventPriority
    digest = get_digest_engine(db)
    await digest.record_event(
        event_type="genetic_repair",
        title=f"ORA Genetic Repair Applied: {location.file_path}",
        description=f"Repair {'successful' if repair.repair_successful else 'failed'}",
        business_id="admin",
        priority=EventPriority.HIGH,
        metadata={
            "repair_id": repair.repair_id,
            "files_modified": repair.files_modified
        }
    )
    
    return {
        "repair_id": repair.repair_id,
        "repair": repair.dict(),
        "message": "Genetic repair completed" if repair.repair_successful else "Repair failed"
    }


@router.get("/history")
async def get_forensic_history(
    limit: int = 20,
    user = Depends(get_current_user)
):
    """
    Get history of forensic analyses and repairs
    """
    if db is None:
        return {"analyses": [], "repairs": []}
    
    # Get recent analyses
    analyses = await db.aurem_forensic_analyses.find(
        {},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    
    # Get recent repairs
    repairs = await db.aurem_genetic_repairs.find(
        {},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    
    return {
        "analyses": analyses,
        "repairs": repairs,
        "total_analyses": len(analyses),
        "total_repairs": len(repairs)
    }


@router.get("/stats")
async def get_forensic_stats(user = Depends(get_current_user)):
    """
    Get forensic suite statistics
    """
    if db is None:
        return {"total_analyses": 0, "total_repairs": 0, "success_rate": 0}
    
    total_analyses = await db.aurem_forensic_analyses.count_documents({})
    total_repairs = await db.aurem_genetic_repairs.count_documents({})
    successful_repairs = await db.aurem_genetic_repairs.count_documents({"repair_successful": True})
    
    success_rate = (successful_repairs / total_repairs * 100) if total_repairs > 0 else 0
    
    return {
        "total_analyses": total_analyses,
        "total_repairs": total_repairs,
        "successful_repairs": successful_repairs,
        "success_rate": round(success_rate, 1),
        "average_confidence": 0.75  # TODO: Calculate from database
    }


print("[STARTUP] ORA Forensic Routes loaded (AI Root-Cause Analysis)")
