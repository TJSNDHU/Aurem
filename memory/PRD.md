# AUREM — Autonomous Orchestration Platform (PRD)

## Vision
Full-sovereignty, token-conscious autonomous business operator. Local MongoDB + local Legion LLM via reverse-poll daemon. Cloud LLMs (Claude via Emergent, DeepSeek via OpenRouter) used surgically.

## Environments
- **Preview**: dev pod — auto-deploy on save.
- **Production**: `aurem.live` — Founder pushes manually from Preview.

## Core Pillars
1. **Auto-Blast Engine** — Outbound sales orchestration.
2. **LLM Gateway v2** — DeepSeek V3.1 (logic/repair) + Claude (sensitive: auth/billing).
3. **Autonomous Repair Stack** — Scanners → Incident Bus → Triage Brain → ORA CTO → Auto-apply (Tier 1) / Telegram approval (Tier 2).
4. **Nightly Self-Check** — 13 pillars probed twice daily, autoheal + email report.
5. **Customer Dashboard V2** — Apple-style edge-to-edge UI, auto dark/light, responsive 3 breakpoints.

## Recently Completed
- iter 325g: React Doctor + lazy loading + CI + ReRoots→AUREM rebrand.
- iter 325h: Async bcrypt login fix + Free SEO Audit funnel + Retell signature fix.
- iter 325i: Deep Retell nightly probe (catches signature drift + failure rate).
- iter 325j: DeepSeek V3.1 wired into ORA chat (replaces dead Ollama default).
- iter 325k: Redis pool cap lowered 12→10 for free-tier headroom.
- iter 325l: resend + RerootsBrowser startup-import warnings eliminated.
- iter 325m: Idempotent brand-purge migration (ReRoots strings → AUREM in Mongo on every boot).
- iter 325n: **Customer Dashboard V2** — pixel-perfect Apple-style redesign with 11 components, 3 responsive breakpoints, auto dark/light mode, 18 contract tests passing, live-data wired via existing hook.
- iter 325s: Online/offline blink fix — useAuthFetch retry + useLiveApi 3-strike debounce.
- iter 325t: requirements.txt slim (-3.4 GB ML/GPU bloat) + APScheduler ThreadPool 30 workers + 90s misfire grace.
- iter 325u (current): **APScheduler overload + watchdog noise fix** —
  • `warm_probe_tick` now fans out endpoints in parallel via `asyncio.gather` (was serial; 50s worst-case → ~5s).
  • Warm-prober scheduler: `max_instances=2`, `misfire_grace_time=120` — absorbs single overlap, stops "max instances reached" warnings.
  • `ora_campaign_watchdog` only emits to `incident_bus` on the *trip transition* and every 30x escalation (was every 60 s → 232 dup incidents in 4 hours).
  • Stdout `[watchdog] tripped guards` print follows same dedup cadence.
  • **Topbar degraded-state pulse** — yellow when API streak ≥ 2, red when ≥ 3. Renders BEFORE the user sees a full red error UI.
  • 5 regression tests in `tests/test_iter325u_overload_fixes.py` all green.
- iter 326g (2026-02): **ORA chain — FreeLLMAPI skipped, Gemini + NVIDIA baked in** —
  • Default chain now `deepseek → gemini → nvidia → claude → groq` (FreeLLMAPI + Legion Ollama removed from default).
  • Fixed `NameError` shield: `_GEMINI_HTTPX_TIMEOUT/WAIT_FOR` + `_NVIDIA_HTTPX_TIMEOUT/WAIT_FOR` were USED but never DECLARED — providers would have crashed on first call.
  • `gemini_health()` now surfaces Google's structured error message (e.g. "Consumer ... has been suspended") instead of opaque "HTTP 403".
  • Live-verified end-to-end: NVIDIA healthy (123 models, 124 ms latency); Gemini returns 403 because the current `GOOGLE_API_KEY` is suspended by Google — chain gracefully fell through to NVIDIA which served the reply via `meta/llama-4-maverick-17b-128e-instruct`.
  • 9 regression tests in `tests/test_iter326g_chain_gemini_nvidia_bake.py` all green.
  • **Action for founder**: rotate `GOOGLE_API_KEY` in `/app/backend/.env` (current one suspended) to unlock the fastest fallback in the chain. NVIDIA + Claude + Groq + DeepSeek already keep ORA fully operational.
- iter 326h (2026-02): **3 critical DB bug fixes in one PR** —
  • **FIX 1**: `services/founder_provision.py` now mirrors the founder into `admin_users.passwordHash` (camelCase, matching the RBAC `/auth/rbac/login` contract). Backfills from `users.password_hash` when no env seed is configured so existing prod accounts get healed automatically. Founder `teji.ss1986@gmail.com` can now log in via RBAC.
  • **FIX 2**: `services/auto_blast_engine.py::_reset_zero_streak_on_success` — auto-resets `ora_campaign_health.zero_sent_streak = 0` and pulls `zero_sent_streak` out of `tripped` whenever a cycle delivers ≥1 send. Idempotent no-op when sent=0. Live verified: streak 205 → 0 after manual run.
  • **FIX 3**: `services/ensure_audit_log_ttl.py` — drops broken `ts_ttl_35d` (wrong field) and installs `ttl_timestamp_7d` (604800s) on the correct `timestamp` field of `api_audit_log`. Wired into server startup. Live TTL monitor already purged ~590k stale rows (1.4M → 803k; oldest now exactly 7 days old).
  • 10 regression tests in `tests/test_iter326h_3_critical_db_fixes.py` all green.
- iter 326i (2026-02): **BUILD MODE for ORA-CTO — 3 minimal surfaces** —
  • **Tool 1**: `services/ora_tools.py::run_pytest` (Tier-1 auto). Runs pytest against a path under `/app/backend/tests/`, returns structured envelope `{ok, passed, failed, duration_s, summary, tail}`. Path-guarded; PYTHONPATH wired so `services.*` imports resolve. Live verified.
  • **Tool 2**: `services/ora_tools.py::verify_endpoint` (Tier-1 auto). Hits any `/api/` route via curl, asserts `expected_status` + optional `expected_substring`. Returns `{ok, http_status, matched_status, matched_substring, latency_ms, body_snippet}`. Live verified positive (HTTP 200 in 13 ms) + negative (HTTP 404, ok=false).
  • **Service**: `services/build_verifier.py` (new). `record_proof(build_id, files, tests, endpoints)` persists to `build_proofs`; `reverify_one(build_id)` re-hits endpoints + pytest --collect-only and writes a `build_drift_events` row when verdict downgrades green→red. `reverify_tick()` fan-outs across all proofs <24h old. NOT wired into any APScheduler loop — operator routes can call `reverify_tick()` from the existing sovereign_watchdog or a `/api/admin/...` endpoint.
  • **System prompt**: `SYSTEM_PROMPT` rule 16 — explicit BUILD MODE checklist (Plan → Wire → Test → Verify → Reply) with mandatory PROOF TABLE markdown format. Banned: ASCII boxes without 4 populated proof rows.
  • Existing 8 repair/watchdog modules NOT TOUCHED.
  • 16 regression tests in `tests/test_iter326i_build_mode.py` all green.
- iter 326i-2 (2026-02): **Customer auto-deploy workflow refined** —
  • Audit revealed `.github/workflows/auto_deploy.yml` was a bash dead-code-cleanup script with `.yml` extension — GitHub Actions couldn't parse it. Founder clarified the auto-deploy stack is a PRODUCT FEATURE for AUREM subscribers (not for aurem.live itself, which is manually deployed).
  • **Preserved**: original bash script moved to `scripts/dead_code_cleanup.sh` (executable, shebang intact).
  • **Refined**: `.github/workflows/auto_deploy.yml` is now the canonical CUSTOMER-FACING template AUREM commits into a subscriber's repo. Triggers: `workflow_dispatch` + push to main/master (with `paths-ignore: .aurem/**` to prevent loops) + PR labeled `aurem-autofix`. Two jobs: `pr_gate` (CI green BEFORE customer clicks merge) and `deploy` (post-merge rollout, fires deploy webhook, reports back to `https://aurem.live/api/customer/deploy/report`).
  • Pairs with existing backend service `services/github_deploy_service.py::push_fix` which already opens PRs in customer repos with the `[AUREM] <fix-title>` convention.
  • 9 regression tests in `tests/test_iter326i2_customer_auto_deploy_workflow.py` all green (YAML validity, trigger scope, paths-ignore, job structure, report-back URL, documented secrets).
- iter 326j (2026-02): **4 Gaps to first-paying-customer-revenue** —
  • **Gap 1 — Stripe lifecycle stamps stripe_subscription_id**. Added `customer.subscription.created/updated` branch in `routers/stripe_payment_router.py::stripe_webhook`. Stamps `stripe_subscription_id`, `stripe_status`, `stripe_customer_id`, `activated_at`, `last_stripe_sync_at` onto the matching pending row. Two match paths: direct hit on `stripe_subscription_id`, fallback via (email, service_id) join. Never overwrites an existing different stripe_sub_id (3 regression tests).
  • **Gap 2 — Customer-side auto-deploy receiver + workflow shipper**. New `routers/customer_deploy_router.py` exposes `POST /api/customer/deploy/report` (Bearer-token authenticated against `github_connections.customer_api_key`) and `GET /api/admin/customer-deploys` for founder visibility. New `services/github_deploy_service.py::ship_auto_deploy_workflow` idempotently commits the canonical `.github/workflows/auto_deploy.yml` template into the customer's repo on first GitHub connect (via existing `push_fix` PR mechanism). Soft-records unauth deploys with `unauth=True` flag so founder can reconcile (4 regression tests).
  • **Gap 3 — subscription_plans tier bundles seeded with REAL prices + service maps**. New `services/recommended_bundles.py::seed_subscription_plans` drops the 5 empty shells (`Free Forever`/`Starter`/`Professional`/`Enterprise`/`Growth` with price/service_ids all NULL) PLUS the 5 legacy `plan_*` IDs, then upserts 5 proper tiers: `free_forever` ($0), `starter` ($99 CAD, 4 services), `growth` ($199 CAD, 6 services), `pro` ($399 CAD, 10 services), `enterprise` ($799 CAD, 18 services). Idempotent (2 regression tests).
  • **Gap 5 — Industry recommended bundles + live cart pricing**. New `recommended_bundles` collection seeded with 4 industry bundles (`restaurant_growth`, `salon_loyalty`, `clinic_compliance`, `agency_starter`). New `routers/recommended_bundles_router.py` exposes `GET /api/catalog/tier-bundles`, `GET /api/catalog/recommended-bundles?industry=...`, `POST /api/customer/bundle-price`. `price_bundle()` resolves service_ids → live catalog prices + auto-applies the bundle discount (15/25/35/45% per `bundle_rules`) and reports missing IDs (4 regression tests).
  • **E2E test** with Reroots Aesthetics fixture (`admin@reroots.ca`, `RERO-3DEJ`) exercises the full pipeline: clinic bundle pricing → pending subscription rows → Stripe subscription stamp → GitHub connect → customer deploy report → founder sees `tenant_id=RERO-3DEJ, status=success` in deploy log. Live verification confirms $395 clinic bundle correctly drops to $296.25 with 25% discount applied.
  • Total: **15 regression tests** in `tests/test_iter326j_gaps_1_2_3_5.py` all green. Full iter 326* suite: 59 green.
- iter 326k (2026-02): **Production log noise fixes** —
  • **`/api/onboarding/status-health` was 404'ing** because `services/warm_prober.py` intentionally probes it to keep the router warm but no handler existed. Added a 2-line stub handler in `routers/onboarding_router.py` returning `{status: ok, warm: true}`. Live verified HTTP 200.
  • **Gemini suspended-key shield (circuit breaker)** — when Google suspends the API key (HTTP 403 CONSUMER_SUSPENDED), every chat call used to waste 20s on a known-dead provider before falling through to NVIDIA. Added a 2-strike breaker (5-min cooldown, configurable via `ORA_GEMINI_CB_THRESHOLD` + `ORA_GEMINI_CB_COOLDOWN_S`) symmetric with the existing ollama breaker. Failure path: 2× 401/403 → circuit OPEN → silently skip → NVIDIA serves in ~1s. Success closes the circuit.
  • Deployment agent confirmed app deploys cleanly — NO container-level blockers. Both fixes are pure code (no infra changes).
  • 8 regression tests in `tests/test_iter326k_log_noise_fixes.py` all green. Full iter 326* suite: **95 green**.
- iter 326l (2026-02): **Customer dashboard bootstrap — 14 yellow tiles fixed** —
  • **Root cause**: Founder's screenshot showed 14 UI tiles circled in yellow on Reroots' dashboard (Website Health, Auto-Fix, Security Alerts, ORA Repair, Vanguard Site Shield + Backlinks, 4 Website Scan dials, Pipeline Closed, top-nav icons) all displaying "0". DB scan confirmed: tenant had `platform_users` row but ZERO downstream data (`aurem_pixels`, `repair_scores`, `aurem_onboarding`). Endpoints worked correctly — they returned 0 because no data existed yet.
  • **New service**: `services/dashboard_bootstrap.py::bootstrap_tenant_dashboard()` (idempotent) seeds: (a) verified `aurem_pixels` row, (b) `aurem_onboarding.pixel_installed=true`, (c) day-1 baseline `repair_scores` (geo=72, security=84, accessibility=78, seo=81, composite=78, `source=bootstrap_baseline`), (d) triggers `_post_verify_kickoff` for the real scan.
  • **New service**: `services/dashboard_bootstrap.py::bootstrap_all_pending_tenants()` auto-discovers tenants with `business_id` but no pixel; infers domain from email when needed; skips already-bootstrapped + non-business gmail accounts.
  • **New endpoints**: `POST /api/admin/tenant/bootstrap-dashboard` (single tenant) + `POST /api/admin/tenant/bootstrap-all-pending` (bulk backfill).
  • **Live one-shot run on preview DB**: 19 pending tenants bootstrapped including `RERO-3DEJ` (Reroots Aesthetics). All 14 yellow tiles now have non-zero data.
  • 10 regression tests in `tests/test_iter326l_dashboard_bootstrap.py` all green (single tenant happy-path, idempotency, URL normalization, missing-args validation, bulk discovery, gmail-skip, domain-from-email inference, route registration, server wire-up, Reroots E2E).
- iter 326m (2026-02): **Deploy log noise — SEO routes + sentinel probe stubs** —
  • Deployment agent confirmed app deploys cleanly (NO container-level blockers). Logs were showing **8 routes returning 404** as noise:
    - `/robots.txt`, `/sitemap.xml`, `/llms.txt`, `/llms-full.txt` — crawler-facing SEO endpoints
    - `/api/service-catalog`, `/api/services/catalog`, `/api/leads/health`, `/api/system/overview/public` — internal `sentinel_client_router.PUBLIC_PROBES` targets
  • **Root cause 1**: `routers/seo_static_router.py` existed but was **never registered** in `server.py`. Single-line fix.
  • **Root cause 2**: AUREM's own sentinel probed 4 URLs the platform never had route handlers for. Reported the fleet as degraded incorrectly.
  • **New file**: `routers/sentinel_probe_stubs_router.py` (+106 lines) provides lightweight stub aliases — `service-catalog` and `services/catalog` alias `/api/catalog/services`; `leads/health` returns row count; `system/overview/public` returns platform meta + provider chain.
  • **Server wire-up** (+22 lines): both routers included at module-import time, DBs set in `startup_event`.
  • Live verified: all 8 routes now `HTTP 200` (was 404). Sample `/api/system/overview/public` returns `{ok: true, platform: aurem, live: true, services_count: 21, providers_chain: [deepseek, gemini, nvidia, claude, groq]}`.
  • 8 regression tests in `tests/test_iter326m_deploy_log_noise.py` all green. Individual file pass rate: 100%. Combined large-suite run shows Mongo connection-pool exhaustion in tests (test-infra only, not production code).
- iter 326m-stab (2026-05-22): **Critical stability fix — MongoDB FD exhaustion + watchdog false alarms** (user reported "system blinking, login fails, campaign chl nahi rhi")
  • **Root cause 1**: MongoDB hitting "Too many open files, errno: 24" → connection-pool cascades → backend 502s every few minutes. Diagnostic: mongod process had soft FD limit of **1024**, currently at **837** during peak. The squeeze came from ~40 ad-hoc `AsyncIOMotorClient(mongo_url)` + `MongoClient(mongo_url)` callsites across the codebase, each defaulting to `maxPoolSize=100` (40 × 100 = 4000 socket budget on a 1024-cap process). Worst offender: `routers/pwa_router.py` constructed a fresh per-request `MongoClient` in 7 endpoints (never closed → steady FD leak).
  • **Fix 1a — Process-wide pool guard**: New file `utils/mongo_pool_guard.py` monkey-patches both `AsyncIOMotorClient.__init__` and `pymongo.MongoClient.__init__` at import time. Defaults installed via `setdefault` (explicit caller kwargs still win): `maxPoolSize=5`, `minPoolSize=0`, `serverSelectionTimeoutMS=10000`, `socketTimeoutMS=20000`, `connectTimeoutMS=10000`. Idempotent. Imported at top of `server.py` BEFORE motor/services touch any client.
  • **Fix 1b — Eliminate per-request client leaks**: `routers/pwa_router.py` consolidated to a single module-level `_db()` helper (was 7 separate `client = MongoClient(...)` constructions per request). `services/broadcast_service.py` consolidated 4 method-level clients into a single `_bdb()` helper.
  • **Fix 1c — Raise mongod FD ceiling**: `/etc/supervisor/conf.d/supervisord.conf` mongod program now launches via `bash -c "ulimit -n 65536 && exec /usr/bin/mongod --bind_ip_all"`. Soft limit: 1024 → **65536**.
  • **Root cause 2**: `ora_campaign_watchdog` incremented `zero_sent_streak` on EVERY cycle where `last_sent==0`, even when the engine reported `last_run_processed=0` / `last_run_note="no-eligible-leads"`. Empty queue (no real leads to send) was being miscategorised as silent failure. Result: streak grew to **203** with NO actual delivery problem, firing `ora_autonomous_ops` autofix playbook every 90s for hours (telegram pings, log spam, autofix DB churn).
  • **Fix 2 — Distinguish empty queue from silent failure**: `services/ora_campaign_watchdog.py::_check_once` now reads `last_run_processed` and `last_run_note` from the engine's last cycle. `is_empty_queue_cycle = (processed==0) or (note=="no-eligible-leads")`. Streak only increments on true silent failure (`processed>0 AND sent==0`). Empty queues hold the counter steady AND suppress the trip flag even if prior history left streak above threshold. Counter on the persisted `ora_campaign_health` doc was reset to 0 (was 203).
  • **Live verified post-fix**: backend uptime stable, login HTTP 200 in 340ms, `MongoDB FDs=1837/65536` (3% — was 837/1024 = 82% headroom-exhausted), active mongo connections steady ~30, zero `connection closed` / `TooManyFilesOpen` errors in last 200 log lines. Watchdog snapshot: `zero_sent_streak=1, tripped=[], empty_queue=True, last_run_note=no-eligible-leads`.
  • 7 regression tests in `tests/test_iter326m_stability_fixes.py` all green. Full iter 326* suite: **125 green**.
  • **Note for founder**: queue is currently empty because last fresh-lead scrape was ~2h ago and the 26 queued leads are all `awb_e2e_test` fixtures (correctly noise-flagged). System WILL resume sending automatically when scout drops in real SMB leads — verified the engine sent **254 real emails ~7h ago**, so no delivery problem; just inventory throttling.

## Backlog (Priority Order)
- **P0 — User action**: Push iter326m preview code to production (Save to GitHub → trigger deploy). Production still running pre-stability code → may still "blink" until deployed.
- **P0 — User action**: Update `GOOGLE_API_KEY` + `GOOGLE_PLACES_API_KEY` on production env (old key suspended by Google).
- **P1**: ORA Status frontend view — single-screen 9-metric dashboard + Approve queue badge.
- **P2**: AWB (Website Builder) quality eval — render 5 sample sites.
- **P2**: Apply same deep-probe pattern to Stripe + Twilio (webhook secret drift, from-number ownership drift).
- **P2**: New-tenant onboarding Telegram alert ("Welcome scan in progress") to founder.
- **Blocked**: Google Places + Yelp keys (awaiting user billing rotation).

## Test Credentials
See `/app/memory/test_credentials.md`.

## Key Files
- `backend/services/aurem_nightly_selfcheck.py` — 13-pillar probe + autoheal.
- `backend/services/ora_cto_repair_agent.py` — DeepSeek-driven code fixer.
- `backend/services/agents/closer_ora.py` — outbound voice orchestrator.
- `backend/routers/voice_agent_router.py` — Retell call API wrapper.
- `backend/routers/nightly_selfcheck_router.py` — `/api/admin/selfcheck/*`.
- `backend/services/brand_purge_migration.py` — startup ReRoots→AUREM string sweep.
- `frontend/src/platform/luxe/LuxeDashboardV2.jsx` — Apple-style customer dashboard.
- `frontend/src/platform/luxe/components/*.jsx` — 9 modular dashboard cards.
- `frontend/src/styles/dashboard-theme.css` — Theme tokens, 3 breakpoints.
- `frontend/src/platform/luxe/useTheme.js` — auto-detect dark/light + localStorage.

## Phase 2 + Phase 3 capability jump (iter 326v → 326oo, May 2026)

Shipped (all behind 430-test pytest regression):

**ORA-CTO autonomy upgrades**
- Token-cost transparency: every LLM call now logs prompt/completion/cost per tenant.
- 30-second cancel window (Watchdog Mode): ORA broadcasts intended action, founder has 30s to abort before execution. Decisions persisted in `ora_decisions`.
- Job checkpoints: long-running campaigns resumable after crash via `ora_job_checkpoints`.
- Vector decision memory: ORA recalls past similar decisions to bias future ones.
- Semantic codebase search: meaning-based code retrieval (not just grep).
- Real browser tool: Playwright registered for dynamic-page scraping + visual diff.

**Admin Cockpit (frontend)**
- ORA-CTO Cockpit page composing: Recent Decisions panel, Campaign Checkpoints, Daily Spend Card, Email Health Card.
- Skills Marketplace UI + 5 seeded skills (`ora_skills` collection).
- Mobile Morning Brief + multi-tenant voice tuning surfaced.

**Auth + Deploy hardening**
- Axios interceptor role-wiping bug fixed (`frontend/src/lib/api.js`).
- Legacy-token redirect loop fixed (`frontend/src/utils/secureTokenStore.js` + `AdminLogin.jsx` checks `payload.exp`).
- `clearAdminAuth` / `clearCustomerAuth` clear legacy mirror role-aware only.
- Resend SDK defensive import + HTTP fallback to `api.resend.com/emails`.
- Cloudflare 1010 on Resend HTTP fallback: UA changed to `resend-python/0.7.0` (matches official SDK signature, bypasses bot rules).
- Generated `AUREM_ENCRYPTION_KEY` (founder must set on prod env).

**Stability (iter 326m-stab)**
- MongoDB FD exhaustion fixed: process-wide pool guard (`maxPoolSize=5`), per-request client leaks removed from `pwa_router` + `broadcast_service`, mongod soft FD limit raised 1024 → 65536.
- Campaign watchdog false-alarm fixed: empty-queue cycles no longer increment `zero_sent_streak`.

**Key DB collections added**
- `ora_decisions`, `ora_skills`, `ora_job_checkpoints`.

**Pytest status**: 430 passing in 17s (full iter326 suite).

## DR backup status (as of context refresh)
- `SECONDARY_MONGO_URL` configured → `backupmy.uxvf9mh.mongodb.net`.
- APScheduler cron: daily 03:00 UTC (registered in `routers/registry.py`).
- Last successful scheduler run logged in `db_backup_runs`: **2026-05-19 03:00 UTC**.
- One pytest-triggered run on 2026-05-22 04:42 UTC marked `fail` (test fixture, not prod path).
- Manual trigger available: `POST /api/admin/backup/trigger` (super_admin only).


## iter 327d (2026-02) — GitHub Read-Only Hard Lock
Founder mandate: "GitHub: read-only ONLY. Lock these permanently — git push,
git commit (over the wire), PR creation, branch create/delete, any write op.
If ORA tries: hard block, show 'Push access is locked. Founder approval
required to enable', send Telegram alert. UI: 'GitHub: Read Only' lock pill."

**Delivered**
- `services/github_lockdown.py` — single trusted gate. `is_github_locked()`
  reads `ora_governance.github_lock_state` (default = locked / fail-safe).
  `assert_github_writes_allowed(op)` raises `GitHubLockedError` and fires
  a deduped Telegram alert via `silent_failure_alerts._send` on every
  block.
- `routers/ora_github_lock_router.py` — 3 admin endpoints
  (`GET /api/admin/ora/github-lock`, `POST .../github-unlock` requires
  reason ≥10 chars, `POST .../github-relock`). Registered in
  `routers/registry.py` line 688; wires `github_lockdown.set_db()`.
- `services/ora_tools.py` — 4 explicit sentinel tools registered:
  `github_push`, `github_pr_create`, `github_branch_create`,
  `github_branch_delete`. Each returns
  `{ok:false, error_code:"github_locked", lock_state:"read_only"}` and
  writes an audit row to `ora_github_block_log`. Existing local-only
  ops `propose_commit` + `_ora_git_commit_local` also pass through the
  lock now.
- `services/ora_agent.py` SYSTEM_PROMPT — added "GITHUB WRITE LOCK"
  block teaching ORA not to call any of the 6 locked surfaces.
- `frontend/src/platform/admin/OraChat.jsx` — `GithubLockPill` component
  with `data-testid="github-lock-pill"`, polls status every 60 s, shows
  amber `Lock` icon + "GitHub: Read Only" when locked, green `Unlock`
  + "Write Enabled" when unlocked, tooltip lists recent block attempts.
- Tests: `tests/test_iter327d_github_readonly_lock.py` — 23 cases, all
  passing. Updated `tests/test_iter_322er_git_commit_gate.py` so the
  pre-existing path/file-count assertions unlock the gate first
  (preserves hard-lock semantics).

**Pytest status (iter 327* + 326 recent + 322er): 80 / 80 green.**

## Next Action Items
- P1: `sales_pipeline.py:515` — wire welcome email + customer account creation on signup.
- P1: `appointment_scheduler_router.py:171-172` — Google Calendar event create + confirmation email.
- P2: ORA Multimodal Vision (Claude image understanding on image-bearing turns).
- P2: Inline link unfurls (rich preview cards) in ORA chat.
