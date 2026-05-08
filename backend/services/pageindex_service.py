"""
PageIndex Document Service — Multi-Agent RAG Layer
====================================================
Second retrieval engine for long-form documents (>20 pages).
Complements existing ChromaDB/MiniLM RAG for short docs.

Uses PageIndex cloud API for reasoning-based document retrieval.
Falls back gracefully when API key is unavailable.
"""

import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_db = None
_pi_client = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        mongo_url = os.environ.get("MONGO_URL", "").strip().strip('"').strip("'")
        if not mongo_url:
            return None
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(mongo_url)
        _db = client[os.environ.get("DB_NAME", "aurem_db")]
        return _db
    except Exception:
        return None


def _get_pi_client():
    """Get or initialize PageIndex client."""
    global _pi_client
    if _pi_client is not None:
        return _pi_client
    api_key = os.environ.get("PAGEINDEX_API_KEY", "").strip()
    if not api_key:
        logger.info("[PAGEINDEX] No API key configured — document RAG disabled")
        return None
    try:
        from pageindex import PageIndexClient
        _pi_client = PageIndexClient(api_key=api_key)
        logger.info("[PAGEINDEX] Client initialized")
        return _pi_client
    except ImportError:
        logger.warning("[PAGEINDEX] pageindex package not installed")
        return None
    except Exception as e:
        logger.warning(f"[PAGEINDEX] Client init failed: {e}")
        return None


def is_available() -> bool:
    """Check if PageIndex is configured and available."""
    return _get_pi_client() is not None


async def upload_document(tenant_id: str, filename: str, file_bytes: bytes) -> dict:
    """Upload a PDF document to PageIndex for indexing."""
    db = _get_db()
    pi = _get_pi_client()

    doc_record = {
        "tenant_id": tenant_id,
        "filename": filename,
        "size_bytes": len(file_bytes),
        "status": "pending",
        "pageindex_doc_id": None,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }

    if pi:
        try:
            result = pi.documents.create(file=file_bytes, filename=filename)
            doc_id = result.id if hasattr(result, 'id') else str(result)
            doc_record["pageindex_doc_id"] = doc_id
            doc_record["status"] = "processing"
            logger.info(f"[PAGEINDEX] Document uploaded: {filename} → {doc_id}")
        except Exception as e:
            logger.warning(f"[PAGEINDEX] Upload failed: {e}")
            doc_record["status"] = "upload_failed"
            doc_record["error"] = str(e)
    else:
        doc_record["status"] = "no_api_key"
        doc_record["pageindex_doc_id"] = f"mock_{filename.replace('.', '_')}"

    if db is not None:
        await db.tenant_documents.insert_one({**doc_record})

    return {k: v for k, v in doc_record.items() if k != "_id"}


async def query_document(tenant_id: str, doc_id: str, query: str) -> dict:
    """Query a specific document using PageIndex reasoning-based retrieval."""
    pi = _get_pi_client()
    db = _get_db()

    # Verify document belongs to tenant
    if db is not None:
        doc = await db.tenant_documents.find_one(
            {"tenant_id": tenant_id, "pageindex_doc_id": doc_id}, {"_id": 0}
        )
        if not doc:
            return {"error": "Document not found for this tenant"}

    if pi:
        try:
            response = pi.chat_completions(
                messages=[{"role": "user", "content": query}],
                doc_id=doc_id,
            )
            # Extract answer from response
            answer = ""
            if hasattr(response, 'choices') and response.choices:
                answer = response.choices[0].message.content
            elif isinstance(response, dict):
                answer = response.get("answer", response.get("content", str(response)))
            else:
                answer = str(response)

            return {
                "doc_id": doc_id,
                "query": query,
                "answer": answer,
                "source": "pageindex",
                "reasoning": True,
            }
        except Exception as e:
            logger.warning(f"[PAGEINDEX] Query failed: {e}")
            return {
                "doc_id": doc_id,
                "query": query,
                "answer": f"PageIndex query failed: {str(e)}",
                "source": "pageindex_error",
                "reasoning": False,
            }
    else:
        return {
            "doc_id": doc_id,
            "query": query,
            "answer": "PageIndex not configured. Add PAGEINDEX_API_KEY to .env to enable document reasoning.",
            "source": "mock",
            "reasoning": False,
        }


async def search_document(tenant_id: str, doc_id: str, query: str) -> dict:
    """Search a document for relevant sections (non-chat mode)."""
    pi = _get_pi_client()
    db = _get_db()

    if db is not None:
        doc = await db.tenant_documents.find_one(
            {"tenant_id": tenant_id, "pageindex_doc_id": doc_id}, {"_id": 0}
        )
        if not doc:
            return {"error": "Document not found for this tenant"}

    if pi:
        try:
            results = pi.documents.search(doc_id, query=query)
            sections = []
            if hasattr(results, '__iter__'):
                for r in results:
                    sections.append({
                        "text": getattr(r, 'text', str(r)),
                        "score": getattr(r, 'score', 0),
                    })
            return {
                "doc_id": doc_id,
                "query": query,
                "sections": sections,
                "source": "pageindex",
            }
        except Exception as e:
            return {"doc_id": doc_id, "query": query, "sections": [], "source": "error", "error": str(e)}
    else:
        return {"doc_id": doc_id, "query": query, "sections": [], "source": "mock"}


async def get_tenant_documents(tenant_id: str) -> list:
    """Get all documents for a tenant."""
    db = _get_db()
    if db is None:
        return []
    cursor = db.tenant_documents.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("uploaded_at", -1)
    return await cursor.to_list(length=100)


async def delete_document(tenant_id: str, doc_id: str) -> dict:
    """Delete a document record."""
    db = _get_db()
    if db is None:
        return {"error": "DB unavailable"}
    result = await db.tenant_documents.delete_one(
        {"tenant_id": tenant_id, "pageindex_doc_id": doc_id}
    )
    return {"deleted": result.deleted_count > 0, "doc_id": doc_id}


async def get_document_status(doc_id: str) -> dict:
    """Check if a document is ready for retrieval."""
    pi = _get_pi_client()
    if not pi:
        return {"doc_id": doc_id, "ready": False, "reason": "no_api_key"}
    try:
        doc_info = pi.get_document(doc_id)
        status = doc_info.get("status", "unknown") if isinstance(doc_info, dict) else getattr(doc_info, "status", "unknown")
        ready = status in ("ready", "completed", "indexed")
        return {"doc_id": doc_id, "ready": ready, "status": status}
    except Exception as e:
        return {"doc_id": doc_id, "ready": False, "error": str(e)}


def route_query(query: str, tenant_docs: list) -> str:
    """Route a query to the right retrieval engine.
    Returns 'pageindex' for document queries, 'rag' for everything else."""
    doc_keywords = [
        "document", "pdf", "contract", "manual", "policy", "regulation",
        "filing", "report", "clause", "section", "page", "article",
        "terms", "conditions", "coverage", "compliance", "requirement",
    ]
    query_lower = query.lower()

    # If tenant has documents and query mentions doc-related terms
    if tenant_docs and any(kw in query_lower for kw in doc_keywords):
        return "pageindex"

    # If query references a specific document
    if tenant_docs and any(
        doc.get("filename", "").lower().split(".")[0] in query_lower
        for doc in tenant_docs
    ):
        return "pageindex"

    return "rag"
