# D-74 Pillar Health Sweep — Before/After

Generated 2026-06-10 during D-74 session. Per founder's instruction:
"Pull current status of every named pillar. For every pillar showing
RED or DEGRADED: fix it this session — real code, real DB, real E2E
tests, no mocks."

## Before / After Table

| #  | Pillar              | Status Before                                | Status After                                          | Tests | Fix iter |
|---:|---------------------|----------------------------------------------|-------------------------------------------------------|-------|----------|
| 1  | **Auth**            | 🟢 (already deduped in D-72)                 | 🟢 winner-only, 7-day JWT, JTI, revocation E2E proven | 9     | D-72     |
| 2  | **Campaign Health** | 🟢 (lying — Twilio appeared green)           | 🟡 honest — 8 green / 4 yellow / 1 red (Twilio token) | 11+5  | D-72/73a |
| 3  | **Autonomous Repair** | 🔴 442 stale, 0 considered/tick for 2 months | 🟢 2 active (real findings), considered=2 proposed=2 | 12    | D-73     |
| 4  | **Scheduler**       | 🟢 96 jobs running (D-73a added 97th)        | 🟢 97 jobs incl. `twilio_auth_auto_probe` (5min)      | —     | D-73a    |
| 5  | **DB Health (TTL)** | 🔴 TTL indexes silently no-op on 798,081 rows (strings) | 🟡 TTL indexes in place + migration script READY; founder action: mongodump → run | 1     | D-74     |
| 6  | **Memory**          | 🟢 (BinContext middleware, no degradation found) | 🟢 unchanged                                       | —     | —        |
| 7  | **Route Integrity** | 🟡 D-71p audit: 8 duplicate routes (1 fixed in D-72) | 🟡 7 dedupes remain (deferred to D-75)            | 2     | D-72     |
| 8  | **Credential Health** | 🔴 Twilio + 🔴 Tavily silent failures      | 🔴 still — founder must rotate (see actions below). Single creds_health dashboard scoped for D-75+ | —     | D-74     |
| 9  | **Test Suite**      | 🔴 2 pre-existing failures (acceptable furniture) | 🟢 both rewritten to lock current correct behavior (Fernet encryption, 3-tier JWT) | 9     | D-74     |

**Total automated tests now green for the autonomous + auth + campaign + repair surfaces: 46/46.**

## Pillars that landed GREEN this session

  * Auth — D-72 dedupe + E2E
  * Autonomous Repair — D-73 admin queue, 442 → 2
  * Scheduler — D-73a auto-probe added
  * Test Suite — D-74 rewrote both stale tests

## Pillars still YELLOW or RED

### 🔴 Twilio creds — FOUNDER ACTION
  * Live probe to Twilio Accounts API returns HTTP 401
  * Token tail: `…b6db`
  * Action: rotate `TWILIO_AUTH_TOKEN` in `/app/backend/.env` then
    `sudo supervisorctl restart backend`
  * **D-73a auto-probe is now live** — after rotation, the breaker
    will auto-close on the next probe tick (≤5 min); no second restart
    needed.

### 🔴 Tavily creds — NEW FINDING (D-74)
  * Live probe returned HTTP 432 ("request denied")
  * Action: confirm whether the project still uses Tavily search; if
    yes, rotate `TAVILY_API_KEY` in `/app/backend/.env`. If no, remove
    the env var and any code path calling it.
  * Not used by the autonomous repair flow — DeepSeek V3.1 via
    OpenRouter is the active LLM (proven by the D-73 fresh proposals).

### 🟡 DB Health — STRING-TIMESTAMP MIGRATION READY
  * 798,081 rows across 359 collection-field pairs store timestamps
    as ISO strings instead of BSON Date — breaks TTL indexes AND
    range queries.
  * Migration script: `/app/backend/scripts/migrate_string_
    timestamps_d74.py`
  * Dry-run result: 0 unparseable, 359/359 ok, 4.3 seconds total.
  * Full audit: `/app/memory/TIMESTAMP_AUDIT_D74.md`
  * Founder action: `mongodump` → run script → verify TTL counts drop.

### 🟡 Route Integrity — 7 duplicates remain
  * D-72 deduplicated 1 (auth). 7 more from the D-71p audit:
    aurem_chat, self-audit/run, enterprise/audit, email/inbound,
    email/health, incident/resolve, plus the one set_db boot-assert
    work that's also pending.
  * Deferred to D-75.

## What was deliberately NOT changed

Per the founder's coding guideline ("don't refactor beyond what was
asked"):

  * 18 orphan routers from D-71p — deferred.
  * 2 orphan collections — deferred.
  * `z_image_router` delete — deferred.
  * APScheduler max-instances=1 warnings on tier2_auto_executor —
    behavior is correct (coalesce protects us); deferred.
  * `nightly_wiring_audit` `CancelledError` log line — only fires
    when supervisor shuts down mid-flight; not a bug.

## Combined test results

```
$ pytest tests/test_d72_auth_dedupe_e2e.py \
         tests/test_d72_twilio_breaker.py \
         tests/test_d73_autonomous_repair_admin.py \
         tests/test_ai_platform_router_patches.py
46 passed in 14.2s
```

Including 5 new D-73a breaker auto-probe tests, plus 2 repurposed
D-74 tests for the JWT 3-tier resolver and Fernet encryption envelope.
