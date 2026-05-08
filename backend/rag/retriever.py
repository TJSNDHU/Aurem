"""
RAG Retriever for WhatsApp AI
═══════════════════════════════════════════════════════════════════
Retrieves relevant product context for LLM prompts.
Now with confidence scoring, web search fallback, and TOON format.
═══════════════════════════════════════════════════════════════════
"""

import logging
from typing import Optional, Tuple, List, Dict, Any

from .embedder import (
    ensure_index, 
    search_index, 
    generate_embedding, 
    get_index_stats
)

# Import TOON converter
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.toon import json_to_toon

logger = logging.getLogger(__name__)

# Module-level db reference
_db = None

# Confidence threshold - below this, trigger web search
CONFIDENCE_THRESHOLD = 0.65


def init_retriever(db):
    """Initialize the retriever with database reference."""
    global _db
    _db = db
    logger.info("RAG: Retriever initialized")


async def retrieve_context(query: str, top_k: int = 3) -> str:
    """
    Retrieve relevant product context for a customer query.
    
    Args:
        query: Customer's message/question
        top_k: Number of products to retrieve (default 3)
    
    Returns:
        Formatted string of relevant product information
    """
    context, _ = await retrieve_context_with_confidence(query, top_k)
    return context


async def retrieve_context_with_confidence(query: str, top_k: int = 3) -> Tuple[str, float]:
    """
    Retrieve relevant product context with confidence score.
    
    Args:
        query: Customer's message/question
        top_k: Number of products to retrieve (default 3)
    
    Returns:
        Tuple of (formatted context string, max confidence score)
    """
    global _db
    
    if _db is None:
        logger.warning("RAG: Retriever not initialized (no db)")
        return "", 0.0
    
    try:
        # Ensure index is loaded
        await ensure_index(_db)
        
        # Generate query embedding
        query_embedding = generate_embedding(query)
        
        # Search for similar products
        results = search_index(query_embedding, top_k)
        
        if not results:
            return "", 0.0
        
        # Get max confidence from results
        max_confidence = max(
            product.get("_similarity_score", 0.0) 
            for product in results
        )
        
        # Build product list for TOON conversion
        product_list = []
        for product in results:
            # Extract relevant fields for LLM context
            product_data = {
                "name": product.get("name", "Unknown"),
                "brand": product.get("brand", ""),
                "company": product.get("brand_owner", ""),
                "price": f"CAD ${product.get('price', 'N/A')}",
                "size": product.get("volume", ""),
            }
            
            # Add description (truncated)
            desc = product.get("description", "")
            if desc:
                product_data["description"] = desc[:150] + "..." if len(desc) > 150 else desc
            
            # Add ingredients
            ingredients = product.get("ingredients", [])
            if ingredients:
                if isinstance(ingredients, list):
                    product_data["ingredients"] = ", ".join(ingredients[:6])
                else:
                    product_data["ingredients"] = str(ingredients)[:100]
            
            # Add benefits
            benefits = product.get("benefits", []) or product.get("key_benefits", [])
            if benefits:
                if isinstance(benefits, list):
                    product_data["benefits"] = ", ".join(benefits[:3])
                else:
                    product_data["benefits"] = str(benefits)[:80]
            
            product_list.append(product_data)
        
        # Convert to TOON format for LLM
        context = json_to_toon(product_list, "Products")
        
        logger.info(f"RAG: Retrieved {len(results)} products in TOON format, max confidence: {max_confidence:.2f}")
        return context, max_confidence
        
    except Exception as e:
        logger.error(f"RAG: Retrieval failed: {e}")
        return "", 0.0


def needs_web_search(confidence: float) -> bool:
    """Check if confidence is too low and web search is needed."""
    return confidence < CONFIDENCE_THRESHOLD


def build_rag_system_prompt(base_prompt: str, context: str) -> str:
    """
    Build a system prompt with RAG context injected.
    
    Args:
        base_prompt: Original system prompt
        context: Retrieved product context
    
    Returns:
        Enhanced system prompt with grounding data
    """
    if not context:
        return base_prompt
    
    rag_section = f"""
Relevant product information:
{context}

IMPORTANT RULES:
- Always answer based on the product information above
- Never invent product details, prices, or ingredients
- If asked about a product not in the context, say you don't have that information
- Brand ownership is critical: Reroots Aesthetics Inc. owns AURA-GEN and La Vela Bianca. Polaris Built Inc. owns OROÉ. Never mix these.
"""
    
    return f"{base_prompt}\n\n{rag_section}"


async def get_retriever_status() -> dict:
    """Get status of the RAG retriever."""
    stats = get_index_stats()
    return {
        "rag_enabled": True,
        "db_connected": _db is not None,
        **stats
    }
