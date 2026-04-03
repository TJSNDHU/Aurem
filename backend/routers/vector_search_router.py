"""
Vector Search API Router
Semantic search endpoints for AUREM
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging

from services.vector_search import get_vector_search

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vector", tags=["Vector Search"])


class SemanticSearchRequest(BaseModel):
    """Semantic search request"""
    query: str
    collection: str = "connector_data"
    limit: int = 10
    filter_platform: Optional[str] = None


class IndexDataRequest(BaseModel):
    """Index data request"""
    platform: str
    data: List[Dict[str, Any]]
    query_context: str = ""


@router.get("/")
async def vector_search_info():
    """
    Get vector search service information
    
    Returns statistics about collections and indexing
    """
    vector_search = get_vector_search()
    stats = vector_search.get_stats()
    
    return {
        "service": "AUREM Vector Search",
        "status": "active" if stats["initialized"] else "not_initialized",
        "embedding_model": stats.get("embedding_model", "text-embedding-3-small"),
        "collections": stats.get("collections", {}),
        "features": [
            "Semantic search across connectors",
            "Agent memory (RAG)",
            "Code pattern search",
            "Error pattern matching"
        ]
    }


@router.post("/search")
async def semantic_search(request: SemanticSearchRequest):
    """
    Perform semantic search
    
    Example:
    {
        "query": "AI automation discussions",
        "collection": "connector_data",
        "limit": 10,
        "filter_platform": "reddit"
    }
    
    Returns semantically similar results based on meaning, not just keywords.
    """
    vector_search = get_vector_search()
    
    try:
        results = await vector_search.semantic_search(
            query=request.query,
            collection_name=request.collection,
            limit=request.limit,
            filter_platform=request.filter_platform
        )
        
        return {
            "success": True,
            "query": request.query,
            "collection": request.collection,
            "total_results": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"[VectorSearchAPI] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index")
async def index_data(request: IndexDataRequest):
    """
    Index data for semantic search
    
    Example:
    {
        "platform": "reddit",
        "data": [
            {"title": "AI SaaS trends", "text": "..."},
            {"title": "Automation tools", "text": "..."}
        ],
        "query_context": "AI automation"
    }
    """
    vector_search = get_vector_search()
    
    try:
        success = await vector_search.index_connector_data(
            platform=request.platform,
            data=request.data,
            query_context=request.query_context
        )
        
        return {
            "success": success,
            "platform": request.platform,
            "indexed_count": len(request.data),
            "message": f"Indexed {len(request.data)} items from {request.platform}"
        }
        
    except Exception as e:
        logger.error(f"[VectorSearchAPI] Indexing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/connectors")
async def search_connectors(
    q: str = Query(..., description="Search query"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    limit: int = Query(10, ge=1, le=100, description="Number of results")
):
    """
    Quick semantic search across connectors
    
    Example:
    GET /api/vector/search/connectors?q=AI automation&platform=reddit&limit=5
    
    Searches ALL indexed connector data semantically.
    """
    vector_search = get_vector_search()
    
    try:
        results = await vector_search.semantic_search(
            query=q,
            collection_name="connector_data",
            limit=limit,
            filter_platform=platform
        )
        
        return {
            "success": True,
            "query": q,
            "platform_filter": platform,
            "total_results": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"[VectorSearchAPI] Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/memory")
async def search_agent_memory(
    q: str = Query(..., description="Problem description"),
    agent: Optional[str] = Query(None, description="Filter by agent name"),
    limit: int = Query(5, ge=1, le=50, description="Number of results")
):
    """
    Search agent memory for similar past solutions (RAG)
    
    Example:
    GET /api/vector/search/memory?q=Cannot import module&limit=5
    
    Finds similar past problems and their solutions.
    """
    vector_search = get_vector_search()
    
    try:
        results = await vector_search.find_similar_solutions(
            problem_description=q,
            agent_name=agent,
            limit=limit
        )
        
        return {
            "success": True,
            "query": q,
            "agent_filter": agent,
            "total_results": len(results),
            "solutions": results
        }
        
    except Exception as e:
        logger.error(f"[VectorSearchAPI] Memory search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/errors")
async def search_similar_errors(
    error: str = Query(..., description="Error message"),
    limit: int = Query(5, ge=1, le=20, description="Number of similar errors")
):
    """
    Find similar past errors for self-healing
    
    Example:
    GET /api/vector/search/errors?error=ImportError: cannot import name&limit=5
    
    Returns similar past errors with their solutions.
    """
    vector_search = get_vector_search()
    
    try:
        results = await vector_search.find_similar_errors(
            error_message=error,
            limit=limit
        )
        
        return {
            "success": True,
            "error_query": error,
            "total_results": len(results),
            "similar_errors": results
        }
        
    except Exception as e:
        logger.error(f"[VectorSearchAPI] Error search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """Get vector search statistics"""
    vector_search = get_vector_search()
    return vector_search.get_stats()
