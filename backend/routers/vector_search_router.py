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


@router.post("/search/hybrid")
async def hybrid_search(
    query: str,
    platforms: Optional[List[str]] = None,
    limit: int = 10,
    semantic_weight: float = 0.7
):
    """
    Hybrid search: Combines real-time connector search + semantic vector search
    
    Args:
        query: Search query
        platforms: List of platforms to search (default: all)
        limit: Results per platform
        semantic_weight: Weight for semantic results (0.0-1.0, default 0.7)
    
    Example:
    POST /api/vector/search/hybrid
    {
        "query": "AI automation tools",
        "platforms": ["reddit", "twitter"],
        "limit": 5,
        "semantic_weight": 0.7
    }
    
    Returns:
    - Real-time results from connectors (30% weight)
    - Semantic results from vector DB (70% weight)
    - Combined and ranked by relevance
    """
    vector_search = get_vector_search()
    
    results = {
        "query": query,
        "real_time_results": [],
        "semantic_results": [],
        "combined_results": []
    }
    
    try:
        # 1. Get semantic results from vector DB
        semantic_results = await vector_search.semantic_search(
            query=query,
            collection_name="connector_data",
            limit=limit * 2  # Get more for better ranking
        )
        
        results["semantic_results"] = semantic_results[:limit]
        
        # 2. If platforms specified, get real-time results
        if platforms:
            ecosystem = get_connector_ecosystem()
            
            for platform in platforms:
                try:
                    # Quick search on platform
                    platform_data = await ecosystem.fetch_data(
                        platform,
                        {"type": "search", "query": query, "limit": limit}
                    )
                    
                    results["real_time_results"].extend([
                        {
                            "platform": platform,
                            "data": item,
                            "source": "real_time"
                        }
                        for item in platform_data[:limit]
                    ])
                except Exception as e:
                    logger.warning(f"[HybridSearch] {platform} search failed: {e}")
        
        # 3. Combine and rank results
        # Semantic results get higher weight (default 70%)
        combined = []
        
        for idx, result in enumerate(results["semantic_results"]):
            combined.append({
                **result,
                "source": "semantic",
                "rank_score": result.get("similarity", 0) * semantic_weight
            })
        
        for idx, result in enumerate(results["real_time_results"]):
            # Real-time results get lower weight but are fresher
            combined.append({
                **result,
                "source": "real_time",
                "rank_score": (1 - idx / max(len(results["real_time_results"]), 1)) * (1 - semantic_weight)
            })
        
        # Sort by rank score
        combined.sort(key=lambda x: x.get("rank_score", 0), reverse=True)
        results["combined_results"] = combined[:limit]
        
        return {
            "success": True,
            "query": query,
            "total_results": len(combined),
            "results": results["combined_results"],
            "metadata": {
                "semantic_count": len(results["semantic_results"]),
                "real_time_count": len(results["real_time_results"]),
                "semantic_weight": semantic_weight
            }
        }
        
    except Exception as e:
        logger.error(f"[HybridSearch] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
