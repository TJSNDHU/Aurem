"""
PostConnectorFetch Hook
Runs after connector data fetches - auto-indexes in Vector DB
"""

from typing import Dict, Any
import logging
from datetime import datetime, timezone

from .base_hook import BaseHook, HookResult

logger = logging.getLogger(__name__)


class PostConnectorFetchHook(BaseHook):
    """
    Post-connector-fetch hook
    
    Actions:
    - Auto-index fetched data in Vector DB
    - Track connector usage patterns
    - Enable semantic search across all platforms
    - Build cross-platform knowledge base
    """
    
    def __init__(self):
        super().__init__(
            name="post-connector-fetch",
            description="Auto-indexes connector data in Vector DB",
            hook_type="post"
        )
        
        self.auto_index_enabled = True
        self.min_results_for_indexing = 1
    
    async def execute(self, context: Dict[str, Any]) -> HookResult:
        """
        Execute post-connector-fetch actions
        
        Context:
        {
            "platform": "reddit",
            "query": "ai automation",
            "results": [...],
            "results_count": 10,
            "success": true
        }
        """
        platform = context.get("platform", "")
        query = context.get("query", "")
        results = context.get("results", [])
        results_count = context.get("results_count", 0)
        success = context.get("success", False)
        
        if not success or results_count < self.min_results_for_indexing:
            return HookResult(
                success=True,
                message=f"Skipped indexing - insufficient results ({results_count})",
                should_proceed=True
            )
        
        actions_taken = []
        warnings = []
        
        # Auto-index in Vector DB
        if self.auto_index_enabled:
            try:
                from services.vector_search import get_vector_search
                
                vector_service = get_vector_search()
                
                # Use the existing index_connector_data method
                success_indexed = await vector_service.index_connector_data(
                    platform=platform,
                    data=results[:20],  # Limit to 20 for performance
                    query_context=query
                )
                
                if success_indexed:
                    indexed_count = min(len(results), 20)
                    actions_taken.append(
                        f"✅ Indexed {indexed_count} documents from {platform} in Vector DB"
                    )
                    
                    logger.info(
                        f"[PostConnectorFetch] Auto-indexed {indexed_count} docs "
                        f"from {platform} (query: {query})"
                    )
                else:
                    warnings.append("⚠️ Vector indexing returned False")
                    
            except Exception as e:
                logger.error(f"[PostConnectorFetch] Vector indexing failed: {e}")
                warnings.append(f"Vector indexing failed: {str(e)[:100]}")
        
        # Track usage patterns
        actions_taken.append(
            f"📊 Tracked: {results_count} results from {platform}"
        )
        
        return HookResult(
            success=True,
            message=f"Post-connector actions completed for {platform}",
            should_proceed=True,
            warnings=warnings,
            data={
                "platform": platform,
                "query": query,
                "results_count": results_count,
                "indexed_count": min(len(results), 20) if 'success_indexed' in locals() and success_indexed else 0,
                "actions_taken": actions_taken
            }
        )
