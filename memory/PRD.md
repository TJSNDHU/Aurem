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

## Backlog (Priority Order)
- **P1**: ORA Status frontend view — single-screen 9-metric dashboard + Approve queue badge.
- **P2**: AWB (Website Builder) quality eval — render 5 sample sites.
- **P2**: Apply same deep-probe pattern to Stripe + Twilio (webhook secret drift, from-number ownership drift).
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
