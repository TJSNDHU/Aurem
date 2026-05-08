"""
db_backup_service.py — Disaster Recovery: Primary → Secondary MongoDB mirror.

Strategy:
  1. Connect to PRIMARY (MONGO_URL) — local pod / production Atlas
  2. Connect to SECONDARY (SECONDARY_MONGO_URL) — independent Atlas account ("Backupmy" cluster)
  3. Stream every collection from primary, replace_one() / insert_many() into secondary
  4. Use replace-mode: secondary always reflects the latest primary state (size-bounded)
  5. Track each run in `db_backup_runs` collection on PRIMARY for ops visibility
  6. On failure: log + email founder via Resend (best-effort, non-blocking)

Triggered:
  - APScheduler cron: daily at 03:00 UTC (registered in routers/registry.py)
  - Manual: POST /api/admin/backup/trigger (super_admin only)

Author: Aurem ops · 2026-02-08
"""
import os
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

# Collections we never want to mirror (transient / huge / sensitive).
# High-volume operational/audit logs are intentionally skipped — they're
# write-only noise that bloats the secondary without aiding recovery.
EXCLUDE_COLLECTIONS = {
    "fs.files", "fs.chunks",          # GridFS files (size)
    "system.indexes", "system.users", # mongo internal
    "session_logs",                    # transient
    # High-volume transient logs — recreate themselves quickly post-failover
    "api_audit_log",
    "site_monitor_logs",
    "qa_bot_endpoint_log",
    "agent_feed",
    "a2a_events",
    "sentinel_diagnoses_archive",
    "cost_savings_log_archive",
    "auto_heal_log_archive",
    "council_decisions_archive",
}

# Page size when streaming docs (memory bound)
PAGE_SIZE = 500


def _send_failure_email(error_msg: str, run_id: str) -> None:
    """Best-effort Resend email to founder on backup failure. Never raises."""
    try:
        api_key = os.environ.get("RESEND_API_KEY")
        if not api_key:
            return
        import resend
        resend.api_key = api_key
        founder_email = os.environ.get(
            "FOUNDER_ALERT_EMAIL", "teji.ss1986@gmail.com"
        )
        resend.Emails.send({
            "from": "AUREM Ops <ops@aurem.live>",
            "to": [founder_email],
            "subject": f"⚠️ AUREM DR backup FAILED — {run_id}",
            "html": (
                f"<h2>DR Backup failure</h2>"
                f"<p><b>Run ID:</b> {run_id}</p>"
                f"<p><b>Time:</b> {datetime.now(timezone.utc).isoformat()}</p>"
                f"<p><b>Error:</b></p>"
                f"<pre style='background:#111;color:#f5d76e;padding:14px;"
                f"border-radius:6px;overflow:auto'>{error_msg}</pre>"
                f"<p>Check <code>db_backup_runs</code> collection for details.</p>"
            ),
        })
    except Exception as _e:
        logger.warning(f"[DR-BACKUP] failure-email send failed: {_e}")


def _mirror_collection(
    primary_db, secondary_db, coll_name: str
) -> Dict[str, Any]:
    """
    Mirror a single collection from primary to secondary.
    Strategy: drop secondary collection then bulk insert (cheapest for full mirror).
    Returns dict with stats.
    """
    src = primary_db[coll_name]
    dst = secondary_db[coll_name]
    started = time.time()

    # Drop the secondary collection so we get a clean mirror (no stale docs).
    try:
        dst.drop()
    except PyMongoError as e:
        logger.warning(f"[DR-BACKUP] drop {coll_name} failed: {e}")

    inserted = 0
    skipped = 0
    batch = []
    cursor = src.find({}, no_cursor_timeout=False).batch_size(PAGE_SIZE)
    try:
        for doc in cursor:
            batch.append(doc)
            if len(batch) >= PAGE_SIZE:
                try:
                    dst.insert_many(batch, ordered=False)
                    inserted += len(batch)
                except PyMongoError as e:
                    skipped += len(batch)
                    logger.warning(
                        f"[DR-BACKUP] insert_many {coll_name} chunk failed: {e}"
                    )
                batch = []
        if batch:
            try:
                dst.insert_many(batch, ordered=False)
                inserted += len(batch)
            except PyMongoError as e:
                skipped += len(batch)
                logger.warning(
                    f"[DR-BACKUP] insert_many {coll_name} tail failed: {e}"
                )
    finally:
        cursor.close()

    return {
        "collection": coll_name,
        "inserted": inserted,
        "skipped": skipped,
        "elapsed_ms": int((time.time() - started) * 1000),
    }


def run_backup(triggered_by: str = "scheduler") -> Dict[str, Any]:
    """
    Run a full primary → secondary mirror. Returns a dict with full run report.
    Logs progress + persists final report to PRIMARY db_backup_runs collection.
    """
    started_at = datetime.now(timezone.utc)
    run_id = f"dr-{started_at.strftime('%Y%m%dT%H%M%SZ')}"
    primary_url = os.environ.get("MONGO_URL")
    secondary_url = os.environ.get("SECONDARY_MONGO_URL")
    db_name = os.environ.get("DB_NAME", "aurem_db")

    report: Dict[str, Any] = {
        "run_id": run_id,
        "triggered_by": triggered_by,
        "started_at": started_at.isoformat(),
        "status": "running",
        "collections": [],
        "totals": {"inserted": 0, "skipped": 0, "collections": 0},
    }

    if not primary_url:
        report["status"] = "fail"
        report["error"] = "MONGO_URL not configured"
        return report
    if not secondary_url:
        report["status"] = "fail"
        report["error"] = (
            "SECONDARY_MONGO_URL not configured — DR backup disabled"
        )
        logger.warning(f"[DR-BACKUP] {run_id} skipped: SECONDARY_MONGO_URL missing")
        return report

    primary_client: Optional[MongoClient] = None
    secondary_client: Optional[MongoClient] = None

    try:
        primary_client = MongoClient(primary_url, serverSelectionTimeoutMS=10000)
        secondary_client = MongoClient(
            secondary_url, serverSelectionTimeoutMS=15000
        )
        # Sanity ping both ends
        primary_client.admin.command("ping")
        secondary_client.admin.command("ping")

        primary_db = primary_client[db_name]
        # Use the SAME db_name on the secondary so app failover is a 1-line URL swap.
        secondary_db = secondary_client[db_name]

        coll_names = [
            c for c in primary_db.list_collection_names()
            if c not in EXCLUDE_COLLECTIONS and not c.startswith("system.")
        ]
        logger.info(
            f"[DR-BACKUP] {run_id} started — {len(coll_names)} collections to mirror"
        )

        for name in coll_names:
            stats = _mirror_collection(primary_db, secondary_db, name)
            report["collections"].append(stats)
            report["totals"]["inserted"] += stats["inserted"]
            report["totals"]["skipped"] += stats["skipped"]
            report["totals"]["collections"] += 1

        report["status"] = "ok"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["elapsed_seconds"] = int(
            (datetime.now(timezone.utc) - started_at).total_seconds()
        )
        logger.info(
            f"[DR-BACKUP] {run_id} done — "
            f"{report['totals']['collections']} cols, "
            f"{report['totals']['inserted']} docs, "
            f"{report['elapsed_seconds']}s"
        )
    except Exception as e:
        report["status"] = "fail"
        report["error"] = f"{type(e).__name__}: {e}"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        logger.exception(f"[DR-BACKUP] {run_id} failed: {e}")
        _send_failure_email(str(e), run_id)
    finally:
        # Persist run report to PRIMARY (for ops dashboard); never throw.
        try:
            if primary_client is not None:
                primary_client[db_name]["db_backup_runs"].insert_one(dict(report))
        except Exception as _e:
            logger.warning(f"[DR-BACKUP] could not persist run report: {_e}")
        try:
            if primary_client is not None:
                primary_client.close()
            if secondary_client is not None:
                secondary_client.close()
        except Exception:
            pass

    return report


async def run_backup_async(triggered_by: str = "scheduler") -> Dict[str, Any]:
    """Async wrapper — runs the sync backup in a worker thread so the event
    loop is not blocked by long-running pymongo IO."""
    import asyncio
    return await asyncio.to_thread(run_backup, triggered_by)
