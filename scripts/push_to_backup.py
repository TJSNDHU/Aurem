"""
Push every document from the primary MongoDB to the SECONDARY (backup)
cluster. Idempotent: drops the entire backup DB first, then re-creates
each collection fresh.

Atlas free-tier (M0) caps collections at 500. We skip collections that
are empty or in the LOW_VALUE list to stay under the limit.

Run:
    cd /app/backend && set -a && . ./.env && set +a && python /app/scripts/push_to_backup.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

BATCH = 500

# Collections we deliberately skip on the backup to fit under the 500-col
# Atlas free-tier ceiling. These are high-churn ephemeral logs whose
# content can be regenerated and which carry no business value if lost.
LOW_VALUE_SKIP = {
    "site_monitor_logs",          # 65k+ HTTP probe pings, regenerates
    "system_pulse_actions",       # 28k+ scheduler heartbeats
    "system_events",              # 15k generic event log
    "sovereign_watchdog_log",     # 11k self-heal action log
    "system_pulse_archive",       # 5k pulse history
    "ora_call_log",               # large LLM call log; keep latest only
    "tracing_spans",              # OpenTelemetry spans
    "raw_emails",                 # email parsing scratch
    "boom_audit",                 # audit aliased into unified_audit_log
}


async def sync():
    src_url = os.environ["MONGO_URL"]
    bak_url = os.environ["SECONDARY_MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    src = AsyncIOMotorClient(src_url)[db_name]
    bak_client = AsyncIOMotorClient(bak_url, serverSelectionTimeoutMS=20000)
    bak = bak_client[db_name]
    await bak.command("ping")

    print(f"[sync] start {datetime.now(timezone.utc).isoformat()}")
    print(f"[sync] source={src.name} → backup={bak.name}")
    print("[sync] dropping entire backup DB to start clean…")
    await bak_client.drop_database(db_name)
    # Atlas free-tier sometimes returns from drop_database before the
    # collections are physically removed. Give it a few seconds then
    # also delete-many per-collection right before re-inserting.
    await asyncio.sleep(5)
    bak = bak_client[db_name]

    cols = sorted(await src.list_collection_names())
    print(f"[sync] source collections total: {len(cols)}")
    started = time.time()
    grand_src = grand_bak = grand_cols_moved = 0
    skipped_empty = 0
    skipped_lowvalue = 0
    failed = []
    for idx, col in enumerate(cols, 1):
        if col in LOW_VALUE_SKIP:
            skipped_lowvalue += 1
            print(f"  [{idx:>3}/{len(cols)}] {col:55s} SKIP (low-value)")
            continue
        try:
            n_src = await src[col].estimated_document_count()
            if n_src == 0:
                skipped_empty += 1
                continue
            # Hard-clear destination so retries from a prior partial run
            # don't leave stale rows that inflate the count.
            await bak[col].delete_many({})
            cursor = src[col].find({})
            buf = []
            written = 0
            async for doc in cursor:
                buf.append(doc)
                if len(buf) >= BATCH:
                    await bak[col].insert_many(buf, ordered=False)
                    written += len(buf)
                    buf = []
            if buf:
                await bak[col].insert_many(buf, ordered=False)
                written += len(buf)
            n_bak = await bak[col].estimated_document_count()
            grand_src += n_src
            grand_bak += n_bak
            grand_cols_moved += 1
            mark = "OK" if n_bak == n_src else "MISMATCH"
            print(f"  [{idx:>3}/{len(cols)}] {col:55s} src={n_src:>7} → bak={n_bak:>7}  {mark}")
        except Exception as e:
            print(f"  [{idx:>3}/{len(cols)}] {col:55s} FAILED: {e}")
            failed.append((col, str(e)))
    elapsed = time.time() - started
    print(f"[sync] done in {elapsed:.1f}s")
    print(f"[sync] collections moved: {grand_cols_moved}")
    print(f"[sync] collections skipped (empty): {skipped_empty}")
    print(f"[sync] collections skipped (low-value): {skipped_lowvalue}")
    print(f"[sync] docs src total:  {grand_src}")
    print(f"[sync] docs bak total:  {grand_bak}")
    print(f"[sync] failed: {len(failed)}")
    for c, e in failed:
        print(f"      - {c}: {e}")
    return grand_src, grand_bak, failed


if __name__ == "__main__":
    grand_src, grand_bak, failed = asyncio.run(sync())
    sys.exit(0 if grand_src == grand_bak and not failed else 1)
