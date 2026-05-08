"""
Database Optimization Service — Cold Storage, Indexing, Pruning
================================================================
Implements 3 strategies to reduce DB bloat and improve query speed:
1. Cold Storage: Archive old logs/diagnostics to historical collections
2. Compound Indexes: Add covered indexes for hot query patterns
3. Projections: Ensure queries only fetch needed fields

Run on startup + daily schedule.
"""

import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# Cached summary for Overwatch (updated after each optimization run or every 5 min)
_db_summary_cache = {}
_db_summary_ts = 0


def _cached_db_summary() -> dict:
    """Return cached DB summary for fast Overwatch pulse responses."""
    return _db_summary_cache


async def _update_db_summary(db):
    """Lightweight summary: just count collections and total docs."""
    global _db_summary_cache, _db_summary_ts
    import time
    now = time.time()
    if now - _db_summary_ts < 300 and _db_summary_cache:
        return
    try:
        colls = await db.list_collection_names()
        _db_summary_cache = {
            "collections": len(colls),
            "documents": 0,
            "data_mb": 0,
            "index_mb": 0,
            "optimization_score": 0,
            "bloat_count": 0,
        }
        # Quick stats from dbStats (single command, very fast)
        stats = await db.command("dbStats")
        _db_summary_cache["documents"] = stats.get("objects", 0)
        _db_summary_cache["data_mb"] = round(stats.get("dataSize", 0) / 1024 / 1024, 2)
        _db_summary_cache["index_mb"] = round(stats.get("indexSize", 0) / 1024 / 1024, 2)
        # Quick bloat estimate
        bloat_keywords = ["system_pulse", "heartbeats", "sentinel_diagnos", "auto_heal", "api_audit_log", "cost_savings_log", "crawler_logs", "db_activity_audit"]
        bloat = sum(1 for c in colls if any(c.startswith(kw) for kw in bloat_keywords) and not c.endswith("_archive"))
        _db_summary_cache["bloat_count"] = bloat
        _db_summary_cache["optimization_score"] = max(0, 100 - bloat * 5)
        _db_summary_ts = now
    except Exception as e:
        logger.debug(f"[DB-OPT] Summary cache update failed: {e}")


async def archive_cold_data(db, days_threshold: int = 7):
    """
    Move old diagnostic/log data to cold storage collections.
    Keeps the hot database lean — data stays searchable via *_archive collections.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold)
    cutoff_iso = cutoff.isoformat()

    # Collections to archive: (source, timestamp_field, archive_name)
    archive_targets = [
        ("system_pulse", "timestamp", "system_pulse_archive"),
        ("heartbeats", "timestamp", "heartbeats_archive"),
        ("sentinel_diagnoses", "timestamp", "sentinel_diagnoses_archive"),
        ("auto_heal_log", "timestamp", "auto_heal_log_archive"),
        ("api_audit_log", "timestamp", "api_audit_log_archive"),
        ("cost_savings_log", "timestamp", "cost_savings_log_archive"),
        ("sentinel_verifications", "timestamp", "sentinel_verifications_archive"),
        ("auto_heal_runs", "timestamp", "auto_heal_runs_archive"),
        ("crawler_logs", "timestamp", "crawler_logs_archive"),
        ("db_activity_audit", "timestamp", "db_activity_audit_archive"),
        ("auto_repair_log", "timestamp", "auto_repair_log_archive"),
        ("audit_chain", "timestamp", "audit_chain_archive"),
    ]

    total_archived = 0
    for source, ts_field, archive in archive_targets:
        try:
            # Find old documents
            query = {ts_field: {"$lt": cutoff_iso}}
            old_docs = await db[source].find(query, {"_id": 0}).to_list(length=5000)

            if not old_docs:
                continue

            # Insert into archive
            if old_docs:
                await db[archive].insert_many(old_docs)
                # Delete from hot collection
                result = await db[source].delete_many(query)
                total_archived += result.deleted_count
                logger.info(f"[DB-OPT] Archived {result.deleted_count} docs: {source} → {archive}")
        except Exception as e:
            logger.warning(f"[DB-OPT] Archive failed for {source}: {e}")

    return total_archived


async def create_compound_indexes(db):
    """
    Create compound indexes for the heaviest query patterns.
    These enable covered queries (MongoDB can answer from index alone).
    """
    indexes_created = 0

    index_definitions = [
        # Hot collections — compound indexes for common query patterns
        ("system_pulse", [("ts", -1)], {"name": "idx_ts_desc"}),
        ("heartbeats", [("timestamp", -1)], {"name": "idx_timestamp_desc"}),
        ("sentinel_diagnoses", [("timestamp", -1), ("severity", 1)], {"name": "idx_ts_severity"}),
        ("live_patches", [("timestamp", -1), ("status", 1)], {"name": "idx_ts_status"}),
        ("audit_chain", [("timestamp", -1), ("brand_id", 1)], {"name": "idx_ts_brand"}),
        ("api_audit_log", [("timestamp", -1), ("method", 1)], {"name": "idx_ts_method"}),
        ("agent_traces", [("timestamp", -1), ("agent", 1)], {"name": "idx_ts_agent"}),

        # Business collections — for dashboard queries
        ("tenant_customers", [("created_at", -1), ("brand_id", 1)], {"name": "idx_created_brand"}),
        ("system_scans", [("created_at", -1), ("brand_id", 1)], {"name": "idx_scan_brand"}),
        ("customer_website_fixes", [("status", 1), ("created_at", -1)], {"name": "idx_status_created"}),
        ("comm_leads", [("created_at", -1)], {"name": "idx_comm_created"}),

        # Chat & messaging
        ("live_chat_messages", [("session_id", 1), ("timestamp", -1)], {"name": "idx_session_ts"}),
        ("whatsapp_messages", [("chat_id", 1), ("timestamp", -1)], {"name": "idx_chat_ts"}),

        # Shannon security
        ("shannon_reports", [("created_at", -1)], {"name": "idx_shannon_created"}),

        # Session memory
        ("session_memory", [("session_id", 1), ("created_at", -1)], {"name": "idx_session_mem"}),
    ]

    for collection, keys, kwargs in index_definitions:
        try:
            await db[collection].create_index(keys, background=True, **kwargs)
            indexes_created += 1
        except Exception as e:
            # Index may already exist — that's fine
            if "already exists" not in str(e).lower():
                logger.debug(f"[DB-OPT] Index {kwargs.get('name','?')} on {collection}: {e}")

    logger.info(f"[DB-OPT] Compound indexes ensured: {indexes_created}")
    return indexes_created


async def drop_empty_collections(db):
    """Remove collections with 0 documents to reduce metadata overhead."""
    dropped = 0
    protected = {"system.indexes", "system.users", "system.version"}

    colls = await db.list_collection_names()
    for c in colls:
        if c in protected or c.endswith("_archive"):
            continue
        try:
            count = await db[c].count_documents({})
            if count == 0:
                await db.drop_collection(c)
                dropped += 1
        except Exception:
            pass

    if dropped > 0:
        logger.info(f"[DB-OPT] Dropped {dropped} empty collections")
    return dropped


async def get_db_health_report(db) -> dict:
    """Generate a health report showing collection sizes, index coverage, and optimization opportunities."""
    colls = await db.list_collection_names()
    total_size = 0
    total_idx_size = 0
    total_docs = 0
    bloat_candidates = []
    missing_indexes = []
    collection_stats = []

    for c in sorted(colls):
        try:
            count = await db[c].count_documents({})
            s = await db.command("collStats", c)
            size_mb = s.get("size", 0) / 1024 / 1024
            idx_mb = s.get("totalIndexSize", 0) / 1024 / 1024
            avg_obj = s.get("avgObjSize", 0)
            idx_count = len(s.get("indexSizes", {}))
            total_size += size_mb
            total_idx_size += idx_mb
            total_docs += count

            collection_stats.append({
                "name": c,
                "documents": count,
                "size_mb": round(size_mb, 3),
                "index_size_mb": round(idx_mb, 3),
                "avg_object_bytes": int(avg_obj),
                "index_count": idx_count,
            })

            # Flag bloat: large collections with only _id index
            if count > 500 and idx_count <= 1:
                missing_indexes.append(c)
            # Flag bloat: collections over 1MB that could be archived
            if size_mb > 1.0 and any(kw in c for kw in ["log", "pulse", "heartbeat", "diagnos", "heal", "audit", "crawler"]):
                bloat_candidates.append({"name": c, "size_mb": round(size_mb, 2), "docs": count})
        except Exception:
            pass

    # Sort by size
    collection_stats.sort(key=lambda x: x["size_mb"], reverse=True)

    return {
        "total_collections": len(colls),
        "total_documents": total_docs,
        "total_data_mb": round(total_size, 2),
        "total_index_mb": round(total_idx_size, 2),
        "index_to_data_ratio": round(total_idx_size / max(total_size, 0.01), 2),
        "bloat_candidates": bloat_candidates,
        "missing_indexes": missing_indexes,
        "top_collections": collection_stats[:15],
        "optimization_score": max(0, 100 - len(bloat_candidates) * 10 - len(missing_indexes) * 5),
    }


async def run_full_optimization(db) -> dict:
    """Run all optimizations in sequence. Called on startup + daily."""
    results = {
        "archived": 0,
        "indexes_created": 0,
        "empty_dropped": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        results["archived"] = await archive_cold_data(db, days_threshold=7)
    except Exception as e:
        logger.warning(f"[DB-OPT] Archive step failed: {e}")

    try:
        results["indexes_created"] = await create_compound_indexes(db)
    except Exception as e:
        logger.warning(f"[DB-OPT] Index step failed: {e}")

    try:
        results["empty_dropped"] = await drop_empty_collections(db)
    except Exception as e:
        logger.warning(f"[DB-OPT] Cleanup step failed: {e}")

    logger.info(f"[DB-OPT] Optimization complete: {results}")
    return results
