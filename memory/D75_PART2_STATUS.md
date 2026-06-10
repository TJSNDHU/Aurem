# D-75 Part 2 — Route Dedupe Status

## What got fixed this session (#1 + #2)

| Item | Status | Tests |
|------|--------|------:|
| 1 — `creds_health` dashboard | ✅ live, 16 providers probed | 9 |
| 2 — Route dedupe (idempotent guard) | ✅ 314 → 17 dupes (-94%) | 5 |
| 2 — Boot-time `_detect_duplicate_routes` | ✅ emits WARNING per dupe | (in 5) |
| 2 — Boot-time `_detect_unwired_set_db_modules` | ✅ found 213 unwired | (observability) |

## What `creds_health` caught (new findings)

Two NEW stale credentials found by the dashboard's first live probe:

  * 🔴 **ElevenLabs 401** — `ELEVENLABS_API_KEY` tail `…3640` rejected
  * 🔴 **Google PageSpeed 403** — `GOOGLE_PAGESPEED_API_KEY` tail `…iapA` rejected

Plus the known:
  * 🔴 **Twilio 401** (founder rotation pending)
  * 🟡 **Tavily 432** (founder decision pending)

4 providers **not configured** (E2B, GitHub, Sentry, Vercel) — env vars
not set; dashboard says so honestly.

6 providers **green** with latency: Apollo 457ms, Deepgram 424ms,
Emergent LLM 252ms, OpenRouter 247ms, Resend 367ms, Stripe 342ms.

## The 17 remaining route handler conflicts (for next session)

After the idempotent `include_router` guard, 17 genuine cross-handler
duplicates remain. Each needs a D-72-style diff → pick winner → delete
loser → E2E test. Categorized:

### A. Liveness/health (5) — keep `bootstrap.health_routes`, drop `server._liveness_*`
  * `GET /api/health`
  * `GET /api/platform/health`
  * `GET /health`
  * `GET /ready`
  * `GET /api/platform/health` (3-way: `ai_platform_router` vs `server._liveness_platform_health` vs `bootstrap.health_routes`)

### B. Founder-saves self-dupes (3) — same module, included via 2 mount points
  * `GET /api/admin/founder-saves/_/health`
  * `GET /api/admin/founder-saves/summary`
  * `GET /api/admin/founder-saves/timeline`
  Fix: remove the secondary mount in registry.py.

### C. Cross-module conflicts (9) — needs human decision
  * `POST /api/aurem/chat`  → `aurem_routes` vs `aurem_chat`
  * `POST /api/auth/forgot-password`  → `routes.auth` vs `routers.server_misc_routes`
  * `POST /api/auth/reset-password`  → same pair
  * `GET /api/auth/verify-reset-token`  → same pair
  * `POST /api/auth/google/callback`  → `google_oauth_callback` vs `routes.auth`
  * `POST /api/email/inbound`  → `inbound_email_router` vs `email_inbound_router`
  * `GET /api/email/inbound/health`  → same pair
  * `GET /api/enterprise/audit`  → `enterprise_router` vs `enterprise_engine`
  * `POST /api/incident/resolve/{incident_id}`  → `v2_customer_actions_router` (alias) vs `incident_router`
  * `POST /api/self-audit/run`  → `self_audit_router` vs `autonomy_router`

### Process for next session
For each pair:
  1. Diff the two handlers — feature parity check
  2. Pick the more mature one (auth completeness, error handling,
     logging, recent commits)
  3. Delete the loser's `@router.{verb}(path)` decorator (keep helper
     functions if other code imports them — see D-72 surgical pattern)
  4. Live E2E test asserting the winner's behavior is the one running
  5. Update `test_d75_route_dedupe.py` threshold downward (17 → 7 →
     0) as each pair lands

## Unwired set_db modules — 213 found

`_detect_unwired_set_db_modules` flagged 213 router modules that
define `set_db()` but never receive a DB handle from `register_all_
routers`. Their endpoints silently 503 with "Database not available".

Full list logged at startup. Next-session work: wire the high-traffic
ones (admin_customers_router, approval_router, settings_router,
revenue_engine, etc.), explicitly remove `set_db()` from genuinely
deprecated routers, and convert the WARNING to a RuntimeError once
the list is empty.
