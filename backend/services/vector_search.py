"""
AUREM Vector Search Service
Semantic search using ChromaDB + local sentence-transformers embeddings

Features:
- Semantic search across connectors
- Agent memory (RAG)
- Social intelligence deep memory
- Error pattern matching
- Zero-cost, on-device 384-dim embeddings (all-MiniLM-L6-v2)
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

# iter 282al-32 — chromadb is a ~150MB transitive tree (pulls numpy,
# onnxruntime, tokenizers, pulsar-client). Importing it at module load
# blocks the Python interpreter cold-start by 30-60 s on K8s pods with
# slow disk → nginx /health probe times out → CrashLoopBackOff.
# Defer the import into _initialize() so server.py module-load stays
# under 2 s and uvicorn binds the port instantly.
chromadb = None        # type: ignore[assignment]
ChromaSettings = None  # type: ignore[assignment]
CHROMA_AVAILABLE = False  # flipped to True on first successful _lazy_import

def _lazy_import_chroma() -> bool:
    """Import chromadb on-demand. Returns True iff available."""
    global chromadb, ChromaSettings, CHROMA_AVAILABLE
    if chromadb is not None:
        return CHROMA_AVAILABLE
    try:
        import chromadb as _cdb
        from chromadb.config import Settings as _Settings
        chromadb = _cdb
        ChromaSettings = _Settings
        CHROMA_AVAILABLE = True
    except ImportError:
        CHROMA_AVAILABLE = False
    return CHROMA_AVAILABLE

from services.embeddings import embed_text, EMBEDDING_DIM

# Import TenantContext for multi-tenancy support
try:
    from services.multi_tenancy_service import TenantContext
except ImportError:
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
    - sentence-transformers all-MiniLM-L6-v2 (384d, local, zero-cost)
    """

    def __init__(self):
        self.client = None
        self.collections = {}
        self.embedding_model = "all-MiniLM-L6-v2"
        self.embedding_dimension = EMBEDDING_DIM
        self._initialized = False

    def _initialize(self):
        """Initialize ChromaDB client"""
        if self._initialized:
            return

        # iter 282al-32 — Lazy-load chromadb on first use
        if not _lazy_import_chroma():
            logger.info("[VectorSearch] chromadb not installed — vector search disabled (non-critical)")
            self._initialized = True
            return

        try:
            chroma_path = "/app/backend/.chromadb"
            self.client = chromadb.PersistentClient(
                path=chroma_path,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            self._setup_collections()
            self._initialized = True
            logger.info("[VectorSearch] Initialized with local embeddings (all-MiniLM-L6-v2, 384d)")

        except Exception as e:
            logger.warning(f"[VectorSearch] Initialization skipped (non-critical): {e}")
            self._initialized = True

    def _setup_collections(self):
        """Create or get ChromaDB collections"""
        collection_configs = {
            "connector_data": "Connector search results and content",
            "agent_memory": "Agent execution history and solutions",
            "code_patterns": "Code snippets and patterns from AUREM",
            "error_logs": "Error logs for self-healing AI",
            "social_intelligence": "Agent-Reach social/news data for ORA Deep Memory",
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
        Generate embedding using local sentence-transformers.
        Never returns zero-vectors — raises on failure.
        """
        try:
            return embed_text(text)
        except Exception as e:
            logger.error(f"[VectorSearch] Embedding error: {e}")
            raise

    async def index_connector_data(
        self,
        platform: str,
        data: List[Dict],
        query_context: str = "",
        tenant_id: Optional[str] = None
    ) -> bool:
        """Index connector data for semantic search"""
        self._initialize()

        if not self.client or "connector_data" not in self.collections:
            logger.warning("[VectorSearch] Not initialized, skipping indexing")
            return False

        if tenant_id is None:
            tenant_id = TenantContext.get_tenant()

        if not tenant_id:
            logger.warning("[VectorSearch] No tenant_id - skipping indexing for safety")
            return False

        try:
            collection = self.collections["connector_data"]

            for idx, item in enumerate(data):
                text = self._create_searchable_text(item, platform)
                doc_id = f"{tenant_id}_{platform}_{datetime.now(timezone.utc).timestamp()}_{idx}"
                embedding = self._get_embedding(text)

                collection.add(
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[text],
                    metadatas=[{
                        "tenant_id": tenant_id,
                        "platform": platform,
                        "query_context": query_context,
                        "indexed_at": datetime.now(timezone.utc).isoformat(),
                        "original_data": str(item)[:500]
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

        common_fields = ["title", "text", "body", "content", "description",
                        "summary", "message", "selftext", "name"]

        for field in common_fields:
            if field in item and item[field]:
                text_parts.append(f"{field.title()}: {item[field]}")

        if "author" in item:
            text_parts.append(f"Author: {item['author']}")
        elif "user" in item:
            text_parts.append(f"User: {item['user']}")

        return " | ".join(text_parts)

    async def ingest_social_intelligence(
        self,
        results: List[Dict],
        source: str,
        query: str = "",
        tenant_id: Optional[str] = None,
    ) -> int:
        """
        DEEP MEMORY BRIDGE: Ingest Agent-Reach social/news results into Vector DB.
        Returns: number of documents ingested.
        """
        self._initialize()

        if not self.client or "social_intelligence" not in self.collections:
            return 0

        if tenant_id is None:
            tenant_id = TenantContext.get_tenant() or "global"

        try:
            collection = self.collections["social_intelligence"]
            ingested = 0

            for idx, item in enumerate(results):
                text = self._create_searchable_text(item, source)
                if not text or len(text) < 20:
                    continue

                doc_id = f"social_{tenant_id}_{source}_{datetime.now(timezone.utc).timestamp()}_{idx}"
                embedding = self._get_embedding(text)

                collection.add(
                    ids=[doc_id],
                    embeddings=[embedding],
                    documents=[text],
                    metadatas=[{
                        "tenant_id": tenant_id,
                        "source": source,
                        "query": query[:200],
                        "relevance": item.get("relevance", item.get("score", 0.5)),
                        "ingested_at": datetime.now(timezone.utc).isoformat(),
                        "url": item.get("url", item.get("link", "")),
                    }]
                )
                ingested += 1

            logger.info(f"[VectorSearch] Ingested {ingested} social items from {source} for {tenant_id}")
            return ingested

        except Exception as e:
            logger.error(f"[VectorSearch] Social ingestion error: {e}")
            return 0

    async def semantic_search(
        self,
        query: str,
        collection_name: str = "connector_data",
        limit: int = 10,
        filter_platform: Optional[str] = None,
        tenant_id: Optional[str] = None,
        min_score: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search with optional similarity threshold.

        Args:
            min_score: Minimum similarity score (0-1). Results below this are filtered out.
        """
        self._initialize()

        if not self.client or collection_name not in self.collections:
            logger.warning("[VectorSearch] Not initialized, returning empty results")
            return []

        if tenant_id is None:
            tenant_id = TenantContext.get_tenant()

        if not tenant_id:
            logger.warning("[VectorSearch] No tenant_id - returning empty results for safety")
            return []

        try:
            collection = self.collections[collection_name]

            query_embedding = self._get_embedding(query)

            where_clause = {"tenant_id": tenant_id}
            if filter_platform:
                where_clause["platform"] = filter_platform

            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where_clause
            )

            formatted_results = []

            if results and results["documents"] and len(results["documents"]) > 0:
                for i in range(len(results["documents"][0])):
                    distance = results["distances"][0][i] if "distances" in results else 0
                    similarity = 1 - distance

                    if similarity < min_score:
                        continue

                    formatted_results.append({
                        "id": results["ids"][0][i],
                        "text": results["documents"][0][i],
                        "distance": distance,
                        "similarity": similarity,
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
        """Index agent execution for memory/RAG"""
        self._initialize()

        if not self.client or "agent_memory" not in self.collections:
            return False

        if tenant_id is None:
            tenant_id = TenantContext.get_tenant()

        if not tenant_id:
            logger.warning("[VectorSearch] No tenant_id - skipping agent memory indexing")
            return False

        try:
            collection = self.collections["agent_memory"]
            text = f"Agent: {agent_name} | Task: {task} | Solution: {solution}"
            embedding = self._get_embedding(text)
            doc_id = f"{tenant_id}_agent_{agent_name}_{datetime.now(timezone.utc).timestamp()}"

            meta = {
                "tenant_id": tenant_id,
                "agent_name": agent_name,
                "task": task,
                "solution": solution,
                "success": success,
                "indexed_at": datetime.now(timezone.utc).isoformat()
            }
            if metadata:
                meta.update(metadata)

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
        """Find similar past errors for self-healing"""
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
        """Find similar past solutions (RAG for agents)"""
        return await self.semantic_search(
            query=problem_description,
            collection_name="agent_memory",
            limit=limit
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get vector search statistics"""
        self._initialize()

        if not self.client:
            return {"initialized": False, "collections": {}}

        stats = {
            "initialized": True,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "vector_version": "v2",
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
