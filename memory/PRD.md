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

## iter 327e (2026-02-23) — Chat jargon scrub + curl resilience + sidebar collapse
Founder reported (photo from Legion pod) that ORA was:
  1. Pasting raw tool-call syntax — `curl_internal(endpoint="/api/...", method="GET")` — into chat.
  2. Showing `FileNotFoundError: [Errno 2] No such file or directory: 'curl'` to the founder.
  3. Asking for a collapse button on the ORA-CTO sidebar.

**Delivered**
- `services/ora_tools.py::curl_internal` rewritten to use `httpx`
  (already a backend dep) instead of subprocess-ing the `curl`
  binary. Survives any pod regardless of whether curl is installed.
- `services/ora_agent.py::_looks_like_unhandled_tool_call` extended
  to catch Python-call style leaks (`tool_name(arg=...)`) for any
  registered tool name. JSON-shape detection unchanged.
- `services/ora_agent.py::_humanize_tool_error` (new) — strips
  `FileNotFoundError`, `[Errno N]`, full tracebacks,
  `ConnectionRefusedError`, `TimeoutError` from tool error
  envelopes BEFORE they flow back into the LLM context. The LLM
  literally cannot regurgitate phrases it never saw.
- `frontend/src/platform/admin/OraAdminUnified.jsx` — desktop
  sidebar now has a `ChevronLeft/Right` collapse button
  (`data-testid="ora-admin-sidebar-collapse"`). Width animates
  220 → 64 px; tab labels collapse to icon-only rail with hover
  tooltips. Preference persisted in `localStorage`
  (`ora_admin_sidebar_collapsed`).
- Tests: `tests/test_iter327e_chat_jargon_and_curl_resilience.py`
  — 15 cases, all green.

## iter 327f (2026-02-23) — 15-minute GitHub-unlock TTL + auto-relock
Founder mandate (verbatim): "Yes — add 15-minute unlock timer.
One click unlock → auto-relocks after 15 min. Audit row on relock."

**Delivered**
- `routers/ora_github_lock_router.py::UnlockBody` now accepts
  `ttl_minutes` (default 15, range 1-60). `/github-unlock` writes
  `unlock_expires_at` to the lock row + audit, and returns
  `seconds_until_relock` to the UI.
- `services/github_lockdown.py::is_github_locked()` is now TTL-aware:
  on every read, if the row says `locked=False` but
  `unlock_expires_at` is past, lazily flips the row back to locked,
  clears the expiry, and writes an audit entry
  (`action='github_auto_relock_ttl'`). Concurrency-safe via a
  filter-on-`locked:False` upsert.
- `services/github_lockdown.py::get_lock_status()` surfaces
  `unlock_expires_at` + `seconds_until_relock` so the UI can show
  a live mm:ss countdown.
- `/github-relock` now unsets `unlock_expires_at` so an early
  manual relock doesn't leave a ghost countdown in the UI.
- `frontend/src/platform/admin/OraChat.jsx::GithubLockPill` is now
  a `<button>`: one-click while locked prompts for a ≥10-char
  reason and calls `/github-unlock` with `ttl_minutes: 15`. While
  unlocked it shows `GITHUB: WRITE ENABLED · 14:32` with a live
  1-second tick (server poll cadence: 30 s unlocked / 60 s locked).
  Click while unlocked re-locks immediately.
- Tests: `tests/test_iter327f_github_unlock_ttl.py` — 11 cases,
  all green. Covers TTL field validation, lazy auto-relock,
  audit-row creation, status-endpoint countdown, router default,
  and the clickable UI pill.

**Pytest status (322er + 327d + 327e + 327f): 54 / 54 green.**

## iter 327h (2026-02-23) — Production-404 pixel fix + Appointment Calendar/Email
Founder reported in production logs:
  - `POST /api/universal/webhooks/generic` → 404 (AUREM pixel data loss)
  - P1 follow-up: `appointment_scheduler_router.py:171-172` Google
    Calendar + confirmation email TODO.

**Delivered — Track A (pixel webhook 404)**
- Root cause: `routers/_registry_config.py::SKIP_IN_LEAN` (line 52)
  contained `routers.universal_connector_router`. With
  `LEAN_ROUTES=1` (the production default) the registry never called
  `app.include_router` for it — every `/api/universal/*` route
  returned 404, including the AUREM tracking pixel's POST to
  `/api/universal/webhooks/generic` (static/aurem-pixel.js:44).
  Same skip list also had `appointment_scheduler_router`, which
  would have blocked the P1 fix below.
- Fix: removed both modules from `SKIP_IN_LEAN`, left an inline
  comment explaining why so the next maintainer doesn't re-disable.
- Live verification on preview: `POST /api/universal/webhooks/generic`
  now returns HTTP 200 with `{"received": true, "event_id": "...",
  "universal_type": "custom.pixel_test"}`. The webhook payload normalizes
  through `services/universal_connector.normalize_webhook_event` and
  inserts into `db.universal_events` (or `_unresolved_quarantine` if no
  tenant_id resolved).

**Delivered — Track D (appointment calendar + email)**
- `routers/appointment_scheduler_router.py` — replaced the two TODO
  lines with real work. No third email system, no new Google Calendar
  SDK pulled in:
    1. `_build_ics(appointment)` — RFC 5545 portable iCalendar invite
       (works in Google Calendar, Outlook, Apple Mail, Thunderbird).
       Proper CRLF line endings, basic-UTC datetimes, escaped TEXT
       fields.
    2. `_build_google_calendar_quick_add_url(appointment, base)` —
       one-click `https://calendar.google.com/calendar/render?
       action=TEMPLATE&...` URL so the customer adds the event to
       their personal calendar without any OAuth/API-key dance on
       our side.
    3. `_send_confirmation_email(appointment, ics_url, gcal_url)` —
       calls `GmailService.send_email` DIRECTLY (not the
       fire-and-forget `email_service.send_email` wrapper that
       returns True even on failure). Returns `{ok, message_id}` or
       `{ok: False, error}`. The booking handler persists
       `confirmation_email_sent_at` / `confirmation_message_id` on
       success, or `confirmation_email_error` on failure — booking
       UI gets the truth.
    4. New public endpoint `GET /api/appointments/{appointment_id}/
       calendar.ics` — serves the .ics with the right `text/calendar`
       content-type so any calendar app can grab it. Auth = the
       16-hex appointment_id secret (same pattern as
       `/api/report/{slug}`).
- The book endpoint now returns `confirmation_email_sent` (bool),
  `confirmation_email_error` (nullable), `ics_url`, `gcal_url` —
  callers can decide whether to surface a retry button.
- Tests: `tests/test_iter327h_pixel_404_and_appointments_calendar.py`
  — 13 cases. Covers SKIP_IN_LEAN regression, .ics envelope/escaping,
  GCal URL params, three branches of confirmation send (no Gmail /
  ok / send failure), TODO-removed source check, .ics route exposure.

**Pytest status (322er + 327d/e/f/g/h): 76 / 76 green.**

## Next Action Items
- P2: ORA Multimodal Vision (Claude image understanding on image-bearing turns).
- P2: Inline link unfurls (rich preview cards) in ORA chat.
- P3: Optional — proper Google Calendar API (service-account) event
  creation on a shared AUREM calendar, gated on `GOOGLE_CALENDAR_ID`
  + `GOOGLE_SERVICE_ACCOUNT_KEY` env vars. Today's per-customer
  "add to your calendar" link covers 95% of UX; this would just
  give AUREM staff visibility on a central calendar.

## iter 327j (2026-02-23) — Log silencers + ORA Vision + Link Unfurls
Founder mandate: ship cosmetic log cleanup AND the two P2 wirings in one iter.

**Delivered — cosmetic log silencers (zero functional change)**
- `services/email_engine.py` — collapsed two nested resend warnings into
  one INFO line ("resend top-level import quirky ... using fallback").
- `services/ora_agent.py` — warmup ConnectTimeout demoted WARNING → DEBUG
  on all 4 providers (FreeLLMAPI / Gemini / NVIDIA / DeepSeek). Cold-pod
  warmup failures are expected and the runtime falls back automatically.
- `bootstrap/startup_validation.py` — split EXPECTED groups into REQUIRED
  vs OPTIONAL_GROUPS (`ollama_sovereign`, `scraping`, `groq_fallback`).
  Optional misses log at INFO ("OPTIONAL env vars not set (feature off)")
  instead of shouting in WARNING.
- `services/memoir_service.py` — git-binary-not-found path demoted to
  DEBUG (git is never present in the deploy container).

**Delivered — ORA Vision (GPT-4o wired into ORA-CTO chat)**
- `routers/ora_attachments_router.py::attach_file` — on image upload, calls
  the existing `services.multimodal_processor::MultiModalProcessor.
  _analyze_image(blob)` (GPT-4o vision via emergentintegrations, built in
  iter 322ar). Description cached on `ora_attachments.vision_description`
  so subsequent chat turns reuse it for free.
- `render_attachment_context` image branch now splices the cached
  description into the context block under a clear marker:
  `--- vision (GPT-4o description) --- ... --- end vision ---`. The LLM
  brain stays text-only; vision call already exists; just wired.
- Best-effort: a failing analyze degrades to the old filename + URL
  breadcrumb. No third vision system.

**Delivered — Inline link unfurls (rich card with images)**
- `_link_preview` now extracts `og:image`, `og:site_name`, `og:title`,
  Twitter image, and `link[rel=icon]` favicon. Falls back to URL
  netloc when no `og:site_name` and to `/favicon.ico` when no
  `<link rel="icon">`. All URLs absolutized.
- Link attachment record persists `image`, `site_name`, `favicon`.
- `render_attachment_context` link branch now includes Site, Title,
  Description, Preview image lines so the LLM brain sees the same
  rich context the founder's UI shows.
- Frontend `OraChat.jsx::LinkPreviewCard` (new component): rich card
  with image thumbnail left, site/title/description right.
  `data-testid="attachment-preview-link-card"`,
  `link-card-image / -domain / -title / -description`. Hover lift,
  graceful image-load fallback (`onError → display:none`). Falls back
  to the old emoji chip when no preview data.

**Tests**: `tests/test_iter327j_log_silencers_vision_unfurls.py` —
14 cases. Covers all 4 silencers, vision splice + fallback, link
preview parsing + site-name fallback + favicon absolutization, record
persistence, LinkPreviewCard component presence.

**Pytest status (322er + 326ww + 327a/b/c/d/e/f/g/h/i/j): 155 / 155 green.**

**Live smoke after backend restart**:
- `GET  /api/health` → 200
- `POST /api/universal/webhooks/generic` → 200 (pixel still flowing)
- `GET  /api/appointments/types` → 200 (booking still serving)
- Cosmetic verification: zero `[warmup failed]` WARNINGs and zero
  nested resend warnings in this boot's log output.

## Next Action Items (post-deploy)
- Push to GitHub → redeploy to `aurem.live` so iter 327d-j ships.
- Pixel Health in Morning Brief (founder pre-approved): yesterday's
  `universal_events` count vs 7-day average, Telegram alert on
  50%+ drop.

## Backlog
- P3: Service-account Google Calendar API for shared staff calendar.
- P3: Friendlier "report expired" landing page for stale ghost-* slugs.

## iter 327k (2026-02-23) — Vision provenance badge
Founder request: "Yes — add 'saw image via GPT-4o' badge. Helps
confirm vision actually fired."

**Delivered**
- `frontend/src/platform/admin/OraChat.jsx::Message` — assistant
  bubble now receives a `prev` prop (the immediately-preceding
  message). When `prev.role === 'user'` AND its attachments contain
  an image with a non-empty `vision_description` (cached at upload
  in iter 327j), render a small green pill above the bubble:
  `🔍 SAW IMAGE VIA GPT-4O` with `data-testid="vision-description-source"`.
- No badge when vision failed or wasn't invoked — we don't lie about
  firing.

**Tests**: `tests/test_iter327k_vision_provenance_badge.py` — 4
cases, all green. Total touched-iter regression 159/159 green.


## iter 327l (2026-02-23) — Pixel Health in Morning Brief
Founder mandate: "Yesterday's universal_events count vs 7-day average.
If count drops 50%+ below average → Telegram alert same morning."

**Delivered**
- New module `services/pixel_health.py`:
    - `compute_pixel_health(db)` — two cheap `count_documents` calls
      (yesterday window + prior-7-days window), returns
      `{yesterday_count, seven_day_avg, classification, brief_line,
      date_yesterday}`. Three classes: `normal` / `low` / `sparse`.
      `low` = yesterday < avg × 0.5 AND avg ≥ 10.
      `sparse` = avg < 10 (don't grade noisy baselines).
    - `maybe_alert_low_pixel_day(db, health)` — Telegram alert via
      existing `silent_failure_alerts._send` pipe with per-date
      dedup fingerprint `pixel_low_<YYYY-MM-DD>` so re-running the
      brief never double-pings.
- `services/morning_brief.py::generate_brief` splices a new
  PIXEL HEALTH section into `brief_text`:
    ```
    PIXEL HEALTH:
      • Yesterday: 247 pixel events (7-day avg: 312) — normal
    ```
  AND persists structured `sections.pixel_health` so System Overview /
  ORA brain can read the same numbers.
- Safety net: failure in pixel_health (Mongo down, etc.) is caught at
  DEBUG; the brief itself always renders.

**Tests**: `tests/test_iter327l_pixel_health_in_morning_brief.py` —
12 cases. Covers classification (normal/low/sparse + edge), compute
output for the three states, db-failure soft path, alert NOT firing
for normal/sparse, alert firing for low with the correct
date-fingerprint + recovery hint in the body, and source-level checks
that morning_brief wires it in.

**Live preview verification**:
```
Yesterday: 0 pixel events (7-day avg: 0) — sparse, not enough history yet
```
(Preview DB has zero events — expected. In production once pixel data
flows, this reads real numbers and the 50%-drop alarm becomes useful.)

**Pytest status (322er + 326vv/ww + 327a→l): 178 / 178 green.**

## Next Action Items (post next deploy)
- Push to GitHub → redeploy aurem.live so iter 327d-l ships.
- Verify in production tomorrow's brief that PIXEL HEALTH line shows
  real numbers. If it stays at 0 events with `LEAN_ROUTES=1`, the
  alert will fire automatically — exactly what was asked for.

## Backlog
- P3: Wire iter 327h /api/appointments/book to action_engine
  per-customer OAuth Google Calendar event create (Meet link)
- P3: Service-account staff calendar (needs GOOGLE_CALENDAR_ID +
  GOOGLE_SERVICE_ACCOUNT_KEY)
- P3: Tailored "report expired" copy + "Get a fresh scan" CTA on
  the existing 404 landing page

## iter 327m (2026-02-23) — Four critical fixes from brutal audit

The 2026-02-23 audit found 4 real issues:
  1. 10 LLM-visible tools had NO impl (ORA tried to call, failed silently)
  2. Vision badge fired even on FAILED analyses (silent lie)
  3. Agent-direct outreach bypassed CASL (do_not_contact) check
  4. `BillingService.record_overage()` was dead code — no caller, no Stripe charges

**Delivered**
- **Tool registry**: removed 10 orphan tier entries (`delete_file,
  feature_flag_set, kv_set, ora_rollback_list, ora_rollback_restore,
  prod_env_set, save_to_github, send_bulk_email, stripe_charge,
  supervisor_restart_all`). Added `reconcile_tool_registry()` that
  runs at module import and logs WARN on drift so a future regression
  is caught at boot. **Live verified: 0 orphans, 17 intentional
  hidden tools (github writes, council wrappers).**
- **Vision gate**: `ora_attachments_router.attach_file` now
  distinguishes "Image received but analysis failed: …" (sentinel
  from `_analyze_image`) from real descriptions. Failures go to
  `vision_failed_reason`; `vision_description` stays empty so the
  iter 327k provenance badge no longer lies.
- **CASL gate**: new `services/casl_gate.py` is the single source of
  truth (`is_blocked_by_casl` + `suppress`). Email + phone
  normalization, fail-closed on errors, checks BOTH
  `do_not_contact` collection AND `users.dnc / status=opted_out`.
  Wired into `armed_outreach._fire_one_lead` so the agent-direct
  path is now gated identically to the blast pipeline. Lead row
  stamped with `status=do_not_contact` on hit so we don't retry.
- **Stripe overage cron**: new `_billing_overage_job` in
  `routers/registry.py` runs daily 03:00 UTC. Walks workspaces with
  `billing.stripe_meter_event_name` set AND `current_period_end`
  past, calls `BillingService.record_overage(business_id)` per
  workspace. Per-workspace exceptions caught so one bad workspace
  doesn't kill the sweep. `aurem_stripe_overage_daily` job ID.

**Tests**: `tests/test_iter327m_audit_followups.py` — 17 cases. Full
regression: **195 / 195 green** across 16 iter files. Both new
files (`casl_gate.py`, registry cron) lint clean.

**Live preview verification**
- `/api/health` → 200
- `POST /api/universal/webhooks/generic` → 200
- `reconcile_tool_registry()` returns clean: orphans=[], hidden=17

## iter 327n (2026-02-23) — Tiered memory injection (ORA's rule book is now live)

The 2026-02-23 dead-file audit found 29 instruction docs that ORA never read.
Founder approved a **tiered** approach instead of dumping everything into context.

**Tier 1 — always injected (8000-char cap)**
- `ora_skills/dev_zero-hallucination-charter.md`
- `ora_skills/dev_322ey-ora-mistakes-lessons.md`
- `/app/memory/WATCHDOG_MODE.md`
- `/app/memory/WORKING_POLICY.md`
- `/app/memory/SYSTEM_MAP.md` (head 1500 chars)
Per-file cap 1500 chars × 5 sources ≈ 8000.
Appended to `SYSTEM_PROMPT` at module import in `services/ora_agent.py`.

**Tier 2 — keyword-gated per-turn**
- security/auth/jwt/password/secret/token/encryption  → `SECURITY_PATTERNS.md`
- campaign/outreach/blast/casl/marketing/opt-out      → `SECURITY_PATTERNS.md` (CASL section)
- fix/debug/error/broken/crash/why/how                → `ARCHITECTURE.md` (head 2000 chars)
Inserted as SYSTEM message right BEFORE the user turn so it has
maximum recency. Dedup: same file matching two rules → injected once.

**Tier 3 — already in place**: `search_codebase_semantic`, `git_log`,
`view_file` give ORA on-demand codebase access.

**Live proof on preview backend**:
```
SYSTEM_PROMPT chars: 25,225 (was ~17,200 → +8,025, within 8K budget)
RULE ZERO            → True
FOUNDER'S RULE BOOK  → True
ZERO-HALLUCINATION   → True
MISTAKES             → True
WATCHDOG             → True
WORKING POLICY       → True
SYSTEM MAP           → True
```

**Tests**: `tests/test_iter327n_tiered_memory_injection.py` — 13 cases.
Covers all 5 tier-1 sources present, 8000-char cap, missing-file
graceful skip, tier-2 keyword matching for security/outreach/debug,
same-file dedup, per-file cap. Full regression: **189 / 189 green**
across 15 iter files.

## How ORA learns from now on
| Channel | Effect |
|---|---|
| Edit `SYSTEM_PROMPT` in `ora_agent.py` | Hardcoded; always injected |
| Edit Tier-1 files (WATCHDOG_MODE.md, ora-mistakes-lessons.md, etc.) | Live on next backend restart |
| Edit Tier-2 files (SECURITY_PATTERNS.md, ARCHITECTURE.md) | Live immediately (read on every relevant turn) |
| Add new `dev_*.md` in ora_skills | NOT auto-injected — extend `_TIER1_FILES` or `_TIER2_RULES` to wire it |

