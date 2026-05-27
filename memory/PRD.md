# AUREM — Product Requirements Document

> Last updated 2026-05-24 (iter 332b D-6)

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
