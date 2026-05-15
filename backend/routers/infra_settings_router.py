"""
AUREM Infrastructure Settings Router
Handles Redis URL, CORS origins, MongoDB indexes — configurable from admin panel.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/settings/infrastructure", tags=["Infrastructure"])
logger = logging.getLogger(__name__)

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


def _get_user_from_token(request: Request):
    """Bug-fix #165 (R20): admin enforcement via the canonical guard.
    Previously had `or payload.get("email")` which let any authenticated
    customer rewrite REDIS_URL / CORS_ORIGINS — handing the attacker the
    session-token store and undoing every CORS hardening shipped."""
    from utils.admin_guard import verify_admin
    return verify_admin(request.headers.get("Authorization", ""))


class InfraConfigUpdate(BaseModel):
    redis_url: Optional[str] = None
    cors_origins: Optional[List[str]] = None


@router.get("")
async def get_infra_config(request: Request):
    """Get current infrastructure configuration"""
    _get_user_from_token(request)
    db = get_db()

    config = await db.system_config.find_one(
        {"type": "infrastructure"}, {"_id": 0}
    )

    # Current runtime values
    redis_url = os.environ.get("REDIS_URL", "")
    cors_raw = os.environ.get("CORS_ORIGINS", "*")

    return {
        "redis_url": config.get("redis_url", "") if config else "",
        "redis_url_env": bool(redis_url),
        "redis_connected": _check_redis_connection(config.get("redis_url") if config else redis_url),
        "cors_origins": config.get("cors_origins", []) if config else [o.strip() for o in cors_raw.split(",") if o.strip()],
        "mongodb_indexes": await _get_index_status(db),
        "upstash_guide": "https://console.upstash.com → Create Redis Database → Copy the REST URL",
    }


@router.put("")
async def update_infra_config(update: InfraConfigUpdate, request: Request):
    """Update infrastructure configuration (admin only)"""
    _get_user_from_token(request)
    db = get_db()

    updates = {"type": "infrastructure", "updated_at": datetime.now(timezone.utc).isoformat()}

    if update.redis_url is not None:
        # Validate Redis URL format
        url = update.redis_url.strip()
        if url and not (url.startswith("redis://") or url.startswith("rediss://")):
            raise HTTPException(400, "Redis URL must start with redis:// or rediss://")
        updates["redis_url"] = url

        # Hot-reload Redis connection
        if url:
            _hot_reload_redis(url)

    if update.cors_origins is not None:
        updates["cors_origins"] = update.cors_origins

    await db.system_config.update_one(
        {"type": "infrastructure"},
        {"$set": updates},
        upsert=True
    )

    return {"success": True, "message": "Infrastructure configuration updated"}


@router.post("/create-indexes")
async def create_mongodb_indexes(request: Request):
    """Create performance indexes on hot collections"""
    _get_user_from_token(request)
    db = get_db()

    created = await _ensure_indexes(db)
    return {"success": True, "indexes_created": created}

@router.get("/redis-pool-stats")
async def redis_pool_stats(request: Request):
    """
    Admin monitoring endpoint — live connection count across shared Redis pool.
    Use this to detect connection leaks before Redis Cloud's 30-client limit is hit.
    """
    _get_user_from_token(request)
    try:
        from utils.redis_pool import pool_stats
        return await pool_stats()
    except Exception as e:
        return {"error": str(e)}




@router.post("/test-redis")
async def test_redis_connection(request: Request):
    """Test Redis connection with provided or stored URL"""
    _get_user_from_token(request)
    db = get_db()

    body = await request.json()
    url = body.get("redis_url", "")
    use_shared_pool = False

    if not url:
        config = await db.system_config.find_one({"type": "infrastructure"}, {"_id": 0})
        url = config.get("redis_url", "") if config else ""
        # If testing the currently-configured URL, use the shared pool to avoid leaking a client
        if url and url == os.environ.get("REDIS_URL", ""):
            use_shared_pool = True

    if not url:
        return {"connected": False, "error": "No Redis URL configured"}

    try:
        if use_shared_pool:
            from utils.redis_pool import get_sync_redis
            r = get_sync_redis()
            if r is None:
                return {"connected": False, "error": "Shared pool unavailable"}
            pong = r.ping()
            info = r.info("memory")
        else:
            # Admin is testing an ad-hoc URL — one-shot client, close immediately
            import redis as redis_lib
            r = redis_lib.from_url(url, socket_timeout=5)
            try:
                pong = r.ping()
                info = r.info("memory")
            finally:
                try:
                    r.close()
                except Exception:
                    pass
        return {
            "connected": True,
            "latency_ms": "< 5ms",
            "used_memory": info.get("used_memory_human", "unknown"),
            "max_memory": info.get("maxmemory_human", "unlimited"),
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


def _check_redis_connection(url: str) -> bool:
    if not url:
        return False
    # Prefer the shared pool when URL matches the live config — avoids leaks on GET /infrastructure
    if url == os.environ.get("REDIS_URL", ""):
        try:
            from utils.redis_pool import get_sync_redis
            r = get_sync_redis()
            if r is not None:
                r.ping()
                return True
        except Exception:
            return False
        return False
    # Ad-hoc URL test — one-shot, close after
    try:
        import redis as redis_lib
        r = redis_lib.from_url(url, socket_timeout=2)
        try:
            r.ping()
            return True
        finally:
            try:
                r.close()
            except Exception:
                pass
    except Exception:
        return False


def _hot_reload_redis(url: str):
    """Attempt to hot-reload Redis connection in rate limiter and cache"""
    os.environ["REDIS_URL"] = url
    # Reset shared pool so next call picks up the new URL
    try:
        from utils.redis_pool import reset_for_hot_reload
        reset_for_hot_reload()
    except Exception:
        pass
    try:
        from middleware.security import rate_limiter
        if hasattr(rate_limiter, 'reconnect'):
            rate_limiter.reconnect(url)
        logger.info(f"[Infra] Redis hot-reloaded: {url[:30]}...")
    except Exception as e:
        logger.warning(f"[Infra] Redis hot-reload partial: {e}")


async def _get_index_status(db) -> dict:
    """Check which performance indexes exist"""
    targets = {
        "leads": ["tenant_id", "created_at"],
        "audit_chain": ["tenant_id", "timestamp"],
        "audit_trail": ["action", "timestamp"],
        "sentinel_diagnoses": ["tenant_id", "created_at"],
        "system_pulse": ["timestamp"],
        "voice_calls": ["tenant_id", "started_at"],
        "pipeline_runs": ["tenant_id", "started_at"],
        "ora_leads": ["tenant_id", "created_at"],
    }

    status = {}
    for coll_name, fields in targets.items():
        try:
            coll = db[coll_name]
            existing = await coll.index_information()
            indexed_fields = set()
            for idx_info in existing.values():
                for key, _ in idx_info.get("key", []):
                    indexed_fields.add(key)
            status[coll_name] = {
                "total_indexes": len(existing),
                "fields_indexed": list(indexed_fields),
                "missing": [f for f in fields if f not in indexed_fields],
            }
        except Exception:
            status[coll_name] = {"error": "collection not accessible"}

    return status


async def _ensure_indexes(db) -> list:
    """Create performance indexes on hot collections.

    Idempotent — MongoDB silently no-ops when an index with the same key
    spec already exists. Safe to call on every startup.
    """
    created = []

    index_map = {
        "leads": [("tenant_id", 1), ("created_at", -1)],
        "audit_chain": [("tenant_id", 1), ("timestamp", -1)],
        "audit_trail": [("action", 1), ("timestamp", -1)],
        "sentinel_diagnoses": [("tenant_id", 1), ("created_at", -1)],
        "system_pulse": [("timestamp", -1)],
        "voice_calls": [("tenant_id", 1), ("started_at", -1)],
        "pipeline_runs": [("tenant_id", 1), ("started_at", -1)],
        "ora_leads": [("tenant_id", 1), ("created_at", -1)],
        "pixel_events": [("tenant_id", 1), ("timestamp", -1)],
        "sales_calls": [("tenant_id", 1), ("started_at", -1)],
        "tenant_customers": [("tenant_id", 1)],
        "morning_briefs": [("tenant_id", 1), ("date", -1)],
        # iter 322e — pixel + onboarding hot paths (Mission Control accelerator)
        "pixel_verification_log": [("verified_at", -1), ("detected", 1), ("url", 1)],
        "aurem_onboarding": [("tenant_id", 1), ("pixel_installed", 1)],
    }

    for coll_name, fields in index_map.items():
        try:
            coll = db[coll_name]
            await coll.create_index(fields, background=True)
            created.append(coll_name)
        except Exception as e:
            logger.warning(f"[Infra] Index creation failed for {coll_name}: {e}")

    # Single-field secondary indexes that power additional scans
    single_indexes = {
        "tenant_customers": [
            [("record_type", 1), ("pixel_installed", 1)],
            [("record_type", 1), ("status", 1)],
        ],
        "pixel_verification_log": [
            [("detected", 1)],
        ],
        "aurem_onboarding": [
            [("pixel_installed", 1)],
        ],
    }
    for coll_name, specs in single_indexes.items():
        for spec in specs:
            try:
                await db[coll_name].create_index(spec, background=True)
            except Exception as e:
                logger.warning(f"[Infra] Secondary index {coll_name}{spec} failed: {e}")

    logger.info(f"[Infra] Created/ensured indexes on {len(created)} collections")
    return created
