"""
AUREM Vector Search Service
Semantic search using ChromaDB + OpenAI embeddings

Features:
- Semantic search across connectors
- Agent memory (RAG)
- Code pattern search
- Error pattern matching
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

import chromadb
from chromadb.config import Settings
from openai import OpenAI

# Import TenantContext for multi-tenancy support
try:
    from services.multi_tenancy_service import TenantContext
except ImportError:
    # Fallback if multi_tenancy_service not available
    class TenantContext:
        @classmethod
        def get_tenant(cls):
            return None

logger = logging.getLogger(__name__)


class VectorSearchService:
    """
    Vector search service for AUREM
    
    Uses:
    - ChromaDB for vector storage
    - OpenAI embeddings (text-embedding-3-small)
    - Emergent LLM key
    """
    
    def __init__(self):
        self.client = None
        self.openai_client = None
        self.collections = {}
        self.embedding_model = "text-embedding-3-small"
        self.embedding_dimension = 1536
        
        # Initialize on first use (lazy loading)
        self._initialized = False
    
    def _initialize(self):
        """Initialize ChromaDB and OpenAI client"""
        if self._initialized:
            return
        
        try:
            # Get Emergent LLM key
            emergent_key = os.environ.get("EMERGENT_LLM_KEY")
            
            if not emergent_key:
                logger.warning("[VectorSearch] No EMERGENT_LLM_KEY found, using demo mode")
                self._initialized = True
                return
            
            # Initialize OpenAI client with Emergent key
            self.openai_client = OpenAI(api_key=emergent_key)
            
            # Initialize ChromaDB (persistent storage)
            chroma_path = "/app/backend/.chromadb"
            self.client = chromadb.PersistentClient(
                path=chroma_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Create or get collections
            self._setup_collections()
            
            self._initialized = True
            logger.info("[VectorSearch] Initialized successfully")
            
        except Exception as e:
            logger.error(f"[VectorSearch] Initialization error: {e}")
            self._initialized = True  # Mark as initialized to avoid retry loops
    
    def _setup_collections(self):
        """Create or get ChromaDB collections"""
        collection_configs = {
            "connector_data": "Connector search results and content",
            "agent_memory": "Agent execution history and solutions",
            "code_patterns": "Code snippets and patterns from AUREM",
            "error_logs": "Error logs for self-healing AI"
        }
        
        for collection_name, description in collection_configs.items():
            try:
                self.collections[collection_name] = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={"description": description}
                )
                logger.info(f"[VectorSearch] Collection '{collection_name}' ready")
            except Exception as e:
                logger.error(f"[VectorSearch] Error creating collection {collection_name}: {e}")
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using OpenAI
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector (1536 dimensions)
        """
        if not self.openai_client:
            # Return dummy embedding in demo mode
            return [0.0] * self.embedding_dimension
        
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"[VectorSearch] Embedding error: {e}")
            return [0.0] * self.embedding_dimension
    
    async def index_connector_data(
        self,
        platform: str,
        data: List[Dict],
        query_context: str = "",
        tenant_id: Optional[str] = None
    ) -> bool:
        """
        Index connector data for semantic search
        
        Args:
            platform: Connector platform (e.g., "reddit", "twitter")
            data: List of data items from connector
            query_context: Original query that fetched this data
            tenant_id: Tenant ID for multi-tenancy isolation (auto-detected if not provided)
        
        Returns:
            Success status
        """
        self._initialize()
        
        if not self.client or "connector_data" not in self.collections:
            logger.warning("[VectorSearch] Not initialized, skipping indexing")
            return False
        
        # MULTI-TENANCY: Get tenant_id from context
        if tenant_id is None:
            tenant_id = TenantContext.get_tenant()
        
        if not tenant_id:
            logger.warning("[VectorSearch] No tenant_id - skipping indexing for safety")
            return False
        
        try:
            collection = self.collections["connector_data"]
            
            for idx, item in enumerate(data):
                # Create searchable text from item
                text = self._create_searchable_text(item, platform)
                
                # Generate unique ID
                doc_id = f"{tenant_id}_{platform}_{datetime.now(timezone.utc).timestamp()}_{idx}"
                
                # Get embedding
                embedding = self._get_embedding(text)
                
                # Store in ChromaDB with tenant_id in metadata
                collection.add(
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[text],
                    metadatas=[{
                        "tenant_id": tenant_id,  # CRITICAL: Multi-tenancy isolation
                        "platform": platform,
                        "query_context": query_context,
                        "indexed_at": datetime.now(timezone.utc).isoformat(),
                        "original_data": str(item)  # Store original for retrieval
                    }]
                )
            
            logger.info(f"[VectorSearch] Indexed {len(data)} items from {platform}")
            return True
            
        except Exception as e:
            logger.error(f"[VectorSearch] Indexing error: {e}")
            return False
    
    def _create_searchable_text(self, item: Dict, platform: str) -> str:
        """Create searchable text from connector data item"""
        text_parts = [f"Platform: {platform}"]
        
        # Extract relevant fields based on platform
        common_fields = ["title", "text", "body", "content", "description", 
                        "summary", "message", "selftext", "name"]
        
        for field in common_fields:
            if field in item and item[field]:
                text_parts.append(f"{field.title()}: {item[field]}")
        
        # Add author/user info
        if "author" in item:
            text_parts.append(f"Author: {item['author']}")
        elif "user" in item:
            text_parts.append(f"User: {item['user']}")
        
        return " | ".join(text_parts)
    
    async def semantic_search(
        self,
        query: str,
        collection_name: str = "connector_data",
        limit: int = 10,
        filter_platform: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search
        
        Args:
            query: Search query (natural language)
            collection_name: Collection to search
            limit: Number of results
            filter_platform: Optional platform filter
            tenant_id: Tenant ID for multi-tenancy (auto-detected if not provided)
        
        Returns:
            List of matching documents with scores
        """
        self._initialize()
        
        if not self.client or collection_name not in self.collections:
            logger.warning("[VectorSearch] Not initialized, returning empty results")
            return []
        
        # MULTI-TENANCY: Get tenant_id from context
        if tenant_id is None:
            tenant_id = TenantContext.get_tenant()
        
        if not tenant_id:
            logger.warning("[VectorSearch] No tenant_id - returning empty results for safety")
            return []
        
        try:
            collection = self.collections[collection_name]
            
            # Generate query embedding
            query_embedding = self._get_embedding(query)
            
            # Build where clause for filtering
            # CRITICAL: Always filter by tenant_id for data isolation
            where_clause = {"tenant_id": tenant_id}
            
            # Add platform filter if provided
            if filter_platform:
                where_clause["platform"] = filter_platform
            
            # Search
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where_clause
            )
            
            # Format results
            formatted_results = []
            
            if results and results["documents"] and len(results["documents"]) > 0:
                for i in range(len(results["documents"][0])):
                    formatted_results.append({
                        "id": results["ids"][0][i],
                        "text": results["documents"][0][i],
                        "distance": results["distances"][0][i] if "distances" in results else 0,
                        "similarity": 1 - (results["distances"][0][i] if "distances" in results else 0),
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {}
                    })
            
            logger.info(f"[VectorSearch] Found {len(formatted_results)} results for '{query}'")
            return formatted_results
            
        except Exception as e:
            logger.error(f"[VectorSearch] Search error: {e}")
            return []
    
    async def index_agent_memory(
        self,
        agent_name: str,
        task: str,
        solution: str,
        success: bool,
        metadata: Optional[Dict] = None,
        tenant_id: Optional[str] = None
    ) -> bool:
        """
        Index agent execution for memory/RAG
        
        Args:
            agent_name: Name of agent
            task: Task description
            solution: Solution applied
            success: Whether it was successful
            metadata: Additional metadata
            tenant_id: Tenant ID for multi-tenancy (auto-detected if not provided)
        
        Returns:
            Success status
        """
        self._initialize()
        
        if not self.client or "agent_memory" not in self.collections:
            return False
        
        # MULTI-TENANCY: Get tenant_id from context
        if tenant_id is None:
            tenant_id = TenantContext.get_tenant()
        
        if not tenant_id:
            logger.warning("[VectorSearch] No tenant_id - skipping agent memory indexing")
            return False
        
        try:
            collection = self.collections["agent_memory"]
            
            # Create searchable text
            text = f"Agent: {agent_name} | Task: {task} | Solution: {solution}"
            
            # Generate embedding
            embedding = self._get_embedding(text)
            
            # Generate ID
            doc_id = f"{tenant_id}_agent_{agent_name}_{datetime.now(timezone.utc).timestamp()}"
            
            # Metadata
            meta = {
                "tenant_id": tenant_id,  # CRITICAL: Multi-tenancy isolation
                "agent_name": agent_name,
                "task": task,
                "solution": solution,
                "success": success,
                "indexed_at": datetime.now(timezone.utc).isoformat()
            }
            
            if metadata:
                meta.update(metadata)
            
            # Store
            collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[meta]
            )
            
            logger.info(f"[VectorSearch] Indexed agent memory for {agent_name}")
            return True
            
        except Exception as e:
            logger.error(f"[VectorSearch] Agent memory indexing error: {e}")
            return False
    
    async def find_similar_errors(
        self,
        error_message: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find similar past errors for self-healing
        
        Args:
            error_message: Current error message
            limit: Number of similar errors to find
        
        Returns:
            List of similar past errors with solutions
        """
        return await self.semantic_search(
            query=error_message,
            collection_name="error_logs",
            limit=limit
        )
    
    async def find_similar_solutions(
        self,
        problem_description: str,
        agent_name: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find similar past solutions (RAG for agents)
        
        Args:
            problem_description: Current problem
            agent_name: Optional agent filter
            limit: Number of results
        
        Returns:
            List of similar past solutions
        """
        return await self.semantic_search(
            query=problem_description,
            collection_name="agent_memory",
            limit=limit
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector search statistics"""
        self._initialize()
        
        if not self.client:
            return {
                "initialized": False,
                "collections": {}
            }
        
        stats = {
            "initialized": True,
            "embedding_model": self.embedding_model,
            "collections": {}
        }
        
        for name, collection in self.collections.items():
            try:
                stats["collections"][name] = {
                    "count": collection.count(),
                    "name": name
                }
            except Exception as e:
                logger.error(f"[VectorSearch] Error getting stats for {name}: {e}")
                stats["collections"][name] = {"error": str(e)}
        
        return stats


# Global instance
_vector_search = VectorSearchService()


def get_vector_search() -> VectorSearchService:
    """Get global vector search instance"""
    return _vector_search
