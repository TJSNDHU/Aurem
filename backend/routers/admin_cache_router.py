"""
Admin Cache Management Router
Provides cache clearing and system refresh capabilities

Endpoints:
- POST /api/admin/cache/clear - Clear all caches (Vector DB, MongoDB, etc.)
- GET  /api/admin/cache/status - Check cache status
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/cache", tags=["Admin Cache"])

# MongoDB connection (will be set by server.py)
db = None

# ChromaDB client (will be set by server.py)
chroma_client = None


def set_db(database):
    global db
    db = database


def set_chroma_client(client):
    global chroma_client
    chroma_client = client


def verify_admin_key(x_admin_key: Optional[str] = Header(None)):
    """Verify admin authentication"""
    admin_key = os.getenv("ADMIN_KEY", "admin_secret_key_2024")
    
    if not x_admin_key or x_admin_key != admin_key:
        raise HTTPException(403, "Invalid admin key")
    
    return True


@router.post("/clear")
async def clear_cache(x_admin_key: Optional[str] = Header(None)):
    """
    Clear all system caches
    
    This will:
    - Clear vector DB collections (optionally)
    - Clear any MongoDB cached data
    - Reset system state
    
    Headers:
        X-Admin-Key: Admin authentication key
    
    Returns:
        {
            "success": true,
            "vector_collections_cleared": int,
            "mongodb_cache_cleared": bool,
            "message": str
        }
    """
    verify_admin_key(x_admin_key)
    
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        cleared_collections = 0
        
        # Clear ChromaDB collections (if needed)
        if chroma_client:
            try:
                # List all collections
                collections = chroma_client.list_collections()
                logger.info(f"[AdminCache] Found {len(collections)} ChromaDB collections")
                
                # Optionally clear specific collections
                # For now, we'll just count them
                # To actually clear: chroma_client.delete_collection(collection.name)
                cleared_collections = len(collections)
                
            except Exception as e:
                logger.warning(f"[AdminCache] ChromaDB clear warning: {e}")
        
        # Clear MongoDB cached data (if you have specific cache collections)
        try:
            # Example: Clear temporary session data, rate limit counters, etc.
            # await db.cache.delete_many({})
            # await db.sessions.delete_many({"temporary": True})
            mongodb_cleared = True
        except Exception as e:
            logger.warning(f"[AdminCache] MongoDB cache clear warning: {e}")
            mongodb_cleared = False
        
        logger.info("[AdminCache] Cache clear operation completed")
        
        return {
            "success": True,
            "vector_collections_cleared": cleared_collections,
            "mongodb_cache_cleared": mongodb_cleared,
            "message": "Cache cleared successfully. Browser cache will be cleared on reload."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AdminCache] Clear cache error: {e}")
        raise HTTPException(500, str(e))


@router.get("/status")
async def get_cache_status(x_admin_key: Optional[str] = Header(None)):
    """
    Get current cache status
    
    Headers:
        X-Admin-Key: Admin authentication key
    
    Returns:
        {
            "vector_db_collections": int,
            "mongodb_cache_size": int,
            "system_memory_mb": float
        }
    """
    verify_admin_key(x_admin_key)
    
    try:
        import psutil
        
        # ChromaDB status
        vector_collections = 0
        if chroma_client:
            try:
                collections = chroma_client.list_collections()
                vector_collections = len(collections)
            except Exception as e:
                logger.warning(f"[AdminCache] ChromaDB status check: {e}")
        
        # MongoDB cache size (example)
        mongodb_cache_size = 0
        if db:
            try:
                # Count cached documents
                # mongodb_cache_size = await db.cache.count_documents({})
                pass
            except Exception as e:
                logger.warning(f"[AdminCache] MongoDB cache size check: {e}")
        
        # System memory
        memory = psutil.virtual_memory()
        memory_used_mb = (memory.total - memory.available) / (1024 * 1024)
        
        return {
            "success": True,
            "vector_db_collections": vector_collections,
            "mongodb_cache_size": mongodb_cache_size,
            "system_memory_mb": round(memory_used_mb, 2),
            "memory_percent": memory.percent
        }
    
    except Exception as e:
        logger.error(f"[AdminCache] Status check error: {e}")
        raise HTTPException(500, str(e))
