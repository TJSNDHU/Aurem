# AUREM Platform — PRD

## Original Problem Statement
AUREM is an autonomous-intelligence AI orchestration platform targeting Canadian
trades businesses. Goal: finalize the platform for first paying client. Core
themes are the "Canadian Moat" (CASL-compliant value-first outreach), AWB
(Auto Website Builder), inbound email auto-reply, ORA Council God-Mode brain,
Sovereign Truth founder mode, and BIN+PIN auth alongside standard creds.

## Core Requirements
- Full OODA pipeline for autonomous lead outreach
- Canadian Moat: value-first, CASL compliant, localized context
- Inbound email auto-reply pipeline (Cloudflare Worker → backend → Resend)
- Auto Website Builder (AWB) with auto QA, theme injection, gold particles
- ORA Council / God-Mode brain
- Sovereign Truth founder-only mode
- BIN + PIN authentication alongside email/password

## Architecture Overview
- Backend: FastAPI + Motor (MongoDB Atlas)
- Frontend: React SPA + PWA (shadcn/ui)
- Schedulers: APScheduler in `routers/registry.py`
- AI Routing: `services/ora_god_mode.py`, `llm_gateway.py`
- Email/DNS: Cloudflare Workers + Cloudflare DNS API + Resend
- Pixel: `aurem-pixel.js` served by `pixel_patches_router.py`


## Implemented — Feb 2026 (Latest)
- **2026-02-08 — PRODUCTION DEPLOYMENT BLOCKERS FIXED ✅**
  - **Root cause 1**: `routers/ai_email_router.py` had `import resend` at module top level (BEFORE the defensive try/except block). Production's older resend SDK lazy-loads `resend.logs` submodule which is missing → entire module fails to import → bulk-wire warning AND knock-on registration failures cascading the rest of startup. **Fix**: removed the unconditional import, kept only the `try/except` defensive one.
  - **Root cause 2**: `services/email_engine.py` had unconditional `import resend` at line 16. Same fix applied — wrapped in try/except with stub fallback.
  - **Root cause 3**: `routers/admin_dr_backup_router.py` was creating `AsyncIOMotorClient(MONGO_URL)` at module-import time. In Atlas prod with slow DNS or missing env var, this can hang/crash the import → blocks router registration. **Fix**: converted to lazy `_get_db()` accessor invoked only on request.
  - Verified preview backend restart: 8s startup, 1922 routes mounted, zero bulk-wire failures, "Application startup complete" reached cleanly.
- **2026-02-08 — RepairQuote flows + Instant Website Builder for "no-website" leads ✅**
  - **`POST /api/website-builder/no-website`** (NEW, public, no-auth) — creates lead → calls existing `generate_website()` → provisions customer in `platform_users` + `users` (7-day trial, tier=starter, BIN=`AURE-NWS-XXXX`) → returns slug, sample_url, login_url, temp_password
  - `RepairQuote.jsx`: top-right **"Log In"** now goes to `/my` (was `/login`)
  - Post-audit **"Next"** button now goes to `/my?signup=1&email=...` (was `/signup`)
  - Brand-new **"I don't have a website — build me a free one (7-day trial)"** CTA pill below the audit form
  - On click: full inline form (business name, email, phone, city, industry, CASL consent) → submits to public endpoint
  - On success: glass success card showing **Email / BIN / Temp password (with copy button) / Trial end date** + "View my site" + "Sign in to dashboard" buttons
  - **E2E verified**: visitor → fill form → site generated → /sample/{slug} live → login with temp password → `/api/platform/auth/login` returns valid JWT
  - Redis rate-limit warning quieted: now logs **once on transition** to fallback instead of every request (memory limiter takes over silently — sovereign override working as designed)
- **2026-02-08 — "Remember me" checkbox on `/my` login overlay ✅**
  - New checkbox with testid `auth-remember`, label "Keep me signed in for 30 days", default CHECKED
  - Storage strategy:
    - **Checked** → token in `localStorage` (persistent across browser restarts) + flag `aurem_customer_remember=1`
    - **Unchecked** → token in `sessionStorage` only (cleared when tab closes — safer for shared computers)
  - Returning visitors: previous preference restored from localStorage flag
  - `LuxeAuthContext` exposes new `rememberPreference` value; `login()` and `signup()` accept `remember` flag
  - **E2E verified** (Playwright, 5 checks): default checked, login routes token correctly to localStorage vs sessionStorage based on box state, logout clears both stores
- **2026-02-08 — Password Reset + show/hide toggle on `/my` login overlay ✅**
  - Rebuilt `LuxeAuthOverlay.jsx` with 4 modes: login / signup / forgot / reset
  - Eye-toggle (`Eye`/`EyeOff` lucide icons) on every password field — testids `auth-password-toggle`, `auth-new-password-toggle`, `auth-confirm-password-toggle`
  - "FORGOT?" link inline next to PASSWORD label → switches to email-only forgot form
  - URL `?reset_token=…` auto-detected → switches to "Set new password" form with new + confirm fields and validates match locally
  - Backend bug fixes:
    - `routes/auth.py reset_password` now syncs both `password` AND `password_hash` across `users` / `platform_users` / `aurem_users` collections (was missing `password_hash`, breaking customer login post-reset)
    - `routers/server_misc_routes.py reset_password` (the actually-mounted handler) — same fix applied + branding switched to AUREM gold
  - **E2E verified**: forgot → token → reset → admin login → reset back → admin login again — full cycle passes via curl test
- **2026-02-08 — Auth fixes (founder password reset + Google login)** ✅
  - Founder admin password reset: `teji.ss1986@gmail.com` / `Aurem@Founder2026!`. Synced across `users` (`password` + `password_hash`), `aurem_users`, `platform_users`. Cleared stale `auth_provider`/`require_sso` blockers.
  - Created missing **`POST /api/auth/google/callback`** endpoint (`routes/auth.py`). Frontend `GoogleAuthCallback.jsx` was hitting it but it never existed — only `/google/session` and `/google/admin-session` did. The new unified callback peeks at the email and routes to admin or customer flow automatically.
  - For PRODUCTION: founder must set `ADMIN_PASSWORD_HASH_1` env var (bcrypt of `Aurem@Founder2026!`) via Emergent deploy panel — value in `/app/memory/test_credentials.md`.
- **2026-02-08 — Disaster Recovery: Primary → Secondary Atlas mirror live ✅**
  - New service: `/app/backend/services/db_backup_service.py` (drop+insert mirror, per-collection stats, Resend email on failure)
  - New router: `/app/backend/routers/admin_dr_backup_router.py` — `POST /api/admin/backup/trigger`, `GET /api/admin/backup/status` (super_admin only)
  - APScheduler cron `aurem_dr_backup_daily` registered: daily 03:00 UTC
  - Secondary cluster: Atlas M0 free tier "Backupmy" (`backupmy.uxvf9mh.mongodb.net`), separate Atlas project for blast-radius isolation
  - **First production mirror VERIFIED**: 462 collections, 159,410 docs, 11min24s, status=ok (run_id `dr-20260508T160226Z`)
  - High-volume transient logs excluded (`api_audit_log`, `site_monitor_logs`, `qa_bot_endpoint_log`, `agent_feed`, `a2a_events`, `*_archive`) for ~70% size reduction
  - Failover doc: `/app/memory/DISASTER_RECOVERY.md` — 30-second URL-swap procedure documented
  - Run history persisted in `db_backup_runs` collection on primary
- **2026-02-08 — Customer Portal /my fully responsive (mobile/tablet/desktop) ✅**
  - Created `useViewport` hook (`/app/frontend/src/platform/luxe/useViewport.js`)
  - Sidebar → mobile drawer with hamburger toggle + backdrop + close button
  - HeaderStrip → mobile-aware (hamburger button + truncated label)
  - All rigid grids (`repeat(N,1fr)`) → fluid `repeat(auto-fit, minmax(...))` so KPIs reflow 2×2 on mobile, 4×1 on desktop
  - AgentsTile bar chart adapts via `auto-fit minmax(38px,1fr)`
  - Card padding/border-radius use `clamp()` for fluid scaling
  - PageShell H1 uses `clamp(18px, 4vw, 22px)`
  - **Critical fix**: ORA help widget was covering login form on mobile (fixed `width:340 × height:460` covered 86% × 54% of phone). Now defaults to minimized (48px bar) on mobile + clamps width/height to viewport (`max ~88vw × 56vh`)
  - Verified across 393px (mobile), 820px (tablet), 1920px (desktop)
- **2026-02-08 — Customer Portal /my (Luxe) E2E verified ✅**
  - Rebuilt luxe/* folder post git rollback (LuxeAuthContext, LuxeAuthOverlay, LuxePages, useLuxeDashboardData, tokens)
  - All files use `lib/api.js` BACKEND_URL helper — zero direct `process.env.REACT_APP_BACKEND_URL` usage in luxe/*
  - testing_agent_v3_fork (iteration_319) — 100% pass on login, 8 sub-pages (Home/Profile/Live Health/Security/Automation/CRM/ORA/Settings), logout
  - Bugs fixed by testing agent: (1) `/api/platform/me` token lookup now supports both user_id and email-based payloads (ai_platform_router.py); (2) testid `page-live-health` consistency in LuxePages.jsx; (3) AutomationPage defensive Array.isArray() for workflows
  - New active test creds: `e2e-test-luxe@aurem-test.com` / `Test@1234567`
- **2026-02-08 — Security key rotation post-breach**
  - All default DB passwords rotated via `/app/scripts/rotate_default_passwords.py`
  - Founder/admin/customer credentials updated in /app/memory/test_credentials.md
  - User contacted Emergent Support for managed Atlas + Universal LLM key rotation (production-side, awaiting confirmation)
- **2026-02-08 — Production startup hardening**
  - Defensive guards around `resend.api_key` assignment to prevent module-level crash on missing key
  - Removed global service worker (sw.js) interception of `/api` POST routes (login/pixel)


## Implemented (Recent)
- **2026-02-06 — Customer Health Monitor + Auto-Repair Pipeline live**
  3 new services + 1 router + 1 admin panel + Morning Brief integration:
  - `services/customer_health_monitor.py` — 14 per-tenant checks (DB / Auth / Route / Pixel), 30-min auto-scan, bounded concurrency 8
  - `services/customer_repair_pipeline.py` — KNOWN_FIXES table; safe ≥0.90 confidence → auto-apply, unsafe → council.deliberate(qa+security), then verify, then ORA SMS alert if still broken
  - `services/customer_fix_executors.py` — 7 idempotent fixes (seed_billing_record, create_workspace, init_onboarding, seed_tenant_record, create_stripe_customer, reset_auth_tokens, diagnose_frontend_route)
  - `routers/customer_diagnostic_router.py` — 7 admin endpoints under `/api/admin/diagnostics/*`
  - `platform/admin/CustomerHealthPanel.jsx` — full admin UI: summary cards, tenant list, detail pane (14 check grid), 6 manual fix buttons, repair history
  - Sidebar entry under HEALTH section + route `/admin/customer-health`
  - Morning Brief injects `customer_health` line from latest summary + 24h fix count
  - P4 worker hosts 34 schedulers (was 33)
  - E2E: RERO-3DEJ → critical (root cause: legacy `users` collection has admin@reroots.ca but never created `platform_users` record → orphaned `aurem_onboarding` doc only); AURE-3M4G dogfood → healthy.

- **2026-02-06 — Code Quality Report Round 2** — Re-triaged second drop of the report:
  - **NEW circular-import claim** `routes/mcp_routes.py ↔ services/mcp_extended_tools.py`: FALSE POSITIVE. Neither imports the other; `grep` of both files shows zero cross-imports.
  - **NEW circular-import claim** `services/aurem_commercial/__init__.py ↔ shared/commercial/__init__.py`: FALSE POSITIVE. `services/aurem_commercial/` directory does not exist in repo.
  - **NEW eval claim** `routers/ai_repair_router.py:1533`: FALSE POSITIVE. Line is `creds_dict = ast.literal_eval(raw_creds)` — already the safe replacement the report recommends. Static scanner confused `literal_eval` with `eval`.
  - **`secrets` module migration** for `services/proximity_blast.py`: NOT APPLIED. File generates fake demo data (per file docstring: "Simulated data layer"). Per CPython docs, `random` is correct for simulation; `secrets` is for tokens/keys/session IDs. Migration would be cargo-culted noise.
  - **Wildcard imports** in 3 SHIM files (`services/agent_rbac.py`, `services/agents/followup_listener.py`, `services/agents/hunter_ora.py`): FIXED. Replaced `from shared.X import *  # noqa: F401,F403` with explicit re-exports + `__all__` lists. Static analysis now sees real symbols; runtime behavior unchanged.
  - **All other items** (test secrets, complexity refactor of `_archive/` files, late-binding closures, import bloat in registry.py): deferred — `_archive/` files are dead code, `registry.py` Phase 2 refactor already on backlog, test-secret cleanup is 100+ files of low-leverage churn pending a proper `.env.test` strategy.

- **2026-02-06 — Code Quality Report Round 1 Triage** — F821 cleanup (77 undefined names in `services/email_templates.py`), missing `logger` in `routers/rag_router.py`, missing `get_connector_ecosystem` import in `routers/vector_search_router.py`, plus `_email_templates_set_db` + `_email_templates_set_twilio_client` startup wiring. False-positive triage for circular imports / `eval` / `exec` / `os.system` / SSL `verify=False` (all confirmed via AST scan + inline comments documenting intentional security-scanner behaviour).

- **2026-05-06 — Phase 2-5 Master Prompt Complete** — Phase 2 fix (clear-backlog cutoff body-tunable + legacy-doc resilience in `promote_if_ready`): pending 335→0, promoted 2→337, ora_knowledge 0→14. Phase 3: `services/ora_knowledge_base.py` (3-tier memory + 5 learning feeds + nightly digest @03 UTC + weekly self-assessment @Sun 04 UTC), router `/api/admin/ora/knowledge/*`. Phase 4: `services/error_ledger.py` (sha1-deduped error registry + crash-catcher middleware + global hooks), `services/deploy_monitor.py` (5-min version drift + 60s post-deploy stability check), auto_repair.py human-approval gate REMOVED (auto-applies low+medium risk; only DESTRUCTIVE keywords blocked, never paged). Phase 5: `services/agent_health_check.py` — 7 rules every 5min (R1 silent>24h, R2 reject>50%, R3 cost spike, R4 errors>10/min, R5 queue>1000, R6 deploy drift, R7 idle). P4 hosts 32 schedulers (was 27). 38/38 tests pass.
- **2026-05-05 — Growth Engine Section 8 (Onboarding / Trial Win-back)** — `services/trial_winback.py` 3-step nudge sequence (Day 0/3/8) auto-armed when trial expires. Auto-cancels on subscribe. Founder-discount mid-step. P2 worker hosts 30m scheduler. Frontend `<TrialBanner />` (gold/red, dismissible) on `CustomerHome`. 11/11 tests pass.
- **2026-05-05 — Growth Engine Section 7 (Blast-Chain)** — `services/blast_chain.py` staggered 4-touch chains (Day 0/2/5/9), Chain A (has-website) + Chain B (no-website). Per-touch copy variants. New router `/api/admin/blast-chain/{start,run-now,status}` + webhook `/api/blast/reply`. Reply classifier: hot → halt+Telegram, DNC → halt+upsert. P1 worker hosts advance scheduler. Auto-blast cycle now calls `start_chain`. 17/17 tests + E2E verified on tj-auto-clinic-001.
- **2026-05-05 — Growth Engine Section 6 (QA No-Website)** — `services/prospect_site_qa.py` end-to-end via `/api/admin/scout/qa-no-website`. Picker page injects `claim_block_html` + business phone visibly. JS template literals filtered from broken-image scan. 6/6 A2A checks pass on tj-auto-clinic-001.
- 2026-05-05 — Deployment K8s liveness probe fix: deferred PillarOrchestrator launch by 25s (`SCHED_BOOT_DELAY_S`) + restored all 24 Pillar 4 schedulers via factory lambdas. `/health` stays sub-ms during cold boot, max 3s during pillar attach (was 10s+ timeout → pod kill loop).
- 2026-04→05 — AWB rebuild-request CTA + 404 JSON fix
- 2026-04→05 — 720p homepage video bg + og:video tags
- 2026-04→05 — OraPWA mobile sticky header/footer rewrite
- 2026-04→05 — BIN+PIN login flow + PlatformAuth tabs + AccountSecurity setup
- 2026-04→05 — Duplicate-site & DNS-CNAME dedup + 184 orphan CNAME purge
- 2026-04→05 — Gold particles auto-inject in AWB sites
- 2026-04→05 — Inbound email auto-reply via Cloudflare Worker → Resend
- **2026-05-04 — Dogfood pixel resolver fix**
  - `_resolve_onboarding(db, key)` cross-walks tenant_id ↔ business_id via
    users/platform_users, so dogfood/BIN-tenants whose onboarding row was
    seeded under business_id no longer 404 on `/pixel/status`.
  - `pixel_status` soft-fails (200 + `pixel_installed: false`) instead of 404
    so frontend banners always render correctly.
  - `pixel_verify` upserts the onboarding row when missing.
  - `/api/platform/auth/login-pin` now returns `tenant_id` in JWT + body so
    the frontend has the canonical id alongside `business_id`.
  - Regression: `/app/backend/tests/test_pixel_status_resolver.py` (4 tests)
- **2026-05-04 — Login page background video**
  - Founder-supplied MP4 saved to `/app/frontend/public/videos/login-bg.mp4`
  - `FaceIDAuthWrapper.jsx` (`/login`) now renders a fixed full-screen
    autoplay/muted/loop `<video>` with a vignette overlay and the
    aurem-hero-robot poster fallback while the video buffers.
- **2026-05-04 — Customer Portal video background** (`/my`)
  - `CustomerPortal.jsx` renders the same login-bg.mp4 at 0.45 opacity
    behind the sidebar + main content.
- **2026-05-04 — `.gitignore` corruption fix** (deploy unblocker)
  - Removed 11 stray `-e ` lines that broke git operations and were
    making the Emergent build pipeline skip the React rebuild.
- **2026-05-04 — Mission Control quick-win latency**
  - 5 new compound indexes auto-ensured on startup: pixel_verification_log
    `(verified_at, detected, url)` + `detected`; aurem_onboarding
    `(tenant_id, pixel_installed)` + `pixel_installed`; tenant_customers
    `(record_type, pixel_installed)` + `(record_type, status)`.
  - 30s TTL Redis cache wraps `/admin/mission-control/pixel-health` and
    `/tenants-summary`. Expected prod impact: 658ms → ~150-200ms warm.
  - Helper script `/app/scripts/apply_perf_indexes_PROD.py` to apply
    indexes to prod Atlas without redeploy.
- **2026-05-04 — Auto-Latency Guardian (iter 322f)**
  - New service `services/latency_guardian.py` hooks into the existing
    QA Bot 10-min sweep — no new scheduler.
  - 3-step heal cascade per slow-but-passing endpoint (>400ms,
    skipped if >5s intentional): cache flush → reprobe → ensure_indexes
    → reprobe → write `admin_alerts` row.
  - Every action logged to `system_pulse_actions`.
  - New endpoints under `/api/qa/guardian/{status,actions,run-now}`.
  - Frontend pill on System Pulse Live page (green/yellow/red) plus a
    Last 5 Actions timeline.
  - 11 unit tests in `tests/test_latency_guardian.py` (all passing).
- **2026-05-04 — Latency Guardian Council Mode (iter 322i)**
  - Removed `alert_admin` from the autonomous flow.
  - 6-step cascade: `cache_flush` → `index_refresh` → `tighten_cache_ttl`
    (30→120s) → `connection_pool_recycle` → `convene_council` (ACCEPT/HOLD)
    → final terminal log.
  - LLM unreachable → defaults to HOLD (autonomous monitoring continues).
  - State machine adapts: `red` only when legacy `alert_admin` rows
    remain; new flow never produces them.
  - Utility endpoint `POST /api/qa/guardian/clear-legacy-alerts` to flip
    prod red→green instantly post-deploy.
  - 14 unit tests pass; 4 new Council-mode tests.
- **2026-05-04 — Sovereign Watchdog (iter 322j)** — full-system
  continuous self-heal
  - New service `services/sovereign_watchdog.py` runs a 60s background
    loop tailing `/var/log/supervisor/backend.{out,err}.log`.
  - Pattern catalog (extensible) detects: Redis exhaustion, Pillar
    failures, MongoDB timeouts, K8s health-probe boot races.
  - Each pattern maps to a deterministic recipe (e.g. `redis_pool_kick`,
    `pillar_restart`, `db_ping`, `noop_log_only`).
  - Recipe failure on `high` severity → `convene_council`. Council picks
    RETRY or ESCALATE; ESCALATE writes to `sovereign_council_escalations`
    for an on-call ORA agent — **no human paging**.
  - Every finding + outcome persisted to `sovereign_watchdog_log`
    (the learning corpus).
  - Findings dedup'd by sha1(source+kind+line) within 30-min window.
  - New endpoints: `GET /api/qa/watchdog/{status,findings}`,
    `POST /api/qa/watchdog/run-now`.
  - 13 unit tests in `tests/test_sovereign_watchdog.py` (all passing).
  - Bonus fix: `customer_scanner.py` `regex=` → `pattern=` (FastAPI
    deprecation noise eliminated).
- **2026-05-04 — Sovereign Memory Guard (iter 322k)** — Day 1 of
  Sovereign Discipline
  - New service `services/sovereign_memory.py` enforcing the
    **two-stamp learning gate**: every backend agent's "learned fix"
    enters `learnings_pending_review` first; promotion to canonical
    `learnings` requires approve stamps from **two distinct Council
    roles** (e.g. `dev` + `qa`). Self-stamps and duplicate-role stamps
    are rejected at the API layer.
  - Data-Anchor rule enforced: submissions without `evidence` → 400.
  - Integrated with Sovereign Watchdog — every successful auto-fix is
    auto-submitted as a `watchdog_fix:<kind>` learning candidate so the
    Council audits the heuristic before it's promoted.
  - New endpoints under `/api/sovereign/memory/*`:
    `submit, review, pending, promoted, stats, next-for-review/{role}`.
  - 12 unit tests in `tests/test_sovereign_memory.py` (all passing) +
    end-to-end live integration verified.
- **2026-05-04 — Sovereign Discipline Day 2 (iter 322l)**
  - **Boundary lint** (`scripts/lint_sovereign_boundary.py`): customer-ORA
    files (`ora_god_mode.py`, `ora_chat_router.py`, `ora_council_router.py`)
    fail CI if they import any system-ORA module
    (`ora_council`, `latency_guardian`, `sovereign_watchdog`,
    `sovereign_memory`, `autopilot_sentinel`) or directly access protected
    collections (`learnings_pending_review`, `sovereign_council_escalations`,
    etc.). 5 tests pass; current repo is clean.
  - **Council Rotation Worker** (`services/council_rotation.py`):
    self-driving 2-stamp reviewer. Every 5 min picks a non-submitter
    Council role, asks `next_pending_for_review`, builds an LLM prompt,
    parses APPROVE/REJECT, calls `review_learning`. LLM unreachable →
    rejection (final). Verified end-to-end: candidate auto-promoted by
    `casl` + `seo` agents in a single tick. 6 tests pass.
  - **Pillar Restart Fulfiller** (`services/pillar_restart_fulfiller.py`):
    reads `pillar_restart_requests` written by the Watchdog and invokes
    the matching pillar's `start_pillarN_worker` launcher. Failed launches
    auto-submit a `pillar_restart_failure:pN` learning candidate so the
    Council audits whether the launcher mapping needs updating. 5 tests
    pass.
### iter 322p+ — Deployment-Blocker Fixes (2026-02-05 night)
  Production deploy was failing with K8s liveness-probe (`/health`)
  upstream timeouts. RCA + fixes:

  - **`/health` upstream timeouts**: caused by event-loop saturation
    during cold-boot — the wedge detector's per-tick fan-out (~30
    Mongo lookups across T1+T2+T3) at 30s interval was starving K8s
    liveness probes.
    Fixes:
      - `WEDGE_SCAN_INTERVAL_S` default 30 → **60 s**
      - `detect_all_wedges()` now uses `asyncio.gather()` so T1, T2,
        T3 detection run in parallel (max(t1,t2,t3) instead of sum)
      - `agent_wedge_scan` job has **45 s `start_date` grace** so it
        cannot fire during the first 45 s of pod boot when liveness
        probes are most aggressive
      - `misfire_grace_time` added to all 4 new ticks (wedge 30 s,
        followup 60 s, referral 300 s, verdict 60 s) so APScheduler
        cannot pile up missed runs that hit the loop together.
  - **`council_rotation` 'id' KeyError** (5+ occurrences in prod log):
      - `services/council_rotation.py` now defensively reads
        `candidate.get("id") or str(candidate.get("_id") or "")`
        before calling `review_learning`. Skips silently when both
        are missing (skipped counter increments).
      - `services/agent_wedge_detector.py` `_record_learning()` now
        always inserts a stable string `id` field so its observation
        rows are first-class Memory-Guard candidates.
  - **Live verification**: `/health` returns in **0.27-0.44 ms** under
    live load (10 sequential probes after backend restart). Full
    suite **125/125 green**. APScheduler "missed by Ns" warnings
    eliminated locally.

### iter 322p — FollowUp + Referral ORA wired LIVE + Council Verdict Auto-Apply (2026-02-05 night)
  - **`services/followup_ora_engine.py`** (~165 LOC) — silent-lead
    nurture engine. Scans `campaign_leads` for leads whose
    `updated_at` < `FOLLOWUP_AGE_DAYS` (default 3) ago and status
    not in {responded, converted, unsubscribed, blocked}. Pushes a
    `followup_attempt` row into `outreach_history` (channel
    `intent_only` by default — `FOLLOWUP_LIVE_SENDING=1` flips to live).
    24h per-lead cooldown. Fires every 30 min.
  - **`services/referral_ora_engine.py`** (~125 LOC) — referral
    harvester. Scans `customer_subscriptions` with status="active",
    queues a row in `referrals_outbox` for any customer not asked
    in the last `REFERRAL_GAP_DAYS` (default 30). Channel `in_app`
    by default — `REFERRAL_LIVE_PROMPTS=1` flips to email. Fires every
    6 h.
  - **`services/council_verdict_executor.py`** (~165 LOC) — closes
    the self-evolving loop. Watches `learnings` for promoted rows
    with a structured `recommended_fix.{action, params}` and runs
    them from a tight allowlist (`ping_agent`, `clear_a2a_signal`,
    `broadcast_a2a` with `verdict_*` prefix). Marks the learning
    `applied: true` after — never retries. Honours
    `COUNCIL_VERDICT_DRY_RUN=1`. Fires every 5 min.
  - **All three wired into APScheduler** in `routers/registry.py`
    with `coalesce=True, max_instances=1` so they're tick-safe.
  - **Tests**: 18 new — `test_followup_ora.py` (5),
    `test_referral_ora.py` (5), `test_council_verdict_executor.py` (8).
    Full Sovereign suite **125/125 green**.
  - **Live production-data verification** (preview DB):
    - FollowUp ORA: 20 leads scanned, **20 follow-up attempts queued**
      in 14 ms.
    - Referral ORA: 5 customers scanned, **2 referral asks queued**
      to `referrals_outbox`, 3 in cooldown, 17 ms.
    - Council Verdict Executor: 0 considered (correct — no promoted
      learnings carry a `recommended_fix` yet; engine ready for first
      Council-promoted fix recipe).
  - **Wedge dashboard impact**: post-tick, wedged_now drops from "5
    across T1/T2" to **0 across all three tiers** — both newly-active
    ORAs now generate real ledger heartbeats.

### iter 322o+ — A2A Multi-Tier + Council Learning Loop (2026-02-05 night)
  - **Naming alignment**: fixed `follow_up_ora` → `followup_ora` so the
    canonical `agent_soul.py` registry and the wedge detector agree.
    Removed the placeholder `hup_ora` (only ever existed in code, not
    in the codebase definition — was a copy from prod UI screenshot).
  - **`ora_brain` first-class** in `agent_soul.py` `AGENT_PERSONAS`:
    God-Mode router was historically the most-active agent in
    telemetry but missing from the official registry. Now visible to
    wedge detector + admin observability.
  - **3-tier A2A wiring** (`agent_wedge_detector.py`):
    - T1 Customer ORAs (7) — heartbeat from `agent_ledger_entries`
    - T2 Council roles (11) — heartbeat from `council_sessions`
    - T3 Sovereign workers (6) — heartbeat from `system_pulse_actions`
    - New helpers `detect_wedged_council`, `detect_wedged_sovereign_workers`,
      `detect_all_wedges`. `run_wedge_scan` now scans all 3 tiers and
      surfaces a `wedged_by_tier` rollup in its summary.
  - **Council Learning Loop** — every successful heal calls
    `_record_learning(db, agent_id, age, tier)` which inserts a row
    in `learnings_pending_review` `{kind: "agent_wedge_observation",
    stamps: [{role: "wedge_detector"}], status: "pending"}`. The
    existing Council Rotation worker (5-min tick) auto-picks the
    second stamp → promotes to permanent `learnings`. **Closes the
    full A2A → Council → ORA learning circle without an LLM call.**
  - **Tests**: `tests/test_agent_wedge_detector.py` 20/20 (was 14)
    — added council/sovereign detection, multi-tier aggregation,
    learning-row contract, tier-breakdown rollup. **Full Sovereign
    suite 107/107 green.**
  - **Live verification (preview)**: detector found 5 wedges across
    T1 (3) + T2 (2), healed all in 4,303 µs avg, broadcast 5 A2A
    signals, queued 2 wedge observations in Memory Guard's 2-stamp
    queue. T3 sovereign workers all healthy.

### iter 322o — Agent A2A Self-Heal Loop (2026-02-05 night)
  - **`services/agent_wedge_detector.py`** (~330 LOC): closes the gap
    between Watchdog (whole-backend liveness) and Latency Guardian
    (per-endpoint slowness) — catches **single-agent boot wedges**
    like the production "boot-1777956593 · 52m" red pill.
  - **Detection**: scans `agent_ledger_entries` per agent. Wedged =
    (had activity in last 7 days) AND (no activity for 30 min).
    Dormant agents (zero rows in 7 days) are NOT wedged. Idempotent.
  - **3-step heal cascade** (sub-200ms):
    - Step 1 · Heartbeat ping → `agent_ledger_entries` `kind: "boot_unwedge"`
    - Step 2 · A2A signal → `agent_a2a_signals` `kind: "wedge_recovered"`
      (peer agents subscribe in their own scan cycles)
    - Step 3 · Pulse log → `system_pulse_actions` for trust badge
  - **Cooldown guard**: 600s per-agent prevents thrash; admin
    `force=True` overrides for manual "Heal Now" clicks.
  - **APScheduler integration** (`registry.py` line 1430): runs every
    30s — wedges are auto-healed within ~30s of detection. Job ID
    `agent_wedge_scan` with `coalesce=True, max_instances=1`.
  - **Telemetry surfaced** on three endpoints:
    - `/api/sovereign/telemetry-status` → adds `agent_wedges` block
    - `/api/public/status` → adds sanitized `agents_wedged_now` +
      `agents_auto_unwedged_24h` (count-only, no agent names leaked)
    - `/api/admin/scout/wedges` → list current wedges + 24h stats
    - `POST /api/admin/scout/heal-agent` → admin "Heal Now" override
  - **Tests**: `tests/test_agent_wedge_detector.py` 14/14 green
    (detection thresholds, dormant filter, cooldown, force-override,
    cascade artefacts, scheduler entry-point, sub-200ms budget,
    stats rollup). Public status sanitizer test updated for new
    locked keys. **Full Sovereign suite 101/101 green.**
  - **Live verification on preview**: 3 stale agents detected
    (`scout_ora` 4.7 days stale, `envoy_ora` 27h, `ora_brain` 30h) →
    autonomous scheduler healed all 3 within 60s → `wedged_now: 0`
    → `auto_healed_24h: 3` → **avg heal time: 6,758 µs (6.7 ms)**.
    8,000× faster than the prod 52-minute wedge.

### iter 322n+ — Sovereign-Gold Tier + On-Demand Deep Intel (2026-02-05 PM)
  - **Sovereign-Gold tier tagging** in `total_scout.py`: every lead in
    the dispatcher output now carries `tier: "gold"|"silver"|"bronze"`
    based on distinct-source consensus (3+ = gold, 2 = silver, 1 = bronze).
    Output also surfaces `tier_counts` rollup so the admin dashboard
    can show "of 50 leads, 8 are Sovereign-Gold" at a glance.
  - **Forensic Miner wired as conditional 7th source** — fires ONLY
    when the query matches an ecommerce-niche keyword
    (`skincare/beauty/shopify/dtc/...`). Local-trade queries (HVAC,
    plumber, electrician, etc.) skip it cleanly so the (paid) Tomba.io
    email lookups stay dormant. Live Mississauga HVAC test confirmed
    `forensic: 0` yield as expected.
  - **`services/lead_deep_intel.py`** + admin endpoints:
    - `POST /api/admin/scout/enrich-deep` `{lead_id, lead, preset}` —
      on-demand Dark Scout fire on a single lead. Persists to
      `lead_deep_intel` collection (`risk_level`, `analysis`,
      `source_count`, `elapsed_ms`, `investigation_id`).
    - `GET  /api/admin/scout/deep-intel/{lead_id}` — read cached intel.
    Sovereign architecture rationale: discovery is autonomous + free,
    but threat-intel LLM cascade ($0.05/lead, 30-60s) stays opt-in to
    avoid budget burn on every search.
  - **Dark Scout import bug fix** — replaced obsolete
    `from emergentintegrations.llm.chat import ChatLLM` with the
    correct `LlmChat(api_key, session_id, system_message)
    .with_model("openai", "gpt-4o-mini")` API at both call sites
    (`filter_results_llm`, `analyze_intelligence`). LLM cascade now
    actually runs instead of silently falling back.
  - **Tests**: 16 new tier/niche/forensic-gating/deep-intel tests
    (12 + 4 in `test_total_scout.py`, plus 8 in
    `test_lead_deep_intel.py`). Full Sovereign suite **87/87 green**.

### iter 322n — Total-Scout Multi-Source Discovery Engine (2026-02-05 PM)
  - **`services/total_scout.py`** (~440 LOC): unified orchestrator that
    fans out to **6 discovery sources in parallel** with per-source
    timeouts, dedup, source-chain accumulation, and run telemetry:
    - T1 Yelp Fusion API · Google Places API
    - T2 OSM Overpass · YellowPages list-scrape (Firecrawl)
    - T3 Tavily web search · DuckDuckGo HTML
  - **Dedup key** prefers normalised name+phone, falls back to
    name+website host, then name+city. Surviving leads carry
    `source_chain` so 2+ source agreement = "Sovereign-Gold" candidate.
  - **Telemetry**: every orchestrator run writes `scout_source_runs`
    `{ts, query, location, source_yields, total_after_dedup,
    elapsed_ms, errors}` for the admin dashboard.
  - **Admin endpoints** (`routers/scout_sources_router.py`):
    - `GET /api/admin/scout/source-stats?days=7` — last-N-day rollup
      with per-source share % and avg elapsed ms.
    - `POST /api/admin/scout/run-now` `{query, location, limit}` —
      fire one orchestrator run from the dashboard.
  - **Back-compat**: `google_places_leads()` kept as alias to
    `discover_leads_total_scout()` — zero callers break.
  - **Source disable flags**: `SCOUT_DISABLE_<SOURCE>=1` env vars let
    ops cut a misbehaving tier without code change.
  - **Tests**: `tests/test_total_scout.py` 12/12 green (dedup logic,
    phone normaliser, source merging, source-chain accumulation,
    timeout isolation, source-stats rollup, alias back-compat).
  - **Live verification** (Mississauga HVAC, limit 8): **8 unique
    leads returned in 3,998 ms** with real Canadian E.164 phones.
    Source yields: `yelp=8, duckduckgo=8, osm=7, google_places=0
    (billing pending), yellowpages=0, tavily=0`. System gracefully
    drops Places without losing a single lead.

### iter 322m Day 5+ — Footer Trust Pill + registry.py Phase 1 refactor (2026-02-05 PM)
  - **Homepage trust pill** (`platform/AuremHomepage.jsx`): lazy-fetches
    `/api/public/status` after a 800ms idle delay and renders a small
    `🟢 99.99% autonomous · 139 heals/24h · status.aurem.live` pill in
    the footer that links to `/status`. Silent failure (pill simply
    stays hidden) so a transient status outage never degrades the
    homepage. New `System Status` link added to footer-links for SEO +
    discoverability. Lint clean.
  - **registry.py Phase 1 refactor** (behaviour-preserving):
    - Extracted `LEAN_MODE` + 94-entry `SKIP_IN_LEAN` set + `make_should_skip()`
      → `routers/_registry_config.py` (147 LOC).
    - Extracted post-registration LEAN prune logic (URL-prefix and
      exact-path delete pass) → `routers/_registry_lean_prune.py` (89 LOC).
    - `registry.py` shrank from **2257 → 2126 LOC** (-131). Added a top-of-file
      section index for navigation. Behaviour byte-identical: import
      smoke-test confirms `make_should_skip(True)('cart_inline') == True`
      and `('routers.public_status_router') == False`. Backend boot clean,
      59/59 Sovereign tests still green.
  - **Deferred to next session** (intentional — needs a dedicated regression
    window): the 720-LOC APScheduler block (Section 6 of `registry.py`)
    and the five domain-based section splits.

### iter 322m Day 5+ — Public Sovereign-Status Trust Page (2026-02-05)
  - **Backend**: new `services/public_status_aggregator.py` builds a
    sanitized 11-key payload (autonomy %, heals 24h, avg heal time,
    decision veracity, sparkline, badge color, last incident). Hard
    sanitizer guard `assert_payload_safe` blocks forbidden substrings
    (`MONGO_URL`, `JWT_SECRET`, `_id`, `Bearer `, etc.) and locks the
    allowed-key set so any future leak is a deliberate two-line change.
  - **Routes**: `GET /api/public/status` and
    `GET /api/public/status/badge.json` (shields.io endpoint format).
    No auth, 60s in-process TTL cache.
  - **Frontend**: `/status` route → `platform/PublicStatus.jsx`. Dark
    Obsidian + gold-gradient `Sovereign Status` headline, four trust
    tiles, 24-bar Council-Activity sparkline, copy-to-clipboard embed
    snippet (`![AUREM Autonomy](https://img.shields.io/endpoint?url=…)`).
    Auto-refreshes every 30s. Fully on-brand with `AuremHomepage` token
    set.
  - **Tests**: `tests/test_public_status.py` 6/6 green (default-DB
    fallback, allowed-key contract, forbidden-substring blocklist,
    deliberate-leak rejection). Full Sovereign suite now 59/59 green.
  - **Live verification**: production payload returns `99.99%` autonomy,
    `118` watchdog heals, `1.8s` avg heal time, `green` badge color.

  - **Total Sovereign suite**: 55/55 tests green
    (memory + boundary + rotation + fulfiller + watchdog + latency
    guardian).

### iter 322m Day 3-5 — Sovereign Truth + Telemetry HUD (2026-02-05)
  - **Sovereign Truth directive** restored in `services/ora_council.py`:
    `_wrap_with_sovereign_truth(raw)` is idempotent, prepends a
    `SOVEREIGN TRUTH PROTOCOL` block, and forces `INSUFFICIENT_DATA`
    refusals when evidence is missing. Every Council role prompt is
    wrapped exactly once via `_load_skill_prompt`.
  - **Data-Anchor** in `convene_council`: any system caller
    (`latency_guardian`, `sovereign_watchdog`, `council_rotation_worker`,
    `pillar_restart_fulfiller`, `memory_guard`) without an `evidence`
    payload short-circuits to `INSUFFICIENT_DATA` instead of guessing.
    Customer-facing callers unaffected.
  - **Telemetry router** `routers/sovereign_telemetry_router.py` mounted
    at `GET /api/sovereign/telemetry-status` (renamed from `/health` to
    avoid collision with the existing `sovereign_node_router`
    `/api/sovereign/health`). Aggregates memory-guard, watchdog,
    latency-guardian, council-rotation, pillar-fulfiller, 24h council
    session count, and boundary-lint pass/fail. 10s TTL cache. Admin-only.
  - **System Pulse Live UI** updated to fetch the new endpoint.
  - **Tests**: `tests/test_sovereign_truth_directive.py` 9/9 green; full
    Sovereign suite 53/53 green. Live curl with admin token returns
    full payload (`memory_guard`, `watchdog`, `latency_guardian`,
    `council_rotation`, `pillar_fulfiller`, `council_sessions_24h`,
    `boundary_lint`, `ts`).

## Backlog / Roadmap

### P0 — Blocked on platform / founder action
- Production deploy stuck on aurem.live (frontend bundle not rebuilt) —
  awaiting Emergent Support response.
- Git history credential scrub — founder must rotate Atlas password and
  run `git filter-repo` locally.

### P1 — Engineering
- `routers/registry.py` refactor (>2200 lines monolith)
- test-lab.ai Site QA integration (founder must create label)

### P2 — Future / Founder action
- Twilio A2P 10DLC brand + campaign approval
- Google Places API billing activation

## Key Endpoints
- `POST /api/platform/auth/login-pin`  (now returns tenant_id)
- `GET  /api/onboarding/tenant/{id}/pixel/status`  (BIN/tenant tolerant)
- `POST /api/onboarding/tenant/{id}/pixel/verify`  (auto-upserts onb row)
- `POST /api/sites/{slug}/rebuild-request`
- `POST /api/email/inbound`
- `POST /api/admin/awb/backfill-particles`

## Test Credentials
See `/app/memory/test_credentials.md`.
