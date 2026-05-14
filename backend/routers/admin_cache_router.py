"""
Admin Cache Management Router
Provides cache clearing and system refresh capabilities

Endpoints:
- POST /api/admin/cache/clear - Clear all caches (JWT auth)
- GET  /api/admin/cache/status - Check cache status (JWT auth)
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from datetime import datetime, timezone
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cache", tags=["Cache Management"])


def _verify_token(authorization: Optional[str] = None):
    """Verify JWT token for admin cache operations"""
    if not authorization:
        raise HTTPException(401, "Authorization required")
    import jwt
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "Authorization required")
    try:
        secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload.get("user_id", payload.get("id", "unknown"))
    except Exception:
        raise HTTPException(401, "Invalid token")


@router.post("/clear")
async def clear_cache(authorization: Optional[str] = Header(None)):
    """
    Clear all system caches — requires JWT auth

    Clears:
    - Archived repair fixes
    - Stale scan sessions older than 7 days
    - Expired push subscriptions
    - Temporary training extraction files
    - In-memory translation caches

    Returns:
        { success, cleared_items, message }
    """
    user_id = _verify_token(authorization)

    from server import db
    if db is None:
        raise HTTPException(500, "Database not initialized")

    try:
        cleared = {}
        total = 0

        # 1. Clear archived repair fixes
        try:
            result = await db.repair_fixes.delete_many({"status": "archived"})
            cleared["archived_repairs"] = result.deleted_count
            total += result.deleted_count
        except Exception as e:
            logger.warning(f"[Cache] Archived repairs clear: {e}")
            cleared["archived_repairs"] = 0

        # 2. Clear old scan sessions (older than 7 days)
        try:
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            result = await db.scan_sessions.delete_many({"created_at": {"$lt": cutoff}})
            cleared["old_scan_sessions"] = result.deleted_count
            total += result.deleted_count
        except Exception as e:
            logger.warning(f"[Cache] Scan sessions clear: {e}")
            cleared["old_scan_sessions"] = 0

        # 3. Clear stale push subscriptions
        try:
            result = await db.push_subscriptions.delete_many({"stale": True})
            cleared["stale_push_subs"] = result.deleted_count
            total += result.deleted_count
        except Exception as e:
            logger.warning(f"[Cache] Push subs clear: {e}")
            cleared["stale_push_subs"] = 0

        # 4. Clear temporary files from /tmp
        try:
            import glob
            tmp_files = glob.glob("/tmp/ora_extract_*") + glob.glob("/tmp/yt_dlp_*")
            for f in tmp_files:
                try:
                    os.remove(f)
                except Exception:
                    pass
            cleared["temp_files"] = len(tmp_files)
            total += len(tmp_files)
        except Exception as e:
            logger.warning(f"[Cache] Temp files clear: {e}")
            cleared["temp_files"] = 0

        # 5. Clear rejected repair fixes
        try:
            result = await db.repair_fixes.delete_many({"status": "rejected"})
            cleared["rejected_repairs"] = result.deleted_count
            total += result.deleted_count
        except Exception as e:
            logger.warning(f"[Cache] Rejected repairs clear: {e}")
            cleared["rejected_repairs"] = 0

        logger.info(f"[Cache] Cleared {total} items for user {user_id}")

        return {
            "success": True,
            "cleared_items": total,
            "details": cleared,
            "cleared_by": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": f"Cache cleared — {total} items removed"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Cache] Clear error: {e}")
        raise HTTPException(500, str(e))


@router.get("/status")
async def get_cache_status(authorization: Optional[str] = Header(None)):
    """Get current cache status — requires JWT auth"""
    _verify_token(authorization)

    from server import db

    try:
        stats = {}

        # Count cached/archived items
        if db is not None:
            try:
                stats["archived_repairs"] = await db.repair_fixes.count_documents({"status": "archived"})
                stats["rejected_repairs"] = await db.repair_fixes.count_documents({"status": "rejected"})
                stats["total_scan_sessions"] = await db.scan_sessions.count_documents({})
                stats["push_subscriptions"] = await db.push_subscriptions.count_documents({})
                stats["training_files"] = await db.ora_training_files.count_documents({})
            except Exception as e:
                logger.warning(f"[Cache] Status check: {e}")

        # System memory
        try:
            import psutil
            memory = psutil.virtual_memory()
            stats["memory_used_mb"] = round((memory.total - memory.available) / (1024 * 1024), 1)
            stats["memory_percent"] = memory.percent
        except Exception:
            stats["memory_used_mb"] = 0
            stats["memory_percent"] = 0

        return {
            "success": True,
            "cache_stats": stats,
            "clearable_items": stats.get("archived_repairs", 0) + stats.get("rejected_repairs", 0),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"[Cache] Status error: {e}")
        raise HTTPException(500, str(e))
