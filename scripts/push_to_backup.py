"""
Push every document from the primary MongoDB to the SECONDARY (backup)
cluster.

Strategy (lessons learned from earlier runs):
1. Atlas free-tier (M0) caps DB at 500 collections. So we must skip
   low-value telemetry/log collections aggressively.
2. drop_database on Atlas free-tier is async-ish and races with
   immediate insert_many → we do a per-collection delete_many AFTER
   the drop returns to be safe.
3. Parallel inserts caused MISMATCHes (race in delete_many vs insert).
   So we run STRICTLY SEQUENTIAL.
4. Critical business collections (users, tenants, developers,
   payments, audit, leads) are sorted FIRST so they always land
   inside the 500-collection ceiling.

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

BATCH = 2000

# Collections that we never sync — pure ephemeral logs/probes whose
# loss does not change any business state. Keeps us under the
# 500-collection Atlas free-tier ceiling.
LOW_VALUE_SKIP = {
    "site_monitor_logs", "system_pulse_actions", "system_events",
    "sovereign_watchdog_log", "system_pulse_archive",
    "ora_call_log", "tracing_spans", "raw_emails", "boom_audit",
    "qa_bot_endpoint_log", "qa_audit_attempts", "qa_bot_calls",
    "system_auto_repairs", "scheduler_heartbeats",
    "agent_ledger_entries", "ora_orchestrator_log",
    "stream_responses_log", "telemetry_events",
    "service_health_history", "system_cron_log",
    "agent_heartbeats", "agent_health_actions",
    "site_monitor_incidents", "site_monitor_endpoints",
    "router_metrics", "outbound_email_audit",
    "lead_email_attempts", "auto_blast_attempts",
    "scout_replenish_cursor", "scout_hunt_jobs", "scout_ghost_jobs",
    "scout_seen_signals", "scout_seen_pages",
    "shannon_reports", "shopify_oauth_nonces",
    "site_audits", "shortlink_clicks", "shortlinks",
    "sla_snapshots", "stripe_events_processed",
    "system_alerts", "system_scans", "swarm_executions",
    "sovereign_queue", "suspicious_ips", "tone_sync_log",
    "telegram_alert_log", "telegram_messages",
}

# These prefixes mark collections we definitely want to keep — they
# carry user, billing, audit, or product state.
PRIORITY_PREFIXES = (
    "user",  "tenant", "developer", "organization", "enterprise",
    "payment", "stripe_w", "subscription", "plan",
    "billing", "invoice", "credit",
    "audit", "unified_audit", "compliance",
    "saml", "scim",
    "lead", "verified_lead", "lead_email",
    "session", "auth_", "jwt_", "refresh_",
    "ora_", "agent_knowledge", "specialist_",
    "share", "share_link", "share_view",
    "feedback", "review",
)


def _is_priority(col: str) -> bool:
    cl = col.lower()
    return any(cl.startswith(p) for p in PRIORITY_PREFIXES)


async def _sync_one(src, bak, col: str, idx: int, total: int) -> tuple[int, int, str | None]:
    try:
        n_src = await src[col].estimated_document_count()
        if n_src == 0:
            return 0, 0, None
        await bak[col].delete_many({})
        cursor = src[col].find({})
        buf: list = []
        async for doc in cursor:
            buf.append(doc)
            if len(buf) >= BATCH:
                await bak[col].insert_many(buf, ordered=False)
                buf = []
        if buf:
            await bak[col].insert_many(buf, ordered=False)
        n_bak = await bak[col].estimated_document_count()
        mark = "OK" if n_bak == n_src else "MISMATCH"
        print(f"  [{idx:>3}/{total}] {col:55s} src={n_src:>7} → bak={n_bak:>7}  {mark}", flush=True)
        return n_src, n_bak, None
    except Exception as e:
        print(f"  [{idx:>3}/{total}] {col:55s} FAILED: {e}", flush=True)
        return 0, 0, str(e)


async def sync():
    src_url = os.environ["MONGO_URL"]
    bak_url = os.environ["SECONDARY_MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    src = AsyncIOMotorClient(src_url)[db_name]
    bak_client = AsyncIOMotorClient(bak_url, serverSelectionTimeoutMS=20000)
    bak = bak_client[db_name]
    await bak.command("ping")

    print(f"[sync] start {datetime.now(timezone.utc).isoformat()}", flush=True)
    print(f"[sync] source={src.name} → backup={bak.name}", flush=True)
    print("[sync] dropping entire backup DB…", flush=True)
    await bak_client.drop_database(db_name)
    await asyncio.sleep(4)
    bak = bak_client[db_name]

    cols = sorted(await src.list_collection_names())
    print(f"[sync] source collections total: {len(cols)}", flush=True)

    # Build the sync queue: skip low-value, then put PRIORITY first
    # so they land before we hit the 500-collection ceiling.
    skipped_lowvalue = 0
    priority: list[str] = []
    rest: list[str] = []
    for col in cols:
        if col in LOW_VALUE_SKIP or col.startswith("_"):
            skipped_lowvalue += 1
            continue
        if _is_priority(col):
            priority.append(col)
        else:
            rest.append(col)

    queue = priority + rest
    print(f"[sync] skipped (low-value/private): {skipped_lowvalue}", flush=True)
    print(f"[sync] priority collections (sync first): {len(priority)}", flush=True)
    print(f"[sync] standard collections (sync after): {len(rest)}", flush=True)
    print(f"[sync] total in queue: {len(queue)}", flush=True)

    started = time.time()
    grand_src = grand_bak = 0
    failed: list[tuple[str, str]] = []
    moved = 0
    skipped_empty = 0
    for i, col in enumerate(queue, 1):
        n_src, n_bak, err = await _sync_one(src, bak, col, i, len(queue))
        if err:
            failed.append((col, err))
            continue
        if n_src == 0:
            skipped_empty += 1
            continue
        grand_src += n_src
        grand_bak += n_bak
        moved += 1

    elapsed = time.time() - started
    print(f"[sync] done in {elapsed:.1f}s", flush=True)
    print(f"[sync] collections moved: {moved}", flush=True)
    print(f"[sync] collections skipped (empty): {skipped_empty}", flush=True)
    print(f"[sync] collections skipped (low-value): {skipped_lowvalue}", flush=True)
    print(f"[sync] docs src total:  {grand_src}", flush=True)
    print(f"[sync] docs bak total:  {grand_bak}", flush=True)
    print(f"[sync] failed: {len(failed)}", flush=True)
    for c, e in failed:
        print(f"      - {c}: {e[:120]}", flush=True)
    return grand_src, grand_bak, failed


if __name__ == "__main__":
    grand_src, grand_bak, failed = asyncio.run(sync())
    sys.exit(0 if grand_src == grand_bak and not failed else 1)
