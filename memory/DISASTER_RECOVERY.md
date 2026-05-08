# AUREM Disaster Recovery Runbook

> **Last drill**: Feb 8, 2026 — initial setup + first successful mirror to `Backupmy` Atlas cluster.

## Architecture

```
   PRIMARY (live)                       SECONDARY (DR mirror)
┌──────────────────────┐             ┌──────────────────────┐
│ MongoDB Atlas        │  daily      │ MongoDB Atlas M0     │
│ (Emergent-managed)   │ ──03:00 UTC│ "Backupmy"            │
│  aurem_db            │  mirror →  │  aurem_db (mirror)    │
│  ~150 MB / 472k docs │             │  Pawandeep's Org #2   │
└──────────────────────┘             └──────────────────────┘
        ▲                                      ▲
        │ MONGO_URL                            │ SECONDARY_MONGO_URL
        └──────────────── Backend pod ─────────┘
```

- **Triggered**: APScheduler cron `aurem_dr_backup_daily` at **03:00 UTC** daily (low-traffic).
- **Manual trigger**: `POST /api/admin/backup/trigger` (super_admin auth).
- **Status / history**: `GET /api/admin/backup/status` returns last 20 runs + secondary reachability probe.
- **Failure alerts**: Resend email to `FOUNDER_ALERT_EMAIL` (default: `teji.ss1986@gmail.com`).
- **Run logs**: persisted to PRIMARY collection `db_backup_runs` (one document per run, including per-collection stats).

## Mirror semantics

- Each run **drops** every secondary collection then **inserts** all primary docs (clean replace).
- `_id` field is preserved exactly so application failover keeps every reference intact.
- Excluded collections: `fs.files`, `fs.chunks`, `system.*`, `session_logs` (transient/huge/sensitive).
- The same **DB name** (`aurem_db`) is used on both clusters → failover is a 1-line URL swap, no app changes.

## 30-second failover procedure

If the primary Atlas cluster is unreachable, locked, or compromised:

1. **Confirm primary is dead**:
   ```bash
   mongosh "$MONGO_URL" --eval "db.adminCommand({ping:1})"
   ```
   If this hangs > 30s or returns auth/network errors, proceed.

2. **Verify secondary is healthy**:
   ```bash
   mongosh "$SECONDARY_MONGO_URL" --eval "db.adminCommand({ping:1})"
   mongosh "$SECONDARY_MONGO_URL" --eval "use aurem_db; db.platform_users.countDocuments()"
   ```

3. **Promote secondary to primary** (Emergent deploy panel → Environment variables):
   - **Save the old `MONGO_URL`** somewhere safe first (`MONGO_URL_OLD = …`)
   - Set `MONGO_URL` to the value currently in `SECONDARY_MONGO_URL`.
   - Save & redeploy.

4. **Disable the cron** (so we don't mirror back into the now-promoted secondary):
   - Set `DR_BACKUP_DISABLED=1` in env, OR
   - Unset `SECONDARY_MONGO_URL` so the cron exits early.

5. **Site is live** within ~30 sec of redeploy.

## After failover — restore primary

Once the original primary is back online (or you've spun up a fresh M10 cluster):

1. Re-set `MONGO_URL` to the new primary connection string.
2. Set `SECONDARY_MONGO_URL` to the **old** secondary (which was briefly promoted) so you're never without a mirror.
3. Trigger an immediate sync: `POST /api/admin/backup/trigger`.
4. Verify via `GET /api/admin/backup/status` that the new primary now feeds the secondary again.
5. Re-enable cron (`unset DR_BACKUP_DISABLED`).

## Rotating the secondary cluster credentials

If the secondary password leaks (or the service user is rotated):

1. **MongoDB Atlas → Database Access → Edit `Kaur1985`** → Edit Password → Autogenerate → **Update User**.
2. Update `SECONDARY_MONGO_URL` env var (Emergent deploy panel) with the new password.
3. Redeploy → `GET /api/admin/backup/status` must show `secondary.reachable = true`.

## Capacity

- Atlas M0 free tier = **512 MB hard cap**.
- Current primary data size: **~150 MB uncompressed**, ~50 MB on disk.
- Headroom available for ~3× growth before we'd need to upgrade to M2/M5 (paid).
- Monitor: Atlas dashboard → Cluster Metrics → "Disk Usage".

## Future hardening (P2 backlog)

- Off-site **compressed snapshots**: weekly `mongodump --gzip` to Cloudflare R2 (free 10 GB).
- **Point-in-time recovery**: enable Atlas Continuous Backups (M10+, paid).
- **Incremental sync** instead of drop+reinsert (use change streams + resume tokens).
- **Multi-region secondary**: e.g., Mumbai + N. Virginia for geographic redundancy.

## File map

- `/app/backend/services/db_backup_service.py` — main mirror engine.
- `/app/backend/routers/admin_dr_backup_router.py` — trigger + status endpoints.
- Cron registered in `/app/backend/routers/registry.py` (id `aurem_dr_backup_daily`).
- Secrets:
  - `MONGO_URL` — primary, in `/app/backend/.env`
  - `SECONDARY_MONGO_URL` — secondary, in `/app/backend/.env`
  - `RESEND_API_KEY` — for failure email alerts
  - `FOUNDER_ALERT_EMAIL` — defaults to `teji.ss1986@gmail.com`
