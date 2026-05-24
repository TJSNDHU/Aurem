# ORA SESSION PROGRESS — Live State

ORA writes here after every major step. ORA reads at session start.

## Format
```
---
Task: short task description
Succeeded: what worked this step
Blocker: what is stuck (or "none")
Next: exact next concrete action
Cost: $X.XX USD so far this session
Branch: current git branch
PIDs: [list of tracked background process IDs]
Updated: 2026-MM-DDTHH:MM:SSZ
---
```

## Current State

---
Task: iter 331c — Sprint 6 COMPLETE (metrics + consent network + Vanguard + portability audit)
Succeeded:
  - Sprint 6.1: Consent-Based Data Network. set_consent / get_consent state machine, anonymizer with PII regex defense-in-depth, record_network_event_if_consented hook in outreach pipeline, 30-day purge cron, /api/me/consent endpoints. CRITICAL compliance proof: data NEVER written if consent=false (verified by 2 dedicated unit tests).
  - Sprint 6.2: ora_session_metrics collection + health_snapshot + /api/admin/ora/health endpoint. Recommend_fork nudge fires when session crosses 100 tool calls.
  - Sprint 6.3: OraHealthTile cockpit component (reads health + Vanguard score). vanguard_alerts module sends Telegram if score <80, daily 03:45 UTC cron. Morning Brief now includes one-line security status. Frontend portability audit: 3 hardcoded API endpoints fixed (PublicStatus, useAuth, LuxeV2Pages); REACT_APP_PUBLIC_BASE_URL added as optional env var.
  - 124/124 regression tests passing. 14 new Sprint 6 tests. Real E2E: consent toggle round-trip + 30-day purge scheduling verified live against preview backend.
Blocker: none
Next:
  - User pushes to GitHub → redeploys aurem.live to ship Sprint 6.
  - Backlog: real vector embeddings (90 MB MiniLM-L6 + sqlite-vec) when memory grows past ~50 docs.
  - Backlog: aggregate predictive lead scorer that consumes aurem_network_leads (once enough consented tenants contribute).
Cost: $0.00 (all unit + curl tests; no LLM calls this sprint)
Branch: main
PIDs: []
Updated: 2026-02-23T22:00:00Z
---


---
Task: iter 331d — Developer Portal Foundation (Option A wrap-up + Day-0 welcome email)
Succeeded:
  - Most of Option A backend was already live from a previous segment (developer_portal_core.py with full state machine, developer_portal_router.py with 10 endpoints, invoke_tool token-wall + deduction hooks, ConsentToggleCard.jsx). This iter closes the remaining 3 deliverables.
  - Day-0 welcome email wired into verify_otp success path via fire-and-forget asyncio task. Subject "Welcome to ORA CTO — Your 1000 tokens are ready", branded HTML body with 3 getting-started steps (login → connect GitHub → tell ORA what to build), token cost table, BYOK callout. Uses existing services.email_service_resend wrapper (no new dependency). Replaced the old broken `from services.email_service import send_email` fallback (that module never existed — every previous OTP email silently failed to send and only logged).
  - Sandbox cleanup cron registered in routers/registry.py: APScheduler CronTrigger at 04:30 UTC daily, calls developer_portal_core.cleanup_inactive_sandboxes() which walks /tmp/ora-sandbox-* and removes folders untouched > ORA_SANDBOX_INACTIVE_DAYS (default 45).
  - Real bug found and fixed during testing: verify_otp() crashed with `can't compare offset-naive and offset-aware datetimes` when Mongo returned a tz-naive expires_at. Now normalizes any tz-naive Mongo datetime to UTC before comparison. Would have broken OTP verify in production once the first OTP roundtripped through Mongo.
  - New regression suite test_iter331d_developer_portal_foundation.py: 20 base cases expanding to 37 with parametrization. Covers signup state machine (anti-bot, disposable email reject), OTP issue + verify + expiry + lockout, JWT roundtrip, BYOK encrypt/decrypt, token deduction + token wall + cost table, 5 abuse patterns, rate limits (per-min + paid-tier bypass), 10 pixel domain edge cases, referral bonus, sandbox cleanup with tmp_path + monkeypatch, welcome email subject/body assertions, welcome email sends via Resend wrapper (monkeypatched), and end-to-end verify_otp → welcome-email fire-and-forget.
  - Full active regression: 355 / 359 green across iter 327d → 331d (4 pre-existing failures in test_iter327n + test_iter329 are stale assertions against pre-Sprint-1 _TIER1_FILES API — known issue carried over from iter 330f notes, not caused by this iter).
Blocker: none
Next:
  - User pushes to GitHub → redeploys aurem.live so iter 331d ships.
  - P1: Developer Portal frontend pages (/developers/signup, /connect, /dashboard, /analytics, /tokens, /terms, /settings).
  - P1: Rest of onboarding email sequence (Day 3, Day 7, Day 25) via APScheduler walking developer_accounts.
  - P2: Stripe integration for Starter ($9) / Builder ($39) / Pro ($99) token packages.
  - Pre-existing: 4 stale tier-1 memory loader tests need to be rewritten against the new folder-driven loader (not done — separate task).
Cost: $0.00 USD (pytest + lint only; no LLM calls)
Branch: main
PIDs: []
Updated: 2026-02-23T23:30:00Z
---

---
Task: iter 331e Batch A — Security hardening + email sequence + stale test repair
Succeeded:
  Part 1 — Security guards (new services/dev_security_guards.py):
    - SSRF guard `assert_url_safe`: blocks 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8, 169.254.0.0/16, ::1, and exact-host list (localhost, kubernetes.default, metadata.google.internal, 169.254.169.254 AWS metadata, host.docker.internal, *.local, *.internal, *.intranet, *.lan, *.corp). Re-resolves hostnames via DNS and re-checks each returned IP — defeats DNS-rebinding (127-0-0-1.nip.io attacks). Fails closed on DNS failure.
    - File size limits `enforce_file_size_limits`: per-file 10 MB hard cap, per-session 50 MB cumulative cap, HTTP 413 envelope with plain-English message. Session totals tracked in-process dict; `reset_session_bytes` exposed for session release.
    - Concurrent session limit `acquire_session` / `release_session`: max 2 active per developer (env: ORA_DEV_MAX_ACTIVE_SESSIONS), tracked in `developer_accounts.active_sessions[]`. Stale sessions (heartbeat > 30 min) auto-pruned before counting. Same `session_id` twice = heartbeat refresh, not refusal.
    - Output masking `mask_sensitive_output`: walks nested dict/list and strips JWTs, bearer tokens, sk-*, sk_live_*, sk_test_*, pk_live_*, AIza*, re_*, mongodb:// URLs, telegram bot tokens, BEGIN PRIVATE KEY blocks, every env-var value whose name matches KEY|TOKEN|SECRET|PASSWORD|PASS|DSN|CONN_STRING, and internal AUREM paths (/app/backend/services/, /app/backend/routers/, /app/backend/.env, /app/memory/tier1/2/, /etc/supervisor/).
    - Internal path block `is_internal_path`: file-read tools (view_file/view_bulk/view_dir/safe_edit) refuse /app/backend/* paths from developer tenants.
    - All four guards wired into `ora_tools.invoke_tool` so they fire on every developer-initiated tool call (carries `_dev_user_id` in args).
    - 3 new tenant endpoints: POST /api/developers/session/acquire, POST /api/developers/session/release, GET /api/developers/sessions.
  Part 4 — Email sequence (new services/developer_email_sequence.py):
    - APScheduler cron daily 05:00 UTC, job id `aurem_dev_email_sequence`.
    - 4 buckets: day3_github_nudge (only if GitHub not connected, days 3-7), day7_unused (tokens_total_used==0, days 7-25), day7_halfway (tokens_remaining < 500 AND used > 0), day25_expiry (days 25-32).
    - Renders branded HTML (dark theme, same shell as Day-0 welcome) + plain-text fallback for each bucket; deep links to dashboard / connect / tokens pages.
    - Idempotent — stamps `email_sequence_sent[bucket_id]` on the account so cron re-runs never re-fire.
    - Best-effort audit row in `developer_email_sequence_log`.
    - Founder-trigger endpoint `POST /api/admin/developers/email-sequence/run` so the cron can be fired manually.
  Part 6 — Stale tier-1 loader test repair:
    - test_iter327n: 3 tests rewritten against the new folder-driven loader API (`last_injection_manifest()` instead of removed `_TIER1_FILES` constant; new normalized labels — `ZERO HALLUCINATION CHARTER`, `ORA MISTAKES LESSONS` etc).
    - test_iter329: 2 tests updated — file path moved /app/memory → /app/memory/tier1, assertion checks the folder discovery manifest rather than the truncated assembled block.
  Full active regression: **401 / 401 GREEN** across iter 327d → 331e (was 355/359 last iter; all 4 previously-stale assertions now green + 42 new iter-331e cases all green). Backend boots cleanly post-restart, /api/health 200.
Blocker: none
Next:
  - Batch B (next context window): all 8 developer frontend pages + landing-page hero + /developers/examples + /developers/status.
  - Batch C (third context window): Stripe — products, checkout, webhook, failed-payment downgrade with 3-day grace, invoice emails. Stripe test key is in pod env per platform policy.
  - User: push iter 331e to GitHub via "Save to Github" button.
Cost: $0.00 USD (pytest + lint only; no LLM calls)
Branch: main
PIDs: []
Updated: 2026-02-24T00:30:00Z
---


---
Task: iter 331f Batch B — Developer Portal frontend (10 pages) + AUREM CTO brand swap
Succeeded:
  • Re-skinned the 10 developer-portal pages to match the live AUREM aesthetic. Two modes in a single DeveloperShell:
    - LANDING mode (/developers, /developers/signup): exact homepage aesthetic — Cinzel serif headlines with orange→gold gradient (#FF6B00 → #E8C86A), Jost body, JetBrains Mono eyebrow pills with blinking orange dot, dark void background with subtle grid + radial glow, gold "Sign in" outlined nav button + orange-gradient "Claim 1000 tokens" CTA.
    - DASHBOARD mode (the 8 authed pages): LuxeDashboardV2 av2-* primitives — edge-to-edge sidebar with 8 nav items, top bar with AUREM logo + live token chip + theme toggle + logout, av2-card panels in av2-grid-4 / av2-grid-2 / av2-grid-3-2 layouts.
  • Built /developers (landing), /developers/signup, /developers/connect, /developers/dashboard, /developers/analytics, /developers/tokens, /developers/terms, /developers/settings, /developers/examples, /developers/status — all 10 routes wired into App.js with data-testids on every interactive element.
  • Shared primitives extracted to DevDashboard.jsx: PageHeader, MetricTile, SectionTitle — reused across the 7 sibling pages so headings stay consistent.
  • iter 331f health endpoint shipped earlier this batch: GET /api/admin/developers/health returns total/verified/abuse_flagged dev counts, active sessions sum across all accounts, token remaining/used totals, 24-h block counters (ssrf/abuse/sessions_refused), 24-h emails sent, 24-h token calls + a green/yellow/red overall status. Wired into the ORA Cockpit as `DeveloperPortalPulseTile` (30 s poll, status dot, 3 metric columns + a blocks-today row).
  • AUREM CTO brand swap: every user-facing reference to "ORA" in marketing copy, signup pages, dashboard pages, terms, status page, welcome email, Day-3/7/25 sequence templates → "AUREM CTO". Hero headline now "Build with AUREM CTO". Welcome email subject changed to "Welcome to AUREM CTO — Your 1000 tokens are ready". Internal code symbols, log messages, file names, tier-1 memory all still say ORA (no code-level rename).
  • Testing agent E2E run on landing + signup + connect + dashboard: all selectors found, signup → OTP → JWT → redirect flow works end-to-end. Lint clean on all 11 new/rewritten frontend files. 401 / 401 backend regression green.
  • Three frontend testids confirmed by visual screenshot: dev-landing-hero-headline, dev-shell-logo, dev-shell-signup-cta. Auth gating on the 8 authed pages confirmed by testing agent (unauthenticated → redirect to /developers/signup).
Blocker: none.
Deferred:
  • iter 331f-c minor cleanup queued: ConsentToggleCard still uses shadcn Card primitive instead of av2-card (testing agent flagged it as minor visual inconsistency). Roughly 20 LOC to swap when next touching settings.
  • iter 332a Emergent Specialist Swarm (extend fork_context with mode="emergent", auto-escalation after 2 failures, validated solution memory with SHA256 signatures, cost tracking, smart routing rules, Specialist Cost Breakdown cockpit tile) — full spec captured by the founder, 3-4 hours of careful infra work. Queued for the next context window; pattern matches the Batch A / Batch B split that has been working.
Next:
  • Push iter 331f-b to GitHub via "Save to Github" — preview is green, production redeploys from main.
  • Batch C (third context window): Stripe — products + checkout + webhook + failed-payment 3-day-grace downgrade + invoice emails. Stripe test key already in pod env per platform policy.
  • iter 332a as described above.
Cost: $0.00 USD (testing agent + lint + pytest only; no LLM calls)
Branch: main
PIDs: []
Updated: 2026-02-24T01:20:00Z
---


---
Task: iter 331g — Beta ticker + Swagger UI + Stripe Batch C
Succeeded:
  • Beta ticker on /developers landing: new `GET /api/developers/public/stats` returns `{verified_developers: N}` (no auth). DevLanding fetches once on mount and renders "in public beta — N developers building" in JetBrains Mono just under the eyebrow pill (only when N > 0). Real count proven: 3 verified devs in preview DB.
  • Swagger UI page at /developers/docs: new `DevApiDocs.jsx` loads swagger-ui-bundle v5.17.14 from JSDelivr CDN, points it at the new filtered openapi feed, auto-attaches the dev JWT to every "Try it out" call via requestInterceptor, pre-authorizes the BearerAuth lock on load.
  • Filtered OpenAPI feed `GET /api/developers/openapi.json`: builds against THIS router's routes only (bypasses the rest of the codebase which has at least one route missing a response class that breaks the global `app.openapi()` schema generator). Returns 11 developer-facing paths + a BearerAuth security scheme. NO admin paths leak through.
  • Stripe Batch C — three packages, all one-time payment (Pro is one-time $99 = 30 days of unlimited rather than a recurring subscription, simpler than Stripe subscriptions for now):
    - starter: $9   → +10,000 tokens
    - builder: $39  → +50,000 tokens
    - pro:     $99  → 30 days of subscription_status="paid"
  • New service `services/developer_stripe.py` using `emergentintegrations.payments.stripe.checkout.StripeCheckout` per the integration playbook. Public surface: `start_checkout`, `get_status`, `credit_for_session`, `process_webhook_event`, `package_table`. Fixed amounts on the BACKEND — frontend cannot inject a tier price.
  • New endpoints in `developer_portal_router.py`:
    - `GET  /api/developers/packages` — public price table for /tokens page
    - `POST /api/developers/checkout/start` — body `{tier, origin_url}` → returns `{url, session_id}`. Creates a pending `payment_transactions` row before redirecting.
    - `GET  /api/developers/checkout/status/{session_id}` — polled by the frontend success page. Idempotently credits on first poll where `payment_status == "paid"`.
    - `POST /api/webhook/stripe` — Stripe webhook handler. Verifies signature via `client.handle_webhook(raw_body, signature)`, dedupes on `event.id` against `stripe_events_processed` collection (unique index), routes the event to credit/grace handlers.
  • Idempotency contract proven by tests: 5 concurrent `credit_for_session` calls + a webhook event all converge to exactly ONE token grant. The race winner is decided atomically via `findOneAndUpdate({credited: false} → {credited: true})`. Webhook deduping uses unique index on `event_id`.
  • 3-day grace logic for `invoice.payment_failed`: first failure stamps `grace_period_ends_at = now + 3d` and emails the customer. Second failure after grace expiry flips `subscription_status` back to "free" and clears the grace stamp. Both branches tested.
  • Invoice email: after successful credit, a Resend email is sent (`AUREM CTO — Receipt for your <tier> purchase`) with the session_id, USD amount, and either token grant or paid-until date.
  • Two new collections wired into `ensure_indexes()`: `payment_transactions` (unique on `session_id`, indexed on `(user_id, created_at)`), `stripe_events_processed` (unique on `event_id`).
  • DevTokens.jsx rewritten to use the real flow: POST `/checkout/start` → window.location.href = j.url → on Stripe redirect back with `?success=1&session_id=...`, polls `/checkout/status/{sid}` up to 8 times (1.5s interval). Success banner shows tokens or days granted.
  • New regression file `test_iter331g_stripe.py` — 14 cases covering all surfaces above. Plus 2 existing test files updated (test_iter331d for AUREM CTO welcome subject, test_iter331e unchanged).
  • Full regression: **415 / 415 GREEN** across iter 327d → 331g (was 401 last iter; +14 new Stripe cases all green).
Blocker: none.
Next:
  • Push iter 331g to GitHub via "Save to Github" — preview is green, production redeploys from main. The pod env already has STRIPE_SECRET_KEY (live key) and STRIPE_PUBLISHABLE_KEY (live key) provisioned by Emergent. STRIPE_WEBHOOK_SECRET will need to be set in production env once you register the webhook endpoint with Stripe and grab the signing secret.
  • iter 332a — Emergent Specialist Swarm (extend fork_context with mode="emergent", auto-escalation after 2 failures, validated solution memory with SHA256 signatures, cost tracking, Specialist Cost Breakdown cockpit tile). Full spec captured. Estimated 3-4 hours of careful infra work. Queued for the next context window.
Backlog:
  • Webhook endpoint needs to be REGISTERED in the Stripe dashboard once aurem.live ships with iter 331g. URL = `https://aurem.live/api/webhook/stripe`. Events to enable: `checkout.session.completed`, `invoice.payment_failed`, `invoice.payment_succeeded`, `customer.subscription.deleted`.
  • Pro recurring subscriptions: current impl treats $99/Pro as one-time → 30 days unlimited. If customers ask for auto-renew, swap to Stripe subscription mode (mode="subscription" + recurring price) — about 60 LOC change in `start_checkout` + 30 LOC in webhook handler.
  • ConsentToggleCard still uses shadcn Card primitive instead of av2-card — minor visual inconsistency previously flagged by testing agent. ~20 LOC swap when next touching settings.
Cost: $0.00 USD (pytest + lint + integration playbook only; no LLM calls beyond playbook)
Branch: main
PIDs: []
Updated: 2026-02-24T01:55:00Z
---


---
Task: iter 332a-1 — Emergent Specialist Swarm foundation (Parts 1 + 3 + 4) + Recent purchases strip
Succeeded:
  • Recent purchases strip on /developers/dashboard: new `GET /api/developers/me/purchases` returns last 3 `payment_transactions` rows. DevDashboard renders a compact JetBrains-Mono list (date · tier · $amount · ✓ credited / pending) in an av2-card, only when at least one purchase exists.
  • Extended `fork_context(...)`: new optional kwargs `mode="ora"|"emergent"` (default "ora") + `session_id` for cost-log audit. Refuses unknown modes with clear error. Added task_type aliases `"integration"` and `"design"` that route to the existing prompts.
  • New service `services/ora_validated_solutions.py` — self-learning memory for ORA's specialist calls:
    - `compute_signature(task_type, error_message, file_type)` produces a SHA256 hash that normalises away traceback line numbers, hex addresses, request ids and quoted strings so two different occurrences of the same bug collapse to the same signature.
    - `lookup_solution(sig)` atomically increments `use_count` and returns the cached row, capped at `MAX_USES_BEFORE_REVALIDATE = 10` (env-overridable). At cap, returns None so the caller falls through to a fresh specialist.
    - `save_solution(...)` upserts a row idempotently against `signature`. Stores fix_suggestion (capped 4000 chars), findings (20 max), files_involved (20 max), specialist tag and cost_usd.
    - `log_specialist_call(...)` appends a row to `ora_specialist_calls` with mode / task_type / specialist_name / verdict / cache-hit flag / tokens_used / cost_usd / elapsed_ms. Cost defaults: $0.001 per ora call, $0.05 per emergent call, $0 for cache hits.
    - `cost_rollup_7d()` aggregates the 7-day cost picture into ora / emergent / validated buckets for the cockpit tile. Saved-USD = N × $0.05 emergent-call equivalent.
  • fork_context now does cache lookup BEFORE the LLM call. On hit it returns at $0 with `used_validated_solution=True` and `elapsed_s=0.0`. On miss it runs the LLM, saves the answer under the signature, and logs the cost row. Cache-hit logging happens in BOTH branches so the rollup is honest.
  • New router `routers/ora_specialist_cost_router.py` exposes `GET /api/admin/ora/specialist-cost-breakdown` (super-admin gated via existing `services.admin_security.ensure_admin`). Smoke-tested: refuses without bearer → HTTP 401, returns the full 7-day shape with bearer.
  • Both `set_db` calls wired into `routers/registry.py` startup so the cache + cost log connect to the real Mongo on every boot.
  • New regression file `test_iter332a_specialist_swarm_foundation.py` — 17 cases covering: signature determinism, traceback-noise collapse, file_type isolation, task_type isolation, cache lookup empty/hit/cap, save+lookup roundtrip, fork_context end-to-end cache hit, mode validation, task_type alias acceptance, log_specialist_call with default + cache pricing, cost_rollup_7d 3-bucket aggregation, cockpit endpoint admin gate, source-level wiring sanity.
  • Full regression: **432 / 432 GREEN** across iter 327d → 332a-1 (was 415 last iter; +17 new cases all green; no regressions on the older `fork_context` callers thanks to all new params being keyword-only with defaults).
  • Recent-purchases endpoint also smoke-tested.
Blocker: none.
Deferred to iter 332a-2 (next context window):
  • Part 2 — Auto-escalation in `ora_guards.py`: count failures per task per session, silently escalate to mode="emergent" after 2 ora-mode failures. Hook into `check_escalation_needed(session_id, task_id)` + the ORA SYSTEM_PROMPT rule "If task fails 2x, auto-call fork_context with mode='emergent'".
  • Part 5 — Smart routing rules: new .jsx/.tsx file created → design-mode directly; new 3rd-party integration → integration-mode directly; debug touching 3+ files → ora first then escalate.
  • Cockpit UI tile — "Specialist Cost Breakdown" card pulling from the new endpoint, similar to DeveloperPortalPulseTile (~50 LOC).
  • The 6 E2E proofs from the original spec — only proofs 3, 5, 6 (cache hit, integration playbook routing, /developers/health real data) work today. Proofs 1, 2, 4 (auto-escalation, validated solution on 3rd try, new-jsx → design agent) need Part 2 + Part 5.
Next:
  • Push iter 332a-1 to GitHub via "Save to Github" — preview is green.
  • iter 332a-2 — the three deferred items above.
Cost: $0.00 USD (pytest + lint + curl smoke only; no LLM calls)
Branch: main
PIDs: []
Updated: 2026-02-24T02:30:00Z
---


---
Task: iter 332a-2 — Auto-escalation + Smart routing + Cockpit tiles + Validated Solutions panel
Succeeded:
  • Validated solutions panel endpoint: new `GET /api/admin/ora/validated-solutions?limit=20` returns the most-recently-used cached fix patterns with plain-English `fix_suggestion` + first `finding` + `use_count` + dates. Admin-gated.
  • Part 2 — Auto-escalation logic in `services/ora_guards.py`:
    - `ESCALATE_AFTER_FAILS` (env: ORA_ESCALATE_AFTER_FAILS, default 2)
    - `record_task_failure(session_id, task_id)` bumps an in-process counter on the `(session_id, task_id)` tuple
    - `record_task_success(session_id, task_id)` resets the counter
    - `check_escalation_needed(session_id, task_id)` returns `{escalate, fails, suggested_mode}` — flips suggested_mode to "emergent" after the threshold is crossed
    - fork_context now bumps the counter on `verdict="fail"` and resets it on `verdict="pass"` (only when session_id is passed — fully backwards-compatible for older callers).
  • Part 5 — `smart_route(task_type, brief, relevant_files, is_new_file, session_id, task_id)` in `ora_guards.py`. Pure function, no DB, no LLM. Returns `{mode, task_type, auto_specialist, reason}`. Hard rules: new .jsx/.tsx → design specialist (emergent + auto_specialist=True); brief mentions a new SaaS integration (stripe/twilio/resend/etc.) → integration playbook (emergent + auto_specialist=True). Soft rules respect the failure counter — after threshold crossed, flips to emergent automatically.
  • Cockpit tiles (visible in /admin/ora-cto-cockpit):
    - `SpecialistCostBreakdownTile.jsx` — 7-day rollup of ORA local / Emergent / Validated cache hits with $ spent vs $ saved. 30-second poll. Pulls from `/api/admin/ora/specialist-cost-breakdown`.
    - `ValidatedSolutionsPanel.jsx` — plain-English list of fix patterns ORA has learned, "What ORA taught itself" header, used-count badge, first finding shown italicized. Empty state explicitly says "ORA will start learning the first time it solves the same problem twice."
    - Both wired into `OraCtoCockpit.jsx` in a side-by-side grid (cost on the left, panel on the right, 1fr : 1.4fr ratio).
  • New regression file `test_iter332a2_escalation_routing.py` — 17 cases covering: failure counter increments + threshold + reset, env-overridable threshold sanity, smart_route new .jsx → design + emergent, new .tsx → design, new Stripe integration → integration + emergent, new Resend integration → integration + emergent, simple debug → ora-first, complex debug (3+ files) → ora-first with escalation-ready tag, after 2 failures → emergent flip, validated-solutions endpoint returns plain English, validated-solutions endpoint admin-gated, **E2E Proof 3** (repeat debug → cache hit at $0 + used_validated_solution=True + elapsed_s=0.0), **E2E Proof 5** (cockpit rollup returns all three buckets after mixed calls land), **E2E Proof 6** (validated-solutions endpoint exposes plain-English rows), source-level wiring sanity for smart_route exports + cockpit JSX + fork_context counter calls.
  • Full regression: **449 / 449 GREEN** across iter 327d → 332a-2 (was 432 last iter; +17 new cases all green; zero regressions in older `fork_context` callers because new kwargs are keyword-only with defaults).
  • Three E2E proofs from the original spec now PROVEN in tests:
    - Proof 3 — same debug task 2nd time → validated solution found in DB, used directly, no Emergent call
    - Proof 5 — cockpit tile shows ORA + Emergent + validated rollup with real numbers
    - Proof 6 — /developers/health real data still flowing (unchanged from iter 331f)
  • Three E2E proofs from the original spec still deferred (need iter 332a-2's hard auto-escalation wiring inside `invoke_tool`):
    - Proof 1 — trigger same debug 2 times → auto-escalates to emergent  (logic shipped, dispatch hook to invoke_tool is the missing 20 LOC)
    - Proof 2 — same debug 3rd time → validated solution used → no Emergent call (Proof 3 covers this case directly via fork_context; the hook into invoke_tool is the missing piece for the "transparently from any tool" path)
    - Proof 4 — new Stripe integration → integration playbook called directly (smart_route returns it correctly; the bridge from invoke_tool to fork_context with auto_specialist is the missing piece)
Blocker: none — 332a is functionally complete; the remaining "hook into invoke_tool" is a 30-minute follow-up that should NOT delay the enterprise work the founder asked for next.

Next context window — iter 332b Batch A (Enterprise Foundation, 7 fixes):
  1. RBAC complete wiring — wire `shared/auth/rbac.py` AgentRole + Permission enums into EVERY router that currently just checks admin-bearer presence. Owner/Admin/Developer/Viewer hierarchy. ~2h.
  2. Unified audit log — merge 5 scattered collections (`audit_log`, `customer_audit_log`, `self_audit_log`, `catalog_audit_log`, `ora_tool_audit`) into `db.unified_audit_log` with `source_collection` tag. New `GET /api/enterprise/audit` with filters + CSV export. ~1h.
  3. White-label UI — Wire frontend to swap branding at runtime (logo URL, primary color, company name) from existing `services/white_label.py` backend. ~1h.
  4. Custom domain UI — Simple wizard at `/enterprise/admin/domain` (enter domain → show CNAME → verify). ~30m.
  5. API key management UI — List/Rotate/Revoke/Create per org. ~30m.
  6. Enterprise dashboard `/enterprise/admin` — Team members + Usage + Security events + Billing + Settings sections. ~1h.
  7. Contact Sales page `/enterprise` on aurem.live — AUREM homepage aesthetic, form → Telegram alert + auto-reply email + `db.enterprise_leads` row. ~30m.
  Final proofs: viewer blocked from deploy → 403; audit event → unified_audit_log row; CSV audit export downloads; custom branding swaps logo; domain CNAME instructions shown; API key rotate works; enterprise form fires Telegram.

Then iter 332a-3 (small): wire smart_route + check_escalation_needed into `invoke_tool` so the missing 3 E2E proofs (1, 2, 4) land — ~30 minutes once enterprise foundation is in.

Future:
  • Pro recurring auto-renew (Stripe subscription mode) when customers ask
  • ConsentToggleCard still uses shadcn Card — minor visual cleanup
  • Stripe webhook registration in dashboard once aurem.live ships iter 331g
  • System overview page redesign (separate slice)
Cost: $0.00 USD (pytest + lint + curl smoke only; no LLM calls)
Branch: main
PIDs: []
Updated: 2026-02-24T03:30:00Z
---


---
Task: iter 332a-3 (Re-teach + invoke_tool hooks) + iter 332b Batch A (Fixes 2 + 7 of 7)
Succeeded:
  • Re-teach button — new `POST /api/admin/ora/validated-solutions/{sig}/reteach` deletes the cached row. ValidatedSolutionsPanel.jsx now renders a small "Re-teach" button on every row; one click removes the stored fix so the next occurrence runs a fresh specialist. 64-char hex signature validation. Admin-gated.
  • iter 332a-3 — invoke_tool hooks (30 min):
    - `invoke_tool` now consults `smart_route` for every `fork_context` call BEFORE dispatch. Mode + task_type are auto-overridden when the brief mentions a new third-party integration (Stripe/Resend/etc.) or when `is_new_file=True` for a .jsx/.tsx. The routing decision is surfaced on the result envelope as `routing_reason` and `auto_specialist`.
    - `invoke_tool` now feeds `record_task_failure` / `record_task_success` on every tool call (keyed on `(session_id, tool_name)`). Two consecutive ok=False results on the same tool → smart_route silently flips subsequent fork_context calls to mode="emergent".
    - The 3 deferred E2E proofs all PASS now:
      • Proof 1 — fork_context fails twice via invoke_tool → next smart_route picks mode="emergent"
      • Proof 4 — fork_context brief mentioning "Integrate Stripe" routes to mode="emergent" + task_type="integration" + auto_specialist=True BEFORE any LLM call
      • New .jsx file → mode="emergent" + task_type="design" + auto_specialist=True
  • iter 332b Batch A (Fixes 2 + 7 SHIPPED, 5 deferred):
    - **Fix 2 — Unified audit log** SHIPPED. New `services/unified_audit.py`:
      • `write_event(action, resource, result, user_id, org_id, ip_address, user_agent, source_collection, extra)` — UUID4 event_id + ISO8601 timestamp + sanitized lengths + bounded `extra` dict (max 50 keys). Returns `{ok, event_id}`, never raises.
      • `query_events(...)` — paginated query with filters: user_id / action / resource / result / source_collection / date_from / date_to. Sorted desc by timestamp.
      • `export_events_csv(...)` — same filter set, returns a real CSV string with the 10-column header row. Capped at 10k rows.
      • New collection `db.unified_audit_log` with indexes on (timestamp desc), event_id (unique), user_id, action.
      • Real bug caught + fixed during test: `dict[:50]` slice was invalid Python — replaced with safe key-bound dict comprehension.
    - **Fix 7 — Contact Sales page** SHIPPED. Public POST `/api/enterprise/leads`. AUREM homepage aesthetic Cinzel hero ("AUREM CTO for Enterprise."), 3 pillar cards (SECURITY / RESIDENCY / SUPPORT), 3 pricing tiers (Team $200/mo, Business $800/mo, Enterprise Custom), contact form with team-size select + "Tell us what you need" textarea. On submit: persists `db.enterprise_leads` row + writes unified_audit_log entry under `action="enterprise_lead_submitted"` + fires Telegram alert (best-effort) + sends Resend auto-reply ("Thanks for reaching out, [Company]") (best-effort). Smoke proven: POST returned `{"ok":true,"lead_id":"7a54..."}`; `/enterprise` page serves 200.
    - New routes in registry: `/api/enterprise/audit` (admin), `/api/enterprise/audit/export` (admin, CSV), `/api/enterprise/leads` (public).
  • Full regression: **471 / 471 GREEN** across iter 327d → 332b Batch A (was 449 last iter; +22 new cases all green; zero regressions in the older `fork_context` callers because the new `mode`/`session_id` kwargs are keyword-only with defaults, and `invoke_tool`'s new hooks are isolated to the `name == "fork_context"` branch).
Blocker: none.
Deferred from iter 332b Batch A to **iter 332b Batch A-2 (next context window)**:
  - **Fix 1 — RBAC complete wiring** (the largest by far). Existing `shared/auth/rbac.py` is for pipeline AGENTS (Scout/Architect/etc.), not human users. Requires a NEW `user_rbac.py` with Owner/Admin/Developer/Viewer hierarchy + Permission enum + `require_permission(user, Permission.X)` decorator + applied to every endpoint that currently just checks admin-bearer presence. Honest scope: 2-3 days of focused work touching ~80 routers. Should NOT be jammed in alongside other items.
  - **Fix 3 — White-label UI**: backend already exists (`services/white_label.py`); needs a settings page with logo upload + color picker + live preview + the runtime branding swap in the React app shell.
  - **Fix 4 — Custom domain UI**: wizard at `/enterprise/admin/domain` (enter domain → show CNAME → verify button → DNS check).
  - **Fix 5 — API key management UI**: list/rotate/revoke/create CRUD page.
  - **Fix 6 — Enterprise dashboard `/enterprise/admin`**: 5 sections (Team members, Usage, Security events feeding from unified_audit_log, Billing, Settings).
Next:
  • Push iter 332a-3 + 332b Batch A to GitHub via "Save to Github" — preview is green.
  • iter 332b Batch A-2 — the 5 deferred enterprise items (Fixes 1, 3, 4, 5, 6). Recommend doing Fix 1 RBAC as its own dedicated slice and Fixes 3/4/5/6 as a second slice ("Enterprise Admin Pages").
Backlog:
  • Migration job to copy historical rows from the 5 legacy audit collections (`audit_log`, `customer_audit_log`, `self_audit_log`, `catalog_audit_log`, `ora_tool_audit`) into `unified_audit_log` with `source_collection` tag. ~40 LOC + APScheduler job; safe to defer because all NEW writes already use unified_audit.
  • Pro recurring auto-renew (Stripe subscription mode) when customers ask
  • System overview page redesign (frontend-only, ~2h)
  • Stripe webhook registration in dashboard once iter 331g ships to prod
Cost: $0.00 USD (pytest + lint + curl smoke only; no LLM calls)
Branch: main
PIDs: []
Updated: 2026-02-24T04:00:00Z
---



---
Task: iter 332b Batch A-2 — Enterprise Admin UI (Fixes 3, 4, 5, 6 of 7) + syntax repair
Succeeded:
  • **Critical syntax bug repaired**: enterprise_router.py had a SyntaxError at line 213 — the previous session's API Key CRUD code was inserted INSIDE the unclosed `send_email(` call of `submit_enterprise_lead`. Result: ALL `/api/enterprise/*` endpoints were dead (router import skipped at startup with `[REGISTRY] enterprise router failed: invalid syntax`). Fixed by closing the `send_email()` call cleanly and moving the inserted CRUD/Branding/Domain sections to after the function body. Backend now boots clean — no enterprise router warnings.
  • **Fix 5 — API key management UI** SHIPPED. `/enterprise/admin/keys` page lists keys (key_preview only — full key NEVER re-shown), create form with scope dropdown (read/write/admin), reveal-once banner with Copy button, Rotate + Revoke per row with confirm prompts, all audit events written to unified_audit_log under api_key_created / api_key_rotated / api_key_revoked.
  • **Fix 3 — White-label UI** SHIPPED. `/enterprise/admin/branding` page with Field rows for tenant_id, company_name, logo_url, native HTML color picker + hex input, plus a side-by-side live preview card that recolors the gradient + CTA button in real time. Save writes to enterprise_branding collection and stamps a unified_audit_log row.
  • **Fix 4 — Custom domain wizard** SHIPPED. `/enterprise/admin/domain` is a 3-step wizard (animated stepper bar): Step 1 enter domain → Step 2 see CNAME instructions (Type/Name/Value/TTL) → Step 3 success card. Verify button does real DNS resolution via the existing `/api/enterprise/domain/verify` endpoint (compares A records of the customer's domain vs aurem.live).
  • **Fix 6 — Enterprise dashboard** SHIPPED. `/enterprise/admin` (Overview) shows 4 metric tiles (audit events 24h, ORA calls 7d, security blocks 7d, $ spend 7d) + a recent audit events feed (15 rows, grid-aligned, color-coded ok/blocked/fail badges) — pulls live data from `/api/enterprise/audit` and `/api/admin/ora/specialist-cost-breakdown`.
  • **Auth model fix**: EnterpriseAdminShell originally wrapped pages in `<DeveloperShell requireAuth>` (which checks `dev_jwt`). But admin pages use `platform_token` via `adminHeaders()` — mismatch would have redirected platform admins to /developers/signup. Fixed by dropping the `requireAuth` flag; backend 401 now drives the auth UX and admins land directly on the page.
  • **App.js wiring**: 4 new routes registered: /enterprise/admin, /enterprise/admin/branding, /enterprise/admin/domain, /enterprise/admin/keys (+ 4 new component imports).
  • **Shared shell**: EnterpriseAdminShell exports a Field, PrimaryButton, Banner helper trio used identically across all 4 sub-pages → consistent visual language. Pill nav bar (`enterprise-admin-nav` testid) with active-route detection.
  • **Tests**: new file `tests/test_iter332b_enterprise_admin_ui.py` — 16 cases covering branding GET/PUT + audit row + public read, domain register + invalid-char rejection + pending row + verify on unresolvable domain, API key create/list/rotate/revoke with 404 paths + audit rows written + key never exposed in list, plus source-level wiring assertions for App.js routes and the requireAuth-removed shell. All 16 green.
  • **Testing agent run** (E2E both backend + frontend): zero issues. Reports 100% backend + 100% frontend success rate. All 21 frontend data-testids verified (enterprise-admin-nav, overview-* tiles, branding-editor + preview + color picker, domain-wizard + 3 steps, apikey-list + create form etc.).
  • **Active regression**: 510 / 511 pytest green across iter 327d → 332b A-2. The single fail (`test_iter327op::test_tier2_rule_table_lists_keywords_and_exists_flag`) is pre-existing — asserts `len(rules) == 3` when tier-2 has grown to 7 rules; not in scope for this slice.
  • **Frontend smoke screenshot**: /enterprise/admin renders cleanly — Cinzel "Tenant overview" headline, ENTERPRISE / ADMIN orange eyebrow, sidebar with Home/Connect/Analytics/Examples/Tokens/API Docs/Status/Settings/Terms, 4 sub-nav pills (Overview / Branding / Domain / API Keys), 4 metric tiles, audit feed card.
Blocker: none.
Deferred to future sessions:
  - **Fix 1 — RBAC complete wiring**: still queued. Per founder ("RBAC backend mein hai — enterprise prospect nahi dekhta backend code") this is intentionally NOT in this slice. Needs its own dedicated 2-3 day session for the new `user_rbac.py` with Owner/Admin/Developer/Viewer + applied across ~80 routers.
Next:
  • Push iter 332b A-2 to GitHub via "Save to Github" — preview is green; production redeploys from main.
  • iter 332b Batch B — SAML 2.0 SSO (Okta, Azure AD, Google), SCIM user provisioning, Organization entity above teams.
  • iter 332b Batch C — Data residency (Canadian cluster option), SOC 2 Type II evidence export (PDF), Enterprise SLA page + MSA template.
Backlog:
  • Pre-existing stale assertion in test_iter327op (1 line fix — `assert len(rules) == 3` → `>= 3`).
  • Migration job to backfill historical rows from 5 legacy audit collections into unified_audit_log.
  • Service-account Google Calendar API for shared staff calendar (P2).
  • Friendlier "report expired" 404 page for stale ghost-* slugs (P2).
  • System overview page redesign (frontend-only, ~2h).
Cost: $0.00 USD (pytest + lint + curl smoke + testing agent only; no LLM calls)
Branch: main
PIDs: []
Updated: 2026-02-24T05:00:00Z
---



---
Task: iter 332b A-3 (production auth fix + Copy CNAME + stale test fix) + Batch B Steps 1+2+3 (Org + SAML + SCIM)
Succeeded:
  • **Production auth bug — RCA + 3 fixes**. Founder reported login loop + direct links land on dashboard without login + logout doesn't logout. Root cause: `AdminGuard` (in `RouteGuards.jsx`) never checked the JWT `exp` claim, so a stale token left in localStorage still passed the `is_admin` test and granted access. Combined with a logout that didn't revoke server-side refresh tokens, the auto-refresh interceptor could silently re-mint sessions.
    - Fix 1: AdminGuard + TenantGuard now decode `exp` and call `clearAdminAuth()` / `clearCustomerAuth()` on expiry → bounce to /admin/login or /login.
    - Fix 2: AdminShell.logout() now hits new backend POST /api/auth/admin/logout (idempotent, returns ok=true even without bearer) to revoke ALL refresh tokens, clears aurem_admin_refresh, then clearAdminAuth(), then navigate to /admin/login. Live: 97 stale refresh tokens revoked on first call.
    - Fix 3: AdminLogin auto-redirect now triggers for any admin (is_admin || is_super_admin), not just super_admin.
  • **Copy CNAME button** added to /enterprise/admin/domain step 2 — 4-line clipboard copy + "Copied ✓" green confirmation, data-testid `domain-cname-copy-btn`.
  • **Stale test repair**: test_iter327op tier-2 rule count assertion relaxed from `== 3` to `>= 3` + SECURITY category presence check.
  • **Batch B Step 1 — Organization entity**: services/organizations.py + routers/organizations_router.py (11 endpoints under /api/orgs). Owner/Admin/Member/Viewer roles, last-owner guards, invite tokens with 14-day TTL, org switcher persists current_org_id to users. 25 pytest cases green; live E2E proven via curl.
  • **Batch B Step 2 — SAML 2.0 SSO**: services/saml_sso.py + routers/saml_router.py (7 endpoints under /api/saml). Config storage validates IdP provider against okta/azure_ad/google/onelogin/generic; sp_entity_id + acs_url derived from org slug; /metadata serves real SP XML; /discover finds active SAML config by email domain. ACS handler is a stub (returns 501) until python3-saml is installed in a follow-up slice — config storage and admin UI surface ship today.
  • **Batch B Step 3 — SCIM 2.0 provisioning**: services/scim_provisioning.py + routers/scim_router.py (admin token CRUD at /api/scim/{org_id}/tokens + protocol at /scim/v2/{org_id}/Users). Tokens stored as SHA-256 hash + 14-char preview, constant-time compare, full token shown ONCE. Users CRUD: create / list / get / delete (soft, active=false + removed from org). SCIM provisioner bypasses org-role gate via authenticated-token authority.
  • 15 SAML + SCIM pytest cases all green. Total Batch B: 40 cases (25 Org + 15 SAML/SCIM).
  • **Full active regression**: 386 / 386 green across iter 327op + 329 + 330 + 331 + 332 series.
  • Backend boots clean — health=200, all five new endpoint families respond 401 (mounted + auth-gated): /api/orgs/me, /api/saml/{id}/config, /api/scim/{id}/tokens, /scim/v2/{id}/Users, /api/auth/admin/logout.
Blocker: none. Production-side: founder pushes to GitHub → redeploys aurem.live to ship auth fix.
Deferred (intentional — separate slices, integration playbook needed):
  • Full SAML AuthnResponse parsing (needs python3-saml + signature/audience/recipient validation + JWT minting).
  • SCIM PATCH partial-update + Groups endpoint (Users CRUD covered).
  • Frontend org switcher dropdown + Enterprise SSO/SCIM settings page (UI for the Step 2/3 backends).
  • RBAC complete wiring across ~80 routers (dedicated 2-3 day slice).
Next:
  • Push to GitHub → redeploy aurem.live so the auth fix lands on prod.
  • Batch B follow-ups: frontend SSO/SCIM settings UI + python3-saml playbook for real AuthnResponse parsing.
  • Batch C: Data residency, SOC 2 Type II PDF export, SLA + MSA page.
Cost: $0.00 USD (pytest + lint + curl smoke only; no LLM calls)
Branch: main
PIDs: []
Updated: 2026-02-24T07:00:00Z
---


---
Task: iter 332b A-4 (session-expired toast) + Batch B-2 follow-up (full python3-saml ACS) + Batch C (data residency + SOC 2 PDF + SLA)
Succeeded:
  • **Session-expired toast** — RouteGuards stashes `sessionStorage['aurem_session_expired']='admin'|'customer'` on expiry/invalid token; AdminLogin reads once on mount, shows an orange banner ("Your session expired. Please sign in again."), auto-dismisses after 6s, clears the flag so a refresh doesn't show it again. data-testid `admin-login-session-expired`.
  • **python3-saml 1.16.0 installed** (along with xmlsec 1.3.17, isodate 0.7.2 + apt libxmlsec1, libxmlsec1-dev, libxml2, pkg-config, xmlsec1). requirements.txt frozen.
  • **Real SAML ACS handler** — services/saml_sso.py now ships:
    - `build_saml_settings(org, cfg)` — assembles OneLogin_Saml2_Settings dict from MongoDB row + strict mode + wantAssertionsSigned.
    - `prepare_fastapi_request(req, post, relay)` — converts FastAPI Request to the dict OneLogin_Saml2_Auth wants. Honors X-Forwarded-Proto + X-Forwarded-Host so the k8s ingress doesn't break python3-saml's Destination check.
    - `parse_acs_response(req, response, relay, org, cfg)` — runs the full python3-saml validation (signature + audience + recipient + assertion), returns {ok, user, attributes, name_id} or {ok:false, error, detail}.
    - `map_saml_attributes` — handles Okta + Azure AD (URN claims) + Google + OneLogin attribute shapes.
    - `upsert_saml_user` — find-or-create the user in db.users + adds to org as default-role member.
    - `POST /api/saml/{org_id}/acs` now mints an AUREM JWT via `create_token(user_id, is_admin, email)`, audits via unified_audit_log + saml_logins, and 303-redirects to `/saml/landing#t=<JWT>` (hash not query — JWT never lands in nginx access logs).
  • **SamlAcsLanding.jsx** — new frontend route at `/saml/landing` that plucks `#t=` from the URL hash, writes it via setPlatformToken, strips the hash, then navigates to `/admin/mission-control`. testid `saml-acs-landing`.
  • **Batch C Step 1 — Data residency** — services/data_residency.py: 3-region table (ca | us | eu) with PIPEDA / Law 25 / GDPR / HIPAA / FedRAMP flags. Canada is the default; orgs request a region change via routers/compliance_router.py which queues to `residency_change_requests` collection (actual cluster migration is a manual ops step).
  • **Batch C Step 2 — SOC 2 Type II PDF** — services/soc2_export.py renders a multi-page ReportLab PDF with: cover page, CC1 control environment, CC6 logical access, CC7 audit event summary (table populated from unified_audit_log for the date window), CC8 change management, Appendix A data residency, Appendix B subprocessors. Endpoint `GET /api/compliance/{org_id}/soc2.pdf?start=&end=` streams the PDF with Content-Disposition attachment. Default window: last 90 days. Audit row written on every download.
  • **Batch C Step 3 — Public SLA + MSA endpoint** — `GET /api/compliance/sla` returns the single source of truth for uptime targets (99.9%), incident response SLAs (15min/1h/4h/next-business-day), service credit table, MSA template URL, DPA URL, governing law (BC), and insurance limits ($2M cyber + $2M GL + $1M E&O). Frontend `/enterprise/sla` page reads from it. testid `enterprise-sla-page` + 4 sub-cards.
  • **21 new pytest cases** across A-4 + C1 (11 SAML/toast + 10 compliance). All green. Total iter 332b regression: 90 tests.
  • **Full active regression**: 407 / 407 green (was 386).
  • **Live smoke**: `/api/compliance/sla` returns `99.9% / Province of British Columbia, Canada` — confirmed via curl through localhost.
  • Fixed one MongoDB projection footgun: `find_one({...}, {"_id":0, "data_residency": 1})` returns `{}` (not None) when the projected field is absent, so `if not org` was treating a real-but-empty doc as "org not found". Switched to `if org is None`.
Blocker: none.
Production redeploy still pending (auth fix from iter 332b A-3 + everything since).
Deferred (intentional — separate slices):
  • Frontend Org switcher dropdown + Enterprise SSO/SCIM settings UI (backends ready).
  • Frontend Enterprise Admin → Data residency settings card + SOC 2 download button (backends ready, UI wiring next slice).
  • SAML SP-side AuthnRequest signing (currently AuthnRequest is unsigned — IdP-init flow works; SP-init signed flow is a future hardening).
  • RBAC complete wiring across ~80 routers (still a separate 2-3 day slice).
  • Real Stripe / Atlas cluster move automation for residency changes (currently queues, then manual ops).
Next:
  • Push to GitHub → redeploy aurem.live so the auth fix + Batch B + Batch C ship to production.
  • Frontend wiring for the new compliance endpoints (residency picker + SOC 2 download button on /enterprise/admin/overview).
  • Org switcher dropdown in AdminShell sidebar.
  • SP-side AuthnRequest signing (next SAML slice).
Cost: $0.00 USD (pytest + lint + curl smoke + 1 integration playbook call)
Branch: main
PIDs: []
Updated: 2026-02-24T09:00:00Z
---



---
Task: iter 332b C-2 — Trust Center page + Compliance admin UI + Org Switcher sidebar
Succeeded:
  • **Trust Center page** at `/enterprise/security` — public, no auth required. AUREM aesthetic (Cinzel "Trust, in writing." headline, JetBrains Mono eyebrow, orange→gold). Pulls live data from 3 endpoints (`/api/compliance/sla`, `/api/compliance/subprocessors`, `/api/compliance/regions`) and renders 4 sections:
    - Live status strip — uptime pill + 4 certification pills (PIPEDA, Law 25, SOC 2 in-progress, HIPAA on request)
    - Pre-built artifacts card — SOC 2 (links to admin sign-in), SLA page (`/enterprise/sla`), MSA template (msa.pdf), DPA (dpa.pdf)
    - Subprocessor list (7 rows from services/soc2_export.SUBPROCESSORS) — Vendor / Region / Purpose
    - Data residency options (3 regions) with compliance pills + DEFAULT gold badge on ca
    - Contact-sales CTA linking to `/enterprise`
    All 15+ data-testids verified via smoke screenshot (page=1, headline=1, 4 cards present, 7 subprocessor rows, 3 region rows). Procurement teams now have ONE URL to bookmark instead of bouncing between SOC 2 page + SLA page + subprocessor PDF + DPA PDF.
  • **2 new public endpoints**: `GET /api/compliance/subprocessors` and `GET /api/compliance/regions` — single source of truth for the Trust Center, fed from services/soc2_export.SUBPROCESSORS (one place to edit) + services/data_residency.REGION_TABLE.
  • **Enterprise Compliance admin page** at `/enterprise/admin/compliance` — fifth pill in EnterpriseAdminShell nav (icon: ShieldCheck). Two responsibilities:
    - Residency picker: 3-tile grid (CA / US / EU). Click a tile → "Queue migration" button → POSTs to `/api/compliance/{org_id}/residency`. Shows current region + effective-since date. Banner reports the queued ETA ("5–10 business days").
    - SOC 2 download: date pickers default to last-90-days. Button streams the PDF via fetch+blob (so Authorization header survives), filename `aurem-soc2-{org}-{date}.pdf`.
    - Org selector dropdown when admin owns >1 orgs. Empty-state banner if admin has 0 orgs.
    - testids: `compliance-residency-card`, `compliance-soc2-card`, `compliance-region-${code}`, `compliance-residency-save-btn`, `compliance-soc2-download-btn`, `compliance-soc2-start`, `compliance-soc2-end`, `compliance-org-selector`.
  • **Org Switcher sidebar component** at `/app/frontend/src/platform/OrgSwitcher.jsx` — drops into AdminShell sidebar (above the HUD strip). Lists orgs from `/api/orgs/me`, shows active one + role (caps-letterspaced eyebrow), dropdown with check-mark on selected, POSTs to `/api/orgs/switch` on click. Auto-hides when admin has 0 orgs (silent — no visual noise on single-tenant deployments). testids: `org-switcher`, `org-switcher-btn`, `org-switcher-dropdown`, `org-switcher-row-{org_id}`.
  • **9 new pytest cases** covering the 2 new endpoints + source-level wiring sanity for all 3 new frontend pieces. All green.
  • **Full active regression**: 416 / 416 green (was 407, +9 new). Backend boots clean.
  • Live smoke + screenshot at `/enterprise/security` confirms: Cinzel headline rendered, 5 status pills, 4 artifact rows, 7 subprocessor rows, 3 region rows — all populated from real backend endpoints.
Blocker: none.
Production redeploy still pending (everything from iter 332b A-3 onward).
Deferred:
  • SAML SP-side AuthnRequest signing.
  • RBAC complete wiring across ~80 routers.
  • Real Atlas cluster-move automation for residency changes (currently manual ops).
  • Enterprise SSO/SCIM settings UI (`/enterprise/admin/sso` page — backend already shipped).
Next:
  • Push to GitHub → redeploy aurem.live so Trust Center + auth fix + Batch B + Batch C all ship to production.
  • Enterprise SSO/SCIM settings UI page (so admins can paste IdP metadata + mint SCIM tokens from the browser instead of curl).
  • SAML SP-side AuthnRequest signing.
Cost: $0.00 USD (lint + pytest + 1 screenshot)
Branch: main
PIDs: []
Updated: 2026-02-24T10:30:00Z
---



---
Task: iter 332b C-3 — Footer link to Trust Center + SSO/SCIM settings UI + SOC 2 lead gate
Succeeded:
  • **Footer link** — homepage `<footer>` now has 2 new entries in the links row: "Trust Center" → `/enterprise/security` and "SLA & MSA" → `/enterprise/sla`. testids `footer-link-trust-center` + `footer-link-sla`. Turns Trust Center into a passive lead magnet for SEO-driven security searches without any other change to the marketing site.
  • **Enterprise SSO & SCIM settings page** at `/enterprise/admin/sso` (5th nav pill, Lock icon). Two stacked cards:
    - SAML config card: provider dropdown (Okta / Azure AD / Google / OneLogin / generic), IdP entity ID, IdP SSO URL, IdP X.509 PEM textarea, status dropdown (pending / active / disabled), default-role dropdown, save button. Shows a read-only "Paste these into your IdP" box with the auto-derived SP entity ID + ACS URL once saved.
    - SCIM token card: name input → "Issue token" button → reveal-once banner with Copy button (saves cleartext to clipboard). Table below lists existing tokens with token_preview, scopes, created/last-used dates, and per-row Revoke button (with confirm prompt).
    - "Test connection" button hits `GET /api/saml/{org_id}/metadata` and reports `✓ SP metadata is reachable` if the XML parses.
    - Org selector dropdown when admin owns more than one org.
    - All testids verified: `sso-saml-{card,provider,entity-id,sso-url,cert,status,default-role,save-btn,test-btn,banner}`, `sso-sp-metadata-box`, `sso-scim-{card,name,issue-btn,reveal,copy-btn,list,row-{id},revoke-{id}}`.
  • **SOC 2 lead-gated sample endpoint** — new public route `POST /api/compliance/soc2/sample`. Prospect submits `{email, company, role?, notes?}`; backend validates email shape, writes to `enterprise_leads` with source=`trust_center_soc2`, fires a Telegram alert to the founder (best-effort), writes a `soc2_sample_lead_captured` row to `unified_audit_log`, then generates and streams a sample PDF (using the auto-upserted `sample_org_trust_center` org so the PDF has the real layout). Returns `X-Aurem-Lead-Id` header so the founder can correlate downloads.
  • **Trust Center modal** — the SOC 2 row's "Sign in →" button is now "Get sample →" which opens a glass-backdrop modal (`trust-lead-modal`) with email + company + role inputs. Submit → fetches the PDF as a blob → triggers browser download → shows the success banner ("The real one lives at /enterprise/admin/compliance once you're signed in. I'll be in touch.") in gold. ESC / backdrop-click / Close button all dismiss.
  • **9 new pytest cases** covering footer assertions, lead capture (real Mongo write + PDF magic bytes), invalid-email rejection, modal source wiring, and SSO page testid surface. All green.
  • **Full active regression**: 425 / 425 (was 416, +9). Backend boots clean.
  • **Live smoke** — curl `POST /api/compliance/soc2/sample` returned HTTP 200 with a 5490-byte PDF starting with `%PDF` magic bytes; lead row persisted; smoke screenshot of Trust Center still passes with all 15+ data-testids.
  • Fixed one async-loop footgun: TestClient + Motor share an event-loop bug in this codebase, so the lead-capture test calls the FastAPI route function directly via async invocation instead (same pattern as test_iter332b_enterprise_admin_ui.py).
Blocker: none.
Deferred (intentional, separate slices):
  • SAML SP-side AuthnRequest signing (still unsigned IdP-init flow).
  • Real Atlas cluster-move automation for residency changes.
  • RBAC complete wiring across ~80 routers.
  • Public "subprocessor changelog" RSS feed (so customers can subscribe to vendor-list updates).
Next:
  • Push to GitHub → redeploy aurem.live so the footer link, SSO settings page, and lead gate all ship to production. The auth fix from iter 332b A-3 is now 4 batches behind — every redeploy day costs.
  • SAML SP-side AuthnRequest signing (next SAML hardening).
  • Backfill historical rows from 5 legacy audit collections into `unified_audit_log`.
Cost: $0.00 USD (pytest + lint + curl smoke only)
Branch: main
PIDs: []
Updated: 2026-02-24T11:30:00Z
---



---
Task: iter 332b D-1 (Renewal nudges) + D-2 (SAML SP-side AuthnRequest signing) — FINAL BATCH before stop
Succeeded:
  • **Renewal Nudge cron** (D-1) — services/renewal_nudges.py. Daily 09:00 UTC APScheduler job scans `db.organizations` for orgs whose `contract_renewal_date` lands exactly in {90, 60, 30, 14} days. Fires a Telegram alert to the founder with org name, plan, MRR (if set), ARR estimate, renewal date, and a 3-bullet upsell playbook. Idempotent via `renewal_nudges_sent` collection keyed on (org_id, window_days, due_date) — re-runs on the same day are no-ops. Writes an `renewal_nudge_sent` row to unified_audit_log. Job registered in registry.py at the same point as ora_self_heal watchdog.
  • **SAML SP-side signing** (D-2) — services/saml_sp_keys.py. Generates a self-signed RSA 2048 + X.509 cert (10-year validity, CN="aurem.live SAML SP", O="Polaris Built Inc.", C="CA") on first call, persists to `db.saml_sp_keys` keyed on `key_id='aurem-sp'`. Single global SP keypair shared across all backend replicas. In-process cache for performance; `force_regen=True` rotates the cert and bumps `rotated_at` for ops.
  • **build_saml_settings now accepts (sp_cert, sp_key)** — when both are passed, `security.authnRequestsSigned=True` and `sp.x509cert`/`sp.privateKey` populate, plus `signatureAlgorithm=rsa-sha256` + `digestAlgorithm=sha256`. Strict IdPs (Azure AD with strict mode, Okta "Verify Signature: Required") now accept our AuthnRequests.
  • **SP metadata XML upgrade** — `/api/saml/{org_id}/metadata` now advertises `AuthnRequestsSigned="true"` and embeds a `<KeyDescriptor use="signing">` with our SP's X.509 cert body (stripped of BEGIN/END envelope). IdPs auto-import this and stop rejecting our signed requests.
  • **`/api/saml/{org_id}/login` SP-init flow** — was a stub returning the raw IdP URL. Now builds a properly signed AuthnRequest via `OneLogin_Saml2_Auth.login(return_to=...)` with our SP keypair + IdP cert + strict mode. Returns `{ok, redirect_to (contains SAMLRequest + RelayState), signed: true, relay_state}`. Falls back gracefully to the unsigned URL on any python3-saml exception so a misconfigured IdP doesn't 500 the UI.
  • **parse_acs_response also loads SP keypair** — so signed-message replies from IdPs (rare but spec-compliant) can be validated against our private key.
  • **15 new pytest cases** (renewal: 7, SAML signing: 8). All green. Renewal tests cover all 4 windows, off-window rejection, idempotency, audit row writing, run_tick summary, ISO/date/datetime parsing. SAML tests cover SP keypair generation, persistence, force-regen rotation, cert PEM-envelope stripping, signed-vs-unsigned settings, metadata XML embedding, and live SP-init redirect URL with `SAMLRequest=` query param.
  • **Full active regression**: 440 / 440 green (was 425, +15 new). Backend boots clean. All endpoints respond (health=200, orgs=401, saml=401, sla=200).
  • Fixed one event-loop footgun in the test fixture: had to wire `services.saml_sso.set_db` explicitly so `get_saml_config` saw the test database.
  • **HARD STOP after this batch — per founder's directive: "Then stop. Then STOP building new features."**
Blocker: none.
Deferred (intentional — outside the "stop after SAML signing" window):
  • Real Atlas cluster-move automation for residency changes.
  • RBAC complete wiring across ~80 routers.
  • Backfill historical rows from 5 legacy audit collections into unified_audit_log.
  • Public "subprocessor changelog" RSS feed.
  • SCIM PATCH partial-update + Groups endpoint.
Next:
  • **Push to GitHub → redeploy aurem.live.** This is the only remaining action item. Production is now 5 batches (A-3 auth fix → B → C → C-2 Trust Center → C-3 SSO settings + lead gate → D renewal + SAML signing) behind. Every day of delay leaks broken-logout sessions, blocks the Trust Center SEO funnel, and prevents the renewal nudges from firing on real customers.
  • After redeploy: instruct customers' IT teams to re-import the SP metadata XML so they pick up the new signed-AuthnRequest cert.
Backlog:
  • SP cert rotation playbook (current cert is 10-year; needs a calendar reminder at year 8).
Cost: $0.00 USD (pytest + lint + curl smoke only; cryptography lib already installed)
Branch: main
PIDs: []
Updated: 2026-02-24T12:30:00Z
---


---
Task: iter 332b D-6 — Founder bugfix batch (dev portal admin bypass + dashboard crash + smart sign-in + public overview wiring)
Succeeded:
  • **Admin → /developers bypass actually works now**. `routers/developer_portal_router.py::_current_dev` was trying `from utils.auth import _decode_token` — a symbol that does NOT exist. The bare `except Exception` swallowed the ImportError silently, so every platform-admin token hitting /api/developers/me got rejected with `invalid_or_expired_token`. Replaced the dead import with a direct `jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])` against the shared config. E2E proven: founder admin JWT now lands on /developers/dashboard with auto-provisioned `internal_admin` row (10M tokens, abuse_flagged=false). Verified via Playwright + curl.
  • **DevDashboard crash fixed**. `frontend/src/platform/developers/DevDashboard.jsx` referenced `purchases.length` and `purchases.map(...)` without ever declaring the state — every authed dashboard render threw a ReferenceError and the page either blanked or rendered partial. Added `const [purchases, setPurchases] = useState([])` + a useEffect that fetches `/api/developers/me/purchases`. Recent-purchases strip stays hidden (no crash) when array is empty.
  • **Homepage Sign In is now context-aware**. `AuremHomepage.jsx` `nav-link-login` button kept routing every visitor — including already-signed-in admins/devs — through the public login form. Added `handleSignIn(e)` that inspects platform_token / dev_jwt / aurem_customer_token (with `exp` claim validation), preventDefault's the Link, and routes to /admin/mission-control, /developers/dashboard, or /dashboard respectively. Anonymous visitors keep the default Link to="/login". E2E proven via Playwright: fake admin JWT → /admin/mission-control (24 nav items, ORA Command panel rendered).
  • **Homepage background already matches aurem.live**. Visual-diff Playwright screenshots of preview vs aurem.live: identical layout, same dark void + grid, same red radial glow, same Cinzel headline, same orange→gold gradient. No code change required — background was already in parity from iter 332b C-3.
  • **System Overview public mirror actually mounts**. `routers/system_overview_router.py::get_public_router()` was created in iter 332b D-4 but `routers/registry.py` only included `mod.router` (the admin one) — the public `_PUBLIC_ROUTER` exposing `GET /api/public/system-overview/stats` was orphaned and returned 404. Added a `if hasattr(mod, "get_public_router"): app.include_router(mod.get_public_router())` block right after the admin include — generic enough to catch any future router that exposes a public mirror. Live smoke: `{platform: {iteration: "332b", as_of: "MAY 24, 2026", ...}, public: true}`.
  • **12 new pytest cases** (`test_iter332b_d6_dev_portal_admin_bypass.py` x8 + `test_iter332b_d6_system_overview_public.py` x4). Covers: admin JWT auto-provisions idempotently, garbage/expired/non-admin tokens rejected, regression guard that the broken `_decode_token` import never returns, DevDashboard.jsx declares `purchases` state + calls the right endpoint, homepage handleSignIn checks all 3 storage keys + has /admin/mission-control + /developers/dashboard routes, public stats endpoint requires no auth + leaks no private counters, admin route still 401s on anon, registry source guard, public router prefix guard. All 12 green.
  • **Active iter 327d→332b regression: 680 / 680 GREEN** (was 676 last slice; +12 new cases all green, zero regressions).
  • **Backend boots clean** post-restart; /api/health=200, /api/public/system-overview/stats=200, /api/admin/system-overview/stats=401.
Blocker: none.
Deferred (intentional — outside the founder's "4 fixes then stop" window):
  • SAML SP-side AuthnRequest signing — already shipped iter 332b D-2.
  • Real Atlas cluster-move automation for residency changes.
  • RBAC complete wiring across ~80 routers (dedicated 2-3 day slice).
  • Legacy audit-collection backfill.
  • Service-account Google Calendar for shared staff calendar.
  • Friendlier 404 for stale ghost-* slugs.
Next:
  • Push to GitHub → redeploy aurem.live. Production is now 6 batches (A-3 → D-6) behind. Every redeploy day costs.
  • Once aurem.live ships D-6, founder can drop their existing admin token straight into /developers and the dashboard will populate. The blank-options bug + the dashboard crash both disappear.
Cost: $0.00 USD (pytest + lint + curl + 3 Playwright screenshots only; no LLM calls)
Branch: main
PIDs: []
Updated: 2026-05-24T03:40:00Z
---






---
Task: iter 332b D-14 + D-15 — Cloudflare 524 hardening + SSE streaming for dev chat
Succeeded:
  • **D-14 — Cloudflare 524 fix.** Founder hit "Unexpected token '<', '<!DOCTYPE'… is not valid JSON" on aurem.live/developers/dashboard. Root cause: OpenRouter `:free` model variants queue behind paid traffic; 3 ladder rungs × 45s = 135s worst case → Cloudflare cut the upstream at 100s and returned HTML 524, frontend exploded on JSON.parse. Three-part fix:
       1. Per-call timeout dropped to 28s → 3 × 28 = 84s, safely under 100s ceiling.
       2. Dropped `:free` suffix from rungs 2+3. Now `meta-llama/llama-3.3-70b-instruct` + `mistralai/mistral-7b-instruct` (paid — pennies per million tokens, no queueing).
       3. Frontend `await r.json()` replaced with `await r.text() → try JSON.parse(raw) catch → friendly message`. On 524 user sees: "The free-tier model took too long. Please rephrase your message or try again — usually clears in 30 seconds." Never raw "Unexpected token <".
     Also trimmed conversation history budget: `.slice(-6)` × 2000-char clip per message (was 12 × unlimited). Long histories were a major contributor.
  • **D-15 — SSE streaming**. New `POST /api/developers/cto/chat/stream` endpoint returns `text/event-stream` of JSON events: `meta → token (1..n) → done` (or `error` on failure). Backend uses httpx async streaming + OpenRouter's native SSE; falls through the 3-model ladder per chunk-iter so partial primary failures still recover seamlessly. `X-Accel-Buffering: no` header tells nginx to flush chunks immediately. Frontend uses `r.body.getReader()` + `TextDecoder` to read chunks live and append each token to the trailing assistant bubble — typing-out UX identical to ChatGPT. Time-to-first-token went from ~3s to ~400ms; total time for a long reply unchanged but feels 10× faster.
  • **BYOK path stays non-streaming** (Anthropic/Gemini have different SSE formats, not worth the LOC tonight). BYOK users still get the full reply as a single `token` event so the frontend stays generic.
  • **All error paths emit a single `error` SSE event** with optional `action_required:add_byok` → frontend renders the upgrade modal instead of throwing.
  • **9 new pytest cases** (D-14 × 3 + D-15 × 6): timeout-budget invariant, no-`:free`-rungs guard, safe-parse wiring, happy-path stream emits meta→tokens→done, free-tier ladder falls through on primary failure, token wall emits single error event, all-rungs-fail emits trailing error with no done, frontend uses correct stream endpoint + reader, router exposes StreamingResponse with `text/event-stream` + `X-Accel-Buffering`.
  • **Full active regression iter 327d → 332b D-15: 721 / 721 GREEN** (was 712; +9 new; zero regressions).
  • **Live smoke**: curl -N against `https://.../api/developers/cto/chat/stream` returned the literal SSE wire format: `data: {"type":"meta", ...}\n\ndata: {"type":"token", "content":"ONE"}\n\n...\ndata: {"type":"done"}` — 4 token chunks for a 4-word answer, all over real OpenRouter → DeepSeek V3.
Blocker: none. **HARD STOP per founder directive.**
Next:
  • **Push to GitHub → redeploy aurem.live.** Production is now 11 batches behind. After redeploy: (a) "Unexpected token <" error is gone forever — replaced by friendly retry message; (b) all chat replies stream in like ChatGPT.
  • OPENROUTER_API_KEY already updated in production secrets earlier this session — no further secret changes needed.
Cost: ~$0.001 USD (a few OpenRouter DeepSeek round-trips during live smoke; less than 0.1¢).
Branch: main
PIDs: []
Updated: 2026-05-24T21:00:00Z
---



---
Task: iter 332b D-11 — Free tier moved to OpenRouter (one key, three-model ladder)
Succeeded:
  • **One LLM key for free tier**: OPENROUTER_API_KEY. Removed standalone DEEPSEEK_API_KEY and GROQ_API_KEY from /app/backend/.env — no longer needed. OpenRouter handles model selection.
  • **Three-model fallback ladder** in services/dev_cto_chat.py: 1) `deepseek/deepseek-chat` ($0.27/1M, primary), 2) `meta-llama/llama-3.3-70b-instruct:free` (fallback), 3) `mistralai/mistral-7b-instruct:free` (last resort). If primary 429s or 503s, fallback fires; if both fail, mistral free saves the day. Returns the actual label that answered so the dashboard tier badge stays honest.
  • **BYOK path unchanged** — anthropic / openai / deepseek / gemini / groq / mistral / custom still routed direct to their own native endpoints. Anthropic still wins when present; OpenRouter is never called when BYOK is configured (asserted in test).
  • **Token wall unchanged** — `{ok:false, error:"token_wall", action_required:"add_byok"}` still fires when balance hits zero.
  • **UI copy updated** — DevCtoChatPanel tier badge now reads "FREE TIER · OpenRouter (DeepSeek → Llama → Mistral)"; /developers/connect banner explains the OpenRouter routing strategy.
  • **18 new pytest cases** in test_iter332b_d11_openrouter_free_tier.py. Retired the 17-test D-10 file (legacy DeepSeek-direct strategy). Coverage: free-tier key reads OPENROUTER_API_KEY, FREE_TIER_MODELS ladder is exactly 3 deep with the correct order, dispatch returns first success without hitting fallback, dispatch falls through to llama on primary failure, dispatch falls through to mistral on both failures, dispatch raises clean error when all three fail, BYOK preference still wins, no Emergent LLM key reference, end-to-end happy path returns provider=deepseek + tier=free + correct token deduction, token wall returns add_byok, BYOK overrides free tier (asserts OpenRouter never called), missing OPENROUTER_API_KEY returns no_llm_configured + add_byok, env file shape (OPENROUTER present, DEEPSEEK/GROQ absent), UI copy reflects new strategy on both pages.
  • **Full active regression iter 327d → 332b D-11: 712 / 712 GREEN** (was 711; +18 D-11 new − 17 D-10 retired = +1 net; zero regressions).
  • **Live smoke proven**: `POST /api/developers/cto/chat` with admin JWT → `{ok:true, reply:"Python decorators are functions that modify the behavior of other functions or methods without changing their actual code.", provider:"deepseek", tier:"free", tokens_remaining:9999998, low_balance:false}`. Real OpenRouter → DeepSeek V3 round-trip with sub-second response.
Blocker: none. **HARD STOP per founder directive.**
Next:
  • **Push to GitHub → redeploy aurem.live.** Production is now 10 batches behind (A-3 → D-11).
  • OPENROUTER_API_KEY must already be set in production secrets (founder confirmed it is). No env changes required on redeploy.
Cost: ~$0.0001 (a few free-tier OpenRouter test calls + 1 real DeepSeek V3 round-trip; below 1¢)
Branch: main
PIDs: []
Updated: 2026-05-24T17:25:00Z
---



---
Task: iter 332b D-10 — Developer-portal CTO chat + Free tier (DeepSeek + Groq) + Expanded BYOK
Succeeded:
  • **AUREM CTO chat panel live on /developers/dashboard** — the founder's #1 gap ("I didn't see any window to write prompts or ideas"). Frontend `DevCtoChatPanel.jsx` mounts directly below the metrics tiles, posts to `POST /api/developers/cto/chat`, streams replies into a scrollable message list. Includes auto-grow textarea, Enter-to-send, busy state, error surface, and tier badge ("FREE TIER · DEEPSEEK + GROQ FALLBACK" or "BYOK · provider").
  • **Free tier active immediately on signup, ZERO Emergent LLM dependency.** New `services/dev_cto_chat.py` routes free-tier requests to DeepSeek V3 ($0.27 / 1M tokens) using `DEEPSEEK_API_KEY` env var. If DeepSeek raises (rate limit, outage, missing key), automatic fallback to Groq Llama 3.3 70B via `GROQ_API_KEY`. Hard test guard `test_dev_chat_service_never_imports_emergent_llm` ensures nobody re-introduces the Emergent key into the dev portal.
  • **BYOK preference order**: anthropic > openai > deepseek > gemini > groq > mistral > custom. If a dev has multiple keys, the smartest model fires first.
  • **Native multi-provider support**: OpenAI / DeepSeek / Groq / Mistral go through the OpenAI-compatible `/chat/completions` shape; Anthropic uses its native `/v1/messages` endpoint; Gemini uses the native `generateContent` REST API. All implemented in one small dispatcher with provider-specific calls.
  • **Token-low popup on dashboard chat** — when `tokens_remaining < 100` after a reply, a modal slides in: "Running low — add a DeepSeek key" with two CTAs: "Add my DeepSeek key →" (deep-link to /developers/connect) or "Later" (dismiss, won't re-pop in the same session). Also fires when the backend returns `action_required: add_byok` (token wall).
  • **Token wall logic returns clean machine codes** — `{ok: false, error: "token_wall", action_required: "add_byok", message: "..."}` for 200 OK so the frontend renders the upgrade modal nicely (no try/catch on 4xx).
  • **/developers/connect rebuilt as "optional setup"** — big amber free-tier banner up top with a direct "Open chat" CTA; GitHub + VS Code marked "(optional)" explicitly; full BYOK provider table with cost-per-1M-tokens column (DeepSeek $0.27 highlighted as "RECOMMENDED — cheapest, ~GPT-4o quality"; Groq "Free tier"; Gemini $0.35; OpenAI $0.60; Anthropic $1.00; Mistral $0.20); every provider row has a "Get key →" deep link to the right console; "+ Add a custom OpenAI-compatible provider" toggle reveals 3 inputs (endpoint URL, model name, API key) — perfect for Together / Fireworks / Ollama-hosted endpoints.
  • **BYOK backend schema expansion** — `ByokBody` now accepts `anthropic | openai | deepseek | gemini | groq | mistral | custom_url | custom_model | custom_api_key`. `save_byok_keys` validation widened. 331d's "openai is wrong provider" guard rewritten to assert the new validation (rejects empty / unrecognised fields, accepts openai).
  • **conftest.py boot-grace fix** — pytest grouped runs were flaking because `os.environ.setdefault("REACT_APP_BACKEND_URL", "http://localhost:8001")` routed admin negative tests through the localhost ingress path, which middleware/health_probe.py answers with 204 during the first 90s of every restart. conftest now reads `/app/frontend/.env` first and only falls through to localhost if no preview URL is configured. Killed the entire 8-test boot-grace flake class.
  • **17 new pytest cases** (test_iter332b_d10_dev_cto_chat.py). Cover: free-tier prefers DeepSeek, falls back to Groq, returns None when no keys, BYOK preference picks anthropic first, BYOK falls through, empty BYOK handled, NO Emergent LLM in chat path, end-to-end chat happy path with mocked dispatch + token deduction, token wall returns add_byok, BYOK overrides free tier, save_byok accepts openai/groq/mistral, save_byok accepts custom endpoint, save_byok rejects empty, DevDashboard mounts chat panel, chat panel uses correct endpoint + all testids, /developers/connect shows free-tier banner + all 6 providers + custom toggle + cost columns + GitHub/VSCode optional labels, env vars present.
  • **Full active regression iter 327d → 332b D-10: 711 / 711 GREEN** (was 691 last slice; +20 new cases all green; zero regressions thanks to the conftest fix).
  • **Live smoke proven**: Backend boots clean. /api/health=200. /api/developers/cto/chat with admin JWT returns a real Groq Llama 3.3 reply ("What's your engineering question or problem you're trying to solve?", provider=groq, tier=free, tokens_remaining=9999999, low_balance=false). Frontend Playwright confirms all 6 chat testids mount on /developers/dashboard + the welcome message renders + the tier badge says "FREE TIER · DEEPSEEK + GROQ FALLBACK".
  • **Env-var slots shipped** — `DEEPSEEK_API_KEY=""` and `GROQ_API_KEY=""` added to /app/backend/.env. Founder fills these in via the Emergent secrets UI before redeploy. Currently DeepSeek is empty in preview so the fallback path is what actually responds; once the real DeepSeek key lands in production, primary path kicks in automatically.
Blocker: none. **HARD STOP per founder directive — no more features.**
Deferred (intentional):
  • Auto-provision GitHub OAuth on signup (needs an Emergent OAuth app — separate slice).
  • Auto-provision a free MongoDB sandbox per dev (needs Atlas API key + ~500 LOC).
  • Real Atlas cluster-move automation, legacy audit backfill, RBAC slice, friendlier 404 for stale ghost-* slugs, service-account Google Calendar.
Next:
  • **Push to GitHub → redeploy aurem.live.** Production is now 9 batches behind. Until redeploy: 5 real devs still hit the admin-bypass crash, the dashboard crash, the missing chat panel, and the bouncing Sign-in button.
  • **Fill DEEPSEEK_API_KEY in production secrets** before redeploy so the primary path is live. Free tier will work either way (Groq fallback) but DeepSeek is the cheaper / smarter daily driver.
Cost: $0.00 USD (pytest + lint + curl + 1 Playwright screenshot + 1 live LLM round-trip via free-tier Groq, which is genuinely free).
Branch: main
PIDs: []
Updated: 2026-05-24T16:50:00Z
---



---
Task: iter 332b D-7 + D-8 — Admin dev-signups page + 24h sparkline + CSV export (HARD STOP)
Succeeded:
  • **D-7 — Admin developer-signups page** at /admin/developer-signups. Table of every dev portal signup with email · name · plan · verified ✓ · GitHub handle · tokens remaining · signup date. Filter box + "Copy N emails" clipboard button. Abuse-flagged rows tinted red. Lives inside AdminShell sidebar.
  • **D-7 — Real-time founder Telegram nudge** on every successful OTP verify. Fires send_telegram_alert(alert_type="new_dev_signup", fingerprint=email) with email, name, plan, deep link back to admin page. Fire-and-forget. Dedup by email.
  • **D-7 side-fix** — `_ensure_admin` was catching ALL exceptions including HTTPException(401) and re-raising as 503. Now lets 401/403 bubble correctly.
  • **D-8 — 24h sparkline on cockpit Pulse tile** + new GET /api/admin/developers/timeseries returning 24 hourly buckets + total_24h. Inline SVG sparkline rendered in DeveloperPortalPulseTile with amber fill, 24h count column, and "View all →" deep link.
  • **D-8 — CSV export** via new GET /api/admin/developers/export.csv. Streams text/csv with attachment headers + date-stamped filename. Same projection as list endpoint so secrets never leak.
  • **11 new pytest cases** (D-7 x5 + D-8 x6). All green. Full active regression iter 327d → 332b D-8: **691 / 691 GREEN** (was 680; +11; zero regressions).
  • **Sneaky middleware quirk documented** — middleware/health_probe.py returns 204 to all /api/admin/* requests from localhost during the first 90s of boot grace. Tests bypass via httpx.Client thread call against external preview URL.
Blocker: none. **HARD STOP per founder directive — no more feature work.**
Deferred (intentional):
  • Real Atlas cluster-move automation, legacy audit backfill, RBAC slice across ~80 routers, SP cert rotation playbook, public subprocessor-changelog RSS feed, friendlier 404 for stale ghost-* slugs, service-account Google Calendar, ConsentToggleCard cleanup, SCIM PATCH + Groups.
Next:
  • **Push to GitHub → redeploy aurem.live.** Production is 8 batches behind (A-3 → D-8).
Cost: $0.00 USD (pytest + lint + curl + 2 Playwright screenshots; no LLM)
Branch: main
PIDs: []
Updated: 2026-05-24T04:12:00Z
---
