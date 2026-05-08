"""
AUREM Backup Service
=====================
Every 6 hours: export MongoDB collections to backup DB.
Keep last 7 days. Auto-restore on corruption.
Phase 2: Also writes JSON files to /app/backups/ with 7-day retention.
"""
import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

_db = None
BACKUP_DB_NAME = os.environ.get("DB_NAME", "aurem_db") + "_backups"
BACKUP_INTERVAL_HOURS = 6
BACKUP_RETENTION_DAYS = 7

FILE_BACKUP_DIR = Path("/app/backups")

CRITICAL_COLLECTIONS = [
    "users", "aurem_workspaces", "aurem_billing", "invoices",
    "products", "tenant_customers", "platform_connections",
    "tenant_settings", "api_keys", "aurem_api_key_settings",
]


def set_db(database):
    global _db
    _db = database


async def run_backup():
    """Export critical MongoDB collections to backup database."""
    if _db is None:
        logger.warning("[Backup] No database connection")
        return {"success": False, "error": "no_db"}

    backup_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results = {}
    all_docs = {}

    for col_name in CRITICAL_COLLECTIONS:
        try:
            col = _db[col_name]
            docs = await col.find({}, {"_id": 0}).to_list(10000)
            all_docs[col_name] = docs
            if docs:
                backup_col = _db.client[BACKUP_DB_NAME][f"{col_name}_{backup_ts}"]
                await backup_col.insert_many(docs)
                results[col_name] = {"count": len(docs), "status": "ok"}
            else:
                results[col_name] = {"count": 0, "status": "empty"}
        except Exception as e:
            results[col_name] = {"count": 0, "status": "error", "error": str(e)}

    # Record backup metadata
    try:
        await _db.client[BACKUP_DB_NAME]["_backup_manifest"].insert_one({
            "timestamp": backup_ts,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "collections": results,
        })
    except Exception as e:
        logger.error(f"[Backup] Manifest write failed: {e}")

    logger.info(f"[Backup] Completed: {backup_ts} — {sum(1 for r in results.values() if r['status'] == 'ok')}/{len(CRITICAL_COLLECTIONS)} collections backed up")

    await write_file_backup(backup_ts, results, all_docs)

    return {"success": True, "timestamp": backup_ts, "results": results}


async def write_file_backup(backup_ts, results, collections_data):
    """Write backup JSON file to /app/backups/ with date stamp."""
    try:
        FILE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": backup_ts,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "meta": {col: {"count": r["count"], "status": r["status"]} for col, r in results.items()},
            "collections": {col: docs for col, docs in collections_data.items() if docs},
        }
        filepath = FILE_BACKUP_DIR / f"backup_{backup_ts}.json"
        filepath.write_text(json.dumps(payload, default=str), encoding="utf-8")
        logger.info(f"[Backup] File backup written: {filepath} ({filepath.stat().st_size} bytes)")
    except Exception as e:
        logger.error(f"[Backup] File backup write failed: {e}")


def cleanup_old_file_backups():
    """Remove file backups older than retention period."""
    try:
        if not FILE_BACKUP_DIR.exists():
            return
        cutoff = (datetime.now(timezone.utc) - timedelta(days=BACKUP_RETENTION_DAYS)).strftime("%Y%m%d")
        removed = 0
        for f in FILE_BACKUP_DIR.glob("backup_*.json"):
            date_part = f.stem.replace("backup_", "")[:8]
            if date_part < cutoff:
                f.unlink()
                removed += 1
        if removed:
            logger.info(f"[Backup] Cleaned up {removed} old file backups")
    except Exception as e:
        logger.error(f"[Backup] File cleanup failed: {e}")


async def cleanup_old_backups():
    """Remove backups older than retention period."""
    if _db is None:
        return
    try:
        backup_db = _db.client[BACKUP_DB_NAME]
        cutoff = (datetime.now(timezone.utc) - timedelta(days=BACKUP_RETENTION_DAYS)).strftime("%Y%m%d")
        col_names = await backup_db.list_collection_names()
        removed = 0
        for name in col_names:
            if name == "_backup_manifest":
                continue
            # Extract timestamp from collection name: e.g. "users_20260407_120000"
            parts = name.rsplit("_", 2)
            if len(parts) >= 3:
                date_part = parts[-2]
                if date_part < cutoff:
                    await backup_db.drop_collection(name)
                    removed += 1
        if removed:
            logger.info(f"[Backup] Cleaned up {removed} old backup collections")
    except Exception as e:
        logger.error(f"[Backup] Cleanup failed: {e}")


async def restore_collection(col_name: str, backup_ts: Optional[str] = None):
    """Restore a collection from the most recent (or specified) backup."""
    if _db is None:
        return {"success": False, "error": "no_db"}

    backup_db = _db.client[BACKUP_DB_NAME]

    if not backup_ts:
        # Find most recent backup for this collection
        col_names = await backup_db.list_collection_names()
        matching = sorted([c for c in col_names if c.startswith(f"{col_name}_")], reverse=True)
        if not matching:
            return {"success": False, "error": "no_backup_found"}
        backup_col_name = matching[0]
    else:
        backup_col_name = f"{col_name}_{backup_ts}"

    try:
        backup_col = backup_db[backup_col_name]
        docs = await backup_col.find({}).to_list(10000)
        if not docs:
            return {"success": False, "error": "backup_empty"}

        # Clear existing + restore
        target = _db[col_name]
        await target.delete_many({})
        # Remove _id from backup docs to avoid conflicts
        for doc in docs:
            doc.pop("_id", None)
        await target.insert_many(docs)

        logger.info(f"[Backup] Restored {col_name} from {backup_col_name}: {len(docs)} docs")

        # WhatsApp alert
        try:
            from routers.whatsapp_alerts import send_whatsapp
            admin_phone = os.environ.get("ADMIN_WHATSAPP", "12265017777")
            await send_whatsapp(admin_phone, f"AUREM: Auto-restore completed. Backup from {backup_col_name} restored. {len(docs)} documents recovered.")
        except Exception:
            pass

        return {"success": True, "collection": col_name, "backup": backup_col_name, "docs_restored": len(docs)}

    except Exception as e:
        return {"success": False, "error": str(e)}


async def backup_loop():
    """Background loop that runs backups every 6 hours."""
    while True:
        try:
            await asyncio.sleep(BACKUP_INTERVAL_HOURS * 3600)
            await run_backup()
            await cleanup_old_backups()
            cleanup_old_file_backups()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"[Backup] Loop error: {e}")
            await asyncio.sleep(300)  # Wait 5 min on error


print("[STARTUP] Backup Service loaded — 6h cycle, 7-day retention", flush=True)
