"""
AUREM RAG Knowledge Base Service
=================================
Auto-ingests product data from MongoDB into ChromaDB vector database.
Enables semantic search for the AI Consultant to provide accurate,
context-aware biotech expertise.

Uses sentence-transformers (all-MiniLM-L6-v2) for 384-dim embeddings.
Zero external API cost. Runs entirely on-device.
"""

import os
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Optional
from pymongo import MongoClient
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

from services.embeddings import embed_text, embed_texts, EMBEDDING_DIM, VECTOR_VERSION

import logging

logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "reroots")


class RAGKnowledgeBase:
    """
    RAG Knowledge Base for AI Biotech Specialist.
    Manages product knowledge vectorization and retrieval.
    Uses in-memory ChromaDB with local sentence-transformer embeddings.
    """

    def __init__(self):
        """Initialize ChromaDB and MongoDB connections."""
        if not CHROMA_AVAILABLE:
            logger.warning("[RAG] ChromaDB not available — vector search disabled")
            self.chroma_client = None
            self.product_collection = None
            return
        self.chroma_client = chromadb.Client(ChromaSettings(
            anonymized_telemetry=False,
            allow_reset=True,
            is_persistent=False
        ))

        self.product_collection = self.chroma_client.get_or_create_collection(
            name="reroots_products",
            metadata={"hnsw:space": "cosine"}
        )

        self.biotech_facts_collection = self.chroma_client.get_or_create_collection(
            name="reroots_biotech_facts",
            metadata={"hnsw:space": "cosine"}
        )

        self.mongo_client = MongoClient(MONGO_URL)
        self.db = self.mongo_client[DB_NAME]
        self._auto_ingested = False

        # BM25 keyword index (built during ingestion)
        from services.hybrid_search import BM25Index
        self._bm25_index = BM25Index()

        logger.info(f"[RAG] Knowledge Base initialized (in-memory, {EMBEDDING_DIM}d). Products: {self.product_collection.count()}")

    def _create_product_document(self, product: Dict) -> str:
        """Create a rich text document from product data for embedding."""
        parts = []
        parts.append(f"Product: {product.get('name', 'Unknown')}")

        if product.get('short_description'):
            parts.append(f"Tagline: {product.get('short_description')}")
        if product.get('description'):
            parts.append(f"Description: {product.get('description')}")

        hero_ingredients = product.get('hero_ingredients', [])
        if hero_ingredients:
            parts.append("Key Biotech Ingredients:")
            for ing in hero_ingredients:
                name = ing.get('name', '')
                conc = ing.get('concentration', '')
                desc = ing.get('description', '')
                parts.append(f"  - {name} ({conc}): {desc}")

        if product.get('ingredients'):
            parts.append(f"Full Ingredients: {product.get('ingredients')}")
        if product.get('science_highlight'):
            parts.append(f"Science: {product.get('science_highlight')}")
        if product.get('how_to_use'):
            parts.append(f"How to Use: {product.get('how_to_use')}")
        if product.get('engine_label'):
            parts.append(f"Formula Type: {product.get('engine_label')}")
        if product.get('primary_benefit'):
            parts.append(f"Primary Benefit: {product.get('primary_benefit')}")

        tags = product.get('tags', [])
        if tags:
            parts.append(f"Categories: {', '.join(tags)}")

        return "\n".join(parts)

    def _create_product_metadata(self, product: Dict) -> Dict:
        """Create metadata for product."""
        return {
            "product_id": str(product.get('id', product.get('_id', ''))),
            "name": product.get('name', ''),
            "slug": product.get('slug', ''),
            "category": product.get('category_id', ''),
            "price": float(product.get('price', 0)),
            "compare_price": float(product.get('compare_price', 0) or 0),
            "stock": int(product.get('stock', 0)),
            "is_featured": product.get('is_featured', False),
            "engine_type": product.get('engine_type', ''),
            "brand": product.get('brand', 'AUREM'),
            "has_pdrn": 'pdrn' in str(product).lower(),
            "has_egf": 'egf' in str(product).lower(),
            "has_peptides": 'peptide' in str(product).lower(),
        }

    def ingest_products(self, force_refresh: bool = False) -> Dict:
        """Ingest all products from MongoDB into ChromaDB."""
        logger.info("[RAG] Starting product ingestion...")

        if force_refresh:
            try:
                self.chroma_client.delete_collection("reroots_products")
                self.product_collection = self.chroma_client.get_or_create_collection(
                    name="reroots_products",
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                logger.warning(f"[RAG] Collection reset error: {e}")

        products = list(self.db.products.find({"is_active": {"$ne": False}}))
        logger.info(f"[RAG] Found {len(products)} products to ingest")

        ingested = 0
        errors = 0
        biotech_facts = []

        for product in products:
            try:
                product_id = str(product.get('id', product.get('_id', '')))

                if not force_refresh:
                    existing = self.product_collection.get(ids=[product_id])
                    if existing and existing['ids']:
                        continue

                doc_text = self._create_product_document(product)
                embedding = embed_text(doc_text)
                metadata = self._create_product_metadata(product)

                self.product_collection.add(
                    ids=[product_id],
                    embeddings=[embedding],
                    documents=[doc_text],
                    metadatas=[metadata]
                )
                ingested += 1

                for ing in product.get('hero_ingredients', []):
                    fact = {
                        "ingredient": ing.get('name', ''),
                        "concentration": ing.get('concentration', ''),
                        "benefit": ing.get('description', ''),
                        "product": product.get('name', ''),
                        "product_id": product_id
                    }
                    biotech_facts.append(fact)

            except Exception as e:
                logger.error(f"[RAG] Error ingesting {product.get('name')}: {e}")
                errors += 1

        facts_ingested = self._ingest_biotech_facts(biotech_facts)

        # Build BM25 index from all ingested documents
        self._rebuild_bm25_index()

        result = {
            "products_ingested": ingested,
            "products_errors": errors,
            "biotech_facts_ingested": facts_ingested,
            "total_products_in_kb": self.product_collection.count(),
            "vector_version": VECTOR_VERSION,
            "embedding_model": "all-MiniLM-L6-v2",
            "embedding_dim": EMBEDDING_DIM,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        logger.info(f"[RAG] Ingestion complete: {result}")
        return result

    def _ingest_biotech_facts(self, facts: List[Dict]) -> int:
        """Ingest individual biotech facts for granular retrieval."""
        ingested = 0

        for i, fact in enumerate(facts):
            try:
                fact_text = f"{fact['ingredient']} at {fact['concentration']}: {fact['benefit']} (Found in {fact['product']})"
                fact_id = f"fact_{i}_{hashlib.sha256(fact_text.encode()).hexdigest()[:8]}"

                embedding = embed_text(fact_text)

                self.biotech_facts_collection.add(
                    ids=[fact_id],
                    embeddings=[embedding],
                    documents=[fact_text],
                    metadatas=[{
                        "ingredient": fact['ingredient'],
                        "concentration": fact['concentration'],
                        "product_id": fact['product_id'],
                        "product_name": fact['product']
                    }]
                )
                ingested += 1
            except Exception:
                continue

        return ingested

    def _rebuild_bm25_index(self):
        """Rebuild BM25 keyword index from ChromaDB products."""
        try:
            all_data = self.product_collection.get(
                include=["documents", "metadatas"]
            )
            if all_data and all_data["ids"]:
                self._bm25_index.build(
                    doc_ids=all_data["ids"],
                    documents=all_data["documents"],
                    metadatas=all_data["metadatas"],
                )
                logger.info(f"[RAG] BM25 index built: {len(all_data['ids'])} documents")
        except Exception as e:
            logger.warning(f"[RAG] BM25 index build failed: {e}")

    def search_products(
        self,
        query: str,
        top_k: int = 5,
        include_price: bool = False,
        include_stock: bool = False,
        metadata_filter: Optional[Dict] = None,
        use_hybrid: bool = True,
        use_mmr: bool = True,
        mmr_lambda: float = 0.7,
    ) -> List[Dict]:
        """Search for relevant products using hybrid search (BM25 + Vector + MMR)."""
        if self.product_collection.count() == 0 and not self._auto_ingested:
            logger.info("[RAG] Auto-ingesting products on first query...")
            self.ingest_products(force_refresh=True)
            self._auto_ingested = True

        if self.product_collection.count() == 0:
            return []

        query_embedding = embed_text(query)

        # Vector search via ChromaDB
        chroma_filter = None
        if metadata_filter:
            chroma_filter = {}
            for k, v in metadata_filter.items():
                if isinstance(v, dict):
                    for op, val in v.items():
                        if op == "$gte": chroma_filter[k] = {"$gte": val}
                        elif op == "$lte": chroma_filter[k] = {"$lte": val}
                elif isinstance(v, (str, int, float, bool)):
                    chroma_filter[k] = v

        try:
            vector_results_raw = self.product_collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k * 3, self.product_collection.count()),
                include=["documents", "metadatas", "distances", "embeddings"],
                where=chroma_filter if chroma_filter else None,
            )
        except Exception:
            # ChromaDB where filter may fail on certain types, retry without
            vector_results_raw = self.product_collection.query(
                query_embeddings=[query_embedding],
                n_results=min(top_k * 3, self.product_collection.count()),
                include=["documents", "metadatas", "distances", "embeddings"],
            )

        # Format vector results
        vector_results = []
        for i in range(len(vector_results_raw['ids'][0])):
            emb = None
            if vector_results_raw.get('embeddings') and vector_results_raw['embeddings'][0]:
                emb = vector_results_raw['embeddings'][0][i]
            vector_results.append({
                "id": vector_results_raw['ids'][0][i],
                "document": vector_results_raw['documents'][0][i],
                "metadata": vector_results_raw['metadatas'][0][i],
                "relevance_score": 1 - vector_results_raw['distances'][0][i],
                "embedding": emb,
            })

        # Hybrid search with BM25 + MMR
        if use_hybrid and hasattr(self, '_bm25_index') and self._bm25_index.count > 0:
            from services.hybrid_search import hybrid_search
            hybrid_result = hybrid_search(
                query=query,
                vector_results=vector_results,
                bm25_index=self._bm25_index,
                top_k=top_k,
                metadata_filter=metadata_filter,
                use_mmr=use_mmr,
                mmr_lambda=mmr_lambda,
                query_embedding=query_embedding,
            )
            raw_results = hybrid_result["results"]
        else:
            raw_results = vector_results[:top_k]

        # Format output
        products = []
        for result in raw_results:
            meta = result.get("metadata", {})
            product_info = {
                "product_id": result.get("id", ""),
                "name": meta.get("name", ""),
                "relevance_score": result.get("relevance_score", result.get("hybrid_score", 0)),
                "biotech_info": result.get("document", ""),
                "category": meta.get("category", ""),
                "engine_type": meta.get("engine_type", ""),
                "is_featured": meta.get("is_featured", False),
                "retrieval_method": result.get("retrieval_method", "vector"),
            }
            if include_price:
                product_info["price"] = meta.get("price", 0)
                product_info["compare_price"] = meta.get("compare_price", 0)
            if include_stock:
                product_info["stock"] = meta.get("stock", 0)
            products.append(product_info)

        return products

    def search_biotech_facts(self, query: str, top_k: int = 3) -> List[Dict]:
        """Search for specific biotech facts."""
        if self.biotech_facts_collection.count() == 0:
            return []

        query_embedding = embed_text(query)

        results = self.biotech_facts_collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.biotech_facts_collection.count()),
            include=["documents", "metadatas", "distances"]
        )

        facts = []
        for i in range(len(results['ids'][0])):
            facts.append({
                "fact": results['documents'][0][i],
                "ingredient": results['metadatas'][0][i].get('ingredient', ''),
                "concentration": results['metadatas'][0][i].get('concentration', ''),
                "product_name": results['metadatas'][0][i].get('product_name', ''),
                "relevance_score": 1 - results['distances'][0][i]
            })

        return facts

    def get_context_for_query(
        self,
        query: str,
        include_price: bool = False,
        include_stock: bool = False
    ) -> str:
        """Generate rich context string for the AI Consultant."""
        products = self.search_products(query, top_k=3, include_price=include_price, include_stock=include_stock)
        facts = self.search_biotech_facts(query, top_k=3)

        context_parts = []

        if facts:
            context_parts.append("=== BIOTECH KNOWLEDGE ===")
            for fact in facts:
                context_parts.append(f"  {fact['fact']}")

        if products:
            context_parts.append("\n=== RELEVANT PRODUCTS ===")
            for prod in products:
                context_parts.append(f"\n[{prod['name']}]")
                bio_info = prod['biotech_info'][:500]
                context_parts.append(bio_info)
                if include_price and 'price' in prod:
                    context_parts.append(f"Price: ${prod['price']:.2f}")
                if include_stock and 'stock' in prod:
                    context_parts.append(f"Stock: {prod['stock']} units")

        return "\n".join(context_parts)

    def get_stats(self) -> Dict:
        """Get knowledge base statistics."""
        return {
            "total_products": self.product_collection.count(),
            "total_biotech_facts": self.biotech_facts_collection.count(),
            "embedding_model": "all-MiniLM-L6-v2",
            "embedding_dim": EMBEDDING_DIM,
            "vector_version": VECTOR_VERSION,
            "last_check": datetime.now(timezone.utc).isoformat()
        }


# Singleton instance
_rag_kb = None

def get_rag_knowledge_base() -> RAGKnowledgeBase:
    """Get or create the RAG Knowledge Base singleton."""
    global _rag_kb
    if _rag_kb is None:
        _rag_kb = RAGKnowledgeBase()
    return _rag_kb
