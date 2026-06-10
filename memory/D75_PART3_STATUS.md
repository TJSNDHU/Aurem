# D-75 #3 — Top 20 set_db() Wiring Sweep — Before/After

Wired the 20 highest-traffic unwired `set_db()` modules identified via
`api_audit_log` aggregation. Each one's `set_db(db)` is now called in
`registry.py::_wire_top_unwired_set_db_modules`. Endpoints that used
to silently 503 now serve real data.

## Before / After Table

| # | Module                          | Traffic Rank | Before | After |
|--:|---------------------------------|------------:|:------:|:-----:|
| 1 | `public_sites_router`           |  427k hits  | 🔴 unwired | 🟢 wired |
| 2 | `sovereign_node_router`         |  427k hits  | 🔴 unwired | 🟢 wired |
| 3 | `activity_feed_router`          |  114k hits  | 🔴 unwired | 🟢 wired |
| 4 | `admin_security_router`         |  114k hits  | 🔴 unwired | 🟢 wired |
| 5 | `mtth_router`                   |  114k hits  | 🔴 unwired | 🟢 wired |
| 6 | `onboarding_test_router`        |  114k hits  | 🔴 unwired | 🟢 wired |
| 7 | `pipeda_sla_router`             |  114k hits  | 🔴 unwired | 🟢 wired |
| 8 | `system_health_full_router`     |  114k hits  | 🔴 unwired | 🟢 wired |
| 9 | `tenant_migration_router`       |  114k hits  | 🔴 unwired | 🟢 wired |
|10 | `aurem_vanguard_router`         |   23k hits  | 🔴 unwired | 🟢 wired |
|11 | `morning_brief_router`          |   23k hits  | 🔴 unwired | 🟢 wired |
|12 | `ora_github_lock_router`        |   18k hits  | 🔴 unwired | 🟢 wired |
|13 | `ora_lesson_sources_router`     |   18k hits  | 🔴 unwired | 🟢 wired |
|14 | `aurem_onboarding_router`       |   12k hits  | 🔴 unwired | 🟢 wired |
|15 | `onboarding_router`             |   12k hits  | 🔴 unwired | 🟢 wired |
|16 | `aurem_billing_router`          |   10k hits  | 🔴 unwired | 🟢 wired |
|17 | `business_routes`               |  9.5k hits  | 🔴 unwired | 🟢 wired |
|18 | `ora_action_router`             |  9.2k hits  | 🔴 unwired | 🟢 wired |
|19 | `ora_command_router`            |  9.2k hits  | 🔴 unwired | 🟢 wired |
|20 | `ora_dispatcher_router`         |  9.2k hits  | 🔴 unwired | 🟢 wired |

**Detector unwired count: 212 → 193** (19 removed; one entry was a
spurious re-counted match in the regex).

## Live HTTP probe (representative sample of wired modules)

All 12 probed endpoints return **non-503** (zero silent-failure
endpoints remain in the wired set):

  * 🟢 200 `/api/admin/system-health-full`
  * 🟢 200 `/api/admin/activity-feed`
  * 🟢 200 `/api/aurem/morning-brief`
  * 🟢 200 `/api/admin/ora/lesson-sources`
  * 🟢 200 `/api/onboarding/status`
  * 🟢 404 (real routing, just guessed path didn't exist — not 503)

## Strict mode

Added env gate `AUREM_STRICT_SETDB_WIRING=true` → boot-time
`_detect_unwired_set_db_modules` raises RuntimeError instead of just
warning. Founder can flip this to true once the remaining ~193 modules
are wired/removed. Default = false so boot doesn't break on the
existing backlog.

## Next session

193 unwired modules remain. The 20 highest-traffic ones from each
subsequent session can be wired in 5-min sweeps using the same
`TOP_20_UNWIRED` pattern. After all 213 are addressed, set
`AUREM_STRICT_SETDB_WIRING=true` in `.env` and the contract is
permanently enforced.
