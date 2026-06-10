# AUREM — Product Requirements Document

> Last updated 2026-06-10 (iter D-78)

## Vision

AUREM is Canada's Autonomous Business Operating System for SMBs.
Polaris Built Inc., Mississauga, Ontario. PIPEDA + Law 25 + GDPR
compliant. Sovereign data residency, plain-English communication
("Rule Zero"), zero silent failures.

## Personas

- **Founder (Tejinder)** — operates entire platform via ORA / AUREM CTO chat.
- **Canadian SMB customer** — books jobs, recovers leads, runs ops on autopilot.
- **Developer (BYOK tenant)** — builds with the AUREM CTO API using their own LLM keys.
- **Enterprise procurement** — needs SOC 2, SLA, MSA, SSO, SCIM, residency.

## Core Requirements

1. **Rule Zero** — plain English, 1–3 sentences in chat. No JSON/code/tracebacks.
2. **Test-driven** — pytest required for every iter; full active suite must stay green.
3. **Portability** — every URL/credential lives in .env; production ≡ preview.
4. **PIPEDA + Law 25 default** — Canadian residency, anonymized network telemetry, consent.
5. **No silent failures** — every error must surface in unified_audit_log.

## What's been implemented (chronological highlights)

### iter D-78 (2026-06-10) — Campaign Command Dashboard (first feature on the clean foundation)

**P1 — Real Funnel Metrics shipped (zero mocks, every byte from live Mongo):**
- New `routers/campaign_funnel_router.py` exposes 3 admin endpoints:
  - `GET /api/admin/campaigns/funnel` — all campaigns at once with grand totals
  - `GET /api/admin/campaigns/funnel/{cid}` — drill-down (use `__unattributed__` for campaign_id=None bucket)
  - `GET /api/admin/campaigns/funnel/{cid}/timeline?days=N` — touches-per-day zero-filled sparkline series
- **Metric sources (all real, all auditable):**
  - **Touches** = `campaign_leads.outreach_history` $unwind, bucketed by channel ∈ {email, sms, whatsapp, call}
  - **Opens** = same collection, channel ∈ {report_view, sample_view} — real pixel hits from the D-75 Part 1 deliverable links
  - **Replies** = `inbound_replies.from` ∈ campaign's lead emails
  - **Conversions** = `campaign_leads.status ∈ {contacted, website_generated, subscribed, won}` PLUS `platform_users.email` matches against lead emails
  - **Rates** = honest division with `None` fallback when denominator = 0 (UI renders "—", not NaN)
- Each metric carries its `source_collection` field so the founder can audit any number back to the underlying aggregation.

**Frontend — `platform/CampaignCommandDashboard.jsx` mounted at `/admin/campaign-command`:**
- Hero strip of 5 tiles (Touches / Opens / Replies / Conversions / Leads) with grand totals
- Per-campaign cards collapsible — expand to see channel breakdown bars (Email/WhatsApp/SMS/Call), engagement breakdown, and 14-day sparkline
- "Source: campaign_leads.outreach_history" footers expose the data lineage on the card
- Empty state has an honest message about waiting for the daily scrape, not a fake placeholder
- All interactive elements have `data-testid` for testability

**Tests (all green, all real I/O):**
- `tests/test_d78_campaign_funnel.py` — 8 pytests covering auth (401/403), synthetic-lead aggregation correctness, drill-down, `__unattributed__` sentinel, 14-bucket zero-filled timeline, rate math, safe division on empty campaign
- Frontend E2E — 14/14 Playwright assertions pass via testing_agent_v3_fork (hero tiles populated, card expand works, sparkline renders, refresh works)

**Code-quality fixes from the post-test audit:**
- Removed dead phone-matching branch in replies query (was collecting phones into a set that never reached the inbound_replies $or clause)
- Fixed N+1 `list_collection_names()` admin call — `list_funnels()` now pre-fetches once and passes the cached set into each `_funnel_one()`
- Added logger warning when ≥10 events land in `other_outreach_events` so a future channel like `linkedin` doesn't silently slip past TOUCH_CHANNELS/OPEN_CHANNELS

**Live numbers verified end-to-end against prod data:**
- campaign_id `aurem-acquisition-001`: 1,464 leads · 4,752 touches (email 3,298 / wa 684 / sms 268 / call 502) · 37 opens (report_view 25 / sample_view 12) · 0 replies (no matches yet) · 4 conversions · 0.78% open rate · 0.27% conversion rate

### iter D-77 (2026-06-10) — Branded Repair Plan Email · "Is this flow real?" Audit

**P2 — HTML Repair Plan Email shipped:**
- Built `/app/backend/templates/repair_plan_email.html` — paid-deliverable-grade dark theme with Cinzel display headers, severity-coded item cards (HIGH red / MEDIUM amber / LOW green), score strip, monospace code blocks for the LLM diagnosis + fix, CASL-compliant footer + unsubscribe link.
- Added `services.brand_emails.render_repair_plan(customer_email, website, audit, plan, first_name)`. Handles HTML escaping of LLM bodies (so `<script>` tags can't render), unknown severity fallback to MEDIUM, empty-plan honest notice ("no actionable items"), score color thresholds (≥80 green, ≥50 amber, else red).
- Wired into `routers/customer_website_repair_router._email_repair_plan` — now sends BOTH plaintext (deliverability fallback) AND branded HTML. Returns `html_sent: bool` in the result so the caller surfaces failure honestly. New helper `_lookup_first_name(email)` enriches the greeting.
- 8/8 pytests in `tests/test_d77_repair_plan_email.py` — covers render correctness, severity tones, escape protection, empty plan fallback, real Resend payload structure.

**P0 — "Is this flow real?" audit completed → `/app/memory/D77_FLOW_AUDIT_REPORT.md`:**
- **Campaign blasts** (WhatsApp, SMS, Email, Voice, daily scrape, auto-blast cron) — all real engines (WHAPI, Twilio, Resend, Retell). 1 stale docstring fixed in `blast_service.test_whatsapp` (claimed "or mock if key missing" but always routed through real engine).
- **CTO agent outputs** (12-phase chat, run-scout, import-leads, run-blast, verify, learning, codebase) — all real LLM + real GitHub + real `/api/version` polling. The `cto_verify_router` already has anti-hallucination patterns that REJECT placeholder code.
- **Referrals** — pure MongoDB reads, zero faked counts. 97 LOC, every line honest.
- **Billing** — Stripe webhook signature verified (Bug-fix #76 closed the unverified loophole), Customer.retrieve goes through `asyncio.to_thread` (Bug-fix #81), real price IDs from env.
- Verdict: **zero theater code** remaining across all 4 audited surfaces. The cleanups from D-73 + D-75 Part 1 held.

**P3 (deferred)** — Twilio SMS notification on new pending_approvals — skipped per founder directive. Twilio currently RED (401) per creds_health; building on a stale dep is backwards. Revisit post-rotation.

### iter D-76 (2026-06-10) — Route Dedupe Final · Approval Inbox · Codebase Cleanup

**P0 — All 17 cross-handler route duplicates eliminated:**
1. `server.py` liveness routes deleted (`/health`, `/ready`, `/api/health`, `/api/platform/health`) — canonical lives in `bootstrap/health_routes.py`
2. `server.py` inline `founder_saves_router` block removed (was double-registering via registry) — 3 self-dupes gone
3. `routers/server_misc_routes.py` `/auth/forgot-password|reset-password|verify-reset-token` deleted — canonical is `routes/auth.py` (sha256-hashed MongoDB token store)
4. `routers/aurem_routes.py` `POST /chat` deleted — canonical is `routers/aurem_chat.py` (12-phase ORA pipeline + JWT + 45s timeout)
5. `routers/inbound_email_router.py` `POST /api/email/inbound` + `/health` deleted — canonical is `routers/email_inbound_router.py` (Cloudflare-Worker → ORA reply pipeline)
6. `routers/enterprise_engine.py` `GET /audit` deleted — canonical is `routers/enterprise_router.py` (unified_audit-backed)
7. `routers/v2_customer_actions_router.py` `POST /api/incident/resolve/{id}` alias deleted — canonical is `routers/incident_router.py` (with playbook-learning)
8. `routers/self_audit_router.py` `POST /api/self-audit/run` deleted — canonical is `routers/autonomy_router.py` (5-agent system that frontend AutonomyLog.jsx depends on)
9. `routers/google_oauth_callback.py` **file deleted** — canonical is `routes/auth.process_google_callback` (intelligent admin-vs-customer routing)
10. `routers/ai_platform_router.py` `/health` deleted (was the 3rd of the 3-way `/api/platform/health` conflict)

**P0 — `scripts/wire_all_set_db.py` executed:** 323 router modules now have their `set_db()` auto-wired via the generated `routers/_set_db_wire_list.py`. The 193-unwired backlog is eliminated. `AUREM_STRICT_SETDB_WIRING=true` env gate is in place — flip it on whenever the next stale wiring slips in.

**P0 — `z_image_router.py` file deleted:** 4 dead endpoints behind a silent try/except (gradio_client missing). Removed from registry, `_registry_config` skip list, `endpoint_audit_router` prefix allowlist.

**P0 — 2 orphan Mongo collections dropped:** `awb_cleanup_log` and `site_monitor_admin_log` (1 doc each, zero code references).

**P1 — Approval Inbox built (backend + frontend):**
- Backend: `routers/autonomous_repair_admin_router.py` adds `GET /list` (joins pending_approvals with linked ora_cto_proposals inline) and `POST /approve/{id}` (flips status, writes audit row, refuses if no linked proposal with 409). Reject was already present.
- Frontend: `platform/ApprovalInboxPanel.jsx` mounted on `/admin/pillars-map` between `AutonomousRepairPanel` and `PendingCodeFixesPanel`. One-click approve/reject, expandable LLM diagnosis + suggested fix inline, only-pending filter, refresh button, full empty state. Every interactive element has data-testid.

**Tests added/passing:**
- `tests/test_d76_dedupe.py` — 9 tests (no-dupes, deleted-handlers-gone, canonical-active per route, file-deletions verified)
- `tests/test_d76_approval_inbox.py` — 6 tests (real JWT, real Mongo, list/approve/reject/audit-trail)
- 23 total green across D-75 + D-76 suites

**Lock-in validator updated:** locked-files count went 14 → 13 (google_oauth_callback.py removed from the manifest).

### iter D-60a (2026-06-02) — Production deploy hardening (post-mortem fix)

**Symptom:** Prod deploy logs showed backend booting fine, serving 200s for ~1 minute, then nginx returning `connect() failed (111: Connection refused)`. Root cause was NOT a structural compile/env issue — the `deployment_agent` correctly said PASS on that. The killer was at runtime: `prod_guard.is_production_pod()` returned **False** in prod because the only signals it checked (`AUREM_ENV`, `APP_URL`, `DISABLE_LEGION`) were not set on the deployed pod. With prod undetected, `SovereignWarmer` + `ghost_scout` auto-loop + Ollama health pings + ora_agent circuit breaker poll all ran flat-out trying to reach unreachable preview-only hosts. Combined event-loop pressure most likely OOM-killed the container.

**Fix (3 code changes):**
1. **`services/prod_guard.py`** — broadened detection: any of these flips production mode on
   - `MONGO_URL` contains `mongodb+srv://` (managed Atlas — only ever used in prod)
   - `PREVIEW_PROXY_URL` / `DEPLOY_URL` / `CF_PAGES_URL` contains `deploy.emergentcf.cloud` or `aurem.live`
   - Existing `AUREM_ENV`, `APP_URL`, `DISABLE_LEGION` still honored
2. **`services/ghost_scout_iproyal.py`** — explicit short-circuit in `ghost_scout_loop`: returns early in prod unless `GHOST_SCOUT_PROD_LOOP=true`. Google Places API key on prod has billing disabled, so every cycle was returning REQUEST_DENIED anyway.
3. **`backend/tests/test_prod_guard_d60a.py`** — 7 regression pytests covering every new detection signal + the ghost-scout guard.

**Cascading wins** (already gated via `is_production_pod()` upstream):
- SovereignWarmer skips its 240s ping loop
- ora_agent circuit-breaker stops hammering localhost Ollama
- Several other preview-only background tasks short-circuit

### iter D-60 (2026-06-02) — BugCatch · internal QA bug capture

**Floating bug-report widget (admin only)** mounted inside `AdminShell`:
- Bottom-right 🐛 button on every `/admin/*` page
- Click opens modal that captures: DOM screenshot via `html2canvas`,
  annotation overlay (pen / arrow / text in 4 colors), last 200 console
  logs, last 50 network calls (fetch interceptor), URL + viewport + UA
- POSTs to `/api/admin/bug-reports`
- Annotations baked into the screenshot before send

**Admin reports inbox** at `/admin/bug-reports` (Settings sidebar):
- List with severity dot + status filter (open / investigating / resolved / won't_fix)
- Stats counters at top
- Detail drawer with screenshot, AI root cause, console logs, network calls
- Status flipper

**Backend** (`backend/services/bug_catch.py`, `backend/routers/bug_catch_router.py`):
- Admin-JWT gated CRUD: POST submit, GET list/stats/detail, PATCH status
- Screenshot >2 MB dropped honestly (note kept)
- Logs/network capped at 200/50
- Per-report **AI root cause** via existing free-tier OpenRouter ladder
  (`_dispatch_free_tier`) — DeepSeek primary, no extra cost
- Per-report **email alert** to founder via existing Resend wrapper
- Mongo collection `bug_reports`, boot-grace middleware excluded

**Tests:** 15/15 in `test_bug_catch_d60.py` + 71/71 across the recent ring.
Live verified: AI tagged a test bug correctly — *"The API key issuance
likely failed due to an undefined response array being accessed in
the AdminApiKeysPage component."*

### iter D-59 (2026-06-01) — Campaign Health + Public AUREM API (commercialization)

**Part A — Campaign Health + Autonomous Autofix loop**
- New admin page at `/admin/api-keys` → `/admin/campaign-health` tracks
  11 outreach components (Ghost Scout, Auto-Blast, Resend, Twilio, WHAPI,
  Proactive ORA, Template Perf, Daily Brief, Lead Pool, Emergent LLM,
  Resend Webhook) with 🟢/🟡/🔴 status + root cause + autofix button.
- Per-component autofixes wired: `trigger_scout_run`,
  `trigger_blast_cycle`, `topup_via_scout`, `send_morning_brief`.
- "Fix All" walks the report. 30s timeout per fix. Every attempt logged
  to `campaign_autofix_log`. Honest results — never claims fixed when
  it isn't.
- 15 pytests (`backend/tests/test_campaign_health_d59.py`).

**Part B — Public AUREM API for commercialization**
- New router `/api/v1/public/*` with three scoped endpoints:
  - `POST /ora/chat`        — scope `ora_chat`
  - `POST /cto/chat`        — scope `cto_chat`
  - `GET  /leads/lookup`    — scope `leads_read`
  - `GET  /health`          — anonymous sanity ping
- Bearer-key auth (`aurem_sk_live_<43-urlsafe>`). Server stores only
  the **sha256 hash** — raw secret returned ONCE on issue.
- Per-key daily rate limit, counter resets at UTC midnight, all calls
  logged to `aurem_api_usage`.
- Admin manager router `/api/admin/public-api-keys` (issue / list /
  revoke / 7-day usage) gated by admin JWT.
- Admin UI at `/admin/api-keys` (Settings sidebar) with one-time secret
  reveal card, scope checkboxes, daily-limit input, revoke confirm,
  usage panel.
- Boot-grace middleware excluded for new admin prefixes so the UI gets
  real data instead of `204 No Content` during pod warmup.
- Founder primary key issued live (preview Mongo) — credentials in
  `test_credentials.md`.
- 15 pytests (`backend/tests/test_public_api_d59.py`).
- Full usage guide at `/app/memory/PUBLIC_API_USAGE.md` (cURL +
  Python examples for founder's other projects).

### iter D-49 (2026-05-28) — CTO real-execution tools + blast unstuck

- **CTO Tools Router** (`routers/cto_tools_router.py`): 4 real-execution endpoints
  the chat can invoke instead of only planning:
  - `POST /api/developers/cto/tools/run-scout` → harvest_leads via OSM/Places
  - `POST /api/developers/cto/tools/import-leads` → bulk insert with dedup + channel-gating
  - `POST /api/developers/cto/tools/run-blast` → force auto_blast_engine cycle
  - `GET  /api/developers/cto/tools/db-stats` → live counts for CTO context
  - Every call audited to `cto_tool_runs` collection.
- **Settings whitelist expanded** (`platform_secrets_router._ALLOWED_SECRETS`):
  added `SECURITY_ALERT_SLACK_WEBHOOK` + `SECURITY_ALERT_EMAIL`.
- **Channel-gating reclamation** (one-shot script): flipped 25 emails
  + 151 SMS gating to True for fresh leads that had valid contact info
  but were locked out by stale verification scores.
- **Ghost Scout live harvest**: ran 30 queries across beauty / wellness
  verticals in GTA — added 45 fresh leads to `campaign_leads`, broke
  the "no-eligible-leads" stall.
- **Blast verified live**: 12 emails sent via Resend (confirmed IDs in
  `outreach_history`) within minutes of backend restart. First real
  outbound since May 11.
- pytest: 6/6 green (`test_cto_tools_d49.py`), 38/38 green for D-42..D-49 set.

### Pending — requires user action on prod (preview cannot touch aurem.live)
- Apply rotated secrets (`JWT_SECRET`, `AUREM_ENCRYPTION_KEY`,
  `EMERGENCY_RESET_SECRET`) to `/etc/aurem/.env` on Hetzner and `sudo
  systemctl restart aurem-backend`.
- Set `CORS_ORIGINS=https://aurem.live,https://www.aurem.live` on prod
  (preview default allowlist already covers both).
- Reset prod admin password via prod MongoDB shell — see
  `/app/memory/test_credentials.md` for the exact `db.users.updateOne`
  command (bcrypt hash format).

## What's been implemented (earlier history)

See `/app/memory/tier1/progress.md` for the full ledger. Highlights:

- iter 331c: Sprint 6 — consent network, ora_session_metrics, Vanguard, portability audit.
- iter 331d: Developer Portal foundation (signup/OTP/BYOK/tokens) + Day-0 welcome email.
- iter 331e: Security guards (SSRF, file caps, session limits, output masking) + email sequence.
- iter 331f: Developer Portal frontend (10 pages) + AUREM CTO brand swap.
- iter 331g: Beta ticker, Swagger UI, Stripe (Starter/Builder/Pro packages + webhook).
- iter 332a: Emergent Specialist Swarm (validated-solutions cache, auto-escalation, smart routing).
- iter 332b Batch A: Enterprise foundation (unified_audit_log, /enterprise leads, admin UI shell).
- iter 332b Batch A-2: Enterprise Admin UI (branding, domain, API keys, overview dashboard).
- iter 332b Batch A-3 / B: Production auth fix (AdminGuard JWT exp check, logout revoke),
  Organizations entity, SAML SSO config storage, SCIM provisioning.
- iter 332b Batch B-2: Full python3-saml ACS handler.
- iter 332b Batch C: Data residency (CA default), SOC 2 PDF, SLA + MSA page.
- iter 332b C-2: Trust Center page, Compliance admin UI, Org Switcher sidebar.
- iter 332b C-3: Footer Trust Center link, SSO/SCIM settings UI, SOC 2 email lead gate.
- iter 332b D: Renewal Telegram nudges, SAML SP-side AuthnRequest signing.
- **iter 332b D-6 (this slice)**: Dev portal admin bypass actually works (decode_token bug),
  DevDashboard crash fix (undefined `purchases`), smart Sign-In redirect on homepage,
  System Overview public router actually mounted in registry.

## Active regression status

**721 / 721 GREEN** across iter 327d → 332b D-15.

## Latest slices

- **D-6**: dev portal admin bypass + DevDashboard crash + smart sign-in + System Overview public wiring.
- **D-7**: /admin/developer-signups page + real-time Telegram nudge.
- **D-8**: 24h sparkline on cockpit Pulse tile + CSV export.
- **D-9**: /developers/login page.
- **D-10**: AUREM CTO chat panel on dev dashboard + token-low popup + Connect rebuilt + expanded BYOK.
- **D-11**: Free tier moved to OpenRouter (one key, 3-model ladder).
- **D-12**: Roman-coin background image on dev portal.
- **D-13**: Collapsible dev portal sidebar (persisted to localStorage).
- **D-14**: Cloudflare 524 hardening — 28s per-model timeout + paid Llama/Mistral rungs + safe HTML-response parsing + trimmed history budget.
- **D-15**: SSE streaming for the dev chat — typing-out UX, 10× faster perceived latency. Includes happy-path, fallback, error, and token-wall test coverage.
- **D-30**: Pillar 4 false-red fix + Developer self-deploy (SSH + Docker) + Domain linking wizard + CTO chat copy button.
- **D-31** (PARKED on branch): `/app/aurem_cto/` isolated module skeleton (deploy + domain + chat-commits + unlock + vault). 3/3 isolation tests pass. Re-enable when onboarding ships.
- **D-32 (this slice)**: Build-first onboarding — Watchdog-approved scope pivot.
  - `/my/projects/new` is the new post-signup landing (no GitHub/server/domain prompts).
  - Multi-tenant FastAPI preview at `preview.aurem.live/<project-id>` rendering an inline manifest.
  - Token wallet: 1000 signup grant, cheap=1 / frontier=5, atomic conditional decrement (HTTP 402 with balance + cost on over-spend).
  - Social-share scrape (`+2500` on auto-approve) with admin pending queue + manual decide endpoint.
  - Go-Live checklist component (GitHub / server / domain / BYOK) — locked dashed-card until `progress >= 0.80`, unlocked green card after.
  - DevSignup + DevLogin redirect to `/my/projects/new` instead of `/developers/connect` and `/developers/dashboard`.
  - **Chat ↔ wallet ↔ progress wired**: `/api/developers/cto/chat/stream` accepts `project_id` + `model_tier`, debits the wallet atomically, parses `progress:` / `phase:` / `MANIFEST_PATCH:{…}` markers (balanced-brace JSON extractor) from the LLM reply, and emits `insufficient_tokens` SSE error when wallet is dry. PROGRESS CONTRACT added to the AUREM CTO system prompt.
  - Public preview at `/preview/:project_id` (no auth) reading the public manifest endpoint with 6s live-refresh.
- **D-33 (this slice)**:
  - **Stripe paywall UI gate**: `PaywallBlock` component renders inside the `insufficient_tokens` assistant message with one CTA to `/pricing` (existing Builder/Pro tiers) and one shortcut to `/my/projects/new#share` for the 2500-token earn flow. Zero new Stripe integration.
  - **Preview hosting setup doc**: `/app/aurem_cto/docs/PREVIEW_HOSTING_SETUP.md` — exact DNS A record + Caddy block + verification commands for `preview.aurem.live` (user runs on prod box).
  - **DB scan** completed before any gap code — 38 shadcn components, tailwind config live, parallel referral/wallet/deploy/health systems mapped, Docker templates already at `/app/aurem-cto/` (hyphen folder, distinct from D-31 underscore folder).
  - **AUREM CTO module re-enabled** — fixed sys.path init in registry block so `/aurem-cto/*` routes mount on boot. Verified by GET `/aurem-cto/vault/audit-log` returning HTTP 200.
  - **UI fix 1**: hover-reveal Preview + Deploy buttons on every assistant message that contains a code change (fenced ```code```, MANIFEST_PATCH, or `[step N/M]`). Mobile fallback via `@media (hover: none)`. Test-ids `dev-cto-preview-btn-<idx>` + `dev-cto-deploy-btn-<idx>`.
  - **UI fix 2**: auto-expanding chat textarea grows from 1 row up to 40vh, then scrolls inside. JS resize handler runs on every change.
  - **Gap 1 (Codebase Indexer)**: `aurem_cto/services/codebase_indexer.py` — pulls customer repo via existing BYOK PAT, indexes routes/models/components/deps, exposes `build_context_block(user_id)` which the chat-stream now injects as a system message before every turn.
  - **Gap 2 (Stack Selector)**: 4 templates at `aurem_cto/templates/stacks/` (react-fastapi default + nextjs-node + vue-express + plain-html), each with `docker-compose.yml` + `README.md`. Stack selector grid renders on `/my/projects/new`; `stack` field saved on project doc.
  - **Gap 3 (Trust Signals)**: `aurem_cto/routers/trust.py` — `/aurem-cto/trust/deploy-count` (aggregates 5 legacy collections), `/aurem-cto/trust/uptime` (24h % from `external_uptime_pings`), `/aurem-cto/gallery` (opt-in showcase). New collection `aurem_cto_public_gallery`. Public `/gallery` page lives at `PublicGallery.jsx`.
  - **Gap 4 (Engagement)**: `aurem_cto/routers/engagement.py` — `/aurem-cto/referrals/my` (ref link = `aurem.live/?ref=<user_id>`, reuses `referrals` + `verified_referrals`), `/aurem-cto/streak/me` (consecutive daily debits from `onboarding_token_wallets.ledger`). Streak chip + gallery toggle render on workspace header.
  - **Tests**: 9/9 in `/app/aurem_cto/tests/` green (3 isolation + 6 gap regression).
  - **Module isolation maintained** — 3 host imports declared; new whitelist entry for `aurem_cto_public_gallery` + 7 read-only host collections (developer_accounts, onboarding_*, referrals, external_uptime_pings) documented in the isolation test.
- **D-35 (this slice — Dogfood: aurem.live as a project)**:
  - **`is_production_dogfood` flag** on `onboarding_projects` with `production_warning`, `github_repo_url`, `production_host` fields. View serializer exposes them.
  - **Admin endpoint** `POST /api/onboarding/projects/dogfood/aurem-live-init` — idempotent seed of the `aurem-live-production` project for the calling admin. Skips the preview surface (`preview_url=""`), sets `progress=1.0`/`phase=production`/`domain.done=true` (aurem.live already lives). Non-admins blocked (401/403).
  - **Status endpoint** `GET /api/onboarding/projects/dogfood/aurem-live-status` — returns `github_linked`, `deploy_configured`, `indexer_fresh`, `last_dry_run`, `last_real_run`, `real_deploy_unlocked`.
  - **Dry-run deploy mode** added to `/aurem-cto/deploy/run` — runs `git fetch && docker compose config --quiet && echo DRY_RUN_OK` (no `git pull`, no `up -d`). Safe staging check.
  - **Production guard** — for projects with `is_production_dogfood=true`, a real `deploy` or `revert_to` is rejected with HTTP 409 `dry_run_required` unless a `dry_run` status=ok run exists for the same user within the last 24h. `rollback` stays unrestricted (emergency exit).
  - **Indexer fix** — `_fetch_user_pat` now reads `developer_github_links.pat_enc` (where `/api/developers/github/link` actually writes) with `developer_accounts` as legacy fallback. `_fetch_user_repo_url` prefers the project's saved repo URL.
  - **Frontend `ProjectWorkspace`** — red production-warning banner at top when `is_production_dogfood`, preview card hidden, new `DogfoodDeployPanel` showing GitHub/Server/Indexer pills + Refresh Index + Dry-Run + Real Deploy (gated on dry-run).
  - **Frontend `NewProjectFlow`** — admin-only `DogfoodSeedCard` (auto-hides on 403) with a one-click "Add aurem.live as project" button.
  - **Tests**: 5/5 new in `/app/backend/tests/test_dogfood_d35.py`; full active suite 20/20 green (5 D-35 + 6 D-32 + 9 aurem_cto isolation/gap).
  - **Status**: Scaffold complete. Real test deploy still needs the user to (1) paste GitHub PAT under `/developers/connect` → GitHub card, (2) save SSH host + private key under the Deploy card, then click "Refresh Index" and "Run dry-run deploy" inside the aurem-live-production workspace.
- **D-35-deploy-fix (2026-02)** — Production deploy logs showed `ModuleNotFoundError: No module named 'aurem_cto'`. Root cause: the package lived at `/app/aurem_cto/`, outside the backend container's shipped tree (only `/app/backend/` and `/app/frontend/` are packaged for Atlas-backed prod). Fix: **moved `/app/aurem_cto/` → `/app/backend/aurem_cto/`** so it ships with the backend image. Dropped the sys.path-mangling block in `registry.py` (now a plain `import aurem_cto`). `test_isolation.py` MODULE_ROOT now resolves from `__file__` instead of the hard-coded path. 20/20 tests still green; preview confirms `/aurem-cto/stacks` returns 200 after restart. **NO docker, supervisor, or env changes were needed.**
- **D-36 (2026-02 — AUREM Design System everywhere)** — Adopted Emil Kowalski's design-engineering rules as the *house style* for every LLM-emit surface across AUREM.
  - **`aurem_cto/prompts/aurem_design_system.md`** — full skill markdown (Sonner + Vaul mandate, animation decision framework, custom easing curves, `:active scale(0.97)`, popover origin awareness, reduced-motion + touch hover gates, performance rules, review-format table).
  - **`services/aurem_design_prompt.py`** — single shared loader (`get_aurem_design_prompt`, `inject_design_prompt`, `design_prompt_for_native_provider`) with sentinel marker `[AUREM-DESIGN-SKILL-v1]` for E2E asserts. Cached, idempotent, safe-fallback if markdown missing.
  - **Wired into every UI-emit path**: `services/dev_cto_chat.py` (AUREM CTO BYOK + free tiers + Anthropic + Gemini), `services/ora_brain.py` (ORA mode_2 code work), `services/aurem_ai_service.py` (every chat session created across the platform), `services/website_edit_worker.py` (customer-site HTML/CSS generator).
  - **Stack template baseline** — `aurem_cto/templates/stacks/react-fastapi/ui-design.css` ships with `--ease-out / --ease-drawer / --ease-in-out` curves, universal `:active scale(0.97)`, popover transform-origin override, Sonner toast easing, Vaul iOS drawer curve, `prefers-reduced-motion` guard. README updated to mandate Sonner + Vaul + lucide-react.
  - **Dogfood on aurem.live itself** — `frontend/src/styles/aurem-design.css` created and imported in `App.js` so the same rules render in production. Browser confirms `:root --ease-out` and `--ease-drawer` are live.
  - **Tests**: 9/9 new pytest in `test_design_skill_d36.py` (sentinel, idempotent injection, AUREM CTO BYOK path, AuremIntelligence session creation, stack template CSS + README, frontend CSS import). Full active suite **29/29 green**.
- **D-37 (2026-02 — Intent-aware AUREM CTO output contract)** — The single rigid prompt that forced `Plan + [step N/M] + NEXT_STEPS + progress + MANIFEST_PATCH` on every turn caused robotic replies for greetings, casual questions, and bug reports.
  - **`services/aurem_cto_intent.py`** — pure-heuristic classifier with 6 buckets (`build / question / conversational / diagnostic / strategic / unknown`). Zero extra LLM call per turn — ~0.1 ms latency. Each bucket has its own output-contract suffix appended as a system message tagged `[INTENT=<bucket>]`.
  - **Wired** into both `cto_chat()` and the SSE streaming path in `services/dev_cto_chat.py`. Latest user message is classified once, the matching suffix is inserted at index 1 of the messages list (right after the base AUREM CTO prompt, before the AUREM Design System suffix and the codebase context).
  - **Output contracts:**
    - *conversational*: 1-2 sentences, no markers, no NEXT_STEPS.
    - *question*: 1-3 paragraphs of plain English, no plan/steps, one NEXT_STEPS line.
    - *diagnostic*: root-cause first, then one fix with file path.
    - *strategic*: pull real numbers, 3 paragraphs or a table, decision-style chips.
    - *build*: full plan + step markers + progress + MANIFEST_PATCH + NEXT_STEPS (unchanged from D-32).
    - *unknown*: ask one clarifying question.
  - **Tests**: 34/34 new pytest in `test_intent_d37.py` (22 classifier table cases + 6 system-prompt-branch tests + 4 chat-integration tests verifying the right `[INTENT=...]` system message lands in the LLM message stack). Full active suite **63/63 green** across D-32 + D-33 + D-35 + D-36 + D-37 + aurem_cto isolation.
- **D-38 (2026-02 — Mobile sidebar · chat-button reorg · Admin Integration Health tracker)** — Four bundled fixes shipped in one batch.
  - **Mobile sidebar slide-in drawer** — `<DashboardShell>` now tracks `mobileSidebarOpen` state; a new hamburger in the topbar (`data-testid="dev-shell-mobile-menu"`) toggles the `av2-shell--mobile-open` class. CSS `@media (max-width: 767px)` block (in `styles/dashboard-theme.css`) makes `.av2-sidebar` `position: fixed; transform: translateX(-105%)` by default and slides it in on the modifier class with the iOS drawer curve. Backdrop click + route change auto-dismiss. Hamburger hidden ≥768 px.
  - **Chat panel button reorg** — replaced the hover-only `MessageActionButtons` (Preview/Deploy) with two pieces: a permanent `BubbleActionRow` (Copy + Rollback side-by-side) bottom-right of every assistant bubble, AND a new `ChatFooterActions` bar (Preview + Deploy) above the input. Solves the overlap with Copy on hover that customers reported. Rollback calls `/api/developers/deploy/run` with `mode=rollback,message_id=…` and gracefully routes to `/developers/connect#deploy` if the deploy target isn't configured.
  - **Admin Integration Health tracker** — `routers/admin_integrations_router.py` (admin-only) returns `summary` + 17 integrations across 5 groups (LLM, comms, payment, data, infra) with per-provider `status` pill (green/yellow/red/unset), `key_tail` (last 4 chars only — full key never leaked), `failures_24h` + `failures_7d` (with bucket breakdown), `last_failure_at`, `needs_recharge` boolean, plus `recharge_url` / `docs_url` links. Reads `api_key_health_log` written by `services/api_key_health_watcher.py`. Path `/api/admin/integrations/integrations/*` excluded from the 90-second boot-grace shortcut in `middleware/health_probe.py` (would otherwise return 204 No Content for the first 90 s). New admin page at `frontend/src/platform/AdminIntegrations.jsx`, routed at `/admin/integrations`, linked from `AdminShell` sidebar.
  - **Live campaign diagnosis (preview)** — endpoint returned 17 integrations: 7 healthy (openrouter, emergent_llm, twilio, telegram, stripe, tavily, cloudflare), 9 unset (anthropic, openai, gemini, whapi, sendgrid, linkedin, scrapingbee, hetzner, github_bot), 1 red (resend; from planted test row).
  - **Tests**: 7/7 `test_admin_integrations_d38.py` (auth gate, shape contract, key-leak guard, unset detection, 401-promotes-to-red, group coverage) + 5/5 `test_mobile_sidebar_d38.py` (CSS @media block present, hamburger testids, chat-button reorg, admin page + route wired). Full active suite **75/75 green**.
- **D-38 path-fix** — `aurem_cto` import in `registry.py` was failing in preview because cwd=/app there; D-35 fix only worked for production cwd=/app/backend. Registry now resolves `_backend_root` from `__file__` and prepends to `sys.path` so the plain `import aurem_cto` succeeds in BOTH environments.
- **D-39 (2026-02 — AUREM CTO self-awareness + language mirroring + anti-fabrication)** — Customer reports: AUREM CTO answered "how do you work" with a generic textbook workflow (component tree → state mgmt → tests → handoff), included Python pseudo-code, claimed it found "185 bugs across 22 rounds" (fabricated), and said it has no internet (false). Three fixes shipped:
  - **Base SYSTEM_PROMPT** in `services/dev_cto_chat.py` gained a "WHAT YOU ACTUALLY ARE" block listing the real architecture (intent classifier, AUREM Design System injection, codebase indexer, Tavily web search, dry-run + rollback deploy, 75+ pytests, token wallet 1/5 with 1,000-grant signup) so the LLM has facts to ground introspective answers in.
  - **Anti-fabrication rule** with explicit "185 bugs" negative example: *"NEVER fabricate numbers ... If a stat is not in your context or the codebase index, say so plainly: 'I don't have that number in front of me — want me to look?'"*. Also added "Code blocks are only for code you're producing — never for explaining your own thinking" to kill the Python-pseudo-code tic.
  - **Language mirroring** rule: match the developer's language (Hinglish, Hindi, French, Spanish, Punjabi), keep an English trailer in `(en: …)` so the founder reading logs can still scan quickly.
  - **Intent classifier** in `services/aurem_cto_intent.py` gained `_INTROSPECTIVE_RE` that catches English ("how do you work", "your workflow", "what can you do") AND Hinglish ("tum kaise kaam karte ho", "aap kya kar sakte ho"). Introspective phrasing now ALWAYS routes to `question` even when keywords like "plan" or "workflow" would otherwise hit the build bucket.
  - **Question branch prompt** updated to point the LLM at the base prompt's "WHAT YOU ACTUALLY ARE" block when the question is about the platform itself.
  - **Tests**: 14/14 new pytest in `test_self_awareness_d39.py` (architecture block present, fabrication rule + negative example present, language mirroring rule present, code-block-restriction present, 9 introspective phrases route to `question` across English + Hinglish, question branch references "WHAT YOU ACTUALLY ARE"). Full active suite **89/89 green** (D-32 + D-33 + D-35 + D-36 + D-37 + D-38 + D-39 + aurem_cto isolation).
- **D-40b (2026-02 — Founder caught LLM still dumping illustrative Python pseudo-code to a meta question)** — D-39 strengthened the prompt against fabricated stats, but free-tier deepseek/llama still wrote `def distill_idea(...)` + `patterns = {...}` to "illustrate" its own non-tech reply style. Fix is defense-in-depth, two layers:
  - **Prompt layer** — added an `ABSOLUTE RULE — ILLUSTRATIVE PSEUDO-CODE IS BANNED` block as the FIRST rule after the role line in `services/dev_cto_chat.py::SYSTEM_PROMPT`. Lists negative examples (`def distill_idea`, `if customer_type ==`, `patterns = {...}`) and positive replacements (numbered list, analogy, quoted prose dialogue). Explicitly: code blocks are ONLY legal when producing real code for the dev's actual project.
  - **Output-guard layer** — new `services/aurem_cto_output_guard.py::strip_illustrative_code(reply, *, intent, non_technical)`. For any non-build intent (`question / conversational / strategic / unknown / diagnostic`) OR whenever `non_technical=True`, every fenced block that looks Python/JS-ish (lang tag or `def/if/return/dict-literal` heuristic) is replaced with a single-line breadcrumb so paragraph flow survives. JSON/yaml/text fences are preserved. Wired into BOTH `cto_chat` (post-dispatch) AND `cto_chat_stream` (buffer-and-sanitize for non-build turns; build turns still stream live token-by-token).
  - **Tests**: 9/9 new pytest in `test_non_tech_no_code_d40b.py` (founder's exact prompt → `question` + non-tech True, guard strips all 3 Python blocks for question intent, guard strips when non_technical=True even with intent=build, guard preserves build replies for tech devs, guard preserves JSON config fences, guard is idempotent + handles empty/None). Full active suite **82/82 green** across the D-36→D-40b iter ring.
- **D-41 (2026-02 — AUREM-first rule, ban external dev tools in AUREM CTO replies)** — Founder caught AUREM CTO replying with a "Tools I Use" table that recommended Figma + Vercel + CodeSandbox + JSON Server + Mock Service Worker + Loom — sending customers *off* the platform. Defense-in-depth, two layers same as D-40b:
  - **Prompt layer** — added `AUREM-FIRST RULE — NEVER SUGGEST EXTERNAL DEV TOOLS` block to `SYSTEM_PROMPT` listing 7 banned tool categories (Figma/Sketch/Penpot for design, Vercel/Netlify/Heroku/Railway/Render/Fly.io for hosting, CodeSandbox/StackBlitz/Replit for sandboxes, Bolt.new/Lovable/V0/Cursor/Windsurf for AI build, MSW/JSON Server/Mockoon for mock APIs, Loom for share-back, Postman/Insomnia for API testing) with AUREM-native equivalents (AUREM Design System, preview.aurem.live, AUREM Deploy, public preview link, stack template mock_backend=true, /api/docs). Exempts upstream dependencies the dev already chose (GitHub, Docker, Stripe, AWS).
  - **Output-guard layer** — `services/aurem_cto_output_guard.py` gained `append_aurem_first_correction(reply)` and `apply_output_guards(reply, intent, non_technical)`. Detects banned tool names paired with recommendation verbs (use/try/recommend/host/deploy/prototype-in) within a 60-char window, OR a "Tools I Use / Recommended Tools" blanket header. Appends a non-destructive `[AUREM-FIRST CORRECTION]` footer mapping each banned tool → AUREM equivalent. Idempotent. Wired into both `cto_chat()` and `cto_chat_stream()` BUILD and non-build paths.
  - **Streaming UX** — build turns keep live token-by-token streaming; correction footer arrives as one final token event when banned tools were detected. Non-build turns buffer-and-sanitize as before.
  - **Tests**: 12/12 new pytest in `test_aurem_first_d41.py` (system prompt has rule + ban list + equivalents, correction fires on founder's caught reply, idempotent, no-op on safe replies, catches Vercel/CodeSandbox/Bolt/Lovable/V0, integration test with combined pseudo-code + tool-suggestion). Full active suite **85/85 green** across D-36→D-41 iter ring.
- **D-42 (2026-02 — GitHub OAuth one-click "Connect with GitHub")** — Founder asked to replace the 7-step PAT-paste flow with a 3-step OAuth popup. PAT stays as fallback below an "or paste a token manually" divider so users on environments without `GITHUB_CLIENT_ID`/`GITHUB_CLIENT_SECRET` configured aren't blocked.
  - **Backend**: `routers/developer_portal_router.py` gained `GET /api/developers/github/oauth/start` (mints CSRF `state` + PKCE S256 challenge, persists to new `developer_github_oauth_states` collection, returns the GitHub authorize URL with `scope=repo read:user`) and `GET /api/developers/github/oauth/callback` (validates state — one-time use, 10-min TTL — exchanges `code` via `httpx`, fetches `/user`, upserts encrypted access_token into the existing `developer_github_links` collection so the codebase indexer + deploy pipeline keep working unchanged with `auth_method="oauth"`). Returns a self-closing HTML popup page that `postMessage`'s the opener with `source: "aurem-github-oauth"`.
  - **Required env**: `GITHUB_CLIENT_ID` + `GITHUB_CLIENT_SECRET` (admin task — register OAuth App at github.com/settings/developers). Optional `GITHUB_OAUTH_REDIRECT_URI` (defaults to `{base_url}/api/developers/github/oauth/callback`).
  - **Frontend**: `DevConnect.jsx` `GitHubConnectCard` now renders the new `OneClickGitHubOAuth` button at the top (dark GitHub-style pill, lucide Github icon, `:active scale(0.97)`, popup centered, listens to `window.message`). PAT input stays below an "OR PASTE A TOKEN MANUALLY" divider. Returns helpful error when admin hasn't set credentials yet.
  - **Tests**: 9/9 new pytest in `test_github_oauth_d42.py` (503 when env unset, persists state + emits well-formed authorize URL with PKCE, respects custom redirect_uri env, callback rejects missing/invalid/expired state, propagates GitHub error param, happy path persists encrypted token + consumes state, handles token-exchange HTTP failure). Full active suite **94/94 green** across D-36→D-42 iter ring.
- **D-43 (2026-02 — Founder-controlled platform secrets UI + Maxx toggle + Planning bar + sidebar widgets)** — Massive UI/UX parity slice. Replaces the "edit .env on the server" workflow with a UI page, surfaces token balance + GitHub status + model-tier toggle in the sidebar, and promotes the AI's NEXT_STEPS to a top-of-chat Planning Bar.
  - **Backend `routers/platform_secrets_router.py`** — admin-gated `GET/PUT/DELETE /api/developers/settings/secrets[/{name}]`. Whitelist of 19 secret names (LLM providers, comms, payment, data, infra, GitHub OAuth). AES-256 (Fernet via `services.credential_crypto`) at rest. PUT also applies plaintext live to `os.environ` so every existing code path picks up the new key without a restart. New collection `platform_secrets`. Boot hook `apply_platform_secrets_to_env()` re-applies DB rows to env on every backend start. Wired in `routers/registry.py` next to admin-integrations.
  - **Frontend `PlatformCredentialsBlock.jsx`** — embedded at the top of `/developers/settings`. One row per whitelisted secret with group headers (GitHub, LLM, Comms, Payment, Data, Infra). Green dot = set, show/hide eye toggle, Save button with success flash, Delete (only enabled when source=db), env-set keys read-only. Encryption-warning banner when `AUREM_ENCRYPTION_KEY` is not set.
  - **Sidebar widgets `DeveloperShell.jsx`** — between nav and saved projects: (1) GitHub status pill with green dot when connected, (2) Maxx toggle (`Zap` icon, ON = frontier-model 5/turn, OFF = cheap 1/turn) — gated on `balance >= 5`, persists to localStorage, broadcasts `aurem-maxx-toggle` CustomEvent so the chat composer mirrors state, (3) Token progress bar (% of 1000-grant cap, low-state warning under 200). All three collapse to compact icons in the collapsed sidebar.
  - **Planning Bar `DevCtoChatPanel.jsx`** — moved NEXT_STEPS chips from below the input to the TOP of the chat panel as "Planning the next move…" + 3 chips with leading `+` button + `✕` dismiss icon. Pulsing dot (new `@keyframes aurem-pulse` in `dashboard-theme.css`) when streaming. Resets dismiss state when a new assistant turn produces fresh NEXT_STEPS.
  - **Maxx composer button** — between textarea and Send. Mirrors sidebar toggle via the shared CustomEvent. When ON, the stream POST body forces `model_tier=frontier`; OFF falls back to the prop value or `"cheap"`.
  - **Tests**: 6/6 new pytest in `test_platform_secrets_d43.py` (whitelist enforced, save persists encrypted envelope + applies to env, list never returns plaintext, delete clears DB + env, boot-hook reload from DB, env-only secrets still listed with source="env"). Full active suite **100/100 green** across D-36→D-43 iter ring. Frontend lint clean.
- **D-44 (2026-02 — Sidebar restructure + 3 new pages: Deploy / Domain / Database)** — Founder-spec sidebar with 4 grouped sections + 3 new Build-section pages backed by existing + 1 new admin endpoint.
  - **Sidebar `DeveloperShell.jsx`** — `DASH_NAV` now grouped: MAIN (Home), BUILD (Connect / Projects / Deploy / Domain / Database), DEVELOPER (Analytics / Examples / Tokens / API Docs / Status), ACCOUNT (Settings / Terms). Section labels render as small uppercase rows; collapse to 1px dividers in compact mode. Connect icon changed from `Github` → `Plug`. Projects route added as alias to Dashboard (`/developers/projects` → DevDashboard).
  - **`/developers/deploy` (`DevDeploy.jsx`)** — app thumbnail card with Rocket logo + aurem.live link + `Redeploy` button (POST `/api/developers/deploy/run`), live progress steps (Environment Ready → Building → Migrate DB → Export Secrets → Deploy → Health Check), recent deploys list from `/api/developers/deploy/history` (status dot + short run-id + mode + started_at).
  - **`/developers/domain` (`DevDomain.jsx`)** — 2 client-side toggles (Allow search engine crawling, Redirect root → www, persisted to localStorage), link form (domain + server IP) → `/api/developers/domain/config`, current-domain card with DNS records pre block.
  - **`/developers/database` (`DevDatabase.jsx`)** — admin-only read-only card. App name, provider, masked Mongo URL with show/hide eye, copy-to-clipboard, "Go to database" link to Atlas. Plaintext URL is NEVER sent to the client.
  - **Backend `routers/developer_database_router.py`** — new `GET /api/developers/database/info` (admin-gated). `_mask_mongo_url` helper strips `user:pass` and truncates host body, returns `mongodb+srv://****:****@clus…db.net/aurem`. Wired in `registry.py` next to platform-secrets.
  - **Merge**: BYOK rotate section removed from `DevSettings.jsx` (now lives next to BYOK paste form on `/developers/connect`). PlatformCredentialsBlock + sessions list + consent + danger-zone remain on Settings.
  - **Tests**: 7/7 new pytest in `test_dev_database_d44.py` (4 mask-helper edge cases, db_info masks credentials + raises 503 when MONGO_URL missing, sidebar nav constant exposes all 13 D-44 routes, DevSettings no longer has BYOK-rotate testid). Full active suite **108/108 green** across D-36→D-44 ring. Lint clean. Backend healthy (`/api/health` 200, `/api/developers/database/info` 401 unauthed as expected).
- **D-45 (2026-02 — Wire Deploy progress to real backend log stream + confirm Fork button absence)** — Replaced the client-side timer animation on `/developers/deploy` with a real log poller, and locked the "no Fork button" requirement with a regression test.
  - **Frontend `DevDeploy.jsx`** — exported pure helper `classifyStep(line)` maps a single deploy-log line to a step index 0-5 by matching anchors (`$ ` → 0, `git `/`from origin` → 1, `compose pull`/`pulling ` → 2, `creating`/`recreating` → 3, `started`/`running` → 4, `deploy_head=` → 5). New `startPolling(runId)` walks `/api/developers/deploy/log/{run_id}?since=<cursor>` every 900ms, monotonically advances `stepIdx` (never rewinds), keeps a tail of the last 60 lines in a `deploy-log-tail` `<pre>` console. On `status != "running"` the poller stops and either marks all steps complete or surfaces the failure + exit code.
  - **Tests**: 5/5 new pytest in `test_deploy_log_wire_d45.py` (deploy command still emits `git fetch` + `docker compose pull` + `DEPLOY_HEAD=` anchors so frontend classifier stays correct, `/deploy/log/{run_id}` endpoint signature unchanged with documented keys, DevDeploy keeps all classifier anchors, log-tail panel testid present, **no Fork button anywhere in `/app/frontend/src`** — scans for JSX `>Fork<` text + `GitFork` lucide imports + `data-testid="fork-…"`). Full active suite **113/113 green** across D-36→D-45 ring. Lint clean.
- **D-46 (2026-02 — One-click security-key generation + admin oversight)** — End-to-end security feature: customer one-click mints fresh `JWT_SECRET` + `AUREM_ENCRYPTION_KEY` + `CORS_ORIGINS`, AES-256 at rest, applied live to `os.environ` (no restart). Admin panel shows every customer's status, force-rotate available, plaintext never traverses the admin path.
  - **Backend `routers/security_keys_router.py`** — `POST /api/developers/security/generate-keys` (auth-gated) mints the triplet via `secrets.token_urlsafe(48)` + 32-byte b64 + literal `https://aurem.live`, marks any prior `active` row for the same user as `rotated`, stores AES-256 envelope per key (key-tail tracked), captures source IP, returns plaintext ONCE + applies live to env. `GET /api/developers/security/status` returns masked summary only. Admin: `GET /api/admin/security-keys` (aggregates by user), `GET /api/admin/security-keys/{user_id}/history`, `POST /api/admin/security-keys/{user_id}/rotate` (records `rotated_by_admin` + `rotation_reason`). Plaintext NEVER traverses the admin path.
  - **Frontend `SecurityKeysBlock.jsx`** — sits at the top of `/developers/settings` above `PlatformCredentialsBlock`. Generate/Rotate button with confirm prompt, plaintext-once panel with per-row Copy + Show/Hide + acknowledge-checkbox-gated dismiss. Below: tail-only masked summary card.
  - **Admin panel `AdminSecurityKeys.jsx`** at `/admin/security-keys` — 3 summary tiles (total / active / rotated), customer table, inline rotation-history drawer. Force-rotate prompts for reason.
  - **Bugfix `routers/_registry_lean_prune.py`** — narrowed `/api/admin/security` prefix-prune to exact-match (it was sweeping the D-46 admin routes); moved orphan subscription_router endpoint to `_PRUNE_EXACT` so its prune behavior is preserved.
- **D-47 (2026-02 — Save-to-GitHub dialog + per-turn model badge + security-rotation alerts)** — Three frequently-requested features shipped in one slice.
- **D-48 (2026-02 — Cache-bust on index.html + /api/version endpoint + bundle-vs-api version badge)** — Founder reported prod showing old UI after a redeploy. Caused by `index.html` being browser-cached. Hashed JS/CSS chunks were already content-addressed, but `index.html` had no `Cache-Control`, so the browser kept loading the old shell + the old chunk filenames.
  - **Frontend `public/index.html`** — added `<meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate, max-age=0">` + matching `Pragma`/`Expires` + `<meta name="aurem-build" content="iter-D-48">` marker.
  - **Backend `routers/version_router.py`** — new `GET /api/version` returns `{iter, iter_date, served_at, build_sha, commit_sha, commit_sha_full, commit_message, commit_at}` by shelling out to `git -C /app log` with `timeout=2`. Lets the founder curl prod and instantly confirm which commit is live.
  - **Frontend `DeveloperShell.jsx::BuildVersionBadge`** — small JetBrains-mono pill in the sidebar footer showing `bundle D-48 · api D-48`. Click to toggle reveal of the server's commit SHA. Highlights orange + "mismatch — hard refresh" when the running JS bundle doesn't match `/api/version`.
  - The three places that MUST stay in sync on every release: `backend/routers/version_router.py::ITER`, `frontend/public/index.html` meta tag, and `BUNDLE_ITER` in `DeveloperShell.jsx`. Mismatch is the badge's job to surface.
  - **Tests**: no new pytest — endpoint is shell-out trivial; the dev/api mismatch detector is the regression guard. Full active suite **130/130 green** unchanged. Lint clean. `/api/version` returns iter=D-48 + git commit live on preview.

  - **Backend `routers/github_save_router.py`** — three endpoints, all gated by `require_auth`. `GET /api/developers/github/repos` lists the user's repos via `/user/repos` (per_page=100, sorted by updated, owner+collaborator). `GET /api/developers/github/repos/{owner}/{repo}/branches` lists branches. `POST /api/developers/github/commit` reads the project's `onboarding_projects` row + `dev_cto_chats` history, builds `aurem/<project_id>/manifest.json` (JSON manifest) and `aurem/<project_id>/aurem-chat.md` (full history as markdown with `### USER`/`### ASSISTANT` headers), looks up each path's existing SHA, then PUTs both via `/repos/{owner}/{repo}/contents/{path}`. Uses the OAuth/PAT token persisted by D-42 (`developer_github_links.pat_enc`, decrypted via `services.byok_store`).
  - **Frontend `SaveToGithubDialog.jsx`** — modal dialog with 4 states: `pick` (repo dropdown loaded from `/repos` + branch dropdown loaded from `/branches` + commit-message input + Cancel/Save buttons), `saving`, `success` (big Github icon + "Successfully saved to GitHub!" + repo/branch/commit-sha + "View on GitHub" link + "Okay got it" close button), `error` (with Try-again). Connected-account green pill at the top.
  - **Chat composer button** — `data-testid="dev-cto-chat-save-github"` sits next to the Maxx pill; disabled until a project is loaded. Mounted as `<SaveToGithubDialog open={…} projectId={…} onClose={…} />` near `<LowBalanceModal>`.
  - **Per-turn model badge** — chat panel now stamps `{provider, model, tier}` onto each assistant message when the `meta` event arrives. Rendered as a small JetBrains-mono pill under the bubble content (`dev-cto-msg-model-badge-{i}`); orange for free tier, gold for BYOK, tooltip shows full `provider · model`.
  - **Security-rotation alerts `services/security_alerts.py`** — best-effort, never raises. Two channels (env-gated):
    - Slack via `SECURITY_ALERT_SLACK_WEBHOOK` (incoming-webhook URL)
    - Email via Resend (`SECURITY_ALERT_EMAIL` recipient + existing `RESEND_API_KEY`)
    Hooked into `security_keys_router.generate_security_keys` (fires `self_rotated` ONLY when a prior `rotated` row exists, so first-time generation is silent) and `admin_force_rotate` (fires `admin_force_rotated` with `reason` + `ip_address`). Optional `SECURITY_ALERT_FROM` env var customizes the From: address (default `alerts@aurem.live`).
  - **Tests**: 7/7 new pytest in `test_save_github_d47.py` (repos 401-when-unlinked + happy path, branches happy path, commit writes 2 files with valid JSON manifest + readable markdown chat, commit 401-when-unlinked, alerts no-op when unconfigured, alerts fire Slack with payload containing user + reason + IP). Full active suite **130/130 green** across D-36→D-47 ring. Lint clean (Python + JS). Backend healthy on preview (`/api/developers/github/repos` and `/api/developers/github/commit` both 401 unauthed as expected).

  - **Tests**: 10/10 new pytest in `test_security_keys_d46.py` (triplet randomness, generate returns plaintext-once + applies to env + tails match, rotate marks old row, status hides plaintext, admin list aggregates + hides plaintext, history returns all rows, force-rotate inserts new active row + records reason, 404 on rotate-with-no-keys, 503 when DB missing). The crypt_key fixture pre-touches `JWT_SECRET`/`CORS_ORIGINS` via monkeypatch so test-driven env mutations don't leak into D-38's JWT assertions. Full active suite **123/123 green** across D-36→D-46 ring. Lint clean. Backend healthy on preview (`/api/developers/security/status` 401, `/api/admin/security-keys` 401, `/api/admin/security` 404 as expected).

- **D-72 (2026-06-10 — Auth dedupe (P0 from D-71p audit) + Twilio circuit breaker)**
  - Two-part safety slice. Full detail in `/app/memory/CHANGELOG.md`.
  - **Auth dedupe**: `ai_platform_router.py` and `platform_auth_router.py` both registered `/api/platform/auth/login` + `/register`. Load order let the weaker handler (24h JWT, sync bcrypt, no JTI, no revocation) win prod. Deleted only the duplicates from `ai_platform_router.py` (kept its other endpoints intact). `platform_auth_router` is the sole owner — 7-day JWT with JTI, async bcrypt, real revocation via Mongo `jwt_blocklist`. E2E test hits real backend + real DB: login → token → /me → logout → revoked-token-401. **9/9 pass**.
  - **Twilio breaker**: TWILIO_AUTH_TOKEN is stale → every blast cycle was 401-ing on SMS + voice. New `services/twilio_auth_breaker.py` opens on the first 401, short-circuits every Twilio call (blast_service + shared provider both), and surfaces RED in Campaign Health with the actionable rotation hint. **11/11 pass**. Founder must rotate the token + `sudo supervisorctl restart backend`.
  - **D-72 suite**: 9 auth E2E + 11 twilio breaker + 9 router patches = **29/29 green** (2 pre-existing failures unrelated to D-72).

- **D-73 (2026-06-10 — Autonomous repair stack healed)**
  - Full detail in `/app/memory/CHANGELOG.md`.
  - **Root cause**: 442 stale rows in `pending_approvals` piled up over 2 months because 428 used pre-iter-325f schema (no `type`), 12 were Shannon scans against test-only domains (`*-test.com`), and 2 REAL `aurem.live` findings (HSTS missing, HTTP→HTTPS redirect missing) were buried. Plus `run_repair_tick` had a `db = db or _get_db()` PyMongo truthiness anti-pattern that crashed any explicit-db caller, and the string-vs-datetime mismatch (same as D-71p TTL bug) made staleness queries return 0.
  - **Real fix**: New admin router `routers/autonomous_repair_admin_router.py` with stats, archive-legacy, archive-test-targets, reject, restore, expire-stale, ensure-ttl endpoints. Full audit trail via `autonomous_repair_audit` collection. `run_repair_tick` patched: PyMongo truthiness fix + observability fields (`legacy_count`, `stale_awaiting`).
  - **Live result**: 442 → 2. The 2 surviving rows are real aurem.live security findings that got fresh DeepSeek V3.1 LLM proposals on the very next tick (HSTS header config + Nginx 301 redirect snippet, both tier-2 awaiting founder approval). 60-day TTL safety net active.
  - **12/12 pass**. Combined D-72 + D-73 = **32/32 green**.

- **D-73a + D-74 (2026-06-10 — Twilio auto-probe + Pillar health sweep)**
  - Full detail in `/app/memory/CHANGELOG.md` + `/app/memory/D74_PILLAR_HEALTH_REPORT.md`.
  - **D-73a**: Twilio breaker auto-probe (every 5 min while OPEN, auto-recovers on 200, no Telegram re-fire on 401 probe failures). After token rotation, founder no longer needs `supervisorctl restart` — breaker closes automatically. 5 new tests, **16/16** breaker total.
  - **D-74 timestamp audit**: Scanned all 614 Mongo collections for 14 timestamp field names → **797,928 rows across 359 collection-field pairs** store ISO strings (silently breaking TTL + range queries). Migration script `scripts/migrate_string_timestamps_d74.py` with dry-run mode, auto-discovery, graceful malformed-row handling. Dry-run: 0 unparseable across all 359 pairs in 4.3s. Live execution left to founder (per mongodump-first rule).
  - **D-74 stale-test furniture cleared**: Both pre-existing failures rewritten — `test_jwt_secret_resolves_via_three_tier_fallback` (locks the iter 272+324d K8s-safe resolver) and `test_tool_connect_uses_fernet_encryption_envelope` (locks the iter 326ww Fernet encryption). Each guards the current correct behavior.
  - **D-74 credential probes**: Live-probed every major external provider. Tavily HTTP 432 caught (new stale credential alongside the known Twilio). Resend / OpenRouter / Stripe / Apollo all 200 OK.
  - **Combined D-72 + D-73 + D-73a + D-74 suite**: **46/46 green**. Pillar health table in `/app/memory/D74_PILLAR_HEALTH_REPORT.md` — 4 pillars moved from red/yellow to green this session (Auth E2E, Autonomous Repair, Scheduler, Test Suite). 3 stay yellow/red: Twilio + Tavily creds (founder rotation), DB Health TTL (founder mongodump-then-migrate), Route Integrity (7 dedupes scoped for D-75).

- **D-75 part 1 (2026-06-10 — Pixel repair flow honesty rewrite)**
  - Full detail in `/app/memory/CHANGELOG.md`.
  - **The mock found**: `routers/customer_website_repair_router.py::_run_repair_job` was a 90-second timer that added `rng.randint(24, 38)` to scan score for fake "improvement", emitted scripted events ("Canary rollout to 10% complete / SOC 2 audit-chain appended / CDN cache invalidated / Full deploy confirmed"), built a hardcoded `improvements` array with `lcp * 0.35` fake math, and set status to `completed` even though the customer's website was never touched. This was on the customer-facing `/my/website` page.
  - **Real fix**: Replaced with honest 4-phase flow — real `website_audit_service.real_audit()` (live HTTP probes), real LLM plan via `llm_gateway_v2.route()` (DeepSeek V3.1, same as D-73 autonomous CTO), real email via Resend with honest error surface. Terminal status `plan_ready_for_customer` (not `completed`), `score_after: None` (only re-scan can set it). API response carries `honest_disclaimer` stating "we do not deploy code to your site".
  - **Live proof**: real DeepSeek V3.1 returned 4 actionable plan items in 5.8s for aurem.live (score_before=27/100); Resend delivered email `id: 34f5a2be-...` to founder's inbox (verified via Resend API as `last_event: delivered`).
  - **8/8 pass**. Combined D-72 → D-75 part 1 suite: **54/54 green**.

- **D-75 Part 2 items #1 + #2 (2026-06-10 — Creds Health dashboard + Route dedupe guard)**
  - Full detail in `/app/memory/CHANGELOG.md` + `/app/memory/D75_PART2_STATUS.md`.
  - **#1 `creds_health` dashboard**: new admin surface live-probing 16 providers (Twilio, Resend, OpenRouter, Stripe, Apollo, Tavily, GitHub, Emergent LLM, Firecrawl, Sentry, E2B, Vercel, ElevenLabs, Google PageSpeed, Deepgram, ORA). 4 endpoints (`/probe-all`, `/probe/{provider}`, `/history`, `/providers`). Secret-masking guaranteed (key_tail = last 4 only). 30-day TTL on history in BSON Date form so it actually fires. **First probe caught 2 NEW stale creds: ElevenLabs 401 + Google PageSpeed 403** alongside the known Twilio + Tavily. **9/9 tests**.
  - **#2 Route dedupe**: D-75 detector found **314 silent duplicate `(verb, path)` registrations** in `app.routes` — root cause was `registry.py`'s multiple lists each including the same router. Surgical idempotent guard wrapping `app.include_router` collapses **314 → 17** real handler conflicts (−94%). Added 2 boot-time observability functions: `_detect_duplicate_routes` (logs each remaining dupe with active+shadowed module paths) and `_detect_unwired_set_db_modules` (found **213 unwired modules** vs the audit's 8). Tests lock the dupe count ≤20. **5/5 tests**.
  - **Combined D-72 → D-75 #2 suite**: **68/68 green** — real backend, real Mongo, real OpenRouter, real Resend, real Twilio/ElevenLabs/Google probes. No mocks.

- **D-75 Part 2 #3 (2026-06-10 — Top-20 set_db wiring sweep)**
  - Full detail in `/app/memory/CHANGELOG.md` + `/app/memory/D75_PART3_STATUS.md`.
  - **The find**: D-75 #2 detector revealed 213 unwired `set_db()` modules silently 503'ing every endpoint.
  - **Fix**: `_wire_top_unwired_set_db_modules` in registry.py imports + calls `set_db(db)` for the top-20 ranked by `api_audit_log` traffic (`public_sites_router` 427k hits down to `ora_dispatcher_router` 9.2k hits). Detector unwired count: 212 → 193.
  - **Live proof**: 12 probed endpoints, zero 503s (5×200 serving real data, 7×404 = real routing not error).
  - **Strict-mode env gate**: `AUREM_STRICT_SETDB_WIRING=true` flips the boot warning to RuntimeError so any newly-added unwired module crashes loudly. Default false so the remaining 193 don't break boot.
  - **Detector regex hardening**: now handles single-line, multi-line, dotted-access, AND the `TOP_20_UNWIRED` runtime list — fewer false positives.
  - **Combined D-72 → D-75 #3 suite**: **71/71 green**.


## Backlog (P0 → P2)

### P0 — Production
- **Push to GitHub → redeploy aurem.live**. Prod is 6 batches behind (A-3 → D-6).
  Every redeploy day means broken-logout sessions in prod + missing Trust Center
  + dead admin /developers bypass + dashboard crash.

### P1 — Next slice
- GitHub OAuth flow for one-click connect (PAT already shipped in D-30).
- Real Atlas cluster-move automation for residency change requests
  (currently queues to `residency_change_requests` for manual ops).
- Backfill historical rows from 5 legacy audit collections into
  `unified_audit_log` (APScheduler job, ~40 LOC).
- Public "subprocessor changelog" RSS feed.

### P2 — Backlog
- RBAC complete wiring across ~80 routers — dedicated 2–3 day slice,
  new `user_rbac.py` with Owner/Admin/Developer/Viewer hierarchy.
- Pro tier recurring auto-renew (Stripe subscription mode swap).
- Service-account Google Calendar API for shared staff calendar.
- Friendlier 404 for stale ghost-* slugs.
- ConsentToggleCard shadcn → av2-card cleanup (20 LOC).
- SCIM PATCH partial-update + Groups endpoint.
- SP cert rotation playbook (current 10-year cert; calendar reminder at year 8).

## Architecture

- React SPA + FastAPI + MongoDB.
- Background tasks: APScheduler (renewal nudges, email sequence, sandbox cleanup, Vanguard).
- 3rd-party: Stripe (test+live key in pod env), Resend, Telegram, python3-saml, reportlab.

## Key endpoints (latest)

- `GET  /api/public/system-overview/stats` — public mirror (iter 332b D-6 wired).
- `GET  /api/developers/me` — accepts admin JWT (iter 332b D-6 fixed).
- `GET  /api/developers/me/purchases` — recent 3 payment_transactions.
- `POST /api/saml/{org_id}/acs` — full python3-saml validation.
- `GET  /api/compliance/{org_id}/soc2.pdf` — SOC 2 export.
- `POST /api/compliance/soc2/sample` — lead-gated PDF for Trust Center.
- `POST /api/enterprise/leads` — public contact-sales form.
- `POST /api/auth/admin/logout` — refresh-token revocation.

## Test credentials

See `/app/memory/test_credentials.md`.
