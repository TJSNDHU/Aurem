"""
RAG Embedder for WhatsApp AI
Generates and maintains FAISS index of product embeddings.
Refreshes every 6 hours from MongoDB products collection.

Uses sentence-transformers (all-MiniLM-L6-v2) for 384-dim embeddings.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import numpy as np

from services.embeddings import embed_text, embed_texts, EMBEDDING_DIM

logger = logging.getLogger(__name__)

# Global state
_faiss_index = None
_product_data: List[Dict[str, Any]] = []
_last_refresh: Optional[datetime] = None

# Refresh interval (6 hours)
REFRESH_INTERVAL_SECONDS = 6 * 60 * 60


def product_to_text(product: Dict[str, Any]) -> str:
    """Convert product document to searchable text."""
    parts = []

    name = product.get("name", "")
    brand = product.get("brand", "")
    if name:
        parts.append(f"Product: {name}")
    if brand:
        parts.append(f"Brand: {brand}")

    brand_owner = product.get("brand_owner", "")
    if brand_owner:
        parts.append(f"Owned by: {brand_owner}")

    description = product.get("description", "")
    if description:
        parts.append(f"Description: {description}")

    ingredients = product.get("ingredients", [])
    if isinstance(ingredients, list) and ingredients:
        parts.append(f"Ingredients: {', '.join(ingredients[:10])}")
    elif isinstance(ingredients, str) and ingredients:
        parts.append(f"Ingredients: {ingredients}")

    price = product.get("price", 0)
    volume = product.get("volume", "")
    if price:
        parts.append(f"Price: CAD ${price}")
    if volume:
        parts.append(f"Size: {volume}")

    usage = product.get("usage_instructions", "") or product.get("usage", "")
    if usage:
        parts.append(f"Usage: {usage}")

    benefits = product.get("benefits", []) or product.get("key_benefits", [])
    if benefits:
        if isinstance(benefits, list):
            parts.append(f"Benefits: {', '.join(benefits[:5])}")
        else:
            parts.append(f"Benefits: {benefits}")

    cnf_status = product.get("cnf_filed", False)
    if cnf_status:
        parts.append("Health Canada CNF: Filed")

    return "\n".join(parts)


def generate_embedding(text: str) -> List[float]:
    """Generate embedding using local sentence-transformers."""
    return embed_text(text)


async def refresh_index(db) -> bool:
    """Refresh the FAISS index from MongoDB products."""
    global _faiss_index, _product_data, _last_refresh

    try:
        import faiss
    except ImportError:
        logger.error("faiss-cpu not installed. Run: pip install faiss-cpu")
        return False

    try:
        logger.info("RAG: Starting index refresh from MongoDB...")

        cursor = db.products.find({}, {"_id": 0})
        products = await cursor.to_list(length=1000)

        if not products:
            logger.warning("RAG: No products found in database")
            return False

        logger.info(f"RAG: Found {len(products)} products, generating embeddings...")

        texts = []
        valid_products = []

        for product in products:
            text = product_to_text(product)
            if len(text.strip()) < 20:
                continue
            texts.append(text)
            valid_products.append(product)

        if not texts:
            logger.error("RAG: No valid products to embed")
            return False

        # Batch embed all texts at once (much faster)
        embeddings = embed_texts(texts)

        # Build FAISS index
        embeddings_array = np.array(embeddings, dtype=np.float32)
        index = faiss.IndexFlatL2(EMBEDDING_DIM)
        index.add(embeddings_array)

        _faiss_index = index
        _product_data = valid_products
        _last_refresh = datetime.now(timezone.utc)

        logger.info(f"RAG: Index built with {len(valid_products)} products ({EMBEDDING_DIM}d)")
        return True

    except Exception as e:
        logger.error(f"RAG: Index refresh failed: {e}")
        return False


async def ensure_index(db) -> bool:
    """Ensure index is loaded and fresh. Refresh if needed."""
    global _faiss_index, _last_refresh

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
                product["_similarity_score"] = float(1 / (1 + distances[0][i]))
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
        "index_loaded": _faiss_index is not None,
        "embedding_dim": EMBEDDING_DIM,
        "embedding_model": "all-MiniLM-L6-v2",
    }
