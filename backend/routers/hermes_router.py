"""
AUREM Hermes Identity + Memory Router
=======================================
API endpoints for managing ORA's identity, skills, dream consolidation,
and the 3-tier self-improving memory system.
"""
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict

from utils.tenant import current_tenant

router = APIRouter(prefix="/api/hermes", tags=["Hermes Identity & Memory"])
logger = logging.getLogger(__name__)


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        import jwt
        payload = jwt.decode(authorization.replace("Bearer ", ""), os.getenv("JWT_SECRET"), algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/identity")
async def get_identity(authorization: str = Header(None)):
    """Get ORA's current identity (SOUL + USER) and system stats."""
    await _auth(authorization)
    from services.hermes_identity import load_soul, load_user, get_identity_stats
    return {
        "soul": load_soul(),
        "user": load_user(),
        "stats": get_identity_stats(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/skills")
async def list_skills(authorization: str = Header(None)):
    """List all procedural memory skill documents."""
    await _auth(authorization)
    from services.hermes_identity import list_skills
    return {"skills": list_skills()}


@router.get("/skills/{name}")
async def get_skill(name: str, authorization: str = Header(None)):
    """Retrieve a specific skill document."""
    await _auth(authorization)
    from services.hermes_identity import get_skill
    content = get_skill(name)
    if not content:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return {"name": name, "content": content}


class SkillGenRequest(BaseModel):
    task_description: str
    steps_taken: List[str]
    outcome: str
    use_sovereign: bool = True


@router.post("/skills/generate")
async def generate_skill(req: SkillGenRequest, authorization: str = Header(None)):
    """Manually trigger skill document generation from a completed task."""
    await _auth(authorization)
    from services.hermes_identity import generate_skill_document
    path = await generate_skill_document(
        req.task_description, req.steps_taken, req.outcome, req.use_sovereign
    )
    if path:
        return {"success": True, "skill_path": path}
    raise HTTPException(status_code=500, detail="Skill generation failed")


class DreamRequest(BaseModel):
    session_id: str = "manual"
    transcript: List[Dict] = []
    use_sovereign: bool = True


@router.post("/dream")
async def trigger_dream(req: DreamRequest, authorization: str = Header(None)):
    """Manually trigger Dream Consolidation on a session transcript."""
    await _auth(authorization)
    from services.hermes_identity import dream_consolidation
    try:
        import server
        db = server.db if hasattr(server, "db") else None
    except Exception:
        db = None

    result = await dream_consolidation(
        session_transcript=req.transcript,
        session_id=req.session_id,
        use_sovereign=req.use_sovereign,
        db=db,
    )
    return result


@router.get("/mistakes")
async def get_mistakes(authorization: str = Header(None)):
    """Get the Mistakes Journal."""
    await _auth(authorization)
    from services.hermes_identity import load_mistakes
    return {"content": load_mistakes()}


@router.get("/habits")
async def get_habits(authorization: str = Header(None)):
    """Get the Habits (successful patterns) Journal."""
    await _auth(authorization)
    from services.hermes_identity import load_habits
    return {"content": load_habits()}


class UpdateIdentityRequest(BaseModel):
    file: str  # "soul" or "user"
    content: str


@router.put("/identity")
async def update_identity(req: UpdateIdentityRequest, authorization: str = Header(None)):
    """Update SOUL.md or USER.md directly."""
    await _auth(authorization)
    from services.hermes_identity import IDENTITY_DIR

    if req.file == "soul":
        path = IDENTITY_DIR / "SOUL.md"
    elif req.file == "user":
        path = IDENTITY_DIR / "USER.md"
    else:
        raise HTTPException(status_code=400, detail="file must be 'soul' or 'user'")

    try:
        path.write_text(req.content, encoding="utf-8")
        return {"success": True, "file": req.file, "size": len(req.content)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_hermes_config(authorization: str = Header(None)):
    """Get the Hermes system configuration and toggle states."""
    await _auth(authorization)
    from services.hermes_identity import get_identity_stats, SKILLS_DIR, IDENTITY_DIR
    stats = get_identity_stats()
    return {
        "identity_dir": str(IDENTITY_DIR),
        "skills_dir": str(SKILLS_DIR),
        "smart_toggle": {
            "description": "Sovereign Brain handles reflection by default. Auto-escalates to Cloud on high complexity or self-check failure.",
            "sovereign_default": True,
            "cloud_escalation_triggers": [
                "Session has 10+ messages (high complexity)",
                "3+ error/failure mentions in transcript",
                "Sovereign response missing required MISTAKES/HABITS sections",
                "Sovereign response under 50 chars",
                "Skill doc missing '# Skill' heading or under 100 chars",
            ],
        },
        **stats,
    }


# ═══════════════════════════════════════
# HERMES MEMORY AGENT ENDPOINTS
# ═══════════════════════════════════════

@router.get("/memory/dashboard")
async def memory_dashboard(tenant_id: Optional[str] = None, authorization: str = Header(None)):
    """Full Hermes memory dashboard with all 3 tiers + learning velocity."""
    await _auth(authorization)
    from services.hermes_memory_agent import get_hermes_dashboard
    return await get_hermes_dashboard(tenant_id)


@router.get("/memory/recent")
async def recent_interactions(
    tenant_id: Optional[str] = None,
    limit: int = 20,
    authorization: str = Header(None),
):
    """Get recent Hermes interactions (auto-stored after every agent response)."""
    await _auth(authorization)
    from services.hermes_memory_agent import get_recent_interactions
    interactions = await get_recent_interactions(tenant_id, limit)
    return {"interactions": interactions, "count": len(interactions)}


@router.get("/memory/knowledge")
async def knowledge_base(
    tenant_id: Optional[str] = None,
    limit: int = 20,
    authorization: str = Header(None),
):
    """Get promoted knowledge base patterns (confidence > 0.85)."""
    await _auth(authorization)
    from services.hermes_memory_agent import get_knowledge_entries
    entries = await get_knowledge_entries(tenant_id, limit)
    return {"knowledge": entries, "count": len(entries)}


@router.get("/memory/recall")
async def recall_memory(
    query: str,
    tenant_id: str = Depends(current_tenant),
    authorization: str = Header(None),
):
    """Test the recall function — what Hermes knows before acting."""
    await _auth(authorization)
    from services.hermes_memory_agent import recall
    result = await recall(tenant_id, query, "manual_test")
    return result


class PromoteRequest(BaseModel):
    pattern_type: str
    pattern: str
    action_taken: str


@router.post("/memory/promote")
async def promote_pattern(
    req: PromoteRequest,
    tenant_id: str = Depends(current_tenant),
    authorization: str = Header(None),
):
    """Manually promote a pattern to the knowledge base."""
    await _auth(authorization)
    from services.hermes_memory_agent import manually_promote_pattern
    result = await manually_promote_pattern(
        tenant_id, req.pattern_type, req.pattern, req.action_taken
    )
    return result


# ═══════════════════════════════════════
# MEMOBASE — SEMANTIC MEMORY ENDPOINTS
# ═══════════════════════════════════════

class MemobaseStoreRequest(BaseModel):
    content: str
    memory_type: str = "episodic"
    agent_id: str = "manual"
    session_id: str = ""
    outcome: str = "success"
    context: Dict = {}


@router.post("/memobase/store")
async def memobase_store(req: MemobaseStoreRequest, authorization: str = Header(None)):
    """Store a memory with embedding vector for semantic recall."""
    p = await _auth(authorization)
    from services.memobase import store_memory
    tenant_id = p.get("tenant_id") or p.get("business_id") or "aurem_platform"
    result = await store_memory(
        tenant_id=tenant_id, content=req.content, memory_type=req.memory_type,
        agent_id=req.agent_id, session_id=req.session_id,
        outcome=req.outcome, context=req.context,
    )
    return result


class MemobaseRecallRequest(BaseModel):
    query: str
    limit: int = 5
    threshold: float = 0.45
    memory_type: Optional[str] = None
    agent_id: Optional[str] = None


@router.post("/memobase/recall")
async def memobase_recall(req: MemobaseRecallRequest, authorization: str = Header(None)):
    """Semantic search across memories — finds similar past interactions."""
    p = await _auth(authorization)
    from services.memobase import semantic_recall
    tenant_id = p.get("tenant_id") or p.get("business_id") or "aurem_platform"
    results = await semantic_recall(
        tenant_id=tenant_id, query=req.query, limit=req.limit,
        threshold=req.threshold, memory_type=req.memory_type, agent_id=req.agent_id,
    )
    return {"memories": results, "count": len(results), "query": req.query[:100]}


@router.post("/memobase/consolidate")
async def memobase_consolidate(authorization: str = Header(None)):
    """Consolidate duplicate memories (merge similar, prune noise)."""
    p = await _auth(authorization)
    from services.memobase import consolidate_memories
    tenant_id = p.get("tenant_id") or p.get("business_id") or "aurem_platform"
    result = await consolidate_memories(tenant_id)
    return result


@router.get("/memobase/stats")
async def memobase_stats(tenant_id: Optional[str] = None, authorization: str = Header(None)):
    """Get Memobase memory statistics."""
    await _auth(authorization)
    from services.memobase import get_memory_stats
    stats = await get_memory_stats(tenant_id)
    return stats


# ═══════════════════════════════════════
# AUDIO RAG — Voice Transcript Memory
# ═══════════════════════════════════════

class VoiceTranscriptRequest(BaseModel):
    transcript: str
    session_id: str = ""
    caller_phone: str = ""
    sentiment: str = ""


@router.post("/memobase/voice-transcript")
async def store_voice_transcript(req: VoiceTranscriptRequest, authorization: str = Header(None)):
    """Store voice call transcript as chunked Memobase memories for Audio RAG."""
    p = await _auth(authorization)
    from services.memobase import store_voice_transcript as _store_vt
    tenant_id = p.get("tenant_id") or p.get("business_id") or "aurem_platform"
    result = await _store_vt(
        tenant_id=tenant_id, transcript=req.transcript,
        session_id=req.session_id,
        caller_info={"caller_phone": req.caller_phone} if req.caller_phone else None,
        sentiment=req.sentiment,
    )
    return result


class VoiceRecallRequest(BaseModel):
    query: str
    caller_phone: str = ""
    limit: int = 3


@router.post("/memobase/voice-recall")
async def voice_context_recall(req: VoiceRecallRequest, authorization: str = Header(None)):
    """Recall relevant past voice interactions before ORA responds."""
    p = await _auth(authorization)
    from services.memobase import voice_context_recall as _voice_recall
    tenant_id = p.get("tenant_id") or p.get("business_id") or "aurem_platform"
    results = await _voice_recall(tenant_id, req.query, req.caller_phone, req.limit)
    return {"memories": results, "count": len(results), "pattern": "audio_rag"}
