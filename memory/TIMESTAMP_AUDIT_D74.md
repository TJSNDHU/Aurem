# String-Stored Timestamp Audit — iter D-74

Generated 2026-06-10 18:25 UTC during D-74 pillars sweep, per founder's
instruction: "before the migration runs, have the agent grep every
collection with a timestamp field and produce a single list of
string-stored timestamps across the entire codebase — fix them all in
one migration pass with one mongodump, not piecemeal."

## Scope

Scanned **all 614 collections** in the live `aurem_db` database. For
each, checked the following timestamp field names for BSON-type
mismatch (string vs Date):

`created_at`, `updated_at`, `ts`, `timestamp`, `at`, `last_seen`,
`completed_at`, `archived_at`, `started_at`, `ended_at`, `logged_at`,
`fired_at`, `expires_at`, `deleted_at`.

## Total impact

**797,928 rows across 359 collection-field pairs** store their
timestamps as ISO 8601 strings instead of BSON `Date`. This breaks:
  * MongoDB TTL indexes (silently no-op)
  * `$lt` / `$gte` range queries against datetime objects (silently
    return 0)
  * Any code that does `(now - doc["ts"]).total_seconds()` on a
    string (TypeError)

## Top 20 offenders (largest first)

| collection                       | field      |  rows   |
|----------------------------------|------------|--------:|
| a2a_events                       | timestamp  | 226,821 |
| qa_bot_endpoint_log              | ts         |  86,299 |
| site_monitor_logs                | ts         |  75,961 |
| system_pulse_actions             | ts         |  59,484 |
| council_decisions                | created_at |  46,436 |
| council_decisions                | ts         |  46,436 |
| agent_outcomes                   | ts         |  42,622 |
| sovereign_watchdog_log           | ts         |  16,721 |
| agent_ledger_entries             | timestamp  |  16,824 |
| audit_chain_archive              | timestamp  |  12,750 |
| repair_runs                      | started_at |  11,910 |
| sentinel_diagnoses_archive       | timestamp  |  11,867 |
| agent_a2a_signals                | ts         |   9,975 |
| auto_heal_log_archive            | timestamp  |   8,427 |
| cost_savings_log_archive         | timestamp  |   8,058 |
| a2a_tasks                        | created_at |   6,961 |
| heartbeats_archive               | timestamp  |   6,314 |
| awb_autopilot_runs               | started_at |   6,288 |
| deploy_events                    | timestamp  |   6,571 |
| revenue_forecasts                | timestamp  |   5,706 |

The full 359-pair list is in `/app/memory/TIMESTAMP_AUDIT_D74_FULL.txt`.

## Mixed-state collections (have BOTH string AND date rows)

These need careful handling — there's already a partial migration in
progress that wasn't completed:

| collection                       | field      | strings | dates   |
|----------------------------------|------------|--------:|--------:|
| aurem_audit_logs                 | timestamp  |       1 |    987  |
| aurem_pixels                     | created_at |      20 |      5  |
| aurem_usage                      | created_at |       1 |      6  |
| aurem_usage                      | updated_at |       1 |      6  |
| admin_users                      | created_at |       1 |      1  |
| bin_ora_qa                       | ts         |       1 |      4  |
| customer_subscriptions           | started_at |     107 |     25  |
| ora_brain_thoughts               | ts         |       6 | 133,767 |
| ora_cto_proposals                | created_at |      16 |      0  |
| pending_approvals_archive        | created_at |      12 |    428  |
| platform_users                   | created_at |      24 |      2  |
| platform_users                   | updated_at |      19 |      2  |
| truth_ledger                     | ts         |     839 |      8  |
| usage_tracking                   | created_at |       1 |     30  |
| usage_tracking                   | updated_at |       1 |     30  |

## Quirks observed

`ora_session_memory.updated_at`: ISO with `Z` suffix instead of
`+00:00` — `dateutil.parser` handles both, but `datetime.fromisoformat`
on Python <3.11 chokes on `Z`. (We're on 3.11 so OK.)

`shannon_reports.timestamp`: 2,282 rows store EMPTY STRING. Migration
must handle missing/blank by either deleting the field or backfilling
from `created_at` if present.

`video_queue.completed_at`, `video_queue.started_at`: 2 rows each
store empty string.

`build_journal.ts`: stores `+00:00` without microseconds — parses OK.

`heartbeats.timestamp`: timezone is `-04:00` (some New York client
clocks) — must preserve tz on conversion.

## Migration script (DO NOT RUN UNATTENDED)

A safe migration script template is below. The founder's process:

1. **Quiet window** — pick a 30-min slot when blast cycles + Shannon
   scans + repair tick are unlikely to write new rows.
2. **mongodump** the 14 mixed-state collections + the top-5 string-only
   collections (the rest are append-only logs and a re-import isn't
   needed if rollback is via timestamp filter).
3. Set `AUREM_TS_MIGRATION_DRY_RUN=true` in env, run script, eyeball
   the per-collection counts.
4. Set `AUREM_TS_MIGRATION_DRY_RUN=false`, run for real.
5. Verify TTL indexes now fire (count drops over the next hour).

```python
# /app/backend/scripts/migrate_string_timestamps_d74.py
# Reads the 359-pair list, iterates collections, casts strings to BSON
# Date in bulk via $set with a $dateFromString aggregation pipeline.
# Handles malformed/blank/missing values by SKIPPING (logged), never
# crashing mid-collection.
```

## Why this matters

The pattern has now appeared in THREE separate iter:

  * **D-71p** — `api_audit_log`, `a2a_events`, `system_pulse_actions`
    etc. TTL indexes silently no-op.
  * **D-73** — `pending_approvals.created_at` `{$lt: <datetime>}`
    queries returning 0 instead of catching the 14 stale Shannon
    rows.
  * **D-74** — same root cause across 359 collection-field pairs.

Migrating in piecemeal fashion is what kept this dormant. One pass,
one mongodump, one verification window.
