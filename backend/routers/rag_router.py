"""
ReRoots AI RAG Knowledge Base Router
=====================================
API endpoints for managing the RAG Knowledge Base and AI Consultant.
"""

import os
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, timezone

from services.rag_knowledge_base import get_rag_knowledge_base
from services.sales_scientist_ai import get_sales_scientist
from services.hybrid_search import get_retrieval_metrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rag", tags=["RAG Knowledge Base"])


def _require_auth(request: Request, *, admin_only: bool = False) -> dict:
    """Bug-fix #63 — RAG endpoints (ingest, refresh, chat, etc.) were
    fully unauthenticated. /admin/refresh kicked off an expensive
    background re-index without a single permission check."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    import jwt as _jwt
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(500, "JWT not configured")
    try:
        payload = _jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
    except _jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except _jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    if admin_only:
        from utils.admin_guard import is_admin_email
        if not (payload.get("is_admin") or payload.get("is_super_admin")
                or payload.get("role") in ("admin", "super_admin")
                or is_admin_email(payload.get("email"))):
            raise HTTPException(403, "Admin access required")
    return payload


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class IngestRequest(BaseModel):
    """Request to ingest products into knowledge base."""
    force_refresh: bool = Field(
        default=False,
        description="If True, clear existing data and re-ingest all"
    )


class SearchRequest(BaseModel):
    """Request for semantic search."""
    query: str = Field(..., description="Search query")
    top_k: int = Field(default=5, description="Number of results")
    include_price: bool = Field(default=False, description="Include price info")
    include_stock: bool = Field(default=False, description="Include stock info")
    metadata_filter: Optional[Dict] = Field(default=None, description="Metadata filters e.g. {'category': 'serum', 'price': {'$lte': 100}}")
    use_hybrid: bool = Field(default=True, description="Enable BM25 + Vector hybrid search")
    use_mmr: bool = Field(default=True, description="Enable MMR diversity reranking")
    mmr_lambda: float = Field(default=0.7, description="MMR lambda (1.0=relevance, 0.0=diversity)")
    use_hyde: bool = Field(default=True, description="Enable HyDE query expansion for better recall")
    use_graph: bool = Field(default=True, description="Include knowledge graph context")


class ChatRequest(BaseModel):
    """Request for AI Consultant chat."""
    message: str = Field(..., description="User message")
    session_id: Optional[str] = Field(default="default", description="Conversation session ID")
    user_name: Optional[str] = Field(default=None, description="User name for personalization")


class ChatResponse(BaseModel):
    """Response from AI Consultant."""
    response: str
    session_id: str
    price_context_active: bool = False
    stock_context_active: bool = False
    rag_products_used: bool = False
    timestamp: str


# =============================================================================
# KNOWLEDGE BASE MANAGEMENT ENDPOINTS
# =============================================================================

@router.post("/ingest")
async def ingest_products(request: IngestRequest, background_tasks: BackgroundTasks, http_request: Request):
    """
    Ingest products from MongoDB into the RAG Knowledge Base.
    This creates embeddings and stores them in ChromaDB for semantic search.
    
    Use force_refresh=True to clear existing data and re-ingest all.
    """
    _require_auth(http_request, admin_only=True)  # Bug-fix #63
    try:
        rag_kb = get_rag_knowledge_base()
        
        # For large datasets, run in background
        if request.force_refresh:
            background_tasks.add_task(rag_kb.ingest_products, True)
            return {
                "status": "processing",
                "message": "Full knowledge base refresh started in background",
                "force_refresh": True
            }
        else:
            result = rag_kb.ingest_products(force_refresh=False)
            return {
                "status": "complete",
                "result": result
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@router.get("/stats")
async def get_knowledge_base_stats():
    """
    Get statistics about the RAG Knowledge Base.
    Shows total products, facts, and storage info.
    """
    try:
        rag_kb = get_rag_knowledge_base()
        return rag_kb.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/search")
async def search_knowledge_base(request: SearchRequest):
    """
    Advanced RAG search pipeline:
    1. HyDE query expansion (hypothetical document embeddings)
    2. Hybrid search (BM25 + Vector via RRF fusion)
    3. MMR reranking for diversity
    4. Knowledge graph context injection
    5. Metadata filtering
    """
    try:
        rag_kb = get_rag_knowledge_base()
        
        # Step 1: HyDE Query Expansion
        search_query = request.query
        hyde_applied = False
        if request.use_hyde:
            try:
                from services.hyde_query_rewrite import hyde_expand
                search_query = await hyde_expand(request.query)
                hyde_applied = len(search_query) > len(request.query)
            except Exception as e:
                logger.debug(f"HyDE expansion failed: {e}")
        
        # Step 2-3: Hybrid Search + MMR
        products = rag_kb.search_products(
            query=search_query,
            top_k=request.top_k,
            include_price=request.include_price,
            include_stock=request.include_stock,
            metadata_filter=request.metadata_filter,
            use_hybrid=request.use_hybrid,
            use_mmr=request.use_mmr,
            mmr_lambda=request.mmr_lambda,
        )
        
        facts = rag_kb.search_biotech_facts(request.query, top_k=3)
        
        # Step 4: Knowledge Graph Context
        graph_context = ""
        graph_nodes = 0
        if request.use_graph:
            try:
                from services.graphify_service import query_graph_local
                graph_results = query_graph_local(request.query, top_k=3)
                graph_nodes = len(graph_results)
                if graph_results:
                    graph_context = " | ".join(
                        f"[{r['type']}] {r['node']} ({len(r.get('connections',[]))} connections)"
                        for r in graph_results
                    )
            except Exception:
                pass
        
        return {
            "query": request.query,
            "expanded_query": search_query if hyde_applied else None,
            "products": products,
            "biotech_facts": facts,
            "graph_context": graph_context,
            "graph_nodes_found": graph_nodes,
            "pipeline": {
                "hyde": hyde_applied,
                "hybrid": request.use_hybrid,
                "mmr": request.use_mmr,
                "graph": request.use_graph and graph_nodes > 0,
                "metadata_filter": request.metadata_filter,
            },
            "price_included": request.include_price,
            "stock_included": request.include_stock,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/context")
async def get_rag_context(
    query: str,
    include_price: bool = False,
    include_stock: bool = False
):
    """
    Get the RAG context string that would be injected into the AI prompt.
    Useful for debugging and understanding what the AI "sees".
    """
    try:
        rag_kb = get_rag_knowledge_base()
        context = rag_kb.get_context_for_query(
            query=query,
            include_price=include_price,
            include_stock=include_stock
        )
        
        return {
            "query": query,
            "context": context,
            "context_length": len(context),
            "price_included": include_price,
            "stock_included": include_stock
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get context: {str(e)}")


# =============================================================================
# AI CONSULTANT CHAT ENDPOINTS
# =============================================================================

@router.post("/chat", response_model=ChatResponse)
async def chat_with_consultant(request: ChatRequest, http_request: Request):
    """
    Chat with the Hybrid Sales Scientist AI Consultant.
    
    This is the main endpoint for customer interactions.
    The AI will:
    - Lead with biotech expertise
    - Only discuss price/stock when explicitly asked
    - Maintain the luxury brand voice
    """
    _require_auth(http_request)  # Bug-fix #63 — any auth, not admin-only
    try:
        sales_scientist = get_sales_scientist()
        
        result = await sales_scientist.generate_response(
            user_message=request.message,
            session_id=request.session_id or "default",
            user_name=request.user_name
        )
        
        return ChatResponse(
            response=result.get("response", ""),
            session_id=result.get("session_id", request.session_id),
            price_context_active=result.get("price_context_active", False),
            stock_context_active=result.get("stock_context_active", False),
            rag_products_used=result.get("rag_products_used", False),
            timestamp=result.get("timestamp", datetime.now(timezone.utc).isoformat())
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.delete("/chat/{session_id}")
async def clear_chat_session(session_id: str):
    """
    Clear conversation history for a specific session.
    Use this to start a fresh conversation.
    """
    try:
        sales_scientist = get_sales_scientist()
        sales_scientist.clear_session(session_id)
        
        return {
            "status": "cleared",
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear session: {str(e)}")


@router.get("/chat/{session_id}/stats")
async def get_chat_session_stats(session_id: str):
    """
    Get statistics for a chat session.
    Shows message count and what topics have been discussed.
    """
    try:
        sales_scientist = get_sales_scientist()
        return sales_scientist.get_session_stats(session_id)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session stats: {str(e)}")


# =============================================================================
# ADMIN ENDPOINTS
# =============================================================================

@router.post("/admin/refresh")
async def admin_refresh_knowledge_base(background_tasks: BackgroundTasks, http_request: Request):
    """
    Admin endpoint to force refresh the entire knowledge base.
    This clears all existing data and re-ingests from MongoDB.
    """
    _require_auth(http_request, admin_only=True)  # Bug-fix #63
    try:
        rag_kb = get_rag_knowledge_base()
        background_tasks.add_task(rag_kb.ingest_products, True)
        
        return {
            "status": "refresh_started",
            "message": "Knowledge base refresh started in background. This may take a few minutes.",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refresh failed: {str(e)}")


@router.get("/admin/health")
async def rag_health_check():
    """
    Health check for the RAG Knowledge Base system.
    """
    try:
        rag_kb = get_rag_knowledge_base()
        stats = rag_kb.get_stats()
        
        # Determine health status
        is_healthy = stats.get("total_products", 0) > 0
        
        return {
            "status": "healthy" if is_healthy else "needs_ingestion",
            "products_indexed": stats.get("total_products", 0),
            "biotech_facts_indexed": stats.get("total_biotech_facts", 0),
            "embedding_model": stats.get("embedding_model", "unknown"),
            "recommendation": "Run /api/rag/ingest to populate knowledge base" if not is_healthy else "Knowledge base is ready",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@router.get("/retrieval-quality")
async def retrieval_quality():
    """
    Get retrieval quality metrics for the Sentinel Overwatch dashboard.
    Shows hybrid search effectiveness, method distribution, and latency.
    """
    try:
        metrics = get_retrieval_metrics()
        rag_kb = get_rag_knowledge_base()
        stats = rag_kb.get_stats()

        return {
            "retrieval": metrics,
            "knowledge_base": {
                "products_indexed": stats.get("total_products", 0),
                "biotech_facts_indexed": stats.get("total_biotech_facts", 0),
                "bm25_index_size": rag_kb._bm25_index.count if hasattr(rag_kb, '_bm25_index') else 0,
                "embedding_model": stats.get("embedding_model", "unknown"),
            },
            "capabilities": {
                "hybrid_search": True,
                "bm25_available": True,
                "mmr_reranking": True,
                "metadata_filtering": True,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
