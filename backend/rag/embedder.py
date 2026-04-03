"""
RAG Embedder for WhatsApp AI
═══════════════════════════════════════════════════════════════════
Generates and maintains FAISS index of product embeddings.
Refreshes every 6 hours from MongoDB products collection.
═══════════════════════════════════════════════════════════════════
"""

import os
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Global state
_faiss_index = None
_product_data: List[Dict[str, Any]] = []
_last_refresh: Optional[datetime] = None
_embedding_dim = 1536  # text-embedding-3-small dimension

# Refresh interval (6 hours)
REFRESH_INTERVAL_SECONDS = 6 * 60 * 60


def get_openai_client():
    """Get OpenAI client for embeddings."""
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY or EMERGENT_LLM_KEY required for embeddings")
    return OpenAI(api_key=api_key)


def product_to_text(product: Dict[str, Any]) -> str:
    """Convert product document to searchable text."""
    parts = []
    
    # Product name and brand
    name = product.get("name", "")
    brand = product.get("brand", "")
    if name:
        parts.append(f"Product: {name}")
    if brand:
        parts.append(f"Brand: {brand}")
    
    # Brand owner (critical for compliance)
    brand_owner = product.get("brand_owner", "")
    if brand_owner:
        parts.append(f"Owned by: {brand_owner}")
    
    # Description
    description = product.get("description", "")
    if description:
        parts.append(f"Description: {description}")
    
    # Ingredients
    ingredients = product.get("ingredients", [])
    if isinstance(ingredients, list) and ingredients:
        parts.append(f"Ingredients: {', '.join(ingredients[:10])}")
    elif isinstance(ingredients, str) and ingredients:
        parts.append(f"Ingredients: {ingredients}")
    
    # Price and volume
    price = product.get("price", 0)
    volume = product.get("volume", "")
    if price:
        parts.append(f"Price: CAD ${price}")
    if volume:
        parts.append(f"Size: {volume}")
    
    # Usage instructions
    usage = product.get("usage_instructions", "") or product.get("usage", "")
    if usage:
        parts.append(f"Usage: {usage}")
    
    # Key benefits
    benefits = product.get("benefits", []) or product.get("key_benefits", [])
    if benefits:
        if isinstance(benefits, list):
            parts.append(f"Benefits: {', '.join(benefits[:5])}")
        else:
            parts.append(f"Benefits: {benefits}")
    
    # Health Canada compliance
    cnf_status = product.get("cnf_filed", False)
    if cnf_status:
        parts.append("Health Canada CNF: Filed")
    
    return "\n".join(parts)


def generate_embedding(text: str) -> List[float]:
    """Generate embedding for text using OpenAI."""
    client = get_openai_client()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


async def refresh_index(db) -> bool:
    """
    Refresh the FAISS index from MongoDB products.
    Returns True if successful, False otherwise.
    """
    global _faiss_index, _product_data, _last_refresh
    
    try:
        import faiss
    except ImportError:
        logger.error("faiss-cpu not installed. Run: pip install faiss-cpu")
        return False
    
    try:
        logger.info("RAG: Starting index refresh from MongoDB...")
        
        # Fetch all products
        cursor = db.products.find({}, {"_id": 0})
        products = await cursor.to_list(length=1000)
        
        if not products:
            logger.warning("RAG: No products found in database")
            return False
        
        logger.info(f"RAG: Found {len(products)} products, generating embeddings...")
        
        # Generate embeddings
        embeddings = []
        valid_products = []
        
        for product in products:
            text = product_to_text(product)
            if len(text.strip()) < 20:
                continue
            
            try:
                embedding = generate_embedding(text)
                embeddings.append(embedding)
                valid_products.append(product)
            except Exception as e:
                logger.warning(f"RAG: Failed to embed product {product.get('name', 'unknown')}: {e}")
                continue
        
        if not embeddings:
            logger.error("RAG: No valid embeddings generated")
            return False
        
        # Build FAISS index
        embeddings_array = np.array(embeddings, dtype=np.float32)
        
        # Use L2 distance (IndexFlatL2)
        index = faiss.IndexFlatL2(_embedding_dim)
        index.add(embeddings_array)
        
        # Update global state
        _faiss_index = index
        _product_data = valid_products
        _last_refresh = datetime.now(timezone.utc)
        
        logger.info(f"RAG: Index built with {len(valid_products)} products")
        return True
        
    except Exception as e:
        logger.error(f"RAG: Index refresh failed: {e}")
        return False


async def ensure_index(db) -> bool:
    """Ensure index is loaded and fresh. Refresh if needed."""
    global _faiss_index, _last_refresh
    
    # Check if refresh needed
    needs_refresh = (
        _faiss_index is None or
        _last_refresh is None or
        (datetime.now(timezone.utc) - _last_refresh).total_seconds() > REFRESH_INTERVAL_SECONDS
    )
    
    if needs_refresh:
        return await refresh_index(db)
    
    return True


def search_index(query_embedding: List[float], top_k: int = 3) -> List[Dict[str, Any]]:
    """Search the FAISS index for similar products."""
    global _faiss_index, _product_data
    
    if _faiss_index is None or not _product_data:
        return []
    
    try:
        import faiss
        
        query_array = np.array([query_embedding], dtype=np.float32)
        distances, indices = _faiss_index.search(query_array, min(top_k, len(_product_data)))
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx >= 0 and idx < len(_product_data):
                product = _product_data[idx].copy()
                product["_similarity_score"] = float(1 / (1 + distances[0][i]))  # Convert distance to similarity
                results.append(product)
        
        return results
        
    except Exception as e:
        logger.error(f"RAG: Search failed: {e}")
        return []


def get_index_stats() -> Dict[str, Any]:
    """Get statistics about the current index."""
    return {
        "indexed_products": len(_product_data),
        "last_refresh": _last_refresh.isoformat() if _last_refresh else None,
        "index_loaded": _faiss_index is not None
    }
