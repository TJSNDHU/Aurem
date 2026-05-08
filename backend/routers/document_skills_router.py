"""
AUREM Document Skills Router
POST /api/docs/generate — generate document (DOCX/PPTX/PDF)
POST /api/docs/proposal — auto-generate client proposal DOCX
POST /api/docs/campaign-report — campaign performance PDF
POST /api/docs/outreach — Forensic Miner lead outreach DOCX
POST /api/docs/health-deck — monthly Shopify health PPTX
GET  /api/docs/download/{doc_id} — download generated document
GET  /api/docs/history — document generation history
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict

router = APIRouter(prefix="/api/docs", tags=["Document Skills"])
logger = logging.getLogger(__name__)


async def _auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Auth required")
    try:
        import jwt
        return jwt.decode(authorization.replace("Bearer ", ""), os.getenv("JWT_SECRET"), algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def _tenant(p: dict) -> str:
    return p.get("tenant_id") or p.get("business_id") or "aurem_platform"


def _init():
    from services.document_skills import set_db
    try:
        import server
        if hasattr(server, "db"):
            set_db(server.db)
    except Exception:
        pass


class GenerateDocRequest(BaseModel):
    title: str
    sections: List[Dict]
    format: str = "docx"
    doc_type: str = "custom"


@router.post("/generate")
async def generate_doc(req: GenerateDocRequest, authorization: str = Header(None)):
    """Generate document in chosen format (docx/pptx/pdf)."""
    p = await _auth(authorization)
    _init()
    from services.document_skills import generate_docx, generate_pptx, generate_pdf
    if req.format == "docx":
        return await generate_docx(req.title, req.sections, req.doc_type, tenant_id=_tenant(p))
    elif req.format == "pptx":
        slides = [{"title": s.get("heading", ""), "content": s.get("content", "")} for s in req.sections]
        return await generate_pptx(req.title, slides, req.doc_type, _tenant(p))
    elif req.format == "pdf":
        return await generate_pdf(req.title, req.sections, req.doc_type, _tenant(p))
    raise HTTPException(400, f"Unsupported format: {req.format}. Use docx, pptx, or pdf.")


class ProposalRequest(BaseModel):
    client_name: str
    business: str
    services: List[str] = []


@router.post("/proposal")
async def proposal(req: ProposalRequest, authorization: str = Header(None)):
    """Auto-generate client welcome proposal as DOCX."""
    p = await _auth(authorization)
    _init()
    from services.document_skills import on_new_client_proposal
    return await on_new_client_proposal(req.client_name, req.business, req.services or None, _tenant(p))


class CampaignReportRequest(BaseModel):
    campaign_name: str
    metrics: Dict = {}


@router.post("/campaign-report")
async def campaign_report(req: CampaignReportRequest, authorization: str = Header(None)):
    """Auto-generate campaign performance report as PDF."""
    p = await _auth(authorization)
    _init()
    from services.document_skills import on_campaign_complete_report
    return await on_campaign_complete_report(req.campaign_name, req.metrics or None, _tenant(p))


class OutreachRequest(BaseModel):
    lead_domain: str
    health_score: int = 35
    issues: List[str] = []


@router.post("/outreach")
async def outreach(req: OutreachRequest, authorization: str = Header(None)):
    """Forensic Miner lead → auto-generate outreach proposal DOCX."""
    p = await _auth(authorization)
    _init()
    from services.document_skills import on_forensic_miner_lead
    return await on_forensic_miner_lead(req.lead_domain, req.health_score, req.issues or None, _tenant(p))


class HealthDeckRequest(BaseModel):
    shop: str
    metrics: Dict = {}


@router.post("/health-deck")
async def health_deck(req: HealthDeckRequest, authorization: str = Header(None)):
    """Monthly Shopify health report as PPTX."""
    p = await _auth(authorization)
    _init()
    from services.document_skills import generate_health_deck
    return await generate_health_deck(req.shop, req.metrics or None, _tenant(p))


@router.get("/download/{doc_id}")
async def download(doc_id: str, authorization: str = Header(None)):
    """Download generated document by ID."""
    await _auth(authorization)
    doc_dir = "/app/backend/uploads/documents"
    for ext in ["docx", "pptx", "pdf"]:
        fpath = f"{doc_dir}/{doc_id}.{ext}"
        if os.path.exists(fpath):
            media = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation", "pdf": "application/pdf"}
            return FileResponse(fpath, media_type=media[ext], filename=f"{doc_id}.{ext}")
    raise HTTPException(404, "Document not found")


@router.get("/history")
async def history(limit: int = 20, authorization: str = Header(None)):
    """Document generation history."""
    p = await _auth(authorization)
    _init()
    from services.document_skills import get_document_history
    docs = await get_document_history(_tenant(p), limit)
    return {"documents": docs, "count": len(docs)}
