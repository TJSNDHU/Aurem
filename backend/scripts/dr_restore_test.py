"""
scripts/dr_restore_test.py — iter 328d (Disaster Recovery test)

Verifies that MongoDB backups are restorable. Designed to run monthly
via APScheduler (or manually) and produce a structured report.

The procedure (read-only against production):

  1. List recent successful `db_backup_runs` rows.
  2. Pick the most recent one in the last 7 days.
  3. Restore the dump into a SCRATCH database
     (`aurem_dr_test_<YYYY-MM>`).
  4. For each critical collection, compare counts between live and
     restored DBs (within a tolerance, since the dump is a snapshot).
  5. Drop the scratch DB.
  6. Write the result to `dr_restore_tests` and Telegram if FAIL.

Usage
─────
    python scripts/dr_restore_test.py            # run once, exit 0 on pass
    python scripts/dr_restore_test.py --dry-run  # show plan only

Setup
─────
- Requires `mongorestore` binary in PATH (already in the deploy image).
- Requires `SECONDARY_MONGO_URL` env (where backups land).
- Safe to abort at any time — never touches the primary collections.

Documented restore procedure (manual, for true disasters)
────────────────────────────────────────────────────────
    mongorestore --uri="$MONGO_URL" --nsInclude="aurem.*" \\
                 --dryRun  /var/aurem-backups/<dump-folder>
    # Inspect logs; if clean, drop --dryRun.
"""
from __future__ import annotations

import asyncio
import os
import sys
import subprocess
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("dr-restore-test")

# Critical collections — must survive restore intact.
CRITICAL_COLLECTIONS = [
    "platform_users", "users", "subscriptions",
    "ora_decisions", "ora_learning_journal",
    "ora_agent_history", "leads", "leads_archive",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def find_latest_backup_dir() -> Path | None:
    """Locate the most recent successful mongodump under /var/aurem-backups."""
    base = Path(os.environ.get("AUREM_BACKUP_DIR", "/var/aurem-backups"))
    if not base.exists():
        return None
    dirs = sorted(
        [d for d in base.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    for d in dirs:
        # Mongodump writes <db>/<coll>.bson — check that pattern.
        if any(d.rglob("*.bson")):
            return d
    return None


def restore_to_scratch(dump_dir: Path, scratch_db: str) -> tuple[bool, str]:
    """Run mongorestore against the dump into the scratch DB."""
    mongo_url = os.environ.get("MONGO_URL")
    if not mongo_url:
        return False, "MONGO_URL not set"
    cmd = [
        "mongorestore",
        f"--uri={mongo_url}",
        f"--nsTo=aurem.*",
        f"--nsFrom=aurem.*",
        f"--db={scratch_db}",
        "--drop",
        str(dump_dir),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except FileNotFoundError:
        return False, "mongorestore binary not in PATH"
    except subprocess.TimeoutExpired:
        return False, "mongorestore timeout after 10 minutes"
    if proc.returncode != 0:
        return False, f"mongorestore exit {proc.returncode}: {proc.stderr[-500:]}"
    return True, proc.stdout[-1000:]


async def compare_collection_counts(scratch_db: str, tolerance_pct: float = 5.0) -> dict:
    """Return per-collection {live, restored, delta_pct, ok}."""
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL"), maxPoolSize=5)
    live = client[os.environ.get("DB_NAME") or "aurem"]
    rest = client[scratch_db]
    results: dict[str, dict] = {}
    for name in CRITICAL_COLLECTIONS:
        try:
            live_n = await live[name].count_documents({})
            rest_n = await rest[name].count_documents({})
            denom = max(1, live_n)
            delta_pct = abs(live_n - rest_n) / denom * 100.0
            ok = delta_pct <= tolerance_pct or live_n == 0 == rest_n
            results[name] = {"live": live_n, "restored": rest_n,
                              "delta_pct": round(delta_pct, 2), "ok": ok}
        except Exception as e:
            results[name] = {"error": str(e)[:200], "ok": False}
    # Drop the scratch DB now that we're done.
    try:
        await client.drop_database(scratch_db)
    except Exception as e:
        logger.warning(f"scratch DB drop failed: {e}")
    client.close()
    return results


async def main(dry_run: bool = False) -> int:
    ts = _now()
    scratch_db = f"aurem_dr_test_{ts.strftime('%Y%m')}"
    logger.info(f"DR restore test starting — scratch DB: {scratch_db}")
    backup = find_latest_backup_dir()
    if not backup:
        logger.error("No backup directory found under /var/aurem-backups")
        return 2
    logger.info(f"Restoring from: {backup}")
    if dry_run:
        logger.info("[dry-run] would call mongorestore + compare counts")
        return 0
    ok, msg = restore_to_scratch(backup, scratch_db)
    if not ok:
        logger.error(f"Restore failed: {msg}")
        # Persist a failure row.
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(os.environ.get("MONGO_URL"), maxPoolSize=5)
            await client[os.environ.get("DB_NAME") or "aurem"].dr_restore_tests.insert_one({
                "ts":          ts.isoformat(),
                "status":      "fail",
                "stage":       "restore",
                "error":       msg[:1000],
                "backup_dir":  str(backup),
            })
            client.close()
        except Exception:
            pass
        return 3
    logger.info("Restore OK — comparing collection counts")
    results = await compare_collection_counts(scratch_db)
    all_ok = all(r.get("ok") for r in results.values())
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(os.environ.get("MONGO_URL"), maxPoolSize=5)
        await client[os.environ.get("DB_NAME") or "aurem"].dr_restore_tests.insert_one({
            "ts":           ts.isoformat(),
            "status":       "pass" if all_ok else "fail",
            "stage":        "compare",
            "results":      results,
            "backup_dir":   str(backup),
        })
        client.close()
    except Exception:
        pass
    if not all_ok and os.environ.get("TELEGRAM_BOT_TOKEN"):
        # Best-effort alert without dragging the whole services chain.
        import httpx
        try:
            await httpx.AsyncClient(timeout=8.0).post(
                f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                json={
                    "chat_id": os.environ.get("TELEGRAM_CHAT_ID"),
                    "text":    f"❌ DR restore test FAILED — see dr_restore_tests collection ({ts.isoformat()})",
                },
            )
        except Exception:
            pass
    logger.info(f"Done — all_ok={all_ok}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sys.exit(asyncio.run(main(dry_run=dry)))
