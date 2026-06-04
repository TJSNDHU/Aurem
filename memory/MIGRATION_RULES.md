# AUREM Zero-Downtime Migration Rules

> **Hard rule:** No code change may break the contract between
> old-pod and new-pod that run side-by-side during a rolling deploy.
> Violating this means downtime. There are no exceptions.

---

## The "Two Versions, One DB" Reality

K8s rolling deploy = N seconds where:
- Some pods run **version N** (old code)
- Some pods run **version N+1** (new code)
- Both read & write the **same Mongo collections**

If new code drops/renames a field old code reads, old pods crash → 503s → downtime.

---

## The Three-Deploy Rule

For ANY schema change, ship in **three separate deploys**:

### Deploy A — Additive
- Add new field. **Both old + new code can ignore it.**
- New code writes both old AND new field.
- Old code reads old field only.
- ✅ Safe to deploy.

### Deploy B — Dual-Read
- New code reads new field, falls back to old field if missing.
- Backfill script populates new field for historical docs.
- Old code still reading old field works.
- ✅ Safe to deploy.

### Deploy C — Cleanup
- New code stops writing the old field.
- After 24h: drop old field from DB.
- After 72h: remove the dual-read fallback.
- ✅ Safe to deploy.

**Never combine these.** Every deploy must work side-by-side with the previous.

---

## Allowed in a Single Deploy

| Change | Single deploy OK? |
|---|---|
| Add new collection | ✅ |
| Add new field (nullable) | ✅ |
| Add new index | ✅ (background build) |
| Add new endpoint | ✅ |
| Add new feature flag (off by default) | ✅ |
| Bug fix in an endpoint that returns the same response shape | ✅ |
| Add optional query param | ✅ |

## NOT Allowed in a Single Deploy

| Change | Why it breaks |
|---|---|
| Rename a field | Old code reads `foo`, new code writes `bar` |
| Drop a field | Old code crashes on KeyError |
| Change a field's type (str → int) | Validators on old code reject |
| Rename a collection | Old code queries wrong collection |
| Change an enum value | Old code rejects new value |
| Change a response shape (remove key) | Old frontend (cached SPA) crashes |
| Change an endpoint's required-auth | Frontend caching breaks |

---

## PR Checklist (paste into every PR description)

```
ZERO-DOWNTIME CHECKLIST
[ ] No fields renamed in this PR
[ ] No fields dropped in this PR
[ ] No collection renamed in this PR
[ ] No response-shape changes (removed keys) in this PR
[ ] If schema changed: this is Deploy A / B / C of the 3-deploy plan (circle one)
[ ] If touching a scheduler job: job is idempotent (re-run does no harm)
[ ] If touching SSE: client side has reconnect logic
[ ] Tested with old-pod-still-running scenario in mind
```

---

## Reference: Why This Matters

**Incident 2026-05-12:** Field `lead.contact_email` renamed to `lead.email` in one commit.
- New pods rolled out → started writing `email`.
- Old pods (still running for 90s) read `contact_email` → returned `null` → CRM sync broke for 90 seconds.
- 53 leads enqueued without contact info during that window.
- Fixed by Deploy B: dual-read in new code + backfill.

**Incident 2026-04-21:** Auto-blast scheduler killed mid-cycle on rolling restart.
- 12 leads got duplicate WhatsApp messages.
- Fixed by iter D-63: graceful `scheduler.shutdown(wait=True)` in shutdown handler.

---

## Tools That Help

- `db.feature_flags` (iter D-63) — wrap risky behavior changes in flags. Roll out 1% → 10% → 100%.
- `/api/admin/feature-flags` admin endpoint — see and toggle flags live.
- `app.state.scheduler` graceful drain — auto.
- `/api/ready` readiness probe — K8s holds traffic during Mongo blips.

---

*Adopted iter D-63. Owner: founder. Violations = downtime = paying customers leave.*
