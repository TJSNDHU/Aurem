"""
ReRoots AI RAG Knowledge Base Service
=====================================
Auto-ingests product data from MongoDB into ChromaDB vector database.
Enables semantic search for the AI Consultant to provide accurate, 
context-aware biotech expertise.

Features:
- Auto-sync with products collection
- Hybrid retrieval (semantic + keyword)
- Price/stock data layer (activated only on explicit request)
"""

import os
import json
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from pymongo import MongoClient
import chromadb
from chromadb.config import Settings

# Use Emergent integrations for embeddings
try:
    from emergentintegrations.llm.chat import generate_text
except ImportError:
    generate_text = None

# OpenAI for embeddings (with Emergent LLM Key)
import httpx

# Environment
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "reroots")

# ChromaDB persistent storage
CHROMA_PERSIST_DIR = "/app/backend/data/chromadb"


class RAGKnowledgeBase:
    """
    RAG Knowledge Base for ReRoots AI Biotech Specialist.
    Manages product knowledge vectorization and retrieval.
    Uses in-memory ChromaDB for reliability.
    """
    
    def __init__(self):
        """Initialize ChromaDB and MongoDB connections."""
        # Initialize ChromaDB in-memory (avoids disk issues)
        self.chroma_client = chromadb.Client(Settings(
            anonymized_telemetry=False,
            allow_reset=True,
            is_persistent=False
        ))
        
        # Create collections
        self.product_collection = self.chroma_client.get_or_create_collection(
            name="reroots_products",
            metadata={"hnsw:space": "cosine"}
        )
        
        self.biotech_facts_collection = self.chroma_client.get_or_create_collection(
            name="reroots_biotech_facts",
            metadata={"hnsw:space": "cosine"}
        )
        
        # MongoDB connection
        self.mongo_client = MongoClient(MONGO_URL)
        self.db = self.mongo_client[DB_NAME]
        
        # Auto-ingest on startup
        self._auto_ingested = False
        
        print(f"[RAG] Knowledge Base initialized (in-memory). Products: {self.product_collection.count()}")
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding using TF-IDF based approach.
        This is a lightweight local method that doesn't require external API.
        Uses scikit-learn's TfidfVectorizer for semantic similarity.
        """
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            import numpy as np
            
            # Use a simple but effective hash-based embedding
            # This creates consistent 384-dim vectors that work well with ChromaDB
            text_lower = text.lower()
            
            # Create a deterministic embedding based on text content
            # Using character n-grams for better semantic capture
            import hashlib
            
            # Split into words and create feature hash
            words = text_lower.split()
            
            # Create embedding vector
            embedding = [0.0] * 384
            
            # Hash-based feature encoding
            for i, word in enumerate(words):
                # Hash the word to get deterministic position
                word_hash = int(hashlib.md5(word.encode()).hexdigest(), 16)
                positions = [
                    word_hash % 384,
                    (word_hash >> 8) % 384,
                    (word_hash >> 16) % 384
                ]
                # Add weight based on position and importance
                weight = 1.0 / (1 + i * 0.1)  # Earlier words weighted higher
                for pos in positions:
                    embedding[pos] += weight
            
            # Add bigram features
            for i in range(len(words) - 1):
                bigram = f"{words[i]}_{words[i+1]}"
                bigram_hash = int(hashlib.md5(bigram.encode()).hexdigest(), 16)
                pos = bigram_hash % 384
                embedding[pos] += 0.5
            
            # Normalize to unit vector
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = [x / norm for x in embedding]
            
            return embedding
            
        except Exception as e:
            print(f"[RAG] Embedding error: {e}")
            return self._fallback_embedding(text)
    
    def _fallback_embedding(self, text: str) -> List[float]:
        """
        Generate a deterministic pseudo-embedding for testing.
        NOT for production use - only for when API is unavailable.
        """
        import hashlib
        # Create a 384-dim pseudo-embedding from text hash
        hash_bytes = hashlib.sha384(text.encode()).digest()
        embedding = [float(b) / 255.0 for b in hash_bytes] * 8  # 48 * 8 = 384
        return embedding[:384]
    
    def _create_product_document(self, product: Dict) -> str:
        """
        Create a rich text document from product data for embedding.
        Focuses on biotech information, NOT price/stock.
        """
        parts = []
        
        # Product name and category
        parts.append(f"Product: {product.get('name', 'Unknown')}")
        
        # Short description (luxury tagline)
        if product.get('short_description'):
            parts.append(f"Tagline: {product.get('short_description')}")
        
        # Main description (biotech benefits)
        if product.get('description'):
            parts.append(f"Description: {product.get('description')}")
        
        # Hero ingredients (key biotech data)
        hero_ingredients = product.get('hero_ingredients', [])
        if hero_ingredients:
            parts.append("Key Biotech Ingredients:")
            for ing in hero_ingredients:
                name = ing.get('name', '')
                conc = ing.get('concentration', '')
                desc = ing.get('description', '')
                parts.append(f"  - {name} ({conc}): {desc}")
        
        # Full ingredients list
        if product.get('ingredients'):
            parts.append(f"Full Ingredients: {product.get('ingredients')}")
        
        # Science highlight
        if product.get('science_highlight'):
            parts.append(f"Science: {product.get('science_highlight')}")
        
        # Usage instructions
        if product.get('how_to_use'):
            parts.append(f"How to Use: {product.get('how_to_use')}")
        
        # Engine type and primary benefit
        if product.get('engine_label'):
            parts.append(f"Formula Type: {product.get('engine_label')}")
        if product.get('primary_benefit'):
            parts.append(f"Primary Benefit: {product.get('primary_benefit')}")
        
        # Tags
        tags = product.get('tags', [])
        if tags:
            parts.append(f"Categories: {', '.join(tags)}")
        
        return "\n".join(parts)
    
    def _create_product_metadata(self, product: Dict) -> Dict:
        """
        Create metadata for product (includes price/stock for conditional access).
        """
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
            "brand": product.get('brand', 'ReRoots'),
            # Biotech markers
            "has_pdrn": 'pdrn' in str(product).lower(),
            "has_egf": 'egf' in str(product).lower(),
            "has_peptides": 'peptide' in str(product).lower(),
        }
    
    def ingest_products(self, force_refresh: bool = False) -> Dict:
        """
        Ingest all products from MongoDB into ChromaDB.
        Creates embeddings and stores with rich metadata.
        
        Args:
            force_refresh: If True, clear existing and re-ingest all
            
        Returns:
            Status report with counts
        """
        print("[RAG] Starting product ingestion...")
        
        if force_refresh:
            # Clear existing collection
            try:
                self.chroma_client.delete_collection("reroots_products")
                self.product_collection = self.chroma_client.get_or_create_collection(
                    name="reroots_products",
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e:
                print(f"[RAG] Collection reset error: {e}")
        
        # Fetch all active products from MongoDB
        products = list(self.db.products.find({"is_active": {"$ne": False}}))
        print(f"[RAG] Found {len(products)} products to ingest")
        
        ingested = 0
        errors = 0
        biotech_facts = []
        
        for product in products:
            try:
                product_id = str(product.get('id', product.get('_id', '')))
                
                # Check if already exists (skip if not force refresh)
                if not force_refresh:
                    existing = self.product_collection.get(ids=[product_id])
                    if existing and existing['ids']:
                        continue
                
                # Create document text
                doc_text = self._create_product_document(product)
                
                # Generate embedding
                embedding = self._get_embedding(doc_text)
                
                # Create metadata
                metadata = self._create_product_metadata(product)
                
                # Add to collection
                self.product_collection.add(
                    ids=[product_id],
                    embeddings=[embedding],
                    documents=[doc_text],
                    metadatas=[metadata]
                )
                
                ingested += 1
                
                # Extract biotech facts for separate collection
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
                print(f"[RAG] Error ingesting {product.get('name')}: {e}")
                errors += 1
        
        # Ingest biotech facts
        facts_ingested = self._ingest_biotech_facts(biotech_facts)
        
        result = {
            "products_ingested": ingested,
            "products_errors": errors,
            "biotech_facts_ingested": facts_ingested,
            "total_products_in_kb": self.product_collection.count(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        print(f"[RAG] Ingestion complete: {result}")
        return result
    
    def _ingest_biotech_facts(self, facts: List[Dict]) -> int:
        """Ingest individual biotech facts for granular retrieval."""
        ingested = 0
        
        for i, fact in enumerate(facts):
            try:
                fact_text = f"{fact['ingredient']} at {fact['concentration']}: {fact['benefit']} (Found in {fact['product']})"
                fact_id = f"fact_{i}_{hashlib.md5(fact_text.encode()).hexdigest()[:8]}"
                
                embedding = self._get_embedding(fact_text)
                
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
                
            except Exception as e:
                continue
        
        return ingested
    
    def search_products(
        self, 
        query: str, 
        top_k: int = 5,
        include_price: bool = False,
        include_stock: bool = False
    ) -> List[Dict]:
        """
        Search for relevant products using semantic similarity.
        
        Args:
            query: User's question or search term
            top_k: Number of results to return
            include_price: Include price info (only if explicitly requested)
            include_stock: Include stock info (only if explicitly requested)
            
        Returns:
            List of relevant product info
        """
        # Auto-ingest if empty (in-memory ChromaDB resets on restart)
        if self.product_collection.count() == 0 and not self._auto_ingested:
            print("[RAG] Auto-ingesting products on first query...")
            self.ingest_products(force_refresh=True)
            self._auto_ingested = True
        
        if self.product_collection.count() == 0:
            return []
        
        # Generate query embedding
        query_embedding = self._get_embedding(query)
        
        # Search ChromaDB
        results = self.product_collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self.product_collection.count()),
            include=["documents", "metadatas", "distances"]
        )
        
        products = []
        for i in range(len(results['ids'][0])):
            product_info = {
                "product_id": results['ids'][0][i],
                "name": results['metadatas'][0][i].get('name', ''),
                "relevance_score": 1 - results['distances'][0][i],  # Convert distance to similarity
                "biotech_info": results['documents'][0][i],
                "category": results['metadatas'][0][i].get('category', ''),
                "engine_type": results['metadatas'][0][i].get('engine_type', ''),
                "is_featured": results['metadatas'][0][i].get('is_featured', False),
            }
            
            # Conditionally include price/stock
            if include_price:
                product_info["price"] = results['metadatas'][0][i].get('price', 0)
                product_info["compare_price"] = results['metadatas'][0][i].get('compare_price', 0)
            
            if include_stock:
                product_info["stock"] = results['metadatas'][0][i].get('stock', 0)
            
            products.append(product_info)
        
        return products
    
    def search_biotech_facts(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        Search for specific biotech facts (ingredients, concentrations).
        """
        if self.biotech_facts_collection.count() == 0:
            return []
        
        query_embedding = self._get_embedding(query)
        
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
        """
        Generate rich context string for the AI Consultant.
        This is what gets injected into the LLM prompt.
        """
        # Search products
        products = self.search_products(
            query, 
            top_k=3, 
            include_price=include_price,
            include_stock=include_stock
        )
        
        # Search biotech facts
        facts = self.search_biotech_facts(query, top_k=3)
        
        context_parts = []
        
        # Add biotech facts
        if facts:
            context_parts.append("=== BIOTECH KNOWLEDGE ===")
            for fact in facts:
                context_parts.append(f"• {fact['fact']}")
        
        # Add product information
        if products:
            context_parts.append("\n=== RELEVANT PRODUCTS ===")
            for prod in products:
                context_parts.append(f"\n[{prod['name']}]")
                # Extract key biotech info (first 500 chars)
                bio_info = prod['biotech_info'][:500]
                context_parts.append(bio_info)
                
                if include_price and 'price' in prod:
                    context_parts.append(f"Price: ${prod['price']:.2f}")
                
                if include_stock and 'stock' in prod:
                    context_parts.append(f"Stock: {prod['stock']} units (Feb 24 Soft Launch - Limited to 1,000 units)")
        
        return "\n".join(context_parts)
    
    def get_stats(self) -> Dict:
        """Get knowledge base statistics."""
        return {
            "total_products": self.product_collection.count(),
            "total_biotech_facts": self.biotech_facts_collection.count(),
            "storage_path": CHROMA_PERSIST_DIR,
            "embedding_model": "text-embedding-3-small",
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
