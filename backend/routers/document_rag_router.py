"""
Document RAG Router — PageIndex + Multi-Agent RAG
Upload documents, query with reasoning, manage knowledge docs.
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Depends, Header, UploadFile, File, Form
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.pageindex_service import set_db as pi_set_db
    pi_set_db(database)


async def _get_auth(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    import jwt
    try:
        secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
        payload = jwt.decode(authorization[7:], secret, algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    auth=Depends(_get_auth),
):
    """Upload a PDF document for PageIndex indexing."""
    tenant_id = auth.get("tenant_id", auth.get("user_id", "default"))

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    # Validate file type
    allowed_types = {".pdf", ".docx", ".txt", ".md", ".csv"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Allowed: {allowed_types}")

    # Read file
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    from services.pageindex_service import upload_document
    result = await upload_document(tenant_id, file.filename, content)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return {"status": "ok", **result}


@router.post("/query")
async def query_document(
    doc_id: str = Form(...),
    query: str = Form(...),
    auth=Depends(_get_auth),
):
    """Query a document using PageIndex reasoning-based retrieval."""
    tenant_id = auth.get("tenant_id", auth.get("user_id", "default"))
    from services.pageindex_service import query_document
    result = await query_document(tenant_id, doc_id, query)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return {"status": "ok", **result}


@router.post("/search")
async def search_document(
    doc_id: str = Form(...),
    query: str = Form(...),
    auth=Depends(_get_auth),
):
    """Search a document for relevant sections."""
    tenant_id = auth.get("tenant_id", auth.get("user_id", "default"))
    from services.pageindex_service import search_document
    result = await search_document(tenant_id, doc_id, query)
    return {"status": "ok", **result}


@router.get("/list")
async def list_documents(auth=Depends(_get_auth)):
    """Get all documents for current tenant."""
    tenant_id = auth.get("tenant_id", auth.get("user_id", "default"))
    from services.pageindex_service import get_tenant_documents
    docs = await get_tenant_documents(tenant_id)
    return {"status": "ok", "documents": docs, "count": len(docs)}


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, auth=Depends(_get_auth)):
    """Delete a document."""
    tenant_id = auth.get("tenant_id", auth.get("user_id", "default"))
    from services.pageindex_service import delete_document
    result = await delete_document(tenant_id, doc_id)
    return {"status": "ok", **result}


@router.get("/status/{doc_id}")
async def document_status(doc_id: str, auth=Depends(_get_auth)):
    """Check if a document is ready for retrieval."""
    from services.pageindex_service import get_document_status
    result = await get_document_status(doc_id)
    return {"status": "ok", **result}


@router.get("/rag/status")
async def rag_status(auth=Depends(_get_auth)):
    """Get status of both RAG engines."""
    from services.pageindex_service import is_available as pi_available
    tenant_id = auth.get("tenant_id", auth.get("user_id", "default"))
    from services.pageindex_service import get_tenant_documents
    docs = await get_tenant_documents(tenant_id)
    return {
        "status": "ok",
        "engines": {
            "chromadb_minilm": {
                "status": "active",
                "type": "vector_search",
                "model": "all-MiniLM-L6-v2",
                "use_case": "Short docs, leads, conversations, business metrics",
            },
            "pageindex": {
                "status": "active" if pi_available() else "not_configured",
                "type": "reasoning_tree",
                "model": "PageIndex v0.2.8",
                "use_case": "Long-form PDFs, contracts, manuals, policies",
                "api_key_set": pi_available(),
                "documents_indexed": len(docs),
            },
        },
    }
