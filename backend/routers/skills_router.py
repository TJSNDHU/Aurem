"""
AUREM Skills & Tools Router
POST /api/skills/design/recommend — Full design system recommendation
POST /api/skills/design/search — Search styles, colors, typography
GET  /api/skills/superpowers — List skill patterns
GET  /api/skills/superpowers/{name} — Get specific skill
POST /api/skills/lightrag/insert — Insert knowledge into graph
POST /api/skills/lightrag/query — Hybrid graph+vector query
GET  /api/skills/lightrag/stats — LightRAG status
GET  /api/skills/n8n/status — Check n8n connection
GET  /api/skills/n8n/workflows — List n8n workflows
POST /api/skills/n8n/trigger — Trigger n8n workflow
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Dict, List, Optional

router = APIRouter(prefix="/api/skills", tags=["Skills & Tools"])
logger = logging.getLogger(__name__)


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        import jwt
        return jwt.decode(authorization.replace("Bearer ", ""), os.getenv("JWT_SECRET"), algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


class DesignRecommendRequest(BaseModel):
    product_type: str
    business_name: str = ""


@router.post("/design/recommend")
async def design_recommend(req: DesignRecommendRequest, authorization: str = Header(None)):
    await _auth(authorization)
    from services.design_intelligence import recommend_design_system
    return recommend_design_system(req.product_type, req.business_name)


class SearchRequest(BaseModel):
    query: str
    domain: str = "style"
    limit: int = 5


@router.post("/design/search")
async def design_search(req: SearchRequest, authorization: str = Header(None)):
    await _auth(authorization)
    from services.design_intelligence import search_styles, get_typography, get_color_palette
    if req.domain == "typography":
        return {"results": get_typography(req.query), "domain": "typography"}
    if req.domain == "colors":
        return {"results": get_color_palette(req.query), "domain": "colors"}
    return {"results": search_styles(req.query, req.limit), "domain": "style"}


@router.get("/superpowers")
async def list_skills(authorization: str = Header(None)):
    await _auth(authorization)
    from services.superpowers_skills import get_all_skills
    return {"skills": get_all_skills()}


@router.get("/superpowers/{name}")
async def get_skill(name: str, authorization: str = Header(None)):
    await _auth(authorization)
    from services.superpowers_skills import get_skill, load_skill_file
    skill = get_skill(name)
    if "error" in skill:
        raise HTTPException(404, skill["error"])
    skill["full_doc"] = load_skill_file(name.replace("_", "-"))
    return skill


class LightRAGInsertRequest(BaseModel):
    text: str
    metadata: Dict = {}


@router.post("/lightrag/insert")
async def lightrag_insert(req: LightRAGInsertRequest, authorization: str = Header(None)):
    await _auth(authorization)
    from services.lightrag_adapter import insert_knowledge
    return await insert_knowledge(req.text, req.metadata)


class LightRAGQueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"


@router.post("/lightrag/query")
async def lightrag_query(req: LightRAGQueryRequest, authorization: str = Header(None)):
    await _auth(authorization)
    from services.lightrag_adapter import hybrid_query
    return await hybrid_query(req.query, req.mode)


@router.get("/lightrag/stats")
async def lightrag_stats(authorization: str = Header(None)):
    await _auth(authorization)
    from services.lightrag_adapter import get_stats
    return await get_stats()


@router.get("/n8n/status")
async def n8n_status(authorization: str = Header(None)):
    await _auth(authorization)
    from services.n8n_connector import check_connection
    return await check_connection()


@router.get("/n8n/workflows")
async def n8n_workflows(limit: int = 20, active: bool = False, authorization: str = Header(None)):
    await _auth(authorization)
    from services.n8n_connector import list_workflows
    wfs = await list_workflows(limit, active)
    return {"workflows": wfs, "count": len(wfs)}


class N8NTriggerRequest(BaseModel):
    workflow_id: str
    data: Dict = {}


@router.post("/n8n/trigger")
async def n8n_trigger(req: N8NTriggerRequest, authorization: str = Header(None)):
    await _auth(authorization)
    from services.n8n_connector import trigger_workflow
    return await trigger_workflow(req.workflow_id, req.data)


@router.get("/inventory")
async def skills_inventory(authorization: str = Header(None)):
    await _auth(authorization)
    installed = []
    skills_dir = "/app/.claude/skills"
    if os.path.exists(skills_dir):
        for name in os.listdir(skills_dir):
            path = os.path.join(skills_dir, name)
            if os.path.isdir(path):
                installed.append({"name": name, "path": path, "files": len(os.listdir(path))})
    from services.n8n_connector import check_connection
    from services.lightrag_adapter import get_stats
    return {
        "installed_skills": installed,
        "services": {
            "design_intelligence": {"status": "active", "data": "161 rules, 67 styles, 161 palettes"},
            "superpowers": {"status": "active", "skills": 5},
            "lightrag": await get_stats(),
            "n8n": await check_connection(),
        },
        "total_skills": len(installed),
    }
