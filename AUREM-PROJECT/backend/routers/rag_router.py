"""
ReRoots AI RAG Knowledge Base Router
=====================================
API endpoints for managing the RAG Knowledge Base and AI Consultant.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, timezone

# Import services
from services.rag_knowledge_base import get_rag_knowledge_base
from services.sales_scientist_ai import get_sales_scientist

router = APIRouter(prefix="/rag", tags=["RAG Knowledge Base"])


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
async def ingest_products(request: IngestRequest, background_tasks: BackgroundTasks):
    """
    Ingest products from MongoDB into the RAG Knowledge Base.
    This creates embeddings and stores them in ChromaDB for semantic search.
    
    Use force_refresh=True to clear existing data and re-ingest all.
    """
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
    Perform semantic search on the knowledge base.
    Returns relevant products based on meaning, not just keywords.
    
    Price and stock info are only included if explicitly requested
    (following the Hybrid Sales Scientist protocol).
    """
    try:
        rag_kb = get_rag_knowledge_base()
        
        products = rag_kb.search_products(
            query=request.query,
            top_k=request.top_k,
            include_price=request.include_price,
            include_stock=request.include_stock
        )
        
        facts = rag_kb.search_biotech_facts(request.query, top_k=3)
        
        return {
            "query": request.query,
            "products": products,
            "biotech_facts": facts,
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
async def chat_with_consultant(request: ChatRequest):
    """
    Chat with the Hybrid Sales Scientist AI Consultant.
    
    This is the main endpoint for customer interactions.
    The AI will:
    - Lead with biotech expertise
    - Only discuss price/stock when explicitly asked
    - Maintain the luxury brand voice
    """
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
async def admin_refresh_knowledge_base(background_tasks: BackgroundTasks):
    """
    Admin endpoint to force refresh the entire knowledge base.
    This clears all existing data and re-ingests from MongoDB.
    """
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
